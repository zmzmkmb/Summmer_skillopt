#!/usr/bin/env python3
"""Zero-network mediation audit over the completed Phase 3B activation grid."""
from __future__ import annotations

import json, sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from scripts.acl2027_phase2_response_verifier_v3 import normalize_answer, sha256_file, stable

CONFIG=ROOT/"configs/acl2027/phase3c_uptake_outcome_mediation_audit_v1.json"
SOURCE=ROOT/"artifacts/acl2027_phase3b_activation_recovery_live_v5/activation_analysis.json"
SCRIPT=ROOT/"scripts/analyze_acl2027_phase3c_uptake_outcome_mediation_v1.py"
TEST=ROOT/"tests/test_acl2027_phase3c_uptake_outcome_mediation_v1.py"
ARTIFACT=ROOT/"artifacts/acl2027_phase3c_uptake_outcome_mediation_audit_v1"
AUDIT=ARTIFACT/"mediation_audit.json"
REPORT=ROOT/"paper/acl2027/results/phase3c_uptake_outcome_mediation_audit_v1.md"


def load(path:Path)->Any: return json.loads(path.read_text(encoding="utf-8-sig"))


def pair(rows:dict[str,dict[str,Any]],left:str,right:str,key:str)->dict[str,Any]:
    left_only=sum(bool(r[left][key]) and not bool(r[right][key]) for r in rows.values()); right_only=sum(bool(r[right][key]) and not bool(r[left][key]) for r in rows.values())
    both=sum(bool(r[left][key]) and bool(r[right][key]) for r in rows.values()); neither=len(rows)-left_only-right_only-both
    return {"left_only":left_only,"right_only":right_only,"both":both,"neither":neither,"net_wins":left_only-right_only,"rate_difference":(left_only-right_only)/len(rows) if rows else None}


