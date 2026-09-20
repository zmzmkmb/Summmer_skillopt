# Phase 2 Token Plan route-repair preflight v6

## Decision

The zero-network v6 route repair passed and remains closed. It preserves the
terminal v5 ledger and replaces the incorrect public DashScope transport with
the previously successful Beijing Token Plan route for any future separately
authorized calibration run.

## Frozen route

- endpoint: `https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`
- key source: `DASHSCOPE_API_KEY`
- model: `qwen3.7-plus`
- temperature: `0`
- thinking: disabled
- pacing: one second
- retries: zero
- `max_tokens`: omitted
- timeout: 120 seconds

The future authorization boundary remains calibration-only: exactly 60
logical calls and at most 60 provider attempts, with CNY 0.50 stage and
cumulative ceilings. Development acquisition, formal history, probe,
held-out, and formal scaling remain forbidden.

## Verification

The v6 route, adapter, execution runner, terminal v5 audit, and handoff suite
passed **26/26**. The unchanged v4 focused suite passed **26/26**. Mock
coverage includes a complete 60-call lifecycle, durable interruption after 10
calls followed by exact-prefix completion without duplicates, and permanent
refusal to resume a terminal provider error.

The preflight manifest binds the config, adapter, runner, and both v6 test
sources. Its file SHA-256 is
`e949e266c827772de49ea7c6c0e498295d6ae61baf10f73d0fd3c5a123b32b99`.
The parent v4 aggregate fingerprint remains
`17752bb2d26f38e253c91a5f789654dad209eb6c16a1dd68203a942fa354e8d9`.
The preserved v5 terminal ledger SHA-256 remains
`f72293dd2011300f606670aacd433b1674b45901c3c3f355aeeba5b2b517cb4e`.

Network, provider, model, Qwen, and paid API calls were all **0**. No
authorization was opened.
