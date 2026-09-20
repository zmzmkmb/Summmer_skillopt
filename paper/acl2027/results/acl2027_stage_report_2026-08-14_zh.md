# ACL 2027 阶段性实验报告


## 1. 研究问题与证据边界

论文并不是要证明“任何 skill 都能提高模型准确率”，而是要检验一个更具体的持续学习命题：当技能库随任务流增长时，具有明确作用域和类型的历史技能，是否能在 token 预算约束下被安全复用；当证据不足、发生分布变化或历史技能可能有害时，系统是否能够保留候选、拒绝更新或回退，而不是破坏已有能力。

因此论文证据链被拆成四层：

1. **机制层：** 离线环境能否正确表示 utility、credit、预算、遗忘和非回归。
2. **能力层：** 真实模型是否有足够且可验证的任务能力，避免把模型不会做任务误判为方法失败。
3. **候选层：** 是否能从独立历史任务中得到 verifier-confirmed、typed、可追溯的 skill candidates，并达到每类最低覆盖。
4. **方法效果层：** 只有前三层通过后，才能在独立 probe 和 held-out 上比较 prior identity、representativeness 和 retaining/destructive triage 的真实因果效果。

## 2. Phase 0：先建立可解释的离线机制

直接做真实模型实验会把模型能力、接口错误、答案验证、成本和方法效果混在一起。因此 Phase 0 先固定任务流、rule library、路由、online credit、token accounting 和非回归指标，再逐步加入作用域错误、冲突、漂移、恶意规则、重复规则和 utility corruption。

**关键结果：** 早期实验确认 global utility 不能替代 contextual identity；0L 中 global per-domain correlation 只有 0.481，而显式 contextual identity 达到 1.0，并带来约 +0.1265 的 stream-margin。0F-0K 同时测试 helpful、adversarial 和 all-cold 条件，结果显示安全验证必须计入 token 成本，也不能靠单一 threshold 或“拒绝所有更新”获得安全。0M-0N 进一步验证了 identity-aware、candidate retention 和 abstention 的必要性，但 seed 176 说明少量或偏移 probe 仍不能代表长期 stream。

**这一阶段支持：** 论文需要显式 scope/identity、per-rule credit、成本核算和 non-destructive validation。  
**这一阶段不支持：** 离线机制结果不能直接写成真实 LLM 的任务提升或部署安全。

## 3. Phase 1：按证据层级排除真实任务混淆

Phase 1 没有直接进行大规模方法比较，而是依次检查 provider/accounting、任务能力、objective verifier、历史候选质量和方法效果资格。SearchQA paid pilot 证明真实执行链路可运行，但 2,448 logical calls、2,579 attempts 的结果没有形成稳定的 selector 优势；OfficeQA 和 SpreadsheetBench 的早期 arithmetic、formula semantics、schema 问题则促使实验改为 deterministic recomputation、constrained executor 和 provenance-aware abstention。2WikiMultiHopQA 因为具备多跳、比较、bridge 和 relation 结构，被选为更适合历史 skill verifier 的 substrate。

随后冻结了 `verified history -> typed candidate -> probe -> held-out` 的证据链，并把 prior identity、probe panel、gate policy、candidate/fallback 分支和双侧 token 成本分开。1S 的 192 次 development execution 只有 161/192 contract-valid、6 次 exact task success，candidate 分支 2/96，说明真实能力和候选质量仍不足。1X 的 SearchQA 为 10/12，2Wiki joint 为 6/12；1Y 虽得到 8/10 verified trajectories，却只覆盖 3/5 family。于是 1Z 在零 provider 调用下关闭 Phase 1，结论为 inconclusive。

**这一阶段支持：** 真实方法效果必须建立在 capability floor、objective verifier、独立 history 和 coverage gate 之上；模型不会做任务不能被误判为 prior 失败。  
**这一阶段不支持：** typed prior、representative probe 或 retaining gate 已经在真实 held-out 上有效。

## 4. Phase 2：先做零网络完整性，再进行受控授权

Phase 2 是独立扩展，不重标记 Phase 1 的 incomplete candidates。v1-v4 逐步修复了 710-request schedule、authorization resume、trusted verifier、16 个磁盘 hash binding 和 aggregate fingerprint；v4 通过 26/26 focused tests 及独立验收，证明的是执行安全边界，而不是方法效果。

v5-v8 用于修复 endpoint、JSON contract 和 capability gate：v5/v6 因 401 终止，v7 因响应格式失败，v8 最终达到 60/60 contract-valid、45/60 correct、70,412 tokens、CNY 0.143836，说明模型具备进入 acquisition 的接口和能力条件。v9-v10 只做 development feasibility diagnostic；v10 完成 10/10 contract-valid、8/10 correct，但 entity_bridge 为 0/2，development 输出不能进入 formal history。

v11 在第 33 次 attempt timeout 后永久停止，v12 保留 32 条成功前缀并完成 128/128 recovery calls。v12 精确使用 146,929 tokens、成本 CNY 0.301124，request identity、pacing 和 hash chain 均有效。原 materializer 错把不同任务的相同答案文本当成重复 response，于是创建了独立的 v13 零网络 correction replay：允许重复答案 hash，但仍拒绝重复 logical request、request hash 和 provider response ID。v13 对 160 条历史记录重放后 coverage gate 通过，五类 supports 为 `28/32/28/17/16`，leakage audit 通过，network/provider/model/paid counters 全为 0。

**这一阶段支持：** formal-history candidate readiness 已建立，执行和审计链路可复核。  
**这一阶段不支持：** v13 仍不是 probe、held-out 或方法效果结果；后续 provider 阶段仍需新的明确授权。


## 5. 当前能支持的结论

1. 持续路由系统需要显式的 rule identity、scope、credit 和 token accounting。
2. 非破坏性候选保留比证据不足时的永久删除更符合可恢复持续学习语义。
3. probe representativeness 是独立风险，早期少量 probe 不能自动代表后续 stream。
4. 真实任务必须经过 capability floor、objective verifier、独立 history 和 coverage gate。
5. provider、ledger、hash、成本和失败保留机制已经工程上可审计。


## 6. 当前阶段结论

当前最准确的总判断是：**项目已经完成从离线机制验证、真实能力校准到可审计 Phase 2 执行框架的建设，但真实跨任务方法效果仍未被识别。**

不是“实验没有结果”，而是一个有边界的阶段结果：Phase 0 给出了机制和失败诊断；Phase 1 证明了真实能力、verifier 和 candidate coverage 是不可跳过的前置条件；Phase 2 v4-v13 建立了可授权执行、审计链路和 formal-history candidate readiness，但真实跨任务方法效果仍待 probe/held-out 验证。

下一步需要新的、单独的 probe 授权；在获得授权前，不执行 probe、held-out、后续阶段或 formal scaling。
