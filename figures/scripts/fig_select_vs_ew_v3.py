"""fig:select_vs_ew — (a) cumulative log return of the equal-weight book of the 12 clusterizers against
trailing-winner selection rules; (b) each clusterizer's Sharpe ratio minus the equal-weight book's, with
95% circular-block-bootstrap intervals (block 21 days, 5,000 draws, averaged over three master seeds).

Inputs: the 36 seed-averaged trained books under data/derived/head_logs. The selection rule reselects each
January the clusterizer with the highest trailing Sharpe ratio over the look-back, once at least 252 days of
history exist (``>=``; the earlier ``>`` never fired for the 1-year rule).
"""
import numpy as np
import matplotlib.pyplot as plt
import style
from analysis import books
from analysis.common_calendar import CAL

plt.rcParams.update({"font.size": 11.2, "legend.fontsize": 11})   # print-size batch 2026-08-30

TW = style.CLUSTERIZERS_SHARPE_ORDER; LAB = dict(style.NAME, kmeans_ret="$k$-means", spectral_unsigned="Spectral (unsigned)")
BLK, NB, MASTER = 21, 5000, (42, 7, 101)
SR = lambda v: np.sqrt(252) * v.mean() / v.std(ddof=1)
X = np.stack([books.head_avg(a).values for a in TW]); ew = X.mean(axis=0); T = X.shape[1]
days = [t.strftime("%Y-%m-%d") for t in CAL]
gap = np.array([SR(X[i]) - SR(ew) for i in range(len(TW))])
lo, hi, stable = np.zeros(len(TW)), np.zeros(len(TW)), np.ones(len(TW), dtype=bool)
nb = -(-T // BLK)
for ms in MASTER:
    rng = np.random.default_rng(ms)
    idx = ((rng.integers(0, T, size=(NB, nb))[:, :, None] + np.arange(BLK)[None, None, :]) % T).reshape(NB, -1)[:, :T]
    e = ew[idx]; se = np.sqrt(252) * e.mean(1) / e.std(1, ddof=1)
    for i in range(len(TW)):
        r = X[i][idx]; d = np.sqrt(252) * r.mean(1) / r.std(1, ddof=1) - se
        a, b = np.percentile(d, [2.5, 97.5]); lo[i] += a / len(MASTER); hi[i] += b / len(MASTER); stable[i] &= (a > 0 or b < 0)
o = np.argsort(-gap); yr = np.array([int(k[:4]) for k in days])


def selection(look: int) -> np.ndarray:
    """Payoff of holding, each year, the clusterizer with the best trailing ``look``-year Sharpe ratio."""
    w = np.zeros(T, dtype=int); cur = 0
    for t in range(T):
        if t and yr[t] != yr[t - 1]:
            s = max(0, t - look * 252)
            if t - s >= 252:
                cur = int(np.argmax([SR(X[i][s:t]) for i in range(len(TW))]))
        w[t] = cur
    return X[w, np.arange(T)]


SEL = {f"trailing {L}-year winner": selection(L) for L in (1, 3, 5)}
fig, ax = plt.subplots(1, 2, figsize=(7.3, 2.9), gridspec_kw={"width_ratios": [1.35, 1.0]})
sc = ew.std(ddof=1)
ax[0].plot(np.cumsum(ew), "-", color="black", lw=1.7, label="equal weight, all 12 clusterizers", zorder=4)
for (lab, v), sty in zip(SEL.items(), [(0, (5, 2)), (0, (1.6, 1.6)), (0, (7, 2, 1.6, 2))]):
    ax[0].plot(np.cumsum(v * sc / v.std(ddof=1)), ls=sty, color="0.35", lw=1.1, label=lab)
# ticks: the first trading day of each labeled year (Jan 2 is often a weekend, which used to
# drop 2000/2005/2010 and leave only two labels); 1997 marks the sample start.
_seen, ticks = set(), []
for i, k in enumerate(days):
    y = k[:4]
    if y in ("2000", "2005", "2010", "2015", "2020") and y not in _seen:   # 1997 dropped: collides with 2000 on the narrower canvas
        _seen.add(y); ticks.append(i)
ax[0].set_xticks(ticks); ax[0].set_xticklabels([days[i][:4] for i in ticks])
ax[0].set_ylabel("cumulative log return, vol-matched"); ax[0].set_ylim(-0.12, 2.72)
# the equal-weight book is labeled on the curve itself; the legend carries only the three winners
_h, _l = ax[0].get_legend_handles_labels()
ax[0].legend(_h[1:], _l[1:], frameon=False, loc="lower right", borderaxespad=0.25, labelspacing=0.3, handlelength=1.6, handletextpad=0.5)
_ei = 3800
ax[0].annotate("equal weight, all 12 clusterizers", (_ei, float(np.cumsum(ew)[_ei])), xytext=(-24, 15),
               textcoords="offset points", ha="center", fontsize=11)
ax[0].set_title("(a) selection against\nthe equal-weight portfolio", fontsize=11.2, loc="left")
ax[1].axvline(0, color="0.6", lw=0.8)
for r, i in enumerate(o):
    c = "black" if stable[i] else "0.55"
    ax[1].plot([lo[i], hi[i]], [r, r], "-", color=c, lw=1.2); ax[1].plot(gap[i], r, "o", color=c, ms=4.0)
ax[1].set_yticks(range(len(TW))); ax[1].set_yticklabels([LAB[TW[i]] for i in o], fontsize=11); ax[1].set_ylim(len(TW) - 0.4, -0.6)
ax[1].set_xticks([-0.6, -0.3, 0.0, 0.3])
ax[1].set_xlabel("Sharpe ratio minus\nthe equal-weight portfolio's")
ax[1].set_title("(b) each clusterizer against\nthe equal-weight portfolio,\n$95\\%$ block bootstrap", fontsize=11.2, loc="left")
fig.tight_layout(); style.save(fig, "fig_select_vs_ew", dpi=150)
print(f"  equal-weight Sharpe {SR(ew):.4f}   T={T} days;  intervals excluding zero under every master seed: {stable.sum()} of 12 (below: {(stable & (gap < 0)).sum()})")
for L, v in SEL.items(): print(f"  {L:<24s} Sharpe {SR(v):.4f}")
