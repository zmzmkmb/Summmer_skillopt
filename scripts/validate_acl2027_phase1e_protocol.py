"""Audit the Phase 1E cross-task triage protocol without network calls."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/acl2027/phase1e_real_cross_task_triage_protocol_v1.json"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(config: dict[str, Any]) -> dict[str, Any]:
    execution = config["execution"]
    assert execution["paid_api_allowed"] is False
    assert execution["formal_scaling_allowed"] is False
    assert execution["network_calls_allowed"] is False
    assert config["pairing"]["same_model_prompt_budget_and_task_order"] is True
    assert config["triage_actions"]["discard"] == "never emitted by the validation gate"
    manifests = {}
    for task in config["task_families"]:
        path = ROOT / task["source_manifest"]
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        manifests[task["name"]] = {
            "path": task["source_manifest"],
            "sha256": sha256_file(path),
            "counts": payload["counts"],
            "development_allowed": task["development_allowed"],
        }
    return {
        "analysis": "protocol_audit_only_no_network",
        "tasks": manifests,
        "checks": {
            "three_task_families": len(config["task_families"]) == 3,
            "new_task_families": sum(t["role"] != "confirmatory_reference" for t in config["task_families"]) == 2,
            "searchqa_held_out_protected": next(t for t in config["task_families"] if t["name"] == "SearchQA")["development_allowed"] is False,
            "three_way_actions": list(config["triage_actions"]) == ["accept", "reject", "abstain", "discard"],
            "no_paid_or_network": not any(execution[name] for name in ["paid_api_allowed", "formal_scaling_allowed", "network_calls_allowed"]),
            "payloads_ready": False,
        },
        "decision": "protocol_frozen_pending_payload_materialization_and_provider_review",
    }


def main() -> int:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    result = audit(config)
    out = ROOT / "artifacts/acl2027_phase1e_real_cross_task_triage_protocol_v1"
    out.mkdir(parents=True, exist_ok=False)
    analysis = out / "protocol_audit.json"
    analysis.write_text(json.dumps({"config": config, "config_sha256": sha256_file(CONFIG_PATH), "result": result}, indent=2, ensure_ascii=True), encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "experiment": config["experiment"],
        "config_path": "configs/acl2027/phase1e_real_cross_task_triage_protocol_v1.json",
        "config_sha256": sha256_file(CONFIG_PATH),
        "complete_grid": True,
        "expected_runs": 1,
        "available_runs": 1,
        "runs": [{"run_id": "phase1e_protocol_audit", "status": "completed", "result_path": "artifacts/acl2027_phase1e_real_cross_task_triage_protocol_v1/protocol_audit.json", "file_sha256": sha256_file(analysis)}],
        "analysis_only": True,
        "network_calls": 0,
        "result_sha256": sha256_file(analysis),
        "aggregate_fingerprint": sha256_file(analysis),
    }
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=True), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

