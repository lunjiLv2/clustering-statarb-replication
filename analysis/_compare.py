"""Shared helper for the producers: compare a freshly computed table with the shipped CSV in
analysis/results by key merge and overwrite the shipped file only when they agree to 1e-6."""
from __future__ import annotations
import os, sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths


def compare_and_write(new: pd.DataFrame, name: str, keys: list[str], tol: float = 1e-6) -> float:
    ref = pd.read_csv(paths.RESULTS / name)
    j = new.merge(ref, on=keys, suffixes=("", "_ref"))
    num = [c for c in ref.columns if c not in keys and ref[c].dtype.kind in "fi" and c in new.columns]
    # NaN-safe: a pair is equal when both sides are NaN; a one-sided NaN is a mismatch (inf), never skipped.
    def _coldiff(c):
        a, b = j[c].astype(float).to_numpy(), j[c + "_ref"].astype(float).to_numpy()
        an, bn = np.isnan(a), np.isnan(b)
        if (an ^ bn).any(): return float("inf")
        d = np.abs(a[~an] - b[~bn])
        return float(d.max()) if d.size else 0.0
    d = max((_coldiff(c) for c in num), default=0.0) if num else 0.0
    print(f"{name}: {len(j)}/{len(ref)} rows matched on {keys}; max |diff| {d:.2e}")
    force = os.environ.get("CSA_FORCE_WRITE") == "1"
    if force and paths.RESULTS.resolve() == paths.SHIPPED_RESULTS.resolve():
        raise SystemExit("CSA_FORCE_WRITE is refused for the shipped results directory; set CSA_RESULTS_ROOT")
    if len(j) == len(ref) == len(new) and d < tol:
        new.to_csv(paths.RESULTS / name, index=False); print(f"  -> written")
    elif force:
        new.to_csv(paths.RESULTS / name, index=False); print(f"  -> written (forced, side directory)")
    else:
        print(f"  -> NOT written (mismatch)")
    return d
