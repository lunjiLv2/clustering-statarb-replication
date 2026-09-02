"""Removal share on the traded universe with the members of size-one groups excluded (A.9 footnote:
k-means 0.216 against 0.264 with them; the trading stage does not trade singletons).

Same engine as ``vshare_v3.py`` (``--exclude-singletons``). The shipped file holds the k-means row
only, the one the footnote quotes; pass ``--arms`` for other arms (the comparison with the shipped
file then covers the k-means row alone and nothing is overwritten).

Run: ``CSA_PANEL_ROOT=/path/to/compat_panel python analysis/vshare_v3_nosingleton.py``
"""
from __future__ import annotations
import argparse, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis import vshare_v3


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="*", default=["kmeans_ret"])
    ap.add_argument("--nproc", type=int, default=1)
    a = ap.parse_args()
    vshare_v3.run(a.arms, True, a.nproc, "vshare_v3_nosingleton_cal6913.csv")


if __name__ == "__main__":
    main()
