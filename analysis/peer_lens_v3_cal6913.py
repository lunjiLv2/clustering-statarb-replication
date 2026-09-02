"""The peer lens (§6.3): the cross-sectional counterpart of the peer books, and the joint peer +
factor span.

For each common-calendar day and each partition (on the partition's own universe with a complete
252-day residual history): each name's peers are its top-20 names by trailing 21-day residual
correlation (strictly before the day); a regression on the trailing 60 days (ridge-stabilised,
λ = 1e-8·tr(G)/n) fits the name's day-d residual from its peers' and the fitted component is removed;
the partition's share of what remains is recorded (R2_peer), and again after also projecting out the
top-5 trailing-252-day principal components (R2_peer_pc5) or the FF6 loading span (R2_peer_ff6,
factors at shift 1). R2_clust is the share before any removal; ret_peer = R2_peer / R2_clust and ret_joint_pc =
R2_peer_pc5 / R2_clust. For the K = 1 control every share is zero by construction (one group:
the within-group and the total sum of squares coincide) and the computed values are round-off of
order 1e-17, so the ratios are undefined; they are written as NaN whenever |R2_clust| < 1e-8
(RATIO_FLOOR). The shipped file predates this rule and carries round-off ratios in the k1 row.

Output: analysis/results/peer_lens_cal6913.csv (one row per partition, sorted by R2_clust; the
SSSNET arm under its cache name ``sssnetpre``).

Run: ``CSA_PANEL_ROOT=/path/to/compat_panel python analysis/peer_lens_v3_cal6913.py [--smoke N] [--out PATH]``
(about 9 minutes at 8 threads; ``--smoke N`` runs N evenly spaced days and does not write; ``--out``
writes the full-precision table to PATH and only reports the comparison with the shipped file,
never overwriting it).
"""
from __future__ import annotations
import argparse, sys, time
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books
from analysis._compare import compare_and_write
from analysis.factors import FF6, load_ff
from analysis.lens_common import load_residuals, load_cache, ss_within

OOS = (pd.Timestamp("1997-05-23"), pd.Timestamp("2024-12-30"))
CORR_W, FIT_W, TOPK, PCW = 21, 60, 20, 252
STAGES = ["clust", "peer", "peer_pc5", "peer_ff6"]
RATIO_FLOOR = 1e-8            # |R2_clust| below this is round-off (K = 1): ratios undefined -> NaN


