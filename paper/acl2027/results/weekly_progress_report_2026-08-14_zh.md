# ACL 2027 论文阶段性进展报告

**日期：** 2026-08-14  
**当前状态：** 已完成 33 个阶段、1070 个不可变运行；Phase 1 已关闭，Phase 2 完成能力校准与后续零网络激活设计，尚未进入正式 history/probe/held-out。

## 1. 研究问题与当前论文定位

论文研究持续学习系统如何安全继承历史技能先验。核心问题不是“先验是否总能提高性能”，而是：先验的作用域是否被正确识别、稀疏验证是否代表后续流、以及证据不足或负面时是否应保留候选而非破坏性删除。

当前可辩护的论文定位是：**typed/scoped priors、representativeness-aware validation 与 non-destructive abstention 在合成持续路由环境中获得支持；其真实跨任务方法效果仍未建立。**

## 2. 实验设计路线图

| 阶段 | 设计目的 | 当前结论 |
|---|---|---|
| Phase 0 | 离线持续路由：比较全局/上下文先验、验证策略、冷启动对照、对抗先验与 token 成本 | 形成合成环境的主证据与负例诊断 |
| Phase 1 | 真实模型/真实任务小规模试验：从能力校准、任务基底修复到预注册 paired design | 真实任务效果为混合/阴性，Phase 1 关闭为 inconclusive |
| Phase 2 | 独立 history、probe 与 held-out 扩展，检验 broader typed coverage 是否支持可识别的真实因果证据 | v8 能力校准通过；正式扩展尚未执行 |
| Phase 3-4 | 正式多域实验、消融、鲁棒性、统计与复现 | 未开始，formal scaling 仍关闭 |

所有 live 阶段均采用独立授权、冻结配置、确定性 request hash、append-only ledger、零重试、精确 token/cost 记录与终止式 hard stop。开发、history、probe、held-out 必须分离；coverage 或 transport 通过不被当作方法效果。

## 3. Phase 0：已验证的合成证据

1. **先验身份和作用域重要。** Phase 0L 发现所谓“oracle prior”曾是全局均值被复制到所有上下文状态；显式 contextual identity 的 per-domain correlation 为 1.0，20/20 stream margin 为正，较旧全局身份提高平均 margin 0.1265。
2. **非破坏性 selective policy 有合成支持。** Phase 0M/0N 将 candidate retention、accept/reject/abstain 与 identity-correct initialization 冻结后评估。Phase 0N 的 160/160 held-out runs 通过预注册 gate：相对 copied-global reset 的 oracle reward +0.036734，token overhead 10.66%，且 0/40 candidate-state mutation。
3. **稀疏验证的代表性仍是风险。** held-out adversarial seed 176 被接受后反而劣于 cold fallback；因此不能声称稀疏 probe 已可靠预测 downstream safety。

结论：Phase 0 支持“要区分 prior scope，并在不确定时 abstain/保留候选”，但不支持“零失败安全”或真实任务普适提升。

## 4. Phase 1：真实任务路线、设计修订与结果

### 4.1 设计迭代

- 初始 OfficeQA/SpreadsheetBench smoke 暴露 arithmetic、schema、截断和 formula semantics 问题；这些失败被保留，不被归因于 prior 或 gate。
- 随后将 OfficeQA 改为 deterministic recomputation + provenance abstention，将 SpreadsheetBench 改为 constrained executor-backed substrate，避免把 benchmark-specific 推理失败误作方法效果。
- Phase 1P-Q-R 冻结 contribution-aligned paired design：三种 prior identity、representative/shifted probe panel、retaining/destructive gate、fresh cold fallback 与双侧 token 计费；开发阶段 192 calls，完整设计 960 calls。

### 4.2 主要真实结果

Phase 1S v2 完成 192 个开发调用：161 个 contract-valid，31 个无效输出，123 个可执行结果，38 次 abstention，仅 6 个 exact task success。candidate 分支 2/96，fresh fallback 4/96；contextual/copy-global/global-only 分别为 0/64、4/64、2/64，全部成功集中于单一 OfficeQA task，SpreadsheetBench 为 0/96。

