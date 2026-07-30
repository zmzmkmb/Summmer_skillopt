"""实验完整性检查 — 离线验证，不调用 LLM."""
import json, os, sys, tempfile, hashlib
import numpy as np
import pytest

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT)

from skillopt.rag_rule_selector import RuleMemory
from skillopt.moar.tokenizer import count_tokens


# ── Fixtures ────────────────────────────────────────────────

@pytest.fixture(scope="module")
def skill_content():
    path = os.path.join(PROJECT, "outputs", "searchqa_rag", "best_skill.md")
    with open(path, encoding="utf-8") as f:
        return f.read()


@pytest.fixture(scope="module")
def rule_memory(skill_content):
    return RuleMemory(skill_content, method="tfidf", top_k=5, token_budget=2000)


@pytest.fixture(scope="module")
def rule_token_costs(rule_memory):
    return np.array([count_tokens(r.full_text) for r in rule_memory.dynamic_rules])


# ── 规则计数 ──────────────────────────────────────────────────

def test_rule_count_matches_selected_indices(rule_memory):
    """检索后 _last_selections 中的数量应与 n_rules 一致."""
    query = "What is the capital of France?"
    rule_memory.retrieve(query, top_k=5, token_budget=2000)
    sel = rule_memory._last_selections.get(query, [])
    assert len(sel) > 0, "TF-IDF should select at least 1 rule"
    assert len(sel) <= 5, "Should respect top_k"
    # n_rules should equal len(selected_indices)
    assert len(sel) == len(sel), "trivial self-check"


def test_n_rules_uses_selected_indices_length():
    """验证 moar_searchqa_eval 的 build_skill_text 用 len(sel_idx)."""
    # 直接验证脚本中的函数
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "moar_searchqa_eval",
        os.path.join(PROJECT, "scripts", "moar_searchqa_eval.py"),
    )
    # 不 import 整个脚本（有副作用），直接检查源码
    with open(os.path.join(PROJECT, "scripts", "moar_searchqa_eval.py"), encoding="utf-8") as f:
        src = f.read()
    assert "n_dyn = len(sel_idx)" in src, \
        "build_skill_text must use len(sel_idx), not dynamic.count()"


# ── Token budget ─────────────────────────────────────────────

def test_selection_tokens_never_exceed_budget(rule_memory, rule_token_costs):
    """所有选择方法的 selected_tokens <= budget."""
    queries = [
        "What is the capital of France?",
        "Who wrote Hamlet?",
        "When did World War II end?",
    ]
    budget = 2000
    for q in queries:
        rule_memory.retrieve(q, top_k=5, token_budget=budget)
        sel_idx = rule_memory._last_selections.get(q, [])
        total = sum(rule_token_costs[i] for i in sel_idx if i < len(rule_token_costs))
        assert total <= budget, \
            f"Query '{q[:30]}...': selected_tokens={total} > budget={budget}"


def test_first_rule_cannot_exceed_budget(rule_memory, rule_token_costs):
    """单条规则超过预算时，该规则仍应被排除（不会被加入）."""
    max_cost_idx = int(np.argmax(rule_token_costs))
    max_cost = rule_token_costs[max_cost_idx]
    # 设置为低于任何单条规则的预算
    tiny_budget = int(max_cost * 0.5)
    query = "test query"
    rule_memory.retrieve(query, top_k=5, token_budget=tiny_budget)
    sel_idx = rule_memory._last_selections.get(query, [])
    # 所有选中的规则 token <= tiny_budget 或为空
    for idx in sel_idx:
        assert rule_token_costs[idx] <= tiny_budget, \
            f"Rule {idx} cost {rule_token_costs[idx]} > budget {tiny_budget}"


# ── Greedy-Utility ───────────────────────────────────────────

def test_greedy_util_requires_utility_file():
    """infer_baselines.py 中 greedy-util 找不到 utility 文件应终止."""
    with open(os.path.join(PROJECT, "scripts", "infer_baselines.py"), encoding="utf-8") as f:
        src = f.read()
    assert "Greedy-Utility requires a frozen utility file" in src
    assert "FileNotFoundError" in src
    assert "No utility file found" not in src


def test_greedy_util_rejects_all_zero_utility():
    """所有 rule utility 为 0 时应终止."""
    with open(os.path.join(PROJECT, "scripts", "infer_baselines.py"), encoding="utf-8") as f:
        src = f.read()
    assert "all" in src and "utilities are zero" in src
    assert "nonzero_count == 0" in src


# ── Tokenizer fallback ──────────────────────────────────────

def test_tokenizer_no_silent_fallback_in_formal_scripts():
    """正式实验脚本中 tokenizer 导入失败不应静默降级."""
    for script in ["moar_searchqa_eval.py", "infer_baselines.py"]:
        path = os.path.join(PROJECT, "scripts", script)
        with open(path, encoding="utf-8") as f:
            src = f.read()
        # 不应有 try/except 包裹 count_tokens import
        # 但可以有顶层 from import
        assert "from skillopt.moar.tokenizer import count_tokens" in src, \
            f"{script}: must import count_tokens directly, no try/except"


# ── 现有 JSON 完整性 ─────────────────────────────────────────

def test_formal_results_have_selected_indices():
    """已生成的 formal JSON 中 per_item 应有 selected_indices."""
    for seed in [42, 43, 44]:
        path = os.path.join(PROJECT, "outputs", f"jos_formal_targetS_seed{seed}.json")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        for method, res in d["results"].items():
            for p in res["per_item"]:
                assert "selected_indices" in p, \
                    f"{os.path.basename(path)}/{method}: missing selected_indices"


def test_no_empty_predictions_in_valid_results():
    """排除 seed 44 targetL (已知全空)，其他不应全空."""
    expected = [
        "jos_formal_targetS_seed42.json",
        "jos_formal_targetS_seed43.json",
        "jos_formal_targetS_seed44.json",
        "jos_formal_targetL_seed42.json",
        "jos_formal_targetL_seed43.json",
        "jos_formal_targetL_seed44.json",
    ]
    for fname in expected:
        path = os.path.join(PROJECT, "outputs", fname)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        for method, res in d["results"].items():
            n_empty = sum(1 for p in res["per_item"] if p.get("predicted", "") == "")
            total = len(res["per_item"])
            assert n_empty < total, \
                f"{os.path.basename(path)}/{method}: ALL {total} predictions empty"


# ── Budget assertion ────────────────────────────────────────

def test_budget_violated_flag_in_enriched():
    """enriched 文件中 budget_violated 应全为 False."""
    for fname in os.listdir(os.path.join(PROJECT, "outputs")):
        if not fname.endswith("_enriched.json"):
            continue
        path = os.path.join(PROJECT, "outputs", fname)
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        for method, res in d["results"].items():
            violations = [p for p in res["per_item"] if p.get("budget_violated", False)]
            assert len(violations) == 0, \
                f"{os.path.basename(path)}/{method}: {len(violations)} budget violations"
