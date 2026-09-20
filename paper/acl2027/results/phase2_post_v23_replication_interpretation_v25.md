# Phase 2 v25 Replication Interpretation

## What Was Tested

The v24 design was executed once under an independent v25 authorization: 80 entirely new tasks, four explicit conditions, and 320 qwen3.7-plus requests. The purpose was replication-only estimation of the pre-registered contextual-typed-prior versus global-only comparison, not tuning or a new stage.

## Result

All 320 responses were contract-valid. Accuracy was cold 59/80, copied-global 61/80, global-only 57/80, and contextual-typed-prior 59/80. The paired margin was +0.0250, with 4 typed-prior wins, 2 losses, and 74 ties. The frozen gate is **negative** because the negative rule is triggered by at least two typed-prior losses. The small positive point estimate does not satisfy the positive gate and must not be reported as a causal improvement.

## Evidence Boundary

This result strengthens the paper's negative/bounded conclusion: a typed prior can be evaluated under a complete, auditable replication protocol, but this run does not establish a reliable real-task advantage over global-only context. The v20 probe pass and v23 inconclusive held-out result remain separate evidence; they are not pooled to reverse the v25 gate.

Execution governance passed: 320/320 attempts, 697,395 exact tokens, CNY 1.410264, zero retries/duplicates/terminal rows, valid hash chains/exact-prefix/pacing, and zero forbidden-stage calls. The v25 authorization is closed. No calibration, development acquisition, formal history, probe, held-out, later stage, other model, or formal scaling is authorized by this result.

Audit fingerprint: `35a683a78dd6057b8e3e5122373de024706eba033e3742c04eaf081fdba0c779`.
