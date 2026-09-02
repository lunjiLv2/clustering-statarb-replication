"""Lens 2 — numeric fingerprint of the OLD seed set in the live manuscript.

Build a bank of statistics at seeds (42,1,123) and at (1,2,3,4,5); every number the  # 3seed-ok: the retired set is the fingerprint bank this tool searches FOR
manuscript prints is matched against both at its own print precision. A number that
matches the 3-seed bank and NOT the 5-seed bank is a stale value regardless of what the
surrounding prose says about seeds. Numbers matching both, or neither, are not reported.
"""
import sys, re, itertools, os
sys.path.insert(0, "."); sys.path.insert(0, "audit")
import numpy as np, pandas as pd
import _livetext as L

MAIN14 = ["kmeans_ret","agglo_avg","agglo_complete","pca_load","spectral_unsigned","sponge_w60",
          "fv2a_w60","fv3sm_w60","sortino_w60","sharpe_fixed_w60","gics","sssnetpre","random","k1"]
VARS = {"": MAIN14, "_w21": ["kmeans_ret","agglo_avg","agglo_complete","pca_load","spectral_unsigned"],
        "_w120": ["agglo_avg","pca_load","spectral_unsigned"], "_w252": ["agglo_avg","pca_load","spectral_unsigned"],
        "_k10": ["kmeans_ret","agglo_avg","agglo_complete","pca_load","spectral_unsigned"],
        "_k50": ["kmeans_ret","agglo_avg","agglo_complete","pca_load","spectral_unsigned"]}

def bank(seeds):
    os.environ["CSA_SEEDS"] = ",".join(map(str, seeds))
    for m in [k for k in sys.modules if k.startswith("paths") or k.startswith("analysis")]:
        del sys.modules[m]
    import paths; from analysis import books
    B = {}
    mps = {}
    for v, arms in VARS.items():
        for a in arms:
            try:
                bs = [books.head_book(a, s, v) for s in seeds]
            except Exception as e:
                continue
            srs = [books.sharpe(b) for b in bs]
            key = a + v
            mps[key] = float(np.mean(srs))
            B[f"mps[{key}]"] = mps[key]
            B[f"avg[{key}]"] = float(books.sharpe(sum(bs) / len(bs)))
            B[f"sd[{key}]"] = float(np.std(srs, ddof=1))
            B[f"range[{key}]"] = float(max(srs) - min(srs))
            B[f"vol[{key}]"] = float(np.mean([books.ann_vol(b) for b in bs]))
            B[f"vol%[{key}]"] = 100 * B[f"vol[{key}]"]
            B[f"ret[{key}]"] = float(np.mean([books.ann_ret(b) for b in bs]))
            B[f"ret%[{key}]"] = 100 * B[f"ret[{key}]"]
    # pairwise gaps among the 14 at the main window
    for a, b in itertools.combinations(MAIN14, 2):
        if a in mps and b in mps:
            B[f"gap[{a}-{b}]"] = abs(mps[a] - mps[b])
    # window / k moves
    for v in ["_w21", "_w120", "_w252", "_k10", "_k50"]:
        for a in VARS[v]:
            if a + v in mps and a in mps:
                B[f"move[{a}{v}]"] = mps[a + v] - mps[a]
    # rulers
    m12 = [a for a in MAIN14 if a not in ("random", "k1")]
    lv = []
    for a in m12:
        bs = [books.sharpe(books.head_book(a, s)) for s in seeds]
        lv.append(np.var(bs, ddof=1))
    B["level_ruler"] = float(np.sqrt(np.mean(lv)))
    order = sorted(m12, key=lambda a: -mps[a])
    pv = []
    for a, b in zip(order, order[1:]):
        d = [books.sharpe(books.head_book(a, s)) - books.sharpe(books.head_book(b, s)) for s in seeds]
        pv.append(np.var(d, ddof=1))
    B["paired_ruler"] = float(np.sqrt(np.mean(pv)))
    B["span12"] = mps[order[0]] - mps[order[-1]]
    return B

B3 = bank((42, 1, 123)); B5 = bank((1, 2, 3, 4, 5))  # 3seed-ok: bank of the retired seed set, used only to flag leftovers
print(f"bank sizes: 3-seed {len(B3)}  5-seed {len(B5)}")

def matches(x, prec, bank):
    tol = 0.5 * 10 ** (-prec) + 1e-12
    return [k for k, v in bank.items() if abs(abs(v) - abs(x)) <= tol]

d = L.live(L.MAIN)
NUM = re.compile(r"(?<![\d.])(\d+\.\d+)(?![\d.])")
hits = 0; seen = set()
for name, (flat, _) in d.items():
    for m in NUM.finditer(flat):
        s = m.group(1); x = float(s); prec = len(s.split(".")[1])
        if prec < 2 or x > 20: continue         # 1-decimal numbers match everything
        k3 = matches(x, prec, B3); k5 = matches(x, prec, B5)
        if k3 and not k5:
            key = (name, s, tuple(k3[:2]))
            if key in seen: continue
            seen.add(key); hits += 1
            print(f"\n[{name}] printed {s}  ← 3-seed only: {k3[:3]}")
            print("     " + L.ctx(flat, m, 95))
print(f"\n=== 3-seed-only fingerprints in main text: {hits} ===")
