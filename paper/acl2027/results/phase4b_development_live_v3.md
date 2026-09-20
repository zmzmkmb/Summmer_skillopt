# Phase 4B development calibration live v3

The explicitly authorized execution completed 100/100 qwen3.7-plus calls with zero retries, valid request-start pacing, exact usage accounting, and automatic authorization closure. It used 202,872 exact tokens and CNY 0.476706; known cumulative cost is CNY 11.816126.

Strict contract validity was 0/100 (0.000), below the frozen 0.95 calibration threshold. All 100 responses were JSON-parseable, but none returned the required six-field evidence-grounded contract. Contextual selection and evidence grounding are therefore not strictly assessable. The frozen Phase 4B stop rule fires, and Phase 4C remains unauthorized.

Descriptive answer extraction is non-gating because it comes from contract-invalid responses. It must not override the calibration failure.

Analysis fingerprint: `75f54900bc79b1a9a49f715219b7bfb20571c91a261e71b2e850f9e92713e885`.
