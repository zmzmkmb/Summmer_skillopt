# TraceGraph TG4 Held-out Mechanism Preflight v1

This is a zero-network, schedule-only preflight. It freezes held-out ALFWorld task identities for a later mechanism audit without using held-out trajectories as SkillBank data or tuning data.

The schedule uses 20 deterministic tasks from `valid_seen` and 20 from `valid_unseen`. It stores only split, task directory relative path, and a stable task identity hash. No expert trajectory, action, task gold, planner state, or Phase 0-6 artifact enters the schedule. TG1 SkillBank remains train-only.

A future execution must expose observable-state trace fields and compare admissible versus counterfactual skill eligibility. No provider/model/API call or episode execution is authorized by this preflight.
