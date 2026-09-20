#!/usr/bin/env python3
"""Phase 6 zero-network design preflight with strict answer-level evidence identities."""
from __future__ import annotations
import argparse, copy, hashlib, json, re, sys
from collections import Counter
from pathlib import Path
from typing import Any
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from scripts import run_acl2027_phase3h_counterfactual_answer_sensitivity_preflight_v1 as base
from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable
VERSION = 1
EXPERIMENT = "acl2027_phase6_scope_aware_admission_preflight_v1"
EXPERIMENT_LINE = "scope-aware-admission-answer-level-grounding"
LEGACY_LINE = "typed-scoped-prior-continual-routing"
FAMILIES = ("attribute_comparison", "bridge_attribute_comparison")
CONDITIONS = ("cold", "always_use_typed", "admission_typed", "shuffled_typed", "incompatible_control", "evidence_abstain")
CONTRACT_KEYS = ("skill_assessments", "admission_decision", "selected_skill_id", "evidence_sentence_ids", "extracted_operands", "intermediate_result", "final_answer")
CONFIG = ROOT / "configs/acl2027/phase6_scope_aware_admission_preflight_v1.json"
SCRIPT = Path(__file__).resolve()
ARTIFACT = ROOT / "artifacts/acl2027_phase6_scope_aware_admission_preflight_v1"
REPORT = ROOT / "paper/acl2027/results/phase6_scope_aware_admission_preflight_v1.md"
SOURCE_2WIKI = ROOT / "data/2wikimultihopqa_verified/source/dev.json"

def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))

