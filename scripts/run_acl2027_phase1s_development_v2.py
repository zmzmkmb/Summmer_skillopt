#!/usr/bin/env python3
"""Preflight the resilient ACL 2027 Phase 1S v2 execution contract."""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_acl2027_phase1r_development import (
    HardStop,
    RunnerError,
    exact_usage,
    read_json,
    sha256_file,
    stable_hash,
    validate_response_contract,
    write_json,
)

DEFAULT_CONFIG = (
    ROOT / "configs/acl2027/phase1s_development_method_effect_live_v2.json"
)


def normalize_response_text(raw_text: str) -> str:
    text = raw_text.removeprefix("\ufeff").strip()
    if text.startswith("```") and text.endswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            opener = text[:first_newline].strip().lower()
            if opener in {"```", "```json"}:
                text = text[first_newline + 1 : -3].strip()
    return text


def validate_config_data(config: dict[str, Any]) -> None:
    if config.get("phase") != "1S":
        raise RunnerError("config phase must be 1S")
    execution = config["execution"]
    if not (
        execution["protocol_only"] is True
        and execution["paid_api_allowed"] is False
        and execution["network_calls_allowed"] is False
        and execution["provider_calls_authorized"] == 0
        and execution["formal_scaling_allowed"] is False
    ):
        raise RunnerError("Phase 1S v2 preflight must remain zero-network and unpaid")
    if (
        execution["model_id"] != "qwen3.7-plus"
        or execution["logical_calls"] != 192
        or execution["physical_requests"] != 192
        or execution["max_provider_attempts_per_logical_call"] != 1
        or execution["sdk_max_retries"] != 0
        or execution["explicit_retries"] != 0
        or execution["request_interval_seconds"] != 1.0
    ):
        raise RunnerError("Phase 1S v2 model, call, pacing, or retry drift")
    if "max_tokens" not in execution["request_body_forbidden_keys"]:
        raise RunnerError("max_tokens omission is not frozen")
    authorization = config["authorization_gate"]
    if (
        authorization["status"] != "closed_preflight_only"
        or authorization["new_explicit_authorization_required"] is not True
        or authorization["qwen3.8_max_allowed"]
        or authorization["staged_384_calls_allowed"]
        or authorization["full_960_calls_allowed"]
    ):
        raise RunnerError("Phase 1S v2 authorization closure drift")
    normalization = config["normalization_contract"]
    if normalization["raw_provider_text_preserved_exactly"] is not True:
        raise RunnerError("raw provider text preservation is required")
    if "type_coercion" not in normalization["forbidden"]:
        raise RunnerError("type coercion must remain forbidden")


