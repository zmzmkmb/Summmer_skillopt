#!/usr/bin/env python3
"""Frozen combined analysis for v27, reusable v29, and completed v31."""
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
from scripts.run_acl2027_phase2_post_v25_failure_analysis_recovery_preflight_v30 import complete_task_ids

CONFIG = ROOT / "configs/acl2027/phase2_post_v25_failure_analysis_design_preflight_v26.json"
V27 = ROOT / "artifacts/acl2027_phase2_post_v25_failure_analysis_live_v27"
V29 = ROOT / "artifacts/acl2027_phase2_post_v25_failure_analysis_recovery_live_v29"
V30 = ROOT / "artifacts/acl2027_phase2_post_v25_failure_analysis_recovery_preflight_v30"
V31 = ROOT / "artifacts/acl2027_phase2_post_v25_failure_analysis_second_recovery_live_v31"
V27_LEDGER = V27 / "ledger.json"
V29_LEDGER = V29 / "ledger.json"
V31_LEDGER = V31 / "ledger.json"
V31_RUN_AUDIT = V31 / "run_audit.json"
GOLD = V30 / "combined_private_gold.json"
SCHEDULE = V30 / "second_recovery_schedule.json"
AUDIT = V31 / "combined_failure_analysis_audit.json"
REPORT = ROOT / "paper/acl2027/results/phase2_post_v25_failure_analysis_second_recovery_live_v31.md"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def analyze() -> dict[str, Any]:
    cfg = load(CONFIG)
    tasks = {str(row["task_id"]): row for row in load(GOLD)}
    v27 = [row for row in load(V27_LEDGER) if row.get("status") == "completed"]
    v29_all = load(V29_LEDGER)
    reusable_v29 = complete_task_ids(v29_all)
    v29 = [row for row in v29_all if row.get("status") == "completed" and str(row["task_id"]) in reusable_v29]
    v31 = [row for row in load(V31_LEDGER) if row.get("status") == "completed"]
    run_audit = load(V31_RUN_AUDIT)
    if len(v27) != 1072 or len(v29) != 308 or len(v31) != 220 or run_audit.get("status") != "completed" or run_audit.get("authorization_closed") is not True:
        raise RuntimeError("complete v27+v29+v31 grid required")
    records = v27 + v29 + v31
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
        logical = str(record["logical_call_id"])
        source = "v27" if logical.startswith("phase2-v26:") else "v29" if logical.startswith("phase2-v28:") else "v31"
        outcomes.append({"task_id": task_id, "skill_family": task["skill_family"], "condition": condition, "source_run": source, "logical_call_id": logical, "request_hash": record["request_hash"], "response_sha256": record["raw_response_sha256"], "contract_valid": contract_valid, "answer": answer, "strict_correct": strict_correct, "alias_tolerant_correct": alias_correct})
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
    result = {"schema_version": 31, "status": "complete", "tasks": 400, "rows": 1600, "v27_preserved_rows": 1072, "v29_preserved_rows": 308, "v31_recovery_rows": 220, "strict": strict_summary, "alias_tolerant": alias_summary, "mechanism": mechanism, "alias_nonnegative_families": alias_nonnegative_families, "decision_gate": gate, "decision_rules": cfg["decision_rules"], "v23_gate_preserved": "inconclusive", "v25_gate_preserved": "negative", "v27_v29_terminal_provenance_preserved": True, "gold_sha256": sha256_file(GOLD), "v30_schedule_sha256": sha256_file(SCHEDULE), "v27_ledger_sha256": sha256_file(V27_LEDGER), "v29_ledger_sha256": sha256_file(V29_LEDGER), "v31_ledger_sha256": sha256_file(V31_LEDGER), "v31_run_audit_sha256": sha256_file(V31_RUN_AUDIT), "provider_attempts": 1603, "completed_calls": 1600, "later_stage_calls": 0, "formal_scaling_calls": 0, "outcomes": outcomes}
    result["aggregate_fingerprint"] = stable(result)
    return result


def report_text(result: dict[str, Any]) -> str:
    strict, alias, mechanism = result["strict"], result["alias_tolerant"], result["mechanism"]["alias_tolerant"]
    return (
        "# ACL 2027 Phase 2 second recovery v31\n\n"
        f"The combined 400-task, 1,600-row grid completed using 1,072 v27 rows, 308 reusable v29 rows, and 220 v31 rows. Strict contextual-minus-global margin: `{strict['margin']:+.4f}` with `{strict['typed_wins']}/{strict['typed_losses']}/{strict['ties']}` wins/losses/ties. Alias-tolerant margin: `{alias['margin']:+.4f}` with `{alias['typed_wins']}/{alias['typed_losses']}/{alias['ties']}`.\n\n"
        f"The alias-tolerant degradation stratum contained `{mechanism['stratum_n']}` tasks; typed recovery minus copied-global was `{mechanism['typed_recovery_minus_copied_global']}`. Frozen decision gate: **{result['decision_gate']}**.\n\n"
        "The v23 inconclusive and v25 negative gates remain unchanged. Terminal v27/v29 attempts and orphan rows remain excluded provenance. No later stage, other model, or formal scaling is authorized.\n\n"
        f"Aggregate fingerprint: `{result['aggregate_fingerprint']}`.\n"
    )


if __name__ == "__main__":
    result = analyze()
    AUDIT.write_text(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    REPORT.write_text(report_text(result), encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2, sort_keys=True))
