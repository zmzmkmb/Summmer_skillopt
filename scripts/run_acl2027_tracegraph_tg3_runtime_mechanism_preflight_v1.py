#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
CONFIG=ROOT/'configs/acl2027/tracegraph_tg3_runtime_mechanism_preflight_v1.json'
def validate(c):
 e=[]; p=ROOT/c.get('skillbank',''); t=ROOT/c.get('tg2_config','')
 if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=c.get('skillbank_sha256'): e.append('TG1 SkillBank fingerprint mismatch')
 if not t.is_file() or hashlib.sha256(t.read_bytes()).hexdigest()!=c.get('tg2_config_sha256'): e.append('TG2 config fingerprint mismatch')
 if c.get('runtime_allowed_inputs')!=['observation','historical_actions','admissible_actions']: e.append('runtime inputs must be observable-only')
 if not {'planner_state','pddl_params','expert_future_actions','evaluation_label','phase0_to_phase6_artifact'}.issubset(set(c.get('runtime_forbidden_inputs',[]))): e.append('runtime forbidden inputs incomplete')
 if not {'eligible_edge','inadmissible_skill_rejection','trace_completeness','hidden_state_rejection'}.issubset(set(c.get('fixture_cases',[]))): e.append('fixture cases incomplete')
 for k in ('network_calls_allowed','provider_calls_allowed','model_calls_allowed','authorization_receipts_allowed','episode_execution_enabled'):
  if c.get(k) is not False: e.append(f'{k} must be false')
 return e
def main():
 c=json.loads(CONFIG.read_text(encoding='utf-8')); e=validate(c)
 if e:
  for x in e: print('ERROR:',x)
  return 1
 print('VALID: TG3 runtime mechanism preflight is frozen, fixture-only, and zero-network.')
 return 0
if __name__=='__main__': raise SystemExit(main())
