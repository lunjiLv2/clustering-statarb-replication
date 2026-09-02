"""Reconstruction test for the shipped position files (Zenodo data/derived/weights/*.pkl).

For every arm x seed the daily P&L is rebuilt from the executed positions and the panel's simple
returns, sum_i w_t(i) r_t(i), and compared with the DailyPnL column of the head log; the gross
leverage of the positions is compared with the logged GrossLeverage and with one. The paper's
producers apply the same gates (analysis/turnover_v3.py) on every 40th day; this tool checks every
day. Needs CSA_PANEL_ROOT (the compat panel is CRSP-derived and not shipped).

    CSA_PANEL_ROOT=/path/to/compat_panel python tools/check_weights.py [--arms kmeans_ret gics ...]
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--arms", nargs="*", default=paths.ARMS); ap.add_argument("--seeds", nargs="*", type=int, default=list(paths.SEEDS)); ap.add_argument("--tol", type=float, default=1e-6)
    a = ap.parse_args()
    assert paths.PANEL is not None, "set CSA_PANEL_ROOT"
    raw = pd.read_pickle(paths.PANEL / "prices.pkl").pct_change(fill_method=None)
    bad = 0
    for arm in a.arms:
        for seed in a.seeds:
            log = pd.read_csv(paths.HEAD_LOGS / f"{arm}_seed{seed}.csv", parse_dates=["Date"]).set_index("Date")
            mx = dg = d1 = 0.0; n = 0
            for t, nm, w in books.positions(arm, seed):
                if t not in log.index or t not in raw.index: continue
                r = raw.loc[t].reindex(nm).to_numpy(float); ok = np.isfinite(r)
                mx = max(mx, abs(float(np.nansum(w[ok] * r[ok])) - float(log.loc[t, "DailyPnL"])))
                sw = float(np.abs(w).sum()); dg = max(dg, abs(sw - float(log.loc[t, "GrossLeverage"]))); d1 = max(d1, abs(sw - 1.0)); n += 1
            ok = mx < a.tol and dg < 1e-5 and d1 < 1e-5; bad += not ok
            print(f"{'OK ' if ok else 'BAD'} {arm:18s} seed {seed:<4} days {n}  max|pnl diff| {mx:.2e}  gross dev {dg:.1e}/{d1:.1e}", flush=True)
    print("ALL POSITION FILES RECONSTRUCT THE LOGGED P&L" if not bad else f"{bad} RUN(S) FAILED"); return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
