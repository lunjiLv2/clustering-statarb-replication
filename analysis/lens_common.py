"""Shared pieces of the factor-lens producers (verify_lens, lens_extras_v3, peer_lens_v3_cal6913).

The lens works on each partition's own universe (the names the partition snapshot lists), not on the
traded universe: for a day ``d`` it takes the cross-section of SPY-CAPM residuals (rolling 60-day beta,
no validity mask — the lens requires a complete 252-day history instead) and asks what share of its
variance demeaning within groups removes, before and after projecting out a benchmark span.

* ``load_residuals(columns=None, with_mask=False)``: the residual panel; ``columns`` restricts the
  panel to a subset (residuals are per-name, so the subset is exact — the peer lens needs it to fit
  in memory) and ``with_mask`` applies the validity mask (the peer lens does, the other two do not).
* ``r2_loop`` / ``r2_bincount``: the removal share in the two arithmetically equivalent forms the
  producers use; kept separate so that each shipped file is reproduced bit for bit.
* ``cache_path`` / ``load_cache``: partition caches under ``data/derived/partitions``.
"""
from __future__ import annotations
import pickle, sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths

BETA_W, W = 60, 252
LEGACY_FILE = {"sssnet_w60": "sssnetpre"}
SHARPE_ORDER = ["kmeans_ret", "sssnet_w60", "agglo_complete", "fv3sm_w60", "sponge_w60", "pca_load", "agglo_avg",
                "sortino_w60", "fv2a_w60", "sharpe_fixed_w60", "gics", "spectral_unsigned", "k1", "random"]
"""The twelve clusterizers in the manuscript's Sharpe order, then the two controls (row order of the CSVs)."""


def load_residuals(columns=None, with_mask: bool = False, keep_prices: bool = False):
    """SPY-CAPM residuals of the compat panel (DataFrame); optionally also raw returns and prices."""
    assert paths.PANEL is not None, "set CSA_PANEL_ROOT to the compat panel (prices/caps/mask.pkl)"
    px = pd.read_pickle(paths.PANEL / "prices.pkl")
    if columns is not None:
        px = px[[c for c in px.columns if c in columns or c == "SPY"]].copy()
    raw = px.pct_change(fill_method=None); mkt = raw["SPY"]
    res = raw - (raw.rolling(BETA_W).cov(mkt).div(mkt.rolling(BETA_W).var(), axis=0)).multiply(mkt, axis=0)
    if with_mask:
        mk = pd.read_pickle(paths.PANEL / "mask.pkl")[list(px.columns)]
        res = res.where(mk.reindex_like(raw).astype(bool))
    return (res, raw, px) if keep_prices else res


def cache_path(arm: str) -> Path:
    return paths.PARTITIONS / f"{LEGACY_FILE.get(arm, arm)}.pkl"


def load_cache(arm: str) -> dict:
    with open(cache_path(arm), "rb") as f:
        return pickle.load(f)


def r2_loop(x: np.ndarray, lab: np.ndarray) -> float:
    """Removal share, demeaning group by group (verify_lens form)."""
    x = x - x.mean(); tot = (x ** 2).sum()
    if tot <= 0: return np.nan
    r = x.copy()
    for k in np.unique(lab):
        m = lab == k
        if m.sum() > 0: r[m] -= x[m].mean()
    return 1.0 - (r ** 2).sum() / tot


def ss_within(x: np.ndarray, lab: np.ndarray) -> float:
    """Within-group sum of squares by bincount."""
    _, inv = np.unique(lab, return_inverse=True)
    n = np.bincount(inv).astype(float); s = np.bincount(inv, weights=x)
    return float((x * x).sum() - (s * s / n).sum())


def r2_bincount(x: np.ndarray, lab: np.ndarray) -> float:
    """Removal share in the bincount form (lens_extras / peer_lens)."""
    x = x - x.mean(); tot = float((x * x).sum())
    return 1.0 - ss_within(x, lab) / tot if tot > 0 else np.nan
