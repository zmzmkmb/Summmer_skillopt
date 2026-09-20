#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
CONFIG=ROOT/'configs/acl2027/tracegraph_tg4_heldout_mechanism_preflight_v1.json'
SCHEDULE=ROOT/'artifacts/acl2027_tracegraph_tg4_heldout_mechanism_preflight_v1/heldout_schedule.json'
def validate(c,s):
 e=[]
 p=ROOT/c['skillbank'];
 if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=c['skillbank_sha256']: e.append('TG1 SkillBank fingerprint mismatch')
 if len(s.get('tasks',[]))!=40 or {x.get('split') for x in s['tasks']}!={'valid_seen','valid_unseen'}: e.append('held-out schedule must contain both splits and 40 tasks')
 if len({x.get('task_identity') for x in s.get('tasks',[])})!=40: e.append('held-out identities must be unique')
 if s.get('runtime_allowed_inputs')!=['observation','historical_actions','admissible_actions']: e.append('runtime inputs must be observable-only')
 if any(k not in s for k in ('network_calls','provider_calls','model_calls','paid_api_calls')) or any(s[k]!=0 for k in ('network_calls','provider_calls','model_calls','paid_api_calls')): e.append('schedule call counters must be zero')
 for k in ('network_calls_allowed','provider_calls_allowed','model_calls_allowed','authorization_receipts_allowed','episode_execution_enabled'):
  if c.get(k) is not False: e.append(f'{k} must be false')
 return e
def main():
 c=json.loads(CONFIG.read_text(encoding='utf-8')); s=json.loads(SCHEDULE.read_text(encoding='utf-8')); e=validate(c,s)
 if e:
  for x in e: print('ERROR:',x)
  return 1
 print('VALID: TG4 held-out mechanism schedule is frozen and zero-network.')
 return 0
if __name__=='__main__': raise SystemExit(main())
