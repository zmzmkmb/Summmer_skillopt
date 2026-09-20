# TraceGraph TG3 Runtime Mechanism Preflight v1

Status: zero-network mechanism audit. This stage binds immutable TG1 SkillBank and TG2 observable-state contracts and exercises only deterministic local fixtures.

## Audit cases

The audit checks an eligible candidate and edge, an inadmissible candidate that must be rejected or abstained, complete trace fields, and rejection of hidden-state payloads. No ALFWorld episode, model, provider, API, or evaluation task is used.

## Gate

A TG3 preflight passes only when every fixture decision is reproducible from observation, historical_actions, and admissible_actions; every permitted edge satisfies endpoint admissibility; every trace has all required fields; and the counterfactual inadmissible skill is rejected. This is mechanism evidence only and makes no accuracy claim.
