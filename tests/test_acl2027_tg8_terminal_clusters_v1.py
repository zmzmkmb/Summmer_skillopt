import pytest

from scripts.analyze_acl2027_tg8_terminal_clusters_v1 import bootstrap, contrasts, percentile


def test_factorial_contrasts():
    assert contrasts([0, 0, 0, 1]) == (0.5, 0.5, 1)
    assert contrasts([0, 0, 1, 1]) == (1, 0, 0)
    assert contrasts([0, 1, 0, 1]) == (0, 1, 0)


def test_percentile_interpolation():
    assert percentile([0, 10], 0.25) == 2.5
    assert percentile([3, 1, 2], 0.5) == 2


def test_bootstrap_is_paired_and_reproducible():
    vectors = [[0, 0], [1, -1], [2, -2]]
    first = bootstrap(vectors, 200, 42)
    assert first == bootstrap(vectors, 200, 42)
    assert first[0]["estimate"] == 1
    assert first[1]["estimate"] == -1
    assert first[0]["ci95_percentile"][0] == pytest.approx(-first[1]["ci95_percentile"][1])


def test_identical_task_vectors_have_degenerate_interval():
    result = bootstrap([[0.25, 0.5]] * 30, 100)
    assert result[0] == {"estimate": 0.25, "ci95_percentile": [0.25, 0.25]}
