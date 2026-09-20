# TG9 Open/Close SkillBank 扩展

日期：2026-09-18

TG1 原始 SkillBank 从训练集高层 PDDL 动作构建，因此没有
`OpenObject` 或 `CloseObject` 记录；底层 `SkillIndex` 虽能识别这两类动作，
却没有可匹配的训练技能。TG9 从同一冻结训练清单的 `low_actions` 中仅提取
动作族和规范化容器类型，构建独立、可按实验条件开关的交互扩展。

- `OpenObject`：3509 条
- `CloseObject`：3570 条
- 合计：7079 条
- 输出 SHA-256：`cdc2813a46d2ddafcb54aa12cdb3cd3d6cad453d117befef9caf4cc38ba2c67c`

输出不包含坐标、图像、mask、PDDL 参数、planner action、场景状态或原始轨迹
正文。构建过程没有运行环境 episode，没有采取动作，也没有网络、模型、API
或付费调用。该扩展只在 `*_open_close_coverage` 条件中启用。
