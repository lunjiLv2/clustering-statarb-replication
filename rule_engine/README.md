# Rule engine (layer L2)

`run_naive_routeA.py` turns a daily partition (a label cache from `data/derived/partitions/`) into
the rule-based book of §3.4: within each cluster the rule ranks the 5-day residual-return signal,
goes long the losers and short the winners, and normalises the book to unit gross leverage
(clusters of size one are not traded). The kernel is `p1_inversion/p1_lib.naive_stream`, unchanged
from the audited producer; `parts_v3.py` is the explicit partition registry.

Reproduce the 27 rule books of the manuscript (`data/derived/rule_books/{arm}.csv`):

    export CSA_PANEL_ROOT=/path/to/compat_panel     # prices.pkl, caps.pkl, mask.pkl (CRSP-derived; not shipped)
    python rule_engine/run_naive_routeA.py --parts v3 --basis raw \
        --date-start 1997-05-23 --date-end 2024-12-30 \
        --dump-daily data/derived/rule_books --out analysis/results/naive_routeA_v3_raw.csv

The 30-day signal-window variant (§4.4) uses `--sig-w 30` and writes `{arm}_sigw30.csv`.
