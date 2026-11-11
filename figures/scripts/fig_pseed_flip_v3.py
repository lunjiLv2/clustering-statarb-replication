"""fig:pseed_flip — Sharpe ratio of each stochastic clusterizer under five partition seeds {1,...,5}:
(a) rule-based component (nine clusterizers redrawn; the three deterministic ones as dashed levels),
(b) trained component with the training seed pinned at 42.

Inputs: rule books {arm}_ps{1..5}.csv and trained books {arm}_ps{1..5}_seed42.csv under data/derived.
Every value is computed here from the books. The partition-seed set mirrors the head-seed set since
CORRECTIONS N84 (2026-09-01; before that the draws were {42, 1, 123}: base book plus the ps1 and ps123 twins).
The head seed is pinned at 42 by design, so the head-seed set does not enter this figure.
"""
import matplotlib.pyplot as plt
import style
from analysis import books

plt.rcParams.update({"font.size": 11.2, "legend.fontsize": 10})   # print-size batch 2026-08-30

STOCH = {"kmeans_ret": "$k$-means", "pca_load": "PCA loadings", "sssnetpre": "SSSNET", "fv3sm_w60": "Sharpe (graph)",
         "sharpe_fixed_w60": "Sharpe", "sponge_w60": "SPONGE", "sortino_w60": "Sortino", "fv2a_w60": "Sharpe (EWMA)",
         "spectral_unsigned": "Spectral"}
DET = {"agglo_complete": "Complete linkage", "agglo_avg": "Average linkage", "gics": "GICS"}
PS = (1, 2, 3, 4, 5)
TWINS = tuple(f"_ps{p}" for p in PS)   # PARTITION seeds; the head is pinned at 42 throughout
rule = {a: [books.sharpe(books.rule_book(a, t)) for t in TWINS] for a in list(STOCH) + ["random"]}
det = {a: books.sharpe(books.rule_book(a)) for a in DET}
head = {a: [books.sharpe(books.head_book(a, 42, t)) for t in TWINS] for a in list(STOCH) + ["random"]}

X, XT = list(range(len(PS))), [f"seed {p}" for p in PS]
L = len(PS) - 1
BLACK, MID, GREY, RED = "black", "0.30", "0.55", style.CONTROL_RED   # GREY floored at 0.55: 0.68 hairlines drop out in greyscale print
fig, (ax, bx) = plt.subplots(1, 2, figsize=(6.4, 2.8), gridspec_kw={"width_ratios": [1.1, 1.0]})
for a, name in STOCH.items():
    hi = a == "kmeans_ret"
    ax.plot(X, rule[a], color=BLACK if hi else GREY, lw=1.8 if hi else 1.0, marker="o", ms=3.2 if hi else 2.5, zorder=3 if hi else 2)
ax.annotate("$k$-means", (L, rule["kmeans_ret"][L]), xytext=(5, 0), textcoords="offset points", va="center", fontsize=10)
ax.annotate("SSSNET", (L, rule["sssnetpre"][L]), xytext=(5, 0), textcoords="offset points", va="center", fontsize=9.4, color="0.35")
for v in det.values():
    ax.axhline(v, color="0.45", lw=0.8, ls=(0, (4, 3)), zorder=1)
ax.annotate("deterministic clusterizers", (0.02, det["gics"]), xytext=(0, -11), textcoords="offset points", fontsize=9.4, color="0.35")
ax.plot(X, rule["random"], color=RED, lw=1.6, marker="o", ms=3, zorder=3)
ax.annotate("random", (L, rule["random"][L]), xytext=(5, 0), textcoords="offset points", va="center", fontsize=10, color=RED)
ax.set_xticks(X); ax.set_xticklabels(XT); ax.set_xlim(-0.25, L + 0.95); ax.set_ylabel("Sharpe ratio")
ax.set_title("(a) fixed trading rule,\nnine clusterizers redrawn", fontsize=11.2, loc="left")
for a in STOCH:
    c, lw, ms, z, ls = (BLACK, 1.8, 3.2, 4, "-") if a == "kmeans_ret" else (MID, 1.5, 3.0, 4, (0, (5, 2))) if a == "sponge_w60" else (GREY, 1.0, 2.5, 2, "-")
    bx.plot(X, head[a], color=c, lw=lw, marker="o", ms=ms, zorder=z, ls=ls)
bx.annotate("$k$-means", (L, head["kmeans_ret"][L]), xytext=(5, 0), textcoords="offset points", va="center", fontsize=10)
bx.annotate("SPONGE", (2, head["sponge_w60"][2]), xytext=(0, -12), textcoords="offset points", ha="center", fontsize=10, color=MID)
bx.plot(X, head["random"], color=RED, lw=1.6, marker="o", ms=3, zorder=3)
bx.annotate("random", (L, head["random"][L]), xytext=(5, 0), textcoords="offset points", va="center", fontsize=10, color=RED)
bx.set_xticks(X); bx.set_xticklabels(XT); bx.set_xlim(-0.25, L + 0.85)
bx.set_title("(b) neural trading head,\nhead seed fixed", fontsize=11.2, loc="left")
fig.tight_layout(w_pad=2.2); style.save(fig, "fig_pseed_flip", dpi=150)
print("  rule ranges:", {STOCH[a]: round(max(v) - min(v), 3) for a, v in rule.items() if a in STOCH})
print("  head ranges:", {STOCH[a]: round(max(v) - min(v), 3) for a, v in head.items() if a in STOCH})
