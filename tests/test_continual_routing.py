from __future__ import annotations

import numpy as np
import pytest

from skillopt.evaluation.continual_routing import (
    ContextualUtilityState,
    MethodSpec,
    OnlineUtilityState,
    RuleSpec,
    TaskEvent,
    build_prior_identity_state,
    credit_assignment,
    evaluate_non_regression_gate,
    evaluate_prior_representativeness,
    exact_budgeted_selection,
    expected_reward,
    generate_contextual_synthetic_stream,
    generate_synthetic_stream,
    initialise_contextual_utilities,
    initialise_utilities,
    run_continual_experiment,
    stream_fingerprint,
)


def _stream(seed: int = 7):
    return generate_synthetic_stream(
        seed=seed,
        n_rules=12,
        domains=["a", "b"],
        block_order=["a", "b", "a"],
        tasks_per_block=5,
        probe_tasks_per_domain=3,
    )


def test_stream_and_run_fingerprints_are_deterministic():
    first_stream = _stream()
    second_stream = _stream()
    assert stream_fingerprint(first_stream) == stream_fingerprint(second_stream)
    method = MethodSpec("ucb_shared", "ucb", "shared")
    kwargs = dict(
        method=method,
        condition="all-cold",
        seed=11,
        top_k=2,
        budget=120,
        token_target=0.55,
        target_window=4,
        target_sustain=2,
    )
    first = run_continual_experiment(stream=first_stream, **kwargs)
    second = run_continual_experiment(stream=second_stream, **kwargs)
    assert first["run_fingerprint"] == second["run_fingerprint"]
    assert first["summary"]["total_tokens"] == second["summary"]["total_tokens"]


def test_leave_one_out_charges_extra_tokens_and_assigns_per_rule_credit():
    rules = (
        RuleSpec("good", "a", 30, 0.9),
        RuleSpec("bad", "a", 30, 0.2),
    )
    event = TaskEvent("q", "a", ("good",), (0.9, 0.8), input_tokens=100)
    selected = [0, 1]
    from skillopt.evaluation.continual_routing import expected_reward

    reward = expected_reward(event, rules, selected)
    shared, shared_tokens = credit_assignment(
        mode="shared", event=event, rules=rules, selected=selected, reward=reward,
    )
    loo, loo_tokens = credit_assignment(
        mode="leave-one-out", event=event, rules=rules, selected=selected, reward=reward,
    )
    assert shared_tokens == 0
    assert loo_tokens == 2 * (100 + 8 + 30)
    assert shared[0] == shared[1]
    assert loo[0] > loo[1]


def test_adversarial_initialisation_reverses_truth_ranking():
    rules = [RuleSpec(f"r{i}", "a", 10, value) for i, value in enumerate([0.1, 0.3, 0.7, 0.9])]
    truth = np.asarray([rule.true_utility for rule in rules])
    adversarial = initialise_utilities(rules, condition="adversarial", seed=1)
    assert np.corrcoef(truth, adversarial)[0, 1] < -0.99
    assert np.allclose(initialise_utilities(rules, condition="all-cold", seed=1), 0.5)


def test_exact_selection_respects_budget_and_cardinality():
    rules = [
        RuleSpec("a", "x", 60, 0.5),
        RuleSpec("b", "x", 50, 0.5),
        RuleSpec("c", "x", 40, 0.5),
    ]
    selected = exact_budgeted_selection([1.0, 0.9, 0.8], rules, top_k=2, budget=90)
    assert selected == [1, 2]
    assert sum(rules[index].token_cost for index in selected) <= 90


def test_oracle_is_an_upper_bound_on_relevance_for_same_stream():
    stream = _stream(seed=13)
    common = dict(
        stream=stream,
        condition="all-cold",
        seed=13,
        top_k=2,
        budget=120,
        token_target=0.55,
        target_window=4,
        target_sustain=2,
    )
    relevance = run_continual_experiment(
        method=MethodSpec("relevance", "relevance", "none"), **common,
    )
    oracle = run_continual_experiment(
        method=MethodSpec("oracle", "oracle", "oracle-per-rule"), **common,
    )
    assert oracle["summary"]["mean_reward"] >= relevance["summary"]["mean_reward"]
    assert oracle["summary"]["cumulative_regret"] <= 1e-12


def test_leave_one_out_run_reports_higher_total_cost_than_shared():
    stream = _stream(seed=19)
    common = dict(
        stream=stream,
        condition="all-cold",
        seed=19,
        top_k=2,
        budget=120,
        token_target=0.55,
        target_window=4,
        target_sustain=2,
    )
    shared = run_continual_experiment(
        method=MethodSpec("greedy_shared", "greedy-utility", "shared"), **common,
    )
    loo = run_continual_experiment(
        method=MethodSpec("greedy_loo", "greedy-utility", "leave-one-out"), **common,
    )
    assert loo["summary"]["credit_update_tokens"] > 0
    assert loo["summary"]["total_tokens"] > shared["summary"]["total_tokens"]

def test_contextual_state_updates_only_target_domain_plus_global():
    state = ContextualUtilityState.from_prior(
        np.asarray([0.5, 0.5]), ["a", "b"], prior_strength=2.0, context_weight=0.75,
    )
    before_b = state.domain_states["b"].means.copy()
    state.update([0], [1.0], domain="a")
    assert state.global_state.means[0] > 0.5
    assert state.domain_states["a"].means[0] > 0.5
    assert np.allclose(state.domain_states["b"].means, before_b)
    assert state.means_for("a")[0] > state.means_for("b")[0]


