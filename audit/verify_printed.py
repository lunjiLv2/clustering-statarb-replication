"""verify_printed.py -- one-command regression check of the manuscript's headline numbers
against the cal6913 artifacts, plus synthetic tests of the statistical kernels (N55/N57).
Run:  python verify_printed.py            (CSV-only, seconds)
      python verify_printed.py --slow     (adds the NW-vs-statsmodels check on a real book)
Every check prints PASS/FAIL; exit code = number of failures."""
import sys, os, numpy as np, pandas as pd
import pathlib, os; _ROOT = pathlib.Path(__file__).resolve().parents[1]; R = str(_ROOT); E = os.environ.get("CSA_RESULTS_ROOT", str(_ROOT / "analysis" / "results")).rstrip("/") + "/"  # repository layout (paths.py); CSA_RESULTS_ROOT selects a side directory
sys.path.insert(0, f"{R}/analysis"); sys.path.insert(0, R)
from analysis.books import RULE_REPORT_SCALE as RS   # 2026-11-10 (N123): rule-based LEVELS are printed at gross exposure one = stored value x RS
fails = []
def chk(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}  {detail}")
    if not ok: fails.append(name)
def band(s, lo, hi, nd=2): return (round(s.min(), nd), round(s.max(), nd)) == (lo, hi)

print("== tab:costs (turnover_v3_mean_cal6913) ==")
t = pd.read_csv(E+"turnover_v3_mean_cal6913.csv", index_col=0); a = t.drop(["k1","random"])
chk("gross band 1.74-2.57", band(a.gross_SR, 1.74, 2.57)); chk("return band 6.62-7.60 [B]", band(a.ann_ret*100, 6.62, 7.60))
chk("turnover band 38.2-43.8", band(a.daily_turnover_oneway_N6_convention*100, 38.2, 43.8, 1))
chk("BE band 3.17-3.79", band(a.breakeven_bps, 3.17, 3.79)); chk("net5 band -1.24..-0.67", band(a.netSR_5bp, -1.24, -0.67))
chk("k1 row", [round(t.loc["k1",c],2) for c in ("gross_SR","breakeven_bps","netSR_5bp")] == [1.28, 2.90, -0.96])
chk("random row", [round(t.loc["random",c],2) for c in ("gross_SR","breakeven_bps","netSR_5bp")] == [1.28, 2.66, -1.15])
from scipy.stats import spearmanr
chk("Spearman 14-frame 0.98/0.91 [B]", [round(spearmanr(t.gross_SR, t[c]).statistic,2) for c in ("netSR_1bp","netSR_2bp")] == [0.98, 0.91])
# 5 bp: the text says "about 0.3" and "a tie for seventh of the 14, level with spectral clustering to three decimals" (N87):
# kmeans_ret and spectral_unsigned differ by 1e-4 at 5 bp, the sign flips across seeds, and a one-day turnover convention flips 7th/8th and 0.32/0.37.
chk("Spearman 14-frame 5bp about 0.3 [B]", 0.25 <= spearmanr(t.gross_SR, t.netSR_5bp).statistic <= 0.40)
chk("kmeans/spectral tie to 3 dp at 5bp", abs(t.loc["kmeans_ret","netSR_5bp"] - t.loc["spectral_unsigned","netSR_5bp"]) < 5e-4)
chk("kmeans 7th or 8th of 14 at 5bp", list(t.netSR_5bp.sort_values(ascending=False).index).index("kmeans_ret") in (6, 7))

print("== tab:peer (peer_spanning_v3_cal6913) ==")
p = pd.read_csv(E+"peer_spanning_v3_cal6913.csv", index_col=0)
pe = p[(p.index=="peer") & ~p.arm.isin(["k1","random"])]  # five seeds: all 12 clusterizers, spectral inside the band
chk("peer alpha band -0.81-1.45", band(pe.alpha, -0.81, 1.45)); chk("peer t band -1.7-3.9", band(pe.t, -1.7, 3.9, 1))
pb = p[(p.index=="both") & ~p.arm.isin(["k1","random"])]; chk("both alpha band -0.35-1.68, t -0.7-4.5", band(pb.alpha, -0.35, 1.68) and band(pb.t, -0.7, 4.5, 1))
pf = p[(p.index=="factors") & ~p.arm.isin(["k1","random"])]; chk("factors alpha band 5.89-7.02, t 8.2-10.7", band(pf.alpha, 5.89, 7.02) and band(pf.t, 8.2, 10.7, 1))
chk("adding the factors raises every clusterizer alpha by 0.17-0.47", band((pb.set_index("arm").alpha - pe.set_index("arm").alpha), 0.17, 0.47))
k1p = p[(p.index=="peer") & (p.arm=="k1")].iloc[0]; chk("k1 peer -1.63/-2.2", (round(k1p.alpha,2), round(k1p.t,1)) == (-1.63, -2.2))
rp = p[(p.index=="peer") & (p.arm=="random")].iloc[0]; chk("random peer -1.42/-2.0", (round(rp.alpha,2), round(rp.t,1)) == (-1.42, -2.0))
for _d,_a,_t in (("both","k1",(-0.82,-1.2)),("both","random",(-0.74,-1.1)),("factors","k1",(5.44,6.8)),("factors","random",(5.33,7.1))):
    _q = p[(p.index==_d)&(p.arm==_a)].iloc[0]; chk(f"{_a} {_d} {_t[0]}/{_t[1]}", (round(_q.alpha,2), round(_q.t,1)) == _t)
for _d,_w,_t in (("reverse_EW12","W60",(2.52,5.5)),("reverse_EW12","W252",(2.32,6.8))):
    _q = p[(p.index==_d)&(p.arm==_w)].iloc[0]; chk(f"peer book {_w} on EW12 {_t[0]} ({_t[1]})", (round(_q.alpha,2), round(_q.t,1)) == _t)
sp = p[(p.index=="peer") & (p.arm=="spectral_unsigned")].iloc[0]; chk("spectral weakest on the peer books (-0.81/-1.7)", (round(sp.alpha,2), round(sp.t,1)) == (-0.81, -1.7) and pe.alpha.idxmin()==sp.name and pe.set_index("arm").alpha.idxmin()=="spectral_unsigned")
chk("factors LM max 115.1 (kmeans, head)", round(p[p.index=="factors"].LM.max(),1) == 115.1)
chk("4 of 12 sig on the peer books, 8 of 12 on both", int(pe.sig5.sum())==4 and int(pb.sig5.sum())==8)

print("== lens (lens_extras / full_stages) ==")
l = pd.read_csv(E+"lens_extras_v3_cal6913.csv"); g = l[l.arm=="gics"].iloc[0]; km = l[l.arm=="kmeans_ret"].iloc[0]
chk("gics 10 groups / 322-name / floor 0.028", (round(g.eff_K,1), round(g.lens_N), round(g.dof_floor,3)) == (10.0, 322, 0.028))
chk("kmeans after-5PC 0.160 / 60%", (round(km.R2_after_5PC,3), round(km.ret_5PC*100)) == (0.160, 60))
cl = l[~l.arm.isin(["k1","random"])]; chk("block-bootstrap SE band 0.001-0.005", (round(cl[[c for c in l.columns if c.startswith("se_")]].min().min(),3), round(cl[[c for c in l.columns if c.startswith("se_")]].max().max(),3)) == (0.001, 0.005))
chk("5PC retention band 44-61%", band(cl.ret_5PC*100, 44, 61, 0))
f = pd.read_csv(E+"lens_v3_full_stages_cal6913.csv"); kf = f[f.arm=="kmeans_ret"].iloc[0]
chk("kmeans FF stages .246/.206/.185/.178", [round(kf[c],3) for c in ("R2_after_CAPM","R2_after_FF3","R2_after_FF5","R2_after_FF6")] == [0.246, 0.206, 0.185, 0.178])
chk("FF6 retention band 50-68%", band(f[~f.arm.isin(["k1","random"])].ret_FF6*100, 50, 68, 0))

