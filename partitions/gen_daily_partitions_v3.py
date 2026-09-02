#!/usr/bin/env python
# """gen_daily_partitions_v3.py — the V3-RERUN partition generator.
#
# WHY A COPY. gen_daily_partitions.py carries LINE-NUMBER PINS (73/74/80/195) asserted
# character-for-character by JFEC_ML_Draft/scripts/window_panels.py:102-120; the fixes below shift
# lines, so the original stays frozen as the old-provenance record and THIS file is what the V3
# rerun invokes. Deliberate diffs from the original (audit 2026-08-18), grep "V3-" to see all:
#
#   V3-1  UNIVERSE BACKFILL (syncs with the head's PATCH 6 / D3): the original ranks
#         caps.nlargest(top_k) FIRST, then drops names without a complete corr window, wasting
#         slots exactly like the head bug behind CORRECTIONS N27. Now the completeness mask is
#         computed on ALL priced names and top_k is taken among complete ones — the same rule
#         PATCH 6 gives the head. Applied at the daily generator AND the three verify/diagnostic
#         samplers, so verification samples the universe it verifies.
#
#   V3-2  GICS ON TICKER.PERMNO COLUMNS: the sector snapshot keys are bare tickers; on the v3
#         panel gics.get("AAPL.14593") is None for every name and the gics arm would die of
#         "coverage too thin" every day. Lookups now strip the .PERMNO suffix.
#
#   V3-3  SPY EXCLUDED: under D11 SPY has caps all-NaN so caps ranking can never select it —
#         asserted at the generator so a caps regression cannot silently cluster the market
#         series.
# ==== original follows; diffs marked V3-1/2/3 ====
#!/usr/bin/env python
"""
gen_daily_partitions.py — DAILY cluster partitions on the split-safe panel, for a
family of clustering paradigms, in the format the V2.1 head consumes.

WHY THIS EXISTS
    The clean-panel head layer has only two points (k-means 2.5445, SSSNET 2.2888).
    Every tourney pipeline reads its per-day labels from REFINED_CLUSTERS_FILE for
    EVERY day (pretrain and online), so swapping the clustering source is a pure
    data swap. Generating one partition pkl per paradigm therefore turns each
    additional head run into a ~1.6 h GPU job instead of a ~15 h JIT job.

DESIGN CHOICE (user decision, 2026-08-08): route A — partitions are RECOMPUTED on
    the clean panel, not lifted from the old-panel caches. So each number answers
    "what does this method produce end-to-end on correct data", which is the right
    question for a method comparison. (Route B — old partitions + new returns — is
    what the A1 naive revalidation and JFEC_workspace/trading_driven_ortho used;
    the two are NOT directly comparable and must not be mixed in one table.)

FIDELITY: each paradigm reproduces its OWN canonical producer.
    * tourney family (kmeans_ret / pca_load / agglo_avg / agglo_complete /
      spectral_unsigned / random): June_16_Meeting/gen_label_cache.py
      `labels_from_corr`, on a `corr_window`-day residual window, C = np.corrcoef.
    * sponge: pipeline_v21_sssnet_K_daily.py `_compute_e2e_cluster_now`, which uses
      a 21-DAY window, `res_corr.corr().fillna(0)` with the diagonal zeroed, then
      variant_f_v2a_clusterizer.run_sponge (SPONGE_sym, tau_p=tau_n=1, min_size=2).
    * gics: a static sector map, as a benchmark partition (NOT a learned method).

  ⚠ WINDOW CONFOUND — READ BEFORE COMPARING. The canonical SPONGE window is 21 d
    and the canonical tourney window is 60 d. A SPONGE-vs-k-means comparison at
    their canonical settings therefore confounds METHOD with WINDOW LENGTH. Use
    --corr-window to run a matched control (e.g. sponge at 60, or the tourney
    family at 21) before making any "method X beats method Y" claim.

RESIDUALS are computed by importing `compute_residuals` from the already-validated
    gen_kmeans_daily_partitions module, so the clustering input is bit-identical to
    the one behind the existing k-means result.

USAGE
    PY=server_package/_sol_base/.venv/bin/python
    $PY server_package/family_head/gen_daily_partitions.py \
        --paradigm pca_load --out .../labelcache_pca_load_K30_daily_full.pkl
    # self-check: regenerate k-means and assert byte-identity with the existing pkl
    $PY server_package/family_head/gen_daily_partitions.py --verify-kmeans
"""
from __future__ import annotations

import argparse
import os
import pickle
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
KMEANS_DIR = os.path.join(REPO, "server_package", "kmeans_head")
M15 = os.path.join(REPO, "May_15_Meeting", "MR_clustering")
sys.path.insert(0, KMEANS_DIR)
sys.path.insert(0, M15)

from gen_kmeans_daily_partitions import compute_residuals  # noqa: E402  (validated module)

DEFAULT_PANEL = os.environ.get("CSA_PANEL_ROOT", "")   # replication repo: compat panel (prices/caps/mask.pkl), not shipped
KMEANS_REF = os.path.join(KMEANS_DIR, "labelcache_kmeans_ret_K30_daily_full.pkl")
GICS_CSV = os.environ.get("CSA_GICS_CSV", "")          # replication repo: GICS sector snapshot (licensed; see data/README.md)