def test_contextual_state_clone_is_independent_and_exact():
    state = ContextualUtilityState.from_prior(
        np.asarray([0.4, 0.6]), ["a", "b"], prior_strength=2.0, context_weight=0.8,
    )
    state.update([0], [0.9], domain="a")
    snapshot = state.clone()
    assert np.allclose(snapshot.means_for("a"), state.means_for("a"))
    assert np.allclose(snapshot.means_for("b"), state.means_for("b"))
    state.update([1], [0.0], domain="b")
    assert not np.allclose(snapshot.means_for("b"), state.means_for("b"))


def test_non_regression_gate_rejects_unsafe_and_accepts_safe_plastic_update():
    unsafe = evaluate_non_regression_gate(
        gate="non-regression",
        baseline_scores={"old": 0.80, "new": 0.40},
        candidate_scores={"old": 0.76, "new": 0.60},
        current_domain="new",
        old_domains=["old"],
        tolerance=0.01,
        min_plasticity=0.0,
    )
    assert not unsafe["accepted"]
    assert unsafe["worst_old_domain_delta"] < -0.01

    safe = evaluate_non_regression_gate(
        gate="balanced",
        baseline_scores={"old": 0.80, "new": 0.40},
        candidate_scores={"old": 0.795, "new": 0.45},
        current_domain="new",
        old_domains=["old"],
        tolerance=0.01,
        min_plasticity=0.02,
    )
    assert safe["accepted"]
    assert safe["plastic"]


def test_gate_run_charges_validation_tokens_and_reports_acceptance():
    stream = _stream(seed=23)
    result = run_continual_experiment(
        stream=stream,
        method=MethodSpec(
            "contextual_nonreg", "greedy-utility", "shared",
            estimator="contextual", gate="non-regression",
        ),
        condition="all-cold",
        seed=23,
        top_k=2,
        budget=120,
        token_target=0.55,
        target_window=4,
        target_sustain=2,
    )
    summary = result["summary"]
    assert summary["gate_validation_tokens"] > 0
    assert summary["gate_evaluations"] == len(stream.blocks)
    assert summary["gate_accepts"] + summary["gate_rejects"] == len(stream.blocks)
    assert 0.0 <= summary["update_acceptance_rate"] <= 1.0
    assert summary["total_tokens"] == (
        summary["inference_tokens"]
        + summary["credit_update_tokens"]
        + summary["probe_tokens"]
        + summary["gate_validation_tokens"]
        + summary["guard_validation_tokens"]
    )
    assert len(result["gate_history"]) == len(stream.blocks)


def test_contextual_gated_run_fingerprint_is_deterministic():
    method = MethodSpec(
        "contextual_balanced", "greedy-utility", "shared",
        estimator="contextual", gate="balanced",
    )
    common = dict(
        method=method,
        condition="adversarial",
        seed=31,
        top_k=2,
        budget=120,
        token_target=0.55,
        target_window=4,
        target_sustain=2,
    )
    first = run_continual_experiment(stream=_stream(seed=31), **common)
    second = run_continual_experiment(stream=_stream(seed=31), **common)
    assert first["run_fingerprint"] == second["run_fingerprint"]


def _contextual_stream(seed: int = 37):
    return generate_contextual_synthetic_stream(
        seed=seed,
        n_rules=20,
        domains=["a", "b"],
        block_order=["a", "b", "a", "b"],
        tasks_per_block=3,
        probe_tasks_per_domain=2,
    )


def test_contextual_stream_contains_transfer_conflict_duplicates_and_drift():
    stream = _contextual_stream()
    assert {rule.rule_type for rule in stream.rules} == {
        "specialist", "shared", "conflict", "malicious", "duplicate",
    }
    assert any(
        len({round(value, 8) for _, value in rule.domain_utilities}) > 1
        for rule in stream.rules
    )
    phase_one = [event for block in stream.blocks for event in block if event.drift_phase == 1]
    assert phase_one
    assert all(event.utility_overrides for event in phase_one)
    assert set(stream.probes_by_phase) == {0, 1}


def test_contextual_duplicate_family_is_penalised_and_malicious_rule_can_hurt():
    rules = (
        RuleSpec("original", "a", 20, 0.8, (("a", 0.8),), "specialist"),
        RuleSpec("duplicate", "a", 20, 0.79, (("a", 0.79),), "duplicate", "original"),
        RuleSpec("distinct", "a", 20, 0.7, (("a", 0.7),), "specialist"),
        RuleSpec("malicious", "a", 20, -0.8, (("a", -0.8),), "malicious"),
    )
    event = TaskEvent(
        "q", "a", tuple(rule.rule_id for rule in rules),
        (0.9, 0.9, 0.8, 0.95), input_tokens=80,
    )
    assert expected_reward(event, rules, [0, 1]) < expected_reward(event, rules, [0, 2])
    assert expected_reward(event, rules, [0, 3]) < expected_reward(event, rules, [0])


def test_online_and_contextual_corruption_are_deterministic_and_effective():
    prior = np.asarray([0.1, 0.3, 0.7, 0.9])
    first = OnlineUtilityState.from_prior(prior)
    second = OnlineUtilityState.from_prior(prior)
    first.corrupt("shuffled", np.random.default_rng(9))
    second.corrupt("shuffled", np.random.default_rng(9))
    assert np.allclose(first.means, second.means)
    assert not np.allclose(first.means, prior)

    contextual_a = ContextualUtilityState.from_prior(prior, ["a", "b"])
    contextual_b = ContextualUtilityState.from_prior(prior, ["a", "b"])
    contextual_a.corrupt("adversarial", np.random.default_rng(11))
    contextual_b.corrupt("adversarial", np.random.default_rng(11))
    assert np.allclose(contextual_a.global_state.means, contextual_b.global_state.means)
    assert np.allclose(contextual_a.means_for("a"), contextual_b.means_for("a"))
    assert not np.allclose(contextual_a.means_for("a"), prior)


