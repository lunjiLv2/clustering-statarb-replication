"""fig:bet_corr — correlation of daily position vectors between arms (same training seed, averaged
over seeds) and, on the diagonal, between two training seeds of the same arm, on the full 6,913-day
common calendar.

Inputs: data/derived/weights/{arm}_seed{s}.pkl — a list of (date, tickers, weights) per scored day,
gross exposure one — and the trained books for the gross-leverage cross-check. Also writes
analysis/results/bet_corr_matrix_v3_12arm_cal6913.csv.

The day basis matters and was wrong until 2026-09-01. This figure ran on every 10th day (692 of the
6,913) for speed, while its caption, its output file's name and tab:gradient's position row all said
6,913 — and the table's row comes from analysis/gradient_pos_v3.py, which really does use every day.
The two bases differ in the third decimal (stride 10 gave own-refit 0.706 against 0.704 on the full
calendar), which is how a stride-10 number reached the table. Both are now on the full calendar and
agree: off-diagonal 0.6118, diagonal 0.7036, ratio 0.870 (CORRECTIONS N83 add. 1). BETCORR_STRIDE
still buys a fast preview; a shipped figure must be STRIDE = 1.
"""
import itertools, os, pickle
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
import style, paths
from analysis.common_calendar import CAL

RULES = style.CLUSTERIZERS_SHARPE_ORDER; CTRL = ["k1", "random"]; ARMS = RULES + CTRL; SEEDS = paths.SEEDS
# STRIDE = 1 is the full 6,913-day calendar, which is what the caption claims and what
# tab:gradient's position row is measured on. It was 10 for speed, which put the figure on 692
# days while the caption, the output CSV's old filename and the table row all said 6,913
# (CORRECTIONS N83 add. 1). The manuscript master was switched on 2026-09-01 and the shipped
# figure is now full-calendar; this copy follows it. Override with BETCORR_STRIDE for a fast
# preview, never for a shipped figure.
STRIDE = int(os.environ.get("BETCORR_STRIDE", "1"))
LAB = dict(style.NAME, kmeans_ret="$k$-means", spectral_unsigned="Spectral (unsigned)", k1="$K=1$", random="random")
CALSET = {t.strftime("%Y-%m-%d") for t in CAL}


def positions(arm: str, seed: int) -> dict[str, dict[str, float]]:
    """Position vectors of one run on every STRIDE-th common day, as {date: {ticker: weight}}."""
    W = pickle.load(open(paths.WEIGHTS / f"{arm}_seed{seed}.pkl", "rb")); out = {}
    for i, (dt, tk, wv) in enumerate(W):
        k = str(dt)[:10]
        if i % STRIDE or k not in CALSET: continue
        v = np.asarray(wv, dtype=float); assert abs(abs(v).sum() - 1.0) < 1e-5, f"{arm} {seed} {k}: gross != 1"
        out[k] = dict(zip(tk, v))
    return out


def pos_corr(x, y) -> float:
    """Mean over shared days of the correlation of two position vectors on the union of their names."""
    r = []
    for k in set(x) & set(y):
        names = sorted(set(x[k]) | set(y[k])); a = np.array([x[k].get(t, 0.0) for t in names]); b = np.array([y[k].get(t, 0.0) for t in names])
        r.append(np.corrcoef(a, b)[0, 1])
    return float(np.mean(r))


P = {(a, s): positions(a, s) for a in ARMS for s in SEEDS}
n = len(ARMS); M = np.zeros((n, n))
for i, a in enumerate(ARMS):
    M[i, i] = np.mean([pos_corr(P[(a, s1)], P[(a, s2)]) for s1, s2 in itertools.combinations(SEEDS, 2)])
    for j in range(i + 1, n):
        M[i, j] = M[j, i] = np.mean([pos_corr(P[(a, s)], P[(ARMS[j], s)]) for s in SEEDS])
pd.DataFrame(M, index=ARMS, columns=ARMS).to_csv(paths.RESULTS / "bet_corr_matrix_v3_12arm_cal6913.csv")

fig, ax = plt.subplots(figsize=(6.2, 5.4))
im = ax.imshow(M, cmap="cividis", vmin=0.40, vmax=0.80)
ax.set_xticks(range(n)); ax.set_yticks(range(n))
ax.set_xticklabels([LAB[a] for a in ARMS], rotation=45, ha="right", fontsize=9.2); ax.set_yticklabels([LAB[a] for a in ARMS], fontsize=9.2)
for i in range(n):
    for j in range(n):
        ax.text(j, i, "%.2f" % M[i, j], ha="center", va="center", fontsize=9.0, color="0.10" if M[i, j] > 0.63 else "white")
    ax.add_patch(plt.Rectangle((i - 0.5, i - 0.5), 1, 1, fill=False, ec=style.CONTROL_RED, lw=1.1, zorder=5))
ax.axhline(len(RULES) - 0.5, color=style.CONTROL_RED, lw=1.5); ax.axvline(len(RULES) - 0.5, color=style.CONTROL_RED, lw=1.5)
ax.set_xticks(np.arange(-.5, n, 1), minor=True); ax.set_yticks(np.arange(-.5, n, 1), minor=True)
ax.grid(which="minor", color="white", lw=0.6, alpha=0.55); ax.tick_params(which="minor", length=0)
cb = fig.colorbar(im, ax=ax, fraction=0.040, pad=0.02); cb.set_label("correlation of portfolio weights", fontsize=9.5); cb.ax.tick_params(labelsize=9.2)
fig.tight_layout(); style.save(fig, "fig_bet_corr", dpi=160)
off = [M[i, j] for i in range(len(RULES)) for j in range(i + 1, len(RULES))]; dia = [M[i, i] for i in range(len(RULES))]
print(f"  clusterizers: off-diagonal mean {np.mean(off):.4f} | own-refit diagonal mean {np.mean(dia):.4f} | ratio {np.mean(off) / np.mean(dia):.3f}")
