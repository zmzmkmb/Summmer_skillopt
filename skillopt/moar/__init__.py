"""MOAR: Multi-Objective Atomic Rule selection via NSGA-II.

Replaces TF-IDF top-K with a multi-objective evolutionary algorithm that
simultaneously optimises relevance, historical utility, token cost, and
redundancy — producing a Pareto-optimal rule subset under budget constraint.

Usage (via RuleMemory factory)::

    from skillopt.rag_rule_selector import RuleMemory
    rm = RuleMemory(skill_content, method="moar", moar_utility_path="outputs/moar_utility.json")
    active = rm.core_rules_text + "\\n\\n" + rm.retrieve(question)
    # After rollout:
    rm.update_utilities(rollout_results)

Public classes
--------------
- :class:`MOARMemory` — drop-in replacement for RuleMemory
- :class:`MOAREngine` — NSGA-II orchestration (usable standalone)
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from skillopt.moar.features import FeatureCache, compute_objectives
from skillopt.moar.nsga2 import NSGA2Config, optimize
from skillopt.moar.tracker import UtilityTracker


@dataclass
class MOARConfig:
    """MOAR hyperparameters exposed via config YAML.

    pop_size:        NSGA-II population size (must be even).
    generations:     NSGA-II generations per query.
    crossover_p:     Uniform crossover probability.
    mutation_p:      Per-gene bit-flip mutation probability.
    weights:         4-tuple of objective weights for Pareto-to-single-solution
                     (relevance, utility, cost, redundancy).  Higher weight
                     for objectives we want to maximise (relevance, utility)
                     and lower for those we want to minimise.
    selection_mode:  "weighted_sum" | "knee_point"
    utility_method:  "precision" | "laplace" | "idf"
    utility_decay:   Exponential decay per save cycle (1.0 = no decay).
    """
    pop_size: int = 50
    generations: int = 30
    crossover_p: float = 0.9
    mutation_p: float = 0.10
    weights: tuple[float, float, float, float] = (0.40, 0.30, 0.20, 0.10)
    selection_mode: str = "weighted_sum"
    utility_method: str = "precision"
    utility_decay: float = 1.0


# ── MOAR Engine ──────────────────────────────────────────────────────────────


class MOAREngine:
    """Orchestrates multi-objective rule selection for a single query.

    Parameters
    ----------
    feature_cache : FeatureCache
        Precomputed rule features.
    tracker : UtilityTracker
        Historical utility accumulator.
    nsga2_config : NSGA2Config | None
        NSGA-II hyperparameters.
    moar_config : MOARConfig | None
        MOAR-specific parameters.
    """

    def __init__(
        self,
        feature_cache: FeatureCache,
        tracker: UtilityTracker,
        nsga2_config: NSGA2Config | None = None,
        moar_config: MOARConfig | None = None,
    ) -> None:
        self._cache = feature_cache
        self._tracker = tracker
        self._nsga2_cfg = nsga2_config or NSGA2Config()
        self._moar_cfg = moar_config or MOARConfig()
        self._last_selections: dict[str, list[int]] = {}

    # ── Public API ────────────────────────────────────────────────────────

    def optimize(
        self,
        query: str,
        vectorizer,
        top_k: int,
        budget: int,
        seed: int | None = None,
    ) -> list[int]:
        """Run NSGA-II to find the best rule subset for *query*.

        Returns the selected rule indices (relative to the dynamic rules list).
        """
        n_rules = self._cache.token_costs.shape[0]
        if n_rules == 0:
            return []

        # Fallback: too few rules to warrant NSGA-II
        if n_rules <= 3:
            return self._tfidf_fallback(query, vectorizer, top_k, budget)

        # Query embedding
        qv = vectorizer.transform([query])

        # Current utilities
        utilities = self._tracker.compute_utilities(self._moar_cfg.utility_method)

        # Build fitness function closure
        cache = self._cache
        tk = top_k
        bd = budget

        def fitness(population: np.ndarray) -> np.ndarray:
            return compute_objectives(population, qv, cache, utilities, bd, tk)

        # Run NSGA-II with both budget and top-K constraints
        rng = np.random.RandomState(seed) if seed is not None else np.random.RandomState()
        pareto_chroms, pareto_objs = optimize(
            fitness,
            n_vars=n_rules,
            budget=budget,
            token_costs=self._cache.token_costs,
            top_k=min(top_k, n_rules),
            config=self._nsga2_cfg,
            rng=rng,
        )

        if len(pareto_chroms) == 0:
            return self._tfidf_fallback(query, vectorizer, top_k, budget)

        # Select single best solution from Pareto front
        best_chrom = self._select_from_pareto(pareto_chroms, pareto_objs,
                                               top_k, budget)

        # Extract selected indices
        indices = [int(i) for i in np.where(best_chrom > 0.5)[0]]

        # Enforce both constraints (defence-in-depth: NSGA-II should guarantee these)
        total_chars = int(sum(self._cache.token_costs[i] for i in indices))
        assert len(indices) <= top_k, \
            f"top-K violated: {len(indices)} > {top_k}"
        assert total_chars <= budget or len(indices) <= 1, \
            f"budget violated: {total_chars} > {budget} with {len(indices)} rules"

        # If we got fewer than top_k rules and budget allows, fill with
        # highest relevance+utility rules
        if len(indices) < top_k:
            rel_scores = self._relevance_scores(qv)
            combined = rel_scores + utilities
            # Filter out already-selected
            for i in indices:
                combined[i] = -np.inf
            # Fill up to top_k, respecting budget
            remaining_budget = budget - sum(
                self._cache.token_costs[i] for i in indices
            )
            fill_order = np.argsort(-combined)
            for idx in fill_order:
                if len(indices) >= top_k:
                    break
                if idx in indices:
                    continue
                cost = self._cache.token_costs[idx]
                if cost <= remaining_budget or len(indices) == 0:
                    indices.append(int(idx))
                    remaining_budget -= cost

        # Record for utility update
        self._last_selections[query] = list(indices)

        return indices

    def update_utilities(self, rollout_results: list[dict]) -> None:
        """Feed back rollout outcomes to update per-rule utility.

        Call this after each rollout batch with the raw rollout result dicts.
        Matches queries via the ``question`` field.
        """
        for result in rollout_results:
            question = str(result.get("question", "") or "")
            if not question:
                continue
            correct = int(result.get("hard", 0)) == 1
            # Try to find by question text
            if question in self._last_selections:
                self._tracker.record_selection(
                    self._last_selections.pop(question), correct
                )
            else:
                # Try partial match (query text may have been truncated)
                for q_key in list(self._last_selections):
                    if q_key in question or question in q_key:
                        self._tracker.record_selection(
                            self._last_selections.pop(q_key), correct
                        )
                        break
        self._tracker.save()

    # ── Pareto selection ─────────────────────────────────────────────────

    def _select_from_pareto(
        self,
        pareto_chroms: np.ndarray,
        pareto_objs: np.ndarray,
        top_k: int,
        budget: int,
    ) -> np.ndarray:
        """Select the single best chromosome from the Pareto front."""
        mode = self._moar_cfg.selection_mode

        if mode == "knee_point":
            return self._knee_point_select(pareto_chroms, pareto_objs)

        return self._weighted_sum_select(pareto_chroms, pareto_objs,
                                          top_k, budget)

    def _weighted_sum_select(
        self,
        pareto_chroms: np.ndarray,
        pareto_objs: np.ndarray,
        top_k: int,
        budget: int,
    ) -> np.ndarray:
        """Weighted sum: higher weight = more important to minimise that objective.

        f1, f2 are (1 - util), (1 - rel) — we want those small.
        f3, f4 are cost, redundancy — we want those small too.

        Score = w1*(1-f1) + w2*(1-f2) - w3*f3 - w4*f4
              = maximise relevance+utility, minimise cost+redundancy.
        """
        w = self._moar_cfg.weights
        # f1, f2 are minimised versions of (1 - actual).  Invert.
        scores = (
            w[0] * (1.0 - pareto_objs[:, 0])   # relevance
            + w[1] * (1.0 - pareto_objs[:, 1])  # utility
            - w[2] * pareto_objs[:, 2]           # cost penalty
            - w[3] * pareto_objs[:, 3]           # redundancy penalty
        )
        best = int(np.argmax(scores))
        return pareto_chroms[best]

    def _knee_point_select(
        self,
        pareto_chroms: np.ndarray,
        pareto_objs: np.ndarray,
    ) -> np.ndarray:
        """Knee-point detection: solution with max distance to ideal-nadir line."""
        if len(pareto_chroms) <= 2:
            return pareto_chroms[0]

        ideal = pareto_objs.min(axis=0)
        nadir = pareto_objs.max(axis=0)
        direction = nadir - ideal

        if np.linalg.norm(direction) < 1e-12:
            return pareto_chroms[0]

        # Project each point onto the ideal-nadir line and compute distance
        dir_norm = direction / np.linalg.norm(direction)
        distances = np.zeros(len(pareto_chroms))
        for i in range(len(pareto_chroms)):
            v = pareto_objs[i] - ideal
            proj = np.dot(v, dir_norm) * dir_norm
            distances[i] = np.linalg.norm(v - proj)

        best = int(np.argmax(distances))
        return pareto_chroms[best]

    # ── Helpers ──────────────────────────────────────────────────────────

    def _relevance_scores(self, query_embedding) -> np.ndarray:
        """Compute TF-IDF cosine relevance scores for the current query."""
        from sklearn.metrics.pairwise import cosine_similarity

        qv = query_embedding
        rv = self._cache.rule_embeddings
        if hasattr(qv, 'toarray'):
            qv = qv.toarray().ravel()
        if hasattr(rv, 'toarray'):
            rv = rv.toarray()
        return cosine_similarity(qv.reshape(1, -1), rv).ravel()

    def _tfidf_fallback(
        self, query: str, vectorizer, top_k: int, budget: int
    ) -> list[int]:
        """Fall back to plain TF-IDF when n_rules is too small for NSGA-II."""
        from sklearn.metrics.pairwise import cosine_similarity

        qv = vectorizer.transform([query])
        rv = self._cache.rule_embeddings
        if hasattr(rv, 'toarray'):
            rv = rv.toarray()
        sims = cosine_similarity(qv, rv).ravel()
        order = np.argsort(-sims)

        indices = []
        used = 0
        for idx in order:
            if len(indices) >= top_k:
                break
            cost = self._cache.token_costs[idx]
            if used + cost > budget:
                continue
            indices.append(int(idx))
            used += cost

        self._last_selections[query] = list(indices)
        return indices


# ── MOARMemory: a RuleMemory subclass ─────────────────────────────────────────


class MOARMemory:
    """Multi-Objective Atomic Rule selection memory.

    DO NOT instantiate directly.  Use :func:`RuleMemory` with ``method="moar"``;
    the ``__new__`` method on RuleMemory routes to this class.

    Extends RuleMemory's parse/embed infrastructure with multi-objective
    NSGA-II retrieval and per-rule utility tracking.

    Additional Parameters (vs RuleMemory)
    -------------------------------------
    moar_utility_path : str | None
        JSON file path for utility persistence.
    moar_pop_size, moar_generations, moar_crossover_p, moar_mutation_p : ...
        NSGA-II hyperparameters.
    moar_weights : str
        Comma-separated four floats, e.g. ``"0.4,0.3,0.2,0.1"``.
    moar_selection_mode : str
        ``"weighted_sum"`` (default) or ``"knee_point"``.
    moar_utility_method : str
        ``"precision"``, ``"laplace"``, or ``"idf"``.
    moar_utility_decay : float
        Exponential decay factor (1.0 = no decay).
    moar_tokenizer : str
        tiktoken encoding name for real token counting ("" = use char length).
        Default ``"cl100k_base"`` is a good approximation for Qwen/GPT-4 family.
    moar_frozen : bool
        If True, utility updates are no-ops (test-set isolation).
    moar_base_seed : int
        Base seed for deterministic NSGA-II per-query seeds.  Queries
        with seed={42,43,44} produce genuinely different MOAR selections.
        Default 42.
    """

    def __init__(
        self,
        skill_content: str,
        top_k: int = 5,
        token_budget: int = 2000,
        method: str = "moar",
        moar_utility_path: str | None = None,
        moar_pop_size: int = 50,
        moar_generations: int = 30,
        moar_crossover_p: float = 0.9,
        moar_mutation_p: float = 0.10,
        moar_weights: str = "0.4,0.3,0.2,0.1",
        moar_selection_mode: str = "weighted_sum",
        moar_utility_method: str = "precision",
        moar_utility_decay: float = 1.0,
        moar_tokenizer: str = "cl100k_base",
        moar_frozen: bool = False,
        moar_base_seed: int = 42,
        **__,
    ) -> None:
        # Import parent here to avoid circular import at module level
        from skillopt.rag_rule_selector import RuleMemory

        # Build the parent (TF-IDF) infrastructure first — we reuse its
        # parsing, embedding, and text concatenation logic.
        self._parent = RuleMemory(
            skill_content, top_k=top_k, token_budget=token_budget,
            method="tfidf",
        )

        # ── Token counter (real tokenizer) ────────────────────────────────
        token_counter = None
        tokenizer_used = False
        if moar_tokenizer:
            try:
                from skillopt.moar.tokenizer import get_counter
                token_counter = get_counter(moar_tokenizer)
                tokenizer_used = True
            except Exception:
                pass  # fallback to char length

        # ── Build feature cache ──────────────────────────────────────────
        if self._parent.n_dynamic > 0:
            rule_texts = [r.full_text for r in self._parent.dynamic_rules]
            self._cache = FeatureCache.from_arrays(
                rule_texts,
                self._parent._rule_matrix,
                token_counter=token_counter,
            )
        else:
            self._cache = FeatureCache.from_arrays([], np.empty((0, 0)))

        # ── Utility tracker with stable rule IDs ─────────────────────────
        self._tracker = UtilityTracker(
            persistence_path=moar_utility_path,
            decay=float(moar_utility_decay),
            frozen=bool(moar_frozen),
        )
        if self._parent.n_dynamic > 0:
            self._tracker.register_rules(
                [r.full_text for r in self._parent.dynamic_rules]
            )

        # Store base seed for per-query determinism
        self.moar_base_seed = int(moar_base_seed)

        # ── 统一 cost 函数：token 模式 vs 字符模式 ────────────────────────
        self._token_counter = token_counter

        # Log tokenizer mode
        cost_kind = "tokens" if tokenizer_used else "chars"
        if self._parent.n_dynamic > 0:
            avg_cost = float(np.mean(self._cache.token_costs))
            print(f"  [moar] {cost_kind} mode, avg={avg_cost:.0f} {cost_kind}/rule, "
                  f"frozen={moar_frozen} seed={self.moar_base_seed}", flush=True)

        # ── Parse weights ────────────────────────────────────────────────
        try:
            parts = [float(x.strip()) for x in moar_weights.split(",")]
            weights = tuple(parts[:4])
            if len(weights) < 4:
                weights = (0.4, 0.3, 0.2, 0.1)
        except (ValueError, AttributeError):
            weights = (0.4, 0.3, 0.2, 0.1)

        # ── NSGA-II engine ───────────────────────────────────────────────
        self._engine = MOAREngine(
            feature_cache=self._cache,
            tracker=self._tracker,
            nsga2_config=NSGA2Config(
                pop_size=int(moar_pop_size),
                generations=int(moar_generations),
                crossover_p=float(moar_crossover_p),
                mutation_p=float(moar_mutation_p),
            ),
            moar_config=MOARConfig(
                pop_size=int(moar_pop_size),
                generations=int(moar_generations),
                crossover_p=float(moar_crossover_p),
                mutation_p=float(moar_mutation_p),
                weights=weights,
                selection_mode=moar_selection_mode,
                utility_method=moar_utility_method,
                utility_decay=float(moar_utility_decay),
            ),
        )

        # Expose same public attributes as RuleMemory
        self.top_k = top_k
        self.token_budget = token_budget
        self.method = method

    # ── Delegate properties to parent ──────────────────────────────────

    @property
    def core_rules_text(self) -> str:
        return self._parent.core_rules_text

    @property
    def dynamic_rules(self):
        return self._parent.dynamic_rules

    @property
    def n_total(self) -> int:
        return self._parent.n_total

    @property
    def n_core(self) -> int:
        return self._parent.n_core

    @property
    def n_dynamic(self) -> int:
        return self._parent.n_dynamic

    @property
    def _last_selections(self) -> dict[str, list[int]]:
        return self._engine._last_selections

    # ── Retrieval ───────────────────────────────────────────────────────

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        token_budget: int | None = None,
    ) -> str:
        """Return the Pareto-optimal rule subset for *query*."""
        k = top_k if top_k is not None else self.top_k
        budget = token_budget if token_budget is not None else self.token_budget

        if self.n_dynamic == 0:
            return ""

        indices = self._engine.optimize(
            query,
            self._parent._vectorizer,
            min(k, self.n_dynamic),
            budget,
            seed=_make_query_seed(self.moar_base_seed, query),
        )

        if not indices:
            return ""

        return self._concat_rules(indices, budget)

    def update_utilities(self, rollout_results: list[dict]) -> None:
        """Call after each rollout batch to update per-rule utility."""
        self._engine.update_utilities(rollout_results)

    # ── Helpers ─────────────────────────────────────────────────────────

    def _text_cost(self, text: str) -> int:
        """统一 cost 度量：tokenizer 可用时用 token 数，否则用字符数。

        保证 NSGA-II 优化约束与最终拼接截断使用同一计量方式。
        """
        if self._token_counter is not None:
            return self._token_counter.count(text)
        return len(text)

    def _concat_rules(self, indices: list[int], budget: int) -> str:
        """拼接选中规则文本，统一用 _text_cost 做预算截断。"""
        rules = self._parent.dynamic_rules
        selected = sorted(indices, key=lambda i: rules[i].index)
        parts: list[str] = []
        used = 0
        separator_cost = self._text_cost("\n\n")
        for i in selected:
            text = rules[i].full_text
            cost = self._text_cost(text)
            if used + cost > budget:
                if parts:
                    break
                # 第一条规则就超预算：硬截断
                text = text[:max(budget - used, 1)] + "…"
                cost = self._text_cost(text)
            parts.append(text)
            used += cost + separator_cost
        return "\n\n".join(parts)


def _make_query_seed(base_seed: int, query: str) -> int:
    """Deterministic per-query seed incorporating the base run seed.

    ``base_seed=42`` and ``base_seed=43`` produce genuinely different
    MOAR selections for the same query — enabling multi-seed experiments.
    """
    import hashlib
    raw = f"{base_seed}:{query}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:4], byteorder="little")
