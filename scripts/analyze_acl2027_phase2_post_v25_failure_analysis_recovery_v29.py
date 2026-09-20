#!/usr/bin/env python3
"""Frozen combined analysis for completed v27 provenance plus v29 recovery."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import normalize_answer, parse_response, sha256_file, stable
from scripts.analyze_acl2027_phase2_post_v25_failure_analysis_v27 import paired_summary
from scripts.run_acl2027_phase2_post_v25_failure_analysis_design_preflight_v26 import CONDITIONS, alias_tolerant_correct

CONFIG = ROOT / "configs/acl2027/phase2_post_v25_failure_analysis_design_preflight_v26.json"
V27 = ROOT / "artifacts/acl2027_phase2_post_v25_failure_analysis_live_v27"
V28 = ROOT / "artifacts/acl2027_phase2_post_v25_failure_analysis_recovery_preflight_v28"
V29 = ROOT / "artifacts/acl2027_phase2_post_v25_failure_analysis_recovery_live_v29"
V27_LEDGER = V27 / "ledger.json"
V27_CORRECTED = V27 / "run_audit_v27_1.json"
V29_LEDGER = V29 / "ledger.json"
V29_RUN_AUDIT = V29 / "run_audit.json"
GOLD = V28 / "combined_private_gold.json"
SCHEDULE = V28 / "failure_analysis_recovery_schedule.json"
AUDIT = V29 / "combined_failure_analysis_audit.json"
REPORT = ROOT / "paper/acl2027/results/phase2_post_v25_failure_analysis_recovery_live_v29.md"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def analyze() -> dict[str, Any]:
    cfg = load(CONFIG)
    tasks = {str(row["task_id"]): row for row in load(GOLD)}
    v27 = [row for row in load(V27_LEDGER) if row.get("status") == "completed"]
    v29 = [row for row in load(V29_LEDGER) if row.get("status") == "completed"]
    run_audit = load(V29_RUN_AUDIT)
    if len(v27) != 1072 or len(v29) != 528 or run_audit.get("status") != "completed" or run_audit.get("authorization_closed") is not True:
        raise RuntimeError("complete v27+v29 400x4 grid required")
    records = v27 + v29
    if len(tasks) != 400 or len(records) != 1600 or len({(row["task_id"], row["condition"]) for row in records}) != 1600:
        raise RuntimeError("combined failure-analysis grid drift")
    strict: dict[str, dict[str, bool]] = defaultdict(dict)
    alias: dict[str, dict[str, bool]] = defaultdict(dict)
    outcomes: list[dict[str, Any]] = []
    for record in records:
        task_id, condition = str(record["task_id"]), str(record["condition"])
        task = tasks.get(task_id)
        if task is None or condition not in CONDITIONS:
            raise RuntimeError("combined ledger/gold binding drift")
        expected = task.get("answers") or [task.get("answer")]
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
        outcomes.append({"task_id": task_id, "skill_family": task["skill_family"], "condition": condition, "source_run": "v27" if record["logical_call_id"].startswith("phase2-v26:") else "v29", "logical_call_id": record["logical_call_id"], "request_hash": record["request_hash"], "response_sha256": record["raw_response_sha256"], "contract_valid": contract_valid, "answer": answer, "strict_correct": strict_correct, "alias_tolerant_correct": alias_correct})
    if len(strict) != 400 or any(set(values) != set(CONDITIONS) for values in strict.values()):
        raise RuntimeError("combined condition grid incomplete")
    strict_summary = paired_summary(strict, tasks)
    alias_summary = paired_summary(alias, tasks)
    mechanism: dict[str, Any] = {}
    for name, values_by_task in (("strict", strict), ("alias_tolerant", alias)):
        ids = [task_id for task_id, values in values_by_task.items() if values["cold"] and not values["global_only"]]
        typed = sum(values_by_task[task_id]["contextual_typed_prior"] for task_id in ids)
        copied = sum(values_by_task[task_id]["copied_global"] for task_id in ids)
        mechanism[name] = {"stratum_n": len(ids), "typed_recovers": typed, "copied_global_recovers": copied, "typed_recovery_minus_copied_global": (typed - copied) / len(ids) if ids else None}
    alias_nonnegative_families = sum(value["margin"] >= 0 for value in alias_summary["family_breakdown"].values())
    m = mechanism["alias_tolerant"]
    positive = strict_summary["margin"] >= 0.05 and alias_summary["margin"] >= 0.05 and strict_summary["typed_wins"] - strict_summary["typed_losses"] >= 20 and alias_summary["typed_wins"] - alias_summary["typed_losses"] >= 20 and alias_nonnegative_families >= 4 and m["stratum_n"] >= 20 and m["typed_recovery_minus_copied_global"] is not None and m["typed_recovery_minus_copied_global"] >= 0.10
    negative = (alias_summary["margin"] <= 0 and alias_summary["typed_wins"] <= alias_summary["typed_losses"]) or (strict_summary["margin"] <= -0.025 and alias_summary["margin"] <= -0.025)
    gate = "positive" if positive else "negative" if negative else "inconclusive"
    result = {"schema_version": 29, "status": "complete", "tasks": 400, "rows": 1600, "v27_preserved_rows": 1072, "v29_recovery_rows": 528, "strict": strict_summary, "alias_tolerant": alias_summary, "mechanism": mechanism, "alias_nonnegative_families": alias_nonnegative_families, "decision_gate": gate, "decision_rules": cfg["decision_rules"], "v23_gate_preserved": "inconclusive", "v25_gate_preserved": "negative", "v27_terminal_provenance_preserved": True, "gold_sha256": sha256_file(GOLD), "v28_schedule_sha256": sha256_file(SCHEDULE), "v27_ledger_sha256": sha256_file(V27_LEDGER), "v27_corrected_audit_sha256": sha256_file(V27_CORRECTED), "v29_ledger_sha256": sha256_file(V29_LEDGER), "v29_run_audit_sha256": sha256_file(V29_RUN_AUDIT), "network_calls": 1601, "provider_attempts": 1601, "completed_calls": 1600, "later_stage_calls": 0, "formal_scaling_calls": 0, "outcomes": outcomes}
    result["aggregate_fingerprint"] = stable(result)
    return result


def report_text(result: dict[str, Any]) -> str:
    strict, alias, mechanism = result["strict"], result["alias_tolerant"], result["mechanism"]["alias_tolerant"]
    return (
        "# ACL 2027 Phase 2 failure-analysis recovery v29\n\n"
        "## Result\n\n"
        f"The combined 400-task, 1,600-row grid completed using 1,072 preserved v27 rows and 528 v29 recovery rows. Strict contextual-minus-global margin: `{strict['margin']:+.4f}` with `{strict['typed_wins']}/{strict['typed_losses']}/{strict['ties']}` wins/losses/ties. Alias-tolerant margin: `{alias['margin']:+.4f}` with `{alias['typed_wins']}/{alias['typed_losses']}/{alias['ties']}`.\n\n"
        f"The alias-tolerant global-prior-degradation stratum contained `{mechanism['stratum_n']}` tasks; typed recovery minus copied-global recovery was `{mechanism['typed_recovery_minus_copied_global']}`. Frozen decision gate: **{result['decision_gate']}**.\n\n"
        "## Evidence boundary\n\nThe v23 inconclusive and v25 negative gates remain unchanged. The terminal v27 attempt remains excluded, all spent identities remain provenance, and this result authorizes no later stage, other model, or formal scaling.\n\n"
        f"Aggregate fingerprint: `{result['aggregate_fingerprint']}`.\n"
    )


if __name__ == "__main__":
    result = analyze()
    AUDIT.write_text(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    REPORT.write_text(report_text(result), encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2, sort_keys=True))
