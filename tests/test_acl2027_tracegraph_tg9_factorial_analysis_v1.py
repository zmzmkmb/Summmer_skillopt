from scripts.analyze_acl2027_tracegraph_tg9_factorial_v1 import (
    CONDITIONS,
    analyze,
    effects,
    exact_sign_flip,
    holm,
)


def synthetic_result():
    rows = []
    for task in range(15):
        vector = [0, 1, 0, 1] if task < 12 else [0, 0, 0, 0]
        for condition, success in zip(CONDITIONS, vector):
            for replicate in range(3):
                rows.append({
                    "task_identity": f"task-{task}",
                    "template_key": f"template-{task % 11}",
                    "split": "valid_seen" if task < 10 else "valid_unseen",
                    "condition": condition,
                    "replicate_index": replicate,
                    "success": bool(success),
                    "hard_invariant_violation": None,
                    "transitions": [{"selected": condition, "success": success}],
                })
    return {"rows": rows, "hard_invariant_violation": None}


def test_effect_definitions_match_preregistered_formulas():
    assert effects([0, 1, 0, 1]) == (1.0, 0.0, 0)
    assert effects([0, 0, 0, 1]) == (0.5, 0.5, 1)


def test_analysis_uses_tasks_not_rows_and_reports_both_clusterings():
    result = analyze(synthetic_result(), resamples=200)
    assert result["task_count"] == 15
    assert result["row_count"] == 180
    assert result["task_cluster_results"]["object_binding"]["estimate"] == 0.8
    assert result["template_cluster_sensitivity"]["object_binding"]["cluster_count"] == 11
    assert result["primary_endpoint"] == "completion_by_step_50"


def test_exact_tests_and_holm_are_bounded_and_monotone():
    assert exact_sign_flip([1] * 15) == 2 / (2**15)
    adjusted = holm({"a": 0.01, "b": 0.03, "c": 0.2})
    assert adjusted["a"] <= adjusted["b"] <= adjusted["c"] <= 1
