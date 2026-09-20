# ACL 2027 Phase 2 阶段性汇报（v25）

## 一、研究问题

本阶段不是简单比较“加 skill 是否提高准确率”，而是检验：在持续任务流中，带有明确类型和作用域的历史先验，是否能在严格审计和固定预算下稳定优于全局先验。

## 二、证据链设计

1. **机制验证**：Phase 0 先验证 identity、scope、非破坏性保留和成本核算等机制，避免把系统性错误误判为模型方法效果。
2. **能力与候选覆盖**：Phase 1 验证模型是否能完成任务，并能从独立 history 中产生可复核的 typed candidate。能力失败、verifier 失败和方法失败严格分开。
3. **候选资格门槛**：v13 formal-history coverage 通过，五类 skill family 的 verified supports 为 `28/32/28/17/16`。这只说明候选已具备进入后续实验的资格。
4. **Probe 门槛**：v20 达到最低 probe eligibility，contextual typed prior 为 `28/40`，global-only 为 `27/40`。这只允许进入 held-out，不是最终方法效果证据。
5. **Held-out 与独立 replication**：v23 held-out 结果为 inconclusive；随后 v24 冻结 80 个全新任务、4 个条件和 320 个请求，v25 对该设计进行一次独立 replication。

## 三、v25 replication 结果

| 条件 | 正确数 | 准确率 |
|---|---:|---:|
| cold | 59/80 | 73.75% |
| copied-global | 61/80 | 76.25% |
| global-only | 57/80 | 71.25% |
| contextual-typed-prior | 59/80 | 73.75% |

主要比较是 contextual typed prior 减去 global-only：margin `+0.0250`，配对结果为 `4` wins、`2` losses、`74` ties。预注册规则要求正向结果同时满足 margin 至少 `+0.125`、至少 3 个 wins 且 0 个 losses；负向规则在 losses 至少 2 个时触发。因此 v25 gate 为 **negative**。

## 四、结果支持什么结论

- 可以在完整、可恢复、可审计的真实任务流程中执行 typed-prior replication。
- 独立 history、private gold、request identity、hash-chained ledger、exact-prefix resume 和成本审计形成了可复核的实验治理链。
- 在本次 80-task replication 上，没有得到“typed prior 稳定优于 global-only”的证据。

## 五、结果不能支持什么结论

- 不能据此声称所有 typed prior 都有害；v25 是本设计、模型和样本范围内的 bounded negative evidence。
- 不能把 v20 probe pass 当作最终方法效果。
- 不能把 v23 inconclusive 与 v25 negative 任意合并成新的阈值或新结论。
- 不能外推到其他模型、其他任务族或 formal scaling。

## 六、工程审计

v25 精确完成 `320/320` 次调用，输入 `694,816` tokens，输出 `2,579` tokens，总计 `697,395` tokens，本地成本 `CNY 1.410264`。零重试、零重复、零 terminal row；ledger/start hash chain、exact-prefix 和 pacing 全部通过。calibration、development、formal history、probe、held-out、later stage 和 formal scaling 调用均为 `0`。授权已自动关闭。

审计 fingerprint：`35a683a78dd6057b8e3e5122373de024706eba033e3742c04eaf081fdba0c779`。

## 七、当前建议

论文应将贡献定位为“可审计、带边界的安全先验验证框架”，而不是“typed prior 已被证明普遍提升准确率”。当前继续工作仅限于零网络论文写作、表格整理和误差分析；任何新实验、阶段、模型或 formal scaling 都需要新的独立授权。
