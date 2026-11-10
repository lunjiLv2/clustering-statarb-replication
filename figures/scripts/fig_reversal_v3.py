"""fig:reversal — what the short-term reversal factor does to each book's alpha (§6.2, tab:spanning).

Two panels, one per trading component, era = full sample (6,913 days). The 14 arms sit on the vertical axis
ordered by their FF5+MOM alpha (alpha6, top = highest); for each arm an open circle marks alpha6, a filled circle
alpha7 (FF5+MOM + the Ken French short-term reversal factor), joined by a segment. Controls red, clusterizers black.
The dotted guide is the lowest clusterizer alpha7 in the panel: at the rule-based component both controls' filled
circles land below it, at the trained component every segment is short. Both panels share one x-axis: the
rule-based alphas are drawn at gross exposure one (stored books x analysis.books.RULE_REPORT_SCALE, N123), the gross
exposure of the trained books, as in tab:spanning. Values are read from analysis/results/strev_spanning_v3_cal6913.csv (strev_spanning_v3.py); the
figure prints no number that tab:spanning / §6.2 do not already print.
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import style, paths
from analysis.books import RULE_REPORT_SCALE   # N123: rule-based levels at gross exposure one

plt.rcParams.update({"font.size": 9.2})
LABEL = {"kmeans_ret": "$k$-means on returns", "pca_load": "PCA loadings", "agglo_avg": "Average linkage",
         "agglo_complete": "Complete linkage", "spectral_unsigned": "Spectral (unsigned)", "gics": "GICS",
         "sponge_w60": "SPONGE", "fv2a_w60": "Sharpe (EW)", "fv3sm_w60": "Sharpe (graph)", "sharpe_fixed_w60": "Sharpe",
         "sortino_w60": "Sortino", "sssnetpre": "SSSNET", "k1": "No clustering ($K{=}1$)", "random": "Random partition"}
CTRL = ("k1", "random")
d = pd.read_csv(paths.RESULTS / "strev_spanning_v3_cal6913.csv")
d = d[d.era == "full"].copy()
d.loc[d.component == "rule", ["alpha6", "alpha7"]] *= RULE_REPORT_SCALE
LO, HI = min(d.alpha6.min(), d.alpha7.min()), max(d.alpha6.max(), d.alpha7.max())   # one horizontal axis for both panels
assert set(d.arm) == set(LABEL) and len(d) == 28, "expected the 14 arms at both components on the full sample"

fig, axes = plt.subplots(1, 2, figsize=(6.4, 3.9), sharey=False, sharex=True)
for ax, comp, title in zip(axes, ("rule", "head"), ("(a) rule-based component", "(b) trained component")):
    p = d[d.component == comp].set_index("arm").sort_values("alpha6", ascending=True)   # top of the axis = highest alpha6
    y = np.arange(len(p))
    guide = p.drop(list(CTRL)).alpha7.min()
    ax.axvline(guide, color="0.75", lw=0.8, ls=(0, (2, 2)), zorder=1)
    for i, (arm, r) in enumerate(p.iterrows()):
        c = style.CONTROL_RED if arm in CTRL else "black"
        ax.plot([r.alpha6, r.alpha7], [i, i], "-", color=c, lw=1.1, zorder=2)
        ax.plot(r.alpha6, i, "o", ms=4.6, mfc="white", mec=c, mew=1.1, zorder=3)
        ax.plot(r.alpha7, i, "o", ms=4.6, mfc=c, mec=c, zorder=4)
    ax.set_yticks(y); ax.set_yticklabels([LABEL[a] for a in p.index], fontsize=8.2)
    for lab, arm in zip(ax.get_yticklabels(), p.index):
        if arm in CTRL: lab.set_color(style.CONTROL_RED)
    ax.set_ylim(-0.7, len(p) - 0.3)
    ax.set_xlabel("alpha (% per year)")
    ax.set_title(title, loc="left", fontsize=9.6)
    ax.grid(axis="x", color="0.92", lw=0.6, zorder=0)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(LO - 0.06 * (HI - LO), HI + 0.06 * (HI - LO))
    print(f"  {comp:5s} clusterizers alpha6 {p.drop(list(CTRL)).alpha6.min():.2f}-{p.drop(list(CTRL)).alpha6.max():.2f} -> alpha7 "
          f"{p.drop(list(CTRL)).alpha7.min():.2f}-{p.drop(list(CTRL)).alpha7.max():.2f}; controls alpha7 "
          f"{p.loc['k1','alpha7']:.2f} / {p.loc['random','alpha7']:.2f}; guide {guide:.2f}")
# one legend for both panels, no box, in the empty upper-left corner of panel (a) (the high-alpha rows sit to the right)
h = [plt.Line2D([], [], marker="o", ls="", mfc="white", mec="black", mew=1.1, ms=4.6, label="FF5+MOM"),
     plt.Line2D([], [], marker="o", ls="", mfc="black", mec="black", ms=4.6, label="FF5+MOM + short-term reversal")]
fig.legend(handles=h, loc="lower center", ncol=2, frameon=False, fontsize=8.0, handletextpad=0.4, columnspacing=1.6, bbox_to_anchor=(0.5, 0.0))   # below both panels: a shared axis leaves no empty corner
fig.tight_layout(w_pad=1.6, rect=(0, 0.06, 1, 1))
style.save(fig, "fig_reversal", dpi=170)
