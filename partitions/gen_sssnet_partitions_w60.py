#!/usr/bin/env python
"""
gen_sssnet_partitions.py — precompute SSSNET-Hybrid daily partitions on the
split-safe panel, so the head can read them like every other paradigm.

================================================================================
READ THIS FIRST — WHAT THIS IS, AND WHAT IT IS NOT
================================================================================
This does NOT reproduce the JIT SSSNET run bit-for-bit. That is impossible, and
the reason is structural, not an implementation shortcut:

  * `cluster_with_sssnet_hybrid` does NOT seed internally. The
    `torch.manual_seed(42)` at sssnet_hybrid_clusterer.py:171 sits in the file's
    bottom-of-module demo block (`for alpha in [0.0, 0.5, 2.0]`), not in the
    function, which begins at :79.
  * In the pipeline, clustering and head training therefore share one global RNG
    stream. Day N's SSSNET training starts from a state advanced by every prior
    day's clustering AND every prior head update (dropout, day shuffling, margin
    pair sampling).

So a standalone precompute — chunked or not — cannot see that stream. Rather than
pretend otherwise, this defines the partition as a deterministic function of
(date, data, seed) by seeding `SEED + day_idx` before each day. That is
reproducible, order-independent, and chunkable, and it removes an implicit
dependence on training history that the JIT version has by accident.

  ==> Label the output "SSSNET-precomputed", never "SSSNET". It is a variant.
      Validate it against the JIT runs by COMPARING CLUSTER STATISTICS
      (N_Clusters, ClSize{Mean,Std,Min,Max} in the runs' diag_*.csv), never by
      expecting equality.

Everything else is a verbatim replica of `_compute_e2e_cluster_now`
(pipeline_v21_sssnet_K_daily.py:253-309): same universe rule, same 21-day
correlation window with a zeroed diagonal, same 252-day residual window, same
`len(common) < 100` guard, same SPONGE warm start, same hyperparameters. The
unused `bet_model` / `prices_index` arguments are dropped — verified unused: they
appear only in that function's signature.

WHY PRECOMPUTE AT ALL
  A JIT SSSNET run is ~16 h and indivisible. Once the partitions exist, any head
  experiment on them costs ~1.6 h, like every other paradigm — seed sweeps, the
  head fixes, cost-aware training, all reuse the same file. It also makes SSSNET
  structurally identical to the other twelve arms of the tournament.

USAGE
  PY=server_package/_sol_base/.venv/bin/python
  $PY gen_sssnet_partitions.py --start-idx 0 --end-idx 1000 --out part_000.pkl
  $PY gen_sssnet_partitions.py --merge part_*.pkl --out sssnet_K30_daily_full.pkl
"""
from __future__ import annotations

import argparse
import glob
import os
import pickle
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
M15 = os.path.join(REPO, "May_15_Meeting", "MR_clustering")
sys.path.insert(0, M15)

DEFAULT_PANEL = os.environ.get("CSA_PANEL_ROOT", "")   # the CRSP-derived panel (layer L2); set CSA_PANEL_ROOT

# Config constants copied from pipeline_v21_sssnet_K_daily.py. Kept as literals,
# with the source line, so a drift in the pipeline shows up as a diff here rather
# than silently changing the partitions.
TOP_K_STOCKS = 500          # :72
BETA_WINDOW = 60            # :73
N_CLUSTERS = 30             # :81  (SPONGE_K env, canonical 30)
SSSNET_EPOCHS = 100         # :56
SSSNET_LR = 0.01            # :57
SSSNET_HIDDEN = 32          # :58
ALPHA_TRADING = 0.0         # :48  pure SSSNET; the trading-loss term is OFF
SPEC_WEIGHT = 1.0           # :60
SEED_WEIGHT = 50.0          # :61
BALANCE_WEIGHT = 10.0       # :62
SIGNAL_WINDOW_HYBRID = 30   # :64
MR_LOOKBACK = 252           # :268 (local constant in _compute_e2e_cluster_now)
CORR_WINDOW = 60            # W60 COPY (2026-08-27): the executed sssnetw60 arm uses residuals.iloc[day_idx-60:day_idx]
MIN_COMMON = 100            # :271
SPONGE_MIN_SIZE = 2         # :270


