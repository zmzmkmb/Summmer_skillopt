# TraceGraph TG8 Preflight Review v3

Date: 2026-09-09

## Decision

TG8 v3 fixes the major factorial and step-budget defects and is suitable as the
basis for selector implementation. It remains **no-go for readiness** until a
corrected frozen schedule and zero-execution manifest are issued.

## Remaining findings

1. The schedule contains 30 task identities but only 29 globally unique
   templates: `pick_two_obj_and_place-SoapBar-None-GarbageCan` appears in both
   splits. The v3 code and tests enforce uniqueness only within a
   family-by-split cell.
2. The hash-derived condition order is valid but position-imbalanced. First
   position counts are 33, 20, 19, and 18 across the four conditions. A
   hash-ranked cyclic Latin rotation should hold every condition-position
   count to 22 or 23 across 90 task-replicate blocks.
3. The zero-network design manifest labels 360 materialized schedule rows as
   `completed_calls=360`, although episodes, actions, and external calls are
   all zero. The corrected manifest must distinguish planned/materialized rows
   from executed calls.
4. Reuse of v1/v2 design identities is scientifically admissible because both
   manifests record zero episodes, but validation should also require zero
   actions, zero external calls, closed authorization, and absence of result
   data.

## Gate

Proceed with selector implementation and adversarial fixtures against the v3
contract. Before reset-only readiness, create v4 with global template
uniqueness, balanced Latin condition order, and explicit zero-execution
accounting. No episode authorization is open.
