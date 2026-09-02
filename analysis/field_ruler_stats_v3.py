"""The §5.1 ruler: pooled within-configuration seed dispersion and the adjacent-gap counts.

Reproduces, and recomputes for any seed set, the four printed quantities of §5.1 and
fig:field_ruler: the pooled standard deviation of a configuration's Sharpe ratio across its
training runs (12 clusterizers, df = 12*(S-1)), its 95% chi-square interval, the 11 gaps between
adjacent clusterizer means, and how many of those gaps fall below the ruler at the interval's lower
end, at the point estimate and at the upper end. Controls (K=1, random) are excluded from the pool
and from the gaps, as in the paper.

    python analysis/field_ruler_stats_v3.py --seeds 42 1 123          # must reproduce 0.0844 / 24 df / [0.066, 0.117] / 5-7-10
    python analysis/field_ruler_stats_v3.py --seeds 42 1 123 2 3 --compare 42 1 123
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import chi2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books

CLUSTERIZERS = [a for a in paths.ARMS if a not in ("k1", "random")]


def ruler(seeds: tuple[int, ...]) -> dict:
    S = len(seeds)
    per = {a: np.array([books.sharpe(books.head_book(a, s)) for s in seeds]) for a in CLUSTERIZERS}
    for a in CLUSTERIZERS:
        bad = [s for s in seeds if not books.gate_ok(a, s)]
        assert not bad, f"{a}: seeds {bad} fail the validity gate"
    var = np.mean([v.var(ddof=1) for v in per.values()])          # pooled within-configuration variance
    df = len(CLUSTERIZERS) * (S - 1)
    sd = float(np.sqrt(var))
    lo = float(np.sqrt(var * df / chi2.ppf(0.975, df)))            # chi-square interval for a sd
    hi = float(np.sqrt(var * df / chi2.ppf(0.025, df)))
    means = pd.Series({a: v.mean() for a, v in per.items()}).sort_values(ascending=False)
    gaps = means.values[:-1] - means.values[1:]
    return dict(seeds=seeds, sd=sd, df=df, lo=lo, hi=hi, means=means, gaps=gaps,
                n_lo=int((gaps < lo).sum()), n_pt=int((gaps < sd).sum()), n_hi=int((gaps < hi).sum()),
                span=(float(means.min()), float(means.max())),
                pairs=[(means.index[i], means.index[i + 1], float(gaps[i])) for i in range(len(gaps))])


def show(r: dict, label: str) -> None:
    print(f"\n=== {label}: seeds {r['seeds']}")
    print(f"pooled within-configuration sd {r['sd']:.4f} on {r['df']} df, 95% CI [{r['lo']:.3f}, {r['hi']:.3f}]")
    print(f"gaps below the ruler: {r['n_lo']} of 11 at the lower end, {r['n_pt']} at the point estimate, {r['n_hi']} at the upper end")
    print(f"12 means span {r['span'][0]:.3f} to {r['span'][1]:.3f}")
    for a, b, g in r["pairs"]:
        print(f"   {a:>18s} -> {b:<18s} {g:.4f} {'<' if g < r['sd'] else '>'} ruler")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", nargs="+", type=int, default=list(paths.SEEDS))
    ap.add_argument("--compare", nargs="*", type=int, default=None)
    a = ap.parse_args()
    new = ruler(tuple(a.seeds)); show(new, "new")
    if a.compare:
        base = ruler(tuple(a.compare)); show(base, "baseline")
        print(f"\nruler {base['sd']:.4f} -> {new['sd']:.4f}; counts (lo/pt/hi) {base['n_lo']}/{base['n_pt']}/{base['n_hi']}"
              f" -> {new['n_lo']}/{new['n_pt']}/{new['n_hi']}")
        d = pd.DataFrame({"pair": [f"{x}>{y}" for x, y, _ in base["pairs"]],
                          "gap_base": [g for *_, g in base["pairs"]], "gap_new": [g for *_, g in new["pairs"]]})
        print(d.assign(delta=lambda z: z.gap_new - z.gap_base).round(4).to_string(index=False))


if __name__ == "__main__":
    main()
