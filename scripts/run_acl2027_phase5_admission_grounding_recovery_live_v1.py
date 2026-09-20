#!/usr/bin/env python3
"""Execute the explicitly authorized Phase 5 recovery prefix."""
from __future__ import annotations
import argparse, hashlib, json, os, sys, time
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable
from scripts.acl2027_phase2_token_plan_provider_adapter_v8 import QwenTokenPlanProviderAdapter
ART=ROOT/"artifacts/acl2027_phase5_admission_grounding_recovery_live_v1"
PREF=ROOT/"artifacts/acl2027_phase5_admission_grounding_recovery_preflight_v1"
AUTH_REQ=PREF/"authorization_request.json"; RECEIPT=ROOT/"configs/acl2027/phase5_admission_grounding_recovery_user_authorization_receipt_v1.json"
AUTH=ART/"authorization_open.json"; STARTS=ART/"request_start_ledger.json"; LEDGER=ART/"ledger.json"; AUDIT=ART/"run_audit.json"; CLOSURE=ART/"authorization_closure.json"
FP="2cf8ba557fcdb766ca9737ceea3a755f1849237a622260442398af1c0214d45c"; MODEL="qwen3.7-plus"; ENDPOINT="https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"; CALLS=147; INTERVAL=1_000_000_000; PRIOR_RESERVE=0.780116

