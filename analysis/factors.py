"""Factor data and the regression kernels used by every spanning table.

Factors: Ken French's daily Fama–French five factors, momentum, and short-term reversal, read from the
raw library files in ``data/factors`` (fetched by ``data/fetch_ken_french.py``); values are converted
from percent to decimals. Regressions: OLS with Newey–West (Bartlett) standard errors at 21 lags —
the convention of every t-statistic in the paper — and the score (LM) form of the intercept test.

Calendar alignment (manuscript §3.1, Appendix on the calendar offset): the panel's date labels run
one trading day ahead of the factor file's for the trained component, so trained books are joined to
``factors.shift(1)``; rule-based books are joined at shift 0.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths

FF6 = ["MktRF", "SMB", "HML", "RMW", "CMA", "MOM"]
"""The six benchmark factors of tab:spanning, in the order used throughout."""


def _read_french(path: Path) -> pd.DataFrame:
    """Parse a Ken French daily file: header lines, then rows 'YYYYMMDD, v1, v2, ...' in percent."""
    rows = []
    for line in open(path, encoding="latin-1"):
        parts = [p.strip() for p in line.split(",")]
        if len(parts) > 1 and parts[0].isdigit() and len(parts[0]) == 8:
            try:
                rows.append([pd.Timestamp(parts[0])] + [float(x) for x in parts[1:]])
            except ValueError:
                continue                                  # a footer or a blank row
    return pd.DataFrame(rows).set_index(0)


def load_ff(with_reversal: bool = True) -> pd.DataFrame:
    """FF5 + MOM (+ ST_Rev) daily factors as decimals, indexed by date."""
    f5 = _read_french(paths.FACTORS / "F-F_Research_Data_5_Factors_2x3_daily.csv")
    f5.columns = ["MktRF", "SMB", "HML", "RMW", "CMA", "RF"]
    mo = _read_french(paths.FACTORS / "F-F_Momentum_Factor_daily.csv"); mo.columns = ["MOM"]
    ff = f5.join(mo, how="inner") / 100.0
    if with_reversal:
        st = _read_french(paths.FACTORS / "F-F_ST_Reversal_Factor_daily.csv"); st.columns = ["ST_Rev"]
        ff = ff.join(st / 100.0, how="left")
    ff.index.name = "Date"
    return ff


def lrv(u: np.ndarray, lag: int = 21) -> float:
    """Newey–West (Bartlett kernel) long-run variance of ``u``, demeaned, divided by T."""
    u = u - u.mean(); T = len(u); s = float(u @ u) / T
    for l in range(1, lag + 1):
        s += 2 * (1 - l / (lag + 1)) * float(u[:-l] @ u[l:]) / T
    return s


def nw_ols(y: np.ndarray, X: np.ndarray, lag: int = 21):
    """OLS of ``y`` on a constant and ``X``; returns (coefficients, NW t-statistics, R²).

    ``coefficients[0]`` is the daily intercept; the paper reports ``252 * 100 * coefficients[0]`` as
    the annualized alpha in percent.
    """
    T = len(y); Xm = np.column_stack([np.ones(T), X])
    b = np.linalg.solve(Xm.T @ Xm, Xm.T @ y); e = y - Xm @ b
    Q = np.linalg.inv(Xm.T @ Xm / T)
    se = np.array([np.sqrt(lrv((Xm @ Q[k]) * e, lag) / T) for k in range(Xm.shape[1])])
    return b, b / se, float(1 - e.var() / y.var())


def alpha_pct(b: np.ndarray) -> float:
    """Annualized alpha in percent from a daily intercept."""
    return float(252 * 100 * b[0])


def nw_ols_hac(y: np.ndarray, X: np.ndarray, lag: int = 21):
    """OLS of ``y`` on ``X`` (which must already contain the constant) with the sandwich form of the
    Newey–West covariance; returns (coefficients, t-statistics, R²).

    Algebraically the same estimator as :func:`nw_ols`; kept in its original sandwich form because the
    Monte Carlo size study (analysis/mc_size_v3.py) counts rejections at a fixed threshold, and the
    shipped counts are reproduced bit for bit only with the kernel that produced them.
    """
    XtX_inv = np.linalg.pinv(X.T @ X)
    b = XtX_inv @ (X.T @ y); e = y - X @ b
    Xe = X * e[:, None]; S = Xe.T @ Xe
    for L in range(1, lag + 1):
        A = Xe[L:].T @ Xe[:-L]
        S += (1.0 - L / (lag + 1.0)) * (A + A.T)
    se = np.sqrt(np.maximum(np.diag(XtX_inv @ S @ XtX_inv), 0))
    ss_tot = float(((y - y.mean()) ** 2).sum())
    return b, b / se, (1.0 - float((e ** 2).sum()) / ss_tot if ss_tot > 0 else np.nan)


def lm_score(y: np.ndarray, X: np.ndarray, lag: int = 21):
    """Score (LM) test of a zero intercept: ``y`` is regressed on ``X`` *without* a constant, and the
    statistic is T * mean(eps)^2 / lrv(u) with u the projected residual; returns (LM, residual u).

    Under H0 the statistic is chi-square with one degree of freedom (critical value 3.841 at 5%).
    """
    T = len(y)
    beta = np.linalg.solve(X.T @ X, X.T @ y); eps = y - X @ beta
    QF = (X.T @ X) / T; mu = X.mean(axis=0)
    u = eps * (1.0 - X @ np.linalg.solve(QF, mu))
    return T * eps.mean() ** 2 / lrv(u, lag), u
