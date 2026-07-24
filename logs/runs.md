# 实验记录

| ID | 日期 | 代码分支 | 改动说明 | Optimizer | Target | Gate 最终分数 | 输出目录 | 备注 |
|----|------|---------|---------|-----------|--------|-------------|---------|------|
| 001 | 0724 | main | baseline: 原始 SkillOpt, SearchQA, slow_update_gate_with_selection=**false**(force-accept) | deepseek-chat | qwen-flash | val 0.6200→0.7350, test 0.6336→0.7400, final 退化到 0.7286, 4 accept/29 reject/7 skip | `outputs/skillopt_searchqa_deepseek-chat_20260724_170800` | ⚠️ 假停滞：force-accept slow update 污染 current_skill |
| 002 | 0724 | main | **gated slow update**: slow_update_gate_with_selection=**true**, 其余同 #001 | deepseek-chat | qwen-flash | val 0.6200→0.7200, test 0.6364→0.7157, final=best 零退化, 6 accept/34 reject/0 skip | `outputs/searchqa_gated_slowupdate` | ✅ 消除退化，Epoch 2&3 各多一个 accept，无假停滞 |
