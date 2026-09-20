#!/usr/bin/env python3
"""TG9 two-object mechanism selector with observable-only instance binding."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_acl2027_tracegraph_tg6_local_execution_runner_v1 as base  # noqa: E402
from scripts import run_acl2027_tracegraph_tg8_observable_subgoal_selector_v3 as tg8  # noqa: E402


ALLOWED_INPUTS = list(tg8.ALLOWED_INPUTS)
CONDITIONS = (
    "type_level_current_coverage",
    "instance_bound_current_coverage",
    "type_level_open_close_coverage",
    "instance_bound_open_close_coverage",
)
CONDITION_FACTORS = {
    "type_level_current_coverage": (False, False),
    "instance_bound_current_coverage": (True, False),
    "type_level_open_close_coverage": (False, True),
    "instance_bound_open_close_coverage": (True, True),
}
TG8_CONTROL_CONDITION = "observable_subgoal_anti_cycle"
FORBIDDEN_INPUTS = set(tg8.FORBIDDEN_INPUTS) | {
    "tg9_private_metadata",
    "object_id",
    "scene_graph",
    "environment_success",
}
INSTANCE_LEDGER_VERSION = "tg9-observable-instance-binding-v1"
INSTANCE_CONFIDENCE_VALUES = {
    "unobserved",
    "not_applicable",
    "explicit_instance",
    "source_distinguished",
    "ambiguous_type_only",
    "duplicate_instance",
}
SLOT_FIELDS = {
    "object_type",
    "object_signature",
    "instance_signature",
    "source_signature",
    "destination_signature",
    "pickup_confirmed",
    "put_confirmed",
    "binding_confidence",
}
REQUIRED_TRACE_FIELDS = set(tg8.REQUIRED_TRACE_FIELDS) | {
    "tg9_condition",
    "tg9_control_condition",
    "object_instance_binding_enabled",
    "open_close_coverage_enabled",
    "instance_binding_rejections",
    "object_slot_1",
    "object_slot_2",
    "source_signature",
    "destination_signature",
    "completed_instance_signatures",
    "second_source_is_distinct",
    "second_source_same_as_first_destination",
    "instance_binding_confidence",
}

PICKUP_RE = re.compile(r"^(?:take|pick up|pickup)\s+(.+?)(?:\s+from\s+(.+))?$")
PUT_RE = re.compile(r"^(?:move|put|place)\s+(.+?)\s+(?:to|in|into|on|onto)\s+(.+)$")
INTERACTION_RE = re.compile(r"^(open|close)\s+(.+)$")


def condition_factors(condition: str) -> tuple[bool, bool]:
    try:
        return CONDITION_FACTORS[condition]
    except KeyError as exc:
        raise ValueError(f"unknown TG9 condition: {condition}") from exc


def _canonical_phrase(value: str) -> str:
    parts = tg8.normalize(value).split()
    if parts and parts[-1].isdigit():
        return " ".join([*(tg8.canonical_token(part) for part in parts[:-1]), parts[-1]])
    return " ".join(tg8.canonical_token(part) for part in parts)


def _entity_descriptor(value: str) -> dict[str, Any]:
    signature = _canonical_phrase(value)
    parts = signature.split()
    explicit = bool(parts and parts[-1].isdigit())
    object_type = " ".join(parts[:-1] if explicit else parts)
    return {
        "type": object_type,
        "signature": signature,
        "explicit_instance": explicit,
    }


def parse_observable_action(action: str) -> dict[str, Any] | None:
    """Parse only instance evidence literally present in an admissible/history action."""
    text = tg8.normalize(action)
    pickup = PICKUP_RE.match(text)
    if pickup:
        object_row = _entity_descriptor(pickup.group(1))
        source = _canonical_phrase(pickup.group(2) or "") or None
        return {
            "family": "pickup",
            "object_type": object_row["type"],
            "object_signature": object_row["signature"],
            "explicit_instance": object_row["explicit_instance"],
            "source_signature": source,
            "destination_signature": None,
        }
    put = PUT_RE.match(text)
    if put:
        object_row = _entity_descriptor(put.group(1))
        return {
            "family": "put",
            "object_type": object_row["type"],
            "object_signature": object_row["signature"],
            "explicit_instance": object_row["explicit_instance"],
            "source_signature": None,
            "destination_signature": _canonical_phrase(put.group(2)) or None,
        }
    interaction = INTERACTION_RE.match(text)
    if interaction:
        return {
            "family": interaction.group(1),
            "object_type": _entity_descriptor(interaction.group(2))["type"],
            "object_signature": _canonical_phrase(interaction.group(2)),
            "explicit_instance": _entity_descriptor(interaction.group(2))["explicit_instance"],
            "source_signature": None,
            "destination_signature": None,
        }
    return None


def _instance_signature(parsed: dict[str, Any]) -> str:
    if parsed.get("explicit_instance"):
        return str(parsed["object_signature"])
    source = parsed.get("source_signature")
    if source:
        return f"{parsed['object_type']}@source:{source}"
    return str(parsed["object_type"])


def classify_second_source(first_slot: dict[str, Any], action: str) -> dict[str, Any]:
    """Classify a second pickup using only literal action and first-slot evidence."""
    candidate = parse_observable_action(action)
    if candidate is None or candidate.get("family") != "pickup":
        return {
            "classification": "not_pickup",
            "is_distinct": None,
            "same_as_first_destination": False,
            "confidence": "not_applicable",
        }
    if candidate.get("object_type") != first_slot.get("object_type"):
        return {
            "classification": "different_object_type",
            "is_distinct": None,
            "same_as_first_destination": False,
            "confidence": "not_applicable",
            "candidate": candidate,
        }

    first_object = str(first_slot.get("object_signature") or "")
    first_explicit = bool(first_object and first_object.split()[-1:].pop().isdigit())
    candidate_object = str(candidate.get("object_signature") or "")
    candidate_explicit = bool(candidate.get("explicit_instance"))
    source = candidate.get("source_signature")
    first_source = first_slot.get("source_signature")
    first_destination = first_slot.get("destination_signature")
    same_destination = bool(source and first_destination and source == first_destination)

    if first_explicit and candidate_explicit and candidate_object != first_object:
        return {
            "classification": "distinct_explicit_instance",
            "is_distinct": True,
            "same_as_first_destination": same_destination,
            "confidence": "explicit_instance",
            "candidate": candidate,
        }
    if first_explicit and candidate_explicit and candidate_object == first_object:
        return {
            "classification": "duplicate_explicit_instance",
            "is_distinct": False,
            "same_as_first_destination": same_destination,
            "confidence": "duplicate_instance",
            "candidate": candidate,
        }
    if same_destination:
        return {
            "classification": "duplicate_from_first_destination",
            "is_distinct": False,
            "same_as_first_destination": True,
            "confidence": "duplicate_instance",
            "candidate": candidate,
        }
    if source and first_source and source != first_source:
        return {
            "classification": "distinct_source_container",
            "is_distinct": True,
            "same_as_first_destination": False,
            "confidence": "source_distinguished",
            "candidate": candidate,
        }
    return {
        "classification": "ambiguous_type_level_source",
        "is_distinct": None,
        "same_as_first_destination": False,
        "confidence": "ambiguous_type_only",
        "candidate": candidate,
    }


class ConditionalSkillIndex:
    """Expose exactly the SkillBank surface enabled by one TG9 condition."""

    def __init__(
        self,
        base_index: base.SkillIndex,
        interaction_index: base.SkillIndex | None,
        *,
        open_close_enabled: bool,
        rejected_actions: set[str] | None = None,
    ) -> None:
        if open_close_enabled and interaction_index is None:
            raise ValueError("OpenObject/CloseObject coverage requires the TG9 interaction SkillBank")
        self.base_index = base_index
        self.interaction_index = interaction_index
        self.open_close_enabled = open_close_enabled
        self.rejected_actions = {tg8.normalize(action) for action in (rejected_actions or set())}

    def matching_skill_ids(self, command: str) -> list[str]:
        if tg8.normalize(command) in self.rejected_actions:
            return []
        family = tg8.command_family(command)
        if family in {"open", "close"} and not self.open_close_enabled:
            return []
        matches = list(self.base_index.matching_skill_ids(command))
        if family in {"open", "close"} and self.interaction_index is not None:
            matches.extend(self.interaction_index.matching_skill_ids(command))
        return sorted(set(matches))


def _empty_instance_fields(condition: str) -> dict[str, Any]:
    binding_enabled, _coverage_enabled = condition_factors(condition)
    return {
        "tg9_instance_ledger_version": INSTANCE_LEDGER_VERSION,
        "tg9_condition": condition,
        "object_slot_1": None,
        "object_slot_2": None,
        "source_signature": None,
        "destination_signature": None,
        "completed_instance_signatures": [],
        "second_source_is_distinct": None,
        "second_source_same_as_first_destination": False,
        "instance_binding_confidence": "unobserved" if binding_enabled else "not_applicable",
    }


def _ensure_instance_fields(ledger: dict[str, Any], condition: str) -> dict[str, Any]:
    result = dict(ledger)
    prior_condition = result.get("tg9_condition")
    if prior_condition is not None and prior_condition != condition:
        raise ValueError("TG9 condition changed within an episode")
    for key, value in _empty_instance_fields(condition).items():
        if key not in result:
            result[key] = list(value) if isinstance(value, list) else value
    return result


def _slot_number(subgoal_id: str | None) -> int | None:
    if not subgoal_id:
        return None
    if subgoal_id.endswith("_1"):
        return 1
    if subgoal_id.endswith("_2"):
        return 2
    return None


def _update_slot_from_confirmed_event(
    ledger: dict[str, Any],
    observation: str,
    condition: str,
) -> dict[str, Any]:
    result = _ensure_instance_fields(ledger, condition)
    previous_subgoal = tg8.ledger_subgoal(result, result.get("last_selected_subgoal_id"))
    previous_action = result.get("last_selected_action")
    if not tg8._event_completes_action_subgoal(previous_subgoal, previous_action, observation):
        return tg8.seal_ledger(result)
    slot_number = _slot_number(previous_subgoal.get("id") if previous_subgoal else None)
    parsed = parse_observable_action(str(previous_action or ""))
    if slot_number is None or parsed is None:
        return tg8.seal_ledger(result)

    slot_key = f"object_slot_{slot_number}"
    slot = dict(result.get(slot_key) or {})
    prior_instance_signature = slot.get("instance_signature")
    slot.update({
        "object_type": parsed["object_type"],
        "object_signature": parsed["object_signature"],
    })
    slot["instance_signature"] = (
        prior_instance_signature
        if parsed.get("family") == "put" and prior_instance_signature and not parsed.get("explicit_instance")
        else _instance_signature(parsed)
    )
    if parsed.get("family") == "pickup":
        slot["source_signature"] = parsed.get("source_signature")
        slot["pickup_confirmed"] = True
        slot.setdefault("put_confirmed", False)
        slot["binding_confidence"] = (
            "explicit_instance" if parsed.get("explicit_instance") else "ambiguous_type_only"
        )
    elif parsed.get("family") == "put":
        slot["destination_signature"] = parsed.get("destination_signature")
        slot["put_confirmed"] = True
        slot.setdefault("pickup_confirmed", True)
        if parsed.get("explicit_instance"):
            slot["binding_confidence"] = "explicit_instance"
    result[slot_key] = slot
    result["source_signature"] = slot.get("source_signature")
    result["destination_signature"] = slot.get("destination_signature")

    if parsed.get("family") == "put":
        signatures = list(result.get("completed_instance_signatures") or [])
        signature = str(slot.get("instance_signature") or "")
        if signature and signature not in signatures:
            signatures.append(signature)
        result["completed_instance_signatures"] = signatures
    if slot_number == 2:
        first_slot = dict(result.get("object_slot_1") or {})
        classification = classify_second_source(first_slot, str(previous_action))
        if parsed.get("family") == "pickup":
            result["second_source_is_distinct"] = classification["is_distinct"]
            result["second_source_same_as_first_destination"] = classification["same_as_first_destination"]
            result["instance_binding_confidence"] = classification["confidence"]
    return tg8.seal_ledger(result)


def _binding_guard(
    ledger: dict[str, Any] | None,
    admissible_actions: list[str],
    binding_enabled: bool,
) -> tuple[set[str], list[dict[str, Any]]]:
    if not binding_enabled or ledger is None:
        return set(), []
    first_slot = dict(ledger.get("object_slot_1") or {})
    second_slot = dict(ledger.get("object_slot_2") or {})
    subgoal_ids = {row.get("id") for row in ledger.get("subgoals", [])}
    if (
        not first_slot.get("put_confirmed")
        or second_slot.get("pickup_confirmed")
        or "search_source_2" not in subgoal_ids
    ):
        return set(), []

    rejected: set[str] = set()
    rows: list[dict[str, Any]] = []
    for action in admissible_actions:
        classification = classify_second_source(first_slot, action)
        if classification["classification"] in {
            "duplicate_explicit_instance",
            "duplicate_from_first_destination",
            "ambiguous_type_level_source",
        }:
            rejected.add(action)
            rows.append({
                "action": action,
                "reason": "completed first instance is not admissible evidence for source slot 2",
                "classification": classification["classification"],
                "instance_binding_confidence": classification["confidence"],
                "second_source_same_as_first_destination": classification["same_as_first_destination"],
            })
    return rejected, rows


def _safe_rank_selection(
    index: ConditionalSkillIndex,
    historical: list[str],
    admissible: list[str],
    observed_ledger: dict[str, Any],
    rejected_actions: set[str],
    previous_skills: list[str | None] | None,
    previous_edges: list[list[str] | None] | None,
) -> dict[str, Any]:
    selection = tg8._rank_selection(
        index,
        TG8_CONTROL_CONDITION,
        historical,
        admissible,
        observed_ledger,
        previous_skills,
        previous_edges,
    )
    if selection["terminal"] not in rejected_actions:
        return selection
    safe = [action for action in admissible if action not in rejected_actions]
    if not safe:
        raise ValueError("no admissible action remains after the instance-binding guard")
    non_help = [action for action in safe if base.normalize_text(action) != "help"]
    terminal = non_help[0] if non_help else safe[0]
    seen = set(historical)
    previous_skill = previous_skills[-1] if previous_skills else observed_ledger.get("last_selected_skill_id")
    previous_edge = previous_edges[-1] if previous_edges else observed_ledger.get("last_selected_edge")
    had_previous = bool(previous_skills or previous_edges) or observed_ledger.get("last_selected_action") is not None
    selection.update({
        "terminal": terminal,
        "selected_skill": None,
        "selected_edge": None,
        "permitted_edges": [],
        "primary": 0,
        "secondary": 0,
        "matched": [],
        "reason": "instance_binding_abstain",
        "action_seen_before": terminal in seen,
        "skill_changed": had_previous and previous_skill is not None,
        "edge_changed": had_previous and previous_edge is not None,
    })
    return selection


def _annotate_selected_second_source(
    ledger: dict[str, Any],
    selected_action: str,
    pending_id: str | None,
    condition: str,
) -> dict[str, Any]:
    result = _ensure_instance_fields(ledger, condition)
    if pending_id != "pickup_2":
        return tg8.seal_ledger(result)
    first_slot = dict(result.get("object_slot_1") or {})
    classification = classify_second_source(first_slot, selected_action)
    if classification["classification"] in {"not_pickup", "different_object_type"}:
        return tg8.seal_ledger(result)
    result["second_source_is_distinct"] = classification["is_distinct"]
    result["second_source_same_as_first_destination"] = classification["same_as_first_destination"]
    result["instance_binding_confidence"] = classification["confidence"]
    return tg8.seal_ledger(result)


def _build_transition(
    index: base.SkillIndex,
    condition: str,
    runtime_inputs: dict[str, Any],
    previous_ledger: dict[str, Any] | None = None,
    previous_snapshots: list[str] | None = None,
    previous_skills: list[str | None] | None = None,
    previous_edges: list[list[str] | None] | None = None,
    *,
    interaction_index: base.SkillIndex | None = None,
) -> dict[str, Any]:
    binding_enabled, coverage_enabled = condition_factors(condition)
    observation = str(runtime_inputs["observation"])
    historical = [str(item) for item in runtime_inputs["historical_actions"]]
    admissible = [str(item) for item in runtime_inputs["admissible_actions"] if str(item).strip()]
    snapshot = tg8.snapshot_fingerprint(observation, admissible)

    prepared_previous = previous_ledger
    if previous_ledger is not None:
        if previous_ledger.get(tg8.LEDGER_FINGERPRINT_FIELD) != tg8.ledger_fingerprint(previous_ledger):
            raise ValueError("previous ledger fingerprint mismatch")
        prepared_previous = _update_slot_from_confirmed_event(previous_ledger, observation, condition)
    rejected_actions, binding_rejections = _binding_guard(prepared_previous, admissible, binding_enabled)
    effective_admissible = [action for action in admissible if action not in rejected_actions]
    observed_ledger = tg8.advance_ledger(prepared_previous, observation, effective_admissible, snapshot)
    observed_ledger = _ensure_instance_fields(observed_ledger, condition)
    observed_ledger["last_admissible_action_count"] = len(admissible)
    observed_ledger = tg8.seal_ledger(observed_ledger)

    conditional_index = ConditionalSkillIndex(
        index,
        interaction_index,
        open_close_enabled=coverage_enabled,
        rejected_actions=rejected_actions,
    )
    selection = _safe_rank_selection(
        conditional_index,
        historical,
        admissible,
        observed_ledger,
        rejected_actions,
        previous_skills,
        previous_edges,
    )
    ledger = tg8.commit_action(
        observed_ledger,
        selection["terminal"],
        selection["pending_id"],
        selection["selected_skill"],
        selection["selected_edge"],
    )
    ledger = _annotate_selected_second_source(
        ledger,
        selection["terminal"],
        selection["pending_id"],
        condition,
    )
    prior_snapshots = list(previous_snapshots or [])
    if previous_ledger and previous_ledger.get("last_snapshot_fingerprint"):
        prior_snapshots.append(str(previous_ledger["last_snapshot_fingerprint"]))
    eligibility_rejections = [
        {"action": command, "reason": "no eligible train-derived canonical action"}
        for command, ids in selection["command_candidates"].items()
        if not ids and command not in rejected_actions
    ]
    return {
        "runtime_inputs": runtime_inputs,
        "observable_state_fingerprint": base.fingerprint(runtime_inputs),
        "candidate_skill_ids": selection["candidate_ids"],
        "eligibility_rejections": eligibility_rejections,
        "instance_binding_rejections": binding_rejections,
        "permitted_edges": selection["permitted_edges"],
        "selected_skill_id": selection["selected_skill"],
        "selected_edge": selection["selected_edge"],
        "terminal_action_decision": selection["terminal"],
        "abstained": selection["selected_skill"] is None,
        "observable_snapshot_fingerprint": snapshot,
        "action_state_fingerprint": tg8.action_state_fingerprint(snapshot, selection["terminal"]),
        "cycle_triggered": selection["cycle_triggered"],
        "action_seen_before": selection["action_seen_before"],
        "skill_changed": selection["skill_changed"],
        "edge_changed": selection["edge_changed"],
        "selector_condition": condition,
        "tg9_condition": condition,
        "tg9_control_condition": TG8_CONTROL_CONDITION,
        "object_instance_binding_enabled": binding_enabled,
        "open_close_coverage_enabled": coverage_enabled,
        "selection_reason": selection["reason"],
        "repeated_observable_snapshot": snapshot in set(prior_snapshots),
        "subgoal_ledger": ledger,
        "subgoal_ledger_valid": True,
        "subgoal_ledger_provenance_complete": True,
        "observable_delta_since_previous": bool(observed_ledger["observable_delta_since_previous"]),
        "progress_event": bool(observed_ledger["progress_event"]),
        "false_progress_event": bool(observed_ledger["false_progress_event"]),
        "newly_completed_subgoal_ids": list(observed_ledger["newly_completed_subgoal_ids"]),
        "completed_subgoal_ids": list(observed_ledger["completed_subgoal_ids"]),
        "pending_subgoal_id": selection["pending_id"],
        "progress_evidence_source": observed_ledger.get("progress_evidence_source"),
        "representation_score": {
            "representation": selection["representation"],
            "primary": selection["primary"],
            "secondary": selection["secondary"],
            "matched_tokens": selection["matched"],
        },
        "object_slot_1": ledger.get("object_slot_1"),
        "object_slot_2": ledger.get("object_slot_2"),
        "source_signature": ledger.get("source_signature"),
        "destination_signature": ledger.get("destination_signature"),
        "completed_instance_signatures": list(ledger.get("completed_instance_signatures") or []),
        "second_source_is_distinct": ledger.get("second_source_is_distinct"),
        "second_source_same_as_first_destination": bool(
            ledger.get("second_source_same_as_first_destination")
        ),
        "instance_binding_confidence": ledger.get("instance_binding_confidence"),
    }


def select_condition(
    index: base.SkillIndex,
    condition: str,
    runtime_inputs: dict[str, Any],
    previous_ledger: dict[str, Any] | None = None,
    previous_snapshots: list[str] | None = None,
    previous_skills: list[str | None] | None = None,
    previous_edges: list[list[str] | None] | None = None,
    *,
    interaction_index: base.SkillIndex | None = None,
) -> dict[str, Any]:
    condition_factors(condition)
    if list(runtime_inputs) != ALLOWED_INPUTS:
        raise ValueError("runtime inputs must contain exactly the three observable fields")
    historical = [str(item) for item in runtime_inputs["historical_actions"]]
    admissible = [str(item) for item in runtime_inputs["admissible_actions"] if str(item).strip()]
    if not admissible:
        raise ValueError("environment returned no admissible action")
    if historical and previous_ledger is None:
        raise ValueError("historical actions require a previous subgoal ledger")
    if previous_snapshots is not None and len(previous_snapshots) != len(historical):
        raise ValueError("snapshot history length does not match historical_actions")
    tg8._validate_internal_history(historical, previous_ledger, previous_snapshots)
    transition = _build_transition(
        index,
        condition,
        runtime_inputs,
        previous_ledger,
        previous_snapshots,
        previous_skills,
        previous_edges,
        interaction_index=interaction_index,
    )
    valid, message = validate_selector_transition(
        transition,
        previous_ledger,
        index=index,
        interaction_index=interaction_index,
    )
    if not valid:
        raise RuntimeError(message)
    return transition


def validate_selector_transition(
    transition: dict[str, Any],
    previous_ledger: dict[str, Any] | None = None,
    *,
    index: base.SkillIndex | None = None,
    interaction_index: base.SkillIndex | None = None,
) -> tuple[bool, str]:
    runtime = transition.get("runtime_inputs")
    if not isinstance(runtime, dict) or list(runtime) != ALLOWED_INPUTS:
        return False, "runtime input violation"
    if any(key in transition for key in FORBIDDEN_INPUTS):
        return False, "forbidden runtime field present"
    if not REQUIRED_TRACE_FIELDS.issubset(transition):
        return False, "trace incomplete"
    if transition.get("tg9_condition") not in CONDITIONS:
        return False, "condition invalid"
    if transition.get("selector_condition") != transition.get("tg9_condition"):
        return False, "selector condition mismatch"
    if transition.get("tg9_control_condition") != TG8_CONTROL_CONDITION:
        return False, "TG8 control condition mismatch"
    binding_enabled, coverage_enabled = condition_factors(str(transition["tg9_condition"]))
    if transition.get("object_instance_binding_enabled") is not binding_enabled:
        return False, "object-binding factor mismatch"
    if transition.get("open_close_coverage_enabled") is not coverage_enabled:
        return False, "interaction-coverage factor mismatch"
    if any(key not in ALLOWED_INPUTS for key in runtime):
        return False, "runtime input violation"
    if transition.get("terminal_action_decision") not in runtime.get("admissible_actions", []):
        return False, "terminal action inadmissible"
    if transition.get("observable_state_fingerprint") != base.fingerprint(runtime):
        return False, "observable-state fingerprint mismatch"
    snapshot = tg8.snapshot_fingerprint(str(runtime["observation"]), list(runtime["admissible_actions"]))
    if transition.get("observable_snapshot_fingerprint") != snapshot:
        return False, "observable snapshot fingerprint mismatch"
    if transition.get("action_state_fingerprint") != tg8.action_state_fingerprint(
        snapshot, str(transition["terminal_action_decision"])
    ):
        return False, "action-state fingerprint mismatch"
    if previous_ledger is not None:
        history = list(runtime.get("historical_actions") or [])
        if not history or previous_ledger.get("last_selected_action") != history[-1]:
            return False, "previous ledger history mismatch"
    if index is None:
        return False, "skill index required for deterministic validation"

    ledger = transition.get("subgoal_ledger")
    if not isinstance(ledger, dict) or ledger.get("version") != "tg8-observable-event-ledger-v2":
        return False, "ledger version invalid"
    if ledger.get("tg9_instance_ledger_version") != INSTANCE_LEDGER_VERSION:
        return False, "instance ledger version invalid"
    if ledger.get(tg8.LEDGER_FINGERPRINT_FIELD) != tg8.ledger_fingerprint(ledger):
        return False, "ledger fingerprint mismatch"
    for key in ("object_slot_1", "object_slot_2"):
        slot = ledger.get(key)
        if slot is not None and (not isinstance(slot, dict) or not set(slot).issubset(SLOT_FIELDS)):
            return False, "instance slot contains unsupported evidence"
    if ledger.get("instance_binding_confidence") not in INSTANCE_CONFIDENCE_VALUES:
        return False, "instance confidence invalid"
    signatures = list(ledger.get("completed_instance_signatures") or [])
    if len(signatures) != len(set(signatures)):
        return False, "completed instance signatures are not unique"
    ids = [row["id"] for row in ledger.get("subgoals", [])]
    completed = list(ledger.get("completed_subgoal_ids") or [])
    unresolved = list(ledger.get("unresolved_subgoal_ids") or [])
    if len(ids) != len(set(ids)) or set(completed).intersection(unresolved) or set(completed + unresolved) != set(ids):
        return False, "ledger partition invalid"
    expected_pending = unresolved[0] if unresolved else None
    if ledger.get("pending_subgoal_id") != expected_pending or transition.get("pending_subgoal_id") != expected_pending:
        return False, "pending subgoal invalid"
    if ledger.get("last_selected_action") != transition.get("terminal_action_decision"):
        return False, "ledger action mismatch"
    if transition.get("completed_subgoal_ids") != completed:
        return False, "completed subgoal trace mismatch"
    binding_actions = {row.get("action") for row in transition.get("instance_binding_rejections", [])}
    eligibility_actions = {row.get("action") for row in transition.get("eligibility_rejections", [])}
    if binding_actions.intersection(eligibility_actions):
        return False, "instance and skill eligibility rejections overlap"
    if binding_actions and transition.get("terminal_action_decision") in binding_actions:
        return False, "instance-rejected action selected"
    base_valid, base_message = base.validate_transition(transition)
    if not base_valid:
        return False, base_message
    try:
        expected = _build_transition(
            index,
            str(transition["tg9_condition"]),
            runtime,
            previous_ledger,
            interaction_index=interaction_index,
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"selector recomputation failed: {type(exc).__name__}: {exc}"
    exact_fields = tuple(REQUIRED_TRACE_FIELDS | {
        "runtime_inputs",
        "observable_state_fingerprint",
        "abstained",
        "skill_changed",
        "edge_changed",
        "repeated_observable_snapshot",
    })
    for field in exact_fields:
        if field == "repeated_observable_snapshot":
            continue
        if transition.get(field) != expected.get(field):
            return False, f"{field} mismatch"
    repeated = transition.get("repeated_observable_snapshot")
    if not isinstance(repeated, bool):
        return False, "repeated snapshot flag invalid"
    if previous_ledger is None and repeated:
        return False, "repeated snapshot flag mismatch"
    if previous_ledger is not None and previous_ledger.get("last_snapshot_fingerprint") == snapshot and not repeated:
        return False, "repeated snapshot flag mismatch"
    return True, "ok"


def classify_ledger_environment_consistency(
    ledger: dict[str, Any],
    environment_success: bool,
) -> str:
    """Offline audit helper; environment_success is never a selector runtime input."""
    ledger_complete = not list(ledger.get("unresolved_subgoal_ids") or [])
    if ledger_complete and not environment_success:
        return "ledger_complete_but_env_fail"
    if ledger_complete and environment_success:
        return "ledger_and_environment_complete"
    if environment_success:
        return "environment_success_before_ledger_complete"
    return "ledger_and_environment_incomplete"
