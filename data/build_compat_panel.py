#!/usr/bin/env python3
"""
00_build_compat_panel.py — build Cleaned_Data_v2_compat/{prices.pkl,caps.pkl,mask.pkl}

GOAL
----
Let every EXISTING legacy pipeline (May_15 pipeline_v21_* / June_16 head scripts)
run on the split-safe Cleaned_Data_v2 returns with ZERO code changes.

The legacy pipelines consume `prices.pkl` ONLY via
    raw_returns = prices.pct_change(fill_method=None)
plus the calendar (`prices.index`, `len(prices)`).  (Grep-audited; see
README_SERVER.md section "Price-consumption audit".  There is NO price-level use.)

The A1-validated stamping equivalence (recleaning/revalidation/revalidate_naive.py):
    legacy prices.pct_change(fill_method=None)[t]  ==  returns_v2.shift(1)[t]
    (row t of both = the SAME economic close(t-2)->close(t-1) return)

So we synthesize a price panel P such that
    P.pct_change(fill_method=None)  ==  returns_v2.shift(1)      (call it R)
cell-for-cell: identical values (< 1e-12) AND identical NaN masks — up to the
unavoidable legacy re-entry semantics documented below.

CONSTRUCTION (per column, vectorized)
-------------------------------------
For each maximal run of valid R cells [s..e]:
    P[s-1] = 1.0 (seed), P[t] = P[t-1] * (1 + R[t]) for t in [s..e]; NaN elsewhere.
Implemented with a single cumprod + seed-anchored division, so
pct_change ratios cancel EXACTLY (error ~2 ulp, far below the 1e-12 gate).

LEGACY NaN-GAP SEMANTICS (the one deliberate mask edit)
-------------------------------------------------------
A price panel cannot represent an ISOLATED single-day NaN in a returns panel:
prices would remain contiguous across a 1-day return gap and pct_change would
fabricate a value there. Legacy semantics are: NaN during the gap AND NaN on the
first day after re-entry (no previous price). We reproduce that: whenever R has
a 1-day gap (or a run starts at row 0), the first return after re-entry is
DROPPED (becomes NaN in the compat-derived returns). Each dropped cell is
counted and logged; on the validated local panel this is 265 cells out of
~28.7M valid cells (1e-5 of the panel). Every remaining cell is asserted equal.

caps.pkl / mask.pkl: passed through BYTE-IDENTICAL from legacy Cleaned_Data.
Rationale (documented choice): (1) caps = price x sharesOut is split-safe
(split factors cancel), so the legacy caps are not contaminated by the split
artifact that motivated v2; (2) legacy caps/mask carry the SAME legacy row
stamping as the compat prices, so prior-day-cap universe selection
(caps.iloc[t-1].nlargest(500)) and residual masking stay bit-identical to the
canonical runs — the A2 rerun then isolates the RETURNS panel as the only
changed input.

ENV (all optional)
------------------
  BASE / CSA_PANEL_BASE   directory holding Cleaned_Data_v3/ (no default in the replication repo)
  RETURNS_V2     default $BASE/Cleaned_Data_v2/returns.pkl
  LEGACY_DIR     default $BASE/Cleaned_Data          (source of caps/mask)
  OUT_DIR        default $BASE/Cleaned_Data_v2_compat
  BLOCK_COLS     default 512 (memory blocking)
  VALIDATE_ONLY  "1" -> run the full construction+assertions, write nothing

Exit codes: 0 = built+validated, 1 = hard failure (message on stderr).
Seed: deterministic (no RNG used). numpy+pandas only.
"""

from __future__ import annotations

import os
import shutil
import sys
import time

import numpy as np
import pandas as pd

TOL = 1e-12  # max abs diff gate on non-NaN cells


def fail(msg: str) -> None:
    """Print an explicit failure message and exit nonzero."""
    sys.stderr.write(f"\n[FATAL][00_build_compat_panel] {msg}\n")
    sys.stderr.flush()
    sys.exit(1)


def log(msg: str) -> None:
    print(f"[compat] {msg}", flush=True)


def _ffill_2d(a: np.ndarray) -> np.ndarray:
    """Forward-fill NaNs down axis 0 of a 2-D float array (pure numpy)."""
    t, m = a.shape
    idx = np.where(np.isfinite(a), np.arange(t)[:, None], 0)
    np.maximum.accumulate(idx, axis=0, out=idx)
    return a[idx, np.arange(m)[None, :]]


