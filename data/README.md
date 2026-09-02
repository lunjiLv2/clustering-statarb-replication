# Data

The derived data live on Zenodo: <https://doi.org/10.5281/zenodo.22241254> (5 tarballs + `MANIFEST.csv` + `SHA256SUMS`, 2.9 GB compressed). Unpack the tarballs into `derived/` (or point `CSA_DATA_ROOT` at the unpacked tree) and run `python tools/checksums.py check`.

| folder | content | source | shipped how |
|---|---|---|---|
| `factors/` | Ken French daily FF5, momentum and short-term reversal factors | Kenneth R. French data library | fetched by `fetch_ken_french.py` (not redistributed) |
| `derived/rule_books/` | 116 rule-based daily books: 54 main arms, 14 `_sigw30` (30-day signal window), 8 + 40 partition-seed twins (`{arm}_ps{1..5}`, §5.2) | `rule_engine/` on the compat panel | Zenodo tarball (CC BY 4.0, pending) |
| `derived/head_logs/` | 400 trained-head daily logs (the 70 main runs, the partition-seed runs at head seed 42, window and K variants, extended seeds, three same-seed replicates for A.4) (`{arm}[variant]_seed{s}.csv`) and the two peer books | `head/` on the compat panel | Zenodo tarball |
| `derived/weights/` | executed positions of the trained runs (142 files: the 70 main runs, variants, and the two peer books `peer_w{60,252}_seed42.pkl`; 4.6 GB) | `head/` (WEIGHT_DUMP_PATH) | Zenodo tarball |
| `derived/partitions/` | 102 daily label caches incl. the partition-seed twins `{arm}_ps{1..5}` (`MANIFEST.json` lists producers and sizes; 4.3 GB) | `partitions/` and the GPU clusterizers | Zenodo tarball |
| compat panel (not in the repo) | `prices.pkl`, `caps.pkl`, `mask.pkl`: CRSP daily prices, market caps and the universe mask, 1996–2024 | CRSP via WRDS (licensed) | `build_panel.py <crsp_dir> <out_dir>` (CRSP daily files → returns/caps/mask.pkl; `DATA_CLEANING_NOTES.md` describes the rules), `panel_acceptance.py --panel <out_dir>` (the acceptance gates), then `build_compat_panel.py` (→ prices/caps/mask for the engines); `panel_checksums.json` records sha256/shape/dates of the panel used for the paper |
| GICS snapshot (not in the repo) | S&P 1500 sector membership used by the `gics` arm | licensed | the `gics` partition cache is shipped instead |

Layers L0 and L1 of the README need only this folder's shipped files; L2 and L3 need the compat
panel, i.e. a CRSP subscription. Licences for the derived data are to be confirmed by the authors
before release (see the top-level LICENSE files).

Panel build chain used for the paper (each step is argument/environment driven; no path is hard-coded):

    python data/build_panel.py <crsp_daily_dir> Cleaned_Data_v3 --years 1990-2024        # returns.pkl, caps.pkl, mask.pkl, permno_map.csv
    python data/panel_acceptance.py --panel Cleaned_Data_v3 [--raw <crsp_daily_dir>]     # acceptance gates (ACCEPTANCE_GATE1.txt)
    RETURNS_V2=Cleaned_Data_v3/returns.pkl LEGACY_DIR=Cleaned_Data_v3 OUT_DIR=Cleaned_Data_v3_compat \
        python data/build_compat_panel.py                                                # prices.pkl (cumulated), caps.pkl, mask.pkl on one grid
    python tools/checksums.py panel Cleaned_Data_v3_compat                               # compare with data/panel_checksums.json

The compat panel of the paper: 8,803 days x 6,899 names, 1990-01-17 to 2024-12-30 (see `panel_checksums.json`).
