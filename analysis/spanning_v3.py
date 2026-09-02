"""Time-series spanning of the 28 books on FF5+MOM, full sample and by era (tab:spanning, tab:signal,
tab:head_adds, tab:era, §6.2).

For each arm the rule-based book (factors at shift 0) and the seed-averaged trained book (factors at
shift 1) are regressed on a constant and the six factors; alpha is reported in percent per year with a
Newey–West t-statistic at 21 lags, together with R², the annualized volatility and the Sharpe ratio.
Eras split at 1 January 2009. Output: analysis/results/rule_spanning_era_v3_cal6913.csv (the arm
'sssnetpre' is written under the legacy name 'sssnet_w60' so that downstream readers agree).

Run: ``python analysis/spanning_v3.py``
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books
from analysis.factors import FF6, load_ff, nw_ols, alpha_pct

LEGACY = {"sssnetpre": "sssnet_w60"}          # column name used by the tables and the harness
ERAS = {"full": lambda i: np.ones(len(i), bool), "1997-2008": lambda i: np.asarray(i < "2009-01-01"), "2009-2024": lambda i: np.asarray(i >= "2009-01-01")}


def main() -> None:
    ff = load_ff()[FF6]; rows = []
    for component, loader, shift in (("rule", books.rule_book, 0), ("head", books.head_avg, 1)):
        M = pd.concat({a: loader(a) for a in paths.ARMS}, axis=1).join(ff.shift(shift), how="inner").reindex(books.IDX)
        assert M.notna().all().all(), f"{component}: NaN after the factor join"
        X = M[FF6].to_numpy(float)
        for era, mask in ERAS.items():
            m = mask(M.index); Xe = X[m]
            for a in paths.ARMS:
                y = M[a].to_numpy(float)[m]; b, t, r2 = nw_ols(y, Xe)
                rows.append(dict(component=component, era=era, arm=LEGACY.get(a, a), alpha=alpha_pct(b), t=float(t[0]), R2=r2,
                                 vol=100 * np.sqrt(252) * y.std(ddof=1), SR=np.sqrt(252) * y.mean() / y.std(ddof=1)))
    out = pd.DataFrame(rows); ref = pd.read_csv(paths.RESULTS / "rule_spanning_era_v3_cal6913.csv")
    m = out.merge(ref, on=["component", "era", "arm"], suffixes=("", "_ref"))
    print(f"{len(out)} rows; max |alpha diff| vs shipped CSV {np.abs(m.alpha - m.alpha_ref).max():.2e}, max |t diff| {np.abs(m.t - m.t_ref).max():.2e}")
    out.to_csv(paths.RESULTS / "rule_spanning_era_v3_cal6913.csv", index=False)


if __name__ == "__main__":
    main()