def build_price_block(rb: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Build a compat price block for target returns block `rb` (T, m).

    Returns (prices_block, dropped_mask) where dropped_mask marks target
    return cells sacrificed to legacy re-entry semantics (1-day gaps /
    run starting at row 0).
    """
    t_len, m = rb.shape
    valid = np.isfinite(rb)
    dropped = np.zeros_like(valid)

    # Iteratively drop non-price-representable cells (fixpoint; ~1 pass needed).
    for _ in range(t_len):
        prev1 = np.zeros_like(valid)
        prev1[1:] = valid[:-1]
        prev2 = np.zeros_like(valid)
        prev2[2:] = valid[:-2]
        start = valid & ~prev1
        conflict = start & prev2          # exactly-1-day gap above the run start
        conflict[0] |= start[0]           # run starting at row 0: no room for a seed
        if not conflict.any():
            break
        valid &= ~conflict
        dropped |= conflict
    else:
        fail("gap-conflict resolution did not converge (data pathology?)")

    prev1 = np.zeros_like(valid)
    prev1[1:] = valid[:-1]
    start = valid & ~prev1
    seed = np.zeros_like(valid)
    seed[:-1] = start[1:]                 # seed sits one row above each run start

    growth = np.where(valid, 1.0 + rb, 1.0)
    if (valid & (growth == 0.0)).any():
        fail("encountered return == -100% (1+r == 0); price construction "
             "cannot represent it. Inspect the returns panel.")
    cp = np.cumprod(growth, axis=0)
    if not np.isfinite(cp[valid]).all():
        fail("cumprod overflow/underflow in price construction.")

    anchor = np.where(seed, cp, np.nan)
    anchor = _ffill_2d(anchor)
    prices = np.where(valid | seed, cp / anchor, np.nan)
    return prices, dropped


def validate_block(prices: np.ndarray, rb: np.ndarray,
                   dropped: np.ndarray, col_off: int) -> float:
    """Assert pct_change(prices) == rb minus dropped cells. Returns max |diff|."""
    r_hat = np.full_like(rb, np.nan)
    r_hat[1:] = prices[1:] / prices[:-1] - 1.0
    hat_valid = np.isfinite(r_hat)
    tgt_valid = np.isfinite(rb) & ~dropped

    spurious = hat_valid & ~tgt_valid
    missing = tgt_valid & ~hat_valid
    if spurious.any() or missing.any():
        ts, cs = np.where(spurious | missing)
        fail(f"NaN-mask mismatch in block at cols {col_off}+: "
             f"{int(spurious.sum())} spurious / {int(missing.sum())} missing "
             f"valid cells; first offender (row={ts[0]}, col={col_off + cs[0]}).")

    if not tgt_valid.any():
        return 0.0
    diff = np.abs(r_hat[tgt_valid] - rb[tgt_valid])
    mx = float(diff.max())
    if mx >= TOL:
        fail(f"value mismatch in block at cols {col_off}+: max|diff|={mx:.3e} >= {TOL}")
    return mx


def main() -> None:
    t0 = time.time()
    base = os.environ.get("BASE", os.environ.get("CSA_PANEL_BASE", ""))  # replication repo: directory holding Cleaned_Data_v3/ (returns/caps/mask.pkl)
    assert base, "set CSA_PANEL_BASE (or BASE) to the directory that contains Cleaned_Data_v3/"
    returns_src = os.environ.get("RETURNS_V2",
                                 os.path.join(base, "Cleaned_Data_v2", "returns.pkl"))
    legacy_dir = os.environ.get("LEGACY_DIR", os.path.join(base, "Cleaned_Data"))
    out_dir = os.environ.get("OUT_DIR", os.path.join(base, "Cleaned_Data_v2_compat"))
    block_cols = int(os.environ.get("BLOCK_COLS", "512"))
    validate_only = os.environ.get("VALIDATE_ONLY", "0") == "1"

    legacy_caps = os.path.join(legacy_dir, "caps.pkl")
    legacy_mask = os.path.join(legacy_dir, "mask.pkl")
    for p in (returns_src, legacy_caps, legacy_mask):
        if not os.path.exists(p):
            fail(f"required input missing: {p}\n"
                 f"  (BASE={base}; override RETURNS_V2 / LEGACY_DIR if paths differ)")

    log(f"BASE={base}")
    log(f"returns_v2 = {returns_src}")
    log(f"legacy caps/mask = {legacy_caps} , {legacy_mask}")
    log(f"OUT_DIR = {out_dir}  (VALIDATE_ONLY={validate_only})")

    returns = pd.read_pickle(returns_src)
    if not isinstance(returns, pd.DataFrame):
        fail(f"returns.pkl is {type(returns)}, expected DataFrame")
    if not returns.index.is_monotonic_increasing:
        fail("returns index not monotonic increasing")
    n_dup = int(returns.columns.duplicated().sum())
    log(f"returns shape={returns.shape} "
        f"[{returns.index[0].date()} -> {returns.index[-1].date()}] "
        f"duplicated col names={n_dup} (kept as-is, positional construction)")
    if "SPY" not in returns.columns:
        fail("SPY column missing from returns panel (needed for CAPM residualization)")
    if isinstance(returns["SPY"], pd.DataFrame):
        fail("SPY column is duplicated — pipelines expect a unique SPY Series")

    # Target: legacy-stamped returns
    target = returns.shift(1)
    tgt_vals = target.to_numpy(dtype=np.float64, copy=False)
    t_len, n_cols = tgt_vals.shape

    prices_out = np.full((t_len, n_cols), np.nan, dtype=np.float64)
    n_dropped = 0
    dropped_examples: list[tuple[str, str]] = []
    max_diff = 0.0

    for c0 in range(0, n_cols, block_cols):
        c1 = min(c0 + block_cols, n_cols)
        rb = tgt_vals[:, c0:c1]
        pb, dropped = build_price_block(rb)
        max_diff = max(max_diff, validate_block(pb, rb, dropped, c0))
        prices_out[:, c0:c1] = pb
        nd = int(dropped.sum())
        n_dropped += nd
        if nd and len(dropped_examples) < 10:
            ts, cs = np.where(dropped)
            for k in range(min(nd, 10 - len(dropped_examples))):
                dropped_examples.append(
                    (str(returns.index[ts[k]].date()), str(returns.columns[c0 + cs[k]])))
        if (c0 // block_cols) % 4 == 0:
            log(f"  built+validated cols {c0}..{c1} "
                f"(max|diff| so far {max_diff:.2e}, dropped {n_dropped})")

    prices_df = pd.DataFrame(prices_out, index=returns.index, columns=returns.columns)

    # ---- Ground-truth validation through the EXACT consumer call ----
    log("final validation: prices.pct_change(fill_method=None) vs returns.shift(1) ...")
    r_hat = prices_df.pct_change(fill_method=None)
    hat_valid = r_hat.notna().to_numpy()
    tgt_valid = target.notna().to_numpy()
    n_tgt = int(tgt_valid.sum())
    spurious = int((hat_valid & ~tgt_valid).sum())
    missing = int((tgt_valid & ~hat_valid).sum())
    if spurious != 0:
        fail(f"final check: {spurious} cells valid in pct_change but NaN in target")
    if missing != n_dropped:
        fail(f"final check: mask deficit {missing} != logged re-entry drops {n_dropped}")
    both = hat_valid & tgt_valid
    diffs = np.abs(r_hat.to_numpy()[both] - tgt_vals[both])
    final_max = float(diffs.max())
    final_med = float(np.median(diffs))
    if final_max >= TOL:
        fail(f"final check: max|diff|={final_max:.3e} >= {TOL}")

    # ---- caps/mask grid compatibility ----
    caps = pd.read_pickle(legacy_caps)
    mask = pd.read_pickle(legacy_mask)
    if not caps.index.equals(prices_df.index):
        fail("legacy caps.pkl index != compat prices index — grids diverged; "
             "the compat panel would be misaligned. Aborting.")
    if not mask.index.equals(prices_df.index):
        fail("legacy mask.pkl index != compat prices index — aborting.")
    if list(caps.columns) != list(prices_df.columns):
        log("WARNING: caps columns != returns columns ORDER/SET. Pipelines align "
            "by label (reindex), so this is tolerated — but verify intent.")
    log(f"grid check OK: {t_len} dates x {n_cols} cols; caps/mask share the index")

    # ---- Report ----
    report = [
        "COMPAT PANEL VALIDATION REPORT (00_build_compat_panel.py)",
        f"built: {time.strftime('%Y-%m-%d %H:%M:%S')}  runtime {time.time()-t0:.0f}s",
        f"returns_v2: {returns_src}",
        f"target = returns_v2.shift(1)  (A1 legacy-stamping equivalence)",
        f"panel: {t_len} x {n_cols}  [{returns.index[0].date()} -> {returns.index[-1].date()}]",
        f"valid target cells: {n_tgt}",
        f"ASSERT pct_change(fill_method=None) == returns.shift(1):",
        f"  max|diff| on non-NaN cells: {final_max:.3e}  (< {TOL} PASS)",
        f"  median|diff|:               {final_med:.3e}",
        f"  NaN masks: identical up to {n_dropped} legacy re-entry drops "
        f"({100.0*n_dropped/max(n_tgt,1):.5f}% of valid cells)",
        f"  re-entry drops = first return after a 1-day gap (price panels cannot",
        f"  represent isolated 1-day return gaps; legacy semantics = NaN there)",
        f"  first examples: {dropped_examples}",
        f"caps/mask: byte-copied from {legacy_dir} (legacy stamping, split-safe caps;",
        f"  keeps universe selection bit-identical to canonical runs)",
        f"VERDICT: PASS",
    ]
    print("\n" + "\n".join(report) + "\n", flush=True)

    if validate_only:
        log("VALIDATE_ONLY=1 — nothing written.")
        return

    os.makedirs(out_dir, exist_ok=True)
    out_prices = os.path.join(out_dir, "prices.pkl")
    log(f"writing {out_prices} ...")
    prices_df.to_pickle(out_prices)
    log(f"copying caps.pkl / mask.pkl from {legacy_dir} ...")
    shutil.copyfile(legacy_caps, os.path.join(out_dir, "caps.pkl"))
    shutil.copyfile(legacy_mask, os.path.join(out_dir, "mask.pkl"))
    with open(os.path.join(out_dir, "COMPAT_VALIDATION.txt"), "w") as f:
        f.write("\n".join(report) + "\n")
    log(f"DONE -> {out_dir}  ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