print("== era ratios (SET19) ==")
e = pd.read_csv(E+"era_ratios_v3_cal6913.csv", index_col=0); s19 = e[e.index.str.startswith("19")]
chk("vol ratios 13..21x", (round(s19.ratio_vol.min()), round(s19.ratio_vol.max())) == (13, 21))
chk("mean ratios 2.2 -> 0.6", round(s19.ratio_mean.iloc[0],1)==2.2 and round(s19.ratio_mean.iloc[-1],1)==0.6)
# five seeds: 2010-2016 is 0.979, i.e. also (just) below one; the §3.7 clause "fall below one only there" is a three-seed leftover (1.010 then)  3seed-ok: history of the clause fixed in N84
chk("mean ratio below one in the last two periods only, 0.98 and 0.63 (printed §3.7 clause, N84)", list(s19.ratio_mean<1)==[False,False,True,True] and [round(x,2) for x in s19.ratio_mean.iloc[2:]]==[0.98,0.63], f"periods below one: {list(s19.era[s19.ratio_mean<1])} ({[round(x,3) for x in s19.ratio_mean[s19.ratio_mean<1]]})")

print("== tab:formal (five-seed targets since N83; shipped CSVs five-seed since N85) ==")
fs = pd.read_csv(E+"formal_v3_intersect_summary.csv")
_d90 = fs[(fs["resample"]=="overlap_cbb")&(fs.level=="90%")].set_index("stat").n_retained
chk("MCS 90%: keeps 6 under Tmax and 2 under TR (tab:formal row 1, §5.3)", (int(_d90["Tmax"]), int(_d90["TR"])) == (6, 2))
_n90 = fs[(fs["resample"]=="nonoverlap_21d_agg")&(fs.level=="90%")].set_index("stat").n_retained
chk("21d MCS 90% keeps 11 under Tmax", int(_n90["Tmax"]) == 11)
# tab:formal row 4 and §5.3 print "the 90% set keeps 11 of the 12" with NO statistic named; at three seeds Tmax and TR both kept 11,
# so the clause was exact. At five seeds TR keeps 9, so the unqualified "11" is a three-seed leftover (row 1 does name both statistics).
chk(f"21d MCS 90% keeps 11 under Tmax and 9 under TR (tab:formal row 4, §5.3; N84); measured Tmax {int(_n90['Tmax'])}, TR {int(_n90['TR'])}", (int(_n90["Tmax"]), int(_n90["TR"])) == (11, 9))
chk("spread 0.8758 -> 0.4044", (round(fs.spread_point.iloc[0],4), round(fs[fs["resample"]=="nonoverlap_21d_agg"].spread_boot_mean.iloc[0],4)) == (0.8758, 0.4044))
tw = fs.dropna(subset=["twin_diff"]).iloc[0]; chk("twin Sortino-Sharpe +0.1260 (s.e. 0.0919)", (round(tw.twin_diff*np.sqrt(252),4), round(tw.twin_se*np.sqrt(252),4)) == (0.1260, 0.0919))
ov = pd.read_csv(E+"formal_v3_intersect_pairs_overlap_cbb.csv"); no = pd.read_csv(E+"formal_v3_intersect_pairs_nonoverlap_21d_agg.csv")
adj = ov.adjacent.astype(str).str.strip().eq("True")
chk("Holm 21/66, 0 adjacent; 21d 1/66", (int((ov.holm<.05).sum()), int(((ov.holm<.05)&adj).sum()), int((no.holm<.05).sum())) == (21, 0, 1))
_ca = ov[adj].sort_values("p_boot").iloc[0]
chk("closest adjacent pair gics vs spectral: raw p 0.004 -> Holm 0.15", {_ca.i, _ca.j} == {"gics", "spectral_unsigned"} and round(_ca.p_boot, 3) == 0.004 and round(_ca.holm, 2) == 0.15)
_fc = pd.read_csv(E+"formal_v3_intersect_ctl_pairs_overlap_cbb.csv"); _fn = pd.read_csv(E+"formal_v3_intersect_ctl_pairs_nonoverlap_21d_agg.csv")
def _above_both(df):
    c = df[df.j.isin(["k1", "random"]) & ~df.i.isin(["k1", "random"])]
    return int((c.groupby("i")["diff"].min() > 0).sum())
chk("every clusterizer above both controls at both horizons: 12 of 12", (_above_both(_fc), _above_both(_fn)) == (12, 12))

print("== dose / naive ==")
d = pd.read_csv(E+"dose_v3_traded_cal6913.csv"); q0 = d[d.q==0].iloc[0]; rr = d[d.draw==-1].iloc[0]
chk("dose q0 19.1% / 2.60 (gross one) / floor 5.88 / N 494.3", (round(q0.removal_share*100,1), round(q0.ann_vol*100*RS,2), round(q0.dof_floor*100,2), round(q0.traded_N,1)) == (19.1, 2.60, 5.88, 494.3))
_d1 = d[(d.q==1.0)&(d.draw>=0)]; chk("app:dose: q=1 volatility 4.42 (gross one, mean of the two draws)", round(_d1.ann_vol.mean()*100*RS,2) == 4.42)
chk("random control 5.93%", round(rr.removal_share*100,2) == 5.93)
nv = pd.read_csv(E+"naive_turnover_v3_cal6913.csv", index_col=0)
chk("naive k1 0.83 / random 0.89", (round(nv.loc["k1","naive_SR"],2), round(nv.loc["random","naive_SR"],2)) == (0.83, 0.89))
chk("naive 5bp: k1 1st, random 3rd", list(nv.netSR_5bp.sort_values(ascending=False).index[:3]) == ["k1","gics","random"])
chk("rule per-gross return 3.9-4.6%", band(nv.ann_ret*100/2, 3.9, 4.6, 1))


print("== vshare (traded-universe removal share, vshare_v3_cal6913) ==")
vs = pd.read_csv(E+"vshare_v3_cal6913.csv").set_index("arm").removal_share*100
chk("gics 10.8 / kmeans 26.4", round(vs["gics"],1)==10.8 and round(vs["kmeans_ret"],1)==26.4)
mid = vs.drop(["gics","kmeans_ret","k1","random"])  # OPTION B: sssnet is one row (sssnet_w60)
chk("middle ten 17.0-19.1", round(mid.min(),1)==17.0 and round(mid.max(),1)==19.1 and len(mid)==10)
chk("random 5.93 (vshare)", round(vs["random"],2)==5.93)


