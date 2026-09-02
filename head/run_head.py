"""Launch one trading-head run of the paper inside the replication layout (layer L3, GPU).

The executed pipeline (head/pipeline_work.py, unmodified) is configured through environment
variables; this wrapper sets them from paths.py for one arm x seed and runs the pipeline in a fresh
run directory, then copies the head book (log_sponge_l1norm_*.csv), the diagnostics and the executed
positions into data/derived/ under the repository's naming so that analysis/ picks them up.

    CSA_PANEL_ROOT=/path/to/compat_panel python head/run_head.py --arm kmeans_ret --seed 42

Runtime ~1.5 h on one A100 (5,500 s wall in the paper's runs). Books reproduce to ±0.07 Sharpe
across GPUs (non-deterministic CUDA kernels), not bit-exactly; the shipped logs on Zenodo are the
executed ones.
"""
from __future__ import annotations
import argparse, glob, os, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import paths


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, help="partition name in data/derived/partitions/MANIFEST.json")
    ap.add_argument("--seed", type=int, default=42, choices=paths.SEEDS)
    ap.add_argument("--k", type=int, default=None, help="number of clusters (default 30; 1 for the k1 arm)")
    ap.add_argument("--runs-root", default=str(paths.ROOT / "runs"), help="where run directories are created")
    a = ap.parse_args()
    assert paths.PANEL is not None, "set CSA_PANEL_ROOT to the compat panel directory"
    part = paths.PARTITIONS / f"{a.arm}.pkl"
    assert part.is_file(), f"partition cache missing: {part}"
    k = a.k if a.k is not None else (1 if a.arm == "k1" else 30)
    run = Path(a.runs_root) / f"{a.arm}_seed{a.seed}_{time.strftime('%Y%m%d_%H%M%S')}"
    out = run / "out"; out.mkdir(parents=True)
    weights = paths.WEIGHTS / f"{a.arm}_seed{a.seed}.pkl"
    env = dict(os.environ, A2_CLEAN_DIR=str(paths.PANEL), REFINED_FILE_OVERRIDE=str(part),
               SWEEP_SEED=str(a.seed), SSSNET_SEED=str(a.seed), SPONGE_K=str(k),
               WEIGHT_DUMP_PATH=str(weights), PYTHONPATH=str(HERE))
    with open(run / "MANIFEST.txt", "w") as f:
        f.write(f"arm {a.arm} seed {a.seed} K {k}\npartition {part}\npanel {paths.PANEL}\n"
                f"env A2_CLEAN_DIR REFINED_FILE_OVERRIDE SWEEP_SEED SPONGE_K WEIGHT_DUMP_PATH as above\n"
                f"pipeline {HERE / 'pipeline_work.py'}\nstarted {time.strftime('%Y-%m-%dT%H:%M:%S')}\n")
    rc = subprocess.call([sys.executable, "-u", str(HERE / "pipeline_work.py")], cwd=out, env=env)
    if rc != 0:
        print(f"pipeline exited with {rc}; see {out}", file=sys.stderr); return rc
    logs = sorted(glob.glob(str(out / "log_sponge_l1norm_*.csv")))
    assert len(logs) == 1, f"expected one head log, found {logs}"
    shutil.copyfile(logs[0], paths.HEAD_LOGS / f"{a.arm}_seed{a.seed}.csv")
    for d in glob.glob(str(out / "diag_*.csv")):
        shutil.copyfile(d, run / Path(d).name)
    print(f"head book -> {paths.HEAD_LOGS / f'{a.arm}_seed{a.seed}.csv'}; positions -> {weights}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
