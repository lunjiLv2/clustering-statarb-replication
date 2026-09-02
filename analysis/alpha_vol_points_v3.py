"""fig:alpha_vol's coordinates. Two conventions, deliberately different, as tab:moments uses them:
  x  annualized volatility in percent, computed PER HEAD SEED and averaged over the seed set;
  y  FF5+MOM alpha in percent per year, NW(21), of the SEED-AVERAGED payoff.
Written only when it reproduces the shipped CSV, by the _compare rule.

    python analysis/alpha_vol_points_v3.py            # the seed set in paths.SEEDS (CSA_SEEDS)
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books
from analysis._compare import compare_and_write
from analysis.factors import FF6, load_ff, nw_ols, alpha_pct

def main() -> int:
    ff = load_ff()[FF6]
    rows = []
    for a in paths.ARMS:
        for s in paths.SEEDS:
            assert books.gate_ok(a, s), f"{a} seed{s} fails the validity gate"
        vol = float(np.mean([books.ann_vol(books.head_book(a, s)) for s in paths.SEEDS]))
        avg = sum(books.head_book(a, s) for s in paths.SEEDS) / len(paths.SEEDS)
        m = pd.concat([avg.rename("y"), ff.shift(1)], axis=1).reindex(books.IDX).dropna()
        b, _, _ = nw_ols(m.y.to_numpy(), m[FF6].to_numpy())
        rows.append(dict(arm=a, vol=vol, alpha=alpha_pct(b)))
    df = pd.DataFrame(rows)
    print(f"seeds {tuple(paths.SEEDS)}")
    print(df.to_string(index=False))
    compare_and_write(df, "alpha_vol_points_v3_cal6913.csv", ["arm"])
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
