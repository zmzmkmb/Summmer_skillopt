# Phase 1S Development Method-Effect Live Run

Date: 2026-08-11

## Outcome

The user-authorized Token Plan route was reachable and returned one
`qwen3.7-plus` response with exact usage. The run then hard-stopped on the
frozen OfficeQA response contract. No retry or second provider attempt occurred.

| Measure | Result |
| --- | ---: |
| Planned logical calls | 192 |
| Provider attempts | 1 |
| Completed contract-valid calls | 0 |
| Input tokens | 2,655 |
| Output tokens | 276 |
| Total tokens | 2,931 |
| Retry count | 0 |
| Final status | `hard_stopped` |

The first logical call was the copied-global, representative-probe,
candidate-retaining-triage, OfficeQA candidate branch for `UID0001`. The
provider response supplied exact usage, but its `calculation` field was not a
JSON object. The runner therefore persisted a terminal record and stopped.

## Interpretation

This is not a Token Plan connectivity failure: the endpoint accepted the
request and returned exact usage. It is also not typed-prior,
probe-representativeness, or triage evidence because no response passed the
task contract and no condition comparison was completed.

The terminal artifact is not resumable under the frozen Phase 1S contract. A
continuation would require a separately versioned protocol that preserves the
partial artifact, captures raw provider content on known-usage contract
failures, and receives new explicit authorization. It must not silently weaken
the response schema after observing this result.

## Integrity

- Request-plan stable SHA-256:
  `9eeb21f0a40460deb4db4d480dce3f8bc5f329a2ea3ba98b6d730f3f1391cd41`
- Request-plan file SHA-256:
  `11eeee3cd21e27c52cfeb17501ad66dfe240747ea328b44e34d367b89f2cbd7e`
- Manifest file SHA-256:
  `289f5567c07bfe225a0cef59feeadc32244d9c7540103eef34669535d8e8553d`
- Results file SHA-256:
  `3509d61a10d8ec86614f726f786e04faeeb7d5f8216c28c1a39bf25c344dd106`

Paid permission was closed immediately after the terminal audit.
