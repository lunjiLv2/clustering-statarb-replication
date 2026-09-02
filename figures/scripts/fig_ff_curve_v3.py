"""fig:ff_curve — share of each partition's explained cross-sectional variance that survives projecting
out nested Fama–French factor sets (CAPM, FF3, FF5, FF5+MOM), for the 12 clusterizers and the random control.

Input: analysis/results/lens_v3_full_stages_cal6913.csv (producer analysis/verify_lens.py with LENS_STAGES=1).
SUPERSEDED on 2026-08-31: this content is now panel (b) of fig:lens_curve, which draws it on the
panel-(a) vertical axis. The script is kept because it still runs, but the manuscript no longer
includes fig_ff_curve.pdf.
"""
import pandas as pd
import matplotlib.pyplot as plt
import style, paths

d = pd.read_csv(paths.RESULTS / "lens_v3_full_stages_cal6913.csv").set_index("arm")
ARMS = ["kmeans_ret", "sssnet_w60", "agglo_complete", "fv3sm_w60", "sponge_w60", "pca_load",
        "agglo_avg", "sortino_w60", "fv2a_w60", "sharpe_fixed_w60", "gics", "spectral_unsigned"]
STAGE = [("none", None), ("CAPM", "ret_CAPM"), ("FF3", "ret_FF3"), ("FF5", "ret_FF5"), ("FF5+MOM", "ret_FF6")]
X = range(len(STAGE))

fig, ax = plt.subplots(figsize=(5.3, 3.4))
for a in ARMS:
    y = [1.0] + [d.loc[a, c] for _, c in STAGE[1:]]; hi = a == "kmeans_ret"
    ax.plot(X, y, color="black" if hi else style.GREY, lw=1.6 if hi else 0.9, zorder=3 if hi else 1, marker="o" if hi else None, ms=3)
ax.plot(X, [1.0] + [d.loc["random", c] for _, c in STAGE[1:]], color=style.CONTROL_RED, lw=1.4, ls="--", marker="s", ms=3, zorder=4)
k3, k5 = d.loc["kmeans_ret", "ret_3PC"], d.loc["kmeans_ret", "retention"]
ax.axhline(k3, color="0.30", lw=0.8, ls=":", zorder=2); ax.axhline(k5, color="0.30", lw=0.8, ls=":", zorder=2)
ax.annotate(f"$k$-means at 3 PCs ({k3:.0%})", (0.04, k3), xytext=(0, 4), textcoords="offset points", fontsize=7.5, color="0.30")
ax.annotate(f"$k$-means at 5 PCs ({k5:.0%})", (0.04, k5), xytext=(0, -11), textcoords="offset points", fontsize=7.5, color="0.30")
ax.annotate("$k$-means", (4, d.loc["kmeans_ret", "ret_FF6"]), xytext=(-46, 7), textcoords="offset points", fontsize=8)
lo, hi_ = d.loc[ARMS, "ret_FF6"].min(), d.loc[ARMS, "ret_FF6"].max()
ax.annotate(f"12 clusterizers\n{lo:.0%}–{hi_:.0%} after FF5+MOM", (4, (lo + hi_) / 2), xytext=(-100, -21), textcoords="offset points", fontsize=8, color="0.40")
ax.annotate("random control", (2, d.loc["random", "ret_FF3"]), xytext=(-16, -16), textcoords="offset points", fontsize=8, color=style.CONTROL_RED)
ax.set_xticks(list(X)); ax.set_xticklabels([n for n, _ in STAGE])
ax.set_xlabel("factor set projected out"); ax.set_ylabel("share of the unprojected value retained"); ax.set_ylim(0.42, 1.06)
ax.text(0.02, 0.04, r"$\mathrm{K}{=}1$ control: share is zero by construction", transform=ax.transAxes, fontsize=7.5, color="0.45")
fig.tight_layout(); style.save(fig, "fig_ff_curve")
print(f"  k-means: 3PC {k3:.4f}  FF5+MOM {d.loc['kmeans_ret','ret_FF6']:.4f}  5PC {k5:.4f};  band after FF5+MOM {lo:.4f}–{hi_:.4f}; random {d.loc['random','ret_FF6']:.4f}")
