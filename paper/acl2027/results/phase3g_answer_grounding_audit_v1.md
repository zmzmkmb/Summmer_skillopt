# ACL 2027 Phase 3G answer-grounding audit v1

This zero-network audit reuses only the immutable Phase 3F boolean-mapping
diagnostic. It does not re-gate Phase 3F or make any provider, model, paid, or
network call.

Across attribute comparison tasks, contextual versus operation-incompatible
irrelevant context changed the declared operation on 19/20 tasks but changed
the normalized final answer on 1/20. Both contexts were alias-correct on 18/20
tasks; contextual had one net correctness win. For bridge attribute comparison,
the corresponding values were 10/20 operation changes, 1/20 answer changes,
14/20 both-correct, and one contextual net win.

The main failure is therefore answer grounding rather than selector
specificity: a correct historical-skill selection can alter a declared
procedure while leaving the generated answer unchanged. This audit cannot
establish whether the unchanged answer reflects an answer-insensitive task,
independent latent solving, or a procedure-to-answer disconnect. Cross-domain
and formal scaling remain closed. Any future live test must use new tasks whose
counterfactual skill choice changes a required, observable intermediate value
and must pre-register answer grounding as the primary outcome.
