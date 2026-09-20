#!/usr/bin/env python3
"""Freeze and audit the zero-network Phase 1W live calibration contract."""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.prepare_acl2027_phase1v_calibration import (
    HardStop,
    PreflightError,
    exact_usage,
    parse_response,
    read_json,
    sha256_file,
    stable_hash,
    verify_response,
    write_json,
)

CONFIG = ROOT / "configs/acl2027/phase1w_calibration_live_preflight_v1.json"
OUTPUT = ROOT / "artifacts/acl2027_phase1w_calibration_live_preflight_v1"


def relative(path: Path) -> str:
    try:
        path = path.relative_to(ROOT)
    except ValueError:
        pass
    return str(path).replace("\\", "/")


def cost_cny(config: dict[str, Any], usage: dict[str, int]) -> float:
    cost = config["cost_control"]
    return (
        usage["input_tokens"] * cost["list_price_cny_per_million_input_tokens"]
        + usage["output_tokens"] * cost["list_price_cny_per_million_output_tokens"]
    ) / 1_000_000


def validate_config(config: dict[str, Any]) -> None:
    execution = config.get("execution", {})
    if config.get("phase") != "1W" or not (
        execution.get("protocol_only") is True
        and execution.get("network_calls_allowed") is False
        and execution.get("provider_calls_allowed") is False
        and execution.get("paid_api_allowed") is False
        and execution.get("formal_scaling_allowed") is False
    ):
        raise PreflightError("Phase 1W must remain zero-network, unpaid, and non-scaling")
    if not (
        execution.get("logical_calls") == execution.get("physical_requests") == 24
        and execution.get("max_provider_attempts_per_logical_call") == 1
        and execution.get("sdk_max_retries") == execution.get("explicit_retries") == 0
        and execution.get("request_interval_seconds") == 1.0
        and execution.get("model_id") == "qwen3.7-plus"
        and execution.get("temperature") == 0
        and execution.get("enable_thinking") is False
        and "max_tokens" in execution.get("request_body_forbidden_keys", [])
    ):
        raise PreflightError("Phase 1W transport contract drift")
    authorization = config["authorization_gate"]
    if not (
        authorization["status"] == "closed_preflight_only"
        and authorization["new_explicit_authorization_required"] is True
        and authorization["authorization_may_not_be_inherited_from_phase1s"] is True
        and authorization["authorized_calls"] == 0
        and authorization["qwen3.8_max_allowed"] is False
        and authorization["staged_or_full_scaling_allowed"] is False
    ):
        raise PreflightError("Phase 1W authorization closure drift")
    cost = config["cost_control"]
    expected_input = cost["measured_total_message_chars"] // cost["conservative_chars_per_input_token"]
    expected_output = execution["logical_calls"] * cost["conservative_output_tokens_per_call"]
    expected_price = (
        expected_input * cost["list_price_cny_per_million_input_tokens"]
        + expected_output * cost["list_price_cny_per_million_output_tokens"]
    ) / 1_000_000
    if not (
        expected_input == cost["conservative_input_tokens"]
        and expected_output == cost["conservative_total_output_tokens"]
        and abs(expected_price - cost["conservative_estimated_cost_cny"]) < 1e-12
        and expected_price < cost["accounting_ceiling_cny"] == 10.0
        and cost["accounting_ceiling_is_request_parameter"] is False
        and cost["max_tokens_is_cost_control"] is False
    ):
        raise PreflightError("Phase 1W cost contract drift")


def load_frozen_plan(config_path: Path = CONFIG) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    config = read_json(config_path)
    validate_config(config)
    binding = config["phase1v_binding"]
    for name in ("config", "audit", "manifest"):
        item = binding[name]
        if sha256_file(ROOT / item["path"]) != item["sha256"]:
            raise PreflightError(f"Phase 1V {name} hash mismatch")
    for name in ("request_plan", "evaluator_private"):
        item = binding[name]
        path = ROOT / item["path"]
        if sha256_file(path) != item["file_sha256"] or stable_hash(read_json(path)) != item["stable_sha256"]:
            raise PreflightError(f"Phase 1V {name} binding mismatch")
    source = read_json(ROOT / binding["request_plan"]["path"])
    private = read_json(ROOT / binding["evaluator_private"]["path"])
    ordered = [[row["logical_call_id"], row["request_hash"]] for row in source]
    if ordered != binding["ordered_requests"] or len(source) != 24:
        raise PreflightError("Phase 1V ordered request binding drift")
    plan = []
    for row in source:
        if stable_hash(row["request"]) != row["request_hash"] or set(row["request"]) != {"temperature", "messages"}:
            raise PreflightError("scientific request hash or shape drift")
        request = deepcopy(row["request"])
        request["model"] = config["execution"]["model_id"]
        request["enable_thinking"] = config["execution"]["enable_thinking"]
        if "max_tokens" in request:
            raise PreflightError("transport request contains max_tokens")
        plan.append({
            **{key: row[key] for key in ("call_index", "logical_call_id", "task_family", "task_id")},
            "scientific_request_hash": row["request_hash"],
            "request": request,
            "transport_request_hash": stable_hash(request),
        })
    if set(private) != {row["logical_call_id"] for row in plan}:
        raise PreflightError("evaluator-private identity drift")
    return config, plan, private


