#!/usr/bin/env python3
"""Freeze and audit the zero-call Phase 1V calibration execution contract."""
from __future__ import annotations

import hashlib
import json
import string
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/acl2027/phase1v_calibration_preflight_v1.json"
OUTPUT = ROOT / "artifacts/acl2027_phase1v_calibration_preflight_v1"


class PreflightError(RuntimeError):
    pass


class HardStop(PreflightError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def relative(path: Path) -> str:
    try:
        value = path.relative_to(ROOT)
    except ValueError:
        value = path
    return str(value).replace("\\", "/")


def _nonblank(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_two_wiki_record(record: dict[str, Any]) -> None:
    required = {"id", "question", "answer", "answer_id", "supporting_evidence", "evidences", "evidences_id", "context"}
    if not required.issubset(record):
        raise PreflightError("2Wiki selected record missing required fields")
    if not all(_nonblank(record[key]) for key in ("id", "question", "answer")):
        raise PreflightError("2Wiki selected record contains blank identity or answer fields")
    if record["answer_id"] is not None and not _nonblank(record["answer_id"]):
        raise PreflightError("2Wiki answer ID must be null or a non-blank string")
    context = record["context"]
    if not isinstance(context, list) or not context:
        raise PreflightError("2Wiki context must be non-empty")
    context_index: dict[str, list[str]] = {}
    for entry in context:
        if not (isinstance(entry, list) and len(entry) == 2 and _nonblank(entry[0]) and isinstance(entry[1], list) and entry[1]):
            raise PreflightError("2Wiki context entry is empty or malformed")
        if not all(_nonblank(sentence) for sentence in entry[1]):
            raise PreflightError("2Wiki context contains a blank sentence")
        context_index.setdefault(entry[0].casefold(), entry[1])
    support = record["supporting_evidence"]
    if not isinstance(support, list) or not support:
        raise PreflightError("2Wiki supporting evidence must be non-empty")
    for item in support:
        if not (isinstance(item, list) and len(item) == 2 and _nonblank(item[0]) and isinstance(item[1], int) and not isinstance(item[1], bool)):
            raise PreflightError("2Wiki supporting evidence item is malformed")
        sentences = context_index.get(item[0].casefold())
        if sentences is None or item[1] < 0 or item[1] >= len(sentences):
            raise PreflightError("2Wiki supporting evidence reference is invalid")
    evidences = record["evidences"]
    evidence_ids = record["evidences_id"]
    if not isinstance(evidences, list) or not evidences or not isinstance(evidence_ids, list):
        raise PreflightError("2Wiki evidence chain must be non-empty and evidence IDs must be a list")
    if evidence_ids and len(evidences) != len(evidence_ids):
        raise PreflightError("2Wiki evidence and evidence-ID lengths differ")
    for chain in (evidences, evidence_ids):
        if any(not isinstance(edge, list) or len(edge) != 3 or not all(_nonblank(value) for value in edge) for edge in chain):
            raise PreflightError("2Wiki evidence chain contains an empty or malformed edge")


def validate_config(config: dict[str, Any]) -> None:
    execution = config.get("execution", {})
    if config.get("phase") != "1V" or any(execution.get(key) is not False for key in (
        "network_calls_allowed", "provider_calls_allowed", "paid_api_allowed", "formal_scaling_allowed"
    )):
        raise PreflightError("Phase 1V must remain zero-network, unpaid, and non-scaling")
    if execution.get("logical_calls") != 24 or execution.get("max_provider_attempts_per_logical_call") != 1:
        raise PreflightError("Phase 1V call-count or attempt contract drift")
    if execution.get("sdk_max_retries") != 0 or execution.get("explicit_retries") != 0:
        raise PreflightError("Phase 1V retries must remain zero")
    for group in ("phase1u_binding", "inputs"):
        for binding in config[group].values():
            path = ROOT / binding["path"]
            if not path.is_file() or sha256_file(path) != binding["sha256"]:
                raise PreflightError(f"immutable input hash mismatch: {binding['path']}")


def _render_two_wiki_context(context: list[list[Any]]) -> str:
    blocks = []
    for title, sentences in context:
        blocks.append(f"Title: {title}\n" + "\n".join(f"[{index}] {text}" for index, text in enumerate(sentences)))
    return "\n\n".join(blocks)


def build_request_plan(config_path: Path = CONFIG) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    config = read_json(config_path)
    validate_config(config)
    search_rows = read_json(ROOT / config["inputs"]["searchqa_calibration"]["path"])
    wiki_rows = read_json(ROOT / config["inputs"]["two_wiki_calibration"]["path"])
    if len(search_rows) != 12 or len(wiki_rows) != 12:
        raise PreflightError("calibration payload count drift")

    plan: list[dict[str, Any]] = []
    private: dict[str, dict[str, Any]] = {}
    wiki_aliases = _aliases_for_answer_ids(
        ROOT / config["inputs"]["two_wiki_aliases"]["path"],
        {row["answer_id"] for row in wiki_rows if row["answer_id"] is not None},
    )
    search_system = "Answer the question using the supplied context. Return strict JSON with exactly one key: answer. answer must be a non-empty string. No markdown or extra keys."
    wiki_system = "Answer the question using the supplied titled, sentence-indexed context. Return strict JSON with exactly the keys answer and supporting_evidence. answer must be a non-empty string. supporting_evidence must be a non-empty list of unique [title, sentence_index] pairs. Use the displayed zero-based sentence indices. No markdown or extra keys."

    for family, rows in (("SearchQA", search_rows), ("2WikiMultiHopQA", wiki_rows)):
        for row in rows:
            task_id = str(row["id"])
            logical_id = f"phase1v:{family}:{task_id}"
            if family == "SearchQA":
                if not (_nonblank(row.get("question")) and _nonblank(row.get("context")) and isinstance(row.get("answers"), list) and row["answers"] and all(_nonblank(x) for x in row["answers"])):
                    raise PreflightError("SearchQA selected record is empty or malformed")
                messages = [{"role": "system", "content": search_system}, {"role": "user", "content": f"Question: {row['question']}\n\nContext:\n{row['context']}"}]
                private[logical_id] = {"task_family": family, "task_id": task_id, "answers": row["answers"]}
            else:
                validate_two_wiki_record(row)
                messages = [{"role": "system", "content": wiki_system}, {"role": "user", "content": f"Question: {row['question']}\n\nContext:\n{_render_two_wiki_context(row['context'])}"}]
                aliases = wiki_aliases.get(row["answer_id"], [])
                private[logical_id] = {
                    "task_family": family, "task_id": task_id, "answers": [row["answer"], *aliases],
                    "answer_id": row["answer_id"], "supporting_evidence": row["supporting_evidence"],
                    "evidences": row["evidences"], "evidences_id": row["evidences_id"],
                    "answer_id_available": row["answer_id"] is not None,
                    "evidences_id_available": bool(row["evidences_id"]),
                }
            request = {"temperature": config["request_contract"]["temperature"], "messages": messages}
            plan.append({"call_index": len(plan) + 1, "logical_call_id": logical_id, "task_family": family, "task_id": task_id, "request": request, "request_hash": stable_hash(request)})
    return config, plan, private


def _aliases_for_answer_ids(path: Path, answer_ids: set[str]) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            answer_id = row.get("Q_id")
            if answer_id in answer_ids:
                values = [value for key in ("aliases", "demonyms") for value in row.get(key, []) if _nonblank(value)]
                found.setdefault(answer_id, []).extend(values)
    return {key: list(dict.fromkeys(values)) for key, values in found.items()}


def normalize_answer(value: str) -> str:
    value = value.lower().translate(str.maketrans("", "", string.punctuation))
    return " ".join(token for token in value.split() if token not in {"a", "an", "the"})


def parse_response(family: str, raw_text: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise PreflightError("malformed JSON response") from exc
    if not isinstance(payload, dict):
        raise PreflightError("response must be a JSON object")
    expected = {"answer"} if family == "SearchQA" else {"answer", "supporting_evidence"}
    if set(payload) != expected or not _nonblank(payload.get("answer")):
        raise PreflightError("response schema keys or answer are invalid")
    if family == "2WikiMultiHopQA":
        support = payload["supporting_evidence"]
        if not isinstance(support, list) or not support:
            raise PreflightError("supporting_evidence must be non-empty")
        normalized = []
        for item in support:
            if not (isinstance(item, list) and len(item) == 2 and _nonblank(item[0]) and isinstance(item[1], int) and not isinstance(item[1], bool) and item[1] >= 0):
                raise PreflightError("supporting_evidence item is invalid")
            normalized.append((item[0].casefold(), item[1]))
        if len(set(normalized)) != len(normalized):
            raise PreflightError("supporting_evidence contains duplicates")
    return payload


def verify_response(payload: dict[str, Any], private: dict[str, Any]) -> dict[str, bool]:
    answer_ok = normalize_answer(payload["answer"]) in {normalize_answer(value) for value in private["answers"]}
    if private["task_family"] == "SearchQA":
        return {"answer_correct": answer_ok, "support_correct": True, "joint_correct": answer_ok}
    predicted = {(title.casefold(), index) for title, index in payload["supporting_evidence"]}
    expected = {(title.casefold(), index) for title, index in private["supporting_evidence"]}
    support_ok = predicted == expected
    return {"answer_correct": answer_ok, "support_correct": support_ok, "joint_correct": answer_ok and support_ok}


def exact_usage(response: dict[str, Any]) -> dict[str, int]:
    usage = response.get("usage")
    keys = ("input_tokens", "output_tokens", "total_tokens")
    if not isinstance(usage, dict) or any(not isinstance(usage.get(key), int) or isinstance(usage.get(key), bool) or usage[key] < 0 for key in keys):
        raise PreflightError("unknown usage")
    if usage["input_tokens"] + usage["output_tokens"] != usage["total_tokens"]:
        raise PreflightError("unknown usage")
    return {key: usage[key] for key in keys}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def execute_simulation(plan: list[dict[str, Any]], private: dict[str, dict[str, Any]], output: Path, provider: Callable[[dict[str, Any]], dict[str, Any]], *, max_new_calls: int | None = None) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    plan_path = output / "request_plan.json"
    if plan_path.exists() and stable_hash(read_json(plan_path)) != stable_hash(plan):
        raise PreflightError("request plan drift")
    if not plan_path.exists():
        write_json(plan_path, plan)
    records = _load_jsonl(output / "results.jsonl")
    if len(records) > len(plan):
        raise PreflightError("resume call-count drift")
    seen: set[str] = set()
    for index, record in enumerate(records):
        expected = plan[index]
        if any(record.get(key) != expected[key] for key in ("call_index", "logical_call_id", "request_hash")):
            raise PreflightError("completed records are not an exact plan prefix")
        if record["logical_call_id"] in seen:
            raise PreflightError("duplicate resume record")
        seen.add(record["logical_call_id"])
        if record.get("terminal"):
            raise HardStop("terminal failure is not resumable")
    made = 0
    for item in plan[len(records):]:
        if max_new_calls is not None and made >= max_new_calls:
            break
        made += 1
        base = {key: item[key] for key in ("call_index", "logical_call_id", "request_hash", "task_family", "task_id")}
        try:
            response = provider(deepcopy(item["request"]))
            usage = exact_usage(response)
        except Exception as exc:  # noqa: BLE001
            record = {**base, "status": "hard_stop", "terminal": True, "usage_known": False, "error": str(exc)}
        else:
            raw = response.get("content")
            common = {**base, **usage, "terminal": False, "usage_known": True, "raw_response_text": raw, "raw_response_sha256": stable_hash(raw)}
            try:
                payload = parse_response(item["task_family"], raw)
            except Exception as exc:  # noqa: BLE001
                record = {**common, "status": "invalid_output", "error": str(exc)}
            else:
                record = {**common, "status": "completed", "response": payload, **verify_response(payload, private[item["logical_call_id"]])}
        with (output / "results.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")
        records.append(record)
        if record["terminal"]:
            break
    usage = {key: sum(row.get(key, 0) for row in records) for key in ("input_tokens", "output_tokens", "total_tokens")}
    terminal = bool(records and records[-1].get("terminal"))
    manifest = {
        "status": "hard_stopped" if terminal else "completed_with_invalid_outputs" if len(records) == len(plan) and any(row["status"] == "invalid_output" for row in records) else "completed" if len(records) == len(plan) else "paused",
        "planned_calls": len(plan), "recorded_calls": len(records), "provider_attempts": len(records),
        "invalid_output_calls": sum(row["status"] == "invalid_output" for row in records),
        "usage_known_for_all_attempts": all(row["usage_known"] for row in records), "usage": usage,
    }
    write_json(output / "run_manifest.json", manifest)
    return manifest


class SimulatedProvider:
    def __init__(self, plan: list[dict[str, Any]], private: dict[str, dict[str, Any]], modes: dict[int, str] | None = None):
        self.plan, self.private, self.modes, self.calls = plan, private, modes or {}, 0

    def __call__(self, request: dict[str, Any]) -> dict[str, Any]:
        item = self.plan[self.calls]
        self.calls += 1
        if stable_hash(request) != item["request_hash"]:
            raise PreflightError("simulated request drift")
        mode = self.modes.get(self.calls, "valid")
        usage = {"input_tokens": 11, "output_tokens": 7, "total_tokens": 18}
        if mode == "unknown_usage":
            return {"content": "{}", "usage": None}
        if mode == "malformed":
            return {"content": '{"answer":', "usage": usage}
        private = self.private[item["logical_call_id"]]
        payload: dict[str, Any] = {"answer": private["answers"][0]}
        if item["task_family"] == "2WikiMultiHopQA":
            payload["supporting_evidence"] = private["supporting_evidence"]
        if mode == "schema_invalid":
            payload["extra"] = True
        return {"content": json.dumps(payload), "usage": usage}


def run_preflight(output: Path = OUTPUT) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite immutable artifact: {output}")
    config, plan, private = build_request_plan()
    output.mkdir(parents=True)
    simulations = output / "simulations"
    known = SimulatedProvider(plan, private, {1: "malformed", 2: "schema_invalid"})
    invalid = execute_simulation(plan, private, simulations / "known_invalid", known, max_new_calls=3)
    unknown = execute_simulation(plan, private, simulations / "unknown_usage", SimulatedProvider(plan, private, {1: "unknown_usage"}))
    resume_provider = SimulatedProvider(plan, private)
    paused = execute_simulation(plan, private, simulations / "resume", resume_provider, max_new_calls=5)
    resumed = execute_simulation(plan, private, simulations / "resume", resume_provider, max_new_calls=4)
    drift = deepcopy(plan)
    drift[0]["request"]["temperature"] = 0.5
    drift_detected = False
    try:
        execute_simulation(drift, private, simulations / "resume", SimulatedProvider(drift, private), max_new_calls=1)
    except PreflightError as exc:
        drift_detected = "plan drift" in str(exc)
    terminal_resume_refused = False
    try:
        execute_simulation(plan, private, simulations / "unknown_usage", SimulatedProvider(plan, private))
    except HardStop:
        terminal_resume_refused = True

    fixture_results = []
    for row in plan:
        gold = private[row["logical_call_id"]]
        payload: dict[str, Any] = {"answer": gold["answers"][0]}
        if row["task_family"] == "2WikiMultiHopQA":
            payload["supporting_evidence"] = gold["supporting_evidence"]
        fixture_results.append(
            verify_response(
                parse_response(row["task_family"], json.dumps(payload)), gold
            )["joint_correct"]
        )
    checks = {
        "phase1u_hashes_bound": True,
        "exact_24_ordered_requests": len(plan) == 24 and [row["task_family"] for row in plan] == ["SearchQA"] * 12 + ["2WikiMultiHopQA"] * 12,
        "unique_ids_and_hashes": len({row["logical_call_id"] for row in plan}) == 24 and len({row["request_hash"] for row in plan}) == 24,
        "strengthened_selected_source_gate": all(validate_two_wiki_record(row) is None for row in read_json(ROOT / config["inputs"]["two_wiki_calibration"]["path"])),
        "missing_evidence_ids_visible": sum(not gold.get("evidences_id_available", True) for gold in private.values()) == 5,
        "missing_answer_id_visible": sum(not gold.get("answer_id_available", True) for gold in private.values()) == 1,
        "private_gold_structurally_separated": all(
            set(row) == {"call_index", "logical_call_id", "task_family", "task_id", "request", "request_hash"}
            and set(row["request"]) == {"temperature", "messages"}
            for row in plan
        ) and all(set(gold) - {"task_family", "task_id"} for gold in private.values()),
        "held_out_partition_not_an_input": "held_out" not in json.dumps(config["inputs"], sort_keys=True),
        "strict_parser_and_verifiers": all(fixture_results),
        "known_usage_invalid_visible_and_continues": invalid["recorded_calls"] == 3 and invalid["invalid_output_calls"] == 2 and invalid["usage"]["total_tokens"] == 54,
        "unknown_usage_terminal_nonresumable": unknown["status"] == "hard_stopped" and terminal_resume_refused,
        "append_only_exact_prefix_resume": paused["recorded_calls"] == 5 and resumed["recorded_calls"] == 9 and resume_provider.calls == 9,
        "plan_drift_terminal": drift_detected,
        "zero_retries_calls_and_cost": config["execution"]["explicit_retries"] == 0 and config["execution"]["sdk_max_retries"] == 0,
    }
    write_json(output / "request_plan.json", plan)
    write_json(output / "evaluator_private.json", private)
    audit = {
        "analysis": "phase1v_calibration_request_and_verifier_preflight", "checks": checks,
        "decision": "preflight_passed_provider_execution_closed" if all(checks.values()) else "preflight_failed_provider_execution_closed",
        "request_count": len(plan), "request_plan_sha256": stable_hash(plan), "evaluator_private_sha256": stable_hash(private),
        "network_calls": 0, "provider_calls": 0, "paid_api_calls": 0, "simulated_attempts_are_not_provider_calls": True,
        "scientific_claim_effect": "measurement_readiness_only_main_claim_unchanged",
    }
    audit_path = output / "preflight_audit.json"
    write_json(audit_path, audit)
    manifest = {
        "schema_version": 1, "experiment": config["experiment"], "config_path": relative(CONFIG), "config_sha256": sha256_file(CONFIG),
        "expected_runs": 1, "available_runs": 1, "complete_grid": True, "network_calls": 0, "provider_calls": 0, "paid_api_calls": 0,
        "runs": [{"run_id": "phase1v_zero_call_preflight", "status": "completed", "result_path": relative(audit_path), "file_sha256": sha256_file(audit_path)}],
        "aggregate_fingerprint": sha256_file(audit_path),
    }
    write_json(output / "run_manifest.json", manifest)
    return audit


if __name__ == "__main__":
    result = run_preflight()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if all(result["checks"].values()) else 1)