print("== tab:split (split_v3_cal6913) ==")
sx = pd.read_csv(E+"split_v3_cal6913.csv"); cell = lambda l,c,k: sx[(sx.layer==l)&(sx.conv==k)&(sx.control==c)].iloc[0]
chk("head/perseed/k1 vol share 82.0", round(cell("head","k1","perseed").vol_share_pct,1)==82.0)
chk("tab:split trained rows 0.533/0.096/0.437/82.0 and 0.532/0.131/0.401/75.4", [round(cell("head","k1","perseed")[c],3) for c in ("logSR_gap","mean_part","vol_part")]==[0.533,0.096,0.437] and [round(cell("head","random","perseed")[c],3) for c in ("logSR_gap","mean_part","vol_part")]==[0.532,0.131,0.401] and round(cell("head","random","perseed").vol_share_pct,1)==75.4)
chk("rule/random vol share 83.0 (largest) [B]", round(cell("rule","random","-").vol_share_pct,1)==83.0 and sx.vol_share_pct.idxmax()==sx[(sx.layer=="rule")&(sx.control=="random")].index[0]); sx4 = sx[sx.conv!="seedavg"]
chk("four-cell band 75-83, largest rule/random", round(sx4.vol_share_pct.min())==75 and round(sx4.vol_share_pct.max())==83)
chk("trained cells: lowest arm fv3sm vs K=1, gics vs random down to 68%; no other clusterizer below 69% in any cell", cell("head","k1","perseed").perarm_min_arm=="fv3sm_w60" and cell("head","random","perseed").perarm_min_arm=="gics" and round(cell("head","random","perseed").gics_vol_share_pct)==68 and round(sx4.perarm_min_excl_gics_pct.min())==69)
chk("alpha-paired mean share 29.4 / 33.6", round(cell("head","k1","perseed").alpha_mean_share_pct,1)==29.4 and round(cell("head","random","perseed").alpha_mean_share_pct,1)==33.6)


SF = None
print("== sssnet 3x3 factorial (sssnet_factorial_v3; repo-only, no printed table -- CORRECTIONS N84) ==")
try:
    import sssnet_factorial_v3 as SF
    chk("3x3 cells", [round(x,4) for x in SF.T.values.ravel()] == [2.7071,2.6475,2.7086,2.4998,2.4732,2.5506,2.7936,2.4511,2.8180])
    chk("head range 0.18 / pooled 0.13", round(SF.out["head_range"],2)==0.18 and round(SF.out["head_pooled_sd"],2)==0.13)
    chk("partition range 0.17 / pooled 0.12", round(SF.out["part_range"],2)==0.17 and round(SF.out["part_pooled_sd"],2)==0.12)
except FileNotFoundError:
    print("  SKIP  sssnet factorial (3 checks)  [needs the daily head logs in data/derived (layer L1)]")
if SF is not None: chk("SS shares 42/32/26", [round(100*SF.out[k]) for k in ("ss_head","ss_part","ss_inter")] == [42,32,26])


print("== rule-layer spanning / era (rule_spanning_era_v3) [B] ==")
rs = pd.read_csv(E+"rule_spanning_era_v3_cal6913.csv"); A12 = ["kmeans_ret","pca_load","agglo_avg","agglo_complete","spectral_unsigned","gics","sponge_w60","fv2a_w60","fv3sm_w60","sharpe_fixed_w60","sortino_w60","sssnet_w60"]
rf = rs[(rs.component=="rule")&(rs.era=="full")].set_index("arm"); hf = rs[(rs.component=="head")&(rs.era=="full")].set_index("arm")
chk("tab:spanning rule alpha 4.03-4.40 at gross one / t 6.4-7.6 (LM columns withdrawn N78-8; N123)", band(RS*rf.loc[A12].alpha, 4.03, 4.40) and band(rf.loc[A12].t, 6.4, 7.6, 1))
chk("tab:spanning / tab:moments rule K=1 3.63 (4.1), random 3.72 (4.4) at gross one", (round(RS*rf.loc["k1","alpha"],2), round(rf.loc["k1","t"],1), round(RS*rf.loc["random","alpha"],2), round(rf.loc["random","t"],1)) == (3.63, 4.1, 3.72, 4.4))
chk("tab:moments advantages (was tab:signal) +15.6/+13.1 and +20.0/+22.5", [round(100*(rf.loc[A12].alpha.mean()/rf.loc[c,"alpha"]-1),1) for c in ("k1","random")]==[15.6,13.1] and [round(100*(hf.loc[A12].alpha.mean()/hf.loc[c,"alpha"]-1),1) for c in ("k1","random")]==[20.0,22.5])
r1 = rs[(rs.component=="rule")&(rs.era=="1997-2008")].set_index("arm"); h2 = rs[(rs.component=="head")&(rs.era=="2009-2024")].set_index("arm"); h1 = rs[(rs.component=="head")&(rs.era=="1997-2008")].set_index("arm")
chk("tab:era rule 1997-2008 alpha 7.1-8.1 at gross one (N123)", band(RS*r1.loc[A12].alpha, 7.1, 8.1, 1))
r2 = rs[(rs.component=="rule")&(rs.era=="2009-2024")].set_index("arm")
chk("tab:era rule rows at gross one: sigma 2.6-3.3 / 2.2-3.0, alpha 2009-24 1.7-2.2; K=1 6.45 5.2 1.82 4.2; random 6.52 4.9 1.89 4.0 (N123)",
    band(RS*r1.loc[A12].vol, 2.6, 3.3, 1) and band(RS*r2.loc[A12].vol, 2.2, 3.0, 1) and band(RS*r2.loc[A12].alpha, 1.7, 2.2, 1)
    and (round(RS*r1.loc["k1","alpha"],2), round(RS*r1.loc["k1","vol"],1), round(RS*r2.loc["k1","alpha"],2), round(RS*r2.loc["k1","vol"],1)) == (6.45, 5.2, 1.82, 4.2)
    and (round(RS*r1.loc["random","alpha"],2), round(RS*r1.loc["random","vol"],1), round(RS*r2.loc["random","alpha"],2), round(RS*r2.loc["random","vol"],1)) == (6.52, 4.9, 1.89, 4.0))
_all = pd.concat([RS*r1.alpha, h1.alpha]); _all2 = pd.concat([RS*r2.alpha, h2.alpha])
chk("§6.2 era: alphas fall from 6%-12% (all 28, gross one) to below 4% (N123)", (round(_all.min()), round(_all.max())) == (6, 12) and _all2.max() < 4 and len(_all) == 28 and len(_all2) == 28)
chk("era advantage over K=1: +29.3 (2009-24) vs +20.2 (pre)", round(100*(h2.loc[A12].alpha.mean()/h2.loc["k1","alpha"]-1),1)==29.3 and round(100*(h1.loc[A12].alpha.mean()/h1.loc["k1","alpha"]-1),1)==20.2)


print("== tab:gradient payoff row (12 arms) [B] ==")
import itertools as _it
from analysis import books as _bk
_A = ["kmeans_ret","agglo_complete","fv3sm_w60","sponge_w60","pca_load","agglo_avg","sortino_w60","fv2a_w60","sharpe_fixed_w60","gics","spectral_unsigned","sssnetpre"]
# The seed set comes from paths, not a literal: this check carried (42,1,123) and the three-seed
# target 0.808/0.800/1.01 after the table moved to five seeds, so BOTH sides were three-seed and it
# passed while guarding nothing the paper prints (CORRECTIONS N83 add. 1).
import paths as _paths
_S = tuple(_paths.SEEDS)
try:
    _P = {(a,s): _bk.head_book(a, s) for a in _A for s in _S}
    _off = np.mean([np.corrcoef(_P[(a,s)],_P[(b,s)])[0,1] for a,b in _it.combinations(_A,2) for s in _S]); _dia = np.mean([np.corrcoef(_P[(a,s1)],_P[(a,s2)])[0,1] for a in _A for s1,s2 in _it.combinations(_S,2)])
    chk("payoff row 0.815 / 0.805 / 1.01", (round(_off,3), round(_dia,3), round(_off/_dia,2)) == (0.815, 0.805, 1.01))