def audit()->dict[str,Any]:
    cfg,source=load(CONFIG),load(SOURCE)
    if source.get("aggregate_fingerprint")!=cfg["source_phase3b_fingerprint"] or source.get("status")!="complete" or source.get("rows")!=300: raise RuntimeError("Phase 3B source boundary drift")
    grids:dict[str,dict[str,Any]]=defaultdict(dict)
    for row in source["outcomes"]: grids[str(row["task_id"])][str(row["condition"])]=row
    if len(grids)!=60 or any(len(row)!=5 for row in grids.values()): raise RuntimeError("Phase 3B grid incomplete")
    strata:dict[str,dict[str,dict[str,Any]]]={name:{} for name in cfg["strata"]}
    task_rows=[]
    for task_id,row in grids.items():
        c,s=row["contextual_typed_prior"],row["shuffled_typed_prior"]
        if c["primary_uptake"] and not s["primary_uptake"]: stratum="contextual_only"
        elif c["primary_uptake"] and s["primary_uptake"]: stratum="both_adopt"
        elif not c["primary_uptake"] and not s["primary_uptake"]: stratum="neither_adopt"
        else: stratum="shuffled_only"
        strata[stratum][task_id]=row
        operation_changed=c["intermediate_operation"].strip().lower()!=s["intermediate_operation"].strip().lower()
        answer_changed=normalize_answer(c["final_answer"])!=normalize_answer(s["final_answer"])
        task_rows.append({"task_id":task_id,"skill_family":c["skill_family"],"stratum":stratum,"operation_changed_contextual_vs_shuffled":operation_changed,"normalized_answer_changed_contextual_vs_shuffled":answer_changed,"contextual_alias_correct":c["alias_tolerant_correct"],"shuffled_alias_correct":s["alias_tolerant_correct"],"cold_alias_correct":row["cold"]["alias_tolerant_correct"],"contextual_strict_correct":c["strict_correct"],"shuffled_strict_correct":s["strict_correct"],"cold_strict_correct":row["cold"]["strict_correct"]})
    summaries={}
    for name,items in strata.items():
        selected=[r for r in task_rows if r["stratum"]==name]; n=len(selected)
        summaries[name]={"tasks":n,"task_rate":n/60,"family_counts":dict(Counter(r["skill_family"] for r in selected)),"operation_change_count":sum(r["operation_changed_contextual_vs_shuffled"] for r in selected),"operation_change_rate":sum(r["operation_changed_contextual_vs_shuffled"] for r in selected)/n if n else None,"normalized_answer_change_count":sum(r["normalized_answer_changed_contextual_vs_shuffled"] for r in selected),"normalized_answer_change_rate":sum(r["normalized_answer_changed_contextual_vs_shuffled"] for r in selected)/n if n else None,"alias_contextual_vs_shuffled":pair(items,"contextual_typed_prior","shuffled_typed_prior","alias_tolerant_correct"),"alias_contextual_vs_cold":pair(items,"contextual_typed_prior","cold","alias_tolerant_correct"),"strict_contextual_vs_shuffled":pair(items,"contextual_typed_prior","shuffled_typed_prior","strict_correct"),"strict_contextual_vs_cold":pair(items,"contextual_typed_prior","cold","strict_correct")}
    selective=summaries["contextual_only"]; pg=cfg["positive_gate"]; ng=cfg["negative_gate"]
    positive=selective["tasks"]>=pg["contextual_only_tasks_at_least"] and selective["alias_contextual_vs_shuffled"]["net_wins"]>=pg["contextual_vs_shuffled_alias_net_wins_at_least"] and -selective["alias_contextual_vs_cold"]["net_wins"]<=pg["contextual_vs_cold_alias_net_loss_at_most"] and selective["normalized_answer_change_rate"]>=pg["contextual_vs_shuffled_normalized_answer_change_rate_at_least"]
    negative=selective["tasks"]>=ng["contextual_only_tasks_at_least"] and selective["alias_contextual_vs_shuffled"]["net_wins"]<=ng["contextual_vs_shuffled_alias_net_wins_at_most"] and selective["alias_contextual_vs_cold"]["net_wins"]<ng["contextual_vs_cold_alias_net_wins_below"]
    gate="positive" if positive else "negative" if negative else "inconclusive"
    warning=summaries["both_adopt"]["task_rate"]>=cfg["specificity_warning"]["both_adopt_rate_at_least"]
    result={"schema_version":1,"status":"complete","source_phase3b_fingerprint":source["aggregate_fingerprint"],"tasks":60,"rows":300,"completed_calls":300,"strata":summaries,"decision_gate":gate,"specificity_warning_fired":warning,"interpretation":"selective uptake mediates bounded answer utility" if gate=="positive" else "selective uptake does not establish answer utility" if gate=="negative" else "mediation evidence remains inconclusive","next_design":"repair abstention and bundle specificity in universal-uptake families before cross-domain scaling" if warning else "test selective uptake on a new domain split","task_rows":task_rows,"network_calls":0,"provider_calls":0,"model_calls":0,"paid_api_calls":0,"formal_scaling_calls":0,"bindings":{"config_sha256":sha256_file(CONFIG),"source_analysis_sha256":sha256_file(SOURCE),"script_sha256":sha256_file(SCRIPT),"test_sha256":sha256_file(TEST)}}
    result["aggregate_fingerprint"]=stable(result); return result


def report_text(r:dict[str,Any])->str:
    s,b=r["strata"]["contextual_only"],r["strata"]["both_adopt"]
    return f"""# ACL 2027 Phase 3C uptake-outcome mediation audit v1

This zero-network audit stratifies the completed Phase 3B grid by contextual-versus-shuffled uptake. Contextual-only uptake occurred on `{s['tasks']}/60` tasks; both bundles were adopted on `{b['tasks']}/60`.

Within contextual-only tasks, normalized answers changed on `{s['normalized_answer_change_count']}/{s['tasks']}` and intermediate-operation labels changed on `{s['operation_change_count']}/{s['tasks']}`. Alias-tolerant contextual-versus-shuffled net wins were `{s['alias_contextual_vs_shuffled']['net_wins']}`; contextual-versus-cold net wins were `{s['alias_contextual_vs_cold']['net_wins']}`.

Frozen mediation gate: **{r['decision_gate']}**. Specificity warning fired: `{r['specificity_warning_fired']}`. The next design should {r['next_design']}.

No network, provider, model, paid, or formal-scaling call occurred. Aggregate fingerprint: `{r['aggregate_fingerprint']}`.
"""


def main()->int:
    result=audit(); ARTIFACT.mkdir(parents=True,exist_ok=True); AUDIT.write_text(json.dumps(result,ensure_ascii=True,sort_keys=True,indent=2)+"\n",encoding="utf-8",newline="\n"); REPORT.parent.mkdir(parents=True,exist_ok=True); REPORT.write_text(report_text(result),encoding="utf-8",newline="\n"); print(json.dumps({k:v for k,v in result.items() if k!="task_rows"},indent=2,sort_keys=True)); return 0


if __name__=="__main__": raise SystemExit(main())
