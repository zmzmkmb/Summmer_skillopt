
============================================================
  TF-IDF Token 消耗离线统计报告
============================================================

Skill 文件: E:\桌面\暑期实训\SkillOpt\outputs\searchqa_rag\best_skill.md
实验数据:  E:\桌面\视频生成\_script_work\artifacts\jos_experiment_v1\targetS\jos_formal_targetS_seed42_enriched.json
问题数:    200
检索参数:  top_k=5, budget=2000 tokens

── 规则结构 ──
  总规则数:        9
  核心规则 (Core): 1
  动态规则 (Dyn):  8

── Token 消耗对比 ──
  Full Skill (全部规则):          3,176 tokens  (13,772 chars)
  Core Only (仅核心规则):           114 tokens  (   513 chars)
  TF-IDF Top-5 (核心+检索):         1876 tokens  (均值)
  TF-IDF Top-5 中位数:              1861 tokens

── 降幅分析 ──
  Core vs Full 节省:      96.4%
  RAG (TF-IDF) vs Full 节省: 40.9%
  平均检索规则数:          4.4 / 5

── 横向对比（同 200 题）──
  TF-IDF Top-5 (本脚本):      1876 tokens (均值)
    Core Only:                    513 (来自 enriched JSON)
    TF-IDF Top-5:                1968 (来自 enriched JSON)
    MOAR:                        1917 (来自 enriched JSON)

── 结论 ──
  TF-IDF 原子化检索将 Agent skill 上下文从 3,176 tokens 压缩
  到约 1876 tokens（均值），节省 40.9%。
  在 2000-token 预算下，平均选中 4.4 条动态规则。
