"""Shared style, names and output locations for the manuscript figures.

Every figure script imports this module so that fonts, colours, arm names and output paths are
defined once. Figures are written to ``paper/figures/<name>.pdf`` (the files the manuscript includes)
and a PNG preview to ``figures/previews/``.
"""
from __future__ import annotations
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import paths  # noqa: E402

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Nimbus Roman", "Liberation Serif", "STIXGeneral", "DejaVu Serif"],
    "mathtext.fontset": "stix", "font.size": 9, "legend.fontsize": 8,
    "pdf.fonttype": 42, "axes.spines.top": False, "axes.spines.right": False,
})

CONTROL_RED = "#b22222"      # the random control, everywhere
GREY = "0.68"                # the other clusterizers when one is highlighted

NAME = {"kmeans_ret": "k-means", "sssnet_w60": "SSSNET", "sssnetpre": "SSSNET",
        "agglo_complete": "Complete linkage", "fv3sm_w60": "Sharpe (graph)", "sponge_w60": "SPONGE",
        "pca_load": "PCA loadings", "agglo_avg": "Average linkage", "sortino_w60": "Sortino",
        "fv2a_w60": "Sharpe (EW)", "sharpe_fixed_w60": "Sharpe", "gics": "GICS",
        "spectral_unsigned": "Spectral", "k1": "no clustering ($K=1$)", "random": "random partition"}
"""Display names of the arms, as printed in the manuscript's tables."""

# Sharpe order on the paper's five head seeds, re-derived 2026-09-01 (mean of the per-seed Sharpe
# ratios, the convention fig:rank_shift's caption states). At three seeds this list read
# kmeans_ret, agglo_complete, fv3sm_w60, sponge_w60, sssnetpre, pca_load, agglo_avg, sortino_w60,
# fv2a_w60, sharpe_fixed_w60, gics, spectral_unsigned; positions 2-8 move at five seeds. Any figure
# whose caption says "ordered by Sharpe ratio" reads this list, so it must track the seed set.
CLUSTERIZERS_SHARPE_ORDER = ["kmeans_ret", "fv3sm_w60", "agglo_complete", "pca_load", "sssnetpre",
                             "sponge_w60", "sortino_w60", "agglo_avg", "fv2a_w60",
                             "sharpe_fixed_w60", "gics", "spectral_unsigned"]
"""The 12 clusterizers ordered by mean-of-per-seed trained Sharpe ratio (§5.1)."""


def save(fig, name: str, dpi: int = 200, pad: float | None = None) -> None:
    """Write paper/figures/<name>.pdf and figures/previews/<name>.png (pad = savefig pad_inches)."""
    out = paths.FIGURES / f"{name}.pdf"
    redirected = paths.FIGURES.resolve() != (paths.ROOT / "paper" / "figures").resolve()   # CSA_FIGURES_DIR set
    png = (paths.FIGURES if redirected else paths.ROOT / "figures" / "previews") / f"{name}.png"
    out.parent.mkdir(parents=True, exist_ok=True); png.parent.mkdir(parents=True, exist_ok=True)
    kw = {} if pad is None else {"pad_inches": pad}
    fig.savefig(out, bbox_inches="tight", **kw); fig.savefig(png, dpi=dpi, bbox_inches="tight", **kw)
    print(f"wrote {out if redirected else out.relative_to(paths.ROOT)}")
