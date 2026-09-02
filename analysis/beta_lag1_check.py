"""Beta-lag robustness check of the rule-based layer (§3.4 footnote / A.x): the rule books rebuilt with the
60-day CAPM beta lagged one day (beta_{t-1} instead of beta_t) versus the paper's convention.

The engine is an independent re-implementation of the rule (top-500 by lagged cap, >= 50 names, 60-day
rolling beta on SPY, 5-day residual signal including today, 21-day correlation window before today for
the nearest-cluster fill of names missing from the partition, partition age <= 10 days, bets +-1/n per
side), written from the documented rule and GATED at lag 0 against the shipped rule books before any
lag-1 number is read. The SSSNET column here is the mean of the per-seed SSSNET partitions
(the pre-option-B arm), as in the audited producer.

Outputs: analysis/results/beta_lag0_pnl_cal6913.csv and beta_lag1_pnl_cal6913.csv (Date x 14 books).
Run: ``CSA_PANEL_ROOT=... NPROC=8 python analysis/beta_lag1_check.py``  (~15 min on 8 cores)
"""
from __future__ import annotations
import argparse, bisect, os, pickle, sys, time
from multiprocessing import Pool
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books
from analysis.factors import FF6, load_ff, nw_ols
from analysis._compare import compare_and_write

K, BETA_W, SIG_W, CORR_W, MAX_AGE = 30, 60, 5, 21, 10
ARMS = ["kmeans_ret", "pca_load", "agglo_avg", "agglo_complete", "spectral_unsigned", "gics", "sponge_w60", "random", "k1",
        "fv2a_w60", "fv3sm_w60", "sortino_w60", "sharpe_fixed_w60", "sssnet_s42", "sssnet_s1", "sssnet_s123"]
CACHE = {a: f"sssnetw60_seed{a[8:]}" if a.startswith("sssnet_s") else a for a in ARMS}     # partition cache names
_G: dict = {}                                                                             # panel arrays shared with the workers


def load_panel() -> None:
    assert paths.PANEL is not None, "set CSA_PANEL_ROOT"
    px = pd.read_pickle(paths.PANEL / "prices.pkl"); caps = pd.read_pickle(paths.PANEL / "caps.pkl")
    mask = pd.read_pickle(paths.PANEL / "mask.pkl").astype(bool)
    raw = px.pct_change(fill_method=None); mkt = raw["SPY"]
    beta = raw.rolling(BETA_W).cov(mkt).div(mkt.rolling(BETA_W).var(), axis=0)
    ridx = pd.DatetimeIndex(raw.index); cols = list(raw.columns)
    Mk = mask.reindex_like(raw)
    _G.update(ridx=ridx, col={c: j for j, c in enumerate(cols)}, ccols=np.array(cols), calset=set(books.IDX),
              R0=np.ascontiguousarray((raw - beta.multiply(mkt, axis=0)).where(Mk).values, dtype=np.float64),
              R1=np.ascontiguousarray((raw - beta.shift(1).multiply(mkt, axis=0)).where(Mk).values, dtype=np.float64),
              R_pay=np.ascontiguousarray(raw.where(Mk).values, dtype=np.float64),
              capsA=caps.reindex(index=ridx, columns=cols).values)


def book_pnl(arm: str, R: np.ndarray, max_days: int | None = None) -> pd.Series:
    ridx, col, ccols, calset, R_pay, capsA = (_G[k] for k in ("ridx", "col", "ccols", "calset", "R_pay", "capsA"))
    cache = pickle.load(open(paths.PARTITIONS / f"{CACHE[arm]}.pkl", "rb")); rd = sorted(cache.keys()); out = {}
    for i in range(BETA_W + SIG_W, len(ridx) - 1):
        d = ridx[i]
        if d not in calset: continue
        if max_days and len(out) >= max_days: break
        row = capsA[i - 1]; fin = np.where(np.isfinite(row))[0]
        if len(fin) < 50: continue
        kk = min(500, len(fin)); top = fin[np.argpartition(row[fin], -kk)[-kk:]]; top = top[np.argsort(-row[top])]
        uni = ccols[top]; jU = np.array([col.get(x, -1) for x in uni]); ok = jU >= 0; uni, jU = uni[ok], jU[ok]
        lb = R[i - SIG_W + 1:i + 1][:, jU]; crv = R[i - CORR_W:i][:, jU]; nx = R[i + 1][jU]; nxp = R_pay[i + 1][jU]
        v = np.isfinite(lb).all(0) & np.isfinite(crv).all(0) & np.isfinite(nx) & np.isfinite(nxp)
        if v.sum() < 50: continue
        vi = np.where(v)[0]; tk = uni[vi]
        p = bisect.bisect_right(rd, d) - 1
        if p < 0 or (d - rd[p]).days > MAX_AGE: continue
        ent = cache[rd[p]]; t2l = {t: int(l) for t, l in zip(ent["universe"], ent["labels"])}
        outl = np.zeros(len(tk), dtype=np.int32); new = []
        for a_, t in enumerate(tk):
            if t in t2l: outl[a_] = t2l[t]
            else: new.append(a_)
        if new:
            X = crv[:, vi]; Xc = X - X.mean(0, keepdims=True); nr = np.sqrt((Xc * Xc).sum(0)); nr[nr == 0] = 1.0; V = Xc / nr
            Cn = V[:, new].T @ V; ar = np.arange(len(tk))
            for r_, ni in enumerate(new):
                bk, ba = 0, -np.inf
                for k in range(K):
                    m = np.where((outl == k) & (ar != ni))[0]
                    if not len(m): continue
                    af = float(Cn[r_, m].mean())
                    if af > ba: ba, bk = af, k
                outl[ni] = bk
        lbv = lb[:, vi]; cm = np.zeros_like(lbv)
        for k in range(K):
            m = outl == k
            if m.any(): cm[:, m] = lbv[:, m].mean(1, keepdims=True)
        sig = -(lbv - cm).sum(0); pm, nm = sig > 0, sig < 0
        w = np.zeros_like(sig); w[pm] = 1.0 / max(int(pm.sum()), 1); w[nm] = -1.0 / max(int(nm.sum()), 1)
        out[d] = float((w * nxp[vi]).sum())
    s = pd.Series(out).sort_index()
    return s if max_days else s.reindex(books.IDX)