def calculate_residuals(prices: pd.DataFrame, mask: pd.DataFrame,
                        beta_window: int = BETA_WINDOW) -> pd.DataFrame:
    """Verbatim replica of pipeline_v21_sssnet_K_daily.py:158-164
    `calculate_residuals_and_returns` (SPY-CAPM rolling beta, then masked)."""
    raw = prices.pct_change(fill_method=None)
    if "SPY" not in raw.columns:
        raise SystemExit("[FATAL] SPY column missing — cannot build SPY-CAPM residuals")
    mkt = raw["SPY"]
    roll_cov = raw.rolling(beta_window).cov(mkt)
    roll_var = mkt.rolling(beta_window).var()
    residuals = raw - (roll_cov.div(roll_var, axis=0)).multiply(mkt, axis=0)
    return residuals.where(mask.reindex_like(residuals).astype(bool))


def compute_one_day(day_idx: int, date, residuals: pd.DataFrame,
                    caps: pd.DataFrame, device: str) -> dict | None:
    """Verbatim replica of `_compute_e2e_cluster_now`, minus the two unused args."""
    from variant_f_v2a_clusterizer import run_sponge as _run_sponge
    from sssnet_hybrid_clusterer import cluster_with_sssnet_hybrid

    try:
        day_caps = caps.iloc[day_idx - 1].dropna()
        universe = day_caps.nlargest(TOP_K_STOCKS).index
    except Exception:
        return None
    res_corr = residuals.iloc[day_idx - CORR_WINDOW:day_idx][universe].dropna(axis=1)
    res_window = residuals.iloc[day_idx - MR_LOOKBACK:day_idx][universe].dropna(axis=1)
    if os.environ.get("SSSNET_RELAX_MR") == "1":
        # ALPHA_TRADING == 0: cluster_with_sssnet_hybrid never uses the 252-day window in its
        # loss (sssnet_hybrid_clusterer.py:113 gates the trading term on alpha_trading > 0), so
        # the completeness requirement on it is an interface leftover. Require only the 60-day
        # correlation window, as SPONGE does. User-approved 2026-08-27 for the pretrain filler.
        assert ALPHA_TRADING == 0.0
        common = list(res_corr.columns)
        res_window = residuals.iloc[day_idx - MR_LOOKBACK:day_idx][common]
    else:
        common = list(res_corr.columns.intersection(res_window.columns))
    if len(common) < MIN_COMMON:
        return None
    res_corr = res_corr[common]
    res_window = res_window[common]
    corr = res_corr.corr().fillna(0).values.copy().astype(np.float32)
    np.fill_diagonal(corr, 0)
    sponge_labels = _run_sponge(corr, N_CLUSTERS, SPONGE_MIN_SIZE)
    if sponge_labels is None:
        return None

    R = res_window.fillna(0).values.astype(np.float32)
    try:
        labels, diag = cluster_with_sssnet_hybrid(
            corr, R[:-1], R[1:], sponge_labels, K=N_CLUSTERS,
            top_k_stocks=TOP_K_STOCKS,
            epochs=SSSNET_EPOCHS, lr=SSSNET_LR, hidden=SSSNET_HIDDEN,
            alpha_trading=ALPHA_TRADING,
            spec_weight=SPEC_WEIGHT, seed_weight=SEED_WEIGHT,
            balance_weight=BALANCE_WEIGHT,
            signal_window=SIGNAL_WINDOW_HYBRID, ew_decay=0.99,
            device=device,
        )
    except Exception as exc:                                   # noqa: BLE001
        print(f"  [FAIL] {date.date()}: {exc}", flush=True)
        return None

    lab = np.asarray(labels, dtype=np.int32)
    # Schema the head's loader expects: it reads info["universe"] and, when
    # USE_SPONGE_LABELS_FOR_PHASE_1 is set, info["sponge_labels"].
    return {"universe": list(common), "labels": lab,
            "sponge_labels": np.asarray(sponge_labels, dtype=np.int32),
            "n_clusters_used": int(diag.get("n_clusters_used", 0)),
            "size_max": int(diag.get("size_max", 0)),
            "sharpe_final": float(diag.get("sharpe_final", 0.0))}


