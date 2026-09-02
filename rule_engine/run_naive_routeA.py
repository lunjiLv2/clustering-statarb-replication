#!/usr/bin/env python
"""
run_naive_routeA.py — the naive betting layer on the SAME route-A partitions the
deep head used, so "naive vs deep" isolates the head.

WHY THIS EXISTS
    A backtest number is determined by two things: the PARTITION (which stocks are
    grouped together) and the RETURNS. Either can come from the old or the clean
    panel, and the repo currently mixes them:

      deep tournament (13 arms)          partition CLEAN   returns CLEAN
      existing naive numbers             partition OLD     returns CLEAN
        (JFEC_workspace/trading_driven_ortho/p1_inversion)

    That older study deliberately froze the partition — its question was "holding
    the grouping fixed, how much of the PnL was phantom alpha?", and for that
    question route B is correct. But placing its numbers beside the deep results
    and calling the gap "the head's contribution" is wrong: part of the gap is
    old-vs-new partitions.

    This reruns the naive layer on the clean-panel partitions, so both layers share
    identical partitions AND identical returns and the difference is the head alone.

ENGINE
    Uses `p1_lib.naive_stream` unchanged — the same kernel that reproduced the A1
    anchors bit-exactly (corr 1.000000, max|delta| 0.0 against
    B_sssnet_daily/B_sponge_daily). Only its INPUTS change: residuals are rebuilt
    from the clean panel instead of being read from
    recleaning/revalidation/cache_resid.npz, which does not exist on this machine.

    The residual convention is the project's standard SPY-CAPM rolling-60, byte-
    identical to server_package/family_head/gen_daily_partitions.py:compute_residuals
    and to pipeline_v21_sssnet_K_daily.py:158-164.

READ-ONLY with respect to the repo; writes only its own output CSV.
"""
from __future__ import annotations

import argparse
import glob
import os
import pickle
import sys

import numpy as np
import pandas as pd

# Replication-repo layout: the P1 kernel lives beside this file; the CRSP panel is located through
# paths.py (CSA_PANEL_ROOT), with COMPAT_DIR kept as a legacy override.
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "p1_inversion")); sys.path.insert(0, REPO)
import paths as _paths
PANEL = os.environ.get("COMPAT_DIR", str(_paths.PANEL) if _paths.PANEL else "")
assert PANEL, "set CSA_PANEL_ROOT (or COMPAT_DIR) to the compat panel directory"

