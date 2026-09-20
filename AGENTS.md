# SummerSkillOpt Agent Instructions

## ACL 2027 persistent experiment

For any request to continue, inspect, plan, or run the ACL 2027 experiments, first read:

- `paper/acl2027/experiment_state.json`
- `paper/acl2027/CROSS_CONVERSATION_PROTOCOL.md`

Then run `python scripts/acl2027_experiment_handoff.py validate` before launching work. Treat the repository state as authoritative over prior chat summaries. Do not rerun completed immutable artifacts that validate. Respect `execution_policy`, `current_phase.next_actions`, and `expected_write_scope`.

Because `graphify-out/graph.json` exists, use `graphify query` first for codebase/architecture questions; do not rebuild Graphify unless explicitly requested.

Do not clean/reset/stage/commit unrelated work. Run Python tests without bytecode/cache artifacts:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest -p no:cacheprovider ...
```

Before ending a material experiment turn, update the experiment state/checkpoint and validate it.
