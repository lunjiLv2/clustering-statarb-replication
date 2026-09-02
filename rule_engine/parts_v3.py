"""Partition registry for the rule engine (explicit list, no globbing).

Each entry maps an arm name to a daily label cache under data/derived/partitions/ (Zenodo), named
``{arm}.pkl``; data/derived/partitions/MANIFEST.json records the original producer path and size.
Entries whose file is absent are dropped with a loud warning; the engine asserts the count it
expects. The house rule behind the explicit list: glob-based discovery silently drops arms.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths

MANIFEST = paths.PARTITIONS / "MANIFEST.json"
EXPECTED_MIN = 51


def registry() -> dict[str, str]:
    """Return {arm: path} for every cache listed in the manifest and present on disk."""
    names = json.load(open(MANIFEST)) if MANIFEST.exists() else {}
    present, missing = {}, []
    for arm in sorted(names):
        p = paths.PARTITIONS / names[arm]["file"]
        (present.__setitem__(arm, str(p)) if p.is_file() else missing.append(arm))
    if missing:
        print(f"[parts_v3][WARN] {len(missing)} partition caches missing on disk: {missing}", file=sys.stderr)
    assert len(present) >= EXPECTED_MIN, f"parts_v3: only {len(present)} caches present (< {EXPECTED_MIN})"
    return present


PARTS_V3 = registry()
