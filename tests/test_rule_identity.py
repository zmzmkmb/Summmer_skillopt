from __future__ import annotations

import json
from pathlib import Path

from skillopt.moar.tracker import UtilityTracker, _hash_rule_text
from skillopt.rag_rule_selector import RuleMemory
from skillopt.rule_identity import normalize_rule_text, stable_rule_id


def _skill(rule_order: tuple[str, ...]) -> str:
    sections = ["## Output Format\nReturn one concise answer."]
    sections.extend(f"## {name}\nBody for {name}." for name in rule_order)
    return "\n\n".join(sections)


def test_rule_id_is_stable_under_reordering_and_line_endings():
    first = RuleMemory(_skill(("Alpha", "Beta")))
    second = RuleMemory(_skill(("Beta", "Alpha")).replace("\n", "\r\n"))

    first_ids = {rule.heading: rule.rule_id for rule in first.dynamic_rules}
    second_ids = {rule.heading: rule.rule_id for rule in second.dynamic_rules}

    assert first_ids == second_ids
    assert first.rule_set_fingerprint == second.rule_set_fingerprint
    assert normalize_rule_text("  A  \r\nB \r\n") == "  A\nB"


def test_rule_ids_for_indices_replaces_process_local_positions():
    memory = RuleMemory(_skill(("Alpha", "Beta")))
    assert memory.rule_ids_for_indices([1, -1, 99, 0]) == [
        memory.dynamic_rules[1].rule_id,
        memory.dynamic_rules[0].rule_id,
    ]


def test_tracker_migrates_positional_rule_ids(tmp_path: Path):
    text = "## Alpha\nBody."
    key = _hash_rule_text(text)
    path = tmp_path / "utility.json"
    path.write_text(json.dumps({
        "rules": {
            key: {
                "rule_id": "D00",
                "text_hash": key,
                "selected": 3,
                "correct": 2,
            }
        }
    }), encoding="utf-8")

    tracker = UtilityTracker(str(path))
    tracker.register_rules([text])
    tracker.save()
    saved = json.loads(path.read_text(encoding="utf-8"))

    assert saved["schema_version"] == 2
    assert saved["rules"][key]["rule_id"] == stable_rule_id(text)
    assert saved["rules"][key]["selected"] == 3
