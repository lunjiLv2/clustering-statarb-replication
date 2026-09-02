#!/usr/bin/env python
"""panel_acceptance.py — the gate a data delivery must pass BEFORE any GPU hour is spent.

WHY. The 2026-08 campaign ran two months on /home/lunjizhu/data whose year directories were a
MIX of two dataset vintages: 2000-2021 from the old un-enlarged export (18 columns, NYSE-heavy,
no AAPL/MSFT/NVDA), 1990-1999 + 2022-2024 from the enlarged export (39 columns, +NASDAQ/ARCA
+ETFs). Every existing validation passed, because every check compared the panel AGAINST ITSELF
(pct_change == returns.shift(1) holds when the hole is on both sides). This script checks the
data against THE WORLD: known tickers, known splits, known delistings, and its own continuity.

USAGE
    # raw csv.gz layer (run FIRST, on the new download, before building anything):
    python panel_acceptance.py --raw /path/to/new_data_dir

    # built panel layer (after recleaning/build_cleaned_v2.py):
    python panel_acceptance.py --panel /path/to/Cleaned_Data_vX [--old-panel /home/lunjizhu/Cleaned_Data_v2_full]

Exit 0 = every check passed. Exit 1 = at least one FAIL (do not build / do not run on this data).
Run it on the CURRENT mixed data and it must FAIL — that is the proof it catches the disease.
"""
from __future__ import annotations
import argparse, glob, gzip, os, sys
import numpy as np
import pandas as pd

FAILS = []
def check(name, ok, detail=""):
    tag = "PASS" if ok else "FAIL"
    print(f"[{tag}] {name}" + (f"  — {detail}" if detail else ""), flush=True)
    if not ok: FAILS.append(name)

# ---- ground truth the panel is checked against -------------------------------------------
# anchor: ticker -> (first year data must exist, last year data must exist)
# value = (first year, last year, alias tickers) — a rename (FB->META 2021-10; GOOG class split
# 2014, the 2004-2013 span lives under the GOOGL-last-named PERMNO column) means the SAME anchor
# may be covered by columns under EITHER name; coverage is judged on the UNION of all matches.
ANCHORS = {"AAPL": (1990, 2024, ()), "MSFT": (1990, 2024, ()), "GE": (1990, 2024, ()),
           "JPM": (1990, 2024, ()), "KO": (1990, 2024, ()), "NVDA": (1999, 2024, ()),
           "GOOG": (2004, 2024, ("GOOGL",)), "TSLA": (2010, 2024, ()),
           "META": (2012, 2024, ("FB",)), "SPY": (1993, 2024, ())}
# names that must END mid-sample (delisting present = no survivorship scrub)
DEAD = {"ENE": (2001, 2002), "LEH": (2008, 2008), "BSC": (2008, 2008)}
# (ticker, split date): |return| that day must be small — pvCLCL is split-adjusted
SPLITS = [("AAPL", "2014-06-09"), ("AAPL", "2020-08-31"), ("TSLA", "2020-08-31"),
          ("TSLA", "2022-08-25"), ("NVDA", "2021-07-20"), ("NVDA", "2024-06-10")]