def _records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def execute_simulation(
    config: dict[str, Any],
    plan: list[dict[str, Any]],
    private: dict[str, Any],
    output: Path,
    provider: Callable[[dict[str, Any]], dict[str, Any]],
    authorization: dict[str, Any],
    *,
    max_new_calls: int | None = None,
) -> dict[str, Any]:
    expected_authorization = {
        "status": "simulation_only",
        "authorized_calls": 24,
        "model_id": config["execution"]["model_id"],
        "transport_plan_sha256": stable_hash(plan),
        "accounting_ceiling_cny": config["cost_control"]["accounting_ceiling_cny"],
    }
    if authorization != expected_authorization:
        raise PreflightError("authorization drift")
    output.mkdir(parents=True, exist_ok=True)
    plan_path = output / "transport_plan.json"
    if plan_path.exists() and stable_hash(read_json(plan_path)) != stable_hash(plan):
        raise PreflightError("transport plan drift")
    if not plan_path.exists():
        write_json(plan_path, plan)
    results_path = output / "results.jsonl"
    records = _records(results_path)
    if len(records) > len(plan):
        raise PreflightError("call-count drift")
    for index, record in enumerate(records):
        expected = plan[index]
        if any(record.get(key) != expected[key] for key in ("call_index", "logical_call_id", "scientific_request_hash", "transport_request_hash")):
            raise PreflightError("completed records are not an exact transport-plan prefix")
        if record.get("terminal"):
            raise HardStop("terminal failure is not resumable")
    accumulated = {key: sum(int(row.get(key, 0)) for row in records) for key in ("input_tokens", "output_tokens", "total_tokens")}
    made = 0
    for item in plan[len(records):]:
        if max_new_calls is not None and made >= max_new_calls:
            break
        if cost_cny(config, accumulated) >= config["cost_control"]["accounting_ceiling_cny"]:
            raise HardStop("accounting ceiling reached before provider attempt")
        made += 1
        base = {key: item[key] for key in ("call_index", "logical_call_id", "task_family", "task_id", "scientific_request_hash", "transport_request_hash")}
        try:
            response = provider(deepcopy(item["request"]))
        except Exception as exc:  # noqa: BLE001
            record = {**base, "status": "hard_stop", "terminal": True, "usage_known": False, "error_stage": "provider", "error": str(exc)}
        else:
            try:
                usage = exact_usage(response)
            except Exception as exc:  # noqa: BLE001
                record = {**base, "status": "hard_stop", "terminal": True, "usage_known": False, "error_stage": "usage", "error": str(exc)}
            else:
                raw = response.get("content")
                common = {**base, **usage, "terminal": False, "usage_known": True, "raw_response_text": raw, "raw_response_sha256": stable_hash(raw)}
                try:
                    payload = parse_response(item["task_family"], raw)
                except Exception as exc:  # noqa: BLE001
                    record = {**common, "status": "invalid_output", "error": str(exc)}
                else:
                    record = {**common, "status": "completed", "response": payload, **verify_response(payload, private[item["logical_call_id"]])}
                for key in accumulated:
                    accumulated[key] += usage[key]
        with results_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")
        records.append(record)
        if record["terminal"]:
            break
    terminal = bool(records and records[-1].get("terminal"))
    manifest = {
        "status": "hard_stopped" if terminal else "completed_with_invalid_outputs" if len(records) == len(plan) and any(row["status"] == "invalid_output" for row in records) else "completed" if len(records) == len(plan) else "paused",
        "planned_calls": len(plan), "recorded_calls": len(records), "provider_attempts": len(records),
        "invalid_output_calls": sum(row["status"] == "invalid_output" for row in records),
        "usage_known_for_all_attempts": all(row.get("usage_known") is True for row in records),
        "usage": accumulated, "exact_accounted_cost_cny": cost_cny(config, accumulated),
    }
    write_json(output / "run_manifest.json", manifest)
    return manifest


