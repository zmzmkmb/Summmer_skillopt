"""Feature computation for multi-objective atomic rule selection.

Precomputes static features (token costs, pairwise similarities, TF-IDF matrix)
and computes per-query objectives for a population of binary chromosomes.

Token costs are computed via :mod:`skillopt.moar.tokenizer` (tiktoken) when
``use_tokenizer=True``, falling back to character length otherwise.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

if TYPE_CHECKING:
    from skillopt.moar.tokenizer import TokenCounter


@dataclass
class FeatureCache:
    """Precomputed features shared across all queries for one RuleMemory instance.

    Attributes
    ----------
    token_costs : np.ndarray
        Shape ``(n_rules,)`` — real token count per dynamic rule (or character
        length when no tokenizer is available).
    pairwise_sims : np.ndarray
        Shape ``(n_rules, n_rules)`` — cosine similarity between rule embeddings.
    rule_embeddings : np.ndarray
        Shape ``(n_rules, n_features)`` — dense TF-IDF matrix.
    _tokenizer_used : bool
        True if token costs were computed via a real tokenizer.
    """
    token_costs: np.ndarray         # (n_rules,)
    pairwise_sims: np.ndarray       # (n_rules, n_rules)
    rule_embeddings: np.ndarray     # (n_rules, n_features)
    _cached_triu: np.ndarray | None = None  # upper-triangle for fast redundancy
    _tokenizer_used: bool = False

    @classmethod
    def from_arrays(
        cls,
        rule_texts: list[str],
        rule_embeddings: np.ndarray,
        token_counter: "TokenCounter | None" = None,
    ) -> "FeatureCache":
        """Build cache from rule texts and a pre-built TF-IDF matrix.

        Parameters
        ----------
        rule_texts : list[str]
            Full text of each dynamic rule.
        rule_embeddings : np.ndarray
            Dense TF-IDF matrix of shape ``(n_rules, n_features)``.
        token_counter : TokenCounter | None
            If provided, use real token counts via tiktoken.
            If None, fall back to character length.
        """
        n = len(rule_texts)
        if token_counter is not None:
            token_costs = np.array(
                token_counter.count_batch(rule_texts), dtype=np.float64
            )
            tokenizer_used = True
        else:
            token_costs = np.array([len(t) for t in rule_texts], dtype=np.float64)
            tokenizer_used = False

        if n <= 1:
            pairwise_sims = np.zeros((n, n))
            triu = np.zeros(0)
        else:
            embeddings_dense = rule_embeddings.toarray() if hasattr(
                rule_embeddings, 'toarray') else np.asarray(rule_embeddings)
            pairwise_sims = cosine_similarity(embeddings_dense)
            np.fill_diagonal(pairwise_sims, 0.0)  # self-similarity excluded
            triu = pairwise_sims[np.triu_indices(n, k=1)]

        return cls(
            token_costs=token_costs,
            pairwise_sims=pairwise_sims,
            rule_embeddings=rule_embeddings,
            _cached_triu=triu,
            _tokenizer_used=tokenizer_used,
        )


# ── Objective computation ─────────────────────────────────────────────────────


def compute_objectives(
    chromosomes: np.ndarray,         # (pop_size, n_rules) binary
    query_embedding: np.ndarray,     # (n_features,) sparse or dense
    cache: FeatureCache,              # precomputed static features
    utilities: np.ndarray,            # (n_rules,) current utility per rule
    budget: int,                      # token budget
    top_k: int = 5,                   # reference top-k for normalisation
) -> np.ndarray:
    """Compute 4 objectives for a population of chromosomes.

    All objectives are **minimised** and normalised to roughly [0, 1].

    Parameters
    ----------
    chromosomes : np.ndarray
        Shape ``(pop_size, n_rules)`` — binary rule selection indicators.
    query_embedding : np.ndarray
        Shape ``(n_features,)`` — TF-IDF vector of the current query.
    cache : FeatureCache
        Precomputed token costs, pairwise similarities, rule embeddings.
    utilities : np.ndarray
        Shape ``(n_rules,)`` — current per-rule utility (e.g. precision).
    budget : int
        Token budget for normalisation of the cost objective.
    top_k : int
        Reference k used for relevance/utility normalisation denominators.

    Returns
    -------
    np.ndarray
        Shape ``(pop_size, 4)`` — objectives [f1, f2, f3, f4] all minimised.
    """
    pop_size, n_rules = chromosomes.shape

    # ── Relevance scores (per rule, per query) ───────────────────────────
    qv = query_embedding
    rv = cache.rule_embeddings

    if hasattr(qv, 'toarray'):
        qv = qv.toarray().ravel()
    if hasattr(rv, 'toarray'):
        rv = rv.toarray()

    rel_scores = cosine_similarity(qv.reshape(1, -1), rv).ravel()  # (n_rules,)

    # Max possible: sum of top K relevance scores
    top_k_actual = min(top_k, n_rules)
    if n_rules > 0:
        max_rel = np.sum(np.sort(rel_scores)[-top_k_actual:])
    else:
        max_rel = 0.0

    if n_rules > 0 and max_rel > 1e-12:
        selected_rel = chromosomes @ rel_scores  # (pop_size,)
        f1 = 1.0 - selected_rel / max_rel
    else:
        f1 = np.zeros(pop_size)

    # ── Utility (f2, minimised) ──────────────────────────────────────────
    if n_rules > 0 and np.max(utilities) > 1e-12:
        top_k_util = np.sum(np.sort(utilities)[-top_k_actual:])
        if top_k_util > 1e-12:
            selected_util = chromosomes @ utilities
            f2 = 1.0 - selected_util / top_k_util
        else:
            f2 = np.zeros(pop_size)
    else:
        f2 = np.zeros(pop_size)
    # When selecting more rules than top_k, utility can exceed reference;
    # f2 can go negative — clip it back.  The NSGA-II domination logic
    # handles negative values fine, but normalise the range.
    f2 = np.clip(f2, -1.0, 1.0)

    # ── Token cost (f3, minimised) ───────────────────────────────────────
    selected_cost = chromosomes @ cache.token_costs  # (pop_size,)
    f3 = np.clip(selected_cost / max(budget, 1), 0.0, 1.0)

    # ── Redundancy (f4, minimised) ───────────────────────────────────────
    f4 = _compute_redundancy(chromosomes, cache, n_rules)

    return np.column_stack([f1, f2, f3, f4])


def _compute_redundancy(
    chromosomes: np.ndarray,
    cache: FeatureCache,
    n_rules: int,
) -> np.ndarray:
    """Compute pairwise rule redundancy for each chromosome.

    f4 = Σ_{i<j} x_i * x_j * sim(r_i, r_j) / (n_selected * (n_selected-1) / 2)
    Normalised to [0, 1]; 0 when n_selected <= 1.
    """
    pop_size = len(chromosomes)
    f4 = np.zeros(pop_size)

    if n_rules <= 1:
        return f4

    # Upper-triangle indices of the pairwise similarity matrix
    i_idx, j_idx = np.triu_indices(n_rules, k=1)

    for p in range(pop_size):
        x = chromosomes[p]
        n_sel = np.sum(x)
        if n_sel <= 1:
            f4[p] = 0.0
            continue

        # Selected pairs: x_i * x_j == 1 for both selected
        sel_pairs = x[i_idx] * x[j_idx]
        pair_count = np.sum(sel_pairs)
        if pair_count <= 0:
            f4[p] = 0.0
            continue

        total_sim = np.dot(sel_pairs, cache.pairwise_sims[i_idx, j_idx])
        max_pairs = n_sel * (n_sel - 1) / 2.0
        f4[p] = total_sim / max_pairs

    return np.clip(f4, 0.0, 1.0)
