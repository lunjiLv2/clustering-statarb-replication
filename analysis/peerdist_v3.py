"""A.12 — how close each clusterizer's book and positions are to the two peer books.

Four quantities, all on the 6,913-day common calendar:
  * the share of a clusterizer's payoff variance the two peer books explain (R^2 of the payoff on
    W60 and W252), and its rank correlation with the arm's Sharpe ratio;
  * the mean daily correlation between a clusterizer's positions and the peer books' (the
    _positions.daily_corr definition: union of the two books' names, absent names at zero);
  * that overlap as a fraction of what the clusterizer shares with its own refit (the mean over
    head-seed pairs of the same arm);
  * the overlap between the two peer books themselves.

Positions run on the FULL calendar, matching tab:gradient's position row and analysis/gradient_pos_v3
rather than the stride-10 fig:bet_corr matrix (CORRECTIONS N83 add. 1). Prints only; writes nothing.

    CSA_PANEL_ROOT=... python analysis/peerdist_v3.py
"""
from __future__ import annotations
import itertools, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books, _positions as X
from scipy.stats import spearmanr

CTL = ("k1", "random")
PEERS = {"W60": "peer_w60", "W252": "peer_w252"}


def main() -> None:
    cl = [a for a in paths.ARMS if a not in CTL]
    S = tuple(paths.SEEDS)

    # --- payoff variance explained -------------------------------------------------
    P = pd.concat({k: books.head_book(v, 42) for k, v in PEERS.items()}, axis=1).reindex(books.IDX)
    D = np.column_stack([np.ones(len(P))] + [P[c].to_numpy(float) for c in P.columns])
    r2, sh = {}, {}
    for a in cl:
        y = books.head_avg(a).reindex(books.IDX).to_numpy(float)
        b = np.linalg.lstsq(D, y, rcond=None)[0]
        r2[a] = 1 - float((y - D @ b).var(ddof=0) / y.var(ddof=0))
        sh[a] = books.sharpe(books.head_avg(a))
    v = np.array([r2[a] for a in cl]); s = np.array([sh[a] for a in cl])
    sp = spearmanr(v, s)
    print(f"seeds {S}")
    print(f"  payoff variance explained  {v.min():.4f}-{v.max():.4f}   "
          f"Spearman vs Sharpe rho {sp.statistic:+.3f}  p {sp.pvalue:.3f}")

    # --- position overlap ----------------------------------------------------------
    raw = X.masked_returns(); B = {}
    for a in cl:
        for sd in S:
            b = X.gated_book(a, sd, raw)
            assert b is not None, f"{a} seed {sd} failed the position gate"
            B[(a, sd)] = b
    for k, v_ in PEERS.items():
        b = X.gated_book(v_, 42, raw)
        assert b is not None, f"{v_} failed the position gate"
        B[(k, 42)] = b
    days = X.common_days(*B.values()); print(f"  common calendar: {len(days)} days", flush=True)

    vs_peer = {a: float(np.mean([X.daily_corr(B[(a, sd)], B[(p, 42)], days)
                                 for sd in S for p in PEERS])) for a in cl}
    own = {a: float(np.mean([X.daily_corr(B[(a, s1)], B[(a, s2)], days)
                             for s1, s2 in itertools.combinations(S, 2)])) for a in cl}
    frac = {a: vs_peer[a] / own[a] for a in cl}
    pp = X.daily_corr(B[("W60", 42)], B[("W252", 42)], days)
    o = np.array([vs_peer[a] for a in cl])
    sp2 = spearmanr(o, s)
    print(f"  positions vs the peer books  {o.min():.4f}-{o.max():.4f}   "
          f"Spearman vs Sharpe rho {sp2.statistic:+.3f}  p {sp2.pvalue:.3f}")
    fr = np.array([frac[a] for a in cl])
    print(f"  as a fraction of own refit   {fr.min():.4f}-{fr.max():.4f}")
    print(f"  the two peer books together  {pp:.4f}")


if __name__ == "__main__":
    main()
