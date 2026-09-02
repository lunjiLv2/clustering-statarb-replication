# Data licence (draft — confirm before the Zenodo upload)

The derived data record (`derived/rule_books`, `derived/head_logs`, `derived/weights`,
`derived/partitions`, `results`) is released under **Creative Commons Attribution 4.0
International (CC BY 4.0)**. It contains daily portfolio payoffs, executed weights and daily
group labels produced by the authors' code; it contains no CRSP prices, returns, capitalisations
or identifiers beyond the ticker symbols used as labels, and no GICS classification data.

The Ken French factor files under `factors/` are fetched by `fetch_ken_french.py` from the
Kenneth R. French data library and are not redistributed here. CRSP data (via WRDS) and the GICS
snapshot are licensed and not distributed; the shipped `gics` partition cache stands in for the
latter.
