# TraceGraph TG5 Runtime Runner Preflight v1

This zero-network preflight freezes the local runner contract for the 40-task TG4 held-out schedule. It does not launch ALFWorld or call a model.

The runner accepts only observation, historical_actions, and admissible_actions, emits the complete TG3 trace contract, and stops at the first hard invariant violation. A candidate skill is selectable only when its next canonical action is in admissible_actions. Held-out gold and hidden environment state remain outside the runtime payload.
