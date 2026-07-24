# 实验记录

| ID | 日期 | 代码分支 | 改动说明 | Optimizer | Target | Gate 最终分数 | 输出目录 | 备注 |
|----|------|---------|---------|-----------|--------|-------------|---------|------|
| 001 | 0724 | main | baseline: 原始 SkillOpt, SearchQA | deepseek-chat | qwen-flash | test 0.6336→0.7400 (+16.8%), 40 steps/30min, 4 accept, epoch1 即最优 | `outputs/skillopt_searchqa_deepseek-chat_20260724_170800` | 修复 13 处 Windows GBK 编码问题 |
