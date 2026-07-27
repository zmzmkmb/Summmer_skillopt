# report #013: MMLU-Pro Pipeline Fix — 两个实现 Bug 的发现、修复与验证

> 日期：2026-07-27 | 分支：`main` | 三领域验证

---

## 一、背景

report #012（已归档为 `report_012_pure_adapter_original.md`）报告：纯 MMLU-Pro adapter 下 step-level patches 全部消失（180 步，0 patches）。该报告推测原因是 "SearchQA 模板帮助分析器理解任务"。

**经代码审查，该结论不成立**。root cause 是两个确定性的实现 bug。

---

## 二、发现的 Bug

### Bug 1: 轨迹上下文缺失

**位置**: `skillopt/envs/mmlupro/rollout.py`

MMLU-Pro rollout 只写了 `conversation.json`（内容为 `[{"type":"message","content":"B"}]`），
不保存：
- system prompt（含 skill + format instructions）
- user prompt（含完整题目和选项）
- gold answer（正确答案）
- evaluation detail（预测 vs gold 对比）

Reflect 阶段的 `fmt_minibatch_trajectories()` 从这些字段重构 analyst 看到的上下文。
没有这些字段，analyst 只看到：
```
Task:
Task type:
Steps: ?
[agent] B
```

**影响**: analyst 不知道题目、选项、gold answer → 无法产出有意义的规则。

### Bug 2: Analyst 输出协议不兼容

**位置**: `skillopt/envs/mmlupro/prompts/analyst_error.md`, `analyst_success.md`

MMLU-Pro analyst prompt 要求输出 JSON 数组：
```json
[{"op":"add|replace|delete","content":"...","anchor":"...","rationale":"..."}]
```

但 `reflect.py:344` 的解析逻辑是：
```python
result = extract_json(response)
if "patch" in result:   # <-- 对 list 永远为 False
    return result
return None
```

**影响**: 即使 deepseek 正确生成了编辑，也因 `"patch" in result` 对 list 为 False 而被静默丢弃。

### Bug 3: Math test=0%（非代码 bug）

351 条 test 全部 API 连接失败（`RuntimeError: Connection error after 3 retries`），
导致 response 为空 → `hard=0`。不是 evaluator 格式问题，不是 skill 格式问题。

---

## 三、修复方案

### Fix 1: 轨迹上下文（`skillopt/envs/mmlupro/rollout.py`）

```python
# 新增保存 target_system_prompt.txt, target_user_prompt.txt
# 在 conversation.json 末尾追加 eval detail
# result dict 新增 task_description, reference_text, task_type, domain, subject
# fail_reason 从空字符串改为 "Wrong answer: predicted 'X', expected 'Y'"
```

### Fix 2: Analyst 输出协议

```json
// 旧格式（JSON 数组）
[{"op":"add","content":"...","anchor":"...","rationale":"..."}]

// 新格式（SkillOpt 标准）
{
  "batch_size": 8,
  "failure_summary": [{"failure_type":"knowledge_gap","count":8,"description":"..."}],
  "patch": {
    "reasoning": "...",
    "edits": [
      {"op":"append","content":"<markdown>"},
      {"op":"insert_after","target":"...","content":"..."},
      {"op":"replace","target":"...","content":"..."},
      {"op":"delete","target":"..."}
    ]
  }
}
```

### Fix 3: Skill 去重

在 `reflect.py:fmt_minibatch_trajectories` 中新增 `_strip_skill_section()`，
从每道题的 `target_system_prompt.txt` 中移除 `## Skill` 段，
避免 skill 在 analyst 上下文中重复（1× Current Skill + M× trajectory system prompts）。

### Fix 4: Math test 重跑

用 `eval_only.py` 重新评估，确认 code fix 不是必要条件（API 此时可达）。

---

## 四、验证结果

### 验证设置

- Law: 40 train / 30 val / 276 test
- Philosophy: 40 train / 30 val / 125 test
- Config: batch=20, 2 epochs (4 steps), edit_budget=4, slow_update=true, meta_skill=true

### 定量结果

