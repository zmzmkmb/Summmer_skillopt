import copy

import pytest

from scripts import audit_acl2027_tg8_manual_terminal_v1 as audit


@pytest.fixture
def example():
    config = audit.frozen.read_json(audit.CONFIG)
    schedule, tasks = audit.frozen.load_schedule(config)
    row = audit.frozen.read_json(audit.ROOT / config["run_directory"] / "rows/0000.json")
    return row, schedule[0], tasks[row["task_identity"]]


def test_saved_row_and_full_selector(example):
    row, planned, task = example
    config = audit.frozen.read_json(audit.CONFIG)
    index = audit.frozen.selector.base.load_skill_index(audit.ROOT / config["skillbank"])
    assert audit.audit_row(row, planned, task, index) == row["metrics"]


def test_cached_index_preserves_full_selector_results(example):
    row, planned, task = example
    config = audit.frozen.read_json(audit.CONFIG)
    source = audit.frozen.selector.base.load_skill_index(audit.ROOT / config["skillbank"])
    cached = audit.CachedSkillIndex(source)
    assert audit.audit_row(row, planned, task, cached) == row["metrics"]
    assert cached.calls > len(cached.cache)
    for command, matches in cached.cache.items():
        assert list(matches) == source.matching_skill_ids(command)


def test_cache_does_not_share_mutable_results():
    class Source:
        calls = 0

        def matching_skill_ids(self, command):
            self.calls += 1
            return [command]

    source = Source()
    cached = audit.CachedSkillIndex(source)
    cached.matching_skill_ids("look").clear()
    assert cached.matching_skill_ids("look") == ["look"]
    assert source.calls == 1


@pytest.mark.parametrize("mutation,match", [
    ("history", "complete action history"),
    ("runtime", "runtime fields"),
    ("metric", "episode metric mismatch"),
    ("identity", "schedule identity"),
    ("success", "success mismatch"),
    ("ledger", "ledger fingerprint"),
])
def test_rejects_tampered_saved_artifacts(example, mutation, match):
    original, planned, task = example
    row = copy.deepcopy(original)
    if mutation == "history":
        row["transitions"][1]["runtime_inputs"]["historical_actions"] = []
    elif mutation == "runtime":
        row["transitions"][0]["runtime_inputs"]["task_description"] = "forbidden"
    elif mutation == "metric":
        row["metrics"]["unique_snapshot_count"] = -1
    elif mutation == "identity":
        row["seed"] = -1
    elif mutation == "success":
        row["success"] = not row["success"]
    elif mutation == "ledger":
        row["transitions"][0]["subgoal_ledger"]["pending_subgoal_id"] = "tampered"
    with pytest.raises(ValueError, match=match):
        audit.audit_row(row, planned, task)
