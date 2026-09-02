"""fig:match_cost — how many principal components a partition costs to match.

For each clusterizer, the mean number of leading principal components a rank-matched projection needs
before it explains as much cross-sectional variance as the partition does, with the share of days on
which 30 components never suffice printed beside the bar. This answers a different question from the
retention curves of fig:lens_curve — how expensive the partition is to imitate, rather than how much
of its value survives a projection — so on 2026-08-31 it was split out of that figure, where it had
been panel (b), and given its own.

Input: analysis/results/lens_v3_full_stages_cal6913.csv (producer analysis/verify_lens.py).
"""
import pandas as pd
import matplotlib.pyplot as plt
import style, paths

plt.rcParams.update({"font.size": 11.0, "legend.fontsize": 10.0})   # print-size batch 2026-08-30

d = pd.read_csv(paths.RESULTS / "lens_v3_full_stages_cal6913.csv").set_index("arm")
ARMS = ["kmeans_ret", "sssnet_w60", "agglo_complete", "fv3sm_w60", "sponge_w60", "pca_load",
        "agglo_avg", "sortino_w60", "fv2a_w60", "sharpe_fixed_w60", "gics", "spectral_unsigned"]
PNAME = dict(style.NAME, kmeans_ret="$k$-means")

fig, ax = plt.subplots(figsize=(4.6, 3.3))
order = sorted(ARMS, key=lambda a: d.loc[a, "m_match"])
ax.barh(range(len(order)), [d.loc[a, "m_match"] for a in order],
        color=["black" if a == "kmeans_ret" else "0.55" for a in order], height=0.7)
ax.set_ylim(-1.6, len(order) - 0.3)
ax.set_yticks(range(len(order))); ax.set_yticklabels([PNAME[a] for a in order], fontsize=9.6)
ax.axvline(d.loc["random", "m_match"], color=style.CONTROL_RED, ls="--", lw=1.2)
ax.annotate("random control", (d.loc["random", "m_match"], -0.9), xytext=(4, 0),
            textcoords="offset points", fontsize=9.6, color=style.CONTROL_RED)
for i, a in enumerate(order):
    ax.annotate(f"{d.loc[a, 'never_matched_pct']:.1f}%", (d.loc[a, "m_match"], i),
                xytext=(3, -2.6), textcoords="offset points", fontsize=9.6,
                color="black" if a == "kmeans_ret" else "0.45")
ax.set_xticks([0, 5, 10, 15, 20]); ax.set_xlim(0, 21.5)
ax.set_xlabel("principal components needed\nto match the partition (mean)")
fig.tight_layout(pad=0.4); style.save(fig, "fig_match_cost", pad=0.06)
print(f"  k-means m_match {d.loc['kmeans_ret','m_match']:.2f}, never matched "
      f"{d.loc['kmeans_ret','never_matched_pct']:.1f}% | random {d.loc['random','m_match']:.2f}")