# route-A partitions: {label: path}. These are exactly the files the deep head read.
PARTS: dict[str, str] = {}
# PARTS is the campaign's partition REGISTRY: run_naive_routeA, head_lift,
# partition_diagnostics and factor_lens/cluster_factor_structure all import it, so a
# partition missing here is invisible to the naive layer, the lift table, the ARI matrix,
# the size distribution AND the factor-structure table — silently, with no warning.
# That is not hypothetical: the 18 control-arm runs of 2026-08-11 (five methods at
# corr-window 21, plus the K=1 no-clustering null) write partitions to partitions_w21/,
# which the original single glob below did not reach, so ~29 GPU-hours of results would
# have produced zero table rows.
for _dir, _suffix in (("server_package/family_head/partitions", "_K30_daily_full.pkl"),
                      ("server_package/family_head/partitions_w21", "_K30_daily_full.pkl"),
                      ("server_package/family_head/partitions_w21", "_K1_daily_full.pkl"),
                      # third window batch (120/252). Adding a directory here is the ONLY
                      # thing that makes a new arm visible to the naive layer, the lift table,
                      # partition_diagnostics AND factor_lens — they all import this dict.
                      # Forgetting it has silently dropped arms twice already.
                      ("server_package/family_head/partitions_wsweep", "_K30_daily_full.pkl"),
                      # The singleton-free twin of kmeans_ret, requested by the manuscript
                      # branch (JFEC_A_Manuscript/_reference/RUN_REQUEST_kmeans_twin.md).
                      # ⚠ ADDING THIS CHANGES THE ARM SET. CORRECTIONS.md N14 C1 records that
                      # the "every method beats the K=1 null" margin depends on which arms are
                      # in the table (+0.5979 on the 12 original arms, +0.1280 on the 19-arm
                      # set). Any sentence that quotes a min/max/spread over "the field" must
                      # state its arm set explicitly, or this row silently changes it.
                      ("server_package/family_head/partitions_twin", "_K30_daily_full.pkl"),
                      # Partition-seed replicates (seeds 1 and 123) of the stochastic rules.
                      # Registering these buys a partition-seed dispersion estimate for FREE:
                      # the naive layer is deterministic, CPU-only and reproduces to 16 digits,
                      # so it answers "how much does the clustering seed move performance"
                      # without any GPU. Measured ARI between same-method different-seed
                      # partitions is 0.33 / 0.46 / 0.41 (kmeans / pca_load / spectral) against
                      # 0.22 BETWEEN METHODS — so this is not a rounding effect.
                      ("server_package/family_head/partitions_pseed", "_K30_daily_full.pkl"),
                      # Size-constrained k-means, the cluster-count leg of the three-arm
                      # singleton decomposition. NOT a twin — the constraint is enforced inside
                      # the fit (3.3 % of labels move, ARI 0.9488 vs kmeans_ret).
                      ("server_package/family_head/partitions_minsize", "_K30_daily_full.pkl"),
                      # ⚠ NOTE THE DIFFERENT SUFFIX. The K-sweep and discriminating-experiment
                      # partitions are named labelcache_<M>_k<K>[_w<W>]_daily_full.pkl — there is
                      # no "_K30" in them, so adding these directories with the "_K30_..." suffix
                      # used above would match ZERO files and look like it had worked.
                      # Until this was added (2026-08-15) the 39 completed K-sweep runs were
                      # invisible to the naive layer, the lift table, partition_diagnostics AND
                      # factor_lens — the third time this registry has silently dropped arms.
                      ("server_package/family_head/partitions_ksweep", "_daily_full.pkl"),
                      ("server_package/family_head/partitions_disc", "_daily_full.pkl")):
    for p in sorted(glob.glob(os.path.join(REPO, _dir, "*.pkl"))):
        b = os.path.basename(p)
        if not b.endswith(_suffix):
            continue
        PARTS[b.replace("labelcache_", "").replace(_suffix, "")] = p
# SSSNET persists its labels only when run with LABEL_DUMP_PATH (sssnet_labels/). Those are
# per-SEED partitions, not one shared partition, because the JIT path draws the clustering
# and the head from one RNG stream — so they are registered as sssnet_seed<N>, and a lift
# row must pair each with its OWN seed's deep run, never with the arm mean.
for p in sorted(glob.glob(os.path.join(REPO, "server_package/sssnet_labels/parts/*.pkl"))):
    b = os.path.basename(p)
    if b.startswith("labelcache_sssnet_seed") and b.endswith("_daily.pkl"):
        PARTS[b.replace("labelcache_", "").replace("_daily.pkl", "")] = p
PARTS["kmeans_ret"] = os.path.join(
    REPO, "server_package/kmeans_head/labelcache_kmeans_ret_K30_daily_full.pkl")
for name, pkl in [("sortino", "refined_fv2a_sortino_daily_clusters_1d.pkl"),
                  ("sharpe_fixed", "refined_fv2a_fixed_daily_clusters_1d.pkl"),
                  ("fv2a", "refined_fv2a_daily_clusters_1d.pkl"),
                  ("fv3sm", "refined_fv3sm_clusters_1d.pkl")]:
    q = os.path.join(REPO, f"server_package/tier2/work/{name}/output/{pkl}")
    if os.path.isfile(q):
        PARTS[name] = q
    # The trading-driven arms' w60 twins and their partition-seed replicates live under the SAME
    # per-arm output/ convention, NOT under family_head/partitions_*/, so the glob above cannot
    # reach them and they have to be named here. Registering the ps replicates is what makes the
    # partition-seed figure cover all five stochastic rules instead of four.
    for suf in ("_w60", "_w60_ps1", "_w60_ps123"):
        q2 = os.path.join(REPO, f"server_package/tier2/work/{name}{suf}/output/{pkl}")
        if os.path.isfile(q2):
            PARTS[f"{name}{suf}"] = q2


