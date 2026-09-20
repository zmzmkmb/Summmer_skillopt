# TraceGraph TG6 Local Execution Runner v1

This runner is the executable realization of the authorized local TG6 scope.
It binds the immutable TG6 preflight, TG4 held-out schedule, TG6 readiness
audit, and TG1 train-only SkillBank by SHA-256. It makes no provider, model,
API, network, WebShop, Phase 6, or Phase 0-6 calls.

The policy is deterministic: it indexes only canonical action signatures from
the frozen SkillBank, checks eligibility against the current
admissible_actions, and selects the first eligible skill in the frozen
admissible-action order. When no skill is eligible, it records an explicit
abstention and sends the first non-help admissible action. The policy receives
exactly observation, historical_actions, and admissible_actions; environment
done, reward, and success values are used only outside the policy to control
the episode and report outcomes.

The runner executes exactly 40 tasks in frozen TG4 order, permits zero retries,
refuses to overwrite an existing output, and stops on the first hard invariant
violation. Every transition stores the TG3 trace fields
observable_state_fingerprint, candidate_skill_ids, eligibility_rejections,
permitted_edges, selected_skill_id, selected_edge, and
terminal_action_decision.
