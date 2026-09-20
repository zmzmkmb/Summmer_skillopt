# Phase 4B prompt/transport contract repair preflight

The zero-network diagnostic identifies a prompt/transport visibility failure: the original six-field contract lived outside `messages`, while the provider adapter transmitted only the message list and decoding fields. The model therefore never saw the exact schema or explicit evidence IDs.

The repaired proposal embeds the exact six-field contract in both the system message and user payload, annotates every context sentence with a visible evidence ID, and audits the adapter's final transport projection. It freezes 20 wholly new development tasks and 100 five-condition rows with zero prior task, logical-call, or request-hash overlap.

No authorization was opened and no network, provider, model, paid, Phase 4C, cross-domain, or formal-scaling call occurred.

Aggregate fingerprint: `a9f5143ca6d302c0c9020fbacb2cb2e669de35e74da194dd6b4805f2346f739c`.
