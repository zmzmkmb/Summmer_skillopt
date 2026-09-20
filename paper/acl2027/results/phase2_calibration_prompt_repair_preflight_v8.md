# Phase 2 Calibration Prompt Repair Preflight v8

## Diagnosis

Phase 2 v7 completed all 60 calls, but every response was plain text while the
frozen parser accepted only an object containing exactly the `answer` key. The
v7 request referred to a frozen schema without including that schema. This was
a protocol-format failure, not admissible capability evidence.

## Repair

v8 creates 60 new logical IDs and request hashes. Each request now states the
only accepted shape directly:

```json
{"answer":"<short answer>"}
```

The system message forbids additional text, markdown, and explanation. The
provider payload also sends `response_format={"type":"json_object"}`. Requests
still use `qwen3.7-plus`, temperature 0, disabled thinking, zero retries,
one-second pacing, and no `max_tokens`.

## Verification

The v8 suite passed 6/6, including the deterministic 60-row schedule, JSON
transport forwarding, complete mock lifecycle, exact strict parsing, durable
10-call interruption recovery, duplicate prevention, terminal refusal,
unknown-usage cost handling, and irreversible closure. The combined
v8/v7/v6/handoff suite passed 27/27 and the unchanged v4 suite passed 26/26.
All network/provider/model/Qwen/paid counters remained zero.

## Decision

The preflight is closed and ready for a separately authorized calibration-only
execution. It does not authorize provider access, development acquisition,
formal history, probe, held-out evaluation, or formal scaling.

- Manifest SHA-256: `379bb127737d4059f1978a5550a1281fd33b4468f82e09cf26680963bf1334dd`
- Schedule SHA-256: `d3547c076ded0e10068338b41057f63cb0b9a67cd059c413a9eace245c13f872`
- Parent v6 route manifest SHA-256: `e949e266c827772de49ea7c6c0e498295d6ae61baf10f73d0fd3c5a123b32b99`
