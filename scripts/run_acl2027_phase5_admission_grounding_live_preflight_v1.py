#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable
CONFIG=ROOT/"configs/acl2027/phase5_admission_grounding_live_preflight_v1.json"
SOURCE=ROOT/"artifacts/acl2027_phase5_admission_grounding_preflight_v1"
ARTIFACT=ROOT/"artifacts/acl2027_phase5_admission_grounding_live_preflight_v1"
REPORT=ROOT/"paper/acl2027/results/phase5_admission_grounding_live_preflight_v1.md"
DESIGN="c61009e80f5f662c5b62c87239aff4a9fce86c759a98c6250f1a4e941b11a7de"
MODEL="qwen3.7-plus"
def load(p): return json.loads(p.read_text(encoding="utf-8-sig"))
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--write-artifact",action="store_true"); a=ap.parse_args()
    cfg=load(CONFIG); source=load(SOURCE/"run_manifest.json"); sched=load(SOURCE/"schedule.json")["rows"]
    if source["aggregate_fingerprint"] != DESIGN: raise RuntimeError("source design fingerprint drift")
    if any(cfg["authorization"].values()): raise RuntimeError("authorization must remain closed")
    if len(sched)!=240 or [r["sequence"] for r in sched] != list(range(1,241)): raise RuntimeError("schedule coverage drift")
    if len({r["logical_call_id"] for r in sched}) != 240 or len({r["request_hash"] for r in sched}) != 240 or len({r["transport_payload_hash"] for r in sched}) != 240: raise RuntimeError("identity collision")
    counts=Counter(r["condition"] for r in sched)
    if counts != Counter({"cold":40,"always_use_typed":40,"admission_typed":40,"shuffled_typed":40,"incompatible_control":40,"evidence_abstain":40}): raise RuntimeError("condition balance drift")
    for r in sched:
        body=r["canonical_request_body"]
        if body.get("model_id") != MODEL or body.get("temperature") != 0 or body.get("enable_thinking") is not False or body.get("response_format") != {"type":"json_object"}: raise RuntimeError("route drift")
        if "target_answer" in body or "counterfactual_answer" in body: raise RuntimeError("private gold leak")
    result={"schema_version":1,"experiment":"acl2027_phase5_admission_grounding_live_preflight_v1","status":"live-execution-preflight-passed-closed","authorization_status":"fresh-exact-explicit-user-authorization-required","source_design_fingerprint":DESIGN,"schedule_audit":{"rows":240,"task_count":40,"condition_counts":dict(sorted(counts.items())),"unique_transport_payloads":240,"identity_overlap":{"logical_call_ids":0,"request_hashes":0}},"execution_contract":cfg["execution_contract"],"forbidden_scope":cfg["forbidden_scope"],"bindings":{"config_sha256":sha256_file(CONFIG),"source_manifest_sha256":sha256_file(SOURCE/"run_manifest.json"),"source_schedule_sha256":sha256_file(SOURCE/"schedule.json")}, "authorization_receipt_exists":False,"authorization_open_exists":False,"network_calls":0,"provider_calls":0,"model_calls":0,"paid_api_calls":0}
    result["aggregate_fingerprint"]=stable(result)
    statement=("I explicitly authorize Phase 5 admission/grounding execution, binding design fingerprint "+DESIGN+" and live preflight fingerprint "+result["aggregate_fingerprint"]+", using 240 frozen requests to https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1 with qwen3.7-plus, temperature 0, thinking disabled, zero retries, no max_tokens, JSON-object responses, one-second pacing, CNY 3.00 stage and CNY 15.00 cumulative ceilings, first-failure stop, exact-prefix resume, durable hash-chain ledgers, and automatic closure. I authorize no replication, other models, cross-domain scaling, or formal scaling.")
    request={"schema_version":1,"status":"awaiting_exact_explicit_user_authorization","source_design_fingerprint":DESIGN,"preflight_aggregate_fingerprint":result["aggregate_fingerprint"],"authorization_statement_verbatim":statement,"execution_contract":cfg["execution_contract"],"forbidden_scope":cfg["forbidden_scope"],"network_calls":0,"provider_calls":0,"paid_api_calls":0}
    if a.write_artifact:
        if ARTIFACT.exists(): raise RuntimeError("immutable artifact already exists")
        ARTIFACT.mkdir(parents=True)
        for name,obj in [("schedule_binding_audit.json",result["schedule_audit"]),("run_manifest.json",result),("authorization_request.json",request),("completion_manifest.json",{"schema_version":1,"experiment":result["experiment"],"status":"complete","completion_kind":"zero_network_live_execution_preflight","proposed_calls":240,"completed_calls":240,"rows":240,"provider_calls_executed":0,"authorization_status":result["authorization_status"],"aggregate_fingerprint":result["aggregate_fingerprint"]})]:
            (ARTIFACT/name).write_text(json.dumps(obj,ensure_ascii=True,sort_keys=True,indent=2)+"\n",encoding="utf-8")
        REPORT.write_text("# Phase 5 admission/grounding live-execution preflight\n\nZero-network preflight only; no authorization receipt or provider call exists.\n\nFingerprint: "+result["aggregate_fingerprint"]+".\n\nExact authorization required:\n\n"+statement+"\n",encoding="utf-8")
    print(json.dumps({"result":result,"authorization_request":request},ensure_ascii=True,sort_keys=True,indent=2))
if __name__=="__main__": main()
