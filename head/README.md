# Trading head (layer L3, GPU)

`pipeline_work.py` is the executed head pipeline, byte-for-byte the copy that produced every trained
book in the paper (md5 0b87d7baeb2b…; the run manifests record sha256 of the original and patched
source). It is a LongConv sequence head trained on the partition-structured signal (§3.5); we do
not edit it, so that a reader can diff it against the run manifests on Zenodo. `ne_gate.py` is the
pre-registered training-validity gate (rolling-250 mean |NE| ≤ 0.30) applied before any book is used.

The pipeline is configured through environment variables, not arguments. `run_head.py` (wrapper)
sets them from `paths.py` and the arm/seed you ask for:

| variable | meaning | value used in the paper |
|---|---|---|
| `A2_CLEAN_DIR` | compat panel (`prices.pkl`, `caps.pkl`, `mask.pkl`) | `$CSA_PANEL_ROOT` |
| `REFINED_FILE_OVERRIDE` | daily partition label cache | `data/derived/partitions/{arm}.pkl` |
| `SWEEP_SEED` | torch / numpy seed | 42, 1, 123 |
| `SPONGE_K` | number of clusters | 30 (K=1 for the `k1` arm) |
| `WEIGHT_DUMP_PATH` | where the executed positions are written | `data/derived/weights/{arm}_seed{seed}.pkl` |

Each run writes `log_sponge_l1norm_<timestamp>.csv` (daily P&L, gross leverage; the head book) and a
diagnostics CSV. One run takes ~1.5 h (5,500 s wall) on an A100; results reproduce to ±0.07 Sharpe across GPUs
(the tolerance stated in the README), not bit-exactly, because of non-deterministic CUDA kernels.
