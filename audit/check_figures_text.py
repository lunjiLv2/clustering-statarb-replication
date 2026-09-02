"""Every figure script must reproduce the shipped figure: regenerate each fig_*_v3.py into a temporary directory
(CSA_FIGURES_DIR) and compare the PDF text layer -- every label, tick and printed number -- with paper/figures/.

Why: the repository's figure scripts are ports of the authors' manuscript masters, and two of them drifted
(fig_window_twin drew three arms where the shipped figure has five; fig_alpha_vol had a hard-coded ylim that
dropped both controls) while every other gate stayed green, because no gate compared script output with the
exhibit (CORRECTIONS N94). Token multisets, not bytes: matplotlib PDFs are not byte-reproducible across runs.
Needs data/derived (layer L1) and pypdf. fig_bet_corr reads the 70 position files (several GB); it runs only
with --all.
Run: python audit/check_figures_text.py [--all] [--only fig_dose ...]
"""
import argparse, collections, os, re, subprocess, sys, tempfile, pathlib
_ROOT = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(_ROOT))
import paths
from pypdf import PdfReader

HEAVY = {"fig_bet_corr"}
SUPERSEDED: dict[str, str] = {}   # scripts kept after their figure left the manuscript, with the reason
TOK = re.compile(r"[A-Za-z]+|[-+]?\d+\.?\d*")
def tokens(pdf: pathlib.Path) -> collections.Counter:
    return collections.Counter(TOK.findall(" ".join((pg.extract_text() or "") for pg in PdfReader(str(pdf)).pages)))

def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--all", action="store_true"); ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    scripts = sorted(p for p in (_ROOT / "figures" / "scripts").glob("fig_*_v3.py"))
    if a.only: scripts = [p for p in scripts if p.stem[:-3] in a.only]
    shipped = paths.ROOT / "paper" / "figures"; fails = []; n = 0
    with tempfile.TemporaryDirectory(prefix="csa_figs_") as tmp:
        env = dict(os.environ, CSA_FIGURES_DIR=tmp)
        for s in scripts:
            name = s.stem[:-3]
            if name in HEAVY and not a.all:
                print(f"  SKIP  {name}  [reads the position files; run with --all]"); continue
            r = subprocess.run([sys.executable, str(s)], cwd=_ROOT, env=env, capture_output=True, text=True)
            if r.returncode != 0:
                print(f"  FAIL  {name}  [script exited {r.returncode}: {r.stderr.strip().splitlines()[-1][:120] if r.stderr.strip() else ''}]"); fails.append(name); continue
            out, ref = pathlib.Path(tmp) / f"{name}.pdf", shipped / f"{name}.pdf"
            if not ref.is_file():
                print(f"  FAIL  {name}  [no shipped PDF at {ref}]"); fails.append(name); continue
            t_out, t_ref = tokens(out), tokens(ref); d_out, d_ref = t_out - t_ref, t_ref - t_out; n += 1
            if d_out or d_ref:
                print(f"  FAIL  {name}  [text layer differs; only in regenerated: {dict(d_out)}; only in shipped: {dict(d_ref)}]"); fails.append(name)
            else:
                print(f"  PASS  {name}  ({sum(t_ref.values())} tokens text-identical to the shipped PDF{'; ' + SUPERSEDED[name] if name in SUPERSEDED else ''})")
    print(f"\n{len(fails)} FAIL" + (": " + ", ".join(fails) if fails else f"  -- {n} figure scripts reproduce their shipped PDFs ({n - sum(s in SUPERSEDED for s in [p.stem[:-3] for p in scripts])} manuscript figures + {sum(s in SUPERSEDED for s in [p.stem[:-3] for p in scripts])} superseded)"))
    return len(fails)

if __name__ == "__main__":
    raise SystemExit(main())
