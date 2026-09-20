#!/usr/bin/env python3
"""Offline TG9 Stage-A audit of frozen TG8 double-object failures.

This script never imports or resets the environment. It only reads the sealed
TG8 row JSON files, selector source, and cluster analysis, then writes a new
TG9-scoped task-level mechanism audit.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "tg9-stage-a-tg8-failure-audit-v1"
TARGET_FAMILY = "pick_two_obj_and_place"
TARGET_CONDITION = "observable_subgoal_anti_cycle"

DEFAULT_ROWS_DIR = (
    ROOT
    / "artifacts"
    / "acl2027_tracegraph_tg8_durable_v2"
    / "independent_20260916_manual_v1"
    / "rows"
)
DEFAULT_SELECTOR = ROOT / "scripts" / "run_acl2027_tracegraph_tg8_observable_subgoal_selector_v3.py"
DEFAULT_ANALYSIS = (
    ROOT
    / "artifacts"
    / "acl2027_tracegraph_tg8_durable_v2"
    / "analysis_20260917_manual_v1"
    / "analysis.json"
)
DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "acl2027_tracegraph_tg9_failure_audit_v1"
DEFAULT_REPORT = ROOT / "paper" / "acl2027" / "results" / "tracegraph_tg9_failure_audit_v1.md"

EXPECTED_SELECTOR_SHA256 = "6aae3a8539594bdb65bdeab92f9d82c2de9ac0e287f036af1e83157751636622"
EXPECTED_ANALYSIS_SHA256 = "da3a08f94a0a0198b0fc3ec67e0b26903d4186366c5ed7486009aae6da8f55a9"
EXPECTED_TOTAL_ROWS = 360
EXPECTED_TARGET_ROWS = 30
EXPECTED_TASK_IDENTITIES = 10
EXPECTED_REPLICATES = 3

PICKUP_RE = re.compile(
    r"^take\s+(?P<object_type>.+?)\s+(?P<object_id>\d+)\s+from\s+"
    r"(?P<container_type>.+?)\s+(?P<container_id>\d+)$",
    re.IGNORECASE,
)
PUT_RE = re.compile(
    r"^move\s+(?P<object_type>.+?)\s+(?P<object_id>\d+)\s+to\s+"
    r"(?P<container_type>.+?)\s+(?P<container_id>\d+)$",
    re.IGNORECASE,
)
OPEN_CLOSE_RE = re.compile(
    r"^(?P<verb>open|close)\s+(?P<container_type>.+?)\s+(?P<container_id>\d+)$",
    re.IGNORECASE,
)
TEMPLATE_RE = re.compile(
    r"^pick_two_obj_and_place-(?P<object_type>.+?)-None-(?P<destination_type>.+)$",
    re.IGNORECASE,
)


class AuditError(RuntimeError):
    """Raised when the frozen TG8 evidence no longer matches the audit contract."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def normalize_entity(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def instance_signature(entity_type: str, instance_id: str | int) -> str:
    return f"{normalize_entity(entity_type)}#{int(instance_id)}"


def parse_action_event(action: str) -> dict[str, Any] | None:
    """Parse only the observable ALFWorld action string used in a row trace."""

    normalized = normalize_text(action)
    match = PICKUP_RE.fullmatch(normalized)
    if match:
        fields = match.groupdict()
        return {
            "action_family": "PickupObject",
            "action": normalized,
            "object_type": normalize_entity(fields["object_type"]),
            "object_instance_signature": instance_signature(
                fields["object_type"], fields["object_id"]
            ),
            "source_type": normalize_entity(fields["container_type"]),
            "source_signature": instance_signature(
                fields["container_type"], fields["container_id"]
            ),
        }

    match = PUT_RE.fullmatch(normalized)
    if match:
        fields = match.groupdict()
        return {
            "action_family": "PutObject",
            "action": normalized,
            "object_type": normalize_entity(fields["object_type"]),
            "object_instance_signature": instance_signature(
                fields["object_type"], fields["object_id"]
            ),
            "destination_type": normalize_entity(fields["container_type"]),
            "destination_signature": instance_signature(
                fields["container_type"], fields["container_id"]
            ),
        }

    match = OPEN_CLOSE_RE.fullmatch(normalized)
    if match:
        fields = match.groupdict()
        family = "OpenObject" if fields["verb"].lower() == "open" else "CloseObject"
        return {
            "action_family": family,
            "action": normalized,
            "container_type": normalize_entity(fields["container_type"]),
            "container_signature": instance_signature(
                fields["container_type"], fields["container_id"]
            ),
        }
    return None


