"""Log-Sharpe decomposition of the clusterizer advantage into a mean part and a volatility part
(tab:split, §4.3).

The grouped book is summarised by the field means over the 12 clusterizers of annualised mean and
volatility; the control (K = 1 or random) by its own. Then
    log SR_g - log SR_c = (log mu_g - log mu_c) - (log sigma_g - log sigma_c),
and the volatility share is the second term over the total. Three cells: the rule layer, the
trained layer as mean of per-seed (mu and sigma computed per seed and averaged) and as the
seed-averaged book. For the trained mean-of-per-seed cell the raw mean gap is also replaced by the
FF5+MOM alpha gap (field mean of the 12 alphas vs the control's, from
peer_spanning_v3_cal6913.csv, design 'factors'), giving the alpha-paired mean share.
Per-arm volatility shares (each clusterizer alone against the control) give the min/max band.

Outputs: analysis/results/split_inputs_cal6913.csv, split_v3_cal6913.csv (the SSSNET arm is
written under the legacy name 'sssnet_w60').

Run: ``python analysis/split_v3.py``
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books
from analysis._compare import compare_and_write

LEGACY = {"sssnetpre": "sssnet_w60"}
CLUSTERIZERS = [a for a in paths.ARMS if a not in ("k1", "random")]
SHORT = {"kmeans_ret": "kmeans", "sponge_w60": "sponge", "fv2a_w60": "fv2a", "fv3sm_w60": "fv3sm",
         "sharpe_fixed_w60": "sharpe_fixed", "sortino_w60": "sortino", "sssnetpre": "sssnet"}
"""Arm names used by peer_spanning_v3_cal6913.csv."""
SQ = np.sqrt(252)


def mean_vol(s: pd.Series) -> tuple[float, float]:
    return 252 * s.mean(), SQ * s.std(ddof=1)


def inputs() -> pd.DataFrame:
    rows = []
    for a in paths.ARMS:
        name = LEGACY.get(a, a)
        m, v = mean_vol(books.rule_book(a)); rows.append(dict(arm=name, layer="rule", conv="-", mu=m, sig=v))
        per = [mean_vol(b) for b in books.head_books(a).values()]
        rows.append(dict(arm=name, layer="head", conv="perseed", mu=np.mean([p[0] for p in per]), sig=np.mean([p[1] for p in per])))
        m, v = mean_vol(books.head_avg(a)); rows.append(dict(arm=name, layer="head", conv="seedavg", mu=m, sig=v))
    return pd.DataFrame(rows)


def cells(T: pd.DataFrame) -> pd.DataFrame:
    f = pd.read_csv(paths.RESULTS / "peer_spanning_v3_cal6913.csv")
    f = f[f.design == "factors"].set_index("arm").alpha
    arms = [LEGACY.get(a, a) for a in CLUSTERIZERS]
    alpha_grouped = np.mean([f[SHORT.get(a, a)] for a in CLUSTERIZERS]); out = []
    for (layer, conv), g in T.groupby(["layer", "conv"]):
        g = g.set_index("arm"); F = g.loc[arms]; mu, sg = F.mu.mean(), F.sig.mean()
        for c in ("k1", "random"):
            C = g.loc[c]; dm = np.log(mu / C.mu); ds = np.log(sg / C.sig); tot = dm - ds
            per = {a: -np.log(F.loc[a, "sig"] / C.sig) / (np.log(F.loc[a, "mu"] / C.mu) - np.log(F.loc[a, "sig"] / C.sig)) for a in arms}
            r = dict(layer=layer, conv=conv, control=c, SR_grouped=mu / sg, SR_control=C.mu / C.sig, logSR_gap=tot, mean_part=dm,
                     vol_part=-ds, vol_share_pct=100 * (-ds) / tot, gics_vol_share_pct=100 * per["gics"],
                     perarm_min_pct=100 * min(per.values()), perarm_max_pct=100 * max(per.values()),
                     perarm_min_excl_gics_pct=100 * min(v for a, v in per.items() if a != "gics"), perarm_min_arm=min(per, key=per.get))
            if layer == "head" and conv == "perseed":
                da = np.log(alpha_grouped / f[c]); r["alpha_gap"] = da; r["alpha_mean_share_pct"] = 100 * da / (da - ds)
            out.append(r)
    return pd.DataFrame(out)


def main() -> None:
    T = inputs(); compare_and_write(T, "split_inputs_cal6913.csv", ["arm", "layer", "conv"])
    X = cells(T); compare_and_write(X, "split_v3_cal6913.csv", ["layer", "conv", "control"])
    pd.set_option("display.width", 250); print(X.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
