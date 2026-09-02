"""fig:pseed_flip source gate (rewritten 2026-09-01, N84 add. 1).

Until N84 this file parsed hard-coded Sharpe literals out of a manuscript-side reference script and recomputed them
from the books. That reference script is retired and the shipped figure script computes every value from the books,
so the old check passed against a file the paper no longer uses. What can still go wrong now: the figure script
reading a different draw set or head seed than the text claims (five partition seeds {1..5}, head pinned at 42), the
manuscript carrying a PDF that is not the one the script wrote, or the PDF predating one of its inputs. This gate
checks those three; the printed numbers themselves are gated by check_pseed_5ps.py (books-based).
Run: python audit/check_pseed_flip_literals.py"""
import re, sys, pathlib, filecmp
_ROOT = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(_ROOT))
import paths
SRC = _ROOT / "figures" / "scripts" / "fig_pseed_flip_v3.py"; PDF = paths.FIGURES / "fig_pseed_flip.pdf"
OUP = paths.MANUSCRIPT / "figures" / "fig_pseed_flip.pdf"   # CSA_MANUSCRIPT_DIR overrides the shipped paper/ snapshot
fails = []
def chk(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}  {detail}"); fails.append(name) if not ok else None
s = SRC.read_text()
chk("script draws PS = (1, 2, 3, 4, 5) and TWINS derive from PS", re.search(r"^PS\s*=\s*\(1,\s*2,\s*3,\s*4,\s*5\)", s, re.M) is not None and 'TWINS = tuple(f"_ps{p}" for p in PS)' in s)
chk("script pins the head seed at 42 for every trained book", len(re.findall(r"books\.head_book\(a,\s*42,\s*t\)", s)) == 1 and "head_book(a, s" not in s)
chk("script carries no hard-coded Sharpe literals and no reference to the retired manuscript master", not re.search(r"\b[12]\.\d{4}\b", s) and "_reference" not in s and "_ps123" not in s)
chk("manuscript PDF is byte-identical to the repository PDF", OUP.is_file() and PDF.is_file() and filecmp.cmp(OUP, PDF, shallow=False))
ARMS = ["kmeans_ret", "pca_load", "sssnetpre", "fv3sm_w60", "sharpe_fixed_w60", "sponge_w60", "sortino_w60", "fv2a_w60", "spectral_unsigned", "random"]
inputs = [paths.RULE_BOOKS / f"{a}_ps{p}.csv" for a in ARMS for p in range(1, 6)] + [paths.HEAD_LOGS / f"{a}_ps{p}_seed42.csv" for a in ARMS for p in range(1, 6)] + [SRC]
missing = [p.name for p in inputs if not p.is_file()]
chk("all 100 input books + script present", not missing, f"missing {missing[:5]}" if missing else "")
if not missing:
    newest = max(inputs, key=lambda p: p.stat().st_mtime)
    chk("PDF newer than every input book and the script", PDF.stat().st_mtime >= newest.stat().st_mtime, f"newest input {newest.name}")
print(f"\n{len(fails)} FAIL" + (": " + ", ".join(fails) if fails else "  -- figure source gate passes")); sys.exit(len(fails))