def task_entities(row: dict[str, Any]) -> tuple[str, str]:
    match = TEMPLATE_RE.fullmatch(str(row.get("template_key", "")))
    if not match:
        raise AuditError(f"unexpected double-object template: {row.get('template_key')!r}")
    target_object = normalize_entity(match.group("object_type"))
    destination = normalize_entity(match.group("destination_type"))

    transitions = row.get("transitions") or []
    if not transitions:
        raise AuditError(f"row {row.get('run_id')} has no transitions")
    subgoals = transitions[0].get("subgoal_ledger", {}).get("subgoals", [])
    pickup = next((x for x in subgoals if x.get("id") == "pickup_1"), None)
    put = next((x for x in subgoals if x.get("id") == "put_1"), None)
    if pickup is None or put is None:
        raise AuditError(f"row {row.get('run_id')} lacks the frozen two-object ledger")
    pickup_tokens = {normalize_entity(x) for x in pickup.get("entity_tokens", [])}
    put_tokens = {normalize_entity(x) for x in put.get("entity_tokens", [])}
    if target_object not in pickup_tokens or target_object not in put_tokens or destination not in put_tokens:
        raise AuditError(
            f"template/ledger entity mismatch for task {row.get('task_identity')}"
        )
    return target_object, destination


def round_record(
    row: dict[str, Any], slot: int, target_object: str
) -> dict[str, Any]:
    pickup_id = f"pickup_{slot}"
    put_id = f"put_{slot}"
    pickup: dict[str, Any] | None = None
    put: dict[str, Any] | None = None
    for transition in row["transitions"]:
        event = parse_action_event(transition["terminal_action_decision"])
        if event is None or event.get("object_type") != target_object:
            continue
        if (
            pickup is None
            and transition.get("pending_subgoal_id") == pickup_id
            and event["action_family"] == "PickupObject"
        ):
            pickup = {"step": transition["step"], **event}
        if (
            put is None
            and transition.get("pending_subgoal_id") == put_id
            and event["action_family"] == "PutObject"
        ):
            put = {"step": transition["step"], **event}
    return {
        "slot": slot,
        "pickup_step": None if pickup is None else pickup["step"],
        "pickup_action": None if pickup is None else pickup["action"],
        "object_instance_signature": None
        if pickup is None
        else pickup["object_instance_signature"],
        "source_signature": None if pickup is None else pickup["source_signature"],
        "put_step": None if put is None else put["step"],
        "put_action": None if put is None else put["action"],
        "destination_signature": None if put is None else put["destination_signature"],
    }