这不是稳定 prior-effect 证据，且 gate 标签没有改变模型可见请求，也没有实际 longitudinal retention 语义。因此：

- typed priors 未获真实任务确认；
- representative probes 未优于 shifted probes；
- triage 优势未被测试；
- Phase 1 正式关闭为 **inconclusive**，不通过追加分析改写为正结果。

## 5. Phase 2：本周新增进展

1. 修复了 Token Plan 路由与响应格式问题，保留 v5/v6/v7 的失败账本作为不可变负证据。
2. v8 校准完成 60/60 次 `qwen3.7-plus` 调用：60/60 JSON contract-valid，45/60 答案正确，70,412 total tokens，CNY 0.143836，零重试、零重复，eligibility gate 通过。
3. v9 零网络激活预检将 v8 校准绑定到既有 Phase 2 B 设计。完整 B 方案包含五个 family、350 个互斥任务、最坏 710 calls；但尚未被授权执行。
4. 下一步 live 边界被收紧为仅 10 次 development-acquisition（五个 family 各两次）。formal history、probe、held-out 与 formal scaling 均未开始、未授权。

重要边界：v8 是 capability-calibration 证据，证明格式化任务接口可用；它不是 prior transfer、triage 或真实因果效果的证据。

## 6. 当前论文结论与风险

**已支持：** 合成 held-out 环境中，正确的 prior identity/scope 与非破坏性 abstention 有可审计收益；工程上已形成严格的泄漏控制、配对比较、成本核算和失败保留机制。

**未支持：** 真实跨任务中 typed prior 的稳定优势、稀疏 probe 的 downstream 代表性、retention-aware triage 对真实有害部署的降低，以及任何 formal scaling 结论。

**主要风险：** real-task 成功率稀疏且集中；proxy-to-real mismatch 未解决；seed 176 表明安全性没有余量。论文应继续定位为“有边界的安全先验继承与验证框架”，而不是通用性能提升或零风险部署方法。

## 7. 下周计划

1. 完成 post-v8 的独立 development-acquisition runner/preflight，确保不复用旧 calibration ledger。
2. 在单独授权下运行最多 10 次 development acquisition，仅评估历史获取可行性和 family coverage。
3. 只有所有 family 的覆盖 gate 与独立审计通过，才提交 formal history 的新设计和新授权；不会自动推进到 probe、held-out 或 scaling。
4. 同步整理论文：强化 synthetic evidence 与负结果叙述，明确真实任务主张尚待验证。

## 8. 可复核证据

- `paper/acl2027/CONTRIBUTION_EVIDENCE_LEDGER.md`
- `paper/acl2027/experiment_roadmap.md`
- `paper/acl2027/experiment_state.json`
- `paper/acl2027/results/phase2_calibration_live_v8.md`

## 附录 A：Phase 0 实验设计细节（离线持续环境）

### A.1 Phase 0 要模拟的真实持续学习环境

Phase 0 不是静态分类准确率实验，而是一个可完全审计的多域持续路由模拟器。其基本过程是：系统在时间点 `t=0` 继承一组历史 skill/rule 及其 utility/credit；之后不同领域的任务按轮次到达；路由器根据当前状态选择规则；任务反馈再更新 credit；系统最终按整段任务流的累计 reward 和累计 token 成本接受评价。因此，先验造成的影响不只体现在第一道题，而会通过路由选择和在线 credit 更新继续影响后续任务。

Phase 0 对真实环境的抽象关系如下：

