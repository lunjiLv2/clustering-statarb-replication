"""Each arm's book regressed on the K=1 book of the same trading component (tab:k1span, §6.2).

The K=1 book shares the universe, the signal window and the trading component and differs only in
the grouping, so its alpha measures what the partition adds (within-group relative value). For
every arm and both components the book is regressed on the K=1 book alone and on the K=1 book plus
FF5+MOM (factors at shift 0 for the rule book, shift 1 for the seed-averaged trained book, as in
strev_spanning_v3.py); alphas in percent per year, Newey–West t at 21 lags, common calendar.

Output: analysis/results/k1_regressor_v3_cal6913.csv (component, arm, alpha_on_k1, t_on_k1, beta_k1,
R2_k1, alpha_on_k1_ff6, t_on_k1_ff6, beta_k1_ff6, R2_k1_ff6).

Run: ``python analysis/k1_regressor_v3.py``
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books
from analysis.factors import FF6, load_ff, nw_ols, alpha_pct
from analysis._compare import compare_and_write


def main() -> None:
    ff = load_ff(with_reversal=False)[FF6]
    rows = []
    for comp, loader, shift in (("rule", books.rule_book, 0), ("head", books.head_avg, 1)):
        M = pd.concat({a: loader(a) for a in paths.ARMS}, axis=1).join(ff.shift(shift), how="inner").reindex(books.IDX)
        assert M.notna().all().all(), f"{comp}: NaN after the factor join"
        k1 = M["k1"].to_numpy(float); X6 = M[FF6].to_numpy(float)
        for a in paths.ARMS:
            if a == "k1":
                continue
            y = M[a].to_numpy(float)
            b1, t1, r1 = nw_ols(y, k1[:, None]); b6, t6, r6 = nw_ols(y, np.column_stack([k1, X6]))
            rows.append(dict(component=comp, arm=a, alpha_on_k1=alpha_pct(b1), t_on_k1=float(t1[0]), beta_k1=float(b1[1]), R2_k1=r1,
                             alpha_on_k1_ff6=alpha_pct(b6), t_on_k1_ff6=float(t6[0]), beta_k1_ff6=float(b6[1]), R2_k1_ff6=r6))
    out = pd.DataFrame(rows)
    compare_and_write(out, "k1_regressor_v3_cal6913.csv", ["component", "arm"])
    pd.set_option("display.width", 200)
    print(out.round(3).to_string(index=False))
    cl = out[~out.arm.isin(["random"])]
    for comp in ("rule", "head"):
        c = cl[cl.component == comp]; r = out[(out.component == comp) & (out.arm == "random")].iloc[0]
        print(f"{comp}: 12 clusterizers alpha {c.alpha_on_k1.min():.2f}-{c.alpha_on_k1.max():.2f}  t {c.t_on_k1.min():.1f}-{c.t_on_k1.max():.1f}"
              f"  beta {c.beta_k1.min():.2f}-{c.beta_k1.max():.2f}  R2 {c.R2_k1.min():.2f}-{c.R2_k1.max():.2f}"
              f"  +FF6 alpha {c.alpha_on_k1_ff6.min():.2f}-{c.alpha_on_k1_ff6.max():.2f}  t {c.t_on_k1_ff6.min():.1f}-{c.t_on_k1_ff6.max():.1f}"
              f"  | random {r.alpha_on_k1:.2f} ({r.t_on_k1:.1f}) beta {r.beta_k1:.2f} R2 {r.R2_k1:.2f} +FF6 {r.alpha_on_k1_ff6:.2f} ({r.t_on_k1_ff6:.1f})")


if __name__ == "__main__":
    main()
