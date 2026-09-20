#!/usr/bin/env python3
"""Durable TG8 orchestration; a new exact authorization is required to execute."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import run_acl2027_tracegraph_tg8_observable_subgoal_runner_v1_authorized_ubuntu_wsl as frozen

LEGACY_SHA = "ef7e0a19780fd514a9227849b2467d0734f3f3c0a8cc840bd648a501ed4dfeed"
SCRIPT = Path(__file__).resolve()
CONFIG = ROOT / "configs/acl2027/tracegraph_tg8_durable_v2_candidate.json"
OUTPUT_BASE = ROOT / "artifacts/acl2027_tracegraph_tg8_durable_v2"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def config_binding(config: dict[str, Any]) -> str:
    # Receipt location/hash are excluded to avoid a circular hash dependency.
    payload = {k: v for k, v in config.items()
               if k not in {"authorization_receipt", "authorization_receipt_sha256"}}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=True).encode()).hexdigest()


def run_directory(config: dict[str, Any]) -> Path:
    directory = (ROOT / config["run_directory"]).resolve()
    base = OUTPUT_BASE.resolve()
    if directory.parent != base:
        raise ValueError("run_directory must be a new direct child of the TG8 v2 output base")
    if (ROOT / config["episode_result_output"]).resolve() != directory / "result.json":
        raise ValueError("result path must be run_directory/result.json")
    return directory


def validate_config(config: dict[str, Any]) -> list[str]:
    errors = frozen.validate_authorized_config(config)
    if config.get("durability_version") != 2:
        errors.append("durability_version must be 2")
    if (ROOT / str(config.get("runner", ""))).resolve() != SCRIPT:
        errors.append("runner must be this v2 script")
    if frozen.sha256(Path(frozen.__file__)) != LEGACY_SHA:
        errors.append("frozen row executor changed")
    if config.get("legacy_runner_sha256") != LEGACY_SHA:
        errors.append("legacy runner binding mismatch")
    launcher = ROOT / "scripts/start_acl2027_tracegraph_tg8_durable_v2.ps1"
    if not launcher.is_file() or frozen.sha256(launcher) != config.get("windows_launcher_sha256"):
        errors.append("Windows launcher binding mismatch")
    if config.get("max_wall_seconds") != 21600:
        errors.append("wall-time safety limit must be explicitly bound to 21600 seconds")
    skillbank = ROOT / str(config.get("skillbank", ""))
    if not skillbank.is_file() or frozen.sha256(skillbank) != config.get("skillbank_sha256"):
        errors.append("skillbank binding mismatch")
    try:
        directory = run_directory(config)
    except (KeyError, ValueError) as exc:
        errors.append(str(exc))
        directory = None
    receipt_path = ROOT / str(config.get("authorization_receipt", ""))
    if receipt_path.is_file():
        receipt = frozen.read_json(receipt_path)
        bindings = receipt.get("bindings", {})
        for key, value in {
            "durable_config_sha256": config_binding(config),
            "runner_sha256": frozen.sha256(SCRIPT),
            "legacy_runner_sha256": LEGACY_SHA,
        }.items():
            if bindings.get(key) != value:
                errors.append(f"new authorization {key} mismatch")
        if receipt.get("scope", {}).get("run_directory") != config.get("run_directory"):
            errors.append("receipt must bind the new independent run_directory")
        if receipt.get("scope", {}).get("max_wall_seconds") != config.get("max_wall_seconds"):
            errors.append("receipt wall-time safety limit mismatch")
    if directory is not None and directory.exists():
        errors.append("run_directory already exists; resume/overwrite forbidden")
    return errors


def sync_directory(directory: Path) -> None:
    if sys.platform == "linux":
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def publish(path: Path, payload: Any) -> None:
    """Publish complete JSON without replacing an existing artifact."""
    temporary = path.with_name(path.name + ".pending")
    with temporary.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    # Atomic, no-clobber publication; a crash can leave a diagnostic .pending.
    os.link(temporary, path)
    temporary.unlink()
    sync_directory(path.parent)


def event(directory: Path, kind: str, **fields: Any) -> None:
    record = {"at": now(), "event": kind, **fields}
    with (directory / "events.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    print(json.dumps(record), flush=True)


def _failed_row(row: dict[str, Any], ordinal: int, exc: Exception) -> dict[str, Any]:
    transitions = list(getattr(exc, "transitions", []))
    violation = {key: row.get(key) for key in ("run_id", "task_identity", "condition")}
    violation.update(ordinal=ordinal, type=type(exc).__name__, message=str(exc))
    result = {key: row.get(key) for key in (
        "run_id", "task_identity", "task_ordinal", "split", "task_family",
        "template_key", "replicate_index", "condition", "seed")}
    result.update(success=False, steps=len(transitions), stop_reason="hard_invariant_violation",
                  hard_invariant_violation=violation, metrics=None, transitions=transitions)
    return result


def execute_rows(config: dict[str, Any], directory: Path, rows: list[dict[str, Any]],
                 tasks: dict[str, Any], builder: Any, index: Any) -> dict[str, Any]:
    results = []
    violation = None
    for ordinal, row in enumerate(rows):
        event(directory, "row_started", ordinal=ordinal, run_id=row["run_id"])
        try:
            # The frozen executor retains all selection, step and metric semantics.
            episode = frozen.run_row(builder, index, Path(config["source_data_root"]),
                                     row, tasks[row["task_identity"]], row["max_steps"])
        except Exception as exc:
            episode = _failed_row(row, ordinal, exc)
        publish(directory / "rows" / f"{ordinal:04d}.json", episode)
        results.append(episode)
        violation = episode.get("hard_invariant_violation")
        event(directory, "row_saved", ordinal=ordinal, run_id=row["run_id"],
              rows_saved=len(results), steps=episode["steps"], success=episode["success"],
              hard_invariant_violation=violation)
        if violation is not None:
            break
    completed = sum(item.get("hard_invariant_violation") is None for item in results)
    result = {
        "schema_version": 2, "artifact_type": "tracegraph_tg8_durable_factorial_execution",
        "phase_id": config["phase_id"], "rows": results,
        "preflight_aggregate_fingerprint": frozen.PREFLIGHT_AGGREGATE,
        "selector_sha256": frozen.SELECTOR_SHA256,
        "selector_config_sha256": frozen.SELECTOR_CONFIG_SHA256,
        "readiness_artifact_sha256": frozen.READINESS_SHA256,
        "runner_sha256": config["runner_sha256"], "legacy_runner_sha256": LEGACY_SHA,
        "task_count": frozen.READINESS_TASKS, "planned_episode_rows": frozen.ROWS,
        "episodes_started": len(results), "episodes_completed": completed,
        "successes": sum(item["success"] for item in results),
        "actions_taken": sum(len(item["transitions"]) for item in results),
        "acknowledged_steps": sum("success_after_step" in transition
                                 for item in results for transition in item["transitions"]),
        "hard_invariant_violation": violation,
        "factorial_valid": violation is None and completed == frozen.ROWS,
        "max_steps_per_episode": frozen.MAX_STEPS, "max_retries": 0,
        "runtime_allowed_inputs": frozen.ALLOWED_INPUTS, "stop_rule": config["stop_rule"],
        "network_counters_independently_measured": False,
    }
    publish(directory / "result.json", result)
    return result


def record_execution(config: dict[str, Any], directory: Path) -> int:
    """Already-claimed worker. Tests substitute only the environment boundary."""
    started = now()
    code = 2
    outcome = "infrastructure_error"
    try:
        rows, tasks = frozen.load_schedule(config)
        os.environ["ALFWORLD_DATA"] = config["source_data_root"]
        index = frozen.selector.base.load_skill_index(ROOT / config["skillbank"])
        builder = frozen.env_base.load_alfworld_builder()
        result = execute_rows(config, directory, rows, tasks, builder, index)
        code = 0 if result["factorial_valid"] else 1
        outcome = "completed" if code == 0 else "stopped_invalid_factorial"
    except BaseException as exc:
        outcome = "interrupted" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else "infrastructure_error"
        code = 130 if outcome == "interrupted" else 2
        traceback.print_exc()
        event(directory, "execution_exception", type=type(exc).__name__, message=str(exc))
    finally:
        publish(directory / "exit.json", {
            "started_at": started, "ended_at": now(), "exit_code": code,
            "status": outcome, "result_present": (directory / "result.json").is_file(),
            "note": "Missing exit.json after a forced stop does not mean success.",
        })
    return code


@contextlib.contextmanager
def execution_lock():
    import fcntl

    OUTPUT_BASE.mkdir(parents=True, exist_ok=True)
    with (OUTPUT_BASE / ".active.lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def require_isolation() -> None:
    if sys.platform != "linux":
        raise RuntimeError("formal execution requires the Linux systemd service")
    if os.readlink("/proc/self/ns/net") == os.readlink("/proc/1/ns/net"):
        raise RuntimeError("PrivateNetwork isolation is required before environment loading")


def execute(config: dict[str, Any]) -> int:
    errors = validate_config(config)
    if errors:
        raise ValueError("; ".join(errors))
    require_isolation()
    directory = run_directory(config)
    with execution_lock():
        claims = OUTPUT_BASE / ".authorization_claims"
        claims.mkdir(exist_ok=True)
        publish(claims / f"{config['authorization_receipt_sha256']}.json",
                {"at": now(), "run_directory": str(directory), "reusable": False})
        directory.mkdir(exist_ok=False)
        (directory / "rows").mkdir()
        publish(directory / "config.json", config)
        publish(directory / "authorization.json",
                frozen.read_json(ROOT / config["authorization_receipt"]))
        publish(directory / "manifest.json", {
            "started_at": now(), "pid": os.getpid(),
            "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
            "config_binding_sha256": config_binding(config),
            "runner_sha256": frozen.sha256(SCRIPT), "legacy_runner_sha256": LEGACY_SHA,
            "private_network_namespace": os.readlink("/proc/self/ns/net"),
        })

        def terminate(signum, _frame):
            event(directory, "termination_requested", signal=signum)
            raise KeyboardInterrupt(f"received signal {signum}")

        old = signal.signal(signal.SIGTERM, terminate)
        try:
            with (directory / "stdout.log").open("x", buffering=1, encoding="utf-8") as out, (
                directory / "stderr.log").open("x", buffering=1, encoding="utf-8") as err:
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    return record_execution(config, directory)
        finally:
            signal.signal(signal.SIGTERM, old)


def service_command(config_path: Path, config: dict[str, Any]) -> list[str]:
    return [
        "systemd-run", "--wait", f"--unit=tg8-v2-{config['authorization_receipt_sha256'][:20]}",
        "--service-type=exec", "--property=Restart=no", "--property=KillMode=control-group",
        "--property=PrivateNetwork=yes", "--property=TimeoutStopSec=30",
        f"--property=RuntimeMaxSec={config['max_wall_seconds']}",
        "--property=StandardOutput=journal", "--property=StandardError=journal",
        f"--working-directory={ROOT}", sys.executable, "-B", "-u", str(SCRIPT),
        "execute", "--config", str(config_path.resolve()),
        "--expected-config-sha256", frozen.sha256(config_path),
    ]


def inspect_saved(directory: Path) -> dict[str, Any]:
    """Read-only recovery; never promote a partial run or trigger a resume."""
    episodes = []
    errors = []
    paths = sorted((directory / "rows").glob("*.json"))
    for ordinal, path in enumerate(paths):
        try:
            if path.name != f"{ordinal:04d}.json":
                raise ValueError("non-contiguous row prefix")
            episodes.append(frozen.read_json(path))
        except (ValueError, OSError) as exc:
            errors.append(f"{path.name}: {exc}")
            break
    exit_path = directory / "exit.json"
    try:
        exit_record = frozen.read_json(exit_path) if exit_path.is_file() else None
    except (ValueError, OSError) as exc:
        errors.append(f"exit.json: {exc}")
        exit_record = None
    last_event = None
    event_path = directory / "events.jsonl"
    if event_path.is_file():
        with event_path.open(encoding="utf-8") as handle:
            for line in handle:
                try:
                    last_event = json.loads(line)
                except ValueError:
                    errors.append("event log has an incomplete or invalid record")
                    break
    return {
        "run_directory": str(directory), "directory_exists": directory.is_dir(),
        "durable_rows_readable": len(episodes),
        "durable_successes": sum(row.get("success") is True for row in episodes),
        "exit": exit_record, "recovery_errors": errors,
        "last_durable_event": last_event,
        "pending_artifacts": [path.relative_to(directory).as_posix()
                              for path in sorted(directory.rglob("*.pending"))],
        "status": exit_record["status"] if exit_record else "no_exit_record_liveness_unknown",
        "formal_result_audited": False, "resume_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["validate", "launch", "execute", "status"])
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--expected-config-sha256")
    args = parser.parse_args()
    try:
        if args.expected_config_sha256 and frozen.sha256(args.config) != args.expected_config_sha256:
            raise ValueError("config changed after service submission")
        config = frozen.read_json(args.config)
        if args.command == "status":
            print(json.dumps(inspect_saved(run_directory(config)), indent=2))
            return 0
        if args.command == "validate":
            errors = validate_config(config)
            print(json.dumps({"errors": errors, "config_binding_sha256": config_binding(config)}))
            return 2 if errors else 0
        if args.command == "execute":
            return execute(config)
        errors = validate_config(config)
        if errors:
            raise ValueError("; ".join(errors))
        if sys.platform != "linux":
            raise RuntimeError("launch must be issued inside WSL")
        subprocess.run(service_command(args.config, config), check=True)
        return 0
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