| 现实持续系统中的问题 | Phase 0 中的模拟方式 | 主要观测量 |
|---|---|---|
| 从旧项目继承的技能确实有用 | `helpful/oracle prior`，使历史规则与后续任务域一致 | 相对 cold 的 reward、helpful retention、false reset |
| 历史知识已经过时或被污染 | `adversarial prior`、冲突规则、恶意规则、utility corruption | harmful accept、adversarial detection、下游累计损失 |
| 新领域没有历史经验 | `all-cold` 或 same-policy `cold-router` | 冷启动 reward、误触发 reset、额外验证成本 |
| 同一技能只在部分领域有效 | global-only 与 contextual per-domain state | per-domain correlation、stream margin、跨域负迁移 |
| 初期少量样本与长期流分布不一致 | first-one/first-two probe、all-probe、完整 downstream stream | probe-to-stream correlation、错误 accept/reject |
| 验证本身要消耗模型调用 | probe 和 rollout 的全部 token 计入总成本 | guard tokens、reward/1k tokens、成本上限 |
| 早期错误会改变之后的学习轨迹 | learned/cold 两侧克隆并分别在线更新 credit | 每轮 margin、confidence、recovery slope、累计 reward |
| 证据不足时应保留未来恢复可能 | accept/reject/abstain 与 candidate retention | candidate mutation、abstention、later recovery 语义 |

为了保证因果比较，所有方法共享同一任务流、seed、任务顺序和在线更新规则；差别只允许出现在 prior identity、路由/验证策略和 candidate 处置策略。验证的 candidate 分支与 cold fallback 分支都计入 token，不能只计算最终被选中的一侧。开发 seed、可靠性 seed 和最终 held-out seed 分离，冻结后不得用 held-out 结果重新调阈值。

### A.2 Phase 0A-N 的实验矩阵

| 阶段 | 核心问题与比较 | 模拟的现实风险 | 结果及对设计的影响 |
|---|---|---|---|
| 0A | 建立 continual-routing 基线，对比 greedy、Top-K、MOAR，并核对 token-to-target accounting | 不同技能选择器在连续任务中的收益与成本差异 | 建立后续所有实验的共同任务流、reward 与精确 token 计量框架 |
| 0B | global state 对 contextual state；加入 non-regression gate | 全局经验被错误迁移到局部领域 | 证明必须追踪上下文状态，单一全局 utility 不足以描述作用域 |
| 0C | contextual transfer、conflict、drift、malicious/duplicate rules、utility corruption | 技能重复、过时、冲突、恶意注入和历史评分损坏 | 将“错误先验”从单一噪声扩展为多种真实污染机制，并观察长期伤害 |
| 0D | credit identifiability 与 leave-one-out cost | 多条规则共同工作时无法判断是谁带来收益 | 检查 credit 归因是否足以支撑后续选择，而不是只看总体 reward |
| 0E | global-contextual shrinkage sweep | 局部样本少时完全独立估计不稳定，完全共享又造成负迁移 | 搜索全局共享与局部独立之间的折中，但不把开发最优值当作可靠结论 |
| 0F | charged prior-sanity reset guard | 部署前验证有成本，且错误 reset 会丢掉有用经验 | 首次把 guard 的全部 probe token 计入收益，发现安全检查可能非常昂贵 |
| 0G | one-probe 与 sequential `z=1.0`；开发/held-out seed 分离 | 快速低成本检查与可靠检查之间的矛盾 | one-probe 更省 token 但有误触发；sequential 更稳但效率低，可靠性扩展仍有 all-cold false reset |
| 0H | 加入真正 helpful oracle、informative-probe ablation、same-policy cold-router | 过去 all-cold 对照不对称，且验证可能错误删除真正有用的 prior | helpful prior reward 由 0.7181 提升至 0.7553；one-probe 错删 3/5，sequential 仍错删 1/5 |
| 0I | cloned learned/cold rollout，最少 6 或 12 个验证样本 | probe 期间两条路线会继续学习，静态比较低估轨迹差异 | min-12 达到 helpful 5/5 保留、adversarial 5/5 拒绝、all-cold 0/5 误触发，但 helpful guard 平均耗费 9,591 tokens |
| 0J | adaptive horizon：harm margin、confidence、recovery slope | 固定长验证浪费成本，自适应停止可能更符合在线部署 | 开发集保持 5/5、5/5、0/5 决策，同时将 helpful 成本降至 6,172 tokens；但 slope 的独立价值未证实 |
| 0K | 冻结策略，在 seeds 101-120 做 180-run reliability grid | 检查开发集上看似完美的阈值能否泛化 | gate 失败：3/20 helpful false reset、19/20 adversarial detection、helpful 平均 9,028 tokens，否定直接推广 |
| 0L | global-oracle 对 contextual-oracle；prefix probe 对 all-probe/stream | 先验的“身份标签”可能错误，稀疏 probe 可能不代表长期流 | 旧 oracle 的 per-domain correlation 仅 0.481；contextual identity 达 1.0，20/20 stream margin 为正；seed 109 显示早期正 margin 可翻转为长期负 margin |
| 0M | copied-global、global-only、contextual；destructive reset 对 non-destructive selective guard | 全局技能不应被复制成领域技能，证据不足时删除候选会丧失恢复机会 | global-only 消除 4/20 helpful false reset；selective policy 接受 20/20 oracle、0/20 adversarial accept，4/20 adversarial abstain，candidate mutation 为 0 |
| 0N | 用未见 seeds 161-180 对 0M 冻结 candidate 做 160-run held-out | 最终检验作用域修复、非破坏性 gate 和成本上限能否共同成立 | gate 形式上通过：oracle reward 相对 copied-global +0.036734，token overhead 10.66%，0/40 mutation；但 adversarial seed 176 被接受并伤害 downstream |