class SimulatedProvider:
    def __init__(self, plan: list[dict[str, Any]], private: dict[str, Any], modes: dict[int, str] | None = None, usage: dict[str, int] | None = None):
        self.plan, self.private, self.modes, self.calls = plan, private, modes or {}, 0
        self.usage = usage or {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18}

    def __call__(self, request: dict[str, Any]) -> dict[str, Any]:
        item = self.plan[self.calls]
        self.calls += 1
        if stable_hash(request) != item["transport_request_hash"]:
            raise PreflightError("simulated transport request drift")
        mode = self.modes.get(self.calls, "valid")
        if mode == "unknown_usage":
            return {"content": "{}", "usage": None}
        if mode == "exception":
            raise RuntimeError("simulated provider exception")
        if mode == "malformed":
            return {"content": '{"answer":', "usage": self.usage}
        gold = self.private[item["logical_call_id"]]
        payload: dict[str, Any] = {"answer": gold["answers"][0]}
        if item["task_family"] == "2WikiMultiHopQA":
            payload["supporting_evidence"] = gold["supporting_evidence"]
        if mode == "schema_invalid":
            payload["extra"] = True
        return {"content": json.dumps(payload), "usage": self.usage}


def simulation_authorization(config: dict[str, Any], plan: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "status": "simulation_only", "authorized_calls": 24,
        "model_id": config["execution"]["model_id"],
        "transport_plan_sha256": stable_hash(plan),
        "accounting_ceiling_cny": config["cost_control"]["accounting_ceiling_cny"],
    }


