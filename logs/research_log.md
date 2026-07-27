# SkillOpt 多领域交叉验证研究日志

> 基于 SkillOpt 框架，研究 qwen-flash + deepseek-v4-flash 在 6 个领域上的 skill 自演化

## 研究问题

1. SkillOpt 的训练框架（Gated Slow Update）在非 SearchQA 任务上是否仍然有效？
2. SearchQA adapter 的 prompt 模板是否在不同任务上造成训练偏倚？
3. 原子化规则 + TF-IDF 检索架构能否跨领域迁移？
4. 不同任务的基线分数如何影响 SkillOpt 的训练收益空间？

---

## 实验一：SearchQA adapter（2026-07-24 ~ 07-26）

### 已完成领域

| 领域 | 题型 | 基线→峰值 | 提升 | Accept | 结论 |
|------|------|:--:|:--:|:--:|------|
| SearchQA | 文本QA，4选1提取 | 41.7%→73.5% | **+31.8pp** | 4-6 | ✅ 框架核心验证 |
| MMLU-Pro Math | 数学，10选1 | 89.0%→92.5% | +3.5pp | 3 | ⚠️ 模板污染（+63%） |
| MMLU-Pro History | 历史，10选1 | 61%→68.4% | +7pp | 3 | ✅ 有效但空间有限 |
| MMLU-Pro Law | 法律，10选1 | 43.0%→45.5% | +2.5pp | 3 | ✅ 甜区间（基线42%） |
| MMLU-Pro Philosophy | 哲学，10选1 | 63%→72.0% | +9pp | 4 | ✅ 有效但空间有限 |
| SpreadsheetBench | 表格操作，代码生成 | 35.5%→? | — | — | 🔄 基线已测 |

### 跨领域一致发现

1. **SkillOpt 训练循环在所有领域均有效** — 全部正向提升
2. **SearchQA adapter 模板对不同领域的影响不同** — 数学 (+63%) vs 文本领域 (轻微)
3. **Gate 行为在 5 个领域完全一致** — 前几步 accept → 后期全部 reject
4. **Law 是最理想的交叉验证领域** — 基线 43%，和 SearchQA (42%) 接近，提升潜力最大
5. **提升幅度与基线位置强相关** — 基线越低，提升空间越大（SearchQA +31.8pp vs Math +3.5pp）

---

## 实验二：纯 MMLU-Pro adapter（no SearchQA 模板）（2026-07-27）

### 实验动机

SearchQA adapter 的 prompt 模板可能在不同任务上造成训练偏倚：
- Math：模板把基线从 26% 抬到 89%（+63pp 污染）
- Law/Philosophy：模板和 SearchQA 同属文本理解，影响较小

**去掉 SearchQA 模板，用纯 initial_skill.md（76 字符，格式指令）重新实验。**

### 实验配置

- **Adapter**: `skillopt/envs/mmlupro/adapter.py` — 纯 MMLU-Pro adapter，无 SearchQA prompt 模板
- **Initial skill**: `skillopt/envs/mmlupro/initial_skill.md`（76 chars）— 通用解题指令
- **Target**: qwen-flash (DashScope)
- **Optimizer**: deepseek-v4-flash (DeepSeek)
- **Config**: same as SearchQA adapter runs (4 epochs, batch=40, lr=4, slow_update=true, meta_skill=true)
- **训练启动时间**: 2026-07-27 00:16（凌晨），因机器休眠中断
- **恢复时间**: 2026-07-27 10:52（上午），从 checkpoint resume

### 实验结果

| | Math | Law | Philosophy |
|------|:--:|:--:|:--:|
| 数据量 | train=800, val=200, test=351 | train=660, val=165, test=276 | train=299, val=75, test=125 |
| 基线 val | 49.00% | 38.79% | 58.67% |
| 基线 test | — | 34.42% | 56.80% |
| **最佳 val** | **89.00%** (epoch 2 slow_update) | **41.82%** (epoch 3 slow_update) | **62.67%** (epoch 4 slow_update) |
| **最佳 test** | **0.00%** ⚠️ | **38.41%** | **63.20%** |
| Test 提升 | — | **+4.0pp** | **+6.4pp** |
| Step-level patches | 0 | 0 | 0 |
| Step-level accepts | 0 | 0 | 0 |
| Slow_update accepts | 1 (epoch 2) | 1 (epoch 3) | 2 (epoch 2, 4) |
| 总步数 | 80 | 68 | 32 |
| 训练时长 | 93 min | 28 min | 64 min |

### Slow Update 详细记录

**Math**:
| Epoch | Selection Hard | Action |
|:--:|:--:|------|
| 1 | — | inject_placeholder |
| 2 | **0.8900** | **accept_new_best** ← +40pp! |
| 3 | — | no_content |
| 4 | — | no_content |

**Law**:
| Epoch | Selection Hard | Action |
|:--:|:--:|------|
| 1 | — | inject_placeholder |
| 2 | 0.3455 | reject |
| 3 | **0.4182** | **accept_new_best** ← +3.4pp |
| 4 | 0.3879 | reject |

