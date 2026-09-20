# TraceGraph TG6 Derived PDDL Repair v1

This is a separately versioned, zero-network adapter for the frozen TG6
held-out ALFWorld schedule. It never edits the official `game.tw-pddl` files,
the TG4 schedule, or the terminal TG6 artifact.

## Repair rule

The read-only integrity audit found eight tasks whose pickupable target has an
`objectAtLocation` fact but no `inReceptacle` fact. The vendored ALFRED
`PickupObject` operator requires `inReceptacle(target, receptacle)`. For those
tasks only, the adapter adds a new `TraceGraphFloorReceptacle - receptacle`, a
`TraceGraphFloorType - rtype`, a matching `receptacleType` fact, a
`receptacleAtLocation` fact at the target's existing location, and the missing
`inReceptacle` fact. It does not add `canContain`, `openable`, or any hidden
state, so the synthetic receptacle is floor-only and non-openable.

Tasks that already satisfy the source contract are copied byte-for-byte into
the derived tree. Every row records source and derived SHA-256 values.

## Preflight boundary

The repair preflight checks all 40 frozen task identities, preserves the source
domain and grammar, rejects `dummy(val1)`, and attempts a local Fast Downward
`pddl2sas` parse for every derived problem when the module is available. This
stage runs zero episodes and makes zero provider/model/API calls. If Fast
Downward is unavailable, the result is explicitly blocked rather than treated
as a pass.

The derived tree is not an authorization receipt and cannot authorize episode
execution. Any execution must use a new runner configuration that binds the
derived manifest and preflight fingerprints, with fresh exact user
authorization. The old TG6 authorization cannot be resumed or retried.
