"""Shared loader for the executed position files and the position-correlation estimator.

``gated_book`` loads one run's positions (data/derived/weights/{arm}_seed{seed}.pkl) and applies the
three gates the manuscript promises before any position statistic is used, on every 40th day:
(1) the run's logged DailyPnL is reconstructed from the positions and the masked panel returns to
1e-6; (2) sum|w| equals the logged GrossLeverage to 1e-5; (3) sum|w| equals one to 1e-5. A run that
fails a gate contributes to nothing. Position overlap between two books is the mean over the common
calendar of the daily correlation of the two weight vectors over the union of their names, absent
names entered at zero (tab:gradient position row, §6.3).

Needs CSA_PANEL_ROOT (prices.pkl, mask.pkl) for gate 1.
"""
from __future__ import annotations
import os, sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books

STRIDE = 40


def masked_returns() -> pd.DataFrame:
    assert paths.PANEL is not None, "set CSA_PANEL_ROOT (prices.pkl, mask.pkl) for the reconstruction gate"
    px = pd.read_pickle(paths.PANEL / "prices.pkl")
    mask = pd.read_pickle(paths.PANEL / "mask.pkl").astype(bool)
    return px.pct_change(fill_method=None).where(mask.reindex_like(px))


def gated_book(arm: str, seed: int, raw: pd.DataFrame, days=None) -> dict | None:
    """{date: (sorted names, aligned weights)} on ``days`` (default: the common calendar), or None if a gate fails."""
    log = pd.read_csv(books.head_log_path(arm, seed), parse_dates=["Date"]).set_index("Date")
    W = books.positions(arm, seed)
    mx = dg = d1 = 0.0
    for t, nm, w in W[::STRIDE]:
        if t not in log.index: continue
        if t in raw.index:
            r = raw.loc[t].reindex(nm).to_numpy(float); ok = np.isfinite(r)
            mx = max(mx, abs(float(np.nansum(w[ok] * r[ok])) - float(log.loc[t, "DailyPnL"])))
        sw = float(np.abs(w).sum())
        dg = max(dg, abs(sw - float(log.loc[t, "GrossLeverage"]))); d1 = max(d1, abs(sw - 1.0))
    if mx >= 1e-6 or dg >= 1e-5 or d1 >= 1e-5:
        print(f"  [GATE FAIL] {arm} seed {seed}: recon {mx:.2e} gross {dg:.2e}/{d1:.2e}", flush=True); return None
    print(f"  gated {arm:18s} seed {seed:<4} n={len(W)} recon {mx:.1e} gross {max(dg, d1):.1e}", flush=True)
    keep = set(books.IDX if days is None else days); out = {}
    for t, nm, w in W:
        if t in keep:
            o = np.argsort(nm); out[t] = (np.asarray(nm)[o], np.asarray(w, float)[o])
    return out


def common_days(*bks) -> list:
    """The common calendar, asserting every book covers it (the one-window commitment)."""
    days = list(books.IDX)
    if os.environ.get("CSA_SMOKE_DAYS"):                      # smoke tests only: truncate the calendar
        days = days[: int(os.environ["CSA_SMOKE_DAYS"])]
    for b in bks:
        missing = [d for d in days if d not in b]
        assert not missing, f"book does not cover the calendar: {len(missing)} days missing, first {missing[0]}"
    return days


def daily_corr(a: dict, b: dict, days) -> float:
    """Mean over days of corr(w_a, w_b) on the union of the two books' names, absent names at zero."""
    out = []
    for t in days:
        xn, xv = a[t]; yn, yv = b[t]
        u = np.union1d(xn, yn)
        x = np.zeros(len(u)); x[np.searchsorted(u, xn)] = xv
        y = np.zeros(len(u)); y[np.searchsorted(u, yn)] = yv
        if x.std() > 0 and y.std() > 0:
            out.append(float(np.corrcoef(x, y)[0, 1]))
    return float(np.mean(out))
