#!/usr/bin/env python3
"""qwen3.6-flash 完整实验: formal seed44 + 3 baseline methods x 3 reps."""
import subprocess, sys, os, time

PROJECT = r"E:\桌面\暑期实训\SkillOpt"
PYTHON = sys.executable
INFER = os.path.join(PROJECT, "scripts", "infer_baselines.py")
OUT = os.path.join(PROJECT, "outputs")
UTILITY = os.path.join(PROJECT, "outouts", "frozen", "moar_utility.json")
MODEL = "qwen3.6-flash"

# Fix typo: outputs not outouts
UTILITY = os.path.join(PROJECT, "outputs", "frozen", "moar_utility.json")
N = 200
WORKERS = "16"

# ── Step 1: formal seed 44 ──────────────────────────────────
# Use jos_sanity_check with same target for both s/l to get only qwen3.6-flash
# But that's slow and the old script has issues. Better: use moar_searchqa_eval.py
# for each method since it handles single-model cleanly.

# Actually: use the approach that works reliably:
#   python jos_sanity_check.py --target-s qwen3.6-flash --target-l qwen3.6-flash
# But only keep the output.

# Simpler: run moar_searchqa_eval.py for MOAR + infer_baselines.py for rest
# on qwen3.6-flash.

t0 = time.time()
idx = 0

# ── Step 1: Core Only + TF-IDF + MOAR via moar_searchqa_eval ──
print("=" * 60)
print("STEP 1: Formal seed 44 (Core Only + TF-IDF + MOAR)")
print("=" * 60)
idx += 1
cmd = [
    PYTHON,
    os.path.join(PROJECT, "scripts", "moar_searchqa_eval.py"),
    "--skill", "outputs/searchqa_rag/best_skill.md",
    "--target-model", MODEL,
    "--limit", str(N),
    "--split", "valid_unseen",
    "--seed", "44",
    "--workers", WORKERS,
    "--out", os.path.join(OUT, "jos_formal_targetL_seed44.json"),
]
print(f"\n[{idx}] {' '.join(cmd)}")
r = subprocess.run(cmd, cwd=PROJECT, capture_output=True, text=True, timeout=1800)
if r.returncode == 0:
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    for l in lines[-10:]:
        print(f"  {l}")
else:
    print(f"  STDERR: {r.stderr[-500:]}")
    print(f"  STDOUT: {r.stdout[-500:]}")
sys.stdout.flush()

# ── Step 2: Baselines (BM25, Greedy-Cold, Greedy-Utility) x 3 reps ──
print("\n" + "=" * 60)
print("STEP 2: Baselines (BM25, Greedy-Cold, Greedy-Utility) x 3 reps")
print("=" * 60)

for method in ["bm25", "greedy-cold", "greedy-util"]:
    for rep in ["rep42", "rep43", "rep44"]:
        idx += 1
        out_path = os.path.join(OUT, f"jos_formal_{method.replace('-','_')}_{rep}_targetL.json")
        cmd = [
            PYTHON, INFER,
            "--method", method,
            "--target-model", MODEL,
            "--limit", str(N),
            "--workers", WORKERS,
            "--out", out_path,
        ]
        if method == "greedy-util":
            cmd.extend(["--utility-file", UTILITY])
        print(f"\n[{idx}] {method} {rep}")
        st = time.time()
        try:
            r = subprocess.run(cmd, cwd=PROJECT, capture_output=True, text=True, timeout=600)
            elapsed = time.time() - st
            if r.returncode == 0:
                lines = [l for l in r.stdout.splitlines() if l.strip()]
                print(f"  OK ({elapsed:.0f}s): {lines[-1] if lines else 'done'}")
            else:
                print(f"  FAIL ({elapsed:.0f}s)")
                print(f"  STDERR: {r.stderr[-300:]}")
        except subprocess.TimeoutExpired:
            print(f"  TIMEOUT after 600s")

print(f"\nTotal: {time.time()-t0:.0f}s. Done.")