def raw_checks(d: str) -> None:
    files = sorted(glob.glob(os.path.join(d, "[12][0-9][0-9][0-9]", "*.csv.gz")))
    check("raw: files found", len(files) > 8000, f"{len(files)} files")
    # (R1) ONE schema for the whole span — the mixed-vintage catch, cheapest possible form
    ncols = {}
    for p in files[::126]:                                   # ~2/year
        with gzip.open(p, "rt") as f: ncols[p] = len(f.readline().split(","))
    check("raw: single schema across all years", len(set(ncols.values())) == 1,
          f"column counts seen: {sorted(set(ncols.values()))}")
    # (R2) per-year symbol count continuity — year-over-year jump > 25% is a vintage seam
    counts = {}
    for p in files[::63]:
        y = int(os.path.basename(p)[:4])
        counts.setdefault(y, []).append(sum(1 for _ in gzip.open(p, "rt")) - 1)
    yr = pd.Series({y: float(np.median(v)) for y, v in counts.items()}).sort_index()
    jump = (yr / yr.shift(1) - 1).abs().dropna()
    check("raw: no >25% year-over-year universe jump", (jump < 0.25).all(),
          "worst: " + ", ".join(f"{y}:{v:+.0%}" for y, v in jump.nlargest(3).items()))
    # (R3) anchors present in the years they must be (sampled mid-year file)
    bad = []
    for y in (1995, 2000, 2005, 2010, 2015, 2021, 2023):
        ps = sorted(glob.glob(os.path.join(d, str(y), "*.csv.gz")))
        if not ps: continue
        txt = gzip.open(ps[len(ps)//2], "rt").read()
        for t, (y0, y1, aliases) in ANCHORS.items():
            names = (t,) + aliases
            if y0 <= y <= y1 and not any(f'"{n}"' in txt or f",{n}," in txt for n in names):
                bad.append(f"{t}@{y}")
    check("raw: anchor tickers present in their years", not bad, ", ".join(bad[:12]))
    # (R4) CRSP sentinel missing-return codes: RET uses -66/-77/-88/-99 as MISSING markers
    # (Wharton_CRSP_RET_Explanation.png in the delivery). If any leak into pvCLCL or the fret_*
    # columns, the builder would ingest them as -6600% returns. Any return <= -1 is impossible
    # for a long position and is treated as a sentinel leak.
    import pandas as _pd
    leaks, warns = [], []
    for p in files[:: max(1, len(files) // 60)]:
        try:
            df = _pd.read_csv(p)
        except Exception:
            continue
        for c in [x for x in df.columns if x == "pvCLCL" or x.startswith("fret_")]:
            v = _pd.to_numeric(df[c], errors="coerce")
            n = int((v <= -1.0).sum())
            if n:
                (leaks if c == "pvCLCL" else warns).append(
                    f"{os.path.basename(p)}:{c}:{n} (min {v.min():.1f})")
    # HARD gate only on pvCLCL — the one return column the builder consumes. fret_* columns are
    # open-print-derived markout helpers we never read; a penny stock's bad open (e.g. HRG
    # 1997-07-03, $0.88, fret_RR_tmOPCL -1.13) is noise there, not a build blocker.
    check("raw: no sentinel/impossible values in pvCLCL", not leaks, "; ".join(leaks[:8]))
    if warns:
        print(f"       [warn] {len(warns)} sub-(-100%) values in unused fret_* columns: "
              + "; ".join(warns[:4]))

def _cols_for(ticker: str, columns) -> list:
    """Columns matching a ticker under either keying: bare "AAPL" or v3's "AAPL.14593".
    A recycled ticker may match several PERMNO columns; anchor checks pass if ANY satisfies."""
    if ticker in columns: return [ticker]
    return [c for c in columns if isinstance(c, str) and c.rsplit(".", 1)[0] == ticker]


def panel_checks(d: str, old: str | None) -> None:
    r = pd.read_pickle(os.path.join(d, "returns.pkl"))
    caps = pd.read_pickle(os.path.join(d, "caps.pkl"))
    mask = pd.read_pickle(os.path.join(d, "mask.pkl"))
    print(f"\npanel {r.shape}  {r.index[0].date()}..{r.index[-1].date()}")
    check("panel: index sorted, unique, tz-naive",
          r.index.is_monotonic_increasing and r.index.is_unique and r.index.tz is None)
    check("panel: columns unique", r.columns.is_unique)
    check("panel: mask == returns.notna()", bool((mask == r.notna()).all().all()))
    # (P1) THE catch: daily names-with-return continuity. 5-day median vs 250-day median.
    n = r.notna().sum(axis=1).astype(float)
    ratio = (n.rolling(5).median() / n.rolling(250).median().shift(5)).dropna()
    seams = ratio[(ratio > 1.20) | (ratio < 0.80)]
    seam_days = seams.groupby(seams.index.year).size()
    check("panel: no universe seam (5d-vs-250d median within ±20%)", len(seams) == 0,
          f"{len(seams)} seam days, by year: {seam_days.to_dict()}" if len(seams) else "")
    # (P2) anchors: coverage in every required year, and no internal gap > 10 trading days
    bad = []
    for t, (y0, y1, aliases) in ANCHORS.items():
        cands = []
        for n in (t,) + aliases:
            cands += _cols_for(n, r.columns)
        if not cands: bad.append(f"{t}: absent"); continue
        # UNION coverage: a rename splits one company across columns; the union must cover
        # every required year, and SOME column must be gap-free over its own span.
        u = r[cands].notna().any(axis=1)
        for y in range(max(y0, r.index[0].year), min(y1, r.index[-1].year) + 1):
            if u.loc[f"{y}"].sum() == 0: bad.append(f"{t}: no data in {y} (union)"); break
        else:
            gaps = []
            for c in cands:
                v = r[c].notna().values
                if not v.any(): continue
                i0, i1 = np.argmax(v), len(v) - np.argmax(v[::-1])
                gaps.append(np.diff(np.flatnonzero(v[i0:i1])).max() if v[i0:i1].sum() > 1 else 1)
            if gaps and min(gaps) > 10:        # fail only if EVERY candidate column is gapped
                bad.append(f"{t}: every candidate column has an internal gap > 10d")
    check("panel: anchor coverage, no internal gap > 10 days", not bad, "; ".join(bad[:6]))
    # (P2b) D11: on a PERMNO-keyed (v3) panel the bare "SPY" market series must exist and must
    # be untradable (caps all-NaN). On bare-ticker panels SPY has caps by design — skip there.
    if any("." in str(c) for c in r.columns):
        ok = "SPY" in r.columns and bool(caps["SPY"].isna().all()) if "SPY" in caps.columns else False
        check("panel: bare SPY market series present, caps all-NaN (D11)", ok)
    # (P3) split safety on known split days
    bad = []
    for t, dt in SPLITS:
        for c in _cols_for(t, r.columns):
            if dt in r.index and pd.notna(r.loc[dt, c]) and abs(r.loc[dt, c]) > 0.25:
                bad.append(f"{t}@{dt}:{r.loc[dt, c]:+.1%}")
    check("panel: split-day returns adjusted (<25%)", not bad, ", ".join(bad))
    # (P4) delistings present (no survivorship scrub) and terminal returns finite
    bad = []
    for t, (y0, y1) in DEAD.items():
        if not (r.index[0].year <= y0 and y1 <= r.index[-1].year):
            continue                       # death window outside this panel's span — not testable
        cands = _cols_for(t, r.columns)
        if not cands: bad.append(f"{t}: absent"); continue
        if not any(y0 <= r[c].dropna().index[-1].year <= y1 for c in cands if r[c].notna().any()):
            bad.append(f"{t}: no candidate column ends in {y0}-{y1}")
    check("panel: mid-sample delistings present", not bad, "; ".join(bad))
    # (P5) return magnitudes: |ret|>50% should be rare and not clustered on one day
    ext = (r.abs() > 0.50).sum(axis=1)
    check("panel: no day with >50 names beyond |50%| return", int(ext.max()) <= 50,
          f"worst day {ext.idxmax().date()} with {int(ext.max())}")
    # (P6) caps: positive, and the anchor with the largest cap in 2023 is a mega-cap
    if "2023-06-15" in caps.index.astype(str).str[:10].values:
        row = caps.loc["2023-06-15"]; top1 = str(row.idxmax()).rsplit(".", 1)[0]
        check("panel: 2023 top cap is a known mega-cap", top1 in
              {"AAPL", "MSFT", "GOOG", "GOOGL", "AMZN", "NVDA", "SPY", "VOO", "VTI", "IVV"},
              f"top1={top1}  (ETF here means the ETF-inclusion decision is still pending)")
    # (P7) overlap cross-validation against the previous panel (same ticker, same day)
    if old:
        ro = pd.read_pickle(os.path.join(old, "returns.pkl"))
        rr = r
        # trigger the bare-ticker mapping whenever the panel is PERMNO-keyed, not only at zero
        # direct overlap — D11's bare "SPY" gives a 1-column intersection that used to satisfy
        # .any() and silently reduced this whole check to comparing SPY alone (88 cells).
        if (len(r.columns.intersection(ro.columns)) < 0.05 * len(r.columns)
                and any("." in str(c) for c in r.columns)):
            bare = pd.Index([str(c).rsplit(".", 1)[0] for c in r.columns])
            keep = ~bare.duplicated(keep=False)       # recycled tickers are ambiguous — skip them
            rr = r.loc[:, keep]; rr.columns = bare[keep]
        common_t = rr.columns.intersection(ro.columns)
        common_d = r.index.intersection(ro.index)
        cd = common_d[(common_d >= "2000-01-01") & (common_d <= "2021-12-31")][::63]
        # IDENTITY-AWARE comparison (2026-08-19). A bare-ticker reference panel splices
        # companies for recycled names and mislabels renamed ones, so cells there are
        # incomparable BY IDENTITY, not by value. The strict zero-tolerance test runs on the
        # unambiguous columns; the ambiguous ones are REPORTED, never silently absorbed.
        # NO materiality threshold anywhere (user directive 2026-08-19): any mismatch on an
        # unambiguous identity is a FAIL and goes to the user.
        amb = set()
        pmap_f = os.path.join(d, "permno_map.csv")
        if os.path.exists(pmap_f):
            pmap = pd.read_csv(pmap_f)
            amb_name = set(pmap.groupby("ticker")["PERMNO"].nunique()[lambda x: x > 1].index)
            multi_tk = set(pmap.groupby("PERMNO")["ticker"].nunique()[lambda x: x > 1].index)
            col_pm = {str(c).rsplit(".", 1)[0]: int(str(c).rsplit(".", 1)[1])
                      for c in r.columns if "." in str(c)}
            amb = {t for t in common_t if t in amb_name or col_pm.get(t) in multi_tk}
        clean_t = [t for t in common_t if t not in amb]
        a = rr.loc[cd, clean_t].to_numpy(float)
        b = ro.loc[cd, clean_t].to_numpy(float)
        both = np.isfinite(a) & np.isfinite(b)
        diff = np.abs(a[both] - b[both])
        nbad = int((diff > 1e-6).sum())
        check("panel: overlap 2000-2021, unambiguous identities, ZERO mismatch",
              nbad == 0,
              f"{nbad} mismatching cells of {both.sum():,} on {len(clean_t)} columns, "
              f"max|diff| {diff.max():.2e}")
        if amb:
            print(f"       [report] {len(amb)} identity-ambiguous tickers EXCLUDED from the "
                  f"strict test (recycled or renamed; the reference panel splices them). "
                  f"Census, not a pass: {sorted(amb)[:10]}...")
        onlyold = ro.loc[cd, common_t].notna().sum(1) - rr.loc[cd, common_t].notna().sum(1)
        check("panel: on COMMON tickers, new panel never has fewer names than old",
              int(onlyold.max()) <= 0, f"worst day short by {int(onlyold.max())}")

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw"); ap.add_argument("--panel"); ap.add_argument("--old-panel")
    a = ap.parse_args()
    if not a.raw and not a.panel: ap.error("give --raw and/or --panel")
    if a.raw: raw_checks(a.raw)
    if a.panel: panel_checks(a.panel, a.old_panel)
    print(f"\n{'='*60}\n{'ALL CHECKS PASSED' if not FAILS else f'{len(FAILS)} FAILED: ' + ', '.join(FAILS)}")
    return 0 if not FAILS else 1

if __name__ == "__main__":
    sys.exit(main())
