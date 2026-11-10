"""Loaders for the daily payoff series ("books") that every statistic in the paper is built from.

Conventions (see the manuscript, §3.4 and §3.6):
* A *rule-based* book is the deterministic five-day reversal rule applied to one partition; gross
  exposure 2 (±1/n per side) as implemented and as stored. One series per arm: ``rule_books/{arm}.csv``
  with columns Date, DailyPnL. Since 2026-11-10 the manuscript reports the rule-based portfolio at gross
  exposure one (its eq. naivew uses ±1/(2n) per side), the gross exposure of the trained books: every
  rule-based alpha, volatility, return and factor loading it prints is the stored value times
  ``RULE_REPORT_SCALE``. Sharpe ratios, t-statistics, R^2, percentage changes and loadings on another
  rule-based book are unaffected. The stored books and every result CSV stay at gross exposure 2.
* A *trained* book is the neural trading head run on the same partition under one training seed;
  gross exposure 1. Five seeds per arm: ``head_logs/{arm}_seed{1,2,3,4,5}.csv``.
* Every series is reindexed to the common calendar (6,913 days) and asserted complete.
* "Mean of per-seed" statistics compute the statistic per seed and average; "seed-averaged book"
  statistics average the five payoff series day by day first. Functions here return the series;
  callers choose the convention explicitly.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths
from analysis.common_calendar import CAL

IDX = pd.DatetimeIndex(CAL)

RULE_REPORT_SCALE = 0.5
"""Multiply a stored rule-based level (alpha, volatility, return, factor loading) by this to get the value the
manuscript prints: the books are stored at gross exposure 2, the paper reports them at gross exposure one."""


def _read(path: Path) -> pd.Series:
    """Read one book onto the common calendar.

    NOTE: the CSVs on disk carry 6,944 days; this reindex silently drops the 31 that are not on the
    6,913-day common window. Two consequences that have both bitten (2026-09-01):
    (1) a caller who reindexes the RESULT to ``IDX`` sees a no-op and may conclude the file was
        already 6,913, which it was not; and
    (2) a statistic computed straight off the CSV is NOT the paper's statistic. The gap is small but
        it is not always cosmetic -- on the five-seed mean Sharpe it reverses ``sortino_w60`` and
        ``agglo_avg`` (6,944: agglo 2.1676 > sortino 2.1660; 6,913: sortino 2.1495 > agglo 2.1486),
        which is the order fig:bet_corr's rows are drawn in. Always go through this reader.
    """
    s = pd.read_csv(path, parse_dates=["Date"]).set_index("Date")["DailyPnL"].reindex(IDX)
    if s.isna().any():
        raise ValueError(f"{path.name}: {int(s.isna().sum())} days missing on the common calendar")
    return s


def rule_book(arm: str, variant: str = "") -> pd.Series:
    """Daily payoff of the rule-based component on ``arm``'s partition.

    ``variant`` selects a partition-seed twin (``"_ps1"``, ``"_ps123"``) or a window/K variant
    (``"_w21"``, ``"_k10"``, ...) where one exists.
    """
    return _read(paths.RULE_BOOKS / f"{arm}{variant}.csv")


def head_book(arm: str, seed: int, variant: str = "") -> pd.Series:
    """Daily payoff of the trained component on ``arm``'s partition under training ``seed``."""
    return _read(paths.HEAD_LOGS / f"{arm}{variant}_seed{seed}.csv")


def head_books(arm: str, variant: str = "", seeds=paths.SEEDS) -> dict[int, pd.Series]:
    """The per-seed trained books of an arm, one per seed in ``seeds`` (default paths.SEEDS)."""
    return {s: head_book(arm, s, variant) for s in seeds}


def head_avg(arm: str, variant: str = "", seeds=paths.SEEDS) -> pd.Series:
    """The seed-averaged trained book (day-by-day mean over ``seeds``, default paths.SEEDS)."""
    return sum(head_books(arm, variant, seeds).values()) / len(seeds)


def sharpe(s: pd.Series) -> float:
    """Annualized Sharpe ratio: sqrt(252) * mean / std (ddof=1) of the daily payoff."""
    return float(np.sqrt(252) * s.mean() / s.std(ddof=1))


def ann_vol(s: pd.Series) -> float:
    """Annualized volatility in percent."""
    return float(100 * np.sqrt(252) * s.std(ddof=1))


def ann_ret(s: pd.Series) -> float:
    """Annualized mean return in percent."""
    return float(252 * 100 * s.mean())


def positions(arm: str, seed: int) -> list[tuple[pd.Timestamp, np.ndarray, np.ndarray]]:
    """Traded positions of one trained run: a list of (date, tickers, weights) in calendar order.

    The weights are the executed dollar positions of the trading head after the singleton mask and
    the gross-leverage normalisation (sum |w| = 1), exported by the run at
    data/derived/weights/{arm}_seed{seed}.pkl (Zenodo).
    """
    import pickle
    with open(paths.WEIGHTS / f"{arm}_seed{seed}.pkl", "rb") as f:
        return [(pd.Timestamp(e[0]), np.asarray(e[1]), np.asarray(e[2], float)) for e in pickle.load(f)]


SHORT_NAME = {"kmeans_ret": "kmeans", "sponge_w60": "sponge", "fv2a_w60": "fv2a", "fv3sm_w60": "fv3sm",
              "sortino_w60": "sortino", "sharpe_fixed_w60": "sharpe_fixed", "sssnetpre": "sssnet"}
"""Short arm labels used by the peer-spanning, Monte Carlo size and serial-dependence CSVs."""


def head_log_path(arm: str, seed: int, variant: str = "") -> Path:
    """Path of the full run log (P&L, exposures, counts) of one trained run."""
    return paths.HEAD_LOGS / f"{arm}{variant}_seed{seed}.csv"


def gate_ok(arm: str, seed: int, variant: str = "") -> bool:
    """The campaign's validity gate for a trained run (rolling-250 mean |net exposure| <= 0.30 and no
    one-sided day), evaluated by ``head/ne_gate.py`` on the run log."""
    sys.path.insert(0, str(paths.ROOT / "head"))
    import ne_gate
    return bool(ne_gate.gate_ok(str(head_log_path(arm, seed, variant))))
