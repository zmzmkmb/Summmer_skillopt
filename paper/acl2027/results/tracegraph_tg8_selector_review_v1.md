# TraceGraph TG8 Selector Review v1

Date: 2026-09-09

## Decision

Selector v1 is **not eligible for reset-only readiness**.

## Blocking findings

- It modeled the first step as `goto(target object)`, while ALFWorld exposes
  navigation to receptacles and pickup only after the object is found.
- It omitted search/open prerequisites and used an invalid two-object ordering.
- Raw snapshot hash changes could be mistaken for semantic subgoal completion.
- The lexical representation did not consume unresolved tokens.
- Trace validation trusted self-reported ledger and cycle fields.
- The lexical score was written under a misleading `family_match` field.

Selector v2 must use observable pickup/put/clean availability and event text,
canonicalized snapshots, realistic search/open chains, ledger/history
consistency checks, and adversarial tamper tests. No readiness or episode was
run from selector v1.
