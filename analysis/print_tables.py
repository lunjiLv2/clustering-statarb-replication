"""Print the cells of the manuscript's main tables from the shipped result CSVs (layer L0).

This is the human-readable counterpart of the harness: it shows where each printed band comes from.
Run: ``python analysis/print_tables.py``.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis.books import RULE_REPORT_SCALE as RS   # rule-based levels are printed at gross exposure one

R = paths.RESULTS; C = [a for a in paths.ARMS if a not in ("k1", "random")]
band = lambda s, nd=2: f"{s.min():.{nd}f}–{s.max():.{nd}f}"
scale = lambda comp: RS if comp == "rule" else 1.0     # stored rule books are gross 2; the paper prints gross 1


def tab_costs():
    t = pd.read_csv(R / "turnover_v3_mean_cal6913.csv", index_col=0); c = t.drop(["k1", "random"])
    print("tab:costs (trained component, mean of per-seed)")
    print(f"  12 clusterizers: gross SR {band(c.gross_SR)} | return {band(100*c.ann_ret)}% | one-way turnover {band(100*c.daily_turnover_oneway_N6_convention,1)}% | break-even {band(c.breakeven_bps)} bp | net 1/2/5 bp {band(c.netSR_1bp)} / {band(c.netSR_2bp)} / {band(c.netSR_5bp)}")
    for k in ("k1", "random"):
        r = t.loc[k]; print(f"  {k:6s}: {r.gross_SR:.2f} | {100*r.ann_ret:.2f}% | {100*r.daily_turnover_oneway_N6_convention:.1f}% | {r.breakeven_bps:.2f} bp | {r.netSR_1bp:.2f} / {r.netSR_2bp:.2f} / {r.netSR_5bp:.2f}")


def tab_spanning():
    s = pd.read_csv(R / "rule_spanning_era_v3_cal6913.csv").replace({"arm": {"sssnet_w60": "sssnetpre"}}); st = pd.read_csv(R / "strev_spanning_v3_cal6913.csv")
    print("tab:spanning (FF5+MOM; alpha %/yr, NW21 t, R2, LM withdrawn)")
    for comp in ("rule", "head"):
        f = s[(s.component == comp) & (s.era == "full")].set_index("arm"); c = f.loc[C]; k = scale(comp)
        print(f"  {comp:4s} 12: alpha {band(k*c.alpha)} t {band(c.t,1)} R2 {band(c.R2)} | K=1 {k*f.loc['k1','alpha']:.2f} ({f.loc['k1','t']:.1f}) | random {k*f.loc['random','alpha']:.2f} ({f.loc['random','t']:.1f})")
    print("tab:spanning (FF5+MOM+Reversal)")
    for comp in ("rule", "head"):
        f = st[(st.component == comp) & (st.era == "full")].set_index("arm"); c = f.loc[C]; k = scale(comp)
        print(f"  {comp:4s} 12: alpha {band(k*c.alpha7)} t {band(c.t7,1)} R2 {band(c.R2_7)} beta_Rev {band(k*c.beta_strev)} | K=1 {k*f.loc['k1','alpha7']:.2f} ({f.loc['k1','t7']:.1f}) [beta {k*f.loc['k1','beta_strev']:.2f}] | random {k*f.loc['random','alpha7']:.2f} ({f.loc['random','t7']:.1f}) [beta {k*f.loc['random','beta_strev']:.2f}]")


def tab_peer():
    p = pd.read_csv(R / "peer_spanning_v3_cal6913.csv")
    print("tab:peer (alpha %/yr, NW21 t)")
    for d in ("peer", "factors", "both"):
        x = p[(p.design == d) & ~p.arm.isin(["k1", "random"])]; k = p[(p.design == d) & (p.arm == "k1")].iloc[0]; r = p[(p.design == d) & (p.arm == "random")].iloc[0]
        assert len(x) == 12, f"tab:peer {d}: expected the 12 clusterizers, got {len(x)}"
        print(f"  {d:8s}: 12 clusterizers {band(x.alpha)} t {band(x.t,1)} | K=1 {k.alpha:.2f} ({k.t:.1f}) | random {r.alpha:.2f} ({r.t:.1f})")


def tab_moments():
    """tab:moments levels: rule-based from naive_turnover (gross 2, printed x RS), trained as mean of per-seed volatility."""
    nt = pd.read_csv(R / "naive_turnover_v3_cal6913.csv", index_col=0); c = nt.drop(["k1", "random"])
    st = pd.read_csv(R / "strev_spanning_v3_cal6913.csv"); f = st[(st.component == "rule") & (st.era == "full")].set_index("arm")
    print("tab:moments, rule-based rows at gross exposure one (vol and alpha %/yr)")
    print(f"  volatility 12: {band(100*RS*c.ann_vol)} | K=1 {100*RS*nt.loc['k1','ann_vol']:.2f} | random {100*RS*nt.loc['random','ann_vol']:.2f} | mean {100*RS*c.ann_vol.mean():.2f}")
    print(f"  alpha      12: {band(RS*f.loc[C].alpha6)} | K=1 {RS*f.loc['k1','alpha6']:.2f} | random {RS*f.loc['random','alpha6']:.2f} | mean {RS*f.loc[C].alpha6.mean():.2f}")


def tab_k1span():
    k = pd.read_csv(R / "k1_regressor_v3_cal6913.csv")
    print("tab:k1span (alpha %/yr; beta, t and R2 are scale-free)")
    for comp in ("rule", "head"):
        x = k[(k.component == comp) & (k.arm != "random")]; r = k[(k.component == comp) & (k.arm == "random")].iloc[0]; s_ = scale(comp)
        assert len(x) == 12, f"tab:k1span {comp}: expected 12 clusterizers, got {len(x)}"
        print(f"  {comp:4s} 12: alpha {band(s_*x.alpha_on_k1)} t {band(x.t_on_k1,1)} beta {band(x.beta_k1)} R2 {band(x.R2_k1)} | +FF6 alpha {band(s_*x.alpha_on_k1_ff6)} t {band(x.t_on_k1_ff6,1)}"
              f" | random {s_*r.alpha_on_k1:.2f} ({r.t_on_k1:.1f}) beta {r.beta_k1:.2f} R2 {r.R2_k1:.2f} +FF6 {s_*r.alpha_on_k1_ff6:.2f} ({r.t_on_k1_ff6:.1f})")


def tab_era():
    e = pd.read_csv(R / "rule_spanning_era_v3_cal6913.csv").replace({"arm": {"sssnet_w60": "sssnetpre"}})
    print("tab:era (alpha %/yr, NW21 t, sigma %/yr)")
    for comp in ("head", "rule"):
        for era in ("1997-2008", "2009-2024"):
            f = e[(e.component == comp) & (e.era == era)].set_index("arm"); c = f.loc[C]; k = scale(comp)
            print(f"  {comp:4s} {era}: 12 alpha {band(k*c.alpha,1)} t {band(c.t,1)} sigma {band(k*c.vol,1)} | K=1 {k*f.loc['k1','alpha']:.2f} ({f.loc['k1','t']:.1f}) {k*f.loc['k1','vol']:.1f} | random {k*f.loc['random','alpha']:.2f} ({f.loc['random','t']:.1f}) {k*f.loc['random','vol']:.1f}")


def tab_split():
    s = pd.read_csv(R / "split_v3_cal6913.csv"); s = s[s.conv != "seedavg"]
    print("tab:split (four cells: rule/K=1, rule/random, trained mps/K=1, trained mps/random)")
    for _, r in s.iterrows():
        print(f"  {r.layer:4s} {r.control:6s}: gap {r.logSR_gap:.3f} = mean {r.mean_part:.3f} + vol {r.vol_part:.3f}  ({r.vol_share_pct:.1f}% volatility)")


if __name__ == "__main__":
    for f in (tab_moments, tab_costs, tab_spanning, tab_k1span, tab_era, tab_peer, tab_split):
        f(); print()
