#!/usr/bin/env python3
"""Zero-network Phase 2 staged live-runner preflight and local runner core."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from copy import deepcopy
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/acl2027/phase2_staged_live_runner_preflight_v1.json"
AUTH = ROOT / "configs/acl2027/phase2_staged_live_runner_authorization_v1.json"
OUTPUT = ROOT / "artifacts/acl2027_phase2_staged_live_runner_preflight_v1"
class HardStop(RuntimeError):
    def __init__(self, message: str, ledger: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.ledger = ledger


HARD = HardStop
CALL_STAGES = ("calibration", "development_acquisition", "formal_history", "probe", "held_out")
FAMILIES = ("fact_retrieval", "attribute_comparison", "bridge_attribute_comparison", "entity_bridge", "relation_inference")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def authorization_hash(authorization: dict[str, Any]) -> str:
    return stable(authorization)


def plan_rows(config: dict[str, Any]) -> list[dict[str, Any]]:
    plan_path = ROOT / config["frozen_bindings"]["request_plan"]["path"]
    return load(plan_path)["plan"]


def validate_bindings(config: dict[str, Any]) -> list[dict[str, Any]]:
    b = config["frozen_bindings"]
    if sha256_file(ROOT / b["freeze_config_path"]) != b["freeze_config_sha256"]:
        raise HARD("freeze config hash drift")
    frozen = load(ROOT / b["freeze_config_path"])
    for key in ("request_plan", "partition_audit"):
        path = ROOT / b[key]["path"]
        if sha256_file(path) != b[key]["sha256"]:
            raise HARD(f"{key} hash drift")
    rows = plan_rows(config)
    if len(rows) != 710:
        raise HARD("request order drift: expected 710 logical requests")
    ids: set[str] = set()
    counts = {stage: 0 for stage in CALL_STAGES}
    for index, row in enumerate(rows, 1):
        if row["logical_call_id"] in ids:
            raise HARD("duplicate logical ID")
        ids.add(row["logical_call_id"])
        if row["partition"] not in counts:
            raise HARD("unknown request stage")
        counts[row["partition"]] += 1
        body = row["canonical_request_body"]
        if row["call_index"] != index or stable(body) != row["request_hash"]:
            raise HARD("request hash drift or request order drift")
        if body.get("partition") != row["partition"] or body.get("model_id") != "qwen3.7-plus" or body.get("temperature") != 0:
            raise HARD("model, stage, or temperature drift")
        accounting = row["expected_accounting"]
        if "max_tokens" in body or accounting.get("max_tokens_present") is not False or accounting.get("retries") != 0:
            raise HARD("max_tokens present or retry attempt policy drift")
    if counts != {stage: config["stages"][stage] for stage in CALL_STAGES}:
        raise HARD("stage call-count drift")
    if frozen["model"] != {"model_id": "qwen3.7-plus", "temperature": 0, "retries": 0, "max_tokens_present": False}:
        raise HARD("frozen model contract drift")
    return rows


def validate_authorization(config: dict[str, Any], authorization: dict[str, Any]) -> str:
    binding = authorization.get("preflight_binding", {})
    expected_path = str(CONFIG.relative_to(ROOT)).replace("\\", "/")
    if binding.get("path") != expected_path or binding.get("sha256") != sha256_file(CONFIG):
        raise HARD("authorization config drift: preflight hash binding")
    if authorization.get("formal_scaling_allowed") is not False:
        raise HARD("formal scaling must remain disabled for staged pilot")
    for key in ("model_id", "temperature", "retries", "max_tokens_present"):
        if authorization.get(key) != config["model_route"][key]:
            raise HARD("authorization model contract drift")
    stages = authorization.get("authorized_stages")
    stage_calls = authorization.get("stage_call_ceilings")
    stage_costs = authorization.get("stage_cost_ceilings_cny")
    if not isinstance(stages, list) or len(stages) != len(set(stages)) or any(stage not in CALL_STAGES for stage in stages):
        raise HARD("invalid authorized stages")
    if not isinstance(stage_calls, dict) or not isinstance(stage_costs, dict) or set(stage_calls) != set(stages) or set(stage_costs) != set(stages):
        raise HARD("authorization stage ceiling mismatch")
    for stage in stages:
        if type(stage_calls[stage]) is not int or not 0 <= stage_calls[stage] <= config["stages"][stage]:
            raise HARD("invalid stage call ceiling")
        if not isinstance(stage_costs[stage], (int, float)) or not 0 <= stage_costs[stage] <= config["cost_control"]["stage_ceilings_cny"][stage]:
            raise HARD("invalid stage cost ceiling")
    calls = authorization.get("authorized_calls")
    ceiling = authorization.get("cumulative_cost_ceiling_cny")
    if type(calls) is not int or not 0 <= calls <= sum(stage_calls.values()):
        raise HARD("invalid authorized call ceiling")
    if not isinstance(ceiling, (int, float)) or not 0 <= ceiling <= config["cost_control"]["cumulative_ceiling_cny"]:
        raise HARD("invalid cumulative cost ceiling")
    switches = ("paid_api_allowed", "provider_calls_allowed", "qwen_authorization_open")
    if authorization.get("status") == "closed_preflight" and (any(authorization.get(key) is not False for key in switches) or stages or calls or ceiling):
        raise HARD("closed authorization drift")
    return authorization_hash(authorization)


def exact_prefix(ledger: list[dict[str, Any]], rows: list[dict[str, Any]]) -> None:
    if len(ledger) > len(rows):
        raise HARD("non-prefix resume")
    seen = set()
    for expected, actual in zip(rows, ledger):
        if any(actual.get(key) != expected[key] for key in ("call_index", "logical_call_id", "request_hash", "partition")):
            raise HARD("non-prefix resume")
        if actual["logical_call_id"] in seen:
            raise HARD("duplicate logical ID")
        seen.add(actual["logical_call_id"])
        if not isinstance(actual.get("authorization_sha256"), str) or len(actual["authorization_sha256"]) != 64:
            raise HARD("authorization hash missing from ledger")
        if actual.get("terminal") is True:
            raise HARD("terminal hard stop is not resumable", ledger)
        usage(actual)


def usage(record: dict[str, Any]) -> dict[str, int]:
    u = record.get("usage")
    if not isinstance(u, dict) or any(not isinstance(u.get(k), int) or u[k] < 0 for k in ("input_tokens", "output_tokens", "total_tokens")) or u["input_tokens"] + u["output_tokens"] != u["total_tokens"]:
        raise HARD("unknown/missing usage")
    return u


def usage_totals(ledger: list[dict[str, Any]]) -> dict[str, int]:
    return {key: sum(usage(record)[key] for record in ledger) for key in ("input_tokens", "output_tokens", "total_tokens")}


def cost(config: dict[str, Any], totals: dict[str, int]) -> float:
    r = config["cost_control"]
    return (totals["input_tokens"] * r["input_cny_per_million"] + totals["output_tokens"] * r["output_cny_per_million"]) / 1_000_000


def coverage_gate(supports: dict[str, list[str]]) -> dict[str, Any]:
    all_ids = [support for family in FAMILIES for support in supports.get(family, [])]
    duplicates = sorted({support for support in all_ids if all_ids.count(support) > 1})
    counts = {f: len(set(supports.get(f, []))) for f in FAMILIES}
    passed = not duplicates and all(n >= 8 for n in counts.values())
    return {"status": "coverage-passed" if passed else "coverage-incomplete", "passed": passed, "independent_verified_supports": counts, "duplicate_support_ids": duplicates, "method_failure": False}


def stage_cost(config: dict[str, Any], ledger: list[dict[str, Any]], stage: str) -> float:
    return cost(config, usage_totals([record for record in ledger if record["partition"] == stage]))


def probe_audit_gate(rows: list[dict[str, Any]], ledger: list[dict[str, Any]], audit: dict[str, Any] | None) -> bool:
    expected = [row["request_hash"] for row in rows if row["partition"] == "probe"]
    actual = [record["request_hash"] for record in ledger if record["partition"] == "probe"]
    return bool(audit and audit.get("passed") is True and audit.get("probe_calls") == len(expected) == len(actual) and audit.get("probe_request_hashes_sha256") == stable(expected) == stable(actual) and audit.get("coverage_gate_passed") is True)


def stage_allowed(stage: str, config: dict[str, Any], authorization: dict[str, Any], ledger: list[dict[str, Any]], gate: dict[str, Any], probe_audited: bool) -> bool:
    if stage not in CALL_STAGES or authorization.get("formal_scaling_allowed") is not False:
        return False
    if not all(authorization.get(key) is True for key in ("paid_api_allowed", "provider_calls_allowed", "qwen_authorization_open")):
        return False
    if stage not in authorization["authorized_stages"]:
        return False
    if sum(record["partition"] == stage for record in ledger) >= authorization["stage_call_ceilings"][stage] or len(ledger) >= authorization["authorized_calls"]:
        return False
    if stage_cost(config, ledger, stage) >= authorization["stage_cost_ceilings_cny"][stage] or cost(config, usage_totals(ledger)) >= authorization["cumulative_cost_ceiling_cny"]:
        return False
    if stage in ("probe", "held_out") and not gate["passed"]:
        return False
    if stage == "held_out" and not probe_audited:
        return False
    return True


def execute_stage(config: dict[str, Any], authorization: dict[str, Any], ledger: list[dict[str, Any]], stage: str, provider: Callable[[dict[str, Any]], dict[str, Any]], *, supports: dict[str, list[str]] | None = None, probe_audit: dict[str, Any] | None = None, max_new_calls: int | None = None) -> list[dict[str, Any]]:
    rows = validate_bindings(config)
    auth_hash = validate_authorization(config, authorization)
    records = deepcopy(ledger)
    exact_prefix(records, rows)
    if any(record["authorization_sha256"] != auth_hash for record in records):
        raise HARD("authorization hash drift in resume ledger")
    gate = coverage_gate(supports or {})
    audited = probe_audit_gate(rows, records, probe_audit)
    made = 0
    while len(records) < len(rows):
        row = rows[len(records)]
        if row["partition"] != stage:
            if made == 0:
                raise HARD("stage boundary or exact-prefix violation")
            break
        if max_new_calls is not None and made >= max_new_calls:
            break
        if not stage_allowed(stage, config, authorization, records, gate, audited):
            raise HARD("stage is not authorized or a gate/ceiling is closed")
        try:
            response = provider(deepcopy(row["canonical_request_body"]))
        except Exception as exc:  # noqa: BLE001
            records.append({"call_index": row["call_index"], "logical_call_id": row["logical_call_id"], "request_hash": row["request_hash"], "partition": row["partition"], "authorization_sha256": auth_hash, "terminal": True, "error_type": type(exc).__name__, "error": str(exc), "usage": None})
            raise HARD("provider exception; no retry allowed", records) from exc
        try:
            exact = usage(response)
        except HardStop as exc:
            records.append({"call_index": row["call_index"], "logical_call_id": row["logical_call_id"], "request_hash": row["request_hash"], "partition": row["partition"], "authorization_sha256": auth_hash, "terminal": True, "error": str(exc), "usage": response.get("usage"), "raw_response": response.get("content"), "raw_response_sha256": stable(response.get("content"))})
            raise HARD(str(exc), records) from exc
        records.append({"call_index": row["call_index"], "logical_call_id": row["logical_call_id"], "request_hash": row["request_hash"], "partition": row["partition"], "authorization_sha256": auth_hash, "terminal": False, "usage": dict(exact), "raw_response": response.get("content"), "raw_response_sha256": stable(response.get("content"))})
        made += 1
        if stage_cost(config, records, stage) > authorization["stage_cost_ceilings_cny"][stage]:
            records[-1]["terminal"] = True
            records[-1]["error"] = "stage cost ceiling exceeded"
            raise HARD("stage cost ceiling exceeded", records)
        if cost(config, usage_totals(records)) > authorization["cumulative_cost_ceiling_cny"]:
            records[-1]["terminal"] = True
            records[-1]["error"] = "cumulative cost ceiling exceeded"
            raise HARD("cumulative cost ceiling exceeded", records)
    return records


def run_local(config: dict[str, Any], ledger: list[dict[str, Any]] | None = None, *, supports: dict[str, list[str]] | None = None, probe_audit: dict[str, Any] | None = None, provider: Callable[[dict[str, Any]], dict[str, Any]] | None = None, authorization: dict[str, Any] | None = None) -> dict[str, Any]:
    rows = validate_bindings(config)
    auth = authorization or load(AUTH)
    auth_hash = validate_authorization(config, auth)
    ledger = list(ledger or [])
    exact_prefix(ledger, rows)
    if any(record["authorization_sha256"] != auth_hash for record in ledger):
        raise HARD("authorization hash drift in resume ledger")
    gate = coverage_gate(supports or {})
    if provider is not None:
        raise HARD("provider calls are disabled by preflight authorization")
    totals = usage_totals(ledger) if ledger else {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    counts = {stage: sum(row["partition"] == stage for row in rows) for stage in CALL_STAGES}
    return {"status": "preflight-passed", "mode": "zero-network-dry-run", "authorization_sha256": auth_hash, "request_counts": counts, "estimated_cost_cny": config["stage_estimated_cost_cny"], "hard_ceilings_cny": config["cost_control"]["stage_ceilings_cny"], "cumulative_hard_ceiling_cny": config["cost_control"]["cumulative_ceiling_cny"], "coverage_gate": gate, "probe_audit_passed": probe_audit_gate(rows, ledger, probe_audit), "usage": totals, "cost_cny": cost(config, totals), "network_calls": 0, "provider_calls": 0, "model_calls": 0, "paid_api_calls": 0}


def write_artifact(config: dict[str, Any], output: Path = OUTPUT) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"immutable artifact already exists: {output}")
    output.mkdir(parents=True)
    audit = run_local(config)
    audit_path = output / "preflight_audit.json"
    write(audit_path, audit)
    fingerprint_inputs = {
        "preflight_config_sha256": sha256_file(CONFIG),
        "closed_authorization_config_sha256": sha256_file(AUTH),
        "preflight_audit_sha256": sha256_file(audit_path),
    }
    manifest = {
        "schema_version": 1,
        "artifact": "acl2027_phase2_staged_live_runner_preflight_v1",
        "status": "preflight_passed_authorization_closed",
        **fingerprint_inputs,
        "aggregate_fingerprint": stable(fingerprint_inputs),
        "logical_requests": len(plan_rows(config)),
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "paid_api_calls": 0,
    }
    write(output / "run_manifest.json", manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-artifact", action="store_true")
    args = parser.parse_args(argv)
    result = write_artifact(load(CONFIG)) if args.write_artifact else run_local(load(CONFIG))
    print(json.dumps(result, indent=2, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
