"""Within-rule partition-seed ARI on the common calendar (tab:gradient's ARI row, sec:pseed, A.12).

For each of the ten arms with partition-seed twins (six CPU clusterizers incl. the random control and
the SSSNET partition, four trading-driven tier-2 clusterizers) the adjusted Rand index between every
pair of the five partition draws PS = (1, 2, 3, 4, 5) (ten pairs) is computed on every common refit
day on which the caches hold the same universe in the same order, then averaged over days and pairs.
Until 2026-09-01 the draws were {42, 1, 123} (base cache + twins _ps1/_ps123); the partition axis
now mirrors the head-seed set {1,...,5} (CORRECTIONS N84). Gates: the five paths are distinct; the
label vectors on a day are never all identical (would mean one file loaded several times); >= 100
usable days per arm. Output: ari_within_rule_v3_cal6913.csv under paths.RESULTS (arm names as in the
caches: 'sssnetpre'); columns ARI_ps{i}_ps{j} for the ten pairs, ARI_mean over all pair-days.

Run: ``python analysis/ari_within_rule_v3.py``
"""
from __future__ import annotations
import itertools, sys
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.metrics import adjusted_rand_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis import _partitions as P
from analysis._compare import compare_and_write

CPU = ["kmeans_ret", "pca_load", "spectral_unsigned", "sponge_w60", "random", "sssnetpre"]
TIER2 = ["fv2a_w60", "fv3sm_w60", "sharpe_fixed_w60", "sortino_w60"]
PS = (1, 2, 3, 4, 5)   # partition seeds; the head seed is not involved (partition-only statistic)


def main() -> None:
    rows = []; pairs = list(itertools.combinations(range(len(PS)), 2))
    for arm in CPU + TIER2:
        names = [f"{arm}_ps{p}" for p in PS]; ps = [P.cache_path(n) for n in names]
        if not all(p.is_file() for p in ps):
            print(f"  {arm:20s} SKIP — missing {[p.name for p in ps if not p.is_file()]}"); continue
        assert len(set(ps)) == len(PS), f"[GATE1 FAIL] {arm}: duplicate cache paths"
        C = [P.load_cache(n) for n in names]
        common = P.in_window(set.intersection(*[set(c) for c in C]))
        assert len(common) >= 100, f"[GATE3 FAIL] {arm}: only {len(common)} common refit dates"
        per = {ij: [] for ij in pairs}
        for d in common:
            u = [list(c[d]["universe"]) for c in C]
            if any(x != u[0] for x in u[1:]):
                continue
            l = [np.asarray(c[d]["labels"]) for c in C]
            assert not all(np.array_equal(l[0], x) for x in l[1:]), f"[GATE2 FAIL] {arm} {d}: identical label vectors"
            for i, j in pairs:
                per[(i, j)].append(adjusted_rand_score(l[i], l[j]))
        n = len(per[pairs[0]]); assert n >= 100, f"[GATE3 FAIL] {arm}: only {n} days with matching universes"
        m = {f"ARI_ps{PS[i]}_ps{PS[j]}": float(np.mean(v)) for (i, j), v in per.items()}
        allp = np.concatenate([np.asarray(v) for v in per.values()])
        rows.append(dict(arm=arm, days=n, source="tier2" if arm in TIER2 else "partitions_v3", **m,
                         ARI_mean=float(allp.mean()), ARI_pair_min=float(min(m.values())), ARI_pair_max=float(max(m.values()))))
        print(f"  {arm:20s} n={n:5d}  mean ARI {allp.mean():.4f}  pair band {min(m.values()):.4f}–{max(m.values()):.4f}", flush=True)
    df = pd.DataFrame(rows)
    r = df[df.arm != "random"]
    print(f"within-rule ARI, mean over the nine rule arms {r.ARI_mean.mean():.4f} (band {r.ARI_mean.min():.4f}–{r.ARI_mean.max():.4f}); random {float(df[df.arm == 'random'].ARI_mean.iloc[0]):.4f}")
    compare_and_write(df, "ari_within_rule_v3_cal6913.csv", ["arm"])


if __name__ == "__main__":
    main()
