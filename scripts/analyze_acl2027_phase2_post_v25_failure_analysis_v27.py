#!/usr/bin/env python3
"""Frozen strict and alias-tolerant analysis for the v27 follow-up."""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import normalize_answer, parse_response, sha256_file, stable
from scripts.run_acl2027_phase2_post_v25_failure_analysis_design_preflight_v26 import CONDITIONS, FAMILIES, alias_tolerant_correct

DESIGN = ROOT / "artifacts/acl2027_phase2_post_v25_failure_analysis_design_preflight_v26"
LIVE = ROOT / "artifacts/acl2027_phase2_post_v25_failure_analysis_live_v27"
CONFIG = ROOT / "configs/acl2027/phase2_post_v25_failure_analysis_design_preflight_v26.json"
SCHEDULE = DESIGN / "future_schedule.json"
GOLD = DESIGN / "future_private_gold.json"
LEDGER = LIVE / "ledger.json"
AUDIT = LIVE / "followup_audit.json"
REPORT = ROOT / "paper/acl2027/results/phase2_post_v25_failure_analysis_live_v27.md"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def pair(values: dict[str, bool]) -> str:
    typed, global_only = values["contextual_typed_prior"], values["global_only"]
    if typed and not global_only:
        return "typed_win"
    if global_only and not typed:
        return "typed_loss"
    return "both_correct" if typed else "both_wrong"


