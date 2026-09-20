#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
CONFIG=ROOT/'configs/acl2027/tracegraph_tg6_local_execution_preflight_v1.json'
def validate(c):
 e=[]
 for key,sha in [('heldout_schedule','heldout_schedule_sha256'),('runtime_runner_dryrun','runtime_runner_dryrun_sha256')]:
  p=ROOT/c.get(key,'')
  if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=c.get(sha): e.append(f'{key} fingerprint mismatch')
 if c.get('episode_count')!=40 or c.get('max_retries')!=0: e.append('exact local episode scope mismatch')
 if c.get('stop_rule')!='stop on first hard invariant violation': e.append('stop rule mismatch')
 if c.get('runtime_allowed_inputs')!=['observation','historical_actions','admissible_actions']: e.append('runtime inputs must be observable-only')
 if not {'planner_state','pddl_params','expert_future_actions','evaluation_label','phase0_to_phase6_artifact'}.issubset(set(c.get('runtime_forbidden_inputs',[]))): e.append('runtime forbidden inputs incomplete')
 for k in ('network_calls_allowed','provider_calls_allowed','model_calls_allowed','authorization_receipts_allowed','execution_authorized'):
  if c.get(k) is not False: e.append(f'{k} must be false')
 if c.get('webshop_status')!='blocked_pending_preregistered_alfworld_mechanism_gate': e.append('WebShop gate relaxed')
 return e
def main():
 c=json.loads(CONFIG.read_text(encoding='utf-8')); e=validate(c)
 if e:
  for x in e: print('ERROR:',x)
  return 1
 print('VALID: TG6 exact local execution scope is frozen; execution remains unauthorized and zero-network.')
 return 0
if __name__=='__main__': raise SystemExit(main())
