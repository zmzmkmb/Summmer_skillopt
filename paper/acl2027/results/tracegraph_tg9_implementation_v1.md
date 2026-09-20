# TraceGraph TG9 双物体机制实验实施记录 v1

日期：2026-09-18

## 研究定位

TG9 将 TG8 双物体失败拆分为两个独立因素：对象实例绑定与
`OpenObject/CloseObject` SkillBank 覆盖。四个条件保持 TG8
`observable_subgoal_anti_cycle` 的候选排序、平局规则和防循环控制不变，
运行时输入仍严格限制为 `observation`、`historical_actions` 和
`admissible_actions`。

## 已完成

1. **Stage A 冻结轨迹审计。** TG8 的 10 个双物体任务身份均失败；7 个为
   第一实例被重新计数，3 个为合法 `open` 动作缺少 SkillBank 资格。三个重复
   在每个任务内完全一致。该结果只支持机制候选，不是因果结论。
2. **Open/Close 训练技能扩展。** 从冻结 TG1 训练清单的底层动作构建 7079 条
   独立记录，其中 `OpenObject=3509`、`CloseObject=3570`；未输出几何、mask、
   PDDL 参数或隐藏状态。
3. **TG9 selector v1。** 实现对象槽位、来源/目标签名、已完成实例集合、第二来源
   区分及显式 abstain；实例拒绝与 SkillBank 资格拒绝分开记录。六类离线反例均
   有测试覆盖，未绑定控制条件保持 TG8 决策等价。
4. **任务池与排程。** 本地共有 41 个可运行双物体身份；26 个已在 TG6-TG8
   执行，剩余 15 个从未执行身份组成内部验证集。13 个身份曾出现在零执行排程，
   因此该集合不是盲确认集。冻结排程为 15 tasks x 3 seeds x 4 conditions = 180 rows。
5. **Horizon readiness。** 当前 ALFWorld 配置的 episode 上限为 50 步，因此
   `completion_by_step_50` 是冻结 primary endpoint；step 75 明确 unavailable。
6. **统计分析器。** 以 `task_identity` 为独立单位，提供 10,000 次 task-cluster
   paired bootstrap、template-cluster 敏感性分析、exact sign test、exact
   sign-flip 检验以及三个主对比的 Holm 校正。
7. **授权门。** runner 已实现，但候选配置保持 `execution_authorized=false`，且
   缺少一次性、完整哈希绑定的授权收据时会拒绝启动。

## 四条件

| 条件 | 实例绑定 | Open/Close 覆盖 |
|---|---:|---:|
| `type_level_current_coverage` | 关闭 | 关闭 |
| `instance_bound_current_coverage` | 开启 | 关闭 |
| `type_level_open_close_coverage` | 关闭 | 开启 |
| `instance_bound_open_close_coverage` | 开启 | 开启 |

## 当前边界

本次实施没有启动正式 episode，没有采取环境动作，也没有网络、provider、模型、
API 或付费调用。180 行只是冻结排程。下一步只有在 selector、schedule、两个
SkillBank、readiness、runner 和独立输出目录全部重新计算哈希后，才可生成授权
请求；没有新的精确授权不得执行。

TG9 完成后最多能够判断两个机制是否降低对应失败事件、是否改善任务身份级完成率
以及是否存在交互。15 个身份仍只能支持强机制信号或不确定结论，不能作为跨任务、
跨数据集或一般规划能力的确认性证明。
