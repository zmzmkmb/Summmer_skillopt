# Phase 1D: Three-Way Deployment Triage Development Pilot

Date: 2026-08-10

## Protocol

This is a no-paid, no-network development pilot using explicitly fabricated evidence. It is not a real-task accuracy experiment and does not use Phase 1B held-out answers. The grid contains 144 cases: three prior types (`copied-global`, `global-only`, `contextual`), three evidence regimes (`sparse`, `sufficient`, `conflicted`), and 16 deterministic replicates per cell.

The protocol separates deployment from candidate lifecycle. `accept` deploys, `reject` does not deploy but retains the candidate, and `abstain` suspends deployment because evidence is insufficient or conflicting while retaining the candidate. `discard` is not a gate action.

## Development comparison

| Policy | Accept | Reject | Abstain | Helpful deployments | Unsafe deployments | Candidates retained |
|---|---:|---:|---:|---:|---:|---:|
| Binary proxy gate | 48 | 96 | 0 | 16 | 48 | 144 |
| Three-way triage gate | 16 | 32 | 96 | 16 | 0 | 144 |

The fabricated grid intentionally includes proxy-positive but downstream-harmful copied-global cases. The triage protocol blocks those cases and preserves all candidates. It also abstains on sparse or conflicted evidence rather than converting uncertainty into either deployment or destruction.

## Interpretation

This result is a development signal only. It supports freezing the three-way protocol for a real validation pilot, but it does not establish real-task gains, generalization, or a calibrated threshold. The central paper question remains safe use of inherited experience; proxy calibration is a subproblem of deciding when evidence is sufficient for deployment.

## Decision gate

Proceed to a small real cross-task validation only after the three-way action semantics and thresholds are frozen in a new immutable protocol. Keep paid API and formal scaling disabled until that protocol is reviewed. If real validation does not reduce harmful deployment without suppressing nearly all useful updates, retain the prior taxonomy and proxy-to-real mismatch analysis as the primary contribution and demote the triage mechanism to a limitation or safety ablation.

## Provenance

- Config: `configs/acl2027/phase1d_triage_pilot_v1.json`
- Artifact: `artifacts/acl2027_phase1d_triage_pilot_v2`
- Analysis script: `scripts/analyze_acl2027_phase1d_triage_v2.py`
- Network calls: 0
- Paid API calls: 0
- Evidence source: fabricated development grid, not held-out evaluation
