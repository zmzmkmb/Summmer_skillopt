# ACL 2027 实验流程总览

更新时间：2026-08-18

本文把 ACL 2027 实验从研究问题、离线验证、真实模型执行，到审计和论文结论的完整路径串起来。仓库中的 `experiment_state.json`、不可变配置、运行清单和审计报告是事实来源；本文是导航，不替代这些记录。

## 1. 研究主线

核心问题是：在规则/技能库持续增长、提示词 token 预算有限、任务域不断切换的情况下，带有类型和作用域信息的技能先验、在线路由和非回归保护，能否提高每累计 token 的持续路由可靠性。

每个任务步遵循同一闭环：

```text
任务与当前技能库
  -> 候选检索
  -> 预算约束下选择技能
  -> 模型/模拟器执行
  -> 观察中间操作与最终答案
  -> 给被选技能分配信用
  -> 更新 utility / uncertainty
  -> 可选技能编辑
  -> 非回归门控
  -> 记录性能、遗忘、延迟、token 与成本
```

所有方法必须共享任务流、模型、提示词、预算、示例、初始化和随机种子；搜索、探索、输入和输出 token 都计入成本。

## 2. 统一阶段生命周期

每个可执行阶段都按以下顺序推进：

```text
设计（zero-network）
  -> 冻结任务、条件、契约、指标和决策门
  -> 证明任务/逻辑请求/request hash 不重叠
  -> 生成不可变配置、payload、manifest 和 fingerprint
  -> live-execution preflight
  -> 明确授权（模型、路由、attempts、温度、重试、格式、节奏、成本上限）
  -> provider 执行
  -> request-start / response ledger 与 hash-chain 审计
  -> 自动闭合授权
  -> 严格分析与非门控诊断
  -> 更新实验状态和 checkpoint
```

关键规则：已完成运行不可重试、不可覆盖；失败和缺失行必须保留在 provenance；普通“继续实验”不等于 provider 授权。

## 3. Phase 0：离线框架与先验安全性

目标是在无付费 API 的情况下验证实验基础设施和机制假设：在线 per-rule credit、累计 token/regret、校准、遗忘、对抗 utility、嵌套规则库和强基线。

主要链条：

- **0A–0D**：连续路由基线、上下文状态/非回归门、漂移/冲突/恶意规则、credit 可识别性。
- **0E–0H**：上下文权重、先验 sanity guard、guard 可靠性、helpful prior 与 cold-router 对照。
- **0I–0K**：带真实在线更新的 rollout guard、adaptive guard 和冻结可靠性网格。
- **0L–0N**：先验代表性、身份感知 guard、开发/held-out 可靠性验证。

关键认识：全局均值先验不能代表每个上下文域；非破坏式、带身份的先验合同比继续扫阈值更重要。Phase 0 的结果只决定是否值得进入真实模型阶段，不直接支持最终论文主张。

## 4. Phase 1：小规模真实模型与能力校准

目标是确认 proxy 与真实任务是否一致，暴露 API/解析/路由问题，并筛选值得进入持续实验的方法。主 substrate 是 SearchQA，后续尝试了跨任务 triage、能力校准、历史技能候选和 held-out 部署识别。

该阶段形成了大量预检和修复版本（1A–1Z），最终边界是：

- 能力与协议问题被单独记录，不能把 capability failure 当成 prior-transfer 证据。
- 已完成的 Phase 1 artifact 全部冻结，不创建新的 1AA/1AB 等延伸阶段。
- 付费调用、模型选择和后续阶段必须另行授权，不能从旧授权恢复。

## 5. Phase 2：持续非回归与真实任务门

目标是将校准后的路由放进多域持续流，比较 contextual typed prior、global-only、cold、shuffled 等条件，并检查新任务收益与旧任务遗忘。

主要步骤：

1. **校准与 route repair（v5–v13）**：修复 Token Plan 路由、形式历史候选和覆盖问题。
2. **probe（v14–v20）**：先做可识别性和 eligibility，不把 probe 结果当 held-out 方法效果。
3. **held-out（v21–v23）**：完成 320 行合并网格；contextual typed prior 相对 global-only 仅有很小优势，冻结门为 inconclusive。
4. **独立复制（v24–v25）**：完成独立 320-call replication；contextual `59/80`、global-only `57/80`，配对结果 `4/2/74`，复制门为 negative。
5. **失败分析与恢复（v26–v31）**：只做失败类型、覆盖、验证器和能力解释的设计与恢复执行；保留不完整前缀，不重试已花费请求。

结论：Phase 2 的真实任务效果门不能支持“typed prior 已稳定改善方法效果”的正面结论，因此 Phase 2 关闭为 **inconclusive**，不能直接进入正式扩展或跨域规模化。

## 6. Phase 3：机制、选择特异性与答案落地

Phase 3 不是简单扩大样本，而是针对 Phase 2 的“是否采用技能”和“是否真正改善答案”之间的断裂进行机制实验。

### 3A–3C：从现象到中介机制

