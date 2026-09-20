# ACL 2027 Phase 2 v27 failure-analysis execution

The exact v27 authorization terminally hard-stopped on provider attempt 1073 after 1072 completed `qwen3.7-plus` calls. The provider returned HTTP 400, the runner made zero retries, and the authorization closed automatically.

The completed prefix contains 268 complete four-condition task grids. Request pacing, prefix order, logical identities, request hashes, and hash chains validate. No later-stage or formal-scaling call occurred.

The original terminal row copied the prior successful response object while recording the HTTP 400. The immutable ledger is preserved, and additive audit v27.1 therefore treats terminal usage as unknown. The 1072 completed calls contain 2,280,604 input tokens and 8,199 output tokens, with a known local cost lower bound of CNY 4.6268. Exact total cost is unknown.

The frozen 400-task analysis gate was not reached. No positive or negative method-effect conclusion may be drawn from v27 alone, and no spent v27 request may be retried or resumed.
