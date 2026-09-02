"""The factor lens continued (§6.1): the principal-component sweep up to m = 10 with the excess over
the degrees-of-freedom floor at every m, the characteristics lens, and block-bootstrap standard errors.

Same universe and days as ``verify_lens.py`` (each partition's own names with a complete 252-day
history, common calendar). For every arm: R2_clust and R2_after_mPC for m = 1, 3, 5, 10 (loadings of
the trailing 252 days, strictly before the day); the characteristics lens with Z = size (log cap),
momentum (252−21), 21-day reversal and 60-day volatility, cross-sectionally standardised (missing → 0):
the share span(Z) explains on its own (R2_expl_spanZ) and the partition's share of what is left
(R2_after_spanZ, ret_spanZ); excess_m* = share minus the floor (K − 1)/(N − 1); se_* = circular
block-bootstrap standard errors of the day means (block 63, 2,000 draws, seed 20260813).

Output: analysis/results/lens_extras_v3_cal6913.csv (one row per arm, Sharpe order, SSSNET as
``sssnet_w60``).

Run: ``CSA_PANEL_ROOT=/path/to/compat_panel python analysis/lens_extras_v3.py [--arms ...] [--stride 1]``
"""
from __future__ import annotations
import argparse, sys, time
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books
from analysis._compare import compare_and_write
from analysis.lens_common import W, SHARPE_ORDER, load_residuals, load_cache, ss_within, r2_bincount as r2

MS = [1, 3, 5, 10]
BLOCK, NBOOT, SEED = 63, 2000, 20260813
CALSET = set(books.IDX)


def bboot(v, rng: np.random.Generator) -> float:
    """Standard error of the mean of ``v`` by circular block bootstrap."""
    v = np.asarray(v, float); v = v[np.isfinite(v)]; n = len(v)
    if n <= BLOCK: return np.nan
    nb = int(np.ceil(n / BLOCK))
    st = rng.integers(0, n - BLOCK + 1, size=(NBOOT, nb))
    idx = (st[:, :, None] + np.arange(BLOCK)[None, None, :]).reshape(NBOOT, -1)[:, :n]
    return float(v[idx].mean(axis=1).std(ddof=1))


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--arms", nargs="*", default=SHARPE_ORDER); ap.add_argument("--stride", type=int, default=1)
    a = ap.parse_args()
    res, raw, px = load_residuals(keep_prices=True)
    ridx = res.index; cols = {c: j for j, c in enumerate(res.columns)}; pos = {d: i for i, d in enumerate(ridx)}
    Rv = res.to_numpy(np.float64)
    caps = pd.read_pickle(paths.PANEL / "caps.pkl").reindex(index=ridx, columns=res.columns)
    px = px.reindex(index=ridx, columns=res.columns)
    CH = [np.log(caps.where(caps > 0)).values,                       # size
          (px.shift(21) / px.shift(252) - 1).values,                 # momentum 252-21
          (px / px.shift(21) - 1).values,                            # reversal 21d
          raw.reindex(columns=res.columns).rolling(60).std().values]  # volatility 60d
    del px, caps, raw, res
    print(f"[extras] characteristics built, panel {Rv.shape}", flush=True)
    rows, t0 = [], time.time()
    for arm in a.arms:
        cache = load_cache(arm)
        days = [d for d in sorted(cache) if pd.Timestamp(d) in CALSET][::a.stride]
        acc = {k: [] for k in ["rc", "expl_Z", "inc_Z", "K", "N"] + [f"pc{m}" for m in MS]}
        for d in days:
            i = pos.get(pd.Timestamp(d))
            if i is None or i < W: continue
            e = cache[d]; uni = list(e["universe"])
            tk = [t for t in uni if t in cols]
            if len(tk) < 100: continue
            lab_all = np.array([int(l) for t, l in zip(uni, e["labels"]) if t in cols])
            j = np.array([cols[t] for t in tk])
            x = Rv[i, j]; hist = Rv[i - W:i][:, j]
            ok = np.isfinite(x) & np.isfinite(hist).all(axis=0)
            if ok.sum() < 100: continue
            x, lab, jj = x[ok], lab_all[ok], j[ok]
            sst = float(((x - x.mean()) ** 2).sum())
            if sst <= 0: continue
            acc["rc"].append(r2(x, lab)); acc["K"].append(len(np.unique(lab))); acc["N"].append(len(x))
            H = hist[:, ok] - hist[:, ok].mean(0, keepdims=True)
            _, _, Vt = np.linalg.svd(H, full_matrices=False)
            for m in MS:
                L = Vt[:m].T
                acc[f"pc{m}"].append(r2(x - L @ np.linalg.lstsq(L, x, rcond=None)[0], lab))
            Zd = np.column_stack([ch[i, jj] for ch in CH])
            Zs = np.where(np.isfinite(Zd), Zd, np.nan)
            mu = np.nanmean(Zs, 0); sd = np.nanstd(Zs, 0); sd[sd == 0] = 1
            Zs = np.where(np.isfinite((Zs - mu) / sd), (Zs - mu) / sd, 0.0)
            Q, _ = np.linalg.qr(Zs)
            xc = x - x.mean(); xo = xc - Q @ (Q.T @ xc)
            acc["expl_Z"].append(1 - float((xo * xo).sum()) / sst)
            sso = float(((xo - xo.mean()) ** 2).sum())
            acc["inc_Z"].append(1 - ss_within(xo, lab) / sso if sso > 0 else np.nan)
        rng = np.random.default_rng(SEED)
        rc = float(np.nanmean(acc["rc"])); Kb = float(np.mean(acc["K"])); Nb = float(np.mean(acc["N"])); floor = (Kb - 1) / (Nb - 1)
        r = dict(arm=arm, days=len(acc["rc"]), R2_clust=rc, eff_K=Kb, lens_N=Nb, dof_floor=floor,
                 se_R2_clust=bboot(acc["rc"], rng),
                 R2_expl_spanZ=float(np.nanmean(acc["expl_Z"])), se_expl_spanZ=bboot(acc["expl_Z"], np.random.default_rng(SEED)),
                 R2_after_spanZ=float(np.nanmean(acc["inc_Z"])), ret_spanZ=float(np.nanmean(acc["inc_Z"])) / rc if rc > 0 else np.nan,
                 excess_m0=rc - floor)
        for m in MS:
            v = float(np.nanmean(acc[f"pc{m}"]))
            r[f"R2_after_{m}PC"] = v; r[f"ret_{m}PC"] = v / rc if rc > 0 else np.nan; r[f"excess_m{m}"] = v - floor
            r[f"se_{m}PC"] = bboot(acc[f"pc{m}"], np.random.default_rng(SEED + m))
        rows.append(r)
        print(f"  {arm:18s} n={r['days']:5d} R2 {rc:.4f}  1PC {r['ret_1PC']:.1%} 3PC {r['ret_3PC']:.1%} 5PC {r['ret_5PC']:.1%} "
              f"10PC {r['ret_10PC']:.1%} | spanZ expl {r['R2_expl_spanZ']:.4f} ret {r['ret_spanZ']:.1%} | excess@10 {r['excess_m10']:+.5f}  ({time.time() - t0:.0f}s)", flush=True)
    D = pd.DataFrame(rows)
    if a.stride == 1: compare_and_write(D, "lens_extras_v3_cal6913.csv", ["arm"])
    else: print("smoke run (stride > 1): not written")


if __name__ == "__main__":
    main()
