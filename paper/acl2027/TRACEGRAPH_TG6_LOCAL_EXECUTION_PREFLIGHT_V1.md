# TraceGraph TG6 Local Execution Preflight v1

This is a zero-network execution-scope preflight for the frozen 40-task TG4 held-out schedule. It defines a possible local ALFWorld episode run but does not authorize or execute it.

Scope is exactly 40 episodes, one per held-out task identity, with no retries and stop-on-first hard invariant violation. Runtime payloads are limited to observation, historical_actions, and admissible_actions. Model/provider/API calls, authorization receipts, Phase 0-6 reuse, and WebShop work remain disabled in this preflight.

A later execution requires explicit user authorization bound to this exact scope, all fingerprints, and the local-only route. Any result is mechanism evidence, not an assumed accuracy gain.
