"""Serial dependence of the 28 books and its relation to the Monte Carlo size (A.10).

For every book (seed-averaged trained books with factors at shift 1; rule-based books at shift 0) the
score-test residual u of the no-intercept regression on FF5+MOM is formed, and the autocorrelations of
u at lags 1..21, their sum and mean absolute value, and the NW(21) variance inflation factor
lrv(u) / var(u) are reported. The measured size of the Wald test, averaged over the four master seeds
of the Monte Carlo study (analysis/results/mc_size_v3_B5000_s*.csv), is merged in so the mechanism —
does inflation predict size across books? — can be tested.

Output: analysis/results/serial_dep_v3.csv (short arm labels: books.SHORT_NAME).

Note: the ``size`` column of the file shipped with the audit averaged five Monte Carlo files, including
the pre-common-calendar run ``mc_size_v3_B5000.csv``; this script averages the four common-calendar
seeds only, so ``size`` differs from that file by up to 0.0015. No printed number uses this column
(the paper quotes the size from the Monte Carlo files directly and ``acf_sum_1_21`` from here); the
ACF and inflation columns reproduce to 1e-15.

Run: ``python analysis/serial_dep_v3.py`` (after analysis/mc_size_v3.py for the four seeds)
"""
from __future__ import annotations
import os, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books
from analysis.factors import FF6, load_ff, lrv, lm_score

MC_SEEDS = (42, 7, 101, 2024)


def main() -> None:
    ff = load_ff()[FF6]; rows = []
    short = {books.SHORT_NAME.get(a, a): a for a in paths.ARMS}
    for layer, loader, shift in (("trained", books.head_avg, 1), ("rule", books.rule_book, 0)):
        for arm, full in sorted(short.items()):
            j = pd.concat([loader(full).rename("y"), ff.shift(shift)], axis=1).dropna()
            y = j["y"].to_numpy(float); Fm = j[FF6].to_numpy(float); T = len(y)
            _, u = lm_score(y, Fm); uc = u - u.mean()
            acf = [float(np.corrcoef(uc[:-l], uc[l:])[0, 1]) for l in range(1, 22)]
            rows.append(dict(layer=layer, arm=arm, days=T, inflation=lrv(u) / (float(uc @ uc) / T),
                             acf1=acf[0], acf5=acf[4], acf21=acf[20], acf_absmean_1_21=float(np.mean(np.abs(acf))),
                             acf_sum_1_21=float(np.sum(acf))))
    D = pd.DataFrame(rows)
    mc = pd.concat([pd.read_csv(paths.RESULTS / f"mc_size_v3_B5000_s{s}.csv") for s in MC_SEEDS])
    D = D.merge(mc.groupby(["layer", "arm"]).size_waldt.mean().rename("size"), left_on=["layer", "arm"], right_index=True)
    for k in ("inflation", "acf1", "acf_sum_1_21", "size"):
        t, r = D[D.layer == "trained"].set_index("arm")[k], D[D.layer == "rule"].set_index("arm")[k]
        print(f"  {k:14s} trained {t.mean():.4f}  rule {r.mean():.4f}  paired diff {(t - r).mean():+.4f}  same sign {(t - r > 0).sum()}/{len(t)}")
    pr, pp = stats.pearsonr(D.inflation, D["size"]); print(f"  inflation vs size across 28 books: Pearson {pr:+.4f} (p={pp:.4f})")
    name = "serial_dep_v3.csv"; ref = pd.read_csv(paths.RESULTS / name)
    j = D.merge(ref, on=["layer", "arm"], suffixes=("", "_ref"))
    num = [c for c in ref.columns if c not in ("layer", "arm") and ref[c].dtype.kind == "f"]
    d = max(np.abs(j[c] - j[c + "_ref"]).max() for c in num)
    print(f"{name}: {len(j)}/{len(ref)} rows matched on [layer, arm]; max |diff| {d:.2e}")
    force = os.environ.get("CSA_FORCE_WRITE") == "1" and paths.RESULTS.resolve() != paths.SHIPPED_RESULTS.resolve()
    if d < 1e-6 or "--accept" in sys.argv or force:   # --accept: 4-seed definition adopted 2026-08-30 (CORRECTIONS N81 addendum 2); force: side directory only, as in _compare.py
        D.to_csv(paths.RESULTS / name, index=False)
        if force and d >= 1e-6: print("  -> written (forced, side directory)")
    else:
        print("NOT written: the shipped file is not reproduced")


if __name__ == "__main__":
    main()