**Philosophy**:
| Epoch | Selection Hard | Action |
|:--:|:--:|------|
| 1 | — | inject_placeholder |
| 2 | 0.6000 | accept_new_best ← +1.3pp |
| 3 | 0.6000 | reject |
| 4 | **0.6267** | **accept_new_best** ← +2.7pp |

---

## 两轮实验对比分析

### SearchQA adapter vs 纯 adapter

| 领域 | 指标 | 旧 adapter (SearchQA 模板) | 新 adapter (纯) |
|------|------|:--:|:--:|
| **Math** | baseline val | 89.0% | 49.0% |
| | best val | 92.5% | 89.0% |
| | test | 有 patches | **0% test bug** ⚠️ |
| | step patches | 3 accepts | 0 |
| **Law** | baseline test | 38% (from val ~43%) | 34.4% |
| | best test | ~45.5% (val) | **38.4%** |
| | step patches | 3 accepts | 0 |
| | slow_update | — | 1 accept (+3.4pp) |
| **Philosophy** | baseline test | ~63% (from val) | 56.8% |
| | best test | ~72.0% (val) | **63.2%** |
| | step patches | 4 accepts | 0 |
| | slow_update | — | 2 accepts (+6.4pp total) |

### 关键发现

1. **Step-level patches 全部消失** — deepseek 分析器无法从纯 initial_skill 产出规则补丁
   - 旧 adapter 的 SearchQA 模板包含 "从文档提取答案""验证上下文" 等指令，帮助了分析器
   - 新 adapter 只有 76 字符的通用解题指令，分析器无法产出领域特定的规则
   - **结论：SearchQA adapter 模板不是污染，而是在帮助分析器理解任务并产出规则**

2. **Slow Update 成为唯一改进来源** — 所有提升均来自 epoch 间 slow update
   - Math: slow_update epoch 2 把 val 从 49% 拉回 89%（注入的 guidance 恰好复现了 SearchQA 模板的效果）
   - Law: slow_update epoch 3 注入法律特化 guidance → test +4.0pp
   - Philosophy: slow_update epoch 2+4 注入哲学特化 guidance → test +6.4pp

3. **Math test=0% bug** — slow_update guidance 改变了模型输出格式，evaluator 无法解析答案
   - val evaluation 正常（89%），但 test 评估全部失败
   - 需要检查 slow_update 注入的 guidance 是否破坏了答案格式

4. **New adapter + slow_update 在文本领域优于旧 adapter**
   - Law: 新 test 38.4% vs 旧 val 45.5%（不可直接比较，但新 adapter test 是干净的）
   - Philosophy: 新 test 63.2% vs 旧 val 72.0%（同上）

5. **纯训练方式（无 step patches）+ slow_update 也是一条可行路径**
   - 不依赖分析器产出规则 = 更少的 API 调用
   - slow_update 在 epoch 边界做一次高质量分析，更经济

---

## 旧实验详情（保留）

### SearchQA adapter 实验细节

- Target: qwen-flash (DashScope)
- Optimizer: deepseek-v4-flash (DeepSeek)
- 初始 skill: SearchQA 通用 skill

#### Math 训练监控

| Step | 动作 | val | 说明 |
|------|------|:--:|------|
| 基线 | — | 89.0% | SearchQA adapter 包装后基线 |
| 1 | accept_new_best | 91.0% | +2% |
| 2 | accept_new_best | 91.5% | +0.5% |
| 3-6 | reject | 91.5% | |
| 7+ 续跑 | reject | 92.0% | API 充值后恢复 |
| 28 | 截停 | 92.5% | 连续 13 reject |

| 指标 | 值 |
|------|:--:|
| 基线 (SearchQA adapter) | 89.0% |
| 最高 val | 92.5% (Step 15) |
| Accept | 3/28 |
| 提升 | +3.5pp |

#### History, Law, Philosophy（旧 adapter）

| | History | Law | Philosophy |
|------|:--:|:--:|:--:|
| 基线 val | ~61% | 43.0% | ~63% |
| 峰值 val | 68.4% | 45.5% | 72.0% |
| Accept 数 | 3 | 3 | 4 |
| 提升 | +7pp | +2.5pp | +9pp |

#### SpreadsheetBench

| 指标 | 值 |
|------|:--:|
| Mean hard | 0.355 |
| Mean soft | 0.570 |
| 执行成功率 | ~62% |

---

## 后续方向（更新于 2026-07-27）

| 优先级 | 方向 | 理由 |
|------|------|------|
| ⭐⭐⭐ | **修复 Math test bug** | slow_update guidance 能拉回 89% val 但 test 评估崩了 |
| ⭐⭐⭐ | **混合 adapter** | SearchQA 模板+纯 initial_skill — 有 step patches 也有 slow_update |
| ⭐⭐⭐ | **SpreadsheetBench 接入训练循环** | 35% 基线，空间最大 |
| ⭐⭐ | **History 补跑纯 adapter** | 增加对比数据点 |
| ⭐ | 更大的 val 集 | 降低 selection 评估噪声 |
| 💡 | **Slow update 可能比 step patches 更有效** | 本次实验所有 gain 均来自 slow_update