def pca_basis(H: np.ndarray, k: int) -> np.ndarray:
    """Top-k right singular vectors of the centred history H (T x n) via the T x T Gram matrix."""
    G = H @ H.T; w, U = np.linalg.eigh(G)
    o = np.argsort(w)[::-1][:k]; sv = np.sqrt(np.maximum(w[o], 0.0))
    return (H.T @ U[:, o]) / np.where(sv > 0, sv, 1.0)


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--smoke", type=int, default=0)
    ap.add_argument("--out", default=None, help="diagnostic: write the table here and do not touch the shipped file"); A = ap.parse_args()
    t0 = time.time()
    C = {n: load_cache(n) for n in paths.ARMS}
    use = set()
    for c in C.values():
        for e in c.values(): use.update(e["universe"])
    resid = load_residuals(columns=use, with_mask=True)
    print(f"[lens] residuals on the used subset {resid.shape}", flush=True)
    ridx = pd.DatetimeIndex(resid.index); col = {c: j for j, c in enumerate(resid.columns)}; pos = {d: i for i, d in enumerate(ridx)}
    Rv = resid.values.astype(np.float64); del resid
    ff_al = load_ff(with_reversal=False)[FF6].shift(1).reindex(ridx).values.astype(np.float64)
    names = sorted(C)
    common = None
    for c in C.values():
        ks = {pd.Timestamp(k) for k in c if OOS[0] <= pd.Timestamp(k) <= OOS[1]}
        common = ks if common is None else common & ks
    common = sorted(set(common) & set(books.IDX))
    if A.smoke: common = common[::max(1, len(common) // A.smoke)][:A.smoke]
    print(f"{len(names)} partitions, {len(common)} days  setup {time.time() - t0:.0f}s", flush=True)
    acc = {n: {s: [] for s in STAGES} for n in names}
    for di, d in enumerate(common):
        i = pos.get(d)
        if i is None or i < PCW: continue
        bases = {}
        for n in names:
            ent = C[n][d]; uni = list(ent["universe"])
            tk = [t for t in uni if t in col]
            lab_all = np.asarray([int(l) for t, l in zip(uni, ent["labels"]) if t in col])
            j = np.asarray([col[t] for t in tk])
            x = Rv[i, j]; hist = Rv[i - PCW:i][:, j]
            ok = np.isfinite(x) & np.isfinite(hist).all(axis=0)
            if ok.sum() < 100: continue
            x, lab, jj = x[ok], lab_all[ok], j[ok]
            sst = float(((x - x.mean()) ** 2).sum())
            if sst <= 0: continue
            rc = 1 - ss_within(x, lab) / sst
            key = tuple(jj.tolist())
            if key not in bases:
                Hc = Rv[i - PCW:i][:, jj]; Hc = Hc - Hc.mean(axis=0, keepdims=True)
                V = pca_basis(Hc, 5)
                Fw = ff_al[i - PCW:i]; Fw = Fw - Fw.mean(axis=0, keepdims=True)
                B6 = np.linalg.lstsq(Fw, Hc, rcond=None)[0]
                Qf, _ = np.linalg.qr(B6.T)
                W21 = Rv[i - CORR_W:i][:, jj]; W21c = W21 - W21.mean(axis=0, keepdims=True)
                sd = W21c.std(axis=0); sd[sd == 0] = 1
                Cm = (W21c / sd).T @ (W21c / sd) / CORR_W
                np.fill_diagonal(Cm, -np.inf)
                peers = np.argsort(Cm, axis=1)[:, -TOPK:]
                W60 = Rv[i - FIT_W:i][:, jj]; W60c = W60 - W60.mean(axis=0, keepdims=True)
                G = W60c.T @ W60c
                nloc = len(jj); xhat = np.zeros(nloc); xcen = x - x.mean()
                lam = 1e-8 * np.trace(G) / nloc
                for s_ in range(nloc):
                    p = peers[s_]
                    Gpp = G[np.ix_(p, p)] + lam * np.eye(TOPK)
                    b = np.linalg.solve(Gpp, G[p, s_])
                    xhat[s_] = float(b @ xcen[p])
                bases[key] = (V, Qf, xhat)
            V, Qf, xhat = bases[key]
            xcen = x - x.mean(); xo = xcen - xhat

            def stagestat(vec):
                ssv = float(((vec - vec.mean()) ** 2).sum())
                return 1 - ss_within(vec, lab) / ssv if ssv > 0 else np.nan
            acc[n]["clust"].append(rc)
            acc[n]["peer"].append(stagestat(xo))
            xo1 = xo - V @ (V.T @ xo); acc[n]["peer_pc5"].append(stagestat(xo1))
            xo2 = xo - Qf @ (Qf.T @ xo); acc[n]["peer_ff6"].append(stagestat(xo2))
        if di % 500 == 0: print(f"  day {di}/{len(common)} ({time.time() - t0:.0f}s)", flush=True)
    rows = []
    for n in names:
        r = {"partition": n, "days": len(acc[n]["clust"])}
        for s_ in STAGES: r[f"R2_{s_}"] = float(np.nanmean(acc[n][s_]))
        defined = abs(r["R2_clust"]) >= RATIO_FLOOR
        r["ret_peer"] = r["R2_peer"] / r["R2_clust"] if defined else np.nan
        r["ret_joint_pc"] = r["R2_peer_pc5"] / r["R2_clust"] if defined else np.nan
        rows.append(r)
    D = pd.DataFrame(rows).sort_values("R2_clust", ascending=False)
    print(D.round(4).to_string(index=False)); print(f"total {time.time() - t0:.0f}s")
    if A.smoke: print("smoke run: not written")
    elif A.out:
        D.to_csv(A.out, index=False); print(f"diagnostic table -> {A.out} (shipped file untouched)")
        ref = pd.read_csv(paths.RESULTS / "peer_lens_cal6913.csv"); j = D.merge(ref, on="partition", suffixes=("", "_ref"))
        for c in [c for c in ref.columns if c != "partition"]:
            dd = (j[c] - j[c + "_ref"]).abs(); print(f"  {c:12s} max |diff| {dd.max():.2e} ({j.loc[dd.idxmax(), 'partition']}); NaN in new: {int(j[c].isna().sum())}")
    else: compare_and_write(D, "peer_lens_cal6913.csv", ["partition"])


if __name__ == "__main__":
    main()
