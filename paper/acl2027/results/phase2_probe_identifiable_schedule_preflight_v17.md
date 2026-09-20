# Phase 2 v17 可识别替代 Probe 计划预检

本阶段只完成 zero-network 计划与授权边界预检，没有执行 provider。目标是修复 v14 的首个 HTTP 400 后仍可解释的 probe 设计：替换已花费任务的完整四条件网格，并让四个条件在模型输入中真正可区分。

## 设计与证据链

- v15 将失败原因收敛为显式 JSON contract/transport 需要修复，因此 v17 的 system prompt 固定要求唯一 JSON 对象 `{"answer":"<short answer>"}`，请求绑定 `response_format=json_object`、`enable_thinking=false`、temperature 0、zero retries，并省略 `max_tokens`。
- v16 证明原 160 行没有 model-visible prior，不能支持条件因果比较。v17 为每个任务构造 `cold`、`global_only`、`copied_global`、`contextual_typed_prior` 四种明确输入：空 prior、跨五个 family 的 10 个例子、同一 global bundle 放入 typed slot、以及同 family 的 10 个例子。
- prior 只从 v13 verifier-confirmed formal-history trajectories 的原始 provider responses 重建；没有使用 probe 或 held-out gold 生成 prior。检查确认 prior support 与 probe/held-out task ID 均不重叠。
- v14 已花费任务 `b6bfa34339c649398ae3b4540ed95fcf` 按完整四条件网格移除；v16 选择的替代任务为 `b10f01cf02e04443a3de620e24f5f86c`，payload hash 为 `012d97ab647485470569ddc46154f99c893ea9ecd9bb3e84f5b9da81a2ccab77`。

## 预检结果

- 任务/条件：40 x 4 = 160 rows；每个条件 40 rows。
- 身份：160 个 logical request ID 和 request hash 均为新值，且与原 v14 probe schedule 全集不相交；stage index 为 1..160。
- coverage eligibility：v13 formal-history supports 为 fact retrieval 28、attribute comparison 32、bridge attribute comparison 28、entity bridge 17、relation inference 16，coverage gate 通过。
- 完整性绑定：v4 aggregate `17752bb2d26f38e253c91a5f789654dad209eb6c16a1dd68203a942fa354e8d9`、v13/v16 acceptance、v14 terminal ledger、原 probe schedule/gold 和 held-out gold 均从磁盘复验。
- 回归：完整 zero-network ACL v1-v4/v13-v17/handoff 回归 `112/112`，新增 v17 authorization-binding 回归 `4/4`。
- network/provider/model/paid calls：`0/0/0/0`。

本预检 aggregate fingerprint：`68a173ca4e45f58879221ca4c15c9df7bc08dcccae452d496cdb22d9e6cdaa8a`。

## 授权状态

新申请文件保持关闭状态，等待新的、明确的 probe-only 用户授权。拟授权边界是 `qwen3.7-plus`、160 attempts、temperature 0、retries 0、无 `max_tokens`、stage/cumulative CNY 7.50；不包括 held-out、任何后续 Phase 2 stage 或 formal scaling。v14 closed authorization 未被修改。

## 文件

- 配置：`configs/acl2027/phase2_probe_identifiable_schedule_preflight_v17.json`
- 关闭的授权申请：`configs/acl2027/phase2_probe_only_authorization_request_v17.json`
- artifact：`artifacts/acl2027_phase2_probe_identifiable_schedule_preflight_v17/`

只有在收到针对上述精确边界的新授权后，才允许重新运行 zero-network gates 并执行 v17 probe；执行结束后必须立即关闭授权并审计 ledger。即使 probe gate 通过，也不能自动进入 held-out、后续阶段或 formal scaling。
