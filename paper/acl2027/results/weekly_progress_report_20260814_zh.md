# ACL 2027 论文项目阶段性进展报告

**报告日期：** 2026-08-14  
**项目主题：** 面向持续学习技能路由的作用域感知先验、代表性验证与非破坏性候选保留

## 一、本周完成工作

本周完成了 Phase 2 的模型能力校准、Token Plan 路由修复和后续实验激活设计，并对前期真实任务实验的证据边界进行了系统梳理。当前实验仓库累计包含 33 个完成阶段和 1070 个不可变运行记录，所有关键运行均有配置、请求/响应账本、哈希和审计结果可追溯。

### 1. 完成 Phase 2 校准并修复输出契约问题

早期 Phase 2 v7 校准完成了 60 次调用，但模型全部返回纯文本，而冻结解析器要求严格 JSON，因此严格有效率为 0。该结果被保留为负面证据，没有通过宽松解析“修正”为成功。

随后完成 v8 的零网络修复与重新校准：在 system prompt 中显式规定 `{"answer":"..."}` 输出结构，并使用 JSON-object response mode。v8 完成 60/60 次 `qwen3.7-plus` 调用，全部满足严格 JSON 契约，45/60 答案正确（75%，满足预注册准确率门槛），总计 70,412 tokens，成本 CNY 0.143836，零重试、零重复、无 `max_tokens`。校准资格门通过，授权已自动关闭。

### 2. 固化后续 Phase 2 的因果实验设计

已冻结 Phase 2 B 方案：覆盖五类任务 family，采用 calibration、development-acquisition、formal history、probe 和 held-out 的严格分区设计。完整方案最坏为 710 次请求，所有任务 ID、payload、request hash、账本和成本边界均被预注册。

本周新增 post-calibration activation 预检：v8 的通过仅被作为“模型与输出契约可用”的前置条件，不被解释为 prior-transfer 或 triage 的方法效果。任何下一步 live 执行首先只能是 10 次 development-acquisition 诊断；formal history、probe、held-out 和 formal scaling 仍关闭，必须分别预检和授权。

### 3. 完成前期实验的证据重估

对已有实验的解释边界进行了收紧：

- 合成 held-out 实验支持“先验的身份和作用域重要”。`global_only` 与 `contextual` 处理能避免 copied-global 的错误继承；非破坏性 accept/reject/abstain 与候选保留在合成环境中有正面证据。
- 稀疏 probe 是否能预测真实 downstream 安全性尚未建立，仍是最重要的科学风险。合成 held-out 和真实任务 proxy-to-real 都发现了不一致现象。
- Phase 1 的真实任务开发实验没有提供稳定的 prior-effect 或 triage-effect 证据。成功率过低且集中于单一任务；gate 标签没有形成真实的状态转移，因此不能声称三路 triage 优于简单基线。
- OfficeQA 与 SpreadsheetBench 已不再被当作自由模型推理能力的直接证据，而被调整为 executor-backed、constrained 的验证基底，用于研究验证、abstain 和受控比较。

## 二、当前论文结论

当前论文最稳健的结论是：在持续技能路由中，历史先验需要被显式标注作用域；验证证据是否具有代表性必须被检验；在证据不足或负面时，保留候选并允许 abstain 比不可逆删除更可审计、更安全。

该结论在合成 held-out 环境中具有较强支持，在真实跨任务环境中尚未建立充分的因果优势证据。因此论文定位已从“普遍提升真实持续任务性能”收缩为“作用域感知、代表性验证和非破坏性部署的可验证框架与实证风险分析”。

## 三、当前风险与问题

1. 真实任务中 prior 身份效应尚未稳定复现。
2. 稀疏 probe 对 downstream 的代表性未被证明，且已有反例风险。
3. 当前旧版 staged runner 不能直接承接 v8 校准账本进入 development-acquisition；需要新增独立的 post-v8 runner，保持请求前缀、授权和账本隔离。
4. Phase 2 尚未进入 formal history、probe 或 held-out，因此不能对主张的真实因果效果作正面结论。

## 四、下周计划

1. 完成 post-v8 development-acquisition runner 的零网络预检，包括 10 个新 request hash、断点恢复、重复拒绝、未知 usage/异常终止和授权关闭测试。
2. 在独立授权下执行最多 10 次 development-acquisition 调用，仅评估五个 family 的采集可行性；其结果不进入正式 history。
3. 根据采集覆盖结果决定是否值得冻结 formal-history 方案；若覆盖不足，将报告为 capability/coverage-incomplete，而非方法失败。
4. 继续保持 formal history、probe、held-out 和 formal scaling 关闭，直至获得新的预检结果和单独授权。

## 五、可核查材料

- `paper/acl2027/CONTRIBUTION_EVIDENCE_LEDGER.md`
- `paper/acl2027/experiment_roadmap.md`
- `paper/acl2027/experiment_state.json`
- `paper/acl2027/results/phase2_calibration_live_v8.md`
- `paper/acl2027/results/phase2_postcalibration_activation_preflight_v9.md`
