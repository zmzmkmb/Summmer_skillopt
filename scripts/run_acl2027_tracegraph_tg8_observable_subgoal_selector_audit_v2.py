#!/usr/bin/env python3
"""Run synthetic zero-network audit cases for the TG8 selector v2 contract."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_acl2027_tracegraph_tg6_local_execution_runner_v1 import SkillIndex  # noqa: E402
from scripts.run_acl2027_tracegraph_tg8_observable_subgoal_selector_v2 import (  # noqa: E402
    select_condition,
    validate_selector_transition,
)

CONFIG = ROOT / "configs/acl2027/tracegraph_tg8_observable_subgoal_selector_v2.json"
OUTPUT_DIR = ROOT / "artifacts/acl2027_tracegraph_tg8_observable_subgoal_selector_audit_v2"
AUDIT = OUTPUT_DIR / "selector_audit.json"
MANIFEST = OUTPUT_DIR / "run_manifest.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture_index() -> SkillIndex:
    records = [
        ("goto-cabinet", "GotoLocation", ["cabinet"]),
        ("goto-countertop", "GotoLocation", ["countertop"]),
        ("goto-fridge", "GotoLocation", ["fridge"]),
        ("pickup-apple", "PickupObject", ["apple"]),
        ("pickup-banana", "PickupObject", ["banana"]),
        ("put-apple-fridge", "PutObject", ["apple", "fridge"]),
        ("put-banana-fridge", "PutObject", ["banana", "fridge"]),
        ("clean-apple-sink", "CleanObject", ["apple", "sinkbasin"]),
    ]
    return SkillIndex([
        {"skill_id": skill_id, "source_split": "train", "canonical_actions": [{"action": action, "args": args}]}
        for skill_id, action, args in records
    ])


def runtime(observation: str, history: list[str], actions: list[str]) -> dict[str, Any]:
    return {"observation": observation, "historical_actions": history, "admissible_actions": actions}


def run_case(name: str, check: Any) -> dict[str, Any]:
    try:
        details = check()
        return {"name": name, "passed": True, "details": details}
    except Exception as exc:  # noqa: BLE001
        return {"name": name, "passed": False, "error_type": type(exc).__name__, "error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    expected = {
        "execution_authorized": False,
        "readiness_allowed": False,
        "network_calls_allowed": False,
        "provider_calls_allowed": False,
        "model_calls_allowed": False,
        "api_calls_allowed": False,
        "paid_api_calls_allowed": False,
    }
    for key, value in expected.items():
        if config.get(key) != value:
            raise ValueError(f"{key} must be {value!r}")
    selector_path = ROOT / config["selector"]
    if sha256(selector_path) != config["selector_sha256"]:
        raise ValueError("selector hash mismatch")
    index = fixture_index()
    initial_obs = "You are in a room. Your task is to: put an apple in the fridge."
    initial_actions = ["go to cabinet 1", "go to countertop 1"]

    def realistic_chain() -> dict[str, Any]:
        first = select_condition(index, "observable_subgoal_greedy", runtime(initial_obs, [], initial_actions))
        second = select_condition(
            index,
            "observable_subgoal_greedy",
            runtime("You arrive at countertop 1. On the countertop 1, you see an apple 1.", [first["terminal_action_decision"]], ["take apple 1 from countertop 1", "go to cabinet 1"]),
            previous_ledger=first["subgoal_ledger"],
            previous_snapshots=[first["observable_snapshot_fingerprint"]],
        )
        assert second["newly_completed_subgoal_ids"] == ["search_source"]
        assert second["pending_subgoal_id"] == "pickup"
        return {"first_action": first["terminal_action_decision"], "second_action": second["terminal_action_decision"], "completed": second["newly_completed_subgoal_ids"]}

    def false_progress() -> dict[str, Any]:
        first = select_condition(index, "observable_subgoal_greedy", runtime(initial_obs, [], ["go to countertop 1"]))
        repeated = select_condition(
            index,
            "observable_subgoal_greedy",
            runtime(initial_obs, ["go to countertop 1"], ["go to countertop 1"]),
            previous_ledger=first["subgoal_ledger"],
            previous_snapshots=[first["observable_snapshot_fingerprint"]],
        )
        assert repeated["observable_delta_since_previous"] is False
        assert repeated["progress_event"] is False
        assert repeated["false_progress_event"] is True
        return {"false_progress": repeated["false_progress_event"]}

    def wrong_object_put() -> dict[str, Any]:
        first = select_condition(index, "observable_subgoal_greedy", runtime(initial_obs, [], ["go to countertop 1"]))
        ledger = copy.deepcopy(first["subgoal_ledger"])
        ledger["completed_subgoal_ids"] = ["search_source", "pickup"]
        ledger["unresolved_subgoal_ids"] = ["search_destination", "put"]
        ledger["pending_subgoal_id"] = "search_destination"
        ledger["last_selected_action"] = "take apple 1 from countertop 1"
        ledger["last_selected_subgoal_id"] = "pickup"
        row = select_condition(
            index,
            "observable_subgoal_greedy",
            runtime("You arrive at fridge 1. A banana is visible.", ["take apple 1 from countertop 1"], ["put banana 1 in fridge 1", "go to cabinet 1"]),
            previous_ledger=ledger,
            previous_snapshots=[first["observable_snapshot_fingerprint"]],
        )
        assert "search_destination" not in row["newly_completed_subgoal_ids"]
        assert row["pending_subgoal_id"] == "search_destination"
        return {"pending": row["pending_subgoal_id"]}

    def tamper_rejection() -> dict[str, Any]:
        row = select_condition(index, "lexical_greedy", runtime(initial_obs, [], ["go to apple"]))
        tampered = copy.deepcopy(row)
        tampered["observable_snapshot_fingerprint"] = "0" * 64
        assert validate_selector_transition(tampered) == (False, "observable snapshot fingerprint mismatch")
        tampered = copy.deepcopy(row)
        tampered["planner_state"] = {"hidden": True}
        assert validate_selector_transition(tampered) == (False, "forbidden runtime field present")
        return {"tamper_cases": 2}

    def factor_separation() -> dict[str, Any]:
        actions = ["go to fridge", "go to apple", "take apple from countertop"]
        first = select_condition(index, "lexical_greedy", runtime(initial_obs, [], actions))
        history = [first["terminal_action_decision"]]
        lexical = select_condition(
            index,
            "lexical_greedy",
            runtime(initial_obs, history, actions),
            previous_ledger=first["subgoal_ledger"],
            previous_snapshots=[first["observable_snapshot_fingerprint"]],
        )
        anti = select_condition(
            index,
            "lexical_anti_cycle",
            runtime(initial_obs, history, actions),
            previous_ledger=first["subgoal_ledger"],
            previous_snapshots=[first["observable_snapshot_fingerprint"]],
        )
        structured = select_condition(
            index,
            "observable_subgoal_greedy",
            runtime(initial_obs, history, actions),
            previous_ledger=first["subgoal_ledger"],
            previous_snapshots=[first["observable_snapshot_fingerprint"]],
        )
        assert lexical["terminal_action_decision"] != anti["terminal_action_decision"]
        assert structured["representation_score"]["representation"] == "observable_subgoal"
        return {"lexical": lexical["terminal_action_decision"], "anti_cycle": anti["terminal_action_decision"], "structured": structured["terminal_action_decision"]}

    cases = [
        run_case("realistic_search_pickup_chain", realistic_chain),
        run_case("target_action_without_delta", false_progress),
        run_case("wrong_object_put_rejected", wrong_object_put),
        run_case("tamper_and_hidden_field_rejected", tamper_rejection),
        run_case("representation_controller_factor_separation", factor_separation),
    ]
    result = {
        "schema_version": 2,
        "phase_id": "TG8-tracegraph-observable-subgoal-selector-v2",
        "status": "passed" if all(case["passed"] for case in cases) else "failed",
        "cases": cases,
        "case_count": len(cases),
        "passed_case_count": sum(case["passed"] for case in cases),
        "execution_authorized": False,
        "readiness_allowed": False,
        "episodes_run": 0,
        "actions_taken": 0,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "api_calls": 0,
        "paid_api_calls": 0,
        "runtime_allowed_inputs": config["runtime_allowed_inputs"],
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if AUDIT.exists() or MANIFEST.exists():
        raise FileExistsError("selector audit artifacts already exist")
    AUDIT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": 2,
        "phase_id": result["phase_id"],
        "status": result["status"],
        "audit": str(AUDIT.relative_to(ROOT)).replace("\\", "/"),
        "audit_sha256": sha256(AUDIT),
        "case_count": len(cases),
        "passed_case_count": result["passed_case_count"],
        "episodes_run": 0,
        "actions_taken": 0,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "api_calls": 0,
        "paid_api_calls": 0,
        "execution_authorized": False,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "cases": len(cases), "passed": result["passed_case_count"], "audit_sha256": sha256(AUDIT)}, ensure_ascii=False))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
