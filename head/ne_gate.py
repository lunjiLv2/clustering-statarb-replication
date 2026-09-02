#!/usr/bin/env python
"""
ne_gate.py — FIX 3: replace the full-sample book-balance gate with a rolling-window
maximum, and re-adjudicate every completed run.

WHY THE OLD GATE FAILS
    The pre-registered rule is  mean|NE| <= 0.30  =>  VALID, where NE is the daily
    net exposure (long - short)/gross. It was designed to catch exactly the failure
    mode we hit: a head that degenerates into a one-sided book. It did not catch it.

    k-means seed 7 traded a PURE LONG book for its first 241 days — mean|NE| over
    that stretch is 1.0000, i.e. not a single day was hedged. But 241 days is 3.5%
    of 6,941, so the full-sample mean is 0.0933 and the run passes a 0.30 bar with
    room to spare. A total failure was diluted below a third of the threshold by
    the 96.5% of the sample that was healthy.

    Worse, the degenerate stretch was PROFITABLE (Sharpe +2.04 over those 241 days)
    because 1997-98 was a rising market, so nothing downstream looked wrong either.
    A market-neutral strategy silently became a long-only fund and still made money.

THE FIX
    Gate on  max over rolling W-day windows of mean|NE|  instead of the full-sample
    mean. A localised failure can no longer be averaged away.

SEPARATION (measured on the four completed k-means seeds, W=250):
    seed 42  full 0.0588   rolling-max 0.1204   VALID
    seed  1  full 0.0608   rolling-max 0.1123   VALID
    seed123  full 0.0589   rolling-max 0.1343   VALID
    seed  7  full 0.0933   rolling-max 1.0000   INVALID   <-- caught
    Healthy runs top out at 0.13; the failed run hits 1.00. The 0.30 bar sits with
    roughly an 8x margin on either side, so the threshold needs no retuning — only
    the statistic does.

READ-ONLY. Reads the per-day CSVs; writes nothing except --out.

USAGE
    server_package/_sol_base/.venv/bin/python server_package/head_fix/ne_gate.py
    ... --window 250 --threshold 0.30 [--out gate_report.txt]
"""
from __future__ import annotations

import argparse
import glob
import os
import sys

import numpy as np
import pandas as pd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def discover() -> dict[str, str]:
    """label -> per-day CSV path, over every completed run of the CURRENT generation.

    GENERATION (CORRECTIONS N39(f)). This function used to glob
    `sssnet_seed_sweep/runs/*` unconditionally — the V2 tree — and read no NS_GEN. It
    therefore FAILED OPEN: called from a v3 context it returned v2 books, silently, with
    no error. A caller that loaded some books by explicit path and the rest through here
    got a mixed-generation result that ran clean and produced a plausible table. That
    nearly happened to the v3 rebuild of tab:peer; only an unrelated directory rename made
    an assert fire.

    NS_GEN=v3 selects `sssnet_seed_sweep/runs_v3/`; unset or v2 keeps the V2 tree and is
    byte-identical to the historical behaviour, so the fourteen scripts that call this and
    predate the v3 delivery are unaffected. The two frozen a2_reruns books are V2-only and
    are not offered under v3 — they have no v3 counterpart, and returning them would
    reintroduce exactly the mixing this guard exists to stop.

    Every returned path is asserted to lie under the selected tree before it is handed
    back: a generation switch that is not checked at the point of use is how N36 and
    N39(f) both happened.
    """
    gen = os.environ.get("NS_GEN", "").strip() or "v2"   # empty env var == unset
    if gen not in ("v2", "v3"):
        raise SystemExit(f"NS_GEN must be v2 or v3, got {gen!r}")
    runs_rel = ("server_package/sssnet_seed_sweep/runs_v3" if gen == "v3"
                else "server_package/sssnet_seed_sweep/runs")
    runs_root = os.path.join(REPO, runs_rel)

    out: dict[str, str] = {}
    if gen == "v2":
        fixed = {
            "kmeans_seed42": "server_package/a2_reruns/runs/kmeans_k30/full/"
                             "output_tourney_kmeans_ret/log_sponge_l1norm_20260806_091746.csv",
            "sssnet_seed42": "server_package/a2_reruns/runs/sssnet_k30/full/"
                             "output_sssnet_K30_daily/log_sponge_l1norm_20260806_094735.csv",
        }
        for k, rel in fixed.items():
            p = os.path.join(REPO, rel)
            if os.path.isfile(p):
                out[k] = p
    for run in sorted(glob.glob(os.path.join(runs_root, "*"))):
        name = os.path.basename(run)
        if gen == "v3" and name.startswith("_"):
            continue                      # _cancelled_partials/, _superseded_fixpartition/
        csvs = sorted(glob.glob(os.path.join(run, "log_sponge_l1norm_*.csv")))
        if csvs:
            label = name if name.startswith(("kmeans_", "family_")) else f"sssnet_{name}"
            out[label] = csvs[-1]

    # An EMPTY result is never a valid answer here: every generation has runs on disk, and
    # returning {} would let a caller's "all paths are correct" check pass vacuously — which
    # is how this patch's own first test round produced a false green.
    assert out, f"discover(NS_GEN={gen}): no runs found under {runs_root}"
    # POINT-OF-USE ASSERTION: every path must lie under the tree this generation selected.
    marker = "/runs_v3/" if gen == "v3" else "/runs/"
    for lbl, p in out.items():
        if lbl in ("kmeans_seed42", "sssnet_seed42"):
            continue                      # the two frozen v2 books live under a2_reruns/
        assert marker in p, (
            f"discover(NS_GEN={gen}): {lbl} resolved to {p}, which is not under {marker}")
    return out


