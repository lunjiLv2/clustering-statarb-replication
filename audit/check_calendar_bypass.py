"""Find code that reads a book straight off disk instead of through analysis.books.

The CSVs under data/derived/head_logs and data/derived/rule_books carry 6,944 days; the paper is
measured on the 6,913-day common calendar, and analysis/books.py:_read is the only place that
truncation happens. A statistic computed from the CSV directly is therefore NOT the paper's
statistic. The gap is usually small and always silent -- on the five-seed mean Sharpe it reverses
sortino_w60 and agglo_avg (6,944: agglo 2.1676 > sortino 2.1660; 6,913: sortino 2.1495 > agglo
2.1486), the pair that sets fig:bet_corr's row order (CORRECTIONS N83 add. 1).

This flags every read of those directories that does not go through books, so a reviewer or a future
producer cannot reintroduce it without the check going red.

    python audit/check_calendar_bypass.py            # exit 1 if any bypass is found
    python audit/check_calendar_bypass.py --self-test # negative control: plants one, expects it caught
"""
from __future__ import annotations
import argparse, re, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN = ["analysis", "figures/scripts", "audit", "tools"]
# The one legitimate reader, plus the reconstruction tools that MUST see all 6,944 logged days
# because they validate a position file against its own log rather than computing a paper statistic.
ALLOW = {"analysis/books.py", "tools/check_weights.py", "audit/check_calendar_bypass.py"}
# A read that truncates on the same statement is compliant, so do not flag it.
REINDEXED = re.compile(r"\.reindex\(\s*(books\.)?IDX\s*\)")
READ = re.compile(r"(read_csv|read_pickle|open)\s*\(")
BOOKDIR = re.compile(r"HEAD_LOGS|RULE_BOOKS|head_logs|rule_books")


def scan(root: Path) -> list[tuple[str, int, str]]:
    hits = []
    for d in SCAN:
        for p in sorted((root / d).rglob("*.py")):
            rel = p.relative_to(root).as_posix()
            if rel in ALLOW or "__pycache__" in rel:
                continue
            for i, line in enumerate(p.read_text().splitlines(), 1):
                code = line.split("#", 1)[0]
                if READ.search(code) and BOOKDIR.search(code) and not REINDEXED.search(code):
                    hits.append((rel, i, line.strip()))
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        with tempfile.TemporaryDirectory() as td:
            fake = Path(td); (fake / "analysis").mkdir()
            (fake / "analysis" / "books.py").write_text("# the allowed reader\n")
            (fake / "analysis" / "bad.py").write_text(
                'import pandas as pd, paths\n'
                'd = pd.read_csv(paths.HEAD_LOGS / "kmeans_ret_seed1.csv")   # bypass\n')
            (fake / "analysis" / "good.py").write_text(
                'from analysis import books\n'
                'b = books.head_book("kmeans_ret", 1)\n')
            for d in SCAN[1:]:
                (fake / d).mkdir(parents=True, exist_ok=True)
            got = scan(fake)
            ok = len(got) == 1 and got[0][0] == "analysis/bad.py"
            print(f"  self-test: planted 1 bypass, found {len(got)} -> {'PASS' if ok else 'FAIL'}")
            for h in got:
                print(f"    {h[0]}:{h[1]}  {h[2]}")
            return 0 if ok else 1
    hits = scan(ROOT)
    if not hits:
        print("PASS  no book is read outside analysis/books.py"); return 0
    print(f"FAIL  {len(hits)} read(s) bypass analysis/books.py and so sit on the 6,944-day file,")
    print("      not the 6,913-day calendar the paper is measured on:")
    for rel, i, line in hits:
        print(f"  {rel}:{i}\n      {line}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
