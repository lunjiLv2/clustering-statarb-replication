"""Principal-component factor returns from the §6.1 lens construction, and the time-series spanning of the
28 books on FF5+MOM (+ short-term reversal) with and without the five PCs (§6.2, CORRECTIONS N81).

Factors: residual returns r~ = raw - beta_60 * SPY (rolling 60-day CAPM on the compat panel); on each
common-calendar day t the universe is the day's 500-name top-cap universe (the k-means partition cache),
restricted to names with a complete trailing 252-day residual history strictly before t; H is the
column-demeaned 252 x n residual matrix, its SVD gives loadings V (rows of unit L2 norm); factor k on day
t is f_kt = v_k' r~_t / ||v_k||_1 (a unit-gross book in the day-t cross-section). The sign of v_k is
aligned day to day (flipped when its dot product with the previous day's v_k is negative).

Spanning: for both components and the four designs ff6 / ff6_pc5 / ff6_st / ff6_st_pc5, OLS with
Newey–West (21) t-statistics; alpha in %/yr. Phase: the PC factors live on the panel calendar. The
seed-averaged trained books (dated on the panel calendar) match them at shift 0 with FF at shift 1;
the rule-based books (dated on the signal day, paying the next panel day) match the PCs at shift -1
with FF at shift 0 — pc_spanning_v3 carries the head rows (and, for reference, the rule rows at PC
shift 0), pc_spanning_rule_shiftm1_v3 the rule rows at the correct phase.

Outputs (analysis/results): pc_factors_v3_cal6913.csv, pc_spanning_v3_cal6913.csv,
pc_spanning_rule_shiftm1_v3_cal6913.csv.
Run: ``CSA_PANEL_ROOT=... python analysis/pc_factors_v3.py``  (~20 min; ``--skip-factors`` reuses the shipped factor file)
"""
from __future__ import annotations
import argparse, pickle, sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books
from analysis.factors import FF6, load_ff, nw_ols
from analysis._compare import compare_and_write

W, M = 252, 5
ARMS = ["kmeans_ret", "pca_load", "agglo_avg", "agglo_complete", "spectral_unsigned", "gics", "sponge_w60", "fv2a_w60",
        "fv3sm_w60", "sharpe_fixed_w60", "sortino_w60", "sssnetpre", "k1", "random"]
PCS = [f"PC{k + 1}" for k in range(M)]
DESIGNS = {"ff6": FF6, "ff6_pc5": FF6 + PCS, "ff6_st": FF6 + ["ST_Rev"], "ff6_st_pc5": FF6 + ["ST_Rev"] + PCS}


def pc_factors() -> pd.DataFrame:
    assert paths.PANEL is not None, "set CSA_PANEL_ROOT"
    px = pd.read_pickle(paths.PANEL / "prices.pkl"); raw = px.pct_change(fill_method=None); mkt = raw["SPY"]
    rc = raw.rolling(60).cov(mkt); rv = mkt.rolling(60).var(); res = raw - rc.div(rv, axis=0).multiply(mkt, axis=0)
    del px, raw, rc, rv
    cols = {c: j for j, c in enumerate(res.columns)}; Rv = res.to_numpy(np.float64); pos = {d: i for i, d in enumerate(res.index)}; del res
    cache = pickle.load(open(paths.PARTITIONS / "kmeans_ret.pkl", "rb")); calset = set(books.IDX)
    days = [k for k in sorted(cache) if pd.Timestamp(k) in calset]
    F = {}; prev = None; nuse = []
    for n_, dt in enumerate(days):
        i = pos[pd.Timestamp(dt)]; uni = [t for t in cache[dt]["universe"] if t in cols]; j = np.array([cols[t] for t in uni])
        x = Rv[i, j]; hist = Rv[i - W:i][:, j]; ok = np.isfinite(x) & np.isfinite(hist).all(axis=0)
        x, hist = x[ok], hist[:, ok]; names = np.array(uni)[ok]
        H = hist - hist.mean(0, keepdims=True); _, _, Vt = np.linalg.svd(H, full_matrices=False); V = Vt[:M].copy()
        if prev is not None:
            pn, pV = prev; common = np.isin(names, pn); cm = {t: k for k, t in enumerate(pn)}; jj = np.array([cm[t] for t in names[common]])
            for k in range(M):
                if float(V[k, common] @ pV[k, jj]) < 0: V[k] *= -1
        prev = (names, V)
        F[pd.Timestamp(dt)] = [float(V[k] @ x / np.abs(V[k]).sum()) for k in range(M)]; nuse.append(ok.sum())
        if n_ % 1000 == 0: print(f"  day {n_}/{len(days)} n={ok.sum()}", flush=True)
    PC = pd.DataFrame.from_dict(F, orient="index", columns=PCS).reindex(books.IDX); assert PC.notna().all().all()
    PC.index.name = "Date"
    print("PC factors: ann vol %", (100 * PC.std() * np.sqrt(252)).round(2).to_dict(), "mean names", np.mean(nuse))
    return PC


def spanning(PC: pd.DataFrame, ff: pd.DataFrame, component: str, pc_shift: int) -> pd.DataFrame:
    loader, sh = (books.rule_book, 0) if component == "rule" else (books.head_avg, 1)
    Mx = (pd.concat({a: loader(a) for a in ARMS}, axis=1).join(ff[FF6 + ["ST_Rev"]].shift(sh), how="inner")
          .join(PC.shift(pc_shift), how="inner").reindex(books.IDX).dropna())
    rows = []
    for a in ARMS:
        y = Mx[a].to_numpy(float)
        for design, cols_ in DESIGNS.items():
            b, t, r2 = nw_ols(y, Mx[cols_].to_numpy(float))
            d = dict(component=component, arm=a, design=design, alpha=252 * 100 * b[0], t=t[0], R2=r2)
            for k, c in enumerate(cols_): d[f"b_{c}"] = b[k + 1]; d[f"t_{c}"] = t[k + 1]
            rows.append(d)
    print(f"  {component} at PC shift {pc_shift}: {len(Mx)} days", flush=True)
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--skip-factors", action="store_true", help="reuse the shipped pc_factors_v3_cal6913.csv")
    a = ap.parse_args()
    if a.skip_factors:
        PC = pd.read_csv(paths.RESULTS / "pc_factors_v3_cal6913.csv", index_col=0, parse_dates=True).reindex(books.IDX)
    else:
        PC = pc_factors()
        compare_and_write(PC.reset_index().assign(Date=lambda d: d.Date.dt.strftime("%Y-%m-%d")), "pc_factors_v3_cal6913.csv", ["Date"])
    ff = load_ff(with_reversal=True)
    S = pd.concat([spanning(PC, ff, "rule", 0), spanning(PC, ff, "head", 0)], ignore_index=True)
    compare_and_write(S, "pc_spanning_v3_cal6913.csv", ["component", "arm", "design"])
    Rm = spanning(PC, ff, "rule", -1).drop(columns=["component"])
    compare_and_write(Rm, "pc_spanning_rule_shiftm1_v3_cal6913.csv", ["arm", "design"])
    for design in ("ff6", "ff6_pc5", "ff6_st", "ff6_st_pc5"):
        for comp, T in (("rule", Rm), ("head", S[S.component == "head"])):
            s = T[T.design == design]; c = s[~s.arm.isin(["k1", "random"])]
            print(f"  {design:10s} {comp:4s}: 12 clusterizers alpha {c.alpha.min():.2f}–{c.alpha.max():.2f}, R2 {c.R2.min():.2f}–{c.R2.max():.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