- **3A**：审计全部 Phase 2 task grids，区分无 uptake、仅操作变化、typed benefit/harms。
- **3B**：冻结 60 个新任务、5 个条件和 300 行 schedule；随后恢复执行完成 300/300 合同有效响应。得到强机制 uptake，但最终答案相对 cold 的改善有限。
- **3C**：中介审计显示 contextual-only 在 29 个任务中有 26 个改变中间操作，但仅 1 个改变归一化答案；mediation gate 为 inconclusive，并触发 specificity warning。

### 3D–3F：修复契约与控制

- **3D**：加入 abstention、双候选顺序反转和 irrelevant control，冻结 240 行。
- **3D v3**：真实执行 240/240，但 provider 返回 candidate-ID keyed mapping，而冻结契约要求 ordered arrays；严格契约门为 negative。
- **3E**：发现 bridge-attribute family 的 entity-bridge control 本身提供了必要桥接操作，控制无效。
- **3F**：改用 candidate-ID keyed native schema，并把 bridge-family control 换成 operation-incompatible fact retrieval；v2 执行 240/240。

3F 严格分析为 inconclusive：contextual selection `1.0`、irrelevant rejection `0.625`、dual correct selection `0.95`、answer-change `0.40`。非门控 boolean-normalization diagnostic 虽修复选择特异性，但 answer-change 仅 `0.05`，低于预注册的 `0.10` mediation 阈值。

### 3G–3H：答案 grounding

- **3G**：审计确认操作变化远多于答案变化，主要瓶颈在 answer grounding，而非单纯 selector。
- **3H v1–v3**：设计反事实、来源可验证、答案敏感的 40-task / 200-row schedule，并完成零网络契约和重叠审计。
- **3H v4**：冻结真实执行配置：Token Plan Beijing、`qwen3.7-plus`、temperature 0、thinking disabled、zero retries、无 `max_tokens`、JSON object、1 秒 pacing、CNY 3/15 ceilings。
- **3H v5**：200/200 完成；contextual target-answer `0.825`、incompatible-control counterfactual-answer `0.475`、paired grounding `0.425`，答案 grounding gate 仍为 inconclusive。

结论：Phase 3 提供了正面的机制 uptake 证据，但没有证明稳定的最终答案收益；跨域、换模型和 formal scaling 仍然关闭。

## 7. Phase 4：强结论校准与当前边界

### 4A：零网络强结论设计

冻结 20 个 development、80 个 held-out 任务，500 个五条件 proposal rows，统一 evidence-grounded response contract，预注册 positive/negative/inconclusive gates，并证明与历史 task、logical-call、request-hash 全部不重叠。

Fingerprint：`2a7a6814b261ad336902fa8c4c6048a6114f62ffa242aae267a3700d0e97a2db`。

### 4B：开发集 live-execution preflight

将 Phase 4A development split 绑定到精确的 live proposal，准备 100 个 provider calls 的执行方案和成本/审计约束。

Fingerprint：`0826f7a4cd5b673ce2e2dfed50a0cecd8806b0b8176c1ac004987b3a0f8bd243`。

当前状态：Phase 4B preflight 已完成，但 **100 次 provider 调用尚未授权**。必须由用户明确确认两个完整 fingerprint 以及冻结的 qwen3.7-plus Token Plan 合约；普通继续请求、报告整理或代码检查都不能替代该授权。Phase 4C held-out 执行也不能从普通继续请求启动。

## 8. 结果如何变成论文结论

证据分三层：

1. **基础设施证据**：配置、manifest、唯一 ID、hash-chain、成本和 cache-free regression 通过。
2. **机制证据**：技能是否被选择、是否特异、是否改变中间操作、是否影响答案。
3. **方法效果证据**：在 held-out、跨任务、跨模型和多次独立运行下的准确率/成功率、token、延迟、遗忘和成本。

当前仓库已经有较强的第 1 层证据和部分第 2 层证据；第 3 层仍不完整。因此目前可以写：机制 uptake 存在，但答案 grounding 与真实任务收益尚未形成稳定正结论；不能写成“typed prior 已普遍提升 continual routing”。

## 9. 当前可执行动作

在没有新授权时，只做以下工作：

- 整理论文正文、结果表、限制和 evidence ledger；
- 复核已完成 artifact 的 manifest、fingerprint 和报告引用；
- 设计新的零网络阶段，并冻结新任务、契约、门和重叠证明；
- 运行 cache-free、zero-network 的回归/审计测试。

禁止：重试任何已花费请求、覆盖完成 artifact、直接执行 Phase 4B/4C、换模型、跨域扩展、formal scaling，或把诊断结果升级为正式方法效果。

## 10. 新会话恢复入口

```powershell
python scripts/acl2027_experiment_handoff.py validate
python scripts/acl2027_experiment_handoff.py status
python scripts/acl2027_experiment_handoff.py handoff
```

恢复时以 `paper/acl2027/experiment_state.json` 为准；若与聊天记录冲突，以仓库状态为准。
