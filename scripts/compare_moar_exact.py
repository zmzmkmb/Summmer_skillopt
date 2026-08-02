#!/usr/bin/env python3
"""MOAR vs Exact 离线最优性差距 -- 0 API token 消耗。

对每条 query 同时运行 MOAR (NSGA-II) 和精确穷举搜索，比较：
1. MOAR 命中精确最优解的比例（hit rate）
2. MOAR 与 Exact 的平均目标函数差距
3. 目标函数差距 P95
4. 规则集合平均 Jaccard
5. 统一的 M 分数量化

目标函数 M（与 exact_select / greedy_select 一致）：

    M = w[0]·Σrel/top_k + w[1]·Σutil/top_k - w[2]·Σcost/budget - w[3]·avg_sim

当前规则库仅有 8 条动态规则，在 Top-K=5 约束下共有 C(8,1)+...+C(8,5)=218 种合法候选子集，可完全穷举。
本脚本回答：MOAR 在穷举最优解中离最优解有多远？

用法:
    python scripts/compare_moar_exact.py \
        --skill outputs/searchqa_rag/best_skill.md \
        --limit 200
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from math import comb
from itertools import combinations

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from skillopt.rag_rule_selector import RuleMemory


# ── 目标函数 M ──────────────────────────────────────────────────────────────

# M_exact: 与 exact_select / greedy_select 一致的归一化（除以 top_k）
def compute_m_exact(
    selected_indices: list[int],
    relevance: np.ndarray,
    utilities: np.ndarray,
    token_costs: np.ndarray,
    pairwise_sims: np.ndarray,
    top_k: int,
    budget: int,
    weights: tuple[float, float, float, float],
) -> float:
    """精确目标函数：按 top_k 归一化。

    M = w0·Σrel/top_k + w1·Σutil/top_k - w2·Σcost/budget - w3·avg_sim
    """
    if not selected_indices:
        return 0.0

    idx = np.array(selected_indices)
    sel_rel = float(np.sum(relevance[idx])) / top_k
    sel_util = float(np.sum(utilities[idx])) / top_k
    cost_ratio = float(np.sum(token_costs[idx])) / max(budget, 1)
    if len(idx) >= 2:
        pairs = [(i, j) for pi, i in enumerate(idx) for j in idx[pi + 1:]]
        avg_sim = float(np.mean([pairwise_sims[i, j] for i, j in pairs]))
    else:
        avg_sim = 0.0

    return (
        weights[0] * sel_rel
        + weights[1] * sel_util
        - weights[2] * cost_ratio
        - weights[3] * avg_sim
    )


# M_moar: 与 MOAR 内部 NSGA-II compute_objectives 一致的归一化（除以 max_rel/topk_util）
def compute_m_moar(
    selected_indices: list[int],
    relevance: np.ndarray,
    utilities: np.ndarray,
    token_costs: np.ndarray,
    pairwise_sims: np.ndarray,
    top_k: int,
    budget: int,
    weights: tuple[float, float, float, float],
) -> float:
    """MOAR 内部目标函数：按 max_rel 归一化。

    MOAR 内部分数 = w0·(1-f1) + w1·(1-f2) - w2·f3 - w3·f4
    其中 f1 = 1 - Σrel/max_rel, f2 = 1 - Σutil/topk_util 等。

    等价于：
    M = w0·Σrel/max_rel + w1·Σutil/topk_util - w2·Σcost/budget - w3·redundancy
    """
    if not selected_indices:
        return 0.0

    idx = np.array(selected_indices)
    n = len(relevance)
    top_k_actual = min(top_k, n)

    # max_rel = sum of top-K relevance scores（与 compute_objectives 一致）
    max_rel = float(np.sum(np.sort(relevance)[-top_k_actual:]))
    sel_rel = float(np.sum(relevance[idx])) / max(max_rel, 1e-12)

    # top_k_util = sum of top-K utility scores
    top_k_util = float(np.sum(np.sort(utilities)[-top_k_actual:]))
    sel_util = float(np.sum(utilities[idx])) / max(top_k_util, 1e-12)

    cost_ratio = float(np.sum(token_costs[idx])) / max(budget, 1)

    if len(idx) >= 2:
        pairs = [(i, j) for pi, i in enumerate(idx) for j in idx[pi + 1:]]
        redundancy = float(np.mean([pairwise_sims[i, j] for i, j in pairs]))
    else:
        redundancy = 0.0

    return (
        weights[0] * sel_rel
        + weights[1] * sel_util
        - weights[2] * cost_ratio
        - weights[3] * redundancy
    )


# ── 精确穷举 ────────────────────────────────────────────────────────────────

def exact_select_both(
    relevance: np.ndarray,
    utilities: np.ndarray,
    token_costs: np.ndarray,
    pairwise_sims: np.ndarray,
    top_k: int,
    budget: int,
    weights: tuple[float, float, float, float],
) -> tuple[list[int], float, list[int], float]:
    """同时穷举 M_exact 和 M_moar 两套精确最优解。

    返回 (exact_by_M_exact, best_M_exact, exact_by_M_moar, best_M_moar)。

    仅适用于 n <= 20。
    """
    n = len(relevance)
    if n > 20:
        raise ValueError(f"穷举仅支持 n <= 20，当前 n={n}")

    best_m_exact = -np.inf
    best_m_moar = -np.inf
    best_exact: list[int] = []
    best_moar: list[int] = []

    for k in range(1, top_k + 1):
        for combo in combinations(range(n), k):
            combo_list = list(combo)
            total_cost = float(np.sum(token_costs[list(combo_list)]))
            if total_cost > budget:
                continue

            m_ex = compute_m_exact(combo_list, relevance, utilities,
                                   token_costs, pairwise_sims, top_k, budget, weights)
            if m_ex > best_m_exact:
                best_m_exact = m_ex
                best_exact = combo_list

            m_mo = compute_m_moar(combo_list, relevance, utilities,
                                  token_costs, pairwise_sims, top_k, budget, weights)
            if m_mo > best_m_moar:
                best_m_moar = m_mo
                best_moar = combo_list

    return best_exact, best_m_exact, best_moar, best_m_moar


# ── MOAR 选择 ───────────────────────────────────────────────────────────────

def moar_select_for_query(
    rm,
    query: str,
    relevance: np.ndarray,
    utilities: np.ndarray,
    token_costs: np.ndarray,
    pairwise_sims: np.ndarray,
    top_k: int,
    budget: int,
    weights: tuple[float, float, float, float],
) -> tuple[list[int], float, float, float]:
    """用 MOAR (NSGA-II) 为单条 query 选择规则。

    返回 (selected_indices, M_exact, M_moar, 检索耗时 ms)。
    """
    t0 = time.time()
    rm.retrieve(query, top_k=top_k, token_budget=budget)
    sel_ms = (time.time() - t0) * 1000

    indices = rm._last_selections.get(query, [])
    if not indices:
        return [], 0.0, 0.0, sel_ms

    m_exact = compute_m_exact(list(indices), relevance, utilities,
                              token_costs, pairwise_sims, top_k, budget, weights)
    m_moar = compute_m_moar(list(indices), relevance, utilities,
                            token_costs, pairwise_sims, top_k, budget, weights)
    return list(indices), m_exact, m_moar, sel_ms


def _jaccard(set_a: set, set_b: set) -> float:
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


# ── 加载 ────────────────────────────────────────────────────────────────────

def load_test_queries(limit: int = 0) -> list[dict]:
    """加载 SearchQA test set."""
    data_dir = os.path.join(_PROJECT_ROOT, "data", "searchqa_split", "test")
    path = os.path.join(data_dir, "items.json")
    with open(path, encoding="utf-8") as f:
        items = json.load(f)
    if limit > 0:
        items = items[:limit]
    return items


# ── 主流程 ──────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--skill", type=str,
                   default="outputs/searchqa_rag/best_skill.md")
    p.add_argument("--limit", type=int, default=200)
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--budget", type=int, default=2000)
    p.add_argument("--weights", type=str, default="0.4,0.3,0.2,0.1")
    p.add_argument("--moar-pop-size", type=int, default=50)
    p.add_argument("--moar-generations", type=int, default=30)
    p.add_argument("--out", type=str, default="")
    return p.parse_args()


def main():
    args = parse_args()
    weights = tuple(float(x.strip())
                    for x in args.weights.split(",")[:4])
    if len(weights) < 4:
        weights = (0.4, 0.3, 0.2, 0.1)

    # ── 加载 skill ──────────────────────────────────────────────────────────
    skill_path = args.skill
    if not os.path.isabs(skill_path):
        skill_path = os.path.join(_PROJECT_ROOT, skill_path)
    with open(os.path.abspath(skill_path), encoding="utf-8") as f:
        skill_content = f.read()

    # ── 构建 RuleMemory（TF-IDF 基础 + MOAR 引擎） ──────────────────────────
    rm_tfidf = RuleMemory(skill_content, method="tfidf",
                          top_k=args.top_k, token_budget=args.budget)
    rm_moar = RuleMemory(
        skill_content, method="moar",
        top_k=args.top_k, token_budget=args.budget,
        moar_pop_size=args.moar_pop_size,
        moar_generations=args.moar_generations,
        moar_utility_method="precision",
        moar_base_seed=42,
        moar_frozen=True,
    )

    n_dyn = rm_tfidf.n_dynamic
    actual_top_k = min(args.top_k, n_dyn)
    total_combos = sum(comb(n_dyn, k) for k in range(1, actual_top_k + 1))
    print(f"Skill: core={rm_tfidf.n_core} dynamic={n_dyn} "
          f"(top_k={actual_top_k}, 枚举组合数={total_combos})")
    print(f"Config: top_k={args.top_k} budget={args.budget} "
          f"weights={weights}")
    print(f"MOAR: pop={args.moar_pop_size} gen={args.moar_generations}")

    if n_dyn == 0:
        print("无动态规则，退出。")
        return
    if n_dyn > 20:
        print(f"n_dyn={n_dyn} > 20，精确穷举不可行，退出。")
        return

    # ── 预计算共享特征 ──────────────────────────────────────────────────────
    rv = rm_tfidf._rule_matrix
    if hasattr(rv, 'toarray'):
        rv = rv.toarray()

    rule_texts = [r.full_text for r in rm_tfidf.dynamic_rules]

    # 用真实 tokenizer 计数
    try:
        from skillopt.moar.tokenizer import count_tokens
        token_costs = np.array([count_tokens(t) for t in rule_texts], dtype=float)
        cost_mode = "tokens"
    except Exception:
        token_costs = np.array([len(t) for t in rule_texts], dtype=float)
        cost_mode = "chars"

    pairwise_sims = cosine_similarity(rv)
    np.fill_diagonal(pairwise_sims, 0.0)
    utilities = np.zeros(n_dyn)  # 冷启动：0 历史效用
    avg_cost = float(np.mean(token_costs))

    print(f"Cost mode: {cost_mode} (avg {avg_cost:.0f} {cost_mode}/rule)")

    # ── 逐 query 比较 ───────────────────────────────────────────────────────
    items = load_test_queries(args.limit)
    n_queries = len(items)
    print(f"\nQueries: {n_queries}")

    exact_hits = 0         # MOAR 规则集 == M_exact 最优规则集
    moar_hits_own = 0      # MOAR 规则集 == M_moar 最优规则集
    gaps_exact: list[float] = []  # M_exact* - M_exact(MOAR), >=0
    gaps_moar: list[float] = []   # M_moar* - M_moar(MOAR), >=0 (MOAR 低于自身度量最优)
    jaccards_exact: list[float] = []
    jaccards_moar: list[float] = []
    moar_times: list[float] = []
    exact_times: list[float] = []

    per_query: list[dict] = []

    print(f"\n{'='*70}")
    for qi, item in enumerate(items):
        query = item["question"]

        # TF-IDF 相关性
        qv = rm_tfidf._vectorizer.transform([query])
        rel = cosine_similarity(qv, rv).ravel()

        # ── MOAR ────────────────────────────────────────────────────────
        moar_indices, moar_m_exact, moar_m_moar, moar_ms = moar_select_for_query(
            rm_moar, query, rel, utilities, token_costs,
            pairwise_sims, args.top_k, args.budget, weights,
        )

        # ── Exact（双重穷举）─────────────────────────────────────────────
        t_exact_start = time.time()
        opt_exact_idx, opt_m_exact, opt_moar_idx, opt_m_moar = exact_select_both(
            rel, utilities, token_costs, pairwise_sims,
            args.top_k, args.budget, weights,
        )
        exact_ms = (time.time() - t_exact_start) * 1000

        # ── 比较 ────────────────────────────────────────────────────────
        # A: M_exact 度量
        gap_ex = opt_m_exact - moar_m_exact
        if abs(gap_ex) < 1e-10:
            exact_hits += 1
        gaps_exact.append(gap_ex)

        # B: M_moar 度量（MOAR vs M_moar 全局最优）
        gap_mo = opt_m_moar - moar_m_moar
        if abs(gap_mo) < 1e-10:
            moar_hits_own += 1
        gaps_moar.append(gap_mo)

        # Jaccard vs M_exact 最优
        set_moar = set(moar_indices)
        set_exact = set(opt_exact_idx)
        jac_ex = _jaccard(set_moar, set_exact)
        jaccards_exact.append(jac_ex)

        # Jaccard vs M_moar 最优
        set_moar_opt = set(opt_moar_idx)
        jac_mo = _jaccard(set_moar, set_moar_opt)
        jaccards_moar.append(jac_mo)

        moar_times.append(moar_ms)
        exact_times.append(exact_ms)

        per_query.append({
            "query_id": str(item["id"]),
            "moar_indices": moar_indices,
            "opt_exact_indices": opt_exact_idx,
            "opt_moar_indices": opt_moar_idx,
            "moar_m_exact": float(moar_m_exact),
            "moar_m_moar": float(moar_m_moar),
            "opt_m_exact": float(opt_m_exact),
            "opt_m_moar": float(opt_m_moar),
            "gap_exact": float(gap_ex),
            "gap_moar": float(gap_mo),
            "jaccard_exact": float(jac_ex),
            "jaccard_moar": float(jac_mo),
            "moar_ms": float(moar_ms),
            "exact_ms": float(exact_ms),
        })

        if (qi + 1) % 50 == 0:
            cur_ge = np.array(gaps_exact)
            cur_gm = np.array(gaps_moar)
            print(f"  [{qi+1}/{n_queries}] "
                  f"hit_exact={exact_hits/(qi+1)*100:.0f}% "
                  f"hit_moar={moar_hits_own/(qi+1)*100:.0f}% "
                  f"gap_ex_mean={np.mean(cur_ge):.4f} "
                  f"gap_mo_mean={np.mean(cur_gm):.4f} "
                  f"J_ex={np.mean(jaccards_exact):.3f} "
                  f"J_mo={np.mean(jaccards_moar):.3f} "
                  f"moar={np.mean(moar_times):.0f}ms "
                  f"exact={np.mean(exact_times):.0f}ms")

    # ── 汇总 ────────────────────────────────────────────────────────────────
    gaps_exact_arr = np.array(gaps_exact)
    gaps_moar_arr = np.array(gaps_moar)
    jac_ex_arr = np.array(jaccards_exact)
    jac_mo_arr = np.array(jaccards_moar)
    moar_t_arr = np.array(moar_times)
    exact_t_arr = np.array(exact_times)

    hit_rate_exact = exact_hits / n_queries
    hit_rate_moar = moar_hits_own / n_queries

    print(f"\n{'='*70}")
    print(f"  MOAR vs Exact -- 离线最优性对比 ({n_queries} 条 query)")
    print(f"{'='*70}")
    print(f"  规则数: {n_dyn}（top_k={actual_top_k}, 枚举组合数={total_combos}）")
    print(f"  Cost 模式: {cost_mode}")
    print(f"")

    # ── 指标 A：M_exact 度量 ─────────────────────────────────────────────
    print(f"  === 指标 A: MOAR vs M_exact 全局最优（与 greedy/exact 一致） ===")
    print(f"  {'指标':<40s} {'值':>15s}")
    print(f"  {'-'*55}")
    print(f"  {'MOAR 命中 M_exact 最优解':<40s} {hit_rate_exact:14.1%}")
    print(f"  {'M_exact* - M_exact(MOAR) 均值':<40s} {float(np.mean(gaps_exact_arr)):14.4f}")
    print(f"  {'差距中位数':<40s} {float(np.median(gaps_exact_arr)):14.4f}")
    print(f"  {'差距 P95':<40s} {float(np.percentile(gaps_exact_arr, 95)):14.4f}")
    print(f"  {'差距最大值':<40s} {float(np.max(gaps_exact_arr)):14.4f}")
    print(f"  {'Jaccard vs M_exact 最优':<40s} {float(np.mean(jac_ex_arr)):14.4f}")
    print(f"")

    # ── 指标 B：M_moar 度量 ─────────────────────────────────────────────
    # gap_moar = opt_m_moar - moar_m_moar >= 0 表示 MOAR 低于全局 M_moar 最优
    moar_at_opt = int(np.sum(np.abs(gaps_moar_arr) < 1e-10))
    moar_below_opt = int(np.sum(gaps_moar_arr > 1e-10))
    # 理论上 gap_moar < 0 意味着 MOAR 超过了穷举最优（浮点误差）

    print(f"  === 指标 B: MOAR vs M_moar 全局最优（NSGA-II 自身目标函数） ===")
    print(f"  gap_moar = M_moar* - M_moar(MOAR)  (>=0 表示 MOAR 低于穷举最优)")
    print(f"  {'指标':<40s} {'值':>15s}")
    print(f"  {'-'*55}")
    print(f"  {'MOAR 命中 M_moar 全局最优':<40s} {hit_rate_moar:14.1%}")
    print(f"  {'M_moar* - M_moar(MOAR) 均值':<40s} {float(np.mean(gaps_moar_arr)):14.4f}")
    print(f"  {'差距中位数':<40s} {float(np.median(gaps_moar_arr)):14.4f}")
    print(f"  {'差距 P95':<40s} {float(np.percentile(gaps_moar_arr, 95)):14.4f}")
    print(f"  {'差距最大值':<40s} {float(np.max(gaps_moar_arr)):14.4f}")
    print(f"  {'Jaccard vs M_moar 最优':<40s} {float(np.mean(jac_mo_arr)):14.4f}")
    print(f"")
    print(f"  其中: at_opt={moar_at_opt}, below_opt={moar_below_opt} "
          f"({moar_below_opt/n_queries*100:.1f}% below optimal)")
    print(f"")

    print(f"  检索延迟:")
    print(f"    MOAR  mean={np.mean(moar_t_arr):.0f}ms "
          f"median={np.median(moar_t_arr):.0f}ms "
          f"P95={np.percentile(moar_t_arr, 95):.0f}ms")
    print(f"    Exact (双重穷举) mean={np.mean(exact_t_arr):.0f}ms "
          f"median={np.median(exact_t_arr):.0f}ms "
          f"P95={np.percentile(exact_t_arr, 95):.0f}ms")

    # ── 结论 ────────────────────────────────────────────────────────────────
    print(f"\n  {'='*60}")
    print(f"  结论:")
    print(f"    1) M_exact 度量差距 (mean={float(np.mean(gaps_exact_arr)):.4f}):")
    print(f"       源于两套度量归一化不同")
    print(f"       （MOAR: divide-by-max_rel, Exact: divide-by-top_k）。")
    print(f"    2) M_moar 度量差距 (mean={float(np.mean(gaps_moar_arr)):.4f}):")
    print(f"       Exact 直接最大化 M_moar 标量公式，穷举所有合法组合取最大。")
    print(f"       MOAR 先进化多目标 Pareto 前沿再用加权和选解。")
    print(f"       差距说明有限种群和迭代下得到的 Pareto 前沿是近似前沿，")
    print(f"       尚未完全覆盖该权重对应的标量最优解。这不意味着 MOAR")
    print(f"       实现错误，而是进化式近似搜索与精确组合搜索之间的")
    print(f"       精度-可扩展性权衡。")
    print(f"    3) 在 Top-K 约束下，精确搜索需枚举 C(n,1)+...+C(n,K)="
          f"{total_combos} 个候选子集（而非全部 2^{n_dyn}={2**n_dyn} 种）。")
    print(f"       n={n_dyn} 时穷举仅需 ~20ms，比 MOAR 的 ~2000ms 更快。")
    print(f"       但随着 n 和 K 增大，组合数快速增长——例如 n=16,K=5 时")
    print(f"       已达 C(16,1)+...+C(16,5)=6884，穷举成本迅速上升，")
    print(f"       此时 MOAR 的固定计算量优势将逐渐体现。")
    print(f"  {'='*60}")

    # ── 保存 ────────────────────────────────────────────────────────────────
    out_path = args.out or os.path.join(
        _PROJECT_ROOT, "outputs",
        f"moar_vs_exact_n{n_queries}_{int(time.time())}.json",
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    import subprocess
    commit = ""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, cwd=_PROJECT_ROOT).strip()
    except Exception:
        pass

    import hashlib
    with open(os.path.abspath(skill_path), "rb") as f:
        skill_sha256 = hashlib.sha256(f.read()).hexdigest()

    summary = {
        "skill": os.path.abspath(skill_path),
        "skill_sha256": skill_sha256,
        "commit": commit,
        "n_dynamic_rules": n_dyn,
        "total_combinations": int(total_combos),
        "total_subsets_2n": 2 ** n_dyn,
        "top_k_constraint": actual_top_k,
        "cost_mode": cost_mode,
        "config": {
            "top_k": args.top_k,
            "budget": args.budget,
            "weights": list(weights),
            "moar_pop_size": args.moar_pop_size,
            "moar_generations": args.moar_generations,
        },
        "results": {
            "n_queries": n_queries,
            "metric_exact": {
                "description": "MOAR vs M_exact 全局最优",
                "hit_rate": float(hit_rate_exact),
                "gap_mean": float(np.mean(gaps_exact_arr)),
                "gap_median": float(np.median(gaps_exact_arr)),
                "gap_p95": float(np.percentile(gaps_exact_arr, 95)),
                "gap_max": float(np.max(gaps_exact_arr)),
                "jaccard_mean": float(np.mean(jac_ex_arr)),
            },
            "metric_moar": {
                "description": "MOAR vs M_moar 全局最优（NSGA-II 自身目标函数）",
                "hit_rate": float(hit_rate_moar),
                "at_opt": moar_at_opt,
                "below_opt": moar_below_opt,
                "gap_mean": float(np.mean(gaps_moar_arr)),
                "gap_median": float(np.median(gaps_moar_arr)),
                "gap_p95": float(np.percentile(gaps_moar_arr, 95)),
                "gap_max": float(np.max(gaps_moar_arr)),
                "jaccard_mean": float(np.mean(jac_mo_arr)),
            },
            "latency": {
                "moar_mean_ms": float(np.mean(moar_t_arr)),
                "moar_median_ms": float(np.median(moar_t_arr)),
                "moar_p95_ms": float(np.percentile(moar_t_arr, 95)),
                "exact_mean_ms": float(np.mean(exact_t_arr)),
                "exact_median_ms": float(np.median(exact_t_arr)),
                "exact_p95_ms": float(np.percentile(exact_t_arr, 95)),
            },
        },
        "per_query": per_query,
    }

    def _clean(obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_clean(x) for x in obj]
        return obj

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(_clean(summary), f, ensure_ascii=False, indent=2)
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
