#!/usr/bin/env python3
"""Build TraceGraph TG1 skills deterministically from the audited train manifest."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
FORBIDDEN={"images","pddl_params","scene","turk_annotations","planner_action","api_action","raw_traj_data","expert_future_actions","phase0_to_phase6_artifact"}
PROTOCOL="tracegraph-tg1-skillbank-construction-v1"

def canon_action(x):
    d=x.get("discrete_action",{}) if isinstance(x,dict) else {}
    return {"action":str(d.get("action","")), "args":d.get("args",{})}

def build(manifest_path: Path, output: Path, source_root: Path):
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("source_split")!="train": raise ValueError("manifest is not train-only")
    records=[]; seen={}
    for src in manifest["records"]:
        if src["source_split"]!="train" or any(x in src["gamefile_relative_path"] for x in ("valid_seen","valid_unseen")): raise ValueError("split contamination")
        traj=source_root / src["gamefile_relative_path"].replace("game.tw-pddl","traj_data.json")
        d=json.loads(traj.read_text(encoding="utf-8"))
        high=d.get("plan",{}).get("high_pddl",[])
        for i,span in enumerate(high):
            action=canon_action(span)
            if not action["action"]: raise ValueError("empty action")
            payload={"trajectory_id":src["trajectory_id"],"source_split":"train","gamefile_sha256":src["gamefile_sha256"],"traj_data_sha256":src["traj_data_sha256"],"task_type":src["task_type"],"span_start":i,"span_end":i,"canonical_actions":[action],"construction_protocol_fingerprint":PROTOCOL}
            raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=True)
            payload["skill_id"]=hashlib.sha256(raw.encode()).hexdigest()
            if any(k in payload for k in FORBIDDEN): raise ValueError("forbidden field emitted")
            old=seen.get(payload["skill_id"])
            if old and old != payload: raise ValueError("conflicting duplicate skill id")
            seen[payload["skill_id"]]=payload
    records=sorted(seen.values(),key=lambda x:x["skill_id"])
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("w",encoding="utf-8",newline="\n") as f:
        for r in records: f.write(json.dumps(r,ensure_ascii=True,sort_keys=True,separators=(",",":"))+"\n")
    return records

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--manifest",type=Path,required=True); ap.add_argument("--source-root",type=Path,required=True); ap.add_argument("--output",type=Path,required=True); a=ap.parse_args()
    rows=build(a.manifest,a.output,a.source_root); print(f"BUILT: {len(rows)} deterministic skills; zero network/provider/model/API calls.")
if __name__=="__main__": main()
