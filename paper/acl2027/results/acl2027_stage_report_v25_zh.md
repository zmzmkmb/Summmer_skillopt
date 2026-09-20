# ACL 2027 阶段性实验报告（截至 Phase 2 v25）

## 1. 研究目标

本项目检验一个有边界的持续学习问题：拥有经过核验、带类型和作用域信息的历史技能后，系统能否在真实任务流中安全复用，并在 token 预算下稳定优于全局历史。研究重点不是证明“加入 skill 总会提升准确率”，而是建立一条可审计证据链，区分机制正确性、模型能力、候选覆盖和方法效果。

## 2. 证据链设计与阶段结果

- **Phase 0：机制验证。** 先固定 identity、scope、credit、预算和非破坏性保留规则，避免把路由、记账或更新错误误判为方法收益。结果支持显式作用域、成本核算和安全回退，但不能直接推出真实模型效果。
- **Phase 1：能力与候选质量。** 分开检查模型是否会做题、答案是否可验证、历史候选是否充足。结果表明能力、客观 verifier 和候选覆盖都是方法比较的前置条件，因此该阶段结论为边界明确的 inconclusive，而不是方法失败。
- **Phase 2 v1-v4：执行安全。** 零网络 preflight、manifest、磁盘绑定、授权关闭和 hash 链确认实验可恢复、可审计且不重复扣费；这些结果证明执行治理，不证明 typed prior 效果。
- **Phase 2 v5-v13：候选就绪。** 修复接口、JSON 合约和 materializer，并保留 recovery provenance。v13 五类 verified supports 为 `28/32/28/17/16`，覆盖门通过，说明候选可进入后续测试，但还不是 probe 或 held-out 效果证据。
- **Phase 2 v14-v20：probe 资格。** 检查候选代表性，避免把少量成功样本外推到完整任务流。v20 contextual typed prior `28/40`，global-only `27/40`，probe eligibility 通过；该结果只允许进入 held-out。
- **Phase 2 v21-v23：held-out。** 冻结任务、条件和判断规则后完成 320 行组合分析。v23 contextual typed prior `60/80`、global-only `59/80`，margin `+0.0125`，为 inconclusive，不能宣称正向或负向因果效果。
- **Phase 2 v24-v25：独立 replication。** v24 预先冻结 80 个全新任务和 320 个请求，v25 只执行该 schedule，避免调参和复用旧请求。

## 3. v25 replication 结果

| 条件 | 正确数 | 准确率 |
|---|---:|---:|
| cold | 59/80 | 73.75% |
| copied-global | 61/80 | 76.25% |
| global-only | 57/80 | 71.25% |
| contextual-typed-prior | 59/80 | 73.75% |

typed prior 相对 global-only 的 paired margin 为 `+0.0250`，配对结果 `4 wins / 2 losses / 74 ties`。预注册正向门槛要求 margin 至少 `+0.125` 且无损失；负向规则在 losses 至少 2 次时触发，因此 frozen gate 为 **negative**。

## 4. 结论边界

当前支持：

1. typed-prior 复用可以在完整、可恢复、可审计的真实任务流程中被严格评估；
2. identity、scope、候选核验、非破坏性保留和成本审计是持续学习证据链的必要组成部分；
3. 在本次固定模型、任务样本和规则下，没有建立 typed prior 稳定优于 global-only 的证据，最新独立 replication 给出 bounded negative evidence。

当前不支持：所有 typed prior 都有害；把 v20 probe、v23 held-out 与 v25 replication 合并成新阈值；外推到其他模型、任务族或 formal scaling。

## 5. 审计与下一步

v25 精确完成 `320/320` 次调用：输入 `694,816`、输出 `2,579`、总计 `697,395` tokens，本地成本 `CNY 1.410264`；retries、重复、terminal rows 和越界阶段调用均为 0。request-start/ledger hash chain、exact-prefix resume 和 pacing 全部通过。audit fingerprint：`35a683a78dd6057b8e3e5122373de024706eba033e3742c04eaf081fdba0c779`。授权已关闭，当前没有 provider、paid API、其他模型、后续阶段或 formal scaling 权限。

因此下一步只做论文、表格和导师汇报整理；任何新实验或模型调用都需要新的独立 preflight 与明确授权。