except FileNotFoundError as _e:
    print(f"  SKIP  payoff row 0.815 / 0.805 / 1.01  [needs the daily head logs in data/derived (layer L1): {os.path.basename(str(_e).split(chr(39))[1]) if chr(39) in str(_e) else _e}]")


print("== MC size (mc_size_v3_B5000_s{42,7,101,2024}) [B, per-book rng] ==")
from scipy.stats import chi2 as _chi2
_mc = pd.concat([pd.read_csv(E+f"mc_size_v3_B5000_s{s}.csv") for s in (42,7,101,2024)]); _pb = _mc.groupby(["layer","arm"]).size_arlm.mean()
_pw = _mc.groupby(["layer","arm"]).size_waldt.mean(); _rs28 = pd.read_csv(E+"rule_spanning_era_v3_cal6913.csv"); _rs28 = _rs28[_rs28.era=="full"]
chk("three-seed mc_size files (not printed since the five-seed migration): 6.5%, 5.4-7.8%", set(_mc.days)=={6913} and round(100*_mc.size_waldt.mean(),1)==6.5 and (round(100*_pw.min(),1), round(100*_pw.max(),1))==(5.4,7.8))  # 3seed-ok: the mc_size files are three-seed by construction and unprinted (N83 add. 1)
# printed app:size (A.11) / §6.2 (five seeds): size_critical_v3 per master seed, mean over the four seeds per book, then min/max over the 28 books and mean over books
import glob as _glob
_s5 = sorted(_glob.glob(E+"size5/size_crit_5seed_s*.csv"))
if _s5:
    # the smallest per-book size (trained k1) is exactly 5.350% (mean of 0.0562/0.0514/0.0530/0.0534): a rounding tie, printed as 5.3%
    _d5 = pd.concat([pd.read_csv(f).assign(ms=f[-8:-4]) for f in _s5]); _b5 = _d5.groupby(["layer","arm"])[["size","crit95"]].mean(); _w5 = _b5["size"].idxmax()
    chk("app:size (A.11) five-seed size: pooled 6.6%, book by book 5.3-7.6%, corrected crit 2.2 (worst book trained fv3sm), smallest FF5+MOM t 4.1", len(_s5)==4 and round(100*_b5["size"].mean(),1)==6.6 and abs(100*_b5["size"].min()-5.35)<1e-9 and round(100*_b5["size"].max(),1)==7.6 and round(_b5.loc[_w5,"crit95"],1)==2.2 and _w5==("trained","fv3sm") and round(_rs28.t.abs().min(),1)==4.1)
else:
    chk("app:size (A.11) five-seed size files present (analysis/results/size5/)", False, "run analysis/size_critical_v3.py --seed {42,7,101,2024} --out analysis/results/size5/")


print("== lens universe sizes (lens_v3_full_stages) ==")
lu = pd.read_csv(E+"lens_v3_full_stages_cal6913.csv").set_index("arm").lens_N
chk("lens N: 11 clusterizers 479-500, gics 322; traded 494", (round(lu.drop(["gics","k1","random"]).min()), round(lu.drop(["gics","k1","random"]).max()), round(lu["gics"])) == (479,500,322) and round(pd.read_csv(E+"vshare_v3_cal6913.csv").traded_N.iloc[0]) == 494)

print("== LM null-imposed block bootstrap p (lm_boot_v3_cal6913_s42) [N77] ==")
_lb = pd.read_csv(E+"lm_boot_v3_cal6913_s42.csv"); chk("[diagnostic, not printed since N78-8] LM bootstrap p at most 0.001", len(_lb)==28 and _lb.p_boot.max() <= 0.001)

print("== rule at the head's 30-day signal window (rule_sigw30_spanning_cal6913) [N77] ==")
_r30 = pd.read_csv(E+"rule_sigw30_spanning_cal6913.csv").set_index("arm")
# N99: the CSV's alpha_head / gain_* columns were computed at the superseded head-seed set (CORRECTIONS N77); the head side is taken from the five-seed spanning file instead.
_r30h = pd.read_csv(E+"rule_spanning_era_v3_cal6913.csv"); _r30h = _r30h[_r30h.era=="full"].set_index(["component","arm"]).alpha
_r30 = _r30.rename(index={"sssnetpre":"sssnet_w60"}); _r30["head5"] = [_r30h[("head",a)] for a in _r30.index]; _r30["rule5"] = [_r30h[("rule",a)] for a in _r30.index]
_g5 = _r30.head5 - _r30.rule5/2; _g30 = _r30.head5 - _r30.alpha_rule30/2
chk("head-minus-rule/2 alpha gain widens at all 14 arms with a 30-day rule [five-seed head]", len(_r30)==14 and (_g30 > _g5).all() and (_g30 > 0).all())
_c12 = [a for a in _r30.index if a not in ("k1","random")]
chk("§4.4: 30-day rule widens the relative advantage to +38.7/+35.8%", tuple(round(100*(_r30.loc[_c12,"alpha_rule30"].mean()/_r30.loc[c,"alpha_rule30"]-1),1) for c in ("k1","random")) == (38.7, 35.8))
chk("§4.4: 30-day rule alphas at the head's gross run 1.4-2.3% across the 14 arms; control t = 1.6 and 1.7", band(_r30.alpha_rule30/2, 1.4, 2.3, 1) and (round(_r30.loc["k1","t_rule30"],1), round(_r30.loc["random","t_rule30"],1)) == (1.6, 1.7))
_gap = {(w,c): (_r30.loc[_c12,col].mean() - _r30.loc[c,col])/div for w,col,div in (("head","head5",1),("rule5","rule5",2),("rule30","alpha_rule30",2)) for c in ("k1","random")}
chk("§4.4: 30-day window moves the rule's gap to either control by at most 0.04 points", max(abs(_gap[("rule30",c)]-_gap[("rule5",c)]) for c in ("k1","random")) <= 0.04)
_rat = [_gap[("head",c)]/_gap[(w,c)] for w in ("rule5","rule30") for c in ("k1","random")]
chk("§4.4: head's gap is 1.9-2.5 times the rule's at either window (roughly twice)", (round(min(_rat),1), round(max(_rat),1)) == (1.9, 2.5) and all(1.5 < r < 3 for r in _rat))

print("== §4.1 own-dispersion counts (perrule_count_v3_cal6913, paths.SEEDS) [N77-2, N83 add. 2] ==")
# head_alpha_perseed_cal6913.csv is an orphan three-seed file (seeds 42/1/123, no producer in the repo); the printed counts come from perrule_count_v3.py.  3seed-ok: orphan file, documented not consumed
_pc = pd.read_csv(E+"perrule_count_v3_cal6913.csv"); _pk = _pc[_pc.control=="k1"]; _pr = _pc[_pc.control=="random"]
chk("both advantages positive at every one of the 12 clusterizers", bool((_pc["mean"] > 0).all()) and len(_pk) == 12 and len(_pr) == 12)
chk("advantage > 2x own five-seed dispersion: 4 of 12 vs K=1, 7 of 12 vs random", (int(_pk.clears_own.sum()), int(_pr.clears_own.sum())) == (4, 7))
chk("same counts under the pooled dispersion, though not the same four", (int(_pk.clears_pooled.sum()), int(_pr.clears_pooled.sum())) == (4, 7) and set(_pk.rule[_pk.clears_own]) != set(_pk.rule[_pk.clears_pooled]))
chk("perrule_count carries one adv_s<seed> column per seed in paths.SEEDS", [c for c in _pc.columns if c.startswith("adv_s")] == [f"adv_s{s}" for s in _paths.SEEDS])

