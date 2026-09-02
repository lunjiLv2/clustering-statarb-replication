"""Across-rule ARI on the common calendar: twelve clusterizers (66 pairs) plus the two controls (§5, tab:gradient).

Same estimator as ari_within_rule_v3.py: adjusted Rand index per refit day, averaged over days, then
over pairs. Because the CPU and tier-2 caches do not store the same universe in the same order, the
two label vectors are aligned by ticker on the per-day intersection (>= 100 shared names). Gates: no
arm compared with itself (paths differ); label vectors on a day never identical; >= 100 usable days
per pair. Output: analysis/results/ari_across_rule_v3_cal6913.csv (arm names as in the tables:
'sssnet_w60').

Run: ``python analysis/ari_across_rule_v3.py``
"""
from __future__ import annotations
import itertools, sys
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.metrics import adjusted_rand_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis import _partitions as P
from analysis._compare import compare_and_write

RULES = ["kmeans_ret", "sssnet_w60", "agglo_complete", "fv3sm_w60", "sponge_w60", "pca_load",
         "agglo_avg", "sortino_w60", "fv2a_w60", "sharpe_fixed_w60", "gics", "spectral_unsigned"]
CTRL = ["k1", "random"]


def main() -> None:
    C = {}
    for a in RULES + CTRL:
        if not P.cache_path(a).is_file():
            print(f"  [skip] {a}: {P.cache_path(a)} missing"); continue
        C[a] = P.load_cache(a); print(f"  loaded {a:20s} {len(C[a])} refit dates", flush=True)
    rows = []
    for i, j in itertools.combinations([a for a in RULES + CTRL if a in C], 2):
        assert P.cache_path(i) != P.cache_path(j), f"[GATE1 FAIL] {i} and {j} resolve to the same file"
        per, ov = [], []
        for d in P.in_window(set(C[i]) & set(C[j])):
            mi = {t: int(l) for t, l in zip(C[i][d]["universe"], C[i][d]["labels"])}
            mj = {t: int(l) for t, l in zip(C[j][d]["universe"], C[j][d]["labels"])}
            sh = sorted(set(mi) & set(mj))
            if len(sh) < 100:
                continue
            li = np.array([mi[t] for t in sh]); lj = np.array([mj[t] for t in sh])
            assert not np.array_equal(li, lj), f"[GATE2 FAIL] {i}/{j} {d}: identical label vectors"
            per.append(adjusted_rand_score(li, lj)); ov.append(len(sh) / max(len(mi), len(mj)))
        if len(per) < 100:
            print(f"  [drop] {i}-{j}: only {len(per)} usable days"); continue
        rows.append(dict(i=i, j=j, days=len(per), ARI=float(np.mean(per)), universe_overlap=float(np.mean(ov)),
                         kind=("rule-rule" if i in RULES and j in RULES else "rule-control" if (i in RULES) != (j in RULES) else "control-control")))
    df = pd.DataFrame(rows); rr = df[df.kind == "rule-rule"]
    print(f"across-rule ARI over {len(rr)} pairs: mean {rr.ARI.mean():.4f}, band {rr.ARI.min():.4f}–{rr.ARI.max():.4f}")
    compare_and_write(df, "ari_across_rule_v3_cal6913.csv", ["i", "j"])


if __name__ == "__main__":
    main()
