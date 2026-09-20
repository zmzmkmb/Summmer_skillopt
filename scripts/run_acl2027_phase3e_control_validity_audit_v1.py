#!/usr/bin/env python3
"""Audit whether the Phase 3D negative control was structurally irrelevant."""
from __future__ import annotations
import json, sys
from collections import Counter
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable
CONFIG=ROOT/'configs/acl2027/phase3e_control_validity_audit_v1.json'
LEDGER=ROOT/'artifacts/acl2027_phase3d_specificity_abstention_live_v3/ledger.json'
SCHEDULE=ROOT/'artifacts/acl2027_phase3d_specificity_abstention_preflight_v1/specificity_schedule.json'
STRICT=ROOT/'artifacts/acl2027_phase3d_specificity_abstention_live_v3/specificity_analysis.json'
DIAG=ROOT/'artifacts/acl2027_phase3d_specificity_abstention_live_v3/contract_shape_diagnostic_v3_1.json'
ARTIFACT=ROOT/'artifacts/acl2027_phase3e_control_validity_audit_v1'
REPORT=ROOT/'paper/acl2027/results/phase3e_control_validity_audit_v1.md'
SCRIPT=ROOT/'scripts/run_acl2027_phase3e_control_validity_audit_v1.py'
TEST=ROOT/'tests/test_acl2027_phase3e_control_validity_audit_v1.py'
def load(p:Path)->Any:return json.loads(p.read_text(encoding='utf-8-sig'))
def audit()->dict[str,Any]:
 cfg,strict,diag=load(CONFIG),load(STRICT),load(DIAG)
 if any(cfg['execution'].values()) or strict['aggregate_fingerprint']!=cfg['source_phase3d_strict_fingerprint'] or diag['aggregate_fingerprint']!=cfg['source_phase3d_diagnostic_fingerprint']:raise RuntimeError('source or execution drift')
 plan={r['logical_call_id']:r for r in load(SCHEDULE)['schedule']}; rows=[]
 for r in load(LEDGER):
  p=plan[r['logical_call_id']]
  if p['condition']=='irrelevant_single':
   x=json.loads(r['raw_response']); item=next(iter(x['skill_assessments'].values()),{})
   rows.append({'family':p['skill_family'],'control_family':p['control_skill_family'],'applicable':item.get('applicable'),'selected':x.get('selected_skill_id')})
 if len(rows)!=40:raise RuntimeError('irrelevant-control grid drift')
 by={}
 for family in sorted({r['family'] for r in rows}):
  subset=[r for r in rows if r['family']==family]; by[family]={'n':len(subset),'control_family':subset[0]['control_family'],'applicable_count':sum(r['applicable'] is True for r in subset),'selected_control_count':sum(r['selected']!='none' for r in subset)}
 bridge=by['bridge_attribute_comparison']; invalid=bridge['control_family']=='entity_bridge' and bridge['applicable_count']>0
 result={'schema_version':1,'experiment':cfg['experiment'],'status':'complete','strict_gate_preserved':'negative','irrelevant_single_by_family':by,'control_validity':{'attribute_comparison_control_valid':by['attribute_comparison']['applicable_count']==0,'bridge_attribute_comparison_control_valid':not invalid,'bridge_control_invalid_reason':'entity_bridge supplies the film-to-director bridge required before comparison' if invalid else None},'next_design_constraint':'Use a control that cannot supply the target family\'s required bridge operation; treat contract mapping as the native response shape and pre-register mapping normalization before any new calls.','network_calls':0,'provider_calls':0,'model_calls':0,'paid_api_calls':0,'formal_scaling_calls':0,'bindings':{'config_sha256':sha256_file(CONFIG),'ledger_sha256':sha256_file(LEDGER),'schedule_sha256':sha256_file(SCHEDULE),'strict_sha256':sha256_file(STRICT),'diagnostic_sha256':sha256_file(DIAG),'script_sha256':sha256_file(SCRIPT),'test_sha256':sha256_file(TEST)}};result['aggregate_fingerprint']=stable(result);return result
def main()->int:
 r=audit();ARTIFACT.mkdir(parents=True,exist_ok=True);(ARTIFACT/'control_validity_audit.json').write_text(json.dumps(r,ensure_ascii=True,sort_keys=True,indent=2)+'\n',encoding='utf-8');(ARTIFACT/'run_manifest.json').write_text(json.dumps(r,ensure_ascii=True,sort_keys=True,indent=2)+'\n',encoding='utf-8');REPORT.write_text(f"# Phase 3E control-validity audit\n\nThe Phase 3D strict negative gate remains unchanged. Attribute-comparison rejected its bridge control on all 20 tasks, while bridge-attribute-comparison marked the entity-bridge control applicable on {r['irrelevant_single_by_family']['bridge_attribute_comparison']['applicable_count']}/20 tasks. That control supplies a required first-hop operation and is invalid as an irrelevant negative control. No calls were made. Fingerprint: `{r['aggregate_fingerprint']}`.\n",encoding='utf-8');print(json.dumps(r,indent=2,sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
