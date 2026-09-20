# ACL 2027 Phase 3B activation recovery preflight v4

The terminal v3 run spent 127 requests and completed 126. Exactly 125 completed rows from 25 full task grids are reusable. The one-row partial task and its terminal row are excluded as a whole.

The closed recovery freezes 35 task grids and 175 new requests: 34 untouched original tasks plus one deterministic same-family replacement task `bbefa25e08cc11ebbd93ac1f6bf848b6`. Combined with the reusable prefix, this yields 60 tasks and 300 analyzable rows. Spent logical-call and request-hash overlap are both zero.

No network, provider, model, or paid call was made. Execution is not authorized. Aggregate fingerprint: `f0c8170626d43cd97c854399b1c0b8194341b9a4034f2aba4b979d39b125cf36`.
