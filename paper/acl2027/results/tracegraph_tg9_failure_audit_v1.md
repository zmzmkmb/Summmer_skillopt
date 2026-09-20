# TG9 Stage-A：TG8 双物体失败机制冻结审计

生成时间：`2026-09-18T09:18:09.196154+00:00`

## 审计边界

本审计只读取 TG8 已冻结的 360 条轨迹、selector v3 和任务聚类分析。
未重置环境、未执行动作、未启动 episode，也未发生 network/provider/model/API/paid call。
分析单位是 `task_identity`；三个确定性重复仅用于轨迹一致性检查，不作为独立样本。

## 冻结输入

- selector：`scripts/run_acl2027_tracegraph_tg8_observable_subgoal_selector_v3.py`，SHA-256 `6aae3a8539594bdb65bdeab92f9d82c2de9ac0e287f036af1e83157751636622`
- TG8 analysis：`artifacts/acl2027_tracegraph_tg8_durable_v2/analysis_20260917_manual_v1/analysis.json`，SHA-256 `da3a08f94a0a0198b0fc3ec67e0b26903d4186366c5ed7486009aae6da8f55a9`
- rows manifest：360 rows，SHA-256 `505e86cc7e0e982147dec59632457d99e4747fe332862777bf85b22a7d521252`

## 结果

`observable_subgoal_anti_cycle` 在双物体任务中为 **0/10** 个任务身份成功。
10 个任务身份的三个重复轨迹均完全一致。失败可被互斥地分为：

- **对象实例重复计数：7/10。** 第一对象放入目标后，第二轮从第一轮目标位置重新拾取同一实例，账本随后完成但环境仍失败。
- **关闭容器技能缺口：3/10。** 目标容器的合法 `open` 动作出现在 `admissible_actions` 中，却被资格过滤拒绝，轨迹停在 `search_destination_1`。

| task | split | template | 首次偏离 step | 主机制 | 第一轮 pickup | 第二轮 pickup | 相关 open |
|---|---|---|---:|---|---|---|---|
| 18c071315858 | valid_seen | Pan-None-CounterTop | 20 | object_instance_reuse | `take pan 1 from stoveburner 2` | `take pan 1 from countertop 1` | `-` |
| 3150970cd60e | valid_unseen | SoapBar-None-Cabinet | 7 | closed_container_skill_gap | `take soapbar 1 from countertop 1` | `-` | `open cabinet 1` |
| 346112755c4b | valid_seen | SprayBottle-None-Toilet | 7 | object_instance_reuse | `take spraybottle 2 from shelf 1` | `take spraybottle 2 from toilet 1` | `-` |
| 407aa4a1ddec | valid_seen | Newspaper-None-Drawer | 27 | object_instance_reuse | `take newspaper 2 from dresser 1` | `take newspaper 2 from drawer 1` | `-` |
| 5be70830f421 | valid_unseen | SoapBar-None-GarbageCan | 14 | object_instance_reuse | `take soapbar 1 from toilet 1` | `take soapbar 1 from garbagecan 1` | `-` |
| 70730d599e26 | valid_unseen | Pillow-None-Sofa | 4 | object_instance_reuse | `take pillow 1 from armchair 1` | `take pillow 1 from sofa 1` | `-` |
| 78d2ee391b61 | valid_seen | Watch-None-Dresser | 6 | object_instance_reuse | `take watch 1 from diningtable 1` | `take watch 1 from dresser 1` | `-` |
| b848af8139b3 | valid_unseen | ToiletPaper-None-Cabinet | 7 | closed_container_skill_gap | `take toiletpaper 1 from countertop 1` | `-` | `open cabinet 1` |
| c231c61f9380 | valid_seen | SprayBottle-None-GarbageCan | 9 | object_instance_reuse | `take spraybottle 1 from sidetable 1` | `take spraybottle 1 from garbagecan 1` | `-` |
| deb8fa701f89 | valid_unseen | PepperShaker-None-Drawer | 3 | closed_container_skill_gap | `take peppershaker 2 from cabinet 1` | `-` | `open drawer 1` |

## 假设判定

- **H1（对象实例绑定缺失）得到支持。** 7/10 个身份同时满足同一对象签名、第二来源等于第一目标位置、账本完成但环境失败。
- **H2（Open/Close 覆盖不足）得到支持。** 3/10 个身份出现任务相关、合法且被拒绝的 `open` 动作，并以关闭容器停滞结束。
- **H3（两机制互补）证据不足。** TG8 是观察性冻结轨迹，没有交叉操控两个因素，不能由本审计估计交互效应。
- **H4（防循环不是主要根因）得到任务内支持。** 10/10 个失败均发生在 anti-cycle 条件下，且存在实例重复或技能缺口这一非短二周期机制。

## 结论边界

该结果是回顾性机制诊断，不是 TG9 2×2 因果实验的结果。它支持把对象实例绑定与 Open/Close 覆盖作为可证伪因素，
但不能证明二者是唯一根因、不能估计交互效应，也不能外推到其他数据集或其他智能体。TG8 的实际 horizon 为 50 steps，
75-step sensitivity 不可用。
