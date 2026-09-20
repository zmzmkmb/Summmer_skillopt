from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import pytest

from scripts import run_acl2027_tracegraph_tg8_durable_v2 as durable


@pytest.fixture(autouse=True)
def no_live_calls(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Live environment/network access forbidden in durability tests")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(durable.frozen.env_base, "load_alfworld_builder", forbidden)


@pytest.fixture
def config():
    return durable.frozen.read_json(durable.CONFIG)


def make_episode(row):
    return {
        "run_id": row["run_id"], "task_identity": row["task_identity"],
        "condition": row["condition"], "steps": 1, "success": False,
        "hard_invariant_violation": None, "metrics": {},
        "transitions": [{
            "runtime_inputs": {"observation": "synthetic", "historical_actions": [],
                               "admissible_actions": ["look"]},
            "terminal_action_decision": "look", "success_after_step": False,
        }],
    }


@pytest.fixture
def fake_run(tmp_path, config, monkeypatch):
    directory = tmp_path / "run"
    directory.mkdir()
    (directory / "rows").mkdir()
    rows, tasks = durable.frozen.load_schedule(config)
    monkeypatch.setattr(durable.frozen.env_base, "load_alfworld_builder", lambda: object())
    monkeypatch.setattr(durable.frozen.selector.base, "load_skill_index", lambda *_: object())
    monkeypatch.setattr(durable.frozen, "run_row",
                        lambda builder, index, root, row, task, steps: make_episode(row))
    return directory, rows, tasks


def test_frozen_code_unchanged():
    assert durable.frozen.sha256(Path(durable.frozen.__file__)) == durable.LEGACY_SHA


def test_candidate_is_fully_bound_but_authorization_closed(config):
    expected = {
        "execution_authorized mismatch", "episode_execution_allowed mismatch",
        "authorization_status mismatch", "authorization receipt missing or changed",
    }
    if durable.run_directory(config).exists():
        expected.add("run_directory already exists; resume/overwrite forbidden")
    assert set(durable.validate_config(config)) == expected


def test_closed_candidate_cannot_execute(config, tmp_path, monkeypatch):
    monkeypatch.setattr(durable, "OUTPUT_BASE", tmp_path)
    with pytest.raises(ValueError, match="execution_authorized"):
        durable.execute(config)
    assert list(tmp_path.iterdir()) == []


def test_atomic_no_overwrite_and_pending_publication(tmp_path):
    path = tmp_path / "row.json"
    durable.publish(path, {"original": True})
    with pytest.raises(FileExistsError):
        durable.publish(path, {"original": False})
    assert durable.frozen.read_json(path) == {"original": True}
    assert path.with_name("row.json.pending").is_file()


def test_all_360_rows_saved_before_next_row(config, fake_run, monkeypatch):
    directory, rows, tasks = fake_run
    observed = []
    def fake(builder, index, data_root, row, task, steps):
        ordinal = len(observed)
        if ordinal:
            assert (directory / "rows" / f"{ordinal-1:04d}.json").is_file()
        observed.append(row["run_id"])
        assert steps == 75
        assert task == tasks[row["task_identity"]]
        return make_episode(row)
    monkeypatch.setattr(durable.frozen, "run_row", fake)
    result = durable.execute_rows(config, directory, rows, tasks, object(), object())
    assert observed == [row["run_id"] for row in rows]
    assert len(set(observed)) == 360
    assert result["episodes_completed"] == 360
    assert result["factorial_valid"] is True
    assert result["acknowledged_steps"] == 360
    assert len(list((directory / "rows").glob("*.json"))) == 360


def test_first_error_stops_without_retry_and_saves_partial(config, fake_run, monkeypatch):
    directory, rows, tasks = fake_run
    calls = []
    partial = make_episode(rows[1])["transitions"]
    del partial[0]["success_after_step"]
    def fake(builder, index, data_root, row, task, steps):
        calls.append(row["run_id"])
        if len(calls) == 2:
            raise durable.frozen.EpisodeExecutionError("injected invariant", partial)
        return make_episode(row)
    monkeypatch.setattr(durable.frozen, "run_row", fake)
    result = durable.execute_rows(config, directory, rows, tasks, object(), object())
    assert calls == [row["run_id"] for row in rows[:2]]
    assert result["episodes_completed"] == 1
    assert result["episodes_started"] == 2
    assert result["factorial_valid"] is False
    assert result["actions_taken"] == 2
    assert result["acknowledged_steps"] == 1
    assert durable.frozen.read_json(directory / "rows/0001.json")["transitions"] == partial
    assert not (directory / "rows/0002.json").exists()


def test_keyboard_interrupt_records_exit_and_keeps_previous_rows(config, fake_run, monkeypatch):
    directory, rows, _ = fake_run
    def fake(builder, index, data_root, row, task, steps):
        if row["run_id"] == rows[1]["run_id"]:
            raise KeyboardInterrupt("injected")
        return make_episode(row)
    monkeypatch.setattr(durable.frozen, "run_row", fake)
    assert durable.record_execution(config, directory) == 130
    status = durable.inspect_saved(directory)
    assert status["durable_rows_readable"] == 1
    assert status["status"] == "interrupted"
    assert status["resume_allowed"] is False
    assert not (directory / "result.json").exists()


def test_disk_failure_does_not_start_next_row(config, fake_run, monkeypatch):
    directory, rows, tasks = fake_run
    original = durable.publish
    def broken(path, payload):
        if path.name == "0001.json":
            raise OSError("injected disk full")
        return original(path, payload)
    monkeypatch.setattr(durable, "publish", broken)
    assert durable.record_execution(config, directory) == 2
    events = [json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines()]
    assert [e["run_id"] for e in events if e["event"] == "row_started"] == [
        row["run_id"] for row in rows[:2]]
    assert durable.inspect_saved(directory)["durable_rows_readable"] == 1


def test_startup_error_is_logged_without_fake_episode_counts(config, fake_run, monkeypatch):
    directory, _, _ = fake_run
    def broken():
        raise RuntimeError("injected builder failure")
    monkeypatch.setattr(durable.frozen.env_base, "load_alfworld_builder", broken)
    assert durable.record_execution(config, directory) == 2
    assert durable.inspect_saved(directory)["durable_rows_readable"] == 0
    assert not (directory / "result.json").exists()


def test_status_does_not_claim_running_or_completed_from_missing_exit(tmp_path):
    (tmp_path / "rows").mkdir()
    durable.publish(tmp_path / "rows/0000.json", {"success": True})
    (tmp_path / "rows/0001.json.pending").write_text('{"truncated":', encoding="utf-8")
    status = durable.inspect_saved(tmp_path)
    assert status["durable_rows_readable"] == 1
    assert status["status"] == "no_exit_record_liveness_unknown"
    assert status["formal_result_audited"] is False
    assert status["pending_artifacts"] == ["rows/0001.json.pending"]


def test_recovery_reports_truncated_event_log(tmp_path):
    (tmp_path / "events.jsonl").write_text(
        '{"event":"row_started","ordinal":4}\n{"partial":', encoding="utf-8")
    status = durable.inspect_saved(tmp_path)
    assert status["last_durable_event"] == {"event": "row_started", "ordinal": 4}
    assert status["recovery_errors"]
    assert status["resume_allowed"] is False


def test_service_is_detached_no_restart_and_network_isolated(config, tmp_path):
    path = tmp_path / "config.json"
    durable.publish(path, config)
    command = durable.service_command(path, config)
    assert "--wait" in command
    assert "--property=Restart=no" in command
    assert "--property=PrivateNetwork=yes" in command
    assert "--property=KillMode=control-group" in command
    assert "--property=RuntimeMaxSec=21600" in command
    assert command[-1] == durable.frozen.sha256(path)
    assert "execute" in command


def test_receipt_bound_config_rejects_output_or_scope_change(config):
    original = durable.config_binding(config)
    for key, value in [("run_directory", "other"), ("max_steps_per_episode", 76),
                       ("max_retries", 1), ("max_wall_seconds", 999)]:
        changed = copy.deepcopy(config)
        changed[key] = value
        assert durable.config_binding(changed) != original
    config["authorization_receipt_sha256"] = "a" * 64
    assert durable.config_binding(config) == original


def authorize_synthetic(config, tmp_path, monkeypatch):
    config = copy.deepcopy(config)
    base = tmp_path / "output"
    monkeypatch.setattr(durable, "OUTPUT_BASE", base)
    config.update(
        execution_authorized=True, episode_execution_allowed=True,
        authorization_status="authorized", run_directory=str(base / "independent"),
        episode_result_output=str(base / "independent/result.json"),
        runner_sha256=durable.frozen.sha256(durable.SCRIPT),
        windows_launcher_sha256=durable.frozen.sha256(
            durable.ROOT / "scripts/start_acl2027_tracegraph_tg8_durable_v2.ps1"),
        skillbank_sha256=durable.frozen.sha256(durable.ROOT / config["skillbank"]),
    )
    receipt = {
        "status": "authorized", "authorization_opened": True,
        "test_only": True, "authorization_source": "synthetic_unit_test_not_user",
        "bindings": {
            "preflight_aggregate_fingerprint": durable.frozen.PREFLIGHT_AGGREGATE,
            "selector_sha256": durable.frozen.SELECTOR_SHA256,
            "selector_config_sha256": durable.frozen.SELECTOR_CONFIG_SHA256,
            "readiness_artifact_sha256": durable.frozen.READINESS_SHA256,
            "runner_sha256": config["runner_sha256"],
            "legacy_runner_sha256": durable.LEGACY_SHA,
            "durable_config_sha256": durable.config_binding(config),
        },
        "scope": {key: config[key] for key in (
            "planned_episode_rows", "max_steps_per_episode", "max_retries",
            "runtime_allowed_inputs", "stop_rule", "run_directory", "max_wall_seconds")},
    }
    path = tmp_path / "synthetic-authorization.json"
    durable.publish(path, receipt)
    config["authorization_receipt"] = str(path)
    config["authorization_receipt_sha256"] = durable.frozen.sha256(path)
    return config


def test_fully_bound_synthetic_authorization_and_tamper_rejection(config, tmp_path, monkeypatch):
    config = authorize_synthetic(config, tmp_path, monkeypatch)
    assert durable.validate_config(config) == []
    for key, value in [
        ("runner_sha256", "0" * 64), ("legacy_runner_sha256", "0" * 64),
        ("max_steps_per_episode", 76), ("max_retries", 1),
        ("windows_launcher_sha256", "0" * 64), ("skillbank_sha256", "0" * 64),
        ("runtime_allowed_inputs", ["observation", "hidden_state"]),
    ]:
        changed = copy.deepcopy(config)
        changed[key] = value
        assert durable.validate_config(changed), key


def test_old_receipt_cannot_authorize_new_executor(config, tmp_path, monkeypatch):
    config = authorize_synthetic(config, tmp_path, monkeypatch)
    old = durable.ROOT / "configs/acl2027/tracegraph_tg8_observable_subgoal_authorization_receipt_v6_20260913.json"
    config["authorization_receipt"] = str(old)
    config["authorization_receipt_sha256"] = durable.frozen.sha256(old)
    assert any("new authorization" in error for error in durable.validate_config(config))


@pytest.mark.skipif(sys.platform != "linux", reason="Linux-only flock and service worker")
def test_authorization_claim_is_permanent_and_lock_is_exclusive(config, tmp_path, monkeypatch):
    config = authorize_synthetic(config, tmp_path, monkeypatch)
    with durable.execution_lock():
        with pytest.raises(BlockingIOError):
            with durable.execution_lock():
                pytest.fail("second lock acquired")
    claims = durable.OUTPUT_BASE / ".authorization_claims"
    claims.mkdir()
    durable.publish(claims / f"{config['authorization_receipt_sha256']}.json", {"reusable": False})
    monkeypatch.setattr(durable, "require_isolation", lambda: None)
    with pytest.raises(FileExistsError):
        durable.execute(config)
    assert not durable.run_directory(config).exists()


@pytest.mark.skipif(sys.platform != "linux", reason="Linux namespace check")
def test_unisolated_worker_refuses_before_environment_loading(config, tmp_path, monkeypatch):
    config = authorize_synthetic(config, tmp_path, monkeypatch)
    monkeypatch.setattr(os, "readlink", lambda *_: "net:[same]")
    with pytest.raises(RuntimeError, match="PrivateNetwork"):
        durable.execute(config)
    assert not durable.OUTPUT_BASE.exists()


def test_killed_process_keeps_committed_row_and_no_false_exit(tmp_path):
    child = r"""
import time
from pathlib import Path
from scripts import run_acl2027_tracegraph_tg8_durable_v2 as d
directory = Path(__import__('sys').argv[1])
(directory / 'rows').mkdir()
d.publish(directory / 'rows/0000.json', {'run_id': 'synthetic-0', 'success': False})
d.event(directory, 'row_started', ordinal=1, run_id='synthetic-1')
time.sleep(120)
"""
    process = subprocess.Popen(
        [sys.executable, "-B", "-c", child, str(tmp_path)], cwd=durable.ROOT,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    try:
        deadline = time.monotonic() + 25
        while not (tmp_path / "events.jsonl").exists():
            if process.poll() is not None:
                pytest.fail(process.stderr.read().decode())
            if time.monotonic() >= deadline:
                pytest.fail("synthetic child did not commit its row")
            time.sleep(0.05)
        process.kill()
        process.wait(timeout=10)
        status = durable.inspect_saved(tmp_path)
        assert status["durable_rows_readable"] == 1
        assert status["exit"] is None
        assert status["formal_result_audited"] is False
        assert not (tmp_path / "result.json").exists()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        process.stderr.close()
