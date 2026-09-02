"""Sharpe ratio of the trained component by number of groups, K = 10 / 30 / 50 (tab:ksweep, A.ksweep).

Five clusterizers were rerun at K = 10 and K = 50 at the head seeds of paths.SEEDS ({1,...,5}), everything
else identical to the K = 30 main runs. Each cell is the mean of the per-seed annualized Sharpe ratios
(sqrt(252) * mean / sd of the daily payoff) on the 6,913-day common calendar; the across-seed standard
deviation and the five per-seed values are written beside it (columns sharpe_sd, sharpe_seed1..5).
Head logs: data/derived/head_logs/{arm}{_k10|''|_k50}_seed{s}.csv.

Output: ksweep_v3_cal6913.csv under paths.RESULTS, one row per (arm, K): the mean of per-seed Sharpe ratios
(sharpe_mps), their across-seed sd (sharpe_sd) and the per-seed values (sharpe_seed1..5); tab:ksweep prints the
first two. Runs: the k10/k50 variant arms exist at every seed of paths.SEEDS (appxA fleet, 2026-09-01).
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books

ARMS = ["kmeans_ret", "agglo_avg", "agglo_complete", "pca_load", "spectral_unsigned"]   # the five swept clusterizers
KS = {10: "_k10", 30: "", 50: "_k50"}                                                     # K -> head-log variant suffix


def main() -> None:
    rows = []
    for arm in ARMS:
        for k, variant in KS.items():
            sr = {s: books.sharpe(books.head_book(arm, s, variant)) for s in paths.SEEDS}
            rows.append(dict(arm=arm, K=k, sharpe_mps=float(np.mean(list(sr.values()))), sharpe_sd=float(np.std(list(sr.values()), ddof=1)),
                             **{f"sharpe_seed{s}": v for s, v in sr.items()}))
    out = pd.DataFrame(rows)
    out.to_csv(paths.RESULTS / "ksweep_v3_cal6913.csv", index=False)
    print(out.pivot(index="arm", columns="K", values="sharpe_mps").loc[ARMS].round(2).to_string())
    print(f"across-seed sd range {out.sharpe_sd.min():.2f}-{out.sharpe_sd.max():.2f}")


if __name__ == "__main__":
    main()