def build_residuals(panel: str, beta_window: int = 60):
    """SPY-CAPM rolling-beta residuals on the clean panel — the project's standard
    convention, identical to gen_daily_partitions.compute_residuals."""
    prices = pd.read_pickle(os.path.join(panel, "prices.pkl"))
    caps = pd.read_pickle(os.path.join(panel, "caps.pkl"))
    mask = pd.read_pickle(os.path.join(panel, "mask.pkl"))
    raw = prices.pct_change(fill_method=None)
    if "SPY" not in raw.columns:
        raise SystemExit("[FATAL] SPY missing from the panel")
    mkt = raw["SPY"]
    roll_cov = raw.rolling(beta_window).cov(mkt)
    roll_var = mkt.rolling(beta_window).var()
    resid = (raw - (roll_cov.div(roll_var, axis=0)).multiply(mkt, axis=0)) \
        .where(mask.reindex_like(raw).astype(bool))
    return resid, caps


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "naive_routeA.csv"))
    ap.add_argument("--only", nargs="*", help="restrict to these paradigms")
    ap.add_argument("--sig-w", type=int, default=5,
                    help="naive signal window. Default 5 is the historical Engine-B value "
                         "and reproduces naive_routeA.csv. The DEEP head uses "
                         "SIGNAL_WINDOW=30 (pipeline:71), so a head-lift computed at 5 "
                         "credits the head with a horizon change it did not earn; --sig-w 30 "
                         "is the matched comparator.")
    ap.add_argument("--dump-daily", default=None,
                    help="directory to persist the PER-DAY PnL of every arm as "
                         "<arm>.csv (Date,DailyPnL). Without it only the summary CSV is "
                         "written, which blocks every downstream per-day analysis "
                         "(hedge/signal/onebet tables, position-level comparisons).")
    ap.add_argument("--parts", choices=["v2", "v3"], default="v2",
                    help="partition registry: v2 = the in-file PARTS (old panel); v3 = the "
                         "explicit V3 registry in parts_v3.py (COMPAT_DIR must point at the "
                         "V3 compat panel when using it)")
    ap.add_argument("--date-start", default=None,
                    help="explicit scoring window start (D6, RERUN_PREFLIGHT §2). Default None "
                         "= inherit p1_lib's 1996-01-01, which is 352 days more than the deep "
                         "OOS and produced the fv2a-144%% error when differenced naively. On "
                         "the rerun, ALWAYS pass the window derived from the T1 head runs.")
    ap.add_argument("--date-end", default=None, help="explicit scoring window end (D6)")
    ap.add_argument("--basis", choices=["residual", "raw"], default="residual",
                    help="what the book is PAID on. 'residual' is the historical "
                         "default and reproduces naive_routeA.csv bit-for-bit. 'raw' "
                         "matches the deep head, which builds its target from raw_df "
                         "(pipeline:250,570) — use it for any head-lift comparison. "
                         "The signal, basis and universe are unchanged either way.")
    a = ap.parse_args()

    import p1_lib as L

    print(f"[naive] panel {PANEL}", flush=True)
    resid, caps = build_residuals(PANEL)
    R_pay = None
    if a.basis == "raw":
        _px = pd.read_pickle(os.path.join(PANEL, "prices.pkl"))
        _mk = pd.read_pickle(os.path.join(PANEL, "mask.pkl"))
        R_pay = np.ascontiguousarray(
            _px.pct_change(fill_method=None)
               .where(_mk.reindex_like(_px).astype(bool))
               .reindex(index=resid.index, columns=resid.columns).values,
            dtype=np.float64)
        print("[naive] PAYOFF BASIS = raw returns (matches the deep head)", flush=True)
    ridx = pd.DatetimeIndex(resid.index)
    cols = list(resid.columns)
    col = {c: j for j, c in enumerate(cols)}
    R = np.ascontiguousarray(resid.values, dtype=np.float64)
    caps = caps.reindex(index=ridx, columns=cols)
    caps_np, caps_cols = caps.values, caps.columns.to_numpy()
    print(f"[naive] residuals {R.shape}  {ridx[0].date()}..{ridx[-1].date()}", flush=True)

    parts = PARTS
    if a.parts == "v3":
        from parts_v3 import PARTS_V3 as parts          # explicit v3 registry, loud on gaps
        assert "Cleaned_Data_v3" in PANEL, \
            f"--parts v3 requires COMPAT_DIR at the V3 panel, got {PANEL}"
    todo = {k: v for k, v in parts.items() if not a.only or k in a.only}
    rows = []
    for name, path in sorted(todo.items()):
        # load INSIDE a guard: one missing/truncated/mid-write pkl must cost one arm, not the
        # whole layer (audit 2026-08-18 — the bare load here could kill all completed arms).
        try:
            cache = pickle.load(open(path, "rb"))
        except Exception as exc:                                 # noqa: BLE001
            print(f"  {name:20s} UNREADABLE pkl: {type(exc).__name__}: {exc}", flush=True)
            continue
        # LOUD universe-vs-panel guard (audit 2026-08-18): if the partition stores names the
        # panel doesn't have (bare tickers vs a TICKER.PERMNO panel, or stale pkls on a new
        # panel), p1_lib's affiliation fallback SILENTLY collapses every stock to cluster 0 —
        # output identical to a K=1 arm, with a plausible Sharpe. Refuse instead.
        _k0 = sorted(cache)[len(cache) // 2]
        _uni = list(cache[_k0]["universe"])
        _hit = sum(1 for t in _uni if t in col)
        if _uni and _hit / len(_uni) < 0.5:
            print(f"  {name:20s} REFUSED: partition universe matches only {_hit}/{len(_uni)} "
                  f"panel columns — wrong panel/keying for this pkl", flush=True)
            continue
        # every route-A partition stores "labels"; the SSSNET-style ones also carry
        # "sponge_labels" — we always take the method's own labels.
        key = "labels"
        try:
            kw = {}
            if a.date_start: kw["date_start"] = a.date_start
            if a.date_end: kw["date_end"] = a.date_end
            s = L.naive_stream(cache, key, ridx, col, caps_np, caps_cols,
                               R_trade=R, R_affil=R, R_valid2=None, R_pay=R_pay,
                               SIG_W=a.sig_w, **kw)
        except Exception as exc:                                  # noqa: BLE001
            print(f"  {name:20s} FAILED: {type(exc).__name__}: {exc}", flush=True)
            continue
        s = s.dropna()
        if a.dump_daily and len(s):
            os.makedirs(a.dump_daily, exist_ok=True)
            s.rename("DailyPnL").to_frame().to_csv(
                os.path.join(a.dump_daily, f"{name}.csv"), index_label="Date")
        if len(s) < 100:
            print(f"  {name:20s} too few days ({len(s)})", flush=True)
            continue
        sr = np.sqrt(252) * s.mean() / s.std(ddof=1)
        rows.append({"paradigm": name, "days": len(s), "SR_naive_routeA": sr,
                     "start": s.index.min().date(), "end": s.index.max().date(),
                     "partition": os.path.basename(path)})
        print(f"  {name:20s} n={len(s):5d}  SR={sr:+.4f}", flush=True)

    if not rows:
        print("[naive] nothing produced", file=sys.stderr)
        return 1
    df = pd.DataFrame(rows).sort_values("SR_naive_routeA", ascending=False)
    df.to_csv(a.out, index=False)
    print(f"\n[naive] wrote {a.out}")
    print(df.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
