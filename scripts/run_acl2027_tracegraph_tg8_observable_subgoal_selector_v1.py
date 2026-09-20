#!/usr/bin/env python3
"""Deterministic, zero-network TG8 observable-subgoal selector contract."""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_acl2027_tracegraph_tg6_local_execution_runner_v1 as base  # noqa: E402

ALLOWED_INPUTS = ["observation", "historical_actions", "admissible_actions"]
FORBIDDEN_INPUTS = set(base.FORBIDDEN_INPUTS) | {
    "tg6_private_metadata", "tg7_private_metadata", "tg8_private_metadata",
}
CONDITIONS = (
    "lexical_greedy",
    "lexical_anti_cycle",
    "observable_subgoal_greedy",
    "observable_subgoal_anti_cycle",
)
REQUIRED_TRACE_FIELDS = set(base.REQUIRED_TRACE_FIELDS) | {
    "observable_snapshot_fingerprint",
    "action_state_fingerprint",
    "cycle_triggered",
    "action_seen_before",
    "selector_condition",
    "selection_reason",
    "repeated_observable_snapshot",
    "subgoal_ledger",
    "subgoal_ledger_valid",
    "subgoal_ledger_provenance_complete",
    "progress_event",
    "false_progress_event",
    "observable_delta_since_previous",
    "progress_evidence_source",
    "completed_subgoal_ids",
    "pending_subgoal_id",
}
STOPWORDS = {
    "a", "an", "and", "are", "at", "be", "by", "for", "from", "in", "into",
    "is", "it", "of", "on", "one", "room", "some", "task", "the", "then", "to",
    "up", "with", "your", "you",
}
TASK_MARKERS = ("your task is", "task is", "you need to")


