"""Single place that knows where things are.

Every script in this repository imports ROOT / DATA / RESULTS from here instead of hard-coding a
path. The repository root is the directory containing this file; large derived data (daily books,
positions, partition caches) lives under DATA, which can be redirected to a Zenodo download via the
environment variable ``CSA_DATA_ROOT``; the CRSP panel, which is not distributed, is pointed to by
``CSA_PANEL_ROOT`` and is only needed for layers L2 and L3.
"""
from __future__ import annotations
import os
from pathlib import Path

ROOT: Path = Path(__file__).resolve().parent
DATA: Path = Path(os.environ.get("CSA_DATA_ROOT", ROOT / "data" / "derived"))
PANEL: Path | None = Path(os.environ["CSA_PANEL_ROOT"]) if "CSA_PANEL_ROOT" in os.environ else None
SHIPPED_RESULTS: Path = ROOT / "analysis" / "results"   # the CSVs the tables and figures are drawn from
RESULTS: Path = Path(os.environ.get("CSA_RESULTS_ROOT", SHIPPED_RESULTS))
"""Set CSA_RESULTS_ROOT to regenerate into a side directory (e.g. at a different seed set) without
touching the shipped CSVs; _compare.compare_and_write refuses to force-write into SHIPPED_RESULTS."""
FIGURES: Path = Path(os.environ.get("CSA_FIGURES_DIR", ROOT / "paper" / "figures"))
"""Where figure scripts write their PDFs; CSA_FIGURES_DIR redirects them (audit/check_figures_text.py uses a temp dir)."""
FACTORS: Path = ROOT / "data" / "factors"          # Ken French files fetched by data/fetch_ken_french.py
MANUSCRIPT: Path = Path(os.environ.get("CSA_MANUSCRIPT_DIR", ROOT / "paper"))
"""LaTeX sources the audit checkers read (sections/, figures/). The repository ships a snapshot under
paper/; the authors point CSA_MANUSCRIPT_DIR at the working manuscript while it is being written."""
CAMPAIGN: Path | None = Path(os.environ["CSA_CAMPAIGN_ROOT"]) if "CSA_CAMPAIGN_ROOT" in os.environ else None
"""The authors' training-campaign tree (run directories, MANIFESTs, slurm logs). Only tools/ingest_head_runs.py,
tools/run_provenance.py, analysis/seed_delivery.py and analysis/common_calendar.py._build need it; everything
a reader runs works from DATA alone."""

RULE_BOOKS: Path = DATA / "rule_books"             # naive_routeA/daily_v3/{arm}.csv in the workspace
HEAD_LOGS: Path = DATA / "head_logs"               # runs_v3/family_{arm}_seed{s}/log_*.csv
WEIGHTS: Path = DATA / "weights"                   # runs_v3/family_{arm}_seed{s}/weights.pkl (Zenodo)
PARTITIONS: Path = DATA / "partitions"             # daily label caches (Zenodo)

ARMS = ["kmeans_ret", "pca_load", "agglo_avg", "agglo_complete", "spectral_unsigned", "gics",
        "sponge_w60", "fv2a_w60", "fv3sm_w60", "sharpe_fixed_w60", "sortino_w60", "sssnetpre",
        "k1", "random"]
"""The 12 clusterizers followed by the two controls, in the manuscript's canonical order."""
SEEDS = (tuple(int(x) for x in os.environ["CSA_SEEDS"].replace(",", " ").split())
         if os.environ.get("CSA_SEEDS") else (1, 2, 3, 4, 5))
"""Training seeds of the neural trading head; every head-layer statistic averages over these."""
