"""Monte Carlo size of the intercept tests on all 28 books (§6.2, A.10).

For every book (14 seed-averaged trained books, factors at shift 1; 14 rule-based books, factors at
shift 0) a null world is built as y* = F b + e*, where b are the no-intercept OLS betas on FF5+MOM and
e* is a centred 21-day circular block resample of the null residual. B replications are drawn with an
independent stream per book, ``default_rng([seed, book_index])`` with books enumerated trained-then-
rule in sorted order of their short labels. Two tests at nominal 5% are counted: the NW(21) Wald t of
the intercept (|t| > 1.959964) and the score (LM) statistic (> 3.841459). The real book's |t|, LM and
their ratio are reported alongside.

Output: analysis/results/mc_size_v3_B{B}_s{seed}.csv. The paper pools four master seeds
(42, 7, 101, 2024) at B = 5000; each seed runs about 10-15 minutes on one core.

Run: ``python analysis/mc_size_v3.py --B 5000 --seed 42`` (see slurm/mc_size.sh)
"""
from __future__ import annotations
import argparse, sys, time
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books
from analysis.factors import FF6, load_ff, nw_ols_hac, lm_score

BLK, T_CRIT, LM_CRIT = 21, 1.959964, 3.841459


def stats(y: np.ndarray, Fm: np.ndarray) -> tuple[float, float]:
    """(|Wald t| of the intercept, score statistic) of ``y`` on a constant and ``Fm``."""
    _, t, _ = nw_ols_hac(y, np.column_stack([np.ones(len(y)), Fm]))
    return abs(float(t[0])), float(lm_score(y, Fm)[0])


def all_books() -> list[tuple[str, str, pd.Series, int]]:
    """(layer, short arm label, book, factor shift) in the enumeration order of the RNG streams."""
    short = {books.SHORT_NAME.get(a, a): a for a in paths.ARMS}
    out = [("trained", s, books.head_avg(a), 1) for s, a in sorted(short.items())]
    out += [("rule", s, books.rule_book(a), 0) for s, a in sorted(short.items())]
    return out


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--B", type=int, default=5000); ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args(); ff = load_ff()[FF6]; t0 = time.time(); rows = []
    for ib, (layer, arm, s, shift) in enumerate(all_books()):
        j = pd.concat([s.rename("y"), ff.shift(shift)], axis=1).dropna()
        y = j["y"].to_numpy(float); Fm = j[FF6].to_numpy(float); T = len(y)
        t_obs, lm_obs = stats(y, Fm)
        beta = np.linalg.solve(Fm.T @ Fm, Fm.T @ y); eps_c = y - Fm @ beta; eps_c -= eps_c.mean()
        rng = np.random.default_rng([args.seed, ib]); nb = int(np.ceil(T / BLK)); rt = rl = 0
        for _ in range(args.B):
            st = rng.integers(0, T, nb)
            idx = (st[:, None] + np.arange(BLK)[None, :]).reshape(-1)[:T] % T
            tt, ll = stats(Fm @ beta + eps_c[idx], Fm)
            rt += tt > T_CRIT; rl += ll > LM_CRIT
        rows.append(dict(layer=layer, arm=arm, days=T, size_waldt=rt / args.B, size_arlm=rl / args.B,
                         obs_absT=t_obs, obs_t2=t_obs ** 2, obs_LM=lm_obs, LM_over_t2=lm_obs / t_obs ** 2 if t_obs else np.nan))
        print(f"  {layer:7s} {arm:18s} n={T}  Wald-t {rt/args.B:.4f}  LM {rl/args.B:.4f}  ({time.time()-t0:.0f}s)", flush=True)
    out = pd.DataFrame(rows); name = f"mc_size_v3_B{args.B}_s{args.seed}.csv"; p = paths.RESULTS / name
    if p.exists():
        ref = pd.read_csv(p); j = out.merge(ref, on=["layer", "arm"], suffixes=("", "_ref"))
        d = max(np.abs(j[c] - j[c + "_ref"]).max() for c in ("size_waldt", "size_arlm", "obs_absT", "obs_LM"))
        print(f"{name}: {len(j)}/{len(ref)} rows matched; max |diff| {d:.2e}")
        if d >= 1e-9: print("NOT written: the shipped file is not reproduced"); return
    out.to_csv(p, index=False); print(f"wrote {p}  ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
