# ACL 2027 Phase 2 v29 recovery execution

The exact v29 recovery authorization terminally hard-stopped on provider attempt 310 after 309 completed `qwen3.7-plus` calls. The remote endpoint closed the connection without a response. Zero retries occurred and authorization closed automatically.

The ledger contains 77 complete four-condition task grids plus one orphan completed `cold` row from the terminal task. Only the 308 rows from complete grids are reusable in a future combined analysis. The orphan row and terminal request remain spent provenance and must not be retried.

Known v29 usage is 742,397 input tokens plus 2,842 output tokens, for a CNY 1.50753 stage-cost lower bound. Together with the v27 known lower bound, cumulative known cost is CNY 6.13433. Terminal usage and exact cumulative cost are unknown.

The 400-task analysis gate was not reached. No positive or negative method-effect conclusion may be drawn, and no later stage or formal scaling is authorized.
