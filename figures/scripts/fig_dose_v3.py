"""fig:dose — one partition (PCA loadings) degraded step by step toward a random one.

Input: analysis/results/dose_v3_traded_cal6913.csv (producer analysis/dose_v3_traded.py): for corruption
level q the share of cross-sectional residual variance the partition removes and the annualized
volatility of its rule-based book, two independent corruption draws, plus the actual random control
(draw == -1) on the same traded basis.
"""
import pandas as pd
import matplotlib.pyplot as plt
import style, paths

d = pd.read_csv(paths.RESULTS / "dose_v3_traded_cal6913.csv")
control = d[d.draw == -1].iloc[0]                      # the actual random control
d = d[d.draw >= 0]
m = d.groupby("q")[["removal_share", "ann_vol"]].mean().reset_index()
floor = float(d[d.q == 0].dof_floor.iloc[0])           # (K-1)/(N_t-1) on the traded universe
intact = float(d[d.q == 0].removal_share.iloc[0])

fig, ax = plt.subplots(figsize=(5.0, 3.6))
ax.axvline(floor, color="0.30", ls=":", lw=0.9); ax.axvline(intact, color="0.30", ls=":", lw=0.9)
ax.annotate(r"floor $(\mathrm{K}{-}1)/(\mathrm{N}{-}1)$", (floor, 0.0625), xytext=(6, 0), textcoords="offset points",
            fontsize=8.2, color="0.30", rotation=90, va="bottom")
ax.annotate("intact partition", (intact, 0.0625), xytext=(-6, 0), ha="right", textcoords="offset points",
            fontsize=8.2, color="0.30", rotation=90, va="bottom")
ax.plot(m.removal_share, m.ann_vol, color=style.GREY, lw=1.0, zorder=1)
for draw, marker in ((0, "o"), (1, "^")):
    s = d[d.draw == draw]
    ax.scatter(s.removal_share, s.ann_vol, s=22, marker=marker, facecolors="none", edgecolors="black",
               linewidths=0.9, zorder=3)
ax.scatter([control.removal_share], [control.ann_vol], marker="x", s=60, color=style.CONTROL_RED,
           linewidths=1.6, zorder=4)
for q in (0.0, 0.3, 0.6, 1.0):
    r = m[m.q == q].iloc[0]
    ax.annotate(f"$q={q:g}$", (r.removal_share, r.ann_vol), xytext=(7, -8), textcoords="offset points", fontsize=8.2, color="0.35")
ax.set_xlabel("share of cross-sectional variance the partition removes")
import matplotlib.ticker as _mt
ax.xaxis.set_major_formatter(_mt.PercentFormatter(xmax=1.0, decimals=0))
ax.yaxis.set_major_formatter(_mt.PercentFormatter(xmax=1.0, decimals=1))
ax.set_ylabel("annualized book volatility")
ax.invert_xaxis()
# labels sit on the series themselves (Schwabish 2014): the two corruption draws are one cloud, so
# one label with a note is clearer than a legend box repeating the marker shapes.
ax.text(0.55, 0.24, "two corruption draws\n(circles and triangles)", transform=ax.transAxes,
        ha="center", fontsize=8.2, color="0.25")
ax.annotate("random control (actual)", (control.removal_share, control.ann_vol), xytext=(-12, 12),
            textcoords="offset points", ha="right", fontsize=8.2, color=style.CONTROL_RED)
fig.tight_layout(); style.save(fig, "fig_dose")
print(m.round(5).to_string(index=False))
