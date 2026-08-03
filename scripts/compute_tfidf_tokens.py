#!/usr/bin/env python3
"""离线补算 TF-IDF 检索的 Token 消耗，并与 Full Skill 对比降幅。

不调 API、无随机性（TF-IDF 确定性）。
从 formal JSON 读 sample_id → HuggingFace 取问题 → TF-IDF 检索 → tiktoken 计数。

用法::

    python scripts/compute_tfidf_tokens.py
    python scripts/compute_tfidf_tokens.py --seed 42 --top-k 5 --budget 2000
    python scripts/compute_tfidf_tokens.py --output tfidf_token_report.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

PROJECT = Path(__file__).resolve().parent.parent

# ── skill 文件候选位置 ──────────────────────────────────────────────
SKILL_CANDIDATES = [
    PROJECT / "outputs" / "searchqa_rag" / "best_skill.md",
    Path("E:/桌面/暑期实训/SkillOpt/outputs/searchqa_rag/best_skill.md"),
    PROJECT / "outputs" / "rule_libraries" / "rules_0024.md",
    PROJECT / "ckpt" / "searchqa" / "gpt5.5_skill.md",
]

# ── formal JSON 候选（优先 enriched 版，否则用原始版） ─────────────
FORMAL_JSON_CANDIDATES = [
    PROJECT / "artifacts" / "jos_experiment_v1" / "targetS" / "jos_formal_targetS_seed42_enriched.json",
    PROJECT / "outputs" / "jos_formal_targetS_seed42.json",
]


def find_file(candidates: list[Path], label: str) -> Path:
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError(
        f"找不到 {label}。候选路径:\n  " + "\n  ".join(str(c) for c in candidates)
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--skill", type=Path, default=None, help="skill markdown 文件路径（自动检测）")
    p.add_argument("--formal-json", type=Path, default=None, help="formal 实验 JSON 路径（自动检测）")
    p.add_argument("--dataset", default="lucadiliello/searchqa", help="HuggingFace dataset")
    p.add_argument("--top-k", type=int, default=5, help="TF-IDF 检索规则数 (default: 5)")
    p.add_argument("--budget", type=int, default=2000, help="Token 预算 (default: 2000)")
    p.add_argument("--output", type=Path, default=None, help="输出报告路径（可选 .md 或 .json）")
    p.add_argument("--encoding", default="cl100k_base", help="tiktoken encoding (default: cl100k_base)")
    return p.parse_args()


def load_questions_from_hf(dataset_name: str, sample_ids: list[str]) -> dict[str, str]:
    """从 HuggingFace 加载指定 sample_id 的问题文本。"""
    print(f"  加载 {dataset_name} ...", flush=True)
    from datasets import load_dataset
    ds = load_dataset(dataset_name)
    # SearchQA 的 split: train/val/test
    id_to_question: dict[str, str] = {}
    wanted = set(sample_ids)
    for split_name in ds:
        for row in ds[split_name]:
            key = str(row.get("key", ""))
            if key in wanted:
                id_to_question[key] = row["question"]
    missing = wanted - set(id_to_question)
    if missing:
        print(f"  ⚠ 警告: {len(missing)} 个 sample_id 未在数据集中找到", flush=True)
    return id_to_question


def main() -> None:
    args = parse_args()

    # ── 1. 加载 skill 文件 ──────────────────────────────────────────
    skill_path = args.skill or find_file(SKILL_CANDIDATES, "skill 文件")
    print(f"[1/5] Skill: {skill_path}", flush=True)
    skill_content = skill_path.read_text(encoding="utf-8")

    # ── 2. 加载 formal JSON ─────────────────────────────────────────
    json_path = args.formal_json or find_file(FORMAL_JSON_CANDIDATES, "formal JSON")
    print(f"[2/5] Formal JSON: {json_path}", flush=True)
    formal = json.loads(json_path.read_text(encoding="utf-8"))
    # 取 TF-IDF 或 Core Only 的 per_item 拿 sample_id
    results = formal["results"]
    first_method = list(results.values())[0]
    per_items = first_method["per_item"]
    sample_ids = [p["sample_id"] for p in per_items]
    print(f"  {len(sample_ids)} questions", flush=True)

    # ── 3. 加载问题文本 ────────────────────────────────────────────
    print(f"[3/5] 加载问题 ...", flush=True)
    id_to_q = load_questions_from_hf(args.dataset, sample_ids)
    questions = [id_to_q[sid] for sid in sample_ids if sid in id_to_q]
    matched_ids = [sid for sid in sample_ids if sid in id_to_q]
    if len(questions) != len(sample_ids):
        print(f"  ⚠ 匹配 {len(questions)}/{len(sample_ids)} 题", flush=True)
    else:
        print(f"  ✓ {len(questions)} 题全部匹配", flush=True)

    # ── 4. 构建 RuleMemory + TF-IDF 检索 ───────────────────────────
    print(f"[4/5] TF-IDF 检索 (top_k={args.top_k}, budget={args.budget}) ...", flush=True)
    from skillopt.rag_rule_selector import RuleMemory
    from skillopt.moar.tokenizer import count_tokens

    rm = RuleMemory(skill_content, top_k=args.top_k,
                     token_budget=args.budget, method="tfidf")

    core_text = rm.core_rules_text
    core_tokens = count_tokens(core_text) if core_text else 0
    full_tokens = count_tokens(skill_content)
    full_chars = len(skill_content)

    print(f"  ├─ 总规则: {rm.n_total} (Core: {rm.n_core}, Dynamic: {rm.n_dynamic})", flush=True)
    print(f"  ├─ Full Skill: {full_chars:,} chars / {full_tokens:,} tokens", flush=True)
    print(f"  ├─ Core Only:  {len(core_text):,} chars / {core_tokens:,} tokens", flush=True)

    per_question_tokens: list[int] = []
    per_question_n_rules: list[int] = []
    separator_cost = 2  # "\n\n" 的 token 近似

    for i, q in enumerate(questions):
        retrieved = rm.retrieve(q, top_k=args.top_k, token_budget=args.budget)
        n_selected = len(rm._last_selections.get(q, []))
        if retrieved:
            active = core_text + "\n\n" + retrieved if core_text else retrieved
        else:
            active = core_text
        tok = count_tokens(active)
        per_question_tokens.append(tok)
        per_question_n_rules.append(n_selected)
        if (i + 1) % 50 == 0:
            print(f"  ... {i+1}/{len(questions)}", flush=True)

    tok_arr = np.array(per_question_tokens)
    rules_arr = np.array(per_question_n_rules)

    print(f"  └─ 检索完成", flush=True)

    # ── 5. 汇总 ─────────────────────────────────────────────────────
    print(f"[5/5] 汇总报告", flush=True)
    avg_active = float(np.mean(tok_arr))
    median_active = float(np.median(tok_arr))
    avg_rules = float(np.mean(rules_arr))
    core_ratio = (1 - core_tokens / full_tokens) * 100
    saving_ratio = (1 - avg_active / full_tokens) * 100

    report_lines = [
        "",
        "=" * 60,
        "  TF-IDF Token 消耗离线统计报告",
        "=" * 60,
        "",
        f"Skill 文件: {skill_path}",
        f"实验数据:  {json_path}",
        f"问题数:    {len(questions)}",
        f"检索参数:  top_k={args.top_k}, budget={args.budget} tokens",
        "",
        "── 规则结构 ──",
        f"  总规则数:        {rm.n_total}",
        f"  核心规则 (Core): {rm.n_core}",
        f"  动态规则 (Dyn):  {rm.n_dynamic}",
        "",
        "── Token 消耗对比 ──",
        f"  Full Skill (全部规则):         {full_tokens:>6,} tokens  ({full_chars:>6,} chars)",
        f"  Core Only (仅核心规则):        {core_tokens:>6,} tokens  ({len(core_text):>6,} chars)",
        f"  TF-IDF Top-{args.top_k} (核心+检索):       {avg_active:>6.0f} tokens  (均值)",
        f"  TF-IDF Top-{args.top_k} 中位数:            {median_active:>6.0f} tokens",
        "",
        "── 降幅分析 ──",
        f"  Core vs Full 节省:      {core_ratio:.1f}%",
        f"  RAG (TF-IDF) vs Full 节省: {saving_ratio:.1f}%",
        f"  平均检索规则数:          {avg_rules:.1f} / {args.top_k}",
    ]

    # ── 尝试读取 BM25/MOAR 数据做横向对比 ────────────────────────
    try:
        bm25_file = json_path.parent / "jos_formal_bm25_rep42.json"
        if bm25_file.exists():
            bm25 = json.loads(bm25_file.read_text(encoding="utf-8"))
            bm25_tok = bm25.get("avg_selected_tokens", bm25.get("avg_chars", None))
            report_lines.append("")
            report_lines.append("── 横向对比（同 200 题）──")
            report_lines.append(f"  TF-IDF Top-5 (本脚本):    {avg_active:>6.0f} tokens (均值)")
            # 从 enriched JSON 读 MOAR
            for method_name in ["Core Only", "TF-IDF Top-5", "MOAR"]:
                if method_name in results:
                    r = results[method_name]
                    val = r.get("avg_selected_tokens") or r.get("avg_chars", 0)
                    label = f"  {method_name}:"
                    report_lines.append(f"  {label:<28s} {val:>6.0f} (来自 enriched JSON)")
    except Exception:
        pass

    report_lines += [
        "",
        "── 结论 ──",
        f"  TF-IDF 原子化检索将 Agent skill 上下文从 {full_tokens:,} tokens 压缩",
        f"  到约 {avg_active:.0f} tokens（均值），节省 {saving_ratio:.1f}%。",
        f"  在 {args.budget}-token 预算下，平均选中 {avg_rules:.1f} 条动态规则。",
        "",
    ]

    report = "\n".join(report_lines)
    print(report)

    # ── 输出到文件 ────────────────────────────────────────────────
    if args.output:
        out = args.output
        if out.suffix == ".json":
            out_data = {
                "skill_path": str(skill_path),
                "n_questions": len(questions),
                "top_k": args.top_k,
                "budget": args.budget,
                "n_total_rules": rm.n_total,
                "n_core": rm.n_core,
                "n_dynamic": rm.n_dynamic,
                "full_skill_tokens": full_tokens,
                "full_skill_chars": full_chars,
                "core_only_tokens": core_tokens,
                "tfidf_active_tokens_mean": avg_active,
                "tfidf_active_tokens_median": median_active,
                "tfidf_avg_rules_selected": avg_rules,
                "saving_vs_full_pct": saving_ratio,
                "per_question_tokens": per_question_tokens,
                "per_question_n_rules": per_question_n_rules,
            }
            out.write_text(json.dumps(out_data, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            out.write_text(report, encoding="utf-8")
        print(f"\n报告已保存: {out}")


if __name__ == "__main__":
    main()
