"""A.11's empirical size and size-corrected critical value, per book.

mc_size_v3 reports the size of the Wald-t test but discards the simulated null, so the corrected
critical value cannot be read from its output. This rebuilds the same null -- y* = F b + e*, e* a
centred 21-day circular block resample of the OLS residual, B draws -- and keeps the draws, so it
can report both the size and the 95th percentile of |t| (the corrected critical value, since the
test rejects on |t| at a nominal 5%).

CONVENTION, pinned 2026-09-01 by reproducing the printed three-seed values from the four shipped
mc_size_v3_B5000_s{42,7,101,2024}.csv: a book's size is the MEAN over the four master seeds (i.e.
20,000 draws per book), the printed range is the min/max of that over the 28 books, and "pooled" is
the mean over books. 3seed-ok: the sentence below describes the SHIPPED three-seed calibration
files, which is how the convention was pinned. Under that convention they give 5.40%-7.76% book by
book and 6.455% pooled -- the printed 5.4%-7.8% and 6.5%. Per-master-seed ranges are wider
(5.12%-7.94%) and reproduce nothing printed, so do not combine them that way.

    python analysis/size_critical_v3.py --B 5000 --seed 42 --out analysis/results/size_crit_s42.csv

Run once per master seed, then combine with --combine (reads the per-seed CSVs, applies the
convention above, prints the three numbers A.11 quotes).
"""
from __future__ import annotations
import argparse, sys, glob
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books
from analysis.factors import FF6, load_ff, nw_ols
import analysis.newstats_lib as L


def combine(pattern: str) -> int:
    fs = sorted(glob.glob(pattern))
    if not fs:
        raise SystemExit(f"[FATAL] --combine matched no files: {pattern}")
    d = None
    for f in fs:
        v = pd.read_csv(f).set_index(["layer", "arm"])
        s = v[["size"]].rename(columns={"size": f"size_{Path(f).stem[-4:]}"})
        c = v[["crit95"]].rename(columns={"crit95": f"crit_{Path(f).stem[-4:]}"})
        d = s.join(c) if d is None else d.join(s).join(c)
    size = d[[c for c in d.columns if c.startswith("size_")]].mean(axis=1)
    crit = d[[c for c in d.columns if c.startswith("crit_")]].mean(axis=1)
    worst = size.idxmax()
    print(f"combined {len(fs)} master seeds over {len(size)} books")
    print(f"  pooled size            {100 * size.mean():.3f}%  -> {100 * size.mean():.1f}%")
    print(f"  book by book           {100 * size.min():.2f}% - {100 * size.max():.2f}%"
          f"  -> {100 * size.min():.1f}% to {100 * size.max():.1f}%")
    print(f"  worst-behaved book     {worst[0]} {worst[1]}  size {100 * size.loc[worst]:.2f}%")
    print(f"  corrected critical val 1.96 -> {crit.loc[worst]:.3f}  -> {crit.loc[worst]:.1f}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--B", type=int, default=5000); ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=""); ap.add_argument("--combine", default="")
    a = ap.parse_args()
    if a.combine:
        return combine(a.combine)
    ff = load_ff()[FF6]
    short = {books.SHORT_NAME.get(x, x): x for x in paths.ARMS}
    allb = [("trained", s, books.head_avg(x), 1) for s, x in sorted(short.items())] \
         + [("rule", s, books.rule_book(x), 0) for s, x in sorted(short.items())]
    rows = []
    for layer, arm, ser, shift in allb:
        m = pd.concat([ser.rename("y"), ff.shift(shift)], axis=1).reindex(books.IDX).dropna()
        y = m.y.to_numpy(float); Fm = m[FF6].to_numpy(float); T = len(y)
        beta = np.linalg.solve(Fm.T @ Fm, Fm.T @ y); eps = y - Fm @ beta; eps -= eps.mean()
        idx = L.cbb_indices(T, 21, a.B, a.seed)
        ts = np.array([abs(float(nw_ols(Fm @ beta + eps[i], Fm)[1][0])) for i in idx])
        rows.append(dict(layer=layer, arm=arm, days=T, size=float((ts > 1.96).mean()),
                         crit95=float(np.quantile(ts, 0.95))))
        print(f"  {layer:7s} {arm:18s} size {rows[-1]['size']:.4f}  crit95 {rows[-1]['crit95']:.3f}", flush=True)
    d = pd.DataFrame(rows)
    print(f"seeds {tuple(paths.SEEDS)}  master seed {a.seed}  B={a.B}")
    print(f"  pooled {d['size'].mean():.4f} | per book {d['size'].min():.4f}-{d['size'].max():.4f}")
    if a.out:
        d.to_csv(a.out, index=False); print(f"  -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
