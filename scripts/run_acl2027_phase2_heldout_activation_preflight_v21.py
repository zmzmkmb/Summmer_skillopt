#!/usr/bin/env python3
"""Build and validate the zero-network Phase 2 v21 held-out activation preflight."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_integrity_v4 import verify_integrity
from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable

CONFIG = ROOT / "configs/acl2027/phase2_heldout_activation_preflight_v21.json"
V4_CONFIG = ROOT / "configs/acl2027/phase2_staged_live_runner_preflight_v4.json"
V4_MANIFEST = ROOT / "artifacts/acl2027_phase2_staged_live_runner_preflight_v4/run_manifest.json"
V17_MANIFEST = ROOT / "artifacts/acl2027_phase2_probe_identifiable_schedule_preflight_v17/run_manifest.json"
V17_SCHEDULE = ROOT / "artifacts/acl2027_phase2_probe_identifiable_schedule_preflight_v17/probe_schedule.json"
V17_PRIORS = ROOT / "artifacts/acl2027_phase2_probe_identifiable_schedule_preflight_v17/prior_bundles.json"
V19_MANIFEST = ROOT / "artifacts/acl2027_phase2_probe_recovery_preflight_v19/run_manifest.json"
V19_SCHEDULE = ROOT / "artifacts/acl2027_phase2_probe_recovery_preflight_v19/probe_recovery_schedule.json"
V20_AUDIT = ROOT / "artifacts/acl2027_phase2_probe_recovery_live_v20/probe_audit.json"
V20_RUN_AUDIT = ROOT / "artifacts/acl2027_phase2_probe_recovery_live_v20/run_audit.json"
V20_LEDGER = ROOT / "artifacts/acl2027_phase2_probe_recovery_live_v20/ledger.json"
V20_CLOSURE = ROOT / "artifacts/acl2027_phase2_probe_recovery_live_v20/authorization_closure.json"
V20_REGISTRY = ROOT / "artifacts/acl2027_phase2_probe_recovery_live_v20/authorization_registry.json"
V20_ZERO_PREFLIGHT = ROOT / "artifacts/acl2027_phase2_probe_recovery_live_v20/zero_network_preflight.json"
V20_AUTH_CLOSED = ROOT / "configs/acl2027/phase2_probe_recovery_live_authorization_closed_v20.json"
HELD_OUT = ROOT / "data/searchqa_phase2_verified/held_out.json"
HISTORY_SCHEDULE = ROOT / "artifacts/acl2027_phase2_formal_history_recovery_preflight_v12/combined_formal_history_schedule.json"
ARTIFACT = ROOT / "artifacts/acl2027_phase2_heldout_activation_preflight_v21"
TEST = ROOT / "tests/test_acl2027_phase2_heldout_activation_preflight_v21.py"
FAMILIES = ("fact_retrieval", "attribute_comparison", "bridge_attribute_comparison", "entity_bridge", "relation_inference")
CONDITIONS = ("cold", "copied_global", "global_only", "contextual_typed_prior")
SYSTEM = ('Answer the question from the supplied context and optional prior bundle. Return exactly one JSON object and no other text, markdown, or explanation. The object must contain exactly one key named answer whose value is a non-empty short string. Required shape: {"answer":"<short answer>"}.')


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def render(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n"


def rendered_sha256(value: Any) -> str:
    return hashlib.sha256(render(value).encode("utf-8")).hexdigest()


def condition_prior(condition: str, family: str, bundles: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if condition == "cold":
        return "candidate:none:v21", {"slot": "none", "source_scope": "none", "examples": []}
    if condition == "global_only":
        return bundles["global"]["candidate_id"], {"slot": "global", "source_scope": "global", "examples": bundles["global"]["examples"]}
    if condition == "copied_global":
        return f"candidate:copied-global:{family}:v21", {"slot": f"family:{family}", "source_scope": "global_copied", "examples": bundles["global"]["examples"]}
    typed = bundles["typed"][family]
    return typed["candidate_id"], {"slot": f"family:{family}", "source_scope": typed["source_scope"], "examples": typed["examples"]}


def held_out_tasks() -> list[dict[str, Any]]:
    rows = load(HELD_OUT)
    if len(rows) != 80 or len({row["task_id"] for row in rows}) != 80:
        raise RuntimeError("held-out payload must contain exactly 80 unique tasks")
    counts = {family: sum(row.get("skill_family") == family for row in rows) for family in FAMILIES}
    if counts != {family: 16 for family in FAMILIES}:
        raise RuntimeError(f"held-out family counts drift: {counts}")
    return rows


def build_schedule() -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    bundles = load(V17_PRIORS)
    rows: list[dict[str, Any]] = []
    for index, task in enumerate(held_out_tasks(), 1):
        family = task["skill_family"]
        payload_hash = stable(task)
        for condition in CONDITIONS:
            candidate_id, prior = condition_prior(condition, family, bundles)
            prior_text = json.dumps(prior, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            user = "Prior bundle:\n" + prior_text + "\n\nQuestion:\n" + task["question"] + "\n\nContext:\n" + json.dumps(task["context"], ensure_ascii=True)
            body = {
                "model_id": "qwen3.7-plus", "temperature": 0, "enable_thinking": False,
                "response_format": {"type": "json_object"}, "phase": "2", "stage": "Stage 6",
                "partition": "held_out", "task_family": task["task_family"], "task_type": task["task_type"],
                "skill_family": family, "task_id": task["task_id"], "payload_hash": payload_hash,
                "condition": condition, "candidate_id": candidate_id, "candidate_version": "phase2-v21",
                "typed_scope": family, "prompt_template_version": "phase2-heldout-identifiable-json-v21",
                "prior_payload_sha256": stable(prior), "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
            }
            rows.append({
                "schema_version": 21, "sequence": (index - 1) * 4 + len([r for r in rows if r["task_id"] == task["task_id"]]) + 1,
                "staged_execution_index": len(rows) + 1,
                "logical_call_id": f"phase2-v21:held_out:{family}:{task['task_id']}:{condition}",
                "request_hash": stable(body), "partition": "held_out", "stage": "Stage 6", "task_id": task["task_id"],
                "task_family": task["task_family"], "task_type": task["task_type"], "skill_family": family,
                "typed_scope": family, "payload_hash": payload_hash, "condition": condition, "candidate_id": candidate_id,
                "candidate_version": "phase2-v21", "prompt_template_version": "phase2-heldout-identifiable-json-v21",
                "prior_payload_sha256": body["prior_payload_sha256"],
                "canonical_request_body": body,
                "provenance": {"source_dataset": "SearchQA", "source_record_id": task["task_id"], "payload_source": task["source_split"], "gold_is_not_request": True, "held_out_gold_not_in_prior": True, "network_calls": 0, "provider_calls": 0, "paid_api_calls": 0},
                "expected_accounting": {"retries": 0, "max_tokens_present": False, "usage_required": True},
            })
    return rows, bundles, held_out_tasks()


def source_bindings() -> dict[str, str]:
    return {
        "v4_manifest_sha256": sha256_file(V4_MANIFEST), "v17_manifest_sha256": sha256_file(V17_MANIFEST),
        "v17_schedule_sha256": sha256_file(V17_SCHEDULE), "v17_prior_bundles_sha256": sha256_file(V17_PRIORS),
        "v19_manifest_sha256": sha256_file(V19_MANIFEST), "v20_probe_audit_sha256": sha256_file(V20_AUDIT),
        "v20_run_audit_sha256": sha256_file(V20_RUN_AUDIT), "v20_closure_sha256": sha256_file(V20_CLOSURE),
        "v19_schedule_sha256": sha256_file(V19_SCHEDULE), "v20_ledger_sha256": sha256_file(V20_LEDGER),
        "v20_registry_sha256": sha256_file(V20_REGISTRY), "v20_closed_authorization_sha256": sha256_file(V20_AUTH_CLOSED),
        "v20_zero_network_preflight_sha256": sha256_file(V20_ZERO_PREFLIGHT),
        "held_out_gold_sha256": sha256_file(HELD_OUT), "history_schedule_sha256": sha256_file(HISTORY_SCHEDULE),
    }


def validate() -> dict[str, Any]:
    cfg = load(CONFIG)
    if any(cfg["execution"].get(key) is not False for key in ("network_calls_allowed", "provider_calls_allowed", "paid_api_allowed", "qwen_authorization_open", "formal_scaling_allowed")):
        raise RuntimeError("v21 execution switches must remain closed")
    if source_bindings() != cfg["bindings"]["source_files"]:
        raise RuntimeError("v21 source binding drift")
    verify_integrity(V4_CONFIG, V4_MANIFEST, root=ROOT)
    v4, v17, v19, v20, v20run, closure, registry, v20zero, v20closed = load(V4_MANIFEST), load(V17_MANIFEST), load(V19_MANIFEST), load(V20_AUDIT), load(V20_RUN_AUDIT), load(V20_CLOSURE), load(V20_REGISTRY), load(V20_ZERO_PREFLIGHT), load(V20_AUTH_CLOSED)
    if v4.get("aggregate_fingerprint") != cfg["bindings"]["v4_aggregate_fingerprint"]:
        raise RuntimeError("v4 acceptance drift")
    if v17.get("aggregate_fingerprint") != cfg["bindings"]["v17_aggregate_fingerprint"] or v17.get("status") != "ready-for-explicit-authorization":
        raise RuntimeError("v17 acceptance drift")
    if v19.get("aggregate_fingerprint") != cfg["bindings"]["v19_aggregate_fingerprint"]:
        raise RuntimeError("v19 acceptance drift")
    if v20.get("passed") is not True or v20.get("combined_probe_rows") != 160:
        raise RuntimeError("v20 probe gate drift")
    if v20zero.get("aggregate_fingerprint") != cfg["bindings"]["v20_probe_aggregate_fingerprint"] or v20zero.get("status") != "zero-network-preflight-passed":
        raise RuntimeError("v20 zero-network acceptance drift")
    if v20run.get("provider_attempts") != 112 or v20run.get("completed_calls") != 112 or v20run.get("terminal_rows") != 0:
        raise RuntimeError("v20 ledger is incomplete")
    if closure.get("status") != "closed" or "phase2-probe-recovery-only-v20" not in registry.get("authorizations", {}) or v20closed.get("qwen_authorization_open") is not False:
        raise RuntimeError("v20 authorization is not closed")
    rows, bundles, gold = build_schedule()
    if len(rows) != 320 or len({r["logical_call_id"] for r in rows}) != 320 or len({r["request_hash"] for r in rows}) != 320:
        raise RuntimeError("v21 schedule identity drift")
    if [r["staged_execution_index"] for r in rows] != list(range(1, 321)):
        raise RuntimeError("v21 exact prefix indices drift")
    if {r["condition"] for r in rows} != set(CONDITIONS) or any(sum(r["condition"] == c for r in rows) != 80 for c in CONDITIONS):
        raise RuntimeError("v21 condition grid drift")
    if any(sum(r["task_id"] == task["task_id"] for r in rows) != 4 for task in gold):
        raise RuntimeError("v21 task grid drift")
    prior_request_hashes = {item.get("request_hash") for item in load(V19_SCHEDULE).get("schedule", [])}
    prior_request_hashes.update(item.get("request_hash") for item in load(V20_LEDGER))
    if {r["request_hash"] for r in rows} & prior_request_hashes:
        raise RuntimeError("v21 request hashes overlap prior probe recovery")
    if any("max_tokens" in r["canonical_request_body"] or r["canonical_request_body"]["response_format"] != {"type": "json_object"} or r["canonical_request_body"]["temperature"] != 0 or r["canonical_request_body"]["model_id"] != "qwen3.7-plus" for r in rows):
        raise RuntimeError("v21 provider route drift")
    prior_tasks = {x["task_id"] for x in bundles["global"]["examples"]}
    for bundle in bundles["typed"].values():
        prior_tasks.update(x["task_id"] for x in bundle["examples"])
    held_ids = {x["task_id"] for x in gold}
    history_ids = {x["task_id"] for x in load(HISTORY_SCHEDULE)["schedule"] if x.get("partition") == "formal_history"}
    probe_ids = {x["task_id"] for x in load(V17_SCHEDULE)["schedule"]}
    if prior_tasks & held_ids or history_ids & held_ids or probe_ids & held_ids:
        raise RuntimeError("history/probe/held-out task overlap")
    if any('"answers"' in json.dumps(r["canonical_request_body"], ensure_ascii=False) for r in rows):
        raise RuntimeError("gold field leaked into request")
    documents = {"held_out_schedule.json": {"schema_version": 21, "schedule": rows}, "prior_bundles.json": bundles, "schedule_audit.json": {"schema_version": 21, "held_out_tasks": 80, "logical_requests": 320, "condition_counts": {c: 80 for c in CONDITIONS}, "family_counts": {f: 64 for f in FAMILIES}, "prior_held_out_overlap": 0, "history_held_out_overlap": 0, "probe_held_out_overlap": 0, "gold_in_request": False, "network_calls": 0, "provider_calls": 0, "paid_api_calls": 0}}
    result = {"schema_version": 21, "experiment": "acl2027_phase2_heldout_activation_preflight_v21", "status": "ready-for-fresh-held-out-authorization", "authorization_request_status": "awaiting_fresh_explicit_user_authorization", "held_out_calls": 320, "task_count": 80, "condition_counts": {c: 80 for c in CONDITIONS}, "family_counts": {f: 64 for f in FAMILIES}, "probe_gate_passed": True, "v20_probe_primary_margin": v20["primary_paired_comparison"], "source_bindings": source_bindings(), "gold_in_request": False, "prior_held_out_overlap": 0, "history_held_out_overlap": 0, "probe_held_out_overlap": 0, "network_calls": 0, "provider_calls": 0, "model_calls": 0, "paid_api_calls": 0, "authorization_opened": False, "held_out_authorized": False, "later_stages_authorized": False, "formal_scaling_authorized": False, "decision_rules": cfg["decision_rules"], "documents": {name: rendered_sha256(value) for name, value in documents.items()}}
    result["aggregate_fingerprint"] = stable(result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-artifact", action="store_true")
    args = parser.parse_args()
    result = validate()
    if args.write_artifact:
        ARTIFACT.mkdir(parents=False, exist_ok=True)
        rows, bundles, gold = build_schedule()
        documents = {"held_out_schedule.json": {"schema_version": 21, "schedule": rows}, "prior_bundles.json": bundles, "schedule_audit.json": {"schema_version": 21, "held_out_tasks": 80, "logical_requests": 320, "condition_counts": {c: 80 for c in CONDITIONS}, "family_counts": {f: 64 for f in FAMILIES}, "prior_held_out_overlap": 0, "history_held_out_overlap": 0, "probe_held_out_overlap": 0, "gold_in_request": False, "network_calls": 0, "provider_calls": 0, "paid_api_calls": 0}}
        for name, value in documents.items():
            (ARTIFACT / name).write_text(render(value), encoding="utf-8", newline="\n")
        (ARTIFACT / "run_manifest.json").write_text(render(result), encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2, sort_keys=True))