def test_contextual_oracle_is_upper_bound_and_recovery_metrics_exist():
    stream = _contextual_stream(seed=43)
    common = dict(
        stream=stream,
        condition="all-cold",
        seed=43,
        top_k=2,
        budget=120,
        token_target=0.60,
        target_window=4,
        target_sustain=2,
        corruption_mode="shuffled",
        corruption_block=2,
        recovery_sustain=2,
    )
    relevance = run_continual_experiment(
        method=MethodSpec("relevance", "relevance", "none"), **common,
    )
    oracle = run_continual_experiment(
        method=MethodSpec("oracle", "oracle", "oracle-per-rule"), **common,
    )
    assert oracle["summary"]["mean_reward"] >= relevance["summary"]["mean_reward"]
    assert oracle["summary"]["cumulative_regret"] <= 1e-12
    for key in (
        "utility_recovery_tokens", "corruption_recovery_tokens", "post_drift_recovery_tokens",
        "harmful_rule_selection_rate", "malicious_rule_selection_rate",
        "conflict_rule_selection_rate", "duplicate_coselection_rate",
    ):
        assert key in relevance["summary"]


def test_contextual_corruption_run_is_deterministic_and_preserves_token_identity():
    method = MethodSpec(
        "contextual_corrupted", "greedy-utility", "shared", estimator="contextual",
    )
    common = dict(
        method=method,
        condition="adversarial",
        seed=47,
        top_k=2,
        budget=120,
        token_target=0.60,
        target_window=4,
        target_sustain=2,
        corruption_mode="shuffled",
        corruption_block=2,
        recovery_sustain=2,
    )
    first = run_continual_experiment(stream=_contextual_stream(seed=47), **common)
    second = run_continual_experiment(stream=_contextual_stream(seed=47), **common)
    assert first["run_fingerprint"] == second["run_fingerprint"]
    summary = first["summary"]
    assert summary["total_tokens"] == (
        summary["inference_tokens"]
        + summary["credit_update_tokens"]
        + summary["probe_tokens"]
        + summary["gate_validation_tokens"]
        + summary["guard_validation_tokens"]
    )


def test_corruption_permutation_is_method_name_invariant_for_deterministic_policy():
    common = dict(
        condition="all-cold",
        seed=53,
        top_k=2,
        budget=120,
        token_target=0.60,
        target_window=4,
        target_sustain=2,
        corruption_mode="shuffled",
        corruption_block=2,
        recovery_sustain=2,
    )
    first = run_continual_experiment(
        stream=_contextual_stream(seed=53),
        method=MethodSpec("name_a", "greedy-utility", "shared", estimator="contextual"),
        **common,
    )
    second = run_continual_experiment(
        stream=_contextual_stream(seed=53),
        method=MethodSpec("name_b", "greedy-utility", "shared", estimator="contextual"),
        **common,
    )
    assert [row["selected_rule_ids"] for row in first["per_step"]] == [
        row["selected_rule_ids"] for row in second["per_step"]
    ]
    assert [row["reward"] for row in first["per_step"]] == [
        row["reward"] for row in second["per_step"]
    ]


def test_adaptive_context_weight_starts_global_and_grows_with_local_evidence():
    state = ContextualUtilityState.from_prior(
        np.asarray([0.5, 0.5]), ["a", "b"], prior_strength=2.0,
        context_weight_mode="adaptive", context_evidence_scale=2.0,
        context_min_weight=0.0, context_max_weight=0.9,
    )
    assert np.allclose(state.context_weights_for("a"), 0.0)
    state.update([0], [1.0], domain="a")
    weights_a = state.context_weights_for("a")
    weights_b = state.context_weights_for("b")
    assert np.isclose(weights_a[0], 0.3)
    assert weights_a[1] == 0.0
    assert np.allclose(weights_b, 0.0)
    state.update([0], [1.0], domain="a")
    assert state.context_weights_for("a")[0] > weights_a[0]


def test_fixed_context_weight_remains_backward_compatible():
    state = ContextualUtilityState.from_prior(
        np.asarray([0.4, 0.6]), ["a"], context_weight=0.75,
    )
    assert np.allclose(state.context_weights_for("a"), 0.75)
    state.update([0], [1.0], domain="a")
    expected = 0.25 * state.global_state.means + 0.75 * state.domain_states["a"].means
    assert np.allclose(state.means_for("a"), expected)
    clone = state.clone()
    assert clone.context_weight_mode == "fixed"
    assert np.allclose(clone.means_for("a"), state.means_for("a"))




def _prior_guard_run(*, condition: str, guard: str, seed: int = 71):
    return run_continual_experiment(
        stream=_contextual_stream(seed=seed),
        method=MethodSpec(
            "prior_guard_candidate", "greedy-utility", "oracle-per-rule",
            estimator="contextual", context_weight=0.5,
            prior_guard=guard, prior_guard_tolerance=0.05,
        ),
        condition=condition,
        seed=seed,
        top_k=2,
        budget=120,
        token_target=0.60,
        target_window=4,
        target_sustain=2,
    )


