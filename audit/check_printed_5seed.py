"""Recompute the manuscript's five-seed quantities from the books and compare with what it prints.

This is the books-based complement of audit/verify_printed.py. That harness checks the printed values against
the shipped result CSVs; this one recomputes them from the daily books at paths.SEEDS, so a CSV that was
regenerated on the wrong basis cannot pass both. History: on 2026-09-01, before the five-seed promotion (N85),
the shipped CSVs were the build site's earlier snapshot and 14 of verify_printed's 51 concrete targets aimed at
values the manuscript no longer printed; this file was written that day to close that gap.

Every target below is the value the manuscript prints today, and every computed value comes from
analysis/books at paths.SEEDS. A FAIL means the paper and the data disagree.

    CSA_PANEL_ROOT=... python audit/check_printed_5seed.py
"""
from __future__ import annotations
import itertools, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books
from analysis.factors import FF6, load_ff, nw_ols, alpha_pct

FAILS = []
def chk(name, got, want, tol=0.006):
    ok = (abs(got - want) <= tol) if isinstance(want, float) else (got == want)
    print(f"  {'PASS' if ok else 'FAIL'}  {name:52s} got {got}  printed {want}")
    if not ok: FAILS.append(name)

CTL = ("k1", "random")
CL = [a for a in paths.ARMS if a not in CTL]
ff = load_ff()
REV = [c for c in ff.columns if "rev" in c.lower()]


def alpha_t(s, cols, shift):
    m = pd.concat([s.rename("y"), ff[cols].shift(shift)], axis=1).reindex(books.IDX).dropna()
    b, t, _ = nw_ols(m.y.to_numpy(float), m[cols].to_numpy(float))
    return alpha_pct(b), float(t[0]), float(b[1])


