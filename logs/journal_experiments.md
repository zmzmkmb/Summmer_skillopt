# Journal Experiments Log

> MMLU-Pro Law Fast/Slow 四组消融
> Target: qwen-flash | Optimizer: deepseek-v4-flash
> Started: 2026-07-27 19:00

## 实验组

| 组别 | slow_update | edit_budget | 描述 |
|------|:--:|:--:|------|
| Initial | — | — | 初始 skill，无训练 |
| Fast-only | false | 4 | 仅 step-level patches |
| Slow-only | true | 0 (no patches) | 仅 epoch-level slow_update |
| Fast+Slow | true | 4 | 两者同时 |

## Law (660 train / 165 val / 276 test)

### Initial
- Test: 34.42% (from `mmlupro_law_true` baseline)

### Slow-only
- Source: `outputs/mmlupro_law_true` (pipelines bug masked step patches)
- Test: 38.41% (best-step), 38.41% (final)
- 关键发现: slow_update epoch 3 accept (+3.4pp)

### Fast-only
- Running: `outputs/ablation_law_fastonly`
- 

### Fast+Slow
- Running: `outputs/ablation_law_fastslow`
- 

---

## 待补充

- [ ] Law Fast-only 结果
- [ ] Law Fast+Slow 结果
- [ ] Philosophy 四组消融
- [ ] Math 四组消融
- [ ] 多 seed 重复 (seed=42, 43, 44)
- [ ] MOAR + BM25 baseline
- [ ] 规则库规模实验
