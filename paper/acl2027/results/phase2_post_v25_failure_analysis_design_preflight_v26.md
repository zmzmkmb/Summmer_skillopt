# ACL 2027 Phase 2 post-v25 failure-analysis design preflight v26

## Scope

This is a zero-network, design-only preflight. It preserves the v23 inconclusive gate and v25 negative gate, creates no authorization, and makes no provider, model, paid, or formal-scaling call.

## Frozen failure analysis

v23 strict paired outcomes were `{'both_wrong': 19, 'both_correct': 58, 'typed_win': 2, 'typed_loss': 1}` and v25 outcomes were `{'both_correct': 55, 'both_wrong': 19, 'typed_win': 4, 'typed_loss': 2}`. Alias-tolerant sensitivity changes `2` historical discordant classification(s), including exact-match title/alias cases, but does not rescore or re-gate either completed phase. All families had frozen typed bundles with 10 examples and independently verified support; prompt length remains confounded with condition; cold/any-condition capability is reported separately.

## Falsifiable follow-up

The frozen hypothesis is that a reusable typed-prior effect must survive both strict and alias-tolerant scoring and appear as recovery from global-prior degradation, not isolated answer-string flips. The independent schedule contains 400 new tasks, 80 per skill family, and 1,600 four-condition requests. The positive, negative, and inconclusive rules are frozen in the config before any future execution.

Available candidates after exclusions: `fact_retrieval=1277, attribute_comparison=2877, bridge_attribute_comparison=2597, entity_bridge=5041, relation_inference=1439`. Task, logical-call, request-hash, and proposed provider-response-ID overlaps are all zero.

## Execution boundary

The schedule is not authorized. Any future execution requires a separately versioned explicit authorization with exact model, attempts, temperature, retries, max_tokens policy, response format, pacing, stage and cumulative CNY ceilings, and forbidden later stages.

## Integrity

Aggregate fingerprint: `6c27bceb77541e05cbb4b255796d806e72d83b95205744f10a7f877f49058564`. Network/provider/model/paid/formal-scaling counters: `0/0/0/0/0`. Authorization status: `not-authorized`.