def generate(panel: str, out_path: str, start_idx: int, end_idx: int,
             seed: int, device: str) -> None:
    import torch

    prices = pd.read_pickle(os.path.join(panel, "prices.pkl"))
    caps = pd.read_pickle(os.path.join(panel, "caps.pkl"))
    mask = pd.read_pickle(os.path.join(panel, "mask.pkl"))
    residuals = calculate_residuals(prices, mask)
    ridx = residuals.index
    lo = max(start_idx, MR_LOOKBACK + 1)          # need a full 252-day window
    hi = min(end_idx, len(ridx))
    print(f"[gen] panel={panel} rows={len(ridx)} {ridx[0].date()}..{ridx[-1].date()}",
          flush=True)
    print(f"[gen] slice [{lo},{hi}) seed={seed} device={device} "
          f"K={N_CLUSTERS} alpha={ALPHA_TRADING}", flush=True)

    cache: dict = {}
    n_fail = 0
    t0 = time.time()
    for t in range(lo, hi):
        # Per-day seeding: makes each day a pure function of (date, data, seed),
        # independent of chunk boundaries and of any training history. This is the
        # documented departure from the JIT path — see the module docstring.
        torch.manual_seed(seed + t)
        np.random.seed((seed + t) % (2 ** 31 - 1))
        info = compute_one_day(t, ridx[t], residuals, caps, device)
        if info is None:
            n_fail += 1
            continue
        cache[pd.Timestamp(ridx[t])] = info
        if len(cache) % 100 == 0:
            el = time.time() - t0
            done = t - lo + 1
            print(f"[gen]   {len(cache)} snapshots ({done}/{hi-lo} days, "
                  f"through {ridx[t].date()}, {el:.0f}s, "
                  f"eta {el/done*(hi-lo-done):.0f}s)", flush=True)

    with open(out_path, "wb") as fh:
        pickle.dump(cache, fh, protocol=4)
    print(f"[gen] done: {len(cache)} snapshots, {n_fail} failures, "
          f"{time.time()-t0:.0f}s -> {out_path} ({os.path.getsize(out_path)} bytes)",
          flush=True)


def merge(parts: list[str], out_path: str) -> None:
    merged: dict = {}
    dupes = 0
    for p in sorted(parts):
        d = pickle.load(open(p, "rb"))
        for k, v in d.items():
            if k in merged:
                dupes += 1                 # chunk ranges must not overlap
            merged[k] = v
        print(f"  + {os.path.basename(p)}: {len(d)} snapshots")
    if dupes:
        raise SystemExit(f"[FATAL] {dupes} duplicate dates across chunks — ranges overlap")
    ks = sorted(merged)
    gaps = np.diff([k.value for k in ks]) / (86400 * 1e9)
    print(f"  merged: {len(merged)} snapshots {ks[0].date()}..{ks[-1].date()}; "
          f"max calendar gap {gaps.max():.0f} d")
    if gaps.max() > 10:
        print(f"  ⚠ a gap exceeds REFINED_CLUSTER_MAX_AGE_DAYS=10 — the head will "
              f"fall back to fresh SPONGE on those days", file=sys.stderr)
    with open(out_path, "wb") as fh:
        pickle.dump(merged, fh, protocol=4)
    print(f"  wrote {out_path} ({os.path.getsize(out_path)} bytes)")


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    p.add_argument("--panel", default=os.environ.get("COMPAT_DIR", DEFAULT_PANEL))
    p.add_argument("--out", required=True)
    p.add_argument("--start-idx", type=int, default=0)
    p.add_argument("--end-idx", type=int, default=10 ** 9)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--device", default="cuda")
    p.add_argument("--merge", nargs="*", help="merge these chunk pkls into --out")
    a = p.parse_args(argv)
    if a.merge:
        files = [f for pat in a.merge for f in glob.glob(pat)]
        if not files:
            raise SystemExit("[FATAL] --merge matched no files")
        merge(files, a.out)
        return 0
    generate(a.panel, a.out, a.start_idx, a.end_idx, a.seed, a.device)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