def relevant_open_events(
    row: dict[str, Any], destination_type: str
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for transition in row["transitions"]:
        pending = transition.get("pending_subgoal_id")
        if not isinstance(pending, str) or not pending.startswith("search_destination"):
            continue
        admissible = {
            normalize_text(x)
            for x in transition.get("runtime_inputs", {}).get("admissible_actions", [])
        }
        for rejection in transition.get("eligibility_rejections", []):
            action = normalize_text(str(rejection.get("action", "")))
            event = parse_action_event(action)
            if (
                event is None
                or event["action_family"] != "OpenObject"
                or event["container_type"] != destination_type
            ):
                continue
            events.append(
                {
                    "step": transition["step"],
                    "pending_subgoal_id": pending,
                    "action": action,
                    "container_signature": event["container_signature"],
                    "present_in_admissible_actions": action in admissible,
                    "eligibility_rejected": True,
                    "rejection_reason": rejection.get("reason"),
                    "selected_action": transition["terminal_action_decision"],
                }
            )
    return events


def transition_at_step(row: dict[str, Any], step: int) -> dict[str, Any]:
    for transition in row["transitions"]:
        if transition.get("step") == step:
            return transition
    raise AuditError(f"missing transition step {step} in row {row.get('run_id')}")


def hypothesis_statuses(
    *,
    same_instance: bool | None,
    same_source_as_destination: bool | None,
    ledger_complete_but_env_fail: bool,
    closed_container_stall: bool,
    condition: str,
) -> dict[str, dict[str, str]]:
    h1_support = bool(
        same_instance and same_source_as_destination and ledger_complete_but_env_fail
    )
    h2_support = closed_container_stall
    h4_support = condition == TARGET_CONDITION and (h1_support or h2_support)
    return {
        "H1_object_instance_binding": {
            "status": "support" if h1_support else "evidence_insufficient",
            "evidence": (
                "the second counted pickup reused the first placed object instance"
                if h1_support
                else "the trajectory did not reach an auditable second-object pickup"
            ),
        },
        "H2_open_close_coverage": {
            "status": "support" if h2_support else "evidence_insufficient",
            "evidence": (
                "a task-relevant legal open action was rejected while destination search stalled"
                if h2_support
                else "no task-terminal closed-destination candidate gap was observed"
            ),
        },
        "H3_complementarity": {
            "status": "evidence_insufficient",
            "evidence": "the frozen TG8 trace is observational and does not cross both TG9 factors",
        },
        "H4_anti_cycle_not_primary_root": {
            "status": "support" if h4_support else "evidence_insufficient",
            "evidence": (
                "failure persisted under observable_subgoal_anti_cycle with a non-cycle mechanism"
                if h4_support
                else "no classified residual mechanism was available"
            ),
        },
    }


def classify_identity(row: dict[str, Any]) -> dict[str, Any]:
    if row.get("task_family") != TARGET_FAMILY:
        raise AuditError("classify_identity received a non-double-object row")
    if row.get("condition") != TARGET_CONDITION:
        raise AuditError("classify_identity received the wrong condition")
    if row.get("success"):
        raise AuditError("Stage-A target row unexpectedly succeeded")

    target_object, destination_type = task_entities(row)
    first_round = round_record(row, 1, target_object)
    second_round = round_record(row, 2, target_object)
    open_events = relevant_open_events(row, destination_type)
    if any(not x["present_in_admissible_actions"] for x in open_events):
        raise AuditError("eligibility rejection references an action absent from admissible_actions")

    first_instance = first_round["object_instance_signature"]
    second_instance = second_round["object_instance_signature"]
    same_instance = (
        None
        if first_instance is None or second_instance is None
        else first_instance == second_instance
    )
    first_destination = first_round["destination_signature"]
    second_source = second_round["source_signature"]
    same_source_as_destination = (
        None
        if first_destination is None or second_source is None
        else first_destination == second_source
    )

    final_ledger = row["transitions"][-1]["subgoal_ledger"]
    ledger_complete = not final_ledger.get("unresolved_subgoal_ids")
    ledger_complete_but_env_fail = ledger_complete and not bool(row["success"])
    final_pending = final_ledger.get("pending_subgoal_id")
    closed_container_stall = bool(
        not ledger_complete
        and isinstance(final_pending, str)
        and final_pending.startswith("search_destination")
        and open_events
    )
    second_source_same_as_first_destination = bool(same_source_as_destination)
    instance_reuse = bool(
        same_instance
        and second_source_same_as_first_destination
        and ledger_complete_but_env_fail
    )
    candidate_gap = bool(closed_container_stall and open_events)

    if instance_reuse:
        divergence_step = second_round["pickup_step"]
        divergence_reason = "second_pickup_reused_first_placed_instance"
        primary_mechanism = "object_instance_reuse"
    elif closed_container_stall:
        divergence_step = open_events[0]["step"]
        divergence_reason = "task_relevant_open_action_rejected"
        primary_mechanism = "closed_container_skill_gap"
    else:
        divergence_step = row["transitions"][-1]["step"]
        divergence_reason = "unclassified_terminal_failure"
        primary_mechanism = "other"

    divergence = transition_at_step(row, int(divergence_step))
    divergence_ledger = divergence["subgoal_ledger"]
    hypotheses = hypothesis_statuses(
        same_instance=same_instance,
        same_source_as_destination=same_source_as_destination,
        ledger_complete_but_env_fail=ledger_complete_but_env_fail,
        closed_container_stall=closed_container_stall,
        condition=row["condition"],
    )

    return {
        "task_identity": row["task_identity"],
        "split": row["split"],
        "task_family": row["task_family"],
        "template_key": row["template_key"],
        "gamefile_sha256": row["gamefile_sha256"],
        "condition": row["condition"],
        "environment_success": bool(row["success"]),
        "target_object_type": target_object,
        "target_destination_type": destination_type,
        "first_divergence": {
            "step": divergence_step,
            "reason": divergence_reason,
            "selected_action": divergence["terminal_action_decision"],
            "pending_subgoal_id": divergence.get("pending_subgoal_id"),
            "completed_subgoal_ids": divergence_ledger.get("completed_subgoal_ids", []),
            "unresolved_subgoal_ids": divergence_ledger.get("unresolved_subgoal_ids", []),
        },
        "first_round": first_round,
        "second_round": second_round,
        "second_instance_same_as_first": same_instance,
        "second_source_is_distinct": None
        if same_source_as_destination is None
        else not same_source_as_destination,
        "relevant_open_action_present_in_admissible": bool(open_events),
        "relevant_open_action_eligibility_rejected": bool(open_events),
        "relevant_open_events": open_events,
        "final_ledger": {
            "completed_subgoal_ids": final_ledger.get("completed_subgoal_ids", []),
            "unresolved_subgoal_ids": final_ledger.get("unresolved_subgoal_ids", []),
            "pending_subgoal_id": final_pending,
        },
        "mechanism_flags": {
            "ledger_complete_but_env_fail": ledger_complete_but_env_fail,
            "closed_container_stall": closed_container_stall,
            "second_source_same_as_first_destination": second_source_same_as_first_destination,
            "candidate_gap": candidate_gap,
            "instance_reuse": instance_reuse,
        },
        "primary_failure_mechanism": primary_mechanism,
        "hypotheses": hypotheses,
    }


def trajectory_fingerprint(row: dict[str, Any]) -> str:
    payload = {
        "success": row["success"],
        "stop_reason": row["stop_reason"],
        "hard_invariant_violation": row["hard_invariant_violation"],
        "metrics": row["metrics"],
        "transitions": row["transitions"],
    }
    return canonical_sha256(payload)


def load_frozen_inputs(
    rows_dir: Path, selector_path: Path, analysis_path: Path
) -> tuple[list[tuple[Path, dict[str, Any]]], dict[str, Any], dict[str, Any]]:
    for path in (rows_dir, selector_path, analysis_path):
        if not path.exists():
            raise AuditError(f"missing frozen input: {path}")
    selector_sha = sha256_file(selector_path)
    analysis_sha = sha256_file(analysis_path)
    if selector_sha != EXPECTED_SELECTOR_SHA256:
        raise AuditError(f"TG8 selector SHA mismatch: {selector_sha}")
    if analysis_sha != EXPECTED_ANALYSIS_SHA256:
        raise AuditError(f"TG8 analysis SHA mismatch: {analysis_sha}")

    row_paths = sorted(rows_dir.glob("*.json"))
    if len(row_paths) != EXPECTED_TOTAL_ROWS:
        raise AuditError(f"expected {EXPECTED_TOTAL_ROWS} TG8 rows, found {len(row_paths)}")
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    if analysis.get("status") != "complete" or analysis.get("rows") != EXPECTED_TOTAL_ROWS:
        raise AuditError("TG8 cluster analysis is not the sealed 360-row result")
    sealed_hashes = analysis.get("immutable_input_sha256", {})

    loaded: list[tuple[Path, dict[str, Any]]] = []
    row_hash_entries: list[dict[str, str]] = []
    for path in row_paths:
        relative = display_path(path)
        digest = sha256_file(path)
        if sealed_hashes.get(relative) != digest:
            raise AuditError(f"row hash is not sealed by TG8 analysis: {relative}")
        row_hash_entries.append({"path": relative, "sha256": digest})
        loaded.append((path, json.loads(path.read_text(encoding="utf-8"))))

    input_binding = {
        "selector": {"path": display_path(selector_path), "sha256": selector_sha},
        "analysis": {"path": display_path(analysis_path), "sha256": analysis_sha},
        "rows_dir": display_path(rows_dir),
        "row_count": len(row_hash_entries),
        "rows_manifest_sha256": canonical_sha256(row_hash_entries),
    }
    return loaded, analysis, input_binding


def build_audit(
    rows_dir: Path = DEFAULT_ROWS_DIR,
    selector_path: Path = DEFAULT_SELECTOR,
    analysis_path: Path = DEFAULT_ANALYSIS,
) -> dict[str, Any]:
    loaded, analysis, input_binding = load_frozen_inputs(
        rows_dir, selector_path, analysis_path
    )
    relevant = [
        (path, row)
        for path, row in loaded
        if row.get("task_family") == TARGET_FAMILY
        and row.get("condition") == TARGET_CONDITION
    ]
    if len(relevant) != EXPECTED_TARGET_ROWS:
        raise AuditError(f"expected {EXPECTED_TARGET_ROWS} target rows, found {len(relevant)}")

    grouped: dict[str, list[tuple[Path, dict[str, Any]]]] = defaultdict(list)
    for path, row in relevant:
        if row.get("success"):
            raise AuditError("TG8 target condition unexpectedly contains a success")
        if row.get("hard_invariant_violation") is not None:
            raise AuditError("TG8 target condition contains a hard invariant violation")
        grouped[row["task_identity"]].append((path, row))
    if len(grouped) != EXPECTED_TASK_IDENTITIES:
        raise AuditError(
            f"expected {EXPECTED_TASK_IDENTITIES} task identities, found {len(grouped)}"
        )

    task_audits: list[dict[str, Any]] = []
    for task_identity, values in sorted(grouped.items()):
        values.sort(key=lambda item: item[1]["replicate_index"])
        replicate_indices = [row["replicate_index"] for _, row in values]
        if replicate_indices != list(range(EXPECTED_REPLICATES)):
            raise AuditError(
                f"task {task_identity} has unexpected replicates {replicate_indices}"
            )
        fingerprints = [trajectory_fingerprint(row) for _, row in values]
        if len(set(fingerprints)) != 1:
            raise AuditError(f"task {task_identity} has non-identical deterministic replicates")
        classified = classify_identity(values[0][1])
        classified["replicate_evidence"] = {
            "replicate_count": len(values),
            "identical_trajectory": True,
            "trajectory_sha256": fingerprints[0],
            "rows": [
                {
                    "replicate_index": row["replicate_index"],
                    "seed": row["seed"],
                    "path": display_path(path),
                    "sha256": sha256_file(path),
                }
                for path, row in values
            ],
        }
        task_audits.append(classified)

    mechanism_counts = Counter(x["primary_failure_mechanism"] for x in task_audits)
    flag_counts = {
        flag: sum(bool(x["mechanism_flags"][flag]) for x in task_audits)
        for flag in (
            "ledger_complete_but_env_fail",
            "closed_container_stall",
            "second_source_same_as_first_destination",
            "candidate_gap",
            "instance_reuse",
        )
    }
    hypothesis_counts: dict[str, dict[str, int]] = {}
    for hypothesis in task_audits[0]["hypotheses"]:
        hypothesis_counts[hypothesis] = dict(
            Counter(x["hypotheses"][hypothesis]["status"] for x in task_audits)
        )

    if mechanism_counts != Counter(
        {"object_instance_reuse": 7, "closed_container_skill_gap": 3}
    ):
        raise AuditError(f"unexpected TG8 mechanism partition: {dict(mechanism_counts)}")
    if analysis.get("task_count") != 30:
        raise AuditError("TG8 analysis task count changed")

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "complete_zero_execution_offline_audit",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "source_phase": "TG8",
            "target_phase": "TG9-Stage-A",
            "task_family": TARGET_FAMILY,
            "condition": TARGET_CONDITION,
            "unit_of_analysis": "task_identity",
            "runtime_or_environment_execution": False,
            "new_episodes": 0,
            "new_actions": 0,
            "network_calls": 0,
            "provider_calls": 0,
            "model_calls": 0,
            "api_calls": 0,
            "paid_calls": 0,
        },
        "immutable_inputs": input_binding,
        "summary": {
            "source_rows": EXPECTED_TOTAL_ROWS,
            "audited_rows": len(relevant),
            "task_identities": len(task_audits),
            "successful_task_identities": sum(x["environment_success"] for x in task_audits),
            "identical_three_replicate_task_groups": sum(
                x["replicate_evidence"]["identical_trajectory"] for x in task_audits
            ),
            "primary_failure_mechanism_counts": dict(sorted(mechanism_counts.items())),
            "mechanism_flag_counts": flag_counts,
            "hypothesis_status_counts": hypothesis_counts,
            "all_failures_exclusively_classified": mechanism_counts.get("other", 0) == 0,
            "claim_scope": (
                "retrospective frozen-trace mechanism diagnosis; not a causal factorial result"
            ),
        },
        "task_audits": task_audits,
    }