print("== §5.4 selection rules vs EW (select_ci_v3_cal6913) [N78] ==")
_sc = pd.read_csv(E+"select_ci_v3_cal6913.csv"); chk("trailing 1/3/5-year winner: 26 reselections each, gap CI covers zero at every look-back", set(_sc.reselections)=={26} and bool(_sc.covers_zero.all()) and round(_sc.SR_ew.iloc[0],3)==2.505)

print("== app:size (A.11) cumulated serial dependence (serial_dep_v3, cal6913) [N78] ==")
_sd = pd.read_csv(E+"serial_dep_v3.csv"); _g = _sd.groupby("layer").acf_sum_1_21.mean(); _rat = _g["trained"]/_g["rule"]
# app:size now prints no numbers, only "dependence cumulated over the 21 lags is about half again as large in the trained books" (the 0.64/0.33, "twice" of N78 add. 3 were removed with the LM block).
# "about half again" = a ratio near 1.5; three-seed 0.644/0.325 = 1.98 ("twice"), five-seed 0.557/0.325 = 1.71. The clause matches neither seed set exactly.  3seed-ok: history of the A.10 clause fixed in N84
chk(f"app:size (A.11) rule cumulated |acf| 0.33 (seed-free)", set(_sd.days)=={6913} and round(_g["rule"],2)==0.33)
chk(f"app:size (A.11) 'about 1.7 times as large' (N84); measured trained {_g['trained']:.3f} / rule {_g['rule']:.3f} = {_rat:.2f}", round(_rat, 1) == 1.7)

print("== app:lensrobust (A.10) footnote 0.216 (vshare_v3_nosingleton_cal6913, k-means, singleton members excluded) [N77] ==")
_ns = pd.read_csv(E+"vshare_v3_nosingleton_cal6913.csv").set_index("arm"); chk("k-means singleton-excluded removal share 0.216", round(_ns.loc["kmeans_ret","removal_share"],3)==0.216 and int(_ns.loc["kmeans_ret","days"])==6913)

print("== §6.4 turnover conventions (naive_turnover / turnover_v3) [N78-17] ==")
_nv2 = pd.read_csv(E+"naive_turnover_v3_cal6913.csv", index_col=0); _tv2 = pd.read_csv(E+"turnover_v3_mean_cal6913.csv", index_col=0)
chk("rule one-way per unit gross 23.1-30.8%; head 38.2-46.9%; turnover spread 23% vs Sharpe spread 101%", (round(100*_nv2.turnover_twoway_per_unit_gross.min()/2,1), round(100*_nv2.turnover_twoway_per_unit_gross.max()/2,1))==(23.1,30.8) and (round(100*_tv2.daily_turnover_oneway_N6_convention.min(),1), round(100*_tv2.daily_turnover_oneway_N6_convention.max(),1))==(38.2,46.9) and round(100*(_tv2.daily_turnover_oneway_N6_convention.max()/_tv2.daily_turnover_oneway_N6_convention.min()-1))==23 and round(100*(_tv2.gross_SR.max()/_tv2.gross_SR.min()-1))==101)

print("== tab:spanning ST_Rev block / tab:k1span (strev_spanning_v3, k1_regressor_v3) [N79/N80] ==")
_st = pd.read_csv(E+"strev_spanning_v3_cal6913.csv"); _stf = _st[_st.era=="full"]
def _blk(comp):
    c = _stf[(_stf.component==comp)&~_stf.arm.isin(["k1","random"])]; k = _stf[(_stf.component==comp)&(_stf.arm=="k1")].iloc[0]; r = _stf[(_stf.component==comp)&(_stf.arm=="random")].iloc[0]
    f = RS if comp == "rule" else 1.0   # alpha and the reversal loading are levels: printed at gross one for the rule-based component (N123)
    return (band(f*c.alpha7,*{"rule":(3.09,3.50),"head":(5.24,6.38)}[comp]) and band(c.t7,*{"rule":(5.3,6.6),"head":(7.5,10.4)}[comp],1) and band(f*c.beta_strev,*{"rule":(0.08,0.11),"head":(0.05,0.07)}[comp])
            and (round(f*k.alpha7,2),round(k.t7,1),round(f*r.alpha7,2),round(r.t7,1)) == {"rule":(2.11,2.5,2.29,2.8),"head":(4.80,6.1,4.65,6.3)}[comp]
            and (round(f*k.beta_strev,2),round(f*r.beta_strev,2)) == {"rule":(0.15,0.14),"head":(0.06,0.07)}[comp])
chk("tab:spanning +ST_Rev block: rule 3.09-3.50 / 5.3-6.6 / 0.08-0.11, K=1 2.11 (2.5) beta 0.15, random 2.29 (2.8) beta 0.14 (gross one, N123)", _blk("rule"))
chk("tab:spanning +ST_Rev block: head 5.24-6.38 / 7.5-10.4 / 0.05-0.07, K=1 4.80 (6.1) beta 0.06, random 4.65 (6.3) beta 0.07", _blk("head"))
_sh = _stf.assign(share=1-_stf.alpha7/_stf.alpha6); _shr = _sh[_sh.component=="rule"].set_index("arm"); _shh = _sh[_sh.component=="head"].set_index("arm")
chk("§6.2/§1 reversal share of alpha: rule clusterizers 20-25%, controls 38-42%, trained 8-13%, at most 42% of any portfolio (N123)",
    (round(100*_shr.drop(["k1","random"]).share.min()), round(100*_shr.drop(["k1","random"]).share.max())) == (20, 25)
    and (round(100*_shr.loc["random","share"]), round(100*_shr.loc["k1","share"])) == (38, 42)
    and (round(100*_shh.share.min()), round(100*_shh.share.max())) == (8, 13) and round(100*_sh.share.max()) == 42 and len(_sh) == 28)
