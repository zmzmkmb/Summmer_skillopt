"""Deterministic offline harness for continual, budgeted skill routing.

This is Phase 0 instrumentation: synthetic rewards validate routing policies,
credit assignment, and total-token accounting before paid model calls. Synthetic
reward must never be reported as downstream LLM accuracy.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from functools import lru_cache
from itertools import combinations
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


@dataclass(frozen=True)
class RuleSpec:
    rule_id: str
    domain: str
    token_cost: int
    true_utility: float
    domain_utilities: tuple[tuple[str, float], ...] = ()
    rule_type: str = "standard"
    duplicate_of: str | None = None


@dataclass(frozen=True)
class TaskEvent:
    event_id: str
    domain: str
    relevant_rule_ids: tuple[str, ...]
    relevance: tuple[float, ...]
    input_tokens: int
    output_tokens: int = 8
    base_reward: float = 0.20
    utility_overrides: tuple[tuple[str, float], ...] = ()
    drift_phase: int = 0


@dataclass(frozen=True)
class MethodSpec:
    name: str
    policy: str
    credit: str
    estimator: str = "global"
    prior_identity: str = "copied-global"
    gate: str = "none"
    context_weight: float = 0.75
    context_weight_mode: str = "fixed"
    context_evidence_scale: float = 8.0
    context_min_weight: float = 0.0
    context_max_weight: float = 0.9
    gate_tolerance: float = 0.01
    gate_min_plasticity: float = 0.0
    prior_guard: str = "none"
    prior_guard_tolerance: float = 0.0
    prior_guard_probe_domains: str = "all"
    prior_guard_max_probes_per_domain: int = 0
    prior_guard_sequential: bool = False
    prior_guard_confidence_z: float = 1.96
    prior_guard_min_samples: int = 3
    prior_guard_min_accept_rounds: int = 0
    prior_guard_min_reset_rounds: int = 0
    prior_guard_min_harm_margin: float = 0.0
    prior_guard_recovery_window: int = 0
    prior_guard_max_recovery_slope: float | None = None
    prior_guard_relevance_cost_share: float = 1.0
    prior_guard_probe_order: str = "stream"
    prior_guard_reference: str = "relevance"
    prior_guard_evaluation: str = "frozen"


@dataclass
class OnlineUtilityState:
    prior_means: np.ndarray
    reward_sums: np.ndarray
    credit_counts: np.ndarray
    selection_counts: np.ndarray
    step: int = 0

    @classmethod
    def from_prior(cls, prior: np.ndarray, prior_strength: float = 2.0) -> "OnlineUtilityState":
        prior = np.asarray(prior, dtype=float)
        return cls(
            prior_means=prior.copy(),
            reward_sums=prior * float(prior_strength),
            credit_counts=np.full(len(prior), float(prior_strength), dtype=float),
            selection_counts=np.zeros(len(prior), dtype=float),
        )

    @property
    def means(self) -> np.ndarray:
        return np.divide(
            self.reward_sums,
            self.credit_counts,
            out=self.prior_means.copy(),
            where=self.credit_counts > 0,
        )

    def means_for(self, domain: str) -> np.ndarray:
        del domain
        return self.means

    def selection_counts_for(self, domain: str) -> np.ndarray:
        del domain
        return self.selection_counts

    def step_for(self, domain: str) -> int:
        del domain
        return self.step

    def beta_parameters(self, domain: str) -> tuple[np.ndarray, np.ndarray]:
        del domain
        alpha = 1.0 + np.maximum(self.reward_sums, 0.0)
        beta = 1.0 + np.maximum(self.credit_counts - self.reward_sums, 0.0)
        return alpha, beta

    def update(
        self, indices: Sequence[int], credits: Sequence[float], domain: str | None = None,
    ) -> None:
        del domain
        if len(indices) != len(credits):
            raise ValueError("indices and credits must have the same length")
        for raw_index, raw_credit in zip(indices, credits):
            index = int(raw_index)
            credit = float(np.clip(raw_credit, 0.0, 1.0))
            self.reward_sums[index] += credit
            self.credit_counts[index] += 1.0
            self.selection_counts[index] += 1.0
        self.step += 1

    def observe_selection(self, indices: Sequence[int], domain: str | None = None) -> None:
        del domain
        self.step += 1
        for raw_index in indices:
            self.selection_counts[int(raw_index)] += 1.0

    def corrupt(self, mode: str, rng: np.random.Generator) -> None:
        corrupted = _corrupt_means(self.means, mode=mode, rng=rng)
        self.reward_sums = corrupted * self.credit_counts

    def clone(self) -> "OnlineUtilityState":
        return OnlineUtilityState(
            prior_means=self.prior_means.copy(),
            reward_sums=self.reward_sums.copy(),
            credit_counts=self.credit_counts.copy(),
            selection_counts=self.selection_counts.copy(),
            step=self.step,
        )


@dataclass
class ContextualUtilityState:
    global_state: OnlineUtilityState
    domain_states: dict[str, OnlineUtilityState]
    default_domain_prior: np.ndarray | None = None
    default_domain_prior_strength: float = 2.0
    context_weight: float = 0.75
    context_weight_mode: str = "fixed"
    context_evidence_scale: float = 8.0
    context_min_weight: float = 0.0
    context_max_weight: float = 0.9

    @classmethod
    def from_prior(
        cls, prior: np.ndarray, domains: Sequence[str], *, prior_strength: float = 2.0,
        context_weight: float = 0.75, context_weight_mode: str = "fixed",
        context_evidence_scale: float = 8.0, context_min_weight: float = 0.0,
        context_max_weight: float = 0.9,
    ) -> "ContextualUtilityState":
        if not 0.0 <= context_weight <= 1.0:
            raise ValueError("context_weight must be within [0, 1]")
        if context_weight_mode not in VALID_CONTEXT_WEIGHT_MODES:
            raise ValueError(f"Unsupported context weight mode: {context_weight_mode}")
        if context_evidence_scale <= 0.0:
            raise ValueError("context_evidence_scale must be positive")
        if not 0.0 <= context_min_weight <= context_max_weight <= 1.0:
            raise ValueError("adaptive context weights must satisfy 0 <= min <= max <= 1")
        return cls(
            global_state=OnlineUtilityState.from_prior(prior, prior_strength=prior_strength),
            domain_states={
                str(domain): OnlineUtilityState.from_prior(prior, prior_strength=prior_strength)
                for domain in dict.fromkeys(domains)
            },
            default_domain_prior=prior.copy(),
            default_domain_prior_strength=float(prior_strength),
            context_weight=float(context_weight),
            context_weight_mode=str(context_weight_mode),
            context_evidence_scale=float(context_evidence_scale),
            context_min_weight=float(context_min_weight),
            context_max_weight=float(context_max_weight),
        )

    @property
    def means(self) -> np.ndarray:
        """Global estimates used for cross-run calibration against global truth."""
        return self.global_state.means

    def _domain_state(self, domain: str) -> OnlineUtilityState:
        if domain not in self.domain_states:
            prior = (
                self.global_state.prior_means
                if self.default_domain_prior is None else self.default_domain_prior
            )
            strength = (
                float(self.global_state.credit_counts[0])
                if self.default_domain_prior is None else self.default_domain_prior_strength
            )
            self.domain_states[domain] = OnlineUtilityState.from_prior(
                prior, prior_strength=float(strength),
            )
        return self.domain_states[domain]

    def context_weights_for(self, domain: str) -> np.ndarray:
        local = self._domain_state(domain)
        if self.context_weight_mode == "fixed":
            return np.full(len(local.means), self.context_weight, dtype=float)
        evidence = np.asarray(local.selection_counts, dtype=float)
        progress = evidence / (evidence + self.context_evidence_scale)
        return self.context_min_weight + (
            self.context_max_weight - self.context_min_weight
        ) * progress

    def means_for(self, domain: str) -> np.ndarray:
        local = self._domain_state(domain).means
        weights = self.context_weights_for(domain)
        return (1.0 - weights) * self.global_state.means + weights * local

    def selection_counts_for(self, domain: str) -> np.ndarray:
        return self._domain_state(domain).selection_counts

    def step_for(self, domain: str) -> int:
        return self._domain_state(domain).step

    def beta_parameters(self, domain: str) -> tuple[np.ndarray, np.ndarray]:
        local = self._domain_state(domain)
        means = self.means_for(domain)
        weights = self.context_weights_for(domain)
        effective_counts = (
            (1.0 - weights) * self.global_state.credit_counts
            + weights * local.credit_counts
        )
        alpha = 1.0 + np.maximum(means * effective_counts, 0.0)
        beta = 1.0 + np.maximum((1.0 - means) * effective_counts, 0.0)
        return alpha, beta

    def update(self, indices: Sequence[int], credits: Sequence[float], domain: str | None = None) -> None:
        if domain is None:
            raise ValueError("contextual updates require a domain")
        self.global_state.update(indices, credits)
        self._domain_state(domain).update(indices, credits)

    def observe_selection(self, indices: Sequence[int], domain: str | None = None) -> None:
        if domain is None:
            raise ValueError("contextual observations require a domain")
        self.global_state.observe_selection(indices)
        self._domain_state(domain).observe_selection(indices)

    def corrupt(self, mode: str, rng: np.random.Generator) -> None:
        self.global_state.corrupt(mode, rng)
        for domain, state in sorted(self.domain_states.items()):
            state.corrupt(mode, np.random.default_rng(_stable_seed(rng.integers(2**32), domain)))

    def clone(self) -> "ContextualUtilityState":
        return ContextualUtilityState(
            global_state=self.global_state.clone(),
            domain_states={domain: state.clone() for domain, state in self.domain_states.items()},
            default_domain_prior=(
                None if self.default_domain_prior is None else self.default_domain_prior.copy()
            ),
            default_domain_prior_strength=self.default_domain_prior_strength,
            context_weight=self.context_weight,
            context_weight_mode=self.context_weight_mode,
            context_evidence_scale=self.context_evidence_scale,
            context_min_weight=self.context_min_weight,
            context_max_weight=self.context_max_weight,
        )


UtilityState = OnlineUtilityState | ContextualUtilityState

@dataclass(frozen=True)
class SyntheticStream:
    rules: tuple[RuleSpec, ...]
    blocks: tuple[tuple[TaskEvent, ...], ...]
    probes: dict[str, tuple[TaskEvent, ...]]
    probes_by_phase: dict[int, dict[str, tuple[TaskEvent, ...]]] = field(default_factory=dict)


VALID_POLICIES = {
    "random", "relevance", "greedy-utility", "ucb", "thompson",
    "exact-utility", "oracle",
}
VALID_CREDITS = {"none", "shared", "leave-one-out", "oracle-per-rule"}
VALID_CONDITIONS = {"all-cold", "noisy", "shuffled", "adversarial", "oracle"}
VALID_ESTIMATORS = {"global", "contextual"}
VALID_PRIOR_IDENTITIES = {"global", "copied-global", "global-only", "contextual"}
VALID_CONTEXT_WEIGHT_MODES = {"fixed", "adaptive"}
VALID_GATES = {"none", "non-regression", "balanced"}
VALID_PRIOR_GUARDS = {"none", "reset-cold", "fallback-relevance", "selective-cold"}
VALID_PRIOR_GUARD_PROBE_ORDERS = {"stream", "selection-disagreement"}
VALID_PRIOR_GUARD_REFERENCES = {"relevance", "cold-router"}
VALID_PRIOR_GUARD_EVALUATIONS = {"frozen", "rollout"}
VALID_CORRUPTIONS = {"none", "shuffled", "adversarial"}


def _build_utility_state(
    method: MethodSpec, prior: np.ndarray, domains: Sequence[str], prior_strength: float,
) -> UtilityState:
    if method.estimator == "contextual":
        return ContextualUtilityState.from_prior(
            prior, tuple(domains), prior_strength=prior_strength,
            context_weight=method.context_weight,
            context_weight_mode=method.context_weight_mode,
            context_evidence_scale=method.context_evidence_scale,
            context_min_weight=method.context_min_weight,
            context_max_weight=method.context_max_weight,
        )
    return OnlineUtilityState.from_prior(prior, prior_strength=prior_strength)


def _stable_seed(*parts: object) -> int:
    text = "|".join(str(part) for part in parts)
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16) % (2**32)


def _corrupt_means(
    means: np.ndarray, *, mode: str, rng: np.random.Generator,
) -> np.ndarray:
    if mode not in VALID_CORRUPTIONS:
        raise ValueError(f"Unsupported corruption mode: {mode}")
    values = np.asarray(means, dtype=float)
    if mode == "none":
        return values.copy()
    if mode == "shuffled":
        return values[rng.permutation(len(values))]
    order = np.argsort(values, kind="stable")
    result = np.empty_like(values)
    result[order] = np.sort(values)[::-1]
    return result


def rule_utility_for_domain(rule: RuleSpec, domain: str) -> float:
    utilities = dict(rule.domain_utilities)
    return float(utilities.get(domain, rule.true_utility))


def effective_rule_utility(event: TaskEvent, rule: RuleSpec) -> float:
    overrides = dict(event.utility_overrides)
    return float(overrides.get(rule.rule_id, rule_utility_for_domain(rule, event.domain)))


def generate_synthetic_stream(
    *, seed: int, n_rules: int, domains: Sequence[str], block_order: Sequence[str],
    tasks_per_block: int, probe_tasks_per_domain: int = 8,
) -> SyntheticStream:
    """Create a domain-shift stream with difficult same-domain distractors."""
    if n_rules < len(domains) * 3:
        raise ValueError("n_rules must provide at least three rules per domain")
    if not domains or any(domain not in domains for domain in block_order):
        raise ValueError("block_order must contain only configured domains")
    rng = np.random.default_rng(seed)
    rules = tuple(
        RuleSpec(
            rule_id=f"synthetic-rule-{index:04d}",
            domain=str(domains[index % len(domains)]),
            token_cost=int(rng.integers(24, 81)),
            true_utility=float(rng.uniform(0.20, 0.98)),
        )
        for index in range(n_rules)
    )
    domain_indices = {
        domain: np.asarray([i for i, rule in enumerate(rules) if rule.domain == domain], dtype=int)
        for domain in domains
    }

    def make_event(domain: str, event_id: str, local_rng: np.random.Generator) -> TaskEvent:
        candidates = domain_indices[domain]
        relevant_count = min(3, max(2, len(candidates) // 6))
        relevant = {int(i) for i in local_rng.choice(candidates, size=relevant_count, replace=False)}
        scores = []
        for index, rule in enumerate(rules):
            if index in relevant:
                score = local_rng.uniform(0.68, 1.00)
            elif rule.domain == domain:
                score = local_rng.uniform(0.42, 0.96)
            else:
                score = local_rng.uniform(0.01, 0.30)
            scores.append(float(score))
        return TaskEvent(
            event_id=event_id,
            domain=domain,
            relevant_rule_ids=tuple(rules[i].rule_id for i in sorted(relevant)),
            relevance=tuple(scores),
            input_tokens=int(local_rng.integers(90, 181)),
        )

    blocks = []
    for block_index, domain in enumerate(block_order):
        local_rng = np.random.default_rng(_stable_seed(seed, "block", block_index, domain))
        blocks.append(tuple(
            make_event(domain, f"block-{block_index:02d}-{domain}-{i:04d}", local_rng)
            for i in range(tasks_per_block)
        ))
    probes = {}
    for domain in domains:
        local_rng = np.random.default_rng(_stable_seed(seed, "probe", domain))
        probes[domain] = tuple(
            make_event(domain, f"probe-{domain}-{i:04d}", local_rng)
            for i in range(probe_tasks_per_domain)
        )
    return SyntheticStream(rules=rules, blocks=tuple(blocks), probes=probes)


def generate_contextual_synthetic_stream(
    *, seed: int, n_rules: int, domains: Sequence[str], block_order: Sequence[str],
    tasks_per_block: int, probe_tasks_per_domain: int = 8,
) -> SyntheticStream:
    """Create a stream with transfer, conflicts, duplicates, malicious rules, and drift."""
    if n_rules < max(20, len(domains) * 6):
        raise ValueError("contextual streams require at least 20 rules and six per domain")
    if not domains or any(domain not in domains for domain in block_order):
        raise ValueError("block_order must contain only configured domains")
    domains = tuple(str(domain) for domain in domains)
    rng = np.random.default_rng(seed)
    rules_list: list[RuleSpec] = []
    specialist_ids: list[int] = []

    for index in range(n_rules):
        home_index = index % len(domains)
        home = domains[home_index]
        slot = index % 10
        duplicate_of: str | None = None
        if slot <= 3:
            rule_type = "specialist"
            utilities = {
                domain: float(rng.uniform(0.58, 0.96)) if domain == home
                else float(rng.uniform(-0.30, 0.12))
                for domain in domains
            }
            specialist_ids.append(index)
        elif slot <= 5:
            rule_type = "shared"
            utilities = {domain: float(rng.uniform(0.38, 0.82)) for domain in domains}
        elif slot <= 7:
            rule_type = "conflict"
            negative_domain = domains[(home_index + 1) % len(domains)]
            utilities = {}
            for domain in domains:
                if domain == home:
                    utilities[domain] = float(rng.uniform(0.62, 0.96))
                elif domain == negative_domain:
                    utilities[domain] = float(rng.uniform(-0.88, -0.38))
                else:
                    utilities[domain] = float(rng.uniform(-0.05, 0.28))
        elif slot == 8:
            rule_type = "malicious"
            utilities = {domain: float(rng.uniform(-0.92, -0.42)) for domain in domains}
        else:
            rule_type = "duplicate"
            if not specialist_ids:
                raise RuntimeError("duplicate rule requires a prior specialist")
            target_index = specialist_ids[index % len(specialist_ids)]
            target = rules_list[target_index]
            duplicate_of = target.rule_id
            home = target.domain
            utilities = {
                domain: float(np.clip(value + rng.normal(0.0, 0.02), -1.0, 1.0))
                for domain, value in target.domain_utilities
            }
        token_low, token_high = (18, 48) if rule_type == "malicious" else (24, 81)
        rules_list.append(RuleSpec(
            rule_id=f"context-rule-{index:04d}",
            domain=home,
            token_cost=int(rng.integers(token_low, token_high)),
            true_utility=float(np.mean(list(utilities.values()))),
            domain_utilities=tuple((domain, utilities[domain]) for domain in domains),
            rule_type=rule_type,
            duplicate_of=duplicate_of,
        ))
    rules = tuple(rules_list)

    drift_overrides: dict[str, dict[str, float]] = {}
    for domain in domains:
        candidates = [
            rule for rule in rules
            if rule.rule_type in {"specialist", "conflict"}
            and abs(rule_utility_for_domain(rule, domain)) >= 0.35
        ]
        candidates.sort(key=lambda rule: (-abs(rule_utility_for_domain(rule, domain)), rule.rule_id))
        overrides: dict[str, float] = {}
        for rule in candidates[:3]:
            base = rule_utility_for_domain(rule, domain)
            shifted = -0.72 * base if base > 0.0 else min(0.92, abs(base) + 0.28)
            overrides[rule.rule_id] = float(np.clip(shifted, -0.95, 0.95))
        drift_overrides[domain] = overrides

    def make_event(
        domain: str, event_id: str, local_rng: np.random.Generator, phase: int,
    ) -> TaskEvent:
        overrides = drift_overrides[domain] if phase > 0 else {}
        utilities = np.asarray([
            overrides.get(rule.rule_id, rule_utility_for_domain(rule, domain)) for rule in rules
        ], dtype=float)
        good = np.flatnonzero(utilities >= 0.35)
        harmful = np.flatnonzero(utilities <= -0.25)
        good_count = min(3, len(good))
        harmful_count = min(1, len(harmful))
        relevant: set[int] = set()
        if good_count:
            relevant.update(int(i) for i in local_rng.choice(good, size=good_count, replace=False))
        if harmful_count:
            relevant.update(int(i) for i in local_rng.choice(harmful, size=harmful_count, replace=False))
        scores: list[float] = []
        relevant_ids = {rules[index].rule_id for index in relevant}
        for index, rule in enumerate(rules):
            if index in relevant:
                low = 0.84 if utilities[index] < 0.0 else 0.72
                score = local_rng.uniform(low, 1.00)
            elif rule.duplicate_of in relevant_ids:
                score = local_rng.uniform(0.66, 0.95)
            elif rule.rule_type in {"shared", "conflict"}:
                score = local_rng.uniform(0.18, 0.72)
            elif rule.domain == domain:
                score = local_rng.uniform(0.32, 0.84)
            else:
                score = local_rng.uniform(0.01, 0.34)
            scores.append(float(score))
        return TaskEvent(
            event_id=event_id,
            domain=domain,
            relevant_rule_ids=tuple(sorted(relevant_ids)),
            relevance=tuple(scores),
            input_tokens=int(local_rng.integers(90, 181)),
            utility_overrides=tuple(sorted(overrides.items())),
            drift_phase=phase,
        )

    drift_start = max(len(domains), len(block_order) // 2)
    blocks = []
    for block_index, domain in enumerate(block_order):
        phase = int(block_index >= drift_start)
        local_rng = np.random.default_rng(_stable_seed(seed, "context-block", block_index, domain, phase))
        blocks.append(tuple(
            make_event(domain, f"context-{block_index:02d}-{domain}-{i:04d}", local_rng, phase)
            for i in range(tasks_per_block)
        ))
    probes_by_phase: dict[int, dict[str, tuple[TaskEvent, ...]]] = {}
    for phase in (0, 1):
        phase_probes: dict[str, tuple[TaskEvent, ...]] = {}
        for domain in domains:
            local_rng = np.random.default_rng(_stable_seed(seed, "context-probe", phase, domain))
            phase_probes[domain] = tuple(
                make_event(domain, f"context-probe-p{phase}-{domain}-{i:04d}", local_rng, phase)
                for i in range(probe_tasks_per_domain)
            )
        probes_by_phase[phase] = phase_probes
    return SyntheticStream(
        rules=rules,
        blocks=tuple(blocks),
        probes=probes_by_phase[0],
        probes_by_phase=probes_by_phase,
    )


def initialise_utilities(rules: Sequence[RuleSpec], *, condition: str, seed: int) -> np.ndarray:
    if condition not in VALID_CONDITIONS:
        raise ValueError(f"Unsupported utility condition: {condition}")
    truth = np.asarray([rule.true_utility for rule in rules], dtype=float)
    rng = np.random.default_rng(seed)
    if condition == "all-cold":
        return np.full(len(rules), 0.5, dtype=float)
    if condition == "noisy":
        return np.clip(truth + rng.normal(0.0, 0.25, size=len(rules)), 0.0, 1.0)
    if condition == "shuffled":
        return truth[rng.permutation(len(rules))]
    if condition == "adversarial":
        order = np.argsort(truth)
        result = np.empty_like(truth)
        result[order] = np.sort(truth)[::-1]
        return result
    return truth.copy()


def initialise_contextual_utilities(
    rules: Sequence[RuleSpec], *, domains: Sequence[str], condition: str, seed: int,
) -> dict[str, np.ndarray]:
    """Build per-domain priors without conflating global and contextual identity."""
    if condition not in VALID_CONDITIONS:
        raise ValueError(f"Unsupported utility condition: {condition}")
    priors: dict[str, np.ndarray] = {}
    for domain in dict.fromkeys(str(item) for item in domains):
        truth = np.asarray([rule_utility_for_domain(rule, domain) for rule in rules], dtype=float)
        rng = np.random.default_rng(_stable_seed(seed, "contextual-prior", condition, domain))
        if condition == "all-cold":
            prior = np.full(len(rules), 0.5, dtype=float)
        elif condition == "noisy":
            prior = np.clip(truth + rng.normal(0.0, 0.25, size=len(rules)), -1.0, 1.0)
        elif condition == "shuffled":
            prior = truth[rng.permutation(len(rules))]
        elif condition == "adversarial":
            prior = _corrupt_means(truth, mode="adversarial", rng=rng)
        else:
            prior = truth.copy()
        priors[domain] = prior
    return priors


def build_prior_identity_state(
    *, rules: Sequence[RuleSpec], domains: Sequence[str], method: MethodSpec,
    condition: str, identity: str, seed: int, prior_strength: float,
) -> tuple[UtilityState, np.ndarray, dict[str, np.ndarray]]:
    """Construct a typed global, global-only, or explicit contextual prior state."""
    if identity not in VALID_PRIOR_IDENTITIES:
        raise ValueError(f"Unsupported prior identity: {identity}")
    normalized_identity = "copied-global" if identity == "global" else identity
    global_prior = initialise_utilities(rules, condition=condition, seed=seed)
    state = _build_utility_state(method, global_prior, domains, prior_strength)
    if normalized_identity in {"global-only", "contextual"} and not isinstance(
        state, ContextualUtilityState
    ):
        raise ValueError(f"{normalized_identity} prior identity requires estimator='contextual'")
    if normalized_identity == "contextual":
        domain_priors = initialise_contextual_utilities(
            rules, domains=domains, condition=condition, seed=seed,
        )
        state.domain_states = {
            domain: OnlineUtilityState.from_prior(prior, prior_strength=prior_strength)
            for domain, prior in domain_priors.items()
        }
        state.default_domain_prior = np.full(len(rules), 0.5, dtype=float)
        state.default_domain_prior_strength = float(prior_strength)
    elif normalized_identity == "global-only":
        cold_prior = np.full(len(rules), 0.5, dtype=float)
        domain_priors = {str(domain): cold_prior.copy() for domain in domains}
        state.domain_states = {
            domain: OnlineUtilityState.from_prior(prior, prior_strength=prior_strength)
            for domain, prior in domain_priors.items()
        }
        state.default_domain_prior = cold_prior.copy()
        state.default_domain_prior_strength = float(prior_strength)
    else:
        domain_priors = {str(domain): global_prior.copy() for domain in domains}
    return state, global_prior, domain_priors


def _rule_contribution(event: TaskEvent, rule: RuleSpec, index: int) -> float:
    relevance = float(event.relevance[index])
    if rule.rule_id in event.relevant_rule_ids:
        if rule.domain_utilities or event.utility_overrides:
            utility = effective_rule_utility(event, rule)
            return 0.07 + 0.34 * utility + 0.07 * relevance
        return 0.12 + 0.22 * rule.true_utility + 0.08 * relevance
    if rule.domain == event.domain:
        return -0.025 - 0.035 * relevance
    return -0.035 - 0.025 * (1.0 - relevance)


def expected_reward(event: TaskEvent, rules: Sequence[RuleSpec], selected_indices: Sequence[int]) -> float:
    score = float(event.base_reward)
    seen_families: set[str] = set()
    for index in dict.fromkeys(int(i) for i in selected_indices):
        rule = rules[index]
        contribution = _rule_contribution(event, rule, index)
        family = rule.duplicate_of or rule.rule_id
        if family in seen_families:
            contribution = min(contribution, 0.0) - 0.04
        seen_families.add(family)
        score += contribution
    return float(np.clip(score, 0.0, 1.0))


def _budgeted_order(order: Iterable[int], rules: Sequence[RuleSpec], *, top_k: int, budget: int) -> list[int]:
    selected: list[int] = []
    used = 0
    for raw_index in order:
        index = int(raw_index)
        cost = int(rules[index].token_cost)
        if used + cost > budget:
            continue
        selected.append(index)
        used += cost
        if len(selected) >= top_k:
            break
    return selected


def exact_budgeted_selection(
    values: Sequence[float], rules: Sequence[RuleSpec], *, top_k: int, budget: int,
) -> list[int]:
    """Exact cardinality-constrained 0/1 knapsack with deterministic ties."""
    states: dict[tuple[int, int], tuple[float, tuple[int, ...]]] = {(0, 0): (0.0, ())}
    for index, raw_value in enumerate(values):
        value, cost = float(raw_value), int(rules[index].token_cost)
        for (used, count), (current_value, selected) in list(states.items()):
            if count >= top_k or used + cost > budget:
                continue
            key = (used + cost, count + 1)
            candidate = (current_value + value, (*selected, index))
            incumbent = states.get(key)
            if incumbent is None or candidate[0] > incumbent[0] + 1e-12 or (
                abs(candidate[0] - incumbent[0]) <= 1e-12 and candidate[1] < incumbent[1]
            ):
                states[key] = candidate
    best = max(states.values(), key=lambda item: (item[0], -len(item[1]), tuple(-i for i in item[1])))
    return list(best[1])


@lru_cache(maxsize=16384)
def _oracle_budgeted_selection_cached(
    event: TaskEvent, rules: tuple[RuleSpec, ...], top_k: int, budget: int,
) -> tuple[int, ...]:
    best_reward = expected_reward(event, rules, ())
    best: tuple[int, ...] = ()
    indices = range(len(rules))
    for count in range(1, top_k + 1):
        for selected in combinations(indices, count):
            if sum(rules[index].token_cost for index in selected) > budget:
                continue
            reward = expected_reward(event, rules, selected)
            if reward > best_reward + 1e-12 or (
                abs(reward - best_reward) <= 1e-12 and selected < best
            ):
                best_reward = reward
                best = selected
    return best


def oracle_budgeted_selection(
    event: TaskEvent, rules: Sequence[RuleSpec], *, top_k: int, budget: int,
) -> list[int]:
    return list(_oracle_budgeted_selection_cached(event, tuple(rules), int(top_k), int(budget)))


def select_rules(
    *, policy: str, event: TaskEvent, rules: Sequence[RuleSpec], state: UtilityState,
    top_k: int, budget: int, rng: np.random.Generator,
) -> list[int]:
    if policy not in VALID_POLICIES:
        raise ValueError(f"Unsupported policy: {policy}")
    relevance = np.asarray(event.relevance, dtype=float)
    estimates = state.means_for(event.domain)
    costs = np.asarray([rule.token_cost for rule in rules], dtype=float)
    cost_penalty = costs / max(float(budget), 1.0)
    if policy == "random":
        return _budgeted_order(rng.permutation(len(rules)), rules, top_k=top_k, budget=budget)
    if policy == "relevance":
        return _budgeted_order(np.argsort(-relevance, kind="stable"), rules, top_k=top_k, budget=budget)
    if policy == "greedy-utility":
        values = 0.55 * relevance + 0.35 * estimates - 0.10 * cost_penalty
        return _budgeted_order(np.argsort(-values, kind="stable"), rules, top_k=top_k, budget=budget)
    if policy == "ucb":
        counts = state.selection_counts_for(event.domain)
        bonus = np.sqrt(2.0 * math.log(max(state.step_for(event.domain) + 2, 2)) / (counts + 1.0))
        values = 0.50 * relevance + 0.35 * estimates + 0.15 * bonus - 0.10 * cost_penalty
        return _budgeted_order(np.argsort(-values, kind="stable"), rules, top_k=top_k, budget=budget)
    if policy == "thompson":
        alpha, beta = state.beta_parameters(event.domain)
        samples = rng.beta(alpha, beta)
        values = 0.50 * relevance + 0.40 * samples - 0.10 * cost_penalty
        return _budgeted_order(np.argsort(-values, kind="stable"), rules, top_k=top_k, budget=budget)
    if policy == "exact-utility":
        values = 0.55 * relevance + 0.35 * estimates - 0.10 * cost_penalty
        return exact_budgeted_selection(values, rules, top_k=top_k, budget=budget)
    return oracle_budgeted_selection(event, rules, top_k=top_k, budget=budget)


def credit_assignment(
    *, mode: str, event: TaskEvent, rules: Sequence[RuleSpec], selected: Sequence[int], reward: float,
) -> tuple[list[float], int]:
    """Return per-rule credits and extra tokens required to obtain them."""
    if mode not in VALID_CREDITS:
        raise ValueError(f"Unsupported credit mode: {mode}")
    if mode == "none" or not selected:
        return [], 0
    if mode == "shared":
        advantage = max(0.0, reward - event.base_reward) / max(1.0 - event.base_reward, 1e-9)
        return [float(np.clip(advantage, 0.0, 1.0))] * len(selected), 0
    credits, update_tokens = [], 0
    for position, _ in enumerate(selected):
        without = [candidate for offset, candidate in enumerate(selected) if offset != position]
        marginal = reward - expected_reward(event, rules, without)
        credits.append(float(np.clip(marginal / 0.42, 0.0, 1.0)))
        if mode == "leave-one-out":
            update_tokens += event.input_tokens + event.output_tokens + sum(rules[i].token_cost for i in without)
    return credits, update_tokens


def _rank_correlation(left: np.ndarray, right: np.ndarray) -> float:
    if len(left) < 2:
        return 0.0
    lr = np.argsort(np.argsort(left, kind="stable"), kind="stable").astype(float)
    rr = np.argsort(np.argsort(right, kind="stable"), kind="stable").astype(float)
    return float(np.corrcoef(lr, rr)[0, 1]) if np.std(lr) and np.std(rr) else 0.0


def _first_sustained_target(
    rewards: Sequence[float], cumulative_tokens: Sequence[int], *, target: float, window: int, sustain: int,
) -> int | None:
    if window <= 0 or sustain <= 0:
        raise ValueError("window and sustain must be positive")
    streak = 0
    for index in range(window - 1, len(rewards)):
        rolling = float(np.mean(rewards[index - window + 1:index + 1]))
        streak = streak + 1 if rolling >= target else 0
        if streak >= sustain:
            return int(cumulative_tokens[index - sustain + 1])
    return None


def _probe_domains(
    *, domains: Sequence[str], stream: SyntheticStream, method: MethodSpec,
    state: UtilityState, top_k: int, budget: int, seed: int, probe_index: object,
    drift_phase: int = 0,
) -> tuple[dict[str, float], int]:
    scores, tokens = {}, 0
    probe_set = stream.probes_by_phase.get(drift_phase, stream.probes)
    for domain in domains:
        rewards = []
        for event_index, event in enumerate(probe_set[domain]):
            rng = np.random.default_rng(_stable_seed(
                seed, method.name, "probe", probe_index, drift_phase, domain, event_index,
            ))
            selected = select_rules(
                policy=method.policy, event=event, rules=stream.rules, state=state,
                top_k=top_k, budget=budget, rng=rng,
            )
            rewards.append(expected_reward(event, stream.rules, selected))
            tokens += event.input_tokens + event.output_tokens + sum(stream.rules[i].token_cost for i in selected)
        scores[domain] = float(np.mean(rewards)) if rewards else 0.0
    return scores, tokens



def _evaluate_prior_guard(
    *, domains: Sequence[str], stream: SyntheticStream, method: MethodSpec,
    state: UtilityState, top_k: int, budget: int, seed: int,
    prior_strength: float,
) -> dict[str, Any]:
    """Evaluate paired learned/reference probes with optional sequential stopping."""
    probe_set = stream.probes_by_phase.get(0, stream.probes)
    available = min((len(probe_set[domain]) for domain in domains), default=0)
    max_probes = (
        available if method.prior_guard_max_probes_per_domain <= 0
        else min(available, method.prior_guard_max_probes_per_domain)
    )
    if max_probes <= 0:
        raise ValueError("Prior guard requires at least one probe per selected domain")

    if method.prior_guard_reference == "relevance":
        reference_method = MethodSpec(
            name="prior_guard_relevance", policy="relevance", credit="none",
        )
        reference_policy = "relevance"
        reference_seed_name = "prior_guard_relevance"
        reference_seed_role = "relevance"
    else:
        reference_method = replace(
            method, name="prior_guard_cold_router", prior_guard="none",
        )
        reference_policy = method.policy
        reference_seed_name = "prior_guard_cold_router"
        reference_seed_role = "cold-router"
    reference_state = _build_utility_state(
        reference_method, np.full(len(stream.rules), 0.5, dtype=float),
        tuple(stream.probes), prior_strength,
    )
    learned_probe_state = state.clone() if method.prior_guard_evaluation == "rollout" else state
    reference_probe_state = reference_state

    ordered_probes: dict[str, list[TaskEvent]] = {}
    probe_plan: dict[str, list[dict[str, Any]]] = {}
    for domain in domains:
        candidates = list(probe_set[domain])
        ranked: list[tuple[float, float, str, int, TaskEvent, list[int], list[int]]] = []
        for original_index, event in enumerate(candidates):
            learned_order_rng = np.random.default_rng(_stable_seed(
                seed, method.name, "prior-guard-order", "learned", domain, event.event_id,
            ))
            reference_order_rng = np.random.default_rng(_stable_seed(
                seed, reference_seed_name, "prior-guard-order", reference_seed_role,
                domain, event.event_id,
            ))
            learned_selected = select_rules(
                policy=method.policy, event=event, rules=stream.rules, state=state,
                top_k=top_k, budget=budget, rng=learned_order_rng,
            )
            reference_selected = select_rules(
                policy=reference_policy, event=event, rules=stream.rules, state=reference_state,
                top_k=top_k, budget=budget, rng=reference_order_rng,
            )
            learned_set, reference_set = set(learned_selected), set(reference_selected)
            union = learned_set | reference_set
            disagreement = len(learned_set ^ reference_set) / max(1, len(union))
            learned_relevance = sum(float(event.relevance[index]) for index in learned_selected)
            reference_relevance = sum(float(event.relevance[index]) for index in reference_selected)
            relevance_contrast = abs(learned_relevance - reference_relevance)
            ranked.append((
                -float(disagreement), -float(relevance_contrast), event.event_id,
                original_index, event, learned_selected, reference_selected,
            ))
        if method.prior_guard_probe_order == "selection-disagreement":
            ranked.sort(key=lambda item: item[:4])
        else:
            ranked.sort(key=lambda item: item[3])
        ordered_probes[domain] = [item[4] for item in ranked]
        probe_plan[domain] = [
            {
                "event_id": item[4].event_id,
                "original_index": item[3],
                "selection_disagreement": -item[0],
                "relevance_contrast": -item[1],
                "learned_selected_rule_ids": [stream.rules[index].rule_id for index in item[5]],
                "reference_selected_rule_ids": [stream.rules[index].rule_id for index in item[6]],
                "relevance_selected_rule_ids": [stream.rules[index].rule_id for index in item[6]],
            }
            for item in ranked
        ]

    learned_rewards = {domain: [] for domain in domains}
    reference_rewards = {domain: [] for domain in domains}
    paired_differences: list[float] = []
    learned_tokens = 0
    reference_tokens = 0
    learned_update_tokens = 0
    reference_update_tokens = 0
    stop_reason = "max-probes"
    confidence_lower: float | None = None
    confidence_upper: float | None = None
    recovery_slope: float | None = None
    round_history: list[dict[str, Any]] = []
    rounds_used = 0

    for probe_round in range(max_probes):
        rounds_used = probe_round + 1
        for domain in domains:
            event = ordered_probes[domain][probe_round]
            probe_seed_part: object = (
                probe_round if method.prior_guard_probe_order == "stream" else event.event_id
            )
            learned_rng = np.random.default_rng(_stable_seed(
                seed, method.name, "prior-guard", "learned", domain, probe_seed_part,
            ))
            reference_rng = np.random.default_rng(_stable_seed(
                seed, reference_seed_name, "prior-guard", reference_seed_role, domain,
                probe_seed_part,
            ))
            learned_selected = select_rules(
                policy=method.policy, event=event, rules=stream.rules, state=learned_probe_state,
                top_k=top_k, budget=budget, rng=learned_rng,
            )
            reference_selected = select_rules(
                policy=reference_policy, event=event, rules=stream.rules, state=reference_probe_state,
                top_k=top_k, budget=budget, rng=reference_rng,
            )
            learned_reward = expected_reward(event, stream.rules, learned_selected)
            reference_reward = expected_reward(event, stream.rules, reference_selected)
            learned_rewards[domain].append(learned_reward)
            reference_rewards[domain].append(reference_reward)
            paired_differences.append(learned_reward - reference_reward)
            learned_tokens += (
                event.input_tokens + event.output_tokens
                + sum(stream.rules[index].token_cost for index in learned_selected)
            )
            reference_tokens += (
                event.input_tokens + event.output_tokens
                + sum(stream.rules[index].token_cost for index in reference_selected)
            )
            if method.prior_guard_evaluation == "rollout":
                learned_credits, learned_extra_tokens = credit_assignment(
                    mode=method.credit, event=event, rules=stream.rules,
                    selected=learned_selected, reward=learned_reward,
                )
                if learned_credits:
                    learned_probe_state.update(
                        learned_selected, learned_credits, domain=event.domain,
                    )
                else:
                    learned_probe_state.observe_selection(learned_selected, domain=event.domain)
                reference_credits, reference_extra_tokens = credit_assignment(
                    mode=reference_method.credit, event=event, rules=stream.rules,
                    selected=reference_selected, reward=reference_reward,
                )
                if reference_credits:
                    reference_probe_state.update(
                        reference_selected, reference_credits, domain=event.domain,
                    )
                else:
                    reference_probe_state.observe_selection(reference_selected, domain=event.domain)
                learned_update_tokens += learned_extra_tokens
                reference_update_tokens += reference_extra_tokens

        differences = np.asarray(paired_differences, dtype=float)
        mean_difference = float(np.mean(differences))
        if len(differences) > 1:
            standard_error = float(np.std(differences, ddof=1) / math.sqrt(len(differences)))
        else:
            standard_error = float("inf")
        confidence_lower = mean_difference - method.prior_guard_confidence_z * standard_error
        confidence_upper = mean_difference + method.prior_guard_confidence_z * standard_error
        decision_boundary = -method.prior_guard_tolerance

        recovery_window = method.prior_guard_recovery_window
        margin_trajectory = [float(item["margin"]) for item in round_history] + [mean_difference]
        if recovery_window > 1 and len(margin_trajectory) >= recovery_window:
            recent_margins = np.asarray(margin_trajectory[-recovery_window:], dtype=float)
            round_offsets = np.arange(recovery_window, dtype=float)
            recovery_slope = float(np.polyfit(round_offsets, recent_margins, 1)[0])
        else:
            recovery_slope = None
        round_history.append({
            "round": rounds_used,
            "paired_samples": len(paired_differences),
            "learned_mean": float(np.mean([
                reward for values in learned_rewards.values() for reward in values
            ])),
            "reference_mean": float(np.mean([
                reward for values in reference_rewards.values() for reward in values
            ])),
            "margin": mean_difference,
            "standard_error": standard_error,
            "confidence_lower": confidence_lower,
            "confidence_upper": confidence_upper,
            "decision_boundary": decision_boundary,
            "recovery_slope": recovery_slope,
            "learned_probe_tokens": learned_tokens,
            "reference_probe_tokens": reference_tokens,
            "learned_update_tokens": learned_update_tokens,
            "reference_update_tokens": reference_update_tokens,
            "validation_tokens": (
                learned_tokens + reference_tokens
                + learned_update_tokens + reference_update_tokens
            ),
        })

        if method.prior_guard_sequential and len(paired_differences) >= method.prior_guard_min_samples:
            accept_horizon_met = rounds_used >= max(1, method.prior_guard_min_accept_rounds)
            if confidence_lower >= decision_boundary and accept_horizon_met:
                stop_reason = "confident-acceptable"
                break

            reset_horizon_met = rounds_used >= method.prior_guard_min_reset_rounds
            large_harm = mean_difference <= (
                decision_boundary - method.prior_guard_min_harm_margin
            )
            recovery_checked = method.prior_guard_recovery_window <= 1
            non_recovering = recovery_checked or (
                recovery_slope is not None
                and method.prior_guard_max_recovery_slope is not None
                and recovery_slope <= method.prior_guard_max_recovery_slope
            )
            if (
                confidence_upper < decision_boundary
                and reset_horizon_met
                and large_harm
                and non_recovering
            ):
                stop_reason = "confident-harmful"
                break

    accept_horizon_met = rounds_used >= max(1, method.prior_guard_min_accept_rounds)
    reset_horizon_met = rounds_used >= method.prior_guard_min_reset_rounds
    large_harm = mean_difference <= (
        decision_boundary - method.prior_guard_min_harm_margin
    )
    recovery_checked = method.prior_guard_recovery_window <= 1
    non_recovering = recovery_checked or (
        recovery_slope is not None
        and method.prior_guard_max_recovery_slope is not None
        and recovery_slope <= method.prior_guard_max_recovery_slope
    )
    if confidence_lower >= decision_boundary and accept_horizon_met:
        decision = "acceptable"
    elif (
        confidence_upper < decision_boundary
        and reset_horizon_met
        and large_harm
        and non_recovering
    ):
        decision = "harmful"
    else:
        decision = "ambiguous"

    learned_scores = {
        domain: float(np.mean(values)) if values else 0.0
        for domain, values in learned_rewards.items()
    }
    reference_scores = {
        domain: float(np.mean(values)) if values else 0.0
        for domain, values in reference_rewards.items()
    }
    learned_mean = float(np.mean(list(learned_scores.values())))
    reference_mean = float(np.mean(list(reference_scores.values())))
    margin = learned_mean - reference_mean
    triggered = learned_mean < reference_mean - method.prior_guard_tolerance
    reference_share = float(method.prior_guard_relevance_cost_share)
    amortized_validation_tokens = (
        learned_tokens + learned_update_tokens
        + (reference_tokens + reference_update_tokens) * reference_share
    )
    return {
        "domains": list(domains),
        "reference": method.prior_guard_reference,
        "evaluation": method.prior_guard_evaluation,
        "learned_scores": learned_scores,
        "reference_scores": reference_scores,
        "relevance_scores": reference_scores,
        "learned_mean": learned_mean,
        "reference_mean": reference_mean,
        "relevance_mean": reference_mean,
        "margin": margin,
        "triggered": bool(triggered),
        "decision": decision,
        "learned_probe_tokens": learned_tokens,
        "reference_probe_tokens": reference_tokens,
        "relevance_probe_tokens": reference_tokens,
        "learned_update_tokens": learned_update_tokens,
        "reference_update_tokens": reference_update_tokens,
        "validation_tokens": (
            learned_tokens + reference_tokens
            + learned_update_tokens + reference_update_tokens
        ),
        "amortized_validation_tokens": amortized_validation_tokens,
        "reference_cost_share": reference_share,
        "relevance_cost_share": reference_share,
        "rounds_used": rounds_used,
        "paired_samples": len(paired_differences),
        "max_probes_per_domain": max_probes,
        "probe_order": method.prior_guard_probe_order,
        "probe_plan": probe_plan,
        "evaluated_event_ids": {
            domain: [event.event_id for event in ordered_probes[domain][:rounds_used]]
            for domain in domains
        },
        "sequential": bool(method.prior_guard_sequential),
        "confidence_z": method.prior_guard_confidence_z,
        "min_accept_rounds": method.prior_guard_min_accept_rounds,
        "min_reset_rounds": method.prior_guard_min_reset_rounds,
        "min_harm_margin": method.prior_guard_min_harm_margin,
        "recovery_window": method.prior_guard_recovery_window,
        "max_recovery_slope": method.prior_guard_max_recovery_slope,
        "confidence_lower": confidence_lower,
        "confidence_upper": confidence_upper,
        "recovery_slope": recovery_slope,
        "round_history": round_history,
        "stop_reason": stop_reason,
    }


def _pearson_correlation(left: np.ndarray, right: np.ndarray) -> float:
    left = np.asarray(left, dtype=float)
    right = np.asarray(right, dtype=float)
    if len(left) < 2 or not np.std(left) or not np.std(right):
        return 0.0
    return float(np.corrcoef(left, right)[0, 1])


def _static_prior_pairing(
    *, events: Sequence[TaskEvent], rules: Sequence[RuleSpec], learned_state: UtilityState,
    cold_state: UtilityState, method: MethodSpec, top_k: int, budget: int, seed: int,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        local_seed = _stable_seed(seed, "prior-representativeness", event.event_id, index)
        learned_selected = select_rules(
            policy=method.policy, event=event, rules=rules, state=learned_state,
            top_k=top_k, budget=budget, rng=np.random.default_rng(local_seed),
        )
        cold_selected = select_rules(
            policy=method.policy, event=event, rules=rules, state=cold_state,
            top_k=top_k, budget=budget, rng=np.random.default_rng(local_seed),
        )
        learned_reward = expected_reward(event, rules, learned_selected)
        cold_reward = expected_reward(event, rules, cold_selected)
        learned_utilities = [
            rule_utility_for_domain(rules[item], event.domain) for item in learned_selected
        ]
        cold_utilities = [
            rule_utility_for_domain(rules[item], event.domain) for item in cold_selected
        ]
        rows.append({
            "event_id": event.event_id,
            "domain": event.domain,
            "learned_reward": learned_reward,
            "cold_reward": cold_reward,
            "margin": learned_reward - cold_reward,
            "learned_selected_rule_ids": [rules[item].rule_id for item in learned_selected],
            "cold_selected_rule_ids": [rules[item].rule_id for item in cold_selected],
            "learned_selected_domain_utility_mean": (
                float(np.mean(learned_utilities)) if learned_utilities else 0.0
            ),
            "cold_selected_domain_utility_mean": (
                float(np.mean(cold_utilities)) if cold_utilities else 0.0
            ),
            "learned_selected_harmful_fraction": (
                float(np.mean(np.asarray(learned_utilities) < 0.0)) if learned_utilities else 0.0
            ),
            "cold_selected_harmful_fraction": (
                float(np.mean(np.asarray(cold_utilities) < 0.0)) if cold_utilities else 0.0
            ),
        })

    def summarize(members: Sequence[dict[str, Any]]) -> dict[str, Any]:
        if not members:
            return {
                "n": 0, "margin_mean": None, "margin_std": None,
                "positive_fraction": None, "negative_fraction": None,
                "learned_selected_domain_utility_mean": None,
                "cold_selected_domain_utility_mean": None,
                "learned_selected_harmful_fraction": None,
                "cold_selected_harmful_fraction": None,
            }
        margins = np.asarray([row["margin"] for row in members], dtype=float)
        return {
            "n": len(members),
            "margin_mean": float(np.mean(margins)),
            "margin_std": float(np.std(margins)),
            "positive_fraction": float(np.mean(margins > 0.0)),
            "negative_fraction": float(np.mean(margins < 0.0)),
            "learned_selected_domain_utility_mean": float(np.mean([
                row["learned_selected_domain_utility_mean"] for row in members
            ])),
            "cold_selected_domain_utility_mean": float(np.mean([
                row["cold_selected_domain_utility_mean"] for row in members
            ])),
            "learned_selected_harmful_fraction": float(np.mean([
                row["learned_selected_harmful_fraction"] for row in members
            ])),
            "cold_selected_harmful_fraction": float(np.mean([
                row["cold_selected_harmful_fraction"] for row in members
            ])),
        }

    result = summarize(rows)
    result["by_domain"] = {
        domain: summarize([row for row in rows if row["domain"] == domain])
        for domain in dict.fromkeys(event.domain for event in events)
    }
    result["events"] = rows
    return result


def evaluate_prior_representativeness(
    *, stream: SyntheticStream, method: MethodSpec, condition: str, identity: str,
    seed: int, top_k: int, budget: int, prior_strength: float,
    prefix_probe_rounds: int = 2, phase0_blocks: int = 3,
) -> dict[str, Any]:
    """Diagnose prior identity and phase-0 probe coverage without a full online run."""
    domains = tuple(stream.probes_by_phase.get(0, stream.probes))
    if prefix_probe_rounds <= 0:
        raise ValueError("prefix_probe_rounds must be positive")
    if phase0_blocks <= 0 or phase0_blocks > len(stream.blocks):
        raise ValueError("phase0_blocks must select a nonempty prefix of stream blocks")
    probe_set = stream.probes_by_phase.get(0, stream.probes)
    if any(len(probe_set[domain]) < prefix_probe_rounds for domain in domains):
        raise ValueError("prefix_probe_rounds exceeds available phase-0 probes")

    learned_state, global_prior, domain_priors = build_prior_identity_state(
        rules=stream.rules, domains=domains, method=method, condition=condition,
        identity=identity, seed=seed, prior_strength=prior_strength,
    )
    cold_state = _build_utility_state(
        method, np.full(len(stream.rules), 0.5, dtype=float), domains, prior_strength,
    )
    global_truth = np.asarray([rule.true_utility for rule in stream.rules], dtype=float)
    domain_truth = {
        domain: np.asarray([
            rule_utility_for_domain(rule, domain) for rule in stream.rules
        ], dtype=float)
        for domain in domains
    }
    prior_correlations = {
        "global": {
            "pearson": _pearson_correlation(global_prior, global_truth),
            "spearman": _rank_correlation(global_prior, global_truth),
        },
        "by_domain": {
            domain: {
                "pearson": _pearson_correlation(domain_priors[domain], domain_truth[domain]),
                "spearman": _rank_correlation(domain_priors[domain], domain_truth[domain]),
                "global_prior_pearson": _pearson_correlation(global_prior, domain_truth[domain]),
                "global_prior_spearman": _rank_correlation(global_prior, domain_truth[domain]),
            }
            for domain in domains
        },
    }
    domain_spearman = [
        prior_correlations["by_domain"][domain]["spearman"] for domain in domains
    ]

    prefix_events = [
        event for domain in domains for event in probe_set[domain][:prefix_probe_rounds]
    ]
    all_probe_events = [event for domain in domains for event in probe_set[domain]]
    phase0_events = [event for block in stream.blocks[:phase0_blocks] for event in block]
    prefix_pairing = _static_prior_pairing(
        events=prefix_events, rules=stream.rules, learned_state=learned_state,
        cold_state=cold_state, method=method, top_k=top_k, budget=budget, seed=seed,
    )
    all_probe_pairing = _static_prior_pairing(
        events=all_probe_events, rules=stream.rules, learned_state=learned_state,
        cold_state=cold_state, method=method, top_k=top_k, budget=budget, seed=seed,
    )
    stream_pairing = _static_prior_pairing(
        events=phase0_events, rules=stream.rules, learned_state=learned_state,
        cold_state=cold_state, method=method, top_k=top_k, budget=budget, seed=seed,
    )
    guard = _evaluate_prior_guard(
        domains=domains, stream=stream, method=method, state=learned_state,
        top_k=top_k, budget=budget, seed=seed, prior_strength=prior_strength,
    )
    stream_margin = float(stream_pairing["margin_mean"])
    prefix_margin = float(prefix_pairing["margin_mean"])
    all_probe_margin = float(all_probe_pairing["margin_mean"])
    summary = {
        "condition": condition,
        "prior_identity": identity,
        "seed": seed,
        "global_prior_pearson": prior_correlations["global"]["pearson"],
        "global_prior_spearman": prior_correlations["global"]["spearman"],
        "domain_prior_spearman_mean": float(np.mean(domain_spearman)),
        "domain_prior_spearman_min": float(np.min(domain_spearman)),
        "guard_margin": float(guard["margin"]),
        "guard_triggered": bool(guard["triggered"]),
        "guard_rounds_used": int(guard["rounds_used"]),
        "guard_stop_reason": str(guard["stop_reason"]),
        "prefix_probe_margin": prefix_margin,
        "all_probe_margin": all_probe_margin,
        "phase0_stream_margin": stream_margin,
        "prefix_probe_stream_sign_agreement": bool(np.sign(prefix_margin) == np.sign(stream_margin)),
        "all_probe_stream_sign_agreement": bool(np.sign(all_probe_margin) == np.sign(stream_margin)),
        "all_probe_learned_selected_domain_utility_mean": all_probe_pairing[
            "learned_selected_domain_utility_mean"
        ],
        "all_probe_learned_selected_harmful_fraction": all_probe_pairing[
            "learned_selected_harmful_fraction"
        ],
        "phase0_stream_learned_selected_domain_utility_mean": stream_pairing[
            "learned_selected_domain_utility_mean"
        ],
        "phase0_stream_learned_selected_harmful_fraction": stream_pairing[
            "learned_selected_harmful_fraction"
        ],
    }
    payload = {
        "schema_version": 1,
        "scope": "prior identity and phase-0 probe representativeness diagnostic",
        "summary": summary,
        "prior_correlations": prior_correlations,
        "guard": guard,
        "static_prefix_probes": prefix_pairing,
        "static_all_probes": all_probe_pairing,
        "static_phase0_stream": stream_pairing,
    }
    payload["diagnostic_fingerprint"] = hashlib.sha256(json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    return payload

def evaluate_non_regression_gate(
    *, gate: str, baseline_scores: dict[str, float], candidate_scores: dict[str, float],
    current_domain: str, old_domains: Sequence[str], tolerance: float,
    min_plasticity: float,
) -> dict[str, Any]:
    """Evaluate a block update without hiding rejection or plasticity costs."""
    if gate not in VALID_GATES - {"none"}:
        raise ValueError(f"Unsupported gate: {gate}")
    old_deltas = {
        domain: float(candidate_scores[domain] - baseline_scores[domain])
        for domain in old_domains
        if domain in baseline_scores and domain in candidate_scores
    }
    current_delta = float(
        candidate_scores.get(current_domain, 0.0) - baseline_scores.get(current_domain, 0.0)
    )
    worst_old_delta = min(old_deltas.values(), default=0.0)
    safe = worst_old_delta >= -float(tolerance)
    plastic = current_delta >= float(min_plasticity)
    accepted = safe and (gate != "balanced" or plastic)
    return {
        "accepted": bool(accepted),
        "safe": bool(safe),
        "plastic": bool(plastic),
        "old_domain_deltas": old_deltas,
        "worst_old_domain_delta": float(worst_old_delta),
        "current_domain_delta": current_delta,
    }


def run_continual_experiment(
    *, stream: SyntheticStream, method: MethodSpec, condition: str, seed: int,
    top_k: int, budget: int, token_target: float = 0.75, target_window: int = 20,
    target_sustain: int = 5, prior_strength: float = 2.0,
    corruption_mode: str = "none", corruption_block: int | None = None,
    recovery_correlation_target: float = 0.25, recovery_sustain: int = 5,
) -> dict[str, Any]:
    if method.estimator not in VALID_ESTIMATORS:
        raise ValueError(f"Unsupported estimator: {method.estimator}")
    if method.prior_identity not in VALID_PRIOR_IDENTITIES:
        raise ValueError(f"Unsupported prior identity: {method.prior_identity}")
    if method.gate not in VALID_GATES:
        raise ValueError(f"Unsupported gate: {method.gate}")
    if method.context_weight_mode not in VALID_CONTEXT_WEIGHT_MODES:
        raise ValueError(f"Unsupported context weight mode: {method.context_weight_mode}")
    if method.prior_guard not in VALID_PRIOR_GUARDS:
        raise ValueError(f"Unsupported prior guard: {method.prior_guard}")
    if method.prior_guard_tolerance < 0.0:
        raise ValueError("prior_guard_tolerance must be non-negative")
    if method.prior_guard_max_probes_per_domain < 0:
        raise ValueError("prior_guard_max_probes_per_domain must be non-negative")
    if method.prior_guard_min_samples <= 0:
        raise ValueError("prior_guard_min_samples must be positive")
    if method.prior_guard_min_accept_rounds < 0:
        raise ValueError("prior_guard_min_accept_rounds must be non-negative")
    if method.prior_guard_min_reset_rounds < 0:
        raise ValueError("prior_guard_min_reset_rounds must be non-negative")
    if method.prior_guard_min_harm_margin < 0.0:
        raise ValueError("prior_guard_min_harm_margin must be non-negative")
    if method.prior_guard_recovery_window < 0:
        raise ValueError("prior_guard_recovery_window must be non-negative")
    if (
        method.prior_guard_recovery_window > 1
        and method.prior_guard_max_recovery_slope is None
    ):
        raise ValueError(
            "prior_guard_max_recovery_slope is required when prior_guard_recovery_window > 1"
        )
    if method.prior_guard_confidence_z < 0.0:
        raise ValueError("prior_guard_confidence_z must be non-negative")
    if not 0.0 < method.prior_guard_relevance_cost_share <= 1.0:
        raise ValueError("prior_guard_relevance_cost_share must be within (0, 1]")
    if method.prior_guard_probe_order not in VALID_PRIOR_GUARD_PROBE_ORDERS:
        raise ValueError(f"Unsupported prior-guard probe order: {method.prior_guard_probe_order}")
    if method.prior_guard_reference not in VALID_PRIOR_GUARD_REFERENCES:
        raise ValueError(f"Unsupported prior-guard reference: {method.prior_guard_reference}")
    if method.prior_guard_evaluation not in VALID_PRIOR_GUARD_EVALUATIONS:
        raise ValueError(f"Unsupported prior-guard evaluation: {method.prior_guard_evaluation}")
    if corruption_mode not in VALID_CORRUPTIONS:
        raise ValueError(f"Unsupported corruption mode: {corruption_mode}")

    state, prior, initial_domain_priors = build_prior_identity_state(
        rules=stream.rules, domains=tuple(stream.probes), method=method,
        condition=condition, identity=method.prior_identity,
        seed=_stable_seed(seed, condition), prior_strength=prior_strength,
    )
    effective_initial_prior = prior.copy()
    active_method = method
    guard_validation_tokens = 0
    prior_guard_triggered = False
    prior_guard_learned_score: float | None = None
    prior_guard_relevance_score: float | None = None
    prior_guard_reference_score: float | None = None
    prior_guard_margin: float | None = None
    prior_guard_domains: list[str] = []
    prior_guard_history: dict[str, Any] | None = None
    prior_guard_state_mutated = False

    if method.prior_guard != "none":
        if method.prior_guard_probe_domains == "all":
            prior_guard_domains = list(stream.probes)
        else:
            prior_guard_domains = [
                item.strip() for item in method.prior_guard_probe_domains.split(",") if item.strip()
            ]
            if not prior_guard_domains:
                raise ValueError("prior_guard_probe_domains must name at least one domain")
            missing_domains = [domain for domain in prior_guard_domains if domain not in stream.probes]
            if missing_domains:
                raise ValueError(f"Unknown prior-guard probe domains: {missing_domains}")

        prior_guard_history = _evaluate_prior_guard(
            domains=prior_guard_domains, stream=stream, method=active_method, state=state,
            top_k=top_k, budget=budget, seed=seed, prior_strength=prior_strength,
        )
        guard_validation_tokens = int(prior_guard_history["validation_tokens"])
        prior_guard_learned_score = float(prior_guard_history["learned_mean"])
        prior_guard_relevance_score = float(prior_guard_history["relevance_mean"])
        prior_guard_reference_score = float(prior_guard_history["reference_mean"])
        prior_guard_margin = float(prior_guard_history["margin"])
        prior_guard_triggered = bool(prior_guard_history["triggered"])
        decision = str(prior_guard_history["decision"])
        action = "none"
        if prior_guard_triggered and method.prior_guard == "reset-cold":
            effective_initial_prior = np.full(len(stream.rules), 0.5, dtype=float)
            state = _build_utility_state(
                method, effective_initial_prior, tuple(stream.probes), prior_strength,
            )
            prior_guard_state_mutated = True
            action = "reset-cold"
        elif prior_guard_triggered and method.prior_guard == "fallback-relevance":
            active_method = replace(
                method, policy="relevance", credit="none", gate="none", prior_guard="none",
            )
            action = "fallback-relevance"
        elif method.prior_guard == "selective-cold":
            prior_guard_triggered = decision != "acceptable"
            if decision == "acceptable":
                action = "accept"
            else:
                cold_prior = np.full(len(stream.rules), 0.5, dtype=float)
                state = _build_utility_state(
                    method, cold_prior, tuple(stream.probes), prior_strength,
                )
                action = (
                    "reject-fallback-cold" if decision == "harmful"
                    else "abstain-fallback-cold"
                )
        prior_guard_history.update({
            "mode": method.prior_guard,
            "tolerance": method.prior_guard_tolerance,
            "action": action,
            "candidate_state_mutated": prior_guard_state_mutated,
        })

    truth = np.asarray([rule.true_utility for rule in stream.rules], dtype=float)
    cumulative_tokens, cumulative_regret, routing_seconds = guard_validation_tokens, 0.0, 0.0
    inference_tokens_total = 0
    credit_update_tokens_total = 0
    probe_tokens_total = 0
    gate_validation_tokens = 0
    rows: list[dict[str, Any]] = []
    probe_history: list[dict[str, Any]] = []
    gate_history: list[dict[str, Any]] = []
    seen_domains: list[str] = []
    gate_accepts = 0
    gate_rejects = 0
    safety_violations = 0
    plasticity_deltas: list[float] = []
    old_domain_deltas: list[float] = []
    accepted_old_domain_deltas: list[float] = []
    corruption_applied = False
    harmful_selections = 0
    malicious_selections = 0
    conflict_selections = 0
    selected_rule_count = 0
    duplicate_coselection_tasks = 0

    for block_index, block in enumerate(stream.blocks):
        if not block:
            continue
        block_domains = {event.domain for event in block}
        if len(block_domains) != 1:
            raise ValueError("Each continual stream block must contain exactly one domain")
        current_domain = block[0].domain
        drift_phase = int(block[0].drift_phase)
        seen_before = list(seen_domains)
        if current_domain not in seen_domains:
            seen_domains.append(current_domain)

        if (
            not corruption_applied and corruption_mode != "none"
            and corruption_block is not None and block_index == corruption_block
        ):
            state.corrupt(
                corruption_mode,
                np.random.default_rng(_stable_seed(seed, condition, "corruption", block_index)),
            )
            corruption_applied = True

        snapshot: UtilityState | None = None
        baseline_scores: dict[str, float] = {}
        validation_tokens = 0
        if active_method.gate != "none":
            snapshot = state.clone()
            validation_domains = [*seen_before]
            if current_domain not in validation_domains:
                validation_domains.append(current_domain)
            baseline_scores, validation_tokens = _probe_domains(
                domains=validation_domains, stream=stream, method=active_method, state=state,
                top_k=top_k, budget=budget, seed=seed,
                probe_index=f"gate-pre-{block_index}", drift_phase=drift_phase,
            )
            gate_validation_tokens += validation_tokens
            cumulative_tokens += validation_tokens

        for event_index, event in enumerate(block):
            rng = np.random.default_rng(_stable_seed(
                seed, method.name, condition, corruption_mode, block_index, event_index, event.event_id,
            ))
            started = time.perf_counter()
            selected = select_rules(
                policy=active_method.policy, event=event, rules=stream.rules, state=state,
                top_k=top_k, budget=budget, rng=rng,
            )
            routing_ms = (time.perf_counter() - started) * 1000.0
            routing_seconds += routing_ms / 1000.0
            reward = expected_reward(event, stream.rules, selected)
            oracle_selected = select_rules(
                policy="oracle", event=event, rules=stream.rules, state=state,
                top_k=top_k, budget=budget, rng=rng,
            )
            oracle_reward = expected_reward(event, stream.rules, oracle_selected)
            regret = max(0.0, oracle_reward - reward)
            credits, update_tokens = credit_assignment(
                mode=active_method.credit, event=event, rules=stream.rules, selected=selected, reward=reward,
            )
            if credits:
                state.update(selected, credits, domain=event.domain)
            else:
                state.observe_selection(selected, domain=event.domain)

            current_truth = np.asarray([
                effective_rule_utility(event, rule) for rule in stream.rules
            ], dtype=float)
            current_correlation = _rank_correlation(state.means_for(event.domain), current_truth)
            selected_rule_count += len(selected)
            harmful_selections += sum(
                effective_rule_utility(event, stream.rules[index]) < 0.0 for index in selected
            )
            malicious_selections += sum(
                stream.rules[index].rule_type == "malicious" for index in selected
            )
            conflict_selections += sum(
                stream.rules[index].rule_type == "conflict" for index in selected
            )
            families = [stream.rules[index].duplicate_of or stream.rules[index].rule_id for index in selected]
            duplicate_coselection = len(families) != len(set(families))
            duplicate_coselection_tasks += int(duplicate_coselection)

            selected_tokens = sum(stream.rules[i].token_cost for i in selected)
            inference_tokens = event.input_tokens + event.output_tokens + selected_tokens
            step_tokens = inference_tokens + update_tokens
            inference_tokens_total += inference_tokens
            credit_update_tokens_total += update_tokens
            cumulative_tokens += step_tokens
            cumulative_regret += regret
            rows.append({
                "step": len(rows), "block": block_index, "event_id": event.event_id,
                "domain": event.domain, "drift_phase": event.drift_phase,
                "selected_rule_ids": [stream.rules[i].rule_id for i in selected],
                "selected_rule_types": [stream.rules[i].rule_type for i in selected],
                "selected_tokens": selected_tokens, "inference_tokens": inference_tokens,
                "credit_update_tokens": update_tokens, "step_tokens": step_tokens,
                "cumulative_tokens": cumulative_tokens, "reward": reward,
                "oracle_reward": oracle_reward, "regret": regret,
                "cumulative_regret": cumulative_regret, "routing_ms": routing_ms,
                "utility_rank_correlation_current": current_correlation,
                "harmful_selected": sum(
                    effective_rule_utility(event, stream.rules[index]) < 0.0 for index in selected
                ),
                "duplicate_coselection": duplicate_coselection,
            })

        candidate_scores, post_probe_tokens = _probe_domains(
            domains=seen_domains, stream=stream, method=active_method, state=state,
            top_k=top_k, budget=budget, seed=seed, probe_index=block_index,
            drift_phase=drift_phase,
        )
        probe_tokens_total += post_probe_tokens
        cumulative_tokens += post_probe_tokens
        effective_scores = candidate_scores
        gate_record: dict[str, Any] | None = None

        if active_method.gate != "none":
            old_domains = list(seen_before)
            decision = evaluate_non_regression_gate(
                gate=active_method.gate, baseline_scores=baseline_scores,
                candidate_scores=candidate_scores, current_domain=current_domain,
                old_domains=old_domains, tolerance=method.gate_tolerance,
                min_plasticity=method.gate_min_plasticity,
            )
            if decision["accepted"]:
                gate_accepts += 1
            else:
                gate_rejects += 1
                if snapshot is None:
                    raise RuntimeError("Gate rejection requires a state snapshot")
                state = snapshot
                effective_scores = dict(baseline_scores)
            effective_old = {
                domain: float(effective_scores[domain] - baseline_scores[domain])
                for domain in old_domains
                if domain in baseline_scores and domain in effective_scores
            }
            effective_current_delta = float(
                effective_scores.get(current_domain, 0.0) - baseline_scores.get(current_domain, 0.0)
            )
            plasticity_deltas.append(effective_current_delta)
            old_domain_deltas.extend(effective_old.values())
            safety_violations += sum(
                delta < -method.gate_tolerance for delta in effective_old.values()
            )
            if decision["accepted"]:
                accepted_old_domain_deltas.extend(effective_old.values())
            gate_record = {
                "after_block": block_index, "drift_phase": drift_phase,
                "current_domain": current_domain,
                "baseline_scores": baseline_scores,
                "candidate_scores": candidate_scores,
                "effective_scores": effective_scores,
                "validation_tokens": validation_tokens,
                **decision,
            }
            gate_history.append(gate_record)
        else:
            previous_scores = probe_history[-1]["scores"] if probe_history else {}
            comparable_old_domains = list(seen_before)
            deltas = {
                domain: float(candidate_scores[domain] - previous_scores[domain])
                for domain in comparable_old_domains
                if domain in previous_scores and domain in candidate_scores
            }
            old_domain_deltas.extend(deltas.values())
            accepted_old_domain_deltas.extend(deltas.values())
            safety_violations += sum(
                delta < -method.gate_tolerance for delta in deltas.values()
            )
            if current_domain in previous_scores:
                plasticity_deltas.append(
                    float(candidate_scores[current_domain] - previous_scores[current_domain])
                )

        probe_history.append({
            "after_block": block_index, "drift_phase": drift_phase,
            "seen_domains": list(seen_domains),
            "scores": effective_scores, "candidate_scores": candidate_scores,
            "probe_tokens": post_probe_tokens,
            "gate": gate_record,
            "cumulative_tokens": cumulative_tokens,
        })

    rewards = [float(row["reward"]) for row in rows]
    task_tokens = [int(row["cumulative_tokens"]) for row in rows]
    correlations = [float(row["utility_rank_correlation_current"]) for row in rows]
    best_by_domain, final_by_domain = {}, {}
    for probe in probe_history:
        for domain, score in probe["scores"].items():
            best_by_domain[domain] = max(best_by_domain.get(domain, -float("inf")), float(score))
            final_by_domain[domain] = float(score)
    forgetting = {d: max(0.0, best_by_domain[d] - final_by_domain[d]) for d in final_by_domain}
    estimates = state.means
    effective_window = min(target_window, len(rewards))
    tokens_to_target = _first_sustained_target(
        rewards, task_tokens, target=token_target, window=effective_window, sustain=target_sustain,
    ) if rewards else None
    utility_recovery_tokens = _first_sustained_target(
        correlations, task_tokens, target=recovery_correlation_target, window=1,
        sustain=recovery_sustain,
    ) if correlations else None
    guard_amortized_tokens = float(
        prior_guard_history["amortized_validation_tokens"]
        if prior_guard_history is not None else 0.0
    )
    amortized_total_tokens = float(cumulative_tokens - guard_validation_tokens + guard_amortized_tokens)
    amortized_task_tokens = [
        int(round(value - guard_validation_tokens + guard_amortized_tokens)) for value in task_tokens
    ]
    amortized_tokens_to_target = _first_sustained_target(
        rewards, amortized_task_tokens, target=token_target, window=effective_window,
        sustain=target_sustain,
    ) if rewards else None

    def recovery_after(first_index: int | None) -> int | None:
        if first_index is None or first_index >= len(rows):
            return None
        recovered_at = _first_sustained_target(
            correlations[first_index:], task_tokens[first_index:],
            target=recovery_correlation_target, window=1, sustain=recovery_sustain,
        )
        if recovered_at is None:
            return None
        baseline_tokens = task_tokens[first_index - 1] if first_index > 0 else 0
        return int(recovered_at - baseline_tokens)

    corruption_index = next((i for i, row in enumerate(rows) if (
        corruption_applied and corruption_block is not None and row["block"] >= corruption_block
    )), None)
    drift_index = next((i for i, row in enumerate(rows) if row["drift_phase"] > 0), None)
    corruption_recovery_tokens = recovery_after(corruption_index)
    post_drift_recovery_tokens = recovery_after(drift_index)

    final_phase = max((int(row["drift_phase"]) for row in rows), default=0)
    final_probe_set = stream.probes_by_phase.get(final_phase, stream.probes)
    domain_mae: list[float] = []
    domain_correlations: list[float] = []
    final_domain_truth: dict[str, list[float]] = {}
    for domain in stream.probes:
        reference_event = final_probe_set[domain][0]
        domain_truth = np.asarray([
            effective_rule_utility(reference_event, rule) for rule in stream.rules
        ], dtype=float)
        domain_estimates = state.means_for(domain)
        domain_mae.append(float(np.mean(np.abs(domain_estimates - domain_truth))))
        domain_correlations.append(_rank_correlation(domain_estimates, domain_truth))
        final_domain_truth[domain] = domain_truth.tolist()

    gate_evaluations = gate_accepts + gate_rejects
    summary = {
        "method": method.name, "policy": method.policy, "credit": method.credit,
        "effective_policy": active_method.policy, "effective_credit": active_method.credit,
        "estimator": method.estimator, "prior_identity": method.prior_identity,
        "gate": method.gate,
        "effective_gate": active_method.gate,
        "context_weight": method.context_weight,
        "context_weight_mode": method.context_weight_mode,
        "context_evidence_scale": method.context_evidence_scale,
        "context_min_weight": method.context_min_weight,
        "context_max_weight": method.context_max_weight,
        "prior_guard": method.prior_guard,
        "prior_guard_tolerance": method.prior_guard_tolerance,
        "prior_guard_probe_domains": method.prior_guard_probe_domains,
        "prior_guard_max_probes_per_domain": method.prior_guard_max_probes_per_domain,
        "prior_guard_sequential": method.prior_guard_sequential,
        "prior_guard_confidence_z": method.prior_guard_confidence_z,
        "prior_guard_min_samples": method.prior_guard_min_samples,
        "prior_guard_min_accept_rounds": method.prior_guard_min_accept_rounds,
        "prior_guard_min_reset_rounds": method.prior_guard_min_reset_rounds,
        "prior_guard_min_harm_margin": method.prior_guard_min_harm_margin,
        "prior_guard_recovery_window": method.prior_guard_recovery_window,
        "prior_guard_max_recovery_slope": method.prior_guard_max_recovery_slope,
        "prior_guard_relevance_cost_share": method.prior_guard_relevance_cost_share,
        "prior_guard_probe_order": method.prior_guard_probe_order,
        "prior_guard_reference": method.prior_guard_reference,
        "prior_guard_evaluation": method.prior_guard_evaluation,
        "prior_guard_triggered": prior_guard_triggered,
        "prior_guard_decision": (
            str(prior_guard_history["decision"]) if prior_guard_history is not None else "none"
        ),
        "prior_guard_state_mutated": prior_guard_state_mutated,
        "prior_guard_action": (
            str(prior_guard_history["action"]) if prior_guard_history is not None else "none"
        ),
        "prior_guard_reset_magnitude": float(np.mean(np.abs(prior - effective_initial_prior))),
        "prior_guard_learned_score": prior_guard_learned_score,
        "prior_guard_relevance_score": prior_guard_relevance_score,
        "prior_guard_reference_score": prior_guard_reference_score,
        "prior_guard_margin": prior_guard_margin,
        "prior_guard_recovery_slope": (
            prior_guard_history["recovery_slope"] if prior_guard_history is not None else None
        ),
        "condition": condition, "corruption_mode": corruption_mode,
        "corruption_block": corruption_block,
        "seed": seed, "n_rules": len(stream.rules),
        "n_tasks": len(rows), "top_k": top_k, "budget": budget,
        "mean_reward": float(np.mean(rewards)) if rewards else 0.0,
        "final_window_reward": float(np.mean(rewards[-effective_window:])) if rewards else 0.0,
        "cumulative_regret": cumulative_regret,
        "mean_regret": float(np.mean([row["regret"] for row in rows])) if rows else 0.0,
        "total_tokens": cumulative_tokens, "inference_tokens": inference_tokens_total,
        "credit_update_tokens": credit_update_tokens_total,
        "probe_tokens": probe_tokens_total,
        "gate_validation_tokens": gate_validation_tokens,
        "guard_validation_tokens": guard_validation_tokens,
        "guard_amortized_validation_tokens": guard_amortized_tokens,
        "amortized_total_tokens": amortized_total_tokens,
        "prior_guard_rounds_used": (
            int(prior_guard_history["rounds_used"]) if prior_guard_history is not None else 0
        ),
        "prior_guard_paired_samples": (
            int(prior_guard_history["paired_samples"]) if prior_guard_history is not None else 0
        ),
        "prior_guard_stop_reason": (
            str(prior_guard_history["stop_reason"]) if prior_guard_history is not None else "none"
        ),
        "search_overhead_ratio": (
            (credit_update_tokens_total + gate_validation_tokens + guard_validation_tokens)
            / cumulative_tokens
            if cumulative_tokens else 0.0
        ),
        "tokens_to_target": tokens_to_target,
        "amortized_tokens_to_target": amortized_tokens_to_target,
        "reward_per_1k_tokens": float(sum(rewards)) * 1000.0 / cumulative_tokens if cumulative_tokens else 0.0,
        "amortized_reward_per_1k_tokens": (
            float(sum(rewards)) * 1000.0 / amortized_total_tokens
            if amortized_total_tokens else 0.0
        ),
        "utility_calibration_mae": float(np.mean(domain_mae)) if domain_mae else 0.0,
        "utility_rank_correlation": float(np.mean(domain_correlations)) if domain_correlations else 0.0,
        "utility_recovery_tokens": utility_recovery_tokens,
        "corruption_recovery_tokens": corruption_recovery_tokens,
        "post_drift_recovery_tokens": post_drift_recovery_tokens,
        "harmful_rule_selection_rate": harmful_selections / selected_rule_count if selected_rule_count else 0.0,
        "malicious_rule_selection_rate": malicious_selections / selected_rule_count if selected_rule_count else 0.0,
        "conflict_rule_selection_rate": conflict_selections / selected_rule_count if selected_rule_count else 0.0,
        "duplicate_coselection_rate": duplicate_coselection_tasks / len(rows) if rows else 0.0,
        "average_forgetting": float(np.mean(list(forgetting.values()))) if forgetting else 0.0,
        "worst_domain_forgetting": max(forgetting.values(), default=0.0),
        "gate_evaluations": gate_evaluations,
        "gate_accepts": gate_accepts,
        "gate_rejects": gate_rejects,
        "update_acceptance_rate": gate_accepts / gate_evaluations if gate_evaluations else 1.0,
        "mean_new_domain_plasticity": float(np.mean(plasticity_deltas)) if plasticity_deltas else 0.0,
        "worst_old_domain_delta": min(old_domain_deltas, default=0.0),
        "safety_violations": safety_violations,
        "worst_accepted_regression": max(
            0.0, -min(accepted_old_domain_deltas, default=0.0)
        ),
        "routing_ms_mean": routing_seconds * 1000.0 / len(rows) if rows else 0.0,
    }
    fingerprint_payload = {
        "summary": {k: v for k, v in summary.items() if k != "routing_ms_mean"},
        "selected": [row["selected_rule_ids"] for row in rows],
        "rewards": rewards, "probe_history": probe_history, "gate_history": gate_history,
        "prior_guard_history": prior_guard_history,
    }
    fingerprint = hashlib.sha256(json.dumps(
        fingerprint_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    contextual_utilities = {
        domain: state.means_for(domain).tolist() for domain in stream.probes
    } if method.estimator == "contextual" else {}
    return {
        "schema_version": 5,
        "scope": "synthetic offline continual-routing instrumentation; not downstream LLM accuracy",
        "summary": summary, "utility_condition": condition,
        "initial_utilities": prior.tolist(),
        "initial_domain_utilities": {
            domain: values.tolist() for domain, values in initial_domain_priors.items()
        },
        "effective_initial_utilities": effective_initial_prior.tolist(),
        "final_utilities": estimates.tolist(),
        "final_contextual_utilities": contextual_utilities,
        "true_utilities": truth.tolist(), "final_domain_truth": final_domain_truth,
        "probe_history": probe_history, "gate_history": gate_history,
        "prior_guard_history": prior_guard_history,
        "per_step": rows, "run_fingerprint": fingerprint,
    }


def stream_fingerprint(stream: SyntheticStream) -> str:
    payload = {
        "rules": [asdict(rule) for rule in stream.rules],
        "blocks": [[asdict(event) for event in block] for block in stream.blocks],
        "probes": {domain: [asdict(event) for event in events] for domain, events in stream.probes.items()},
        "probes_by_phase": {
            str(phase): {
                domain: [asdict(event) for event in events]
                for domain, events in phase_probes.items()
            }
            for phase, phase_probes in stream.probes_by_phase.items()
        },
    }
    return hashlib.sha256(json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
