"""Turnover, break-even cost and net Sharpe ratios of the 14 rule-based books (tab:costs, §4.4, §6.3).

The rule engine exports only the daily P&L of each rule book, not its positions, so the positions
are rebuilt here by an independent re-implementation of the rule (written from the kernel's
definition, not by importing it): each day the top-500 names by lagged market cap that have a
complete 5-day residual-return history are assigned to the day's partition (names absent from the
partition go to the cluster with the highest mean 21-day residual correlation), the signal is minus
the sum of the 5-day cluster-demeaned residual returns, and the book is +1/n_long on the positive
signals and -1/n_short on the negative ones, so its gross exposure is exactly 2. Residual returns
are simple returns minus a 60-day rolling beta times the SPY return, masked to the panel universe.

Three gates decide whether an arm's turnover is reported at all -- the failure is the finding:
(1) the rebuilt calendar equals the shipped book's calendar (the common 6,913 days); (2) the rebuilt
daily P&L reproduces the shipped book to 1e-12; (3) gross exposure is 2 on every day.

Conventions: two-way turnover = sum_i |w_t(i) - w_{t-1}(i)|; the one-way figure printed in the
paper is half of it, and because the rule book has gross 2 the turnover per unit of gross is also
half of it (the trained books have gross 1, so the per-gross columns put the two on one basis).
Net P&L at c basis points deducts c * 1e-4 * two-way turnover; the break-even cost is
mean(P&L) / mean(two-way turnover) in bp, identical under both conventions.

Output: analysis/results/naive_turnover_v3_cal6913.csv (arm names as in the partition manifest;
the SSSNET arm is 'sssnetpre').

Run: ``CSA_PANEL_ROOT=... python analysis/naive_turnover_v3.py [--arms kmeans_ret gics ...]``
"""
from __future__ import annotations
import argparse, bisect, pickle, sys, time
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books
from analysis._compare import compare_and_write

ARMS = ["kmeans_ret", "agglo_complete", "fv3sm_w60", "sponge_w60", "pca_load", "agglo_avg", "sortino_w60",
        "fv2a_w60", "sharpe_fixed_w60", "gics", "spectral_unsigned", "sssnetpre", "k1", "random"]
K, BETA_W, SIG_W, CORR_W, MAX_AGE = 30, 60, 5, 21, 10     # clusters, beta window, signal window, correlation window, max partition age (days)
TOP, MIN_NAMES = 500, 50                                 # universe size by lagged cap; minimum names for a trading day
BPS, SQ = (1, 2, 5, 10, 14), np.sqrt(252.0)
CALSET = set(books.IDX)


class Panel:
    """Residual and payoff return matrices plus lagged caps, aligned on the panel calendar."""

    def __init__(self, root: Path):
        px = pd.read_pickle(root / "prices.pkl"); caps = pd.read_pickle(root / "caps.pkl")
        mask = pd.read_pickle(root / "mask.pkl").astype(bool)
        raw = px.pct_change(fill_method=None)
        assert "SPY" in raw.columns, "SPY missing from the panel"
        mkt = raw["SPY"]
        resid = (raw - raw.rolling(BETA_W).cov(mkt).div(mkt.rolling(BETA_W).var(), axis=0)
                 .multiply(mkt, axis=0)).where(mask.reindex_like(raw))
        self.idx = pd.DatetimeIndex(resid.index)
        self.cols = list(resid.columns); self.col = {c: j for j, c in enumerate(self.cols)}
        self.R = np.ascontiguousarray(resid.values, dtype=np.float64)
        self.R_pay = np.ascontiguousarray(raw.where(mask.reindex_like(raw))
                                          .reindex(index=resid.index, columns=resid.columns).values, dtype=np.float64)
        caps = caps.reindex(index=self.idx, columns=self.cols)
        self.caps, self.caps_cols = caps.values, caps.columns.to_numpy()
        print(f"[naive-turn] residuals {self.R.shape}  {self.idx[0].date()}..{self.idx[-1].date()}", flush=True)


def rule_positions(P: Panel, cache: dict):
    """Yield (date, tickers, weights, next-day payoff returns, names filled by nearest cluster)."""
    rd = sorted(cache.keys()); R, R_pay = P.R, P.R_pay
    for i in range(BETA_W + SIG_W, len(P.idx) - 1):
        d = P.idx[i]
        if d not in CALSET:
            continue
        row = P.caps[i - 1]                                   # lagged market caps
        fin = np.where(np.isfinite(row))[0]
        if len(fin) < MIN_NAMES:
            continue
        kk = min(TOP, len(fin))
        top = fin[np.argpartition(row[fin], -kk)[-kk:]]; top = top[np.argsort(-row[top])]
        uni = P.caps_cols[top]
        jU = np.array([P.col.get(x, -1) for x in uni]); ok = jU >= 0
        uni, jU = uni[ok], jU[ok]
        lb = R[i - SIG_W + 1:i + 1][:, jU]                    # signal window (inclusive of today)
        crv = R[i - CORR_W:i][:, jU]                          # correlation window (before today)
        nx, nxp = R[i + 1][jU], R_pay[i + 1][jU]              # next-day residual and payoff returns
        v = np.isfinite(lb).all(0) & np.isfinite(crv).all(0) & np.isfinite(nx) & np.isfinite(nxp)
        if v.sum() < MIN_NAMES:
            continue
        vi = np.where(v)[0]; tk = uni[vi]
        p = bisect.bisect_right(rd, d) - 1                    # latest partition on or before d
        if p < 0 or (d - rd[p]).days > MAX_AGE:
            continue
        ent = cache[rd[p]]
        X = crv[:, vi]; Xc = X - X.mean(0, keepdims=True)
        nr = np.sqrt((Xc * Xc).sum(0)); nr[nr == 0] = 1.0
        V = Xc / nr
        t2l = {t: int(l) for t, l in zip(ent["universe"], ent["labels"])}
        out = np.zeros(len(tk), dtype=np.int32); new = []
        for a_, t in enumerate(tk):
            if t in t2l: out[a_] = t2l[t]
            else: new.append(a_)
        if new:                                               # nearest-cluster fill by mean correlation
            Cn = V[:, new].T @ V; ar = np.arange(len(tk))
            for r_, ni in enumerate(new):
                bk, ba = 0, -np.inf
                for k in range(K):
                    m = np.where((out == k) & (ar != ni))[0]
                    if not len(m): continue
                    af = float(Cn[r_, m].mean())
                    if af > ba: ba, bk = af, k
                out[ni] = bk
        lbv = lb[:, vi]; cm = np.zeros_like(lbv)
        for k in range(K):
            m = out == k
            if m.any(): cm[:, m] = lbv[:, m].mean(1, keepdims=True)
        sig = -(lbv - cm).sum(0)                              # reversal: long the losers, short the winners
        pm, nm = sig > 0, sig < 0
        w = np.zeros_like(sig)
        w[pm] = 1.0 / max(int(pm.sum()), 1)
        w[nm] = -1.0 / max(int(nm.sum()), 1)
        yield d, tk, w, nxp[vi], len(new)


