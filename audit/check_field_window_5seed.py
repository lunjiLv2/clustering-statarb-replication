"""sec:field (§5.1) and sec:window (§5.5) seed-dependent sentences, recomputed from the per-seed books at paths.SEEDS.
These were the only body sentences containing 'seed' and a digit that no other checker covered (N84 add. 1).
Run: python audit/check_field_window_5seed.py"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import numpy as np, pandas as pd, paths
from scipy import stats
from analysis import books
fails = []
def chk(name, ok, note=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  [{note}]" if note else "")); fails.append(name) if not ok else None
CL = [a for a in paths.ARMS if a not in ("k1", "random")]; S = paths.SEEDS
M = pd.DataFrame({a: [books.sharpe(books.head_book(a, s)) for s in S] for a in CL}, index=S).T
gm = M.values.mean(); arm = M.mean(1); seed = M.mean(0); tot = ((M.values - gm) ** 2).sum()
ss_seed = len(CL) * ((seed - gm) ** 2).sum(); ss_arm = len(S) * ((arm - gm) ** 2).sum(); ss_int = tot - ss_seed - ss_arm
chk("§5.1: 12x5 matrix, 27% of the variance is a shared seed shift, interaction 8%", (round(100 * ss_seed / tot), round(100 * ss_int / tot)) == (27, 8), f"{100*ss_seed/tot:.1f} {100*ss_int/tot:.1f}")
chk("§5.1: five seed means span 0.41, half the 0.83 between best and worst clusterizer", (round(seed.max() - seed.min(), 2), round(arm.max() - arm.min(), 2)) == (0.41, 0.83))
chk("§5.1: mean-of-per-seed Sharpe ratios span 1.742 to 2.567", (round(arm.min(), 3), round(arm.max(), 3)) == (1.742, 2.567))
o = arm.sort_values(ascending=False); G = np.array([[M.loc[o.index[i], s] - M.loc[o.index[i + 1], s] for s in S] for i in range(11)])
pooled = np.sqrt((G.std(axis=1, ddof=1) ** 2).mean()); df = 11 * (len(S) - 1)
ci = (pooled * np.sqrt(df / stats.chi2.ppf(0.975, df)), pooled * np.sqrt(df / stats.chi2.ppf(0.025, df)))
chk("§5.1: pooled sd of an adjacent gap across its five runs 0.103 on 44 df, 95% CI [0.085, 0.130]", round(pooled, 3) == 0.103 and df == 44 and (round(ci[0], 3), round(ci[1], 3)) == (0.085, 0.130), f"{pooled:.4f} [{ci[0]:.3f}, {ci[1]:.3f}]")
chk("§5.1: nine of the 11 adjacent gaps are smaller than 0.103", int((np.diff(-o.values) < pooled).sum()) == 9)
mv = lambda a: np.array([books.sharpe(books.head_book(a, s, "_w252")) - books.sharpe(books.head_book(a, s, "_w21")) for s in S])
sp, pc, ag = mv("spectral_unsigned"), mv("pca_load"), mv("agglo_avg")
chk("§5.5: 21->252 window: spectral +0.88, PCA loadings +0.66, average linkage -0.00; spectral and PCA positive in every seed", (round(sp.mean(), 2), round(pc.mean(), 2), round(abs(ag.mean()), 2)) == (0.88, 0.66, 0.0) and (sp > 0).all() and (pc > 0).all(), f"{sp.mean():+.4f} {pc.mean():+.4f} {ag.mean():+.4f}")
chk("§5.5: against average linkage, spectral +0.88 and PCA +0.67, the same sign in every seed", (round((sp - ag).mean(), 2), round((pc - ag).mean(), 2)) == (0.88, 0.67) and (sp - ag > 0).all() and (pc - ag > 0).all())
print(f"\n{len(fails)} FAIL" if fails else "\nall checks passed"); sys.exit(1 if fails else 0)
