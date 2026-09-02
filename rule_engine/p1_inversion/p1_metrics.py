#!/usr/bin/env python3
"""
p1_metrics.py -- STEPS 3-4: SR/eras, paired-CBB CIs, paired-delta table, rho.
=============================================================================
Reads p1_streams.pkl (clean-panel naive PnL for every partition) and produces:

  p1_sr_eras.csv        full + per-era gross Sharpe for every stream, with
                        95% CBB CIs on the full-sample SR.
  p1_paired_deltas.csv  paired-CBB delta of each partition's naive SR vs the two
                        anchors (SSSNET-naive, SPONGE-naive) on COMMON days, with
                        95% CIs and P(delta>0) -- this answers the inversion Q.
  p1_pnl_rho.csv        PnL correlation of each trading-driven naive stream vs
                        SSSNET-naive, SPONGE-naive (clean, same convention) and
                        vs the campaign EW3 head ensemble + K30 SSSNET-head
                        (OLD-panel head convention -- the 0.026 orthogonality).
  p1_cadence_effect.csv native-1d vs 5d-aligned SR for the three 1d caches.

All CBB: 21d circular blocks, 500 draws, seed 42 (HOUSE). Deltas are PAIRED:
the same resampled day-index is applied to both streams each draw, so the CI is
on the difference of Sharpes, not the difference of independent CIs.
"""
import os
import pickle
import itertools

import numpy as np
import pandas as pd

import p1_lib as L

OUT = os.path.dirname(os.path.abspath(__file__))
ANN = L.ANN

# canonical display order
TD_NATIVE = ["sortino", "sharpe_fixed", "fv3sm", "spectral_sortino"]
TD_5D = ["sortino@5d", "sharpe_fixed@5d", "fv3sm@5d", "spectral_sortino"]
UNSUP = ["sssnet", "sponge", "kmeans", "agglo", "pca"]


def align(series_dict, names):
    """Common-date aligned (T,n) matrix + index for a set of streams."""
    idx = None
    for nm in names:
        idx = series_dict[nm].index if idx is None else idx.intersection(series_dict[nm].index)
    idx = idx.sort_values()
    mat = np.column_stack([series_dict[nm].reindex(idx).values for nm in names])
    return mat, idx


def paired_delta_cbb(a: pd.Series, b: pd.Series, n_boot=500, block=21, seed=L.SEED):
    """Paired CBB on SR(a)-SR(b) over common days. Returns dict of stats."""
    idx = a.index.intersection(b.index).sort_values()
    xa, xb = a.reindex(idx).values, b.reindex(idx).values
    T = len(idx)
    rng = np.random.default_rng(seed)
    d = np.empty(n_boot)
    sa = np.empty(n_boot)
    sb = np.empty(n_boot)
    for i in range(n_boot):
        bi = L.block_boot_indices(T, rng, block)
        ra, rb = xa[bi], xb[bi]
        Sa = ra.mean() / ra.std() * ANN if ra.std() > 0 else np.nan
        Sb = rb.mean() / rb.std() * ANN if rb.std() > 0 else np.nan
        sa[i], sb[i], d[i] = Sa, Sb, Sa - Sb
    pt = L.sharpe(xa) - L.sharpe(xb)
    return dict(n_days=T, sr_a=L.sharpe(xa), sr_b=L.sharpe(xb), delta=pt,
                lo=float(np.nanpercentile(d, 2.5)), hi=float(np.nanpercentile(d, 97.5)),
                p_gt0=float(np.mean(d > 0)), boot_sd=float(np.nanstd(d)),
                rho=float(np.corrcoef(xa, xb)[0, 1]))


