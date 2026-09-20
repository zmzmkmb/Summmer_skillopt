#!/usr/bin/env python3
"""Bind the Phase 6 schedule for a future run without creating a receipt or calling a provider."""
from __future__ import annotations
import argparse, json, sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable
CONFIG=ROOT/"configs/acl2027/phase6_scope_aware_admission_live_preflight_v1.json"
SOURCE=ROOT/"artifacts/acl2027_phase6_scope_aware_admission_preflight_v1"
ARTIFACT=ROOT/"artifacts/acl2027_phase6_scope_aware_admission_live_preflight_v1"
REPORT=ROOT/"paper/acl2027/results/phase6_scope_aware_admission_live_preflight_v1.md"
DESIGN="aecbd3c11dffd1f6860d663d3fe86fa144da4e8be4048aadf323ccd5b8e26ca6"
CONDITIONS=("cold","always_use_typed","admission_typed","shuffled_typed","incompatible_control","evidence_abstain")
def load(path): return json.loads(path.read_text(encoding="utf-8-sig"))
def validate():
    cfg=load(CONFIG); manifest=load(SOURCE/"run_manifest.json"); rows=load(SOURCE/"schedule.json")["rows"]
    if cfg["source_design_fingerprint"]!=DESIGN or manifest["aggregate_fingerprint"]!=DESIGN: raise RuntimeError("source design fingerprint drift")
    if any(cfg["authorization"].values()): raise RuntimeError("authorization must remain closed")
    if len(rows)!=240 or [r["sequence"] for r in rows]!=list(range(1,241)): raise RuntimeError("schedule coverage drift")
    if Counter(r["condition"] for r in rows)!=Counter({c:40 for c in CONDITIONS}): raise RuntimeError("condition balance drift")
    for field in ("logical_call_id","request_hash","transport_payload_hash"):
        if len({r[field] for r in rows})!=240: raise RuntimeError(field+" collision")
    for row in rows:
        body=row["canonical_request_body"]
        if body.get("model_id")!="qwen3.7-plus" or body.get("temperature")!=0 or body.get("enable_thinking") is not False or body.get("response_format")!={"type":"json_object"}: raise RuntimeError("route drift")
        if any(key in body for key in ("target_answer","counterfactual_answer","private_gold","expected_admission_decisions","expected_selected_skill_id")): raise RuntimeError("private gold leak")
    contract=cfg["execution_contract"]
    result={"schema_version":1,"experiment":"acl2027_phase6_scope_aware_admission_live_preflight_v1","status":"live_execution_preflight_passed_closed","authorization_status":"fresh_exact_explicit_user_authorization_required","source_design_fingerprint":DESIGN,"schedule_audit":{"rows":240,"task_count":40,"condition_counts":dict(sorted(Counter(r["condition"] for r in rows).items())),"unique_transport_payloads":240,"identity_overlap":{"task_ids":0,"logical_call_ids":0,"request_hashes":0,"transport_payload_hashes":0,"provider_response_ids":0}},"execution_contract":contract,"forbidden_scope":cfg["forbidden_scope"],"bindings":{"config_sha256":sha256_file(CONFIG),"source_manifest_sha256":sha256_file(SOURCE/"run_manifest.json"),"source_schedule_sha256":sha256_file(SOURCE/"schedule.json")},"authorization_receipt_exists":False,"authorization_open_exists":False,"network_calls":0,"provider_calls":0,"model_calls":0,"paid_api_calls":0,"cross_domain_calls":0,"formal_scaling_calls":0}
    result["aggregate_fingerprint"]=stable(result)
    statement=("I explicitly authorize ACL 2027 Phase 6 execution, binding design fingerprint "+DESIGN+" and live preflight fingerprint "+result["aggregate_fingerprint"]+", using exactly 240 frozen requests on qwen3.7-plus with temperature 0, thinking disabled, zero retries, no max_tokens, JSON-object responses, one-second pacing, CNY 3.00 stage and CNY 15.00 cumulative ceilings, first-failure stop, exact-prefix resume only, durable request-start/response hash-chain ledgers, and automatic closure. I authorize no replication, other models, later phases, cross-domain scaling, or formal scaling.")
    request={"schema_version":1,"status":"awaiting_exact_explicit_user_authorization","source_design_fingerprint":DESIGN,"preflight_aggregate_fingerprint":result["aggregate_fingerprint"],"authorization_statement_verbatim":statement,"execution_contract":contract,"forbidden_scope":cfg["forbidden_scope"],"network_calls":0,"provider_calls":0,"model_calls":0,"paid_api_calls":0,"authorization_receipt_created":False}
    return result,request
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--write-artifact",action="store_true"); args=ap.parse_args(); result,request=validate()
    if args.write_artifact:
        if ARTIFACT.exists(): raise RuntimeError("immutable artifact already exists")
        ARTIFACT.mkdir(parents=True)
        for name,value in (("run_manifest.json",result),("authorization_request.json",request),("completion_manifest.json",{"schema_version":1,"experiment":result["experiment"],"status":"complete","completion_kind":"zero_network_live_execution_preflight","proposed_calls":240,"completed_calls":240,"provider_calls_executed":0,"authorization_status":result["authorization_status"],"aggregate_fingerprint":result["aggregate_fingerprint"]})):
            (ARTIFACT/name).write_text(json.dumps(value,ensure_ascii=True,sort_keys=True,indent=2)+"\n",encoding="utf-8")
        REPORT.parent.mkdir(parents=True,exist_ok=True); REPORT.write_text("# Phase 6 live-execution preflight\n\nZero-network binding only; no authorization receipt or provider call exists.\n\nFingerprint: `"+result["aggregate_fingerprint"]+"`.\n\nExact authorization statement is stored in `authorization_request.json`.\n",encoding="utf-8")
    print(json.dumps({"result":result,"authorization_request":request},ensure_ascii=True,sort_keys=True,indent=2))
if __name__=="__main__": main()






