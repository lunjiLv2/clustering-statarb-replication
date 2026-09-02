"""tab:formal — model confidence sets, Ledoit–Wolf pairwise Sharpe tests with Holm, and the
non-overlapping-block row, on the twelve seed-averaged trained books (optionally with the two controls).

Battery: circular block bootstrap (block 21, 5,000 draws, seed 42) of the payoff matrix on the common
calendar; per draw the annualized Sharpe ratios and the Ledoit–Wolf (2008) Sharpe differences with
Parzen/Andrews HAC standard errors; the Hansen–Lunde–Nason model confidence set (T_max and the range
statistic, elimination run to completion so that the set at level p is {i : p_i >= p}); studentized
bootstrap p-values of the pairwise differences with Holm's adjustment. The "non-overlapping" row
compounds the daily payoffs into 21-day blocks first (T = 329 block returns, Sharpe annualized by
sqrt(252/21)) and redoes the battery with block length 1 — a return-horizon robustness check.

Outputs (analysis/results): formal_v3_intersect{_ctl}_summary.csv (MCS sizes and the sortino-vs-
sharpe_fixed twin difference), _pairs_{overlap_cbb,nonoverlap_21d_agg}.csv (66 or 91 pairs) and
_mcs_{tag}_{Tmax,TR}.csv (MCS p-values). ``_ctl`` adds the K=1 and random controls (14 arms).

Run: ``python analysis/formal_v3.py [--controls] [--draws 5000]``   (~hours of CPU; see slurm/batch_e.sh)
"""
from __future__ import annotations
import argparse, os, sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths
from analysis import books
import newstats_lib as L
from newstats_w60_matched import SET_W60, FILE_ARM, build_matrix, bootstrap

BLK, SEED, ALPHA = 21, 42, 0.10
TWIN = ("sortino_w60", "sharpe_fixed_w60")


def block_aggregate(X: np.ndarray, b: int) -> np.ndarray:
    """Compound daily payoffs into non-overlapping b-day block returns."""
    nb = len(X) // b
    Z = X[:nb * b].reshape(nb, b, X.shape[1])
    return np.prod(1.0 + Z, axis=1) - 1.0


def lw_holm(delta, se, draws):
    """Studentized bootstrap p-values of the pairwise Sharpe differences and their Holm adjustment."""
    d, s = delta[0], se[0]
    t = d / s
    ds = np.abs(delta[1:] - d[None, :]) / se[1:]
    pb = (1.0 + (ds >= np.abs(t)[None, :]).sum(0)) / (draws + 1.0)
    return d, s, t, pb, L.holm(pb)


def payoff_matrix(arms: list[str]) -> pd.DataFrame:
    valid, invalid = L.load_runs([FILE_ARM.get(a, a) for a in arms])
    print(f"[formal] gate: {len(valid)} VALID / {len(invalid)} INVALID runs", flush=True)
    assert not invalid, f"invalid runs: {[(r['arm'], r['seed'], r['why']) for r in invalid]}"
    X = build_matrix(valid, arms).dropna()            # intersect the run frames (k1 is 30 days short)
    X = X.reindex(books.IDX)
    assert not X.isna().any().any(), "NaN after reindexing to the common calendar"
    assert list(X.columns) == arms
    return X


