"""Realized partition shape of every arm's main partition (tab:sizes, A.sizes).

For each of the 6,913 common-calendar days the day's label vector (all names in the partition's
universe, before the trading stage's size>=2 mask) gives the group-size distribution, from which
four statistics are taken and then averaged over days: effective K = inverse-Simpson index
1 / sum_g p_g^2 with p_g the share of names in group g; the size of the largest group; the number
of singleton groups; the number of groups of size < 5. The realized number of labels per day is
reported as well (SPONGE and SSSNET realize 29.9 against a nominal 30). The section text's Spearman
correlation between effective K and the mean-of-per-seed Sharpe ratio over the 12 clusterizers
(from turnover_v3_mean_cal6913.csv, gross_SR) is printed too.

Inputs: data/derived/partitions/{arm}.pkl ({date: {universe, labels}}, names from MANIFEST.json).
Output: analysis/results/sizes_from_caches_cal6913.csv. Run: ``python analysis/sizes_from_caches.py``
"""
from __future__ import annotations
import json, pickle, sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books

# arm (cache / rule-book name) -> display name used in the table, in the table's row order
ROWS = [("fv2a_w60", "Sharpe (EW)"), ("sortino_w60", "Sortino"), ("sharpe_fixed_w60", "Sharpe"), ("fv3sm_w60", "Sharpe (graph)"),
        ("random", "Random"), ("pca_load", "PCA loadings"), ("spectral_unsigned", "Spectral (unsigned)"), ("sponge_w60", "SPONGE"),
        ("sssnetpre", "SSSNET"), ("agglo_complete", "Complete linkage"), ("agglo_avg", "Average linkage"),
        ("kmeans_ret", "k-means on returns"), ("gics", "GICS"), ("k1", "K=1")]
LEGACY = {"sssnetpre": "sssnet_w60"}          # arm name used by the result CSVs of the trained books
CONTROLS = {"random", "k1"}


def day_stats(labels: np.ndarray) -> tuple[float, int, int, int, int]:
    sizes = np.bincount(labels[labels >= 0]); sizes = sizes[sizes > 0]
    p = sizes / sizes.sum()
    return float(1 / np.sum(p ** 2)), int(sizes.max()), int((sizes == 1).sum()), int((sizes < 5).sum()), len(sizes)


def main() -> None:
    manifest = json.load(open(paths.PARTITIONS / "MANIFEST.json")); rows = []
    for arm, name in ROWS:
        with open(paths.PARTITIONS / manifest[arm]["file"], "rb") as f:
            cache = pickle.load(f)
        missing = [t for t in books.IDX if t not in cache]
        assert not missing, f"{arm}: {len(missing)} common-calendar days missing from the cache"
        S = np.array([day_stats(np.asarray(cache[t]["labels"])) for t in books.IDX], float)
        rows.append(dict(arm=LEGACY.get(arm, arm), name=name, days=len(S), eff_K=S[:, 0].mean(), largest=S[:, 1].mean(),
                         singletons=S[:, 2].mean(), groups_lt5=S[:, 3].mean(), labels_realized=S[:, 4].mean(),
                         universe=float(np.mean([len(cache[t]["labels"]) for t in books.IDX]))))
    out = pd.DataFrame(rows)
    out.to_csv(paths.RESULTS / "sizes_from_caches_cal6913.csv", index=False)
    print(out.set_index("name")[["eff_K", "largest", "singletons", "groups_lt5", "labels_realized"]].round(2).to_string())
    # section text: effective K against mean-of-per-seed Sharpe over the 12 clusterizers
    from scipy.stats import spearmanr
    sr = pd.read_csv(paths.RESULTS / "turnover_v3_mean_cal6913.csv", index_col=0).gross_SR
    c = out[~out.arm.isin(CONTROLS)]; r = spearmanr(c.eff_K, sr.loc[c.arm].to_numpy())
    print(f"Spearman(effective K, mean-of-per-seed Sharpe) over {len(c)} clusterizers: {r.statistic:.2f} (p = {r.pvalue:.2f})")


if __name__ == "__main__":
    main()
