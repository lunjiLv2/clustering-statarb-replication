"""fig:lens_curve — the share of each partition's explained cross-sectional variance that survives a
projection, under two lenses drawn on one shared vertical axis:

  (a) after the leading m principal components are projected out;
  (b) after nested Fama–French factor sets (CAPM, FF3, FF5, FF5+MOM) are projected out.

The panels share the axis because the comparison between them is the point: the principal components
take more than the factors do, and panel (b) carries the k-means positions at three and five
components as dotted references so that the two lenses can be read against each other without
turning the page. Panel (b) held its own figure until 2026-08-31; the matching-cost bar chart that
used to sit here as panel (b) is now fig:match_cost.

Input: analysis/results/lens_v3_full_stages_cal6913.csv (producer analysis/verify_lens.py). The
in-figure statistics are computed from that file at draw time.
"""
import pandas as pd
import matplotlib.pyplot as plt
import style, paths

plt.rcParams.update({"font.size": 12.6, "legend.fontsize": 11.2})   # print-size batch 2026-08-30
BUNDLE = "0.55"                                    # print floor: 0.68 hairlines drop out in greyscale

d = pd.read_csv(paths.RESULTS / "lens_v3_full_stages_cal6913.csv").set_index("arm")
ARMS = ["kmeans_ret", "sssnet_w60", "agglo_complete", "fv3sm_w60", "sponge_w60", "pca_load",
        "agglo_avg", "sortino_w60", "fv2a_w60", "sharpe_fixed_w60", "gics", "spectral_unsigned"]
M = [0, 1, 3, 5]; COL = {0: None, 1: "ret_1PC", 3: "ret_3PC", 5: "retention"}
STAGE = [("none", None), ("CAPM", "ret_CAPM"), ("FF3", "ret_FF3"), ("FF5", "ret_FF5"), ("FF5+MOM", "ret_FF6")]
XF = range(len(STAGE))

fig, ax = plt.subplots(1, 2, figsize=(7.4, 3.35), sharey=True)

# ---- (a) principal components -------------------------------------------------
for a in ARMS:
    y = [1.0] + [d.loc[a, COL[m]] for m in M[1:]]; hi = a == "kmeans_ret"
    ax[0].plot(M, y, color="black" if hi else BUNDLE, lw=1.6 if hi else 1.0,
               zorder=3 if hi else 1, marker="o" if hi else None, ms=3)
rnd = [1.0] + [d.loc["random", COL[m]] for m in M[1:]]
ax[0].plot(M, rnd, color=style.CONTROL_RED, lw=1.4, ls="--", marker="s", ms=3, zorder=4)
ax[0].annotate("$k$-means", (5, d.loc["kmeans_ret", "retention"]), xytext=(4, 6),
               textcoords="offset points", fontsize=11.2)
ax[0].annotate(f"random control — on the floor,\nretains {min(rnd[1:]):.1%} at every $m$", (1, 1.0),
               xytext=(6, -30), textcoords="offset points", fontsize=11.2, color=style.CONTROL_RED)
lo, hiv = d.loc[ARMS, "retention"].min(), d.loc[ARMS, "retention"].max()
ax[0].annotate(f"12 clusterizers\n{lo:.0%}–{hiv:.0%} at $m$=5", (3, 0.60), xytext=(-6, 26),
               textcoords="offset points", fontsize=11.2, color="0.40")
ax[0].set_xticks(M); ax[0].set_xlabel("principal components projected out, $m$")
ax[0].set_ylabel("share of the unprojected value retained"); ax[0].set_ylim(0.35, 1.09)
ax[0].set_title("(a) after principal components", fontsize=12.6, loc="left")
ax[0].text(0.02, 0.06, r"$\mathrm{K}{=}1$ control: share is zero by construction",
           transform=ax[0].transAxes, fontsize=10.5, color="0.45")

# ---- (b) Fama–French factors, on the same vertical scale ----------------------
for a in ARMS:
    y = [1.0] + [d.loc[a, c] for _, c in STAGE[1:]]; hi = a == "kmeans_ret"
    ax[1].plot(XF, y, color="black" if hi else BUNDLE, lw=1.6 if hi else 1.0,
               zorder=3 if hi else 1, marker="o" if hi else None, ms=3)
ax[1].plot(XF, [1.0] + [d.loc["random", c] for _, c in STAGE[1:]],
           color=style.CONTROL_RED, lw=1.4, ls="--", marker="s", ms=3, zorder=4)
k3, k5 = d.loc["kmeans_ret", "ret_3PC"], d.loc["kmeans_ret", "retention"]
for v, lab in ((k3, f"$k$-means at 3 PCs ({k3:.0%})"), (k5, f"$k$-means at 5 PCs ({k5:.0%})")):
    ax[1].axhline(v, color="0.30", lw=0.8, ls=":", zorder=2)
    ax[1].annotate(lab, (0.04, v), xytext=(0, -13), textcoords="offset points", fontsize=10.5, color="0.30")
lof, hif = d.loc[ARMS, "ret_FF6"].min(), d.loc[ARMS, "ret_FF6"].max()
ax[1].annotate("$k$-means", (4, d.loc["kmeans_ret", "ret_FF6"]), xytext=(-52, 8),
               textcoords="offset points", fontsize=11.2)
ax[1].annotate(f"12 clusterizers\n{lof:.0%}–{hif:.0%} after FF5+MOM", (4, (lof + hif) / 2),
               xytext=(-96, -48), textcoords="offset points", fontsize=11.2, color="0.40")
ax[1].annotate("random control", (2, d.loc["random", "ret_FF3"]), xytext=(-18, -18),
               textcoords="offset points", fontsize=11.2, color=style.CONTROL_RED)
ax[1].set_xticks(list(XF)); ax[1].set_xticklabels([n for n, _ in STAGE])
ax[1].set_xlabel("factor set projected out")
ax[1].set_title("(b) after the Fama–French factors", fontsize=12.6, loc="left")

fig.tight_layout(pad=0.5); style.save(fig, "fig_lens_curve", pad=0.06)
print(f"  (a) k-means retention@5 {d.loc['kmeans_ret','retention']:.4f} | field {lo:.4f}-{hiv:.4f} | random {d.loc['random','retention']:.4f}")
print(f"  (b) k-means FF5+MOM {d.loc['kmeans_ret','ret_FF6']:.4f} | field {lof:.4f}-{hif:.4f} | random {d.loc['random','ret_FF6']:.4f}")
