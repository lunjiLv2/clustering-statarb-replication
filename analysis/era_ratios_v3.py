"""Dispersion-over-measurement-error ratios of the seed-averaged trained books, by era (§3.7).

For an arm set, rho_bar is the mean off-diagonal correlation of the daily payoffs over the full
common calendar. Per era (1997-2001, 2002-2009, 2010-2016, 2017-2024):
    sd_mean = sd across arms of the annualised era mean,     se_mean = vol * sqrt(252/T) * sqrt(1 - rho_bar)
    sd_vol  = sd across arms of the annualised era volatility, se_vol = vol / sqrt(2T) * sqrt(1 - rho_bar^2)
with vol the cross-arm mean volatility; the ratios sd/se are reported per era, never as a range
(they are not era-monotone). Four arm sets: the 12 clusterizers; + 2 controls; + 3 and + 5
21-day-window twins. Every run must pass the NE gate (head/ne_gate.gate_ok) before entering.

Output: analysis/results/era_ratios_v3_cal6913.csv.  Run: ``python analysis/era_ratios_v3.py``
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "head"))
import paths
from analysis import books
from analysis._compare import compare_and_write
import ne_gate

SQ = np.sqrt(252.0)
ERAS = [("1997-2001", 1997, 2001), ("2002-2009", 2002, 2009), ("2010-2016", 2010, 2016), ("2017-2024", 2017, 2024)]
CLUSTERIZERS = [a for a in paths.ARMS if a not in ("k1", "random")]
CTRL = ["k1", "random"]
TWINS3 = [("agglo_avg", "_w21"), ("pca_load", "_w21"), ("spectral_unsigned", "_w21")]
TWINS2 = [("agglo_complete", "_w21"), ("kmeans_ret", "_w21")]


def gated_avg(arm: str, variant: str = "") -> pd.Series:
    for s in paths.SEEDS:
        p = paths.HEAD_LOGS / f"{arm}{variant}_seed{s}.csv"
        assert ne_gate.gate_ok(str(p)), f"NE gate failed: {p.name}"
    return books.head_avg(arm, variant)


def run(name: str, arms: list[tuple[str, str]]) -> list[dict]:
    X = pd.concat({a + v: gated_avg(a, v) for a, v in arms}, axis=1)
    V = X.to_numpy(float); n = V.shape[1]
    C = np.corrcoef(V, rowvar=False); rho = (C.sum() - n) / (n * (n - 1)); out = []
    print(f"=== {name}: {n} arms, rho_bar = {rho:.4f}")
    for nm, a, b in ERAS:
        e = np.where((X.index.year >= a) & (X.index.year <= b))[0]; T = len(e)
        M = V[e].mean(0) * 252.0; S = V[e].std(0, ddof=1) * SQ; vol = S.mean()
        sd_m, sd_v = M.std(ddof=1), S.std(ddof=1)
        se_m = vol * np.sqrt(252.0 / T) * np.sqrt(1 - rho); se_v = vol / np.sqrt(2 * T) * np.sqrt(1 - rho ** 2)
        print(f"  {nm:<11s} T={T:5d}  ratio_mean {sd_m / se_m:5.1f}x  ratio_vol {sd_v / se_v:5.1f}x")
        out.append(dict(armset=name, n_arms=n, era=nm, T=T, rho_bar=rho, sd_mean=sd_m, se_mean=se_m, ratio_mean=sd_m / se_m,
                        sd_vol=sd_v, se_vol=se_v, ratio_vol=sd_v / se_v))
    return out


def main() -> None:
    base = [(a, "") for a in CLUSTERIZERS]; ctrl = [(a, "") for a in CTRL]; rows = []
    rows += run("12 rules", base)
    rows += run("12 rules + 2 controls", base + ctrl)
    rows += run("17 = 12 rules + 2 controls + 3 w21 twins", base + ctrl + TWINS3)
    rows += run("19 = 12 rules + 2 controls + 5 w21 twins", base + ctrl + TWINS3 + TWINS2)
    compare_and_write(pd.DataFrame(rows), "era_ratios_v3_cal6913.csv", ["armset", "era"])


if __name__ == "__main__":
    main()
