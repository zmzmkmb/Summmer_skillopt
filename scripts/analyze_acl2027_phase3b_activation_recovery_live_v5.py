#!/usr/bin/env python3
"""Combine the reusable v3 prefix with completed v5 recovery and run frozen analysis."""
from __future__ import annotations

import importlib.util, json, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from scripts.acl2027_phase2_response_verifier_v3 import sha256_file, stable

BASE_PATH=ROOT/"scripts/analyze_acl2027_phase3b_activation_live_v3.py"
spec=importlib.util.spec_from_file_location("_phase3b_analysis_v5_base",BASE_PATH)
if spec is None or spec.loader is None: raise RuntimeError("cannot load v3 analyzer base")
base=importlib.util.module_from_spec(spec); spec.loader.exec_module(base)

V1=ROOT/"artifacts/acl2027_phase3b_activation_preflight_v1"
V4=ROOT/"artifacts/acl2027_phase3b_activation_recovery_preflight_v4"
V5=ROOT/"artifacts/acl2027_phase3b_activation_recovery_live_v5"
V1_GOLD,V1_SCHEDULE=V1/"activation_private_gold.json",V1/"activation_schedule.json"
RECOVERY_GOLD,RECOVERY_SCHEDULE,REUSABLE,PLAN=V4/"recovery_private_gold.json",V4/"recovery_schedule.json",V4/"reusable_v3_prefix.json",V4/"analysis_plan.json"
V5_LEDGER,V5_AUDIT=V5/"ledger.json",V5/"run_audit.json"
COMBINED_GOLD,COMBINED_SCHEDULE,COMBINED_LEDGER=V5/"combined_private_gold.json",V5/"combined_schedule.json",V5/"combined_ledger.json"
AUDIT,REPORT=V5/"activation_analysis.json",ROOT/"paper/acl2027/results/phase3b_activation_recovery_live_v5.md"


def load(path:Path): return json.loads(path.read_text(encoding="utf-8-sig"))


def materialize_combined() -> None:
    reusable=load(REUSABLE); recovery=load(V5_LEDGER); run=load(V5_AUDIT)
    if len(reusable)!=125 or len(recovery)!=175 or run.get("status")!="completed" or run.get("authorization_closed") is not True: raise RuntimeError("complete closed v5 recovery required")
    reusable_ids={str(row["task_id"]) for row in reusable}
    gold=[row for row in load(V1_GOLD) if str(row["task_id"]) in reusable_ids]+load(RECOVERY_GOLD)
    schedule=[row for row in load(V1_SCHEDULE)["schedule"] if str(row["task_id"]) in reusable_ids]+load(RECOVERY_SCHEDULE)["schedule"]
    ledger=reusable+recovery
    if len(gold)!=60 or len(schedule)!=300 or len(ledger)!=300 or len({(str(r["task_id"]),r["condition"]) for r in ledger})!=300: raise RuntimeError("combined Phase 3B grid drift")
    COMBINED_GOLD.write_text(json.dumps(gold,ensure_ascii=True,sort_keys=True,indent=2)+"\n",encoding="utf-8",newline="\n")
    COMBINED_SCHEDULE.write_text(json.dumps({"schema_version":5,"schedule":schedule},ensure_ascii=True,sort_keys=True,indent=2)+"\n",encoding="utf-8",newline="\n")
    COMBINED_LEDGER.write_text(json.dumps(ledger,ensure_ascii=True,sort_keys=True,indent=2)+"\n",encoding="utf-8",newline="\n")


def analyze():
    materialize_combined()
    base.GOLD,base.SCHEDULE,base.PLAN=COMBINED_GOLD,COMBINED_SCHEDULE,PLAN
    base.LEDGER,base.RUN_AUDIT=COMBINED_LEDGER,V5_AUDIT
    result=base.analyze(); v3_audit=load(ROOT/"artifacts/acl2027_phase3b_activation_live_v3/run_audit.json"); v5_audit=load(V5_AUDIT)
    result.update({"schema_version":5,"source_v3_reusable_rows":125,"source_v5_recovery_rows":175,"combined_provider_attempts":v3_audit["provider_attempts"]+v5_audit["provider_attempts"],"v3_known_stage_cost_lower_bound_cny":v3_audit["known_stage_cost_lower_bound_cny"],"v5_exact_stage_cost_cny":v5_audit["exact_stage_cost_cny"],"combined_known_stage_cost_cny":round(v3_audit["known_stage_cost_lower_bound_cny"]+v5_audit["exact_stage_cost_cny"],6)})
    result["bindings"].update({"reusable_v3_prefix_sha256":sha256_file(REUSABLE),"v5_ledger_sha256":sha256_file(V5_LEDGER),"combined_gold_sha256":sha256_file(COMBINED_GOLD),"combined_schedule_sha256":sha256_file(COMBINED_SCHEDULE),"combined_ledger_sha256":sha256_file(COMBINED_LEDGER)})
    result["aggregate_fingerprint"]=stable({k:v for k,v in result.items() if k!="aggregate_fingerprint"}); return result


def report_text(result):
    u=result["uptake_rates"]; p=result["contextual_vs_shuffled_uptake"]; a=result["alias_contextual_vs_shuffled"]
    return f"""# ACL 2027 Phase 3B activation recovery live v5

The combined 60-task, 300-row grid contains 125 reusable v3 rows and 175 completed v5 recovery rows. Contract-valid responses: `{result['contract_valid_rows']}/300`.

Contextual typed uptake: `{u['contextual_typed_prior']:.4f}`. Shuffled typed uptake: `{u['shuffled_typed_prior']:.4f}`. Paired uptake difference: `{p['rate_difference']:+.4f}`. Alias-tolerant contextual-versus-shuffled net wins: `{a['net_wins']}`.

Frozen decision gate: **{result['decision_gate']}**. Stop rule fired: `{result['stop_rule_fired']}`. Scale-up allowed: `{result['scale_up_allowed']}`.

V5 exact stage cost: CNY `{result['v5_exact_stage_cost_cny']}`. Combined known v3+v5 stage cost: CNY `{result['combined_known_stage_cost_cny']}`. Later stages and formal scaling remain unauthorized.

Aggregate fingerprint: `{result['aggregate_fingerprint']}`.
"""


if __name__=="__main__":
    result=analyze(); AUDIT.write_text(json.dumps(result,ensure_ascii=True,sort_keys=True,indent=2)+"\n",encoding="utf-8",newline="\n"); REPORT.parent.mkdir(parents=True,exist_ok=True); REPORT.write_text(report_text(result),encoding="utf-8",newline="\n"); print(json.dumps(result,indent=2,sort_keys=True))
