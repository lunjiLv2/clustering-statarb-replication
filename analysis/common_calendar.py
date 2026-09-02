"""THE common calendar — computed once, asserted everywhere.

6,913 days, 1997-07-08 .. 2024-12-27. User decision 2026-08-23.

It is the intersection of BOTH components: all fourteen arms' trained series across all three
head seeds (6,914 days), further intersected with the rule-based series. The rule-based engine
never emits a row for the panel's LAST day — `p1_lib.py:167` loops
`range(BETA_W + SIG_W, len(ridx) - 1)` and indexes `d_idx + 1` for the payoff — so all fourteen
rule-based series stop at 2024-12-27 and none of them is missing any other day. A 6,914-day
calendar therefore governs only the trained layer, and every cross-layer exhibit under it would
carry a footnote or silently drop a day on reindex. Dropping that one day costs at most
0.0052 Sharpe across the field, a fifth of the GPU reproduction floor of 0.024.

Deriving it per-exhibit is exactly how a partially-migrated table produces a plausible wrong
number instead of an error, so it is computed here, written to disk, and every downstream
script loads and asserts against THIS file rather than recomputing.

Usage:
    from common_calendar import CAL, assert_on   # CAL is a DatetimeIndex
    assert_on(series_or_index, "what this is")   # raises unless it covers CAL exactly
"""
import glob, os, sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths
OUT = str(paths.ROOT / "analysis" / "COMMON_CALENDAR_v3.csv")     # the shipped calendar every module reads
RUNS = f"{paths.CAMPAIGN}/sssnet_seed_sweep/runs_v3" if paths.CAMPAIGN else None   # _build() only (authors; CSA_CAMPAIGN_ROOT)
SEEDS = (42, 1, 123)   # 3seed-ok: _build() reconstructs the calendar from the ORIGINAL three-seed
                       # campaign that defined it; the CSV it wrote is what every module reads, so
                       # this path is dormant. Rebuilding on five seeds would redefine the common
                       # window and silently move every printed number -- do not "modernise" it.
DIRS = {"kmeans_ret": "family_kmeans_ret_seed{s}", "sponge_w60": "family_sponge_w60_seed{s}",
        "agglo_avg": "family_agglo_avg_seed{s}", "agglo_complete": "family_agglo_complete_seed{s}",
        "pca_load": "family_pca_load_seed{s}", "spectral_unsigned": "family_spectral_unsigned_seed{s}",
        "gics": "family_gics_seed{s}", "fv2a_w60": "family_fv2a_w60_seed{s}",
        "fv3sm_w60": "family_fv3sm_w60_seed{s}", "sortino_w60": "family_sortino_w60_seed{s}",
        "sharpe_fixed_w60": "family_sharpe_fixed_w60_seed{s}", "sssnet_w60": "sssnetw60_seed{s}",
        "k1": "family_k1_seed{s}", "random": "family_random_seed{s}"}


def _build():
    """trained-layer intersection, then intersected with the rule-based layer."""
    idx = None
    per = {}
    for a, pat in DIRS.items():
        for s in SEEDS:
            c = sorted(glob.glob(f"{RUNS}/{pat.format(s=s)}/log_sponge_l1norm_*.csv"))
            assert c, f"{a} seed{s}: no log"
            d = pd.read_csv(c[-1], parse_dates=["Date"]).Date
            per[(a, s)] = len(d)
            i = pd.DatetimeIndex(d)
            idx = i if idx is None else idx.intersection(i)
    trained = idx.sort_values()
    # ---- intersect with the RULE-BASED component -----------------------------------
    D = f"{REPO}/server_package/naive_routeA/daily_v3"
    NB = {"kmeans_ret": "kmeans_ret", "sponge_w60": "sponge_w60", "agglo_avg": "agglo_avg",
          "agglo_complete": "agglo_complete", "pca_load": "pca_load",
          "spectral_unsigned": "spectral_unsigned", "gics": "gics", "fv2a_w60": "fv2a_w60",
          "fv3sm_w60": "fv3sm_w60", "sortino_w60": "sortino_w60",
          "sharpe_fixed_w60": "sharpe_fixed_w60", "sssnet_w60": "sssnetw60_seed42",
          "k1": "k1", "random": "random"}
    both = trained
    for a, fn in NB.items():
        p = os.path.join(D, f"{fn}.csv")
        assert os.path.exists(p), f"rule-based {a}: {p} missing"
        i = pd.DatetimeIndex(pd.read_csv(p, parse_dates=["Date"]).Date)
        per[(a, "rule")] = len(i)
        both = both.intersection(i)
    assert len(both) == len(trained) - 1, (
        f"expected the rule layer to cost exactly the panel's last day; trained "
        f"{len(trained)}, both {len(both)}")
    return both.sort_values(), per


if os.path.exists(OUT):
    CAL = pd.DatetimeIndex(pd.read_csv(OUT, parse_dates=["Date"]).Date)
else:
    CAL, _per = _build()
    pd.DataFrame({"Date": CAL}).to_csv(OUT, index=False)

N_CAL = len(CAL)


def assert_on(obj, what, allow_superset=False):
    """Raise unless `obj`'s dates cover CAL exactly (or as a superset if allowed)."""
    i = pd.DatetimeIndex(obj.index if hasattr(obj, "index") else obj)
    miss = CAL.difference(i)
    assert len(miss) == 0, (f"[CALENDAR] {what}: missing {len(miss)} of {N_CAL} common days, "
                            f"first {miss[0].date()} last {miss[-1].date()}")
    extra = i.difference(CAL)
    if not allow_superset:
        assert len(extra) == 0, (f"[CALENDAR] {what}: {len(extra)} days OUTSIDE the common "
                                 f"calendar, first {extra[0].date()} last {extra[-1].date()}")
    return True


if __name__ == "__main__":
    CAL2, per = _build()
    assert CAL2.equals(CAL), "rebuild disagrees with the file on disk"
    print(f"COMMON CALENDAR: {N_CAL} days  {CAL[0].date()} .. {CAL[-1].date()}")
    print(f"  -> {OUT}")
    n = pd.Series(per)
    print(f"\n  per-run day counts: {sorted(set(n.values))}")
    for v in sorted(set(n.values)):
        arms = sorted({a for (a, s), c in per.items() if c == v})
        print(f"    {v} days: {len(arms)} arms — {', '.join(arms)}")
    # the rule-based component, which the peer flagged as 6,943 not 6,944
    D = f"{REPO}/server_package/naive_routeA/daily_v3"
    print("\n  rule-based component coverage of the common calendar:")
    for a in ("kmeans_ret", "gics", "random", "k1", "sssnetw60_seed42"):
        p = f"{D}/{a}.csv"
        if not os.path.exists(p): print(f"    {a:20s} MISSING"); continue
        i = pd.DatetimeIndex(pd.read_csv(p, parse_dates=["Date"]).Date)
        miss = CAL.difference(i)
        print(f"    {a:20s} n={len(i)}  covers CAL: {len(miss)==0}"
              + ("" if not len(miss) else f"  MISSING {len(miss)}: {miss[0].date()}..{miss[-1].date()}"))
