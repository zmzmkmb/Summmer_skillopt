#!/usr/bin/env python3
from __future__ import annotations
import json
from collections import Counter, defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DESIGN=ROOT/"artifacts/acl2027_phase5_admission_grounding_preflight_v1"
ORIG=ROOT/"artifacts/acl2027_phase5_admission_grounding_live_v1"
REC=ROOT/"artifacts/acl2027_phase5_admission_grounding_recovery_live_v1"
OUT=ROOT/"artifacts/acl2027_phase5_admission_grounding_analysis_v1"
REPORT=ROOT/"paper/acl2027/results/phase5_admission_grounding_analysis_v1.md"
KEYS={"skill_assessments","admission_decision","selected_skill_id","evidence_sentence_ids","extracted_operands","intermediate_result","final_answer"}
def load(p): return json.loads(p.read_text(encoding="utf-8-sig"))
def norm(x): return " ".join(str(x).strip().lower().split())
def main():
    sched=load(DESIGN/"schedule.json")["rows"]; by_log={r["logical_call_id"]:r for r in sched}
    ledgers=load(ORIG/"ledger.json")+load(REC/"ledger.json")
    if len(ledgers)!=240: raise RuntimeError("combined coverage incomplete")
    rows=[]; prev=None
    for rec in ledgers:
        base=rec["logical_call_id"].removesuffix(":recovery_v1"); src=by_log[base]
        raw=json.loads(rec["raw_response"]); body=src["canonical_request_body"]; text=" ".join(m["content"] for m in body["messages"]); ids={p.split('"id": "',1)[1].split('"',1)[0] for p in []}
        valid=set(raw)==KEYS and isinstance(raw.get("skill_assessments"),dict) and raw.get("admission_decision") in {"admit","abstain","fallback"} and isinstance(raw.get("selected_skill_id"),str) and isinstance(raw.get("evidence_sentence_ids"),list) and bool(raw["evidence_sentence_ids"]) and all(isinstance(x,str) for x in raw["evidence_sentence_ids"])
        evidence_resolving=valid and all(e in text for e in raw["evidence_sentence_ids"])
        expected=body["expected_admission_decision"]; admission_match=raw.get("admission_decision") in ({expected} if expected in {"admit","abstain","fallback"} else {"admit","abstain"})
        selected_match=raw.get("selected_skill_id")==body["expected_selected_skill_id"]
        answer=norm(raw.get("final_answer")); target=norm(src["private_gold"]["target_answer"]); counter=norm(src["private_gold"]["counterfactual_answer"])
        rows.append({"sequence":src["sequence"],"task_id":src["task_id"],"condition":src["condition"],"skill_family":src["skill_family"],"contract_valid":valid,"evidence_resolving":evidence_resolving,"admission_match":admission_match,"selected_match":selected_match,"answer_correct":answer==target,"counterfactual_answer":answer==counter,"final_answer":raw.get("final_answer"),"admission_decision":raw.get("admission_decision")})
    rows.sort(key=lambda r:r["sequence"])
    agg={}
    for condition in sorted({r["condition"] for r in rows}):
        rs=[r for r in rows if r["condition"]==condition]; agg[condition]={"rows":len(rs),"contract_valid":sum(r["contract_valid"] for r in rs),"evidence_resolving":sum(r["evidence_resolving"] for r in rs),"admission_match":sum(r["admission_match"] for r in rs),"selected_match":sum(r["selected_match"] for r in rs),"answer_correct":sum(r["answer_correct"] for r in rs),"counterfactual_answer":sum(r["counterfactual_answer"] for r in rs)}
    result={"schema_version":1,"experiment":"acl2027_phase5_admission_grounding_analysis_v1","status":"completed","rows":len(rows),"condition_aggregates":agg,"overall":{"contract_valid":sum(r["contract_valid"] for r in rows),"evidence_resolving":sum(r["evidence_resolving"] for r in rows),"admission_match":sum(r["admission_match"] for r in rows),"selected_match":sum(r["selected_match"] for r in rows),"answer_correct":sum(r["answer_correct"] for r in rows)},"source_artifacts":{"original_ledger":str(ORIG/"ledger.json"),"recovery_ledger":str(REC/"ledger.json")}}
    OUT.mkdir(parents=True,exist_ok=True); (OUT/"scored_rows.json").write_text(json.dumps(rows,ensure_ascii=True,sort_keys=True,indent=2)+"\n",encoding="utf-8"); (OUT/"analysis_manifest.json").write_text(json.dumps(result,ensure_ascii=True,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    REPORT.parent.mkdir(parents=True,exist_ok=True); REPORT.write_text("# Phase 5 admission/grounding analysis\n\nCombined 240/240 rows from the original 93 complete responses and 147-row recovery.\n\n```json\n"+json.dumps(result["condition_aggregates"],ensure_ascii=True,sort_keys=True,indent=2)+"\n```\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=True,sort_keys=True,indent=2))
if __name__=="__main__": main()