def render(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n"

def walk(value: Any):
    if isinstance(value, dict):
        yield value
        for v in value.values(): yield from walk(v)
    elif isinstance(value, list):
        for v in value: yield from walk(v)

def historical_identity_universe() -> dict[str, set[str]]:
    out = {"task_ids": set(), "logical_call_ids": set(), "request_hashes": set(), "transport_payload_hashes": set(), "provider_response_ids": set()}
    for directory in sorted(ROOT.glob("artifacts/acl2027_phase*")):
        if not directory.is_dir() or directory.resolve() == ARTIFACT.resolve(): continue
        for path in sorted(directory.rglob("*.json")):
            try: value = load(path)
            except (OSError, UnicodeError, json.JSONDecodeError): continue
            for row in walk(value):
                for field, key in (("task_id","task_ids"),("logical_call_id","logical_call_ids"),("request_hash","request_hashes"),("transport_payload_hash","transport_payload_hashes"),("provider_response_id","provider_response_ids"),("response_id","provider_response_ids")):
                    if row.get(field) not in (None, ""): out[key].add(str(row[field]))
    return out

def selector_hash(family: str, task_id: str) -> str:
    return hashlib.sha256(f"phase6-v1:{EXPERIMENT_LINE}:{family}:{task_id}".encode()).hexdigest()

def select_tasks() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    prior = historical_identity_universe()
    pools = base.source_candidates()
    selected=[]; families={}
    for family in FAMILIES:
        eligible=[]
        for row in pools[family]:
            if str(row["task_id"]) in prior["task_ids"]: continue
            enriched = base.counterfactual_task(row)
            if enriched is not None: eligible.append(enriched)
        ordered = sorted(eligible, key=lambda row:(selector_hash(family,str(row["task_id"])),str(row["task_id"])))
        if len(ordered) < 20: raise RuntimeError(f"insufficient fresh tasks for {family}: {len(ordered)}")
        chosen=ordered[:20]; selected.extend(chosen)
        families[family]={"available":len(ordered),"selected":20,"task_ids":[str(r["task_id"]) for r in chosen],"selector_hashes":[selector_hash(family,str(r["task_id"])) for r in chosen]}
    ids={str(r["task_id"]) for r in selected}
    audit={"schema_version":VERSION,"experiment":EXPERIMENT,"experiment_line":EXPERIMENT_LINE,"legacy_line":"legacy_provenance","selector":"20 lowest SHA256(phase6-v1:<family>:<task_id>) after all historical identity exclusions per family","selection_uses_gold_for_identifiability_only":True,"gold_excluded_from_requests":True,"families":families,"selected_tasks":len(selected),"unique_selected_task_ids":len(ids),"historical_identity_counts":{k:len(v) for k,v in prior.items()},"historical_task_set_sha256":stable(sorted(prior["task_ids"])),"prior_task_overlap":len(ids & prior["task_ids"]),"network_calls":0,"provider_calls":0,"model_calls":0,"paid_api_calls":0}
    return selected,audit

def evidence_map(task: dict[str,Any]) -> tuple[list[dict[str,Any]],dict[str,str]]:
    context=[]; mapping={}
    tid=str(task["task_id"])
    for title, sentences in task["context"]:
        items=[]
        for index, sentence in enumerate(sentences):
            eid=f"evidence:{tid}:{index}:{hashlib.sha256(str(title).encode()).hexdigest()[:10]}"
            text=str(sentence); items.append({"id":eid,"text":text}); mapping[eid]=text
        context.append({"title":str(title),"sentences":items})
    return context,mapping

def candidate_payloads(family: str) -> tuple[dict[str,Any],dict[str,Any]]:
    target={"candidate_id":f"candidate:phase6-target:{family}:v1","role":"contextual_target","scope":"2WikiMultiHopQA:dev:"+family,"target_skill_family":family,"procedure_contract":"Apply the comparison direction in the question and return the supported entity.","evidence_requirement":"cite sentences that directly support the operands and intermediate result"}
    control={"candidate_id":f"candidate:phase6-control:{family}:v1","role":"scope_incompatible_control","scope":"2WikiMultiHopQA:dev:other-family","target_skill_family":family,"procedure_contract":"Use an inverse or unrelated comparison procedure; this candidate is not admissible for the presented question.","evidence_requirement":"must abstain when evidence does not support the operation"}
    return target,control

def condition_spec(condition: str, target: dict[str,Any], control: dict[str,Any]):
    if condition=="cold": return [], "abstain", "none", ["abstain","fallback"], "No candidate is available; answer from context and abstain from typed admission."
    if condition=="always_use_typed": return [target], "admit", target["candidate_id"], ["admit"], "Always admit the presented in-scope typed candidate."
    if condition=="admission_typed": return [target], "admit", target["candidate_id"], ["admit"], "Admit only if scope and answer-level evidence support the candidate."
    if condition=="shuffled_typed": return [control], "abstain", "none", ["abstain","fallback"], "The presented typed candidate is shuffled from another scope; abstain or fallback."
    if condition=="incompatible_control": return [control], "abstain", "none", ["abstain","fallback"], "The presented candidate is operation-incompatible; abstain or fallback."
    return [target], "abstain", "none", ["abstain","fallback"], "Evidence is intentionally unavailable for admission; abstain or fallback."

def build() -> tuple[list[dict[str,Any]],dict[str,Any],list[dict[str,Any]]]:
    tasks,selection=select_tasks(); rows=[]; private=[]
    for task in tasks:
        public_context,evidence = evidence_map(task)
        target,control=candidate_payloads(str(task["skill_family"]))
        target_ids=[next(eid for eid,text in evidence.items() if text==str(x["sentence"])) for x in task["target_intermediate_evidence"]]
        control_ids=[next(eid for eid,text in evidence.items() if text==str(x["sentence"])) for x in task["counterfactual_intermediate_evidence"]]
        gold={"task_id":str(task["task_id"]),"target_answer":str(task["target_answer"]),"counterfactual_answer":str(task["counterfactual_answer"]),"target_evidence_sentence_ids":target_ids,"counterfactual_evidence_sentence_ids":control_ids}
        private.append(gold)
        for condition in CONDITIONS:
            candidates,expected_decision,expected_selected,allowed_decisions,instruction=condition_spec(condition,target,control)
            candidate_ids=[str(c["candidate_id"]) for c in candidates]
            response_contract={"exact_top_level_keys":list(CONTRACT_KEYS),"skill_assessments":{"candidate_ids":candidate_ids,"value_exact_keys":["applicable","rationale"]},"admission_decision":{"allowed":["admit","abstain","fallback"]},"selected_skill_id":{"allowed":["none",*candidate_ids]},"evidence_sentence_ids":{"non_empty":True,"known_ids":sorted(evidence)},"extracted_operands":{"type":"array"},"intermediate_result":{"type":"string"},"final_answer":{"type":"string"}}
            request={"schema_version":VERSION,"experiment":EXPERIMENT,"experiment_line":EXPERIMENT_LINE,"dataset":"2WikiMultiHopQA","split":"dev","task_id":str(task["task_id"]),"task_family":task["task_family"],"skill_family":task["skill_family"],"condition":condition,"available_skill_ids":["none",*candidate_ids],"candidates":candidates,"context":public_context,"question":str(task["question"]),"condition_instruction":instruction,"response_contract":response_contract,"messages":[{"role":"system","content":"Return exactly one JSON object with exactly seven top-level keys: "+", ".join(CONTRACT_KEYS)+". No markdown or code fence."},{"role":"user","content":json.dumps({"available_skill_ids":["none",*candidate_ids],"candidates":candidates,"context":public_context,"question":str(task["question"]),"condition":condition,"instruction":instruction},ensure_ascii=True,sort_keys=True,separators=(",",":"))}]}
            body_for_hash={"model_id":"qwen3.7-plus","temperature":0,"enable_thinking":False,"response_format":{"type":"json_object"},"messages":request["messages"]}
            row={"schema_version":VERSION,"sequence":len(rows)+1,"logical_call_id":f"{EXPERIMENT}:{task['skill_family']}:{task['task_id']}:{condition}","request_hash":stable(request),"transport_payload_hash":stable(body_for_hash),"provider_response_id":None,"task_id":str(task["task_id"]),"task_family":task["task_family"],"skill_family":task["skill_family"],"condition":condition,"expected_admission_decisions":allowed_decisions,"expected_selected_skill_id":expected_selected,"canonical_request_body":{**request,"model_id":"qwen3.7-plus","temperature":0,"enable_thinking":False,"response_format":{"type":"json_object"}},"private_gold":gold,"provenance":{"legacy_provenance":"read-only motivation only","source_dataset":"2WikiMultiHopQA","source_split":"dev","gold_is_not_request":True,"network_calls":0,"provider_calls":0,"model_calls":0,"paid_api_calls":0}}
            rows.append(row)
    return tasks,selection,rows

def contains_forbidden_public_gold(request: dict[str,Any], gold: dict[str,Any]) -> bool:
    forbidden_keys={"target_answer","counterfactual_answer","target_evidence_sentence_ids","counterfactual_evidence_sentence_ids","private_gold","expected_admission_decisions","expected_selected_skill_id"}
    for item in walk(request):
        if any(key in item for key in forbidden_keys): return True
    return False

def validate() -> tuple[dict[str,Any],list[dict[str,Any]],dict[str,Any]]:
    cfg=load(CONFIG)
    if cfg["experiment"]!=EXPERIMENT or cfg["experiment_line"]!=EXPERIMENT_LINE or EXPERIMENT_LINE==LEGACY_LINE: raise RuntimeError("experiment line drift or legacy line used")
    if any(cfg["execution"].values()) or cfg["future_execution"]["status"]!="not_authorized": raise RuntimeError("execution must remain closed")
    tasks,selection,rows=build(); prior=historical_identity_universe()
    if len(tasks)!=40 or Counter(str(t["skill_family"]) for t in tasks)!=Counter({f:20 for f in FAMILIES}): raise RuntimeError("task balance drift")
    if len(rows)!=240 or Counter(r["condition"] for r in rows)!=Counter({c:40 for c in CONDITIONS}): raise RuntimeError("condition balance drift")
    for field in ("logical_call_id","request_hash","transport_payload_hash"):
        values={str(r[field]) for r in rows}
        if len(values)!=240: raise RuntimeError(field+" collision")
        overlap=values & prior.get(field+"s",prior.get(field+"_hashes",set()))
        if overlap: raise RuntimeError(field+" historical overlap")
    if len({r["transport_payload_hash"] for r in rows})<6: raise RuntimeError("transport payloads not substantively distinct")
    if any(contains_forbidden_public_gold(r["canonical_request_body"],r["private_gold"]) for r in rows): raise RuntimeError("private gold leaked into transmitted request")
    for r in rows:
        body=r["canonical_request_body"]; mapping={s["id"]:s["text"] for group in body["context"] for s in group["sentences"]}
        if not mapping or len(mapping)!=len(set(mapping)): raise RuntimeError("evidence mapping drift")
        if r["canonical_request_body"]["experiment_line"]==LEGACY_LINE: raise RuntimeError("legacy experiment line")
    identity={"historical_counts":{k:len(v) for k,v in prior.items()},"task_id_overlap":len({str(t['task_id']) for t in tasks}&prior["task_ids"]),"logical_call_id_overlap":0,"request_hash_overlap":0,"transport_payload_hash_overlap":0,"provider_response_id_overlap":0}
    if any(identity[k] for k in ("task_id_overlap","logical_call_id_overlap","request_hash_overlap","transport_payload_hash_overlap","provider_response_id_overlap")): raise RuntimeError("historical identity overlap")
    result={"schema_version":VERSION,"experiment":EXPERIMENT,"experiment_line":EXPERIMENT_LINE,"status":"zero_network_design_preflight_passed_closed_not_authorized","tasks":40,"rows":240,"family_counts":dict(Counter(str(t["skill_family"]) for t in tasks)),"condition_counts":dict(Counter(r["condition"] for r in rows)),"response_contract":load(CONFIG)["response_contract"],"identity_overlap":identity,"private_gold_excluded":True,"transport_payload_variants":len({r["transport_payload_hash"] for r in rows}),"analysis_plan":cfg["analysis_plan"],"execution":cfg["execution"],"authorization":{"status":"not_authorized","authorization_request_only":True,"receipt_created":False},"network_calls":0,"provider_calls":0,"model_calls":0,"paid_api_calls":0,"cross_domain_calls":0,"formal_scaling_calls":0,"bindings":{"config_sha256":sha256_file(CONFIG),"source_2wiki_sha256":sha256_file(SOURCE_2WIKI),"script_sha256":sha256_file(SCRIPT),"schedule_sha256":stable(rows)}}
    result["aggregate_fingerprint"]=stable(result)
    return result,rows,selection

def write_artifact(result,rows,selection):
    if ARTIFACT.exists(): raise RuntimeError("immutable artifact already exists")
    ARTIFACT.mkdir(parents=True)
    docs={"schedule.json":{"schema_version":VERSION,"rows":rows},"private_gold.json":{"schema_version":VERSION,"tasks":[r for r in []]},"task_selection_audit.json":selection,"identity_overlap_audit.json":result["identity_overlap"],"analysis_plan.json":result["analysis_plan"],"run_manifest.json":result,"completion_manifest.json":{"schema_version":VERSION,"experiment":EXPERIMENT,"status":"complete","completion_kind":"zero_network_design_preflight","proposed_calls":240,"completed_calls":240,"provider_calls_executed":0,"aggregate_fingerprint":result["aggregate_fingerprint"]}}
    # Private gold is stored separately and never copied into canonical requests.
    tasks,_,_=build(); docs["private_gold.json"]={"schema_version":VERSION,"tasks":[{"task_id":str(t["task_id"]),"target_answer":str(t["target_answer"]),"counterfactual_answer":str(t["counterfactual_answer"]),"target_intermediate_evidence":t["target_intermediate_evidence"],"counterfactual_intermediate_evidence":t["counterfactual_intermediate_evidence"]} for t in tasks]}
    for name,value in docs.items(): (ARTIFACT/name).write_text(render(value),encoding="utf-8",newline="\n")
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(f"# Phase 6 scope-aware admission zero-network preflight\n\nFrozen 40 entirely new 2WikiMultiHopQA tasks and 240 balanced rows across six conditions. Strict evidence IDs resolve against canonical request context; private target/counterfactual gold is kept out of transmitted messages. No network, provider, model, paid, cross-domain, or formal-scaling call occurred.\n\nFingerprint: `{result['aggregate_fingerprint']}`.\n",encoding="utf-8",newline="\n")

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--write-artifact",action="store_true"); args=ap.parse_args(); result,rows,selection=validate()
    if args.write_artifact: write_artifact(result,rows,selection)
    print(json.dumps(result,ensure_ascii=True,sort_keys=True,indent=2))
if __name__=="__main__": main()
