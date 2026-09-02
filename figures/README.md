# Figures

`scripts/fig_*_v3.py` redraw every figure of the paper from `analysis/results/` and `data/derived/`
through the shared loader (`analysis/books.py`) and the shared style (`scripts/style.py`: rcParams,
display names, the Sharpe-ordered clusterizer list, and `save()` which writes `paper/figures/<name>.pdf`
and a PNG preview into `previews/`). Two scripts are heavy: `fig_select_vs_ew_v3.py` (bootstrap) and
`fig_bet_corr_v3.py` (reads the 70 main position files); `slurm/figures_heavy.sh` runs them on a node.
Ten of the 11 PDFs are the manuscript's figures; `fig_ff_curve.pdf` was superseded on 2026-08-31 by panel (b) of fig:lens_curve and is kept only because its script still reproduces it. `audit/check_figures_text.py` regenerates every script into a temporary directory and asserts its PDF text layer (labels, ticks, printed numbers) equals the shipped PDF's; `audit/check_pseed_flip_literals.py` additionally asserts the shipped fig:pseed_flip is newer than every input it reads.

    make figures            # everything except the two heavy ones takes ~1 min
    python figures/scripts/fig_dose_v3.py