def normalize(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", str(value or "").lower()).split())


def tokens(value: str) -> list[str]:
    return [token for token in normalize(value).split() if token and token not in STOPWORDS]


def extract_task_clause(observation: str) -> str:
    text = normalize(observation)
    for marker in TASK_MARKERS:
        if marker in text:
            return text.split(marker, 1)[1].split(".", 1)[0].strip()
    return text.split(".", 1)[0].strip()


def extract_task_anchor(observation: str) -> list[str]:
    return sorted(set(tokens(extract_task_clause(observation))))


def _task_family(clause: str) -> str:
    words = set(tokens(clause))
    if "two" in normalize(clause) or "both" in words:
        return "pick_two_obj_and_place"
    if words.intersection({"clean", "cleaned", "wash", "washed", "rinse", "rinsed"}):
        return "pick_clean_then_place_in_recep"
    return "pick_and_place_simple"


def _canonical_entity_token(value: str) -> str:
    token = normalize(value)
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith("s") and not token.endswith("ss") and len(token) > 3:
        return token[:-1]
    return token


def _task_entities(clause: str) -> tuple[list[str], list[str]]:
    words = normalize(clause).split()
    operation_words = {
        "put", "place", "move", "carry", "rinse", "wash", "clean", "cleaned", "washed",
    }
    determiners = {"a", "an", "the", "some", "two", "both"}
    modifiers = {"clean", "cleaned", "wash", "washed", "rinse", "rinsed"}
    start = next((index + 1 for index, word in enumerate(words) if word in operation_words), 0)
    split_at = next(
        (index for index in range(start, len(words)) if words[index] in {"in", "into", "on", "onto", "to"}),
        len(words),
    )
    object_words = [word for word in words[start:split_at] if word not in determiners | modifiers]
    destination_words = [word for word in words[split_at + 1:] if word not in determiners]
    object_tokens = sorted({_canonical_entity_token(word) for word in object_words if word})
    destination_tokens = sorted({_canonical_entity_token(word) for word in destination_words if word})
    fallback = [
        _canonical_entity_token(word)
        for word in tokens(clause)
        if word not in operation_words | determiners | modifiers
    ]
    if not object_tokens and fallback:
        object_tokens = [fallback[0]]
    if not destination_tokens and len(fallback) > 1:
        destination_tokens = [fallback[-1]]
    return object_tokens or ["unknown"], destination_tokens or ["unknown"]


def _subgoal(
    identifier: str,
    family: str,
    entity_tokens: list[str],
    clause: str,
) -> dict[str, Any]:
    return {
        "id": identifier,
        "family": family,
        "entity_tokens": sorted(set(entity_tokens)),
        "clause": clause,
        "family_source": "static tg8 grammar from initial runtime_inputs.observation",
    }


def build_subgoals(observation: str) -> list[dict[str, Any]]:
    clause = extract_task_clause(observation)
    family = _task_family(clause)
    object_tokens, destination_tokens = _task_entities(clause)
    if family == "pick_two_obj_and_place":
        return [
            _subgoal("sg0", "search_source", [], clause),
            _subgoal("sg1", "pickup", object_tokens, clause),
            _subgoal("sg2", "search_source", [], clause),
            _subgoal("sg3", "pickup", object_tokens, clause),
            _subgoal("sg4", "search_destination", destination_tokens, clause),
            _subgoal("sg5", "put", object_tokens + destination_tokens, clause),
            _subgoal("sg6", "put", object_tokens + destination_tokens, clause),
        ]
    if family == "pick_clean_then_place_in_recep":
        return [
            _subgoal("sg0", "search_source", [], clause),
            _subgoal("sg1", "pickup", object_tokens, clause),
            _subgoal("sg2", "search_cleaning", ["sinkbasin"], clause),
            _subgoal("sg3", "clean", object_tokens + ["sinkbasin"], clause),
            _subgoal("sg4", "search_destination", destination_tokens, clause),
            _subgoal("sg5", "put", object_tokens + destination_tokens, clause),
        ]
    return [
        _subgoal("sg0", "search_source", [], clause),
        _subgoal("sg1", "pickup", object_tokens, clause),
        _subgoal("sg2", "search_destination", destination_tokens, clause),
        _subgoal("sg3", "put", object_tokens + destination_tokens, clause),
    ]


def snapshot_fingerprint(observation: str, admissible_actions: list[str]) -> str:
    canonical_actions = sorted(normalize(str(item)) for item in admissible_actions)
    return base.fingerprint({
        "observation": normalize(str(observation)),
        "admissible_actions": canonical_actions,
    })


def action_state_fingerprint(snapshot: str, action: str) -> str:
    return base.fingerprint({"observable_snapshot_fingerprint": snapshot, "action": str(action)})


def detect_two_cycle(actions: list[str]) -> tuple[bool, tuple[str, str] | None]:
    if len(actions) < 4:
        return False, None
    a, b, c, d = actions[-4:]
    if a == c and b == d and a != b:
        return True, (a, b)
    return False, None


def _subgoal_overlap(command: str, subgoal: dict[str, Any]) -> list[str]:
    command_tokens = {_canonical_entity_token(token) for token in tokens(command)}
    return sorted(command_tokens.intersection(set(subgoal.get("entity_tokens") or [])))


def _representation_score(
    command: str,
    representation: str,
    anchor: list[str],
    pending: dict[str, Any] | None,
) -> tuple[int, int, list[str]]:
    family = base.command_family(command)
    if representation == "lexical":
        command_tokens = {_canonical_entity_token(token) for token in tokens(command)}
        anchor_tokens = {_canonical_entity_token(token) for token in anchor}
        overlap = sorted(command_tokens.intersection(anchor_tokens))
        return len(overlap), 0, overlap
    if pending is None:
        return 0, 0, []
    overlap = _subgoal_overlap(command, pending)
    family_match = int(family == pending.get("family"))
    return family_match, len(overlap), overlap


def _initial_ledger(observation: str) -> dict[str, Any]:
    subgoals = build_subgoals(observation)
    return {
        "version": "tg8-observable-subgoal-ledger-v1",
        "subgoals": subgoals,
        "completed_subgoal_ids": [],
        "unresolved_subgoal_ids": [row["id"] for row in subgoals],
        "pending_subgoal_id": subgoals[0]["id"] if subgoals else None,
        "anchor_tokens": extract_task_anchor(observation),
        "last_snapshot_fingerprint": None,
        "last_selected_action": None,
        "last_selected_subgoal_id": None,
        "last_action_progress_event": False,
        "last_action_false_progress_event": False,
        "progress_event": False,
        "false_progress_event": False,
        "progress_evidence_source": None,
    }


def _ledger_subgoal(ledger: dict[str, Any], subgoal_id: str | None) -> dict[str, Any] | None:
    if subgoal_id is None:
        return None
    return next((row for row in ledger.get("subgoals", []) if row.get("id") == subgoal_id), None)


def _action_matches_subgoal_family(command: str, subgoal: dict[str, Any]) -> bool:
    action_family = base.command_family(command)
    goal_family = str(subgoal.get("family", ""))
    if goal_family in {"search_source", "search_destination", "search_cleaning"}:
        return action_family == "goto"
    return action_family == goal_family


def _observable_text_evidence(
    subgoal: dict[str, Any], previous_action: str | None, observation: str
) -> bool:
    """Conservative event evidence from the current observation only."""
    if previous_action is None:
        return False
    text = normalize(observation)
    goal_family = str(subgoal.get("family", ""))
    entities = [str(item) for item in subgoal.get("entity_tokens") or []]
    entity_hit = any(entity and entity in text for entity in entities)
    if goal_family == "search_source":
        # A search is complete only when the target object becomes observable.
        return entity_hit and ("see" in text or "arrive" in text or "find" in text)
    if goal_family == "search_destination":
        return entity_hit and ("arrive" in text or "on the" in text or "in the" in text)
    if goal_family == "search_cleaning":
        return entity_hit and ("arrive" in text or "see" in text)
    if goal_family == "pickup":
        return entity_hit and bool(re.search(r"pick up|picked up|take|taken", text))
    if goal_family == "clean":
        return entity_hit and bool(re.search(r"clean|washed|rinsed|rinse|wash", text))
    if goal_family == "put":
        return entity_hit and bool(re.search(r"put|place|placed", text))
    return False


def _action_relevant_to_subgoal(action: str | None, subgoal: dict[str, Any] | None) -> bool:
    if action is None or subgoal is None:
        return False
    if not _action_matches_subgoal_family(action, subgoal):
        return False
    entities = set(str(item) for item in subgoal.get("entity_tokens") or [])
    if not entities:
        return True
    return bool(entities.intersection({_canonical_entity_token(t) for t in tokens(action)}))


def update_ledger(
    previous: dict[str, Any] | None,
    observation: str,
    admissible_actions: list[str],
    selected_action: str,
    selected_subgoal_id: str | None,
    snapshot: str,
) -> dict[str, Any]:
    ledger = dict(previous or _initial_ledger(observation))
    ledger["subgoals"] = [dict(row) for row in ledger.get("subgoals") or _initial_ledger(observation)["subgoals"]]
    ledger["anchor_tokens"] = list(ledger.get("anchor_tokens") or extract_task_anchor(observation))
    previous_snapshot = ledger.get("last_snapshot_fingerprint")
    previous_action = ledger.get("last_selected_action")
    previous_subgoal = _ledger_subgoal(ledger, ledger.get("last_selected_subgoal_id"))
    delta = previous_snapshot is not None and previous_snapshot != snapshot
    previous_overlap = _subgoal_overlap(previous_action or "", previous_subgoal or {})
    action_matches_subgoal = _action_relevant_to_subgoal(previous_action, previous_subgoal)
    completed_by_observation = _observable_text_evidence(
        previous_subgoal or {}, previous_action, observation
    )
    progress_event = bool(previous_action is not None and delta)
    false_progress_event = bool(action_matches_subgoal and not delta)
    completed = list(ledger.get("completed_subgoal_ids") or [])
    if (
        completed_by_observation
        and previous_subgoal is not None
        and previous_subgoal["id"] not in completed
    ):
        completed.append(previous_subgoal["id"])
    unresolved = [row["id"] for row in ledger["subgoals"] if row["id"] not in completed]
    pending = unresolved[0] if unresolved else None
    ledger.update({
        "completed_subgoal_ids": completed,
        "unresolved_subgoal_ids": unresolved,
        "pending_subgoal_id": pending,
        "last_snapshot_fingerprint": snapshot,
        "last_selected_action": selected_action,
        "last_selected_subgoal_id": selected_subgoal_id,
        "last_action_progress_event": progress_event,
        "last_action_false_progress_event": false_progress_event,
        "progress_event": progress_event,
        "false_progress_event": false_progress_event,
        "progress_evidence_source": (
            "runtime_inputs.observation + runtime_inputs.admissible_actions"
            if previous_action is not None else None
        ),
        "last_admissible_action_count": len(admissible_actions),
    })
    ledger["provenance"] = {
        "subgoals": "static tg8 grammar applied to initial runtime_inputs.observation",
        "anchor_tokens": "initial runtime_inputs.observation",
        "snapshot": "runtime_inputs.observation + runtime_inputs.admissible_actions",
        "previous_action": "runtime_inputs.historical_actions",
        "progress_event": "comparison of consecutive observable snapshots",
        "false_progress_event": "selected action entity overlap plus unchanged observable snapshot",
        "completed_subgoal_ids": "derived from previous selected action and observable text evidence",
    }
    return ledger


def _candidate_rows(index: base.SkillIndex, admissible: list[str]) -> tuple[dict[str, list[str]], list[str], list[tuple[int, str, str]]]:
    command_candidates = {command: index.matching_skill_ids(command) for command in admissible}
    candidate_ids = sorted({skill_id for ids in command_candidates.values() for skill_id in ids})
    pairs = [
        (ordinal, command, skill_id)
        for ordinal, command in enumerate(admissible)
        for skill_id in command_candidates[command]
    ]
    return command_candidates, candidate_ids, pairs


def select_condition(
    index: base.SkillIndex,
    condition: str,
    runtime_inputs: dict[str, Any],
    previous_ledger: dict[str, Any] | None = None,
    previous_snapshots: list[str] | None = None,
    previous_skills: list[str | None] | None = None,
    previous_edges: list[list[str] | None] | None = None,
) -> dict[str, Any]:
    if condition not in CONDITIONS:
        raise ValueError(f"unknown TG8 condition: {condition}")
    if list(runtime_inputs) != ALLOWED_INPUTS:
        raise ValueError("runtime inputs must contain exactly the three observable fields")
    admissible = [str(item) for item in runtime_inputs["admissible_actions"] if str(item).strip()]
    historical = [str(item) for item in runtime_inputs["historical_actions"]]
    if not admissible:
        raise ValueError("environment returned no admissible action")
    representation = "observable_subgoal" if condition.startswith("observable_") else "lexical"
    anti_cycle = condition.endswith("anti_cycle")
    anchor = list((previous_ledger or {}).get("anchor_tokens") or extract_task_anchor(str(runtime_inputs["observation"])))
    ledger_before = dict(previous_ledger or _initial_ledger(str(runtime_inputs["observation"])))
    snapshot = snapshot_fingerprint(str(runtime_inputs["observation"]), admissible)
    had_previous_snapshot = bool(
        previous_ledger and previous_ledger.get("last_snapshot_fingerprint") is not None
    )
    delta_since_previous = bool(
        had_previous_snapshot
        and previous_ledger.get("last_snapshot_fingerprint") != snapshot
    )
    # Consume evidence from the previous action before ranking the current one.
    ledger_observed = update_ledger(
        ledger_before,
        str(runtime_inputs["observation"]),
        admissible,
        ledger_before.get("last_selected_action"),
        ledger_before.get("last_selected_subgoal_id"),
        snapshot,
    )
    pending = _ledger_subgoal(ledger_observed, ledger_observed.get("pending_subgoal_id"))
    selected_subgoal_id = ledger_observed.get("pending_subgoal_id")
    command_candidates, candidate_ids, pairs = _candidate_rows(index, admissible)
    cycle_triggered, cycle_pair = detect_two_cycle(historical)
    seen = set(historical)
    cycle_set = set(cycle_pair or ())
    ranked: list[tuple[tuple[Any, ...], int, str, str, list[str]]] = []
    for ordinal, command, skill_id in pairs:
        family_score, overlap_count, overlap = _representation_score(command, representation, anchor, pending)
        key: tuple[Any, ...] = (-family_score, -overlap_count)
        if anti_cycle:
            key += (command in seen, command in cycle_set)
        key += (ordinal, skill_id)
        ranked.append((key, ordinal, command, skill_id, overlap))
    selected_command: str | None = None
    selected_skill: str | None = None
    selected_overlap: list[str] = []
    reason = f"{representation}_greedy"
    if ranked:
        _key, _ordinal, selected_command, selected_skill, selected_overlap = sorted(ranked, key=lambda row: row[0])[0]
        if anti_cycle:
            reason = f"{representation}_anti_cycle_rank"
    else:
        non_help = [command for command in admissible if base.normalize_text(command) != "help"]
        selected_command = non_help[0] if non_help else admissible[0]
        reason = "fallback_no_eligible_skill"
    non_help = [command for command in admissible if base.normalize_text(command) != "help"]
    terminal = selected_command or (non_help[0] if non_help else admissible[0])
    rejections = [
        {"action": command, "reason": "no eligible train-derived canonical action"}
        for command, skill_ids in command_candidates.items() if not skill_ids
    ]
    permitted_edges = (
        [[selected_skill, candidate] for candidate in candidate_ids if candidate != selected_skill]
        if selected_skill is not None else []
    )
    selected_edge = permitted_edges[0] if permitted_edges else None
    ledger = dict(ledger_observed)
    ledger["last_selected_action"] = terminal
    ledger["last_selected_subgoal_id"] = selected_subgoal_id
    transition = {
        "runtime_inputs": runtime_inputs,
        "observable_state_fingerprint": base.fingerprint(runtime_inputs),
        "candidate_skill_ids": candidate_ids,
        "eligibility_rejections": rejections,
        "permitted_edges": permitted_edges,
        "selected_skill_id": selected_skill,
        "selected_edge": selected_edge,
        "terminal_action_decision": terminal,
        "abstained": selected_skill is None,
        "observable_snapshot_fingerprint": snapshot,
        "action_state_fingerprint": action_state_fingerprint(snapshot, terminal),
        "cycle_triggered": cycle_triggered,
        "action_seen_before": terminal in seen,
        "skill_changed": bool(previous_skills) and selected_skill != previous_skills[-1],
        "edge_changed": bool(previous_edges) and selected_edge != previous_edges[-1],
        "selector_condition": condition,
        "selection_reason": reason,
        "repeated_observable_snapshot": snapshot in set(previous_snapshots or []),
        "task_anchor": anchor,
        "task_anchor_provenance": "initial runtime_inputs.observation",
        "subgoal_ledger": ledger,
        "subgoal_ledger_valid": True,
        "subgoal_ledger_provenance_complete": True,
        "progress_event": bool(ledger.get("progress_event")),
        "false_progress_event": bool(ledger.get("false_progress_event")),
        "observable_delta_since_previous": delta_since_previous,
        "progress_evidence_source": ledger.get("progress_evidence_source"),
        "completed_subgoal_ids": list(ledger.get("completed_subgoal_ids") or []),
        "pending_subgoal_id": ledger.get("pending_subgoal_id"),
        "representation_score": {
            "family_match": _representation_score(terminal, representation, anchor, pending)[0],
            "entity_overlap": selected_overlap,
            "representation": representation,
        },
    }
    valid, message = base.validate_transition(transition)
    if not valid:
        raise RuntimeError(message)
    if not REQUIRED_TRACE_FIELDS.issubset(transition):
        raise RuntimeError("TG8 trace incomplete")
    return transition


def validate_selector_transition(transition: dict[str, Any]) -> tuple[bool, str]:
    if list(transition.get("runtime_inputs") or {}) != ALLOWED_INPUTS:
        return False, "runtime input violation"
    if any(key in transition for key in FORBIDDEN_INPUTS):
        return False, "forbidden runtime field present"
    if not REQUIRED_TRACE_FIELDS.issubset(transition):
        return False, "trace incomplete"
    runtime = transition["runtime_inputs"]
    if transition["terminal_action_decision"] not in runtime["admissible_actions"]:
        return False, "terminal action inadmissible"
    if transition.get("observable_state_fingerprint") != base.fingerprint(runtime):
        return False, "observable-state fingerprint mismatch"
    ledger = transition.get("subgoal_ledger")
    if not isinstance(ledger, dict) or ledger.get("version") != "tg8-observable-subgoal-ledger-v1":
        return False, "subgoal ledger version invalid"
    if transition.get("progress_event") and transition.get("false_progress_event"):
        return False, "progress and false-progress cannot both be true"
    if transition.get("progress_event") and not transition.get("progress_evidence_source"):
        return False, "progress evidence source missing"
    return True, "ok"
