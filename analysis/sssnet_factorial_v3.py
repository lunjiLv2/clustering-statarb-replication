"""The SSSNET partition-seed × head-seed factorial behind the 'SS shares' statement (harness check).

3seed-ok: the table is a 3x3 factorial DEFINED at partition and head seeds 42/1/123; it separates
the two axes from each other rather than reporting a five-seed head average.
Three fixed SSSNET partitions (seeds 42, 1, 123; run family ``sssnetfix2_p{seed}``) x three training
seeds (42, 1, 123) = nine trained books. ``T`` holds their Sharpe ratios with rows = training seed and
columns = partition seed, the orientation of the original producer; ``out`` holds the row/column
ranges, the pooled within-row / within-column standard deviations, and the two-way sum-of-squares
decomposition (head, partition, interaction) reported in the manuscript.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis import books

PART = {42: "sssnetfix2_p42", 1: "sssnetfix2_p1", 123: "sssnetfix2_p123"}   # partition seed -> run family
HEAD = (42, 1, 123)   # 3seed-ok: tab:sssnet is a 3x3 partition-seed x head-seed factorial defined
                      # at these seeds; it identifies the two axes against each other, not the
                      # five-seed head average, so extending it would change what the table is.
T = pd.DataFrame({p: {h: books.sharpe(books.head_book(fam, h)) for h in HEAD} for p, fam in PART.items()})
T.index.name, T.columns.name = "head_seed", "partition_seed"
g = T.values; gm = g.mean()
ss_part = 3 * ((g.mean(0) - gm) ** 2).sum()      # between columns (partitions)
ss_head = 3 * ((g.mean(1) - gm) ** 2).sum()      # between rows (training seeds)
ss_tot = ((g - gm) ** 2).sum()
out = dict(head_range=float(T.mean(1).max() - T.mean(1).min()),               # rows averaged over partitions
           head_pooled_sd=float(np.sqrt(((g - g.mean(0)) ** 2).sum() / 6)),  # within-column sd, pooled
           part_range=float(T.mean(0).max() - T.mean(0).min()),
           part_pooled_sd=float(np.sqrt(((g - g.mean(1, keepdims=True)) ** 2).sum() / 6)),
           ss_head=float(ss_head / ss_tot), ss_part=float(ss_part / ss_tot), ss_inter=float(1 - (ss_head + ss_part) / ss_tot))
if __name__ == "__main__":
    print(T.round(4)); print({k: round(v, 4) for k, v in out.items()})
