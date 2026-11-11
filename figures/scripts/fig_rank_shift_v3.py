"""fig:rank_shift — the 12 clusterizers ranked by Sharpe ratio under the rule-based component (left) and the
trained component (right, mean of per-seed), joined by lines; Spearman correlation of the two rankings.

Inputs: rule books and the 70 main trained books (14 arms x paths.SEEDS) under data/derived. Gates assert the leader and the
bottom pair stated in §4.4.
"""
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import spearmanr
import style
from analysis import books

plt.rcParams.update({"axes.spines.left": False, "axes.spines.bottom": False})   # a bare slope chart: no axis lines

TW = ["kmeans_ret", "agglo_complete", "pca_load", "sssnetpre", "fv3sm_w60", "sharpe_fixed_w60",
      "agglo_avg", "sponge_w60", "sortino_w60", "fv2a_w60", "spectral_unsigned", "gics"]
LAB = dict(style.NAME, kmeans_ret="$k$-means", spectral_unsigned="Spectral (unsigned)")
R = {a: books.sharpe(books.rule_book(a)) for a in TW}
T = {a: float(np.mean([books.sharpe(b) for b in books.head_books(a).values()])) for a in TW}
rr = sorted(TW, key=lambda a: -R[a]); tr = sorted(TW, key=lambda a: -T[a])
assert rr[0] == tr[0] == "kmeans_ret", "leader gate"
assert set(rr[-2:]) == set(tr[-2:]) == {"spectral_unsigned", "gics"}, "bottom-pair gate"
rho, pv = spearmanr([rr.index(a) for a in TW], [tr.index(a) for a in TW])

fig, ax = plt.subplots(figsize=(5.9, 4.6))
for a in TW:
    i, j = rr.index(a), tr.index(a); d = abs(i - j)
    # two tones only: the slope already shows how far an arm moves, so the grey ramp duplicated the
    # geometry and 0.30 against 0.42 was not separable on a thin line in print. Labels are decoupled
    # from the line colour — the lines carry the encoding, the text only has to be readable.
    col = "black" if d >= 3 else "0.55"; lw = 1.8 if d >= 3 else 0.9
    lab = "black" if d >= 3 else "0.35"
    ax.plot([0, 1], [i, j], "-", color=col, lw=lw, zorder=3 if d >= 3 else 2); ax.plot([0, 1], [i, j], "o", color=col, ms=3.4, zorder=4)
    ax.text(-0.045, i, LAB[a], ha="right", va="center", fontsize=8.6, color=lab); ax.text(1.045, j, LAB[a], ha="left", va="center", fontsize=8.6, color=lab)
ax.set_xlim(-0.62, 1.62); ax.set_ylim(len(TW) - 0.4, -1.15); ax.set_xticks([]); ax.set_yticks([])
ax.text(0, -0.75, "fixed rule", ha="center", fontsize=9.6); ax.text(1, -0.75, "neural head", ha="center", fontsize=9.6)
ax.annotate(r"Spearman $\rho = %.2f$" % rho, (0.5, len(TW) - 0.65), ha="center", fontsize=9.0)
fig.tight_layout(); style.save(fig, "fig_rank_shift", dpi=160)
mv = {a: rr.index(a) - tr.index(a) for a in TW}
print(f"  Spearman {rho:.4f}  p {pv:.4f} | unmoved {sum(v == 0 for v in mv.values())} | largest move {max(abs(v) for v in mv.values())}")
