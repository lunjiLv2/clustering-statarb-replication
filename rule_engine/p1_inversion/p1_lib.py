#!/usr/bin/env python3
"""
p1_lib.py  --  PILOT 1: loss-form inversion on the CLEAN panel.
================================================================
Shared engine for the "does Sortino-wins-naive survive the split-fix?" pilot.

The naive MR engine here is a *faithful, parameterised re-implementation* of
ENGINE B (daily-rebalance convention) from
  recleaning/revalidation/revalidate_naive.py :: run_engine_b()
which is the canonical source of the headline "SSSNET daily naive 1.708"
(and, on the clean/split-safe panel, 1.564).

CONVENTION (Engine B, verbatim):
  * daily universe = top-500 by PRIOR-day market cap (Cleaned_Data/caps.pkl)
  * residuals = SPY-CAPM rolling(60,min_periods=60) beta residuals, masked by
    Cleaned_Data/mask.pkl  -> here supplied pre-built as rb_new / rb_old in
    recleaning/revalidation/cache_resid.npz (the CLEAN panel is rb_new).
  * labels: latest cache refresh <= t with age <= 10 calendar days; tickers in
    today's tradable universe but absent from that snapshot are affiliated to the
    cluster with max mean 21d-residual-correlation (sequential, canon order).
  * bet: sig = -(5d cumsum of daily cluster-demeaned residual); dollar-neutral
    +1/n_long, -1/n_short (gross leverage 2.0); PnL = bet . next-day residual
    (raw residual, not demeaned).
  * Sharpe = mean/std(ddof=0) * sqrt(252) of daily book PnL  (HOUSE convention).

PARAMETERISATION for this pilot:
  R_trade   : panel used for signal (lb), next-day PnL (nx)          [= rb_new]
  R_affil   : panel used for the 21d affiliation correlation of new tickers
  R_valid2  : optional 2nd panel; if given, a stock is tradable only if finite
              under BOTH R_trade and R_valid2 (used ONLY to reproduce the cached
              anchor bit-exactly, whose validity was intersected old&new).
  refit_dates: override refresh schedule (used to view a 1d cache at 5d cadence).

Seed 42. numpy/pandas only. No network, no installs. Read-only inputs; the
caller writes only inside p1_inversion/.
"""
from __future__ import annotations

import os
import bisect
import pickle
import warnings
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
np.seterr(all="ignore")

SEED = 42
ANN = np.sqrt(252.0)

# Legacy inputs of the ORIGINAL route-B study (frozen partitions, cached residuals). run_naive_routeA.py uses
# only naive_stream() from this module and rebuilds residuals from the panel, so none of these paths is read
# in the replication; they are kept for provenance and can be pointed elsewhere with CSA_LEGACY_WS.
WS = os.environ.get("CSA_LEGACY_WS", "/Users/lunjizhu/Desktop/Fin-Network Working Space")
ROOT = os.path.join(WS, "GNN_for_Trading")
CACHE_RESID = os.path.join(ROOT, "recleaning", "revalidation", "cache_resid.npz")
CAPS_OLD = os.path.join(WS, "Cleaned_Data", "caps.pkl")
ENG_B_PKL = os.path.join(ROOT, "recleaning", "revalidation", "engineB_results.pkl")

M15 = os.path.join(ROOT, "_pkl_download", "May_15_Meeting", "MR_clustering", "output")
J5 = os.path.join(ROOT, "_pkl_download", "June_5_Meeting", "diagnostics")
STREAM_PKL = os.path.join(ROOT, "_pkl_download", "May_29_Meeting", "results", "stream_pnl.pkl")

# label caches used in this pilot -------------------------------------------------
CACHES = {
    # --- trading-driven (loss-shaped clusterizers) ---
    "sortino":      (os.path.join(M15, "refined_fv2a_sortino_daily_clusters_1d.pkl"), "labels", "1d"),
    "sharpe_fixed": (os.path.join(M15, "refined_fv2a_fixed_daily_clusters_1d.pkl"),   "labels", "1d"),
    "fv3sm":        (os.path.join(M15, "refined_fv3sm_clusters_1d.pkl"),              "labels", "1d"),
    "spectral_sortino": (os.path.join(J5, "sssnet_spectral_sortino_labels.pkl"),      "labels", "5d"),
    # --- unsupervised baselines ---
    "sssnet":       (os.path.join(M15, "sssnet_soft_K30_5d.pkl"),                     "labels", "5d"),
    "sponge":       (os.path.join(M15, "sssnet_soft_K30_5d.pkl"),             "sponge_labels", "5d"),
    "kmeans":       (os.path.join(M15, "labelcache_kmeans_ret_K30_5d.pkl"),           "labels", "5d"),
    "agglo":        (os.path.join(M15, "labelcache_agglo_avg_K30_5d.pkl"),            "labels", "5d"),
    "pca":          (os.path.join(M15, "labelcache_pca_load_K30_5d.pkl"),             "labels", "5d"),
}
TRADING_DRIVEN = ["sortino", "sharpe_fixed", "fv3sm", "spectral_sortino"]
UNSUPERVISED = ["sssnet", "sponge", "kmeans", "agglo", "pca"]

