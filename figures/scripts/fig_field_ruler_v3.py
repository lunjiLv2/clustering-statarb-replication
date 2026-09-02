"""fig:field_ruler — every trained run's Sharpe ratio against the ruler its ordering must clear.

The ruler is a SEGMENT WHOSE LENGTH IS THE QUANTITY BEING COMPARED: one pooled paired-difference
standard deviation, the dispersion of the GAP between two adjacent configurations. It is drawn
free-standing, not as "plus or minus x either side of the median", because the paired s.d. is the
scale of a difference, not of a level, and a symmetric bar invites the reader to compare it with a
single arm's spread.

The level ruler (pooled within-configuration s.d.) is not drawn; §5.1 reports both numbers and says
the same conclusion follows from either. Ported from the manuscript master
(JFEC_A_Manuscript/_reference/fig_field_ruler_v3.py) on 2026-09-01: this copy had been left on the
earlier design -- a +/- level ruler, three points per arm hard-coded -- so the replication package
shipped a script that draws a DIFFERENT figure from the one in the paper (CORRECTIONS N83 add. 1).

Inputs: the trained books of the 14 arms at paths.SEEDS under data/derived/head_logs; every run must
pass the pre-registered validity gate. The two gates below assert the printed §5.1 dispersions and
fire only on the paper's five-seed set, so the script stays runnable under CSA_SEEDS.
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import style, paths
from analysis import books

plt.rcParams.update({"font.size": 10.5, "legend.fontsize": 9.5})   # print-size batch 2026-08-30

SEEDS = tuple(paths.SEEDS)
RULES = [a for a in paths.ARMS if a not in ("k1", "random")]
CTRL = ["k1", "random"]
LABEL = dict(style.NAME, kmeans_ret="$k$-means on returns", spectral_unsigned="Spectral (unsigned)",
             k1="No clustering ($K=1$)", random="Random partition")

for a in RULES + CTRL:
    bad = [s for s in SEEDS if not books.gate_ok(a, s)]
    assert not bad, f"{a}: seeds {bad} fail the pre-registered validity gate"
S = {a: np.array([books.sharpe(books.head_book(a, s)) for s in SEEDS]) for a in RULES + CTRL}

means = pd.Series({a: S[a].mean() for a in RULES}).sort_values(ascending=False)
order_rules = list(means.index)
paired = float(np.sqrt(np.mean([np.var(S[order_rules[i]] - S[order_rules[i + 1]], ddof=1)
                                for i in range(len(order_rules) - 1)])))
level = float(np.sqrt(np.mean([S[a].var(ddof=1) for a in RULES])))
if SEEDS == (1, 2, 3, 4, 5):                       # the paper's set; §5.1 prints both dispersions
    assert abs(paired - 0.1032) < 5e-4, f"paired ruler gate: {paired:.4f} != 0.1032"
    assert abs(level - 0.1682) < 5e-4, f"level ruler gate: {level:.4f} != 0.1682"

order = sorted(CTRL, key=lambda a: S[a].mean()) + order_rules[::-1]     # worst at the bottom
fig, ax = plt.subplots(figsize=(6.4, 4.5))
for i, a in enumerate(order):
    col = style.CONTROL_RED if a in CTRL else "0.30"
    ax.plot(S[a], [i] * len(SEEDS), "o", ms=3.0, mfc="none", mec=col, mew=0.8, zorder=3)
    m = S[a].mean(); ax.plot([m, m], [i - 0.30, i + 0.30], "-", color=col, lw=1.6, zorder=4)

# the two adjacent gaps that clear the ruler, marked where they occur
for hi, lo in [(order_rules[0], order_rules[1]), (order_rules[-2], order_rules[-1])]:
    y = (order.index(hi) + order.index(lo)) / 2.0
    xa, xb = S[lo].mean(), S[hi].mean()
    ax.annotate("", (xa, y), (xb, y), arrowprops=dict(arrowstyle="<->", lw=0.9, color="black"))
    ax.annotate(f"${xb - xa:.3f}$", ((xa + xb) / 2, y), ha="center", va="center", fontsize=8.4,
                bbox=dict(boxstyle="round,pad=0.14", fc="white", ec="none"), zorder=6)

ax.set_yticks(range(len(order))); ax.set_yticklabels([LABEL[a] for a in order])
ax.set_ylim(-1.5, len(order) + 1.15)
lo_x, hi_x = ax.get_xlim(); ax.set_xlim(lo_x, hi_x)
top = len(order) + 0.30
x0 = hi_x - 0.06 * (hi_x - lo_x) - paired                    # free-standing, right margin
ax.plot([x0, x0 + paired], [top, top], "-", color="black", lw=1.6, zorder=5)
for x in (x0, x0 + paired):
    ax.plot([x, x], [top - 0.17, top + 0.17], "-", color="black", lw=1.6, zorder=5)
ax.annotate(f"one paired-difference s.d. (${paired:.3f}$):\n"
            "the distance two adjacent means must exceed",
            (x0 + paired / 2, top), xytext=(0, 7), textcoords="offset points",
            ha="center", va="bottom", fontsize=8.8, linespacing=1.25)
ax.axhline(len(CTRL) - 0.5, color="0.75", lw=0.7, ls=(0, (4, 3)))
ax.set_xlabel("Sharpe ratio, trained component")
fig.tight_layout(); style.save(fig, "fig_field_ruler", dpi=150)

gaps = means.values[:-1] - means.values[1:]
nd_p = (len(RULES) - 1) * (len(SEEDS) - 1)
nd_l = len(RULES) * (len(SEEDS) - 1)
print(f"  seeds {SEEDS}")
print(f"  paired ruler {paired:.4f} on {nd_p} df   gaps inside it: {int((gaps < paired).sum())} of {len(gaps)}")
print(f"  level  ruler {level:.4f} on {nd_l} df   gaps inside it: {int((gaps < level).sum())} of {len(gaps)}")
print(f"  span {means.values[-1]:.3f}-{means.values[0]:.3f}   "
      f"top gap {gaps[0]:.3f}   bottom gap {gaps[-1]:.3f}")
