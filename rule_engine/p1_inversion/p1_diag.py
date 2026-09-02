#!/usr/bin/env python3
"""
p1_diag.py -- diagnostics that make the SR table interpretable + honest.
=========================================================================
Three additions to the core inversion tables:

(D1) GLOBAL cross-sectional MR baseline (K=1, single cluster).  The unsupervised
     kmeans/agglo caches are DEGENERATE (one 110-132 stock cluster + a tail of
     singletons; Neff 7-11, not 30).  A K=1 partition demeans the whole universe
     each day => plain cross-sectional mean reversion.  If K=1 ~ kmeans/agglo,
     their "win" is cross-sectional MR, not 30-cluster structure.  This is also
     the canonical "without clustering / single global group" ablation.

(D2) OLD-panel pass (rb_old) for every partition with the IDENTICAL engine, so
     the split-fix delta (NEW - OLD) is measured holding engine + cadence fixed.
     Directly answers "does the split-fix change the inversion?".

(D3) Cluster-structure + clustering-quality table: sizes, effective # clusters,
     >50 / <5 gate flags (CLAUDE.md), mean ARI vs the SPONGE partition and vs
     GICS sector (from econ_interpretation membership snapshots).

Writes p1_global_baseline.csv, p1_oldnew_split.csv, p1_cluster_structure.csv.
"""
import os
import glob
import pickle

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score

import p1_lib as L

OUT = os.path.dirname(os.path.abspath(__file__))
ECON = os.path.join(L.ROOT, "JFEC_workspace", "econ_interpretation")
ALLP = L.TRADING_DRIVEN + L.UNSUPERVISED


def synth_global_cache(ref_cache: dict) -> dict:
    """K=1 cache: same universes/dates as SSSNET, all labels 0 (one cluster)."""
    g = {}
    for d, ent in ref_cache.items():
        g[d] = {"universe": ent["universe"],
                "labels": np.zeros(len(ent["universe"]), dtype=np.int32)}
    return g


def load_sector_map() -> dict:
    """ticker -> GICS-ish sector, union over econ_interpretation membership_*.csv."""
    m = {}
    for f in glob.glob(os.path.join(ECON, "membership_*.csv")):
        df = pd.read_csv(f)
        col = "sector_sp1500" if "sector_sp1500" in df.columns else df.columns[-1]
        for _, r in df.iterrows():
            s = r.get(col)
            if isinstance(s, str) and s and s.lower() != "nan":
                m[str(r["ticker"])] = s
    return m


