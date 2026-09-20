#!/usr/bin/env python3
"""Run the ACL 2027 Phase 1B SearchQA Token Plan v4 pilot.

V4 pre-registers an output-only prompt override and one bounded formatting
repair attempt. Dry-run and live execution share prompt rendering, retrieval,
guard, resume, and accounting paths. Live mode is additionally gated by the
frozen config and repository experiment state.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.metadata
import io
import json
import math
import os
import re
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

from openai import OpenAI

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
DEFAULT_CONFIG = (
    PROJECT_ROOT / "configs" / "acl2027" / "searchqa_phase1b_token_plan_live_pilot_v4.json"
)
DEFAULT_STATE = PROJECT_ROOT / "paper" / "acl2027" / "experiment_state.json"
DEFAULT_BASE_URL = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
PICO_PER_UNIT = 10**12


class PreflightError(RuntimeError):
    """Base class for an explicit Phase 1B pilot failure."""


class ConfigError(PreflightError):
    """Raised when an immutable input or protocol field is invalid."""


class StrictAnswerError(PreflightError):
    """Raised when a response violates the strict answer contract."""


class ProviderUsageError(PreflightError):
    """Raised when a provider response has missing or inconsistent usage."""


class ResumeError(PreflightError):
    """Raised when persisted resume state is malformed or mismatched."""


class BudgetExceeded(PreflightError):
    """Raised before an attempt that would cross a frozen hard cap."""


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def object_fingerprint(payload: Any) -> str:
    return sha256_bytes(canonical_json(payload).encode("utf-8"))


def summary_fingerprint(payload: dict[str, Any]) -> str:
    """Fingerprint scientific totals while excluding invocation-local resume fields."""
    excluded = {
        "summary_fingerprint",
        "new_calls_this_invocation",
        "provider_invocations_this_process",
    }
    return object_fingerprint({key: value for key, value in payload.items() if key not in excluded})


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"required file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid JSON in {path}: {exc}") from exc


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ConfigError(message)


def _verify_file_hash(root: Path, spec: dict[str, Any], path_key: str, hash_key: str) -> Path:
    path = _resolve(root, str(spec[path_key]))
    expected = str(spec[hash_key])
    actual = sha256_file(path)
    if actual != expected:
        raise ConfigError(
            f"immutable hash mismatch for {path_key}: expected {expected}, got {actual}"
        )
    return path


def _candidate_parameters_from_source(source: dict[str, Any], method_name: str) -> dict[str, Any]:
    methods = source.get("methods")
    if not isinstance(methods, list):
        raise ConfigError("frozen candidate source has no method list")
    matches = [method for method in methods if method.get("name") == method_name]
    if len(matches) != 1:
        raise ConfigError(
            f"expected exactly one {method_name!r} in frozen candidate source; got {len(matches)}"
        )
    return {key: value for key, value in matches[0].items() if key != "name"}


def pricing_units(config: dict[str, Any]) -> dict[str, int]:
    """Return exact integer pico-currency rates per token."""
    pricing = config["pricing_snapshot"]
    cny_per_usd = Decimal(str(pricing["fixed_accounting_cny_per_usd"]))
    if cny_per_usd <= 0:
        raise ConfigError("fixed_accounting_cny_per_usd must be positive")

    result: dict[str, int] = {}
    for direction in ("input", "output"):
        cny_per_million = Decimal(str(pricing[f"{direction}_cny_per_million_tokens"]))
        pico_cny_per_token = cny_per_million * Decimal(PICO_PER_UNIT) / Decimal(1_000_000)
        pico_usd_per_token = (pico_cny_per_token / cny_per_usd).quantize(Decimal("1"))
        if pico_cny_per_token != pico_cny_per_token.to_integral_value():
            raise ConfigError(f"{direction} price is not exactly representable in pico-CNY")
        result[f"{direction}_pico_cny_per_token"] = int(pico_cny_per_token)
        result[f"{direction}_pico_usd_per_token"] = int(pico_usd_per_token)
    return result


def validate_config(config_path: Path = DEFAULT_CONFIG, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    """Validate the frozen protocol and every immutable input hash."""
    config_path = config_path.resolve()
    config = read_json(config_path)
    _require(isinstance(config, dict), "config must be a JSON object")
    _require(config.get("schema_version") == 2, "unsupported SearchQA config schema")
    _require(config.get("phase") == "1B", "config phase must be 1B")

    execution = config.get("execution", {})
    _require(execution.get("default_mode") == "dry-run", "default mode must be dry-run")
    _require(execution.get("paid_api_allowed") is True, "v4 config must allow one bounded authorized Token Plan smoke")
    _require(execution.get("formal_scaling_allowed") is False, "formal scaling must stay closed")
    _require(execution.get("token_plan_allowed") is True, "Token Plan route must be explicit")
    _require(execution.get("provider_written_permission_attested") is True, "written provider permission attestation is required")
    _require(execution.get("billing_route") == "token_plan_authorized", "v4 runner requires the authorized Token Plan route")
    _require(
        execution.get("hidden_backend_retries_allowed") is False,
        "hidden backend retries must be disabled",
    )
    model = config.get("model", {})
    _require(model.get("model_id") == "qwen3.6-flash", "frozen model must be qwen3.6-flash")
    _require(model.get("endpoint") == DEFAULT_BASE_URL, "unexpected provider endpoint")
    _require(model.get("enable_thinking") is False, "thinking must be explicitly disabled")
    repair = config.get("formatting_repair", {})
    _require(repair.get("enabled") is True, "v4 formatting repair must be enabled")
    _require(repair.get("trigger") == "strict_parser_failure_with_nonempty_response", "unexpected repair trigger")
    _require(repair.get("max_repairs_per_logical_call") == 1, "exactly one repair attempt is required")
    _require(repair.get("temperature") == 0.0, "repair temperature must be zero")
    _require(repair.get("primary_max_output_tokens") == 256, "primary output cap must be 256")
    _require(repair.get("repair_max_input_tokens") == 2048, "repair input cap must be 2048")
    _require(repair.get("repair_max_output_tokens") == 64, "repair output cap must be 64")
    _require(repair.get("include_original_question") is False, "repair must not see the original question")
    _require(repair.get("include_original_context") is False, "repair must not see the original context")
    _require(repair.get("allow_new_facts") is False, "repair must not introduce new facts")
    installed_openai = importlib.metadata.version("openai")
    _require(
        model.get("openai_sdk_version") == installed_openai == "2.45.0",
        f"OpenAI SDK contract changed: config={model.get('openai_sdk_version')}, "
        f"installed={installed_openai}",
    )

    dataset = config.get("dataset", {})
    seeds = dataset.get("replicate_seeds")
    _require(isinstance(seeds, list) and len(seeds) == 3, "exactly three replicate seeds required")
    _require(len(set(seeds)) == len(seeds), "replicate seeds must be unique")
    items_per_replicate = int(dataset.get("items_per_replicate", 0))
    probe_count = int(dataset.get("guard_probe_items_per_replicate", -1))
    evaluation_count = int(dataset.get("evaluation_items_per_replicate", -1))
    _require(100 <= items_per_replicate <= 200, "items_per_replicate must be in [100, 200]")
    _require(
        probe_count + evaluation_count == items_per_replicate,
        "probe and evaluation counts must sum to items_per_replicate",
    )

    methods = config.get("methods")
    _require(isinstance(methods, list) and 5 <= len(methods) <= 7, "five to seven methods required")
    method_names = [str(method.get("name", "")) for method in methods]
    _require(all(method_names), "every method requires a name")
    _require(len(set(method_names)) == len(method_names), "method names must be unique")
    frozen_name = str(config["frozen_candidate_source"]["method_name"])
    _require(method_names.count(frozen_name) == 1, "frozen candidate must appear exactly once")

    dataset_path = _verify_file_hash(root, dataset, "items_path", "items_sha256")
    split_manifest_path = _verify_file_hash(
        root, dataset, "split_manifest_path", "split_manifest_sha256"
    )
    skill_path = _verify_file_hash(root, config["skill"], "path", "sha256")
    _require(skill_path.stat().st_size == int(config["skill"]["bytes"]), "skill byte count mismatch")
    _verify_file_hash(
        root,
        config["formatting_development_fixture"],
        "path",
        "sha256",
    )

    split_manifest = read_json(split_manifest_path)
    _require(
        int(split_manifest.get("counts", {}).get("test", -1)) == int(dataset["available_items"]),
        "SearchQA split manifest test count mismatch",
    )
    items = read_json(dataset_path)
    _require(isinstance(items, list), "SearchQA items must be a JSON array")
    _require(len(items) == int(dataset["available_items"]), "SearchQA item count mismatch")

    source_spec = config["frozen_candidate_source"]
    source_path = _verify_file_hash(root, source_spec, "config_path", "config_sha256")
    source = read_json(source_path)
    actual_parameters = _candidate_parameters_from_source(source, frozen_name)
    expected_parameters = source_spec["parameters"]
    if actual_parameters != expected_parameters:
        raise ConfigError("frozen Phase 0N candidate parameters changed")

    source_paths: dict[str, str] = {}
    for name, spec in config["source_fingerprints"].items():
        source_paths[name] = str(_verify_file_hash(root, spec, "path", "sha256"))

    from skillopt.rag_rule_selector import RuleMemory

    rule_memory = RuleMemory(
        skill_path.read_text(encoding="utf-8"),
        top_k=5,
        token_budget=2000,
        method="tfidf",
    )
    _require(
        rule_memory.rule_set_fingerprint == config["skill"]["rule_set_fingerprint"],
        "parsed rule-set fingerprint mismatch",
    )
    _require(rule_memory.n_core == 1 and rule_memory.n_dynamic == 8, "unexpected rule counts")

    workload = config["planned_workload"]
    guarded_branches = sum(len(method.get("guard_probe_branches", [])) for method in methods)
    expected_main = len(seeds) * evaluation_count * len(methods)
    expected_guard = len(seeds) * probe_count * guarded_branches
    _require(
        int(workload["main_evaluation_logical_calls"]) == expected_main,
        "main evaluation workload formula mismatch",
    )
    _require(
        int(workload["guard_probe_logical_calls"]) == expected_guard,
        "guard probe workload formula mismatch",
    )
    _require(
        int(workload["total_logical_calls"]) == expected_main + expected_guard == 2448,
        "total workload must be exactly 2448",
    )
    expected_fallback = (
        len(seeds)
        * probe_count
        * sum(
            1
            for method in methods
            for branch in method.get("guard_probe_branches", [])
            if "cold" in str(branch)
        )
    )
    _require(
        int(workload["fallback_logical_calls"]) == expected_fallback == 48,
        "fallback workload must be exactly 48",
    )

    guard = config["guard"]
    _require(Decimal(str(guard["decision_boundary"])) == Decimal("-0.06"), "guard boundary")
    _require(int(guard["min_samples"]) == 6, "guard min_samples changed")
    _require(int(guard["min_accept_rounds"]) == 8, "guard accept horizon changed")

    caps = config["hard_caps"]
    max_attempts = int(config["model"]["max_attempts_per_logical_call"])
    _require(int(caps["logical_calls"]) == 2448, "logical-call cap must be exact")
    _require(
        int(caps["provider_attempts"]) >= (expected_main + expected_guard) * max_attempts,
        "provider-attempt cap cannot cover the frozen retry policy",
    )
    _require(
        int(caps["total_tokens"]) == int(caps["input_tokens"]) + int(caps["output_tokens"]),
        "total-token cap must equal input plus output caps",
    )
    units = pricing_units(config)
    max_cost_pico_cny = (
        int(caps["input_tokens"]) * units["input_pico_cny_per_token"]
        + int(caps["output_tokens"]) * units["output_pico_cny_per_token"]
    )
    declared_envelope_pico_cny = int(
        Decimal(str(caps["priced_token_envelope_cny"])) * PICO_PER_UNIT
    )
    _require(
        declared_envelope_pico_cny >= max_cost_pico_cny,
        "priced token envelope is below the frozen token-cap price",
    )
    declared_cost_pico_cny = int(Decimal(str(caps["cost_cny"])) * PICO_PER_UNIT)
    _require(
        declared_cost_pico_cny == 200 * PICO_PER_UNIT,
        "absolute Phase 1B CNY cap must be 200",
    )
    _require(
        max_cost_pico_cny <= declared_cost_pico_cny,
        "token caps can exceed the absolute CNY cap",
    )

    parser = config["parser_contract"]
    _require(parser.get("fallback_to_last_line") is False, "strict parser fallback must be disabled")
    config["_validated"] = {
        "config_path": str(config_path),
        "config_sha256": sha256_file(config_path),
        "dataset_path": str(dataset_path),
        "skill_path": str(skill_path),
        "source_paths": source_paths,
        "pricing_units": units,
    }
    return config


_ANSWER_PATTERN = re.compile(r"<answer>(.*?)</answer>", re.IGNORECASE | re.DOTALL)
_OPEN_PATTERN = re.compile(r"<answer>", re.IGNORECASE)
_CLOSE_PATTERN = re.compile(r"</answer>", re.IGNORECASE)


def strict_extract_answer(text: str) -> str:
    """Extract exactly one non-empty, balanced ``<answer>`` element."""
    text = str(text or "")
    opens = len(_OPEN_PATTERN.findall(text))
    closes = len(_CLOSE_PATTERN.findall(text))
    matches = _ANSWER_PATTERN.findall(text)
    if opens == 0 and closes == 0:
        raise StrictAnswerError("missing <answer>...</answer> element")
    if opens != closes or opens != len(matches):
        raise StrictAnswerError("unbalanced or nested answer tags")
    if len(matches) != 1:
        raise StrictAnswerError(f"expected exactly one answer element; got {len(matches)}")
    answer = matches[0].strip()
    if not answer:
        raise StrictAnswerError("answer element is empty")
    return answer


def load_searchqa_items(config: dict[str, Any]) -> list[dict[str, Any]]:
    path = Path(config["_validated"]["dataset_path"])
    items = read_json(path)
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ConfigError(f"SearchQA item {index} is not an object")
        missing = [field for field in ("id", "question", "context", "answers") if field not in item]
        if missing:
            raise ConfigError(f"SearchQA item {index} missing fields: {', '.join(missing)}")
        item_id = str(item["id"])
        if item_id in seen:
            raise ConfigError(f"duplicate SearchQA item ID: {item_id}")
        answers = item["answers"]
        if not isinstance(answers, list) or not answers or not all(
            isinstance(answer, str) and answer.strip() for answer in answers
        ):
            raise ConfigError(f"SearchQA item {item_id} has invalid answers")
        seen.add(item_id)
        normalized.append(
            {
                "id": item_id,
                "question": str(item["question"]),
                "context": str(item["context"]),
                "answers": list(answers),
            }
        )
    return normalized


def build_replicate_manifest(config: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
    dataset = config["dataset"]
    available = {str(item["id"]) for item in items}
    count = int(dataset["items_per_replicate"])
    probe_count = int(dataset["guard_probe_items_per_replicate"])
    replicates = []
    for seed in dataset["replicate_seeds"]:
        ranked = sorted(
            available,
            key=lambda item_id: (
                sha256_bytes(f"{seed}:{item_id}".encode("utf-8")),
                item_id,
            ),
        )
        selected = ranked[:count]
        if len(selected) != count:
            raise ConfigError("not enough unused SearchQA items for disjoint replicate manifests")
        available.difference_update(selected)
        replicates.append(
            {
                "seed": int(seed),
                "probe_ids": selected[:probe_count],
                "evaluation_ids": selected[probe_count:],
            }
        )

    payload = {
        "schema_version": 2,
        "config_sha256": config["_validated"]["config_sha256"],
        "dataset_sha256": config["dataset"]["items_sha256"],
        "selection": config["dataset"]["selection"],
        "seed_semantics": config["dataset"]["seed_semantics"],
        "replicates": replicates,
    }
    payload["manifest_fingerprint"] = object_fingerprint(payload)
    return payload


def _call_identity_payload(
    config_fingerprint: str,
    manifest_fingerprint: str,
    *,
    seed: int,
    method: str,
    stage: str,
    branch: str,
    item_id: str,
) -> dict[str, Any]:
    return {
        "config_fingerprint": config_fingerprint,
        "manifest_fingerprint": manifest_fingerprint,
        "seed": int(seed),
        "method": method,
        "stage": stage,
        "branch": branch,
        "item_id": item_id,
    }


def build_call_plan(config: dict[str, Any], manifest: dict[str, Any]) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    config_fingerprint = config["_validated"]["config_sha256"]
    manifest_fingerprint = manifest["manifest_fingerprint"]

    def add_call(
        *,
        seed: int,
        method: dict[str, Any],
        stage: str,
        branch: str,
        item_id: str,
    ) -> None:
        identity = _call_identity_payload(
            config_fingerprint,
            manifest_fingerprint,
            seed=seed,
            method=str(method["name"]),
            stage=stage,
            branch=branch,
            item_id=item_id,
        )
        plan.append(
            {
                **identity,
                "run_id": "phase1b-" + object_fingerprint(identity),
                "fallback": "cold" in branch,
                "requested_skill_policy": method["skill_policy"],
            }
        )

    for replicate in manifest["replicates"]:
        seed = int(replicate["seed"])
        # Guard evidence is paid and persisted before any guarded evaluation.
        for method in config["methods"]:
            branches = method.get("guard_probe_branches", [])
            for item_id in replicate["probe_ids"]:
                for branch in branches:
                    add_call(
                        seed=seed,
                        method=method,
                        stage="guard_probe",
                        branch=str(branch),
                        item_id=str(item_id),
                    )
        for method in config["methods"]:
            for item_id in replicate["evaluation_ids"]:
                add_call(
                    seed=seed,
                    method=method,
                    stage="evaluation",
                    branch="primary",
                    item_id=str(item_id),
                )
    run_ids = [call["run_id"] for call in plan]
    if len(run_ids) != len(set(run_ids)):
        raise ConfigError("deterministic call plan contains duplicate run IDs")
    if len(plan) != int(config["planned_workload"]["total_logical_calls"]):
        raise ConfigError("call plan length does not match frozen workload")
    for seed in config["dataset"]["replicate_seeds"]:
        first_eval = next(
            index
            for index, call in enumerate(plan)
            if call["seed"] == seed and call["stage"] == "evaluation"
        )
        probes_before = sum(
            call["seed"] == seed and call["stage"] == "guard_probe"
            for call in plan[:first_eval]
        )
        if probes_before != 32:
            raise ConfigError("all 32 replicate guard probes must precede evaluation")
    return plan


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()


def _portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def _artifact_manifest(
    config: dict[str, Any],
    replicate_manifest: dict[str, Any],
    plan: list[dict[str, Any]],
    mode: str,
) -> dict[str, Any]:
    plan_identity = [
        {
            key: call[key]
            for key in ("run_id", "seed", "method", "stage", "branch", "item_id", "fallback")
        }
        for call in plan
    ]
    return {
        "artifact_schema_version": 2,
        "experiment": config["experiment"],
        "mode": mode,
        "config_path": config["_validated"]["config_path"],
        "config_fingerprint": config["_validated"]["config_sha256"],
        "dataset_fingerprint": config["dataset"]["items_sha256"],
        "skill_fingerprint": config["skill"]["sha256"],
        "rule_set_fingerprint": config["skill"]["rule_set_fingerprint"],
        "frozen_candidate_source_fingerprint": config["frozen_candidate_source"]["config_sha256"],
        "source_fingerprints": {
            name: spec["sha256"] for name, spec in config["source_fingerprints"].items()
        },
        "provider_contract_fingerprint": object_fingerprint(
            {
                "execution": config["execution"],
                "model": config["model"],
                "pricing_snapshot": config["pricing_snapshot"],
            }
        ),
        "replicate_manifest": replicate_manifest,
        "manifest_fingerprint": replicate_manifest["manifest_fingerprint"],
        "plan_fingerprint": object_fingerprint(plan_identity),
        "expected_logical_calls": len(plan),
        "expected_fallback_calls": sum(1 for call in plan if call["fallback"]),
        "paid_calls_expected": len(plan) if mode == "live" else 0,
    }


def initialize_artifact(
    output_dir: Path,
    config: dict[str, Any],
    replicate_manifest: dict[str, Any],
    plan: list[dict[str, Any]],
    mode: str,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "calls.jsonl").touch(exist_ok=True)
    (output_dir / "attempts.jsonl").touch(exist_ok=True)
    manifest_path = output_dir / "run_manifest.json"
    expected = _artifact_manifest(config, replicate_manifest, plan, mode)
    if manifest_path.exists():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ResumeError(f"run manifest is invalid JSON: {exc}") from exc
        for field in (
            "mode",
            "config_fingerprint",
            "dataset_fingerprint",
            "skill_fingerprint",
            "rule_set_fingerprint",
            "frozen_candidate_source_fingerprint",
            "source_fingerprints",
            "provider_contract_fingerprint",
            "manifest_fingerprint",
            "plan_fingerprint",
            "expected_logical_calls",
            "expected_fallback_calls",
        ):
            if existing.get(field) != expected.get(field):
                raise ResumeError(
                    f"run manifest {field} mismatch: "
                    f"existing={existing.get(field)!r}, expected={expected.get(field)!r}"
                )
        return existing
    _atomic_write_json(manifest_path, expected)
    return expected


def finalize_artifact_manifest(
    output_dir: Path,
    artifact_manifest: dict[str, Any],
    config: dict[str, Any],
    summary: dict[str, Any],
) -> dict[str, Any]:
    """Write a deterministic completed-phase-compatible artifact manifest."""
    complete = summary["status"] == "completed"
    summary_path = output_dir / "summary.json"
    calls_path = output_dir / "calls.jsonl"
    attempts_path = output_dir / "attempts.jsonl"
    finalized = {
        **artifact_manifest,
        "config_path": _portable_path(Path(config["_validated"]["config_path"])),
        "config_sha256": config["_validated"]["config_sha256"],
        "expected_runs": 1,
        "available_runs": 1 if complete else 0,
        "complete_grid": complete,
        "aggregate_fingerprint": summary["summary_fingerprint"] if complete else "",
        "calls_path": _portable_path(calls_path),
        "calls_file_sha256": sha256_file(calls_path),
        "attempts_path": _portable_path(attempts_path),
        "attempts_file_sha256": sha256_file(attempts_path),
        "summary_path": _portable_path(summary_path),
        "summary_file_sha256": sha256_file(summary_path),
        "runs": (
            [
                {
                    "run_id": f"phase1b-searchqa-live-pilot-v2-{summary['mode']}",
                    "result_path": _portable_path(summary_path),
                    "file_sha256": sha256_file(summary_path),
                }
            ]
            if complete
            else []
        ),
    }
    _atomic_write_json(output_dir / "run_manifest.json", finalized)
    return finalized


def _empty_ledger() -> dict[str, int]:
    return {
        "logical_calls": 0,
        "provider_attempts": 0,
        "successful_attempts": 0,
        "failed_attempts": 0,
        "retries": 0,
        "fallback_calls": 0,
        "paid_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "input_cost_pico_cny": 0,
        "output_cost_pico_cny": 0,
        "cost_pico_cny": 0,
        "input_cost_pico_usd": 0,
        "output_cost_pico_usd": 0,
        "cost_pico_usd": 0,
    }


def validate_call_record(record: dict[str, Any]) -> None:
    attempts = record.get("attempts")
    if not isinstance(attempts, list) or not attempts:
        raise ResumeError(f"run {record.get('run_id')} has no attempts")
    successful = sum(1 for attempt in attempts if attempt.get("status") == "success")
    failed = sum(1 for attempt in attempts if attempt.get("status") == "failed")
    if successful != 1 or successful + failed != len(attempts):
        raise ResumeError(f"run {record.get('run_id')} has invalid attempt statuses")
    for attempt in attempts:
        if int(attempt["total_tokens"]) != int(attempt["input_tokens"]) + int(
            attempt["output_tokens"]
        ):
            raise ResumeError(f"run {record.get('run_id')} violates attempt token identity")
        if int(attempt["cost_pico_cny"]) != int(attempt["input_cost_pico_cny"]) + int(
            attempt["output_cost_pico_cny"]
        ):
            raise ResumeError(f"run {record.get('run_id')} violates CNY cost identity")
        if int(attempt["cost_pico_usd"]) != int(attempt["input_cost_pico_usd"]) + int(
            attempt["output_cost_pico_usd"]
        ):
            raise ResumeError(f"run {record.get('run_id')} violates USD cost identity")

    sums = {
        field: sum(int(attempt[field]) for attempt in attempts)
        for field in (
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "input_cost_pico_cny",
            "output_cost_pico_cny",
            "cost_pico_cny",
            "input_cost_pico_usd",
            "output_cost_pico_usd",
            "cost_pico_usd",
        )
    }
    for field, expected in sums.items():
        if int(record[field]) != expected:
            raise ResumeError(
                f"run {record.get('run_id')} cumulative {field} mismatch: "
                f"record={record[field]}, attempts={expected}"
            )
    if int(record["provider_attempts"]) != len(attempts):
        raise ResumeError(f"run {record.get('run_id')} provider-attempt mismatch")
    if int(record["failed_attempts"]) != failed:
        raise ResumeError(f"run {record.get('run_id')} failed-attempt mismatch")
    if int(record["retry_count"]) != len(attempts) - 1:
        raise ResumeError(f"run {record.get('run_id')} retry identity mismatch")
    if record.get("parse_status") != "valid":
        raise ResumeError(f"completed run {record.get('run_id')} is not strictly parseable")


def load_completed_records(
    output_dir: Path,
    *,
    artifact_manifest: dict[str, Any],
    plan_by_id: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    path = output_dir / "calls.jsonl"
    if not path.exists():
        return {}
    completed: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            if not raw.strip():
                raise ResumeError(f"blank JSONL line at {path}:{line_number}")
            try:
                record = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ResumeError(f"bad JSONL at {path}:{line_number}: {exc}") from exc
            run_id = str(record.get("run_id", ""))
            if not run_id:
                raise ResumeError(f"missing run_id at {path}:{line_number}")
            if run_id in completed:
                raise ResumeError(f"duplicate run_id in resume JSONL: {run_id}")
            if run_id not in plan_by_id:
                raise ResumeError(f"resume JSONL contains unknown run_id: {run_id}")
            if record.get("config_fingerprint") != artifact_manifest["config_fingerprint"]:
                raise ResumeError(f"config fingerprint mismatch for resumed run {run_id}")
            if record.get("manifest_fingerprint") != artifact_manifest["manifest_fingerprint"]:
                raise ResumeError(f"manifest fingerprint mismatch for resumed run {run_id}")
            expected_call_fingerprint = object_fingerprint(plan_by_id[run_id])
            if record.get("call_fingerprint") != expected_call_fingerprint:
                raise ResumeError(f"call fingerprint mismatch for resumed run {run_id}")
            validate_call_record(record)
            completed[run_id] = record
    return completed


def load_attempt_records(
    output_dir: Path,
    *,
    artifact_manifest: dict[str, Any],
    plan_by_id: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    path = output_dir / "attempts.jsonl"
    if not path.exists():
        return {}
    grouped: dict[str, list[dict[str, Any]]] = {}
    seen: set[tuple[str, int]] = set()
    with path.open(encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, start=1):
            if not raw.strip():
                raise ResumeError(f"blank JSONL line at {path}:{line_number}")
            try:
                attempt = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ResumeError(f"bad attempts JSONL at {path}:{line_number}: {exc}") from exc
            run_id = str(attempt.get("run_id", ""))
            attempt_index = int(attempt.get("attempt_index", 0))
            key = (run_id, attempt_index)
            if run_id not in plan_by_id:
                raise ResumeError(f"attempt journal contains unknown run_id: {run_id}")
            if key in seen:
                raise ResumeError(f"duplicate attempt journal key: {key}")
            if attempt.get("config_fingerprint") != artifact_manifest["config_fingerprint"]:
                raise ResumeError(f"attempt config fingerprint mismatch for {run_id}")
            if attempt.get("manifest_fingerprint") != artifact_manifest["manifest_fingerprint"]:
                raise ResumeError(f"attempt manifest fingerprint mismatch for {run_id}")
            if attempt.get("status") not in {"success", "failed"}:
                raise ResumeError(f"invalid attempt status for {run_id}")
            if int(attempt["total_tokens"]) != int(attempt["input_tokens"]) + int(
                attempt["output_tokens"]
            ):
                raise ResumeError(f"attempt token identity mismatch for {run_id}")
            if int(attempt["cost_pico_cny"]) != int(
                attempt["input_cost_pico_cny"]
            ) + int(attempt["output_cost_pico_cny"]):
                raise ResumeError(f"attempt CNY cost identity mismatch for {run_id}")
            if int(attempt["cost_pico_usd"]) != int(
                attempt["input_cost_pico_usd"]
            ) + int(attempt["output_cost_pico_usd"]):
                raise ResumeError(f"attempt USD cost identity mismatch for {run_id}")
            if not isinstance(attempt.get("usage_known"), bool):
                raise ResumeError(f"attempt usage_known is missing for {run_id}")
            seen.add(key)
            grouped.setdefault(run_id, []).append(attempt)
    for run_id, attempts in grouped.items():
        attempts.sort(key=lambda row: int(row["attempt_index"]))
        indices = [int(row["attempt_index"]) for row in attempts]
        if indices != list(range(1, len(attempts) + 1)):
            raise ResumeError(f"non-contiguous attempts for {run_id}: {indices}")
        if sum(row["status"] == "success" for row in attempts) > 1:
            raise ResumeError(f"multiple successful attempts for {run_id}")
        if any(row["status"] == "success" for row in attempts[:-1]):
            raise ResumeError(f"successful attempt is not terminal for {run_id}")
    return grouped


def ledger_from_records(records: Iterable[dict[str, Any]]) -> dict[str, int]:
    ledger = _empty_ledger()
    for record in records:
        validate_call_record(record)
        ledger["logical_calls"] += 1
        ledger["provider_attempts"] += int(record["provider_attempts"])
        ledger["successful_attempts"] += 1
        ledger["failed_attempts"] += int(record["failed_attempts"])
        ledger["retries"] += int(record["retry_count"])
        ledger["fallback_calls"] += int(bool(record["fallback"]))
        for field in (
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "input_cost_pico_cny",
            "output_cost_pico_cny",
            "cost_pico_cny",
            "input_cost_pico_usd",
            "output_cost_pico_usd",
            "cost_pico_usd",
        ):
            ledger[field] += int(record[field])
    return ledger


def ledger_from_attempts(
    attempts_by_id: dict[str, list[dict[str, Any]]],
    completed: Iterable[dict[str, Any]],
) -> dict[str, int]:
    completed_rows = list(completed)
    ledger = _empty_ledger()
    ledger["logical_calls"] = len(completed_rows)
    ledger["fallback_calls"] = sum(bool(record["fallback"]) for record in completed_rows)
    ledger["paid_calls"] = sum(bool(record["paid_call"]) for record in completed_rows)
    for attempts in attempts_by_id.values():
        for attempt in attempts:
            ledger["provider_attempts"] += 1
            ledger["successful_attempts"] += int(attempt["status"] == "success")
            ledger["failed_attempts"] += int(attempt["status"] == "failed")
            for field in (
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "input_cost_pico_cny",
                "output_cost_pico_cny",
                "cost_pico_cny",
                "input_cost_pico_usd",
                "output_cost_pico_usd",
                "cost_pico_usd",
            ):
                ledger[field] += int(attempt[field])
    ledger["retries"] = ledger["provider_attempts"] - ledger["logical_calls"]
    return ledger


def _assert_ledger_identities(ledger: dict[str, int]) -> None:
    if ledger["provider_attempts"] != ledger["successful_attempts"] + ledger["failed_attempts"]:
        raise PreflightError("provider attempts != successful + failed attempts")
    if ledger["retries"] != ledger["provider_attempts"] - ledger["logical_calls"]:
        raise PreflightError("retries != provider attempts - logical calls")
    if ledger["logical_calls"] > ledger["successful_attempts"]:
        raise PreflightError("logical calls exceed successful provider attempts")
    if ledger["total_tokens"] != ledger["input_tokens"] + ledger["output_tokens"]:
        raise PreflightError("total tokens != input + output tokens")
    if ledger["cost_pico_cny"] != ledger["input_cost_pico_cny"] + ledger["output_cost_pico_cny"]:
        raise PreflightError("CNY cost != input + output cost")
    if ledger["cost_pico_usd"] != ledger["input_cost_pico_usd"] + ledger["output_cost_pico_usd"]:
        raise PreflightError("USD cost != input + output cost")


def _cost_display(pico_value: int) -> str:
    return format(Decimal(pico_value) / Decimal(PICO_PER_UNIT), "f")


@dataclass
class MockAttempt:
    status: str
    response: str
    input_tokens: int
    output_tokens: int
    error: str = ""


@dataclass
class LiveAttempt:
    status: str
    response: str
    input_tokens: int
    output_tokens: int
    error: str = ""
    usage_known: bool = True
    reasoning_content: str = ""
    request_id: str = ""


class DashScopePaygProvider:
    """Explicit adapter for the Beijing DashScope OpenAI-compatible PAYG API.

    This class is deliberately isolated from the experiment permission gate.
    Callers must enforce the repository/config permission and hard caps before
    invoking it; the adapter itself performs exactly one provider request.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        max_output_tokens: int,
        timeout_seconds: float = 30.0,
        client: Any | None = None,
    ) -> None:
        if not api_key:
            raise ProviderUsageError("provider API key is empty")
        if not base_url:
            raise ProviderUsageError("provider base URL is empty")
        self.model = model
        self.max_output_tokens = int(max_output_tokens)
        self.invocations = 0
        self.client = client or OpenAI(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            max_retries=0,
        )

    @staticmethod
    def _usage(response: Any) -> tuple[int, int]:
        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", None)
        output_tokens = getattr(usage, "completion_tokens", None)
        total_tokens = getattr(usage, "total_tokens", None)
        if input_tokens is None or output_tokens is None or total_tokens is None:
            raise ProviderUsageError("provider response omitted complete usage metadata")
        input_tokens = int(input_tokens)
        output_tokens = int(output_tokens)
        total_tokens = int(total_tokens)
        if min(input_tokens, output_tokens, total_tokens) < 0:
            raise ProviderUsageError("provider usage contains negative token counts")
        if total_tokens != input_tokens + output_tokens:
            raise ProviderUsageError(
                "provider usage identity failed: total != prompt + completion"
            )
        return input_tokens, output_tokens

    def invoke(
        self,
        messages: list[dict[str, Any]],
        *,
        max_output_tokens: int | None = None,
    ) -> LiveAttempt:
        self.invocations += 1
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=int(max_output_tokens or self.max_output_tokens),
                temperature=0,
                extra_body={"enable_thinking": False},
            )
            choices = getattr(response, "choices", None) or []
            if not choices:
                raise ProviderUsageError("provider response returned no choices")
            input_tokens, output_tokens = self._usage(response)
            message = getattr(choices[0], "message", None)
            text = getattr(message, "content", None)
            if not text:
                raise StrictAnswerError("provider response contained empty content")
            return LiveAttempt(
                status="success",
                response=str(text),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                reasoning_content=str(getattr(message, "reasoning_content", "") or ""),
                request_id=str(getattr(response, "id", "") or ""),
            )
        except Exception as exc:  # noqa: BLE001 - preserve provider failure provenance
            return LiveAttempt(
                status="failed",
                response="",
                input_tokens=0,
                output_tokens=0,
                error=f"{type(exc).__name__}: {exc}",
                usage_known=False,
            )


