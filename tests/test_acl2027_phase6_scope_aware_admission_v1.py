import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "artifacts/acl2027_phase6_scope_aware_admission_preflight_v1"
LIVE = ROOT / "artifacts/acl2027_phase6_scope_aware_admission_live_preflight_v1"


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_phase6_design_preflight_is_balanced_and_closed():
    proc = subprocess.run([sys.executable, "scripts/run_acl2027_phase6_scope_aware_admission_preflight_v1.py"], cwd=ROOT, text=True, capture_output=True, check=True)
    result = json.loads(proc.stdout)
    assert result["tasks"] == 40
    assert result["rows"] == 240
    assert result["condition_counts"] == {"admission_typed": 40, "always_use_typed": 40, "cold": 40, "evidence_abstain": 40, "incompatible_control": 40, "shuffled_typed": 40}
    assert result["identity_overlap"] == {**result["identity_overlap"], "task_id_overlap": 0, "logical_call_id_overlap": 0, "request_hash_overlap": 0, "transport_payload_hash_overlap": 0, "provider_response_id_overlap": 0}
    assert result["network_calls"] == result["provider_calls"] == result["paid_api_calls"] == 0


def test_phase6_strict_parser_rejects_bad_evidence_and_extra_keys():
    sys.path.insert(0, str(ROOT))
    from scripts.analyze_acl2027_phase6_scope_aware_admission_v1 import validate_response
    row = load(DESIGN / "schedule.json")["rows"][0]
    ids = row["canonical_request_body"]["response_contract"]["evidence_sentence_ids"]["known_ids"]
    candidate_ids = row["canonical_request_body"]["candidates"]
    assessments = {c["candidate_id"]: {"applicable": True, "rationale": "supported"} for c in candidate_ids}
    base = {"skill_assessments": assessments, "admission_decision": "abstain", "selected_skill_id": "none", "evidence_sentence_ids": [ids[0]], "extracted_operands": [], "intermediate_result": "", "final_answer": "x"}
    assert validate_response({**base, "extra": 1}, row)["contract_valid"] is False
    assert "evidence_unknown_id" in validate_response({**base, "evidence_sentence_ids": ["unknown"]}, row)["errors"]
    assert "evidence_duplicate_id" in validate_response({**base, "evidence_sentence_ids": [ids[0], ids[0]]}, row)["errors"]
    assert "evidence_empty_id" in validate_response({**base, "evidence_sentence_ids": [""]}, row)["errors"]


def test_phase6_live_preflight_only_emits_authorization_request():
    proc = subprocess.run([sys.executable, "scripts/run_acl2027_phase6_scope_aware_admission_live_preflight_v1.py"], cwd=ROOT, text=True, capture_output=True, check=True)
    payload = json.loads(proc.stdout)
    assert payload["result"]["status"] == "live_execution_preflight_passed_closed"
    assert payload["result"]["authorization_receipt_exists"] is False
    assert payload["result"]["provider_calls"] == 0
    request = load(LIVE / "authorization_request.json")
    assert request["status"] == "awaiting_exact_explicit_user_authorization"
    assert request["source_design_fingerprint"] == load(DESIGN / "run_manifest.json")["aggregate_fingerprint"]
    assert request["preflight_aggregate_fingerprint"] == payload["result"]["aggregate_fingerprint"]


def test_phase6_manifest_fingerprint_is_stable():
    manifest = load(DESIGN / "run_manifest.json")
    completion = load(DESIGN / "completion_manifest.json")
    assert completion["aggregate_fingerprint"] == manifest["aggregate_fingerprint"]
    live = load(LIVE / "run_manifest.json")
    live_completion = load(LIVE / "completion_manifest.json")
    assert live_completion["aggregate_fingerprint"] == live["aggregate_fingerprint"]
    assert live["source_design_fingerprint"] == manifest["aggregate_fingerprint"]


