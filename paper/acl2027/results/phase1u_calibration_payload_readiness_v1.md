# Phase 1U: calibration payload readiness

## Purpose

Phase 1U admits SearchQA as an experiment anchor under the user's explicit
instruction and materializes the second gold-bearing substrate required by the
Phase 1T held-out design. It binds complete local SearchQA calibration payloads,
audits 2WikiMultiHopQA source bytes and schema, creates deterministic disjoint
partitions, and freezes answer-plus-supporting-evidence verification before any
model response exists.

This phase prepares data and measurement contracts. It does not run a provider,
measure capability, or establish a paper method effect.

## Source provenance

The normative source is the 2WikiMultiHopQA author repository:

```text
https://github.com/Alab-NII/2wikimultihop
```

Its README identifies the April 7, 2021 `data_ids_april7.zip` release as the
ID-bearing release with corrected paragraph sentence segmentation. The
author-hosted Dropbox endpoint repeatedly timed out in this environment, so the
public Kaggle dataset `tranleanhpha/rescoreembedding` was used only as a byte
transport mirror. It is not treated as the normative source.

The materialized gold pool contains the mirrored development file and answer-ID
aliases:

| File | Bytes | SHA-256 |
|---|---:|---|
| `dev.json` | 57,613,717 | `21b0a6ffef454f887b5a7a6115db443d3476e99fefeb05d4c5fb73be01582554` |
| `id_aliases.json` | 17,501,406 | `f08ffcb6c2cefca9bdbe86b4248d6ad7a7743762d3f7264c14ff0bae85726fb6` |

The remote inventory also records the 707,811,331-byte train file and
53,837,823-byte test file; they were not downloaded because the 12,576-record
gold-bearing development pool is sufficient for all frozen Phase 1T partitions.

## Audit result

The immutable audit passed all 10 checks:

- all 12 SearchQA calibration identities bind to complete local question,
  context, and answer payloads;
- the 12-row SearchQA payload hash is
  `502d05b7709072d5951a1aa576e433c1ee398288e217dfaff3df23be898126a4`;
- 2WikiMultiHopQA has 12,576 records and 12,576 unique IDs;
- duplicate IDs, missing required fields, invalid supporting references,
  evidence-ID length mismatches, blank answer IDs, and invalid task types are
  all zero;
- type counts are 2,751 `bridge_comparison`, 3,040 `comparison`, 5,236
  `compositional`, and 1,549 `inference`;
- calibration, history, development-probe, and held-out downstream partitions
  have exact counts 12, 120, 24, and 120 and are pairwise disjoint;
- gold answer/support fixtures pass, while a wrong answer and missing support
  fail;
- provider calls and paid calls remain zero.

Decision:

```text
payloads_materialized_execution_closed
```

Config SHA-256:

```text
46e5d38eb6c886b5b276a0aced89055c8332193a49fb7ff160cfd795e85d9dc9
```

Aggregate fingerprint:

```text
6604ef63517129291aead96afaebb5e21fc6ac30931f0b4ad3350bcb90eeb41a
```

## Frozen contracts

Partition selection sequentially assigns still-unassigned IDs ordered by
`sha256(seed + ':' + id)`. Partition SHA-256 values are:

| Partition | Count | SHA-256 |
|---|---:|---|
| calibration | 12 | `a98479817858e4aea42435e1cdbd4eba10fcc49208105523851e7ccb9f888e29` |
| history | 120 | `6aa5ead61a00587b9bb99e56ee74cfd07f8027f2da4e5d8372839911581ab15f` |
| development probe | 24 | `aa4abce9facaae836534d116d40f0a8cc635b0507743103a68ac470dcf3efb12` |
| held-out downstream | 120 | `4e1af1fa8be20c4f4b2e64139d88911579e0c88973ae9feb7ec77fdcfcb93977` |

Answer verification follows the author's normalization and exact-matches the
gold answer or an alias for `answer_id`. Supporting evidence uses
case-insensitive exact set equality over `[title, sentence_index]` pairs. Joint
success requires both checks. Dataset `type` metadata and its skill-family
mapping are frozen before model responses.

## Scientific interpretation

Phase 1U removes dataset availability, identity, partition, and verifier
ambiguity for the next capability calibration. SearchQA is admitted by explicit
experiment policy; its Phase 1T gate remains diagnostic rather than an
inclusion blocker. 2WikiMultiHopQA is now a complete, hash-bound candidate but
has not yet demonstrated a non-floor model capability level.

No central ACL claim is strengthened by this materialization alone. Typed-prior
benefit, sparse-probe representativeness, and candidate-retention benefit remain
unconfirmed on this substrate.

## Next step

Phase 1V should be a zero-provider-call calibration request and verifier
preflight for the two 12-task payloads. It should freeze leakage checks, output
schemas, exact request identities, parser/verifier behavior, usage accounting,
and hard stops before any separate authorization is considered. Paid calls,
`qwen3.8-max`, staged/full scaling, and the legacy OfficeQA/SpreadsheetBench
batch remain closed.
