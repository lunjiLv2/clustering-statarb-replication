"""Turnover, break-even cost and net Sharpe ratios of the 42 trained books (tab:costs, §4.4, §6.3).

For each arm x seed the executed positions are loaded and three gates are applied before any number
is emitted: (i) the logged daily P&L is reconstructed from the positions and the panel returns to
within 1e-6 (needs CSA_PANEL_ROOT; skipped with a warning otherwise), (ii) the gross leverage of the
positions equals the logged gross, (iii) it equals one. Turnover is the two-way sum of absolute
weight changes, sum_i |w_t(i) - w_{t-1}(i)|; the one-way figure printed in the paper is half of it.
Net P&L at c basis points deducts c * 1e-4 * two-way turnover, so the break-even cost is
mean(P&L) / mean(turnover) in bp and is identical under both conventions.

Outputs: analysis/results/turnover_v3_perseed_cal6913.csv and turnover_v3_mean_cal6913.csv
(mean of per-seed statistics, the manuscript convention).

Run: ``CSA_PANEL_ROOT=... python analysis/turnover_v3.py``
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books

LEGACY = {"sssnetpre": "sssnet_w60"}
BPS = (1, 2, 5, 10, 14)
SQ = np.sqrt(252)
STRIDE = 40           # the gates sample every 40th day (as in the audited producer)


def load_returns() -> pd.DataFrame | None:
    if paths.PANEL is None:
        print("WARNING: CSA_PANEL_ROOT not set; the P&L reconstruction gate is skipped", file=sys.stderr)
        return None
    return pd.read_pickle(paths.PANEL / "prices.pkl").pct_change(fill_method=None)


def one_run(arm: str, seed: int, raw: pd.DataFrame | None) -> dict | None:
    pnl = books.head_book(arm, seed)                      # on the common calendar
    log = pd.read_csv(paths.HEAD_LOGS / f"{arm}_seed{seed}.csv", parse_dates=["Date"]).set_index("Date").reindex(books.IDX)
    W = [e for e in books.positions(arm, seed) if e[0] in log.index]
    # gate 1: reconstruct DailyPnL from the positions and the panel returns
    mx = 0.0
    if raw is not None:
        for t, nm, w in W[::STRIDE]:
            if t not in raw.index: continue
            r = raw.loc[t].reindex(nm).to_numpy(float); ok = np.isfinite(r)
            mx = max(mx, abs(float(np.nansum(w[ok] * r[ok])) - float(log.loc[t, "DailyPnL"])))
        if mx >= 1e-6:
            print(f"  [GATE FAIL] {arm} seed{seed}: reconstruction max|diff| {mx:.2e}"); return None
    # gates 2 and 3: the positions are the traded book and gross leverage is one
    dg = d1 = 0.0
    for t, nm, w in W[::STRIDE]:
        sw = float(np.abs(w).sum())
        dg = max(dg, abs(sw - float(log.loc[t, "GrossLeverage"]))); d1 = max(d1, abs(sw - 1.0))
    if dg >= 1e-5 or d1 >= 1e-5:
        print(f"  [GATE FAIL] {arm} seed{seed}: gross deviation {dg:.2e}/{d1:.2e}"); return None
    # two-way turnover on consecutive position vectors
    prev, tos = None, []
    for t, nm, w in W:
        p = pd.Series(w, index=nm)
        if prev is not None:
            u = prev.index.union(p.index)
            tos.append(float((p.reindex(u, fill_value=0) - prev.reindex(u, fill_value=0)).abs().sum()))
        prev = p
    to = float(np.mean(tos))
    row = dict(arm=LEGACY.get(arm, arm), seed=seed, gross_dev=max(dg, d1), gross_SR=books.sharpe(pnl), ann_ret=252 * pnl.mean(),
               daily_turnover_oneway_N6_convention=to / 2, ann_vol=SQ * pnl.std(ddof=1), daily_turnover=to,
               ann_turnover=252 * to, gross_book=float(np.mean([np.abs(w).sum() for _, _, w in W[::STRIDE]])),
               recon_maxdiff=mx, breakeven_bps=1e4 * pnl.mean() / to)
    cost = pd.Series([np.nan] + tos, index=pnl.index[:len(tos) + 1]).reindex(pnl.index)
    for b in BPS:
        net = (pnl - (b / 1e4) * cost).dropna()
        row[f"netSR_{b}bp"] = SQ * net.mean() / net.std(ddof=1)
    return row


def main() -> None:
    raw = load_returns(); rows = []
    for arm in paths.ARMS:
        for sd in paths.SEEDS:
            r = one_run(arm, sd, raw)
            if r: rows.append(r); print(f"  {r['arm']:18s} s{sd:<4} gSR {r['gross_SR']:+.4f}  turn {r['daily_turnover']:.4f}  BE {r['breakeven_bps']:.3f}bp", flush=True)
    df = pd.DataFrame(rows)
    m = df.groupby("arm").mean(numeric_only=True).drop(columns=["seed"]).sort_values("gross_SR", ascending=False)
    for name, new, keys in (("turnover_v3_perseed_cal6913.csv", df, ["arm", "seed"]), ("turnover_v3_mean_cal6913.csv", m.reset_index(), ["arm"])):
        ref = pd.read_csv(paths.RESULTS / name)
        j = new.merge(ref, on=keys, suffixes=("", "_ref"))
        num = [c for c in ref.columns if c not in keys and ref[c].dtype.kind == "f"]
        d = max(np.abs(j[c] - j[c + "_ref"]).max() for c in num)
        print(f"{name}: {len(j)}/{len(ref)} rows matched on {keys}; max |diff| {d:.2e}")
        new.to_csv(paths.RESULTS / name, index=False)

if __name__ == "__main__":
    main()
