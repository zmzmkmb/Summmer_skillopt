#!/usr/bin/env python3
"""Phase 2 staged runner v2: deterministic schedule and zero-network preflight."""
from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/acl2027/phase2_staged_live_runner_preflight_v2.json"
AUTH = ROOT / "configs/acl2027/phase2_staged_live_runner_authorization_closed_v2.json"
OUTPUT = ROOT / "artifacts/acl2027_phase2_staged_live_runner_preflight_v2"
COVERAGE_SCHEMA = ROOT / "configs/acl2027/phase2_candidate_materialization_schema_v2.json"
PROBE_SCHEMA = ROOT / "configs/acl2027/phase2_probe_audit_schema_v2.json"
CALL_STAGES = ("calibration", "development_acquisition", "formal_history", "probe", "held_out")
FAMILIES = ("fact_retrieval", "attribute_comparison", "bridge_attribute_comparison", "entity_bridge", "relation_inference")


class HardStop(RuntimeError):
    def __init__(self, message: str, ledger: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.ledger = ledger


HARD = HardStop


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    serialized = json.dumps(value, indent=2, ensure_ascii=True, sort_keys=True) + "\n"
    path.write_bytes(serialized.encode("utf-8"))


def stable(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def original_rows(config: dict[str, Any]) -> list[dict[str, Any]]:
    return load(ROOT / config["frozen_bindings"]["request_plan"]["path"])["plan"]


def build_schedule(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda row: (CALL_STAGES.index(row["partition"]), row["call_index"]))
    schedule = []
    for staged_index, source in enumerate(ordered, 1):
        row = deepcopy(source)
        row["original_call_index"] = row.pop("call_index")
        row["staged_execution_index"] = staged_index
        schedule.append(row)
    return schedule


def audit_schedule(rows: list[dict[str, Any]], schedule: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows) != 710 or len(schedule) != 710:
        raise HARD("schedule cardinality drift")
    originals = {r["logical_call_id"]: r for r in rows}
    if len(originals) != 710 or len({r.get("logical_call_id") for r in schedule}) != 710:
        raise HARD("duplicate logical ID or schedule omission")
    counts = {stage: 0 for stage in CALL_STAGES}
    for index, row in enumerate(schedule, 1):
        source = originals.get(row["logical_call_id"])
        if source is None or row.get("staged_execution_index") != index:
            raise HARD("schedule is not a staged exact order")
        if row.get("original_call_index") != source["call_index"]:
            raise HARD("original call index drift")
        for key in ("request_hash", "canonical_request_body", "partition", "task_id", "skill_family", "condition"):
            if row.get(key) != source.get(key):
                raise HARD("schedule request/body/assignment drift")
        if stable(row["canonical_request_body"]) != row["request_hash"]:
            raise HARD("request hash drift")
        counts[row["partition"]] += 1
    expected = {"calibration": 60, "development_acquisition": 10, "formal_history": 160, "probe": 160, "held_out": 320}
    if counts != expected or [r["partition"] for r in schedule] != [s for s in CALL_STAGES for _ in range(expected[s])]:
        raise HARD("stage order or count drift")
    return {"passed": True, "strict_bijection": True, "requests": 710, "stage_counts": counts,
            "zero_omissions": True, "zero_duplicates": True, "zero_request_hash_changes": True,
            "stable_within_stage_key": "original_call_index"}


def validate_bindings(config: dict[str, Any], schedule_path: Path | None = None) -> list[dict[str, Any]]:
    bindings = config["frozen_bindings"]
    for label, path_key, hash_key in (
        ("freeze config", "freeze_config_path", "freeze_config_sha256"),
        ("request plan", "request_plan", "sha256"), ("partition audit", "partition_audit", "sha256")):
        if label == "freeze config":
            path, expected = ROOT / bindings[path_key], bindings[hash_key]
        else:
            path, expected = ROOT / bindings[path_key]["path"], bindings[path_key][hash_key]
        if sha256_file(path) != expected:
            raise HARD(f"{label} hash drift")
    rows = original_rows(config)
    schedule_path = schedule_path or ROOT / config["schedule_binding"]["path"]
    if sha256_file(schedule_path) != config["schedule_binding"]["sha256"]:
        raise HARD("schedule hash drift")
    schedule = load(schedule_path)["schedule"]
    audit_schedule(rows, schedule)
    return schedule


def usage(record: dict[str, Any]) -> dict[str, int]:
    value = record.get("usage")
    keys = ("input_tokens", "output_tokens", "total_tokens")
    if not isinstance(value, dict) or any(type(value.get(k)) is not int or value[k] < 0 for k in keys):
        raise HARD("unknown/missing/invalid usage")
    if value["input_tokens"] + value["output_tokens"] != value["total_tokens"]:
        raise HARD("unknown/missing/invalid usage")
    return value


def ledger_hash(records: list[dict[str, Any]]) -> str:
    return stable(records)


def cost(config: dict[str, Any], records: list[dict[str, Any]]) -> float:
    rate = config["cost_control"]
    return sum(usage(r)["input_tokens"] * rate["input_cny_per_million"] +
               usage(r)["output_tokens"] * rate["output_cny_per_million"] for r in records) / 1_000_000


def resolve_registry(registry_path: Path) -> dict[str, tuple[dict[str, Any], str]]:
    registry = load(registry_path)
    resolved = {}
    for auth_id, item in registry.get("authorizations", {}).items():
        path = (registry_path.parent / item["path"]).resolve()
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            raise HARD("authorization registry cannot resolve historical authorization")
        auth = load(path)
        if auth.get("authorization_id") != auth_id:
            raise HARD("authorization registry identity drift")
        resolved[auth_id] = (auth, item["sha256"])
    return resolved


def validate_authorization(config: dict[str, Any], auth: dict[str, Any], auth_sha: str, stage: str | None = None) -> None:
    required = {
        "preflight_config_sha256": sha256_file(CONFIG),
        "schedule_sha256": config["schedule_binding"]["sha256"],
        "freeze_config_sha256": config["frozen_bindings"]["freeze_config_sha256"],
        "request_plan_sha256": config["frozen_bindings"]["request_plan"]["sha256"],
        "partition_audit_sha256": config["frozen_bindings"]["partition_audit"]["sha256"],
    }
    if auth.get("bindings") != required:
        raise HARD("authorization hash binding drift")
    route = config["model_route"]
    for key in ("model_id", "temperature", "retries", "max_tokens_present", "endpoint_route"):
        if auth.get(key) != route[key]:
            raise HARD("model/temperature/route drift")
    if auth.get("formal_scaling_allowed") is not False or auth.get("retries") != 0 or auth.get("max_tokens_present") is not False:
        raise HARD("formal scaling, retry, or max_tokens policy drift")
    authorized_stage = auth.get("authorized_stage")
    calls = auth.get("authorized_calls")
    stage_calls = auth.get("stage_call_ceiling")
    stage_cost = auth.get("stage_cost_ceiling_cny")
    cumulative = auth.get("cumulative_cost_ceiling_cny")
    if authorized_stage is not None and authorized_stage not in CALL_STAGES:
        raise HARD("stage not authorized")
    if stage is not None and authorized_stage != stage:
        raise HARD("stage not authorized")
    if type(calls) is not int or type(stage_calls) is not int or calls < 0 or stage_calls < 0:
        raise HARD("invalid authorization call ceiling")
    if authorized_stage and (calls > stage_calls or stage_calls > config["stages"][authorized_stage]):
        raise HARD("invalid stage call ceiling")
    if not isinstance(stage_cost, (int, float)) or not isinstance(cumulative, (int, float)) or stage_cost < 0 or cumulative < 0:
        raise HARD("invalid cost ceiling")
    if authorized_stage and stage_cost > config["cost_control"]["stage_ceilings_cny"][authorized_stage]:
        raise HARD("invalid stage cost ceiling")
    if cumulative > config["cost_control"]["cumulative_ceiling_cny"]:
        raise HARD("invalid cumulative cost ceiling")
    if auth.get("status") == "closed_preflight":
        if authorized_stage is not None or calls or stage_calls or stage_cost or cumulative or any(
                auth.get(key) is not False for key in ("paid_api_allowed", "provider_calls_allowed", "qwen_authorization_open")):
            raise HARD("closed authorization drift")
    if not isinstance(auth_sha, str) or len(auth_sha) != 64:
        raise HARD("authorization hash drift")


def validate_ledger(schedule: list[dict[str, Any]], records: list[dict[str, Any]], registry_path: Path) -> dict[str, tuple[dict[str, Any], str]]:
    if len(records) > len(schedule):
        raise HARD("non staged exact-prefix resume")
    registry = resolve_registry(registry_path)
    seen_ids, seen_responses = set(), set()
    for expected, record in zip(schedule, records):
        for key in ("logical_call_id", "request_hash", "partition", "original_call_index", "staged_execution_index"):
            if record.get(key) != expected.get(key):
                raise HARD("non staged exact-prefix resume")
        auth_id = record.get("authorization_id")
        if auth_id not in registry or registry[auth_id][1] != record.get("authorization_sha256"):
            raise HARD("authorization registry cannot resolve historical authorization")
        auth, auth_sha = registry[auth_id]
        validate_authorization(load(CONFIG), auth, auth_sha, record["authorized_stage"])
        if record["authorized_stage"] != record["partition"]:
            raise HARD("stage not authorized")
        if record["logical_call_id"] in seen_ids:
            raise HARD("duplicate logical ID")
        seen_ids.add(record["logical_call_id"])
        response_hash = record.get("raw_response_sha256")
        if response_hash and response_hash in seen_responses:
            raise HARD("duplicate response")
        if response_hash:
            seen_responses.add(response_hash)
        if record.get("terminal"):
            raise HARD("terminal ledger is not resumable", records)
        usage(record)
    return registry


def current_stage(schedule: list[dict[str, Any]], records: list[dict[str, Any]]) -> str | None:
    return schedule[len(records)]["partition"] if len(records) < len(schedule) else None


def verify_coverage(config: dict[str, Any], schedule: list[dict[str, Any]], records: list[dict[str, Any]], artifact_path: Path, expected_sha: str) -> dict[str, Any]:
    if not isinstance(artifact_path, Path):
        raise HARD("coverage must be an immutable artifact path, not caller-provided supports")
    if sha256_file(artifact_path) != expected_sha:
        raise HARD("coverage artifact hash drift")
    artifact = load(artifact_path)
    schema_sha = sha256_file(COVERAGE_SCHEMA)
    history = [r for r in records if r["partition"] == "formal_history"]
    expected_history = [r for r in schedule if r["partition"] == "formal_history"]
    if len(history) != len(expected_history) or artifact.get("history_response_ledger_sha256") != ledger_hash(history):
        raise HARD("coverage ledger binding drift")
    if artifact.get("schema_config_sha256") != schema_sha or artifact.get("verifier_config_sha256") != config["coverage_gate"]["verifier_config_sha256"]:
        raise HARD("coverage verifier binding drift")
    if artifact.get("evaluation_leakage_audit") != {"passed": True, "probe_gold_accessed": False, "held_out_gold_accessed": False}:
        raise HARD("coverage evaluation leakage audit failed")
    by_id = {r["logical_call_id"]: r for r in history}
    scheduled = {r["logical_call_id"]: r for r in expected_history}
    required = load(COVERAGE_SCHEMA)["required_trajectory_fields"]
    unique_fields = ("trajectory_id", "task_id", "logical_call_id", "response_sha256", "support_id")
    seen = {key: set() for key in unique_fields}
    counts = {family: 0 for family in FAMILIES}
    for item in artifact.get("trajectories", []):
        if any(key not in item for key in required) or item.get("verifier_confirmed_success") is not True:
            raise HARD("coverage trajectory/verifier verdict invalid")
        record, row = by_id.get(item["logical_call_id"]), scheduled.get(item["logical_call_id"])
        if not record or not row or any((item["request_hash"] != row["request_hash"], item["task_id"] != row["task_id"],
                                         item["family"] != row["skill_family"], item["response_sha256"] != record["raw_response_sha256"])):
            raise HARD("coverage family/request/response binding drift")
        if item.get("provenance", {}).get("partition") != "formal_history" or item.get("candidate_id") is None:
            raise HARD("coverage trajectory provenance invalid")
        for key in unique_fields:
            if item[key] in seen[key]:
                raise HARD(f"duplicate trajectory/task/request/response/support: {key}")
            seen[key].add(item[key])
        counts[item["family"]] += 1
    passed = all(counts[f] >= 8 for f in FAMILIES)
    return {"status": "coverage-passed" if passed else "coverage-incomplete", "passed": passed,
            "independent_verified_supports": counts, "method_failure": False, "artifact_sha256": expected_sha}


def verify_probe_audit(config: dict[str, Any], records: list[dict[str, Any]], coverage_sha: str, audit_path: Path, expected_sha: str) -> bool:
    if sha256_file(audit_path) != expected_sha:
        raise HARD("probe audit hash drift")
    audit = load(audit_path)
    probe = [r for r in records if r["partition"] == "probe"]
    return bool(len(probe) == 160 and audit.get("passed") is True and
                audit.get("coverage_artifact_sha256") == coverage_sha and
                audit.get("probe_ledger_sha256") == ledger_hash(probe) and
                audit.get("analyzer_config_sha256") == sha256_file(PROBE_SCHEMA) == config["probe_gate"]["analyzer_config_sha256"])


def execute_stage(config: dict[str, Any], schedule: list[dict[str, Any]], registry_path: Path, auth_id: str,
                  records: list[dict[str, Any]], stage: str, provider: Callable[[dict[str, Any]], dict[str, Any]], *,
                  coverage_path: Path | None = None, coverage_sha: str | None = None,
                  probe_audit_path: Path | None = None, probe_audit_sha: str | None = None) -> list[dict[str, Any]]:
    output = deepcopy(records)
    registry = validate_ledger(schedule, output, registry_path)
    if auth_id not in registry:
        raise HARD("authorization registry cannot resolve current authorization")
    auth, auth_sha = registry[auth_id]
    validate_authorization(config, auth, auth_sha, stage)
    if not all(auth.get(key) is True for key in ("paid_api_allowed", "provider_calls_allowed", "qwen_authorization_open")):
        raise HARD("provider execution switches are closed")
    if current_stage(schedule, output) != stage:
        raise HARD("stage skipped, incomplete, or order drift")
    coverage = None
    if stage in ("probe", "held_out"):
        if not coverage_path or not coverage_sha:
            raise HARD("coverage not passed before probe or held-out")
        coverage = verify_coverage(config, schedule, output, coverage_path, coverage_sha)
        if not coverage["passed"]:
            raise HARD("coverage not passed before probe or held-out")
    if stage == "held_out":
        if not probe_audit_path or not probe_audit_sha or not verify_probe_audit(config, output, coverage_sha, probe_audit_path, probe_audit_sha):
            raise HARD("probe not completely audited before held-out")
    current_count = sum(r["authorization_id"] == auth_id and r["authorization_sha256"] == auth_sha for r in output)
    stage_current = sum(r["authorization_id"] == auth_id and r["partition"] == stage for r in output)
    while current_stage(schedule, output) == stage:
        if current_count >= auth["authorized_calls"] or stage_current >= auth["stage_call_ceiling"]:
            raise HARD("current authorization call ceiling", output)
        row = schedule[len(output)]
        body = deepcopy(row["canonical_request_body"])
        if "max_tokens" in body or body.get("model_id") != auth["model_id"] or body.get("temperature") != 0:
            raise HARD("max_tokens or model/temperature/route drift")
        base = {key: row[key] for key in ("logical_call_id", "request_hash", "partition", "original_call_index", "staged_execution_index")}
        base.update(authorization_id=auth_id, authorization_sha256=auth_sha, authorized_stage=stage)
        try:
            response = provider(body)
        except Exception as exc:  # noqa: BLE001
            base.update(terminal=True, error_type=type(exc).__name__, error=str(exc), usage=None, raw_response=None, raw_response_sha256=None)
            output.append(base)
            raise HARD("provider exception; no retry", output) from exc
        try:
            exact = usage(response)
        except HardStop as exc:
            raw = response.get("content") if isinstance(response, dict) else response
            base.update(terminal=True, error=str(exc), usage=response.get("usage") if isinstance(response, dict) else None,
                        raw_response=raw, raw_response_sha256=stable(raw))
            output.append(base)
            raise HARD(str(exc), output) from exc
        raw = response.get("content")
        base.update(terminal=False, error=None, usage=dict(exact), raw_response=raw, raw_response_sha256=stable(raw))
        output.append(base)
        current_count += 1
        stage_current += 1
        stage_records = [r for r in output if r["partition"] == stage]
        if cost(config, stage_records) > auth["stage_cost_ceiling_cny"]:
            output[-1].update(terminal=True, error="stage cost ceiling exceeded")
            raise HARD("stage cost ceiling exceeded", output)
        if cost(config, output) > auth["cumulative_cost_ceiling_cny"]:
            output[-1].update(terminal=True, error="global cumulative cost ceiling exceeded")
            raise HARD("global cumulative cost ceiling exceeded", output)
    return output


def run_local(config: dict[str, Any], provider: Callable | None = None) -> dict[str, Any]:
    if provider is not None:
        raise HARD("closed preflight forbids provider calls")
    schedule = validate_bindings(config)
    auth = load(AUTH)
    validate_authorization(config, auth, sha256_file(AUTH))
    return {"status": "preflight-passed-authorization-closed", "schedule_requests": len(schedule),
            "coverage_status": "coverage-incomplete", "network_calls": 0, "provider_calls": 0,
            "model_calls": 0, "qwen_calls": 0, "paid_api_calls": 0,
            "stage_calls": config["stages"], "estimated_cost_cny": config["stage_estimated_cost_cny"],
            "stage_hard_ceilings_cny": config["cost_control"]["stage_ceilings_cny"],
            "cumulative_hard_ceiling_cny": config["cost_control"]["cumulative_ceiling_cny"]}


def write_artifact(config: dict[str, Any], output: Path = OUTPUT) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"immutable artifact already exists: {output}")
    output.mkdir(parents=True)
    source = original_rows(config)
    schedule = build_schedule(source)
    schedule_doc = {"schema_version": 2, "source_request_plan_sha256": config["frozen_bindings"]["request_plan"]["sha256"], "schedule": schedule}
    write(output / "staged_execution_schedule.json", schedule_doc)
    if sha256_file(output / "staged_execution_schedule.json") != config["schedule_binding"]["sha256"]:
        raise HARD("generated schedule hash drift")
    write(output / "schedule_audit.json", audit_schedule(source, schedule))
    audit = run_local(config)
    write(output / "preflight_audit.json", audit)
    inputs = {
        "preflight_config_sha256": sha256_file(CONFIG), "closed_authorization_config_sha256": sha256_file(AUTH),
        "runner_source_sha256": sha256_file(Path(__file__)),
        "test_source_sha256": sha256_file(ROOT / "tests/test_acl2027_phase2_staged_live_runner_preflight_v2.py"),
        "freeze_config_sha256": config["frozen_bindings"]["freeze_config_sha256"],
        "request_plan_sha256": config["frozen_bindings"]["request_plan"]["sha256"],
        "partition_audit_sha256": config["frozen_bindings"]["partition_audit"]["sha256"],
        "staged_schedule_sha256": sha256_file(output / "staged_execution_schedule.json"),
        "preflight_audit_sha256": sha256_file(output / "preflight_audit.json"),
        "coverage_schema_config_sha256": sha256_file(COVERAGE_SCHEMA), "probe_audit_schema_config_sha256": sha256_file(PROBE_SCHEMA),
    }
    manifest = {"schema_version": 2, "artifact": output.name, "status": "immutable_preflight_passed_authorization_closed",
                **inputs, "aggregate_fingerprint": stable(inputs), "logical_requests": 710,
                "network_calls": 0, "provider_calls": 0, "model_calls": 0, "qwen_calls": 0, "paid_api_calls": 0}
    write(output / "run_manifest.json", manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-artifact", action="store_true")
    args = parser.parse_args(argv)
    result = write_artifact(load(CONFIG)) if args.write_artifact else run_local(load(CONFIG))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
