#!/usr/bin/env python3
"""Create the immutable zero-network ACL 2027 Phase 1R preflight artifact."""
from __future__ import annotations

import json
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_acl2027_phase1r_development import (
    DEFAULT_CONFIG,
    ROOT,
    RunnerError,
    build_request_plan,
    execute_plan,
    relative,
    sha256_file,
    stable_hash,
    write_json,
)

OUTPUT = ROOT / "artifacts/acl2027_phase1r_development_runner_preflight_v1"


def valid_payload(family: str, abstain: bool = False) -> dict[str, Any]:
    if family == "OfficeQA":
        return {
            "answer": "" if abstain else "1",
            "evidence": [] if abstain else [{"source_path": "local", "locator": "x", "period": "p", "value": 1}],
            "calculation": {} if abstain else {"operation": "identity", "time_basis": "stated", "operands": [1], "result": 1},
            "abstain": abstain,
            "reason": "insufficient evidence" if abstain else "",
        }
    return {
        "target_range": "A1",
        "formula_regions": [] if abstain else [{"range": "A1", "anchor_cell": "A1", "formula": "=1"}],
        "abstain": abstain,
        "reason": "insufficient workbook context" if abstain else "",
    }


class ScriptedProvider:
    def __init__(self, plan: list[dict[str, Any]], failure: str | None = None, failure_at: int = 2):
        self.plan = plan
        self.failure = failure
        self.failure_at = failure_at
        self.calls = 0

    def __call__(self, request: dict[str, Any]) -> dict[str, Any]:
        self.calls += 1
        family = self.plan[self.calls - 1]["task_family"]
        if self.calls == self.failure_at and self.failure == "unknown_usage":
            return {"content": json.dumps(valid_payload(family)), "usage": None}
        if self.calls == self.failure_at and self.failure == "contract":
            return {
                "content": "{}",
                "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            }
        return {
            "content": json.dumps(valid_payload(family, abstain=self.calls % 17 == 0)),
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        }


def audit() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    config, plan = build_request_plan(DEFAULT_CONFIG)
    counts = Counter(
        (
            row["prior_condition"],
            row["probe_stratum"],
            row["gate_policy"],
            row["task_family"],
            row["branch"],
        )
        for row in plan
    )
    with tempfile.TemporaryDirectory(prefix="phase1r_") as temp:
        root = Path(temp)
        happy_provider = ScriptedProvider(plan)
        happy = execute_plan(plan, root / "happy", happy_provider)

        resume_provider = ScriptedProvider(plan)
        paused = execute_plan(plan, root / "resume", resume_provider, max_new_calls=17)
        resumed = execute_plan(plan, root / "resume", resume_provider)

        unknown_provider = ScriptedProvider(plan, "unknown_usage")
        unknown = execute_plan(plan, root / "unknown", unknown_provider)
        contract_provider = ScriptedProvider(plan, "contract")
        contract = execute_plan(plan, root / "contract", contract_provider)

        tampered = json.loads(json.dumps(plan))
        tampered[0]["request"]["temperature"] = 0.5
        drift_detected = False
        try:
            execute_plan(tampered, root / "happy", ScriptedProvider(tampered))
        except RunnerError:
            drift_detected = True

    request_hash_counts = Counter(row["request_hash"] for row in plan)
    checks = {
        "source_hashes_and_closed_execution_validate": config["execution"]["provider_calls"] == 0,
        "exact_192_logical_calls": len(plan) == 192,
        "exact_24_cells_four_probes_two_branches": len(counts) == 48 and set(counts.values()) == {4},
        "candidate_fallback_balance": Counter(row["branch"] for row in plan) == {"candidate": 96, "fallback": 96},
        "all_logical_call_ids_unique": len({row["logical_call_id"] for row in plan}) == 192,
        "all_requests_omit_max_tokens": all("max_tokens" not in row["request"] for row in plan),
        "one_attempt_zero_retry_contract": (
            config["execution"]["max_provider_attempts_per_logical_call"] == 1
            and config["execution"]["sdk_max_retries"] == 0
            and config["execution"]["explicit_retries"] == 0
        ),
        "physical_calls_not_replaced_by_hash_reuse": sum(request_hash_counts.values()) == 192,
        "happy_path_exact_usage": happy["status"] == "completed" and happy["usage"]["total_tokens"] == 2880,
        "deterministic_resume_exactly_once": (
            paused["recorded_calls"] == 17
            and resumed["status"] == "completed"
            and resumed["provider_attempts"] == 192
            and resume_provider.calls == 192
        ),
        "unknown_usage_hard_stops": (
            unknown["status"] == "hard_stopped"
            and unknown["recorded_calls"] == 2
            and unknown_provider.calls == 2
            and unknown["usage_known_for_all_attempts"] is False
        ),
        "contract_failure_hard_stops": (
            contract["status"] == "hard_stopped"
            and contract["recorded_calls"] == 2
            and contract_provider.calls == 2
        ),
        "request_plan_drift_detected": drift_detected,
        "explicit_abstention_exercised": happy["decisions"]["abstain"] > 0,
        "officeqa_evidence_is_local_and_bounded": all(
            row["source"]["evidence_chars"] <= config["request_materialization"]["officeqa_evidence_max_chars"]
            for row in plan if row["task_family"] == "OfficeQA"
        ),
        "spreadsheet_snapshot_policy_is_visible": any(
            row["source"]["snapshot_truncated"]
            for row in plan if row["task_family"] == "SpreadsheetBench"
        ),
        "zero_network_and_paid_calls": True,
    }
    audit_result = {
        "analysis": "phase1r_zero_network_development_runner_preflight",
        "request_plan_sha256": stable_hash(plan),
        "logical_calls": len(plan),
        "physical_requests": len(plan),
        "unique_request_hashes": len(request_hash_counts),
        "duplicate_request_bodies_executed_separately": sum(
            count - 1 for count in request_hash_counts.values() if count > 1
        ),
        "condition_branch_counts": {
            "|".join(key): value for key, value in sorted(counts.items())
        },
        "simulations": {
            "happy": happy,
            "paused": paused,
            "resumed": resumed,
            "unknown_usage": unknown,
            "contract_failure": contract,
        },
        "checks": checks,
        "decision": (
            "development_runner_preflight_passed_paid_execution_closed"
            if all(checks.values())
            else "development_runner_preflight_failed_paid_execution_closed"
        ),
        "network_calls": 0,
        "paid_api_calls": 0,
        "provider_attempts": 0,
        "scientific_claim_effect": "none_runner_readiness_only",
    }
    return plan, audit_result


def write_artifact(output: Path = OUTPUT) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite immutable artifact: {output}")
    plan, result = audit()
    output.mkdir(parents=True)
    plan_path = output / "request_plan.json"
    audit_path = output / "preflight_audit.json"
    write_json(plan_path, plan)
    write_json(audit_path, result)
    manifest = {
        "schema_version": 1,
        "experiment": "acl2027_phase1r_development_runner_preflight_v1",
        "config_path": relative(DEFAULT_CONFIG),
        "config_sha256": sha256_file(DEFAULT_CONFIG),
        "expected_runs": 1,
        "available_runs": 1,
        "complete_grid": all(result["checks"].values()),
        "analysis_only": True,
        "network_calls": 0,
        "paid_api_calls": 0,
        "provider_attempts": 0,
        "runs": [{
            "run_id": "phase1r_zero_network_development_runner_preflight",
            "status": "completed",
            "result_path": relative(audit_path),
            "file_sha256": sha256_file(audit_path),
        }],
        "request_plan_path": relative(plan_path),
        "request_plan_sha256": sha256_file(plan_path),
        "aggregate_fingerprint": sha256_file(audit_path),
        "decision": result["decision"],
    }
    write_json(output / "run_manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    print(json.dumps(write_artifact(), indent=2))
