#!/usr/bin/env python3
"""Frozen Phase 6 response analyzer; all outcome fields are scored independently."""
from __future__ import annotations
import argparse, json, re, sys
from collections import Counter
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable
DESIGN=ROOT/"artifacts/acl2027_phase6_scope_aware_admission_preflight_v1"
REPORT=ROOT/"paper/acl2027/results/phase6_scope_aware_admission_analysis_v1.md"
KEYS={"skill_assessments","admission_decision","selected_skill_id","evidence_sentence_ids","extracted_operands","intermediate_result","final_answer"}
ADMISSIONS={"admit","abstain","fallback"}
CONDITIONS=("cold","always_use_typed","admission_typed","shuffled_typed","incompatible_control","evidence_abstain")

def load(path:Path): return json.loads(path.read_text(encoding="utf-8-sig"))
def norm(value:Any)->str: return " ".join(str(value).strip().casefold().split())
def walk(value:Any):
    if isinstance(value,dict):
        yield value
        for child in value.values(): yield from walk(child)
    elif isinstance(value,list):
        for child in value: yield from walk(child)
def context_map(request:dict[str,Any])->dict[str,str]:
    result={}
    for group in request.get("context",[]):
        for sentence in group.get("sentences",[]) if isinstance(group,dict) else []:
            if not isinstance(sentence,dict): continue
            ident=sentence.get("id")
            if isinstance(ident,str) and ident: result[ident]=str(sentence.get("text",""))
    return result
def candidate_ids(request:dict[str,Any])->list[str]:
    return [str(c["candidate_id"]) for c in request.get("candidates",[]) if isinstance(c,dict) and isinstance(c.get("candidate_id"),str)]
def candidate_scope(row:dict[str,Any], selected:str)->set[str]:
    gold=row.get("private_gold",{})
    target=set(str(x) for x in gold.get("target_evidence_sentence_ids",[]))
    control=set(str(x) for x in gold.get("counterfactual_evidence_sentence_ids",[]))
    request=row.get("canonical_request_body",{})
    candidates=request.get("candidates",[])
    if selected=="none":
        return set().union(*(target,control))
    for c in candidates:
        if str(c.get("candidate_id"))==selected:
            role=str(c.get("role",""))
            return control if "control" in role else target
    return set()
def parse_response(raw:Any)->tuple[dict[str,Any]|None,list[str]]:
    errors=[]
    if isinstance(raw,str):
        if "```" in raw: errors.append("code_fence")
        try: raw=json.loads(raw)
        except json.JSONDecodeError: return None,errors+["invalid_json"]
    if not isinstance(raw,dict): return None,errors+["not_object"]
    return raw,errors
