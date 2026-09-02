"""sec:pseed / fig:pseed_flip / app:rules (A.1) SSSNET / app:singleton (A.2) merged arm / app:ksweep (A.6) random-partition
clause / sec:select partition-range clauses, all at the five-partition-seed basis {1,2,3,4,5} (CORRECTIONS N84, 2026-09-01).
Every printed value is recomputed from the books (rule books {arm}_ps{p}.csv, trained books {arm}_ps{p}_seed42.csv,
head seed pinned at 42) and from the within-rule ARI CSV under paths.RESULTS (the shipped analysis/results since N85).
Run: python audit/check_pseed_5ps.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd, paths
from analysis import books
PS = (1, 2, 3, 4, 5)
ST = ["kmeans_ret", "pca_load", "sssnetpre", "fv3sm_w60", "sharpe_fixed_w60", "sponge_w60", "sortino_w60", "fv2a_w60", "spectral_unsigned"]
TD = ["fv2a_w60", "fv3sm_w60", "sharpe_fixed_w60", "sortino_w60"]; OTH = ["kmeans_ret", "pca_load", "spectral_unsigned", "sponge_w60"]
fails = []
def chk(name, ok, note=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  [{note}]" if note else "")); fails.append(name) if not ok else None
R = pd.DataFrame({a: [books.sharpe(books.rule_book(a, f"_ps{p}")) for p in PS] for a in ST + ["random"]}, index=PS).T
H = pd.DataFrame({a: [books.sharpe(books.head_book(a, 42, f"_ps{p}")) for p in PS] for a in ST + ["random"]}, index=PS).T
rr, hr = (R.max(1) - R.min(1)), (H.max(1) - H.min(1))
# ARI (partition-only)
w = pd.read_csv(paths.RESULTS / "ari_within_rule_v3_cal6913.csv").set_index("arm"); x = pd.read_csv(paths.RESULTS / "ari_across_rule_v3_cal6913.csv")
within = w.loc[[a for a in ST], "ARI_mean"].mean(); across = x[x.kind == "rule-rule"].ARI.mean()
chk("sec:pseed ARI within 0.30 / across 0.19 (tab:gradient 0.296/0.193, ratio 0.65)", (round(within, 2), round(across, 2), round(within, 3), round(across, 3), round(across / within, 2)) == (0.30, 0.19, 0.296, 0.193, 0.65), f"{within:.4f} {across:.4f}")
chk("sec:pseed redraw = 87% of the disagreement a change of clusterizer produces", round(100 * (1 - within) / (1 - across)) == 87, f"{100*(1-within)/(1-across):.1f}")
chk("sec:pseed three levels: trading-driven 0.21-0.28, other four 0.32-0.45, SSSNET 0.18", (round(w.loc[TD].ARI_mean.min(), 2), round(w.loc[TD].ARI_mean.max(), 2), round(w.loc[OTH].ARI_mean.min(), 2), round(w.loc[OTH].ARI_mean.max(), 2), round(w.loc["sssnetpre", "ARI_mean"], 2)) == (0.21, 0.28, 0.32, 0.45, 0.18))
chk("ARI CSV covers the five draws (10 pair columns, 6913 days)", sum(c.startswith("ARI_ps") for c in w.columns) == 10 and set(w.days) == {6913})
# rule component
chk("rule: largest range 0.21, for k-means", round(rr[ST].max(), 2) == 0.21 and rr[ST].idxmax() == "kmeans_ret", f"{rr[ST].max():.4f} {rr[ST].idxmax()}")
sp = R.loc[ST].to_numpy().max() - R.loc[ST].to_numpy().min()
chk("rule: 45 books spread 0.58, largest range = 36% of it", round(sp, 2) == 0.58 and round(100 * rr[ST].max() / sp) == 36 and R.loc[ST].size == 45, f"{sp:.4f} {100*rr[ST].max()/sp:.1f}")
chk("rule: random moves 0.08", round(rr["random"], 2) == 0.08, f"{rr['random']:.4f}")
lead = [R.loc[ST, p].idxmax() for p in PS]; last = [R.loc[ST, p].idxmin() for p in PS]
chk("rule: spectral last at all five; k-means first at three, Sharpe (graph) and PCA once each", set(last) == {"spectral_unsigned"} and sorted(lead) == sorted(["kmeans_ret"] * 3 + ["fv3sm_w60", "pca_load"]), f"{lead}")
chk("rule: largest range grows from 0.21 to 0.38 under the head (by three quarters)", round(hr[ST].max(), 2) == 0.38 and 1.7 <= hr[ST].max() / rr[ST].max() <= 1.85, f"ratio {hr[ST].max()/rr[ST].max():.3f}")
# trained component, head seed 42
hl = [H.loc[ST, p].idxmax() for p in PS]
chk("head: k-means first at four of five draws, SPONGE at the other (seed 1); fig caption 'seeds 2 to 5'", hl == ["sponge_w60"] + ["kmeans_ret"] * 4, f"{hl}")
chk("head: largest range 0.38 for SPONGE; random moves 0.39", round(hr[ST].max(), 2) == 0.38 and hr[ST].idxmax() == "sponge_w60" and round(hr["random"], 2) == 0.39, f"{hr[ST].max():.4f} {hr['random']:.4f}")
rk_r = rr[ST].rank(ascending=False).astype(int); rk_h = hr[ST].rank(ascending=False).astype(int)
chk("SSSNET moves 0.15 (rule) / 0.13 (head), fifth-largest and smallest of nine; app:rules (A.1) band 2.398-2.527", (round(rr["sssnetpre"], 2), round(hr["sssnetpre"], 2), rk_r["sssnetpre"], rk_h["sssnetpre"]) == (0.15, 0.13, 5, 9) and (round(H.loc["sssnetpre"].min(), 3), round(H.loc["sssnetpre"].max(), 3)) == (2.398, 2.527), f"{rr['sssnetpre']:.4f} {hr['sssnetpre']:.4f} ranks {rk_r['sssnetpre']} {rk_h['sssnetpre']}")
chk("app:ksweep (A.6) clause: random partition moves 0.39 between partition draws (head pinned) vs 0.41 across head seeds", round(hr["random"], 2) == 0.39 and round(max(books.sharpe(books.head_book("random", s)) for s in paths.SEEDS) - min(books.sharpe(books.head_book("random", s)) for s in paths.SEEDS), 2) == 0.41)
chk("rule component: random (0.08) moves less than every clusterizer except Sharpe (0.007) — fact behind sec:pseed, no longer a printed sentence in sec:gradient", rr["random"] < rr[[a for a in ST if a != "sharpe_fixed_w60"]].min())
# sec:select (05_convergence.tex ~455-456): gaps to the equal-weight book vs the five-draw head ranges
CL = [a for a in paths.ARMS if a not in ("k1", "random")]
ew = books.sharpe(sum(books.head_avg(a) for a in CL) / len(CL)); gap = {a: books.sharpe(books.head_avg(a)) - ew for a in CL}
below = {"agglo_avg", "gics", "spectral_unsigned", "fv2a_w60", "sharpe_fixed_w60"}   # the five the text names as reliably below (bootstrap CI excludes zero)
chk("sec:select: the five below the EW book span 0.17-0.60", (round(min(-gap[a] for a in below), 2), round(max(-gap[a] for a in below), 2)) == (0.17, 0.60) and all(-gap[a] > 0.1 for a in below) and max(-gap[a] for a in set(CL) - below) < 0.15, f"{sorted(round(-gap[a],3) for a in below)}; next {max(-gap[a] for a in set(CL)-below):.3f}")
chk("sec:select: Sharpe (EW) gap 0.27 vs its five-draw range 0.30 (inside); k-means margin 0.27 vs range 0.29", (round(-gap["fv2a_w60"], 2), round(hr["fv2a_w60"], 2), round(gap["kmeans_ret"], 2), round(hr["kmeans_ret"], 2)) == (0.27, 0.30, 0.27, 0.29) and -gap["fv2a_w60"] < hr["fv2a_w60"], f"{-gap['fv2a_w60']:.4f} {hr['fv2a_w60']:.4f} {gap['kmeans_ret']:.4f} {hr['kmeans_ret']:.4f}")
chk("sec:select: of the five below the EW book (0.17-0.60), Sharpe (EW) is the only stochastic one not separated by its own partition range", [a for a in below if a in ST and -gap[a] < hr[a]] == ["fv2a_w60"], f"{sorted(below)}")
# A.2 merged arm at the five head seeds
S = paths.SEEDS
km = {s: books.head_book("kmeans_ret", s) for s in S}; mg = {s: books.head_book("kmeans_ret_merged", s) for s in S}
d = np.array([books.sharpe(mg[s]) - books.sharpe(km[s]) for s in S]); dv = np.array([(books.ann_vol(mg[s]) - books.ann_vol(km[s])) for s in S])
t = d.mean() / (d.std(ddof=1) / np.sqrt(len(S)))
chk("app:singleton (A.2): merged arm 0.04 less Sharpe on the five-seed average, t=-0.9 on 4 df, sign changes", round(-d.mean(), 2) == 0.04 and round(t, 1) == -0.9 and (d > 0).any() and (d < 0).any(), f"gap {d.mean():.4f} t {t:.2f} signs {np.sign(d).astype(int)}")
chk("app:singleton (A.2): 0.05 pp more volatile, per-seed gaps from 0.00 to +0.24", round(dv.mean(), 2) == 0.05 and round(dv.min(), 2) == -0.0 and round(dv.max(), 2) == 0.24, f"{dv.round(3)}")
chk("app:singleton (A.2): k-means own head-seed sd 0.112", round(np.std([books.sharpe(km[s]) for s in S], ddof=1), 3) == 0.112)
print(f"\n{len(fails)} FAIL" if fails else "\nall checks passed"); sys.exit(1 if fails else 0)
