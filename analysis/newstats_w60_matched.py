"""The formal-inference battery on the matched common-window field (tab:formal).

SET_W60 is the twelve clusterizers of the headline table at a common 60-day window (the bare names
of the k-means, PCA, agglomerative, spectral and GICS arms already are the 60-day versions; the
signed-spectral and the four trading-driven arms enter as their ``_w60`` twins; the SSSNET arm is the
fixed-partition arm ``sssnetpre``, written as ``sssnet_w60`` in every output). ``bootstrap`` is the
audited Ledoit–Wolf loop unchanged: for the sample and for every circular-block resample it returns
the annualized Sharpe ratios, the pairwise Sharpe differences in LW's moment form and their HAC
standard errors. ``analysis/formal_v3.py`` is the entry point.
"""
from __future__ import annotations
import sys, time
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import newstats_lib as L

SET_W60 = ["kmeans_ret", "fv3sm_w60", "agglo_avg", "agglo_complete", "sssnet_w60", "pca_load",
           "sortino_w60", "sharpe_fixed_w60", "sponge_w60", "fv2a_w60", "gics", "spectral_unsigned"]
FILE_ARM = {"sssnet_w60": "sssnetpre"}
"""Output name -> head-log arm name (the fixed-partition SSSNET arm, option B)."""


def build_matrix(valid: list[dict], arms: list[str] = SET_W60) -> pd.DataFrame:
    """Seed-averaged payoffs of ``arms`` (output names), one column per arm, on the union of the run
    frames; the caller intersects/reindexes to the common calendar."""
    X = L.seed_averaged(valid, [FILE_ARM.get(a, a) for a in arms])
    X.columns = arms
    return X


def pair_index(n: int) -> np.ndarray:
    return np.array([(i, j) for i in range(n) for j in range(i + 1, n)], dtype=int)


def bootstrap(X: np.ndarray, arms: list[str], B: int, block: int, seed: int,
              idx: np.ndarray | None = None, ann: float = L.SQ):
    """Sample (row 0) and B circular-block-bootstrap replicates of: annualized Sharpe ratios (B+1 x n),
    Ledoit–Wolf pairwise Sharpe differences and their HAC standard errors (B+1 x n(n-1)/2).

    ``idx`` (B x T) overrides the resampling indices (formal_v3 passes the block-aggregated
    variant); ``ann`` is the annualization factor of the Sharpe ratio (sqrt(252) for daily payoffs).
    """
    T, n = X.shape
    P = pair_index(n)
    cols = np.stack([P[:, 0], P[:, 1], n + P[:, 0], n + P[:, 1]], axis=1)
    if idx is None:
        idx = L.cbb_indices(T, block, B, seed)
    sr_boot = np.empty((B + 1, n))
    delta = np.empty((B + 1, len(P)))
    se = np.empty((B + 1, len(P)))
    sstar_max, t0 = 0.0, time.time()
    for b in range(B + 1):
        Y = X if b == 0 else X[idx[b - 1]]
        sr_boot[b] = ann * Y.mean(0) / Y.std(0, ddof=1)
        mu, gam = L.sharpe_moment_parts(Y)
        V = np.concatenate([Y - mu, Y ** 2 - gam], axis=1)
        rho, sig = L.alpha_hat_cols(V)
        S_star = L.andrews_bandwidth(rho, sig, T)
        sstar_max = max(sstar_max, S_star)
        psi = L.psi_hat(V, S_star)
        g = L.lw_gradient(mu[P[:, 0]], gam[P[:, 0]], mu[P[:, 1]], gam[P[:, 1]])
        delta[b] = L.sr_from_moments(mu[P[:, 0]], gam[P[:, 0]]) - \
            L.sr_from_moments(mu[P[:, 1]], gam[P[:, 1]])
        sub = psi[np.ix_(cols.ravel(), cols.ravel())].reshape(len(P), 4, len(P), 4)
        sub = np.einsum("ijik->ijk", sub)
        se[b] = np.sqrt(np.maximum(np.einsum("ij,ijk,ik->i", g, sub, g), 0.0) / T)
        if b % 1000 == 0:
            print(f"  draw {b}/{B}  elapsed {time.time()-t0:6.1f}s", flush=True)
    return sr_boot, delta, se, P, sstar_max
