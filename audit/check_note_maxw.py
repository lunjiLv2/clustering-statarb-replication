"""Two table-note claims that no producer owns, both measured ACROSS RUNS so both move when the
seed set changes (2026-09-01):

  tab:head  note b  "the clip never binds on any run-day of this article (largest |w_it| is 0.007)"
                    -> max |w| over every run-day of every arm x seed in CSA_SEEDS.
  tab:sizes note    "averaging instead over the partition redraws moves no effective-K entry by
                    more than 0.03" -> effective K (inverse-Simpson) on each arm's main partition
                    against the mean over that arm's partition redraws.

Prints only; writes nothing.  CSA_SEEDS selects the seed set.
"""
from __future__ import annotations
import sys, glob, os, pickle
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books

CLIP = 0.04


def max_abs_weight() -> None:
    worst = (0.0, None)
    n_run = n_day = 0
    for a in paths.ARMS:
        for s in paths.SEEDS:
            try:
                pos = books.positions(a, s)
            except Exception as e:
                print(f"  [skip] {a} seed{s}: {e}"); continue
            n_run += 1
            m = 0.0
            for _d, _n, w in pos:
                n_day += 1
                v = float(np.max(np.abs(w))) if len(w) else 0.0
                if v > m: m = v
            if m > worst[0]: worst = (m, f"{a} seed{s}")
    print(f"tab:head note b — {n_run} runs, {n_day} run-days")
    print(f"  largest |w_it| = {worst[0]:.6f}  at {worst[1]}   (printed 0.007; hard clip {CLIP})")
    print(f"  clip binds: {'YES' if worst[0] >= CLIP else 'no'}")


# The partition-seed set tab:sizes averages over. A number computed while some redraws are still
# being generated is not a preliminary version of the right number -- it is a different statistic on
# a different set, and it prints without any warning. This producer emitted 0.092 against the
# printed 0.03 that way on 2026-09-01, off a third of the redraws (several of which were also the
# quarantined --singleton-rule fix batch). REDRAWS is therefore asserted, not discovered.
REDRAWS = ("_ps1", "_ps2", "_ps3", "_ps4", "_ps5")


# tab:sizes' claim covers EVERY arm. The repository ships one partition tree, data/derived/partitions/
# ({arm}.pkl = the main draw, {arm}_ps{1..5}.pkl = the five redraws, all ten stochastic arms), so every
# arm is resolved there; the authors' campaign kept them in three trees, which is why this used to be
# a three-root lookup (N87).
def part_path(arm: str, t: str = "") -> str | None:
    p = paths.PARTITIONS / f"{arm}{t}.pkl"
    return str(p) if p.is_file() else None


def eff_k(require_complete: bool = True) -> None:
    """tab:sizes note (N87 wording): 'averaging instead over the five partition redraws moves the k-means entry
    from 9.90 to 9.97 and no other entry by more than 0.02'.
    Measured as the table measures it: inverse-Simpson effective K of the partition in force on each of the
    6,913 common days, averaged over the days -- not every 20th labelcache key, which put the k-means gap at 0.12.
    Covers all ten stochastic arms across the three partition trees."""
    import pandas as pd
    from analysis import books
    cal = pd.DatetimeIndex(books.IDX); assert len(cal) == 6913

    def eff_k_days(pkl: str) -> float:
        d = pickle.load(open(pkl, "rb")); keys = sorted(d)
        ki = pd.DatetimeIndex([pd.Timestamp(k).normalize() for k in keys])
        pos = ki.searchsorted(cal, side="right") - 1; assert (pos >= 0).all()
        cache = {}
        for j in np.unique(pos):
            lab = np.asarray(d[keys[j]]["labels"]); _, c = np.unique(lab, return_counts=True)
            pr = c / c.sum(); cache[j] = 1.0 / float((pr ** 2).sum())
        return float(np.mean([cache[j] for j in pos]))

    print("\ntab:sizes note — effective K on the 6,913 common days, main partition vs the mean over its five redraws")
    arms = ["kmeans_ret", "pca_load", "spectral_unsigned", "sponge_w60", "random",
            "sssnetpre", "fv2a_w60", "fv3sm_w60", "sharpe_fixed_w60", "sortino_w60"]
    incomplete = {a: [t for t in REDRAWS if part_path(a, t) is None] for a in arms}
    incomplete = {a: m for a, m in incomplete.items() if m}
    if incomplete:
        msg = "; ".join(f"{a} missing {','.join(m)}" for a, m in incomplete.items())
        if require_complete:
            print(f"  REFUSING to report: the redraw set is incomplete -- {msg}"); return
        print(f"  WARNING partial redraw set: {msg}")
    worst = (0.0, None); second = 0.0
    for arm in arms:
        if arm in incomplete: continue
        m = eff_k_days(part_path(arm)); r = [eff_k_days(part_path(arm, t)) for t in REDRAWS]
        d = abs(m - float(np.mean(r)))
        print(f"  {arm:22s} main {m:6.2f}  redraws {len(r)} mean {np.mean(r):6.2f}  |diff| {d:.3f}")
        if d > worst[0]: second = worst[0]; worst = (d, arm)
        elif d > second: second = d
    km = (round(eff_k_days(part_path("kmeans_ret")), 2), round(float(np.mean([eff_k_days(part_path("kmeans_ret", t)) for t in REDRAWS])), 2))
    ok = worst[1] == "kmeans_ret" and km == (9.90, 9.97) and second <= 0.02
    print(f"  k-means main {km[0]:.2f} -> redraw mean {km[1]:.2f} (printed 9.90 -> 9.97); largest other |diff| {second:.3f} (printed: no other entry by more than 0.02)")
    print(f"  {'PASS' if ok else 'FAIL'}  tab:sizes redraw clause")


if __name__ == "__main__":
    print(f"seeds {tuple(paths.SEEDS)}\n")
    max_abs_weight(); eff_k()
