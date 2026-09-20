# ACL 2027 Phase 2 v22 Held-out Recovery Preflight

This is a zero-network recovery preflight. It excludes all 234 spent v21 requests and opens no provider authorization.

It admits 232 completed rows from 58 complete v21 task grids, excludes the orphan cold row from the incomplete entity-bridge task, freezes 84 renamed unattempted rows, and adds a deterministic four-condition replacement grid. The combined analysis target is restored to 320 rows over 80 tasks.

Replacement task: `933d94640bd911eba7f7acde48001122`. Recovery calls: 88. Aggregate fingerprint: `8bcd47e190bf68a00e7df10c4b9d9b3ae35dbd14a076396498cd84031f7b8306`.

A separate authorization request remains closed and has no cost ceilings. Fresh explicit authorization must provide both stage and cumulative CNY ceilings before any provider call. Later stages and formal scaling remain forbidden.
