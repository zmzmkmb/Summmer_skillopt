#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
CONFIG=ROOT/'configs/acl2027/tracegraph_tg2_observable_skillgraph_preflight_v1.json'
def validate(c):
 e=[]
 if c.get('experiment_line')!='tracegraph-observable-state-skill-composition': e.append('wrong TraceGraph research line')
 p=ROOT/c.get('skillbank','')
 if not p.is_file(): e.append('TG1 SkillBank artifact missing')
 elif hashlib.sha256(p.read_bytes()).hexdigest()!=c.get('skillbank_sha256'): e.append('TG1 SkillBank fingerprint mismatch')
 if c.get('runtime_allowed_inputs')!=['observation','historical_actions','admissible_actions']: e.append('runtime inputs must be observable-only')
 if not {'planner_state','pddl_params','expert_future_actions','evaluation_label','phase0_to_phase6_artifact'}.issubset(set(c.get('runtime_forbidden_inputs',[]))): e.append('runtime forbidden inputs incomplete')
 if not {'observable_state_fingerprint','candidate_skill_ids','eligibility_rejections','permitted_edges','selected_skill_id','selected_edge','terminal_action_decision'}.issubset(set(c.get('trace_required_fields',[]))): e.append('trace contract incomplete')
 for k in ('network_calls_allowed','provider_calls_allowed','model_calls_allowed','authorization_receipts_allowed','episode_execution_enabled'):
  if c.get(k) is not False: e.append(f'{k} must be false')
 if c.get('webshop_status')!='blocked_pending_preregistered_alfworld_mechanism_gate': e.append('WebShop gate relaxed')
 return e
def main():
 c=json.loads(CONFIG.read_text(encoding='utf-8')); e=validate(c)
 if e:
  for x in e: print('ERROR:',x)
  return 1
 print('VALID: TG2 observable-state SkillGraph preflight is frozen and zero-network; episode execution remains disabled.')
 return 0
if __name__=='__main__': raise SystemExit(main())