_rk1 = _stf[(_stf.component=="rule")&(_stf.arm=="k1")].iloc[0]; _crs = _stf[(_stf.component=="rule")&~_stf.arm.isin(["k1","random"])]
chk("§6.2 text: K=1 alpha falls from 3.63% to 2.11%; every clusterizer stays at 3.09% or more (gross one, N123)", (round(RS*_rk1.alpha6,2), round(RS*_rk1.alpha7,2), round(RS*_crs.alpha7.min(),2)) == (3.63, 2.11, 3.09))
_e2 = _st[(_st.era=="2009-2024")&(_st.component=="rule")]; chk("era 2009-24 seven-factor rule: 12 t 2.6-3.6, K=1 1.5, random 1.7", band(_e2[~_e2.arm.isin(["k1","random"])].t7,2.6,3.6,1) and round(_e2[_e2.arm=="k1"].t7.iloc[0],1)==1.5 and round(_e2[_e2.arm=="random"].t7.iloc[0],1)==1.7)
_e3 = _st[(_st.era=="2009-2024")&(_st.component=="head")]; chk("era 2009-24 seven-factor trained: 12 t 2.3-5.3, K=1 2.1, random 2.2 (§6.2 sec:spanning sentence, N86)", band(_e3[~_e3.arm.isin(["k1","random"])].t7,2.3,5.3,1) and round(_e3[_e3.arm=="k1"].t7.iloc[0],1)==2.1 and round(_e3[_e3.arm=="random"].t7.iloc[0],1)==2.2)
_k1 = pd.read_csv(E+"k1_regressor_v3_cal6913.csv")
for _c,_v in (("rule",(2.24,2.86,6.9,8.2,0.34,2.3)),("head",(2.39,4.70,5.8,9.4,0.40,1.7))):
    _f = RS if _c == "rule" else 1.0   # N123: rule-based alphas printed at gross one; beta (book on book), t and R2 are scale-free
    _cc = _k1[(_k1.component==_c)&(_k1.arm!="random")]; _rr = _k1[(_k1.component==_c)&(_k1.arm=="random")].iloc[0]
    chk(f"tab:k1span {_c}: alpha {_v[0]}-{_v[1]}, t {_v[2]}-{_v[3]}, random {_v[4]} ({_v[5]}); 12/12 significant", band(_f*_cc.alpha_on_k1,_v[0],_v[1]) and band(_cc.t_on_k1,_v[2],_v[3],1) and (round(_f*_rr.alpha_on_k1,2),round(_rr.t_on_k1,1))==(_v[4],_v[5]) and int((_cc.t_on_k1.abs()>1.96).sum())==12 and len(_cc)==12)

_k1c = {"rule":((0.37,0.59),(0.53,0.81),(2.19,2.84),(6.9,8.3),(0.93,0.97,0.32,2.1)), "head":((0.42,0.65),(0.48,0.69),(2.46,4.77),(5.8,9.5),(0.90,0.92,0.39,1.7))}   # rule +FF6 alphas at gross one (N123)
for _c,(_b,_r2,_a6,_t6,_rn) in _k1c.items():
    _cc = _k1[(_k1.component==_c)&(_k1.arm!="random")]; _rr = _k1[(_k1.component==_c)&(_k1.arm=="random")].iloc[0]
    chk(f"tab:k1span {_c}: beta {_b[0]}-{_b[1]}, R2 {_r2[0]}-{_r2[1]}, +FF6 alpha {_a6[0]}-{_a6[1]} t {_t6[0]}-{_t6[1]}; random beta {_rn[0]} R2 {_rn[1]} +FF6 {_rn[2]} ({_rn[3]})",
        band(_cc.beta_k1,*_b) and band(_cc.R2_k1,*_r2) and band((RS if _c=="rule" else 1.0)*_cc.alpha_on_k1_ff6,*_a6) and band(_cc.t_on_k1_ff6,*_t6,1) and (round(_rr.beta_k1,2),round(_rr.R2_k1,2),round((RS if _c=="rule" else 1.0)*_rr.alpha_on_k1_ff6,2),round(_rr.t_on_k1_ff6,1))==_rn)
_a6 = _stf.set_index(["component","arm"]).alpha6
for _c,_lo,_hi,_rn in (("rule",52,68,9),("head",41,68,8)):
    _kk = _k1[_k1.component==_c].set_index("arm"); _pc = 100*_kk.alpha_on_k1/_a6.loc[_c].reindex(_kk.index)
    chk(f"§1/§6.2 alpha kept against the K=1 portfolio, {_c}: clusterizers {_lo}%-{_hi}%, random {_rn}% (N123: §1 prints 41%-68% and 8%-9%)", (round(_pc.drop("random").min()), round(_pc.drop("random").max()), round(_pc["random"])) == (_lo,_hi,_rn) and len(_pc)==13)

# N111: §6.2:137 / §1:106 share of the FF5+MOM alpha (tab:spanning, strev_spanning alpha6, era full) that a clusterizer keeps against the K=1 book (tab:k1span alpha_on_k1); §1 words it "between two fifths and two thirds"
for _c,_lo,_hi in (("rule",52,68),("head",41,68)):
    _sh = _k1[(_k1.component==_c)&(_k1.arm!="random")].merge(_stf[(_stf.component==_c)][["arm","alpha6"]], on="arm", how="inner"); assert len(_sh)==12, (_c, len(_sh))  # arm names agree across the two producers (sssnetpre in both)
    _pct = 100*_sh.alpha_on_k1/_sh.alpha6
    chk(f"§6.2 alpha kept against the K=1 book, {_c}: {_lo}%-{_hi}% of the FF5+MOM alpha (12 arms; §1 prints the pooled 41%-68%, N123)", (round(_pct.min()), round(_pct.max()))==(_lo,_hi))

print("== N123 (2026-11-10): rule-based levels at gross one, and the percentages that replaced verbal fractions ==")
_nt = pd.read_csv(E+"naive_turnover_v3_cal6913.csv", index_col=0); _ntc = _nt.drop(["k1","random"]); assert len(_ntc) == 12
chk("tab:moments rule volatility 2.38-3.09, K=1 4.65, random 4.41, mean 2.70 (gross one)", band(100*RS*_ntc.ann_vol, 2.38, 3.09) and (round(100*RS*_nt.loc["k1","ann_vol"],2), round(100*RS*_nt.loc["random","ann_vol"],2), round(100*RS*_ntc.ann_vol.mean(),2)) == (4.65, 4.41, 2.70))
_rf6 = _stf[(_stf.component=="rule")&~_stf.arm.isin(["k1","random"])]
chk("tab:moments rule alpha 4.03-4.40, mean 4.20 (gross one)", band(RS*_rf6.alpha6, 4.03, 4.40) and round(RS*_rf6.alpha6.mean(),2) == 4.20 and len(_rf6) == 12)
_vr = [round(100*(1-_ntc.ann_vol.mean()/_nt.loc[c,"ann_vol"])) for c in ("k1","random")]
chk("§1: rule-based portfolio 39%-42% less volatile than either control", sorted(_vr) == [39, 42])
_le = pd.read_csv(E+"lens_extras_v3_cal6913.csv", index_col=0).drop(["k1","random"]); _lf = pd.read_csv(E+"lens_v3_full_stages_cal6913.csv", index_col=0).drop(["k1","random"])
chk("§6.1/§6.2/§1/§7: five PCs absorb 39%-56% of a real partition's variance share; FF6 at most 50%", (round(100*(1-_le.ret_5PC.max())), round(100*(1-_le.ret_5PC.min()))) == (39, 56) and round(100*(1-_lf.ret_FF6.min())) == 50 and len(_le) == 12 and len(_lf) == 12)
_er = pd.read_csv(E+"era_ratios_v3_cal6913.csv"); _rho = float(_er[_er.armset.astype(str).str.startswith("19")].rho_bar.iloc[0])
chk("§3.7 footnote: using rho in place of rho^2 raises the volatility ratios by 36% (factor sqrt(1+rho))", round(100*(np.sqrt(1+_rho)-1)) == 36)
_pcr = pd.read_csv(E+"pc_spanning_v3_cal6913.csv"); _pcr = _pcr[(_pcr.component=="rule")&(_pcr.design=="ff6")].set_index("arm")
chk("§6.2 rule market loadings 0.023-0.029, K=1 0.036, random 0.035 (gross one)", band(RS*_pcr.drop(["k1","random"]).b_MktRF, 0.023, 0.029, 3) and (round(RS*_pcr.loc["k1","b_MktRF"],3), round(RS*_pcr.loc["random","b_MktRF"],3)) == (0.036, 0.035))

