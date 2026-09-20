# ACL 2027 阶段性实验报告

**日期：** 2026-08-16  
**阶段状态：** Phase 0 与 Phase 1 已关闭；Phase 2 已完成 formal-history、probe 和 held-out 证据链。当前所有 provider、付费调用与 formal scaling 权限均关闭。

## 1. 研究问题与实验逻辑

论文研究的不是“加入历史 skill 是否总能提高准确率”，而是一个更严格的问题：在持续任务流中，系统能否识别历史技能的类型和作用域，在有限 token 预算下安全复用；当证据不足或先验可能有害时，能否保留候选、拒绝部署或回退，而不破坏已有能力。

为避免把不同原因混为一谈，实验按以下证据链推进：

| 证据层 | 为什么要这样设计 | 要支撑的论文判断 |
|---|---|---|
| 离线机制 | 在完全可控环境中分离 prior identity、credit、验证成本、遗忘和分布漂移 | 方法中的 scope、credit、成本核算和非破坏性验证是否必要 |
| 真实能力与候选 | 先确认模型能完成任务，并能从独立 history 中产生可验证、可追溯的 typed candidates | 后续失败是否真是方法失败，而不是模型能力或 verifier 失败 |
| 独立 probe | 用未进入 history 的任务检查候选是否至少具备进入 held-out 的资格 | typed prior 是否达到最低可辨识性，但不把 probe 当最终效果 |
| 冻结 held-out | 在预注册四条件和门槛下比较 contextual typed prior 与 global-only | 真实跨任务方法效果能否被正向或负向识别 |

四个条件分别是 cold、copied-global、global-only 和 contextual typed prior。它们用于区分“没有历史”“错误复制全局经验”“只保留全局作用域”和“带显式类型/作用域的历史先验”，从而把先验内容与先验身份分开。

## 2. Phase 0：先证明机制为什么必要

真实 API 实验同时包含模型能力、接口、解析、成本和方法效果，直接扩展很难解释。因此 Phase 0 先在可复现的持续路由环境中固定任务流和在线更新，再逐步加入冲突、漂移、恶意规则、重复规则、utility corruption、稀疏 probe 和冷启动条件。

主要结果如下：

- 全局 utility 不能替代 contextual identity。Phase 0L 中，旧 global prior 的 per-domain correlation 仅为 `0.481`；显式 contextual identity 达到 `1.0`，20/20 个 stream margin 为正，平均 margin 提高约 `0.1265`。这支持论文中的“技能必须携带明确 scope/identity”这一机制主张。
- 非破坏性候选保留有合成证据。Phase 0N 的 160/160 frozen held-out runs 通过 gate：相对 copied-global reset，oracle reward 提高 `0.036734`，token overhead 为 `10.66%`，candidate mutation 为 `0/40`。这支持证据不足时 abstain/保留候选，而不是永久删除。
- probe 代表性仍是独立风险。adversarial seed 176 在验证阶段被接受，却在后续 stream 中劣于 cold fallback。这说明“probe 通过”不能直接等同于“下游安全”。

Phase 0 支持机制必要性，但不能外推为真实 LLM 的稳定性能提升或零风险部署。

## 3. Phase 1：排除真实任务中的混淆因素

Phase 1 的目标是验证从离线机制到真实任务的每个前置条件，而不是直接追求正结果。早期 OfficeQA 和 SpreadsheetBench 暴露 arithmetic、schema、截断及 formula semantics 问题，因此实验改用 deterministic recomputation、constrained executor 和 provenance-aware abstention。随后选择具有多跳、比较、bridge 和 relation 结构的 2WikiMultiHopQA，冻结 `verified history -> typed candidate -> probe -> held-out` 路线。

关键结果是：

- SearchQA 大规模 pilot 证明真实执行与记账链路可运行，但没有形成稳定的 selective-selector 优势；proxy 与真实结果存在偏差。
- Phase 1S 的 192 次 development calls 中，161 次 contract-valid，只有 6 次 exact task success，且成功集中在单一任务类型。此时比较 prior 会把基础能力不足误写成方法效果。
- Phase 1X 的能力校准为 SearchQA `10/12`、2Wiki joint `6/12`；Phase 1Y 虽获得 `8/10` verified trajectories，但只覆盖五类中的三类，未达到候选覆盖要求。

因此 Phase 1 以 `inconclusive` 关闭。它支持“capability floor、objective verifier、独立 history 和 coverage gate 都不可跳过”，但不支持 typed prior 已在真实 held-out 上有效。

## 4. Phase 2：完成独立证据链

### 4.1 执行完整性与能力校准

Phase 2 采用冻结配置、独立阶段授权、确定性 request identity、原子 hash-chained ledger、exact-prefix resume、零重试、精确 token/cost 记账和 terminal hard stop。v1-v4 的多轮 preflight 统一合并为一项工程结论：v4 最终绑定 16 个磁盘文件和 aggregate fingerprint `17752bb2d26f38e253c91a5f789654dad209eb6c16a1dd68203a942fa354e8d9`，独立验收通过。中途的 endpoint、JSON contract、timeout 和连接终止均保留为不可变负记录，recovery schedule 排除所有已花费 request，避免重试或选择性删除失败。

