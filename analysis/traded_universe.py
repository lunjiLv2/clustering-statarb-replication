"""The traded universe of the rule-based book, day by day, and the label fill used by the engine.

Three producers (vshare_v3, vshare_v3_nosingleton, dose_v3_traded) measure partition quality on the
names the rule-based book actually trades. This module holds the shared machinery, verbatim from the
audited producers, so that the three scripts differ only in what they do with a day's labels:

* ``load_panel``: SPY-CAPM residuals with a rolling 60-day beta, masked by the validity mask, plus the
  raw payoff returns and the lagged capitalisations (the compat panel at ``CSA_PANEL_ROOT``).
* ``day_universe``: on day ``i`` the top-500 names by yesterday's capitalisation that have a complete
  5-day signal window, a complete 21-day correlation window and a finite next-day return; at least 50.
* ``fill_labels``: the partition's labels on those names; a name the (up to 10-day-old) partition does
  not cover joins the group whose members are most correlated with it over the 21-day window.
* ``r2``: the share of a cross-section's variance removed by demeaning within groups.

Constants (K = 30, beta window 60, signal window 5, correlation window 21, maximum partition age 10
days) are the rule engine's (``rule_engine/p1_inversion/p1_lib.py``).
"""
from __future__ import annotations
import bisect, pickle, sys
from pathlib import Path
from types import SimpleNamespace
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths

K, BETA_W, SIG_W, CORR_W, MAX_AGE = 30, 60, 5, 21, 10
LEGACY_FILE = {"sssnet_w60": "sssnetpre"}
"""Arm name used by the result CSVs -> partition-cache name (option B: the fixed SSSNET partition)."""


def load_panel() -> SimpleNamespace:
    """Residuals, payoff returns and capitalisations of the compat panel as contiguous arrays."""
    assert paths.PANEL is not None, "set CSA_PANEL_ROOT to the compat panel (prices/caps/mask.pkl)"
    px = pd.read_pickle(paths.PANEL / "prices.pkl"); caps = pd.read_pickle(paths.PANEL / "caps.pkl")
    mask = pd.read_pickle(paths.PANEL / "mask.pkl").astype(bool)
    raw = px.pct_change(fill_method=None); mkt = raw["SPY"]
    resid = (raw - raw.rolling(BETA_W).cov(mkt).div(mkt.rolling(BETA_W).var(), axis=0).multiply(mkt, axis=0)).where(mask.reindex_like(raw))
    ridx = pd.DatetimeIndex(resid.index); cols = list(resid.columns)
    caps = caps.reindex(index=ridx, columns=cols)
    return SimpleNamespace(
        ridx=ridx, col={c: j for j, c in enumerate(cols)},
        R=np.ascontiguousarray(resid.values, dtype=np.float64),
        R_pay=np.ascontiguousarray(raw.where(mask.reindex_like(raw)).reindex(index=resid.index, columns=cols).values, dtype=np.float64),
        caps_np=caps.values, caps_cols=caps.columns.to_numpy())


def load_cache(arm: str) -> tuple[dict, list]:
    """A partition cache ({date: {universe, labels}}) and its sorted refit dates."""
    with open(paths.PARTITIONS / f"{LEGACY_FILE.get(arm, arm)}.pkl", "rb") as f:
        cache = pickle.load(f)
    return cache, sorted(cache.keys())


def day_universe(G: SimpleNamespace, i: int):
    """The traded names on day ``i``; None when fewer than 50 qualify.

    Returns (tk, vi, jU, lb, crv, nxp): tickers, their positions within the top-500 list, their panel
    columns, the 5-day signal window, the 21-day correlation window and the next-day payoff returns
    (the last three on the top-500 list, to be indexed with ``vi``).
    """
    row = G.caps_np[i - 1]; fin = np.where(np.isfinite(row))[0]
    if len(fin) < 50: return None
    kk = min(500, len(fin)); top = fin[np.argpartition(row[fin], -kk)[-kk:]]; top = top[np.argsort(-row[top])]
    uni = G.caps_cols[top]; jU = np.array([G.col.get(x, -1) for x in uni]); ok = jU >= 0; uni, jU = uni[ok], jU[ok]
    lb = G.R[i - SIG_W + 1:i + 1][:, jU]; crv = G.R[i - CORR_W:i][:, jU]; nx, nxp = G.R[i + 1][jU], G.R_pay[i + 1][jU]
    v = (np.isfinite(lb).all(0) & np.isfinite(crv).all(0) & np.isfinite(nx) & np.isfinite(nxp))
    if v.sum() < 50: return None
    vi = np.where(v)[0]
    return uni[vi], vi, jU, lb, crv, nxp


def partition_for(RD: list, d: pd.Timestamp):
    """The latest refit date at or before ``d`` if it is at most MAX_AGE days old, else None."""
    p = bisect.bisect_right(RD, d) - 1
    if p < 0 or (d - RD[p]).days > MAX_AGE: return None
    return RD[p]


def fill_labels(universe, labels, tk: np.ndarray, crv_v: np.ndarray, KA: int) -> np.ndarray:
    """Labels of the traded names, with uncovered names assigned to their most correlated group."""
    X = crv_v; Xc = X - X.mean(0, keepdims=True); nr = np.sqrt((Xc * Xc).sum(0)); nr[nr == 0] = 1.0; V = Xc / nr
    t2l = {t: int(l) for t, l in zip(universe, np.asarray(labels, dtype=np.int32))}
    out = np.zeros(len(tk), dtype=np.int32); new = []
    for a_, t in enumerate(tk):
        if t in t2l: out[a_] = t2l[t]
        else: new.append(a_)
    if new:
        Cn = V[:, new].T @ V; ar = np.arange(len(tk))
        for r_, ni in enumerate(new):
            bk, ba = 0, -np.inf
            for k in range(KA):
                m = np.where((out == k) & (ar != ni))[0]
                if not len(m): continue
                af = float(Cn[r_, m].mean())
                if af > ba: ba, bk = af, k
            out[ni] = bk
    return out


def r2(x: np.ndarray, lab: np.ndarray) -> float:
    """1 - SS(x - group mean) / SS(x - grand mean); NaN when the cross-section has no variance."""
    x = x - x.mean(); tot = float((x * x).sum())
    if tot <= 0: return np.nan
    r_ = x.copy()
    for k in np.unique(lab):
        m = lab == k
        if m.any(): r_[m] -= x[m].mean()
    return 1.0 - float((r_ * r_).sum()) / tot
