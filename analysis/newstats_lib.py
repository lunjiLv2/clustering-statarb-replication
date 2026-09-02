"""Set-valued inference machinery for tab:formal: the circular block bootstrap, the Ledoit–Wolf (2008)
Sharpe-difference test with the Parzen/Andrews HAC covariance, the Hansen–Lunde–Nason (2011) model
confidence set (T_max and T_R) and Holm's step-down adjustment.

The statistical kernels below are the audited ones, unchanged; only the run discovery was replaced by a
loader over the repository's head logs (data/derived/head_logs). Conventions that must not drift:
Sharpe = sqrt(252) * mean / std(ddof=1) of the daily payoff; the Ledoit–Wolf delta method is stated in
LW's own moment form (mu, gamma = E[r^2], sigma^2 = gamma - mu^2). A run is valid when it has the full
6,944-day frame (6,914 for the K=1 arm, whose pre-cache burn-in is 30 days longer) and no day on which
the book held no longs or no shorts (head/ne_gate.n_one_sided).
"""
from __future__ import annotations
import sys
from pathlib import Path
import os
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis import books

sys.path.insert(0, str(paths.ROOT / "head"))
from ne_gate import n_one_sided  # noqa: E402  the single validity criterion

SQ = np.sqrt(252.0)
N_DAYS = 6944                 # the trained runs' full frame (1997-05-23 .. 2024-12-30)
N_DAYS_ALT = {6914}           # k1 (and, before option B, sssnet) start 30 trading days later
DISCOVERY_SEEDS = tuple(int(x) for x in sorted(
    (os.environ["CSA_SEEDS"].replace(",", " ").split()
     if os.environ.get("CSA_SEEDS") else ["1", "2", "3", "4", "5"])))
"""Overridable with CSA_SEEDS; the sort is LEXICOGRAPHIC on the seed string, not numeric,
because that is the order in which the audited producer walks family_<arm>_seed<N>, and the
seed average must add its terms in that same order for the sum to reproduce bit for bit."""
"""Seed order in which the audited producer discovered the run directories (lexicographic
family_<arm>_seed1 < _seed123 < _seed42); kept so that seed averages add in the same order."""


def load_runs(arms: list[str]) -> tuple[list[dict], list[dict]]:
    """(valid, invalid) run records for the given arms, one record per arm x seed.

    Each record carries the full-frame daily payoff (``pnl``), the row count and the number of
    one-sided days; validity is asserted from the log, never assumed.
    """
    valid, invalid = [], []
    for arm in arms:
        for seed in DISCOVERY_SEEDS:
            path = books.head_log_path(arm, seed)
            d = pd.read_csv(path, parse_dates=["Date"]).sort_values("Date")
            rows, os_ = len(d), n_one_sided(d)
            rec = dict(arm=arm, seed=seed, path=str(path), rows=rows, one_sided=os_)
            if (rows == N_DAYS or rows in N_DAYS_ALT) and os_ == 0:
                p = d.set_index("Date")["DailyPnL"].astype(float)
                rec["pnl"] = p
                rec["SR"] = SQ * p.mean() / p.std(ddof=1)
                valid.append(rec)
            else:
                rec["why"] = "one-sided book" if os_ > 0 else f"{rows} rows, not {N_DAYS}"
                invalid.append(rec)
    return valid, invalid


def seed_averaged(valid: list[dict], arms: list[str]) -> pd.DataFrame:
    """arm -> seed-averaged daily payoff on the union of the run frames (NaN where an arm is short)."""
    cols = {}
    for a in arms:
        rs = [r for r in valid if r["arm"] == a]
        assert len(rs) == len(DISCOVERY_SEEDS), (
            f"{a}: {len(rs)} valid runs, expected {len(DISCOVERY_SEEDS)} "
            f"(seed set {DISCOVERY_SEEDS}); set CSA_SEEDS to change it")
        m = pd.concat([r["pnl"] for r in rs], axis=1)
        assert not m.isna().any().any(), f"{a}: seeds do not share a date index"
        cols[a] = m.mean(axis=1)
    return pd.DataFrame(cols)[arms]


