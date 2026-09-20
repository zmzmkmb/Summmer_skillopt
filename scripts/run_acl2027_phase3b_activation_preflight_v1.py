#!/usr/bin/env python3
"""Build the zero-network ACL 2027 Phase 3B activation preflight v1."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable
from scripts.run_acl2027_phase2_post_v23_replication_design_preflight_v24 import (
    FAMILIES,
    V17_PRIORS,
    contains_forbidden_gold_key,
    occupied_task_ids,
    public_task,
    source_candidates,
)

VERSION = 1
TASKS_PER_FAMILY = 12
CONDITIONS = (
    "cold",
    "copied_global",
    "global_only",
    "contextual_typed_prior",
    "shuffled_typed_prior",
)
RESPONSE_KEYS = (
    "declared_skill_applicability",
    "selected_skill_id",
    "intermediate_operation",
    "final_answer",
)
SYSTEM = (
    "Answer the question from the supplied context and optional historical skill bundle. "
    "Return exactly one JSON object and no other text or markdown. The object must contain "
    "exactly these four keys: declared_skill_applicability (boolean), selected_skill_id "
    "(the presented candidate ID when used, otherwise the string none), intermediate_operation "
    "(a short non-empty operation label, not hidden reasoning or chain-of-thought), and "
    "final_answer (a non-empty short string)."
)

CONFIG = ROOT / "configs/acl2027/phase3b_activation_preflight_v1.json"
SCRIPT = ROOT / "scripts/run_acl2027_phase3b_activation_preflight_v1.py"
TEST = ROOT / "tests/test_acl2027_phase3b_activation_preflight_v1.py"
ARTIFACT = ROOT / "artifacts/acl2027_phase3b_activation_preflight_v1"
REPORT = ROOT / "paper/acl2027/results/phase3b_activation_preflight_v1.md"
PHASE3A_CONFIG = ROOT / "configs/acl2027/phase3a_real_task_mechanism_audit_v1.json"
PHASE3A_AUDIT = ROOT / "artifacts/acl2027_phase3a_real_task_mechanism_audit_v1/mechanism_audit.json"
PHASE3A_PILOT = ROOT / "artifacts/acl2027_phase3a_real_task_mechanism_audit_v1/activation_pilot_design.json"
PHASE2_FINAL_AUDIT = ROOT / "artifacts/acl2027_phase2_post_v25_failure_analysis_second_recovery_live_v31/combined_failure_analysis_audit.json"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def render(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n"


def rendered_sha256(value: Any) -> str:
    return hashlib.sha256(render(value).encode("utf-8")).hexdigest()


def walk_records(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_records(child)


def phase2_identity_universe() -> dict[str, set[str]]:
    result = {
        "task_ids": set(occupied_task_ids()),
        "logical_call_ids": set(),
        "request_hashes": set(),
    }
    for directory in sorted(ROOT.glob("artifacts/acl2027_phase2*")):
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".json", ".jsonl"}:
                continue
            try:
                if path.suffix.lower() == ".jsonl":
                    values = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
                else:
                    values = [load(path)]
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            for value in values:
                for row in walk_records(value):
                    if row.get("task_id") not in (None, ""):
                        result["task_ids"].add(str(row["task_id"]))
                    if row.get("logical_call_id") not in (None, ""):
                        result["logical_call_ids"].add(str(row["logical_call_id"]))
                    if row.get("request_hash") not in (None, ""):
                        result["request_hashes"].add(str(row["request_hash"]))
    return result


def selector_hash(family: str, task_id: str) -> str:
    return hashlib.sha256(f"phase3b-v1:activation-preflight:{family}:{task_id}".encode()).hexdigest()


def select_tasks() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pools = source_candidates()
    prior = phase2_identity_universe()
    selected: list[dict[str, Any]] = []
    families: dict[str, Any] = {}
    for family in FAMILIES:
        available = [row for row in pools[family] if str(row["task_id"]) not in prior["task_ids"]]
        ordered = sorted(available, key=lambda row: (selector_hash(family, str(row["task_id"])), str(row["task_id"])))
        if len(ordered) < TASKS_PER_FAMILY:
            raise RuntimeError(f"insufficient unused Phase 3B tasks for {family}: {len(ordered)}")
        chosen = ordered[:TASKS_PER_FAMILY]
        selected.extend(chosen)
        families[family] = {
            "available_after_all_phase2_exclusions": len(ordered),
            "selected": len(chosen),
            "task_ids": [row["task_id"] for row in chosen],
            "selector_hashes": [selector_hash(family, str(row["task_id"])) for row in chosen],
        }
    chosen_ids = {str(row["task_id"]) for row in selected}
    return selected, {
        "schema_version": VERSION,
        "selector": "12 lowest SHA256(phase3b-v1:activation-preflight:<family>:<task_id>) per family",
        "selection_uses_gold": False,
        "families": families,
        "selected_tasks": len(selected),
        "unique_selected_task_ids": len(chosen_ids),
        "phase2_task_universe_size": len(prior["task_ids"]),
        "phase2_task_universe_sha256": stable(sorted(prior["task_ids"])),
        "phase2_task_overlap": len(chosen_ids & prior["task_ids"]),
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "paid_api_calls": 0,
    }


def shuffled_family_map() -> dict[str, str]:
    cfg = load(CONFIG)
    return {str(key): str(value) for key, value in cfg["design"]["shuffled_family_map"].items()}


def condition_prior(condition: str, family: str, bundles: dict[str, Any]) -> tuple[str, dict[str, Any], str]:
    if condition == "cold":
        return "none", {
            "slot": "none",
            "source_scope": "none",
            "target_skill_family": family,
            "source_skill_family": "none",
            "examples": [],
        }, "none"
    if condition == "global_only":
        candidate = str(bundles["global"]["candidate_id"])
        return candidate, {
            "slot": "global",
            "source_scope": "global",
            "target_skill_family": family,
            "source_skill_family": "mixed",
            "examples": bundles["global"]["examples"],
        }, "mixed"
    if condition == "copied_global":
        candidate = f"candidate:copied-global:{family}:phase3b-v1"
        return candidate, {
            "slot": f"family:{family}",
            "source_scope": "global_copied",
            "base_candidate_id": bundles["global"]["candidate_id"],
            "target_skill_family": family,
            "source_skill_family": "mixed",
            "examples": bundles["global"]["examples"],
        }, "mixed"
    if condition == "contextual_typed_prior":
        typed = bundles["typed"][family]
        candidate = str(typed["candidate_id"])
        return candidate, {
            "slot": f"family:{family}",
            "source_scope": typed["source_scope"],
            "target_skill_family": family,
            "source_skill_family": family,
            "examples": typed["examples"],
        }, family
    source_family = shuffled_family_map()[family]
    if source_family == family:
        raise RuntimeError("shuffled typed prior must come from a different family")
    typed = bundles["typed"][source_family]
    candidate = f"candidate:shuffled-typed:{source_family}-to-{family}:phase3b-v1"
    return candidate, {
        "slot": f"family:{family}",
        "source_scope": "shuffled_typed_negative_control",
        "base_candidate_id": typed["candidate_id"],
        "target_skill_family": family,
        "source_skill_family": source_family,
        "examples": typed["examples"],
    }, source_family


def build_schedule(tasks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    bundles = load(V17_PRIORS)
    schedule: list[dict[str, Any]] = []
    for task in tasks:
        family = str(task["skill_family"])
        public = public_task(task)
        for condition in CONDITIONS:
            candidate_id, prior, source_family = condition_prior(condition, family, bundles)
            prior_text = json.dumps(prior, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            allowed = ["none"] if candidate_id == "none" else ["none", candidate_id]
            body = {
                "model_id": "qwen3.7-plus",
                "temperature": 0,
                "enable_thinking": False,
                "response_format": {"type": "json_object"},
                "phase": "3B",
                "stage": "activation_pilot",
                "partition": "mechanism_bridge_held_out",
                "task_family": task["task_family"],
                "task_type": task["task_type"],
                "skill_family": family,
                "task_id": task["task_id"],
                "condition": condition,
                "candidate_id": candidate_id,
                "candidate_version": "phase3b-v1-design-only",
                "target_skill_family": family,
                "source_skill_family": source_family,
                "available_skill_ids": allowed,
                "public_payload_sha256": stable(public),
                "prior_payload_sha256": stable(prior),
                "prompt_template_version": "phase3b-activation-json-v1",
                "response_contract": {
                    "exact_keys": list(RESPONSE_KEYS),
                    "declared_skill_applicability": "boolean",
                    "selected_skill_id": {"type": "string", "allowed": allowed},
                    "intermediate_operation": {"type": "string", "non_empty": True, "chain_of_thought": False},
                    "final_answer": {"type": "string", "non_empty": True},
                },
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {
                        "role": "user",
                        "content": (
                            "Available skill IDs: " + json.dumps(allowed, ensure_ascii=True) +
                            "\nHistorical skill bundle:\n" + prior_text +
                            "\n\nQuestion:\n" + str(task["question"]) +
                            "\n\nContext:\n" + json.dumps(task["context"], ensure_ascii=True)
                        ),
                    },
                ],
            }
            sequence = len(schedule) + 1
            schedule.append({
                "schema_version": VERSION,
                "sequence": sequence,
                "staged_execution_index": sequence,
                "logical_call_id": f"phase3b-v1:activation:{family}:{task['task_id']}:{condition}",
                "request_hash": stable(body),
                "provider_response_id": None,
                "task_id": task["task_id"],
                "task_family": task["task_family"],
                "task_type": task["task_type"],
                "skill_family": family,
                "condition": condition,
                "candidate_id": candidate_id,
                "target_skill_family": family,
                "source_skill_family": source_family,
                "prior_payload_sha256": body["prior_payload_sha256"],
                "public_payload_sha256": body["public_payload_sha256"],
                "canonical_request_body": body,
                "provenance": {
                    "source_dataset": task["task_family"],
                    "source_record_id": task["task_id"],
                    "source_split": task["source_split"],
                    "gold_is_not_request": True,
                    "selection_used_gold": False,
                    "network_calls": 0,
                    "provider_calls": 0,
                    "model_calls": 0,
                    "paid_api_calls": 0,
                },
                "expected_accounting": {"retries": 0, "max_tokens_present": False, "usage_required": True},
            })
    return schedule, tasks


def identity_audit(tasks: list[dict[str, Any]], schedule: list[dict[str, Any]], selection: dict[str, Any]) -> dict[str, Any]:
    prior = phase2_identity_universe()
    task_ids = {str(row["task_id"]) for row in tasks}
    logical = {str(row["logical_call_id"]) for row in schedule}
    hashes = {str(row["request_hash"]) for row in schedule}
    return {
        "schema_version": VERSION,
        "phase2_task_ids": len(prior["task_ids"]),
        "phase2_logical_call_ids": len(prior["logical_call_ids"]),
        "phase2_request_hashes": len(prior["request_hashes"]),
        "proposed_task_ids": len(task_ids),
        "proposed_logical_call_ids": len(logical),
        "proposed_request_hashes": len(hashes),
        "task_id_overlap": len(task_ids & prior["task_ids"]),
        "logical_call_id_overlap": len(logical & prior["logical_call_ids"]),
        "request_hash_overlap": len(hashes & prior["request_hashes"]),
        "phase2_task_set_sha256": selection["phase2_task_universe_sha256"],
        "phase2_logical_call_set_sha256": stable(sorted(prior["logical_call_ids"])),
        "phase2_request_hash_set_sha256": stable(sorted(prior["request_hashes"])),
    }


def source_paths() -> dict[str, Path]:
    return {
        "preflight_source_sha256": SCRIPT,
        "preflight_test_sha256": TEST,
        "phase3a_config_sha256": PHASE3A_CONFIG,
        "phase3a_mechanism_audit_sha256": PHASE3A_AUDIT,
        "phase3a_activation_pilot_design_sha256": PHASE3A_PILOT,
        "phase2_final_audit_sha256": PHASE2_FINAL_AUDIT,
        "v17_prior_bundles_sha256": V17_PRIORS,
    }


def source_bindings() -> dict[str, str]:
    return {name: sha256_file(path) for name, path in source_paths().items()}


def analysis_plan() -> dict[str, Any]:
    return load(CONFIG)["analysis_plan"]


def validate() -> dict[str, Any]:
    cfg = load(CONFIG)
    if any(value is not False for value in cfg["execution"].values()):
        raise RuntimeError("Phase 3B execution switches must remain closed")
    if cfg["future_execution_proposal"]["status"] != "not_authorized":
        raise RuntimeError("Phase 3B cannot imply provider authorization")
    actual_bindings = source_bindings()
    if actual_bindings != cfg["bindings"]["source_files"]:
        raise RuntimeError("Phase 3B source binding drift")
    phase3a = load(PHASE3A_AUDIT)
    if phase3a["aggregate_fingerprint"] != cfg["bindings"]["phase3a_aggregate_fingerprint"]:
        raise RuntimeError("Phase 3A aggregate fingerprint drift")
    if phase3a["phase2_gate_preserved"] != "inconclusive" or cfg["bindings"]["phase2_gate_preserved"] != "inconclusive":
        raise RuntimeError("Phase 2 gate must remain inconclusive")

    tasks, selection = select_tasks()
    schedule, private_gold = build_schedule(tasks)
    identities = identity_audit(tasks, schedule, selection)
    family_counts = Counter(str(row["skill_family"]) for row in tasks)
    condition_counts = Counter(str(row["condition"]) for row in schedule)
    if len(tasks) != 60 or len({row["task_id"] for row in tasks}) != 60:
        raise RuntimeError("Phase 3B task count drift")
    if family_counts != Counter({family: TASKS_PER_FAMILY for family in FAMILIES}):
        raise RuntimeError("Phase 3B family balance drift")
    if len(schedule) != 300 or len({row["logical_call_id"] for row in schedule}) != 300 or len({row["request_hash"] for row in schedule}) != 300:
        raise RuntimeError("Phase 3B request identity drift")
    if condition_counts != Counter({condition: 60 for condition in CONDITIONS}):
        raise RuntimeError("Phase 3B condition balance drift")
    if [row["staged_execution_index"] for row in schedule] != list(range(1, 301)):
        raise RuntimeError("Phase 3B exact sequence drift")
    if any(contains_forbidden_gold_key(row["canonical_request_body"]) for row in schedule):
        raise RuntimeError("Phase 3B private gold leaked into a canonical request")
    if any(identities[key] != 0 for key in ("task_id_overlap", "logical_call_id_overlap", "request_hash_overlap")):
        raise RuntimeError("Phase 3B identity overlap audit failed")
    for task in tasks:
        grid = [row for row in schedule if row["task_id"] == task["task_id"]]
        if {row["condition"] for row in grid} != set(CONDITIONS) or len({row["prior_payload_sha256"] for row in grid}) != 5:
            raise RuntimeError("Phase 3B condition semantics are not distinct")
        shuffled = next(row for row in grid if row["condition"] == "shuffled_typed_prior")
        if shuffled["source_skill_family"] == shuffled["target_skill_family"]:
            raise RuntimeError("Phase 3B shuffled control family mismatch failed")

    documents = {
        "activation_schedule.json": {"schema_version": VERSION, "schedule": schedule},
        "activation_private_gold.json": private_gold,
        "task_selection_audit.json": selection,
        "identity_overlap_audit.json": identities,
        "analysis_plan.json": analysis_plan(),
    }
    result = {
        "schema_version": VERSION,
        "experiment": cfg["experiment"],
        "status": "design-preflight-passed-closed",
        "authorization_status": "not-authorized",
        "authorization_artifact_created": False,
        "config_sha256": sha256_file(CONFIG),
        "source_bindings": actual_bindings,
        "phase3a_aggregate_fingerprint": phase3a["aggregate_fingerprint"],
        "phase2_gate_preserved": "inconclusive",
        "task_count": len(tasks),
        "tasks_per_family": TASKS_PER_FAMILY,
        "family_counts": dict(family_counts),
        "condition_counts": dict(condition_counts),
        "logical_calls_proposed": len(schedule),
        "unique_task_ids": len({row["task_id"] for row in tasks}),
        "unique_logical_call_ids": len({row["logical_call_id"] for row in schedule}),
        "unique_request_hashes": len({row["request_hash"] for row in schedule}),
        "prior_task_overlap": 0,
        "prior_logical_call_overlap": 0,
        "prior_request_hash_overlap": 0,
        "response_contract_keys": list(RESPONSE_KEYS),
        "analysis_plan": analysis_plan(),
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
        f"{family}={selection['families'][family]['available_after_all_phase2_exclusions']}"
        for family in FAMILIES
    )
    return (
        "# ACL 2027 Phase 3B activation preflight v1\n\n"
        "## Scope\n\n"
        "This is a zero-network activation preflight. It preserves the Phase 2 inconclusive gate, creates no authorization, and makes no provider, model, paid, or formal-scaling call.\n\n"
        "## Frozen mechanism bridge\n\n"
        "The design selects 60 entirely new tasks, 12 per skill family, and expands them into 300 requests over cold, copied-global, global-only, contextual-typed, and shuffled-typed conditions. Each response must expose exactly four structured observations: declared applicability, selected skill ID, a short intermediate operation label, and the final answer. The shuffled-typed condition deterministically presents a bundle from a different family as a negative control.\n\n"
        f"Available candidates after all Phase 2 exclusions: `{capacities}`. Task, logical-call, and request-hash overlaps with all scanned Phase 2 spent and proposed identities are zero. Private gold is separate from every canonical request.\n\n"
        "## Frozen analysis and stop rule\n\n"
        "Primary uptake requires both declared applicability and exact selection of the presented candidate ID. Contextual typed uptake is compared pairwise with shuffled typed uptake, and final answers receive both strict normalized and alias-tolerant scores. Positive, negative, and inconclusive gates are frozen in `analysis_plan.json`. The pilot must stop without scaling when contextual uptake is below 0.15 or its advantage over shuffled typed is below 0.05.\n\n"
        "## Execution boundary\n\n"
        "The 300-call schedule is a proposal only. A separate explicit authorization must bind this exact fingerprint before any provider call. No authorization receipt or open authorization file exists.\n\n"
        "## Integrity\n\n"
        f"Aggregate fingerprint: `{result['aggregate_fingerprint']}`. Network/provider/model/paid/formal-scaling counters: `0/0/0/0/0`. Authorization status: `not-authorized`.\n"
    )


def write_artifact(result: dict[str, Any]) -> None:
    ARTIFACT.mkdir(parents=False, exist_ok=False)
    tasks, selection = select_tasks()
    schedule, private_gold = build_schedule(tasks)
    identities = identity_audit(tasks, schedule, selection)
    documents = {
        "activation_schedule.json": {"schema_version": VERSION, "schedule": schedule},
        "activation_private_gold.json": private_gold,
        "task_selection_audit.json": selection,
        "identity_overlap_audit.json": identities,
        "analysis_plan.json": analysis_plan(),
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
