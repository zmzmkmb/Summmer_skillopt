"""Offline selector-only diagnostics across nested rule-library sizes.

These metrics measure routing behavior, latency, and budget use without calling an
LLM.  Base-rule purity is a diagnostic proxy, not task accuracy.
"""
from __future__ import annotations

import hashlib
import json
import statistics
import time
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from rank_bm25 import BM25Okapi
from sklearn.metrics.pairwise import cosine_similarity

from skillopt.moar.tokenizer import count_tokens
from skillopt.moar.tracker import UtilityTracker
from skillopt.rag_rule_selector import RuleMemory

DEFAULT_WEIGHTS = (0.4, 0.3, 0.2, 0.1)


def _tokenize(text: str) -> list[str]:
    return text.lower().split()


def _budgeted_ranked_selection(
    order: Iterable[int], costs: np.ndarray, *, top_k: int, budget: int
) -> list[int]:
    selected: list[int] = []
    used = 0.0
    for raw_index in order:
        index = int(raw_index)
        cost = float(costs[index])
        if used + cost > budget:
            continue
        selected.append(index)
        used += cost
        if len(selected) >= top_k:
            break
    return selected


def _enforce_exact_budget(
    indices: Iterable[int], rule_texts: list[str], *, budget: int
) -> list[int]:
    """Preserve selector order while enforcing the final rendered token budget."""
    selected: list[int] = []
    for raw_index in indices:
        index = int(raw_index)
        candidate = [*selected, index]
        rendered = "\n\n".join(rule_texts[item] for item in candidate)
        if count_tokens(rendered) <= budget:
            selected.append(index)
    return selected


def _greedy_select(
    relevance: np.ndarray,
    utilities: np.ndarray,
    costs: np.ndarray,
    similarities: np.ndarray,
    *,
    top_k: int,
    budget: int,
    weights: tuple[float, float, float, float],
) -> list[int]:
    selected: list[int] = []
    remaining = list(range(len(relevance)))
    used = 0.0
    for _ in range(top_k):
        best_score = -float("inf")
        best_index = -1
        for index in remaining:
            cost = float(costs[index])
            if used + cost > budget:
                continue
            score = (
                weights[0] * float(relevance[index])
                + weights[1] * float(utilities[index])
                - weights[2] * (cost / budget)
            )
            if selected:
                score -= weights[3] * float(
                    np.mean([similarities[index, chosen] for chosen in selected])
                )
            if score > best_score:
                best_score = score
                best_index = index
        if best_index < 0:
            break
        selected.append(best_index)
        used += float(costs[best_index])
        remaining.remove(best_index)
    return selected


def _selection_fingerprint(rows: list[dict[str, Any]]) -> str:
    payload = [
        {"sample_id": row["sample_id"], "selected_rule_ids": row["selected_rule_ids"]}
        for row in rows
    ]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _summarize(
    *,
    method: str,
    library_size: int,
    rows: list[dict[str, Any]],
    base_rule_ids: set[str],
    rule_set_fingerprint: str,
) -> dict[str, Any]:
    latencies = [float(row["selection_ms"]) for row in rows]
    selected_counts = [len(row["selected_rule_ids"]) for row in rows]
    token_counts = [int(row["selected_tokens"]) for row in rows]
    total_selected = sum(selected_counts)
    total_base = sum(int(row["selected_base_rules"]) for row in rows)
    selected_base_ids = {
        rule_id
        for row in rows
        for rule_id in row["selected_rule_ids"]
        if rule_id in base_rule_ids
    }
    return {
        "method": method,
        "library_size": library_size,
        "n_queries": len(rows),
        "rule_set_fingerprint": rule_set_fingerprint,
        "selection_fingerprint": _selection_fingerprint(rows),
        "avg_selected_rules": statistics.mean(selected_counts) if rows else 0.0,
        "avg_selected_tokens": statistics.mean(token_counts) if rows else 0.0,
        "budget_violations": sum(bool(row["budget_violated"]) for row in rows),
        "selection_ms_mean": statistics.mean(latencies) if rows else 0.0,
        "selection_ms_p50": float(np.percentile(latencies, 50)) if rows else 0.0,
        "selection_ms_p95": float(np.percentile(latencies, 95)) if rows else 0.0,
        "base_selection_precision_proxy": total_base / total_selected if total_selected else 0.0,
        "base_query_hit_rate_proxy": (
            sum(int(row["selected_base_rules"] > 0) for row in rows) / len(rows)
            if rows else 0.0
        ),
        "distractor_query_rate": (
            sum(int(row["selected_distractor_rules"] > 0) for row in rows) / len(rows)
            if rows else 0.0
        ),
        "unique_base_rule_coverage": (
            len(selected_base_ids) / len(base_rule_ids) if base_rule_ids else 0.0
        ),
    }