def one_arm(arm: str, P: Panel) -> dict | None:
    ref = books.rule_book(arm)                                # shipped book on the common calendar
    with open(paths.PARTITIONS / f"{arm}.pkl", "rb") as f:
        cache = pickle.load(f)
    prev, tos, mine, fills, gr = None, {}, {}, [], []
    for d, tk, w, pay, nf in rule_positions(P, cache):
        mine[d] = float((w * pay).sum()); fills.append(nf); gr.append(float(np.abs(w).sum()))
        p = pd.Series(w, index=tk)
        if prev is not None:
            u = prev.index.union(p.index)
            tos[d] = float((p.reindex(u, fill_value=0) - prev.reindex(u, fill_value=0)).abs().sum())
        prev = p
    mine = pd.Series(mine).sort_index()
    if not mine.index.equals(ref.index):                      # gate 1: calendar
        print(f"  {arm:18s} [GATE1 FAIL] rebuilt {len(mine)} days vs shipped {len(ref)}; only-rebuilt "
              f"{len(mine.index.difference(ref.index))} only-shipped {len(ref.index.difference(mine.index))}"); return None
    md = float((mine - ref).abs().max())
    if md >= 1e-12:                                           # gate 2: P&L reproduction
        print(f"  {arm:18s} [GATE2 FAIL] max|rebuilt - shipped| = {md:.3e}"); return None
    gdev = float(np.max(np.abs(np.array(gr) - 2.0)))
    if gdev >= 1e-12:                                         # gate 3: gross exposure 2
        print(f"  {arm:18s} [GATE3 FAIL] max|sum|w| - 2| = {gdev:.3e}"); return None
    to = pd.Series(tos).sort_index(); tw = float(to.mean())
    r = dict(arm=arm, days=len(ref), recon_maxdiff=md, gross_book=float(np.mean(gr)), gross_dev=gdev,
             naive_SR=SQ * ref.mean() / ref.std(ddof=1), ann_ret=252 * ref.mean(), ann_vol=SQ * ref.std(ddof=1),
             daily_turnover_twoway_sum_abs_dw=tw, daily_turnover_oneway_N6_convention=tw / 2,
             turnover_twoway_per_unit_gross=tw / 2, ann_turnover_twoway=252 * tw,
             nearest_fill_names_per_day=float(np.mean(fills)), breakeven_bps=1e4 * ref.mean() / tw)
    for b in BPS:
        n = (ref - (b / 1e4) * to.reindex(ref.index)).dropna()
        r[f"netSR_{b}bp"] = SQ * n.mean() / n.std(ddof=1)
    print(f"  {arm:18s} n={len(ref)} SR{r['naive_SR']:+.4f} recon {md:.1e} turn2w {tw:.4f} (1w {tw/2:.4f}) "
          f"fill {r['nearest_fill_names_per_day']:.2f}/d BE {r['breakeven_bps']:.3f}bp net@2 {r['netSR_2bp']:+.4f}", flush=True)
    return r


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--arms", nargs="*", default=ARMS); a = ap.parse_args()
    assert paths.PANEL is not None, "set CSA_PANEL_ROOT to the compat panel directory"
    t0 = time.time(); P = Panel(paths.PANEL); rows = []
    for arm in a.arms:
        r = one_arm(arm, P)
        if r: rows.append(r)
    df = pd.DataFrame(rows).sort_values("naive_SR", ascending=False)
    print(f"\n[naive-turn] {len(df)}/{len(a.arms)} arms passed all three gates in {time.time() - t0:.0f}s")
    if len(a.arms) == len(ARMS):
        compare_and_write(df, "naive_turnover_v3_cal6913.csv", ["arm"])
    else:
        ref = pd.read_csv(paths.RESULTS / "naive_turnover_v3_cal6913.csv"); j = df.merge(ref, on="arm", suffixes=("", "_ref"))
        num = [c for c in ref.columns if c != "arm" and ref[c].dtype.kind in "fi"]
        print(f"partial run: {len(j)} arms; max |diff| vs shipped {max(float(np.abs(j[c] - j[c + '_ref']).max()) for c in num):.2e} (not written)")


if __name__ == "__main__":
    main()
