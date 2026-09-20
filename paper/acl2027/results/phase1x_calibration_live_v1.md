# Phase 1X: bounded live capability calibration

## Purpose

Phase 1X executes the immutable Phase 1W transport plan once under the user's
fresh authorization for exactly 24 `qwen3.7-plus` Token Plan attempts. The run
measures no-skill capability on 12 admitted SearchQA tasks and 12 frozen
2WikiMultiHopQA tasks before any history extraction or method-effect execution.

This is a capability and substrate-eligibility result. It is not evidence for
typed priors, sparse-probe representativeness, or candidate-retaining triage.

## Execution audit

The unique live run completed all 24 logical calls and all 24 provider attempts.
Retries were zero, `max_tokens` was omitted, exact usage was known for every
attempt, and raw provider text was preserved for every result. No malformed,
schema-invalid, unknown-usage, or terminal record occurred.

```text
status:                    completed
planned/recorded calls:    24/24
provider attempts:         24
retries:                   0
input tokens:              27,981
output tokens:                884
total tokens:              28,865
exact accounted cost:      CNY 0.063034
authorized local ceiling:  CNY 100
```

Artifact hashes:

```text
transport plan file: 046d844de9efdb5267f002a29f056d2e7aa84081fcebe1eb0ab8655332cc921d
transport plan stable: 099f899a2c5c06a1773b43d55909f5ac7e446ea37af9b9aceeed4441f2fa08b8
results JSONL:        da20c987505f0df11aa037fd6392ec5641390ad5f6e95515efe212e4f6a6e846
run manifest:         cb8171cb8e0861f817dfa6d4eee9be6d0238d96e5dbb402a7d09de015c05ed8e
authorization config: 5b544c6296f5803933ac49714faddfe066b6815956eeaadd4f1708cab85a650c
analysis fingerprint:  027b39fd5bf07d98d29590c7bdd35ab00393f61fc33ce37934a888f31b55fcee
```

## Capability results

| Substrate | Contract valid | Answer correct | Support correct | Joint correct |
| --- | ---: | ---: | ---: | ---: |
| SearchQA | 12/12 (100.00%) | 10/12 (83.33%) | n/a | 10/12 (83.33%) |
| 2WikiMultiHopQA | 12/12 (100.00%) | 7/12 (58.33%) | 9/12 (75.00%) | 6/12 (50.00%) |

SearchQA remains admitted by policy; its fresh result is diagnostic rather than
an inclusion blocker.

## Frozen 2Wiki eligibility decision

The Phase 1T gate was applied without retuning. 2Wiki passes every criterion:

- 12 calibration tasks and 100% contract validity exceed the 90% minimum;
- 6/12 joint successes give 50% baseline accuracy, inside the inclusive
  25%-75% non-floor interval;
- the six joint successes occur on six distinct task IDs, so the maximum share
  from any one task ID is 1/6, below the 1/2 limit;
- successes cover three frozen task types: `bridge_comparison`, `comparison`,
  and `compositional`;
- successes cover three reusable skill families:
  `bridge_attribute_comparison`, `attribute_comparison`, and `entity_bridge`;
- answer-plus-support verification is automatic and was frozen before live
  execution.

The fourth calibration type, `inference`, had no joint success in this small
panel. This does not fail the preregistered three-type gate, but it remains a
coverage limitation for later history construction.

Decision: `2WikiMultiHopQA` is eligible for the next zero-network history and
skill-candidate materialization preflight. This decision does not authorize
provider execution or scaling.

## Scientific interpretation

The result removes the severe executor-floor problem observed on OfficeQA and
SpreadsheetBench and establishes that both retained substrates can supply
verified successes. It does not yet show that extracted experience transfers,
that typed priors improve routing, that sparse probes represent downstream
streams, or that retaining candidates improves deployment outcomes.

The ACL main claim therefore remains partially supported. Phase 1Y should
materialize verified history trajectories and typed skill candidates from the
already frozen SearchQA and 2Wiki history partitions, audit support and scope,
and freeze a zero-network execution design before seeking any new provider
authorization. Paid permission is closed and the 24-call authorization is
exhausted.
