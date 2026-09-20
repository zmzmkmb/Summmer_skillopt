# Phase 0 execution plan

This plan operationalizes `experiment_roadmap.md`. Phase 0 results are instrumentation evidence only and must not be described as downstream LLM accuracy.

## Phase 0A — Offline continual-routing harness (current)

- deterministic multi-domain task stream and budgeted policy interface;
- All-Cold, noisy, shuffled, and adversarial utility initialization;
- random, relevance Top-K, greedy utility, UCB, Thompson Sampling, exact knapsack, and oracle upper-bound policies;
- shared, leave-one-out, and oracle per-rule credit assignment;
- cumulative inference/update/probe token accounting;
- Tokens-to-Target, regret, utility calibration/rank correlation, and forgetting metrics;
- per-run JSON, fingerprints, resumable execution, aggregate JSON/CSV, and deterministic tests.

Decision gate: identical configs and seeds reproduce fingerprints, and leave-one-out cost appears in total-token comparisons.

## Phase 0B — Safety and scale

- add explicit non-regression gates and safety/plasticity metrics;
- construct provenance-preserving 128 and 512-rule libraries;
- add domain drift, conflicting, duplicate, and malicious-rule conditions;
- connect existing Greedy, BM25, TF-IDF, and MOAR selectors to the harness.

## Phase 0C — Proxy validation package

- retain strong methods after three seeds;
- produce token–reward, scale–quality–latency, recovery, and forgetting plots;
- audit configs, run IDs, fingerprints, failures, and resumability;
- choose five to seven methods and budgets for the paid SearchQA pilot.

## Phase 1 entry requirement

Do not spend API budget until Phase 0 passes reproduction and cost checks. Then the user only needs to confirm model/API access and a maximum pilot budget.

## Phase 0B checkpoint ? August 6, 2026

Completed the contextual-utility and non-regression-gate slice: 54/54 offline runs, three seeds, All-Cold and adversarial initialization, full token accounting, and safety/plasticity metrics. The hard gate removes measured forgetting with 91.7% block acceptance, but adds about 37.7% total cost. Contextual utility does not improve over global utility in the current single-home-domain simulator. Before scale or API experiments, Phase 0C must introduce genuinely context-dependent, conflicting, drifting, duplicate, and malicious rule utility. See `paper/acl2027/results/phase0b_contextual_nonregression_v1.md`.