def work(args):
    arm, max_days = args; t0 = time.time()
    return arm, book_pnl(arm, _G["R0"], max_days), book_pnl(arm, _G["R1"], max_days), time.time() - t0


def stats(s: pd.Series, X: pd.DataFrame) -> dict:
    m = pd.concat([s, X], axis=1).dropna(); y = m.iloc[:, 0].to_numpy(float)
    b, t, r2 = nw_ols(y, m.iloc[:, 1:].to_numpy(float))
    return dict(SR=np.sqrt(252) * s.mean() / s.std(ddof=1), vol=100 * np.sqrt(252) * s.std(ddof=1), alpha=252 * 100 * b[0], t=t[0])


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--arms", nargs="*", default=ARMS); ap.add_argument("--max-days", type=int, default=None)
    a = ap.parse_args(); load_panel()
    with Pool(int(os.environ.get("NPROC", "8"))) as pool:
        res = pool.map(work, [(arm, a.max_days) for arm in a.arms])
    S0, S1 = {}, {}
    print("== GATE lag0 vs the shipped rule books ==")
    for arm, s0, s1, dt in res:
        ref = books.rule_book(f"sssnetw60_seed{arm[8:]}" if arm.startswith("sssnet") else arm).reindex(s0.index)
        md = float((s0 - ref).abs().max()); print(f"  {arm:18s} max|diff| {md:.2e}  nan {int(s0.isna().sum())}  {dt:.0f}s", flush=True)
        S0[arm], S1[arm] = s0, s1
    if a.max_days or set(a.arms) != set(ARMS):
        print("partial run: nothing written"); return 0
    for S in (S0, S1):
        S["sssnet_w60"] = pd.concat([S.pop("sssnet_s42"), S.pop("sssnet_s1"), S.pop("sssnet_s123")], axis=1).mean(axis=1)
    for lag, S in (("lag0", S0), ("lag1", S1)):
        D = pd.DataFrame(S); D.index.name = "Date"
        compare_and_write(D.reset_index().assign(Date=lambda d: d.Date.dt.strftime("%Y-%m-%d")), f"beta_{lag}_pnl_cal6913.csv", ["Date"])
    X = load_ff(with_reversal=False)[FF6]; CL = [x for x in S0 if x not in ("k1", "random")]
    st0 = {x: stats(S0[x], X) for x in S0}; st1 = {x: stats(S1[x], X) for x in S1}
    for lag, st in (("lag0", st0), ("lag1", st1)):
        v = [st[x]["vol"] for x in CL]; al = [st[x]["alpha"] for x in CL]
        print(f"== {lag} == mean vol {np.mean(v):.4f} band {min(v):.2f}–{max(v):.2f} k1 {st['k1']['vol']:.2f} random {st['random']['vol']:.2f}; "
              f"mean alpha {np.mean(al):.2f} band {min(al):.2f}–{max(al):.2f} k1 {st['k1']['alpha']:.2f} random {st['random']['alpha']:.2f}")
    d = {x: st1[x]["SR"] - st0[x]["SR"] for x in S0}
    print(f"   max|dSR| {max(abs(x) for x in d.values()):.4f}; clusterizer dSR>0: {sum(d[x] > 0 for x in CL)}/12 mean {np.mean([d[x] for x in CL]):+.4f}; k1 {d['k1']:+.4f} random {d['random']:+.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