### A.3 Phase 0 的指标与判定逻辑

Phase 0 不以单一平均准确率作为结论。主要指标包括：整段 stream reward、相对 cold/reset 的 paired margin、reward/1k tokens、helpful false reset、adversarial accept/detection、abstention、candidate-state mutation、每轮 margin/confidence/recovery slope，以及 run/round 级精确 token identity。Phase 0K 和 0N 都使用预先声明的可靠性 gate；即使平均值改善，只要关键安全边界失败，也必须保留为负结果。

最终得到两层结论。第一层已验证：先验必须带有正确 scope/identity，global-only 信息不能伪装成每个领域的 contextual knowledge；在证据不足时保留 candidate 的 abstention 比不可逆 reset 更符合持续学习语义。第二层未验证：少量 probe 仍不能可靠代表长期 downstream，seed 176 说明即使正式 held-out gate 通过，adversarial safety 也没有余量。因此 Phase 0 是论文的合成机制证据和失败诊断，不是现实部署安全性的最终证明。

## 附录 B：Phase 1 实验设计细节（真实模型与真实任务）

### B.1 Phase 1 为什么要从“真实任务能力”开始

Phase 1 的目标是把 Phase 0 的三项主张移到真实 LLM 任务：typed/scoped prior 是否改善任务结果，representative probe 是否比 shifted probe 更能预测 downstream，以及 retaining triage 是否比 destructive gate 更安全。但真实实验多出一个前置条件：基础模型必须先能稳定完成并被自动验证，否则“prior 没有效果”和“模型根本不会做任务”无法区分。因此 Phase 1 被设计成四层漏斗，而不是直接进行大规模方法比较：

1. transport/contract 层：接口、JSON、重试、账本和 token/cost 是否可靠；
2. capability/substrate 层：无技能条件下是否有足够但不饱和的成功率，任务能否自动验证；
3. history/candidate 层：是否能从独立历史任务得到 verifier-confirmed trajectories，并形成多 family typed candidates；
4. method-effect 层：在独立 probe 与 held-out 上比较 prior identity、probe representativeness 和 retention policy。

这四层严格分离。接口连通、格式正确、能力校准通过或 candidate coverage 通过，都只能说明进入下一层的资格，不能被写成 prior 方法效果。

### B.2 Phase 1 使用的真实任务及其现实含义

