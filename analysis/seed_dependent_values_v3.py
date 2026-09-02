"""Every printed value whose definition averages over head seeds, recomputed for any seed set.

Covers the quantities outside tab:head / tab:costs / tab:spanning that move when the head-seed set
changes, each under the definition printed in the paper:

  * §4.1  alpha advantage over each control (formed seed by seed, then averaged) and the number of
          clusterizers whose advantage exceeds twice its own across-seed dispersion,
  * §4.3  the volatility share of the log-Sharpe gap under the seed-averaged-payoff convention,
  * §4.4  the random-minus-K=1 Sharpe difference at the trained component, paired by seed,
  * A.3   the Spearman correlation between effective K and the mean-of-per-seed Sharpe ratio.

At the paper's five seeds it must reproduce 20.0% / 22.5%, 4 of 12 and 7 of 12, 80.2% / 71.6%,
0.00 with sd 0.08 and t = 0.00, and -0.15 with p = 0.63 (N83). At the retired set {42, 1, 123} it
reproduced the values the paper printed before N83 (17.0% / 24.7%, 5 of 12 and 12 of 12, 75.3% / 68.4%,
+0.13 sd 0.24 t 0.94, -0.27 p 0.39), which is how the script itself was verified.

    python analysis/seed_dependent_values_v3.py --seeds 1 2 3 4 5
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import spearmanr, t as tdist

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books
from analysis.factors import FF6, load_ff, nw_ols, alpha_pct

CL = [a for a in paths.ARMS if a not in ("k1", "random")]


def per_seed_alpha(seeds) -> pd.DataFrame:
    ff = load_ff()[FF6]
    out = {}
    for a in paths.ARMS:
        row = {}
        for s in seeds:
            y = books.head_book(a, s)
            m = pd.concat([y.rename("y"), ff.shift(1)], axis=1).reindex(books.IDX).dropna()
            b, _, _ = nw_ols(m.y.to_numpy(), m[FF6].to_numpy())
            row[s] = alpha_pct(b)
        out[a] = row
    return pd.DataFrame(out).T          # arms x seeds


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--seeds", nargs="+", type=int, default=list(paths.SEEDS))
    a = ap.parse_args(); seeds = tuple(a.seeds); S = len(seeds)
    print(f"seeds {seeds}\n")

    # --- 4.1 advantage over each control (headline: seed-averaged books; counts: per-seed differences)
    A = per_seed_alpha(seeds)                                  # arms x seeds
    ff = load_ff()[FF6]; avg_alpha = {}
    for arm in paths.ARMS:
        y = books.head_avg(arm, seeds=seeds)
        m = pd.concat([y.rename("y"), ff.shift(1)], axis=1).reindex(books.IDX).dropna()
        b, _, _ = nw_ols(m.y.to_numpy(), m[FF6].to_numpy()); avg_alpha[arm] = alpha_pct(b)
    field = float(np.mean([avg_alpha[a] for a in CL]))
    for ctl, name in (("k1", "all-market"), ("random", "random")):
        adv = A.loc[CL].sub(A.loc[ctl], axis=1)                # per-seed alpha difference (harness N77-2)
        own = int((adv.mean(1) > 2 * adv.std(1, ddof=1)).sum())
        pooled = float(np.sqrt(np.mean(adv.std(1, ddof=1) ** 2)))
        print(f"§4.1 advantage over the {name} control: {100*(field/avg_alpha[ctl]-1):.1f}%  | "
              f"exceeds 2x own dispersion at {own} of 12, 2x pooled at {int((adv.mean(1) > 2*pooled).sum())} of 12")

    # --- 4.3 volatility share of the log-Sharpe gap, seed-averaged-payoff convention
    for ctl, name in (("k1", "all-market"), ("random", "random")):
        mu = np.mean([252 * books.head_avg(x, seeds=seeds).mean() for x in CL])
        sg = np.mean([np.sqrt(252) * books.head_avg(x, seeds=seeds).std(ddof=1) for x in CL])
        c = books.head_avg(ctl, seeds=seeds); mu_c, sc = 252 * c.mean(), np.sqrt(252) * c.std(ddof=1)
        vol_part = np.log(sc) - np.log(sg); gap = (np.log(mu) - np.log(mu_c)) + vol_part
        print(f"§4.3 volatility share vs the {name} control, seed-averaged payoff: {100*vol_part/gap:.1f}%")

    # --- 4.4 random minus K=1 at the trained component, paired by seed
    d = np.array([books.sharpe(books.head_book("k1", s)) - books.sharpe(books.head_book("random", s)) for s in seeds])   # K=1 minus random, as printed
    tt = d.mean() / (d.std(ddof=1) / np.sqrt(S))
    print(f"§4.4 K=1 - random paired by seed: {d.mean():+.2f} with sd {d.std(ddof=1):.2f} across {S} fits "
          f"(t = {tt:.2f}, p = {2*(1-tdist.cdf(abs(tt), S-1)):.2f}); per seed {np.round(d, 3).tolist()}")

    # --- A.3 Spearman between effective K and the mean-of-per-seed Sharpe
    sz = pd.read_csv(paths.RESULTS / "sizes_from_caches_cal6913.csv")
    key = "arm" if "arm" in sz.columns else sz.columns[0]
    sz = sz.set_index(key)
    mps = {arm: float(np.mean([books.sharpe(books.head_book(arm, s)) for s in seeds])) for arm in CL}
    look = {"sssnetpre": "sssnet_w60"}
    x = [sz.loc[look.get(arm, arm), "eff_K"] for arm in CL]
    r, p = spearmanr(x, [mps[arm] for arm in CL])
    print(f"A.3 Spearman(effective K, mean-of-per-seed Sharpe) over the 12 clusterizers: {r:+.2f} (p = {p:.2f})")


if __name__ == "__main__":
    main()