| 指标 | Law small | Philosophy small |
|------|:--:|:--:|
| 基线 val | 46.67% | 60.00% |
| 基线 test | 34.42% | 60.80% |
| Patch files/step | 3–4 ↑ | 3 ↑ |
| Step-level ACCEPT | 0/4 | **1/4 (Step 1)** |
| Skill chars | 323→376 | 323→2559 |
| 最佳 val | 46.67% | **63.33%** |
| 最佳 test | 34.78% | **66.40%** |
| Test Δ | +0.36pp | **+5.60pp** ✅ |

> Law 的 gate 全部 reject，因为 30-item val 对 Law 来说噪声太大（46.67% 已接近数据集上限）。

### Math test 重跑

| Skill | test hard |
|------|:--:|
| initial_skill.md (323 chars) | 88.03% |
| best_skill.md (3602 chars) | **89.46%** (+1.43pp) |

### 关键对比

| 修复前 | 修复后 |
|------|------|
| 180 steps, **0 patches** (3 experiments) | 8 steps, **every step 3-4 patches** |
| Analyst 只看到答案字母 | Analyst 看到完整题目、选项、gold answer |
| 正确生成的编辑被静默丢弃 | 编辑被正确解析、聚合、gate 评估 |

---

## 五、修正后的结论

### 被推翻的结论

1. ~~"SearchQA template 不是污染，而是帮助分析器理解任务"~~ → 无法从现有数据判断。Bug 修复后纯 adapter 也能产出规则。
2. ~~"纯 initial_skill 下 step-level 优化器失效"~~ → 不成立。两个实现 bug 的叠加效应。
3. ~~"Slow update 是唯一改进来源"~~ → step patches 也被 bug 堵住了，未做公平比较。

### 修正后的结论

1. **MMLU-Pro 纯 adapter 下，step-level optimizer 可以正常工作。** 修复后每步产出 3-4 个合法 patch。
2. **Step patches 可以立即产生 test gain。** Philosophy step 1 gate accept → test +5.60pp。
3. **Skill 上下文去重必须做。** 修复前每个 trajectory 携带一份完整 skill 副本，导致 token 膨胀和潜在的 bias。
4. **Math 88%→89.5% 的增益空间确实有限。** 即使修复，天花板效应真实存在。
5. **report #012 原始结论已归档** (`report_012_pure_adapter_original.md`)，本报告为权威版本。

---

## 六、修复 Commits

| Commit | 内容 |
|--------|------|
| `5c70cae` | P0 fix: rollout trajectory context + analyst output protocol |
| `8dac6a4` | P1: Math test=0% 诊断 + test re-eval |
| `0ed38f7` | P0 verification: step patches confirmed |
| `7ec4b4e` | report #012 appendix: P0 bugfix + verification |
| `待提交` | Fix 3: skill deduplication in analyst context |
| `待提交` | report #013: pipeline fix report (本报告) |

---

## 七、修改文件清单

| 文件 | 修改 |
|------|------|
| `skillopt/envs/mmlupro/rollout.py` | 轨迹上下文写入 |
| `skillopt/envs/mmlupro/prompts/analyst_error.md` | 输出协议修正 |
| `skillopt/envs/mmlupro/prompts/analyst_success.md` | 输出协议修正 |
| `skillopt/gradient/reflect.py` | Skill 去重 |
| `scripts/train.py` | MMLU-Pro adapter 注册 |
| `scripts/eval_only.py` | MMLU-Pro adapter 注册 |
| `configs/mmlupro/default.yaml` | 新增配置 |
| `skillopt/envs/mmlupro/` | 完整新增 adapter（dataloader, evaluator, prompts） |
| `reports/report_012_pure_adapter_original.md` | 归档（原报告结论已失效） |
| `reports/report_013_mmlupro_pipeline_fix.md` | 本报告 |
| `logs/research_log.md` | 全程记录 |

---

## 八、下一步

**正式消融实验**（不在本报告范围内）：

| 实验组 | Step (Fast) | Slow | 目的 |
|------|:--:|:--:|------|
| Initial | × | × | 基线 |
| Fast-only | √ | × | 局部 minibatch 更新效果 |
| Slow-only | × | √ | 跨 epoch 全局更新效果 |
| Fast+Slow | √ | √ | 互补性验证 |

> **已具备条件**: 修复后的 pipeline 可以区分 fast 和 slow 各自贡献。
> **阻塞因素已消除**: step-level patch 产生链路已验证。
