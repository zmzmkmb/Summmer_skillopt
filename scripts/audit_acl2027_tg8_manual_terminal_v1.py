"""Offline terminal audit of the single authorized September 16 TG8 run."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import run_acl2027_tracegraph_tg8_durable_v2 as durable

frozen = durable.frozen
CONFIG = ROOT / "configs/acl2027/tracegraph_tg8_manual_authorized_20260916.json"
DEFAULT_OUTPUT = ROOT / "artifacts/acl2027_tracegraph_tg8_durable_v2/audit_20260917_manual_v1"
PLAN_SHA = "bb68465f38a85105042dc086426415f1b6b2465c67997569d5bc412399c072ba"
CONFIG_SHA = "aba5b4567e8d635587e6f58c2bf0493bae8a821f0b3cbacbd58d0e8ecdcbd205"
IDENTITY_FIELDS = (
    "run_id", "task_identity", "task_ordinal", "split", "task_family",
    "template_key", "replicate_index", "condition", "condition_position",
    "latin_rotation", "seed",
)


class CachedSkillIndex:
    """Memoize pure queries to one immutable, hash-verified SkillIndex."""

    def __init__(self, source):
        self.source = source
        self.cache = {}
        self.calls = 0

    def matching_skill_ids(self, command):
        self.calls += 1
        if command not in self.cache:
            self.cache[command] = tuple(self.source.matching_skill_ids(command))
        return list(self.cache[command])


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def require(predicate, message):
    if not predicate:
        raise ValueError(message)


def audit_row(row, scheduled, task, index=None):
    for key in IDENTITY_FIELDS:
        require(row.get(key) == scheduled[key], f"schedule identity: {key}")
    require(row.get("gamefile_sha256") == task["gamefile_sha256"], "gamefile binding")
    transitions = row["transitions"]
    require(0 < len(transitions) == row["steps"] <= 75, "step count/cap")
    require(row["hard_invariant_violation"] is None, "recorded hard invariant")
    history, snapshots, previous = [], [], None
    for step, transition in enumerate(transitions):
        require(transition["step"] == step, "step sequence")
        require(transition["selector_condition"] == row["condition"], "condition")
        runtime = transition["runtime_inputs"]
        require(list(runtime) == frozen.ALLOWED_INPUTS, "runtime fields")
        require(runtime["historical_actions"] == history, "complete action history")
        require(isinstance(runtime["observation"], str), "observation type")
        require(transition["terminal_action_decision"] in runtime["admissible_actions"],
                "terminal admissibility")
        require(type(transition["success_after_step"]) is bool, "acknowledged step")
        require(not transition["success_after_step"] or step == len(transitions) - 1,
                "continued after success")
        valid, message = frozen.env_base.validate_transition(transition)
        require(valid, f"base invariant: {message}")
        ledger = transition["subgoal_ledger"]
        require(ledger[frozen.selector.LEDGER_FINGERPRINT_FIELD]
                == frozen.selector.ledger_fingerprint(ledger), "ledger fingerprint")
        snapshot = frozen.selector.snapshot_fingerprint(
            runtime["observation"], runtime["admissible_actions"])
        require(transition["observable_snapshot_fingerprint"] == snapshot, "snapshot")
        require(transition["repeated_observable_snapshot"] == (snapshot in snapshots),
                "snapshot history")
        if index is not None:
            valid, message = frozen.selector.validate_selector_transition(
                transition, previous, index=index)
            require(valid, f"selector invariant at step {step}: {message}")
        history.append(transition["terminal_action_decision"])
        snapshots.append(snapshot)
        previous = ledger
    require(type(row["success"]) is bool, "success type")
    require(row["success"] == transitions[-1]["success_after_step"], "success mismatch")
    require(row["stop_reason"] in {"success", "environment_done", "max_steps"},
            "unknown stop reason")
    require((row["stop_reason"] == "success") == row["success"], "stop reason mismatch")
    require(row["stop_reason"] != "max_steps" or row["steps"] == 75, "early max_steps")
    metrics = frozen.episode_metrics(transitions, row["success"])
    require(row["metrics"] == metrics, "episode metric mismatch")
    for key in ("ledger_validity", "ledger_provenance_completeness",
                "trace_validity", "terminal_admissibility"):
        require(metrics[key] is True, f"metric invariant: {key}")
    require(metrics["history_truncation"] is False, "history truncation")
    return metrics


def describe(rows):
    summaries = {}
    for condition in frozen.selector.CONDITIONS:
        group = [row for row in rows if row["condition"] == condition]
        summaries[condition] = {
            "rows": len(group),
            "successes": sum(row["success"] for row in group),
            "success_rate": sum(row["success"] for row in group) / len(group),
            "completion_by_step_50": sum(row["metrics"]["completion_by_step_50"] for row in group),
            "two_cycle_episodes_by_step_50": sum(
                row["metrics"]["episode_two_cycle_incidence_by_step_50"] for row in group),
            "actions": sum(row["steps"] for row in group),
            "stop_reasons": dict(Counter(row["stop_reason"] for row in group)),
        }
    family_split = []
    groups = defaultdict(list)
    for row in rows:
        groups[(row["condition"], row["task_family"], row["split"])].append(row)
    for (condition, family, split), group in sorted(groups.items()):
        family_split.append(dict(condition=condition, task_family=family, split=split,
                                 rows=len(group), successes=sum(r["success"] for r in group)))
    return summaries, family_split


def audit(output: Path, full_selector: bool):
    output = output.resolve()
    require(not output.exists(), "audit output already exists; overwrite forbidden")
    require(output.parent == DEFAULT_OUTPUT.parent.resolve(), "output outside audit base")
    require(output.name.startswith("audit_"), "audit output must use audit_ prefix")
    config = frozen.read_json(CONFIG)
    require(digest(CONFIG) == CONFIG_SHA, "frozen config file changed")
    require(durable.validate_config(config) ==
            ["run_directory already exists; resume/overwrite forbidden"],
            "unexpected frozen validation error")
    directory = ROOT / config["run_directory"]
    evidence_paths = list(directory.rglob("*"))
    evidence_paths = [path for path in evidence_paths if path.is_file()]
    evidence_paths += [CONFIG, ROOT / config["authorization_receipt"]]
    evidence_paths += [ROOT / config[key] for key in (
        "preflight_artifact", "development_schedule", "selector", "selector_config",
        "readiness_artifact", "skillbank", "runner")]
    evidence_paths += [
        Path(frozen.__file__), Path(__file__),
        ROOT / "configs/acl2027/tracegraph_tg8_manual_plan_20260916.json",
        ROOT / "configs/acl2027/tracegraph_tg8_manual_deadline_cancellation_20260916.json",
        ROOT / "artifacts/acl2027_tg8_manual_control_20260916/deadline_cancellation_applied.json",
        ROOT / "artifacts/acl2027_tg8_manual_control_20260916/no_deadline_guardian.stdout.log",
        ROOT / "skillopt/envs/alfworld/vendor/config_tw.yaml",
        ROOT / "skillopt/envs/alfworld/vendor/alfworld_envs.py",
    ]
    hashes = {p.relative_to(ROOT).as_posix(): digest(p) for p in evidence_paths}
    plan = frozen.read_json(ROOT / "configs/acl2027/tracegraph_tg8_manual_plan_20260916.json")
    canonical = json.dumps({k: v for k, v in plan.items() if k != "plan_sha256"},
                           sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    require(hashlib.sha256(canonical.encode()).hexdigest() == plan["plan_sha256"]
            == PLAN_SHA, "manual plan binding")
    for path, expected in plan["files"].items():
        require(digest(ROOT / path) == expected, f"manual file binding: {path}")
    receipt = frozen.read_json(ROOT / config["authorization_receipt"])
    require(receipt["manual_plan_sha256"] == PLAN_SHA, "receipt plan")
    require(frozen.read_json(directory / "config.json") == config, "config copy")
    require(frozen.read_json(directory / "authorization.json") == receipt, "receipt copy")
    manifest = frozen.read_json(directory / "manifest.json")
    for key, expected in (
        ("config_binding_sha256", durable.config_binding(config)),
        ("runner_sha256", config["runner_sha256"]),
        ("legacy_runner_sha256", durable.LEGACY_SHA),
    ):
        require(manifest[key] == expected, f"manifest {key}")
    amendment_path = ROOT / "configs/acl2027/tracegraph_tg8_manual_deadline_cancellation_20260916.json"
    amendment = frozen.read_json(amendment_path)
    application = frozen.read_json(
        ROOT / "artifacts/acl2027_tg8_manual_control_20260916/deadline_cancellation_applied.json")
    require(application["authorization_amendment_sha256"] == digest(amendment_path),
            "deadline amendment hash")
    require(amendment["run_directory"] == config["run_directory"]
            and amendment["original_config_file_sha256"] == CONFIG_SHA
            and application["service_runtime_max"] == "infinity"
            and application["service_main_pid"] == manifest["pid"], "deadline amendment binding")
    result = frozen.read_json(directory / "result.json")
    exit_record = frozen.read_json(directory / "exit.json")
    require(exit_record["status"] == "completed" and exit_record["exit_code"] == 0
            and exit_record["result_present"] is True, "terminal exit")
    schedule, tasks = frozen.load_schedule(config)
    rows = result["rows"]
    require(len(rows) == 360 and len({r["run_id"] for r in rows}) == 360, "row uniqueness")
    require(len({r["task_identity"] for r in rows}) == 30, "task uniqueness")
    require(sorted(p.name for p in (directory / "rows").iterdir()) ==
            [f"{i:04d}.json" for i in range(360)], "row file set")
    events = [json.loads(line) for line in
              (directory / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    require(len(events) == 720, "event count")
    times = [datetime.fromisoformat(event["at"]) for event in events]
    require(times == sorted(times), "event timestamp order")
    require(datetime.fromisoformat(exit_record["started_at"]) <= times[0]
            <= times[-1] <= datetime.fromisoformat(exit_record["ended_at"]), "event time bounds")
    index = CachedSkillIndex(frozen.selector.base.load_skill_index(
        ROOT / config["skillbank"])) if full_selector else None
    print(f"Auditing 360 rows; full_selector={full_selector}", flush=True)
    for ordinal, (row, planned) in enumerate(zip(rows, schedule)):
        require(frozen.read_json(directory / "rows" / f"{ordinal:04d}.json") == row,
                f"aggregate/row file mismatch: {ordinal}")
        try:
            audit_row(row, planned, tasks[row["task_identity"]], index)
        except ValueError as exc:
            raise ValueError(f"row {ordinal}: {exc}") from exc
        start, saved = events[2 * ordinal:2 * ordinal + 2]
        for event, kind in ((start, "row_started"), (saved, "row_saved")):
            require(event["event"] == kind and event["ordinal"] == ordinal
                    and event["run_id"] == row["run_id"], f"event identity: {ordinal}")
        require(saved["rows_saved"] == ordinal + 1 and saved["steps"] == row["steps"]
                and saved["success"] == row["success"]
                and saved["hard_invariant_violation"] is None, f"saved event: {ordinal}")
        if (ordinal + 1) % 30 == 0:
            print(f"Verified {ordinal + 1}/360 rows", flush=True)
    expected_totals = dict(
        episodes_started=360, episodes_completed=360, planned_episode_rows=360,
        task_count=30, max_steps_per_episode=75, max_retries=0, factorial_valid=True,
        hard_invariant_violation=None, runtime_allowed_inputs=frozen.ALLOWED_INPUTS,
        actions_taken=sum(r["steps"] for r in rows),
        acknowledged_steps=sum(r["steps"] for r in rows),
        successes=sum(r["success"] for r in rows),
        network_counters_independently_measured=False,
    )
    for key, expected in expected_totals.items():
        require(result[key] == expected, f"aggregate {key}")
    for key in ("preflight_aggregate_fingerprint", "selector_sha256",
                "selector_config_sha256", "readiness_artifact_sha256",
                "runner_sha256", "legacy_runner_sha256"):
        require(result[key] == receipt["bindings"][key], f"result binding: {key}")
    for path, expected in hashes.items():
        require(digest(ROOT / path) == expected, f"evidence changed during audit: {path}")
    summaries, family_split = describe(rows)
    payload = {
        "schema_version": 1, "status": "passed",
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "run_directory": config["run_directory"],
        "scope": "Saved-artifact integrity and descriptive counts; no environment execution",
        "new_episodes": 0, "new_actions": 0, "full_selector_recomputed": full_selector,
        "selector_steps_recomputed": expected_totals["actions_taken"] if full_selector else 0,
        "skill_lookup_cache": {
            "queries": index.calls, "unique_commands": len(index.cache),
            "method": "Exact string key; frozen pure lookup on first use; fresh list on every return",
        } if index is not None else None,
        "totals": expected_totals, "exit": exit_record,
        "condition_summaries": summaries, "family_split_summaries": family_split,
        "step_distribution": dict(sorted(Counter(r["steps"] for r in rows).items())),
        "failure_steps": dict(Counter(r["steps"] for r in rows if not r["success"])),
        "deadline_amendment_verified": True,
        "immutable_input_sha256": hashes,
        "limitations": [
            "Success labels are recorded environment outcomes, not independently replayed.",
            "All rows end by step 50; 75-step sensitivity cannot be interpreted as an extended horizon.",
            "Current vendor YAML has 50-step limits; its launch-time hash was not frozen in the receipt.",
            "Full selector validation uses the frozen validator, not a separately implemented oracle.",
            "Static SkillIndex queries are memoized; every step's ranking and ledger are rebuilt.",
            "Network isolation evidence is not independent network traffic measurement.",
            "Thirty task identities, not 360 independent tasks; no inferential test performed here.",
            "Earlier partial attempts are preserved separately and are not pooled.",
        ],
    }
    output.mkdir(exist_ok=False)
    durable.publish(output / "audit.json", payload)
    durable.publish(output / "completion_manifest.json", {
        "status": "complete", "audit_sha256": digest(output / "audit.json"),
        "script_sha256": digest(Path(__file__)),
        "result_sha256": hashes[(directory / "result.json").relative_to(ROOT).as_posix()],
    })
    print(json.dumps(summaries, indent=2), flush=True)
    print(f"PASS: {output}", flush=True)
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--full-selector", action="store_true")
    args = parser.parse_args()
    audit(args.output, args.full_selector)


if __name__ == "__main__":
    main()