def test_prior_guard_resets_harmful_adversarial_prior_and_improves_reward():
    unguarded = _prior_guard_run(condition="adversarial", guard="none")
    guarded = _prior_guard_run(condition="adversarial", guard="reset-cold")
    cold = _prior_guard_run(condition="all-cold", guard="none")

    assert guarded["summary"]["prior_guard_triggered"]
    assert guarded["prior_guard_history"]["action"] == "reset-cold"
    assert not np.allclose(guarded["initial_utilities"], 0.5)
    assert np.allclose(guarded["effective_initial_utilities"], 0.5)
    assert guarded["summary"]["mean_reward"] > unguarded["summary"]["mean_reward"]
    assert np.isclose(guarded["summary"]["mean_reward"], cold["summary"]["mean_reward"])


def test_prior_guard_does_not_reset_acceptable_all_cold_prior():
    guarded = _prior_guard_run(condition="all-cold", guard="reset-cold")
    assert not guarded["summary"]["prior_guard_triggered"]
    assert guarded["prior_guard_history"]["action"] == "none"
    assert np.allclose(guarded["initial_utilities"], guarded["effective_initial_utilities"])


def test_prior_guard_charges_both_probe_routes_and_preserves_token_identity():
    result = _prior_guard_run(condition="adversarial", guard="reset-cold")
    summary = result["summary"]
    history = result["prior_guard_history"]
    assert history is not None
    assert history["learned_probe_tokens"] > 0
    assert history["relevance_probe_tokens"] > 0
    assert summary["guard_validation_tokens"] == (
        history["learned_probe_tokens"] + history["relevance_probe_tokens"]
    )
    assert summary["total_tokens"] == (
        summary["inference_tokens"]
        + summary["credit_update_tokens"]
        + summary["probe_tokens"]
        + summary["gate_validation_tokens"]
        + summary["guard_validation_tokens"]
    )
    assert result["per_step"][0]["cumulative_tokens"] >= summary["guard_validation_tokens"]


def test_prior_guard_history_and_fingerprint_are_deterministic():
    first = _prior_guard_run(condition="adversarial", guard="reset-cold")
    second = _prior_guard_run(condition="adversarial", guard="reset-cold")
    unguarded = _prior_guard_run(condition="adversarial", guard="none")
    assert first["prior_guard_history"] == second["prior_guard_history"]
    assert first["run_fingerprint"] == second["run_fingerprint"]
    assert first["run_fingerprint"] != unguarded["run_fingerprint"]


def test_prior_guard_can_fall_back_to_relevance_without_learning_cost():
    result = _prior_guard_run(condition="adversarial", guard="fallback-relevance")
    summary = result["summary"]
    assert summary["prior_guard_triggered"]
    assert result["prior_guard_history"]["action"] == "fallback-relevance"
    assert summary["effective_policy"] == "relevance"
    assert summary["effective_credit"] == "none"
    assert summary["credit_update_tokens"] == 0



def test_prior_guard_probe_limit_reduces_charged_validation_tokens():
    common = dict(
        stream=generate_contextual_synthetic_stream(
            seed=71, n_rules=20, domains=["a", "b"],
            block_order=["a", "b", "a", "b"], tasks_per_block=3,
            probe_tasks_per_domain=8,
        ),
        condition="adversarial", seed=71, top_k=2, budget=120,
        token_target=0.60, target_window=4, target_sustain=2,
    )
    one = run_continual_experiment(
        method=MethodSpec(
            "guard_one", "greedy-utility", "shared", estimator="contextual",
            prior_guard="reset-cold", prior_guard_tolerance=0.06,
            prior_guard_max_probes_per_domain=1,
        ), **common,
    )
    eight = run_continual_experiment(
        method=MethodSpec(
            "guard_eight", "greedy-utility", "shared", estimator="contextual",
            prior_guard="reset-cold", prior_guard_tolerance=0.06,
            prior_guard_max_probes_per_domain=8,
        ), **common,
    )
    assert one["summary"]["prior_guard_rounds_used"] == 1
    assert eight["summary"]["prior_guard_rounds_used"] == 8
    assert one["summary"]["guard_validation_tokens"] < eight["summary"]["guard_validation_tokens"]


def test_sequential_prior_guard_stops_early_on_acceptable_prior():
    result = run_continual_experiment(
        stream=generate_contextual_synthetic_stream(
            seed=71, n_rules=20, domains=["a", "b"],
            block_order=["a", "b", "a", "b"], tasks_per_block=3,
            probe_tasks_per_domain=8,
        ),
        method=MethodSpec(
            "sequential_guard", "greedy-utility", "shared", estimator="contextual",
            prior_guard="reset-cold", prior_guard_tolerance=0.06,
            prior_guard_max_probes_per_domain=8, prior_guard_sequential=True,
            prior_guard_min_samples=4,
        ),
        condition="all-cold", seed=71, top_k=2, budget=120,
        token_target=0.60, target_window=4, target_sustain=2,
    )
    assert not result["summary"]["prior_guard_triggered"]
    assert result["summary"]["prior_guard_rounds_used"] < 8
    assert result["summary"]["prior_guard_stop_reason"] == "confident-acceptable"


