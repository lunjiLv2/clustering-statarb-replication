"""How the headline numbers move when the head-seed set changes (seed extension of 2026-08-30).

3seed-ok: this tool is ABOUT the old set -- it measured what extending it would do.
The paper averaged every trained-book statistic over three head seeds (42, 1, 123) when this
script was written; it is the tool that measured what extending them would do. This script
recomputes the same statistics for an arbitrary seed set so that a larger set can be compared with
the published one. For each arm it reports, under each convention the paper uses:

  * mean-of-per-seed Sharpe (tab:head, tab:costs) with the across-seed sd,
  * the seed-averaged book's Sharpe and its FF5+MOM alpha (percent per year, NW21) and t
    (tab:spanning, tab:signal),

and it applies the pre-registered training-validity gate (rolling-250 mean |NE| <= 0.30) to every
run, refusing to report an arm whose runs do not all pass. Nothing is overwritten: the comparison
is written to analysis/results/seed_extension_<tag>.csv.

    python analysis/seed_extension_v3.py --seeds 42 1 123                 # reproduces the paper
    python analysis/seed_extension_v3.py --seeds 42 1 123 2 3 --compare 42 1 123

Run: needs data/derived/head_logs/{arm}_seed{s}.csv for every arm and seed in the set.
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books
from analysis.factors import FF6, load_ff, nw_ols, alpha_pct

SQ = np.sqrt(252)


def stats(arm: str, seeds: tuple[int, ...], ff: pd.DataFrame) -> dict:
    bad = [s for s in seeds if not books.gate_ok(arm, s)]
    assert not bad, f"{arm}: seeds {bad} fail the training-validity gate (rolling-250 mean |NE| > 0.30)"
    per = {s: books.head_book(arm, s) for s in seeds}
    mps = [books.sharpe(v) for v in per.values()]
    avg = sum(per.values()) / len(per)
    m = pd.concat([avg.rename("y"), ff.shift(1)], axis=1).reindex(books.IDX).dropna()
    b, t, r2 = nw_ols(m.y.to_numpy(), m[FF6].to_numpy())
    return dict(arm=arm, n_seeds=len(seeds), sharpe_mps=float(np.mean(mps)), sharpe_sd=float(np.std(mps, ddof=1)),
                sharpe_min=float(np.min(mps)), sharpe_max=float(np.max(mps)), sharpe_avgbook=books.sharpe(avg),
                alpha=alpha_pct(b), t_alpha=float(t[0]), R2=r2)


def table(seeds: tuple[int, ...]) -> pd.DataFrame:
    ff = load_ff()[FF6]
    return pd.DataFrame([stats(a, seeds, ff) for a in paths.ARMS])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", nargs="+", type=int, default=list(paths.SEEDS))
    ap.add_argument("--compare", nargs="*", type=int, default=None, help="baseline seed set to diff against")
    ap.add_argument("--tag", default=None)
    a = ap.parse_args()
    new = table(tuple(a.seeds)); tag = a.tag or "".join(str(s) for s in a.seeds)
    if a.compare:
        base = table(tuple(a.compare))
        j = base.merge(new, on="arm", suffixes=("_base", "_new"))
        for c in ("sharpe_mps", "sharpe_avgbook", "alpha", "t_alpha"):
            j["d_" + c] = j[c + "_new"] - j[c + "_base"]
        rank_base = base.sort_values("sharpe_mps", ascending=False).arm.tolist()
        rank_new = new.sort_values("sharpe_mps", ascending=False).arm.tolist()
        print(j[["arm", "sharpe_mps_base", "sharpe_mps_new", "d_sharpe_mps", "alpha_base", "alpha_new", "d_alpha",
                 "t_alpha_base", "t_alpha_new"]].round(3).to_string(index=False))
        print(f"\nmax |d Sharpe (mps)| {j.d_sharpe_mps.abs().max():.3f} | max |d alpha| {j.d_alpha.abs().max():.3f} pts")
        print(f"leader base {rank_base[0]} -> new {rank_new[0]}; rank changes: "
              f"{sum(rank_base[i] != rank_new[i] for i in range(len(rank_base)))} of {len(rank_base)} positions")
        j.to_csv(paths.RESULTS / f"seed_extension_{tag}_vs_{''.join(str(s) for s in a.compare)}.csv", index=False)
    else:
        print(new.round(4).to_string(index=False))
        new.to_csv(paths.RESULTS / f"seed_extension_{tag}.csv", index=False)


if __name__ == "__main__":
    main()
