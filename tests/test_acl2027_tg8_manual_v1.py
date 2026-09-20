import copy
import socket

import pytest

from scripts import prepare_acl2027_tg8_manual_v1 as manual


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No environment or network allowed in preparation tests")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(manual.durable.frozen.env_base, "load_alfworld_builder", forbidden)


def test_plan_closed_and_scope_unchanged():
    plan = manual.check_plan(manual.make_plan())
    config = plan["closed_config"]
    assert config["execution_authorized"] is False
    assert config["episode_execution_allowed"] is False
    assert config["planned_episode_rows"] == 360
    assert config["max_steps_per_episode"] == 75
    assert config["max_retries"] == 0
    assert config["max_wall_seconds"] == 21600
    assert config["run_directory"] == manual.RUN_REL
    assert config["runtime_allowed_inputs"] == [
        "observation", "historical_actions", "admissible_actions"]
    assert plan["controls"]["keep_display_awake"] is False
    assert plan["controls"]["codex_monitor_required"] is False


@pytest.mark.parametrize("statement", [None, "", "yes", "AUTHORIZE", "AUTHORIZE " + "0" * 64])
def test_confirmation_required_before_any_write(statement, monkeypatch):
    def forbidden(*args):
        raise AssertionError("Unexpected write")
    monkeypatch.setattr(manual.durable, "publish", forbidden)
    with pytest.raises(ValueError, match="Exact local authorization"):
        manual.confirm(manual.make_plan(), statement)


def test_mutated_plan_rejected_even_with_recomputed_digest():
    plan = manual.make_plan()
    plan["closed_config"]["max_retries"] = 1
    plan["plan_sha256"] = manual.digest({k: v for k, v in plan.items() if k != "plan_sha256"})
    with pytest.raises(ValueError, match="binding changed"):
        manual.check_plan(plan)


def test_script_change_invalidates_prepared_plan(monkeypatch):
    plan = manual.make_plan()
    original = manual.durable.frozen.sha256
    monkeypatch.setattr(manual.durable.frozen, "sha256",
                        lambda path: "0" * 64 if path.name == manual.WRAPPER_REL.split("/")[-1]
                        else original(path))
    with pytest.raises(ValueError, match="binding changed"):
        manual.check_plan(plan)


def test_existing_output_or_receipt_refuses(monkeypatch):
    plan = manual.make_plan()
    original = manual.Path.exists
    monkeypatch.setattr(manual.Path, "exists",
                        lambda p: True if p == manual.ROOT / manual.RUN_REL else original(p))
    with pytest.raises(FileExistsError):
        manual.check_plan(plan)


def test_confirmation_binds_exact_plan_and_never_launches(monkeypatch):
    plan = manual.make_plan()
    written = {}
    monkeypatch.setattr(manual, "check_plan", lambda p: p)
    monkeypatch.setattr(manual.durable, "publish",
                        lambda path, payload: written.setdefault(path.name, copy.deepcopy(payload)))
    monkeypatch.setattr(manual.durable, "validate_config", lambda config: [])
    monkeypatch.setattr(manual.durable.frozen, "sha256", lambda path: "a" * 64)
    result = manual.confirm(plan, "AUTHORIZE " + plan["plan_sha256"])
    receipt = written[manual.Path(manual.RECEIPT_REL).name]
    config = written[manual.Path(manual.CONFIG_REL).name]
    assert len(written) == 2
    assert receipt["authorization_source"] == "explicit_local_terminal_confirmation"
    assert receipt["manual_plan_sha256"] == plan["plan_sha256"]
    assert receipt["bindings"]["durable_config_sha256"] == manual.durable.config_binding(config)
    assert config["execution_authorized"] is True
    assert result["run_directory"] == manual.RUN_REL


def test_wrapper_has_no_permanent_power_or_display_request():
    text = (manual.ROOT / manual.WRAPPER_REL).read_text(encoding="utf-8")
    assert "0x80000001u" in text
    assert "0x80000003" not in text
    assert "powercfg /change" not in text
    assert "$awake.Dispose()" in text
    assert "if ($CheckOnly)" in text
    assert "Stop-TG8Service $unit" in text
    assert "[DateTimeOffset]::UtcNow -ge $deadline" in text


def test_full_validation_of_synthetic_confirmation_in_temporary_paths(tmp_path, monkeypatch):
    base = tmp_path / "synthetic-output"
    monkeypatch.setattr(manual.durable, "OUTPUT_BASE", base)
    monkeypatch.setattr(manual, "RUN_REL", (base / "independent").as_posix())
    monkeypatch.setattr(manual, "CONFIG_REL", (tmp_path / "synthetic-config.json").as_posix())
    monkeypatch.setattr(manual, "RECEIPT_REL", (tmp_path / "synthetic-receipt.json").as_posix())
    plan = manual.make_plan()
    result = manual.confirm(plan, "AUTHORIZE " + plan["plan_sha256"])
    config = manual.durable.frozen.read_json(manual.Path(result["config"]))
    assert manual.durable.validate_config(config) == []
    assert not base.exists()
    with pytest.raises(FileExistsError):
        manual.confirm(plan, "AUTHORIZE " + plan["plan_sha256"])