def adjudicate(path: str, window: int, thresh: float) -> dict | None:
    try:
        d = pd.read_csv(path, parse_dates=["Date"]).sort_values("Date")
    except Exception as exc:                                   # noqa: BLE001
        print(f"  [warn] unreadable {path}: {exc}", file=sys.stderr)
        return None
    if "NetExposure" not in d or d["Date"].isna().any():
        return None
    if len(d) == 0:
        # header-only CSV (a crashed run's stub): idxmax on the empty rolling series would
        # RAISE, making gate_ok crash instead of returning False (audit 2026-08-18).
        return None
    ne = d["NetExposure"].abs()
    roll = ne.rolling(window).mean()
    imax = roll.idxmax()
    p = d["DailyPnL"].to_numpy(float)
    sr = np.sqrt(252.0) * p.mean() / p.std(ddof=1) if p.std(ddof=1) > 0 else np.nan
    # PRIMARY criterion: days on which the book is purely long or purely short.
    n_pure = n_one_sided(d)
    first_pure = None
    if n_pure > 0:
        m = (d["N_Short"] == 0) | (d["N_Long"] == 0)
        first_pure = d.loc[m, "Date"].iloc[0].date()
    return {
        "days": len(d),
        "SR": sr,
        "full": float(ne.mean()),
        "rollmax": float(roll.max()),
        "n_pure": n_pure,
        "first_pure": first_pure,
        # the window END date; the offending stretch is the `window` days before it
        "worst_end": d.loc[imax, "Date"].date() if pd.notna(imax) else None,
        "old_verdict": "VALID" if ne.mean() <= thresh else "INVALID",
        # n_pure == -1 means the columns are missing: unprovable, therefore not valid
        "new_verdict": "VALID" if n_pure == 0 else "INVALID",
    }


def n_one_sided(d: pd.DataFrame) -> int:
    """Days on which the book held no shorts or no longs. THE validity statistic.

    Frame-level so that callers holding a DataFrame (compare_family, compare_seeds)
    and callers holding a path (head_lift, this module) share one implementation.
    Returns -1 when the columns are absent, which no caller may treat as valid.
    """
    if not {"N_Long", "N_Short"} <= set(d.columns):
        return -1
    return int(((d["N_Short"] == 0) | (d["N_Long"] == 0)).sum())


def gate_ok(path: str) -> bool:
    """THE campaign's single validity criterion. Import this; do not re-implement it.

    Three scripts previously carried three different cuts — head_lift.py and
    compare_family.py on rolling-250 mean|NE| <= 0.30, compare_seeds.py on the
    full-sample mean (which stamps the frozen seed-7 runs VALID). The audit of
    2026-08-10 found the tables had been frozen against the rolling cut after it was
    retired here, and that it culls 3 of the 4 valid `random` seeds while keeping the
    highest one — which is what made the published "a random partition still gains
    +0.5197" true. On all four it is +0.4070, the smallest lift in the field.

    An unreadable or malformed CSV is NOT valid: it cannot be shown to have zero
    one-sided days, and silently averaging it in is how the previous gate failed.
    """
    r = adjudicate(path, 250, 0.30)
    return r is not None and r["new_verdict"] == "VALID"


