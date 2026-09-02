"""The factor lens (§6.1; fig:lens_curve, fig:ff_curve): what share of a day's cross-sectional
residual variance demeaning within a partition's groups removes, and how much of that share survives
projecting out a benchmark span.

For each partition and each common-calendar day, on the partition's own universe (names with a
complete trailing 252-day residual history; at least 100): R2_clust = 1 − SS(x − group mean) /
SS(x − grand mean) for the day's SPY-CAPM residuals x; R2_after_mPC = the same share after x is
regressed on the loadings of the leading m principal components of the trailing 252 days (strictly
before the day), m = 1, 3, 5; R2_after_{CAPM,FF3,FF5,FF6} = the same after projecting x out of the
span of the names' factor betas on the same window (factors at shift 1); m_match = the smallest m at
which a rank-m PCA reconstruction explains at least R2_clust (NaN when m = 30 does not suffice).
Each column is the mean over days; ``retention`` and ``ret_*`` divide by R2_clust; ``dof_floor`` is
(K − 1)/(N − 1), the share a random partition removes by degrees of freedom alone.

Output: analysis/results/lens_v3_full_stages_cal6913.csv, one row per arm in the manuscript's Sharpe
order (the SSSNET arm as ``sssnet_w60``).

Run: ``CSA_PANEL_ROOT=/path/to/compat_panel python analysis/verify_lens.py [--arms ...] [--stride 1]``
(full sample: a few minutes per arm; ``--stride 100`` for a smoke test, which compares but never writes).
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis import books
from analysis._compare import compare_and_write
from analysis.factors import FF6, load_ff
from analysis.lens_common import W, SHARPE_ORDER, load_residuals, load_cache, r2_loop as r2

M = 5
CALSET = set(books.IDX)


def one(arm: str, Rv, cols, pos, FFV, stride: int) -> dict:
    d = load_cache(arm)
    days = [k for k in sorted(d) if pd.Timestamp(k) in CALSET][::stride]
    a_, b_, nn, kk = [], [], [], []
    PC_R2 = {1: [], 3: []}; FF_R2 = {k: [] for k in ("CAPM", "FF3", "FF5", "FF6")}; MHIT = []
    for dt in days:
        i = pos.get(pd.Timestamp(dt))
        if i is None or i < W: continue
        e = d[dt]; uni = list(e["universe"])
        tk = [t for t in uni if t in cols]
        if len(tk) < 100: continue
        lab = np.array([int(l) for t, l in zip(uni, e["labels"]) if t in cols])
        j = np.array([cols[t] for t in tk])
        x = Rv[i, j]; hist = Rv[i - W:i][:, j]
        ok = np.isfinite(x) & np.isfinite(hist).all(axis=0)
        if ok.sum() < 100: continue
        x, lab, hist = x[ok], lab[ok], hist[:, ok]
        rc_d = r2(x, lab)
        a_.append(rc_d); nn.append(ok.sum()); kk.append(len(np.unique(lab)))
        H = hist - hist.mean(0, keepdims=True)
        _, _, Vt = np.linalg.svd(H, full_matrices=False)
        L = Vt[:M].T
        xr = x - L @ np.linalg.lstsq(L, x, rcond=None)[0]
        b_.append(r2(xr, lab))
        xc = x - x.mean(); sst = float((xc * xc).sum())
        for m in (1, 3):
            Lm = Vt[:m].T
            PC_R2[m].append(r2(x - Lm @ np.linalg.lstsq(Lm, x, rcond=None)[0], lab))
        hit = np.nan
        for m in range(1, min(30, Vt.shape[0]) + 1):
            P = Vt[:m]; rec = P.T @ (P @ xc)
            if sst > 0 and 1.0 - float(((xc - rec) ** 2).sum()) / sst >= rc_d:
                hit = m; break
        MHIT.append(hit)
        Fw = FFV[i - W:i]
        if np.isfinite(Fw).all():
            Fw = Fw - Fw.mean(0, keepdims=True)
            for nm_, k_ in (("CAPM", 1), ("FF3", 3), ("FF5", 5), ("FF6", 6)):
                B = np.linalg.lstsq(Fw[:, :k_], H, rcond=None)[0]
                Q, _ = np.linalg.qr(B.T)
                FF_R2[nm_].append(r2(xc - Q @ (Q.T @ xc), lab))
    rc, rp = np.nanmean(a_), np.nanmean(b_)
    o = dict(arm=arm, days=len(a_), R2_clust=rc, R2_after_5PC=rp, retention=rp / rc if rc else np.nan,
             eff_K=float(np.mean(kk)), lens_N=float(np.mean(nn)), dof_floor=(np.mean(kk) - 1) / (np.mean(nn) - 1),
             excess_over_floor=rc - (np.mean(kk) - 1) / (np.mean(nn) - 1))
    for m in (1, 3):
        o[f"R2_after_{m}PC"] = float(np.nanmean(PC_R2[m])); o[f"ret_{m}PC"] = o[f"R2_after_{m}PC"] / rc if rc else np.nan
    for nm_ in ("CAPM", "FF3", "FF5", "FF6"):
        v_ = FF_R2[nm_]
        o[f"R2_after_{nm_}"] = float(np.nanmean(v_)) if v_ else np.nan
        o[f"ret_{nm_}"] = o[f"R2_after_{nm_}"] / rc if (v_ and rc) else np.nan
    mh = np.asarray(MHIT, dtype=float)
    o["m_match"] = float(np.nanmean(mh)); o["never_matched_pct"] = 100.0 * float(np.isnan(mh).mean()); o["ff_days"] = len(FF_R2["FF6"])
    print(f"  {arm:18s} n={o['days']:5d}  R2_clust {rc:.4f}  after 5 PCs {rp:.4f}  retention {o['retention']:.1%}  "
          f"1PC {o['ret_1PC']:.1%} 3PC {o['ret_3PC']:.1%} | FF6 {o['ret_FF6']:.1%}  m_match {o['m_match']:.2f}  K {o['eff_K']:.2f}  N {o['lens_N']:.0f}", flush=True)
    return o


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--arms", nargs="*", default=SHARPE_ORDER); ap.add_argument("--stride", type=int, default=1)
    a = ap.parse_args()
    res = load_residuals()
    cols = {c: j for j, c in enumerate(res.columns)}; Rv = res.to_numpy(np.float64); idx = res.index; pos = {d: i for i, d in enumerate(idx)}
    FFV = load_ff(with_reversal=False)[FF6].shift(1).reindex(idx).to_numpy(np.float64)
    del res
    print(f"[lens] residual panel {Rv.shape}; stride {a.stride}", flush=True)
    D = pd.DataFrame([one(arm, Rv, cols, pos, FFV, a.stride) for arm in a.arms])
    if a.stride == 1: compare_and_write(D, "lens_v3_full_stages_cal6913.csv", ["arm"])
    else:
        ref = pd.read_csv(__import__("paths").RESULTS / "lens_v3_full_stages_cal6913.csv").set_index("arm")
        for _, r in D.iterrows(): print(f"  smoke {r['arm']}: R2_clust {r['R2_clust']:.5f} (full-sample {ref.loc[r['arm'], 'R2_clust']:.5f}); not written")


if __name__ == "__main__":
    main()
