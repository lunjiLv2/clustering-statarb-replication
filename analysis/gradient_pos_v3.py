"""tab:gradient's position row: how much of a rule's positions other rules share, against a rule's own
refit (§5.3).

Positions are the executed daily weight vectors; two books are compared by the mean daily correlation
over the union of their names with absent names at zero (analysis/_positions.py). "Across rules" pairs
different rules at the same head seed (55 pairs x 3 seeds); "rule against itself" pairs the same rule
at two head seeds (3 pairs per rule). The printed row uses eleven rules: SSSNET is excluded by design
because its partition is redrawn with the training seed, so its two sources of randomness cannot be
separated; the twelve-rule line is reported alongside so that the choice stays visible. Every
position file passes the three gates before use (needs CSA_PANEL_ROOT).
Output: analysis/results/gradient_pos_v3_cal6913.csv.

Run: ``CSA_PANEL_ROOT=... python analysis/gradient_pos_v3.py``
"""
from __future__ import annotations
import itertools, sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import _positions as X
from analysis._compare import compare_and_write

ELEVEN = ["kmeans_ret", "agglo_complete", "fv3sm_w60", "sponge_w60", "pca_load", "agglo_avg",
          "sortino_w60", "fv2a_w60", "sharpe_fixed_w60", "gics", "spectral_unsigned"]
FILE = {"sssnet_w60": "sssnetpre"}                 # option B: the SSSNET books are the sssnetpre runs


def main() -> None:
    raw = X.masked_returns(); B = {}
    for arm in ELEVEN + ["sssnet_w60"]:
        for s in paths.SEEDS:
            b = X.gated_book(FILE.get(arm, arm), s, raw)
            if b is not None: B[(arm, s)] = b
    days = X.common_days(*B.values()); print(f"common calendar: {len(days)} days", flush=True)
    rows = []
    for label, arms in (("eleven_rules_as_printed", ELEVEN), ("twelve_incl_sssnet", ELEVEN + ["sssnet_w60"])):
        have = [a for a in arms if all((a, s) in B for s in paths.SEEDS)]
        if len(have) != len(arms):
            print(f"[{label}] only {len(have)}/{len(arms)} arms fully gated: missing {set(arms) - set(have)}"); continue
        across = [X.daily_corr(B[(i, s)], B[(j, s)], days) for s in paths.SEEDS for i, j in itertools.combinations(have, 2)]
        within = [X.daily_corr(B[(a, s1)], B[(a, s2)], days) for a in have for s1, s2 in itertools.combinations(paths.SEEDS, 2)]
        A, S = float(np.mean(across)), float(np.mean(within)); npair = len(list(itertools.combinations(have, 2)))
        print(f"[{label}] {len(have)} rules: across {A:.4f} (band {min(across):.4f}–{max(across):.4f}), own refit {S:.4f} "
              f"(band {min(within):.4f}–{max(within):.4f}), ratio {A / S:.4f}", flush=True)
        rows.append(dict(basis=label, n_rules=len(have), n_pairs=npair, days=len(days), across_rules=A, rule_vs_itself=S, ratio=A / S,
                         across_min=min(across), across_max=max(across), within_min=min(within), within_max=max(within)))
    compare_and_write(pd.DataFrame(rows), "gradient_pos_v3_cal6913.csv", ["basis"])


if __name__ == "__main__":
    main()
