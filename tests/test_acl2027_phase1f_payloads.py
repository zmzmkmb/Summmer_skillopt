"""Tests for the local Phase 1F payload audit."""
from __future__ import annotations

from scripts.audit_acl2027_phase1f_payloads import audit


def test_spreadsheetbench_ids_and_materialization_are_consistent():
    result = audit()
    spreadsheetbench = result["spreadsheetbench"]
    assert spreadsheetbench["dataset_rows"] == 400
    assert spreadsheetbench["dataset_unique_ids"] == 400
    assert spreadsheetbench["split_counts"] == {"train": 80, "val": 40, "test": 280}
    assert spreadsheetbench["missing_dataset_ids"] == []
    assert spreadsheetbench["dataset_ids_not_in_split"] == []
    assert spreadsheetbench["missing_or_invalid_task_materializations"] == []
    assert spreadsheetbench["ready"] is True


def test_officeqa_mirror_payload_matches_authorized_split():
    result = audit()
    officeqa = result["officeqa"]
    assert officeqa["ready"] is True
    assert officeqa["csv_rows"] == 246
    assert officeqa["csv_unique_uids"] == 246
    assert officeqa["split_counts"] == {"train": 50, "val": 24, "test": 172}
    assert officeqa["csv_uids_missing_from_split"] == []
    assert officeqa["split_uids_missing_from_csv"] == []
    assert officeqa["duplicate_split_uids"] == 0
    assert result["ready_for_paired_pilot"] is True
