# TraceGraph TG1 ALFWorld SkillBank Preflight

Status: planned, zero-network only. This preflight does not load trajectories,
construct a SkillBank, run ALFWorld, call a model, or create an authorization
receipt.

## Source boundary

The sole admissible future source is `$ALFWORLD_DATA/json_2.1.1/train`. Each
source record must bind one training `game.tw-pddl` to the adjacent
`traj_data.json`. Paths containing `valid_seen` or `valid_unseen` are rejected.
The initial local check found no `ALFWORLD_DATA` environment variable, so no
source manifest has been built.

## SkillBank boundary

TG1 may later derive versioned skill records from training experts, but every
record must carry a trajectory ID, gamefile and trajectory SHA-256 digests, task
type, and `source_split=train`. Raw trajectories, future expert actions,
planner state, PDDL parameters, human task descriptions, and evaluation
trajectories may not enter a runtime payload.

## Runtime boundary

The later composer may receive only observation, historical actions, and
admissible actions. It may retrieve a frozen skill record but may not receive
its raw expert trace or privileged ALFWorld state.

## TG1 completion gate

Before construction, a local preflight must validate the configuration,
source-root/split constraints, provenance schema, runtime-payload exclusions,
and zero Phase 0-6 dependency. A separately versioned construction stage may
run only after this preflight passes against a locally available training root.
## Local Source Audit Runner

`python scripts/audit_acl2027_tracegraph_tg1_alfworld_source_v1.py --source-root <ALFWORLD_DATA> --output <manifest>` is the first source-sensitive TG1 command. It is local and read-only with respect to ALFWorld data. It audits only `json_2.1.1/train`, requires each `game.tw-pddl` to have adjacent `traj_data.json`, records per-file SHA-256 provenance, and writes a manifest with `skillbank_records_created=0`. It must not be run against valid_seen or valid_unseen data.