def run_preflight(output: Path = OUTPUT) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite immutable artifact: {output}")
    config, plan, private = load_frozen_plan()
    output.mkdir(parents=True)
    write_json(output / "transport_plan.json", plan)
    auth = simulation_authorization(config, plan)
    sims = output / "simulations"
    known = execute_simulation(config, plan, private, sims / "known_invalid", SimulatedProvider(plan, private, {1: "malformed", 2: "schema_invalid"}), auth, max_new_calls=3)
    unknown = execute_simulation(config, plan, private, sims / "unknown_usage", SimulatedProvider(plan, private, {1: "unknown_usage"}), auth)
    exception = execute_simulation(config, plan, private, sims / "provider_exception", SimulatedProvider(plan, private, {1: "exception"}), auth)
    resume_provider = SimulatedProvider(plan, private)
    paused = execute_simulation(config, plan, private, sims / "resume", resume_provider, auth, max_new_calls=4)
    resumed = execute_simulation(config, plan, private, sims / "resume", resume_provider, auth, max_new_calls=3)
    terminal_resume_refused = False
    try:
        execute_simulation(config, plan, private, sims / "unknown_usage", SimulatedProvider(plan, private), auth)
    except HardStop:
        terminal_resume_refused = True
    authorization_drift = False
    bad_auth = deepcopy(auth)
    bad_auth["authorized_calls"] = 25
    try:
        execute_simulation(config, plan, private, sims / "authorization_drift", SimulatedProvider(plan, private), bad_auth)
    except PreflightError as exc:
        authorization_drift = "authorization drift" in str(exc)
    plan_drift = False
    changed = deepcopy(plan)
    changed[0]["request"]["temperature"] = 1
    changed[0]["transport_request_hash"] = stable_hash(changed[0]["request"])
    try:
        execute_simulation(config, changed, private, sims / "resume", SimulatedProvider(changed, private), simulation_authorization(config, changed), max_new_calls=1)
    except PreflightError as exc:
        plan_drift = "plan drift" in str(exc)
    ceiling = execute_simulation(config, plan, private, sims / "ceiling", SimulatedProvider(plan, private, usage={"input_tokens": 0, "output_tokens": 1_250_000, "total_tokens": 1_250_000}), auth, max_new_calls=1)
    ceiling_stop = False
    try:
        execute_simulation(config, plan, private, sims / "ceiling", SimulatedProvider(plan, private), auth, max_new_calls=1)
    except HardStop as exc:
        ceiling_stop = "accounting ceiling" in str(exc)
    source = read_json(ROOT / config["phase1v_binding"]["request_plan"]["path"])
    checks = {
        "phase1v_files_and_stable_hashes_bound": True,
        "exact_24_ordered_scientific_requests": len(plan) == 24 and [[row["logical_call_id"], row["scientific_request_hash"]] for row in plan] == config["phase1v_binding"]["ordered_requests"],
        "scientific_hashes_preserved": all(row["scientific_request_hash"] == source[index]["request_hash"] for index, row in enumerate(plan)),
        "transport_adds_only_model_and_thinking": all(set(row["request"]) - set(source[index]["request"]) == {"model", "enable_thinking"} for index, row in enumerate(plan)),
        "unique_transport_hashes": len({row["transport_request_hash"] for row in plan}) == 24,
        "private_gold_not_in_transport": all(not ({"answers", "answer_id", "supporting_evidence", "evidences", "evidences_id"} & set(row["request"])) for row in plan),
        "route_pacing_retry_and_no_max_frozen": config["execution"]["endpoint_class"] == "token_plan_user_confirmed" and config["execution"]["request_interval_seconds"] == 1.0 and config["execution"]["sdk_max_retries"] == config["execution"]["explicit_retries"] == 0 and all("max_tokens" not in row["request"] for row in plan),
        "cost_arithmetic_and_local_ceiling": config["cost_control"]["conservative_estimated_cost_cny"] == 0.889442 and config["cost_control"]["accounting_ceiling_is_request_parameter"] is False,
        "authorization_closed_and_independent": config["authorization_gate"]["authorized_calls"] == 0 and config["authorization_gate"]["authorization_may_not_be_inherited_from_phase1s"] is True,
        "known_usage_invalid_visible_and_continues": known["recorded_calls"] == 3 and known["invalid_output_calls"] == 2,
        "unknown_usage_terminal_nonresumable": unknown["status"] == "hard_stopped" and terminal_resume_refused,
        "provider_exception_terminal": exception["status"] == "hard_stopped" and exception["recorded_calls"] == 1,
        "append_only_exact_prefix_resume": paused["recorded_calls"] == 4 and resumed["recorded_calls"] == 7 and resume_provider.calls == 7,
        "plan_and_authorization_drift_terminal": plan_drift and authorization_drift,
        "accounting_ceiling_hard_stop": ceiling["exact_accounted_cost_cny"] == 10.0 and ceiling_stop,
        "raw_response_preserved": _records(sims / "known_invalid" / "results.jsonl")[0]["raw_response_text"] == '{"answer":',
        "zero_network_provider_and_paid_calls": config["execution"]["network_calls_allowed"] is False,
    }
    audit = {
        "analysis": "phase1w_bounded_live_calibration_authorization_preflight",
        "checks": checks,
        "decision": "preflight_passed_new_explicit_authorization_required" if all(checks.values()) else "preflight_failed_provider_execution_closed",
        "request_count": len(plan), "scientific_request_plan_sha256": stable_hash(source),
        "transport_plan_sha256": stable_hash(plan), "evaluator_private_sha256": stable_hash(private),
        "conservative_estimated_cost_cny": config["cost_control"]["conservative_estimated_cost_cny"],
        "accounting_ceiling_cny": config["cost_control"]["accounting_ceiling_cny"],
        "network_calls": 0, "provider_calls": 0, "paid_api_calls": 0,
        "simulated_attempts_are_not_provider_calls": True,
        "scientific_claim_effect": "authorization_readiness_only_main_claim_unchanged",
    }
    write_json(output / "preflight_audit.json", audit)
    manifest = {
        "schema_version": 1, "experiment": config["experiment"], "config_path": relative(CONFIG),
        "config_sha256": sha256_file(CONFIG), "expected_runs": 1, "available_runs": 1,
        "complete_grid": True, "network_calls": 0, "provider_calls": 0, "paid_api_calls": 0,
        "runs": [{"run_id": "phase1w_zero_call_live_authorization_preflight", "status": "completed" if all(checks.values()) else "failed", "result_path": relative(output / "preflight_audit.json"), "file_sha256": sha256_file(output / "preflight_audit.json")}],
        "aggregate_fingerprint": sha256_file(output / "preflight_audit.json"),
    }
    write_json(output / "run_manifest.json", manifest)
    return audit


if __name__ == "__main__":
    result = run_preflight()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if all(result["checks"].values()) else 1)
