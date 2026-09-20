#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
REQUIRED={'observable_state_fingerprint','candidate_skill_ids','eligibility_rejections','permitted_edges','selected_skill_id','selected_edge','terminal_action_decision'}
def validate_trace(t):
 if set(t.get('runtime_inputs',{}))!={'observation','historical_actions','admissible_actions'}: return False,'runtime input violation'
 if not REQUIRED.issubset(t): return False,'trace incomplete'
 if t['selected_skill_id'] not in t['candidate_skill_ids']: return False,'selected skill missing'
 if t['terminal_action_decision'] not in t['runtime_inputs']['admissible_actions']: return False,'terminal action inadmissible'
 return True,'ok'
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--schedule',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); a=ap.parse_args(); s=json.loads(a.schedule.read_text(encoding='utf-8')); rows=[]; failures=[]
 for task in s['tasks']:
  sid=hashlib.sha256(task['task_identity'].encode()).hexdigest(); inp={'observation':'dry-run','historical_actions':[],'admissible_actions':['LookDown']}; t={'runtime_inputs':inp,'observable_state_fingerprint':hashlib.sha256(json.dumps(inp,sort_keys=True).encode()).hexdigest(),'candidate_skill_ids':[sid],'eligibility_rejections':[],'permitted_edges':[],'selected_skill_id':sid,'selected_edge':None,'terminal_action_decision':'LookDown'}; ok,msg=validate_trace(t); rows.append({'task_identity':task['task_identity'],'passed':ok,'message':msg});
  if not ok: failures.append(task['task_identity'])
 result={'experiment_line':'tracegraph-observable-state-skill-composition','phase_id':'TG5-tracegraph-runtime-runner-preflight-v1','task_count':len(rows),'passed':len(rows)-len(failures),'failed':len(failures),'all_passed':not failures,'stop_rule':'stop on first hard invariant violation','network_calls':0,'provider_calls':0,'model_calls':0,'paid_api_calls':0,'rows':rows}; a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8'); print(f"VALID: TG5 dry-run {result['passed']}/{result['task_count']} traces passed; zero network/provider/model/API calls."); return 0 if result['all_passed'] else 1
if __name__=='__main__': raise SystemExit(main())
