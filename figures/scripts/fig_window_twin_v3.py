"""fig:window_twin — the 60-to-21-day leg of the estimation-window sweep (§5.5, app:window): all five 21-day
twins of app:names (k-means on returns, complete linkage, PCA loadings, average linkage, spectral), each at the
head seeds of paths.SEEDS. Circles: 60-day window per seed; diamonds: 21-day window per seed; bars: the two
means; grey band: ± one across-seed s.d. of the 60-day leg; the number beside each arm is the mean move.

Inputs: trained books {arm}_seed{s}.csv and {arm}_w21_seed{s}.csv under data/derived/head_logs, read through
analysis.books (6,913-day common calendar). Ported from the manuscript master of 2026-09-01 (five arms; the
earlier three-arm version predates the seeds-2–5 runs of kmeans_ret_w21 and agglo_complete_w21).
"""
import numpy as np
import matplotlib.pyplot as plt
import style
import paths
from analysis import books

plt.rcParams.update({"font.size": 9.7, "legend.fontsize": 8.8})   # print-size batch 2026-08-30

ARMS = [("kmeans_ret", "$k$-means on returns"), ("agglo_complete", "Complete linkage"), ("pca_load", "PCA loadings"),
        ("agglo_avg", "Average linkage"), ("spectral_unsigned", "Spectral (unsigned)")]
# Five arms do not fit on one line at this width; the tick labels wrap onto two lines and the gap
# between neighbours is asserted on the rendered canvas below, not eyeballed.
TICK = {"kmeans_ret": "$k$-means\non returns", "agglo_complete": "Complete\nlinkage", "pca_load": "PCA\nloadings",
        "agglo_avg": "Average\nlinkage", "spectral_unsigned": "Spectral\n(unsigned)"}
per_seed = lambda a, v="": [books.sharpe(b) for b in books.head_books(a, v).values()]
n = len(paths.SEEDS)

fig, ax = plt.subplots(figsize=(5.6, 3.2))
for i, (a, lab) in enumerate(ARMS):
    w60, w21 = per_seed(a), per_seed(a, "_w21"); assert len(w60) == len(w21) == n
    sd = np.std(w60, ddof=1); m60, m21 = np.mean(w60), np.mean(w21)
    ax.fill_between([i - 0.30, i + 0.30], m60 - sd, m60 + sd, color="0.88", zorder=1, lw=0)
    ax.plot([i] * n, w60, "o", ms=4.0, mfc="none", mec="0.30", mew=1.0, zorder=3)
    ax.plot([i] * n, w21, "D", ms=3.6, mfc="none", mec="black", mew=1.0, zorder=3)
    ax.plot([i - 0.16, i + 0.16], [m60] * 2, "-", color="0.30", lw=1.5, zorder=4)
    ax.plot([i - 0.16, i + 0.16], [m21] * 2, "-", color="black", lw=1.5, zorder=4)
    ax.annotate("$%+.2f$" % (m21 - m60), (i + 0.20, m21), ha="left", va="center", fontsize=8.9)
    print(f"  {a:<20s} w60 {m60:.4f} (sd {sd:.4f})  w21 {m21:.4f}  move {m21 - m60:+.4f}  {'inside sd' if abs(m21 - m60) < sd else 'outside sd'}")
ax.set_xticks(range(len(ARMS))); ax.set_xticklabels([TICK[a] for a, _ in ARMS], fontsize=8.6, linespacing=1.15)
ax.set_xlim(-0.55, len(ARMS) - 0.45)
ax.set_ylabel("Sharpe ratio, trained component")
# the two windows are labelled where they separate most (the second arm), not in a legend box
_a1 = ARMS[1][0]; _w60, _w21 = per_seed(_a1), per_seed(_a1, "_w21")
ax.annotate("$60$-day window", (1, max(_w60)), xytext=(12, 6), textcoords="offset points", ha="left", fontsize=8.8, color="0.30")
ax.annotate("$21$-day window", (1, min(_w21)), xytext=(12, -8), textcoords="offset points", ha="left", fontsize=8.8, color="black")
fig.tight_layout()
# gate: no two tick labels may touch, measured on the rendered canvas in points
fig.canvas.draw()
_bb = sorted((t.get_window_extent(fig.canvas.get_renderer()) for t in ax.get_xticklabels()), key=lambda b: b.x0)
_gaps = [(_bb[k + 1].x0 - _bb[k].x1) / fig.dpi * 72.0 for k in range(len(_bb) - 1)]
print("  tick-label gaps (pt): " + "  ".join("%.1f" % g for g in _gaps))
assert min(_gaps) >= 4.0, "x tick labels collide: min gap %.1f pt" % min(_gaps)
style.save(fig, "fig_window_twin", dpi=150)
