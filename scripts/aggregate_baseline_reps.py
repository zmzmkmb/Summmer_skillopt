#!/usr/bin/env python3
"""汇总基线 3-rep 结果."""
import json, os, sys, numpy as np

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs")

methods = {
    'BM25': ['jos_formal_bm25_rep42','jos_formal_bm25_rep43','jos_formal_bm25_rep44'],
    'Greedy-Cold': ['jos_formal_greedy_cold_rep42','jos_formal_greedy_cold_rep43','jos_formal_greedy_cold_rep44'],
    'Greedy-Utility': ['jos_formal_greedy_util_rep42','jos_formal_greedy_util_rep43','jos_formal_greedy_util_rep44'],
}

for method, files in methods.items():
    accs = []; rules = []; tokens = []; budget_viol = 0; api_fail = 0
    for fname in files:
        d = json.load(open(os.path.join(OUT, fname + '.json'), encoding='utf-8'))
        accs.append(d['acc'])
        rules.append(d['avg_rules'])
        pq = d['per_question']
        tokens.append(np.mean([p.get('selected_tokens',0) for p in pq]))
        budget_viol += sum(1 for p in pq if p.get('budget_violated', False))
        api_fail += sum(1 for p in pq if p.get('predicted','') == '')

    mean = np.mean(accs); std = np.std(accs, ddof=1) if len(accs) > 1 else 0
    acc_strs = ", ".join("%.1f%%" % (a*100) for a in accs)
    print("%s:" % method)
    print("  acc: %.2f%% +/- %.2f%%  (%s)" % (mean*100, std*100, acc_strs))
    print("  rules: %.1f  tokens: %.0f  budget_viol: %d  api_fail: %d" % (
        np.mean(rules), np.mean(tokens), budget_viol, api_fail))
    print()
