#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
CONFIG=ROOT/'configs/acl2027/tracegraph_tg4_heldout_mechanism_preflight_v1.json'
def identity(split,rel): return hashlib.sha256(f'{split}:{rel}'.encode()).hexdigest()
def build(source_root:Path, output:Path):
 rows=[]
 for split in ('valid_seen','valid_unseen'):
  base=source_root/'json_2.1.1'/split
  dirs=sorted({p.parent for p in base.rglob('traj_data.json')})
  for d in dirs[:20]:
   rel=d.relative_to(source_root/'json_2.1.1').as_posix(); rows.append({'task_identity':identity(split,rel),'split':split,'task_relative_path':rel})
 if len(rows)!=40: raise ValueError(f'expected 40 held-out tasks, found {len(rows)}')
 if len({r['task_identity'] for r in rows})!=40: raise ValueError('duplicate held-out identity')
 output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps({'experiment_line':'tracegraph-observable-state-skill-composition','tasks':rows,'runtime_allowed_inputs':['observation','historical_actions','admissible_actions'],'network_calls':0,'provider_calls':0,'model_calls':0,'paid_api_calls':0},indent=2)+'\n',encoding='utf-8'); return rows
def main():
 p=argparse.ArgumentParser(); p.add_argument('--source-root',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a=p.parse_args(); rows=build(a.source_root,a.output); print(f'VALID: froze {len(rows)} held-out task identities; no trajectories or SkillBank records used.')
if __name__=='__main__': main()
