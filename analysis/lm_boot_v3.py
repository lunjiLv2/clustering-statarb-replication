"""Null-imposed moving-block bootstrap p-values of the score (LM) intercept test, 28 books on the common
calendar (diagnostic; the LM columns were withdrawn from tab:spanning, CORRECTIONS N78 addendum 8, and the
harness keeps this file only as a check that the bootstrap p-values are at most 0.001).

Statistic: for book y on FF5+MOM (rule books at factor shift 0, seed-averaged trained books at shift 1),
beta from OLS without a constant, LM = T * mean(eps)^2 / LRV_21(u) with u = eps * (1 - x'Q^-1 mu) and a
Newey–West (Bartlett, 21 lags) long-run variance. Null imposed by re-centering the residuals: pseudo
series y* = X* beta + e0* with e0 = eps - mean(eps), built from 2,000 moving-block resamples of 21-day
blocks (start points uniform on {0..T-21}, one index matrix per component, seed 42); p = (#{LM* >= LM} + 1)/(B + 1).

Output: analysis/results/lm_boot_v3_cal6913_s{seed}.csv (component, arm, LM, p_boot, p_boot_raw).
Run: ``python analysis/lm_boot_v3.py [--seed 42]``  (~3 min)
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books
from analysis.factors import FF6, load_ff, lrv
from analysis._compare import compare_and_write

ARMS = ["kmeans_ret", "pca_load", "agglo_avg", "agglo_complete", "spectral_unsigned", "gics", "sponge_w60", "fv2a_w60",
        "fv3sm_w60", "sharpe_fixed_w60", "sortino_w60", "sssnetpre", "k1", "random"]
B, BL = 2000, 21


def arlm(y: np.ndarray, X: np.ndarray):
    """LM statistic of a zero intercept (regression without constant), the residuals and beta."""
    T = len(y); beta = np.linalg.solve(X.T @ X, X.T @ y); eps = y - X @ beta
    QF = (X.T @ X) / T; mu = X.mean(axis=0)
    u = eps * (1.0 - X @ np.linalg.solve(QF, mu))
    return T * eps.mean() ** 2 / lrv(u), eps, beta


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--seed", type=int, default=42); a = ap.parse_args()
    ff = load_ff(with_reversal=False)[FF6]; rows = []
    for comp, loader, sh in (("rule", books.rule_book, 0), ("head", books.head_avg, 1)):
        M = pd.concat({x: loader(x) for x in ARMS}, axis=1).join(ff.shift(sh), how="inner").dropna().reindex(books.IDX)
        assert not M.isna().any().any(), f"{comp}: NaN after the factor join"
        X = M[FF6].to_numpy(float); T = len(M); nb = int(np.ceil(T / BL))
        rng = np.random.default_rng(a.seed)
        starts = rng.integers(0, T - BL + 1, size=(B, nb))
        for arm in ARMS:
            y = M[arm].to_numpy(float); LM0, eps, beta = arlm(y, X)
            e0 = eps - eps.mean(); cnt = 0
            for b in range(B):
                ix = (starts[b][:, None] + np.arange(BL)[None, :]).ravel()[:T]
                LMb, _, _ = arlm(X[ix] @ beta + e0[ix], X[ix])
                cnt += LMb >= LM0
            rows.append(dict(component=comp, arm=arm, LM=LM0, p_boot=(cnt + 1) / (B + 1), p_boot_raw=cnt / B))
            print(f"  {comp:4s} {arm:18s} LM {LM0:7.2f}  p_boot {rows[-1]['p_boot']:.4f}", flush=True)
    compare_and_write(pd.DataFrame(rows), f"lm_boot_v3_cal6913_s{a.seed}.csv", ["component", "arm"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