| 任务基底 | 被测能力 | 模拟的实际场景 | 自动验证方式与暴露的问题 |
|---|---|---|---|
| SearchQA | 检索式问答、答案抽取和已有规则迁移 | 历史 QA 技能在新问题流中的复用 | exact match/F1/substring；适合大规模 pilot，但 Phase 0 proxy 排名未清晰迁移 |
| OfficeQA | 从有 provenance 的月份数据中检索、选择操作数并计算 | 办公数据分析中“证据正确但计算可能错误” | deterministic recomputation；模型曾找对 12 个数却把 2602 算成 2561/2498 |
| SpreadsheetBench | 按行生成满足约束的公式 | 表格自动化中语法正确但业务语义错误 | constrained executor 与 golden semantics；曾出现 12/12 公式语法有效但逻辑方向错误 |
| 2WikiMultiHopQA | 多跳证据链、比较、桥接和组合推理 | 从可验证成功轨迹抽取不同 family 的历史技能 | answer + supporting-fact joint verifier；校准 joint accuracy 6/12，覆盖三个 task type/family |

OfficeQA 与 SpreadsheetBench 的早期自由回答失败没有被归因为 prior 失败。相反，Phase 1O 将它们重构为 executor-backed substrate：OfficeQA 只允许基于冻结操作数做确定性重算，并在 provenance、时间、覆盖或 operand 不一致时 abstain；SpreadsheetBench 只把受约束构造器生成且执行器验证的公式作为有效结果。这个修改使“生成能力失败”和“验证/路由方法失败”可以分开。

### B.3 Phase 1A-Z 的实验与设计修改链

| 阶段 | 实验设计 | 主要结果 | 对后续设计的修改 |
|---|---|---|---|
| 1A-1B | SearchQA 七种 paired 方法、三个互斥 120-item replicate；冻结 fallback、预算和 provider accounting | 1B v5 完成 2,448 logical calls、2,579 attempts；`skillopt_moar_frozen` 最强，selective candidate 未清晰优于 identity-correct reset | 证明真实 API 和大规模评估可运行，同时暴露 synthetic proxy 到真实排名的差异 |
| 1C-1D | 对 1B 做 no-paid paired reconciliation，并构造 triage pilot | 未找到 selective guard 的稳定真实优势 | 不再把 SearchQA 单次排名解释为三项主张的证明，转向跨任务 paired design |
| 1E-1H | 冻结 OfficeQA/SpreadsheetBench 跨任务协议、修复 schema/时间泄漏、做两请求 smoke preflight | 零网络审计通过，但仅代表协议就绪 | 要求任何方法比较前先过 task-valid capability floor |
| 1I-1N | Flash/Plus 的少量真实 capability smoke；分别检查截断、JSON、算术和公式语义 | Flash 与 Plus 即使完整输出仍出现算术和公式语义错误；Plus 找对 OfficeQA 操作数却报告错误总和 | 取消盲目扩大 24/40 batch；引入 deterministic executor 和 abstention，避免 capability failure 污染 method-effect |
| 1O | zero-network construct-first route adjudication | OfficeQA 独立重算得到 2602；SpreadsheetBench constrained constructor 达 12/12 exact | 保留两任务，但限定为 executor-backed，不再声称自由生成能力 |
| 1P-1R | 冻结 `3 prior identities x 2 probe panels x 2 gates x 2 families` 的 24 cells；每 family 8 development + 16 downstream；materialize 192 development calls | 22/22、19/19 等预检通过；candidate 与 fresh fallback 各 96 calls，双侧计费 | 形成首个 contribution-aligned factorial design，并设置 unknown usage、contract drift 等 hard stop |
| 1S v2 | 执行 192-call development method-effect run | 161 contract-valid、123 executions、38 abstentions、6 exact successes；candidate 2/96，fallback 4/96；representative 0/96，shifted 6/96 | 真实能力 floor 过低；gate 标签未改变请求且无 longitudinal retention，因此 triage 实际未被测试，OfficeQA/SpreadsheetBench 被降级 |
| 1T-1W | 重新定义链路：verified history -> typed candidate -> probe -> held-out；冻结 SearchQA/2Wiki 的 12/120/24/120 分区和 24-call calibration | 所有 payload、ID 互斥、verifier、resume、usage 和 leakage 审计通过 | 将 capability gate 前置：contract-valid >=90%，accuracy 25%-75%，至少三类成功且不能集中于单一 task ID |
| 1X | SearchQA 12 + 2Wiki 12 的真实 calibration | SearchQA 10/12；2Wiki answer 7/12、support 9/12、joint 6/12，覆盖三个 task type/family | 2Wiki 通过 frozen non-floor eligibility gate，可进入独立历史获取 |
| 1Y | 先做零网络 history audit，再执行 10 次独立 history acquisition 并 materialize typed candidates | 8/10 verified trajectories；形成 3 个 typed candidates，但只覆盖 3/5 family | history acquisition 可行，但 candidate coverage gate 失败；未进入 probe/held-out |
| 1Z | 将 candidate hash 和 coverage gate 绑定后做 final execution adjudication | 0 provider calls，关闭为 `inconclusive_without_phase1z_provider_execution` | Phase 1 正式关闭，不能通过补跑或事后挑选把不完整 coverage 改写成真实 prior 结果 |

