#!/usr/bin/env python3
"""Bind the closed Phase 3F proposal for a future separately authorized run."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'artifacts/acl2027_phase3f_contract_control_redesign_v1'
OUT=ROOT/'artifacts/acl2027_phase3f_live_preflight_v1'
REPORT=ROOT/'paper/acl2027/results/phase3f_live_preflight_v1.md'
FP='61e474ad6c8fef92a4fe3673ce7a40e8e3d015b6bdb0bb8bb2ae9e391188233e'
def stable(x):return hashlib.sha256((json.dumps(x,sort_keys=True,separators=(',',':'))).encode()).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
 m,s=load(SRC/'run_manifest.json'),load(SRC/'specificity_schedule.json')['schedule']
 if m['aggregate_fingerprint']!=FP or len(s)!=240:raise RuntimeError('Phase 3F source drift')
 if len({r['logical_call_id'] for r in s})!=240 or len({r['request_hash'] for r in s})!=240:raise RuntimeError('identity drift')
 if any(r['canonical_request_body']['response_contract']['skill_assessments']['type']!='object' for r in s):raise RuntimeError('mapping contract drift')
 audit={'schema_version':1,'experiment':'acl2027_phase3f_live_preflight_v1','status':'complete','authorization_status':'not-authorized','source_fingerprint':FP,'schedule_rows':240,'schedule_sha256':hashlib.sha256((SRC/'specificity_schedule.json').read_bytes()).hexdigest(),'request_hash_set_sha256':stable(sorted(r['request_hash'] for r in s)),'execution_contract':{'model_id':'qwen3.7-plus','temperature':0,'enable_thinking':False,'retries':0,'max_tokens_present':False,'response_format':'json_object','minimum_pacing_seconds':1,'terminal_stop':'first_failure','authorization_closure':'automatic'},'network_calls':0,'provider_calls':0,'model_calls':0,'paid_api_calls':0,'formal_scaling_calls':0}
 audit['aggregate_fingerprint']=stable(audit)
 if OUT.exists():raise RuntimeError('immutable artifact exists')
 OUT.mkdir();(OUT/'run_manifest.json').write_text(json.dumps(audit,sort_keys=True,indent=2)+'\n',encoding='utf-8')
 (OUT/'schedule_binding_audit.json').write_text(json.dumps(audit,sort_keys=True,indent=2)+'\n',encoding='utf-8')
 req={'status':'awaiting_exact_explicit_user_authorization','preflight_fingerprint':audit['aggregate_fingerprint'],'attempts':240,'payload_egress_requires_explicit_permission':True,'paid_usage_requires_explicit_permission':True}
 (OUT/'authorization_request.json').write_text(json.dumps(req,sort_keys=True,indent=2)+'\n',encoding='utf-8')
 REPORT.write_text(f"# Phase 3F live preflight\n\nClosed zero-network binding for 240 requests. No authorization or calls. Fingerprint: `{audit['aggregate_fingerprint']}`.\n",encoding='utf-8')
 print(json.dumps(audit,indent=2))
if __name__=='__main__':main()
