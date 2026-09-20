# Paper outline

## 1. Introduction

- Agent skills evolve, so a fixed prompt or fixed retriever becomes stale.
- Growing skill libraries create relevance, budget, redundancy, and forgetting problems.
- Existing pilot result: complex optimization is not automatically better at eight rules.
- Thesis: online per-rule credit plus a non-regression constraint matters more than selector complexity alone.

## 2. Problem formulation

- Stream of tasks `(x_t, y_t, d_t)`.
- Atomic skill library with stable IDs and lineage.
- Router selects subset under token and top-K constraints.
- Feedback updates per-rule utility.
- Skill mutations pass a cross-domain non-regression gate.

## 3. Method

- Atomic skill lifecycle: add, validate, activate, merge/split, decay, retire.
- Per-rule credit: shared, leave-one-out oracle, and contextual-bandit estimator.
- Budgeted router: lexical/dense candidate generation plus utility-aware constrained selection.
- Cross-domain non-regression gate.

## 4. Experimental setup

- SearchQA, three MMLU-Pro domains, and one multi-step tool-use task.
- Pilot library sizes: 8, 16, 32, 64 with a fixed in-domain base and nested cross-task distractors; submission target: 128 and 512 after provenance-controlled pool expansion.
- Baselines: Core, Full, Random, TF-IDF, BM25, dense, reranker, greedy, bandit, Exact, MOAR.
- Independent runs, paired tests, confidence intervals, latency/token/cost reporting.

## 5. Results

- Main task-performance table.
- Scale-performance-latency Pareto curves.
- Online regret and utility calibration.
- Cross-domain forgetting/non-regression.
- Fast/Slow and objective ablations.

## 6. Analysis

- When simple retrieval wins.
- Failure cases caused by correlated or conflicting rules.
- Credit-assignment errors.
- Sensitivity to library composition and target model.

## 7. Limitations and ethics

- API/model drift, benchmark contamination, cost, and rule provenance.
- Risks of persistent incorrect agent instructions.

## 8. Conclusion
