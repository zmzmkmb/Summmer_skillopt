# Phase 2 replacement probe schedule preflight v16

This zero-network preflight attempted to prepare a replacement 160-call probe schedule and authorization request after the terminal v14 request.

The spent task `b6bfa34339c649398ae3b4540ed95fcf` must be removed as a complete four-condition grid, not only as its attempted `cold` row. A deterministic selector over 1,294 unused, Phase-1-excluded, and Phase-2-partition-excluded SearchQA records selected replacement task `b10f01cf02e04443a3de620e24f5f86c` from the test source split. Its payload hash is `012d97ab647485470569ddc46154f99c893ea9ecd9bb3e84f5b9da81a2ccab77`.

The executable schedule was not written. All 160 frozen probe rows have null candidate IDs, pending candidate versions, and zero model-visible prior payloads. The four request bodies differ only by condition label; they do not instantiate cold, copied-global, global-only, and contextual-typed-prior semantics. Running them would therefore fail the preregistered condition-identifiability requirement and could not support a method-effect claim.

- Replacement pool: 1,294
- Spent grid removed/planned replacement grid: 4/4 rows
- Intended shape after repair: 40 tasks x 4 conditions = 160 calls
- Schedule status: not written
- Authorization request: blocked, not submittable
- Network/provider/paid calls: 0/0/0
- Aggregate fingerprint: `cdaa7a9a5bae4f2726ad3bd1d0a6867c7d6edfb595015d03d45684c7c420e8f2`

Before an executable schedule can be frozen, the experiment must specify the exact model-visible payload for each condition and a deterministic transformation from verified v13 trajectories into global and family-scoped priors. Provider, held-out, later-stage, and formal-scaling permissions remain closed.