def test_phase6_parser_rejects_cross_candidate_evidence_and_legacy_line(monkeypatch, tmp_path):
    sys.path.insert(0, str(ROOT))
    from scripts.analyze_acl2027_phase6_scope_aware_admission_v1 import validate_response
    from scripts import run_acl2027_phase6_scope_aware_admission_preflight_v1 as runner
    row = next(r for r in load(DESIGN / "schedule.json")["rows"] if r["condition"] == "always_use_typed")
    contract = row["canonical_request_body"]["response_contract"]
    candidate = row["canonical_request_body"]["candidates"][0]["candidate_id"]
    assessments = {candidate: {"applicable": True, "rationale": "supported"}}
    counter_id = row["private_gold"]["counterfactual_evidence_sentence_ids"][0]
    raw = {"skill_assessments": assessments, "admission_decision": "admit", "selected_skill_id": candidate, "evidence_sentence_ids": [counter_id], "extracted_operands": [], "intermediate_result": "supported", "final_answer": "x"}
    assert "evidence_cross_candidate" in validate_response(raw, row)["errors"]
    config = load(ROOT / "configs/acl2027/phase6_scope_aware_admission_preflight_v1.json")
    config["experiment_line"] = runner.LEGACY_LINE
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setattr(runner, "CONFIG", path)
    import pytest
    with pytest.raises(RuntimeError, match="legacy"):
        runner.validate()


def test_phase6_task_selection_is_deterministic_and_fresh():
    sys.path.insert(0, str(ROOT))
    from scripts.run_acl2027_phase6_scope_aware_admission_preflight_v1 import select_tasks
    first, first_audit = select_tasks()
    second, second_audit = select_tasks()
    assert [task["task_id"] for task in first] == [task["task_id"] for task in second]
    assert first_audit["prior_task_overlap"] == 0
    assert second_audit["prior_task_overlap"] == 0


def test_phase6_schedule_has_zero_overlap_with_all_historical_identity_types():
    schedule = load(DESIGN / "schedule.json")["rows"]
    historical = {"task_id": set(), "logical_call_id": set(), "request_hash": set(), "transport_payload_hash": set(), "provider_response_id": set()}

    def records(value):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from records(child)
        elif isinstance(value, list):
            for child in value:
                yield from records(child)

    current_phase_artifacts = {
        DESIGN.resolve(),
        (ROOT / "artifacts/acl2027_phase6_scope_aware_admission_live_preflight_v1").resolve(),
        (ROOT / "artifacts/acl2027_phase6_scope_aware_admission_live_v1").resolve(),
        (ROOT / "artifacts/acl2027_phase6_scope_aware_admission_analysis_v1").resolve(),
    }
    for directory in (ROOT / "artifacts").glob("acl2027_phase*"):
        if directory.resolve() in current_phase_artifacts:
            continue
        for path in directory.rglob("*.json"):
            try:
                value = load(path)
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            for record in records(value):
                for field, values in historical.items():
                    if record.get(field) not in (None, ""):
                        values.add(str(record[field]))
    for field, values in historical.items():
        assert not ({str(row.get(field)) for row in schedule if row.get(field) not in (None, "")} & values)


def test_phase6_live_runner_preflight_binds_frozen_schedule_without_network():
    proc = subprocess.run(
        [sys.executable, "scripts/run_acl2027_phase6_scope_aware_admission_live_v1.py", "preflight"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    result = json.loads(proc.stdout)
    assert result == {
        "aggregate_fingerprint": "dfe7cbf6c9e4a8ad5da6298e9fe41a9b4b745cf404eb08b3e9c0f3443721fb3d",
        "network_calls": 0,
        "rows": 240,
    }


def test_phase6_live_ledgers_are_complete_hashed_and_closed():
    from scripts.acl2027_phase2_response_verifier_v3 import stable

    artifact = ROOT / "artifacts/acl2027_phase6_scope_aware_admission_live_v1"
    starts = load(artifact / "request_start_ledger.json")
    records = load(artifact / "ledger.json")
    audit = load(artifact / "run_audit.json")
    closure = load(artifact / "authorization_closure.json")
    assert len(starts) == len(records) == 240
    assert len({record["request_id"] for record in records}) == 240
    assert all(start["start_entry_sha256"] == stable({k: v for k, v in start.items() if k != "start_entry_sha256"}) for start in starts)
    assert all(record["ledger_entry_sha256"] == stable({k: v for k, v in record.items() if k != "ledger_entry_sha256"}) for record in records)
    assert all(second["previous_start_entry_sha256"] == first["start_entry_sha256"] for first, second in zip(starts, starts[1:]))
    assert all(second["previous_ledger_entry_sha256"] == first["ledger_entry_sha256"] for first, second in zip(records, records[1:]))
    assert audit["status"] == "completed"
    assert audit["terminal_rows"] == 0
    assert audit["request_start_pacing_valid"] is True
    assert audit["replication_calls"] == audit["cross_domain_calls"] == audit["formal_scaling_calls"] == 0
    assert closure["status"] == "closed"
    assert closure["reason"] == "completed_exact_240"