# ============================================================ circular block bootstrap
def cbb_indices(T: int, b: int, B: int, seed: int) -> np.ndarray:
    """B x T matrix of circular-block-bootstrap time indices (Politis-Romano 1992).

    ceil(T/b) blocks are drawn with replacement from uniform start points on {0..T-1};
    each block wraps modulo T; the concatenation is truncated to exactly T so that every
    resample has the same length as the sample.  ONE index matrix is shared by the
    Ledoit-Wolf tests, the model confidence set and the family-range band, so those three
    exhibits are draws from a single resampling scheme and can be read against each other.
    """
    rng = np.random.default_rng(seed)
    nb = int(np.ceil(T / b))
    starts = rng.integers(0, T, size=(B, nb))
    idx = (starts[:, :, None] + np.arange(b)[None, None, :]) % T
    return idx.reshape(B, nb * b)[:, :T]


# ================================================== Parzen / Andrews HAC (Ledoit-Wolf 2008)
def parzen(x: np.ndarray) -> np.ndarray:
    a = np.abs(x)
    out = np.where(a <= 0.5, 1.0 - 6.0 * a ** 2 + 6.0 * a ** 3, 2.0 * (1.0 - a) ** 3)
    return np.where(a <= 1.0, out, 0.0)


def alpha_hat_cols(V: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Per-column AR(1) rho and innovation sd of an already-demeaned matrix V (T x p).

    Ledoit-Wolf's `compute.alpha.hat` fits an AR(1) by OLS to each column of the
    influence-function matrix; these are its two inputs.
    """
    T = V.shape[0]
    x0, x1 = V[:-1], V[1:]
    denom = (x0 * x0).sum(0)
    rho = np.where(denom > 0, (x0 * x1).sum(0) / np.where(denom > 0, denom, 1.0), 0.0)
    resid = x1 - rho[None, :] * x0
    sig = np.sqrt(np.maximum((resid ** 2).sum(0) / (T - 2), 1e-300))
    rho = np.clip(rho, -0.97, 0.97)          # LW's code diverges as |rho| -> 1
    return rho, sig


def andrews_bandwidth(rho: np.ndarray, sig: np.ndarray, T: int) -> float:
    """Andrews (1991) automatic bandwidth for the Parzen kernel, LW's S* rule."""
    num = float((4.0 * rho ** 2 * sig ** 4 / (1.0 - rho) ** 8).sum())
    den = float((sig ** 4 / (1.0 - rho) ** 4).sum())
    a = num / den if den > 0 else 0.0
    return 2.6614 * (a * T) ** 0.2


def psi_hat(V: np.ndarray, S_star: float) -> np.ndarray:
    """LW's Psi.hat: Parzen-weighted sum of autocovariances of the demeaned V, x T/(T-p)."""
    T, p = V.shape
    Psi = (V.T @ V) / T
    j = 1
    while j < S_star:
        G = (V[j:].T @ V[:T - j]) / T
        Psi = Psi + parzen(np.array(j / S_star)) * (G + G.T)
        j += 1
    return Psi * (T / (T - p))


# ----------------------------------------------------------------- Sharpe influence function
def sharpe_moment_parts(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(mu, gamma) with gamma = E[x^2], columnwise.  LW's parameterisation."""
    return x.mean(0), (x ** 2).mean(0)


def sr_from_moments(mu: np.ndarray, gam: np.ndarray) -> np.ndarray:
    """DAILY Sharpe in LW's moment form (population sd).  Annualise by sqrt(252)."""
    return mu / np.sqrt(np.maximum(gam - mu ** 2, 1e-300))


def lw_gradient(mu1, gam1, mu2, gam2) -> np.ndarray:
    """d(SR1 - SR2) / d(mu1, mu2, gamma1, gamma2).  LW (2008) section 3."""
    s1 = np.maximum(gam1 - mu1 ** 2, 1e-300) ** 1.5
    s2 = np.maximum(gam2 - mu2 ** 2, 1e-300) ** 1.5
    return np.stack([gam1 / s1, -gam2 / s2, -0.5 * mu1 / s1, 0.5 * mu2 / s2], axis=-1)


def lo_gradient(mu, gam) -> np.ndarray:
    """d SR / d(mu, gamma) for a single series -- Lo (2002) section 4 / LW one-sided."""
    s = np.maximum(gam - mu ** 2, 1e-300) ** 1.5
    return np.stack([gam / s, -0.5 * mu / s], axis=-1)


# ================================================ Hansen-Lunde-Nason (2011) model confidence set
def mcs(theta_obs: np.ndarray, theta_boot: np.ndarray, names: list[str],
        alpha: float, stat: str = "Tmax") -> dict:
    """MCS for a HIGHER-IS-BETTER criterion (here the Sharpe ratio).

    theta_obs   (n,)    observed criterion per model
    theta_boot  (B, n)  bootstrap replicates, same resamples for every model
    stat        'Tmax'  -> T_max,M with elimination rule e_max  (HLN eq. 4-5)
                'TR'    -> the range statistic T_R with elimination rule e_R
    alpha       pass alpha > 1 (e.g. 2.0) to run the elimination to completion; the MCS at
                any confidence level is then {i : p_i >= alpha_wanted}.

    Loss is L = -theta.  d_ij = L_i - L_j.  Bootstrap variances are the empirical
    variances of the CENTERED replicates, recomputed inside every elimination round on
    the surviving set, as HLN prescribe.  The MCS p-value of an eliminated model is the
    running maximum of the round p-values, so the p-values are monotone in elimination
    order and the surviving set is {i : p_i >= alpha}.
    """
    L = -np.asarray(theta_obs, float)
    Lb = -np.asarray(theta_boot, float)
    B = Lb.shape[0]
    alive = list(range(len(L)))
    pvals = {}
    order = []
    while len(alive) > 1:
        a = np.array(alive)
        Lm, Lbm = L[a], Lb[:, a]
        dbar = Lm - Lm.mean()                                  # d_{i.} on the live set
        dbarb = Lbm - Lbm.mean(axis=1, keepdims=True)
        cen = dbarb - dbar[None, :]
        var_i = (cen ** 2).mean(0)
        t_i = dbar / np.sqrt(np.maximum(var_i, 1e-300))
        tb_i = cen / np.sqrt(np.maximum(var_i, 1e-300))[None, :]
        if stat == "Tmax":
            Tobs = float(t_i.max())
            Tb = tb_i.max(axis=1)
            worst = int(a[int(np.argmax(t_i))])
        elif stat == "TR":
            D = Lm[:, None] - Lm[None, :]
            Db = Lbm[:, :, None] - Lbm[:, None, :]
            C = Db - D[None, :, :]
            V = (C ** 2).mean(0)
            np.fill_diagonal(V, np.inf)
            Tsig = D / np.sqrt(V)                 # signed: how much WORSE i is than j
            Tobs = float(np.abs(Tsig).max())
            Tb = (np.abs(C) / np.sqrt(V)[None, :, :]).reshape(B, -1).max(axis=1)
            # HLN's e_R: drop the model whose loss most significantly exceeds another's
            worst = int(a[int(np.argmax(Tsig.max(axis=1)))])
        else:
            raise ValueError(stat)
        p = float((1.0 + (Tb >= Tobs).sum()) / (B + 1.0))
        prev = max(pvals.values()) if pvals else 0.0
        pvals[worst] = max(p, prev)
        order.append((names[worst], pvals[worst], Tobs))
        if p >= alpha:
            break
        alive.remove(worst)
    for i in alive:
        if i not in pvals:
            pvals[i] = 1.0
    surv = [names[i] for i in range(len(L)) if pvals[i] >= alpha]
    return dict(pvalues={names[i]: pvals[i] for i in range(len(L))},
                survivors=surv, elimination=order, stat=stat, alpha=alpha)


# ================================================================================ Holm
def holm(p: np.ndarray) -> np.ndarray:
    """Holm (1979) step-down adjusted p-values, monotonised and capped at 1."""
    p = np.asarray(p, float)
    m = len(p)
    o = np.argsort(p)
    adj = np.empty(m)
    run = 0.0
    for k, i in enumerate(o):
        run = max(run, (m - k) * p[i])
        adj[i] = min(run, 1.0)
    return adj