def test_prior_guard_amortized_metrics_do_not_change_exact_token_identity():
    result = run_continual_experiment(
        stream=_contextual_stream(seed=71),
        method=MethodSpec(
            "amortized_guard", "greedy-utility", "shared", estimator="contextual",
            prior_guard="reset-cold", prior_guard_tolerance=0.06,
            prior_guard_max_probes_per_domain=2,
            prior_guard_relevance_cost_share=0.25,
        ),
        condition="adversarial", seed=71, top_k=2, budget=120,
        token_target=0.60, target_window=4, target_sustain=2,
    )
    summary = result["summary"]
    history = result["prior_guard_history"]
    expected_amortized_guard = (
        history["learned_probe_tokens"] + 0.25 * history["relevance_probe_tokens"]
    )
    assert np.isclose(summary["guard_amortized_validation_tokens"], expected_amortized_guard)
    assert summary["amortized_total_tokens"] < summary["total_tokens"]
    assert summary["total_tokens"] == (
        summary["inference_tokens"] + summary["credit_update_tokens"]
        + summary["probe_tokens"] + summary["gate_validation_tokens"]
        + summary["guard_validation_tokens"]
    )


def test_selection_disagreement_probe_order_is_deterministic_and_ranked():
    common = dict(
        stream=generate_contextual_synthetic_stream(
            seed=91, n_rules=20, domains=["a", "b"],
            block_order=["a", "b", "a", "b"], tasks_per_block=3,
            probe_tasks_per_domain=8,
        ),
        method=MethodSpec(
            "informative_guard", "greedy-utility", "shared", estimator="contextual",
            prior_guard="reset-cold", prior_guard_tolerance=0.06,
            prior_guard_max_probes_per_domain=1,
            prior_guard_probe_order="selection-disagreement",
        ),
        condition="adversarial", seed=91, top_k=2, budget=120,
        token_target=0.60, target_window=4, target_sustain=2,
    )
    first = run_continual_experiment(**common)
    second = run_continual_experiment(**common)
    history = first["prior_guard_history"]
    assert history["probe_order"] == "selection-disagreement"
    assert history == second["prior_guard_history"]
    assert first["run_fingerprint"] == second["run_fingerprint"]
    for domain, plan in history["probe_plan"].items():
        disagreements = [item["selection_disagreement"] for item in plan]
        assert disagreements == sorted(disagreements, reverse=True)
        assert history["evaluated_event_ids"][domain] == [plan[0]["event_id"]]
    summary = first["summary"]
    assert summary["prior_guard_probe_order"] == "selection-disagreement"
    assert summary["total_tokens"] == (
        summary["inference_tokens"] + summary["credit_update_tokens"]
        + summary["probe_tokens"] + summary["gate_validation_tokens"]
        + summary["guard_validation_tokens"]
    )


def test_prior_guard_reports_action_and_reset_magnitude():
    guarded = _prior_guard_run(condition="adversarial", guard="reset-cold")
    acceptable = _prior_guard_run(condition="all-cold", guard="reset-cold")
    assert guarded["summary"]["prior_guard_action"] == "reset-cold"
    assert guarded["summary"]["prior_guard_reset_magnitude"] > 0.0
    assert acceptable["summary"]["prior_guard_action"] == "none"
    assert acceptable["summary"]["prior_guard_reset_magnitude"] == 0.0


def test_prior_guard_rejects_unknown_probe_order():
    with pytest.raises(ValueError, match="Unsupported prior-guard probe order"):
        run_continual_experiment(
            stream=_contextual_stream(seed=93),
            method=MethodSpec(
                "bad_probe_order", "greedy-utility", "shared", estimator="contextual",
                prior_guard="reset-cold", prior_guard_probe_order="unknown",
            ),
            condition="all-cold", seed=93, top_k=2, budget=120,
            token_target=0.60, target_window=4, target_sustain=2,
        )


def _cold_router_guard_run(*, condition: str, seed: int = 2, max_probes: int = 1):
    return run_continual_experiment(
        stream=generate_contextual_synthetic_stream(
            seed=seed, n_rules=20, domains=["a", "b"],
            block_order=["a", "b", "a", "b"],
            tasks_per_block=3, probe_tasks_per_domain=4,
        ),
        method=MethodSpec(
            "cold_router_guard", "greedy-utility", "shared", estimator="contextual",
            context_weight=0.5, prior_guard="reset-cold", prior_guard_tolerance=0.06,
            prior_guard_max_probes_per_domain=max_probes,
            prior_guard_reference="cold-router",
        ),
        condition=condition, seed=seed, top_k=2, budget=120,
        token_target=0.60, target_window=4, target_sustain=2,
    )


def test_prior_guard_rejects_unknown_reference():
    with pytest.raises(ValueError, match="Unsupported prior-guard reference"):
        run_continual_experiment(
            stream=_contextual_stream(seed=95),
            method=MethodSpec(
                "bad_reference", "greedy-utility", "shared", estimator="contextual",
                prior_guard="reset-cold", prior_guard_reference="unknown",
            ),
            condition="all-cold", seed=95, top_k=2, budget=120,
            token_target=0.60, target_window=4, target_sustain=2,
        )


def test_cold_router_reference_is_deterministic_and_exactly_charged():
    first = _cold_router_guard_run(condition="adversarial", seed=2)
    second = _cold_router_guard_run(condition="adversarial", seed=2)
    assert first["prior_guard_history"] == second["prior_guard_history"]
    assert first["run_fingerprint"] == second["run_fingerprint"]

    history = first["prior_guard_history"]
    summary = first["summary"]
    assert history["reference"] == "cold-router"
    assert history["validation_tokens"] == (
        history["learned_probe_tokens"] + history["reference_probe_tokens"]
    )
    assert summary["guard_validation_tokens"] == history["validation_tokens"]
    assert summary["prior_guard_reference_score"] == history["reference_mean"]
    assert summary["total_tokens"] == (
        summary["inference_tokens"] + summary["credit_update_tokens"]
        + summary["probe_tokens"] + summary["gate_validation_tokens"]
        + summary["guard_validation_tokens"]
    )