def same(new: pd.DataFrame, ref: pd.DataFrame, keys: list[str]) -> float:
    """Key-merged comparison: max |difference| over the numeric columns (NaN == NaN); a differing
    NaN pattern, string column or row count counts as an infinite difference."""
    j = new.merge(ref, on=keys, suffixes=("", "_ref"))
    if not (len(j) == len(ref) == len(new)):
        print(f"  row mismatch {len(j)}/{len(ref)}/{len(new)}"); return np.inf
    d = 0.0
    for c in [c for c in ref.columns if c not in keys]:
        a, b = j[c], j[c + "_ref"]
        if ref[c].dtype.kind in "fi":
            if not (a.isna() == b.isna()).all():
                print(f"  NaN pattern differs in {c}"); return np.inf
            m = ~a.isna()
            if m.any(): d = max(d, float(np.abs(a[m].astype(float) - b[m].astype(float)).max()))
        elif not (a.astype(str) == b.astype(str)).all():
            print(f"  column {c} differs: {int((a.astype(str) != b.astype(str)).sum())} rows"); return np.inf
    return d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--controls", action="store_true", help="add the K=1 and random controls (14 arms, _ctl outputs)")
    ap.add_argument("--draws", type=int, default=5000)
    ap.add_argument("--write", action="store_true", help="overwrite the shipped CSVs when they are reproduced")
    a = ap.parse_args()
    arms = SET_W60 + (["k1", "random"] if a.controls else [])
    tag_out = "formal_v3_intersect" + ("_ctl" if a.controls else "")
    B = a.draws
    X = payoff_matrix(arms)
    Xn = X.to_numpy(float)
    sr0 = L.SQ * Xn.mean(0) / Xn.std(0, ddof=1)
    spread_full = float(sr0.max() - sr0.min())
    print(f"[formal] matrix {X.shape}  {X.index[0].date()}..{X.index[-1].date()}")
    for a_, s_ in sorted(zip(arms, sr0), key=lambda z: -z[1]):
        print(f"  {a_:20s} SR {s_:7.4f}")
    print(f"  spread (max-min) = {spread_full:.4f}", flush=True)

    rows, outputs = [], {}
    for tag in ("overlap_cbb", "nonoverlap_21d_agg"):
        print(f"\n=== {tag} ({B} draws, block {BLK}) ===", flush=True)
        if tag == "overlap_cbb":
            Xuse, ann = Xn, L.SQ
            idx = L.cbb_indices(len(Xuse), BLK, B, SEED)
        else:
            Xuse, ann = block_aggregate(Xn, BLK), np.sqrt(252.0 / BLK)
            _s = ann * Xuse.mean(0) / Xuse.std(0, ddof=1)
            print(f"  aggregated to {Xuse.shape[0]} non-overlapping {BLK}-day blocks; point spread {float(_s.max()-_s.min()):.4f}", flush=True)
            idx = L.cbb_indices(len(Xuse), 1, B, SEED)
        sr_b, dl, se_, P, sstar = bootstrap(Xuse, arms, B, BLK, SEED, idx=idx, ann=ann)
        sp = float(sr_b[0].max() - sr_b[0].min())
        print(f"  point SR spread on this sample = {sp:.4f}   (daily-sample spread {spread_full:.4f})")
        for stat in ("Tmax", "TR"):
            pv = L.mcs(sr_b[0], sr_b[1:], arms, alpha=2.0, stat=stat)["pvalues"]
            for lev, nm in ((0.10, "90%"), (0.25, "75%")):
                kp = [m for m in arms if pv[m] >= lev]
                print(f"  MCS {nm} ({stat}): {len(kp)}/{len(arms)} retained"
                      + ("" if len(kp) == len(arms) else "  excluded: " + ", ".join(f"{m}({pv[m]:.3f})" for m in arms if m not in kp)))
                rows.append(dict(resample=tag, stat=stat, level=nm, n_retained=len(kp), retained="|".join(kp),
                                 spread_point=spread_full, spread_boot_mean=sp))
            outputs[f"{tag_out}_mcs_{tag}_{stat}.csv"] = pd.Series(pv).sort_values(ascending=False).rename("mcs_pvalue")
        d, s, t, pb, ha = lw_holm(dl, se_, B)
        rk = np.argsort(-sr_b[0]).tolist()
        pdf = pd.DataFrame([dict(i=arms[i], j=arms[j], diff=d[k], se=s[k], t=t[k], p_boot=pb[k], holm=ha[k],
                                 adjacent=abs(rk.index(i) - rk.index(j)) == 1) for k, (i, j) in enumerate(P)])
        outputs[f"{tag_out}_pairs_{tag}.csv"] = pdf
        for lev in (0.05, 0.10):
            sg = pdf.holm < lev
            print(f"  Ledoit-Wolf Holm at {lev:.0%}: {int(sg.sum())}/{len(pdf)} significant, {int((sg & pdf.adjacent).sum())} adjacent")
        # §5.3 quotes the clusterizer-vs-control counts SEPARATELY for each control ("none separates
        # from K=1 and three from the random control"), which the 91-pair total cannot give.
        if len(pdf) > 66:
            _cl = [x for x in arms if x not in ("k1", "random")]
            for _c in ("k1", "random"):
                _m = pdf[((pdf.i == _c) & pdf.j.isin(_cl)) | ((pdf.j == _c) & pdf.i.isin(_cl))]
                print(f"  clusterizers vs {_c}: {int((_m.holm < 0.05).sum())}/{len(_m)} past Holm at 5%")
        # the closest adjacent pair, which §5.3 quotes by name with its raw and adjusted p-value
        _adj = pdf[pdf.adjacent]
        if len(_adj):
            _b = _adj.loc[_adj.p_boot.idxmin()]
            print(f"  closest adjacent pair: {_b.i} vs {_b.j}  raw p {_b.p_boot:.4f}  holm {_b.holm:.4f}")
        if a.controls:
            rules = [x for x in arms if x not in ("k1", "random")]
            srr = dict(zip(arms, sr_b[0])); beat = {}
            for c in ("k1", "random"):
                m = pdf[((pdf.i.isin(rules)) & (pdf.j == c)) | ((pdf.j.isin(rules)) & (pdf.i == c))]
                hi = [(r.i if r.j == c else r.j) for r in m.itertuples() if (srr[r.i] - srr[r.j]) * (1 if r.i != c else -1) > 0]
                sg = [(r.i if r.j == c else r.j) for r in m.itertuples() if r.holm < 0.05]
                beat[c] = set(hi)
                print(f"    vs {c:7s}: {len(hi)}/{len(rules)} rules have the higher SR; {len(sg)}/{len(rules)} separate past Holm<5%")
            print(f"    above BOTH controls: {len(beat['k1'] & beat['random'])}/{len(rules)}")
        tw = pdf[((pdf.i == TWIN[0]) & (pdf.j == TWIN[1])) | ((pdf.i == TWIN[1]) & (pdf.j == TWIN[0]))]
        if len(tw):
            r = tw.iloc[0]; sgn = 1.0 if r.i == TWIN[0] else -1.0
            _ann = np.sqrt(252.0) if tag == "overlap_cbb" else np.sqrt(252.0 / BLK)
            # tab:formal prints the ANNUALIZED difference and standard error; printing only the
            # daily pair forced a hand conversion at the point of transcription, which is where
            # the shipped s.e. of 0.1021 came from (the correct annualization of 0.0058 is 0.0921).
            print(f"  twin {TWIN[0]}-vs-{TWIN[1]}: diff {sgn*r['diff']:+.6f}  se {r.se:.6f}  "
                  f"p_boot {r.p_boot:.4f}  holm {r.holm:.4f}   "
                  f"[annualized: {sgn*r['diff']*_ann:+.4f}  s.e. {r.se*_ann:.4f}]")
            rows[-1].update(twin_diff=sgn * r["diff"], twin_se=r.se, twin_p=r.p_boot)
    outputs[f"{tag_out}_summary.csv"] = pd.DataFrame(rows)

    # ---- compare with the shipped files, write only on reproduction ---------------------------
    worst = 0.0
    # CSA_FORCE_WRITE=1 writes a non-reproducing result into a SIDE directory only (CSA_RESULTS_ROOT), as in _compare.py.
    force = os.environ.get("CSA_FORCE_WRITE") == "1"
    if force and paths.RESULTS.resolve() == paths.SHIPPED_RESULTS.resolve():
        raise SystemExit("CSA_FORCE_WRITE is refused for the shipped results directory; set CSA_RESULTS_ROOT")
    for name, obj in outputs.items():
        ref_path = paths.RESULTS / name
        if not ref_path.exists():
            print(f"{name}: no shipped file to compare")
            if force:
                (obj.to_csv(ref_path, header=["mcs_pvalue"]) if isinstance(obj, pd.Series) else obj.to_csv(ref_path, index=False)); print("  -> written (forced, side directory)")
            continue
        if name.split("_")[-2] == "mcs" or "_mcs_" in name:
            ref = pd.read_csv(ref_path, index_col=0)["mcs_pvalue"]
            new = obj.reindex(ref.index)
            d = float(np.abs(new - ref).max()); ok = list(obj.index) == list(ref.index) and d < 1e-6
        else:
            keys = ["i", "j"] if "_pairs_" in name else ["resample", "stat", "level"]
            ref = pd.read_csv(ref_path)
            d = same(obj, ref, keys); ok = d < 1e-6
        worst = max(worst, d)
        print(f"{name}: max |diff| {d:.2e} {'OK' if ok else 'MISMATCH'}")
        if (ok and a.write) or force:
            if isinstance(obj, pd.Series): obj.to_csv(ref_path, header=["mcs_pvalue"])
            else: obj.to_csv(ref_path, index=False)
            print("  -> written" if ok else "  -> written (forced, side directory)")
    print(f"[formal] worst |diff| over all outputs {worst:.2e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