ERAS = [("97-02", 1997, 2002), ("03-09", 2003, 2009), ("10-14", 2010, 2014),
        ("15-19", 2015, 2019), ("20-24", 2020, 2024)]


# ------------------------------------------------------------------ basic stats
def sharpe(x) -> float:
    """Annualized gross Sharpe, HOUSE convention: mean/std(ddof=0)*sqrt(252)."""
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 20:
        return float("nan")
    s = x.std()
    return float(x.mean() / s * ANN) if s > 0 else float("nan")


def era_sharpe(s: pd.Series, a: int, b: int) -> float:
    sub = s[(s.index.year >= a) & (s.index.year <= b)]
    return sharpe(sub.values)


# ------------------------------------------------------------------ data loading
def load_resid() -> Tuple[dict, List[str], pd.DatetimeIndex]:
    z = np.load(CACHE_RESID, allow_pickle=True)
    cols = list(z["cols"])
    ridx = pd.DatetimeIndex(z["dates"])
    return z, cols, ridx


def masked_panel(z, which: str) -> np.ndarray:
    """Return residual panel `which` with the OLD mask applied (canon)."""
    mask = z["mask"]
    return np.where(mask, z[which], np.nan)


def load_cache(name: str) -> Tuple[dict, str, str]:
    path, key, cadence = CACHES[name]
    with open(path, "rb") as f:
        cache = pickle.load(f)
    return cache, key, cadence


# ------------------------------------------------------------------ naive engine
def naive_stream(cache: dict, label_key: str,
                 ridx: pd.DatetimeIndex, col: Dict[str, int],
                 caps_np: np.ndarray, caps_cols: np.ndarray,
                 R_trade: np.ndarray, R_affil: np.ndarray,
                 R_valid2: Optional[np.ndarray] = None,
                 R_pay: Optional[np.ndarray] = None,
                 refit_dates: Optional[Sequence[pd.Timestamp]] = None,
                 K: int = 30, BETA_W: int = 60, SIG_W: int = 5,
                 CORR_W: int = 21, MAX_AGE: int = 10,
                 date_start: str = "1996-01-01",
                 date_end: str = "2024-12-31") -> pd.Series:
    """Daily-rebalance naive MR PnL series for one cluster partition on one panel.

    Faithful to run_engine_b(); parameterised on trade/affil/validity panels and
    the refresh schedule.  Returns a date-indexed pd.Series of daily book PnL.

    R_pay — OPTIONAL payoff-only panel. When given, the book is still formed exactly
    as before (signal, correlation basis, universe and validity all from R_trade /
    R_affil), but the position is PAID on R_pay[t+1] instead of R_trade[t+1].

    This exists because the deep and naive legs of the head-lift were booking
    different things: the head pipeline builds its target from `raw_df`
    (pipeline_v21_tourney_kmeans_ret.py:250,570) while this engine was paid on the
    SPY-CAPM residual panel, so "lift" was a raw-return Sharpe minus a residual-return
    Sharpe. Measured spread of that mismatch across arms is 0.04-0.21 SR against
    adjacent gaps of 0.016 in the published lift table.

    Do NOT instead pass R_trade=raw to fix this: R_trade also drives the 5-day
    signal and the 21-day validity mask, so swapping it wholesale changes the
    STRATEGY, not just the payoff, and roughly doubles the apparent effect.

    A name whose payoff is not finite is dropped from the book on that day, so the
    universe can differ marginally from the R_pay=None run; the count is reported by
    run_naive_routeA.py --basis raw.
    """
    if refit_dates is None:
        refit_dates = sorted(cache.keys())
    refit_dates = list(refit_dates)
    d0 = pd.Timestamp(date_start)
    d1 = pd.Timestamp(date_end)

    pnl: Dict[pd.Timestamp, float] = {}
    n_days = 0

    for d_idx in range(BETA_W + SIG_W, len(ridx) - 1):
        d = ridx[d_idx]
        if d < d0 or d > d1:
            continue
        row = caps_np[d_idx - 1]
        fin = np.where(np.isfinite(row))[0]
        if len(fin) < 50:
            continue
        kk = min(500, len(fin))
        top = fin[np.argpartition(row[fin], -kk)[-kk:]]
        top = top[np.argsort(-row[top])]                 # descending cap (canon order)
        universe = caps_cols[top]
        jU = np.array([col.get(x, -1) for x in universe])
        okmap = jU >= 0
        universe, jU = universe[okmap], jU[okmap]

        lb = R_trade[d_idx - SIG_W + 1:d_idx + 1][:, jU]      # 5 rows ending at d
        cr_v = R_trade[d_idx - CORR_W:d_idx][:, jU]           # 21 rows excl d (validity)
        cr_a = R_affil[d_idx - CORR_W:d_idx][:, jU]           # 21 rows excl d (affiliation)
        nx = R_trade[d_idx + 1][jU]

        nx_pay = nx if R_pay is None else R_pay[d_idx + 1][jU]

        v = (np.isfinite(lb).all(axis=0) & np.isfinite(cr_v).all(axis=0)
             & np.isfinite(nx))
        if R_pay is not None:
            v = v & np.isfinite(nx_pay)
        if R_valid2 is not None:
            lb2 = R_valid2[d_idx - SIG_W + 1:d_idx + 1][:, jU]
            cr2 = R_valid2[d_idx - CORR_W:d_idx][:, jU]
            nx2 = R_valid2[d_idx + 1][jU]
            v = (v & np.isfinite(lb2).all(axis=0) & np.isfinite(cr2).all(axis=0)
                 & np.isfinite(nx2))
        if v.sum() < 50:
            continue
        vi = np.where(v)[0]
        ticks = universe[vi]

        pos = bisect.bisect_right(refit_dates, d) - 1
        if pos < 0 or (d - refit_dates[pos]).days > MAX_AGE:
            continue
        ent = cache[refit_dates[pos]]

        # affiliation basis (unit-normalised demeaned 21d columns, affil panel)
        X = cr_a[:, vi]
        Xc = X - X.mean(axis=0, keepdims=True)
        nrm = np.sqrt((Xc * Xc).sum(axis=0))
        nrm[nrm == 0] = 1.0
        V = Xc / nrm

        t2l = {tk: int(l) for tk, l in zip(ent["universe"], ent[label_key])}
        out = np.zeros(len(ticks), dtype=np.int32)
        new_idx = []
        for i, tk in enumerate(ticks):
            if tk in t2l:
                out[i] = t2l[tk]
            else:
                new_idx.append(i)
        if new_idx:
            Cn = V[:, new_idx].T @ V
            arange = np.arange(len(ticks))
            for r, ni in enumerate(new_idx):
                best_k, best_a = 0, -np.inf
                for k in range(K):
                    mems = np.where((out == k) & (arange != ni))[0]
                    if len(mems) == 0:
                        continue
                    aff = float(Cn[r, mems].mean())
                    if aff > best_a:
                        best_a, best_k = aff, k
                out[ni] = best_k
        lab = out

        lbv = lb[:, vi]
        cm = np.zeros_like(lbv)
        for k in range(K):
            mem = lab == k
            if mem.any():
                cm[:, mem] = lbv[:, mem].mean(axis=1, keepdims=True)
        raw = -(lbv - cm).sum(axis=0)
        posm, negm = raw > 0, raw < 0
        bet = np.zeros_like(raw)
        nl, ns = max(int(posm.sum()), 1), max(int(negm.sum()), 1)
        bet[posm] = 1.0 / nl
        bet[negm] = -1.0 / ns
        pnl[d] = float((bet * nx_pay[vi]).sum())
        n_days += 1

    return pd.Series(pnl).sort_index()