def main():
    obj = pickle.load(open(os.path.join(OUT, "p1_streams.pkl"), "rb"))
    S = obj["streams"]
    meta = obj["meta"]
    allnames = list(S.keys())

    # ---------------------------------------------------------------- SR + eras + CBB CI
    # CBB CI on each stream's own full-sample SR (unpaired, own day set)
    rows = []
    for nm in allnames:
        s = S[nm]
        mat = s.values.reshape(-1, 1)
        sr_ci, _, _ = L.paired_cbb(mat, [nm])
        pt, lo, hi, sd = sr_ci[nm]
        row = dict(stream=nm, view=meta[nm]["view"], native_cadence=meta[nm]["cadence_native"],
                   n_days=len(s), SR_full=round(pt, 4), ci_lo=round(lo, 4),
                   ci_hi=round(hi, 4), boot_sd=round(sd, 4))
        for era, a, b in L.ERAS:
            row[era] = round(L.era_sharpe(s, a, b), 4)
        rows.append(row)
    sr_df = pd.DataFrame(rows)
    sr_df.to_csv(os.path.join(OUT, "p1_sr_eras.csv"), index=False)

    # ---------------------------------------------------------------- paired deltas vs anchors
    anchors = {"vs_SSSNET": S["sssnet"], "vs_SPONGE": S["sponge"]}
    drows = []
    # every partition (native + aligned) vs each anchor
    cand = [n for n in allnames if n not in ("sssnet",)]  # keep sponge too (vs SSSNET)
    for nm in allnames:
        for aname, aser in anchors.items():
            if S[nm] is aser:
                continue
            st = paired_delta_cbb(S[nm], aser)
            drows.append(dict(stream=nm, view=meta[nm]["view"], anchor=aname,
                              n_days=st["n_days"], SR=round(st["sr_a"], 4),
                              SR_anchor=round(st["sr_b"], 4), delta=round(st["delta"], 4),
                              ci_lo=round(st["lo"], 4), ci_hi=round(st["hi"], 4),
                              p_delta_gt0=round(st["p_gt0"], 3), boot_sd=round(st["boot_sd"], 4),
                              pnl_rho=round(st["rho"], 4)))
    del_df = pd.DataFrame(drows)
    del_df.to_csv(os.path.join(OUT, "p1_paired_deltas.csv"), index=False)

    # ---------------------------------------------------------------- cadence effect (1d vs 5d)
    crows = []
    for base in ["sortino", "sharpe_fixed", "fv3sm"]:
        st = paired_delta_cbb(S[base], S[base + "@5d"])
        crows.append(dict(partition=base, SR_1d=round(st["sr_a"], 4),
                          SR_5d=round(st["sr_b"], 4), delta_1d_minus_5d=round(st["delta"], 4),
                          ci_lo=round(st["lo"], 4), ci_hi=round(st["hi"], 4),
                          p_gt0=round(st["p_gt0"], 3), pnl_rho=round(st["rho"], 4),
                          n_days=st["n_days"]))
    cad_df = pd.DataFrame(crows)
    cad_df.to_csv(os.path.join(OUT, "p1_cadence_effect.csv"), index=False)

    # ---------------------------------------------------------------- PnL rho vs references
    # EW3 head ensemble + K30 SSSNET-head (OLD-panel head convention; cross-convention)
    from diversity_law import load_pkl
    sp = load_pkl(L.STREAM_PKL)
    ew3 = sp[["K30", "W60", "W252"]].mean(axis=1)   # campaign EW3 (head, OLD panel)
    k30 = sp["K30"]                                  # SSSNET-head (the 0.026 reference)
    refs = {
        "SSSNET_naive_clean": S["sssnet"],
        "SPONGE_naive_clean": S["sponge"],
        "EW3_head_OLD": ew3,
        "SSSNET_head_K30_OLD": k30,
    }
    rrows = []
    for nm in TD_NATIVE + [n + "@5d" for n in ["sortino", "sharpe_fixed", "fv3sm"]]:
        s = S[nm]
        row = dict(stream=nm, view=meta[nm]["view"], SR_naive=round(L.sharpe(s.values), 4))
        for rname, rser in refs.items():
            idx = s.index.intersection(rser.index)
            x, y = s.reindex(idx).values, rser.reindex(idx).values
            row["rho_" + rname] = round(float(np.corrcoef(x, y)[0, 1]), 4)
            row["n_" + rname] = len(idx)
        rrows.append(row)
    # also SSSNET-naive vs the head refs (baseline orthogonality context)
    for nm in ["sssnet", "sponge"]:
        s = S[nm]
        row = dict(stream=nm + "_naive", view="anchor", SR_naive=round(L.sharpe(s.values), 4))
        for rname, rser in refs.items():
            idx = s.index.intersection(rser.index)
            x, y = s.reindex(idx).values, rser.reindex(idx).values
            row["rho_" + rname] = round(float(np.corrcoef(x, y)[0, 1]), 4)
            row["n_" + rname] = len(idx)
        rrows.append(row)
    rho_df = pd.DataFrame(rrows)
    rho_df.to_csv(os.path.join(OUT, "p1_pnl_rho.csv"), index=False)

    # ---------------------------------------------------------------- console summary
    pd.set_option("display.width", 200, "display.max_columns", 40)
    print("=" * 90)
    print("SR full + eras (clean panel rb_new) + 95% CBB CI on full SR")
    print("=" * 90)
    show = ["stream", "view", "n_days", "SR_full", "ci_lo", "ci_hi"] + [e[0] for e in L.ERAS]
    print(sr_df[show].to_string(index=False))
    print("\n" + "=" * 90)
    print("PAIRED delta vs anchors (CBB 21d/500/seed42), COMMON days")
    print("=" * 90)
    print(del_df.to_string(index=False))
    print("\n" + "=" * 90)
    print("Refit-cadence effect: native 1d vs 5d-aligned")
    print("=" * 90)
    print(cad_df.to_string(index=False))
    print("\n" + "=" * 90)
    print("PnL rho vs references")
    print("=" * 90)
    print(rho_df.to_string(index=False))
    print("\nwrote p1_sr_eras.csv, p1_paired_deltas.csv, p1_cadence_effect.csv, p1_pnl_rho.csv")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # legacy entry point; p1_lib sits beside this file
    main()
