"""§6.3's position-overlap trio: a rule's positions against the two peer books, relative to its own refit.

Same estimator as the tab:gradient position row (analysis/_positions.py). Per rule: the correlation of
its positions with each peer book (single runs at seed 42, as in tab:peer) at each of the rule's
the head seeds in paths.SEEDS, averaged; "own refit" is the rule's within-arm head-seed correlation (3 pairs);
plus the correlation between the two peer books. Every position file passes the three gates before
use (needs CSA_PANEL_ROOT). Output: analysis/results/pos_overlap_v3_cal6913.csv.

Run: ``CSA_PANEL_ROOT=... python analysis/pos_overlap_v3.py``
"""
from __future__ import annotations
import itertools, sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import _positions as X
from analysis._compare import compare_and_write

RULES = ["kmeans_ret", "agglo_complete", "fv3sm_w60", "sponge_w60", "pca_load", "agglo_avg",
         "sortino_w60", "fv2a_w60", "sharpe_fixed_w60", "gics", "spectral_unsigned", "sssnet_w60"]
FILE = {"sssnet_w60": "sssnetpre"}


def main() -> None:
    raw = X.masked_returns()
    B = {(a, s): X.gated_book(FILE.get(a, a), s, raw) for a in RULES for s in paths.SEEDS}
    PEER = {p: X.gated_book(f"peer_{p}", 42, raw) for p in ("w60", "w252")}
    assert all(v is not None for v in list(B.values()) + list(PEER.values())), "a position file failed a gate"
    days = X.common_days(*B.values(), *PEER.values())
    rows = []
    for a in RULES:
        vs_peer = float(np.mean([X.daily_corr(B[(a, s)], PEER[p], days) for s in paths.SEEDS for p in PEER]))
        own = float(np.mean([X.daily_corr(B[(a, s1)], B[(a, s2)], days) for s1, s2 in itertools.combinations(paths.SEEDS, 2)]))
        rows.append(dict(rule=a, vs_peer=vs_peer, own_refit=own, ratio=vs_peer / own))
        print(f"  {a:20s} vs_peer {vs_peer:.4f}  own {own:.4f}  ratio {vs_peer / own:.4f}", flush=True)
    D = pd.DataFrame(rows)
    print(f"vs_peer band {D.vs_peer.min():.4f}–{D.vs_peer.max():.4f}; ratio band {D.ratio.min():.4f}–{D.ratio.max():.4f}; "
          f"w60 vs w252 {X.daily_corr(PEER['w60'], PEER['w252'], days):.4f}")
    compare_and_write(D, "pos_overlap_v3_cal6913.csv", ["rule"])


if __name__ == "__main__":
    main()