def main() -> int:
    print(f"seeds {tuple(paths.SEEDS)}  |  {len(books.IDX)} days\n")

    print("== tab:moments / tab:head_adds ==")
    tv = {a: float(np.mean([books.ann_vol(books.head_book(a, s)) for s in paths.SEEDS])) for a in CL + list(CTL)}
    ta = {a: alpha_t(books.head_avg(a), FF6, 1)[0] for a in CL + list(CTL)}
    chk("trained vol band low 2.88", min(tv[a] for a in CL), 2.88)
    chk("trained vol band high 3.80", max(tv[a] for a in CL), 3.80)
    chk("trained vol k1 5.07", tv["k1"], 5.07); chk("trained vol random 4.89", tv["random"], 4.89)
    chk("trained alpha band low 5.89", min(ta[a] for a in CL), 5.89)
    chk("trained alpha band high 7.02", max(ta[a] for a in CL), 7.02)
    chk("trained alpha k1 5.44", ta["k1"], 5.44); chk("trained alpha random 5.33", ta["random"], 5.33)

    print("\n== tab:spanning, +ST_Rev block (§6.2, sec:spanning) ==")
    r = {a: alpha_t(books.head_avg(a), FF6 + REV, 1) for a in CL + list(CTL)}
    chk("ST_Rev trained band low 5.24", min(r[a][0] for a in CL), 5.24)
    chk("ST_Rev trained band high 6.38", max(r[a][0] for a in CL), 6.38)
    chk("ST_Rev k1 4.80", r["k1"][0], 4.80); chk("ST_Rev random 4.65", r["random"][0], 4.65)

    print("\n== §6.2 market loadings ==")
    mk = {a: alpha_t(books.head_avg(a), FF6, 1)[2] for a in CL + list(CTL)}
    chk("market beta k1 0.105", mk["k1"], 0.105, 0.0006)
    chk("market beta random 0.093", mk["random"], 0.093, 0.0006)
    chk("market beta band low 0.051", min(mk[a] for a in CL), 0.051, 0.0006)
    chk("market beta band high 0.077", max(mk[a] for a in CL), 0.077, 0.0006)

    print("\n== tab:peer (§6.3) ==")
    P = {k: books.head_book(v, 42) for k, v in (("W60", "peer_w60"), ("W252", "peer_w252"))}
    cols = {books.SHORT_NAME.get(a, a): books.head_avg(a) for a in paths.ARMS}; cols.update(P)
    M = pd.concat(cols, axis=1).join(ff[FF6].shift(1), how="inner").reindex(books.IDX)
    rules = [c for c in cols if c not in CTL and c not in P]
    for tag, xs, lo, hi, cnt in (("peer", list(P), -0.81, 1.45, 4), ("both", list(P) + FF6, -0.35, 1.68, 8)):
        X = M[xs].to_numpy(float)
        v = {a: nw_ols(M[a].to_numpy(float), X) for a in rules}
        al = {a: alpha_pct(v[a][0]) for a in rules}; tt = {a: float(v[a][1][0]) for a in rules}
        chk(f"{tag} alpha band low {lo}", min(al.values()), lo)
        chk(f"{tag} alpha band high {hi}", max(al.values()), hi)
        chk(f"{tag}: {cnt} of 12 keep |t|>1.96", sum(abs(x) > 1.96 for x in tt.values()), cnt)

    print("\n== §5.1 rulers, §5.4 equal weight ==")
    S = {a: np.array([books.sharpe(books.head_book(a, s)) for s in paths.SEEDS]) for a in CL}
    order = list(pd.Series({a: S[a].mean() for a in CL}).sort_values(ascending=False).index)
    paired = float(np.sqrt(np.mean([np.var(S[order[i]] - S[order[i + 1]], ddof=1) for i in range(len(order) - 1)])))
    level = float(np.sqrt(np.mean([S[a].var(ddof=1) for a in CL])))
    chk("paired ruler 0.103", paired, 0.103, 0.0006)
    chk("level ruler 0.168", level, 0.168, 0.0006)
    _gap = max(S[a].mean() for a in CL) - min(S[a].mean() for a in CL)
    chk("§5.1: the level ruler is 20% of the 0.83 gap (N123)", round(100 * level / _gap), 20)
    ew = sum(books.head_avg(a) for a in CL) / len(CL)
    chk("equal-weight book 2.505", books.sharpe(ew), 2.505, 0.0006)
    d = sorted(((books.sharpe(books.head_avg(a)) - books.sharpe(ew)) for a in CL), reverse=True)[:3]
    chk("above EW: 0.27 / 0.13 / 0.05", [round(x, 2) for x in d], [0.27, 0.13, 0.05])

    print("\n== §3.7 (19 arms incl. the five 21-day twins) ==")
    W21 = ["kmeans_ret", "pca_load", "spectral_unsigned", "agglo_avg", "agglo_complete"]
    arms19 = [(a, "") for a in paths.ARMS] + [(a, "_w21") for a in W21]
    B19 = {(a, v, s): books.head_book(a, s, v) for a, v in arms19 for s in paths.SEEDS}
    avg19 = {(a, v): sum(B19[(a, v, s)] for s in paths.SEEDS) / len(paths.SEEDS) for a, v in arms19}
    def rbar(d):
        return float(np.mean([float(np.corrcoef(d[i].to_numpy(float), d[j].to_numpy(float))[0, 1])
                              for i, j in itertools.combinations(sorted(d), 2)]))
    rb = rbar(avg19)
    chk("19-arm rho-bar 0.854", rb, 0.854, 0.0006)
    chk("19-arm rho-bar^2 0.729", rb ** 2, 0.729, 0.0006)
    per = [rbar({k: B19[(k[0], k[1], s)] for k in avg19}) for s in paths.SEEDS]
    chk("single-run band low 0.757", min(per), 0.757, 0.0006)
    chk("single-run band high 0.799", max(per), 0.799, 0.0006)

    print("\n== fig:window_twin (60 -> 21 days) ==")
    WT = {"kmeans_ret": -0.07, "agglo_complete": -0.31, "pca_load": -0.39,
          "agglo_avg": +0.11, "spectral_unsigned": -0.36}
    for a, want in WT.items():
        s60 = np.array([books.sharpe(books.head_book(a, s)) for s in paths.SEEDS])
        s21 = np.array([books.sharpe(books.head_book(a, s, "_w21")) for s in paths.SEEDS])
        chk(f"window move {a} {want:+.2f}", s21.mean() - s60.mean(), want)
        if a in ("pca_load", "spectral_unsigned"):   # fig:window_twin caption: each loss is 2.4 / 2.6 times the 60-day configuration's sd across head seeds (N123)
            chk(f"window loss / sd {a}", round((s60.mean() - s21.mean()) / s60.std(ddof=1), 1), {"pca_load": 2.4, "spectral_unsigned": 2.6}[a])

    print("\n== abstract / §4.1: clustering cuts book volatility by 28% to 42% in every combination (N86 add.) ==")
    _ctl = ["k1", "random"]; _cl = [a for a in paths.ARMS if a not in _ctl]
    vr = {a: books.ann_vol(books.rule_book(a)) for a in paths.ARMS}
    vs = {a: np.mean([books.ann_vol(books.head_book(a, s)) for s in paths.SEEDS]) for a in paths.ARMS}
    va = {a: books.ann_vol(books.head_avg(a)) for a in paths.ARMS}
    red = [np.mean([100 * (1 - v[a] / v[c]) for a in _cl]) for v in (vr, vs, va) for c in _ctl]
    chk("abstract: volatility cut, smallest combination 28%", round(min(red)), 28, 0.5)
    chk("abstract: volatility cut, largest combination 42%", round(max(red)), 42, 0.5)
    chk("tab:moments: rule -41.9 / -38.7, trained per-seed -35.4 / -33.0", [round(x, 1) for x in red[:4]], [41.9, 38.7, 35.4, 33.0], 0.06)
    print(f"\n{len(FAILS)} FAIL" + ("  -- " + "; ".join(FAILS) if FAILS else "  -- every printed five-seed value reproduces"))
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