def csv_text(task_audits: Iterable[dict[str, Any]]) -> str:
    fields = [
        "task_identity",
        "split",
        "template_key",
        "target_object_type",
        "target_destination_type",
        "primary_failure_mechanism",
        "first_divergence_step",
        "first_divergence_reason",
        "pending_subgoal_id",
        "first_pickup_action",
        "first_put_action",
        "second_pickup_action",
        "second_put_action",
        "second_instance_same_as_first",
        "second_source_is_distinct",
        "relevant_open_action_present_in_admissible",
        "relevant_open_action_eligibility_rejected",
        "ledger_complete_but_env_fail",
        "closed_container_stall",
        "second_source_same_as_first_destination",
        "candidate_gap",
        "H1_status",
        "H2_status",
        "H3_status",
        "H4_status",
    ]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for task in task_audits:
        flags = task["mechanism_flags"]
        hypotheses = task["hypotheses"]
        writer.writerow(
            {
                "task_identity": task["task_identity"],
                "split": task["split"],
                "template_key": task["template_key"],
                "target_object_type": task["target_object_type"],
                "target_destination_type": task["target_destination_type"],
                "primary_failure_mechanism": task["primary_failure_mechanism"],
                "first_divergence_step": task["first_divergence"]["step"],
                "first_divergence_reason": task["first_divergence"]["reason"],
                "pending_subgoal_id": task["first_divergence"]["pending_subgoal_id"],
                "first_pickup_action": task["first_round"]["pickup_action"],
                "first_put_action": task["first_round"]["put_action"],
                "second_pickup_action": task["second_round"]["pickup_action"],
                "second_put_action": task["second_round"]["put_action"],
                "second_instance_same_as_first": task["second_instance_same_as_first"],
                "second_source_is_distinct": task["second_source_is_distinct"],
                "relevant_open_action_present_in_admissible": task[
                    "relevant_open_action_present_in_admissible"
                ],
                "relevant_open_action_eligibility_rejected": task[
                    "relevant_open_action_eligibility_rejected"
                ],
                "ledger_complete_but_env_fail": flags["ledger_complete_but_env_fail"],
                "closed_container_stall": flags["closed_container_stall"],
                "second_source_same_as_first_destination": flags[
                    "second_source_same_as_first_destination"
                ],
                "candidate_gap": flags["candidate_gap"],
                "H1_status": hypotheses["H1_object_instance_binding"]["status"],
                "H2_status": hypotheses["H2_open_close_coverage"]["status"],
                "H3_status": hypotheses["H3_complementarity"]["status"],
                "H4_status": hypotheses["H4_anti_cycle_not_primary_root"]["status"],
            }
        )
    return stream.getvalue()