def load_frozen_plan(
    config_path: Path = DEFAULT_CONFIG,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    config = read_json(config_path)
    validate_config_data(config)
    for name, source in config["terminal_v1_binding"].items():
        if not isinstance(source, dict) or "path" not in source:
            continue
        path = ROOT / source["path"]
        if not path.is_file() or sha256_file(path) != source["sha256"]:
            raise RunnerError(f"terminal v1 hash mismatch: {name}")
    binding = config["immutable_request_plan"]
    plan_path = ROOT / binding["path"]
    if sha256_file(plan_path) != binding["file_sha256"]:
        raise RunnerError("immutable request-plan file hash mismatch")
    plan = read_json(plan_path)
    if stable_hash(plan) != binding["stable_sha256"]:
        raise RunnerError("immutable request-plan stable hash mismatch")
    if len(plan) != 192 or len(plan) != binding["logical_calls"]:
        raise RunnerError("immutable request-plan call-count drift")
    if sum(row["branch"] == "candidate" for row in plan) != 96:
        raise RunnerError("candidate branch count drift")
    if sum(row["branch"] == "fallback" for row in plan) != 96:
        raise RunnerError("fallback branch count drift")
    if any("max_tokens" in row["request"] for row in plan):
        raise RunnerError("frozen request plan contains max_tokens")
    return config, plan


def _load_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def execute_plan_v2(
    plan: list[dict[str, Any]],
    output_dir: Path,
    provider: Callable[[dict[str, Any]], dict[str, Any]],
    *,
    max_new_calls: int | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    plan_hash = stable_hash(plan)
    plan_path = output_dir / "request_plan.json"
    if plan_path.exists():
        if stable_hash(read_json(plan_path)) != plan_hash:
            raise RunnerError("request plan drift")
    else:
        write_json(plan_path, plan)

    results_path = output_dir / "results.jsonl"
    records = _load_records(results_path)
    if len(records) > len(plan):
        raise RunnerError("call-count drift")
    seen: set[str] = set()
    for index, record in enumerate(records):
        expected = plan[index]
        if (
            record.get("logical_call_id") != expected["logical_call_id"]
            or record.get("request_hash") != expected["request_hash"]
            or record.get("call_index") != expected["call_index"]
        ):
            raise RunnerError("completed records are not an exact plan prefix")
        if record["logical_call_id"] in seen:
            raise RunnerError("duplicate logical call ID in resume records")
        seen.add(record["logical_call_id"])
        if record.get("terminal"):
            raise HardStop("terminal failure is not resumable")

    made = 0
    for item in plan[len(records) :]:
        if max_new_calls is not None and made >= max_new_calls:
            break
        made += 1
        base = {
            "call_index": item["call_index"],
            "logical_call_id": item["logical_call_id"],
            "request_hash": item["request_hash"],
            "task_family": item["task_family"],
            "task_id": item["task_id"],
            "branch": item["branch"],
            "attempt_count": 1,
        }
        try:
            response = provider(deepcopy(item["request"]))
        except Exception as exc:  # noqa: BLE001
            record = {
                **base,
                "status": "hard_stop",
                "terminal": True,
                "usage_known": False,
                "error_stage": "provider",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        else:
            try:
                usage = exact_usage(response)
            except Exception as exc:  # noqa: BLE001
                record = {
                    **base,
                    "status": "hard_stop",
                    "terminal": True,
                    "usage_known": False,
                    "error_stage": "usage",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            else:
                raw_text = str(response.get("content", ""))
                normalized_text = normalize_response_text(raw_text)
                common = {
                    **base,
                    "terminal": False,
                    "usage_known": True,
                    **usage,
                    "raw_response_text": raw_text,
                    "raw_response_sha256": stable_hash(raw_text),
                    "normalized_response_text": normalized_text,
                    "normalization_changed_text": normalized_text != raw_text,
                }
                try:
                    payload = json.loads(normalized_text)
                    contract = validate_response_contract(
                        item["task_family"], payload
                    )
                except Exception as exc:  # noqa: BLE001
                    stage = (
                        "json_parse"
                        if isinstance(exc, json.JSONDecodeError)
                        else "response_contract"
                    )
                    record = {
                        **common,
                        "status": "invalid_output",
                        "contract_valid": False,
                        "scientific_outcome": "invalid",
                        "error_stage": stage,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                else:
                    record = {
                        **common,
                        "status": "completed",
                        "contract_valid": True,
                        "scientific_outcome": "valid",
                        "response": payload,
                        **contract,
                    }
        with results_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n"
            )
        records.append(record)
        if record["terminal"]:
            break

    valid = sum(row["status"] == "completed" for row in records)
    invalid = sum(row["status"] == "invalid_output" for row in records)
    terminal = bool(records and records[-1].get("terminal"))
    manifest = {
        "schema_version": 2,
        "status": (
            "hard_stopped"
            if terminal
            else "completed_with_invalid_outputs"
            if len(records) == len(plan) and invalid
            else "completed"
            if len(records) == len(plan)
            else "paused"
        ),
        "request_plan_sha256": plan_hash,
        "planned_logical_calls": len(plan),
        "recorded_calls": len(records),
        "valid_calls": valid,
        "invalid_output_calls": invalid,
        "provider_attempts": len(records),
        "usage_known_for_all_attempts": all(
            row.get("usage_known") is True for row in records
        ),
        "raw_response_preserved_for_known_usage_attempts": all(
            "raw_response_text" in row
            for row in records
            if row.get("usage_known") is True
        ),
        "decisions": {
            decision: sum(row.get("decision") == decision for row in records)
            for decision in ("execute", "abstain")
        },
        "usage": {
            key: sum(int(row.get(key, 0)) for row in records)
            for key in ("input_tokens", "output_tokens", "total_tokens")
        },
    }
    write_json(output_dir / "run_manifest.json", manifest)
    return manifest


def valid_payload(family: str, *, abstain: bool = False) -> dict[str, Any]:
    if family == "OfficeQA":
        return {
            "answer": "" if abstain else "1",
            "evidence": [] if abstain else [{"value": 1}],
            "calculation": {} if abstain else {
                "operation": "sum",
                "time_basis": "calendar",
                "operands": [1],
                "result": 1,
            },
            "abstain": abstain,
            "reason": "insufficient evidence" if abstain else "",
        }
    return {
        "target_range": "A1",
        "formula_regions": [] if abstain else [
            {"range": "A1", "anchor_cell": "A1", "formula": "=1"}
        ],
        "abstain": abstain,
        "reason": "insufficient snapshot" if abstain else "",
    }


class SimulatedProvider:
    def __init__(self, plan: list[dict[str, Any]], modes: dict[int, str] | None = None):
        self.plan = plan
        self.modes = modes or {}
        self.calls = 0

    def __call__(self, request: dict[str, Any]) -> dict[str, Any]:
        index = self.calls
        self.calls += 1
        if stable_hash(request) != self.plan[index]["request_hash"]:
            raise RunnerError("simulated provider request drift")
        mode = self.modes.get(index + 1, "valid")
        usage = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
        family = self.plan[index]["task_family"]
        if mode == "unknown_usage":
            return {"content": "{}", "usage": None}
        if mode == "provider_exception":
            raise RuntimeError("simulated provider exception")
        if mode == "malformed_json":
            return {"content": '{"answer":', "usage": usage}
        if mode == "wrong_type":
            payload = valid_payload(family)
            if family == "OfficeQA":
                payload["calculation"] = "1+0"
            else:
                payload["formula_regions"] = "not-a-list"
            return {"content": json.dumps(payload), "usage": usage}
        if mode == "abstain":
            payload = valid_payload(family, abstain=True)
        else:
            payload = valid_payload(family)
        content = "\ufeff  ```json\n" + json.dumps(payload) + "\n```  "
        return {"content": content, "usage": usage}


def run_preflight(output_dir: Path) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite immutable artifact: {output_dir}")
    config, plan = load_frozen_plan()
    output_dir.mkdir(parents=True)
    simulations = output_dir / "simulations"

    valid = execute_plan_v2(
        plan, simulations / "valid_abstain",
        SimulatedProvider(plan, {2: "abstain"}), max_new_calls=2
    )
    malformed = execute_plan_v2(
        plan, simulations / "malformed",
        SimulatedProvider(plan, {1: "malformed_json"}), max_new_calls=2
    )
    wrong_type = execute_plan_v2(
        plan, simulations / "wrong_type",
        SimulatedProvider(plan, {1: "wrong_type"}), max_new_calls=2
    )
    unknown = execute_plan_v2(
        plan, simulations / "unknown_usage",
        SimulatedProvider(plan, {1: "unknown_usage"})
    )
    resume_provider = SimulatedProvider(plan)
    paused = execute_plan_v2(
        plan, simulations / "resume", resume_provider, max_new_calls=3
    )
    resumed = execute_plan_v2(
        plan, simulations / "resume", resume_provider, max_new_calls=2
    )

    drift_detected = False
    changed = deepcopy(plan)
    changed[0]["request"]["temperature"] = 0.25
    try:
        execute_plan_v2(
            changed, simulations / "resume", SimulatedProvider(changed),
            max_new_calls=1
        )
    except RunnerError as exc:
        drift_detected = "plan drift" in str(exc)

    malformed_records = _load_records(
        simulations / "malformed" / "results.jsonl"
    )
    wrong_records = _load_records(
        simulations / "wrong_type" / "results.jsonl"
    )
    checks = {
        "same_immutable_192_call_plan": len(plan) == 192
        and stable_hash(plan)
        == config["immutable_request_plan"]["stable_sha256"],
        "terminal_v1_hashes_preserved": all(
            sha256_file(ROOT / item["path"]) == item["sha256"]
            for item in config["terminal_v1_binding"].values()
            if isinstance(item, dict) and "path" in item
        ),
        "zero_network_and_paid_calls": config["execution"]["network_calls_allowed"]
        is False
        and config["execution"]["paid_api_allowed"] is False,
        "valid_response_and_abstention": valid["valid_calls"] == 2
        and valid["decisions"] == {"execute": 1, "abstain": 1},
        "malformed_known_usage_continues": malformed["recorded_calls"] == 2
        and malformed["invalid_output_calls"] == 1
        and malformed_records[0]["terminal"] is False,
        "wrong_type_known_usage_continues": wrong_type["recorded_calls"] == 2
        and wrong_type["invalid_output_calls"] == 1
        and wrong_records[0]["error_stage"] == "response_contract",
        "unknown_usage_is_terminal": unknown["status"] == "hard_stopped"
        and unknown["recorded_calls"] == 1,
        "deterministic_resume": paused["recorded_calls"] == 3
        and resumed["recorded_calls"] == 5
        and resume_provider.calls == 5,
        "request_plan_drift_detected": drift_detected,
        "raw_response_preserved": malformed_records[0]["raw_response_text"]
        == '{"answer":'
        and wrong_records[0]["raw_response_sha256"]
        == stable_hash(wrong_records[0]["raw_response_text"]),
        "normalization_does_not_coerce_types": wrong_records[0][
            "normalized_response_text"
        ].find('"calculation": "1+0"') >= 0,
        "no_max_tokens": all(
            "max_tokens" not in row["request"] for row in plan
        ),
    }
    audit = {
        "analysis": "phase1s_v2_zero_network_response_resilience_preflight",
        "decision": (
            "preflight_passed_new_paid_authorization_required"
            if all(checks.values())
            else "preflight_failed"
        ),
        "checks": checks,
        "network_calls": 0,
        "paid_api_calls": 0,
        "provider_attempts": 0,
        "request_plan_sha256": stable_hash(plan),
        "terminal_v1_spent_call_reused": False,
        "simulations": {
            "valid_abstain": valid,
            "malformed": malformed,
            "wrong_type": wrong_type,
            "unknown_usage": unknown,
            "paused": paused,
            "resumed": resumed,
        },
        "scientific_claim_effect": "none_execution_repair_only",
    }
    write_json(output_dir / "preflight_audit.json", audit)
    config_sha = sha256_file(DEFAULT_CONFIG)
    manifest = {
        "schema_version": 1,
        "experiment": config["experiment"],
        "status": "completed" if all(checks.values()) else "failed",
        "config_path": str(DEFAULT_CONFIG.relative_to(ROOT)).replace("\\", "/"),
        "config_sha256": config_sha,
        "request_plan_sha256": stable_hash(plan),
        "terminal_v1_manifest_sha256": config["terminal_v1_binding"][
            "run_manifest"
        ]["sha256"],
        "network_calls": 0,
        "paid_api_calls": 0,
        "provider_attempts": 0,
        "checks_passed": sum(checks.values()),
        "checks_total": len(checks),
        "aggregate_fingerprint": stable_hash(audit),
    }
    write_json(output_dir / "run_manifest.json", manifest)
    return audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--preflight-output", type=Path)
    args = parser.parse_args(argv)
    config, plan = load_frozen_plan(args.config)
    if args.preflight_output is None:
        print(json.dumps({
            "mode": "zero-network-eligibility",
            "logical_calls": len(plan),
            "request_plan_sha256": stable_hash(plan),
            "paid_api_allowed": config["execution"]["paid_api_allowed"],
            "network_calls_allowed": config["execution"]["network_calls_allowed"],
            "new_explicit_authorization_required": config[
                "authorization_gate"
            ]["new_explicit_authorization_required"],
        }, indent=2))
        return 0
    audit = run_preflight(args.preflight_output)
    print(json.dumps(audit, indent=2))
    return 0 if all(audit["checks"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