TOURNEY = ["kmeans_ret", "pca_load", "agglo_avg", "agglo_complete",
           "spectral_unsigned", "random"]
PARADIGMS = TOURNEY + ["sponge", "gics"]
CANONICAL_WINDOW = {p: 60 for p in TOURNEY}
CANONICAL_WINDOW["sponge"] = 21
# gics does not use the window to derive LABELS, but it MUST use the same window
# to derive the UNIVERSE, or its stock set differs from every other paradigm and
# the comparison is void. (Setting this to 0 once produced 8,735 snapshots vs
# 7,911 for the others: R[t-0:t] is an empty slice and np.isfinite(empty).all()
# is vacuously True, so the residual-history filter silently vanished.)
CANONICAL_WINDOW["gics"] = 60


def _log(m: str) -> None:
    print(f"[gen] {m}", flush=True)


def tourney_labels(name: str, Rtr: np.ndarray, k: int, seed: int, n_init: int,
                   rng: np.random.Generator) -> np.ndarray:
    """Verbatim replica of June_16_Meeting/gen_label_cache.py `labels_from_corr`.

    Args:
        name: paradigm key.
        Rtr: residual window, shape (window, n_stocks).
        k, seed, n_init: canonical 30 / 42 / 4.
        rng: only used by the `random` control.

    Returns:
        int label vector of length n_stocks.
    """
    from sklearn.cluster import AgglomerativeClustering, KMeans, SpectralClustering

    if name == "kmeans_ret":                       # no correlation matrix at all
        return KMeans(k, random_state=seed, n_init=n_init).fit_predict(Rtr.T)
    if name == "random":
        return rng.integers(0, k, Rtr.shape[1])

    C = np.corrcoef(Rtr.T)
    if name == "spectral_unsigned":
        A = np.abs(C)
        np.fill_diagonal(A, 1.0)
        return SpectralClustering(k, affinity="precomputed", assign_labels="kmeans",
                                  random_state=seed, n_init=n_init).fit_predict(A)
    if name in ("agglo_avg", "agglo_complete"):
        D = np.clip(1.0 - C, 0, 2)
        np.fill_diagonal(D, 0.0)
        link = "average" if name == "agglo_avg" else "complete"
        return AgglomerativeClustering(k, metric="precomputed",
                                       linkage=link).fit_predict(D)
    if name == "pca_load":
        _, V = np.linalg.eigh(C)
        emb = V[:, -10:]
        return KMeans(k, random_state=seed, n_init=n_init).fit_predict(emb)
    raise ValueError(name)


def sponge_labels(Rtr: np.ndarray, k: int) -> np.ndarray | None:
    """SPONGE_sym on the SIGNED correlation, matching the pipeline exactly:
    corr with the diagonal zeroed, then variant_f_v2a_clusterizer.run_sponge.
    Returns None when SPONGE fails all retries (caller records a skip)."""
    from variant_f_v2a_clusterizer import run_sponge
    C = np.corrcoef(Rtr.T).astype(np.float32)
    C = np.nan_to_num(C, nan=0.0)
    np.fill_diagonal(C, 0.0)
    return run_sponge(C, k, 2)


def load_gics() -> dict:
    """ticker -> sector name, from the static SP1500 snapshot.

    NOTE the coverage caveat the memos insist on: this is a single ~mid-2010s
    snapshot and it covers only ~50-67% of the traded universe by era, so the
    GICS arm is a benchmark with KNOWN survivorship and coverage bias, never a
    like-for-like competitor.
    """
    df = pd.read_csv(GICS_CSV, header=None,
                     names=["sector_etf", "sector_id", "ticker", "sector_name"])
    return dict(zip(df["ticker"].astype(str), df["sector_name"].astype(str)))