def paired_summary(outcomes: dict[str, dict[str, bool]], tasks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    labels = Counter(pair(values) for values in outcomes.values())
    total = len(outcomes)
    correct = {condition: sum(values[condition] for values in outcomes.values()) for condition in CONDITIONS}
    accuracy = {condition: correct[condition] / total for condition in CONDITIONS}
    family: dict[str, dict[str, Any]] = {}
    for name in FAMILIES:
        ids = [task_id for task_id, task in tasks.items() if task["skill_family"] == name]
        typed = sum(outcomes[task_id]["contextual_typed_prior"] for task_id in ids)
        global_only = sum(outcomes[task_id]["global_only"] for task_id in ids)
        family[name] = {"tasks": len(ids), "typed_correct": typed, "global_only_correct": global_only, "margin": (typed - global_only) / len(ids)}
    return {
        "condition_correct_counts": correct,
        "condition_accuracy": accuracy,
        "margin": accuracy["contextual_typed_prior"] - accuracy["global_only"],
        "typed_wins": labels["typed_win"],
        "typed_losses": labels["typed_loss"],
        "ties": labels["both_correct"] + labels["both_wrong"],
        "pair_outcomes": dict(labels),
        "family_breakdown": family,
    }


def analyze() -> dict[str, Any]:
    cfg = load(CONFIG)
    schedule = load(SCHEDULE)["schedule"]
    tasks = {str(row["task_id"]): row for row in load(GOLD)}
    records = {str(row["logical_call_id"]): row for row in load(LEDGER) if row.get("status") == "completed"}
    if len(schedule) != 1600 or len(tasks) != 400 or len(records) != 1600:
        raise RuntimeError("complete v27 400x4 grid required")
    strict: dict[str, dict[str, bool]] = defaultdict(dict)
    alias: dict[str, dict[str, bool]] = defaultdict(dict)
    rows: list[dict[str, Any]] = []
    for planned in schedule:
        record = records.get(str(planned["logical_call_id"]))
        if record is None or record.get("request_hash") != planned["request_hash"] or record.get("task_id") != planned["task_id"] or record.get("condition") != planned["condition"]:
            raise RuntimeError("v27 ledger/schedule binding drift")
        task_id, condition = str(planned["task_id"]), str(planned["condition"])
        expected = tasks[task_id].get("answers") or [tasks[task_id].get("answer")]
        answer = ""
        contract_valid = False
        try:
            answer = str(parse_response(record["raw_response"])["answer"])
            contract_valid = True
        except Exception:
            pass
        strict_correct = contract_valid and normalize_answer(answer) in {normalize_answer(str(value)) for value in expected if value is not None}
        alias_correct = contract_valid and alias_tolerant_correct(answer, [str(value) for value in expected if value is not None])
        strict[task_id][condition] = strict_correct
        alias[task_id][condition] = alias_correct
        rows.append({"task_id": task_id, "skill_family": planned["skill_family"], "condition": condition, "logical_call_id": planned["logical_call_id"], "request_hash": planned["request_hash"], "response_sha256": record["raw_response_sha256"], "contract_valid": contract_valid, "answer": answer, "strict_correct": strict_correct, "alias_tolerant_correct": alias_correct})
    if any(set(values) != set(CONDITIONS) for values in strict.values()) or len(strict) != 400:
        raise RuntimeError("v27 condition grid incomplete")
    strict_summary = paired_summary(strict, tasks)
    alias_summary = paired_summary(alias, tasks)
    mechanism: dict[str, Any] = {}
    for name, outcomes in (("strict", strict), ("alias_tolerant", alias)):
        ids = [task_id for task_id, values in outcomes.items() if values["cold"] and not values["global_only"]]
        typed = sum(outcomes[task_id]["contextual_typed_prior"] for task_id in ids)
        copied = sum(outcomes[task_id]["copied_global"] for task_id in ids)
        mechanism[name] = {"stratum_n": len(ids), "typed_recovers": typed, "copied_global_recovers": copied, "typed_recovery_minus_copied_global": (typed - copied) / len(ids) if ids else None}
    alias_nonnegative_families = sum(value["margin"] >= 0 for value in alias_summary["family_breakdown"].values())
    m = mechanism["alias_tolerant"]
    positive = (
        strict_summary["margin"] >= 0.05
        and alias_summary["margin"] >= 0.05
        and strict_summary["typed_wins"] - strict_summary["typed_losses"] >= 20
        and alias_summary["typed_wins"] - alias_summary["typed_losses"] >= 20
        and alias_nonnegative_families >= 4
        and m["stratum_n"] >= 20
        and m["typed_recovery_minus_copied_global"] is not None
        and m["typed_recovery_minus_copied_global"] >= 0.10
    )
    negative = (
        (alias_summary["margin"] <= 0 and alias_summary["typed_wins"] <= alias_summary["typed_losses"])
        or (strict_summary["margin"] <= -0.025 and alias_summary["margin"] <= -0.025)
    )
    gate = "positive" if positive else "negative" if negative else "inconclusive"
    result = {
        "schema_version": 27,
        "status": "complete",
        "tasks": 400,
        "rows": 1600,
        "strict": strict_summary,
        "alias_tolerant": alias_summary,
        "mechanism": mechanism,
        "alias_nonnegative_families": alias_nonnegative_families,
        "decision_gate": gate,
        "decision_rules": cfg["decision_rules"],
        "v23_gate_preserved": "inconclusive",
        "v25_gate_preserved": "negative",
        "schedule_sha256": sha256_file(SCHEDULE),
        "gold_sha256": sha256_file(GOLD),
        "ledger_sha256": sha256_file(LEDGER),
        "network_calls": 1600,
        "provider_calls": 1600,
        "paid_api_calls": 1600,
        "later_stage_calls": 0,
        "formal_scaling_calls": 0,
        "outcomes": rows,
    }
    result["aggregate_fingerprint"] = stable(result)
    return result


def report_text(result: dict[str, Any]) -> str:
    strict, alias, mechanism = result["strict"], result["alias_tolerant"], result["mechanism"]["alias_tolerant"]
    return (
        "# ACL 2027 Phase 2 post-v25 failure-analysis follow-up v27\n\n"
        "## Result\n\n"
        f"The exact 400-task, 1,600-row grid completed. Strict contextual-minus-global margin: `{strict['margin']:+.4f}` with `{strict['typed_wins']}/{strict['typed_losses']}/{strict['ties']}` wins/losses/ties. Alias-tolerant margin: `{alias['margin']:+.4f}` with `{alias['typed_wins']}/{alias['typed_losses']}/{alias['ties']}`.\n\n"
        f"The alias-tolerant global-prior-degradation stratum contained `{mechanism['stratum_n']}` tasks; typed recovery minus copied-global recovery was `{mechanism['typed_recovery_minus_copied_global']}`. Frozen decision gate: **{result['decision_gate']}**.\n\n"
        "## Evidence boundary\n\n"
        "The v23 inconclusive and v25 negative gates remain unchanged. This v27 gate applies only to the independently frozen v26 follow-up. No later stage, other model, or formal scaling is authorized by this result.\n\n"
        "## Integrity\n\n"
        f"Aggregate fingerprint: `{result['aggregate_fingerprint']}`.\n"
    )


if __name__ == "__main__":
    result = analyze()
    AUDIT.write_text(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    REPORT.write_text(report_text(result), encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2, sort_keys=True))
