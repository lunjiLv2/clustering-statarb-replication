"""Day-over-day position persistence of the rule-based books (§8 / A.x: contiguous positions correlate at
about 0.5 and about 30% of names change sign), for the 12 clusterizers and the two controls.

The rule engine's positions are rebuilt day by day with the same independent re-implementation as
analysis/beta_lag1_check.py (top-500 by lagged cap, 60-day CAPM residuals, 5-day signal, 21-day
correlation fill, partition age <= 10 days, +-1/n per side); for consecutive trading days the
correlation of the two weight vectors on the common names and the share of common names whose sign
changed are averaged over the common calendar.

Output: analysis/results/pos_autocorr_naive_cal6913.csv (arm, corr, flip in percent).
Run: ``CSA_PANEL_ROOT=... NPROC=8 python analysis/pos_autocorr_naive.py``  (~5 min on 8 cores)
"""
from __future__ import annotations
import argparse, bisect, os, pickle, sys, time
from multiprocessing import Pool
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books
from analysis._compare import compare_and_write

K, BETA_W, SIG_W, CORR_W, MAX_AGE = 30, 60, 5, 21, 10
ARMS = ["kmeans_ret", "agglo_complete", "agglo_avg", "pca_load", "spectral_unsigned", "sponge_w60", "gics", "k1", "random",
        "fv2a_w60", "fv3sm_w60", "sortino_w60", "sharpe_fixed_w60", "sssnet_w60"]
CACHE = {"sssnet_w60": "sssnetpre"}                    # output name -> partition cache (option B fixed partition)
_G: dict = {}


def load_panel() -> None:
    assert paths.PANEL is not None, "set CSA_PANEL_ROOT"
    px = pd.read_pickle(paths.PANEL / "prices.pkl"); caps = pd.read_pickle(paths.PANEL / "caps.pkl")
    mask = pd.read_pickle(paths.PANEL / "mask.pkl").astype(bool)
    raw = px.pct_change(fill_method=None); mkt = raw["SPY"]
    resid = (raw - raw.rolling(BETA_W).cov(mkt).div(mkt.rolling(BETA_W).var(), axis=0).multiply(mkt, axis=0)).where(mask.reindex_like(raw))
    ridx = pd.DatetimeIndex(resid.index)
    caps = caps.reindex(index=ridx, columns=resid.columns)
    _G.update(ridx=ridx, col={c: j for j, c in enumerate(resid.columns)}, R=np.ascontiguousarray(resid.values, dtype=np.float64),
              caps_np=caps.values, caps_cols=caps.columns.to_numpy(), calset=set(books.IDX))


def persistence(args) -> dict:
    arm, max_days = args; t0 = time.time()
    ridx, col, R, caps_np, caps_cols, calset = (_G[k] for k in ("ridx", "col", "R", "caps_np", "caps_cols", "calset"))
    cache = pickle.load(open(paths.PARTITIONS / f"{CACHE.get(arm, arm)}.pkl", "rb")); rd = sorted(cache.keys())
    prev = None; cors = []; flips = []; ndays = 0
    for i in range(BETA_W + SIG_W, len(ridx) - 1):
        dd = ridx[i]
        if dd not in calset: continue
        if max_days and ndays >= max_days: break
        row = caps_np[i - 1]; fin = np.where(np.isfinite(row))[0]
        if len(fin) < 50: continue
        kk = min(500, len(fin)); top = fin[np.argpartition(row[fin], -kk)[-kk:]]; top = top[np.argsort(-row[top])]
        uni = caps_cols[top]; jU = np.array([col.get(x, -1) for x in uni]); ok = jU >= 0
        uni, jU = uni[ok], jU[ok]
        lb = R[i - SIG_W + 1:i + 1][:, jU]; crv = R[i - CORR_W:i][:, jU]; nx = R[i + 1][jU]
        v = (np.isfinite(lb).all(0) & np.isfinite(crv).all(0) & np.isfinite(nx))
        if v.sum() < 50: continue
        vi = np.where(v)[0]; tk = uni[vi]
        p = bisect.bisect_right(rd, dd) - 1
        if p < 0 or (dd - rd[p]).days > MAX_AGE: continue
        ent = cache[rd[p]]
        X = crv[:, vi]; Xc = X - X.mean(0, keepdims=True); nr = np.sqrt((Xc * Xc).sum(0)); nr[nr == 0] = 1.0; V = Xc / nr
        t2l = {t: int(l) for t, l in zip(ent["universe"], ent["labels"])}
        out = np.zeros(len(tk), dtype=np.int32); new = []
        for a_, t in enumerate(tk):
            if t in t2l: out[a_] = t2l[t]
            else: new.append(a_)
        if new:
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
        sig = -(lbv - cm).sum(0); pm, nm = sig > 0, sig < 0
        w = np.zeros_like(sig); w[pm] = 1.0 / max(int(pm.sum()), 1); w[nm] = -1.0 / max(int(nm.sum()), 1)
        cur = pd.Series(w, index=tk); ndays += 1
        if prev is not None:
            u = cur.index.intersection(prev.index)
            a = cur.reindex(u).to_numpy(); b = prev.reindex(u).to_numpy()
            if a.std() > 0 and b.std() > 0: cors.append(float(np.corrcoef(a, b)[0, 1]))
            flips.append(float((np.sign(a) != np.sign(b)).mean()))
        prev = cur
    r = dict(arm=arm, corr=float(np.mean(cors)), flip=100 * float(np.mean(flips)))
    print(f"  {arm:18s} corr {r['corr']:.4f}  flip {r['flip']:.1f}%  days {ndays}  {time.time() - t0:.0f}s", flush=True)
    return r


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--arms", nargs="*", default=ARMS); ap.add_argument("--max-days", type=int, default=None)
    a = ap.parse_args(); load_panel()
    with Pool(int(os.environ.get("NPROC", "8"))) as pool:
        res = pool.map(persistence, [(arm, a.max_days) for arm in a.arms])
    D = pd.DataFrame(res)
    if a.max_days or set(a.arms) != set(ARMS):
        print("partial run: nothing written"); return 0
    r = D[~D.arm.isin(["k1", "random"])]
    print(f"12 clusterizers: corr {r['corr'].min():.3f}–{r['corr'].max():.3f} mean {r['corr'].mean():.3f}; flip {r['flip'].min():.1f}–{r['flip'].max():.1f} mean {r['flip'].mean():.1f}%")
    compare_and_write(D, "pos_autocorr_naive_cal6913.csv", ["arm"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