def test_cold_router_reference_resets_adversarial_prior():
    result = _cold_router_guard_run(condition="adversarial", seed=2)
    assert result["summary"]["prior_guard_triggered"]
    assert result["summary"]["prior_guard_action"] == "reset-cold"
    assert result["summary"]["prior_guard_reset_magnitude"] > 0.0


def test_cold_router_reference_retains_helpful_prior_on_development_seed():
    guarded = _cold_router_guard_run(condition="oracle", seed=2)
    unguarded = run_continual_experiment(
        stream=generate_contextual_synthetic_stream(
            seed=2, n_rules=20, domains=["a", "b"],
            block_order=["a", "b", "a", "b"],
            tasks_per_block=3, probe_tasks_per_domain=4,
        ),
        method=MethodSpec(
            "cold_router_guard", "greedy-utility", "shared", estimator="contextual",
            context_weight=0.5,
        ),
        condition="oracle", seed=2, top_k=2, budget=120,
        token_target=0.60, target_window=4, target_sustain=2,
    )
    assert not guarded["summary"]["prior_guard_triggered"]
    assert guarded["summary"]["prior_guard_action"] == "none"
    assert guarded["summary"]["prior_guard_reset_magnitude"] == 0.0
    assert np.isclose(guarded["summary"]["mean_reward"], unguarded["summary"]["mean_reward"])


def test_relevance_reference_default_is_backward_compatible():
    common = dict(
        stream=_contextual_stream(seed=97), condition="adversarial", seed=97,
        top_k=2, budget=120, token_target=0.60, target_window=4, target_sustain=2,
    )
    implicit = run_continual_experiment(
        method=MethodSpec(
            "compat_guard", "greedy-utility", "shared", estimator="contextual",
            prior_guard="reset-cold", prior_guard_max_probes_per_domain=2,
        ),
        **common,
    )
    explicit = run_continual_experiment(
        method=MethodSpec(
            "compat_guard", "greedy-utility", "shared", estimator="contextual",
            prior_guard="reset-cold", prior_guard_max_probes_per_domain=2,
            prior_guard_reference="relevance",
        ),
        **common,
    )
    assert implicit["prior_guard_history"] == explicit["prior_guard_history"]
    implicit_summary = {k: v for k, v in implicit["summary"].items() if k != "routing_ms_mean"}
    explicit_summary = {k: v for k, v in explicit["summary"].items() if k != "routing_ms_mean"}
    assert implicit_summary == explicit_summary
    assert implicit["run_fingerprint"] == explicit["run_fingerprint"]


def test_prior_guard_rejects_unknown_evaluation_mode():
    with pytest.raises(ValueError, match="Unsupported prior-guard evaluation"):
        run_continual_experiment(
            stream=_contextual_stream(seed=99),
            method=MethodSpec(
                "bad_evaluation", "greedy-utility", "shared", estimator="contextual",
                prior_guard="reset-cold", prior_guard_reference="cold-router",
                prior_guard_evaluation="unknown",
            ),
            condition="all-cold", seed=99, top_k=2, budget=120,
            token_target=0.60, target_window=4, target_sustain=2,
        )


def _rollout_guard_fixture(*, condition: str, evaluation: str, credit: str = "shared"):
    return run_continual_experiment(
        stream=generate_contextual_synthetic_stream(
            seed=29, n_rules=20, domains=["a", "b"],
            block_order=["a", "b", "a", "b"], tasks_per_block=3,
            probe_tasks_per_domain=8,
        ),
        method=MethodSpec(
            "rollout_guard", "greedy-utility", credit, estimator="contextual",
            context_weight=0.5, prior_guard="reset-cold", prior_guard_tolerance=0.06,
            prior_guard_max_probes_per_domain=8, prior_guard_reference="cold-router",
            prior_guard_evaluation=evaluation,
        ),
        condition=condition, seed=29, top_k=2, budget=120,
        token_target=0.60, target_window=4, target_sustain=2,
    )


def test_rollout_guard_can_retain_helpful_prior_rejected_by_frozen_probes():
    frozen = _rollout_guard_fixture(condition="oracle", evaluation="frozen")
    rollout = _rollout_guard_fixture(condition="oracle", evaluation="rollout")
    assert frozen["summary"]["prior_guard_triggered"]
    assert not rollout["summary"]["prior_guard_triggered"]
    assert rollout["prior_guard_history"]["evaluation"] == "rollout"
    assert rollout["summary"]["prior_guard_action"] == "none"


def test_rollout_guard_still_rejects_adversarial_prior():
    result = _rollout_guard_fixture(condition="adversarial", evaluation="rollout")
    assert result["summary"]["prior_guard_triggered"]
    assert result["summary"]["prior_guard_action"] == "reset-cold"


def test_rollout_guard_charges_credit_update_tokens_exactly():
    result = _rollout_guard_fixture(
        condition="adversarial", evaluation="rollout", credit="leave-one-out",
    )
    history = result["prior_guard_history"]
    summary = result["summary"]
    assert history["learned_update_tokens"] > 0
    assert history["reference_update_tokens"] > 0
    assert history["validation_tokens"] == (
        history["learned_probe_tokens"] + history["reference_probe_tokens"]
        + history["learned_update_tokens"] + history["reference_update_tokens"]
    )
    assert summary["guard_validation_tokens"] == history["validation_tokens"]
    assert summary["total_tokens"] == (
        summary["inference_tokens"] + summary["credit_update_tokens"]
        + summary["probe_tokens"] + summary["gate_validation_tokens"]
        + summary["guard_validation_tokens"]
    )