### B.4 Phase 1 正式 factorial design 的控制变量

Phase 1P-R 原设计包含三种 prior identity：`copied-global` 把全局经验错误复制到各域，`global-only` 只初始化全局状态，`contextual` 使用带 family/scope 的领域先验；两种 probe panel：`representative` 与后续任务同分布，`shifted` 故意偏移；两种 gate：`retaining` 在 reject/abstain 后保留 candidate，`destructive` 不可逆删除；两条执行分支：candidate 与 fresh-cold fallback。只要模型可见上下文不同，就必须进行独立物理调用，不能复用同一回答；两条反事实分支都计 token。

冻结 decision rule 为：paired mean margin `>= 0.125`、至少 3 个 helpful pairs 且没有 harmful pair时 accept；mean margin `<= -0.125` 或至少 2 个 harmful pairs 时 reject；其他有效结果 abstain。retaining policy 允许 candidate 在之后两个合格窗口后恢复，destructive policy 则永久丢弃。开发、history、probe、held-out ID 在调用前固定并相互排斥，已用 held-out 不得参与阈值选择。

但 Phase 1S 的运行并没有真正实现上述 gate 的模型可见差异和跨时间 candidate 状态：96 对 gate label 使用了相同 request body，标签只是 metadata。因此 Phase 1S 只能说明当前任务基底表现不足，不能用于比较 retaining 与 destructive。这个缺陷直接推动了 1T 的 longitudinal redesign。

### B.5 Phase 1 的最终结论

Phase 1 验证了三件工程和测量事实：真实 provider 运行可以做到不可变计划、零重试、精确 usage/cost 和失败保留；executor-backed verifier 能把“证据检索正确但计算/语义错误”分离出来；2Wiki 校准说明存在可验证、非饱和且跨 family 的真实成功轨迹。Phase 1 同时否定或修改了三项早期假设：OfficeQA/SpreadsheetBench 不适合作为自由生成式主因果基底；representative probe 并未在 1S 中表现更好；仅有 gate 标签而没有请求和状态差异不能测试 triage。

Phase 1 没有验证 typed prior、probe representativeness 或 retaining triage 的真实 held-out 效果。1Y 虽获得 8 条 verified trajectories 和 3 个 typed candidates，但 3/5 family coverage 未达到冻结门槛，因此 1Z 在零 provider 调用下关闭。这个 `inconclusive` 结论是实验完整性的一部分，而不是尚未整理完的正结果。

## 附录 C：Phase 2 完整设计与执行顺序

Phase 2 独立冻结五个 skill family：每 family 12 calibration、2 development-acquisition、32 formal-history、8 probe、16 held-out，共 350 个互斥任务。完整 B 方案为 60 calibration、10 development acquisition、160 formal history、160 probe、320 held-out，共 710 calls。

probe/held-out 在 cold、copied-global、global-only、contextual typed prior 四个模型可见条件下分别物理调用；primary contrast 是 contextual 对 global-only。只有每 family 达到 verifier-confirmed history coverage 才能进 probe，probe 审计通过后才能进 held-out。coverage 不足、unknown usage、provider exception、hash drift 或 cost overflow 都是 protocol stop，不能事后改写成方法负结果。
