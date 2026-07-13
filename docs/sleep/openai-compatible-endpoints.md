# OpenAI-compatible endpoints for SkillOpt-Sleep (DeepSeek, local vLLM, …)

This document describes a small enhancement to the `azure_openai` backend in
`skillopt_sleep/backend.py` that lets SkillOpt-Sleep drive **any
OpenAI-compatible chat-completions endpoint** — for example DeepSeek's hosted
API or a self-hosted vLLM/Ollama server — in addition to native Azure OpenAI
deployments. It also documents a concrete end-to-end integration: running the
nightly sleep cycle inside the Antigravity IDE against DeepSeek.

## What changed

Three focused changes in `AzureOpenAIBackend` (`skillopt_sleep/backend.py`),
all backward-compatible — the default managed-identity path is unchanged:

1. **Endpoint resolution honors `AZURE_OPENAI_ENDPOINT`.**
   `__init__` now resolves the endpoint as `explicit arg` → `AZURE_OPENAI_ENDPOINT`
   env → the built-in `_AZURE_ENDPOINTS` table. Previously a non-Azure endpoint
   could not be supplied at all, so calls always went to a hardcoded
   `*.openai.azure.com` host.

2. **`openai_compatible` auth mode.** When
   `AZURE_OPENAI_AUTH_MODE=openai_compatible` (also accepts `compat`/`openai`),
   `_get_client()` builds a plain `openai.OpenAI(base_url=…)` client instead of
   an `AzureOpenAI` client. This mirrors the auth mode already supported by the
   sibling `skillopt/model/azure_openai.py` module, so the two are consistent.

3. **DeepSeek request shape + error surfacing.** `_call()` sends `max_tokens`
   plus `extra_body={"thinking": {"type": "enabled"}}` for `deepseek*`
   deployments (the DeepSeek reasoning models expect this), and records the last
   exception in `self.last_call_error` so a failed night is diagnosable instead
   of collapsing to a silent empty response scored `0.0`.

### Why the previous behavior failed on non-Azure servers

The `AzureOpenAI` SDK client rewrites request URLs with Azure-only structure —
a `?api-version=…` query string and deployment path segments. A non-Azure
OpenAI-compatible server (DeepSeek, vLLM, …) does not recognize those routes and
responds `404 Resource not found`. SkillOpt-Sleep then receives an empty
response, the judge scores it `0.0`, and every night reports
`baseline 0.0 -> candidate 0.0` with no usable diagnostic. Selecting a plain
`OpenAI` client via `openai_compatible` mode avoids the Azure URL rewriting and
talks to the endpoint directly.

## How to use it

Set four environment variables and run the cycle with `--backend azure_openai`:

```bash
export AZURE_OPENAI_AUTH_MODE=openai_compatible
export AZURE_OPENAI_ENDPOINT=https://api.deepseek.com   # no /v1, no trailing path
export AZURE_OPENAI_API_KEY=sk-...                       # your provider key
# optimizer/target dual-role overrides are also honored, e.g.
#   OPTIMIZER_AZURE_OPENAI_AUTH_MODE / TARGET_AZURE_OPENAI_AUTH_MODE, etc.

skillopt-sleep run \
  --backend azure_openai \
  --model deepseek-v4-pro \
  --project /path/to/your/project
```

The same pattern works for any OpenAI-compatible server — point
`AZURE_OPENAI_ENDPOINT` at it and set a matching `--model`.

## End-to-end integration: Antigravity + DeepSeek

The [`examples/`](examples/) directory contains a sanitized reference of how this
was wired into the [Antigravity](https://antigravity.google/) agent IDE so the
sleep cycle runs unattended:

- **`examples/runner.py`** — a thin launcher that loads a provider key from an
  `.env` file, exports the four variables above, and invokes `skillopt-sleep run`
  with the DeepSeek backend. It also implements a `session-end` hook that appends
  task-outcome metadata to a rollout-evidence log (wired to Antigravity's `Stop`
  hook) so future nights have richer sessions to mine.
- **`examples/watchdog.py`** — a minimal supervisor loop that invokes the runner
  on a fixed interval (e.g. every 4 hours). On Windows this is registered as a
  Scheduled Task so it survives logout; on Linux/macOS a `systemd` timer or cron
  entry serves the same role.

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

## A note on Gemini (optional, unverified fallback)

`examples/runner.py` also contains a fallback branch that, when only a Gemini key
is present, routes the **`claude` CLI backend** through a local
Anthropic-compatible proxy (e.g. [LiteLLM](https://github.com/BerriAI/litellm) on
`http://127.0.0.1:4000`) by setting `ANTHROPIC_BASE_URL`/`ANTHROPIC_API_KEY`.
There is **no native Gemini backend** in SkillOpt, and this proxy path was not
independently validated in this work — it is included only as a configuration
example. The verified, supported path in this document is DeepSeek via
`openai_compatible` mode. Treat the Gemini branch as illustrative, not tested.