print("== §6.2 principal-component factors (pc_spanning_v3 / pc_spanning_rule_shiftm1_v3) [N81] ==")
_H = pd.read_csv(E+"pc_spanning_v3_cal6913.csv"); _Rm = pd.read_csv(E+"pc_spanning_rule_shiftm1_v3_cal6913.csv"); _Rm["component"] = "rule"
_P = pd.concat([_H[_H.component=="head"], _Rm]).pivot_table(index=["component","arm"], columns="design", values=["alpha","R2"])
_da = max((_P["alpha"]["ff6_pc5"]-_P["alpha"]["ff6"]).abs().max(), (_P["alpha"]["ff6_st_pc5"]-_P["alpha"]["ff6_st"]).abs().max()); _dr = max((_P["R2"]["ff6_pc5"]-_P["R2"]["ff6"]).abs().max(), (_P["R2"]["ff6_st_pc5"]-_P["R2"]["ff6_st"]).abs().max())
_pc = pd.read_csv(E+"pc_factors_v3_cal6913.csv", index_col=0); _v = 100*_pc.std()*np.sqrt(252)
chk("PC factors move alphas by at most 0.08 pts and R2 by at most 0.02; vols 13.5% to 5.6%", round(_da,2)==0.08 and round(_dr,2)==0.02 and (round(_v.max(),1), round(_v.min(),1))==(13.5,5.6))

print("== statistical kernels (synthetic) ==")
import newstats_lib as L
from statsmodels.stats.multitest import multipletests
rng = np.random.default_rng(0); pv = rng.uniform(0, .2, 12)
chk("Holm == statsmodels", np.abs(L.holm(pv) - multipletests(pv, method="holm")[1]).max() < 1e-12)
xs = np.array([0, .25, .5, .75, 1, 1.2]); chk("Parzen anchors", np.allclose(L.parzen(xs), [1, 1-6*.0625+6*.015625, .25, 2*.25**3, 0, 0]))
mu1, mu2, g1, g2 = .002, .001, .0001+.002**2, .00012+.001**2
grad = L.lw_gradient(np.array(mu1), np.array(g1), np.array(mu2), np.array(g2))
fd = lambda m1,m2,a1,a2: L.sr_from_moments(np.array(m1),np.array(a1)) - L.sr_from_moments(np.array(m2),np.array(a2))
eps = 1e-9; num = np.array([(fd(mu1+eps,mu2,g1,g2)-fd(mu1-eps,mu2,g1,g2))/2/eps, (fd(mu1,mu2+eps,g1,g2)-fd(mu1,mu2-eps,g1,g2))/2/eps,
                            (fd(mu1,mu2,g1+eps,g2)-fd(mu1,mu2,g1-eps,g2))/2/eps, (fd(mu1,mu2,g1,g2+eps)-fd(mu1,mu2,g1,g2-eps))/2/eps])
chk("LW gradient == numeric", (np.abs(grad-num)/np.abs(num)).max() < 1e-5)
T, B, n = 2000, 300, 6; X = rng.normal(0, 1, (T, n)); X[:, 0] += .15
idx = L.cbb_indices(T, 21, B, 7); obs = X.mean(0)/X.std(0); boot = np.stack([X[b].mean(0)/X[b].std(0) for b in idx])
r = L.mcs(obs, boot, [f"m{i}" for i in range(n)], alpha=2.0, stat="Tmax"); chk("MCS power: only true best survives", [k for k,v in r["pvalues"].items() if v>=.1] == ["m0"])
print("== §6.3 sec:peer lens retained fractions (peer_lens_cal6913) ==")
_pl = pd.read_csv(E+"peer_lens_cal6913.csv").set_index("partition")
chk("k-means retains 52%, gics 17% of its clustered R2 under the peer lens", (round(100*_pl.loc["kmeans_ret","ret_peer"]), round(100*_pl.loc["gics","ret_peer"])) == (52, 17))
chk("all 12 clusterizers retain <60% (no arm's peer lens explains the clustered R2)", (_pl.drop(["k1","random"]).ret_peer < 0.60).all())

print("== tab:sizes (sizes_from_caches_cal6913) [A.sizes] ==")
_sz = pd.read_csv(E+"sizes_from_caches_cal6913.csv").set_index("arm")
_printed = {"fv2a_w60": (29.26, 22.1, 0.00, 0.07), "sortino_w60": (29.08, 23.1, 0.00, 0.06), "sharpe_fixed_w60": (28.98, 23.5, 0.00, 0.08),
            "fv3sm_w60": (28.58, 24.9, 0.01, 0.06), "random": (28.36, 25.5, 0.00, 0.01), "pca_load": (26.86, 30.9, 0.01, 0.12),
            "spectral_unsigned": (23.83, 40.7, 0.01, 0.95), "sponge_w60": (23.54, 40.7, 0.00, 1.30), "sssnet_w60": (22.36, 40.8, 0.00, 1.81),
            "agglo_complete": (22.25, 49.8, 0.00, 0.38), "agglo_avg": (12.09, 99.3, 0.55, 6.90), "kmeans_ret": (9.90, 102.0, 9.81, 14.48),
            "gics": (8.08, 55.4, 0.00, 0.66), "k1": (1.00, 500.0, 0.00, 0.00)}
_bad = [a for a, v in _printed.items() if (round(_sz.loc[a,"eff_K"],2), round(_sz.loc[a,"largest"],1), round(_sz.loc[a,"singletons"],2), round(_sz.loc[a,"groups_lt5"],2)) != v]
chk("14 rows x 4 cells at printed rounding", not _bad and set(_sz.days)=={6913}, f"mismatch: {_bad}" if _bad else "")
chk("SPONGE / SSSNET realize 29.9 labels per day", (round(_sz.loc["sponge_w60","labels_realized"],1), round(_sz.loc["sssnet_w60","labels_realized"],1)) == (29.9, 29.9))
_c = _sz.drop(["random","k1"]); _r = spearmanr(_c.eff_K, pd.read_csv(E+"turnover_v3_mean_cal6913.csv", index_col=0).gross_SR.loc[_c.index])
chk("Spearman effK vs mps Sharpe -0.15, p 0.63 (12 clusterizers)", (round(_r.statistic,2), round(_r.pvalue,2)) == (-0.15, 0.63))


