"""Seven-factor (FF5+MOM+ST_Rev) spanning next to the six-factor values (tab:spanning's
'+Reversal' block, tab:peer's reversal columns, §6.2).

For every arm the rule book (factors at shift 0) and the seed-averaged trained book (factors at
shift 1) are regressed on FF5+MOM and on FF5+MOM+ST_Rev, full sample and by era (split at
1 January 2009); alphas in percent per year, Newey–West t at 21 lags. A second table regresses
the trained books on the factors alone and on the factors plus the two peer books
(60- and 252-day windows, unshifted), with and without ST_Rev.

Outputs: analysis/results/strev_spanning_v3_cal6913.csv, strev_peer_v3_cal6913.csv (arm names as
in paths.ARMS, i.e. 'sssnetpre' for the fixed-partition SSSNET arm).

Run: ``python analysis/strev_spanning_v3.py``
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books
from analysis.factors import FF6, load_ff, nw_ols, alpha_pct
from analysis._compare import compare_and_write

FF7 = FF6 + ["ST_Rev"]
ERAS = {"full": lambda i: np.ones(len(i), bool), "1997-2008": lambda i: np.asarray(i < "2009-01-01"),
        "2009-2024": lambda i: np.asarray(i >= "2009-01-01")}


def peer_book(window: str) -> pd.Series:
    """Daily payoff of the peer (non-partition) trading head, seed 42, on the common calendar."""
    return books._read(paths.HEAD_LOGS / f"peer_{window}_seed42.csv")


def main() -> None:
    ff = load_ff(with_reversal=True)[FF7]
    assert ff.reindex(books.IDX)["ST_Rev"].notna().all(), "ST_Rev missing on the common calendar"
    rows = []
    for comp, loader, shift in (("rule", books.rule_book, 0), ("head", books.head_avg, 1)):
        M = pd.concat({a: loader(a) for a in paths.ARMS}, axis=1).join(ff.shift(shift), how="inner").reindex(books.IDX)
        assert M.notna().all().all(), f"{comp}: NaN after the factor join"
        for era, mask in ERAS.items():
            m = mask(M.index); X6 = M.loc[m, FF6].to_numpy(float); X7 = M.loc[m, FF7].to_numpy(float)
            for a in paths.ARMS:
                y = M.loc[m, a].to_numpy(float); b6, t6, r6 = nw_ols(y, X6); b7, t7, r7 = nw_ols(y, X7)
                rows.append(dict(component=comp, era=era, arm=a, alpha6=alpha_pct(b6), t6=float(t6[0]), R2_6=r6,
                                 alpha7=alpha_pct(b7), t7=float(t7[0]), R2_7=r7, beta_strev=float(b7[7]), t_strev=float(t7[7])))
    compare_and_write(pd.DataFrame(rows), "strev_spanning_v3_cal6913.csv", ["component", "era", "arm"])

    # trained books on factors / factors + peer books (peer books unshifted, factors shifted by one day)
    peers = pd.DataFrame({w: peer_book(w) for w in ("w60", "w252")})
    Mh = pd.concat({a: books.head_avg(a) for a in paths.ARMS}, axis=1).join(peers, how="inner").join(ff.shift(1), how="inner").reindex(books.IDX)
    assert Mh.notna().all().all(), "NaN in the peer design"
    prow = []
    for a in paths.ARMS:
        y = Mh[a].to_numpy(float)
        for design, cols in (("factors6", FF6), ("factors7", FF7), ("both6", ["w60", "w252"] + FF6), ("both7", ["w60", "w252"] + FF7)):
            b, t, r2 = nw_ols(y, Mh[cols].to_numpy(float)); prow.append(dict(arm=a, design=design, alpha=alpha_pct(b), t=float(t[0]), R2=r2))
    compare_and_write(pd.DataFrame(prow), "strev_peer_v3_cal6913.csv", ["arm", "design"])


if __name__ == "__main__":
    main()
