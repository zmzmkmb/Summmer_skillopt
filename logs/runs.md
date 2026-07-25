# 实验记录

| ID | 日期 | 代码分支 | 改动说明 | Optimizer | Target | Gate 最终分数 | 输出目录 | 备注 |
|----|------|---------|---------|-----------|--------|-------------|---------|------|
| 001 | 0724 | main | baseline: 原始 SkillOpt, SearchQA, slow_update_gate_with_selection=**false**(force-accept) | deepseek-v4-flash | qwen-flash | val 0.6200→0.7350, test 0.6336→0.7400, final 退化到 0.7286, 4 accept/29 reject/7 skip | `outputs/skillopt_searchqa_deepseek-chat_20260724_170800` | ⚠️ 假停滞：force-accept slow update 污染 current_skill |
| 002 | 0724 | main | **gated slow update**: slow_update_gate_with_selection=**true**, 其余同 #001 | deepseek-v4-flash | qwen-flash | val 0.6200→0.7200, test 0.6364→0.7157, final=best 零退化, 6 accept/34 reject/0 skip | `outputs/searchqa_gated_slowupdate` | ✅ 消除退化，Epoch 2&3 各多一个 accept，无假停滞 |
| 003 | 0725 | main | **模拟退火 Gate**: use_annealing=true, T0=0.02, gated slow update | deepseek-v4-flash | qwen-flash | val 0.6250→0.7300, test 0.6336→0.7214, final 退化到 0.7107, 6 accept+5 annealing/29 reject | `outputs/searchqa_annealing` | ⚠️ 退火有效（5次触发），但 Step 24 退火接受劣解后无法恢复，导致 final 退化 |
| 004 | 0725 | main | **RAG TF-IDF**: use_rag=true, method=tfidf, top_k=5, budget=2000, gated slow update | deepseek-v4-flash | qwen-flash | val 0.6200→0.7300, test 0.6321→**0.7250**, final=best 零退化, 5 accept/32 reject/3 skip, 31M token | `outputs/searchqa_rag` | ✅🏆 TF-IDF 检索有效 |
| 005 | 0725 | main | **RAG Random 对照**: use_rag=true, method=random, top_k=5, budget=2000 | deepseek-v4-flash | qwen-flash | val 0.6100→0.7300, test 0.6293→0.7193, final=best, 6 accept/34 reject, 34M token | `outputs/searchqa_rag_random` | 🔬 TF-IDF 领先随机 +0.0057，确认检索有增量收益 |
| 006 | 0726 | main | **RAG Core Only**: method=core_only, 无动态规则 | deepseek-v4-flash | qwen-flash | val 0.6050→**0.7350**, test→**0.7336**, final=best, Step 4 之后全部 reject | `outputs/searchqa_rag_coreonly` | 🔬🏆 Core Only 意外最高分！说明核心规则是主要收益来源，动态规则当前粒度太粗 |