def generate(paradigm: str, panel: str, out_path: str, k: int, corr_window: int,
             beta_window: int, top_k: int, seed: int, n_init: int,
             limit_days: int | None = None, singleton_rule: str = "fix") -> dict:
    """Recompute `paradigm` partitions on every trading day of `panel`.

    V3-4 (user directive 2026-08-19): singleton_rule="fix" applies the ENGINE'S OWN
    `_fix_tiny_clusters(labels, corr, min_size=2)` to EVERY paradigm's labels, so the
    singleton/degenerate-cluster treatment is IDENTICAL across clusterizers — the N24
    fairness audit found kmeans_ret dropped ~10.3 names/day to singletons while nine of
    eleven arms dropped ~0, confounding "grouping quality" with "universe size". The rule
    is uniform; the EFFECTIVE cluster count may still differ by arm (merging shrinks it),
    which is legitimate arm behavior and is recorded per-day. singleton_rule="raw"
    reproduces the old per-arm behavior, kept ONLY to measure the delta for the appendix."""
    if singleton_rule not in ("fix", "raw"):
        raise ValueError(singleton_rule)
    global _FIX_TINY
    if singleton_rule == "fix" and _FIX_TINY is None:
        _FIX_TINY = _canonical_fix_tiny_clusters()
    if corr_window < 1:
        raise ValueError(
            f"corr_window={corr_window} < 1: an empty window slice makes "
            "np.isfinite(...).all(axis=0) vacuously True, which silently disables "
            "the residual-history filter and changes the universe.")
    prices = pd.read_pickle(os.path.join(panel, "prices.pkl"))
    caps = pd.read_pickle(os.path.join(panel, "caps.pkl"))
    mask = pd.read_pickle(os.path.join(panel, "mask.pkl"))
    residuals = compute_residuals(prices, mask, beta_window=beta_window)
    R = residuals.values
    ridx = residuals.index
    col_of = {c: j for j, c in enumerate(residuals.columns)}
    n_days = len(ridx)
    rng = np.random.default_rng(seed)
    gics = load_gics() if paradigm == "gics" else None

    _log(f"paradigm={paradigm} panel={panel}: {n_days} days "
         f"{ridx[0].date()}..{ridx[-1].date()}; K={k} corr_W={corr_window} "
         f"beta_W={beta_window} top_k={top_k} seed={seed}")

    # The feature/correlation window is `corr_window`; the residual beta warm-up is
    # `beta_window`. Start late enough for BOTH.
    start = max(beta_window, corr_window) + 5
    cache: dict = {}
    n_small = n_fail = 0
    t0 = time.time()
    for t in range(start, n_days if limit_days is None else min(n_days, start + limit_days)):
        day_caps = caps.iloc[t - 1].dropna()          # prior-day cap: no lookahead
        if day_caps.empty:
            continue
        _c0 = list(day_caps.index)                                    # V3-1: backfill
        _j0 = np.array([col_of.get(c, -1) for c in _c0], dtype=np.int64)
        _v0 = np.zeros(len(_c0), dtype=bool)
        if (_j0 >= 0).any():
            _v0[np.where(_j0 >= 0)[0]] = np.isfinite(
                R[t - corr_window:t, :][:, _j0[_j0 >= 0]]).all(axis=0)
        uni = list(day_caps[[c for c, v in zip(_c0, _v0) if v]].nlargest(top_k).index)
        assert "SPY" not in uni, "V3-3: SPY (market series) leaked into a partition universe"
        if len(uni) < k + 5:
            n_small += 1
            continue
        Rtr = R[t - corr_window:t, :][:, np.array([col_of[c] for c in uni], dtype=np.int64)]  # V3-1

        if paradigm == "gics":
            names = [gics.get(u.rsplit(".", 1)[0] if "." in u else u) for u in uni]  # V3-2
            keep = [i for i, s in enumerate(names) if s is not None]
            if len(keep) < k + 5:                     # coverage too thin this day
                n_small += 1
                continue
            uni = [uni[i] for i in keep]
            uniq = sorted({names[i] for i in keep})
            m = {s: j for j, s in enumerate(uniq)}
            lab = np.array([m[names[i]] for i in keep], dtype=np.int32)
        elif paradigm == "sponge":
            lab = sponge_labels(Rtr, k)
            if lab is None:
                n_fail += 1
                continue
            lab = np.asarray(lab, dtype=np.int32)
        else:
            lab = np.asarray(tourney_labels(paradigm, Rtr, k, seed, n_init, rng),
                             dtype=np.int32)

        if singleton_rule == "fix":
            # V3-4: same normalization for every paradigm. gics shrank uni after Rtr was
            # cut, so recompute the member columns from the CURRENT uni.
            _Rm = R[t - corr_window:t, :][:, np.array([col_of[c] for c in uni], dtype=np.int64)]
            _C = np.nan_to_num(np.corrcoef(_Rm.T), nan=0.0)
            lab = np.asarray(_FIX_TINY(lab, _C, 2), dtype=np.int32)
            _sz = np.bincount(lab)
            assert (_sz[_sz > 0] >= 2).all(), f"V3-4 broken: singleton survived on {ridx[t].date()}"
            assert int(lab.max()) < k or paradigm == "gics", "V3-4: label range grew"
        cache[pd.Timestamp(ridx[t])] = {"universe": list(uni), "labels": lab}
        if len(cache) % 500 == 0:
            _log(f"  ...{len(cache)} snapshots (through {ridx[t].date()}, "
                 f"{time.time() - t0:.0f}s)")

    _log(f"done: {len(cache)} snapshots, {n_small} days skipped (<{k+5} valid), "
         f"{n_fail} clustering failures, {time.time() - t0:.0f}s")
    if out_path:
        with open(out_path, "wb") as fh:
            pickle.dump(cache, fh, protocol=4)
        _log(f"wrote {out_path} ({os.path.getsize(out_path)} bytes)")
    return cache


def verify_kmeans(panel: str, n_days: int = 1500) -> int:
    # 1500, not a few hundred: the panel starts 1990-01-17 but the first ~850 rows
    # yield no snapshot at all (fewer than K+5 top-500 names have an all-finite 60d
    # residual window that early), so a short window compares zero dates and
    # vacuously "passes".
    """Regenerate k-means over the first `n_days` scored days and assert the labels
    match the existing pkl EXACTLY. This is the guarantee that generalising the
    generator did not perturb the paradigm that has already been run through the
    head — without it, the new family results would not be comparable to 2.5445."""
    if not os.path.isfile(KMEANS_REF):
        print(f"[verify] reference pkl absent: {KMEANS_REF}", file=sys.stderr)
        return 2
    ref = pd.read_pickle(KMEANS_REF)
    got = generate("kmeans_ret", panel, "", k=30, corr_window=60, beta_window=60,
                   top_k=500, seed=42, n_init=4, limit_days=n_days)
    common = sorted(set(ref) & set(got))
    if not common:
        print("[verify] FAIL: no overlapping dates", file=sys.stderr)
        return 1
    bad_u = bad_l = 0
    for d in common:
        if list(ref[d]["universe"]) != list(got[d]["universe"]):
            bad_u += 1
        elif not np.array_equal(np.asarray(ref[d]["labels"]),
                                np.asarray(got[d]["labels"])):
            bad_l += 1
    print(f"[verify] {len(common)} common dates | universe mismatches {bad_u} | "
          f"label mismatches {bad_l}")
    if bad_u or bad_l:
        print("[verify] FAIL — the generalised generator does NOT reproduce the "
              "existing k-means cache; do not use it.", file=sys.stderr)
        return 1
    print("[verify] PASS — byte-identical to labelcache_kmeans_ret_K30_daily_full.pkl")
    return 0


