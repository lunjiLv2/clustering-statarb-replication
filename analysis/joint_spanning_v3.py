"""Joint spanning: FF5+MOM+ST_Rev plus the five rolling PCs, one regression per book (§1 claim check).

Requested by the prose branch on 2026-08-30 for the introduction's "controlling for the standard
factors, a short-term reversal factor, and the leading principal components" — read as one joint
specification. Factors: Ken French FF5+MOM+ST_Rev (rule books at shift 0, seed-averaged trained
books at shift 1) and the five trailing-252-day sign-aligned PCs of N81 (rule at shift -1, head at
0). Alpha in percent per year, Newey-West t at 21 lags. Output:
analysis/results/joint_spanning_ff6rev5pc_cal6913.csv. Result on the shipped books: every one of
the 28 books keeps a significant alpha; min |t| = 2.56 (rule K=1), clusterizer rules t 5.4-6.7,
trained books t 8.4-10.4 (CORRECTIONS N82).

Run: ``python analysis/joint_spanning_v3.py``
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

PCS = ["PC1", "PC2", "PC3", "PC4", "PC5"]


def main() -> None:
    ff = load_ff(with_reversal=True)[FF6 + ["ST_Rev"]]
    pc = pd.read_csv(paths.RESULTS / "pc_factors_v3_cal6913.csv", parse_dates=["Date"]).set_index("Date")[PCS]
    rows = []
    for comp, loader, ffs, pcs in (("rule", books.rule_book, 0, -1), ("head", books.head_avg, 1, 0)):
        for a in paths.ARMS:
            y = loader(a)
            m = pd.concat([y.rename("y"), ff.shift(ffs), pc.shift(pcs)], axis=1).reindex(y.index).dropna()
            b, t, r2 = nw_ols(m.y.to_numpy(), m[FF6 + ["ST_Rev"] + PCS].to_numpy())
            rows.append(dict(component=comp, arm=a, days=len(m), alpha=alpha_pct(b), t_alpha=float(t[0]), R2=r2))
    compare_and_write(pd.DataFrame(rows), "joint_spanning_ff6rev5pc_cal6913.csv", ["component", "arm"])


if __name__ == "__main__":
    main()
