# TraceGraph TG2 Observable-State SkillGraph Preflight v1

Status: zero-network design preflight. TG2 consumes the immutable TG1 SkillBank artifact but does not launch ALFWorld or invoke a model.

## Observable State

Every runtime decision is represented only by observation, historical_actions, and admissible_actions. The representation stores normalized fingerprints and the canonical admissible action set. It must never include task descriptions, raw trajectory text, planner/PDDL state, scene state, expert future actions, evaluation labels, or Phase 0-6 data.

## Constrained SkillGraph

A node is a frozen TG1 skill_id. An edge from skill A to B is eligible only if A's terminal canonical action and B's first canonical action are both supported by the current admissible-action set and the successor does not require a hidden state predicate. TG2 freezes this structural contract and does not optimize edges from evaluation outcomes.

## Trace Contract

Each later runtime decision must expose observable_state_fingerprint, candidate skill IDs, eligibility rejections, permitted edges, selected skill ID, selected edge, and terminal action decision. Missing trace fields or any ineligible edge is a hard failure. This is a mechanism-audit foundation, not an accuracy claim.
