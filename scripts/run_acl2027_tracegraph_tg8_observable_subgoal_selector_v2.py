#!/usr/bin/env python3
"""Observable-event TG8 selector with no environment or provider execution."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_acl2027_tracegraph_tg6_local_execution_runner_v1 as base  # noqa: E402

ALLOWED_INPUTS = ["observation", "historical_actions", "admissible_actions"]
CONDITIONS = (
    "lexical_greedy",
    "lexical_anti_cycle",
    "observable_subgoal_greedy",
    "observable_subgoal_anti_cycle",
)
FORBIDDEN_INPUTS = set(base.FORBIDDEN_INPUTS) | {
    "tg6_private_metadata", "tg7_private_metadata", "tg8_private_metadata",
}
STOPWORDS = {
    "a", "an", "and", "are", "at", "be", "by", "for", "from", "in", "into",
    "is", "it", "of", "on", "one", "room", "some", "task", "the", "then", "to",
    "up", "with", "your", "you",
}
TASK_MARKERS = ("your task is", "task is", "you need to")
REQUIRED_TRACE_FIELDS = set(base.REQUIRED_TRACE_FIELDS) | {
    "observable_snapshot_fingerprint", "action_state_fingerprint",
    "cycle_triggered", "action_seen_before", "selector_condition",
    "selection_reason", "repeated_observable_snapshot", "subgoal_ledger",
    "subgoal_ledger_valid", "subgoal_ledger_provenance_complete",
    "observable_delta_since_previous", "progress_event", "false_progress_event",
    "newly_completed_subgoal_ids", "completed_subgoal_ids", "pending_subgoal_id",
    "progress_evidence_source", "representation_score",
}


def normalize(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", str(value or "").lower()).split())


def canonical_token(value: str) -> str:
    token = normalize(value)
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith("s") and not token.endswith("ss") and len(token) > 3:
        return token[:-1]
    return token


def tokens(value: str) -> list[str]:
    return [canonical_token(token) for token in normalize(value).split() if token not in STOPWORDS]


def extract_task_clause(observation: str) -> str:
    text = normalize(observation)
    for marker in TASK_MARKERS:
        if marker in text:
            return text.split(marker, 1)[1].split(".", 1)[0].strip()
    return text.split(".", 1)[0].strip()


def extract_task_entities(observation: str) -> tuple[str, list[str], list[str], list[str]]:
    clause = extract_task_clause(observation)
    words = normalize(clause).split()
    clean_words = {"clean", "cleaned", "wash", "washed", "rinse", "rinsed"}
    family = (
        "pick_two_obj_and_place" if "two" in words or "both" in words
        else "pick_clean_then_place_in_recep" if clean_words.intersection(words)
        else "pick_and_place_simple"
    )
    placement_verbs = {"put", "place", "move", "carry"}
    start = next((index + 1 for index, word in enumerate(words) if word in placement_verbs), 0)
    split_at = next((index for index in range(start, len(words)) if words[index] in {"in", "into", "on", "onto", "to"}), len(words))
    ignored = {"a", "an", "the", "some", "two", "both"} | clean_words
    object_tokens = sorted({canonical_token(word) for word in words[start:split_at] if word not in ignored})
    destination_tokens = sorted({canonical_token(word) for word in words[split_at + 1:] if word not in ignored})
    anchor = sorted(set(tokens(clause)))
    if not object_tokens:
        object_tokens = anchor[:1] or ["unknown"]
    if not destination_tokens:
        destination_tokens = anchor[-1:] or ["unknown"]
    return family, object_tokens, destination_tokens, anchor


def _subgoal(
    identifier: str,
    kind: str,
    entities: list[str],
    required_groups: list[list[str]] | None = None,
) -> dict[str, Any]:
    groups = required_groups or ([entities] if entities else [])
    return {
        "id": identifier,
        "kind": kind,
        "entity_tokens": sorted(set(entities)),
        "required_token_groups": [sorted(set(group)) for group in groups if group],
    }


def build_subgoals(observation: str) -> list[dict[str, Any]]:
    family, object_tokens, destination_tokens, _anchor = extract_task_entities(observation)
    one_cycle = [
        _subgoal("search_source", "search_source", object_tokens, [object_tokens]),
        _subgoal("pickup", "pickup", object_tokens, [object_tokens]),
        _subgoal(
            "search_destination", "search_destination",
            object_tokens + destination_tokens, [object_tokens, destination_tokens],
        ),
        _subgoal("put", "put", object_tokens + destination_tokens, [object_tokens, destination_tokens]),
    ]
    if family == "pick_two_obj_and_place":
        return [
            {**row, "id": f"{row['id']}_1"} for row in one_cycle
        ] + [
            {**row, "id": f"{row['id']}_2"} for row in one_cycle
        ]
    if family == "pick_clean_then_place_in_recep":
        return [
            _subgoal("search_source", "search_source", object_tokens, [object_tokens]),
            _subgoal("pickup", "pickup", object_tokens, [object_tokens]),
            _subgoal(
                "search_cleaning", "search_cleaning",
                object_tokens + ["sinkbasin"], [object_tokens, ["sinkbasin"]],
            ),
            _subgoal("clean", "clean", object_tokens + ["sinkbasin"], [object_tokens, ["sinkbasin"]]),
            _subgoal(
                "search_destination", "search_destination",
                object_tokens + destination_tokens, [object_tokens, destination_tokens],
            ),
            _subgoal("put", "put", object_tokens + destination_tokens, [object_tokens, destination_tokens]),
        ]
    return one_cycle


def snapshot_fingerprint(observation: str, admissible_actions: list[str]) -> str:
    return base.fingerprint({
        "observation": normalize(observation),
        "admissible_actions": sorted(normalize(action) for action in admissible_actions),
    })


def action_state_fingerprint(snapshot: str, action: str) -> str:
    return base.fingerprint({"observable_snapshot_fingerprint": snapshot, "action": str(action)})


def detect_two_cycle(actions: list[str]) -> tuple[bool, tuple[str, str] | None]:
    if len(actions) < 4:
        return False, None
    a, b, c, d = actions[-4:]
    return (True, (a, b)) if a == c and b == d and a != b else (False, None)


def token_overlap(command: str, entities: list[str]) -> list[str]:
    return sorted(set(tokens(command)).intersection(entities))


def _required_groups_match(text: str, subgoal: dict[str, Any]) -> bool:
    normalized = set(tokens(text))
    groups = subgoal.get("required_token_groups") or []
    return bool(groups) and all(normalized.intersection(group) for group in groups)


def command_matches(command: str, family: str, entities: list[str]) -> bool:
    return base.command_family(command) == family and bool(token_overlap(command, entities))


def _state_satisfies_search(subgoal: dict[str, Any], actions: list[str]) -> bool:
    kind = subgoal["kind"]
    entities = list(subgoal["entity_tokens"])
    if kind == "search_source":
        return any(
            base.command_family(action) == "pickup"
            and _required_groups_match(action, subgoal)
            for action in actions
        )
    if kind == "search_destination":
        return any(
            base.command_family(action) == "put"
            and _required_groups_match(action, subgoal)
            for action in actions
        )
    if kind == "search_cleaning":
        return any(
            base.command_family(action) == "clean"
            and _required_groups_match(action, subgoal)
            for action in actions
        )
    return False


def _event_completes_action_subgoal(
    subgoal: dict[str, Any] | None,
    previous_action: str | None,
    observation: str,
) -> bool:
    if subgoal is None or previous_action is None:
        return False
    kind = subgoal["kind"]
    if kind not in {"pickup", "clean", "put"}:
        return False
    entities = list(subgoal["entity_tokens"])
    if not command_matches(previous_action, kind, entities):
        return False
    text = normalize(observation)
    if not _required_groups_match(text, subgoal):
        return False
    patterns = {
        "pickup": r"pick up|picked up|take|taken",
        "clean": r"clean|washed|wash|rinsed|rinse",
        "put": r"put|place|placed",
    }
    return bool(re.search(patterns[kind], text))


def _action_relevant(subgoal: dict[str, Any] | None, action: str | None) -> bool:
    if subgoal is None or action is None:
        return False
    kind = subgoal["kind"]
    entities = list(subgoal["entity_tokens"])
    family = base.command_family(action)
    if kind == "search_source":
        return family in {"goto", "open"}
    if kind == "search_destination":
        return family == "goto" and bool(token_overlap(action, entities)) or family == "open" and bool(token_overlap(action, entities))
    if kind == "search_cleaning":
        return family == "goto" and "sinkbasin" in tokens(action)
    return command_matches(action, kind, entities)


def _future_lexical_tokens(subgoals: list[dict[str, Any]], unresolved: list[str], anchor: list[str]) -> list[str]:
    pending = [row for row in subgoals if row["id"] in unresolved]
    entity_tokens = {token for row in pending for token in row["entity_tokens"]}
    operation_tokens = set()
    if any(row["kind"] == "put" for row in pending):
        operation_tokens.update({"put", "place", "move", "carry"})
    if any(row["kind"] == "clean" for row in pending):
        operation_tokens.update({"clean", "cleaned", "wash", "washed", "rinse", "rinsed"})
    if sum(row["kind"] == "pickup" for row in pending) > 1:
        operation_tokens.add("two")
    remaining = sorted(set(anchor).intersection(entity_tokens | operation_tokens))
    return remaining or list(anchor)


def initial_ledger(observation: str) -> dict[str, Any]:
    subgoals = build_subgoals(observation)
    _family, _object, _destination, anchor = extract_task_entities(observation)
    unresolved = [row["id"] for row in subgoals]
    return {
        "version": "tg8-observable-event-ledger-v2",
        "subgoals": subgoals,
        "completed_subgoal_ids": [],
        "unresolved_subgoal_ids": unresolved,
        "pending_subgoal_id": unresolved[0] if unresolved else None,
        "anchor_tokens": anchor,
        "lexical_unresolved_tokens": _future_lexical_tokens(subgoals, unresolved, anchor),
        "last_snapshot_fingerprint": None,
        "last_selected_action": None,
        "last_selected_subgoal_id": None,
        "observable_delta_since_previous": False,
        "progress_event": False,
        "false_progress_event": False,
        "newly_completed_subgoal_ids": [],
        "progress_evidence_source": None,
        "attempted_actions": [],
    }


def ledger_subgoal(ledger: dict[str, Any], identifier: str | None) -> dict[str, Any] | None:
    return next((row for row in ledger.get("subgoals", []) if row["id"] == identifier), None)


def advance_ledger(
    previous: dict[str, Any] | None,
    observation: str,
    admissible_actions: list[str],
    snapshot: str,
) -> dict[str, Any]:
    ledger = dict(previous or initial_ledger(observation))
    ledger["subgoals"] = [dict(row) for row in ledger["subgoals"]]
    completed = list(ledger.get("completed_subgoal_ids") or [])
    previous_snapshot = ledger.get("last_snapshot_fingerprint")
    previous_action = ledger.get("last_selected_action")
    previous_subgoal = ledger_subgoal(ledger, ledger.get("last_selected_subgoal_id"))
    delta = bool(previous_snapshot is not None and previous_snapshot != snapshot)
    newly_completed: list[str] = []
    if _event_completes_action_subgoal(previous_subgoal, previous_action, observation):
        if previous_subgoal and previous_subgoal["id"] not in completed:
            completed.append(previous_subgoal["id"])
            newly_completed.append(previous_subgoal["id"])
    unresolved = [row["id"] for row in ledger["subgoals"] if row["id"] not in completed]
    while unresolved:
        pending = ledger_subgoal(ledger, unresolved[0])
        if pending is None or not _state_satisfies_search(pending, admissible_actions):
            break
        completed.append(pending["id"])
        newly_completed.append(pending["id"])
        unresolved = [row["id"] for row in ledger["subgoals"] if row["id"] not in completed]
    pending_id = unresolved[0] if unresolved else None
    false_progress = bool(
        previous_action is not None
        and _action_relevant(previous_subgoal, previous_action)
        and not delta
        and not newly_completed
    )
    progress = bool(newly_completed)
    ledger.update({
        "completed_subgoal_ids": completed,
        "unresolved_subgoal_ids": unresolved,
        "pending_subgoal_id": pending_id,
        "lexical_unresolved_tokens": _future_lexical_tokens(
            ledger["subgoals"], unresolved, list(ledger["anchor_tokens"])
        ),
        "last_snapshot_fingerprint": snapshot,
        "observable_delta_since_previous": delta,
        "progress_event": progress,
        "false_progress_event": false_progress,
        "newly_completed_subgoal_ids": newly_completed,
        "progress_evidence_source": (
            "runtime_inputs.observation + runtime_inputs.admissible_actions"
            if previous_action is not None or newly_completed else None
        ),
        "last_admissible_action_count": len(admissible_actions),
    })
    ledger["provenance"] = {
        "subgoals": "static grammar from initial runtime_inputs.observation",
        "search_completion": "current runtime_inputs.admissible_actions",
        "action_completion": "previous historical action + current runtime_inputs.observation",
        "snapshot": "normalized runtime_inputs.observation + sorted normalized admissible_actions",
        "false_progress": "relevant previous action + unchanged canonical snapshot",
        "lexical_unresolved_tokens": "anchor tokens intersecting unresolved subgoal entities and operations",
    }
    return ledger


def commit_action(ledger: dict[str, Any], action: str, subgoal_id: str | None) -> dict[str, Any]:
    result = dict(ledger)
    result["last_selected_action"] = action
    result["last_selected_subgoal_id"] = subgoal_id
    result["attempted_actions"] = list(ledger.get("attempted_actions") or []) + [action]
    return result


def structured_score(command: str, pending: dict[str, Any] | None) -> tuple[int, int, list[str]]:
    if pending is None:
        return 0, 0, []
    family = base.command_family(command)
    entities = list(pending["entity_tokens"])
    overlap = token_overlap(command, entities)
    kind = pending["kind"]
    if kind == "search_source":
        primary = 3 if family == "open" else 2 if family == "goto" else 0
    elif kind == "search_destination":
        primary = 3 if family == "open" and overlap else 2 if family == "goto" and overlap else 0
    elif kind == "search_cleaning":
        primary = 2 if family == "goto" and "sinkbasin" in tokens(command) else 0
    else:
        primary = 3 if command_matches(command, kind, entities) else 0
    return primary, len(overlap), overlap


def lexical_score(command: str, unresolved: list[str]) -> tuple[int, int, list[str]]:
    overlap = token_overlap(command, unresolved)
    return len(overlap), 0, overlap


def candidate_rows(index: base.SkillIndex, admissible: list[str]) -> tuple[dict[str, list[str]], list[str], list[tuple[int, str, str]]]:
    command_candidates = {command: index.matching_skill_ids(command) for command in admissible}
    candidate_ids = sorted({skill_id for ids in command_candidates.values() for skill_id in ids})
    pairs = [(position, command, skill_id) for position, command in enumerate(admissible) for skill_id in command_candidates[command]]
    return command_candidates, candidate_ids, pairs


def _validate_internal_history(
    historical: list[str],
    previous_ledger: dict[str, Any] | None,
    previous_snapshots: list[str] | None,
) -> None:
    if previous_ledger is None:
        return
    if not historical or previous_ledger.get("last_selected_action") != historical[-1]:
        raise ValueError("previous ledger action does not match historical_actions")
    if previous_snapshots and previous_ledger.get("last_snapshot_fingerprint") != previous_snapshots[-1]:
        raise ValueError("previous ledger snapshot does not match trace history")


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
    observation = str(runtime_inputs["observation"])
    historical = [str(item) for item in runtime_inputs["historical_actions"]]
    admissible = [str(item) for item in runtime_inputs["admissible_actions"] if str(item).strip()]
    if not admissible:
        raise ValueError("environment returned no admissible action")
    if historical and previous_ledger is None:
        raise ValueError("historical actions require a previous subgoal ledger")
    if previous_snapshots is not None and len(previous_snapshots) != len(historical):
        raise ValueError("snapshot history length does not match historical_actions")
    _validate_internal_history(historical, previous_ledger, previous_snapshots)
    snapshot = snapshot_fingerprint(observation, admissible)
    observed_ledger = advance_ledger(previous_ledger, observation, admissible, snapshot)
    pending_id = observed_ledger.get("pending_subgoal_id")
    pending = ledger_subgoal(observed_ledger, pending_id)
    representation = "observable_subgoal" if condition.startswith("observable_") else "lexical"
    anti_cycle = condition.endswith("anti_cycle")
    command_candidates, candidate_ids, pairs = candidate_rows(index, admissible)
    cycle_triggered, cycle_pair = detect_two_cycle(historical)
    cycle = set(cycle_pair or ())
    seen = set(historical)
    ranked = []
    for position, command, skill_id in pairs:
        score = (
            structured_score(command, pending)
            if representation == "observable_subgoal"
            else lexical_score(command, list(observed_ledger["lexical_unresolved_tokens"]))
        )
        primary, secondary, matched = score
        key: tuple[Any, ...] = (-primary, -secondary)
        if anti_cycle:
            key += (command in seen, command in cycle)
        key += (position, skill_id)
        ranked.append((key, command, skill_id, primary, secondary, matched))
    if ranked:
        _key, terminal, selected_skill, primary, secondary, matched = min(ranked, key=lambda row: row[0])
        reason = f"{representation}_{'anti_cycle' if anti_cycle else 'greedy'}_rank"
    else:
        non_help = [command for command in admissible if base.normalize_text(command) != "help"]
        terminal = non_help[0] if non_help else admissible[0]
        selected_skill = None
        primary, secondary, matched = 0, 0, []
        reason = "fallback_no_eligible_skill"
    permitted_edges = (
        [[selected_skill, candidate] for candidate in candidate_ids if candidate != selected_skill]
        if selected_skill is not None else []
    )
    selected_edge = permitted_edges[0] if permitted_edges else None
    ledger = commit_action(observed_ledger, terminal, pending_id)
    transition = {
        "runtime_inputs": runtime_inputs,
        "observable_state_fingerprint": base.fingerprint(runtime_inputs),
        "candidate_skill_ids": candidate_ids,
        "eligibility_rejections": [
            {"action": command, "reason": "no eligible train-derived canonical action"}
            for command, ids in command_candidates.items() if not ids
        ],
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
        "subgoal_ledger": ledger,
        "subgoal_ledger_valid": True,
        "subgoal_ledger_provenance_complete": True,
        "observable_delta_since_previous": bool(observed_ledger["observable_delta_since_previous"]),
        "progress_event": bool(observed_ledger["progress_event"]),
        "false_progress_event": bool(observed_ledger["false_progress_event"]),
        "newly_completed_subgoal_ids": list(observed_ledger["newly_completed_subgoal_ids"]),
        "completed_subgoal_ids": list(observed_ledger["completed_subgoal_ids"]),
        "pending_subgoal_id": pending_id,
        "progress_evidence_source": observed_ledger.get("progress_evidence_source"),
        "representation_score": {
            "representation": representation,
            "primary": primary,
            "secondary": secondary,
            "matched_tokens": matched,
        },
    }
    valid, message = validate_selector_transition(transition, previous_ledger)
    if not valid:
        raise RuntimeError(message)
    return transition


def validate_selector_transition(
    transition: dict[str, Any], previous_ledger: dict[str, Any] | None = None
) -> tuple[bool, str]:
    runtime = transition.get("runtime_inputs")
    if not isinstance(runtime, dict) or list(runtime) != ALLOWED_INPUTS:
        return False, "runtime input violation"
    if any(key in transition for key in FORBIDDEN_INPUTS):
        return False, "forbidden runtime field present"
    if not REQUIRED_TRACE_FIELDS.issubset(transition):
        return False, "trace incomplete"
    if transition["selector_condition"] not in CONDITIONS:
        return False, "condition invalid"
    if transition["terminal_action_decision"] not in runtime["admissible_actions"]:
        return False, "terminal action inadmissible"
    if transition["observable_state_fingerprint"] != base.fingerprint(runtime):
        return False, "observable-state fingerprint mismatch"
    snapshot = snapshot_fingerprint(str(runtime["observation"]), list(runtime["admissible_actions"]))
    if transition["observable_snapshot_fingerprint"] != snapshot:
        return False, "observable snapshot fingerprint mismatch"
    if transition["action_state_fingerprint"] != action_state_fingerprint(snapshot, transition["terminal_action_decision"]):
        return False, "action-state fingerprint mismatch"
    cycle_triggered, _pair = detect_two_cycle(list(runtime["historical_actions"]))
    if transition["cycle_triggered"] is not cycle_triggered:
        return False, "cycle field mismatch"
    if transition["action_seen_before"] is not (transition["terminal_action_decision"] in runtime["historical_actions"]):
        return False, "action-seen field mismatch"
    ledger = transition.get("subgoal_ledger")
    if not isinstance(ledger, dict) or ledger.get("version") != "tg8-observable-event-ledger-v2":
        return False, "ledger version invalid"
    ids = [row["id"] for row in ledger.get("subgoals", [])]
    completed = list(ledger.get("completed_subgoal_ids") or [])
    unresolved = list(ledger.get("unresolved_subgoal_ids") or [])
    if len(ids) != len(set(ids)) or set(completed).intersection(unresolved) or set(completed + unresolved) != set(ids):
        return False, "ledger partition invalid"
    expected_pending = unresolved[0] if unresolved else None
    if ledger.get("pending_subgoal_id") != expected_pending or transition["pending_subgoal_id"] != expected_pending:
        return False, "pending subgoal invalid"
    if ledger.get("last_selected_action") != transition["terminal_action_decision"]:
        return False, "ledger action mismatch"
    if transition["completed_subgoal_ids"] != completed:
        return False, "completed subgoal trace mismatch"
    if transition["progress_event"] is not bool(ledger.get("progress_event")):
        return False, "progress field mismatch"
    if transition["false_progress_event"] is not bool(ledger.get("false_progress_event")):
        return False, "false-progress field mismatch"
    if (transition["progress_event"] or transition["false_progress_event"]) and not transition.get("progress_evidence_source"):
        return False, "progress evidence source missing"
    if transition.get("subgoal_ledger_valid") is not True or transition.get("subgoal_ledger_provenance_complete") is not True:
        return False, "ledger validity flags false"
    provenance = ledger.get("provenance") or {}
    if not {"subgoals", "search_completion", "action_completion", "snapshot", "false_progress", "lexical_unresolved_tokens"}.issubset(provenance):
        return False, "ledger provenance incomplete"
    if previous_ledger is not None:
        history = list(runtime["historical_actions"])
        if not history or previous_ledger.get("last_selected_action") != history[-1]:
            return False, "previous ledger history mismatch"
    base_valid, base_message = base.validate_transition(transition)
    return (False, base_message) if not base_valid else (True, "ok")