# ------------------------------------------------------- singleton-free twin arm
# `kmeans_ret_nosingle` — requested by the manuscript branch,
# JFEC_A_Manuscript/_reference/RUN_REQUEST_kmeans_twin.md (2026-08-15).
#
# WHY IT EXISTS. `kmeans_ret` is simultaneously the lowest-volatility arm in the field
# (2.741 % annualised vs 2.982 % for the next) and the ONLY arm that drops a material
# number of names from its book (10.8 singletons/day, traded universe 482.85 against
# ~492.07 everywhere else). Euclidean k-means on UNSTANDARDISED residual vectors isolates
# the most volatile stocks into singleton clusters; a singleton's cluster-relative series
# is identically zero, so `build_bet_sample` deletes it via SPONGE_MIN_CLUSTER_SIZE = 2 and
# the L1 renormalisation pushes its weight onto calmer names. Low volatility and a smaller
# universe are therefore confounded, and nine of eleven methods have a singleton rate of
# exactly zero, so the design has no variation to identify which does the work.
# This arm merges the singletons instead of dropping them. It is a TWIN, not a
# replacement: the difference between the two arms IS the measurement, so `kmeans_ret`
# must be left exactly as it is.
#
# ⚠ WHY THIS IS APPENDED HERE INSTEAD OF BEING WRITTEN INTO `tourney_labels`.
# JFEC_ML_Draft/scripts/window_panels.py:102-120 pins FOUR provenance assertions to line
# numbers in THIS file — lines 73, 74, 80 and 195 — and line 195 sits inside `generate()`.
# Inserting a branch into `tourney_labels` (lines 87-123) would shift line 195 and silently
# break a check that lives in another branch's tree. Everything below is strictly after
# line 195, so every pin still resolves to the text it expects.

_FIX_TINY = None
_NAN_C = [0]          # days on which the correlation matrix had a NaN; see below


def _canonical_fix_tiny_clusters():
    """Load `_fix_tiny_clusters` FROM THE TOURNAMENT ENGINE rather than copying it.

    The run request asks explicitly for the existing function and not a second
    implementation, citing the incident where three scripts carried three different
    validity gates and disagreed for days. A plain import is not available — the engine
    runs `matplotlib.use`, `os.makedirs(Config.OUTPUT_DIR)` and `torch.manual_seed` at
    module level — so the function's AST node is compiled on its own. If it is ever
    renamed or removed this raises, rather than silently falling back to a private copy
    that can drift away from the original.
    """
    import ast
    src_path = os.path.join(M15, "pipeline_v21_tourney_kmeans_ret.py")
    with open(src_path) as fh:
        tree = ast.parse(fh.read(), filename=src_path)
    node = next((n for n in tree.body
                 if isinstance(n, ast.FunctionDef) and n.name == "_fix_tiny_clusters"), None)
    if node is None:
        raise RuntimeError(f"_fix_tiny_clusters not found in {src_path}")
    ns = {"np": np}
    exec(compile(ast.Module(body=[node], type_ignores=[]), src_path, "exec"), ns)  # noqa: S102
    return ns["_fix_tiny_clusters"]


def twin_nosingle_labels(Rtr: np.ndarray, k: int, seed: int, n_init: int) -> np.ndarray:
    """`kmeans_ret`'s labels with every singleton merged into its most-correlated cluster.

    The KMeans call is character-for-character the one at :102-103, so the pre-merge
    labels are identical to `kmeans_ret`'s by construction — verified, not assumed, by
    `verify_twin()`.

    `kmeans_ret` never forms a correlation matrix (`tourney_labels` returns before
    `C = np.corrcoef(Rtr.T)` is reached), but the merge needs one, so it is computed here.
    """
    global _FIX_TINY
    from sklearn.cluster import KMeans
    if _FIX_TINY is None:
        _FIX_TINY = _canonical_fix_tiny_clusters()
    lab = KMeans(k, random_state=seed, n_init=n_init).fit_predict(Rtr.T)
    C = np.corrcoef(Rtr.T)
    # The universe filter already guarantees finite entries, so a NaN here means a
    # zero-variance column. Left unhandled it makes every affinity comparison False and
    # the orphan lands silently in `large_clusters[0]` — a complete, plausible, wrong
    # answer of exactly the kind CORRECTIONS.md exists to catch. Count it, do not hide it.
    if np.isnan(C).any():
        _NAN_C[0] += 1
        C = np.nan_to_num(C, nan=0.0)
    return _FIX_TINY(lab, C, 2)


