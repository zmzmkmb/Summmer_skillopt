import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_acl2027_tracegraph_tg9_tg8_failures_v1.py"


def load_module():
    spec = importlib.util.spec_from_file_location("tg9_failure_audit", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_action_parser_preserves_instance_and_container_identity():
    module = load_module()
    pickup = module.parse_action_event("take spraybottle 2 from shelf 1")
    put = module.parse_action_event("move spraybottle 2 to toilet 1")
    opened = module.parse_action_event("open drawer 12")

    assert pickup == {
        "action_family": "PickupObject",
        "action": "take spraybottle 2 from shelf 1",
        "object_type": "spraybottle",
        "object_instance_signature": "spraybottle#2",
        "source_type": "shelf",
        "source_signature": "shelf#1",
    }
    assert put["object_instance_signature"] == "spraybottle#2"
    assert put["destination_signature"] == "toilet#1"
    assert opened["action_family"] == "OpenObject"
    assert opened["container_signature"] == "drawer#12"


def test_frozen_tg8_failure_partition_and_required_fields():
    module = load_module()
    audit = module.build_audit()

    assert audit["status"] == "complete_zero_execution_offline_audit"
    assert audit["scope"]["new_episodes"] == 0
    assert audit["scope"]["new_actions"] == 0
    assert audit["summary"]["source_rows"] == 360
    assert audit["summary"]["audited_rows"] == 30
    assert audit["summary"]["task_identities"] == 10
    assert audit["summary"]["successful_task_identities"] == 0
    assert audit["summary"]["identical_three_replicate_task_groups"] == 10
    assert audit["summary"]["primary_failure_mechanism_counts"] == {
        "closed_container_skill_gap": 3,
        "object_instance_reuse": 7,
    }
    assert audit["summary"]["mechanism_flag_counts"] == {
        "ledger_complete_but_env_fail": 7,
        "closed_container_stall": 3,
        "second_source_same_as_first_destination": 7,
        "candidate_gap": 3,
        "instance_reuse": 7,
    }

    for task in audit["task_audits"]:
        assert task["first_divergence"]["step"] is not None
        assert "pending_subgoal_id" in task["first_divergence"]
        assert "completed_subgoal_ids" in task["first_divergence"]
        assert "unresolved_subgoal_ids" in task["first_divergence"]
        assert task["replicate_evidence"]["replicate_count"] == 3
        assert task["replicate_evidence"]["identical_trajectory"] is True
        assert len(task["replicate_evidence"]["rows"]) == 3
        assert set(task["hypotheses"]) == {
            "H1_object_instance_binding",
            "H2_open_close_coverage",
            "H3_complementarity",
            "H4_anti_cycle_not_primary_root",
        }


def test_mechanism_specific_evidence_is_not_conflated():
    module = load_module()
    tasks = module.build_audit()["task_audits"]
    reuse = [x for x in tasks if x["primary_failure_mechanism"] == "object_instance_reuse"]
    stalls = [
        x for x in tasks if x["primary_failure_mechanism"] == "closed_container_skill_gap"
    ]

    assert len(reuse) == 7
    assert len(stalls) == 3
    for task in reuse:
        assert task["second_instance_same_as_first"] is True
        assert task["second_source_is_distinct"] is False
        assert task["mechanism_flags"]["ledger_complete_but_env_fail"] is True
        assert task["mechanism_flags"]["closed_container_stall"] is False
        assert task["hypotheses"]["H1_object_instance_binding"]["status"] == "support"
        assert task["hypotheses"]["H2_open_close_coverage"]["status"] == "evidence_insufficient"
    for task in stalls:
        assert task["second_instance_same_as_first"] is None
        assert task["second_source_is_distinct"] is None
        assert task["mechanism_flags"]["closed_container_stall"] is True
        assert task["mechanism_flags"]["candidate_gap"] is True
        assert task["relevant_open_action_present_in_admissible"] is True
        assert task["relevant_open_action_eligibility_rejected"] is True
        assert all(x["present_in_admissible_actions"] for x in task["relevant_open_events"])
        assert task["hypotheses"]["H1_object_instance_binding"]["status"] == "evidence_insufficient"
        assert task["hypotheses"]["H2_open_close_coverage"]["status"] == "support"


def test_output_package_is_hashed_and_refuses_overwrite(tmp_path):
    module = load_module()
    audit = module.build_audit()
    output_dir = tmp_path / "artifact"
    report = tmp_path / "report.md"

    manifest = module.write_outputs(audit, output_dir, report)
    assert manifest["episodes_run"] == 0
    assert manifest["actions_taken"] == 0
    assert manifest["tg8_inputs_mutated"] is False
    assert (output_dir / "failure_audit.json").exists()
    assert (output_dir / "failure_audit.csv").exists()
    assert (output_dir / "completion_manifest.json").exists()
    assert report.exists()

    saved = json.loads((output_dir / "failure_audit.json").read_text(encoding="utf-8"))
    assert saved["summary"]["primary_failure_mechanism_counts"] == {
        "closed_container_skill_gap": 3,
        "object_instance_reuse": 7,
    }
    with pytest.raises(module.AuditError, match="refusing to overwrite"):
        module.write_outputs(audit, output_dir, tmp_path / "other.md")
