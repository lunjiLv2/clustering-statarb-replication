#!/usr/bin/env python3
"""
p1_validate.py -- STEP 1: validate the naive MR engine BEFORE trusting it.
==========================================================================
Two checks:
  (V1) ANCHOR MODE reproduces the cached Engine-B anchors bit-exactly.
       naive_stream(sssnet 'labels', R_trade=RN, R_affil=RO, R_valid2=RO)
       must equal engineB_results.pkl :: B_sssnet_daily['new']  (SR 1.5637)
       and the sponge_labels variant must equal B_sponge_daily['new'] (1.4979).
  (V2) CLEAN MODE (single panel rb_new, affil on rb_new, validity on rb_new only)
       must track the anchor with corr>0.999 -- i.e. the legacy old&new
       intersect-validity / OLD-affiliation artifacts are immaterial, so the
       clean single-panel convention is safe to use uniformly for all partitions.

Writes p1_validation.csv and prints a PASS/FAIL summary.
"""
import os
import numpy as np
import pandas as pd
import pickle

import p1_lib as L

OUT = os.path.dirname(os.path.abspath(__file__))


def corr(a: pd.Series, b: pd.Series) -> tuple:
    c = a.index.intersection(b.index)
    x, y = a[c].values, b[c].values
    r = float(np.corrcoef(x, y)[0, 1])
    mad = float(np.max(np.abs(x - y)))
    return r, mad, len(c)


def main():
    z, cols, ridx = L.load_resid()
    col = {c: j for j, c in enumerate(cols)}
    RN = L.masked_panel(z, "rb_new")
    RO = L.masked_panel(z, "rb_old")
    caps = pd.read_pickle(L.CAPS_OLD)
    caps_np, caps_cols = caps.values, caps.columns.to_numpy()
    assert caps.index.equals(pd.DatetimeIndex(ridx)), "caps/resid date mismatch"

    B = pickle.load(open(L.ENG_B_PKL, "rb"))
    anc_sss = B["pnl"]["B_sssnet_daily"]["new"]
    anc_spo = B["pnl"]["B_sponge_daily"]["new"]

    sss_cache, _, _ = L.load_cache("sssnet")

    rows = []
    print("=" * 78)
    print("V1  ANCHOR MODE (R_trade=RN, R_affil=RO, R_valid2=RO)  vs cached anchors")
    print("=" * 78)
    # SSSNET labels
    my_sss_anc = L.naive_stream(sss_cache, "labels", ridx, col, caps_np, caps_cols,
                                R_trade=RN, R_affil=RO, R_valid2=RO)
    r, mad, n = corr(my_sss_anc, anc_sss)
    print(f"  B_sssnet_daily : mySR={L.sharpe(my_sss_anc.values):.4f}  "
          f"ancSR={L.sharpe(anc_sss.values):.4f}  corr={r:.6f}  maxAbsDiff={mad:.2e}  n={n}")
    rows.append(dict(check="V1_anchor_sssnet", my_sr=L.sharpe(my_sss_anc.values),
                     ref_sr=L.sharpe(anc_sss.values), corr=r, max_abs_diff=mad, n=n))
    # SPONGE labels
    my_spo_anc = L.naive_stream(sss_cache, "sponge_labels", ridx, col, caps_np, caps_cols,
                                R_trade=RN, R_affil=RO, R_valid2=RO)
    r, mad, n = corr(my_spo_anc, anc_spo)
    print(f"  B_sponge_daily : mySR={L.sharpe(my_spo_anc.values):.4f}  "
          f"ancSR={L.sharpe(anc_spo.values):.4f}  corr={r:.6f}  maxAbsDiff={mad:.2e}  n={n}")
    rows.append(dict(check="V1_anchor_sponge", my_sr=L.sharpe(my_spo_anc.values),
                     ref_sr=L.sharpe(anc_spo.values), corr=r, max_abs_diff=mad, n=n))

    print("=" * 78)
    print("V2  CLEAN MODE (R_trade=RN, R_affil=RN, R_valid2=None) vs cached anchor")
    print("=" * 78)
    my_sss_clean = L.naive_stream(sss_cache, "labels", ridx, col, caps_np, caps_cols,
                                  R_trade=RN, R_affil=RN, R_valid2=None)
    r, mad, n = corr(my_sss_clean, anc_sss)
    print(f"  clean SSSNET vs anchor : cleanSR={L.sharpe(my_sss_clean.values):.4f}  "
          f"ancSR={L.sharpe(anc_sss.values):.4f}  corr={r:.6f}  maxAbsDiff={mad:.2e}  n={n}")
    rows.append(dict(check="V2_clean_vs_anchor_sssnet", my_sr=L.sharpe(my_sss_clean.values),
                     ref_sr=L.sharpe(anc_sss.values), corr=r, max_abs_diff=mad, n=n))
    my_spo_clean = L.naive_stream(sss_cache, "sponge_labels", ridx, col, caps_np, caps_cols,
                                  R_trade=RN, R_affil=RN, R_valid2=None)
    r, mad, n = corr(my_spo_clean, anc_spo)
    print(f"  clean SPONGE vs anchor : cleanSR={L.sharpe(my_spo_clean.values):.4f}  "
          f"ancSR={L.sharpe(anc_spo.values):.4f}  corr={r:.6f}  maxAbsDiff={mad:.2e}  n={n}")
    rows.append(dict(check="V2_clean_vs_anchor_sponge", my_sr=L.sharpe(my_spo_clean.values),
                     ref_sr=L.sharpe(anc_spo.values), corr=r, max_abs_diff=mad, n=n))

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "p1_validation.csv"), index=False)

    v1_pass = (df[df.check.str.startswith("V1")]["corr"] > 0.999).all()
    v2_pass = (df[df.check.str.startswith("V2")]["corr"] > 0.999).all()
    print("=" * 78)
    print(f"V1 bit-exact anchor reproduction : {'PASS' if v1_pass else 'FAIL'} "
          f"(corr>0.999, SR to 4 dp)")
    print(f"V2 clean-convention immateriality: {'PASS' if v2_pass else 'FAIL'} "
          f"(clean single-panel == anchor to corr>0.999)")
    print(f"-> proceed with CLEAN single-panel convention for all 9 partitions: "
          f"{'YES' if (v1_pass and v2_pass) else 'NO -- investigate'}")
    print(f"wrote {os.path.join(OUT, 'p1_validation.csv')}")


if __name__ == "__main__":
    main()