def test_rollout_guard_records_roundwise_confidence_tokens_and_recovery():
    result = run_continual_experiment(
        stream=generate_contextual_synthetic_stream(
            seed=29, n_rules=20, domains=["a", "b"],
            block_order=["a", "b", "a", "b"], tasks_per_block=3,
            probe_tasks_per_domain=4,
        ),
        method=MethodSpec(
            "trajectory_guard", "greedy-utility", "shared", estimator="contextual",
            context_weight=0.5, prior_guard="reset-cold", prior_guard_tolerance=0.06,
            prior_guard_max_probes_per_domain=4, prior_guard_reference="cold-router",
            prior_guard_evaluation="rollout", prior_guard_recovery_window=2,
            prior_guard_max_recovery_slope=0.0,
        ),
        condition="oracle", seed=29, top_k=2, budget=120,
        token_target=0.60, target_window=4, target_sustain=2,
    )
    history = result["prior_guard_history"]
    rounds = history["round_history"]
    assert len(rounds) == history["rounds_used"] == 4
    assert [row["round"] for row in rounds] == [1, 2, 3, 4]
    assert rounds[0]["recovery_slope"] is None
    assert rounds[1]["recovery_slope"] is not None
    assert rounds[-1]["margin"] == pytest.approx(history["margin"])
    assert rounds[-1]["confidence_lower"] == pytest.approx(history["confidence_lower"])
    assert rounds[-1]["confidence_upper"] == pytest.approx(history["confidence_upper"])
    assert rounds[-1]["validation_tokens"] == history["validation_tokens"]


def test_adaptive_rollout_horizon_retains_seed83_and_rejects_adversarial():
    common = dict(
        stream=generate_contextual_synthetic_stream(
            seed=83, n_rules=48, domains=["searchqa", "law", "health"],
            block_order=["searchqa", "law", "health", "searchqa", "law", "health"],
            tasks_per_block=25, probe_tasks_per_domain=8,
        ),
        method=MethodSpec(
            "adaptive_rollout", "greedy-utility", "shared", estimator="contextual",
            context_weight=0.5, prior_guard="reset-cold", prior_guard_tolerance=0.06,
            prior_guard_max_probes_per_domain=8, prior_guard_reference="cold-router",
            prior_guard_confidence_z=1.0, prior_guard_evaluation="rollout",
            prior_guard_sequential=True, prior_guard_min_samples=6,
            prior_guard_min_reset_rounds=2, prior_guard_min_harm_margin=0.10,
            prior_guard_recovery_window=2, prior_guard_max_recovery_slope=0.25,
        ),
        seed=83, top_k=3, budget=170, token_target=0.72,
        target_window=20, target_sustain=5, prior_strength=2.0,
    )
    helpful = run_continual_experiment(condition="oracle", **common)
    adversarial = run_continual_experiment(condition="adversarial", **common)
    assert not helpful["summary"]["prior_guard_triggered"]
    assert helpful["summary"]["prior_guard_rounds_used"] == 8
    assert helpful["prior_guard_history"]["round_history"][1]["recovery_slope"] > 0.0
    assert adversarial["summary"]["prior_guard_triggered"]
    assert adversarial["summary"]["prior_guard_rounds_used"] == 2
    assert adversarial["summary"]["prior_guard_stop_reason"] == "confident-harmful"


def test_prior_guard_requires_recovery_slope_threshold_when_window_enabled():
    with pytest.raises(ValueError, match="prior_guard_max_recovery_slope is required"):
        run_continual_experiment(
            stream=_contextual_stream(seed=101),
            method=MethodSpec(
                "missing_slope", "greedy-utility", "shared", estimator="contextual",
                prior_guard="reset-cold", prior_guard_recovery_window=2,
            ),
            condition="all-cold", seed=101, top_k=2, budget=120,
            token_target=0.60, target_window=4, target_sustain=2,
        )




def test_contextual_prior_identity_uses_domain_specific_truth():
    stream = generate_contextual_synthetic_stream(
        seed=131, n_rules=20, domains=["a", "b"],
        block_order=["a", "b", "a", "b"], tasks_per_block=3,
        probe_tasks_per_domain=4,
    )
    method = MethodSpec(
        "contextual_identity", "greedy-utility", "shared",
        estimator="contextual", context_weight=0.5,
    )
    state, global_prior, domain_priors = build_prior_identity_state(
        rules=stream.rules, domains=["a", "b"], method=method,
        condition="oracle", identity="contextual", seed=131, prior_strength=2.0,
    )
    expected = initialise_contextual_utilities(
        stream.rules, domains=["a", "b"], condition="oracle", seed=131,
    )
    assert isinstance(state, ContextualUtilityState)
    assert np.allclose(state.global_state.means, global_prior)
    for domain in ["a", "b"]:
        assert np.allclose(domain_priors[domain], expected[domain])
        assert np.allclose(state.domain_states[domain].means, expected[domain])
        assert not np.allclose(domain_priors[domain], global_prior)


