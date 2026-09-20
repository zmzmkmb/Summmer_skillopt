# Phase 1B SearchQA Token Plan Pilot Preflight

## Status

This is a **zero-network dry-run** of the separately frozen Phase 1B protocol. It is not a real-model accuracy result and does not authorize the paid pilot.
The immutable v1 config and artifact remain preflight-only and must not be
mutated or rerun.

## Frozen inputs

- Config: `configs/acl2027/searchqa_phase1b_paid_pilot_v1.json`
- Config fingerprint: `a94abb9a478da45a7eabac71db991020e9eed1724112b14d5448a235e0756ca0`
- Provider: Alibaba Cloud Token Plan, Beijing endpoint
- Model: `qwen3.6-flash`
- Accounting: token-only; monetary fields are explicitly zero and must not be interpreted as zero provider billing

## Dry-run totals

- Logical calls: 2,448
- Provider attempts: 2,579
- Failed attempts/retries: 131
- Fallback calls: 48
- Input tokens: 7,658,095
- Output tokens: 18,406
- Total tokens: 7,676,501
- Paid calls: 0

## Gates

All Phase 1B preflight gates passed: complete call plan, exact token identities, strict parser, exact resume identity, retry/fallback provenance, hard-cap enforcement, and live-permission closure. The mock accuracy values are plumbing-only.

The artifact audit independently confirmed the config, dataset, split manifest,
skill, frozen Phase 0N source, replicate manifest, call plan, aggregate, and
persisted-call fingerprints. It also confirmed exact 2,448-call coverage,
unique run IDs, 2,579 provider attempts, 131 failed attempts/retries, 48
fallback calls, 7,658,095 input tokens, 18,406 output tokens, 7,676,501 total
tokens, and zero paid calls.

The related regression suite passed with 80 tests on August 9, 2026. The
provider adapter now explicitly constructs the OpenAI-compatible SDK client
with `max_retries=0`, preventing hidden SDK retries from bypassing the
experiment attempt ledger.

## Live launch blockers

The v1 artifact is not a runnable paid protocol:

- `assert_execution_allowed()` rejects every live execution, even if both
  permission flags were true.
- `execute_preflight()` always instantiates `DeterministicMockProvider`; the
  `TokenPlanProvider` is not connected to the execution loop.
- Prompt rendering, TF-IDF retrieval details, MOAR execution parameters, and
  the relevant utility source fingerprints are not fully frozen.
- The named guard policy is not operationalized in the real-model runner.
- Token-only accounting fixes `cost_usd` at zero and therefore cannot enforce
  the required maximum monetary-spend authorization.
- The runner source fingerprint is absent from the artifact manifest.
- The bounded smoke response reported 218 completion tokens despite a requested
  32-token output limit, so reasoning-token, maximum-token, and billing
  semantics require fresh provider verification.
- Existing v1 run and manifest identifiers retain `phase1a` labels. Correcting
  them in place would invalidate the immutable artifact.

## Next step

Keep v1 as validated preflight evidence. Before any provider call, obtain
explicit authorization for the maximum monetary spend. Then freshly verify
model, endpoint, region, price, billing currency, and token-limit semantics and
freeze a new versioned live protocol/config with executable prompt, retrieval,
MOAR, guard, accounting, retry, and source-fingerprint contracts.
`paid_api_allowed` and `formal_scaling_allowed` remain false.

## August 9, 2026 provider verification

The user authorized a maximum Phase 1B monetary spend of **CNY 200**. This
satisfies the user-budget gate but does not by itself open execution.

Fresh Alibaba Cloud documentation confirms that Token Plan supports
`qwen3.6-flash` in China North 2 (Beijing) through the OpenAI-compatible base
URL already recorded by v1. Token Plan consumption is measured in Credits and
depends dynamically on model, token usage, thinking mode, and tool calls.

The same current documentation explicitly prohibits Token Plan Personal and
Team API keys from use in automated scripts, custom application backends, or
non-interactive batch-call scenarios. The 2,448-call SearchQA runner falls
within that prohibited category. Therefore the full scientific pilot must not
use the Token Plan key, despite the successful bounded smoke request.

Alibaba Cloud's model page additionally states that standard pay-as-you-go
access for `qwen3.6-flash` will stop at **2026-08-10 00:00**, after which it is
available only through Token Plan for AI programming-tool scenarios. Because
the current date is 2026-08-09 and the scientific runner is not yet frozen for
live execution, the experiment must not rush a run before that deadline.

One currently documented pay-as-you-go migration candidate is Beijing
`qwen3.5-flash`, priced for inputs at or below 128k tokens at CNY 0.2 per
million input tokens and CNY 2 per million output tokens. At those rates, the
v1 dry-run token totals correspond to approximately CNY 1.568, while the
existing 42.0M input / 2.6M output token hard caps correspond to CNY 13.60.
These are planning estimates only. Changing the model would create a new
scientific protocol and requires explicit user approval, a new immutable v2
config, and a fresh bounded smoke test.

Decision: keep `paid_api_allowed=false` until either Alibaba Cloud provides
written permission for Token Plan batch experimentation or the user explicitly
approves migration to a compliant pay-as-you-go model. Any route or model
change requires a new immutable v2 config.

Official sources accessed August 9, 2026:

- Alibaba Cloud Model Studio, "Token Plan (Personal Edition)"
- Alibaba Cloud Model Studio, "Connect third-party programming tools"
- Alibaba Cloud Model Studio, "`qwen3.6-flash` model information"
- Alibaba Cloud Model Studio, "`qwen3.5-flash` model information"
- Alibaba Cloud Model Studio, "OpenAI compatible - Chat"
