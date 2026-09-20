#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path

def audit(schedule:Path, source_root:Path, output:Path):
 s=json.loads(schedule.read_text(encoding='utf-8')); base=source_root/'json_2.1.1'; rows=[]
 for t in s['tasks']:
  d=base/t['task_relative_path']; rows.append({'task_identity':t['task_identity'],'split':t['split'],'task_relative_path':t['task_relative_path'],'trajectory_present':(d/'traj_data.json').is_file(),'game_present':(d/'game.tw-pddl').is_file()})
 result={'experiment_line':'tracegraph-observable-state-skill-composition','phase_id':'TG6-tracegraph-local-readiness-audit-v1','task_count':len(rows),'executable_tasks':sum(r['trajectory_present'] and r['game_present'] for r in rows),'missing_game_tasks':[r['task_relative_path'] for r in rows if not r['game_present']],'missing_trajectory_tasks':[r['task_relative_path'] for r in rows if not r['trajectory_present']],'execution_authorized':False,'network_calls':0,'provider_calls':0,'model_calls':0,'paid_api_calls':0,'rows':rows}
 result['ready_for_frozen_40_task_execution']=result['executable_tasks']==40 and not result['missing_trajectory_tasks']
 output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8'); return result

def main():
 p=argparse.ArgumentParser(); p.add_argument('--schedule',type=Path,required=True); p.add_argument('--source-root',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a=p.parse_args(); r=audit(a.schedule,a.source_root,a.output); print(f"AUDIT: {r['executable_tasks']}/{r['task_count']} frozen tasks executable; ready={r['ready_for_frozen_40_task_execution']}; no episode or model call."); return 0
if __name__=='__main__': raise SystemExit(main())