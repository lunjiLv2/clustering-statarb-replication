"""Copy trained-head runs from the campaign's run tree into the repository's data/derived.

For each arm and seed it locates ``<runs_v3>/family_{arm}_seed{seed}/``, checks that the run is
finished and usable — one head log, full coverage of the common calendar, and the pre-registered
validity gate (rolling-250 mean |NE| <= 0.30) — and only then copies the log to
data/derived/head_logs/{arm}_seed{seed}.csv and the positions to data/derived/weights/{arm}_seed{seed}.pkl.
A run that fails any check is reported and skipped, never copied.

    python tools/ingest_head_runs.py --seeds 2 3               # ingest the new seeds
    python tools/ingest_head_runs.py --seeds 42 1 123 --dry-run  # verify against what is already shipped
"""
from __future__ import annotations
import argparse, filecmp, glob, shutil, sys
import os
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books

CAMPAIGN = Path(os.environ.get("CSA_CAMPAIGN_ROOT", "/nonexistent")) / "sssnet_seed_sweep"   # authors only: set CSA_CAMPAIGN_ROOT to the campaign tree
RUNS = CAMPAIGN / "runs_v3"   # overridden by --root; seeds 7/8 of the canonical set live in runs_v3_2g


def one(arm: str, seed: int, dry: bool, root: Path = None, weights: bool = True) -> str:
    d = (root or RUNS) / f"family_{arm}_seed{seed}"
    if not d.is_dir(): return "no run directory"
    logs = [p for p in sorted(glob.glob(str(d / "log_sponge_l1norm_*.csv"))) if "_cancel" not in p]
    if not logs: return "still running (no head log)"
    df = pd.read_csv(logs[-1], parse_dates=["Date"]).set_index("Date")
    missing = books.IDX.difference(df.index)
    if len(missing): return f"log misses {len(missing)} calendar days"
    sys.path.insert(0, str(paths.ROOT / "head")); import ne_gate
    if not ne_gate.gate_ok(logs[-1]): return "FAILS the validity gate"
    dst = paths.HEAD_LOGS / f"{arm}_seed{seed}.csv"
    if dry:
        return "identical to the shipped log" if dst.exists() and filecmp.cmp(logs[-1], dst, shallow=False) else \
               ("differs from the shipped log" if dst.exists() else "would be added")
    shutil.copyfile(logs[-1], dst)
    w = d / "weights.pkl"
    if weights and w.is_file(): shutil.copyfile(w, paths.WEIGHTS / f"{arm}_seed{seed}.pkl")
    return f"ingested ({len(df)} rows{', with positions' if (weights and w.is_file()) else ''})"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", nargs="+", type=int, required=True)
    ap.add_argument("--arms", nargs="*", default=paths.ARMS)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--root", default=None, help="run root under sssnet_seed_sweep (default runs_v3)")
    ap.add_argument("--no-weights", action="store_true", help="copy the daily log only; the positions stay in the campaign tree")
    a = ap.parse_args(); bad = 0
    for seed in a.seeds:
        for arm in a.arms:
            r = one(arm, seed, a.dry_run, CAMPAIGN / a.root if a.root else None, not a.no_weights)
            bad += ("gate" in r or "misses" in r or "differs" in r)
            print(f"{'OK ' if 'ingest' in r or 'identical' in r else '.. '} {arm:18s} seed {seed:<4} {r}")
    print("all runs usable" if not bad else f"{bad} run(s) need attention")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
