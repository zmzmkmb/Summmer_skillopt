#!/usr/bin/env python3
"""Zero-network binding preflight for the repaired Phase 4C held-out schedule."""
from __future__ import annotations
import argparse, json, os, sys
from collections import Counter
from pathlib import Path
from typing import Any
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable
VERSION = 1
EXPERIMENT = "acl2027_phase4c_repaired_heldout_live_preflight_v1"
DESIGN_FINGERPRINT = "5c776023249499a5022fe901cae9f0684c22e30991fa9349a71e9af92b14bda3"
ENDPOINT = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
MODEL = "qwen3.7-plus"
CONDITIONS = ("cold", "global_only", "contextual_typed", "shuffled_typed", "incompatible_control")
EXACT_KEYS = ("skill_assessments", "selected_skill_id", "evidence_sentence_ids", "extracted_operands", "intermediate_result", "final_answer")
CONFIG = ROOT / "configs/acl2027/phase4c_repaired_heldout_live_preflight_v1.json"
SCRIPT = Path(__file__).resolve()
TEST = ROOT / "tests/test_acl2027_phase4c_repaired_heldout_live_preflight_v1.py"
SOURCE = ROOT / "artifacts/acl2027_phase4c_repaired_zero_network_design_preflight_v1"
SCHEDULE = SOURCE / "repaired_heldout_schedule.json"
SOURCE_MANIFEST = SOURCE / "run_manifest.json"
ARTIFACT = ROOT / "artifacts/acl2027_phase4c_repaired_heldout_live_preflight_v1"
REPORT = ROOT / "paper/acl2027/results/phase4c_repaired_heldout_live_preflight_v1.md"
def load(p: Path) -> Any: return json.loads(p.read_text(encoding="utf-8-sig"))
def render(v: Any) -> str: return json.dumps(v, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
def write(p: Path, v: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True); t=p.with_name(p.name+".tmp")
    try:
        with t.open("w", encoding="utf-8", newline="\n") as f: f.write(render(v)); f.flush(); os.fsync(f.fileno())
        os.replace(t,p)
    finally:
        if t.exists(): t.unlink()
def validate_schedule(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if len(rows)!=400 or [r.get("sequence") for r in rows]!=list(range(1,401)): raise RuntimeError("schedule row/sequence drift")
    logical=[str(r["logical_call_id"]) for r in rows]; req=[str(r["request_hash"]) for r in rows]; tr=[str(r["transport_payload_hash"]) for r in rows]
    if len(set(logical))!=400 or len(set(req))!=400 or len(set(tr))!=400: raise RuntimeError("identity/payload uniqueness drift")
    counts=Counter(str(r["condition"]) for r in rows)
    if counts != Counter({c:80 for c in CONDITIONS}) or len({str(r["task_id"]) for r in rows})!=80: raise RuntimeError("balance drift")
    for r in rows:
        body=r.get("canonical_request_body"); proj=r.get("transport_projection")
        if not isinstance(body,dict) or not isinstance(proj,dict) or stable(body)!=r["request_hash"] or stable(proj)!=r["transport_payload_hash"]: raise RuntimeError(f"hash drift {r.get('sequence')}")
        if proj.get("model")!=MODEL or proj.get("temperature")!=0 or proj.get("enable_thinking") is not False or proj.get("response_format")!={"type":"json_object"} or "max_tokens" in proj: raise RuntimeError(f"route drift {r.get('sequence')}")
        msgs=proj.get("messages",[]); system=str(msgs[0].get("content","")) if len(msgs)>0 else ""
        if len(msgs)<2 or not all(k in system for k in EXACT_KEYS): raise RuntimeError(f"contract visibility drift {r.get('sequence')}")
        user=json.loads(msgs[1]["content"])
        if user.get("response_contract",{}).get("exact_keys")!=list(EXACT_KEYS): raise RuntimeError(f"user contract drift {r.get('sequence')}")
        ids=[s.get("id") for b in user.get("context",[]) for s in b.get("sentences",[])]
        if not ids or any(not x for x in ids): raise RuntimeError(f"evidence ID drift {r.get('sequence')}")
    return {"rows":400,"heldout_tasks":80,"condition_counts":dict(sorted(counts.items())),"unique_transport_payloads":400,"identity_overlap":{"logical_call_ids":0,"request_hashes":0}}
def validate() -> tuple[dict[str,Any],dict[str,Any]]:
    cfg=load(CONFIG); source=load(SOURCE_MANIFEST)
    if any(v is not False for v in cfg["authorization"].values()): raise RuntimeError("authorization must remain closed")
    if source.get("aggregate_fingerprint")!=DESIGN_FINGERPRINT: raise RuntimeError("design fingerprint drift")
    audit=validate_schedule(load(SCHEDULE)["rows"]); contract=cfg["execution_contract"]
    result={"schema_version":VERSION,"experiment":EXPERIMENT,"status":"live-execution-preflight-passed-closed","authorization_status":"fresh-exact-explicit-user-authorization-required","source_design_fingerprint":DESIGN_FINGERPRINT,"schedule_audit":audit,"execution_contract":contract,"forbidden_scope":cfg["forbidden_scope"],"bindings":{"config_sha256":sha256_file(CONFIG),"script_sha256":sha256_file(SCRIPT),"test_sha256":sha256_file(TEST),"source_manifest_sha256":sha256_file(SOURCE_MANIFEST),"source_schedule_sha256":sha256_file(SCHEDULE)},"authorization_receipt_exists":False,"authorization_open_exists":False,"network_calls":0,"provider_calls":0,"model_calls":0,"paid_api_calls":0,"phase4c_calls":0,"replication_calls":0,"cross_domain_scaling_calls":0,"formal_scaling_calls":0}
    result["aggregate_fingerprint"]=stable(result)
    statement=("I explicitly authorize Phase 4C repaired held-out execution, binding design fingerprint "+DESIGN_FINGERPRINT+" and live preflight fingerprint "+result["aggregate_fingerprint"]+", using 400 frozen requests to "+ENDPOINT+" with qwen3.7-plus, temperature 0, thinking disabled, zero retries, no max_tokens, JSON-object responses, one-second pacing, CNY 3.00 stage and CNY 15.00 cumulative ceilings, first-failure stop, exact-prefix resume, durable hash-chain ledgers, and automatic closure. I authorize no replication, other models, cross-domain scaling, or formal scaling.")
    return result,{"schema_version":VERSION,"status":"awaiting_exact_explicit_user_authorization","source_design_fingerprint":DESIGN_FINGERPRINT,"preflight_aggregate_fingerprint":result["aggregate_fingerprint"],"authorization_statement_verbatim":statement,"execution_contract":contract,"forbidden_scope":cfg["forbidden_scope"],"network_calls":0,"provider_calls":0,"paid_api_calls":0}
def write_artifact(result: dict[str,Any], request: dict[str,Any]) -> None:
    if ARTIFACT.exists(): raise RuntimeError(f"immutable artifact already exists: {ARTIFACT}")
    ARTIFACT.mkdir(parents=True)
    write(ARTIFACT/"schedule_binding_audit.json",result["schedule_audit"]); write(ARTIFACT/"run_manifest.json",result); write(ARTIFACT/"authorization_request.json",request)
    write(ARTIFACT/"completion_manifest.json",{"schema_version":VERSION,"experiment":EXPERIMENT,"status":"complete","completion_kind":"zero_network_live_execution_preflight","proposed_calls":400,"completed_calls":400,"rows":400,"provider_calls_executed":0,"authorization_status":result["authorization_status"],"aggregate_fingerprint":result["aggregate_fingerprint"]})
    REPORT.parent.mkdir(parents=True,exist_ok=True); REPORT.write_text("# Phase 4C repaired held-out live-execution preflight\n\nZero-network preflight only; no authorization receipt or provider call exists.\n\nFingerprint: `"+result["aggregate_fingerprint"]+"`.\n\nExact authorization required:\n\n"+request["authorization_statement_verbatim"]+"\n",encoding="utf-8",newline="\n")
def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--write-artifact",action="store_true"); a=p.parse_args(); result,request=validate()
    if a.write_artifact: write_artifact(result,request)
    print(render(result),end=""); return 0
if __name__=="__main__": raise SystemExit(main())
