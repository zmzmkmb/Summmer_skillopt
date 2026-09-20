#!/usr/bin/env python3
"""Build the zero-network Phase 2 post-v23 replication design preflight v24."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_integrity_v4 import verify_integrity
from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable
from scripts.prepare_acl2027_phase2_payload_and_freeze_v2 import TYPES, make_payload, prior_exclusions

VERSION = 24
FAMILIES = (
    "fact_retrieval",
    "attribute_comparison",
    "bridge_attribute_comparison",
    "entity_bridge",
    "relation_inference",
)
CONDITIONS = ("cold", "copied_global", "global_only", "contextual_typed_prior")
TASKS_PER_FAMILY = 16
SYSTEM = (
    "Answer the question from the supplied context and optional prior bundle. "
    "Return exactly one JSON object and no other text, markdown, or explanation. "
    "The object must contain exactly one key named answer whose value is a non-empty "
    'short string. Required shape: {"answer":"<short answer>"}.'
)

CONFIG = ROOT / "configs/acl2027/phase2_post_v23_replication_design_preflight_v24.json"
SCRIPT = ROOT / "scripts/run_acl2027_phase2_post_v23_replication_design_preflight_v24.py"
TEST = ROOT / "tests/test_acl2027_phase2_post_v23_replication_design_preflight_v24.py"
ARTIFACT = ROOT / "artifacts/acl2027_phase2_post_v23_replication_design_preflight_v24"
REPORT = ROOT / "paper/acl2027/results/phase2_post_v23_replication_design_preflight_v24.md"

V4_CONFIG = ROOT / "configs/acl2027/phase2_staged_live_runner_preflight_v4.json"
V4_MANIFEST = ROOT / "artifacts/acl2027_phase2_staged_live_runner_preflight_v4/run_manifest.json"
V13_MANIFEST = ROOT / "artifacts/acl2027_phase2_formal_history_recovery_preflight_v13/run_manifest.json"
V17_PRIORS = ROOT / "artifacts/acl2027_phase2_probe_identifiable_schedule_preflight_v17/prior_bundles.json"
V17_SCHEDULE = ROOT / "artifacts/acl2027_phase2_probe_identifiable_schedule_preflight_v17/probe_schedule.json"
V17_GOLD = ROOT / "artifacts/acl2027_phase2_probe_identifiable_schedule_preflight_v17/replacement_probe_gold.json"
V19_SCHEDULE = ROOT / "artifacts/acl2027_phase2_probe_recovery_preflight_v19/probe_recovery_schedule.json"
V19_GOLD = ROOT / "artifacts/acl2027_phase2_probe_recovery_preflight_v19/recovery_probe_gold.json"
V20_PROBE_AUDIT = ROOT / "artifacts/acl2027_phase2_probe_recovery_live_v20/probe_audit.json"
V21_SCHEDULE = ROOT / "artifacts/acl2027_phase2_heldout_activation_preflight_v21/held_out_schedule.json"
V22_MANIFEST = ROOT / "artifacts/acl2027_phase2_heldout_recovery_preflight_v22/run_manifest.json"
V22_SCHEDULE = ROOT / "artifacts/acl2027_phase2_heldout_recovery_preflight_v22/held_out_recovery_schedule.json"
V22_GOLD = ROOT / "artifacts/acl2027_phase2_heldout_recovery_preflight_v22/combined_held_out_gold.json"
V23_COMBINED_AUDIT = ROOT / "artifacts/acl2027_phase2_heldout_recovery_live_v23/combined_held_out_audit.json"
V23_RUN_AUDIT = ROOT / "artifacts/acl2027_phase2_heldout_recovery_live_v23/run_audit.json"
V23_LEDGER = ROOT / "artifacts/acl2027_phase2_heldout_recovery_live_v23/ledger.json"
V23_CLOSURE = ROOT / "artifacts/acl2027_phase2_heldout_recovery_live_v23/authorization_closure.json"
V23_AUTH_CLOSED = ROOT / "configs/acl2027/phase2_heldout_recovery_live_authorization_closed_v23.json"

PHASE2_GOLD = tuple(
    ROOT / f"data/searchqa_phase2_verified/{name}.json"
    for name in ("calibration", "development_acquisition", "formal_history", "probe", "held_out")
)
SEARCHQA_ITEMS = tuple(ROOT / f"data/searchqa_split/{split}/items.json" for split in ("train", "val", "test"))
SEARCHQA_IDS = tuple(ROOT / f"data/searchqa_id_split/{split}/items.json" for split in ("train", "val", "test"))
SOURCE_2WIKI = ROOT / "data/2wikimultihopqa_verified/source/dev.json"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def render(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n"


def rendered_sha256(value: Any) -> str:
    return hashlib.sha256(render(value).encode("utf-8")).hexdigest()


def rows_from(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict):
        if isinstance(value.get("schedule"), list):
            return [row for row in value["schedule"] if isinstance(row, dict)]
        return [value]
    return []


def task_ids(values: Iterable[dict[str, Any]]) -> set[str]:
    result: set[str] = set()
    for row in values:
        ident = row.get("task_id", row.get("id", row.get("_id")))
        if ident is not None:
            result.add(str(ident))
    return result


def occupied_task_ids() -> set[str]:
    exclusions = prior_exclusions()
    occupied = set(exclusions["SearchQA"]) | set(exclusions["2WikiMultiHopQA"])
    for path in (*PHASE2_GOLD, V17_GOLD, V19_GOLD, V22_GOLD, V17_SCHEDULE, V19_SCHEDULE, V21_SCHEDULE, V22_SCHEDULE):
        occupied.update(task_ids(rows_from(load(path))))
    bundles = load(V17_PRIORS)
    occupied.update(task_ids(bundles["global"]["examples"]))
    for bundle in bundles["typed"].values():
        occupied.update(task_ids(bundle["examples"]))
    return occupied


def source_candidates() -> dict[str, list[dict[str, Any]]]:
    occupied = occupied_task_ids()
    candidates: dict[str, dict[str, dict[str, Any]]] = {family: {} for family in FAMILIES}
    for items_path, ids_path in zip(SEARCHQA_ITEMS, SEARCHQA_IDS):
        allowed_ids = {str(row["id"]) for row in load(ids_path)}
        split = items_path.parent.name
        for row in load(items_path):
            ident = str(row["id"])
            if ident in occupied or ident not in allowed_ids or not row.get("question") or not row.get("context") or not row.get("answers"):
                continue
            payload = make_payload(row, "SearchQA", "fact_retrieval", split)
            candidates["fact_retrieval"][ident] = payload
    for row in load(SOURCE_2WIKI):
        ident = str(row.get("_id", ""))
        family = TYPES.get(str(row.get("type")))
        if (
            not family
            or ident in occupied
            or not row.get("question")
            or not row.get("context")
            or row.get("answer") is None
            or not row.get("supporting_facts")
        ):
            continue
        candidates[family][ident] = make_payload(row, "2WikiMultiHopQA", family, "dev")
    return {family: list(pool.values()) for family, pool in candidates.items()}


def selector_hash(family: str, task_id: str) -> str:
    return hashlib.sha256(f"phase2-v24:post-v23-replication:{family}:{task_id}".encode()).hexdigest()


def select_tasks() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pools = source_candidates()
    selected: list[dict[str, Any]] = []
    audit_families: dict[str, Any] = {}
    for family in FAMILIES:
        ordered = sorted(pools[family], key=lambda row: (selector_hash(family, str(row["task_id"])), str(row["task_id"])))
        if len(ordered) < TASKS_PER_FAMILY:
            raise RuntimeError(f"insufficient unused replication tasks for {family}: {len(ordered)}")
        chosen = ordered[:TASKS_PER_FAMILY]
        selected.extend(chosen)
        audit_families[family] = {
            "available_after_all_exclusions": len(ordered),
            "selected": TASKS_PER_FAMILY,
            "task_ids": [row["task_id"] for row in chosen],
            "selector_hashes": [selector_hash(family, str(row["task_id"])) for row in chosen],
        }
    occupied = occupied_task_ids()
    audit = {
        "schema_version": VERSION,
        "selector": "16 lowest SHA256(phase2-v24:post-v23-replication:<family>:<task_id>) per family",
        "families": audit_families,
        "selected_tasks": len(selected),
        "unique_selected_task_ids": len({row["task_id"] for row in selected}),
        "occupied_task_count": len(occupied),
        "occupied_task_set_sha256": stable(sorted(occupied)),
        "selected_prior_overlap": len({row["task_id"] for row in selected} & occupied),
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "paid_api_calls": 0,
    }
    return selected, audit


def public_task(task: dict[str, Any]) -> dict[str, Any]:
    return {
        key: task[key]
        for key in ("task_id", "task_family", "task_type", "skill_family", "question", "context", "source_split")
    }


def condition_prior(condition: str, family: str, bundles: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if condition == "cold":
        return "candidate:none:v24", {"slot": "none", "source_scope": "none", "examples": []}
    if condition == "global_only":
        return bundles["global"]["candidate_id"], {"slot": "global", "source_scope": "global", "examples": bundles["global"]["examples"]}
    if condition == "copied_global":
        return f"candidate:copied-global:{family}:v24", {"slot": f"family:{family}", "source_scope": "global_copied", "examples": bundles["global"]["examples"]}
    typed = bundles["typed"][family]
    return typed["candidate_id"], {"slot": f"family:{family}", "source_scope": typed["source_scope"], "examples": typed["examples"]}


def build_schedule(tasks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    bundles = load(V17_PRIORS)
    schedule: list[dict[str, Any]] = []
    for task in tasks:
        public = public_task(task)
        family = task["skill_family"]
        for condition in CONDITIONS:
            candidate_id, prior = condition_prior(condition, family, bundles)
            prior_text = json.dumps(prior, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            body = {
                "model_id": "qwen3.7-plus",
                "temperature": 0,
                "enable_thinking": False,
                "response_format": {"type": "json_object"},
                "phase": "2",
                "stage": "post_v23_replication",
                "partition": "replication_held_out",
                "task_family": task["task_family"],
                "task_type": task["task_type"],
                "skill_family": family,
                "task_id": task["task_id"],
                "public_payload_sha256": stable(public),
                "condition": condition,
                "candidate_id": candidate_id,
                "candidate_version": "phase2-v24-design-only",
                "typed_scope": family,
                "prompt_template_version": "phase2-post-v23-replication-json-v24",
                "prior_payload_sha256": stable(prior),
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {
                        "role": "user",
                        "content": "Prior bundle:\n" + prior_text + "\n\nQuestion:\n" + task["question"] + "\n\nContext:\n" + json.dumps(task["context"], ensure_ascii=True),
                    },
                ],
            }
            sequence = len(schedule) + 1
            schedule.append({
                "schema_version": VERSION,
                "sequence": sequence,
                "staged_execution_index": sequence,
                "logical_call_id": f"phase2-v24:post_v23_replication:{family}:{task['task_id']}:{condition}",
                "request_hash": stable(body),
                "partition": "replication_held_out",
                "stage": "post_v23_replication",
                "task_id": task["task_id"],
                "task_family": task["task_family"],
                "task_type": task["task_type"],
                "skill_family": family,
                "condition": condition,
                "candidate_id": candidate_id,
                "prior_payload_sha256": body["prior_payload_sha256"],
                "public_payload_sha256": body["public_payload_sha256"],
                "canonical_request_body": body,
                "provenance": {
                    "source_dataset": task["task_family"],
                    "source_record_id": task["task_id"],
                    "source_split": task["source_split"],
                    "gold_is_not_request": True,
                    "prior_outcome_reused": False,
                    "network_calls": 0,
                    "provider_calls": 0,
                    "paid_api_calls": 0,
                },
                "expected_accounting": {"retries": 0, "max_tokens_present": False, "usage_required": True},
            })
    return schedule, tasks


def prior_request_identities() -> tuple[set[str], set[str]]:
    logical: set[str] = set()
    request_hashes: set[str] = set()
    for path in (V17_SCHEDULE, V19_SCHEDULE, V21_SCHEDULE, V22_SCHEDULE):
        for row in rows_from(load(path)):
            logical.add(str(row.get("logical_call_id", "")))
            request_hashes.add(str(row.get("request_hash", "")))
    for row in rows_from(load(V23_LEDGER)):
        logical.add(str(row.get("logical_call_id", "")))
        request_hashes.add(str(row.get("request_hash", "")))
    return logical - {""}, request_hashes - {""}


def source_paths() -> dict[str, Path]:
    paths = {
        "preflight_source_sha256": SCRIPT,
        "preflight_test_sha256": TEST,
        "v4_config_sha256": V4_CONFIG,
        "v4_manifest_sha256": V4_MANIFEST,
        "v13_manifest_sha256": V13_MANIFEST,
        "v17_prior_bundles_sha256": V17_PRIORS,
        "v17_schedule_sha256": V17_SCHEDULE,
        "v19_schedule_sha256": V19_SCHEDULE,
        "v20_probe_audit_sha256": V20_PROBE_AUDIT,
        "v21_schedule_sha256": V21_SCHEDULE,
        "v22_manifest_sha256": V22_MANIFEST,
        "v22_schedule_sha256": V22_SCHEDULE,
        "v22_combined_gold_sha256": V22_GOLD,
        "v23_combined_audit_sha256": V23_COMBINED_AUDIT,
        "v23_run_audit_sha256": V23_RUN_AUDIT,
        "v23_ledger_sha256": V23_LEDGER,
        "v23_closure_sha256": V23_CLOSURE,
        "v23_closed_authorization_sha256": V23_AUTH_CLOSED,
        "source_2wiki_dev_sha256": SOURCE_2WIKI,
    }
    for index, path in enumerate(PHASE2_GOLD, 1):
        paths[f"phase2_gold_{index}_sha256"] = path
    for index, path in enumerate(SEARCHQA_ITEMS, 1):
        paths[f"searchqa_items_{index}_sha256"] = path
    for index, path in enumerate(SEARCHQA_IDS, 1):
        paths[f"searchqa_ids_{index}_sha256"] = path
    return paths


def source_bindings() -> dict[str, str]:
    return {name: sha256_file(path) for name, path in source_paths().items()}


def contains_forbidden_gold_key(value: Any) -> bool:
    forbidden = {"answer", "answers", "supporting_evidence", "supporting_facts", "gold_answer"}
    if isinstance(value, dict):
        return bool(set(value) & forbidden) or any(contains_forbidden_gold_key(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_forbidden_gold_key(item) for item in value)
    return False


def validate() -> dict[str, Any]:
    cfg = load(CONFIG)
    if any(value is not False for value in cfg["execution"].values()):
        raise RuntimeError("v24 execution switches must remain closed")
    if cfg["future_execution_proposal"]["status"] != "not_authorized_design_only" or cfg["future_execution_proposal"]["authorization_artifact_created"] is not False:
        raise RuntimeError("v24 must not create or imply provider authorization")
    actual_bindings = source_bindings()
    if actual_bindings != cfg["bindings"]["source_files"]:
        raise RuntimeError("v24 source binding drift")
    verify_integrity(V4_CONFIG, V4_MANIFEST, root=ROOT)
    if load(V4_MANIFEST).get("aggregate_fingerprint") != cfg["bindings"]["v4_aggregate_fingerprint"]:
        raise RuntimeError("v4 aggregate fingerprint drift")
    v13 = load(V13_MANIFEST)
    if v13.get("aggregate_fingerprint") != cfg["bindings"]["v13_aggregate_fingerprint"] or v13.get("candidate", {}).get("passed") is not True:
        raise RuntimeError("v13 candidate coverage drift")
    v20 = load(V20_PROBE_AUDIT)
    if v20.get("passed") is not True or v20.get("combined_probe_rows") != 160:
        raise RuntimeError("v20 probe gate drift")
    v23, v23run, v23closure, v23closed = load(V23_COMBINED_AUDIT), load(V23_RUN_AUDIT), load(V23_CLOSURE), load(V23_AUTH_CLOSED)
    if v23.get("aggregate_fingerprint") != cfg["bindings"]["v23_combined_audit_fingerprint"] or v23.get("eligibility_gate") != "inconclusive":
        raise RuntimeError("v23 held-out result drift")
    if v23run.get("authorization_closed") is not True or v23run.get("completed_calls") != 88 or v23run.get("retries") != 0:
        raise RuntimeError("v23 terminal audit drift")
    if v23closure.get("status") != "closed" or v23closed.get("qwen_authorization_open") is not False:
        raise RuntimeError("v23 authorization closure drift")

    tasks, selection_audit = select_tasks()
    schedule, private_gold = build_schedule(tasks)
    if len(tasks) != 80 or len({row["task_id"] for row in tasks}) != 80:
        raise RuntimeError("v24 replication task count drift")
    family_counts = {family: sum(row["skill_family"] == family for row in tasks) for family in FAMILIES}
    if family_counts != {family: TASKS_PER_FAMILY for family in FAMILIES}:
        raise RuntimeError("v24 replication family balance drift")
    if len(schedule) != 320 or len({row["logical_call_id"] for row in schedule}) != 320 or len({row["request_hash"] for row in schedule}) != 320:
        raise RuntimeError("v24 schedule identity drift")
    if [row["staged_execution_index"] for row in schedule] != list(range(1, 321)):
        raise RuntimeError("v24 exact-prefix indices drift")
    if any(sum(row["task_id"] == task["task_id"] for row in schedule) != 4 for task in tasks):
        raise RuntimeError("v24 four-condition task grid drift")
    condition_counts = {condition: sum(row["condition"] == condition for row in schedule) for condition in CONDITIONS}
    if condition_counts != {condition: 80 for condition in CONDITIONS}:
        raise RuntimeError("v24 condition balance drift")
    if selection_audit["selected_prior_overlap"] != 0:
        raise RuntimeError("v24 selected tasks overlap prior evidence")
    prior_logical, prior_hashes = prior_request_identities()
    if {row["logical_call_id"] for row in schedule} & prior_logical or {row["request_hash"] for row in schedule} & prior_hashes:
        raise RuntimeError("v24 request identities overlap prior schedules or ledgers")
    if any(contains_forbidden_gold_key(row["canonical_request_body"]) for row in schedule):
        raise RuntimeError("v24 private gold leaked into a request")
    if any(
        row["canonical_request_body"]["model_id"] != "qwen3.7-plus"
        or row["canonical_request_body"]["temperature"] != 0
        or row["canonical_request_body"]["response_format"] != {"type": "json_object"}
        or "max_tokens" in row["canonical_request_body"]
        for row in schedule
    ):
        raise RuntimeError("v24 route proposal drift")
    for task in tasks:
        grid = [row for row in schedule if row["task_id"] == task["task_id"]]
        if len({row["prior_payload_sha256"] for row in grid}) != 4:
            raise RuntimeError("v24 model-visible condition semantics are not distinct")

    documents = {
        "replication_schedule.json": {"schema_version": VERSION, "schedule": schedule},
        "replication_private_gold.json": private_gold,
        "task_selection_audit.json": selection_audit,
        "prior_bundles.json": load(V17_PRIORS),
    }
    result = {
        "schema_version": VERSION,
        "experiment": cfg["experiment"],
        "status": "design-preflight-passed-closed",
        "authorization_status": "not-authorized",
        "authorization_artifact_created": False,
        "config_sha256": sha256_file(CONFIG),
        "source_bindings": actual_bindings,
        "v4_aggregate_fingerprint": cfg["bindings"]["v4_aggregate_fingerprint"],
        "v13_aggregate_fingerprint": cfg["bindings"]["v13_aggregate_fingerprint"],
        "v23_combined_audit_fingerprint": cfg["bindings"]["v23_combined_audit_fingerprint"],
        "v23_gate": "inconclusive",
        "task_count": len(tasks),
        "tasks_per_family": TASKS_PER_FAMILY,
        "family_counts": family_counts,
        "condition_counts": condition_counts,
        "logical_calls_proposed": len(schedule),
        "max_provider_attempts_proposed": len(schedule),
        "unique_task_ids": len({row["task_id"] for row in tasks}),
        "unique_logical_call_ids": len({row["logical_call_id"] for row in schedule}),
        "unique_request_hashes": len({row["request_hash"] for row in schedule}),
        "prior_task_overlap": 0,
        "prior_logical_call_overlap": 0,
        "prior_request_hash_overlap": 0,
        "gold_in_request": False,
        "decision_rules": cfg["decision_rules"],
        "future_execution_proposal": cfg["future_execution_proposal"],
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "paid_api_calls": 0,
        "formal_scaling_calls": 0,
        "documents": {name: rendered_sha256(value) for name, value in documents.items()},
    }
    result["aggregate_fingerprint"] = stable(result)
    return result


def report_text(result: dict[str, Any], selection: dict[str, Any]) -> str:
    capacities = ", ".join(
        f"{family}={selection['families'][family]['available_after_all_exclusions']}"
        for family in FAMILIES
    )
    return (
        "# ACL 2027 Phase 2 post-v23 replication design preflight v24\n\n"
        "## Scope\n\n"
        "This is a zero-network, design-only preflight. It creates no live authorization and makes no provider, model, paid, or formal-scaling call.\n\n"
        "## Frozen replication design\n\n"
        "The design deterministically selects 80 previously unused tasks, 16 per frozen skill family, and expands them into 320 calls over cold, copied-global, global-only, and contextual-typed-prior conditions. The v17 prior bundles remain unchanged. Private gold is stored separately and no gold field appears in a canonical request.\n\n"
        f"Available candidates after all exclusions: `{capacities}`. Task, logical-call, and request-hash overlaps with prior evidence are all zero.\n\n"
        "The replication-only primary gate reuses the unchanged v21/v23 decision rule. A pooled v23-plus-replication result is secondary descriptive analysis only, preventing post-v23 threshold tuning.\n\n"
        "## Future execution boundary\n\n"
        "A future execution would require a separate explicit authorization for exactly 320 qwen3.7-plus attempts, temperature 0, zero retries, no max_tokens, JSON-object responses, and explicit CNY ceilings. The current artifact does not grant that permission. Other models, later stages, and formal scaling remain forbidden.\n\n"
        "## Integrity\n\n"
        f"Aggregate fingerprint: `{result['aggregate_fingerprint']}`. Network/provider/model/paid/formal-scaling counters: `0/0/0/0/0`. Authorization status: `not-authorized`.\n"
    )


def write_artifact(result: dict[str, Any]) -> None:
    ARTIFACT.mkdir(parents=False, exist_ok=False)
    tasks, selection = select_tasks()
    schedule, private_gold = build_schedule(tasks)
    documents = {
        "replication_schedule.json": {"schema_version": VERSION, "schedule": schedule},
        "replication_private_gold.json": private_gold,
        "task_selection_audit.json": selection,
        "prior_bundles.json": load(V17_PRIORS),
        "run_manifest.json": result,
    }
    for name, value in documents.items():
        (ARTIFACT / name).write_text(render(value), encoding="utf-8", newline="\n")
    REPORT.write_text(report_text(result, selection), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--print-bindings", action="store_true")
    parser.add_argument("--write-artifact", action="store_true")
    args = parser.parse_args()
    if args.print_bindings:
        print(json.dumps(source_bindings(), indent=2, sort_keys=True))
        raise SystemExit(0)
    validated = validate()
    if args.write_artifact:
        write_artifact(validated)
    print(json.dumps(validated, indent=2, sort_keys=True))
