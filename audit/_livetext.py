"""Shared helper: the manuscript's LIVE text, comments stripped and line wraps removed.

Both operations matter and both have burned us:
  - a commented-out block still greps as a hit (false positive)
  - a phrase split across a line break ("three seeds per\ncell") does not grep (false negative)  # 3seed-ok: describes the scanner's own false-negative class, not a seed set in use
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths
SEC = str(paths.MANUSCRIPT / "sections")   # CSA_MANUSCRIPT_DIR overrides the shipped paper/ snapshot
MAIN = ["01_introduction","02_literature","03_design","04_hedge_and_signal",
        "05_convergence","06_factor_model","07_conclusion"]
APPX = ["A_supplementary"]

def _strip(line):
    out, esc = [], False
    for ch in line:
        if esc: out.append(ch); esc = False; continue
        if ch == "\\": out.append(ch); esc = True; continue
        if ch == "%": break
        out.append(ch)
    return "".join(out)

def live(files):
    """-> {name: (flat_text, [(lineno, raw_line)])}"""
    d = {}
    for f in files:
        p = os.path.join(SEC, f + ".tex")
        raw = open(p, encoding="utf8", errors="replace").read().split("\n")
        keep = [(i+1, _strip(l)) for i, l in enumerate(raw)]
        keep = [(i, l) for i, l in keep if l.strip()]
        flat = re.sub(r"\s+", " ", " ".join(l for _, l in keep))
        d[f] = (flat, keep)
    return d

def ctx(flat, m, w=110):
    a = max(0, m.start()-w); b = min(len(flat), m.end()+w)
    return ("…" if a else "") + flat[a:b] + ("…" if b < len(flat) else "")
