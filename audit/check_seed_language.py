"""Find three-seed leftovers in code: hard-coded seed sets and prose that still says "three".

The manuscript moved to five head seeds (CORRECTIONS N83). Producers and figure scripts carry the
old seed set in two forms that no test catches: a literal ``(42, 1, 123)``, and a docstring or
comment that says "three seeds". The first silently produces three-seed output; the second is worse
in a replication package, because it tells a referee the wrong convention while the code does the
right thing -- exactly the state fig_alpha_vol_v3.py's master was found in on 2026-09-01 (output
five-seed, docstring "averaged over the three seeds").

Scans BOTH trees, because they diverge: JFEC_A_Manuscript/_reference holds the figure masters that
produce the shipped PDFs, replication_repo holds the rewritten copies that ship to referees, and
there is no automatic sync between them.

    python audit/check_seed_language.py            # exit 1 if anything is found
    python audit/check_seed_language.py --self-test
"""
from __future__ import annotations
import argparse, re, sys, tempfile
from pathlib import Path

import os
WS = Path(__file__).resolve().parents[1]          # the repository root
# The repository itself, plus any extra trees named in CSA_SEED_SCAN_TREES (":"-separated; the authors
# add their manuscript workspace). paper/ is skipped below: the manuscript is the fingerprint tool's job.
TREES = [WS] + [Path(x) for x in os.environ.get("CSA_SEED_SCAN_TREES", "").split(":") if x]
SKIP = ("__pycache__", "/paper/", "/data/", "_quarantine", "CORRECTIONS.md",
        "check_seed_language.py")   # this file names the pattern it looks for
LITERAL = re.compile(r"\(\s*42\s*,\s*1\s*,\s*123\s*\)|\[\s*42\s*,\s*1\s*,\s*123\s*\]|\{\s*42\s*,\s*1\s*,\s*123\s*\}|42\s*,\s*1\s*,\s*123")
PROSE = re.compile(r"\bthree seeds?\b|\bthree head seeds?\b|\bthree runs?\b|\bthree-seed\b|"
                   r"\bover the three\b|\bthe three per-seed\b|\bthree per-seed\b", re.I)
# An intentional three-seed site carries an inline marker with its reason, e.g.
#     SEEDS = (42, 1, 123)   # 3seed-ok: tab:sssnet is a 3x3 factorial at these seeds by design
# The marker must be followed by a reason; a bare marker is itself flagged, so "silence the checker"
# is never cheaper than writing why.
OK = re.compile(r"3seed-ok:\s*\S")
BARE = re.compile(r"3seed-ok(?!:\s*\S)")
# Sentences that are ABOUT the three-seed past are legitimate; they name it as history.
HISTORY = re.compile(r"was |were |had |previously|before|old |former|used to|"
                     r"at three seeds|three-seed backup|history|N8[0-9]|CORRECTIONS|"
                     r"reproduc|calibrat|pinned|verified|check|not \d", re.I)


def _rel(p: Path) -> str:
    try: return str(p.relative_to(WS))
    except ValueError: return str(p)          # self-test runs outside the workspace


def scan(trees) -> list[tuple[str, int, str, str]]:
    hits = []
    for t in trees:
        if not t.exists(): continue
        for p in sorted(t.rglob("*.py")):
            rel = str(p)
            if any(s in rel for s in SKIP): continue
            lines = p.read_text(errors="replace").splitlines()
            # A marker in the first ten lines exempts the WHOLE file -- for a dead or by-design
            # script, one reason at the top beats one per occurrence.
            if any(OK.search(l) and l.lstrip().startswith("#") for l in lines[:10]):
                continue
            for i, line in enumerate(lines, 1):
                # A marker covers the blank-line-delimited BLOCK it sits in, so one reason can cover
                # a multi-line docstring or a wrapped statement -- but not an unrelated neighbour.
                lo = i - 1
                while lo > 0 and lines[lo - 1].strip(): lo -= 1
                hi = i
                while hi < len(lines) and lines[hi].strip(): hi += 1
                near = "\n".join(lines[lo:hi])
                lit, pro = LITERAL.search(line), PROSE.search(line)
                if not (lit or pro): continue
                if BARE.search(line):
                    hits.append((_rel(p), i, "bare-marker", line.strip())); continue
                if OK.search(near): continue               # intentional, with a written reason
                if HISTORY.search(line): continue          # explicitly about the past
                hits.append((_rel(p), i, "literal" if lit else "prose", line.strip()))
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        with tempfile.TemporaryDirectory() as td:
            f = Path(td); (f / "x.py").write_text(
                'SEEDS = (42, 1, 123)\n'
                '"""averaged over the three seeds"""\n'
                '# at three seeds this reproduced 0.828, which is history and must not be flagged\n'
                '\n'
                'A = (42, 1, 123)   # 3seed-ok: the factorial is defined at these seeds\n'
                '\n'
                'B = (42, 1, 123)   # 3seed-ok\n')
            got = scan([f])
            kinds = sorted(h[2] for h in got)
            ok = kinds == ["bare-marker", "literal", "prose"]
            print(f"  self-test: 2 live + 1 historical + 1 marked + 1 bare marker; "
                  f"expect literal/prose/bare-marker, got {kinds} -> {'PASS' if ok else 'FAIL'}")
            for h in got: print(f"    {h[2]:8s} {h[3]}")
            return 0 if ok else 1
    hits = scan(TREES)
    if not hits:
        print("PASS  no live three-seed literal or prose in either tree"); return 0
    print(f"FAIL  {len(hits)} three-seed leftover(s):")
    for rel, i, kind, line in hits:
        print(f"  [{kind}] {rel}:{i}\n      {line[:150]}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
