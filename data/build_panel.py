"""build_cleaned_v3.py — the rebuild for the CONSISTENT enlarged delivery (D1+D2 of
server_package/panel_audit/RERUN_PREFLIGHT.md; approved by the user 2026-08-18).

Differences from build_cleaned_v2.py, each one a decision with a paper trail:

  D1  SHRCD filter: keep common shares (SHRCD 10, 11, 12 — 12 is foreign-incorporated:
      ACN/LIN/MDT). Drops ETFs (73), ADRs (30/31),
      REITs (18/48), closed-end funds. The v2 panel had no filter, so the "market cap" top-500
      counted SPY's AUM as a cap (rank #8 in 2021) and traded 5-17 ETFs at all times (N28(a)).
      Every dropped SHRCD is counted and printed per year — the filter is auditable, not silent.

  D2  PERMNO keying: columns are "TICKER.PERMNO" (last-seen ticker, for humans; PERMNO, for
      identity). The v2 panel keyed by bare ticker, splicing different companies into one
      column — 27.4% of tickers map to >1 PERMNO over 1990-2024, 302 switch with a <=45-day
      gap, and GM = old GM + new GM in one column (N28(b)). A permno_map.csv records every
      (PERMNO, ticker, first, last) span seen.

  Unchanged from v2 (deliberately): pvCLCL as the return (split+dividend safe), caps =
  |prevAdjClose| * sharesOut stamped t-1, mask = returns.notna(), empty dates dropped,
  economic-date stamping (00_build_compat_panel.py re-stamps t -> t+1 downstream).

REQUIRES the 39-column schema (SHRCD/PERMNO present) for EVERY file — i.e. the consistent
delivery. On the old mixed data this exits at the first 18-column file, by design. Run
panel_audit/panel_acceptance.py --raw FIRST; then this; then --panel on the output.

    python build_cleaned_v3.py <DATA_DIR> <OUT_DIR> [--years 1990-2024]
"""
import argparse
import glob
import os
import sys
import time

import pandas as pd

USECOLS = ["ticker", "PERMNO", "SHRCD", "pvCLCL", "prevAdjClose", "sharesOut"]
KEEP_SHRCD = {10, 11, 12}                 # common shares incl. foreign-incorporated (12).
# D11 (audit 2026-08-18): SPY is BOTH an ETF (SHRCD 73, filtered by D1) AND the market series
# every downstream residualization hard-depends on — 00_build_compat_panel.py:199 hard-fails
# without it, and the GPU pipelines SILENTLY substitute the alphabetically-first stock column
# (pipeline:156, ~41% residual distortion) if the column is missing. So SPY is carried as a
# MARKET-SERIES exemption: bare-named "SPY" (not SPY.84398 — every consumer looks up the bare
# name), returns kept, caps FORCED to NaN so no top-500 cap ranking can ever select it into a
# traded book (caps.nlargest and PATCH 6's caps.notna() both skip NaN). PERMNO 84398 is stable
# 1993-2024 (checked at 1993/1999/2010/2024).
SPY_PERMNO = 84398
# 12 keeps ACN/LIN/MDT/CB/ETN/SLB (62 of the 2023 top-500). The strict academic filter is
# {10, 11}; switching is this one constant. Dropped either way: 73 ETF (66 of top-500!),
# 31 ADR, 18/48 REIT, 71/44 units & SBI.


