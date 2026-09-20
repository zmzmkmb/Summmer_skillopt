#!/usr/bin/env python3
"""Close ACL 2027 Phase 1 from the frozen Phase 1Y candidate audit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs/acl2027/phase1z_final_real_heldout_v1.json"
DEFAULT_OUTPUT = ROOT / "artifacts/acl2027_phase1z_final_real_heldout_v1"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def manifest_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def build_closure(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = read_json(config_path)
    inputs: dict[str, dict[str, str]] = config["immutable_inputs"]
    actual_hashes: dict[str, str] = {}
    for name, binding in inputs.items():
        path = ROOT / binding["path"]
        actual_hashes[name] = sha256_file(path)
        if actual_hashes[name] != binding["sha256"]:
            raise ValueError(f"immutable input hash mismatch: {name}")

    audit = read_json(ROOT / inputs["phase1y_candidate_audit"]["path"])
    expected = config["frozen_expected_observation"]
    observed = {
        "verified_trajectories": audit["verified_trajectories"],
        "typed_candidates": audit["typed_candidates"],
        "covered_skill_families": len(audit["coverage"]["admitted_skill_families"]),
        "required_skill_families": len(audit["coverage"]["required_skill_families"]),
        "missing_skill_families": audit["coverage"]["missing_skill_families"],
        "theoretical_minimum_additional_successful_history_calls": audit["phase1z"]["theoretical_minimum_additional_successful_calls"],
        "exact_guaranteed_additional_calls": audit["phase1z"]["exact_guaranteed_calls"],
        "currently_authorized_additional_calls": audit["phase1z"]["currently_authorized_calls"],
    }
    if observed != expected:
        raise ValueError("frozen Phase 1Y observation drift")

    checks = {
        "immutable_input_hashes_match": True,
        "verifier_replay_passed": audit["checks"]["verifier_replay"] is True,
        "deterministic_candidate_ids": audit["checks"]["deterministic_candidate_ids"] is True,
        "no_evaluation_leakage": audit["checks"]["no_evaluation_leakage"] is True,
        "minimum_supports_for_admitted_candidates": audit["checks"]["minimum_two_supports_per_admitted_candidate"] is True,
        "complete_family_type_coverage": audit["checks"]["family_type_coverage_met"] is True,
        "provider_authorization_closed": audit["checks"]["provider_authorization_exhausted"] is True,
    }
    executable = all(checks.values())
    if executable:
        raise ValueError("config is a zero-provider closure but the execution gate unexpectedly passed")

    result = {
        "schema_version": 1,
        "run_id": "phase1z_final_adjudication_01",
        "status": "completed",
        "decision": config["execution_gate"]["on_gate_failure"],
        "phase1_closed": True,
        "phase1z_scientifically_executable": False,
        "provider_attempts": 0,
        "network_calls": 0,
        "paid_api_calls": 0,
        "observed": observed,
        "coverage": audit["coverage"],
        "concentration": audit["concentration"],
        "checks": checks,
        "immutable_input_hashes": actual_hashes,
        "history_usage": audit["usage"],
        "interpretation": "The candidate gate failed before held-out execution because two required typed scopes have only one verified support each. No Phase 1Z causal effect was estimated.",
    }
    result["scientific_fingerprint"] = stable_hash(result)
    return result


def write_artifact(config_path: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite immutable artifact: {output}")
    result = build_closure(config_path)
    output.mkdir(parents=True)
    result_path = output / "run_01.json"
    result_path.write_text(
        json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    config_relative = manifest_path(config_path)
    result_relative = manifest_path(result_path)
    aggregate_fingerprint = stable_hash(
        {"config_sha256": sha256_file(config_path), "scientific_fingerprint": result["scientific_fingerprint"]}
    )
    manifest = {
        "schema_version": 1,
        "experiment": "acl2027_phase1z_final_real_heldout_v1",
        "status": "completed",
        "decision": result["decision"],
        "phase1_closed": True,
        "provider_attempts": 0,
        "network_calls": 0,
        "paid_api_calls": 0,
        "expected_runs": 1,
        "available_runs": 1,
        "complete_grid": True,
        "config_path": config_relative,
        "config_sha256": sha256_file(config_path),
        "aggregate_fingerprint": aggregate_fingerprint,
        "runs": [{
            "run_id": result["run_id"],
            "result_path": result_relative,
            "file_sha256": sha256_file(result_path),
        }],
    }
    (output / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    manifest = write_artifact(args.config, args.output)
    print(json.dumps(manifest, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
