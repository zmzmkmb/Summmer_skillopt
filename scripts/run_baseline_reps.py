#!/usr/bin/env python3
"""批量跑基线 3-rep: BM25 + Greedy-Cold + Greedy-Utility × 200 题.

每个方法跑 3 次（rep42/43/44），测量 target model 推理波动。
"""
import subprocess, sys, os, time

PROJECT = r"E:\桌面\暑期实训\SkillOpt"
PYTHON = sys.executable
SCRIPT = os.path.join(PROJECT, "scripts", "infer_baselines.py")
OUT = os.path.join(PROJECT, "outputs")
UTILITY = os.path.join(PROJECT, "outputs", "frozen", "moar_utility.json")

METHODS = ["bm25", "greedy-cold", "greedy-util"]
REPS = ["rep42", "rep43", "rep44"]
MODEL = "qwen-flash"
N = 200

total = len(METHODS) * len(REPS)
idx = 0
t0 = time.time()

for method in METHODS:
    for rep in REPS:
        idx += 1
        out_path = os.path.join(OUT, f"jos_formal_{method.replace('-','_')}_{rep}.json")
        cmd = [
            PYTHON, SCRIPT,
            "--method", method,
            "--target-model", MODEL,
            "--limit", str(N),
            "--workers", "16",
            "--out", out_path,
        ]
        if method == "greedy-util":
            cmd.extend(["--utility-file", UTILITY])
        print(f"\n[{idx}/{total}] {method} {rep} ({' '.join(cmd[-6:] if len(cmd)>6 else cmd)})")
        print(f"  Started: {time.strftime('%H:%M:%S')}")
        st = time.time()
        r = subprocess.run(cmd, cwd=PROJECT, capture_output=True, text=True)
        elapsed = time.time() - st
        if r.returncode == 0:
            lines = [l for l in r.stdout.splitlines() if l.strip()]
            print(f"  OK ({elapsed:.0f}s): {lines[-1] if lines else 'done'}")
        else:
            print(f"  FAIL ({elapsed:.0f}s): {r.stderr[:300]}")
        sys.stdout.flush()

print(f"\nTotal: {time.time()-t0:.0f}s. Done.")
