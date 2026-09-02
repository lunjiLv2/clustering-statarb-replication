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

R = paths.RESULTS; C = [a for a in paths.ARMS if a not in ("k1", "random")]
band = lambda s, nd=2: f"{s.min():.{nd}f}–{s.max():.{nd}f}"


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
        f = s[(s.component == comp) & (s.era == "full")].set_index("arm"); c = f.loc[C]
        print(f"  {comp:4s} 12: alpha {band(c.alpha)} t {band(c.t,1)} R2 {band(c.R2)} | K=1 {f.loc['k1','alpha']:.2f} ({f.loc['k1','t']:.1f}) | random {f.loc['random','alpha']:.2f} ({f.loc['random','t']:.1f})")
    print("tab:spanning (FF5+MOM+Reversal)")
    for comp in ("rule", "head"):
        f = st[(st.component == comp) & (st.era == "full")].set_index("arm"); c = f.loc[C]
        print(f"  {comp:4s} 12: alpha {band(c.alpha7)} t {band(c.t7,1)} R2 {band(c.R2_7)} beta_Rev {band(c.beta_strev)} | K=1 {f.loc['k1','alpha7']:.2f} ({f.loc['k1','t7']:.1f}) | random {f.loc['random','alpha7']:.2f} ({f.loc['random','t7']:.1f})")


def tab_peer():
    p = pd.read_csv(R / "peer_spanning_v3_cal6913.csv")
    print("tab:peer (alpha %/yr, NW21 t)")
    for d in ("peer", "factors", "both"):
        x = p[(p.design == d) & ~p.arm.isin(["k1", "random", "spectral_unsigned"])]; k = p[(p.design == d) & (p.arm == "k1")].iloc[0]; r = p[(p.design == d) & (p.arm == "random")].iloc[0]
        print(f"  {d:8s}: 11 clusterizers {band(x.alpha)} t {band(x.t,1)} | K=1 {k.alpha:.2f} ({k.t:.1f}) | random {r.alpha:.2f} ({r.t:.1f})")


def tab_split():
    s = pd.read_csv(R / "split_v3_cal6913.csv"); s = s[s.conv != "seedavg"]
    print("tab:split (four cells: rule/K=1, rule/random, trained mps/K=1, trained mps/random)")
    for _, r in s.iterrows():
        print(f"  {r.layer:4s} {r.control:6s}: gap {r.logSR_gap:.3f} = mean {r.mean_part:.3f} + vol {r.vol_part:.3f}  ({r.vol_share_pct:.1f}% volatility)")


if __name__ == "__main__":
    for f in (tab_costs, tab_spanning, tab_peer, tab_split):
        f(); print()
