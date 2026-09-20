#!/usr/bin/env python3
"""Zero-network Phase 2 formal-history recovery preflight v12."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable
from scripts.materialize_acl2027_phase2_candidates_recovery_v12 import build_recovery_candidate_artifact
from scripts.prepare_acl2027_phase2_payload_and_freeze_v2 import TYPES, make_payload, prior_exclusions
from scripts.run_acl2027_phase2_formal_history_v11 import SYSTEM

VERSION = 12
FAMILIES = ("fact_retrieval", "attribute_comparison", "bridge_attribute_comparison", "entity_bridge", "relation_inference")
CONFIG = ROOT / "configs/acl2027/phase2_formal_history_recovery_preflight_v12.json"
ARTIFACT = ROOT / "artifacts/acl2027_phase2_formal_history_recovery_preflight_v12"
RECOVERY_SCHEDULE = ARTIFACT / "recovery_schedule.json"
COMBINED_SCHEDULE = ARTIFACT / "combined_formal_history_schedule.json"
COMBINED_GOLD = ARTIFACT / "combined_formal_history_gold.json"
REPLACEMENT_AUDIT = ARTIFACT / "replacement_selection_audit.json"
MANIFEST = ARTIFACT / "run_manifest.json"
REPORT = ROOT / "paper/acl2027/results/phase2_formal_history_recovery_preflight_v12.md"
V11_ARTIFACT = ROOT / "artifacts/acl2027_phase2_formal_history_v11"
V11_SCHEDULE = V11_ARTIFACT / "formal_history_schedule.json"
V11_LEDGER = V11_ARTIFACT / "ledger.json"
V11_CLOSURE = V11_ARTIFACT / "authorization_closure.json"
V11_GOLD = ROOT / "data/searchqa_phase2_verified/formal_history.json"
SOURCE_2WIKI = ROOT / "data/2wikimultihopqa_verified/source/dev.json"
PARTITION_AUDIT = ROOT / "artifacts/acl2027_phase2_expansion_freeze_v2/partition_audit.json"
MATERIALIZER = ROOT / "scripts/materialize_acl2027_phase2_candidates_recovery_v12.py"
VERIFIER = ROOT / "scripts/acl2027_phase2_response_verifier_v3.py"
SCHEMA = ROOT / "configs/acl2027/phase2_candidate_materialization_schema_v3.json"
POOL_BUILDER = ROOT / "scripts/prepare_acl2027_phase2_payload_and_freeze_v2.py"
TEST_SOURCE = ROOT / "tests/test_acl2027_phase2_formal_history_recovery_v12.py"
LIVE_RUNNER = ROOT / "scripts/run_acl2027_phase2_formal_history_recovery_live_v12.py"
LIVE_TEST_SOURCE = ROOT / "tests/test_acl2027_phase2_formal_history_recovery_live_v12.py"


class PreflightError(RuntimeError):
    pass


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def replacement_key(task_id: str) -> str:
    return hashlib.sha256(f"phase2-v12:replacement:attribute_comparison:{task_id}".encode()).hexdigest()


def select_replacement() -> tuple[dict[str, Any], dict[str, Any]]:
    partition = load(PARTITION_AUDIT)
    allocated = {str(task_id) for ids in partition["ordered_ids"].values() for task_id in ids}
    excluded = prior_exclusions()["2WikiMultiHopQA"] | allocated
    terminal_id = str(load(V11_LEDGER)[-1]["task_id"])
    candidates = []
    for row in load(SOURCE_2WIKI):
        task_id = str(row["_id"])
        family = TYPES.get(str(row.get("type")))
        if family == "attribute_comparison" and task_id not in excluded and task_id != terminal_id:
            payload = make_payload(row, "2WikiMultiHopQA", family, "dev")
            candidates.append((replacement_key(task_id), task_id, payload))
    if not candidates:
        raise PreflightError("no unused attribute-comparison replacement")
    selector_hash, task_id, payload = min(candidates)
    audit = {
        "schema_version": VERSION,
        "status": "replacement-selected",
        "selector": "min SHA256(phase2-v12:replacement:attribute_comparison:<task_id>)",
        "selector_hash": selector_hash,
        "candidate_pool_size": len(candidates),
        "replacement_task_id": task_id,
        "replacement_payload_hash": stable(payload),
        "terminal_spent_task_id": terminal_id,
        "excluded_existing_phase2_ids": len(allocated),
        "probe_or_held_out_reused": False,
        "development_output_reused": False,
        "network_calls": 0,
        "provider_calls": 0,
        "paid_api_calls": 0,
    }
    return payload, audit


def replacement_row(payload: dict[str, Any], terminal_template: dict[str, Any]) -> dict[str, Any]:
    body = deepcopy(terminal_template["canonical_request_body"])
    body.update({
        "task_id": payload["task_id"], "task_family": payload["task_family"], "task_type": payload["task_type"],
        "skill_family": payload["skill_family"], "typed_scope": payload["skill_family"],
        "payload_hash": stable(payload), "prompt_template_version": "phase2-prompt-v12-exact-json-recovery",
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": payload["question"] + "\n\nContext:\n" + json.dumps(payload["context"], ensure_ascii=True)}],
        "response_format": {"type": "json_object"},
    })
    return {
        **{key: terminal_template[key] for key in terminal_template if key not in {"canonical_request_body", "logical_call_id", "request_hash", "task_id", "task_family", "task_type", "skill_family", "typed_scope", "payload_hash", "prompt_template_version", "sequence"}},
        "logical_call_id": f"phase2-v12:formal_history:attribute_comparison:{payload['task_id']}:cold",
        "request_hash": stable(body), "task_id": payload["task_id"], "task_family": payload["task_family"],
        "task_type": payload["task_type"], "skill_family": payload["skill_family"], "typed_scope": payload["skill_family"],
        "payload_hash": stable(payload), "prompt_template_version": body["prompt_template_version"],
        "canonical_request_body": body, "source_stage": "v12_replacement",
    }


def build_documents() -> dict[str, Any]:
    v11_rows = load(V11_SCHEDULE)["schedule"]
    v11_ledger = load(V11_LEDGER)
    if len(v11_rows) != 160 or len(v11_ledger) != 33 or sum(r.get("status") == "completed" for r in v11_ledger) != 32 or not v11_ledger[-1].get("terminal"):
        raise PreflightError("v11 terminal prefix binding drift")
    payload, selection = select_replacement()
    recovery = [replacement_row(payload, v11_rows[32])]
    for original in v11_rows[33:]:
        row = deepcopy(original)
        body = deepcopy(row["canonical_request_body"])
        body["messages"][0]["content"] = SYSTEM
        body["prompt_template_version"] = "phase2-prompt-v12-exact-json-recovery"
        body["response_format"] = {"type": "json_object"}
        row.update(logical_call_id=f"phase2-v12:formal_history:{row['skill_family']}:{row['task_id']}:cold", request_hash=stable(body), canonical_request_body=body, prompt_template_version=body["prompt_template_version"], source_stage="v12_unattempted_v11")
        recovery.append(row)
    for sequence, row in enumerate(recovery, 1):
        row["sequence"] = sequence
    preserved = []
    for sequence, row in enumerate(v11_rows[:32], 1):
        item = deepcopy(row); item["combined_sequence"] = sequence; item["source_stage"] = "v11_preserved_completed"; preserved.append(item)
    combined = preserved + [{**deepcopy(row), "combined_sequence": index + 33} for index, row in enumerate(recovery)]
    if len(recovery) != 128 or len(combined) != 160:
        raise PreflightError("v12 call arithmetic drift")
    if len({row["logical_call_id"] for row in combined}) != 160 or len({row["task_id"] for row in combined}) != 160 or len({row["request_hash"] for row in recovery}) != 128:
        raise PreflightError("v12 identity uniqueness drift")
    counts = {family: sum(row["skill_family"] == family for row in combined) for family in FAMILIES}
    if counts != {family: 32 for family in FAMILIES}:
        raise PreflightError("v12 combined family allocation drift")
    old_gold = {row["task_id"]: row for row in load(V11_GOLD)}
    combined_gold = [old_gold[row["task_id"]] if row["task_id"] in old_gold else payload for row in combined]
    return {"recovery": recovery, "combined": combined, "gold": combined_gold, "selection": selection, "counts": counts}


def config_document(documents: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": VERSION,
        "experiment": "acl2027_phase2_formal_history_recovery_preflight_v12",
        "status": "preflight_only_closed",
        "execution": {"network_calls_allowed": False, "provider_calls_allowed": False, "paid_api_allowed": False, "qwen_authorization_open": False, "formal_scaling_allowed": False},
        "recovery_contract": {
            "preserved_v11_completed_rows": 32, "terminal_spent_rows": 1, "terminal_spent_task_id": documents["selection"]["terminal_spent_task_id"],
            "terminal_request_must_not_be_retried": True, "new_logical_calls": 128, "replacement_calls": 1,
            "unattempted_v11_calls_reissued_with_new_request_hashes": 127, "combined_formal_history_rows": 160,
            "calls_per_family": 32, "target_verified_supports_per_family": 8,
        },
        "model_route": {"model_id": "qwen3.7-plus", "temperature": 0, "enable_thinking": False, "response_format": {"type": "json_object"}, "request_interval_seconds": 1.0, "retries": 0, "max_tokens_present": False, "endpoint": "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"},
        "cost_control": {"input_cny_per_million": 2.0, "output_cny_per_million": 8.0, "new_stage_ceiling_cny": 1.64, "v11_known_cost_lower_bound_cny": 0.075602, "v11_terminal_cost_unknown": True, "combined_exact_cost_claim_forbidden": True},
        "coverage_gate": {"minimum_per_family": 8, "schema_path": "configs/acl2027/phase2_candidate_materialization_schema_v3.json"},
        "trusted_evaluation": {"combined_gold_path": "artifacts/acl2027_phase2_formal_history_recovery_preflight_v12/combined_formal_history_gold.json", "combined_gold_sha256": sha256_file(COMBINED_GOLD), "verifier_source_sha256": sha256_file(VERIFIER), "materializer_source_sha256": sha256_file(MATERIALIZER), "verifier_config_sha256": sha256_file(SCHEMA)},
        "bindings": {"v11_schedule_sha256": sha256_file(V11_SCHEDULE), "v11_ledger_sha256": sha256_file(V11_LEDGER), "v11_closure_sha256": sha256_file(V11_CLOSURE), "source_2wiki_sha256": sha256_file(SOURCE_2WIKI), "partition_audit_sha256": sha256_file(PARTITION_AUDIT), "recovery_schedule_sha256": sha256_file(RECOVERY_SCHEDULE), "combined_schedule_sha256": sha256_file(COMBINED_SCHEDULE), "replacement_audit_sha256": sha256_file(REPLACEMENT_AUDIT), "runner_source_sha256": sha256_file(Path(__file__).resolve()), "test_source_sha256": sha256_file(TEST_SOURCE), "live_runner_source_sha256": sha256_file(LIVE_RUNNER), "live_test_source_sha256": sha256_file(LIVE_TEST_SOURCE), "pool_builder_source_sha256": sha256_file(POOL_BUILDER)},
        "forbidden_stages": ["probe", "held_out", "formal_scaling"],
        "counters": {"network_calls": 0, "provider_calls": 0, "model_calls": 0, "paid_api_calls": 0},
    }


def prepare() -> dict[str, Any]:
    documents = build_documents()
    write(RECOVERY_SCHEDULE, {"schema_version": VERSION, "schedule": documents["recovery"]})
    write(COMBINED_SCHEDULE, {"schema_version": VERSION, "schedule": documents["combined"]})
    write(COMBINED_GOLD, documents["gold"])
    write(REPLACEMENT_AUDIT, documents["selection"])
    write(CONFIG, config_document(documents))
    manifest = {
        "schema_version": VERSION, "status": "preflight-passed-authorization-closed", "request_count": 128,
        "combined_history_rows": 160, "family_counts": documents["counts"], "replacement_task_id": documents["selection"]["replacement_task_id"],
        "config_sha256": sha256_file(CONFIG), "recovery_schedule_sha256": sha256_file(RECOVERY_SCHEDULE),
        "combined_schedule_sha256": sha256_file(COMBINED_SCHEDULE), "combined_gold_sha256": sha256_file(COMBINED_GOLD),
        "replacement_audit_sha256": sha256_file(REPLACEMENT_AUDIT), "counters": {"network_calls": 0, "provider_calls": 0, "model_calls": 0, "paid_api_calls": 0},
    }
    manifest["aggregate_fingerprint"] = stable({key: value for key, value in manifest.items() if key != "aggregate_fingerprint"})
    write(MANIFEST, manifest)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("# Phase 2 Formal History Recovery Preflight v12\n\nZero-network preflight generated a 128-call recovery schedule and kept authorization closed.\n", encoding="utf-8")
    return manifest


def validate() -> dict[str, Any]:
    expected = build_documents()
    if load(RECOVERY_SCHEDULE) != {"schema_version": VERSION, "schedule": expected["recovery"]}:
        raise PreflightError("recovery schedule drift")
    if load(COMBINED_SCHEDULE) != {"schema_version": VERSION, "schedule": expected["combined"]} or load(COMBINED_GOLD) != expected["gold"] or load(REPLACEMENT_AUDIT) != expected["selection"]:
        raise PreflightError("combined recovery artifact drift")
    if load(CONFIG) != config_document(expected):
        raise PreflightError("v12 config binding drift")
    manifest = load(MANIFEST)
    if manifest.get("aggregate_fingerprint") != stable({key: value for key, value in manifest.items() if key != "aggregate_fingerprint"}):
        raise PreflightError("v12 aggregate fingerprint drift")
    if any(load(CONFIG)["execution"].values()) or any(load(CONFIG)["counters"].values()):
        raise PreflightError("v12 authorization must remain closed")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "validate"))
    args = parser.parse_args()
    result = prepare() if args.command == "prepare" else validate()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
