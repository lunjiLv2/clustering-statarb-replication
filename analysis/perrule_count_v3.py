"""Per-rule alpha advantage over the two controls, formed seed by seed (§4.1 / §5.1 dispersion).

Convention matched to tab:signal: alpha from book ~ a + FF5+MOM with the factors joined at a one-day
lag (trained component), Newey–West sandwich standard errors at 21 lags, alpha annualized in %/yr.
The advantage of a rule is formed PER SEED (alpha of the rule at seed s minus alpha of the control at
seed s, over paths.SEEDS) and only then averaged; two dispersions are reported — the arm's own sd
of its per-seed advantages and the pooled sd sqrt(mean of the twelve within-arm variances).
Degrees of freedom follow the seed count: 2 and 24 at three seeds, 4 and 48 at five. A rule "clears" when |mean advantage| > 2 x dispersion. Every run must pass the validity
gate (rolling-250 mean |net exposure| <= 0.30, no one-sided day).

Output: analysis/results/perrule_count_v3_cal6913.csv (control, rule, one adv_s<seed> column per
seed in SEEDS, mean, own_sd, pooled_sd, clears_own, clears_pooled, alpha_rule_mean, alpha_ctrl_mean).
Run: ``python analysis/perrule_count_v3.py``
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books
from analysis.factors import FF6, load_ff, nw_ols_hac
from analysis._compare import compare_and_write

RULES = {"kmeans": "kmeans_ret", "sponge": "sponge_w60", "agglo_avg": "agglo_avg", "agglo_complete": "agglo_complete",
         "pca_load": "pca_load", "spectral_unsigned": "spectral_unsigned", "gics": "gics", "fv2a": "fv2a_w60",
         "fv3sm": "fv3sm_w60", "sortino": "sortino_w60", "sharpe_fixed": "sharpe_fixed_w60", "sssnet": "sssnetpre"}
CTRL = {"k1": "k1", "random": "random"}
SEEDS = tuple(paths.SEEDS)   # follows CSA_SEEDS; hard-coding it left this producer on three
                             # seeds after the paper moved to five, so a referee running it got
                             # 5/12 and 12/12 against the printed four and seven (N83 add. 1)


def alpha(y: pd.Series, ff_lag: pd.DataFrame) -> float:
    j = pd.concat([y.rename("y"), ff_lag], axis=1).reindex(books.IDX).dropna()
    yv = j["y"].to_numpy(float); X = np.column_stack([np.ones(len(j)), j[FF6].to_numpy(float)])
    b, t, r2 = nw_ols_hac(yv, X, 21)
    return 252 * 100 * b[0]


def main() -> int:
    ff_lag = load_ff(with_reversal=False)[FF6].shift(1)
    B = {}
    for label, arm in {**RULES, **CTRL}.items():
        for s in SEEDS:
            assert books.gate_ok(arm, s), f"{arm} seed {s} fails the validity gate"
            B[(label, s)] = books.head_book(arm, s)
    print(f"[perrule] {len(B)} books on {len(books.IDX)} days, all runs pass the gate", flush=True)
    A = {k: alpha(v, ff_lag) for k, v in B.items()}
    rows = []
    for ctl in ("k1", "random"):
        adv = {r: np.array([A[(r, s)] - A[(ctl, s)] for s in SEEDS]) for r in RULES}
        pooled = float(np.sqrt(np.mean([v.var(ddof=1) for v in adv.values()])))
        for r in sorted(adv, key=lambda x: -adv[x].mean()):
            v = adv[r]; m = v.mean(); sd = v.std(ddof=1)
            rows.append(dict(control=ctl, rule=r, **{f"adv_s{s}": v[i] for i, s in enumerate(SEEDS)}, mean=m, own_sd=sd, pooled_sd=pooled,
                             clears_own=abs(m) > 2 * sd, clears_pooled=abs(m) > 2 * pooled,
                             alpha_rule_mean=np.mean([A[(r, s)] for s in SEEDS]), alpha_ctrl_mean=np.mean([A[(ctl, s)] for s in SEEDS])))
        d = pd.DataFrame([x for x in rows if x["control"] == ctl])
        print(f"  vs {ctl:6s}: pooled sd {pooled:.4f}; clears 2x own sd {int(d.clears_own.sum())}/12, 2x pooled sd {int(d.clears_pooled.sum())}/12, "
              f"positive {int((d['mean'] > 0).sum())}/12; mean advantage {d['mean'].mean():+.3f} %/yr")
    out = pd.DataFrame(rows)
    ref = pd.read_csv(paths.RESULTS / "perrule_count_v3_cal6913.csv")
    j = out.merge(ref, on=["control", "rule"], suffixes=("", "_ref"))
    print("  boolean columns identical:", bool((j.clears_own == j.clears_own_ref).all() and (j.clears_pooled == j.clears_pooled_ref).all()))
    compare_and_write(out, "perrule_count_v3_cal6913.csv", ["control", "rule"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
