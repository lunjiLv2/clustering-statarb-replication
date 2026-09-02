"""Spanning of the trained books on the two peer books and on FF5+MOM (tab:peer, §6.4).

The peer books are the two window-only trading heads (60- and 252-day signal windows) run once at
seed 42; the fourteen arm books are the seed-averaged trained books. Three designs are estimated,
    peer    : book ~ a + b1 W60 + b2 W252
    factors : book ~ a + FF6
    both    : book ~ a + b1 W60 + b2 W252 + FF6
plus the reverse regressions of each peer book on the equal weight of the twelve clusterizer books
(with and without FF6). Factors are joined at shift 1 (trained-component convention). Alpha in
percent per year, Newey–West t at 21 lags, and the score (LM) statistic with its chi-square p-value;
``sig5`` flags |t| > 1.96 and is only set for the twelve clusterizers in the forward designs.
Every run must pass the validity gate (books.gate_ok).

Output: analysis/results/peer_spanning_v3_cal6913.csv (short arm labels: books.SHORT_NAME).

Run: ``python analysis/peer_spanning_v3.py``
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import chi2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books
from analysis.factors import FF6, load_ff, nw_ols, alpha_pct, lm_score

PEERS = {"W60": "peer_w60", "W252": "peer_w252"}
CONTROLS = ("k1", "random")


def fit(y: np.ndarray, X: np.ndarray) -> dict:
    b, t, _ = nw_ols(y, X); LM, _ = lm_score(y, X)
    return dict(alpha=alpha_pct(b), t=float(t[0]), LM=float(LM), p=float(chi2.sf(LM, 1)))


def main() -> None:
    for a in paths.ARMS:
        for s in paths.SEEDS:
            assert books.gate_ok(a, s), f"{a} seed{s} fails the validity gate"
    cols = {books.SHORT_NAME.get(a, a): books.head_avg(a) for a in paths.ARMS}
    cols.update({k: books.head_book(v, 42) for k, v in PEERS.items()})
    M = pd.concat(cols, axis=1).join(load_ff()[FF6].shift(1), how="inner").reindex(books.IDX)
    assert M.notna().all().all(), "NaN after the factor join on the common calendar"
    rules = [c for c in cols if c not in CONTROLS and c not in PEERS]
    designs = {"peer": list(PEERS), "factors": FF6, "both": list(PEERS) + FF6}
    rows = []
    for tag, xs in designs.items():
        X = M[xs].to_numpy(float)
        for a in rules + list(CONTROLS):
            r = fit(M[a].to_numpy(float), X)
            rows.append(dict(design=tag, arm=a, **r, sig5=bool(abs(r["t"]) > 1.96 and a in rules)))
        print(f"{tag:8s}: {sum(r['sig5'] for r in rows if r['design'] == tag)}/12 clusterizers keep |t| > 1.96")
    EW = M[rules].mean(axis=1).to_numpy(float).reshape(-1, 1)
    for nm, extra in (("EW12", None), ("EW12+FF6", FF6)):
        X = EW if extra is None else np.column_stack([EW, M[extra].to_numpy(float)])
        for pb in PEERS:
            r = fit(M[pb].to_numpy(float), X)
            rows.append(dict(design=f"reverse_{nm}", arm=pb, **r, sig5=bool(abs(r["t"]) > 1.96)))
    out = pd.DataFrame(rows); name = "peer_spanning_v3_cal6913.csv"
    ref = pd.read_csv(paths.RESULTS / name); j = out.merge(ref, on=["design", "arm"], suffixes=("", "_ref"))
    d = max(np.abs(j[c] - j[c + "_ref"]).max() for c in ("alpha", "t", "LM", "p"))
    print(f"{name}: {len(j)}/{len(ref)} rows matched on [design, arm]; max |diff| {d:.2e}; sig5 identical: {(j.sig5 == j.sig5_ref).all()}")
    force = os.environ.get("CSA_FORCE_WRITE") == "1"
    if force and paths.RESULTS.resolve() == paths.SHIPPED_RESULTS.resolve():
        raise SystemExit("CSA_FORCE_WRITE is refused for the shipped results directory; set CSA_RESULTS_ROOT")
    if d < 1e-6 and (j.sig5 == j.sig5_ref).all(): out.to_csv(paths.RESULTS / name, index=False)
    elif force: out.to_csv(paths.RESULTS / name, index=False); print("  -> written (forced, side directory)")
    else: print("NOT written: the shipped file is not reproduced")


if __name__ == "__main__":
    main()