def evaluate_library(
    *,
    library_path: str | Path,
    library_manifest: dict[str, Any],
    items: list[dict[str, Any]],
    methods: list[str],
    utility_path: str | Path | None,
    top_k: int = 5,
    budget: int = 2000,
    seed: int = 42,
    weights: tuple[float, float, float, float] = DEFAULT_WEIGHTS,
    moar_pop_size: int = 30,
    moar_generations: int = 15,
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """Evaluate selectors for one library and return summaries plus per-query rows."""
    content = Path(library_path).read_text(encoding="utf-8")
    base_rule_ids = {
        row["rule_id"] for row in library_manifest["rules"] if row["role"] == "base"
    }
    questions = [str(item["question"]) for item in items]
    sample_ids = [str(item.get("id", index)) for index, item in enumerate(items)]

    common_memory = RuleMemory(content, method="tfidf", top_k=top_k, token_budget=budget)
    rules = common_memory.dynamic_rules
    rule_texts = [rule.full_text for rule in rules]
    rule_ids = common_memory.dynamic_rule_ids
    costs = np.asarray([count_tokens(text) for text in rule_texts], dtype=float)
    rule_matrix = common_memory._rule_matrix
    dense_rule_matrix = (
        rule_matrix.toarray() if hasattr(rule_matrix, "toarray") else np.asarray(rule_matrix)
    )
    similarities = cosine_similarity(dense_rule_matrix)
    bm25 = BM25Okapi([_tokenize(text) for text in rule_texts])

    tracker = UtilityTracker(str(utility_path) if utility_path else None, frozen=True)
    tracker.register_rules(rule_texts)
    learned_utilities = tracker.compute_utilities("precision")
    cold_utilities = np.zeros(len(rules), dtype=float)

    memories: dict[str, RuleMemory] = {"tfidf": common_memory}
    if "moar" in methods:
        memories["moar"] = RuleMemory(
            content,
            method="moar",
            top_k=top_k,
            token_budget=budget,
            moar_utility_path=str(utility_path) if utility_path else None,
            moar_pop_size=moar_pop_size,
            moar_generations=moar_generations,
            moar_weights=",".join(str(value) for value in weights),
            moar_base_seed=seed,
            moar_frozen=True,
            moar_tokenizer="cl100k_base",
        )

    per_method: dict[str, list[dict[str, Any]]] = {}
    summaries: list[dict[str, Any]] = []
    for method in methods:
        rows: list[dict[str, Any]] = []
        for sample_id, question in zip(sample_ids, questions):
            start = time.perf_counter()
            if method == "tfidf":
                memory = memories["tfidf"]
                memory.retrieve(question, top_k=top_k, token_budget=budget)
                indices = list(memory._last_selections.get(question, []))
            elif method == "bm25":
                scores = bm25.get_scores(_tokenize(question))
                indices = _budgeted_ranked_selection(
                    np.argsort(-scores), costs, top_k=top_k, budget=budget
                )
            elif method in {"greedy-cold", "greedy-utility"}:
                query_vector = common_memory._vectorizer.transform([question])
                relevance = cosine_similarity(query_vector, dense_rule_matrix).ravel()
                utilities = cold_utilities if method == "greedy-cold" else learned_utilities
                indices = _greedy_select(
                    relevance, utilities, costs, similarities,
                    top_k=top_k, budget=budget, weights=weights,
                )
            elif method == "moar":
                memory = memories["moar"]
                memory.retrieve(question, top_k=top_k, token_budget=budget)
                indices = list(memory._last_selections.get(question, []))
            else:
                raise ValueError(f"Unknown selector method: {method}")
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            indices = _enforce_exact_budget(indices, rule_texts, budget=budget)

            selected_ids = [rule_ids[index] for index in indices]
            selected_text = "\n\n".join(rule_texts[index] for index in indices)
            selected_tokens = count_tokens(selected_text) if selected_text else 0
            selected_base = sum(rule_id in base_rule_ids for rule_id in selected_ids)
            rows.append({
                "sample_id": sample_id,
                "selected_indices": indices,
                "selected_rule_ids": selected_ids,
                "selected_tokens": selected_tokens,
                "budget_violated": selected_tokens > budget,
                "selection_ms": elapsed_ms,
                "selected_base_rules": selected_base,
                "selected_distractor_rules": len(selected_ids) - selected_base,
            })
        per_method[method] = rows
        summaries.append(_summarize(
            method=method,
            library_size=int(library_manifest["n_dynamic_rules"]),
            rows=rows,
            base_rule_ids=base_rule_ids,
            rule_set_fingerprint=str(library_manifest["rule_set_fingerprint"]),
        ))
    return summaries, per_method
