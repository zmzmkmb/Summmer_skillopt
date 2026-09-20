# TraceGraph TG1 SkillBank Construction Protocol v1

Status: design-only, zero-network, not yet executed. This protocol follows the TG1 source audit and defines how a future local construction run may transform paired ALFWorld `json_2.1.1/train` records into immutable SkillBank records.

## Inputs

The input root is `$ALFWORLD_DATA/json_2.1.1/train` only. A record is eligible only when one `game.tw-pddl` and its adjacent `traj_data.json` both exist, parse successfully, and appear in the audited source manifest. Evaluation splits and all Phase 0-6 artifacts are rejected.

## Deterministic transformation

Construction is a local deterministic parser; it makes no model, provider, or API calls. For each audited pair, read `task_type`, the ordered `plan.high_pddl` discrete actions, and the ordered `plan.low_actions` discrete actions. Create one candidate skill per contiguous high-level action span, preserving only canonical action names and normalized argument tokens. A skill ID is the SHA-256 of `trajectory_id`, span start/end, and the canonical action sequence. Duplicate IDs are byte-identical and are emitted once; conflicting duplicates are a hard failure.

## Required stored fields

Each future record must contain `skill_id`, `trajectory_id`, `source_split`, `gamefile_sha256`, `traj_data_sha256`, `task_type`, `span_start`, `span_end`, `canonical_actions`, and a construction-protocol fingerprint. The record may contain aggregate action signatures needed for eligibility, but never raw JSON, images, planner coordinates, object poses, PDDL parameters, human descriptions, future expert payloads, evaluation data, or Phase 0-6 material.

## Runtime boundary

Runtime retrieval and composition receive only `observation`, `historical_actions`, and `admissible_actions`. A retrieved skill exposes its canonical action signature and provenance ID, not the raw expert trajectory or privileged environment state. A skill is eligible only when its next canonical action is in the current admissible-action set; otherwise the constrained SkillGraph must reject or abstain.

## Construction gate

Before any record is written, a separately versioned zero-network validator must check the protocol fingerprint, source-manifest identity, deterministic IDs, required fields, forbidden-field absence, train-only paths, zero Phase 0-6 dependence, and zero network/provider/model/API counters. This protocol does not authorize construction, episode execution, WebShop work, or any provider call.
