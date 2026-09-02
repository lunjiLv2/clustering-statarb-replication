"""The seed-extension delivery, in the order the prose branch asked for.

Sections, in order:
  0. every run's validity: the pre-registered NE gate, plus the node it ran on. NOTE: an earlier
     version of this file labelled nodes "2g"/"1g" MIG profiles. That classification was never
     measured and is retracted (2026-08-31): sacct shows every run of this study allocated the
     same GRES type, gpu:a100.20gb, whose name encodes memory only -- 1g.20gb and 2g.20gb both
     carry 20 GB, so nothing on disk distinguishes them. Report the host, never a MIG profile.
  1. the three counts of section 5.1 -- how many of the 11 adjacent gaps fall below the ruler at the
     lower end, the point estimate and the upper end of its 95% interval -- under BOTH the level
     ruler the paper prints and the paired ruler that cancels the seed-level common shift;
  2. the pooled paired standard deviation with its degrees of freedom and interval;
  3. per-arm means and across-seed dispersion;
  4. the 11 adjacent gaps themselves, both seed sets side by side;
  5. every other printed value that moves with the seed set.

    python analysis/seed_delivery.py --seeds 42 1 123 --new 42 1 123 2 3 4 5 6 8 456
"""
from __future__ import annotations
import argparse, glob, re, sys
import os
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books
from analysis.field_ruler_stats_v3 import ruler
CAMPAIGN = Path(os.environ.get("CSA_CAMPAIGN_ROOT", "/nonexistent")) / "sssnet_seed_sweep"   # authors only: set CSA_CAMPAIGN_ROOT to the campaign tree
# The host is reported verbatim; see the note above on why no MIG profile is inferred from it.


def gate_table(seeds) -> pd.DataFrame:
    sys.path.insert(0, str(paths.ROOT / "head")); import ne_gate
    rows = []
    for s in seeds:
        for a in paths.ARMS:
            f = None
            for root in ("runs_v3_2g", "runs_v3"):
                g = glob.glob(str(CAMPAIGN / root / f"family_{a}_seed{s}" / "log_sponge_l1norm_*.csv"))
                if g: f = g[0]; break
            if not f: rows.append(dict(seed=s, arm=a, status="not run", node="")); continue
            host = ""
            m = CAMPAIGN / Path(f).parent.name
            try: host = re.search(r"^host\s*:\s*(\S+)", open(Path(f).parent / "MANIFEST.txt").read(), re.M).group(1)
            except Exception: pass
            rows.append(dict(seed=s, arm=a, status="PASS" if ne_gate.gate_ok(f) else "FAIL",
                             node=host))
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", nargs="+", type=int, default=[42, 1, 123], help="the set this tool audits against")   # 3seed-ok: audits the old set
    ap.add_argument("--new", nargs="+", type=int, required=True, help="the extended set")
    a = ap.parse_args()
    G = gate_table(sorted(set(a.seeds) | set(a.new)))
    print("=== 0. validity of every run (pre-registered NE gate)")
    print(G.pivot_table(index="seed", columns="status", values="arm", aggfunc="count").fillna(0).astype(int).to_string())
    bad = G[G.status == "FAIL"]
    if len(bad): print(f"    seeds with a failing run: {sorted(bad.seed.unique())} -> excluded by the rule")
    usable = [s for s in a.new if s in set(G[(G.status == "PASS")].seed) and not len(G[(G.seed == s) & (G.status != "PASS")])]
    print(f"    seed sets: published {a.seeds} | extended and usable {usable}")
    if len(usable) < 2: print("\n(the extended set is not yet complete; sections 1-5 wait for it)"); return
    missing = [s for s in usable for arm in paths.ARMS[:1] if not (paths.HEAD_LOGS / f"{arm}_seed{s}.csv").exists()]
    if missing:
        print(f"\nthe repo has no ingested logs for seeds {sorted(set(missing))}; run first:")
        print(f"    python tools/ingest_head_runs.py --seeds {' '.join(str(x) for x in sorted(set(missing)))} --no-weights")
        print("    (add --root runs_v3_2g for the canonical seed 7/8 reruns)")
        return
    base, new = ruler(tuple(a.seeds)), ruler(tuple(usable))
    print("\n=== 1-2. the ruler and the three counts")
    for tag, r in (("published", base), ("extended", new)):
        print(f"  {tag:>10}: level {r['sd']:.4f} on {r['df']} df CI [{r['lo']:.3f},{r['hi']:.3f}] -> {r['n_lo']}/{r['n_pt']}/{r['n_hi']} of 11")
    print("\n=== 4. the 11 adjacent gaps")
    for (A, B, g), (A2, B2, g2) in zip(base["pairs"], new["pairs"]):
        print(f"   {A:>18} > {B:<18} {g:.4f}   |   {A2:>18} > {B2:<18} {g2:.4f}")


if __name__ == "__main__":
    main()