def validate_response(raw:Any,row:dict[str,Any])->dict[str,Any]:
    request=row["canonical_request_body"]
    parsed,parse_errors=parse_response(raw)
    mapping=context_map(request); ids=list(parsed.get("evidence_sentence_ids",[])) if isinstance(parsed,dict) and isinstance(parsed.get("evidence_sentence_ids"),list) else []
    errors=list(parse_errors)
    if parsed is None: return {"contract_valid":False,"evidence_resolving":False,"admission_match":False,"selected_match":False,"answer_correct":False,"counterfactual_answer":False,"errors":errors}
    if set(parsed)!=KEYS: errors.append("top_level_keys")
    ids_candidates=candidate_ids(request)
    assessments=parsed.get("skill_assessments")
    if not isinstance(assessments,dict) or set(assessments)!=set(ids_candidates): errors.append("skill_assessments_keys")
    elif any(not isinstance(value,dict) or set(value)!={"applicable","rationale"} or not isinstance(value.get("applicable"),bool) or not isinstance(value.get("rationale"),str) or not value.get("rationale").strip() for value in assessments.values()): errors.append("skill_assessment_shape")
    decision=parsed.get("admission_decision")
    selected=parsed.get("selected_skill_id")
    if decision not in ADMISSIONS: errors.append("admission_decision")
    if not isinstance(selected,str) or selected not in {"none",*ids_candidates}: errors.append("selected_skill_id")
    if not isinstance(parsed.get("evidence_sentence_ids"),list) or not ids: errors.append("evidence_non_empty")
    if any(not isinstance(e,str) or not e.strip() for e in ids): errors.append("evidence_empty_id")
    if len(ids)!=len(set(ids)): errors.append("evidence_duplicate_id")
    unknown=[e for e in ids if e not in mapping]
    if unknown: errors.append("evidence_unknown_id")
    resolving=not any(error in errors for error in ("evidence_non_empty","evidence_empty_id","evidence_duplicate_id","evidence_unknown_id")) and all(e in mapping for e in ids)
    if resolving and isinstance(selected,str):
        scope=candidate_scope(row,selected)
        if selected!="none" and not set(ids)<=scope: errors.append("evidence_cross_candidate")
    contract_valid=not errors
    expected=set(row.get("expected_admission_decisions",[]))
    admission_match=contract_valid and decision in expected
    selected_match=contract_valid and selected==row.get("expected_selected_skill_id")
    answer=norm(parsed.get("final_answer")); gold=row.get("private_gold",{})
    return {"contract_valid":contract_valid,"evidence_resolving":resolving and "evidence_cross_candidate" not in errors,"admission_match":admission_match,"selected_match":selected_match,"answer_correct":answer==norm(gold.get("target_answer")),"counterfactual_answer":answer==norm(gold.get("counterfactual_answer")),"errors":sorted(set(errors)),"admission_decision":decision,"selected_skill_id":selected,"final_answer":parsed.get("final_answer")}
def analyze_records(records:list[dict[str,Any]],schedule:list[dict[str,Any]])->dict[str,Any]:
    by_id={r["logical_call_id"]:r for r in schedule}; scored=[]
    for record in records:
        logical=str(record["logical_call_id"]); base=logical.removesuffix(":recovery_v1"); row=by_id[base]
        raw=record.get("raw_response",record.get("response")); result=validate_response(raw,row)
        scored.append({"sequence":row["sequence"],"task_id":row["task_id"],"task_family":row["skill_family"],"condition":row["condition"],**result})
    scored.sort(key=lambda x:x["sequence"])
    aggregate={}
    for condition in CONDITIONS:
        subset=[x for x in scored if x["condition"]==condition]
        aggregate[condition]={"rows":len(subset),**{key:sum(bool(x[key]) for x in subset) for key in ("contract_valid","evidence_resolving","admission_match","selected_match","answer_correct","counterfactual_answer")}}
    return {"schema_version":1,"experiment":"acl2027_phase6_scope_aware_admission_analysis_v1","rows":len(scored),"condition_aggregates":aggregate,"scored_rows":scored,"source_design_fingerprint":load(DESIGN/"run_manifest.json")["aggregate_fingerprint"]}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--ledger",type=Path); ap.add_argument("--write-artifact",action="store_true"); args=ap.parse_args()
    schedule=load(DESIGN/"schedule.json")["rows"]
    if args.ledger:
        records=load(args.ledger); result=analyze_records(records,schedule)
        if args.write_artifact:
            out=ROOT/"artifacts/acl2027_phase6_scope_aware_admission_analysis_v1"; out.mkdir(parents=False,exist_ok=False); (out/"analysis_manifest.json").write_text(json.dumps({k:v for k,v in result.items() if k!="scored_rows"},ensure_ascii=True,sort_keys=True,indent=2)+"\n",encoding="utf-8"); (out/"scored_rows.json").write_text(json.dumps(result["scored_rows"],ensure_ascii=True,sort_keys=True,indent=2)+"\n",encoding="utf-8"); REPORT.write_text("# Phase 6 scope-aware admission analysis\n\nFrozen parser output; all outcomes are scored independently.\n",encoding="utf-8")
    else: result={"schema_version":1,"experiment":"acl2027_phase6_scope_aware_admission_analysis_v1","status":"parser_ready_no_live_records","source_design_fingerprint":load(DESIGN/"run_manifest.json")["aggregate_fingerprint"]}
    print(json.dumps(result,ensure_ascii=True,sort_keys=True,indent=2))
if __name__=="__main__": main()


