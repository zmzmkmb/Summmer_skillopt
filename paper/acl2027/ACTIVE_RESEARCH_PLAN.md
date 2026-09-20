# ACL 2027 当前主线研究计划

更新时间：2026-08-22

## 当前主线

**Scope-Aware Admission and Answer-Level Grounding for Historical Experience Reuse in Continual Agents**

当前论文不再把“历史经验复用必然提升准确率”作为前提。历史经验只有在 identity、scope、admission、evidence 和 answer-level validation 同时可审计时，才可能被安全复用。

## 研究对象

```text
candidate = (identity, scope, provenance, evidence, validation_status, retention_status)
```

复用链：`verified trajectory -> typed candidate -> scope-aware admission -> evidence-grounded operation -> intermediate result -> final answer`。

## 当前可保留的证据

1. Phase 0 支持 identity、scope 和 candidate-retention 机制在受控环境中可行。
2. Phase 3/3H 支持 selector uptake 与 answer grounding 不是同一层能力。
3. Phase 5 的 incompatible-control 条件为 0/40 正确率，支持不相容 prior 会系统性污染答案。
4. Phase 5 完成 240/240 行；contract-valid 为 240/240，evidence-resolving 为 203/240，answer-correct 为 188/240，说明格式合规、证据绑定和最终答案必须分开评价。

## 当前不可声称

- 不声称 typed prior 普遍提高真实任务准确率。
- 不声称 evidence-grounded admission 已优于 always-use typed。
- 不声称 sparse probe 已代表 downstream distribution。
- 不声称 continual routing reliability、token efficiency 或跨域泛化已被证明。

## 后续实验原则

所有新实验必须报告 candidate identity、scope match、admission decision、selected skill、operation/intermediate result、evidence resolution、final answer 和 counterfactual answer。selector uptake 或 JSON 合规单独不能作为主结论。新实验必须新建版本，证明与旧 logical/request/transport identities 零重叠，并在 provider 执行前完成零网络 preflight 与精确授权。

## 旧主线隔离规则

原主线“typed/scoped priors + representative sparse validation improve continual routing”现标记为 **LEGACY / FROZEN / READ-ONLY**：

- 旧 artifact、ledger、closure、analysis 和 fingerprint 不得修改、覆盖、重跑或恢复；
- 旧结果只能作为历史证据、失败模式或对照背景，不能作为新实验的候选输入、阈值调参数据或 held-out tuning 数据；
- 不得从旧主线自动生成新的 provider schedule；
- 复用旧数据必须是只读分析，并显式标注 `legacy_provenance`；
- 后续 runner 只接受当前主线 experiment-line 标识和新版本 fingerprint。

## ACL 论文定位

> Historical experience is not safely reusable merely because it is successful, typed, or selected by the agent. Safe reuse requires scope-aware admission and answer-level evidence grounding.