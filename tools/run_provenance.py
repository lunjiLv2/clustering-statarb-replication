"""Provenance table for every trained run: host, GPU slice class, seed, batch and validity.

The cluster advertises both MIG profiles as ``gpu:a100.20gb``, so the GRES name cannot tell them
apart: sg050 hands out 2g.20gb slices (28 SMs, the hardware that produced the published fleet) and
sg048/sg049 hand out 1g.20gb (14 SMs). This tool reads each run's MANIFEST for the host and start
time and labels the run accordingly, so that no table can silently mix hardware classes.

    python tools/run_provenance.py                 # every run under the campaign roots
    python tools/run_provenance.py --seeds 4 5 6   # restrict to some seeds
"""
from __future__ import annotations
import argparse, glob, re, sys
import os
from pathlib import Path
import pandas as pd

CAMPAIGN = Path(os.environ.get("CSA_CAMPAIGN_ROOT", "/nonexistent")) / "sssnet_seed_sweep"   # authors only: set CSA_CAMPAIGN_ROOT to the campaign tree
ROOTS = {"runs_v3": "canonical", "runs_v3_2g": "canonical (2g rerun)",
         "runs_v3_seedctrl": "control (same-seed rerun)", "runs_v3_seedhw": "hardware control"}
CLASS = {"sg050": "2g.20gb (28 SM)", "sg048": "1g.20gb (14 SM)", "sg049": "1g.20gb (14 SM)"}


def rows(seeds: list[int] | None) -> pd.DataFrame:
    out = []
    for root, kind in ROOTS.items():
        for d in sorted((CAMPAIGN / root).glob("*_seed*")):
            m = d / "MANIFEST.txt"
            if not m.is_file(): continue
            txt = m.read_text(errors="ignore")
            host = (re.search(r"^host\s*:\s*(\S+)", txt, re.M) or [None, ""])[1]
            start = (re.search(r"^started\s*:\s*(\S+)", txt, re.M) or [None, ""])[1]
            seed = int(re.search(r"_seed(\d+)$", d.name).group(1))
            if seeds and seed not in seeds: continue
            logs = [p for p in glob.glob(str(d / "log_sponge_l1norm_*.csv")) if "_cancel" not in p]
            out.append(dict(root=root, kind=kind, arm=re.sub(r"^family_|_seed\d+$", "", d.name), seed=seed,
                            host=host, gpu_class=CLASS.get(host, "unknown"), started=start[:16],
                            finished=bool(logs)))
    return pd.DataFrame(out)


def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--seeds", nargs="*", type=int); a = ap.parse_args()
    D = rows(a.seeds)
    if D.empty: print("no runs found"); return
    print(D.groupby(["kind", "gpu_class"]).agg(runs=("arm", "size"), finished=("finished", "sum")).to_string())
    D.sort_values(["kind", "seed", "arm"]).to_csv(CAMPAIGN.parent.parent / "replication_repo" / "analysis" / "results" / "run_provenance.csv", index=False)
    print(f"\nwrote analysis/results/run_provenance.csv ({len(D)} runs)")


if __name__ == "__main__":
    main()
