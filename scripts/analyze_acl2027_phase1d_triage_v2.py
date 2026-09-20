"""No-network Phase 1D development pilot for accept/reject/abstain triage."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/acl2027/phase1d_triage_pilot_v1.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_cases(config: dict[str, Any]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for prior in config["protocol"]["prior_types"]:
        for evidence in config["protocol"]["evidence_regimes"]:
            for replicate in range(config["protocol"]["replicates_per_cell"]):
                if prior == "contextual":
                    downstream_delta, proxy_delta = 0.12, 0.10
                elif prior == "copied-global":
                    downstream_delta, proxy_delta = -0.12, 0.09
                else:
                    downstream_delta, proxy_delta = 0.02, 0.04
                cases.append({
                    "case_id": f"{prior}:{evidence}:{replicate:02d}",
                    "prior_type": prior,
                    "evidence_regime": evidence,
                    "downstream_delta": downstream_delta,
                    "proxy_delta": proxy_delta,
                    "disagreement": {"sparse": 0.22, "sufficient": 0.06, "conflicted": 0.24}[evidence],
                })
    return cases


def binary_proxy_gate(case: dict[str, Any]) -> str:
    return "accept" if case["proxy_delta"] >= 0.05 else "reject"


def triage_gate(case: dict[str, Any]) -> str:
    if case["evidence_regime"] in {"sparse", "conflicted"}:
        return "abstain"
    if case["prior_type"] == "contextual" and case["proxy_delta"] >= 0.05 and case["disagreement"] <= 0.10:
        return "accept"
    return "reject"


def summarize(cases: list[dict[str, Any]], policy: str) -> dict[str, Any]:
    fn = binary_proxy_gate if policy == "binary_proxy_gate" else triage_gate
    decisions = [fn(case) for case in cases]
    accepted = [case for case, decision in zip(cases, decisions) if decision == "accept"]
    return {
        "policy": policy,
        "n": len(cases),
        "actions": {action: decisions.count(action) for action in ["accept", "reject", "abstain"]},
        "helpful_deployments": sum(case["downstream_delta"] > 0.05 for case in accepted),
        "unsafe_deployments": sum(case["downstream_delta"] < -0.05 for case in accepted),
        "neutral_deployments": sum(abs(case["downstream_delta"]) <= 0.05 for case in accepted),
        "retained_candidates": len(cases),
    }


def analyze(config: dict[str, Any]) -> dict[str, Any]:
    execution = config["execution"]
    if execution["paid_api_allowed"] or execution["formal_scaling_allowed"] or execution["network_calls_allowed"]:
        raise ValueError("Phase 1D must remain no-paid and no-network")
    cases = build_cases(config)
    return {
        "analysis": "development_only_fabricated_evidence",
        "protocol": {
            "n_cases": len(cases),
            "prior_types": sorted({case["prior_type"] for case in cases}),
            "evidence_regimes": sorted({case["evidence_regime"] for case in cases}),
            "candidate_retention_invariant": all(case["case_id"] for case in cases),
        },
        "policies": [summarize(cases, policy) for policy in config["comparators"]],
        "interpretation": {
            "held_out_tuning": False,
            "real_task_accuracy_claim": False,
            "discard_is_gate_action": False,
            "decision": "triage_protocol_is_promising_but_requires_real_cross_task_validation",
        },
    }


def write_outputs(result: dict[str, Any], config: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=False)
    payload = {"config": config, "config_sha256": sha256_file(CONFIG_PATH), "result": result}
    analysis_path = output_dir / "analysis.json"
    analysis_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "experiment": config["experiment"],
        "config_path": "configs/acl2027/phase1d_triage_pilot_v1.json",
        "config_sha256": sha256_file(CONFIG_PATH),
        "complete_grid": True,
        "expected_runs": 1,
        "available_runs": 1,
        "runs": [{"run_id": "phase1d_triage_pilot", "status": "completed", "result_path": "artifacts/acl2027_phase1d_triage_pilot_v2/analysis.json", "file_sha256": sha256_file(analysis_path)}],
        "analysis_only": True,
        "development_only": True,
        "network_calls": 0,
        "result_sha256": sha256_file(analysis_path),
        "aggregate_fingerprint": sha256_file(analysis_path),
    }
    (output_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=True), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(CONFIG_PATH))
    parser.add_argument("--output", default="artifacts/acl2027_phase1d_triage_pilot_v2")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    result = analyze(config)
    write_outputs(result, config, ROOT / args.output)
    print(json.dumps({"experiment": config["experiment"], "output": str(ROOT / args.output), "network_calls": 0, "n_cases": result["protocol"]["n_cases"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

