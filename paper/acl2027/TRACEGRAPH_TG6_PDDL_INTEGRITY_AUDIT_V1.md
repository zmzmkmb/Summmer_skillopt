# TraceGraph TG6 PDDL Integrity Audit v1

This is a read-only, zero-network audit of the frozen TG4 held-out ALFWorld
schedule. It checks the PDDL facts required by the vendored ALFRED domain for
the task's target object and light. It does not initialize an environment,
execute an episode, call a provider/model/API, or modify any dataset file.

The ALFRED `PickupObject` operator requires the target object to appear in an
`inReceptacle` fact. A task with a pickupable target that has only
`objectAtLocation` is therefore not executable under this domain contract and
must be treated as a local environment-integrity blocker.

The audit output is stored in
`artifacts/acl2027_tracegraph_tg6_pddl_integrity_audit_v1/audit.json`. Any
repair or subsequent execution requires a separately versioned preflight and
fresh exact authorization; the terminal TG6 runner artifact is immutable.