def markdown_report(audit: dict[str, Any]) -> str:
    summary = audit["summary"]
    inputs = audit["immutable_inputs"]
    rows = []
    for task in audit["task_audits"]:
        first = task["first_round"]["pickup_action"] or "-"
        second = task["second_round"]["pickup_action"] or "-"
        open_action = (
            task["relevant_open_events"][0]["action"]
            if task["relevant_open_events"]
            else "-"
        )
        rows.append(
            "| {identity} | {split} | {template} | {step} | {mechanism} | `{first}` | `{second}` | `{open_action}` |".format(
                identity=task["task_identity"][:12],
                split=task["split"],
                template=task["template_key"].replace("pick_two_obj_and_place-", ""),
                step=task["first_divergence"]["step"],
                mechanism=task["primary_failure_mechanism"],
                first=first,
                second=second,
                open_action=open_action,
            )
        )
    return "\n".join(
        [
            "# TG9 Stage-A：TG8 双物体失败机制冻结审计",
            "",
            f"生成时间：`{audit['created_at']}`",
            "",
            "## 审计边界",
            "",
            "本审计只读取 TG8 已冻结的 360 条轨迹、selector v3 和任务聚类分析。",
            "未重置环境、未执行动作、未启动 episode，也未发生 network/provider/model/API/paid call。",
            "分析单位是 `task_identity`；三个确定性重复仅用于轨迹一致性检查，不作为独立样本。",
            "",
            "## 冻结输入",
            "",
            f"- selector：`{inputs['selector']['path']}`，SHA-256 `{inputs['selector']['sha256']}`",
            f"- TG8 analysis：`{inputs['analysis']['path']}`，SHA-256 `{inputs['analysis']['sha256']}`",
            f"- rows manifest：{inputs['row_count']} rows，SHA-256 `{inputs['rows_manifest_sha256']}`",
            "",
            "## 结果",
            "",
            f"`observable_subgoal_anti_cycle` 在双物体任务中为 **0/{summary['task_identities']}** 个任务身份成功。",
            "10 个任务身份的三个重复轨迹均完全一致。失败可被互斥地分为：",
            "",
            f"- **对象实例重复计数：{summary['primary_failure_mechanism_counts'].get('object_instance_reuse', 0)}/10。** "
            "第一对象放入目标后，第二轮从第一轮目标位置重新拾取同一实例，账本随后完成但环境仍失败。",
            f"- **关闭容器技能缺口：{summary['primary_failure_mechanism_counts'].get('closed_container_skill_gap', 0)}/10。** "
            "目标容器的合法 `open` 动作出现在 `admissible_actions` 中，却被资格过滤拒绝，轨迹停在 `search_destination_1`。",
            "",
            "| task | split | template | 首次偏离 step | 主机制 | 第一轮 pickup | 第二轮 pickup | 相关 open |",
            "|---|---|---|---:|---|---|---|---|",
            *rows,
            "",
            "## 假设判定",
            "",
            "- **H1（对象实例绑定缺失）得到支持。** 7/10 个身份同时满足同一对象签名、第二来源等于第一目标位置、账本完成但环境失败。",
            "- **H2（Open/Close 覆盖不足）得到支持。** 3/10 个身份出现任务相关、合法且被拒绝的 `open` 动作，并以关闭容器停滞结束。",
            "- **H3（两机制互补）证据不足。** TG8 是观察性冻结轨迹，没有交叉操控两个因素，不能由本审计估计交互效应。",
            "- **H4（防循环不是主要根因）得到任务内支持。** 10/10 个失败均发生在 anti-cycle 条件下，且存在实例重复或技能缺口这一非短二周期机制。",
            "",
            "## 结论边界",
            "",
            "该结果是回顾性机制诊断，不是 TG9 2×2 因果实验的结果。它支持把对象实例绑定与 Open/Close 覆盖作为可证伪因素，",
            "但不能证明二者是唯一根因、不能估计交互效应，也不能外推到其他数据集或其他智能体。TG8 的实际 horizon 为 50 steps，",
            "75-step sensitivity 不可用。",
            "",
        ]
    )