校准最终达到 60/60 contract-valid、45/60 correct，说明 `qwen3.7-plus` 具备进入候选获取流程的最低格式与任务能力。development acquisition 为 10/10 contract-valid、8/10 correct，但 entity_bridge 为 0/2，因此只被解释为可行性诊断，不进入正式 history。

### 4.2 Formal history：证明候选覆盖已经建立

正式 history 由独立任务产生，并通过 private gold verifier、family binding、provenance 和 leakage audit。完整 160-row replay 后，五类 verified supports 为：

| family | supports |
|---|---:|
| fact retrieval | 28 |
| attribute comparison | 32 |
| bridge attribute comparison | 28 |
| entity bridge | 17 |
| relation inference | 16 |

coverage gate 通过。这证明后续比较所需的 typed candidate 已具备，不证明候选本身能改善 probe 或 held-out。

### 4.3 Probe：通过最低资格门槛

probe 将 48 条可复用完成记录与 112 条 recovery 记录合并为 40 tasks × 4 conditions 的完整平衡网格：

| 条件 | 正确数 | 准确率 |
|---|---:|---:|
| cold | 30/40 | 75.0% |
| copied-global | 27/40 | 67.5% |
| global-only | 27/40 | 67.5% |
| contextual typed prior | 28/40 | 70.0% |

typed 相对 global-only 为 `+0.025`，2 wins、1 loss、37 ties，达到预注册的 probe eligibility gate。这个结果只允许进入 held-out 检验；它不是最终方法效果证据。

### 4.4 Held-out：完整执行，但方法效果不可判定

held-out 将 232 条 v21 preserved rows 与 88 条 v23 recovery rows 合并为 80 tasks × 4 conditions 的冻结网格：

| 条件 | 正确数 | 准确率 |
|---|---:|---:|
| cold | 62/80 | 77.50% |
| copied-global | 59/80 | 73.75% |
| global-only | 59/80 | 73.75% |
| contextual typed prior | 60/80 | 75.00% |

主比较 typed minus global-only 为 `+0.0125`，即只多答对 1/80；配对结果为 2 wins、1 loss、77 ties。预注册正门槛要求 margin 至少 `+0.125`、至少 3 wins 且 0 loss；负门槛要求 margin 不高于 `-0.125` 或至少 2 losses。因此最终 gate 为 **inconclusive**。

这不是“typed prior 被证明无效”，也不是“typed prior 已有正向效果”。它表示在当前任务、模型、样本量和冻结门槛下，证据不足以识别正向或负向因果效果。

## 5. 当前论文能写什么

| 论文主张 | 当前证据状态 | 可写结论 |
|---|---|---|
| 显式 identity/scope 比复制全局 utility 更合理 | 合成 held-out 支持，真实 probe/held-out 未形成强差异 | 作为机制与设计原则成立；真实效果仍有限 |
| 非破坏性 abstention/候选保留有价值 | 合成 held-out 支持，真实 longitudinal triage 尚未充分测试 | 可写为有边界的安全设计，不写成真实部署保证 |
| 独立 history 能形成 typed candidate coverage | Phase 2 formal-history gate 通过 | 可以明确报告 candidate readiness |
| typed prior 改善真实 probe | probe eligibility 通过，但差值仅 1/40 | 只能写“达到进入 held-out 的最低门槛” |
| typed prior 改善真实 held-out | 60/80 对 59/80，冻结 gate inconclusive | 不支持正向或负向效果主张 |
| 工程执行可审计、可恢复 | hash、ledger、resume、成本和授权边界均通过 | 可以作为复现与实验治理证据 |

## 6. 阶段性结论

目前最准确的总结是：**项目已经完成从合成机制、真实能力与候选覆盖，到独立 probe 和完整 held-out 的证据链；工程链路可靠，但 contextual typed prior 在真实 held-out 上的因果效果仍不可判定。**

这一结果对论文仍有价值。它同时给出三类信息：合成环境中哪些机制确实必要；真实实验必须满足哪些前置条件；即使 history coverage 和 probe 均通过，也不能越过冻结 held-out 门槛宣称方法有效。论文定位应保持为“可审计、有边界的安全先验继承与验证框架”，而不是通用性能提升方法。

## 7. 当前权限与下一步

当前只允许零网络结果解释、表格整理和论文写作。v23 及此前所有 terminal artifacts 必须保持不变。任何新实验、后续阶段、其他模型比较或 formal scaling 都需要新的独立设计、零网络 preflight 和用户明确授权；本报告不产生也不继承任何执行权限。

关键审计锚点：v4 fingerprint `17752bb2...e8d9`；v22 preflight `8bcd47e1...b8306`；v23 zero-network preflight `e9891345...f280`；v23 combined audit `9ebaa09c...7c2b`。v23 recovery 为 88/88 calls、214,464 tokens、CNY 0.433632，零重试、零重复、零 forbidden-stage calls，授权已关闭。
