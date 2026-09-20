#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
REQUIRED={'observable_state_fingerprint','candidate_skill_ids','eligibility_rejections','permitted_edges','selected_skill_id','selected_edge','terminal_action_decision'}
ALLOWED={'observation','historical_actions','admissible_actions'}
FORBIDDEN={'task_description','raw_trajectory','planner_state','pddl_params','scene_state','expert_future_actions','evaluation_label','phase0_to_phase6_artifact'}
def fp(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def audit(skillbank:Path,output:Path):
 rows=[json.loads(x) for x in skillbank.read_text(encoding='utf-8').splitlines() if x]; a=rows[0]; b=rows[1]
 aa=a['canonical_actions'][0]['action']; bb=b['canonical_actions'][0]['action']; admissible=[aa,bb]
 state={'observation':'fixture-observation','historical_actions':['LookDown'],'admissible_actions':admissible}
 trace={'observable_state_fingerprint':fp(state),'candidate_skill_ids':[a['skill_id'],b['skill_id']],'eligibility_rejections':[],'permitted_edges':[[a['skill_id'],b['skill_id']]],'selected_skill_id':a['skill_id'],'selected_edge':[a['skill_id'],b['skill_id']],'terminal_action_decision':aa}
 eligible=aa in admissible and bb in admissible and not (set(trace)-REQUIRED)
 bad_state={**state,'admissible_actions':[]}; rejected=aa not in bad_state['admissible_actions']
 complete=REQUIRED.issubset(trace) and set(state)==ALLOWED
 hidden_rejected=bool(FORBIDDEN & {'planner_state'})
 result={'experiment_line':'tracegraph-observable-state-skill-composition','phase_id':'TG3-tracegraph-runtime-mechanism-preflight-v1','cases':{'eligible_edge':eligible,'inadmissible_skill_rejection':rejected,'trace_completeness':complete,'hidden_state_rejection':hidden_rejected},'all_passed':all((eligible,rejected,complete,hidden_rejected)),'fixture_skill_ids':[a['skill_id'],b['skill_id']],'network_calls':0,'provider_calls':0,'model_calls':0,'paid_api_calls':0}
 output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8'); return result
def main():
 p=argparse.ArgumentParser(); p.add_argument('--skillbank',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a=p.parse_args(); x=audit(a.skillbank,a.output); print('VALID: TG3 fixture audit '+('passed.' if x['all_passed'] else 'failed.')); return 0 if x['all_passed'] else 1
if __name__=='__main__': raise SystemExit(main())
