# Phase 1A: SearchQA Pilot No-Cost Preflight

Date: 2026-08-08

## Decision

Phase 1A passes its predeclared no-cost preflight gates. The deterministic
SearchQA pilot harness is ready to support a separately authorized, budget-capped
real-model pilot, but this result does **not** authorize paid calls or formal
128/512-rule scaling. Repository permissions remain:

- `paid_api_allowed=false`
- `formal_scaling_allowed=false`

The next phase is Phase 1B, which may begin paid execution only after explicit
user cost authorization and a fresh verification of provider price, billing
region, model availability, and endpoint behavior.

## Frozen protocol

- Config:
  `configs/acl2027/searchqa_phase1a_pilot_preflight_v1.json`
- Config SHA-256:
  `11ad1c0a4be49fca41a01123844cdf68f16aefccc7d0858b667783ab819ecce8`
- Frozen Phase 0N source SHA-256:
  `b3050b75c43c269b9618822a46de3c7abf447ba1fa6c200323e1252f9866b85b`
- Model reserved for the later pilot: `qwen3.6-flash`
- Dataset: SearchQA test
- Replicates: deterministic example seeds `202701`, `202702`, and `202703`
- Per replicate: 8 guard probes plus 112 evaluation items
- Pairing: all seven methods use the same ordered evaluation IDs within a
  replicate; guarded methods use the same ordered probe IDs
- Disjointness: all 360 selected SearchQA item IDs are pairwise disjoint across
  the three replicates
- Manifest fingerprint:
  `e996fdf3fbbac5f934873b1b5993d87263111c5ebea88b715678e4be70c84ef1`
- Logical-call plan fingerprint:
  `9ce4bf3171abdb16d93228b41f83e4652be66794069bb1086bb87a1d3ca82557`

The seven frozen methods are:

1. `no_skill`
2. `static_full_skill`
3. `tfidf_topk`
4. `skillopt_moar_frozen`
5. `global_only_reset_comparator`
6. `global_only_selective_full_confirmation`
7. `contextual_prior_diagnostic_upper_bound`

The promoted candidate parameters are bound field-for-field to the Phase 0N
config. No threshold was changed using held-out seeds 161-180, including
adversarial seed 176.

## Complete mock workload

The deterministic, no-network mock workload completed the entire frozen plan:

| Quantity | Observed | Frozen cap |
|---|---:|---:|
| Logical calls | 2,448 | 2,448 |
| Provider attempts | 2,576 | 4,896 |
| Successful attempts | 2,448 | — |
| Failed attempts | 128 | 2,448 |
| Retries | 128 | 2,448 |
| Fallback calls | 48 | 48 |
| Input tokens | 7,673,567 | 42,000,000 |
| Output tokens | 18,385 | 2,600,000 |
| Total tokens | 7,691,952 | 44,600,000 |
| Paid calls | 0 | 0 |

At the frozen pricing snapshot and conservative accounting conversion, the
simulated accounted cost was:

- `14.58348275335 CNY`
- `2.08335467905 USD`

This is accounting simulation over mock token usage, not an incurred charge.
The paid pilot retains a hard `20.00 USD` cap, and price/region must be checked
again immediately before any paid request.

The exact identities were independently recomputed from all 2,448 JSONL
records:

- every attempt satisfies
  `total_tokens = input_tokens + output_tokens`;
- every logical call equals the sum of its persisted attempts;
- failed-attempt usage remains visible and charged;
- `2,576 = 2,448 successful + 128 failed attempts`;
- cumulative input, output, total-token, and pico-currency values exactly match
  `summary.json`.

## Reliability and negative-case checks

The harness passed focused tests for:

- strict acceptance of exactly one non-empty `<answer>...</answer>` element;
- rejection of missing, multiple, empty, unbalanced, and nested answer tags;
- no last-line parser fallback;
- deterministic, disjoint, correctly sized, method-paired manifests;
- retry and fallback visibility with failed-attempt usage;
- cap rejection before provider invocation;
- exact resume and malformed JSONL rejection;
- duplicate/unknown run and config/manifest/call fingerprint rejection;
- stable scientific summary fingerprints across resume invocations;
- direct CLI import from the repository entrypoint;
- live-mode refusal while repository/config paid permission is false.

The first complete direct-CLI preflight exposed a real packaging defect:
`ModuleNotFoundError: skillopt` occurred because executing the script directly
did not put the project root on `sys.path`. The runner now inserts the project
root before importing the package, and a subprocess regression test protects
that execution path.

An exact-resume invocation over the completed artifact produced:

- new logical calls: `0`
- provider invocations in the process: `0`
- unchanged scientific summary fingerprint:
  `dd7e644e34f82b90a3bfcc0569fcaf24225d40d2f3d385e46d2c3c5c54a86db3`

The persisted summary excludes invocation-local resume counters.

## Artifact audit

- Artifact:
  `artifacts/acl2027_searchqa_phase1a_pilot_preflight_v1`
- Calls SHA-256:
  `42f9601bfafa59f3b207dbe74dbe9f20da9d859321b41d05b427abba4bcf72a0`
- Summary SHA-256:
  `96157a5ad2b1ec5e57546decc167b3cfb66d7b1f10f9140dd3cb55f8f169c2a0`
- Aggregate/scientific fingerprint:
  `dd7e644e34f82b90a3bfcc0569fcaf24225d40d2f3d385e46d2c3c5c54a86db3`
- Expected/available artifact runs: `1/1`
- Complete grid: `true`

The repository artifact was copied from the already validated temporary
preflight output; the 2,448-call workload was not rerun. Only portable
repository-relative artifact paths were rewritten in `run_manifest.json`.
Calls and summary bytes and hashes remain unchanged.

The final related regression suite passed:

```text
77 passed in 50.56s
```

## Interpretation and limitations

All methods have mock EM/F1/substring EM of 1.0 because the deterministic mock
returns the gold answer. These values validate answer plumbing and metric
aggregation only. They are **not** real-model accuracy results and support no
scientific claim about method quality.

Phase 1A establishes infrastructure validity: immutable inputs, strict parsing,
complete paired materialization, retry/fallback provenance, exact accounting,
hard-cap enforcement, resume identity, and closed paid permissions. It does not
resolve the main scientific uncertainty from Phase 0N: whether probe evidence
is representative of downstream real-task behavior.

## Gate audit

| Gate | Result |
|---|---|
| Zero paid calls | Pass |
| Immutable input hashes | Pass |
| Deterministic/disjoint/paired manifests | Pass |
| Strict parser and negative cases | Pass |
| Exact resume and corruption fail-fast | Pass |
| Retry/fallback visibility | Pass |
| Exact token/call/cost accounting | Pass |
| Hard-cap pre-invocation enforcement | Pass |
| Live permission refusal | Pass |
| No Phase 0N threshold tuning | Pass |
| Paid pilot permission remains false | Pass |
| Formal scaling remains false | Pass |

## Next step

Define Phase 1B as a minimal, budget-capped real SearchQA pilot using this
frozen protocol. Before execution:

1. obtain explicit user approval for the maximum monetary spend;
2. re-verify Alibaba Cloud Model Studio price, international-region billing,
   model identifier, and endpoint compatibility;
3. create a new immutable Phase 1B config/artifact path rather than modifying
   Phase 1A;
4. retain the seven methods, three disjoint example replicates, strict parser,
   exact retry/fallback accounting, and hard pre-invocation caps;
5. keep formal scaling disabled until the paid pilot is audited and interpreted.
