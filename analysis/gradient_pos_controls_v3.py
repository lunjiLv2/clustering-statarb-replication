"""The §5.4 companions to tab:gradient's position row, on the SAME day basis as that row.

tab:gradient's note says the position row is measured "on all 6,913 common days", and its numbers do
come from analysis/gradient_pos_v3.py, which uses the whole calendar. The companion figures in §5.4 --
a clusterizer against a control, the two controls against each other, the control and clusterizer
own-refit correlations, the pairwise band -- were read off the fig:bet_corr matrix instead, which is
measured on every 10th day (692 of the 6,913). Verified 2026-09-01: at three seeds the printed 0.477 /
0.70 / 0.67-0.74 reproduce on the stride-10 matrix (0.4772 / 0.7045 / 0.6783-0.7499) while the printed
own-refit 0.717 and across 0.62 reproduce on the full calendar, so the paragraph has been mixing two
day bases since before the seed change. This recomputes every companion on the full calendar so the
whole paragraph rests on one measurement.

Definitions are gradient_pos_v3's: positions are daily weight vectors, two books compared by the mean
daily correlation over the union of their names with absent names at zero, arms paired at the SAME
head seed and averaged over seeds, own-refit pairing the same arm at two head seeds. Prints only.

    CSA_PANEL_ROOT=... python analysis/gradient_pos_controls_v3.py
"""
from __future__ import annotations
import itertools, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import _positions as X

TWELVE = ["kmeans_ret", "agglo_complete", "fv3sm_w60", "sponge_w60", "sssnetpre", "pca_load",
          "agglo_avg", "sortino_w60", "fv2a_w60", "sharpe_fixed_w60", "gics", "spectral_unsigned"]
CTRL = ["k1", "random"]
FILE = {"sssnet_w60": "sssnetpre"}


def main() -> None:
    raw = X.masked_returns(); B = {}
    for arm in TWELVE + CTRL:
        for s in paths.SEEDS:
            b = X.gated_book(FILE.get(arm, arm), s, raw)
            assert b is not None, f"{arm} seed {s} failed the position gate"
            B[(arm, s)] = b
    days = X.common_days(*B.values()); print(f"common calendar: {len(days)} days", flush=True)
    S = paths.SEEDS

    across = [X.daily_corr(B[(i, s)], B[(j, s)], days) for s in S for i, j in itertools.combinations(TWELVE, 2)]
    within = [X.daily_corr(B[(a, s1)], B[(a, s2)], days) for a in TWELVE for s1, s2 in itertools.combinations(S, 2)]
    vs_ctl = [X.daily_corr(B[(a, s)], B[(c, s)], days) for s in S for a in TWELVE for c in CTRL]
    mutual = [X.daily_corr(B[("k1", s)], B[("random", s)], days) for s in S]
    ctl_own = {c: float(np.mean([X.daily_corr(B[(c, s1)], B[(c, s2)], days)
                                 for s1, s2 in itertools.combinations(S, 2)])) for c in CTRL}
    cl_own = [float(np.mean([X.daily_corr(B[(a, s1)], B[(a, s2)], days)
                             for s1, s2 in itertools.combinations(S, 2)])) for a in TWELVE]
    pair = [float(np.mean([X.daily_corr(B[(i, s)], B[(j, s)], days) for s in S]))
            for i, j in itertools.combinations(TWELVE, 2)]

    A, W, C = float(np.mean(across)), float(np.mean(within)), float(np.mean(vs_ctl))
    print(f"\nseeds {tuple(S)}  |  all {len(days)} days, 12 clusterizers")
    print(f"  own refit                {W:.4f}  -> {W:.3f}")
    print(f"  across clusterizers      {A:.4f}  -> {A:.3f}   (drop {W - A:.4f} -> {W - A:.2f})")
    print(f"  clusterizer vs control   {C:.4f}  -> {C:.3f}   (drop {W - C:.4f} -> {W - C:.2f})")
    print(f"  first drop as a share    {(W - A) / (W - C):.4f}  -> {100 * (W - A) / (W - C):.0f}%")
    print(f"  controls mutual          {np.mean(mutual):.4f}  -> {np.mean(mutual):.2f}")
    print(f"  control own refit        k1 {ctl_own['k1']:.4f} -> {ctl_own['k1']:.2f}   "
          f"random {ctl_own['random']:.4f} -> {ctl_own['random']:.2f}")
    print(f"  clusterizer own refit    {min(cl_own):.4f}-{max(cl_own):.4f}  -> {min(cl_own):.2f} to {max(cl_own):.2f}")
    print(f"  pairwise band            {min(pair):.4f}-{max(pair):.4f}  -> {min(pair):.3f} to {max(pair):.3f}")


if __name__ == "__main__":
    main()
