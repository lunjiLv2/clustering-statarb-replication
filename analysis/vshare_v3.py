"""Removal share of cross-sectional residual variance by within-group demeaning, on the traded
universe, for every arm (§4.2: the 16–21% band of the clusterizers against 5.9% for the random
partition; A.9).

For each common-calendar day the rule engine's traded universe is rebuilt (top-500 by yesterday's
capitalisation, complete signal and correlation windows, at least 100 names with a finite residual),
the partition's labels are attached with the engine's nearest-group fill, and the share of the
day's residual variance that demeaning within groups removes is recorded; the table reports the
mean over days together with the mean traded universe and the mean number of groups realised.
``--exclude-singletons`` drops the members of size-one groups before the share is computed (the
trading stage does not trade them; the A.9 footnote, k-means 0.216).

Outputs: analysis/results/vshare_v3_cal6913.csv (arm names as in the manuscript's CSVs: the SSSNET
arm is written as ``sssnet_w60``); with ``--exclude-singletons``, vshare_v3_nosingleton_cal6913.csv.

Run: ``CSA_PANEL_ROOT=/path/to/compat_panel python analysis/vshare_v3.py [--arms ...] [--nproc 8]``
(about 40 s per arm; the arms run in a process pool of ``--nproc`` workers).
"""
from __future__ import annotations
import argparse, functools, multiprocessing as mp, sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books
from analysis._compare import compare_and_write
from analysis.traded_universe import K, BETA_W, SIG_W, load_panel, load_cache, day_universe, partition_for, fill_labels, r2

LEGACY = {"sssnetpre": "sssnet_w60"}
CALSET = set(books.IDX)
G = None                                   # the panel, loaded once and shared with the forked workers


def one(arm: str, nosingleton: bool = False) -> dict:
    cache, RD = load_cache(arm); KA = 1 if arm == "k1" else K
    rs, nt, kt = [], [], []
    for i in range(BETA_W + SIG_W, len(G.ridx) - 1):
        d = G.ridx[i]
        if d not in CALSET: continue
        u = day_universe(G, i)
        if u is None: continue
        tk, vi, jU, lb, crv, nxp = u
        rd = partition_for(RD, d)
        if rd is None: continue
        ent = cache[rd]
        out = fill_labels(ent["universe"], ent["labels"], tk, crv[:, vi], KA)
        xt = G.R[i][jU][vi]; okx = np.isfinite(xt)
        if okx.sum() >= 100:
            if nosingleton:
                o_ = out[okx]; _u, _c = np.unique(o_, return_counts=True); keep = np.isin(o_, _u[_c >= 2])
                rs.append(r2(xt[okx][keep], o_[keep]))
            else:
                rs.append(r2(xt[okx], out[okx]))
            nt.append(int(okx.sum())); kt.append(len(np.unique(out[okx])))
    return dict(arm=LEGACY.get(arm, arm), days=len(rs), removal_share=float(np.nanmean(rs)),
                traded_N=float(np.mean(nt)), eff_K=float(np.mean(kt)))


def run(arms: list[str], nosingleton: bool, nproc: int, name: str) -> pd.DataFrame:
    global G
    G = load_panel()
    work = functools.partial(one, nosingleton=nosingleton)
    if nproc > 1 and len(arms) > 1:
        with mp.get_context("fork").Pool(min(nproc, len(arms))) as pool:
            rows = pool.map(work, arms)
    else:
        rows = [work(a) for a in arms]
    D = pd.DataFrame(rows)
    print(D.sort_values("removal_share").to_string(index=False))
    compare_and_write(D, name, ["arm"])
    return D


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="*", default=paths.ARMS)
    ap.add_argument("--nproc", type=int, default=1)
    ap.add_argument("--exclude-singletons", action="store_true")
    a = ap.parse_args()
    run(a.arms, a.exclude_singletons, a.nproc,
        "vshare_v3_nosingleton_cal6913.csv" if a.exclude_singletons else "vshare_v3_cal6913.csv")


if __name__ == "__main__":
    main()