class TokenPlanProvider(DashScopePaygProvider):
    """Compatibility alias for older no-network unit tests."""


class DeterministicMockProvider:
    """No-network provider used by the complete Phase 1B preflight."""

    def __init__(self) -> None:
        self.invocations = 0

    @staticmethod
    def should_retry(run_id: str) -> bool:
        digest = run_id.split("-", 1)[-1]
        return int(digest[:8], 16) % 17 == 0

    def preview(
        self,
        *,
        run_id: str,
        item: dict[str, Any],
        input_tokens: int,
        attempt_index: int,
    ) -> MockAttempt:
        answer = str(item["answers"][0]).strip()
        response = f"<answer>{answer}</answer>"
        output_tokens = max(1, (len(response) + 3) // 4)
        if attempt_index == 1 and self.should_retry(run_id):
            return MockAttempt(
                status="failed",
                response="",
                input_tokens=input_tokens,
                output_tokens=min(7, output_tokens),
                error="deterministic_mock_transient_error",
            )
        return MockAttempt(
            status="success",
            response=response,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def invoke(self, prepared: MockAttempt) -> MockAttempt:
        self.invocations += 1
        return prepared


def build_selectors(config: dict[str, Any], skill_text: str) -> dict[str, Any]:
    """Build the frozen retrieval implementations once per invocation."""
    from skillopt.rag_rule_selector import RuleMemory

    retrieval = config["retrieval"]
    common = {
        "top_k": int(retrieval["top_k"]),
        "token_budget": int(retrieval["cumulative_skill_token_budget"]),
    }
    tfidf = RuleMemory(skill_text, method="tfidf", **common)
    # MOAR's library-level diagnostic print must not corrupt CLI JSON output.
    with contextlib.redirect_stdout(io.StringIO()):
        moar = RuleMemory(
            skill_text,
            method="moar",
            moar_pop_size=int(retrieval["moar"]["pop_size"]),
            moar_generations=int(retrieval["moar"]["generations"]),
            moar_crossover_p=float(retrieval["moar"]["crossover_p"]),
            moar_mutation_p=float(retrieval["moar"]["mutation_p"]),
            moar_weights=str(retrieval["moar"]["weights"]),
            moar_selection_mode=str(retrieval["moar"]["selection_mode"]),
            moar_utility_method=str(retrieval["moar"]["utility_method"]),
            moar_utility_decay=float(retrieval["moar"]["utility_decay"]),
            moar_tokenizer=str(retrieval["moar"]["tokenizer"]),
            moar_frozen=True,
            moar_base_seed=int(retrieval["moar"]["base_seed"]),
            **common,
        )
    return {"tfidf": tfidf, "moar": moar}


def _selection_metadata(selector: Any, question: str) -> tuple[list[int], list[str]]:
    indices = [int(index) for index in selector._last_selections.get(question, [])]
    return indices, selector.rule_ids_for_indices(indices)


def _guard_history(
    config: dict[str, Any],
    *,
    seed: int,
    method_name: str,
    completed: dict[str, dict[str, Any]],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate the frozen paired candidate-minus-cold guard."""
    replicate = next(row for row in manifest["replicates"] if int(row["seed"]) == seed)
    method = next(row for row in config["methods"] if row["name"] == method_name)
    branches = list(method["guard_probe_branches"])
    cold_branch = next(branch for branch in branches if "cold" in branch)
    by_key = {
        (record["item_id"], record["branch"]): record
        for record in completed.values()
        if int(record["seed"]) == seed
        and record["method"] == method_name
        and record["stage"] == "guard_probe"
    }
    guard = config["guard"]
    metric = str(guard["score_metric"])
    boundary = float(guard["decision_boundary"])
    z = float(guard["confidence_z"])
    differences: list[float] = []
    margins: list[float] = []
    round_history: list[dict[str, Any]] = []
    first_decisive_round: int | None = None
    first_decision = "ambiguous"

    for round_index, item_id in enumerate(replicate["probe_ids"], start=1):
        candidate = by_key.get((item_id, "candidate"))
        cold = by_key.get((item_id, cold_branch))
        if candidate is None or cold is None:
            raise PreflightError(
                f"incomplete guard probes for seed={seed}, method={method_name}, item={item_id}"
            )
        difference = float(candidate[metric]) - float(cold[metric])
        differences.append(difference)
        mean = sum(differences) / len(differences)
        if len(differences) > 1:
            variance = sum((value - mean) ** 2 for value in differences) / (
                len(differences) - 1
            )
            standard_error = math.sqrt(variance) / math.sqrt(len(differences))
        else:
            standard_error = float("inf")
        lower = mean - z * standard_error
        upper = mean + z * standard_error
        margins.append(mean)
        window = int(guard["recovery_window"])
        recovery_slope = None
        if window > 1 and len(margins) >= window:
            recent = margins[-window:]
            if window == 2:
                recovery_slope = recent[-1] - recent[0]
            else:
                center = (window - 1) / 2
                recovery_slope = sum(
                    (index - center) * value for index, value in enumerate(recent)
                ) / sum((index - center) ** 2 for index in range(window))
        acceptable = (
            len(differences) >= int(guard["min_samples"])
            and round_index >= int(guard["min_accept_rounds"])
            and lower >= boundary
        )
        harmful = (
            len(differences) >= int(guard["min_samples"])
            and round_index >= int(guard["min_reset_rounds"])
            and upper < boundary
            and mean <= boundary - float(guard["min_harm_margin"])
            and (
                window <= 1
                or (
                    recovery_slope is not None
                    and recovery_slope <= float(guard["max_recovery_slope"])
                )
            )
        )
        decision = "acceptable" if acceptable else "harmful" if harmful else "ambiguous"
        if first_decisive_round is None and decision != "ambiguous":
            first_decisive_round = round_index
            first_decision = decision
        round_history.append(
            {
                "round": round_index,
                "item_id": item_id,
                "candidate_run_id": candidate["run_id"],
                "cold_run_id": cold["run_id"],
                "candidate_score": float(candidate[metric]),
                "cold_score": float(cold[metric]),
                "paired_difference": difference,
                "mean_difference": mean,
                "standard_error": standard_error,
                "confidence_lower": lower,
                "confidence_upper": upper,
                "decision_boundary": boundary,
                "recovery_slope": recovery_slope,
                "decision": decision,
            }
        )

    final_decision = str(round_history[-1]["decision"])
    candidate_mean = sum(row["candidate_score"] for row in round_history) / len(round_history)
    cold_mean = sum(row["cold_score"] for row in round_history) / len(round_history)
    reset_triggered = candidate_mean < cold_mean - float(guard["tolerance"])
    if method["guard_action"] == "reset-cold":
        effective_policy = "none" if reset_triggered else "tfidf"
        action = "reset-cold" if reset_triggered else "none"
        triggered = reset_triggered
        state_mutated = reset_triggered
    else:
        effective_policy = "tfidf" if final_decision == "acceptable" else "none"
        action = (
            "none"
            if final_decision == "acceptable"
            else "reject-fallback-cold"
            if final_decision == "harmful"
            else "abstain-fallback-cold"
        )
        triggered = final_decision != "acceptable"
        state_mutated = False
    history = {
        "mode": method["guard_action"],
        "score_metric": metric,
        "decision": final_decision,
        "triggered": triggered,
        "action": action,
        "effective_skill_policy": effective_policy,
        "candidate_state_mutated": state_mutated,
        "candidate_mean": candidate_mean,
        "cold_mean": cold_mean,
        "margin": candidate_mean - cold_mean,
        "decision_boundary": boundary,
        "rounds_used": len(round_history),
        "first_decisive_round": first_decisive_round,
        "first_decision": first_decision,
        "stop_reason": (
            f"confident-{final_decision}"
            if final_decision != "ambiguous"
            else "max-probes"
        ),
        "round_history": round_history,
    }
    history["guard_fingerprint"] = object_fingerprint(history)
    return history


def prepare_call(
    config: dict[str, Any],
    call: dict[str, Any],
    item: dict[str, Any],
    skill_text: str,
    selectors: dict[str, Any],
    completed: dict[str, dict[str, Any]],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Render the exact messages used by both dry-run and live execution."""
    from skillopt.envs.searchqa.rollout import _build_active_skill, _build_system, _build_user

    method = next(row for row in config["methods"] if row["name"] == call["method"])
    guard_provenance = None
    if call["stage"] == "guard_probe":
        effective_policy = "none" if "cold" in call["branch"] else "tfidf"
    elif method.get("guard_probe_branches"):
        guard_provenance = _guard_history(
            config,
            seed=int(call["seed"]),
            method_name=str(call["method"]),
            completed=completed,
            manifest=manifest,
        )
        effective_policy = str(guard_provenance["effective_skill_policy"])
    else:
        effective_policy = str(method["skill_policy"])

    if effective_policy == "none":
        active_skill = ""
        selected_indices: list[int] = []
        selected_rule_ids: list[str] = []
    elif effective_policy == "full_skill":
        active_skill = skill_text
        selected_indices = []
        selected_rule_ids = []
    elif effective_policy in selectors:
        selector = selectors[effective_policy]
        active_skill = _build_active_skill(skill_text, item["question"], selector)
        selected_indices, selected_rule_ids = _selection_metadata(selector, item["question"])
    else:
        raise ConfigError(f"unsupported effective skill policy: {effective_policy}")

    system = _build_system(active_skill) + (
        "\n\n## Output-Only Override\n"
        "Return exactly one non-empty <answer>...</answer> element and nothing else. "
        "Do not expose analysis, reasoning, citations, or preamble. The first output "
        "character must be '<' and the final output characters must be '</answer>'."
    )
    user = _build_user(item["question"], item["context"])
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    return {
        "messages": messages,
        "prompt_fingerprint": object_fingerprint(messages),
        "system_prompt_sha256": sha256_bytes(system.encode("utf-8")),
        "user_prompt_sha256": sha256_bytes(user.encode("utf-8")),
        "active_skill_sha256": sha256_bytes(active_skill.encode("utf-8")),
        "active_skill_chars": len(active_skill),
        "effective_skill_policy": effective_policy,
        "selected_rule_indices": selected_indices,
        "selected_rule_ids": selected_rule_ids,
        "guard_provenance": guard_provenance,
    }


def build_format_repair_messages(raw_response: str) -> list[dict[str, str]]:
    """Build the frozen repair prompt without question, context, or new evidence."""
    if not raw_response.strip():
        raise StrictAnswerError("format repair requires a non-empty source response")
    return [
        {
            "role": "system",
            "content": (
                "You are a deterministic answer-format normalizer. Extract the shortest "
                "candidate final answer already stated in SOURCE_OUTPUT. Return exactly "
                "one non-empty <answer>...</answer> element and nothing else. Do not add "
                "facts, explanations, citations, or reasoning."
            ),
        },
        {"role": "user", "content": f"SOURCE_OUTPUT:\n{raw_response}"},
    ]


def _estimate_input_tokens(
    config: dict[str, Any],
    call: dict[str, Any],
    item: dict[str, Any],
    skill_text: str,
) -> int:
    context = str(item["context"])[:6000]
    base_chars = len(str(item["question"])) + len(context) + 400
    policy = call.get("effective_skill_policy", call.get("requested_skill_policy", "none"))
    if policy == "none":
        skill_tokens = 0
    elif policy == "full_skill":
        skill_tokens = max(1, (len(skill_text) + 3) // 4)
    else:
        method = next(method for method in config["methods"] if method["name"] == call["method"])
        skill_tokens = int(method.get("cumulative_skill_token_budget", 2000))
    estimate = max(1, (base_chars + 3) // 4) + skill_tokens
    return min(int(config["model"]["max_input_tokens_per_attempt"]), estimate)


def _attempt_record(
    attempt_index: int,
    result: MockAttempt,
    units: dict[str, int],
) -> dict[str, Any]:
    input_tokens = int(result.input_tokens)
    output_tokens = int(result.output_tokens)
    input_cny = input_tokens * units["input_pico_cny_per_token"]
    output_cny = output_tokens * units["output_pico_cny_per_token"]
    input_usd = input_tokens * units["input_pico_usd_per_token"]
    output_usd = output_tokens * units["output_pico_usd_per_token"]
    return {
        "attempt_index": attempt_index,
        "status": result.status,
        "error": result.error,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "input_cost_pico_cny": input_cny,
        "output_cost_pico_cny": output_cny,
        "cost_pico_cny": input_cny + output_cny,
        "input_cost_pico_usd": input_usd,
        "output_cost_pico_usd": output_usd,
        "cost_pico_usd": input_usd + output_usd,
    }


def _check_attempt_budget(
    ledger: dict[str, int],
    config: dict[str, Any],
    attempt: dict[str, Any],
    *,
    will_fail: bool,
) -> None:
    caps = config["hard_caps"]
    projected = {
        "provider_attempts": ledger["provider_attempts"] + 1,
        "failed_attempts": ledger["failed_attempts"] + int(will_fail),
        "retries": max(
            0,
            ledger["provider_attempts"] + 1 - (ledger["logical_calls"] + 1),
        ),
        "input_tokens": ledger["input_tokens"] + int(attempt["input_tokens"]),
        "output_tokens": ledger["output_tokens"] + int(attempt["output_tokens"]),
        "total_tokens": ledger["total_tokens"] + int(attempt["total_tokens"]),
        "cost_pico_cny": ledger["cost_pico_cny"] + int(attempt["cost_pico_cny"]),
        "cost_pico_usd": ledger["cost_pico_usd"] + int(attempt["cost_pico_usd"]),
    }
    numeric_caps = {
        "provider_attempts": int(caps["provider_attempts"]),
        "failed_attempts": int(caps["failed_attempts"]),
        "retries": int(caps["retries"]),
        "input_tokens": int(caps["input_tokens"]),
        "output_tokens": int(caps["output_tokens"]),
        "total_tokens": int(caps["total_tokens"]),
        "cost_pico_cny": int(Decimal(str(caps["cost_cny"])) * PICO_PER_UNIT),
        "cost_pico_usd": int(
            Decimal(str(caps["cost_cny"]))
            / Decimal(str(config["pricing_snapshot"]["fixed_accounting_cny_per_usd"]))
            * PICO_PER_UNIT
        ),
    }
    for field, value in projected.items():
        if value > numeric_caps[field]:
            raise BudgetExceeded(
                f"{field} hard cap would be exceeded before provider invocation: "
                f"projected={value}, cap={numeric_caps[field]}"
            )


def _apply_attempt_to_ledger(
    ledger: dict[str, int], attempt: dict[str, Any], *, failed: bool
) -> None:
    ledger["provider_attempts"] += 1
    ledger["failed_attempts"] += int(failed)
    ledger["successful_attempts"] += int(not failed)
    for field in (
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "input_cost_pico_cny",
        "output_cost_pico_cny",
        "cost_pico_cny",
        "input_cost_pico_usd",
        "output_cost_pico_usd",
        "cost_pico_usd",
    ):
        ledger[field] += int(attempt[field])


def execute_mock_call(
    config: dict[str, Any],
    call: dict[str, Any],
    item: dict[str, Any],
    skill_text: str,
    ledger: dict[str, int],
    provider: DeterministicMockProvider,
    prepared: dict[str, Any] | None = None,
) -> dict[str, Any]:
    caps = config["hard_caps"]
    if ledger["logical_calls"] + 1 > int(caps["logical_calls"]):
        raise BudgetExceeded("logical-call hard cap would be exceeded before provider invocation")
    if call["fallback"] and ledger["fallback_calls"] + 1 > int(caps["fallback_calls"]):
        raise BudgetExceeded("fallback-call hard cap would be exceeded before provider invocation")

    units = config["_validated"]["pricing_units"]
    input_tokens = (
        max(
            1,
            (
                sum(
                    len(message["role"]) + len(message["content"]) + 8
                    for message in prepared["messages"]
                )
                + 3
            )
            // 4,
        )
        if prepared is not None
        else _estimate_input_tokens(config, call, item, skill_text)
    )
    attempts = []
    response = ""
    max_attempts = int(config["model"]["max_attempts_per_logical_call"])
    for attempt_index in range(1, max_attempts + 1):
        mock_preview = provider.preview(
            run_id=call["run_id"],
            item=item,
            input_tokens=input_tokens,
            attempt_index=attempt_index,
        )
        attempt = _attempt_record(attempt_index, mock_preview, units)
        _check_attempt_budget(
            ledger,
            config,
            attempt,
            will_fail=mock_preview.status == "failed",
        )
        result = provider.invoke(mock_preview)
        _apply_attempt_to_ledger(ledger, attempt, failed=result.status == "failed")
        attempts.append(attempt)
        if result.status == "success":
            response = result.response
            break
    else:
        raise PreflightError(f"mock logical call exhausted retries: {call['run_id']}")

    answer = strict_extract_answer(response)
    from skillopt.envs.searchqa.evaluator import exact_match, f1_score, sub_em

    record = {
        **call,
        "call_fingerprint": object_fingerprint(call),
        "status": "completed",
        "provider": "deterministic_no_network",
        "paid_call": False,
        "attempts": attempts,
        "provider_attempts": len(attempts),
        "failed_attempts": sum(1 for attempt in attempts if attempt["status"] == "failed"),
        "retry_count": len(attempts) - 1,
        "parse_status": "valid",
        "predicted_answer": answer,
        "gold_answers": item["answers"],
        "em": exact_match(answer, item["answers"]),
        "f1": f1_score(answer, item["answers"]),
        "sub_em": sub_em(answer, item["answers"]),
        "prompt_fingerprint": prepared["prompt_fingerprint"] if prepared else "",
        "system_prompt_sha256": prepared["system_prompt_sha256"] if prepared else "",
        "user_prompt_sha256": prepared["user_prompt_sha256"] if prepared else "",
        "active_skill_sha256": prepared["active_skill_sha256"] if prepared else "",
        "active_skill_chars": prepared["active_skill_chars"] if prepared else 0,
        "effective_skill_policy": (
            prepared["effective_skill_policy"]
            if prepared
            else call.get("requested_skill_policy", "none")
        ),
        "selected_rule_indices": prepared["selected_rule_indices"] if prepared else [],
        "selected_rule_ids": prepared["selected_rule_ids"] if prepared else [],
        "guard_provenance": prepared["guard_provenance"] if prepared else None,
        "thinking_disabled": True,
        "reasoning_content_present": False,
    }
    for field in (
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "input_cost_pico_cny",
        "output_cost_pico_cny",
        "cost_pico_cny",
        "input_cost_pico_usd",
        "output_cost_pico_usd",
        "cost_pico_usd",
    ):
        record[field] = sum(int(attempt[field]) for attempt in attempts)
    validate_call_record(record)
    ledger["logical_calls"] += 1
    ledger["retries"] += len(attempts) - 1
    ledger["fallback_calls"] += int(bool(call["fallback"]))
    _assert_ledger_identities(ledger)
    return record


def _conservative_attempt_reservation(
    config: dict[str, Any],
    attempt_type: str,
) -> dict[str, Any]:
    repair = config["formatting_repair"]
    is_repair = attempt_type == "format_repair"
    return _attempt_record(
        0,
        LiveAttempt(
            status="failed",
            response="",
            input_tokens=int(repair["repair_max_input_tokens"] if is_repair else config["model"]["max_input_tokens_per_attempt"]),
            output_tokens=int(repair["repair_max_output_tokens"] if is_repair else repair["primary_max_output_tokens"]),
            error="budget_reservation",
        ),
        config["_validated"]["pricing_units"],
    )


def _record_from_prepared_attempts(
    call: dict[str, Any],
    item: dict[str, Any],
    prepared: dict[str, Any],
    attempts: list[dict[str, Any]],
    *,
    mode: str,
) -> dict[str, Any]:
    from skillopt.envs.searchqa.evaluator import exact_match, f1_score, sub_em

    if not attempts or attempts[-1]["status"] != "success":
        raise PreflightError(f"logical call has no successful terminal attempt: {call['run_id']}")
    answer = strict_extract_answer(str(attempts[-1]["response"]))
    record = {
        **call,
        "call_fingerprint": object_fingerprint(call),
        "status": "completed",
        "provider": (
            "dashscope_beijing_token_plan" if mode == "live" else "deterministic_no_network"
        ),
        "paid_call": mode == "live",
        "attempts": attempts,
        "provider_attempts": len(attempts),
        "failed_attempts": sum(attempt["status"] == "failed" for attempt in attempts),
        "retry_count": len(attempts) - 1,
        "parse_status": "valid",
        "predicted_answer": answer,
        "gold_answers": item["answers"],
        "em": exact_match(answer, item["answers"]),
        "f1": f1_score(answer, item["answers"]),
        "sub_em": sub_em(answer, item["answers"]),
        "prompt_fingerprint": prepared["prompt_fingerprint"],
        "system_prompt_sha256": prepared["system_prompt_sha256"],
        "user_prompt_sha256": prepared["user_prompt_sha256"],
        "active_skill_sha256": prepared["active_skill_sha256"],
        "active_skill_chars": prepared["active_skill_chars"],
        "effective_skill_policy": prepared["effective_skill_policy"],
        "selected_rule_indices": prepared["selected_rule_indices"],
        "selected_rule_ids": prepared["selected_rule_ids"],
        "guard_provenance": prepared["guard_provenance"],
        "thinking_disabled": True,
        "reasoning_content_present": any(
            bool(attempt.get("reasoning_content_present")) for attempt in attempts
        ),
    }
    for field in (
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "input_cost_pico_cny",
        "output_cost_pico_cny",
        "cost_pico_cny",
        "input_cost_pico_usd",
        "output_cost_pico_usd",
        "cost_pico_usd",
    ):
        record[field] = sum(int(attempt[field]) for attempt in attempts)
    validate_call_record(record)
    return record


def execute_prepared_call(
    config: dict[str, Any],
    call: dict[str, Any],
    item: dict[str, Any],
    prepared: dict[str, Any],
    ledger: dict[str, int],
    provider: Any,
    output_dir: Path,
    existing_attempts: list[dict[str, Any]],
    *,
    mode: str,
) -> dict[str, Any]:
    """Execute or resume one primary inference plus one bounded repair/retry."""
    attempts = existing_attempts
    if attempts and attempts[-1]["status"] == "success":
        return _record_from_prepared_attempts(call, item, prepared, attempts, mode=mode)
    max_attempts = int(config["model"]["max_attempts_per_logical_call"])
    if len(attempts) >= max_attempts:
        raise PreflightError(f"logical call exhausted retries: {call['run_id']}")

    repair_config = config["formatting_repair"]
    for attempt_index in range(len(attempts) + 1, max_attempts + 1):
        prior = attempts[-1] if attempts else None
        use_repair = bool(
            prior
            and prior.get("status") == "failed"
            and str(prior.get("response", "")).strip()
            and str(prior.get("error", "")).startswith("StrictAnswerError:")
        )
        attempt_type = "format_repair" if use_repair else (
            "primary" if attempt_index == 1 else "primary_retry"
        )
        messages = (
            build_format_repair_messages(str(prior["response"]))
            if use_repair
            else prepared["messages"]
        )
        max_output_tokens = int(
            repair_config["repair_max_output_tokens"]
            if use_repair
            else repair_config["primary_max_output_tokens"]
        )
        max_input_tokens = int(
            repair_config["repair_max_input_tokens"]
            if use_repair
            else config["model"]["max_input_tokens_per_attempt"]
        )
        if ledger["logical_calls"] + 1 > int(config["hard_caps"]["logical_calls"]):
            raise BudgetExceeded("logical-call cap would be exceeded before provider invocation")
        if call["fallback"] and ledger["fallback_calls"] + 1 > int(
            config["hard_caps"]["fallback_calls"]
        ):
            raise BudgetExceeded("fallback-call cap would be exceeded before provider invocation")
        reservation = _conservative_attempt_reservation(config, attempt_type)
        _check_attempt_budget(ledger, config, reservation, will_fail=True)
        if mode == "live":
            result = provider.invoke(messages, max_output_tokens=max_output_tokens)
        else:
            input_tokens = max(
                1,
                (sum(len(m["role"]) + len(m["content"]) + 8 for m in messages) + 3) // 4,
            )
            mock_attempt = provider.preview(
                run_id=call["run_id"],
                item=item,
                input_tokens=input_tokens,
                attempt_index=attempt_index,
            )
            result = provider.invoke(mock_attempt)
        if result.status == "success":
            try:
                strict_extract_answer(result.response)
            except StrictAnswerError as exc:
                result.status = "failed"
                result.error = f"StrictAnswerError: {exc}"
        attempt = _attempt_record(
            attempt_index,
            result,
            config["_validated"]["pricing_units"],
        )
        attempt.update(
            {
                "attempt_type": attempt_type,
                "messages_fingerprint": object_fingerprint(messages),
                "max_output_tokens": max_output_tokens,
                "config_fingerprint": call["config_fingerprint"],
                "manifest_fingerprint": call["manifest_fingerprint"],
                "run_id": call["run_id"],
                "response": result.response,
                "usage_known": bool(getattr(result, "usage_known", True)),
                "reasoning_content": str(getattr(result, "reasoning_content", "") or ""),
                "reasoning_content_present": bool(
                    str(getattr(result, "reasoning_content", "") or "").strip()
                ),
                "request_id": str(getattr(result, "request_id", "") or ""),
            }
        )
        _append_jsonl(output_dir / "attempts.jsonl", attempt)
        attempts.append(attempt)
        _apply_attempt_to_ledger(ledger, attempt, failed=attempt["status"] == "failed")
        ledger["retries"] = ledger["provider_attempts"] - ledger["logical_calls"]
        if int(attempt["input_tokens"]) > max_input_tokens or int(
            attempt["output_tokens"]
        ) > max_output_tokens:
            raise ProviderUsageError(
                "provider usage exceeded the frozen per-attempt token envelope; "
                "attempt is journaled and further paid execution is refused"
            )
        if not attempt["usage_known"]:
            raise ProviderUsageError(
                "provider failure omitted usage metadata; attempt is journaled and "
                "further paid execution is refused"
            )
        if attempt["status"] == "success":
            return _record_from_prepared_attempts(call, item, prepared, attempts, mode=mode)
    raise PreflightError(f"logical call exhausted retries: {call['run_id']}")


def _method_metrics(records: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        if record["stage"] != "evaluation":
            continue
        grouped.setdefault(record["method"], []).append(record)
    result: dict[str, dict[str, Any]] = {}
    for method, rows in sorted(grouped.items()):
        n = len(rows)
        result[method] = {
            "n": n,
            "format_valid": sum(row["parse_status"] == "valid" for row in rows),
            "em": sum(float(row["em"]) for row in rows) / n if n else 0.0,
            "f1": sum(float(row["f1"]) for row in rows) / n if n else 0.0,
            "sub_em": sum(float(row["sub_em"]) for row in rows) / n if n else 0.0,
            "total_tokens": sum(int(row["total_tokens"]) for row in rows),
            "cost_cny": _cost_display(sum(int(row["cost_pico_cny"]) for row in rows)),
        }
    return result


def _guard_metrics(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    histories: dict[tuple[int, str], dict[str, Any]] = {}
    for record in records:
        history = record.get("guard_provenance")
        if record["stage"] == "evaluation" and history is not None:
            histories[(int(record["seed"]), str(record["method"]))] = history
    return {
        f"{seed}:{method}": {
            key: history[key]
            for key in (
                "decision",
                "triggered",
                "action",
                "effective_skill_policy",
                "candidate_state_mutated",
                "candidate_mean",
                "cold_mean",
                "margin",
                "rounds_used",
                "first_decisive_round",
                "stop_reason",
                "guard_fingerprint",
            )
        }
        for (seed, method), history in sorted(histories.items())
    }


def assert_execution_allowed(
    mode: str,
    config: dict[str, Any],
    state_path: Path = DEFAULT_STATE,
) -> None:
    if mode == "dry-run":
        return
    state = read_json(state_path)
    repository_allowed = state.get("execution_policy", {}).get("paid_api_allowed") is True
    config_allowed = config.get("execution", {}).get("paid_api_allowed") is True
    if not repository_allowed or not config_allowed:
        raise PermissionError(
            "live execution refused: paid_api_allowed is false in the config "
            "and/or repository experiment state"
        )
    if state.get("execution_policy", {}).get("formal_scaling_allowed") is True:
        raise PermissionError("Phase 1B requires formal_scaling_allowed=false")


def _provider_for_mode(config: dict[str, Any], mode: str) -> Any:
    if mode == "dry-run":
        return DeterministicMockProvider()
    provider_env = config["execution"]["provider_env"]
    api_key = os.environ.get(str(provider_env["api_key"]), "")
    if not api_key.strip().startswith("sk-sp-"):
        raise ProviderUsageError("authorized Token Plan runner requires an sk-sp- API key")
    base_url = (
        os.environ.get(str(provider_env["base_url"]), "")
        or str(config["model"]["endpoint"])
    )
    return DashScopePaygProvider(
        api_key=api_key,
        base_url=base_url,
        model=str(config["model"]["model_id"]),
        max_output_tokens=int(config["model"]["max_output_tokens_per_attempt"]),
        timeout_seconds=float(config["model"]["timeout_seconds"]),
    )


def execute_preflight(
    *,
    config_path: Path = DEFAULT_CONFIG,
    output_dir: Path,
    mode: str | None = None,
    stop_after_new_calls: int | None = None,
    state_path: Path = DEFAULT_STATE,
) -> dict[str, Any]:
    config = validate_config(config_path)
    selected_mode = mode or str(config["execution"]["default_mode"])
    assert_execution_allowed(selected_mode, config, state_path)

    items = load_searchqa_items(config)
    items_by_id = {item["id"]: item for item in items}
    replicate_manifest = build_replicate_manifest(config, items)
    plan = build_call_plan(config, replicate_manifest)
    artifact_manifest = initialize_artifact(
        output_dir, config, replicate_manifest, plan, selected_mode
    )
    plan_by_id = {call["run_id"]: call for call in plan}
    completed = load_completed_records(
        output_dir,
        artifact_manifest=artifact_manifest,
        plan_by_id=plan_by_id,
    )
    attempts_by_id = load_attempt_records(
        output_dir,
        artifact_manifest=artifact_manifest,
        plan_by_id=plan_by_id,
    )
    for run_id, record in completed.items():
        if attempts_by_id.get(run_id) != record["attempts"]:
            raise ResumeError(f"call/attempt journal mismatch for resumed run {run_id}")
    unknown_usage = [
        (run_id, int(attempt["attempt_index"]))
        for run_id, attempts in attempts_by_id.items()
        for attempt in attempts
        if not attempt["usage_known"]
    ]
    if unknown_usage:
        raise ProviderUsageError(
            "attempt journal contains provider requests with unknown usage; "
            f"paid resume is refused: {unknown_usage[:3]}"
        )
    ledger = ledger_from_attempts(attempts_by_id, completed.values())
    _assert_ledger_identities(ledger)
    provider = _provider_for_mode(config, selected_mode)
    skill_text = Path(config["_validated"]["skill_path"]).read_text(encoding="utf-8")
    selectors = build_selectors(config, skill_text)
    calls_path = output_dir / "calls.jsonl"
    new_calls = 0
    with calls_path.open("a", encoding="utf-8", newline="\n") as handle:
        for call in plan:
            if call["run_id"] in completed:
                continue
            if stop_after_new_calls is not None and new_calls >= stop_after_new_calls:
                break
            item = items_by_id[call["item_id"]]
            prepared = prepare_call(
                config,
                call,
                item,
                skill_text,
                selectors,
                completed,
                replicate_manifest,
            )
            estimated_input = max(
                1,
                (
                    sum(
                        len(message["role"]) + len(message["content"]) + 8
                        for message in prepared["messages"]
                    )
                    + 3
                )
                // 4,
            )
            if estimated_input > int(config["model"]["max_input_tokens_per_attempt"]):
                raise BudgetExceeded(
                    f"estimated prompt exceeds max input envelope: {estimated_input}"
                )
            attempts = attempts_by_id.setdefault(call["run_id"], [])
            record = execute_prepared_call(
                config,
                call,
                item,
                prepared,
                ledger,
                provider,
                output_dir,
                attempts,
                mode=selected_mode,
            )
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            completed[call["run_id"]] = record
            ledger["logical_calls"] += 1
            ledger["retries"] = ledger["provider_attempts"] - ledger["logical_calls"]
            ledger["fallback_calls"] += int(bool(call["fallback"]))
            ledger["paid_calls"] += int(selected_mode == "live")
            _assert_ledger_identities(ledger)
            new_calls += 1

    complete = len(completed) == len(plan)
    _assert_ledger_identities(ledger)
    if complete:
        if ledger["logical_calls"] != int(config["planned_workload"]["total_logical_calls"]):
            raise PreflightError("complete run has the wrong logical-call count")
        if ledger["fallback_calls"] != int(config["planned_workload"]["fallback_logical_calls"]):
            raise PreflightError("complete run has the wrong fallback-call count")
        if selected_mode == "dry-run" and ledger["paid_calls"] != 0:
            raise PreflightError("dry-run recorded a paid call")
        if any(record["reasoning_content_present"] for record in completed.values()):
            raise PreflightError("thinking-disabled run returned reasoning_content")

    summary = {
        "artifact_schema_version": 2,
        "experiment": config["experiment"],
        "mode": selected_mode,
        "status": "completed" if complete else "incomplete",
        "config_fingerprint": artifact_manifest["config_fingerprint"],
        "dataset_fingerprint": artifact_manifest["dataset_fingerprint"],
        "skill_fingerprint": artifact_manifest["skill_fingerprint"],
        "rule_set_fingerprint": artifact_manifest["rule_set_fingerprint"],
        "source_fingerprints": artifact_manifest["source_fingerprints"],
        "provider_contract_fingerprint": artifact_manifest[
            "provider_contract_fingerprint"
        ],
        "frozen_candidate_source_fingerprint": artifact_manifest[
            "frozen_candidate_source_fingerprint"
        ],
        "manifest_fingerprint": artifact_manifest["manifest_fingerprint"],
        "plan_fingerprint": artifact_manifest["plan_fingerprint"],
        "expected_logical_calls": len(plan),
        "completed_logical_calls": len(completed),
        "new_calls_this_invocation": new_calls,
        "provider_invocations_this_process": provider.invocations,
        "ledger": {
            **ledger,
            "cost_cny": _cost_display(ledger["cost_pico_cny"]),
            "cost_usd": _cost_display(ledger["cost_pico_usd"]),
        },
        "method_metrics": _method_metrics(completed.values()),
        "guard_metrics": _guard_metrics(completed.values()),
        "gates": {
            "zero_paid_calls": ledger["paid_calls"] == 0 if selected_mode == "dry-run" else None,
            "complete_call_plan": complete,
            "exact_accounting": True,
            "strict_parser": True,
            "resume_identity": True,
            "hard_caps_respected": True,
            "thinking_disabled": not any(
                record["reasoning_content_present"] for record in completed.values()
            ),
            "authorized_token_plan_route": config["execution"]["billing_route"] == "token_plan_authorized",
            "absolute_cny_cap": config["hard_caps"]["cost_cny"],
        },
    }
    summary["summary_fingerprint"] = summary_fingerprint(summary)
    persisted_summary = {
        key: value
        for key, value in summary.items()
        if key not in {"new_calls_this_invocation", "provider_invocations_this_process"}
    }
    _atomic_write_json(output_dir / "summary.json", persisted_summary)
    finalize_artifact_manifest(output_dir, artifact_manifest, config, persisted_summary)
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--mode", choices=("dry-run", "live"), default=None)
    parser.add_argument(
        "--stop-after-new-calls",
        type=int,
        default=None,
        help="Diagnostic interruption hook used to verify exact resume behavior.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = execute_preflight(
            config_path=args.config,
            output_dir=args.out_dir.resolve(),
            mode=args.mode,
            stop_after_new_calls=args.stop_after_new_calls,
            state_path=args.state.resolve(),
        )
    except (PreflightError, PermissionError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
