# Daily partitions (layer L2)

`gen_daily_partitions_v3.py` builds one daily label cache (`{date: {universe, labels}}`, pickle
protocol 4) from the compat panel for every clusterizer that runs on the CPU. The caches shipped on
Zenodo live in `data/derived/partitions/{arm}.pkl` (62 files incl. the eight tier-2 partition-seed twins, 2.1 GB; `MANIFEST.json` maps each arm
to its producer path and size). Set `CSA_PANEL_ROOT` (prices/caps/mask.pkl) and, for the `gics` arm,
`CSA_GICS_CSV` (the S&P 1500 sector snapshot; licensed, see `data/README.md`).

Commands used for the paper (K = 30 unless stated; `--corr-window` is the correlation window in
trading days; the seed only matters for the stochastic clusterizers):

    # main arms (one array task each): pca_load agglo_avg agglo_complete spectral_unsigned sponge random gics
    python partitions/gen_daily_partitions_v3.py --paradigm <arm> --panel $CSA_PANEL_ROOT \
        --out data/derived/partitions/<arm>.pkl
    # k-means on returns and the window-60 variants
    python partitions/gen_daily_partitions_v3.py --paradigm kmeans_ret --panel $CSA_PANEL_ROOT --k 30 --corr-window 60 \
        --out data/derived/partitions/kmeans_ret.pkl
    # partition-seed twins (A.12): --seed 1 / --seed 123, output <arm>_ps<seed>.pkl
    # window sweep (§4.4): --corr-window 21 / 120 / 252, output <arm>_w<window>.pkl
    # K sweep (§4.4): --k 10 / 50, output <arm>_k<K>.pkl
    # singleton policy variants (A.2): --paradigm kmeans_ret_minsize / kmeans_ret_merged (run --verify-minsize first)
    # no clustering: --paradigm k1

The GPU-side partitions (the trading-driven clusterizers `fv2a_w60`, `fv3sm_w60`, `sortino_w60`,
`sharpe_fixed_w60` and the SSSNET partition `sssnetpre*`) are produced by their own trainers under
`head/` and are shipped as caches only; their generators are listed in `audit/producers.yaml`.
