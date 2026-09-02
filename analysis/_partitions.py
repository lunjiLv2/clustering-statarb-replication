"""Shared loader for the daily partition caches (data/derived/partitions/{name}.pkl, Zenodo).

A cache is ``{date: {"universe": [tickers], "labels": [ints]}}`` with one entry per refit day. The
manuscript's arm label ``sssnet_w60`` (option B, CORRECTIONS N73) is stored under the file name
``sssnetpre``; ``FILE`` maps the CSV arm names to file names where they differ.
"""
from __future__ import annotations
import pickle, sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths

FILE = {"sssnet_w60": "sssnetpre"}


def cache_path(arm: str) -> Path:
    return paths.PARTITIONS / f"{FILE.get(arm, arm)}.pkl"


def load_cache(arm: str) -> dict:
    p = cache_path(arm)
    assert p.is_file(), f"partition cache missing: {p}"
    with open(p, "rb") as f:
        return pickle.load(f)


def in_window(dates, lo=None, hi=None) -> list:
    """Refit dates inside the common calendar window [lo, hi] (defaults: CAL[0], CAL[-1]), sorted."""
    from analysis import books
    lo = books.IDX[0] if lo is None else lo; hi = books.IDX[-1] if hi is None else hi
    return sorted(d for d in dates if lo <= pd.Timestamp(d) <= hi)