def test_contextual_adversarial_prior_reverses_each_domain_ranking():
    stream = generate_contextual_synthetic_stream(
        seed=132, n_rules=20, domains=["a", "b"],
        block_order=["a", "b"], tasks_per_block=3,
        probe_tasks_per_domain=3,
    )
    oracle = initialise_contextual_utilities(
        stream.rules, domains=["a", "b"], condition="oracle", seed=132,
    )
    adversarial = initialise_contextual_utilities(
        stream.rules, domains=["a", "b"], condition="adversarial", seed=132,
    )
    for domain in ["a", "b"]:
        oracle_order = np.argsort(oracle[domain], kind="stable")
        assert np.allclose(
            adversarial[domain][oracle_order], np.sort(oracle[domain])[::-1]
        )


def test_prior_representativeness_diagnostic_is_deterministic_and_complete():
    stream = generate_contextual_synthetic_stream(
        seed=133, n_rules=20, domains=["a", "b"],
        block_order=["a", "b", "a", "b"], tasks_per_block=3,
        probe_tasks_per_domain=4,
    )
    method = MethodSpec(
        "frozen_guard", "greedy-utility", "shared", estimator="contextual",
        context_weight=0.5, prior_guard="reset-cold", prior_guard_tolerance=0.06,
        prior_guard_max_probes_per_domain=4, prior_guard_reference="cold-router",
        prior_guard_confidence_z=1.0, prior_guard_evaluation="rollout",
        prior_guard_sequential=True, prior_guard_min_samples=4,
        prior_guard_min_reset_rounds=2, prior_guard_min_harm_margin=0.1,
        prior_guard_recovery_window=2, prior_guard_max_recovery_slope=0.1,
    )
    kwargs = dict(
        stream=stream, method=method, condition="oracle", identity="contextual",
        seed=133, top_k=2, budget=120, prior_strength=2.0,
        prefix_probe_rounds=2, phase0_blocks=2,
    )
    first = evaluate_prior_representativeness(**kwargs)
    second = evaluate_prior_representativeness(**kwargs)
    assert first["diagnostic_fingerprint"] == second["diagnostic_fingerprint"]
    assert first["summary"] == second["summary"]
    assert first["prior_correlations"]["global"]["spearman"] == pytest.approx(1.0)
    assert all(
        values["spearman"] == pytest.approx(1.0)
        for values in first["prior_correlations"]["by_domain"].values()
    )
    assert first["static_prefix_probes"]["n"] == 4
    assert first["static_all_probes"]["n"] == 8
    assert first["static_phase0_stream"]["n"] == 6
    assert len(first["guard"]["round_history"]) == first["guard"]["rounds_used"]

def test_global_only_prior_identity_keeps_contextual_states_cold():
    stream = generate_contextual_synthetic_stream(
        seed=134, n_rules=20, domains=["a", "b"],
        block_order=["a", "b"], tasks_per_block=3,
        probe_tasks_per_domain=3,
    )
    method = MethodSpec(
        "global_only", "greedy-utility", "shared",
        estimator="contextual", prior_identity="global-only", context_weight=0.5,
    )
    state, global_prior, domain_priors = build_prior_identity_state(
        rules=stream.rules, domains=["a", "b"], method=method,
        condition="oracle", identity="global-only", seed=134, prior_strength=2.0,
    )
    assert isinstance(state, ContextualUtilityState)
    assert not np.allclose(global_prior, 0.5)
    assert np.allclose(state.global_state.means, global_prior)
    for domain in ["a", "b"]:
        assert np.allclose(domain_priors[domain], 0.5)
        assert np.allclose(state.domain_states[domain].means, 0.5)
    assert np.allclose(state.means_for("unseen"), 0.5 * global_prior + 0.25)
    assert np.allclose(state.domain_states["unseen"].prior_means, 0.5)


def test_selective_cold_escalates_acceptance_and_preserves_candidate_state():
    stream = generate_contextual_synthetic_stream(
        seed=133, n_rules=20, domains=["a", "b"],
        block_order=["a", "b", "a", "b"], tasks_per_block=3,
        probe_tasks_per_domain=4,
    )
    method = MethodSpec(
        "selective", "greedy-utility", "shared", estimator="contextual",
        prior_identity="global-only", context_weight=0.5,
        prior_guard="selective-cold", prior_guard_tolerance=0.06,
        prior_guard_max_probes_per_domain=4, prior_guard_reference="cold-router",
        prior_guard_confidence_z=0.0, prior_guard_evaluation="rollout",
        prior_guard_sequential=True, prior_guard_min_samples=2,
        prior_guard_min_accept_rounds=4, prior_guard_min_reset_rounds=2,
        prior_guard_min_harm_margin=0.1, prior_guard_recovery_window=2,
        prior_guard_max_recovery_slope=0.1,
    )
    common = dict(
        stream=stream, method=method, seed=133, top_k=2, budget=120,
        token_target=0.6, target_window=4, target_sustain=2, prior_strength=2.0,
    )
    helpful = run_continual_experiment(condition="oracle", **common)
    harmful = run_continual_experiment(condition="adversarial", **common)

    assert helpful["summary"]["prior_guard_decision"] == "acceptable"
    assert helpful["summary"]["prior_guard_action"] == "accept"
    assert helpful["summary"]["prior_guard_rounds_used"] == 4
    assert not helpful["summary"]["prior_guard_state_mutated"]

    assert harmful["summary"]["prior_guard_decision"] == "harmful"
    assert harmful["summary"]["prior_guard_action"] == "reject-fallback-cold"
    assert harmful["summary"]["prior_guard_rounds_used"] == 2
    assert not harmful["summary"]["prior_guard_state_mutated"]
    assert harmful["summary"]["prior_guard_reset_magnitude"] == 0.0
    assert all(
        np.allclose(values, 0.5)
        for values in harmful["initial_domain_utilities"].values()
    )

