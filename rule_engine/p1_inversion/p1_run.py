#!/usr/bin/env python3
"""
p1_run.py -- STEP 2: apply every cluster partition to the CLEAN panel (rb_new).
==============================================================================
Uniform naive MR engine (validated in p1_validate.py, clean single-panel
convention: R_trade=R_affil=rb_new, no intersect-validity).

Partitions (K=30 throughout):
  TRADING-DRIVEN : sortino, sharpe_fixed, fv3sm  (native cadence = 1d),
                   spectral_sortino               (native cadence = 5d)
  UNSUPERVISED   : sssnet, sponge, kmeans, agglo, pca   (all native 5d)

REFIT-CADENCE ALIGNMENT (disclosed):
  The three fv2a/fv3 trading-driven caches refit EVERY DAY (1d); every other
  partition (incl. the SSSNET/SPONGE anchors) refits every 5 days (5d).  A daily
  refit gives fresher labels, which is a property of the *deployment cadence*,
  not of the loss form.  To separate the two effects we run each 1d cache TWICE:
    <name>            : native 1d cadence (fresh labels every day)
    <name>@5d         : same cache VIEWED at the 5d SSSNET refit dates (labels
                        held ~5 days), so every partition shares one cadence.
  The 5d-aligned set is the apples-to-apples loss-form comparison; the native
  set additionally exposes the refit-frequency bonus.

Outputs p1_streams.pkl = { stream_name -> pd.Series(daily PnL) }.
"""
import os
import time
import pickle

import numpy as np
import pandas as pd

import p1_lib as L

OUT = os.path.dirname(os.path.abspath(__file__))


def main():
    t0 = time.time()
    z, cols, ridx = L.load_resid()
    col = {c: j for j, c in enumerate(cols)}
    RN = L.masked_panel(z, "rb_new")
    caps = pd.read_pickle(L.CAPS_OLD)
    caps_np, caps_cols = caps.values, caps.columns.to_numpy()
    assert caps.index.equals(pd.DatetimeIndex(ridx))

    # 5d refit schedule (SSSNET dates) for cadence-aligning the 1d caches
    sss_cache, _, _ = L.load_cache("sssnet")
    refit5d = sorted(sss_cache.keys())

    streams = {}
    meta = {}
    for name in L.TRADING_DRIVEN + L.UNSUPERVISED:
        cache, key, cadence = L.load_cache(name)
        # native cadence
        s = L.naive_stream(cache, key, ridx, col, caps_np, caps_cols,
                           R_trade=RN, R_affil=RN, R_valid2=None)
        streams[name] = s
        meta[name] = dict(cadence_native=cadence, view="native",
                          label_key=key, n_days=len(s),
                          sr=L.sharpe(s.values))
        print(f"  [{name:16s}] native({cadence})  SR={L.sharpe(s.values):+.4f}  "
              f"n={len(s)}  ({time.time()-t0:.0f}s)")
        # 5d-aligned view for the 1d caches
        if cadence == "1d":
            s5 = L.naive_stream(cache, key, ridx, col, caps_np, caps_cols,
                                R_trade=RN, R_affil=RN, R_valid2=None,
                                refit_dates=refit5d)
            nm5 = name + "@5d"
            streams[nm5] = s5
            meta[nm5] = dict(cadence_native=cadence, view="5d_aligned",
                             label_key=key, n_days=len(s5),
                             sr=L.sharpe(s5.values))
            print(f"  [{nm5:16s}] 5d-aligned    SR={L.sharpe(s5.values):+.4f}  "
                  f"n={len(s5)}  ({time.time()-t0:.0f}s)")

    pickle.dump({"streams": streams, "meta": meta}, open(os.path.join(OUT, "p1_streams.pkl"), "wb"))
    print(f"\nwrote p1_streams.pkl  ({len(streams)} streams, {time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
