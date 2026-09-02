"""Record and verify SHA-256 hashes, row counts and date ranges of every data file in the package.

``python tools/checksums.py write``  writes data/checksums/manifest.csv
``python tools/checksums.py check``  recomputes and reports every mismatch (exit code = number of mismatches)
"""
from __future__ import annotations
import pathlib
import hashlib, sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths

MANIFEST = paths.ROOT / "data" / "checksums" / "manifest.csv"
ROOTS = [paths.RESULTS, paths.RULE_BOOKS, paths.HEAD_LOGS, paths.ROOT / "analysis" / "COMMON_CALENDAR_v3.csv"]


def describe(p: Path) -> dict:
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    rec = dict(path=str(p.relative_to(paths.ROOT)) if p.is_relative_to(paths.ROOT) else str(p), sha256=h, bytes=p.stat().st_size, rows="", first="", last="")
    if p.suffix == ".csv":
        try:
            d = pd.read_csv(p)
            rec["rows"] = len(d)
            if "Date" in d.columns:
                rec["first"], rec["last"] = str(d.Date.min()), str(d.Date.max())
        except Exception as e:                       # a non-tabular csv is still hashed
            rec["rows"] = f"unreadable: {e.__class__.__name__}"
    return rec


def files() -> list[Path]:
    out = []
    for r in ROOTS:
        out += [r] if r.is_file() else sorted(q for q in r.rglob("*") if q.is_file())
    return out


def panel(panel_dir: str) -> int:
    """Compare a compat panel (prices/caps/mask.pkl) with data/panel_checksums.json (sha256, shape, dates)."""
    import hashlib, json
    ref = json.load(open(paths.ROOT / "data" / "panel_checksums.json")); bad = 0
    for n, r in ref.items():
        f = pathlib.Path(panel_dir) / n
        if not f.exists(): print(f"MISSING {n}"); bad += 1; continue
        h = hashlib.sha256(f.read_bytes()).hexdigest(); df = pd.read_pickle(f)
        same = h == r["sha256"]; shape_ok = list(df.shape) == r["shape"]; dates_ok = [str(df.index.min().date()), str(df.index.max().date())] == [r["first"], r["last"]]
        print(f"{'OK ' if same else 'DIFF'} {n}: sha256 {'match' if same else 'differs'}; shape {'ok' if shape_ok else df.shape}; dates {'ok' if dates_ok else (df.index.min().date(), df.index.max().date())}")
        bad += not same
    return bad


def main(cmd: str) -> int:
    if cmd == "write":
        pd.DataFrame([describe(p) for p in files()]).to_csv(MANIFEST, index=False)
        print(f"wrote {MANIFEST} ({len(files())} files)"); return 0
    ref = pd.read_csv(MANIFEST, dtype=str).set_index("path")
    bad = 0
    for p in files():
        rec = describe(p); key = rec["path"]
        if key not in ref.index:
            print(f"NEW      {key}"); bad += 1; continue
        if ref.loc[key, "sha256"] != rec["sha256"]:
            print(f"CHANGED  {key}"); bad += 1
    for key in ref.index:
        if not (paths.ROOT / key).exists():
            print(f"MISSING  {key}"); bad += 1
    print(f"{bad} mismatches"); return bad


if __name__ == "__main__":
    sys.exit(panel(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == "panel" else main(sys.argv[1] if len(sys.argv) > 1 else "check"))
