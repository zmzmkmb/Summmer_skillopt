#!/usr/bin/env python3
"""Non-gating plain-text diagnostic for the closed Phase 2 v7 calibration."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.acl2027_phase2_response_verifier_v3 import normalize_answer, sha256_file

ARTIFACT = ROOT / "artifacts/acl2027_phase2_calibration_live_v7"
LEDGER = ARTIFACT / "ledger.json"
AUDIT = ARTIFACT / "calibration_audit.json"
GOLD = ROOT / "data/searchqa_phase2_verified/calibration.json"
OUTPUT = ARTIFACT / "plain_text_diagnostic.json"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build_diagnostic() -> dict[str, Any]:
    records = load(LEDGER)
    audit = load(AUDIT)
    gold = {row["task_id"]: row for row in load(GOLD)}
    if audit.get("status") != "completed" or len(records) != 60:
        raise RuntimeError("v7 calibration is not a closed complete 60-row ledger")
    rows = []
    for record in records:
        raw = record["raw_response"]
        gold_row = gold[record["task_id"]]
        answers = gold_row.get("answers") or [gold_row["answer"]]
        normalized_raw = normalize_answer(raw)
        normalized_answers = [normalize_answer(answer) for answer in answers]
        exact_plain = normalized_raw in normalized_answers
        gold_contained = any(answer and answer in normalized_raw for answer in normalized_answers)
        rows.append({
            "logical_call_id": record["logical_call_id"],
            "task_id": record["task_id"],
            "skill_family": record["skill_family"],
            "exact_plain_answer": exact_plain,
            "gold_answer_contained": gold_contained,
            "raw_response_sha256": record["raw_response_sha256"],
        })
    per_family = {}
    for family in sorted({row["skill_family"] for row in rows}):
        subset = [row for row in rows if row["skill_family"] == family]
        per_family[family] = {
            "rows": len(subset),
            "exact_plain_answer": sum(row["exact_plain_answer"] for row in subset),
            "gold_answer_contained": sum(row["gold_answer_contained"] for row in subset),
        }
    exact = sum(row["exact_plain_answer"] for row in rows)
    contained = sum(row["gold_answer_contained"] for row in rows)
    return {
        "schema_version": 1,
        "status": "non_gating_diagnostic_only",
        "scientific_gate_override_allowed": False,
        "strict_contract_valid": audit["contract_valid"],
        "strict_answer_correct": audit["answer_correct"],
        "plain_text_outputs": sum(not record["raw_response"].lstrip().startswith(("{", "```")) for record in records),
        "exact_plain_answer": exact,
        "exact_plain_answer_rate": exact / len(rows),
        "gold_answer_contained": contained,
        "gold_answer_contained_rate": contained / len(rows),
        "per_family": per_family,
        "protocol_diagnosis": "The frozen request says to return the frozen response schema but does not include the required exact JSON schema; all provider outputs were plain text while the frozen parser accepts only an object containing exactly the answer key.",
        "ledger_sha256": sha256_file(LEDGER),
        "audit_sha256": sha256_file(AUDIT),
        "gold_sha256": sha256_file(GOLD),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    diagnostic = build_diagnostic()
    if args.write:
        OUTPUT.write_text(json.dumps(diagnostic, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in diagnostic.items() if key != "rows"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