# ------------------------------------------------------------------ bootstrap
def block_boot_indices(T: int, rng: np.random.Generator, block: int = 21) -> np.ndarray:
    """Circular moving-block bootstrap day indices (HOUSE / repo convention)."""
    starts = rng.integers(0, T, int(np.ceil(T / block)))
    idx = np.concatenate([np.arange(s, s + block) % T for s in starts])[:T]
    return idx


def paired_cbb(mat: np.ndarray, names: List[str], n_boot: int = 500,
               block: int = 21, seed: int = SEED
               ) -> Tuple[dict, dict, np.ndarray]:
    """Paired circular-block bootstrap over an aligned (T, n_stream) PnL matrix.

    Returns:
      sr_ci   : name -> (point_SR, lo, hi, sd)
      draws   : name -> np.ndarray of bootstrap SRs  (for paired deltas)
      idx_all : (n_boot, T) resample indices actually used (paired across streams)
    """
    T, n = mat.shape
    rng = np.random.default_rng(seed)
    draws = {nm: np.empty(n_boot) for nm in names}
    idx_all = np.empty((n_boot, T), dtype=np.int64)
    for b in range(n_boot):
        idx = block_boot_indices(T, rng, block)
        idx_all[b] = idx
        sub = mat[idx]
        mu = sub.mean(axis=0)
        sd = sub.std(axis=0)
        sr = np.where(sd > 0, mu / sd * ANN, np.nan)
        for j, nm in enumerate(names):
            draws[nm][b] = sr[j]
    sr_ci = {}
    for j, nm in enumerate(names):
        col_ = mat[:, j]
        pt = sharpe(col_)
        d = draws[nm]
        sr_ci[nm] = (pt, float(np.nanpercentile(d, 2.5)),
                     float(np.nanpercentile(d, 97.5)), float(np.nanstd(d)))
    return sr_ci, draws, idx_all
