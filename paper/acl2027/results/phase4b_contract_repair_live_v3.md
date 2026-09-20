# Phase 4B-R3 repaired development calibration

The explicitly authorized run is terminally closed and incomplete. An external command timeout left the Python child process running; it was explicitly terminated after 73 request-start entries and 72 complete responses. The final start has no response record and is conservatively treated as a spent provider attempt. It must never be retried.

The first 72 response rows and all 73 request-start rows have valid hash chains and valid one-second pacing. The original closure snapshot was written at 67 starts and 66 responses; six additional starts and six responses arrived before the background process was terminated. Authorization was not reopened.

Known usage for the 72 recorded responses is 204,266 tokens and CNY 0.512794; known cumulative cost is CNY 12.328920. Usage for the orphan attempt is unknown.

The partial non-gating diagnostic finds 72/72 strict contract-valid responses (1.000). Because the frozen 100-row calibration did not complete, no Phase 4B calibration gate is evaluated and Phase 4C remains unauthorized.

Terminal audit fingerprint: `f32e141b1ba15637cdb9b99fa360a59996adf613b90d610b7ef206bce14773e1`.
