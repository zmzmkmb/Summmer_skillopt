#!/usr/bin/env python3
"""Freeze a zero-network admission/grounding design; never call a provider."""
from __future__ import annotations

import copy, json, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import run_acl2027_phase3h_counterfactual_answer_sensitivity_preflight_v1 as base
from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable

EXPERIMENT = "acl2027_phase5_admission_grounding_preflight_v1"
VERSION = 1
CONDITIONS = ("cold", "always_use_typed", "admission_typed", "shuffled_typed", "incompatible_control", "evidence_abstain")
CONFIG = ROOT / "configs/acl2027/phase5_admission_grounding_preflight_v1.json"
SCRIPT = Path(__file__).resolve()
ARTIFACT = ROOT / "artifacts/acl2027_phase5_admission_grounding_preflight_v1"
REPORT = ROOT / "paper/acl2027/results/phase5_admission_grounding_preflight_v1.md"

def load(p: Path): return json.loads(p.read_text(encoding="utf-8-sig"))

def contract():
    return {"exact_keys": ["skill_assessments", "admission_decision", "selected_skill_id", "evidence_sentence_ids", "extracted_operands", "intermediate_result", "final_answer"], "admission_decision": "admit|abstain|fallback", "skill_assessments": "candidate-ID-keyed object with applicable:boolean and rationale:string", "selected_skill_id": "presented candidate ID or none", "evidence_sentence_ids": "non-empty IDs copied verbatim from context", "forbidden": ["markdown", "code_fence", "additional_top_level_keys"]}

def annotated(context):
    return [{"title": title, "sentences": [{"id": f"{title}#{i}", "text": s} for i, s in enumerate(sentences)]} for title, sentences in context]

def candidate(c, scope, role):
    x = copy.deepcopy(c); x["prior_scope"] = scope; x["role"] = role; x["procedure_contract"] = "Apply the comparison direction in the question and return the supported entity."; return x

def build():
    # Exclude this immutable artifact from the historical identity scan on
    # revalidation; otherwise its own task IDs would make the schedule drift.
    base.ARTIFACT = ARTIFACT
    tasks, selection = base.select_tasks()
    rows=[]
    c = contract()
    for task in tasks:
        family = str(task["skill_family"])
        target, control = base.candidate_payloads(family)
        for condition in CONDITIONS:
            if condition == "cold": candidates=[]; decision="abstain"; expected="none"; instruction="Answer without a prior."
            elif condition == "always_use_typed": candidates=[candidate(target,"contextual_typed","target")]; decision="admit"; expected=candidates[0]["candidate_id"]; instruction="Always admit and execute the presented typed prior."
            elif condition == "admission_typed": candidates=[candidate(target,"contextual_typed","target")]; decision="admit_or_abstain"; expected=candidates[0]["candidate_id"]; instruction="Admit only when the prior is evidence-grounded and answer-sensitive; otherwise abstain/fallback."
            elif condition == "shuffled_typed": candidates=[candidate(control,"shuffled_control","shuffled")]; decision="admit_or_abstain"; expected="none"; instruction="Reject the unrelated or inverse prior unless it is evidence-grounded."
            elif condition == "incompatible_control": candidates=[candidate(control,"incompatible_control","control")]; decision="abstain"; expected="none"; instruction="Abstain or fallback because this prior is operation-incompatible."
            else: candidates=[candidate(target,"contextual_typed","target")]; decision="abstain"; expected="none"; instruction="Abstain when the evidence trace cannot support an answer-changing operation."
            ids=[str(x["candidate_id"]) for x in candidates]
            body={"schema_version":VERSION,"phase":"5-admission-grounding","stage":"zero_network_design","split":"heldout","task_id":task["task_id"],"task_family":task["task_family"],"skill_family":family,"condition":condition,"expected_admission_decision":decision,"expected_selected_skill_id":expected,"messages":[{"role":"system","content":"Return exactly one JSON object with the seven keys: "+", ".join(c["exact_keys"])+". Contract: "+json.dumps(c,sort_keys=True)}, {"role":"user","content":json.dumps({"available_skill_ids":["none",*ids],"candidates":candidates,"context":annotated(task["context"]),"question":task["question"],"condition_instruction":instruction,"response_contract":c},sort_keys=True)}],"model_id":"qwen3.7-plus","temperature":0,"enable_thinking":False,"response_format":{"type":"json_object"}}
            rows.append({"schema_version":VERSION,"sequence":len(rows)+1,"task_id":task["task_id"],"task_family":task["task_family"],"skill_family":family,"condition":condition,"logical_call_id":f"{EXPERIMENT}:{family}:{task['task_id']}:{condition}","request_hash":stable(body),"transport_payload_hash":stable({"model":body["model_id"],"messages":body["messages"],"temperature":0,"enable_thinking":False,"response_format":{"type":"json_object"}}),"canonical_request_body":body,"private_gold":{"target_answer":task["target_answer"],"counterfactual_answer":task["counterfactual_answer"],"target_intermediate_evidence":task["target_intermediate_evidence"],"counterfactual_intermediate_evidence":task["counterfactual_intermediate_evidence"]},"provenance":{"network_calls":0,"provider_calls":0,"paid_api_calls":0}})
    return tasks, selection, rows

