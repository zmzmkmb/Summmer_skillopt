#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
CONFIG=ROOT/'configs/acl2027/tracegraph_tg5_runtime_runner_preflight_v1.json'
def validate(c):
 e=[]
 for key,path,sha in [('heldout_schedule','heldout_schedule', 'heldout_schedule_sha256'),('skillbank','skillbank','skillbank_sha256')]:
  p=ROOT/c.get(path,'')
  if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=c.get(sha): e.append(f'{key} fingerprint mismatch')
 if c.get('runtime_allowed_inputs')!=['observation','historical_actions','admissible_actions']: e.append('runtime inputs must be observable-only')
 if not {'planner_state','pddl_params','expert_future_actions','evaluation_label','phase0_to_phase6_artifact'}.issubset(set(c.get('runtime_forbidden_inputs',[]))): e.append('runtime forbidden inputs incomplete')
 if c.get('max_trace_rows_per_task')!=1 or c.get('stop_rule')!='stop on first hard invariant violation': e.append('runner stop contract mismatch')
 req={'observable_state_fingerprint','candidate_skill_ids','eligibility_rejections','permitted_edges','selected_skill_id','selected_edge','terminal_action_decision'}
 if not req.issubset(set(c.get('trace_required_fields',[]))): e.append('trace fields incomplete')
 for k in ('network_calls_allowed','provider_calls_allowed','model_calls_allowed','authorization_receipts_allowed','episode_execution_enabled'):
  if c.get(k) is not False: e.append(f'{k} must be false')
 return e
def main():
 c=json.loads(CONFIG.read_text(encoding='utf-8')); e=validate(c)
 if e:
  for x in e: print('ERROR:',x)
  return 1
 print('VALID: TG5 local runtime runner contract is frozen; dry-run only and zero-network.')
 return 0
if __name__=='__main__': raise SystemExit(main())