def load(p): return json.loads(p.read_text(encoding="utf-8-sig"))
def write(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("w",encoding="utf-8",newline="\n") as f:
        json.dump(v,f,ensure_ascii=True,sort_keys=True,indent=2); f.write("\n"); f.flush(); os.fsync(f.fileno())
def contract(): return {"scope":"phase5_admission_grounding_recovery_only","endpoint":ENDPOINT,"authorized_calls":CALLS,"max_provider_attempts":CALLS,"model_id":MODEL,"temperature":0,"enable_thinking":False,"retries":0,"max_tokens_present":False,"response_format":{"type":"json_object"},"request_interval_seconds":1.0,"stage_cost_ceiling_cny":3.0,"cumulative_cost_ceiling_cny":15.0,"terminal_stop_on_first_failed_attempt":True,"authorization_closes_on_completion_or_terminal_stop":True,"usage_accounting_required":True,"request_start_ledger_required":True,"response_ledger_required":True,"hash_chain_required":True,"exact_prefix_resume_only":True}
def schedule():
    req=load(AUTH_REQ); m=load(PREF/"run_manifest.json"); rows=load(PREF/"schedule.json")["rows"]
    if m.get("aggregate_fingerprint")!=FP or req.get("recovery_preflight_aggregate_fingerprint")!=FP: raise RuntimeError("recovery preflight fingerprint drift")
    if req.get("authorization_statement_verbatim") != "I explicitly authorize Phase 5 admission/grounding recovery execution, binding recovery preflight fingerprint "+FP+", preserving 93 completed rows as provenance, excluding all 94 spent source attempts including orphan source sequence 94, and using 147 new frozen requests to "+ENDPOINT+" with qwen3.7-plus, temperature 0, thinking disabled, zero retries, no max_tokens, JSON-object responses, one-second pacing, CNY 3.00 recovery-stage and CNY 15.00 cumulative ceilings including the CNY 0.05 orphan-usage reserve, first-failure stop, exact-prefix resume, durable hash-chain ledgers, and automatic closure. I authorize no replication, other models, cross-domain scaling, or formal scaling.": raise RuntimeError("exact authorization text drift")
    if len(rows)!=CALLS or len({r["logical_call_id"] for r in rows})!=CALLS or len({r["request_hash"] for r in rows})!=CALLS: raise RuntimeError("recovery schedule identity drift")
    return rows
def cost(u): return round((u["input_tokens"]*2+u["output_tokens"]*8)/1_000_000,6)
def total(rs): return round(sum(r.get("local_cost_cny") or 0 for r in rs),6)
def authorize():
    rows=schedule()
    if ART.exists() or RECEIPT.exists(): raise RuntimeError("immutable recovery record already exists")
    key=os.environ.get("DASHSCOPE_API_KEY")
    if not key: raise RuntimeError("DASHSCOPE_API_KEY missing")
    statement=load(AUTH_REQ)["authorization_statement_verbatim"]
    write(RECEIPT,{"schema_version":1,"status":"explicit_user_authorization_received","authorization_statement_verbatim":statement,"authorization_statement_sha256":hashlib.sha256(statement.encode()).hexdigest(),"recovery_preflight_aggregate_fingerprint":FP,**contract(),"data_egress_authorized":True,"paid_usage_authorized":True,"orphan_usage_reserve_cny":0.05})
    ART.mkdir(parents=False,exist_ok=False)
    opened={"schema_version":1,"authorization_id":"phase5-admission-grounding-recovery-live-v1","status":"open","credential_sha256":hashlib.sha256(key.encode()).hexdigest(),"receipt_sha256":sha256_file(RECEIPT),"recovery_preflight_aggregate_fingerprint":FP,"prior_known_plus_reserve_cny":PRIOR_RESERVE,**contract(),"paid_api_allowed":True,"provider_calls_allowed":True,"qwen_authorization_open":True,"formal_scaling_allowed":False,"rows":len(rows)}
    write(AUTH,opened); return opened
def execute():
    rows=schedule(); auth=load(AUTH); authsha=sha256_file(AUTH)
    if auth.get("status")!="open" or not all(auth.get(k) is True for k in ("paid_api_allowed","provider_calls_allowed","qwen_authorization_open")): raise RuntimeError("recovery authorization not open")
    starts=load(STARTS) if STARTS.exists() else []; records=load(LEDGER) if LEDGER.exists() else []
    if len(starts)!=len(records) or len(records)>CALLS: raise RuntimeError("invalid recovery prefix")
    prevs=prevr=None
    for row,st,rec in zip(rows,starts,records):
        if st.get("logical_call_id")!=row["logical_call_id"] or st.get("request_hash")!=row["request_hash"] or st.get("authorization_sha256")!=authsha or st.get("previous_start_entry_sha256")!=prevs or st.get("start_entry_sha256")!=stable({k:v for k,v in st.items() if k!="start_entry_sha256"}): raise RuntimeError("start chain drift")
        if rec.get("logical_call_id")!=row["logical_call_id"] or rec.get("request_hash")!=row["request_hash"] or rec.get("authorization_sha256")!=authsha or rec.get("previous_ledger_entry_sha256")!=prevr or rec.get("ledger_entry_sha256")!=stable({k:v for k,v in rec.items() if k!="ledger_entry_sha256"}): raise RuntimeError("ledger chain drift")
        prevs,prevr=st["start_entry_sha256"],rec["ledger_entry_sha256"]
    provider=QwenTokenPlanProviderAdapter(auth)
    while len(records)<CALLS:
        if PRIOR_RESERVE+total(records)>=15 or total(records)>=3: raise RuntimeError("cost ceiling reached")
        row=rows[len(records)]
        if starts:
            rem=INTERVAL-(time.time_ns()-starts[-1]["request_started_at_unix_ns"])
            if rem>0: time.sleep(rem/1_000_000_000)
        st={"sequence":len(starts)+1,"logical_call_id":row["logical_call_id"],"request_hash":row["request_hash"],"request_body_sha256":row["request_hash"],"authorization_sha256":authsha,"request_started_at_unix_ns":time.time_ns(),"previous_start_entry_sha256":starts[-1]["start_entry_sha256"] if starts else None}; st["start_entry_sha256"]=stable(st); starts.append(st); write(STARTS,starts)
        base={k:row.get(k) for k in ("logical_call_id","request_hash","task_id","task_family","skill_family","condition")}; base.update({"provider_attempt_index":len(records)+1,"authorization_id":"phase5-admission-grounding-recovery-live-v1","authorization_sha256":authsha,"model_id":MODEL,"temperature":0,"retries":0,"max_tokens_present":False,"previous_ledger_entry_sha256":records[-1]["ledger_entry_sha256"] if records else None})
        try:
            resp=provider(deepcopy(row["canonical_request_body"])); u=resp["usage"]; rid=resp.get("request_id"); local=cost(u)
            if not rid or rid in {r.get("request_id") for r in records}: raise RuntimeError("missing or duplicate provider request id")
            if PRIOR_RESERVE+total(records)+local>15 or total(records)+local>3: raise RuntimeError("response would exceed cost ceiling")
            rec={**base,"request_id":rid,"raw_response":resp["content"],"raw_response_sha256":stable(resp["content"]),"raw_provider_response":resp.get("raw_provider_response",resp),"usage":u,"local_cost_cny":local,"cumulative_local_cost_cny":round(PRIOR_RESERVE+total(records)+local,6),"terminal":False,"status":"completed","error":None}
        except Exception as exc: rec={**base,"request_id":None,"raw_response":None,"raw_response_sha256":stable(None),"raw_provider_response":None,"usage":None,"local_cost_cny":None,"cumulative_local_cost_cny":None,"terminal":True,"status":"hard_stop","error":f"{type(exc).__name__}: {exc}"}
        rec["ledger_entry_sha256"]=stable(rec); records.append(rec); write(LEDGER,records)
        if rec["terminal"]: raise RuntimeError(rec["error"])
    return audit()
def audit():
    rs=load(LEDGER) if LEDGER.exists() else []; ss=load(STARTS) if STARTS.exists() else []; known=[r for r in rs if isinstance(r.get("usage"),dict)]; out={"schema_version":1,"experiment":"acl2027_phase5_admission_grounding_recovery_live_v1","status":"completed" if len(rs)==CALLS and all(not r.get("terminal") for r in rs) else "terminal_hard_stop" if rs and rs[-1].get("terminal") else "incomplete","planned_calls":CALLS,"provider_attempts":len(ss),"completed_calls":len(known),"terminal_rows":sum(bool(r.get("terminal")) for r in rs),"input_tokens":sum(r["usage"]["input_tokens"] for r in known),"output_tokens":sum(r["usage"]["output_tokens"] for r in known),"total_tokens":sum(r["usage"]["total_tokens"] for r in known),"recovery_stage_cost_cny":total(rs),"known_cumulative_cost_lower_bound_cny":round(PRIOR_RESERVE+total(rs),6),"request_start_pacing_valid":all(b["request_started_at_unix_ns"]-a["request_started_at_unix_ns"]>=INTERVAL for a,b in zip(ss,ss[1:])),"network_calls":len(ss),"provider_calls":len(ss),"model_calls":len(ss),"paid_api_calls":len(ss),"authorization_closed":CLOSURE.exists()}; write(AUDIT,out); return out
def close(reason):
    out=audit(); c={"schema_version":1,"authorization_id":"phase5-admission-grounding-recovery-live-v1","status":"closed","reason":reason,"provider_attempts":out["provider_attempts"],"completed_calls":out["completed_calls"],"recovery_stage_cost_cny":out["recovery_stage_cost_cny"],"known_cumulative_cost_lower_bound_cny":out["known_cumulative_cost_lower_bound_cny"],"paid_api_allowed":False,"provider_calls_allowed":False,"qwen_authorization_open":False,"formal_scaling_allowed":False}; write(CLOSURE,c); out["authorization_closed"]=True; write(AUDIT,out); return c
def main():
    c=argparse.ArgumentParser(); c.add_argument("command",choices=("preflight","authorize","execute","audit","close")); cmd=c.parse_args().command
    if cmd=="preflight": out={"rows":len(schedule()),"network_calls":0,"aggregate_fingerprint":FP}
    elif cmd=="authorize": out=authorize()
    elif cmd=="audit": out=audit()
    elif cmd=="close": out=close("operator_close")
    else:
        try: out=execute(); close("completed_exact_147")
        except Exception as exc:
            if AUTH.exists() and not CLOSURE.exists(): close(f"terminal_hard_stop:{type(exc).__name__}:{exc}")
            raise
    print(json.dumps(out,ensure_ascii=True,sort_keys=True,indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