print("== §6.1 characteristics lens (lens_extras_v3) [N88] ==")
_lx = pd.read_csv(E+"lens_extras_v3_cal6913.csv").set_index("arm"); _lc = [a for a in _lx.index if a not in ("k1","random")]
chk("characteristics span: real partitions keep 77-85% of their share; Z alone explains 0.13; random at its floor", (round(100*_lx.loc[_lc,"ret_spanZ"].min()), round(100*_lx.loc[_lc,"ret_spanZ"].max()), round(_lx.R2_expl_spanZ.mean(),2)) == (77, 85, 0.13) and abs(_lx.loc["random","ret_spanZ"]-1) < 0.01)
print("== app:costs (A.13) head vs rule per unit of gross (turnover_v3_mean, naive_turnover_v3) [N98] ==")
# A.4 reproducibility [N100]: four same-code, same-seed runs of kmeans_ret at head seed 42 -- the canonical run plus three
# dedicated replicates (server runs_v3/_repro/r{1,2,3}, jobs 62034694-6, 2026-08-23), packaged as kmeans_ret_seed42_repro{1,2,3}.csv.
try:
    import paths as _paths; from analysis.common_calendar import CAL as _CAL
    _rf = [_paths.HEAD_LOGS / "kmeans_ret_seed42.csv"] + [_paths.HEAD_LOGS / f"kmeans_ret_seed42_repro{i}.csv" for i in (1, 2, 3)]
    if all(f.exists() for f in _rf):
        _rs = []
        for f in _rf:
            _b = pd.read_csv(f, parse_dates=["Date"]).set_index("Date").DailyPnL.reindex(pd.DatetimeIndex(_CAL)); assert _b.notna().all(), f
            _rs.append(_b.mean() / _b.std(ddof=1) * np.sqrt(252))
        chk("A.4: four same-seed kmeans_ret runs 2.8243/2.8478/2.8868/2.8940, sd 0.033, range 0.07",
            sorted(round(x, 4) for x in _rs) == [2.8243, 2.8478, 2.8868, 2.8940] and round(np.std(_rs, ddof=1), 3) == 0.033 and round(max(_rs) - min(_rs), 2) == 0.07)
    else:
        print("  SKIP  A.4 four same-seed kmeans_ret runs  [needs kmeans_ret_seed42.csv and kmeans_ret_seed42_repro{1,2,3}.csv in data/derived/head_logs (layer L1)]")
except Exception as _e:
    chk("A.4: four same-seed kmeans_ret runs (loader)", False, repr(_e))
_tv = pd.read_csv(E+"turnover_v3_mean_cal6913.csv").set_index("arm"); _nv3 = pd.read_csv(E+"naive_turnover_v3_cal6913.csv").set_index("arm").rename(index={"sssnetpre": "sssnet_w60"})  # N99: the rule file names the SSSNET arm sssnetpre; without the rename the join silently drops it and the 13-arm ratios are 1.47/1.62
_cm = [a for a in _tv.index if a in _nv3.index]; _row = _nv3.loc[_cm, "turnover_twoway_per_unit_gross"] / 2; _rret = _nv3.loc[_cm, "ann_ret"] / _nv3.loc[_cm, "gross_book"]
chk("A.13: head trades 1.46x per unit of exposure and earns 1.63x (ratios of the 14-arm means); rule return 3.9-4.6%, break-even rule 2.75-3.74 vs head 2.66-3.79",
    len(_cm) == 14 and (round(_tv.loc[_cm, "daily_turnover_oneway_N6_convention"].mean() / _row.mean(), 2), round(_tv.loc[_cm, "ann_ret"].mean() / _rret.mean(), 2)) == (1.46, 1.63)
    and (round(100*_rret.min(), 1), round(100*_rret.max(), 1)) == (3.9, 4.6) and (round(_nv3.loc[_cm, "breakeven_bps"].min(), 2), round(_nv3.loc[_cm, "breakeven_bps"].max(), 2)) == (2.75, 3.74))
_pa = pd.read_csv(E+"pos_autocorr_naive_cal6913.csv"); _pc = _pa[~_pa.arm.isin(["k1", "random"])]
chk("A.13: rule positions correlate with the previous day's at 0.46, 27% of names change sign (clusterizer means)", (round(_pc["corr"].mean(), 2), round(_pc["flip"].mean())) == (0.46, 27))
_n5 = _nv3["netSR_5bp"].rank(ascending=False); chk("A.13: at 5 bp the controls finish first and third on the rule-based component", (int(_n5["k1"]), int(_n5["random"])) == (1, 3))
print("== app:window (A.9) rival account: gain (21->252) on the 21-day level across the swept clusterizers [N103] ==")
try:
    _mp = lambda a, v="": np.mean([_bk.sharpe(_bk.head_book(a, s, v)) for s in _paths.SEEDS])
    _x = np.array([_mp(a, "_w21") for a in ("spectral_unsigned", "pca_load", "agglo_avg")]); _g = np.array([_mp(a, "_w252") - _mp(a, "_w21") for a in ("spectral_unsigned", "pca_load", "agglo_avg")])
    chk("A.9: regression of the window gain on the 21-day starting level fits with r = -0.93", round(float(np.corrcoef(_x, _g)[0, 1]), 2) == -0.93, f"r {np.corrcoef(_x, _g)[0, 1]:.4f}")
except FileNotFoundError:
    print("  SKIP  A.9 rival-account correlation  [needs the window-variant head logs in data/derived (layer L1)]")
print("== tab:ksweep (ksweep_v3_cal6913) [A.ksweep] ==")
_kw = pd.read_csv(E+"ksweep_v3_cal6913.csv"); _pv = _kw.pivot(index="arm", columns="K", values="sharpe_mps").round(2)
_kp = {"kmeans_ret": (2.21, 2.57, 2.48), "agglo_avg": (1.95, 2.15, 2.37), "agglo_complete": (2.07, 2.34, 2.55), "pca_load": (1.99, 2.28, 2.32), "spectral_unsigned": (1.69, 1.74, 1.61)}  # five seeds {1..5}
_kbad = [a for a, v in _kp.items() if tuple(_pv.loc[a, [10, 30, 50]]) != v]
chk("5 arms x 3 K cells at printed rounding", not _kbad, f"mismatch: {_kbad}" if _kbad else "")
chk("across-seed sd 0.09-0.25", (round(_kw.sharpe_sd.min(),2), round(_kw.sharpe_sd.max(),2)) == (0.09, 0.25))
_sp = _kw[_kw.arm=="spectral_unsigned"].set_index("K").sharpe_mps
_km = _kw[_kw.arm=="kmeans_ret"].set_index("K").sharpe_mps
# printed "0.13" is the difference of the rounded cells (1.74 - 1.61); the unrounded means differ by 0.1359 -> 0.14. Check encodes the printed clause and fails until the text says 0.14.
chk("k-means and spectral peak at K=30, falling 0.09 and 0.14 from 30 to 50 (unrounded means; N84); the other three rise monotonically", round(_km[30]-_km[50],2) == 0.09 and round(_sp[30]-_sp[50],2) == 0.14 and _km[30] > _km[10] and _sp[30] > _sp[10]
    and all(_kw[_kw.arm==a].set_index("K").sharpe_mps.is_monotonic_increasing for a in ("agglo_avg","agglo_complete","pca_load")), f"unrounded drops: k-means {_km[30]-_km[50]:.4f}, spectral {_sp[30]-_sp[50]:.4f}")

if "--slow" in sys.argv:
    print("== NW t vs statsmodels (real book) ==")
    import statsmodels.api as sm
    from analysis.factors import load_ff, nw_ols as _nw
    y = _bk.head_book("kmeans_ret", 42); ff = load_ff()
    m = pd.concat([y, ff[["MktRF","SMB","HML","RMW","CMA","MOM"]].shift(1)], axis=1).dropna()
    yv = m.iloc[:,0].to_numpy(float); Xm = m.iloc[:,1:].to_numpy(float)
    tm = _nw(yv, Xm)[1][0]; ts = sm.OLS(yv, np.column_stack([np.ones(len(yv)), Xm])).fit(cov_type="HAC", cov_kwds={"maxlags":21,"kernel":"bartlett"}).tvalues[0]
    chk("NW t == statsmodels HAC", abs(tm-ts)/abs(ts) < 1e-4, f"{tm:.4f} vs {ts:.4f}")
print(f"\n{len(fails)} FAIL" + (": " + ", ".join(fails) if fails else "  -- all checks pass"))
sys.exit(len(fails))
