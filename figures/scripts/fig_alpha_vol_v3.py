"""fig:alpha_vol — what clustering buys, in one picture: one point per arm at the trained component.

  x  annualized book volatility in percent, computed per head seed and then averaged over the
     seeds — the convention of the volatility rows of tab:moments;
  y  FF5+MOM alpha in percent per year of the seed-averaged payoff, Newey–West at 21 lags — the
     convention of the alpha rows of the same table.
The two axes therefore carry the two conventions the table itself uses, which differ; the caption
says so. Labels sit beside the points (no legend box) and only the corners of the cloud are
labelled: with 12 clusterizers inside an alpha band of nine tenths of a point, labelling all of
them makes the plot unreadable.

Inputs: the trained books under data/derived/head_logs and the Ken French factors. The coordinates
are recomputed here from the books and checked against analysis/results/alpha_vol_points_v3_cal6913.csv,
the file the manuscript figure was drawn from; the two must agree to 1e-9. Ported from the manuscript master
of 2026-09-01 (labelled corners and data-driven axis limits follow the five-seed data).
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import style, paths
from analysis import books
from analysis.factors import FF6, load_ff, nw_ols, alpha_pct

plt.rcParams.update({"font.size": 9.2, "legend.fontsize": 8.4})

SEEDS = paths.SEEDS           # the paper's seed set, from paths (CSA_SEEDS overrides it)
CTRL = ["k1", "random"]
PNAME = dict(style.NAME, kmeans_ret="$k$-means", spectral_unsigned="Spectral (unsigned)",
             k1="No clustering ($K{=}1$)", random="Random partition")
# the four labelled clusterizers are the extremes in each direction; the other eight are plain markers
LABELLED = {"kmeans_ret": (0, -11, "center"),        # lowest volatility; the left margin is tight
            "fv3sm_w60": (0, 9, "center"),           # highest alpha at five seeds (complete linkage at the retired set)
            "gics": (7, 4, "left"),                  # high alpha at high volatility
            "spectral_unsigned": (7, -1, "left"),    # highest volatility, lowest alpha
            "k1": (-8, 0, "right"), "random": (8, 0, "left")}

ff = load_ff()[FF6]
rows = []
for arm in paths.ARMS:
    vol = float(np.mean([books.ann_vol(books.head_book(arm, s)) for s in SEEDS]))
    y = books.head_avg(arm, seeds=SEEDS)
    m = pd.concat([y.rename("y"), ff.shift(1)], axis=1).reindex(books.IDX).dropna()
    b, _, _ = nw_ols(m.y.to_numpy(), m[FF6].to_numpy())
    rows.append(dict(arm=arm, vol=vol, alpha=alpha_pct(b)))
d = pd.DataFrame(rows).set_index("arm")

ref = pd.read_csv(paths.RESULTS / "alpha_vol_points_v3_cal6913.csv").set_index("arm")
dev = float((d[["vol", "alpha"]] - ref.loc[d.index, ["vol", "alpha"]]).abs().to_numpy().max())
assert dev < 1e-9, f"coordinates differ from the shipped table by {dev:.2e}"

fig, ax = plt.subplots(figsize=(4.9, 3.5))
for arm, r in d.iterrows():
    ctl = arm in CTRL
    ax.plot(r.vol, r.alpha, "o", ms=5.0 if ctl else 4.2, mfc=style.CONTROL_RED if ctl else "none",
            mec=style.CONTROL_RED if ctl else "0.15", mew=1.2, zorder=3)
    if arm in LABELLED:
        dx, dy, ha = LABELLED[arm]
        ax.annotate(PNAME[arm], (r.vol, r.alpha), xytext=(dx, dy), textcoords="offset points",
                    ha=ha, va="center", fontsize=8.0,
                    color=style.CONTROL_RED if ctl else "0.15", zorder=4)
cl = d.drop(CTRL)
ax.axhspan(cl.alpha.min(), cl.alpha.max(), color="0.92", zorder=0)
ax.annotate("the 12 clusterizers, alpha $%.2f$–$%.2f$" % (cl.alpha.min(), cl.alpha.max()),
            (cl.vol.mean() + 0.55, cl.alpha.max()), xytext=(0, 22), textcoords="offset points",
            ha="center", fontsize=7.8, color="0.40", zorder=4)
ax.set_xlabel("annualized volatility of the portfolio (%)")
ax.set_ylabel("FF5+MOM alpha (% per year)")
# Data-driven limits with a margin. A hard-coded ylim tuned to an earlier seed set silently dropped
# both controls once their alphas fell below it; the assertion makes that failure loud.
xpad = 0.10 * (d.vol.max() - d.vol.min()); ypad = 0.14 * (d.alpha.max() - d.alpha.min())
x0, x1 = d.vol.min() - xpad, d.vol.max() + xpad; y0, y1 = d.alpha.min() - ypad, d.alpha.max() + ypad
ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
assert d.vol.between(x0, x1).all() and d.alpha.between(y0, y1).all(), "a point falls outside the axes"
fig.tight_layout(); style.save(fig, "fig_alpha_vol", dpi=170)
print(f"  coordinates match the shipped table to {dev:.1e}")
print(f"  clusterizers: vol {cl.vol.min():.2f}-{cl.vol.max():.2f}, alpha {cl.alpha.min():.2f}-{cl.alpha.max():.2f}")
print(f"  controls: k1 ({d.loc['k1','vol']:.2f}, {d.loc['k1','alpha']:.2f})  "
      f"random ({d.loc['random','vol']:.2f}, {d.loc['random','alpha']:.2f})")
