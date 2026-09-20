"""Offline preparation and explicit human confirmation for one new TG8 run."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import run_acl2027_tracegraph_tg8_durable_v2 as durable

PLAN = ROOT / "configs/acl2027/tracegraph_tg8_manual_plan_20260916.json"
CONFIG_REL = "configs/acl2027/tracegraph_tg8_manual_authorized_20260916.json"
RECEIPT_REL = "configs/acl2027/tracegraph_tg8_manual_receipt_20260916.json"
RUN_REL = "artifacts/acl2027_tracegraph_tg8_durable_v2/independent_20260916_manual_v1"
WRAPPER_REL = "scripts/start_acl2027_tg8_manual_v1.ps1"
SELF_REL = "scripts/prepare_acl2027_tg8_manual_v1.py"
CLOSED_ERRORS = {
    "execution_authorized mismatch", "episode_execution_allowed mismatch",
    "authorization_status mismatch", "authorization receipt missing or changed",
}


def digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True).encode()).hexdigest()


def activated(config):
    result = copy.deepcopy(config)
    result.update(execution_authorized=True, episode_execution_allowed=True,
                  authorization_status="authorized")
    return result


def make_plan():
    config = durable.frozen.read_json(durable.CONFIG)
    config.update(run_directory=RUN_REL, episode_result_output=RUN_REL + "/result.json",
                  authorization_receipt=RECEIPT_REL, authorization_receipt_sha256="pending")
    payload = {
        "schema_version": 1, "status": "awaiting_explicit_local_confirmation",
        "authorized_config": CONFIG_REL, "authorization_receipt": RECEIPT_REL,
        "closed_config": config,
        "activated_config_binding_sha256": durable.config_binding(activated(config)),
        "files": {
            relative: durable.frozen.sha256(ROOT / relative)
            for relative in (WRAPPER_REL, SELF_REL,
                             "scripts/start_acl2027_tracegraph_tg8_durable_v2.ps1",
                             config["runner"])
        },
        "bindings": {
            "preflight_aggregate_fingerprint": durable.frozen.PREFLIGHT_AGGREGATE,
            "selector_sha256": durable.frozen.SELECTOR_SHA256,
            "selector_config_sha256": durable.frozen.SELECTOR_CONFIG_SHA256,
            "readiness_artifact_sha256": durable.frozen.READINESS_SHA256,
            "runner_sha256": config["runner_sha256"],
            "legacy_runner_sha256": durable.LEGACY_SHA,
            "windows_launcher_sha256": config["windows_launcher_sha256"],
            "skillbank_sha256": config["skillbank_sha256"],
        },
        "controls": {
            "keep_system_awake": True, "keep_display_awake": False,
            "require_ac_at_start": True, "max_wall_seconds": 21600,
            "shutdown_grace_seconds": 30,
            "windows_deadline_poll_seconds": 5,
            "forced_sleep_or_shutdown_not_prevented": True,
            "no_automatic_retry_resume_or_additional_runs": True,
            "codex_monitor_required": False,
        },
    }
    payload["plan_sha256"] = digest(payload)
    return payload


def check_plan(plan):
    payload = {k: v for k, v in plan.items() if k != "plan_sha256"}
    if digest(payload) != plan.get("plan_sha256"):
        raise ValueError("manual plan digest mismatch")
    # Reconstruct from the frozen candidate so edits cannot silently expand scope.
    if plan != make_plan():
        raise ValueError("manual plan, script or frozen binding changed; prepare a new reviewed version")
    for relative in (CONFIG_REL, RECEIPT_REL, RUN_REL):
        if (ROOT / relative).exists():
            raise FileExistsError(f"Already prepared/used; do not retry or overwrite: {relative}")
    errors = set(durable.validate_config(plan["closed_config"]))
    if errors != CLOSED_ERRORS:
        raise ValueError(f"unexpected closed-candidate validation errors: {sorted(errors)}")
    return plan


def confirm(plan, statement):
    check_plan(plan)
    expected = "AUTHORIZE " + plan["plan_sha256"]
    if statement != expected:
        raise ValueError("Exact local authorization not received; nothing activated")
    config = activated(plan["closed_config"])
    receipt = {
        "schema_version": 8, "status": "authorized", "authorization_opened": True,
        "authorization_source": "explicit_local_terminal_confirmation",
        "authorization_statement": statement, "authorized_at": durable.now(),
        "manual_plan": PLAN.relative_to(ROOT).as_posix(),
        "manual_plan_sha256": plan["plan_sha256"],
        "bindings": {**plan["bindings"],
                     "durable_config_sha256": durable.config_binding(config),
                     "manual_files": plan["files"]},
        "scope": {
            **{key: config[key] for key in (
                "planned_episode_rows", "max_steps_per_episode", "max_retries",
                "runtime_allowed_inputs", "stop_rule", "run_directory", "max_wall_seconds")},
            "shutdown_grace_seconds": 30, "resume_allowed": False,
            "overwrite_allowed": False, "additional_runs_allowed": False,
        },
        "execution": {key: value for key, value in config.items()
                      if key.endswith("_allowed") and value is False},
        "controls": plan["controls"],
    }
    durable.publish(ROOT / RECEIPT_REL, receipt)
    config["authorization_receipt_sha256"] = durable.frozen.sha256(ROOT / RECEIPT_REL)
    durable.publish(ROOT / CONFIG_REL, config)
    errors = durable.validate_config(config)
    if errors:
        raise ValueError(f"Activated artifacts preserved, but validation failed; do not launch: {errors}")
    return {"config": CONFIG_REL, "receipt": RECEIPT_REL,
            "config_sha256": durable.frozen.sha256(ROOT / CONFIG_REL),
            "run_directory": RUN_REL, "authorization_source": "explicit_local_terminal_confirmation"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "review", "confirm"])
    parser.add_argument("--authorization")
    args = parser.parse_args()
    if args.command == "prepare":
        plan = check_plan(make_plan())
        durable.publish(PLAN, plan)
    else:
        plan = check_plan(durable.frozen.read_json(PLAN))
    if args.command == "confirm":
        print(json.dumps(confirm(plan, args.authorization), indent=2))
    else:
        print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