def verify_twin(panel: str, n_days: int = 400) -> int:
    """Assert the twin is `kmeans_ret` plus a merge, and nothing else.

    Checks, on `n_days` sampled days: (a) the pre-merge labels are IDENTICAL to
    `tourney_labels("kmeans_ret", ...)`, (b) the merge only ever moves stocks that were
    in clusters of size < 2, and (c) the twin has zero singletons afterwards.
    """
    from sklearn.cluster import KMeans
    prices = pd.read_pickle(os.path.join(panel, "prices.pkl"))
    caps = pd.read_pickle(os.path.join(panel, "caps.pkl"))
    mask = pd.read_pickle(os.path.join(panel, "mask.pkl"))
    residuals = compute_residuals(prices, mask, beta_window=60)
    R = residuals.to_numpy(np.float64)
    ridx = residuals.index
    colmap = {c: j for j, c in enumerate(residuals.columns)}
    rng = np.random.default_rng(42)
    k, seed, n_init, w = 30, 42, 4, 60
    n_ok = n_moved = n_single_before = 0
    for t in range(w + 5, len(ridx), max(1, (len(ridx) - w - 5) // n_days)):
        _dc = caps.iloc[t - 1].dropna()                               # V3-1 (sampler)
        _p0 = np.array([colmap.get(c, -1) for c in _dc.index])
        _f0 = np.zeros(len(_dc), dtype=bool)
        if (_p0 >= 0).any():
            _f0[np.where(_p0 >= 0)[0]] = np.isfinite(R[t - w:t, :][:, _p0[_p0 >= 0]]).all(axis=0)
        cand = list(_dc[_f0].nlargest(500).index)
        jall = np.array([colmap.get(c, -1) for c in cand])
        priced = jall >= 0
        valid = np.zeros(len(cand), dtype=bool)
        if priced.any():
            win = R[t - w:t, :][:, jall[priced]]
            valid[np.where(priced)[0]] = np.isfinite(win).all(axis=0)
        if valid.sum() < k + 5:
            continue
        Rtr = R[t - w:t, :][:, jall[valid]]
        base = np.asarray(_tourney_labels_base("kmeans_ret", Rtr, k, seed, n_init, rng))
        km = KMeans(k, random_state=seed, n_init=n_init).fit_predict(Rtr.T)
        if not np.array_equal(base, km):
            print(f"[twin] FAIL {ridx[t].date()}: pre-merge labels differ from kmeans_ret")
            return 1
        twin = np.asarray(twin_nosingle_labels(Rtr, k, seed, n_init))
        _, cnt = np.unique(base, return_counts=True)
        small = {c for c, n in zip(*np.unique(base, return_counts=True)) if n < 2}
        moved = np.where(base != twin)[0]
        if any(base[i] not in small for i in moved):
            print(f"[twin] FAIL {ridx[t].date()}: merge moved a non-singleton member")
            return 1
        _, cnt2 = np.unique(twin, return_counts=True)
        if (cnt2 < 2).any():
            print(f"[twin] FAIL {ridx[t].date()}: singletons remain after merge")
            return 1
        n_single_before += int((cnt < 2).sum())
        n_moved += len(moved)
        n_ok += 1
    print(f"[twin] PASS — {n_ok} days, pre-merge labels identical to kmeans_ret on all of "
          f"them, {n_single_before/max(n_ok,1):.2f} singletons/day merged, "
          f"{n_moved/max(n_ok,1):.2f} stocks/day moved, 0 singletons remaining, "
          f"{_NAN_C[0]} days needed NaN handling in C")
    return 0


# ------------------------------------------------- size-constrained k-means arm
# `kmeans_ret_minsize` — the THIRD arm of the singleton decomposition, requested 2026-08-15.
#
# WHAT IT IS FOR. With `kmeans_ret` and `kmeans_ret_nosingle` the design still cannot separate
# two things, because the merge arm changes the traded name count while HOLDING the traded
# cluster count fixed at 19.42:
#
#   arm                    traded clusters   traded names   singleton handling
#   kmeans_ret                  19.42            479        deleted by build_bet_sample
#   kmeans_ret_nosingle         19.42            490        dissolved into a large cluster
#   kmeans_ret_minsize          30.00            490        forbidden during the fit
#
#   minsize - nosingle  isolates the CLUSTER COUNT at constant names
#   nosingle - kmeans   isolates the TRADED NAMES at constant cluster count
#   minsize - kmeans    is both, and must equal the sum if the effects are additive
#
# ⚠ THIS ARM CHANGES THE CLUSTERING ALGORITHM, the other two do not. Its labels are NOT
# kmeans_ret's plus a repair — the constraint is enforced inside the fit, so every label can
# move. That was raised as an objection and accepted deliberately: the arm's purpose is to
# supply the cluster-count leg, and there is no way to hold 30 populated clusters without
# changing how the partition is produced. Report it as a third algorithm, never as a twin.
#
# ⚠ A DEGENERACY TO MEASURE AND DISCLOSE, not to hide. The constraint binds at exactly 2 for
# the ~11 clusters that were singletons, so this arm carries ~11 clusters of size 2 (~22 names,
# ~4.5 % of the book). A 2-member cluster is algebraically degenerate under the strategy: the
# cluster mean is (a+b)/2, so raw_a = -raw_b EXACTLY, the pair is always one long and one short,
# and lambda1-share is identically (1+rho)/2. Report the size-2 mass and the book share sitting
# in it beside this arm's Sharpe.
#
# WHY NOT A MIN-COST-FLOW. Bradley-Bennett-Demiriz solves the assignment step as a min-cost
# flow, and networkx 2.6.3 is available — but it is a pure-Python solver on a ~522-node,
# ~14.7k-arc network, ~10 iterations x 7,911 days, i.e. hours per partition. The constraint here
# is very weak (490 points, 30 clusters, mean size 16, ~11 violations), so constrained Lloyd
# with a cheapest-steal repair inside the loop reaches the same constrained local optimum at
# k-means cost. `ortools` and `k_means_constrained` are not installed and cannot be installed.

def _enforce_min_size(lab: np.ndarray, D: np.ndarray, k: int, min_size: int) -> np.ndarray:
    """Repair an assignment so every cluster has >= min_size members, at least cost.

    D[i, j] is the squared distance from point i to centroid j. A deficient cluster steals the
    points whose REGRET D[i, j] - D[i, lab[i]] is smallest, and only from donors that can afford
    to lose one. Deterministic: ties break by point index via a stable argsort.
    """
    lab = lab.copy()
    for _ in range(k * 2):                       # bounded; each pass fixes >= 1 cluster
        sizes = np.bincount(lab, minlength=k)
        deficient = np.where(sizes < min_size)[0]
        if len(deficient) == 0:
            return lab
        j = int(deficient[np.argmin(sizes[deficient])])       # neediest first
        need = min_size - sizes[j]
        donor_ok = sizes > min_size                            # donors keep the invariant
        cand = np.where((lab != j) & donor_ok[lab])[0]
        if len(cand) == 0:                                     # no legal donor exists
            return lab
        regret = D[cand, j] - D[cand, lab[cand]]
        take = cand[np.argsort(regret, kind="stable")[:need]]
        lab[take] = j
    return lab


def constrained_kmeans_labels(Rtr: np.ndarray, k: int, seed: int, n_init: int,
                              min_size: int = 2, max_iter: int = 50) -> np.ndarray:
    """k-means on unstandardised residual vectors, subject to |cluster| >= min_size.

    WARM-STARTED FROM kmeans_ret's OWN SOLUTION. The first assignment is character-for-character
    `tourney_labels("kmeans_ret", ...)`, so when the constraint never binds this returns exactly
    kmeans_ret's labels and the arm degenerates to the baseline — which is the correct behaviour
    and is asserted in `verify_minsize`. When it does bind, Lloyd continues under the constraint
    until the assignment stops changing, i.e. it converges to a local optimum of the CONSTRAINED
    objective rather than post-processing an unconstrained one.
    """
    from sklearn.cluster import KMeans
    X = Rtr.T                                                  # (n_stocks, window)
    lab = KMeans(k, random_state=seed, n_init=n_init).fit_predict(X)
    cent = np.zeros((k, X.shape[1]), dtype=X.dtype)
    for it in range(max_iter):
        for j in range(k):
            m = lab == j
            if m.any():
                cent[j] = X[m].mean(axis=0)
            elif it == 0:
                cent[j] = X[np.argmax(((X - X.mean(0)) ** 2).sum(1))]   # seed an empty cluster
        D = ((X[:, None, :] - cent[None, :, :]) ** 2).sum(-1)
        new = _enforce_min_size(np.argmin(D, axis=1), D, k, min_size)
        if np.array_equal(new, lab):
            break
        lab = new
    return lab.astype(np.int32)


def verify_minsize(panel: str, n_days: int = 200) -> int:
    """Assert the constrained arm does what it claims: 30 populated clusters, none below
    min_size, no stock dropped, and — the check that matters — that it REDUCES to kmeans_ret
    on days where the constraint never binds."""
    from sklearn.cluster import KMeans
    prices = pd.read_pickle(os.path.join(panel, "prices.pkl"))
    caps = pd.read_pickle(os.path.join(panel, "caps.pkl"))
    mask = pd.read_pickle(os.path.join(panel, "mask.pkl"))
    residuals = compute_residuals(prices, mask, beta_window=60)
    R = residuals.to_numpy(np.float64)
    ridx = residuals.index
    colmap = {c: j for j, c in enumerate(residuals.columns)}
    k, seed, n_init, w = 30, 42, 4, 60
    n_ok = n_bind = n_reduce = 0
    ncl, npair, pairmass, moved = [], [], [], []
    for t in range(w + 5, len(ridx), max(1, (len(ridx) - w - 5) // n_days)):
        _dc = caps.iloc[t - 1].dropna()                               # V3-1 (sampler)
        _p0 = np.array([colmap.get(c, -1) for c in _dc.index])
        _f0 = np.zeros(len(_dc), dtype=bool)
        if (_p0 >= 0).any():
            _f0[np.where(_p0 >= 0)[0]] = np.isfinite(R[t - w:t, :][:, _p0[_p0 >= 0]]).all(axis=0)
        cand = list(_dc[_f0].nlargest(500).index)
        jall = np.array([colmap.get(c, -1) for c in cand])
        priced = jall >= 0
        valid = np.zeros(len(cand), dtype=bool)
        if priced.any():
            win = R[t - w:t, :][:, jall[priced]]
            valid[np.where(priced)[0]] = np.isfinite(win).all(axis=0)
        if valid.sum() < k + 5:
            continue
        Rtr = R[t - w:t, :][:, jall[valid]]
        base = np.asarray(KMeans(k, random_state=seed, n_init=n_init).fit_predict(Rtr.T))
        con = constrained_kmeans_labels(Rtr, k, seed, n_init, 2)
        _, cb = np.unique(base, return_counts=True)
        _, cc = np.unique(con, return_counts=True)
        if (cc < 2).any():
            print(f"[minsize] FAIL {ridx[t].date()}: cluster below min_size survived")
            return 1
        if len(cc) != k:
            print(f"[minsize] FAIL {ridx[t].date()}: {len(cc)} populated clusters, expected {k}")
            return 1
        if (cb >= 2).all():                       # constraint never binds -> must reduce
            n_reduce += 1
            if not np.array_equal(base, con):
                print(f"[minsize] FAIL {ridx[t].date()}: differs from kmeans_ret on a day "
                      "where the constraint does not bind")
                return 1
        else:
            n_bind += 1
        ncl.append(len(cc)); npair.append(int((cc == 2).sum()))
        pairmass.append(float(cc[cc == 2].sum()) / float(cc.sum()))
        moved.append(float((base != con).mean()))
        n_ok += 1
    print(f"[minsize] PASS — {n_ok} days, {n_cl_txt(ncl)} populated clusters, 0 below min_size, "
          f"constraint bound on {n_bind}/{n_ok} days, reduced to kmeans_ret on all "
          f"{n_reduce} non-binding days, {np.mean(npair):.2f} size-2 clusters/day carrying "
          f"{100*np.mean(pairmass):.2f}% of names, {100*np.mean(moved):.1f}% of labels moved")
    return 0


def n_cl_txt(v) -> str:
    return f"{np.mean(v):.2f}"


# ------------------------------------------------- SPONGE partition-seed support
# SPONGE was recorded in CORRECTIONS.md N22(f) as "cannot be reseeded through the current
# interface". ⚠ THAT WAS WRONG and is withdrawn — measured 2026-08-16 on one OOS day, K=30,
# N=495, by seeding numpy's GLOBAL RNG before the call:
#     seed 42 called twice   ARI 1.0000   (same seed reproduces exactly)
#     seed 42 vs seed 1      ARI 0.2485
#     seed 42 vs seed 123    ARI 0.2046
# signet's SPONGE_sym draws its LOBPCG start from numpy's global state, so a global seed is
# sufficient and `variant_f_v2a_clusterizer.run_sponge` — the LIVE path that built the published
# sponge cache — does not have to be touched. It is not touched.
#
# Note the size of that ARI: 0.20-0.25 is LOWER than the three already-measured rules
# (kmeans_ret 0.33, spectral_unsigned 0.41, pca_load 0.46) and lower than the 0.2194 measured
# BETWEEN DIFFERENT METHODS. Redrawing SPONGE's seed rearranges more structure than changing the
# algorithm does.
#
# ⚠ SEEDED ONCE AT IMPORT, NOT PER DAY. Reseeding before every day would reset the stream to the
# same state 7,911 times and induce identical LOBPCG starts across days; seeding once lets the
# stream advance naturally and still makes the whole cache a deterministic function of the seed.
# Nothing else in this module consumes the global stream — the `random` paradigm uses its own
# np.random.default_rng and sklearn takes random_state — so for the sponge paradigm the global
# draws belong to LOBPCG alone. Determinism is asserted by --verify-sponge-seed, not assumed.
#
# A no-op unless SPONGE_PARTITION_SEED is set, so every existing invocation is byte-identical.
_SPONGE_PSEED = os.environ.get("SPONGE_PARTITION_SEED")
if _SPONGE_PSEED:
    np.random.seed(int(_SPONGE_PSEED))
    _log(f"SPONGE partition seed = {_SPONGE_PSEED} (numpy global RNG seeded once, at import)")


def verify_sponge_seed(panel: str, n_days: int = 12) -> int:
    """Assert the seeded SPONGE path is deterministic per seed and differs across seeds.

    Runs the SAME day twice under one seed (must be identical) and once under another (must
    differ). Without this the arm could silently reproduce the seed-42 cache under a new name.
    """
    from sklearn.metrics import adjusted_rand_score
    prices = pd.read_pickle(os.path.join(panel, "prices.pkl"))
    caps = pd.read_pickle(os.path.join(panel, "caps.pkl"))
    mask = pd.read_pickle(os.path.join(panel, "mask.pkl"))
    residuals = compute_residuals(prices, mask, beta_window=60)
    R = residuals.to_numpy(np.float64)
    ridx = residuals.index
    colmap = {c: j for j, c in enumerate(residuals.columns)}
    w, k = CANONICAL_WINDOW["sponge"], 30
    same, diff, n = [], [], 0
    for t in range(w + 5, len(ridx), max(1, (len(ridx) - w - 5) // n_days)):
        _dc = caps.iloc[t - 1].dropna()                               # V3-1 (sampler)
        _p0 = np.array([colmap.get(c, -1) for c in _dc.index])
        _f0 = np.zeros(len(_dc), dtype=bool)
        if (_p0 >= 0).any():
            _f0[np.where(_p0 >= 0)[0]] = np.isfinite(R[t - w:t, :][:, _p0[_p0 >= 0]]).all(axis=0)
        cand = list(_dc[_f0].nlargest(500).index)
        jall = np.array([colmap.get(c, -1) for c in cand])
        priced = jall >= 0
        valid = np.zeros(len(cand), dtype=bool)
        if priced.any():
            valid[np.where(priced)[0]] = np.isfinite(R[t - w:t, :][:, jall[priced]]).all(axis=0)
        if valid.sum() < k + 5:
            continue
        Rtr = R[t - w:t, :][:, jall[valid]]
        out = []
        for s in (7, 7, 99):
            np.random.seed(s)
            lab = sponge_labels(Rtr, k)
            if lab is None:
                break
            out.append(np.asarray(lab))
        if len(out) != 3:
            continue
        same.append(adjusted_rand_score(out[0], out[1]))
        diff.append(adjusted_rand_score(out[0], out[2]))
        n += 1
    if not n:
        print("[sponge-seed] FAIL — no usable days"); return 1
    if min(same) < 0.9999:
        print(f"[sponge-seed] FAIL — same seed not reproducible, min ARI {min(same):.4f}"); return 1
    if max(diff) > 0.95:
        print(f"[sponge-seed] FAIL — different seeds give the same partition, max ARI {max(diff):.4f}"); return 1
    print(f"[sponge-seed] PASS — {n} days; same-seed ARI min {min(same):.4f}; "
          f"cross-seed ARI mean {np.mean(diff):.4f} max {max(diff):.4f}")
    return 0


MINSIZE = "kmeans_ret_minsize"
TWIN = "kmeans_ret_nosingle"
PARADIGMS = PARADIGMS + [TWIN, MINSIZE]
CANONICAL_WINDOW[TWIN] = 60
CANONICAL_WINDOW[MINSIZE] = 60

_tourney_labels_base = tourney_labels


def tourney_labels(name: str, Rtr: np.ndarray, k: int, seed: int, n_init: int,   # noqa: F811
                   rng: np.random.Generator) -> np.ndarray:
    """Dispatcher only. Every paradigm except the twin goes to the ORIGINAL function
    above, unchanged. This wrapper exists solely because the line-number pins documented
    at the top of this block forbid editing that function in place."""
    if name == TWIN:
        return twin_nosingle_labels(Rtr, k, seed, n_init)
    if name == MINSIZE:
        return constrained_kmeans_labels(Rtr, k, seed, n_init, 2)
    return _tourney_labels_base(name, Rtr, k, seed, n_init, rng)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    p.add_argument("--paradigm", choices=PARADIGMS)
    p.add_argument("--panel", default=os.environ.get("COMPAT_DIR", DEFAULT_PANEL))
    p.add_argument("--out")
    p.add_argument("--k", type=int, default=30)
    p.add_argument("--corr-window", type=int, default=None,
                   help="residual window for the clustering input; default = the "
                        "paradigm's canonical value (60 tourney / 21 sponge)")
    p.add_argument("--beta-window", type=int, default=60)
    p.add_argument("--top-k", type=int, default=500)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--n-init", type=int, default=4)
    p.add_argument("--limit-days", type=int, default=None)
    p.add_argument("--singleton-rule", choices=["fix", "raw"], default="fix",
                   help="V3-4: 'fix' = uniform engine _fix_tiny_clusters(min_size=2) on every "
                        "paradigm (the v3 canonical); 'raw' = old per-arm behavior, only for "
                        "measuring the unification delta")
    p.add_argument("--verify-kmeans", action="store_true")
    p.add_argument("--verify-twin", action="store_true",
                   help="assert kmeans_ret_nosingle == kmeans_ret + a singleton merge")
    p.add_argument("--verify-sponge-seed", action="store_true",
                   help="assert the seeded SPONGE path is deterministic per seed and differs "
                        "across seeds")
    p.add_argument("--verify-minsize", action="store_true",
                   help="assert kmeans_ret_minsize keeps 30 clusters, none below 2, and "
                        "reduces to kmeans_ret when the constraint does not bind")
    a = p.parse_args(argv)

    if a.verify_kmeans:
        return verify_kmeans(a.panel)
    if a.verify_twin:
        return verify_twin(a.panel)
    if a.verify_minsize:
        return verify_minsize(a.panel)
    if a.verify_sponge_seed:
        return verify_sponge_seed(a.panel)
    if not a.paradigm:
        p.error("--paradigm is required unless --verify-kmeans")
    cw = a.corr_window if a.corr_window is not None else CANONICAL_WINDOW[a.paradigm]
    if a.corr_window is not None and a.corr_window != CANONICAL_WINDOW[a.paradigm]:
        _log(f"NOTE: corr_window={cw} is NOT this paradigm's canonical "
             f"{CANONICAL_WINDOW[a.paradigm]} — this is a matched-window control, "
             f"label the output accordingly.")
    out = a.out or os.path.join(HERE,
                                f"labelcache_{a.paradigm}_K{a.k}_W{cw}_daily_full.pkl")
    generate(a.paradigm, a.panel, out, a.k, cw, a.beta_window, a.top_k,
             a.seed, a.n_init, a.limit_days, singleton_rule=a.singleton_rule)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