def sharpe_if_valid(path: str) -> float | None:
    """Full-sample Sharpe, or None if the run fails `gate_ok`."""
    r = adjudicate(path, 250, 0.30)
    if r is None or r["new_verdict"] != "VALID":
        return None
    return float(r["SR"])


def verdict3(x: float, thresh: float = 0.30, band: float = 0.05) -> str:
    """RETIRED — kept only so older callers do not break. Do not gate on this.

    The rolling-|NE| threshold was an improvement on the full-sample mean, but it is
    still a cut through a continuous statistic, and the statistic is not reproducible:
    the same arm rerun with the same seed, code and GPU moved pca_load 0.2868 -> 0.3006
    and random 0.3202 -> 0.2610, flipping the verdict in both directions. Worse, it
    conflates two different things — a head that COLLAPSED, and a partition that is
    merely hard to hedge. random_seed1 and random_seed11 score 0.4451 and 0.4099 yet
    never once trade a one-sided book; being persistently tilted is a property of random
    partitions worth observing, not a failed run to be deleted.

    Use the pure-one-sided-day count instead (see adjudicate). Rationale: a
    market-neutral book should have ZERO days with no shorts. One such day is a
    structural failure, not a matter of degree — so the threshold is 0, not a tuned
    constant, and no reproducibility band is needed.

    Measured separation over 47 runs: exactly 4 have any one-sided day, and all four
    are seed 7 (kmeans, sssnet, gics, random), each with ~250 pure-long days and a
    rolling |NE| of exactly 1.0000. The other 43 have zero. No boundary cases.
    """
    if x < thresh - band:
        return "VALID"
    if x > thresh + band:
        return "INVALID"
    return "UNCERTAIN"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=250,
                    help="rolling window in trading days (250 ~= one year)")
    ap.add_argument("--threshold", type=float, default=0.30,
                    help="the pre-registered bar; only the STATISTIC changes, not this")
    ap.add_argument("--out")
    a = ap.parse_args()

    lines: list[str] = []

    def emit(s: str = "") -> None:
        print(s)
        lines.append(s)

    emit("=" * 100)
    emit(f"BOOK-BALANCE GATE — full-sample mean|NE| vs rolling-{a.window}d max, bar = {a.threshold}")
    emit("=" * 100)
    emit(f"{'run':26s} {'days':>5s} {'SR':>7s} {'pure':>5s} {'full':>7s} {'roll':>7s} "
         f"{'verdict':>8s}  first one-sided day")
    emit("-" * 100)

    flipped = []
    for label, path in sorted(discover().items()):
        r = adjudicate(path, a.window, a.threshold)
        if r is None:
            continue
        flag = "  <-- FLIPPED" if r["old_verdict"] != r["new_verdict"] else ""
        emit(f"{label:26s} {r['days']:5d} {r['SR']:7.4f} {r['n_pure']:5d} {r['full']:7.4f} "
             f"{r['rollmax']:7.4f} {r['new_verdict']:>8s}  {r['first_pure'] or ''}{flag}")
        if r["old_verdict"] != r["new_verdict"]:
            flipped.append((label, r))

    emit()
    if flipped:
        emit(f"{len(flipped)} run(s) reclassified by the rolling statistic:")
        for label, r in flipped:
            emit(f"  {label}: {r['n_pure']} one-sided days (first {r['first_pure']}), "
                 f"Sharpe {r['SR']:.4f} — the pre-registered full-sample mean was only "
                 f"{r['full']:.4f} and passed it.")
    else:
        emit("No run is reclassified at this window/threshold.")
    emit()
    emit("CRITERION: a run is INVALID if it has ANY day with no shorts or no longs. A")
    emit("market-neutral book should never have one, so the threshold is 0 rather than a")
    emit("tuned constant, and there is no reproducibility band to argue about. `full` and")
    emit("`roll` are printed as diagnostics only — a high roll with zero one-sided days")
    emit("means a persistently tilted book, which for a random partition is a property")
    emit("worth reporting, not a failed run.")
    emit("=" * 100)

    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        print(f"\nwritten: {a.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
