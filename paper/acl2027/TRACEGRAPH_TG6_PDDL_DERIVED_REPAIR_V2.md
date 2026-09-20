# TraceGraph TG6 Derived PDDL Repair v2

Repair v2 extends the frozen v1 adapter to every goal-required pickupable or
toggleable object that has an `objectAtLocation` fact but no `inReceptacle`
fact. Each repaired object receives a deterministic, non-openable synthetic
floor receptacle at its existing location. Official ALFWorld files, the TG4
schedule, the terminal TG6 artifacts, and the TG1 SkillBank remain unchanged.

The formal derived tree covers the same 40 held-out task identities and
repairs 10 interactive objects. Existing zero-step TextWorld reset evidence
for the repair-v2 payload passed 40/40 tasks with zero actions, episodes,
network calls, provider calls, model calls, and API calls. The evidence was
promoted by exact source hash into the formal preflight; no reset was rerun in
this formalization step.

This is environment-compatibility evidence, not TraceGraph capability
evidence. Episode execution remains closed. A later run requires a separately
versioned execution runner configuration bound to this repair-v2 manifest and
preflight, plus fresh exact user authorization.
