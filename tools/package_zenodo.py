"""Package the derived data for Zenodo: one tarball per folder plus the checksum manifest.

    python tools/package_zenodo.py --dry-run     # list what would be packaged and the sizes
    python tools/package_zenodo.py --out /path   # write rule_books.tar.gz, head_logs.tar.gz, weights.tar.gz,
                                                 # partitions.tar.gz, results.tar.gz and MANIFEST.csv

The manifest is data/checksums/manifest.csv (tools/checksums.py write); `tools/checksums.py check`
verifies an unpacked copy. Weights: the 42 main runs plus the two peer books (user decision
2026-08-30: variant-run positions stay with the authors); --all-weights includes every file present.
"""
from __future__ import annotations
import argparse, os, sys, tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths

FOLDERS = {"rule_books": paths.RULE_BOOKS, "head_logs": paths.HEAD_LOGS, "weights": paths.WEIGHTS,
           "partitions": paths.PARTITIONS, "results": paths.RESULTS}


def size(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=None); ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--all-weights", action="store_true")
    a = ap.parse_args(); total = 0
    for name, folder in FOLDERS.items():
        files = sorted(f for f in folder.rglob("*") if f.is_file())
        if name == "weights" and not a.all_weights:
            main_names = {f"{arm}_seed{s}.pkl" for arm in paths.ARMS for s in paths.SEEDS} | {"peer_w60_seed42.pkl", "peer_w252_seed42.pkl"}
            files = [f for f in files if f.name in main_names]
        b = sum(f.stat().st_size for f in files); total += b
        print(f"{name:12s} {len(files):5d} files {b / 1e9:7.2f} GB")
        if a.out and not a.dry_run:
            Path(a.out).mkdir(parents=True, exist_ok=True)
            with tarfile.open(Path(a.out) / f"{name}.tar.gz", "w:gz") as t:
                for f in files: t.add(f, arcname=str(f.relative_to(paths.ROOT)))
    print(f"{'total':12s} {'':11s} {total / 1e9:7.2f} GB")
    if a.out and not a.dry_run:
        import shutil; shutil.copy(paths.ROOT / "data" / "checksums" / "manifest.csv", Path(a.out) / "MANIFEST.csv"); print("wrote", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