def write_outputs(
    audit: dict[str, Any], output_dir: Path, report_path: Path
) -> dict[str, Any]:
    if output_dir.exists():
        raise AuditError(f"refusing to overwrite output directory: {output_dir}")
    if report_path.exists():
        raise AuditError(f"refusing to overwrite report: {report_path}")
    output_dir.mkdir(parents=True, exist_ok=False)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    audit_path = output_dir / "failure_audit.json"
    csv_path = output_dir / "failure_audit.csv"
    audit_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    csv_path.write_text(csv_text(audit["task_audits"]), encoding="utf-8")
    report_path.write_text(markdown_report(audit), encoding="utf-8")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "complete_zero_execution_offline_audit",
        "created_at": audit["created_at"],
        "script": {
            "path": display_path(Path(__file__)),
            "sha256": sha256_file(Path(__file__)),
        },
        "immutable_inputs": audit["immutable_inputs"],
        "outputs": {
            "failure_audit": {
                "path": display_path(audit_path),
                "sha256": sha256_file(audit_path),
            },
            "failure_audit_csv": {
                "path": display_path(csv_path),
                "sha256": sha256_file(csv_path),
            },
            "report": {
                "path": display_path(report_path),
                "sha256": sha256_file(report_path),
            },
        },
        "counts": audit["summary"],
        "episodes_run": 0,
        "actions_taken": 0,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "api_calls": 0,
        "paid_calls": 0,
        "tg8_inputs_mutated": False,
    }
    manifest_path = output_dir / "completion_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows-dir", type=Path, default=DEFAULT_ROWS_DIR)
    parser.add_argument("--selector", type=Path, default=DEFAULT_SELECTOR)
    parser.add_argument("--analysis", type=Path, default=DEFAULT_ANALYSIS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    audit = build_audit(args.rows_dir, args.selector, args.analysis)
    manifest = write_outputs(audit, args.output_dir, args.report)
    print(
        canonical_json(
            {
                "status": manifest["status"],
                "task_identities": audit["summary"]["task_identities"],
                "mechanisms": audit["summary"]["primary_failure_mechanism_counts"],
                "output_dir": display_path(args.output_dir),
                "report": display_path(args.report),
                "episodes_run": 0,
                "actions_taken": 0,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
