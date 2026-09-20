#!/usr/bin/env python3
"""Build the zero-network Phase 2 post-v25 failure-analysis preflight v26."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import normalize_answer, parse_response, sha256_file, stable
from scripts.run_acl2027_phase2_post_v23_replication_design_preflight_v24 import (
    CONDITIONS,
    FAMILIES,
    SYSTEM,
    V17_PRIORS,
    contains_forbidden_gold_key,
    occupied_task_ids,
    public_task,
    source_candidates,
)

VERSION = 26
TASKS_PER_FAMILY = 80
CONFIG = ROOT / "configs/acl2027/phase2_post_v25_failure_analysis_design_preflight_v26.json"
SCRIPT = ROOT / "scripts/run_acl2027_phase2_post_v25_failure_analysis_design_preflight_v26.py"
TEST = ROOT / "tests/test_acl2027_phase2_post_v25_failure_analysis_design_preflight_v26.py"
ARTIFACT = ROOT / "artifacts/acl2027_phase2_post_v25_failure_analysis_design_preflight_v26"
REPORT = ROOT / "paper/acl2027/results/phase2_post_v25_failure_analysis_design_preflight_v26.md"

V13_MANIFEST = ROOT / "artifacts/acl2027_phase2_formal_history_recovery_preflight_v13/run_manifest.json"
V21_SCHEDULE = ROOT / "artifacts/acl2027_phase2_heldout_activation_preflight_v21/held_out_schedule.json"
V21_LEDGER = ROOT / "artifacts/acl2027_phase2_heldout_live_v21/ledger.json"
V22_SCHEDULE = ROOT / "artifacts/acl2027_phase2_heldout_recovery_preflight_v22/held_out_recovery_schedule.json"
V22_GOLD = ROOT / "artifacts/acl2027_phase2_heldout_recovery_preflight_v22/combined_held_out_gold.json"
V23_AUDIT = ROOT / "artifacts/acl2027_phase2_heldout_recovery_live_v23/combined_held_out_audit.json"
V23_LEDGER = ROOT / "artifacts/acl2027_phase2_heldout_recovery_live_v23/ledger.json"
V23_RUN_AUDIT = ROOT / "artifacts/acl2027_phase2_heldout_recovery_live_v23/run_audit.json"
V24_MANIFEST = ROOT / "artifacts/acl2027_phase2_post_v23_replication_design_preflight_v24/run_manifest.json"
V24_SCHEDULE = ROOT / "artifacts/acl2027_phase2_post_v23_replication_design_preflight_v24/replication_schedule.json"
V24_GOLD = ROOT / "artifacts/acl2027_phase2_post_v23_replication_design_preflight_v24/replication_private_gold.json"
V25_AUDIT = ROOT / "artifacts/acl2027_phase2_post_v23_replication_live_v25/replication_audit.json"
V25_LEDGER = ROOT / "artifacts/acl2027_phase2_post_v23_replication_live_v25/ledger.json"
V25_RUN_AUDIT = ROOT / "artifacts/acl2027_phase2_post_v23_replication_live_v25/run_audit.json"
V25_CLOSURE = ROOT / "artifacts/acl2027_phase2_post_v23_replication_live_v25/authorization_closure.json"


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
        for key in ("schedule", "rows", "outcomes"):
            if isinstance(value.get(key), list):
                return [row for row in value[key] if isinstance(row, dict)]
    return []


def expected_answers(task: dict[str, Any]) -> list[str]:
    values = task.get("answers") or [task.get("answer")]
    return [str(value) for value in values if value is not None]


def alias_tolerant_correct(answer: str, expected: Iterable[str]) -> bool:
    actual = normalize_answer(answer)
    for value in expected:
        target = normalize_answer(value)
        if actual == target:
            return True
        if actual and target and min(len(actual), len(target)) >= 4 and (actual in target or target in actual):
            return True
    return False


def pair_label(values: dict[str, bool]) -> str:
    typed = values["contextual_typed_prior"]
    global_only = values["global_only"]
    if typed and not global_only:
        return "typed_win"
    if global_only and not typed:
        return "typed_loss"
    return "both_correct" if typed else "both_wrong"


def schedule_map(paths: Iterable[Path]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in paths:
        for row in rows_from(load(path)):
            result[str(row["logical_call_id"])] = row
    return result


def ledger_map(paths: Iterable[Path]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in paths:
        for row in rows_from(load(path)):
            if row.get("status") == "completed":
                result[str(row["logical_call_id"])] = row
    return result


def analyze_dataset(
    name: str,
    audit_path: Path,
    gold_path: Path,
    schedule_paths: tuple[Path, ...],
    ledger_paths: tuple[Path, ...],
) -> dict[str, Any]:
    audit = load(audit_path)
    gold = {str(row["task_id"]): row for row in rows_from(load(gold_path))}
    schedules = schedule_map(schedule_paths)
    ledgers = ledger_map(ledger_paths)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in audit["outcomes"]:
        grouped[str(row["task_id"])].append(row)

    tasks: list[dict[str, Any]] = []
    family_counts: dict[str, Counter[str]] = defaultdict(Counter)
    prompt_chars: dict[str, list[int]] = defaultdict(list)
    strict_pairs: Counter[str] = Counter()
    alias_pairs: Counter[str] = Counter()
    strict_failure_types: Counter[str] = Counter()
    capability = Counter()
    degradation = Counter()

    for task_id, rows in sorted(grouped.items()):
        task = gold[task_id]
        expected = expected_answers(task)
        strict: dict[str, bool] = {}
        alias: dict[str, bool] = {}
        answers: dict[str, str] = {}
        contracts: dict[str, bool] = {}
        lengths: dict[str, int] = {}
        for outcome in rows:
            condition = str(outcome["condition"])
            logical_id = str(outcome["logical_call_id"])
            record = ledgers[logical_id]
            scheduled = schedules[logical_id]
            parsed_answer = ""
            try:
                parsed_answer = str(parse_response(record["raw_response"])["answer"])
            except Exception:
                pass
            strict[condition] = bool(outcome["answer_correct"])
            alias[condition] = bool(outcome["contract_valid"]) and alias_tolerant_correct(parsed_answer, expected)
            answers[condition] = parsed_answer
            contracts[condition] = bool(outcome["contract_valid"])
            body = scheduled.get("canonical_request_body", {})
            lengths[condition] = sum(len(str(message.get("content", ""))) for message in body.get("messages", []))
            prompt_chars[condition].append(lengths[condition])
            family_counts[str(task["skill_family"])][f"{condition}_correct"] += int(strict[condition])

        strict_pair = pair_label(strict)
        alias_pair = pair_label(alias)
        strict_pairs[strict_pair] += 1
        alias_pairs[alias_pair] += 1
        family = str(task["skill_family"])
        family_counts[family]["tasks"] += 1
        family_counts[family][f"strict_{strict_pair}"] += 1
        family_counts[family][f"alias_{alias_pair}"] += 1
        capability["cold_correct"] += int(strict["cold"])
        capability["any_condition_correct"] += int(any(strict.values()))
        capability["all_conditions_wrong"] += int(not any(strict.values()))
        if strict["cold"] and not strict["global_only"]:
            degradation["stratum_tasks"] += 1
            degradation["typed_recovers"] += int(strict["contextual_typed_prior"])
            degradation["copied_global_recovers"] += int(strict["copied_global"])
        if not strict["contextual_typed_prior"]:
            if not contracts["contextual_typed_prior"]:
                strict_failure_types["typed_contract_failure"] += 1
            elif alias["contextual_typed_prior"]:
                strict_failure_types["typed_alias_near_match"] += 1
            else:
                strict_failure_types["typed_wrong_answer"] += 1

        tasks.append({
            "task_id": task_id,
            "task_family": task["task_family"],
            "task_type": task["task_type"],
            "skill_family": family,
            "question": task["question"],
            "expected_answers": expected,
            "strict_pair_outcome": strict_pair,
            "alias_tolerant_pair_outcome": alias_pair,
            "strict_correct": strict,
            "alias_tolerant_correct": alias,
            "answers": answers,
            "prompt_chars": lengths,
        })

    family_summary = {family: dict(counts) for family, counts in sorted(family_counts.items())}
    prompt_summary = {
        condition: {
            "min": min(values),
            "max": max(values),
            "mean": sum(values) / len(values),
        }
        for condition, values in sorted(prompt_chars.items())
    }
    return {
        "dataset": name,
        "tasks": len(tasks),
        "rows": len(audit["outcomes"]),
        "original_gate": audit["eligibility_gate"],
        "original_aggregate_fingerprint": audit["aggregate_fingerprint"],
        "condition_accuracy": audit["condition_accuracy"],
        "original_primary_paired_comparison": audit["primary_paired_comparison"],
        "strict_pair_outcomes": dict(strict_pairs),
        "alias_tolerant_pair_outcomes": dict(alias_pairs),
        "strict_failure_types": dict(strict_failure_types),
        "family_breakdown": family_summary,
        "task_capability": dict(capability),
        "global_prior_degradation": dict(degradation),
        "prompt_chars": prompt_summary,
        "discordant_tasks": [row for row in tasks if row["strict_pair_outcome"] in {"typed_win", "typed_loss"}],
    }


def failure_analysis() -> dict[str, Any]:
    v23 = analyze_dataset("v23", V23_AUDIT, V22_GOLD, (V21_SCHEDULE, V22_SCHEDULE), (V21_LEDGER, V23_LEDGER))
    v25 = analyze_dataset("v25", V25_AUDIT, V24_GOLD, (V24_SCHEDULE,), (V25_LEDGER,))
    bundles = load(V17_PRIORS)
    coverage = load(V13_MANIFEST)["candidate"]
    combined_strict = Counter(v23["strict_pair_outcomes"]) + Counter(v25["strict_pair_outcomes"])
    combined_alias = Counter(v23["alias_tolerant_pair_outcomes"]) + Counter(v25["alias_tolerant_pair_outcomes"])
    alias_changed = sum(
        row["strict_pair_outcome"] != row["alias_tolerant_pair_outcome"]
        for dataset in (v23, v25)
        for row in dataset["discordant_tasks"]
    )
    return {
        "schema_version": VERSION,
        "status": "analysis-complete-old-gates-unchanged",
        "datasets": [v23, v25],
        "combined_strict_pair_outcomes": dict(combined_strict),
        "combined_alias_tolerant_pair_outcomes": dict(combined_alias),
        "diagnostic_conclusions": {
            "no_prior_effect": "The original strict paired evidence is sparse and unstable: v23 was inconclusive and v25 was negative under its frozen loss-count rule.",
            "verifier_alias_sensitivity": {
                "discordant_tasks_changed_by_alias_rule": alias_changed,
                "interpretation": "Alias sensitivity is real but cannot change either frozen historical gate.",
            },
            "typed_coverage": {
                "coverage_status": coverage["coverage_status"],
                "independent_verified_supports": coverage["independent_verified_supports"],
                "global_bundle_examples": len(bundles["global"]["examples"]),
                "typed_bundle_examples": {family: len(bundles["typed"][family]["examples"]) for family in FAMILIES},
                "interpretation": "No family lacked a frozen typed bundle, so absence of typed coverage does not explain the old result.",
            },
            "prompt_length_confound": "Condition prompts have different lengths because their prior bundles differ; v23/v25 did not independently manipulate prompt length, so length is not identifiable as a cause.",
            "task_capability": "Cold and any-condition accuracy are reported separately; capability failure is not treated as evidence for or against prior transfer.",
        },
        "historical_gates_preserved": {"v23": "inconclusive", "v25": "negative"},
    }


def occupied_tasks() -> set[str]:
    occupied = occupied_task_ids()
    # v24 selected the tasks later executed by v25, so they are additive to the v24 helper's
    # through-v23 exclusion set.
    occupied.update(str(row["task_id"]) for row in rows_from(load(V24_GOLD)))
    return occupied


def selector_hash(family: str, task_id: str) -> str:
    return hashlib.sha256(f"phase2-v26:post-v25-failure-analysis:{family}:{task_id}".encode()).hexdigest()


def select_future_tasks() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pools = source_candidates()
    occupied = occupied_tasks()
    selected: list[dict[str, Any]] = []
    families: dict[str, Any] = {}
    for family in FAMILIES:
        available = [row for row in pools[family] if str(row["task_id"]) not in occupied]
        ordered = sorted(available, key=lambda row: (selector_hash(family, str(row["task_id"])), str(row["task_id"])))
        if len(ordered) < TASKS_PER_FAMILY:
            raise RuntimeError(f"insufficient unused v26 tasks for {family}: {len(ordered)}")
        chosen = ordered[:TASKS_PER_FAMILY]
        selected.extend(chosen)
        families[family] = {
            "available_after_all_exclusions": len(ordered),
            "selected": len(chosen),
            "task_ids": [row["task_id"] for row in chosen],
            "selector_hashes": [selector_hash(family, str(row["task_id"])) for row in chosen],
        }
    return selected, {
        "schema_version": VERSION,
        "selector": "80 lowest SHA256(phase2-v26:post-v25-failure-analysis:<family>:<task_id>) per family",
        "families": families,
        "selected_tasks": len(selected),
        "unique_selected_task_ids": len({row["task_id"] for row in selected}),
        "prior_task_overlap": len({str(row["task_id"]) for row in selected} & occupied),
    }


def condition_prior(condition: str, family: str, bundles: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if condition == "cold":
        return "candidate:none:v26", {"slot": "none", "source_scope": "none", "examples": []}
    if condition == "global_only":
        return bundles["global"]["candidate_id"], {"slot": "global", "source_scope": "global", "examples": bundles["global"]["examples"]}
    if condition == "copied_global":
        return f"candidate:copied-global:{family}:v26", {"slot": f"family:{family}", "source_scope": "global_copied", "examples": bundles["global"]["examples"]}
    typed = bundles["typed"][family]
    return typed["candidate_id"], {"slot": f"family:{family}", "source_scope": typed["source_scope"], "examples": typed["examples"]}


def build_future_schedule(tasks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    bundles = load(V17_PRIORS)
    schedule: list[dict[str, Any]] = []
    for task in tasks:
        public = public_task(task)
        family = str(task["skill_family"])
        for condition in CONDITIONS:
            candidate_id, prior = condition_prior(condition, family, bundles)
            prior_text = json.dumps(prior, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            body = {
                "model_id": "qwen3.7-plus",
                "temperature": 0,
                "enable_thinking": False,
                "response_format": {"type": "json_object"},
                "phase": "2",
                "stage": "post_v25_failure_analysis_followup",
                "partition": "independent_failure_analysis_held_out",
                "task_family": task["task_family"],
                "task_type": task["task_type"],
                "skill_family": family,
                "task_id": task["task_id"],
                "public_payload_sha256": stable(public),
                "condition": condition,
                "candidate_id": candidate_id,
                "candidate_version": "phase2-v26-design-only",
                "typed_scope": family,
                "prompt_template_version": "phase2-post-v25-failure-analysis-json-v26",
                "prior_payload_sha256": stable(prior),
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": "Prior bundle:\n" + prior_text + "\n\nQuestion:\n" + task["question"] + "\n\nContext:\n" + json.dumps(task["context"], ensure_ascii=True)},
                ],
            }
            sequence = len(schedule) + 1
            schedule.append({
                "schema_version": VERSION,
                "sequence": sequence,
                "staged_execution_index": sequence,
                "logical_call_id": f"phase2-v26:post_v25_failure_analysis:{family}:{task['task_id']}:{condition}",
                "request_hash": stable(body),
                "provider_response_id": None,
                "partition": body["partition"],
                "stage": body["stage"],
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


def spent_identities() -> dict[str, set[str]]:
    identities = {"logical_call_ids": set(), "request_hashes": set(), "provider_response_ids": set()}
    for directory in ROOT.glob("artifacts/acl2027*"):
        if not directory.is_dir():
            continue
        for name in ("ledger.json", "request_start_ledger.json"):
            path = directory / name
            if not path.exists():
                continue
            for row in rows_from(load(path)):
                logical = str(row.get("logical_call_id", ""))
                request_hash = str(row.get("request_hash", ""))
                provider_id = str(row.get("request_id", "") or row.get("provider_response_id", ""))
                raw = row.get("raw_provider_response")
                if isinstance(raw, dict) and raw.get("id"):
                    provider_id = str(raw["id"])
                if logical:
                    identities["logical_call_ids"].add(logical)
                if request_hash:
                    identities["request_hashes"].add(request_hash)
                if provider_id:
                    identities["provider_response_ids"].add(provider_id)
    return identities


def identity_audit(tasks: list[dict[str, Any]], schedule: list[dict[str, Any]], selection: dict[str, Any]) -> dict[str, Any]:
    spent = spent_identities()
    logical = {row["logical_call_id"] for row in schedule}
    hashes = {row["request_hash"] for row in schedule}
    proposed_provider_ids = {row["provider_response_id"] for row in schedule if row["provider_response_id"]}
    return {
        "schema_version": VERSION,
        "prior_evaluation_task_overlap": selection["prior_task_overlap"],
        "spent_logical_call_ids": len(spent["logical_call_ids"]),
        "spent_request_hashes": len(spent["request_hashes"]),
        "spent_provider_response_ids": len(spent["provider_response_ids"]),
        "proposed_task_ids": len({row["task_id"] for row in tasks}),
        "proposed_logical_call_ids": len(logical),
        "proposed_request_hashes": len(hashes),
        "proposed_provider_response_ids": len(proposed_provider_ids),
        "logical_call_id_overlap": len(logical & spent["logical_call_ids"]),
        "request_hash_overlap": len(hashes & spent["request_hashes"]),
        "provider_response_id_overlap": len(proposed_provider_ids & spent["provider_response_ids"]),
        "future_provider_response_rule": "Every returned provider response id must be non-empty, unique within v26 execution, and absent from the frozen spent-provider-response-id set.",
        "spent_provider_response_id_set_sha256": stable(sorted(spent["provider_response_ids"])),
    }


def source_paths() -> dict[str, Path]:
    return {
        "preflight_source_sha256": SCRIPT,
        "preflight_test_sha256": TEST,
        "v13_manifest_sha256": V13_MANIFEST,
        "v17_prior_bundles_sha256": V17_PRIORS,
        "v21_schedule_sha256": V21_SCHEDULE,
        "v21_ledger_sha256": V21_LEDGER,
        "v22_schedule_sha256": V22_SCHEDULE,
        "v22_gold_sha256": V22_GOLD,
        "v23_audit_sha256": V23_AUDIT,
        "v23_ledger_sha256": V23_LEDGER,
        "v23_run_audit_sha256": V23_RUN_AUDIT,
        "v24_manifest_sha256": V24_MANIFEST,
        "v24_schedule_sha256": V24_SCHEDULE,
        "v24_gold_sha256": V24_GOLD,
        "v25_audit_sha256": V25_AUDIT,
        "v25_ledger_sha256": V25_LEDGER,
        "v25_run_audit_sha256": V25_RUN_AUDIT,
        "v25_closure_sha256": V25_CLOSURE,
    }


def source_bindings() -> dict[str, str]:
    return {name: sha256_file(path) for name, path in source_paths().items()}


def validate() -> dict[str, Any]:
    cfg = load(CONFIG)
    if any(value is not False for value in cfg["execution"].values()):
        raise RuntimeError("v26 execution switches must remain closed")
    if cfg["future_schedule"]["status"] != "not_authorized_design_only" or cfg["future_schedule"]["authorization_artifact_created"] is not False:
        raise RuntimeError("v26 must not create or imply provider authorization")
    actual_bindings = source_bindings()
    if actual_bindings != cfg["bindings"]["source_files"]:
        raise RuntimeError("v26 source binding drift")
    v23, v24, v25 = load(V23_AUDIT), load(V24_MANIFEST), load(V25_AUDIT)
    if v23["aggregate_fingerprint"] != cfg["bindings"]["v23_combined_audit_fingerprint"] or v23["eligibility_gate"] != "inconclusive":
        raise RuntimeError("v23 binding or gate drift")
    if v24["aggregate_fingerprint"] != cfg["bindings"]["v24_design_fingerprint"]:
        raise RuntimeError("v24 design binding drift")
    if v25["aggregate_fingerprint"] != cfg["bindings"]["v25_replication_audit_fingerprint"] or v25["eligibility_gate"] != "negative":
        raise RuntimeError("v25 binding or gate drift")

    analysis = failure_analysis()
    tasks, selection = select_future_tasks()
    schedule, private_gold = build_future_schedule(tasks)
    identities = identity_audit(tasks, schedule, selection)
    if len(tasks) != 400 or len({row["task_id"] for row in tasks}) != 400:
        raise RuntimeError("v26 future task count drift")
    if {family: sum(row["skill_family"] == family for row in tasks) for family in FAMILIES} != {family: TASKS_PER_FAMILY for family in FAMILIES}:
        raise RuntimeError("v26 future family balance drift")
    if len(schedule) != 1600 or len({row["logical_call_id"] for row in schedule}) != 1600 or len({row["request_hash"] for row in schedule}) != 1600:
        raise RuntimeError("v26 future schedule identity drift")
    if {condition: sum(row["condition"] == condition for row in schedule) for condition in CONDITIONS} != {condition: 400 for condition in CONDITIONS}:
        raise RuntimeError("v26 future condition balance drift")
    if [row["staged_execution_index"] for row in schedule] != list(range(1, 1601)):
        raise RuntimeError("v26 exact-prefix index drift")
    if any(contains_forbidden_gold_key(row["canonical_request_body"]) for row in schedule):
        raise RuntimeError("v26 private gold leaked into request")
    if any(len({row["prior_payload_sha256"] for row in schedule if row["task_id"] == task["task_id"]}) != 4 for task in tasks):
        raise RuntimeError("v26 condition semantics are not distinct")
    if any(identities[key] != 0 for key in ("prior_evaluation_task_overlap", "logical_call_id_overlap", "request_hash_overlap", "provider_response_id_overlap")):
        raise RuntimeError("v26 overlap audit failed")

    documents = {
        "failure_analysis.json": analysis,
        "future_schedule.json": {"schema_version": VERSION, "schedule": schedule},
        "future_private_gold.json": private_gold,
        "task_selection_audit.json": selection,
        "identity_overlap_audit.json": identities,
    }
    result = {
        "schema_version": VERSION,
        "experiment": cfg["experiment"],
        "status": "design-preflight-passed-closed",
        "authorization_status": "not-authorized",
        "authorization_artifact_created": False,
        "config_sha256": sha256_file(CONFIG),
        "source_bindings": actual_bindings,
        "v23_gate_preserved": "inconclusive",
        "v25_gate_preserved": "negative",
        "historical_tasks_analyzed": 160,
        "future_task_count": len(tasks),
        "future_tasks_per_family": TASKS_PER_FAMILY,
        "future_logical_calls": len(schedule),
        "future_condition_counts": {condition: 400 for condition in CONDITIONS},
        "prior_task_overlap": 0,
        "prior_logical_call_overlap": 0,
        "prior_request_hash_overlap": 0,
        "prior_provider_response_id_overlap": 0,
        "decision_rules": cfg["decision_rules"],
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "paid_api_calls": 0,
        "formal_scaling_calls": 0,
        "documents": {name: rendered_sha256(value) for name, value in documents.items()},
    }
    result["aggregate_fingerprint"] = stable(result)
    return result


def report_text(result: dict[str, Any], analysis: dict[str, Any], selection: dict[str, Any]) -> str:
    v23, v25 = analysis["datasets"]
    capacities = ", ".join(f"{family}={selection['families'][family]['available_after_all_exclusions']}" for family in FAMILIES)
    alias_changed = analysis["diagnostic_conclusions"]["verifier_alias_sensitivity"]["discordant_tasks_changed_by_alias_rule"]
    return (
        "# ACL 2027 Phase 2 post-v25 failure-analysis design preflight v26\n\n"
        "## Scope\n\n"
        "This is a zero-network, design-only preflight. It preserves the v23 inconclusive gate and v25 negative gate, creates no authorization, and makes no provider, model, paid, or formal-scaling call.\n\n"
        "## Frozen failure analysis\n\n"
        f"v23 strict paired outcomes were `{v23['strict_pair_outcomes']}` and v25 outcomes were `{v25['strict_pair_outcomes']}`. Alias-tolerant sensitivity changes `{alias_changed}` historical discordant classification(s), including exact-match title/alias cases, but does not rescore or re-gate either completed phase. All families had frozen typed bundles with 10 examples and independently verified support; prompt length remains confounded with condition; cold/any-condition capability is reported separately.\n\n"
        "## Falsifiable follow-up\n\n"
        "The frozen hypothesis is that a reusable typed-prior effect must survive both strict and alias-tolerant scoring and appear as recovery from global-prior degradation, not isolated answer-string flips. The independent schedule contains 400 new tasks, 80 per skill family, and 1,600 four-condition requests. The positive, negative, and inconclusive rules are frozen in the config before any future execution.\n\n"
        f"Available candidates after exclusions: `{capacities}`. Task, logical-call, request-hash, and proposed provider-response-ID overlaps are all zero.\n\n"
        "## Execution boundary\n\n"
        "The schedule is not authorized. Any future execution requires a separately versioned explicit authorization with exact model, attempts, temperature, retries, max_tokens policy, response format, pacing, stage and cumulative CNY ceilings, and forbidden later stages.\n\n"
        "## Integrity\n\n"
        f"Aggregate fingerprint: `{result['aggregate_fingerprint']}`. Network/provider/model/paid/formal-scaling counters: `0/0/0/0/0`. Authorization status: `not-authorized`.\n"
    )


def write_artifact(result: dict[str, Any]) -> None:
    ARTIFACT.mkdir(parents=False, exist_ok=False)
    analysis = failure_analysis()
    tasks, selection = select_future_tasks()
    schedule, private_gold = build_future_schedule(tasks)
    identities = identity_audit(tasks, schedule, selection)
    documents = {
        "failure_analysis.json": analysis,
        "future_schedule.json": {"schema_version": VERSION, "schedule": schedule},
        "future_private_gold.json": private_gold,
        "task_selection_audit.json": selection,
        "identity_overlap_audit.json": identities,
        "run_manifest.json": result,
    }
    for name, value in documents.items():
        (ARTIFACT / name).write_text(render(value), encoding="utf-8", newline="\n")
    REPORT.write_text(report_text(result, analysis, selection), encoding="utf-8", newline="\n")


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
