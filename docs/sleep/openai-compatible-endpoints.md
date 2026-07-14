# OpenAI-compatible endpoints for SkillOpt-Sleep (DeepSeek, local vLLM, …)

This document describes an enhancement to the `azure_openai` backend in
`skillopt_sleep/backend.py` that lets SkillOpt-Sleep drive **any
OpenAI-compatible chat-completions endpoint** — for example DeepSeek's hosted
API or a self-hosted vLLM/Ollama server — in addition to native Azure OpenAI
deployments. It also documents a concrete end-to-end integration: running the
nightly sleep cycle inside the Antigravity IDE against DeepSeek.

## What changed

All changes are backward-compatible — the default managed-identity Azure path
is unchanged:

1. **CLI acceptance.** `skillopt-sleep run --backend azure_openai` is now an
   accepted choice in `skillopt_sleep/__main__.py` (it was previously rejected
   by argparse even though `get_backend()` understood the name).

2. **Endpoint resolution honors `AZURE_OPENAI_ENDPOINT`.**
   `AzureOpenAIBackend.__init__` resolves the endpoint as `explicit arg` →
   `AZURE_OPENAI_ENDPOINT` env → the built-in `_AZURE_ENDPOINTS` table.
   Previously a non-Azure endpoint could not be supplied at all.

3. **`openai_compatible` auth mode.** When
   `AZURE_OPENAI_AUTH_MODE=openai_compatible` (also accepts `compat`/`openai`),
   `_get_client()` builds a plain `openai.OpenAI(base_url=…)` client with
   `AZURE_OPENAI_API_KEY` instead of an `AzureOpenAI` client. This mirrors the
   auth mode already supported by the sibling `skillopt/model/azure_openai.py`
   module. (The `AzureOpenAI` client rewrites request URLs with Azure-only
   `?api-version=…` query params and deployment path segments, which non-Azure
   servers reject with `404 Resource not found` — the sleep cycle then scores
   every rollout `0.0` with no diagnostic.)

4. **Managed-identity credential guard.** The managed-identity path attaches an
   Azure AD bearer token to every request. If a custom endpoint outside
   `*.openai.azure.com` / `*.cognitiveservices.azure.com` is configured without
   explicit compat auth, the backend now raises a clear `ValueError` instead of
   sending Azure credentials to an arbitrary host.

5. **Provider-neutral request shape.** In compat mode the backend sends only the
   standard OpenAI-compatible contract (`model`, `messages`, `max_tokens`).
   Provider-specific request fields are **opt-in** via environment variables
   (below) — nothing is inferred from model-name substrings.

6. **Reliable error state.** `_call()` records the last exception in
   `self.last_call_error` (surfaced in `diagnostics.json`), clears it when a
   retry recovers, and sets an explicit `"empty response on all N attempts"`
   diagnostic when every attempt returns empty text.

## Configuration reference

SkillOpt-Sleep's `azure_openai` backend reads these environment variables
(unprefixed only — the `OPTIMIZER_*`/`TARGET_*` dual-role variables belong to
the separate `skillopt.model.azure_openai` module and are **not** used by the
sleep cycle):

| Variable | Meaning |
|---|---|
| `AZURE_OPENAI_AUTH_MODE` | `openai_compatible` (or `compat`/`openai`) selects the plain OpenAI client. Unset/other = Azure managed identity (default). |
| `AZURE_OPENAI_ENDPOINT` | Base URL of the server, e.g. `https://api.deepseek.com`. |
| `AZURE_OPENAI_API_KEY` | API key sent by the compat client. |
| `SKILLOPT_SLEEP_COMPAT_MAX_TOKENS` | Optional int (default `8192`): `max_tokens` sent in compat mode. |
| `SKILLOPT_SLEEP_CHAT_EXTRA_BODY` | Optional JSON object passed as `extra_body` for provider-specific fields. |

## How to use it

```bash
export AZURE_OPENAI_AUTH_MODE=openai_compatible
export AZURE_OPENAI_ENDPOINT=https://api.deepseek.com   # no /v1, no trailing path
export AZURE_OPENAI_API_KEY=sk-...                       # your provider key

# DeepSeek reasoning models: enable the thinking channel (opt-in, not inferred)
export SKILLOPT_SLEEP_CHAT_EXTRA_BODY='{"thinking": {"type": "enabled"}}'
export SKILLOPT_SLEEP_COMPAT_MAX_TOKENS=8192

skillopt-sleep run \
  --backend azure_openai \
  --model deepseek-v4-pro \
  --project /path/to/your/project
```

The same pattern works for any OpenAI-compatible server — point
`AZURE_OPENAI_ENDPOINT` at it, set a matching `--model`, and omit
`SKILLOPT_SLEEP_CHAT_EXTRA_BODY` unless your provider needs extra request
fields.

## End-to-end integration: Antigravity + DeepSeek

The [`examples/`](examples/) directory contains a sanitized reference of how this
was wired into the [Antigravity](https://antigravity.google/) agent IDE so the
sleep cycle runs unattended:

- **`examples/runner.py`** — a thin launcher that loads a provider key from an
  `.env` file, exports the variables above, invokes `skillopt-sleep run` with
  the DeepSeek backend, and **exits with the child's return code** so
  supervisors see failures as failures. It also implements a `session-end` hook
  that appends task-outcome metadata to a rollout-evidence log (wired to
  Antigravity's `Stop` hook) so future nights have richer sessions to mine.
- **`examples/watchdog.py`** — a minimal supervisor loop that invokes the runner
  on a fixed interval (e.g. every 4 hours) and logs non-zero exits as failures.
  On Windows this is registered as a Scheduled Task so it survives logout; on
  Linux/macOS a `systemd` timer or cron entry serves the same role.

### Verified result

On a Windows 11 host, driving the cycle against `deepseek-v4-pro` in
`openai_compatible` mode:

- A direct backend smoke test returns a live completion (no `404`,
  `last_call_error` empty, client type `OpenAI`).
- A full nightly cycle mined tasks from real IDE sessions and the held-out
  validation gate moved from `0.250 → 1.000`, **accepting** a DeepSeek-authored
  skill edit (`accept_new_best`). `diagnostics.json` for that night reports
  `"backend": "azure_openai"` with a non-empty token count and an empty
  `call_error` — i.e. a genuine optimization night, versus the prior all-`0.0`
  nights that the endpoint bug produced.
- A subsequent unattended night triggered by the watchdog completed the full
  chain (watchdog → runner → `skillopt-sleep` → DeepSeek) and the gate correctly
  **rejected** a non-improving proposal (`0.3 → 0.3`), confirming the validation
  gate behaves normally on the new backend.

Deterministic no-network coverage for the new behavior lives in
`tests/test_azure_openai_compat.py` (CLI acceptance, client selection,
endpoint/auth guard, request kwargs, retry error-state, empty-response
diagnostics, and runner exit-code propagation).

## A note on Gemini (optional, unverified fallback)

`examples/runner.py` also contains a fallback branch that, when only a Gemini key
is present, routes the **`claude` CLI backend** through a local
Anthropic-compatible proxy (e.g. [LiteLLM](https://github.com/BerriAI/litellm) on
`http://127.0.0.1:4000`) by setting `ANTHROPIC_BASE_URL`/`ANTHROPIC_API_KEY`.
There is **no native Gemini backend** in SkillOpt, and this proxy path was not
independently validated in this work — it is included only as a configuration
example. The verified, supported path in this document is DeepSeek via
`openai_compatible` mode. Treat the Gemini branch as illustrative, not tested.