def main():
    z, cols, ridx = L.load_resid()
    col = {c: j for j, c in enumerate(cols)}
    RN = L.masked_panel(z, "rb_new")
    RO = L.masked_panel(z, "rb_old")
    caps = pd.read_pickle(L.CAPS_OLD)
    caps_np, caps_cols = caps.values, caps.columns.to_numpy()

    obj = pickle.load(open(os.path.join(OUT, "p1_streams.pkl"), "rb"))
    S = obj["streams"]

    sss_cache, _, _ = L.load_cache("sssnet")

    # -------- D1: global K=1 cross-sectional MR (new + old) --------
    print("[D1] global K=1 cross-sectional MR baseline ...")
    gcache = synth_global_cache(sss_cache)
    g_new = L.naive_stream(gcache, "labels", ridx, col, caps_np, caps_cols,
                           R_trade=RN, R_affil=RN)
    g_old = L.naive_stream(gcache, "labels", ridx, col, caps_np, caps_cols,
                           R_trade=RO, R_affil=RO)
    S["global_K1"] = g_new
    grow = dict(stream="global_K1_xsectMR", SR_new=round(L.sharpe(g_new.values), 4),
                SR_old=round(L.sharpe(g_old.values), 4))
    for era, a, b in L.ERAS:
        grow[era] = round(L.era_sharpe(g_new, a, b), 4)
    # rho of kmeans/agglo/pca naive vs global K1 (does the "win" collapse to xsect MR?)
    grows = [grow]
    for nm in ["kmeans", "agglo", "pca", "sssnet", "sponge", "sortino"]:
        idx = S[nm].index.intersection(g_new.index)
        r = float(np.corrcoef(S[nm].reindex(idx).values, g_new.reindex(idx).values)[0, 1])
        grows.append(dict(stream=f"rho({nm}_naive, global_K1)", SR_new=round(r, 4),
                          SR_old=np.nan))
    pd.DataFrame(grows).to_csv(os.path.join(OUT, "p1_global_baseline.csv"), index=False)
    print(f"     global K1: SR_new={L.sharpe(g_new.values):.4f}  SR_old={L.sharpe(g_old.values):.4f}")
    for nm in ["kmeans", "agglo", "pca"]:
        idx = S[nm].index.intersection(g_new.index)
        r = float(np.corrcoef(S[nm].reindex(idx).values, g_new.reindex(idx).values)[0, 1])
        print(f"     rho({nm}, global_K1) = {r:.4f}")

    # -------- D2: OLD-panel pass + split-fix delta --------
    print("[D2] OLD-panel pass (rb_old) for split-fix delta ...")
    rows = []
    for nm in ALLP:
        cache, key, cadence = L.load_cache(nm)
        s_old = L.naive_stream(cache, key, ridx, col, caps_np, caps_cols,
                               R_trade=RO, R_affil=RO)
        s_new = S[nm]
        idx = s_old.index.intersection(s_new.index)
        xo, xn = s_old.reindex(idx).values, s_new.reindex(idx).values
        # paired CBB on delta NEW - OLD
        T = len(idx)
        rng = np.random.default_rng(L.SEED)
        dd = np.empty(500)
        for i in range(500):
            bi = L.block_boot_indices(T, rng, 21)
            ao, an = xo[bi], xn[bi]
            So = ao.mean() / ao.std() * L.ANN if ao.std() > 0 else np.nan
            Sn = an.mean() / an.std() * L.ANN if an.std() > 0 else np.nan
            dd[i] = Sn - So
        rows.append(dict(partition=nm, cadence=cadence,
                         SR_old=round(L.sharpe(xo), 4), SR_new=round(L.sharpe(xn), 4),
                         split_delta=round(L.sharpe(xn) - L.sharpe(xo), 4),
                         ci_lo=round(float(np.nanpercentile(dd, 2.5)), 4),
                         ci_hi=round(float(np.nanpercentile(dd, 97.5)), 4),
                         p_delta_lt0=round(float(np.mean(dd < 0)), 3),
                         pnl_rho_oldnew=round(float(np.corrcoef(xo, xn)[0, 1]), 4)))
        print(f"     {nm:16s} OLD={L.sharpe(xo):+.4f} NEW={L.sharpe(xn):+.4f} "
              f"dSplit={L.sharpe(xn)-L.sharpe(xo):+.4f}")
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "p1_oldnew_split.csv"), index=False)

    # -------- D3: cluster structure + ARI(SPONGE), ARI(GICS) --------
    print("[D3] cluster-structure + ARI ...")
    sec = load_sector_map()
    print(f"     sector map: {len(sec)} tickers")
    srows = []
    for nm in ALLP:
        cache, key, cadence = L.load_cache(nm)
        dates = sorted(cache.keys())
        samp = dates[::max(1, len(dates) // 80)]
        nc, mx, mn, med, fmax, g50, l5, neff, ari_sp, ari_gics = ([] for _ in range(10))
        for d in samp:
            lab = np.asarray(cache[d][key]); uni = list(cache[d]["universe"]); N = len(lab)
            vals, cnts = np.unique(lab, return_counts=True)
            nc.append(len(vals)); mx.append(cnts.max()); mn.append(cnts.min())
            med.append(np.median(cnts)); fmax.append(cnts.max() / N)
            g50.append(int((cnts > 50).sum())); l5.append(int((cnts < 5).sum()))
            pk = cnts / N; neff.append(1.0 / (pk ** 2).sum())
            # ARI vs SPONGE at nearest 5d refit date <= d
            pos = np.searchsorted([x for x in sorted(sss_cache.keys())], d, side="right") - 1
            if pos >= 0:
                sd = sorted(sss_cache.keys())[pos]
                sp_ent = sss_cache[sd]
                sp_map = {t: int(l) for t, l in zip(sp_ent["universe"], sp_ent["sponge_labels"])}
                common = [t for t in uni if t in sp_map]
                if len(common) > 20:
                    a = np.array([int(lab[uni.index(t)]) for t in common])
                    b = np.array([sp_map[t] for t in common])
                    ari_sp.append(adjusted_rand_score(a, b))
            # ARI vs GICS sector
            csec = [(int(lab[i]), sec[t]) for i, t in enumerate(uni) if t in sec]
            if len(csec) > 20:
                a = np.array([x[0] for x in csec])
                sset = {s: k for k, s in enumerate(sorted({x[1] for x in csec}))}
                b = np.array([sset[x[1]] for x in csec])
                ari_gics.append(adjusted_rand_score(a, b))
        srows.append(dict(partition=nm, cadence=cadence,
                          n_clusters=round(np.mean(nc), 1), max_size=round(np.mean(mx), 1),
                          min_size=round(np.mean(mn), 1), median_size=round(np.mean(med), 1),
                          frac_in_largest=round(np.mean(fmax), 3),
                          n_clusters_gt50=round(np.mean(g50), 2),
                          n_clusters_lt5=round(np.mean(l5), 2),
                          eff_n_clusters=round(np.mean(neff), 1),
                          ari_vs_sponge=round(np.mean(ari_sp), 3) if ari_sp else np.nan,
                          ari_vs_gics=round(np.mean(ari_gics), 3) if ari_gics else np.nan))
    cs = pd.DataFrame(srows)
    cs.to_csv(os.path.join(OUT, "p1_cluster_structure.csv"), index=False)
    pd.set_option("display.width", 200, "display.max_columns", 30)
    print(cs.to_string(index=False))
    print("\nwrote p1_global_baseline.csv, p1_oldnew_split.csv, p1_cluster_structure.csv")


if __name__ == "__main__":
    main()
