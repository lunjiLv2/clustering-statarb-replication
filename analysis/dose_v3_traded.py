"""fig:dose (A.8): corrupting a real partition one fraction at a time, on the traded universe.

The PCA-loadings partition is degraded by replacing a fraction q of each day's labels with uniform
random ones (two independent draws per q, q = 0, 0.1, …, 1), and at each q a full rule-based
backtest is run on the corrupted labels. Both coordinates of a point come from the same labels:
the removal share (share of the day's cross-sectional residual variance removed by demeaning within
groups, averaged over days, on the traded universe) and the annualised volatility of the rule-based
book (bet ±1/n per side, gross 2, raw payoff basis — the construction of ``rule_engine``). The last
row (q = NaN, draw = −1) is the actual random partition on the same basis. At q = 0 the book is the
shipped pca_load rule book and its volatility must agree with it; at q = 1 the point must land on
the random control.

Output: analysis/results/dose_v3_traded_cal6913.csv (q, draw, removal_share, ann_vol, naive_SR,
days, eff_K, traded_N, dof_floor = (K−1)/(N−1)).

Run: ``CSA_PANEL_ROOT=/path/to/compat_panel python analysis/dose_v3_traded.py`` (23 backtests,
about a minute each; ``--qs 0 --draws 0 --no-control`` for a one-backtest smoke test).
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis import books
from analysis._compare import compare_and_write
from analysis.traded_universe import K, BETA_W, SIG_W, load_panel, load_cache, day_universe, partition_for, fill_labels, r2

CALSET = set(books.IDX); SQ = np.sqrt(252.0)
QS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]; DRAWS = (0, 1)


def corrupt(lab: np.ndarray, q: float, rng: np.random.Generator) -> np.ndarray:
    if q <= 0: return lab
    if q >= 1: return rng.integers(0, K, len(lab)).astype(np.int32)
    m = rng.random(len(lab)) < q
    out = lab.copy(); out[m] = rng.integers(0, K, int(m.sum()))
    return out


def backtest(G, cache: dict, RD: list, q: float, draw: int):
    """One rule-based backtest on the cache's labels corrupted at fraction q with draw ``draw``."""
    rng = np.random.default_rng(1000 * draw + int(round(q * 100)))
    lab_by_day = {d: corrupt(np.asarray(cache[d]["labels"], dtype=np.int32), q, rng) for d in RD}
    rs, nt, kt, pnl = [], [], [], {}
    for i in range(BETA_W + SIG_W, len(G.ridx) - 1):
        d = G.ridx[i]
        if d not in CALSET: continue
        u = day_universe(G, i)
        if u is None: continue
        tk, vi, jU, lb, crv, nxp = u
        rd = partition_for(RD, d)
        if rd is None: continue
        out = fill_labels(cache[rd]["universe"], lab_by_day[rd], tk, crv[:, vi], K)
        lbv = lb[:, vi]; cm = np.zeros_like(lbv)
        for k in range(K):
            m = out == k
            if m.any(): cm[:, m] = lbv[:, m].mean(1, keepdims=True)
        xt = G.R[i][jU][vi]; okx = np.isfinite(xt)
        if okx.sum() >= 100:
            rs.append(r2(xt[okx], out[okx])); nt.append(int(okx.sum())); kt.append(len(np.unique(out[okx])))
        sig = -(lbv - cm).sum(0); pm, nm = sig > 0, sig < 0
        w = np.zeros_like(sig); w[pm] = 1.0 / max(int(pm.sum()), 1); w[nm] = -1.0 / max(int(nm.sum()), 1)
        pnl[d] = float((w * nxp[vi]).sum())
    s = pd.Series(pnl).sort_index(); Kb, Nb = float(np.mean(kt)), float(np.mean(nt))
    return dict(removal_share=float(np.nanmean(rs)), ann_vol=float(SQ * s.std(ddof=1)), naive_SR=float(SQ * s.mean() / s.std(ddof=1)),
                days=len(s), eff_K=Kb, traded_N=Nb, dof_floor=(Kb - 1) / (Nb - 1))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--qs", nargs="*", type=float, default=QS); ap.add_argument("--draws", nargs="*", type=int, default=list(DRAWS))
    ap.add_argument("--no-control", action="store_true", help="skip the actual random partition row")
    a = ap.parse_args()
    G = load_panel(); cache, RD = load_cache("pca_load"); rows = []
    print(f"[dose] residuals {G.R.shape}; partition {len(RD)} refit dates", flush=True)
    for q in a.qs:
        for dr in a.draws:
            r = backtest(G, cache, RD, q, dr); rows.append(dict(q=q, draw=dr, **r))
            print(f"  q={q:.1f} draw{dr}  removal {r['removal_share']:.5f}  vol {r['ann_vol']:.5f}  SR {r['naive_SR']:+.4f}  "
                  f"n={r['days']}  K {r['eff_K']:.2f}  N_t {r['traded_N']:.2f}  floor {r['dof_floor']:.5f}", flush=True)
    if not a.no_control:
        cache, RD = load_cache("random"); r = backtest(G, cache, RD, 0.0, 0); rows.append(dict(q=np.nan, draw=-1, **r))
        print(f"  actual random control (traded basis): removal {r['removal_share']:.5f}  vol {r['ann_vol']:.5f}  SR {r['naive_SR']:+.4f}", flush=True)
    D = pd.DataFrame(rows)
    # gates: the q = 0 book is the shipped pca_load rule book, the control is the shipped random rule book
    for arm, sel in (("pca_load", (D.q == 0) & (D.draw == 0)), ("random", D.draw == -1)):
        if sel.any():
            v = books.ann_vol(books.rule_book(arm)) / 100
            print(f"  gate {arm}: book vol {D.loc[sel, 'ann_vol'].iloc[0]:.6f} vs shipped rule book {v:.6f}  Δ {D.loc[sel, 'ann_vol'].iloc[0] - v:+.1e}")
    m = D[D.draw >= 0].groupby("q")[["removal_share", "ann_vol"]].mean()
    if len(m) > 1:
        print(f"  removal share monotone decreasing in q: {bool((m.removal_share.diff().dropna() < 0).all())}; "
              f"volatility monotone increasing: {bool((m.ann_vol.diff().dropna() > 0).all())}")
    compare_and_write(D, "dose_v3_traded_cal6913.csv", ["q", "draw"])


if __name__ == "__main__":
    main()