def read_day(path):
    date = pd.Timestamp(os.path.basename(path)[:8])
    try:
        df = pd.read_csv(path, usecols=USECOLS)
    except ValueError as e:                # missing column = old-vintage file = mixed delivery
        sys.exit(f"[FATAL] {path}: {e}\nThis is not the consistent 39-column delivery. "
                 f"Run panel_acceptance.py --raw and reconcile the data before building.")
    for c in ("PERMNO", "SHRCD", "pvCLCL", "prevAdjClose", "sharesOut"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["PERMNO"])
    df["PERMNO"] = df["PERMNO"].astype(int)
    return date, df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data_dir"); ap.add_argument("out_dir")
    ap.add_argument("--years", default="1990-2024")
    a = ap.parse_args()
    y0, y1 = (int(x) for x in a.years.split("-"))
    files = [p for p in sorted(glob.glob(os.path.join(a.data_dir, "[12][0-9][0-9][0-9]", "*.csv.gz")))
             if y0 <= int(os.path.basename(p)[:4]) <= y1]
    print(f"{len(files)} files, {y0}-{y1}")

    rets, caps, empty = {}, {}, []
    shrcd_dropped = {}                                    # year -> {shrcd: n}
    spans = {}                                            # (permno, ticker) -> [first, last]
    dup_permno_rows = 0
    t0 = time.time()
    for i, p in enumerate(files):
        date, df = read_day(p)
        dup = int(df["PERMNO"].duplicated().sum())
        if dup:
            dup_permno_rows += dup
            df = df.drop_duplicates("PERMNO", keep="first")
        yr = date.year
        keep = df["SHRCD"].isin(KEEP_SHRCD) | (df["PERMNO"] == SPY_PERMNO)   # D11 exemption
        drop = df[~keep]
        d = shrcd_dropped.setdefault(yr, {})
        for k, v in drop["SHRCD"].value_counts().items():
            d[int(k)] = d.get(int(k), 0) + int(v)
        df = df[keep].set_index("PERMNO")
        if df["pvCLCL"].notna().sum() == 0:
            empty.append(date); continue
        rets[date] = df["pvCLCL"]
        cp = df["prevAdjClose"].abs() * df["sharesOut"]
        if SPY_PERMNO in cp.index:
            cp.loc[SPY_PERMNO] = float("nan")     # D11: market series, never tradable
        caps[date] = cp
        for pm, tk in df["ticker"].dropna().items():
            key = (pm, tk)
            if key in spans: spans[key][1] = date
            else: spans[key] = [date, date]
        if (i + 1) % 1000 == 0:
            print(f"  {i+1}/{len(files)}  {time.time()-t0:.0f}s", flush=True)

    returns = pd.DataFrame(rets).T.sort_index()
    cap_df = pd.DataFrame(caps).T.sort_index().reindex(columns=returns.columns)

    # ---- D2: column names TICKER.PERMNO (last-seen ticker per PERMNO) ----------------------
    last_tk = {}
    for (pm, tk), (f0, f1) in spans.items():
        if pm not in last_tk or f1 > last_tk[pm][1]: last_tk[pm] = (tk, f1)
    cols = {pm: ("SPY" if pm == SPY_PERMNO else
                 f"{last_tk[pm][0]}.{pm}" if pm in last_tk else f"UNK.{pm}")
            for pm in returns.columns}
    assert len(set(cols.values())) == len(cols), "TICKER.PERMNO collision — impossible unless PERMNO dupes"
    returns = returns.rename(columns=cols)[sorted(cols.values())]
    cap_df = cap_df.rename(columns=cols)[returns.columns]

    os.makedirs(a.out_dir, exist_ok=True)
    returns.to_pickle(os.path.join(a.out_dir, "returns.pkl"))
    cap_df.to_pickle(os.path.join(a.out_dir, "caps.pkl"))
    returns.notna().to_pickle(os.path.join(a.out_dir, "mask.pkl"))
    pd.DataFrame([(pm, tk, f0.date(), f1.date()) for (pm, tk), (f0, f1) in sorted(spans.items())],
                 columns=["PERMNO", "ticker", "first", "last"]) \
        .to_csv(os.path.join(a.out_dir, "permno_map.csv"), index=False)

    print(f"\nshape={returns.shape}  {returns.index[0].date()}..{returns.index[-1].date()}"
          f"  ({len(empty)} empty dates dropped)")
    print(f"same-PERMNO duplicate rows dropped: {dup_permno_rows}")
    print("SHRCD dropped per year (73=ETF):")
    for yr in sorted(shrcd_dropped):
        d = shrcd_dropped[yr]; days = max(1, sum(1 for x in returns.index if x.year == yr))
        top = ", ".join(f"{k}:{v//days}/d" for k, v in sorted(d.items(), key=lambda x: -x[1])[:4])
        print(f"  {yr}: {top}")
    # ---- self-checks ----------------------------------------------------------------------
    def col_of(tk):
        c = [c for c in returns.columns if c.rsplit(".", 1)[0] == tk]
        return c[0] if c else None
    for tk in ("AAPL", "MSFT"):
        c = col_of(tk)
        n = int(returns[c].notna().sum()) if c else 0
        print(f"  {tk}: {'column ' + c + f', {n} days' if c else 'ABSENT'}")
    assert "SPY" in returns.columns, "D11 broken: bare SPY market series missing"
    assert cap_df["SPY"].isna().all(), "D11 broken: SPY has caps — it could enter the traded book"
    print(f"  SPY: bare market-series column, {int(returns['SPY'].notna().sum())} days, caps all-NaN ✓")
    c = col_of("NVDA")
    if c is not None and pd.Timestamp("2024-06-10") in returns.index:
        print(f"  NVDA 2024-06-10 (10:1 split day): {returns.loc['2024-06-10', c]:+.4f} (must be small)")
    print(f"  |ret|>45%: {int((returns.abs() > 0.45).sum().sum())}")


if __name__ == "__main__":
    main()
