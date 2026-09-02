"""Trailing-winner selection rules against the equal-weight book: point Sharpe gap and a
circular-block-bootstrap 95% interval (§4.2 selection discussion, companion to fig_select_vs_ew).

Construction: seed-averaged trained books of the 12 clusterizers on the common calendar; at each
calendar-year boundary the rule reselects the arm with the highest Sharpe over the trailing
1/3/5 years, provided at least 252 days of history exist (the condition '>= 252'; the earlier
'> 252' never fired for the one-year rule and is reported as 'strict_bug_*' for the record). The
interval is a block bootstrap of the Sharpe gap, block 21, 5,000 draws under each of three master
seeds, averaged.

Output: analysis/results/select_ci_v3_cal6913.csv.  Run: ``python analysis/select_ci_v3.py``
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books
from analysis._compare import compare_and_write

CLUSTERIZERS = [a for a in paths.ARMS if a not in ("k1", "random")]
BLOCK, DRAWS, MASTERS = 21, 5000, (0, 1, 2)


def sharpe(v: np.ndarray) -> float:
    return float(np.sqrt(252) * v.mean() / v.std(ddof=1))


def selection(X: np.ndarray, years: np.ndarray, look: int, strict: bool = False):
    """Payoff of the trailing-`look`-year winner rule and the number of reselections."""
    T = X.shape[1]; w = np.zeros(T, dtype=int); cur = n = 0
    for t in range(T):
        if t and years[t] != years[t - 1]:
            s = max(0, t - look * 252)
            if (t - s > 252) if strict else (t - s >= 252):
                cur = int(np.argmax([sharpe(X[i][s:t]) for i in range(X.shape[0])])); n += 1
        w[t] = cur
    return X[w, np.arange(T)], n


def main() -> None:
    X = np.stack([books.head_avg(a).to_numpy(float) for a in CLUSTERIZERS]); T = X.shape[1]
    ew = X.mean(0); years = np.asarray(books.IDX.year); rows = []
    for look in (1, 3, 5):
        v, n = selection(X, years, look); gap = sharpe(v) - sharpe(ew); lo = hi = 0.0
        for master in MASTERS:
            rng = np.random.default_rng(1000 + master); nb = int(np.ceil(T / BLOCK)); g = []
            for _ in range(DRAWS):
                st = rng.integers(0, T - BLOCK + 1, size=nb); ix = (st[:, None] + np.arange(BLOCK)[None, :]).ravel()[:T]
                g.append(sharpe(v[ix]) - sharpe(ew[ix]))
            a_, b_ = np.percentile(g, [2.5, 97.5]); lo += a_ / len(MASTERS); hi += b_ / len(MASTERS)
        vs, ns = selection(X, years, look, strict=True)
        rows.append(dict(look=look, reselections=n, SR_rule=sharpe(v), SR_ew=sharpe(ew), gap=gap, ci_lo=lo, ci_hi=hi,
                         covers_zero=(lo < 0 < hi), strict_bug_SR=sharpe(vs), strict_bug_reselections=ns))
        print(rows[-1], flush=True)
    compare_and_write(pd.DataFrame(rows), "select_ci_v3_cal6913.csv", ["look"])


if __name__ == "__main__":
    main()