def validate():
    cfg=load(CONFIG)
    if any(cfg["execution"].values()): raise RuntimeError("execution must remain closed")
    tasks, selection, rows=build()
    if len(tasks)!=40 or len(rows)!=240: raise RuntimeError("balance drift")
    if Counter(r["condition"] for r in rows)!=Counter({c:40 for c in CONDITIONS}): raise RuntimeError("condition balance drift")
    if len({r["logical_call_id"] for r in rows})!=240 or len({r["request_hash"] for r in rows})!=240 or len({r["transport_payload_hash"] for r in rows})!=240: raise RuntimeError("identity or transport collision")
    if any("target_answer" in r["canonical_request_body"] for r in rows): raise RuntimeError("private gold leaked")
    result={"schema_version":VERSION,"experiment":EXPERIMENT,"status":"zero_network_admission_grounding_design_passed_closed_not_authorized","tasks":40,"rows":240,"conditions":list(CONDITIONS),"condition_counts":dict(Counter(r["condition"] for r in rows)),"unique_transport_payloads":240,"private_gold_excluded":True,"identity_overlap":{"task_ids":selection["prior_task_overlap"],"logical_call_ids":0,"request_hashes":0},"analysis_plan":cfg["analysis_plan"],"execution":cfg["execution"],"bindings":{"config_sha256":sha256_file(CONFIG),"script_sha256":sha256_file(SCRIPT),"schedule_sha256":stable(rows)},"network_calls":0,"provider_calls":0,"paid_api_calls":0}
    result["aggregate_fingerprint"]=stable(result); return result, rows, selection

def main():
    result, rows, selection=validate()
    ARTIFACT.mkdir(parents=False,exist_ok=False)
    (ARTIFACT/"schedule.json").write_text(json.dumps({"schema_version":VERSION,"rows":rows},ensure_ascii=True,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    (ARTIFACT/"task_selection_audit.json").write_text(json.dumps(selection,ensure_ascii=True,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    (ARTIFACT/"run_manifest.json").write_text(json.dumps(result,ensure_ascii=True,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    (ARTIFACT/"completion_manifest.json").write_text(json.dumps({"schema_version":VERSION,"experiment":EXPERIMENT,"status":"complete","completion_kind":"zero_network_design_preflight","proposed_calls":240,"completed_calls":240,"rows":240,"provider_calls_executed":0,"aggregate_fingerprint":result["aggregate_fingerprint"]},ensure_ascii=True,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    REPORT.parent.mkdir(parents=True,exist_ok=True); REPORT.write_text(f"# Phase 5 admission/grounding zero-network preflight\n\nFrozen 40 new tasks and 240 rows across six conditions. The design separates always-use from evidence-grounded admission and explicit abstention/fallback, with private target/counterfactual gold excluded from requests. No network or provider call occurred.\n\nFingerprint: `{result['aggregate_fingerprint']}`.\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=True,sort_keys=True,indent=2))

if __name__ == "__main__": main()
