# === Phase-2 auto-injected: stub broken matplotlib (numpy2 ABI) as no-op MagicMock ===
import sys as _sys, types as _types
from unittest.mock import MagicMock as _MM
_mpl = _types.ModuleType('matplotlib')
_mpl.use = lambda *a, **k: None
_plt = _MM()
_plt.subplots = lambda *a, **k: (_MM(), _MM())
_mpl.pyplot = _plt
_sys.modules['matplotlib'] = _mpl
_sys.modules['matplotlib.pyplot'] = _plt
# === end inject ===
"""
pipeline_sponge_l1norm.py — SPONGE_sym + v2.1 + L1 Norm

EXP1.2: 与 exp1.1 (SPONGE_sym + symmetric) 完全相同，唯一区别:
  normalize_bets 从 symmetric (分别 scale 正/负为1) 改为 L1 norm (统一 scale)

Architecture:
  1. Clustering: SPONGE_sym (signet) with retry + shrinkage fallback chain
     - phase=1: success, phase=2: shrinkage fallback, phase=3: random (skip day)
  2. Signal Extraction: CNNLongConvSignal (v2.1 identical)
     - MultiScaleCNNFFTAgg + LongConvLayer + last-step extraction
     - Single-channel cumsum input (NOT multi-channel)
  3. Betting Head: BettingHead v2-L1
     - tanh soft-clamp + L1 norm normalization
     - weights = raw_bets / Σ|raw_bets| (整体 scale, 不分别 rescale 正负)
     - Gross leverage = 1.0 (before vol scaling)

Retains all v2.1 improvements: bias decay, margin loss, vol scaling, position clip.
"""
import os
import random
import datetime
import csv
import math
import copy
from collections import deque

import numpy as np
import pandas as pd
import scipy.sparse as sp
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from tqdm import tqdm
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# ==========================================
# 0. Config
# ==========================================
class Config:
    # [MR-Net] Use pre-computed refined clusters; OUTPUT_DIR is separate.
    _SPONGE_K_ENV = int(os.environ.get("SPONGE_K", "30"))
    OUTPUT_DIR = "output_tourney_kmeans_ret"
    REFINED_CLUSTERS_FILE = os.environ.get("REFINED_FILE_OVERRIDE", "/home/nvidia/lunji/GNN_Trading_WorkSpace/May_15_Meeting/MR_clustering/output/labelcache_kmeans_ret_K30_5d.pkl")  # === A2 PATCH 2 ===
    USE_REFINED_CLUSTERS = True
    REFINED_CLUSTER_MAX_AGE_DAYS = 10  # if no refresh within this many days, fallback to fresh SPONGE
    DATA_DIR = "/home/nvidia/lunji/Cleaned_Data"
    CLEAN_DIR = os.environ.get("A2_CLEAN_DIR", os.path.join(os.path.dirname(DATA_DIR), "Cleaned_Data"))  # === A2 SINGLE-LINE PATCH ===

    DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Universe / windows
    TOP_K_STOCKS = 500
    BETA_WINDOW = 60
    GRAPH_LOOKBACK = 21
    SIGNAL_WINDOW = 30
    HISTORY_WINDOW = max(GRAPH_LOOKBACK, SIGNAL_WINDOW)
    LOOKFORWARD = 1
    MIN_STOCKS = 20

    # ---- SPONGE_sym clustering (multi-K varies this) ----
    N_CLUSTERS = _SPONGE_K_ENV
    # LONG_RATIO_MIN/MAX removed — L1 norm replaces LR constraint
    SPONGE_MIN_CLUSTER_SIZE = 2

    # ---- CNN + LongConv signal extractor (v2.1) ----
    CNN_FILTERS = 8
    CNN_KERNEL_SIZES = [2, 4, 8]
    TRANS_HDN = 16
    TRANS_DROPOUT = 0.25
    LONGCONV_SQUASH_LAMBDA = 0.001

    # ---- Training schedule (v2.1) ----
    BET_LR = 5e-4
    BET_LR_FINETUNE = 1e-4
    BET_WEIGHT_DECAY = 5e-4
    BET_BATCH_DAYS = 125
    BET_EPOCHS_PRETRAIN = 80
    BET_EPOCHS_FINETUNE = 40
    PRETRAIN_DAYS = 1000
    FINE_TUNE_DAYS = 1000
    RE_ESTIMATE_FREQ = 125
    MIN_TRAIN_DAYS = 125

    # ---- Early stopping ----
    EARLY_STOP_PATIENCE = 15
    EARLY_STOP_PATIENCE_FINETUNE = 10
    VAL_RATIO = 0.15

    # ---- LR scheduler ----
    USE_COSINE_LR = True
    COSINE_T0 = 20
    COSINE_T0_FINETUNE = 10
    COSINE_T_MULT = 2
    COSINE_ETA_MIN = 1e-6

    # ---- Bet regularization (v2) ----
    BET_L1_LAMBDA = 1e-3
    BET_CONCENTRATION_PENALTY = 5e-3
    AUGMENT_NOISE_STD = 0.002
    AUGMENT_PROB = 0.3
    MARGIN_LOSS_LAMBDA = 0.05
    MARGIN_LOSS_N_PAIRS = 64

    # ---- Position constraints (v2) ----
    MAX_POSITION_WEIGHT = 0.05

    # ---- Vol targeting (v2) ----
    VOL_TARGET_ANNUAL = 0.15
    VOL_LOOKBACK = 20
    VOL_SCALAR_CAP = 2.0
    POSITION_CLIP_MAX = 0.04

    # ---- Bias decay (v2) ----
    BIAS_DECAY_FACTOR = 0.5

    DIAG_DASH_FREQ = 50
    SEED = int(os.environ.get("SWEEP_SEED", os.environ.get("SSSNET_SEED", "42")))  # === SEED-SWEEP PATCH ===


os.makedirs(Config.OUTPUT_DIR, exist_ok=True)
np.random.seed(Config.SEED)
random.seed(Config.SEED)
torch.manual_seed(Config.SEED)


# ---- Dependency check ----
try:
    from signet.cluster import Cluster
    HAS_SIGNET = True
except ImportError:
    print("Error: signet missing — SPONGE_sym unavailable.")
    HAS_SIGNET = False


# ==========================================
# 1. Data
# ==========================================
def calculate_residuals_and_returns(price_matrix, validity_mask, beta_window=60):
    raw_returns = price_matrix.pct_change(fill_method=None)
    assert "SPY" in raw_returns.columns, (  # === PATCH 7 (no silent market fallback) ===
        "market series SPY missing from the panel — refusing the iloc[:,0] fallback; "
        "check the D11 exemption in build_cleaned_v3.py")
    mkt = raw_returns["SPY"]
    roll_cov = raw_returns.rolling(beta_window).cov(mkt)
    roll_var = mkt.rolling(beta_window).var()
    residuals = raw_returns - (roll_cov.div(roll_var, axis=0)).multiply(mkt, axis=0)
    return residuals.where(validity_mask), raw_returns.where(validity_mask)


# ==========================================
# [MR-Net] Refined cluster loading
# ==========================================
_REFINED_CLUSTERS_CACHE = None
_REFINED_DATES_SORTED = None

def _load_refined_clusters():
    global _REFINED_CLUSTERS_CACHE, _REFINED_DATES_SORTED
    if _REFINED_CLUSTERS_CACHE is None:
        import pickle as _pkl
        with open(Config.REFINED_CLUSTERS_FILE, "rb") as f:
            _REFINED_CLUSTERS_CACHE = _pkl.load(f)
        _REFINED_DATES_SORTED = sorted(_REFINED_CLUSTERS_CACHE.keys())
        print(f"[MR-Net] Loaded {len(_REFINED_CLUSTERS_CACHE)} refined cluster snapshots, "
              f"range {_REFINED_DATES_SORTED[0].date()} to {_REFINED_DATES_SORTED[-1].date()}")
    return _REFINED_CLUSTERS_CACHE, _REFINED_DATES_SORTED


def get_refined_cluster_for_day(date, current_tickers, current_corr, n_clusters):
    """Get cluster labels for current day using most recent pre-computed refined clusters.

    Mapping strategy:
      1. Find most recent refresh_date <= date (within MAX_AGE_DAYS)
      2. For each current ticker:
         - If in refined universe: use that label
         - If not (newly added stock): assign to nearest cluster by corr
      3. Returns labels in same order as current_tickers, plus 'phase' (1=success, 3=fallback)
    """
    refined, dates_sorted = _load_refined_clusters()
    # Most recent refresh <= date
    import bisect
    pos = bisect.bisect_right(dates_sorted, date) - 1
    if pos < 0:
        return None, 3
    refresh_date = dates_sorted[pos]
    age = (date - refresh_date).days
    if age > Config.REFINED_CLUSTER_MAX_AGE_DAYS:
        # Stale; fallback to fresh SPONGE
        return None, 3
    info = refined[refresh_date]
    refined_universe = info["universe"]
    refined_labels = info["labels"]
    # Build mapping: ticker -> label
    ticker_to_label = {t: int(l) for t, l in zip(refined_universe, refined_labels)}

    out_labels = np.zeros(len(current_tickers), dtype=np.int32)
    new_tickers_idx = []
    for i, t in enumerate(current_tickers):
        if t in ticker_to_label:
            out_labels[i] = ticker_to_label[t]
        else:
            new_tickers_idx.append(i)

    # New tickers: assign to cluster with highest mean corr
    if len(new_tickers_idx) > 0:
        # For each new ticker, compute mean corr to each cluster
        for ni in new_tickers_idx:
            best_k = 0
            best_aff = -np.inf
            for k in range(n_clusters):
                mems = np.where((out_labels == k) & (np.arange(len(current_tickers)) != ni))[0]
                if len(mems) == 0:
                    continue
                aff = np.mean(current_corr[ni, mems])
                if aff > best_aff:
                    best_aff = aff
                    best_k = k
            out_labels[ni] = best_k

    return out_labels, 1


def get_daily_batch(date_idx, history_window, lookforward, top_k, res_df, raw_df, cap_df):
    if date_idx < history_window:
        return None, None, None, None, None
    if date_idx + lookforward - 1 >= len(res_df):
        return None, None, None, None, None

    try:
        caps = cap_df.iloc[date_idx - 1]
        # === PATCH 6 (universe backfill) ===
        _ok = (res_df.iloc[date_idx - history_window:date_idx].notna().all()
               & raw_df.iloc[date_idx - history_window:date_idx + lookforward].notna().all()
               & caps.notna())
        valid_tickers = caps[_ok].nlargest(top_k).index
        if len(valid_tickers) < Config.MIN_STOCKS:
            return None, None, None, None, None
    except Exception:
        return None, None, None, None, None

    c_df = res_df.iloc[date_idx - history_window:date_idx].reindex(columns=valid_tickers).dropna(axis=1)
    t_df = raw_df.iloc[date_idx - history_window:date_idx + lookforward].reindex(columns=valid_tickers).dropna(axis=1)
    batch_caps = cap_df.iloc[date_idx - 1].reindex(valid_tickers).dropna()

    valid = c_df.columns.intersection(t_df.columns).intersection(batch_caps.index)
    if len(valid) < Config.MIN_STOCKS:
        return None, None, None, None, None

    c_df = c_df[valid]
    t_df = t_df[valid]
    batch_caps = batch_caps[valid]

    t_hist = t_df.iloc[:history_window]
    t_target = t_df.iloc[history_window:history_window + lookforward]

    c_df_clamped = c_df.apply(lambda x: x.clip(lower=x.quantile(0.05), upper=x.quantile(0.95)), axis=1)
    t_hist_clamped = t_hist.apply(lambda x: x.clip(lower=x.quantile(0.05), upper=x.quantile(0.95)), axis=1)

    return c_df_clamped, t_hist_clamped, t_target, batch_caps, valid


# ==========================================
# 2. SPONGE_sym Clustering
# ==========================================
import warnings


def _compute_cs_demeaned_corr(df: pd.DataFrame) -> np.ndarray:
    cs_mean = df.mean(axis=1)
    demeaned = df.sub(cs_mean, axis=0)
    return demeaned.corr().fillna(0.0).values


def _shrink_corr(corr: np.ndarray, alpha: float = 0.1) -> np.ndarray:
    n = corr.shape[0]
    return (1.0 - alpha) * corr + alpha * np.eye(n)


def _fix_tiny_clusters(labels: np.ndarray, corr: np.ndarray, min_size: int = 2) -> np.ndarray:
    labels = labels.copy()
    unique, counts = np.unique(labels, return_counts=True)
    small_clusters = unique[counts < min_size]
    if len(small_clusters) == 0:
        return labels
    large_clusters = unique[counts >= min_size]
    if len(large_clusters) == 0:
        return labels
    for sc in small_clusters:
        orphan_idx = np.where(labels == sc)[0]
        for oi in orphan_idx:
            best_cluster = large_clusters[0]
            best_affinity = -np.inf
            for lc in large_clusters:
                members = np.where(labels == lc)[0]
                affinity = np.mean(corr[oi, members])
                if affinity > best_affinity:
                    best_affinity = affinity
                    best_cluster = lc
            labels[oi] = best_cluster
    return labels


def run_sponge_clustering(
    corr: np.ndarray,
    k: int,
    min_size: int = 2,
    max_retries: int = 15,
) -> tuple:
    """
    Run SPONGE_sym clustering with retry + shrinkage fallback.

    Returns: (labels_np, phase)
      phase=1: success, phase=2: shrinkage fallback, phase=3: random (skip day)
    """
    n = corr.shape[0]
    best_labels = None
    best_n_clusters = 0

    for _ in range(max_retries):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                c = Cluster((
                    sp.csc_matrix(np.maximum(corr, 0)),
                    sp.csc_matrix(np.maximum(-corr, 0)),
                ))
                lbl = c.SPONGE_sym(k, tau_p=1, tau_n=1)
        except Exception:
            continue

        lbl = _fix_tiny_clusters(lbl, corr, min_size)
        unique, counts = np.unique(lbl, return_counts=True)

        if len(unique) >= k - 5 and np.all(counts >= min_size):
            return lbl, 1

        n_valid = np.sum(counts >= min_size)
        if n_valid > best_n_clusters:
            best_n_clusters = n_valid
            best_labels = lbl.copy()

    for alpha in [0.05, 0.1, 0.2]:
        corr_shrunk = _shrink_corr(corr, alpha)
        for _ in range(5):
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    c = Cluster((
                        sp.csc_matrix(np.maximum(corr_shrunk, 0)),
                        sp.csc_matrix(np.maximum(-corr_shrunk, 0)),
                    ))
                    lbl = c.SPONGE_sym(k, tau_p=1, tau_n=1)
            except Exception:
                continue

            lbl = _fix_tiny_clusters(lbl, corr, min_size)
            unique, counts = np.unique(lbl, return_counts=True)

            if len(unique) >= k - 5 and np.all(counts >= min_size):
                return lbl, 2

            n_valid = np.sum(counts >= min_size)
            if n_valid > best_n_clusters:
                best_n_clusters = n_valid
                best_labels = lbl.copy()

    if best_labels is not None:
        return _fix_tiny_clusters(best_labels, corr, min_size), 2

    labels = np.zeros(n, dtype=int)
    perm = np.random.permutation(n)
    for i, idx_val in enumerate(perm):
        labels[idx_val] = i % k
    return labels, 3


# ==========================================
# 3. Signal Extractor (v2.1 identical)
# ==========================================

class MultiScaleCNNFFTAgg(nn.Module):
    """[v2.1] Multi-scale CNN with FFT amplitude-weighted aggregation."""
    def __init__(self, n_filters: int = 8, kernel_sizes: tuple = (2, 4, 8)):
        super().__init__()
        self.n_filters = n_filters
        self.kernel_sizes = list(kernel_sizes)
        self.n_scales = len(kernel_sizes)

        self.conv1s = nn.ModuleList([
            nn.Conv1d(1, n_filters, kernel_size=ks, padding=0, bias=True)
            for ks in self.kernel_sizes
        ])
        self.conv2s = nn.ModuleList([
            nn.Conv1d(n_filters, n_filters, kernel_size=ks, padding=0, bias=True)
            for ks in self.kernel_sizes
        ])
        self.in1s = nn.ModuleList([
            nn.InstanceNorm1d(n_filters, affine=False) for _ in self.kernel_sizes
        ])
        self.in2s = nn.ModuleList([
            nn.InstanceNorm1d(n_filters, affine=False) for _ in self.kernel_sizes
        ])
        self.scale_bias = nn.Parameter(torch.zeros(self.n_scales))

    def forward(self, x_seq: torch.Tensor) -> torch.Tensor:
        x0 = x_seq.unsqueeze(1)

        branch_outs = []
        for i, ks in enumerate(self.kernel_sizes):
            x = F.pad(x0, (ks - 1, 0))
            x = self.conv1s[i](x); x = self.in1s[i](x); x = F.relu(x)
            x = F.pad(x, (ks - 1, 0))
            x = self.conv2s[i](x); x = self.in2s[i](x); x = F.relu(x)
            x = x + x0.repeat(1, self.n_filters, 1)
            branch_outs.append(x)

        fft_amp = torch.fft.rfft(x_seq, dim=1).abs()
        avg_amp = fft_amp.mean(dim=0)
        n_freq = avg_amp.shape[0]

        band_size = max(1, (n_freq - 1) // self.n_scales)
        band_amps = []
        for i in range(self.n_scales):
            lo = 1 + i * band_size
            hi = min(lo + band_size, n_freq)
            band_amps.append(avg_amp[lo:hi].mean() if lo < n_freq else avg_amp[-1])

        scale_amps = torch.stack(list(reversed(band_amps)))
        scale_weights = F.softmax(scale_amps + self.scale_bias, dim=0)

        stacked = torch.stack(branch_outs, dim=0)
        out = (scale_weights[:, None, None, None] * stacked).sum(dim=0)
        return out.transpose(1, 2)


class LongConvLayer(nn.Module):
    """[v2.1] Long convolution with Squash regularization."""
    def __init__(self, d_model: int, seq_len: int, squash_lambda: float = 0.001):
        super().__init__()
        self.d_model = d_model
        self.seq_len = seq_len
        self.squash_lambda = squash_lambda
        self.kernel = nn.Parameter(torch.empty(d_model, seq_len))
        self.skip = nn.Parameter(torch.ones(d_model))
        self._init_kernel_geometric()

    def _init_kernel_geometric(self) -> None:
        T, d = self.seq_len, self.d_model
        with torch.no_grad():
            t = torch.arange(T, dtype=torch.float32)
            for h in range(d):
                x = torch.randn(T) * 0.02
                decay = torch.exp(-t / T * (d / 2) ** (h / max(d, 1)))
                self.kernel.data[h] = x * decay

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x_t = x.transpose(1, 2)
        T = x_t.shape[-1]
        K = torch.sign(self.kernel) * torch.relu(torch.abs(self.kernel) - self.squash_lambda)
        fft_len = 2 * T
        X_fft = torch.fft.rfft(x_t, n=fft_len, dim=-1)
        K_fft = torch.fft.rfft(K, n=fft_len, dim=-1)
        y = torch.fft.irfft(X_fft * K_fft.unsqueeze(0), n=fft_len, dim=-1)[..., :T]
        y = F.gelu(y + self.skip.unsqueeze(0).unsqueeze(-1) * x_t)
        return y.transpose(1, 2)


class CNNLongConvSignal(nn.Module):
    """[v2.1] CNN + LongConv + last-step extraction."""
    def __init__(self, d_filters: int = 8, kernel_sizes: tuple = (2, 4, 8),
                 signal_window: int = 30, squash_lambda: float = 0.001):
        super().__init__()
        self.cnn = MultiScaleCNNFFTAgg(n_filters=d_filters, kernel_sizes=kernel_sizes)
        self.longconv = LongConvLayer(
            d_model=d_filters, seq_len=signal_window, squash_lambda=squash_lambda,
        )

    def forward(self, x_seq: torch.Tensor, return_diag: bool = False) -> torch.Tensor:
        x_local = self.cnn(x_seq)
        h = self.longconv(x_local)
        theta = h[:, -1, :]

        if return_diag:
            K = self.longconv.kernel
            K_sq = torch.sign(K) * torch.relu(torch.abs(K) - self.longconv.squash_lambda)
            K_profile = K_sq.mean(dim=0).detach()
            K_expanded = K_profile.unsqueeze(0).expand(x_seq.shape[0], -1)
            return theta, K_expanded
        return theta


class BettingHead(nn.Module):
    """[v2-L1] BettingHead with tanh soft-clamp and L1 norm normalization.

    Key change from v2-sym: replaces separate long/short normalization with unified
    L1 norm scaling. weights = raw_bets / Σ|raw_bets|, preserving natural long/short ratio.
    """
    def __init__(self, d_signal: int = 8, hdn: int = 16, dropout: float = 0.25,
                 max_position: float = 0.05):
        super().__init__()
        self.max_position = max_position
        self.ffn = nn.Sequential(
            nn.Linear(d_signal, hdn), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(hdn, 1),
        )

    def normalize_bets(self, raw_bets: torch.Tensor, eps: float = 1e-8) -> torch.Tensor:
        """L1 normalization: scale all bets so sum(|weights|) = 1."""
        l1_norm = torch.sum(torch.abs(raw_bets))
        if l1_norm <= eps:
            return torch.zeros_like(raw_bets)
        return raw_bets / l1_norm

    def forward(self, theta: torch.Tensor) -> tuple:
        raw_bets = self.ffn(theta).squeeze(-1)
        raw_bets_clamped = self.max_position * torch.tanh(raw_bets / self.max_position)
        weights = self.normalize_bets(raw_bets_clamped)
        return weights, raw_bets


class DSABettingModel(nn.Module):
    """SPONGE_sym clustering + v2.1 CNNLongConvSignal + BettingHead (L1 norm)."""
    def __init__(self):
        super().__init__()
        self.signal_extractor = CNNLongConvSignal(
            d_filters=Config.CNN_FILTERS,
            kernel_sizes=Config.CNN_KERNEL_SIZES,
            signal_window=Config.SIGNAL_WINDOW,
            squash_lambda=Config.LONGCONV_SQUASH_LAMBDA,
        )
        self.betting_head = BettingHead(
            d_signal=Config.CNN_FILTERS, hdn=Config.TRANS_HDN,
            dropout=Config.TRANS_DROPOUT,
            max_position=Config.MAX_POSITION_WEIGHT,
        )

    def forward(self, x_seq: torch.Tensor, return_diag: bool = False):
        if return_diag:
            theta, time_w = self.signal_extractor(x_seq, return_diag=True)
            weights, raw_bets = self.betting_head(theta)
            return weights, raw_bets, {"theta": theta, "attn_weights": time_w}
        theta = self.signal_extractor(x_seq)
        return self.betting_head(theta)


# ==========================================
# 4. Data Preparation
# ==========================================
def prepare_day_pack(date_idx, residuals, raw_returns, caps, price_index):
    out = get_daily_batch(
        date_idx=date_idx, history_window=Config.HISTORY_WINDOW,
        lookforward=Config.LOOKFORWARD, top_k=Config.TOP_K_STOCKS,
        res_df=residuals, raw_df=raw_returns, cap_df=caps,
    )
    c_clamped, t_hist_clamped, t_target_raw, caps_b, valid = out
    if c_clamped is None:
        return None

    graph_df = c_clamped.iloc[-Config.GRAPH_LOOKBACK:]
    corr = _compute_cs_demeaned_corr(graph_df)

    y_ret = (1.0 + t_target_raw).prod() - 1.0
    y_target = torch.tensor(y_ret.values, dtype=torch.float32, device=Config.DEVICE)
    signal_window = torch.tensor(
        c_clamped.iloc[-Config.SIGNAL_WINDOW:].values.T,
        dtype=torch.float32, device=Config.DEVICE,
    )

    return {
        "date_idx": date_idx,
        "date": price_index[date_idx],
        "corr": corr,
        "signal_window": signal_window,
        "y_target": y_target,
        "n_stocks": len(valid),
        "tickers": list(valid),  # [MR-Net] needed for cluster mapping
    }


def build_cluster_relative_series(signal_window: torch.Tensor,
                                   cluster_labels: torch.Tensor,
                                   n_clusters: int) -> torch.Tensor:
    rel = torch.zeros_like(signal_window)
    for k in range(n_clusters):
        mask = cluster_labels == k
        if torch.sum(mask) > 0:
            mean_k = signal_window[mask].mean(dim=0, keepdim=True)
            rel[mask] = signal_window[mask] - mean_k
    return rel


def build_bet_sample(day_pack: dict, cluster_labels_np: np.ndarray) -> dict:
    cluster_labels = torch.tensor(cluster_labels_np, dtype=torch.long, device=Config.DEVICE)
    rel_series = build_cluster_relative_series(
        day_pack["signal_window"], cluster_labels, Config.N_CLUSTERS,
    )
    x_seq = torch.cumsum(rel_series, dim=1)
    unique_lbl, counts_lbl = torch.unique(cluster_labels, return_counts=True)
    valid_clusters = unique_lbl[counts_lbl >= Config.SPONGE_MIN_CLUSTER_SIZE]
    mask = torch.isin(cluster_labels, valid_clusters)
    return {
        "x_seq": x_seq[mask].detach(),
        "y_target": day_pack["y_target"][mask].detach(),
        "date": day_pack["date"],
    }


# ==========================================
# 5. Loss Functions
# ==========================================
def sharpe_loss(portfolio_returns: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
    mean_ret = portfolio_returns.mean()
    std_ret = portfolio_returns.std(unbiased=False) + eps
    return -(mean_ret / std_ret)


def margin_ranking_loss(raw_bets: torch.Tensor, y_target: torch.Tensor,
                        n_pairs: int = 64) -> torch.Tensor:
    n = raw_bets.shape[0]
    if n < 4:
        return torch.tensor(0.0, device=raw_bets.device)
    actual_pairs = min(n_pairs, n * (n - 1) // 2)
    idx_i = torch.randint(0, n, (actual_pairs,), device=raw_bets.device)
    idx_j = torch.randint(0, n, (actual_pairs,), device=raw_bets.device)
    different = idx_i != idx_j
    idx_i = idx_i[different]
    idx_j = idx_j[different]
    if idx_i.shape[0] == 0:
        return torch.tensor(0.0, device=raw_bets.device)
    target = torch.sign(y_target[idx_i] - y_target[idx_j])
    pred_diff = raw_bets[idx_i] - raw_bets[idx_j]
    return torch.relu(-target * pred_diff + 0.01).mean()


# ==========================================
# 6. Training Loop (v2.1 identical)
# ==========================================
def train_betting_model(
    bet_model, optimizer, samples, epochs, prefix="Online",
    val_ratio=None, patience=None, use_cosine_lr=None,
    cosine_t0=None, cosine_t_mult=None, cosine_eta_min=None,
    l1_lambda=None, concentration_penalty=None,
    augment_noise_std=None, augment_prob=None,
    batch_days=None, margin_lambda=None, margin_n_pairs=None,
):
    if val_ratio is None: val_ratio = Config.VAL_RATIO
    if patience is None: patience = Config.EARLY_STOP_PATIENCE
    if use_cosine_lr is None: use_cosine_lr = Config.USE_COSINE_LR
    if cosine_t0 is None: cosine_t0 = Config.COSINE_T0
    if cosine_t_mult is None: cosine_t_mult = Config.COSINE_T_MULT
    if cosine_eta_min is None: cosine_eta_min = Config.COSINE_ETA_MIN
    if l1_lambda is None: l1_lambda = Config.BET_L1_LAMBDA
    if concentration_penalty is None: concentration_penalty = Config.BET_CONCENTRATION_PENALTY
    if augment_noise_std is None: augment_noise_std = Config.AUGMENT_NOISE_STD
    if augment_prob is None: augment_prob = Config.AUGMENT_PROB
    if batch_days is None: batch_days = Config.BET_BATCH_DAYS
    if margin_lambda is None: margin_lambda = Config.MARGIN_LOSS_LAMBDA
    if margin_n_pairs is None: margin_n_pairs = Config.MARGIN_LOSS_N_PAIRS

    if len(samples) < 10:
        tqdm.write(f"[{prefix}] Only {len(samples)} samples, skipping.")
        return

    n_val = max(2, int(len(samples) * val_ratio))
    train_samples = samples[:-n_val]
    val_samples = samples[-n_val:]
    if len(train_samples) < 5:
        train_samples = samples
        val_samples = samples[-max(2, len(samples) // 5):]

    tqdm.write(
        f"[{prefix}] Train: {len(train_samples)} days | "
        f"Val: {len(val_samples)} days | Epochs: {epochs} | Patience: {patience}"
    )

    scheduler = None
    if use_cosine_lr:
        scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(
            optimizer, T_0=cosine_t0, T_mult=cosine_t_mult, eta_min=cosine_eta_min,
        )

    best_val_loss = float("inf")
    best_state = None
    no_improve_count = 0

    bet_model.train()
    for epoch in range(epochs):
        order = list(range(len(train_samples)))
        random.shuffle(order)
        epoch_train_loss = 0.0
        num_batches = 0

        for st in range(0, len(order), batch_days):
            idx_chunk = order[st:st + batch_days]
            if len(idx_chunk) < 2:
                continue

            optimizer.zero_grad()
            day_rets = []
            total_l1 = 0.0
            total_herf_long = 0.0
            total_herf_short = 0.0
            total_margin = 0.0

            for j in idx_chunk:
                s = train_samples[j]
                x_input = s["x_seq"]
                if random.random() < augment_prob:
                    x_input = x_input + torch.randn_like(x_input) * augment_noise_std

                weights, raw_bets = bet_model(x_input)
                day_rets.append(torch.sum(weights * s["y_target"]))

                total_l1 += torch.mean(torch.abs(raw_bets))
                pos_w = torch.relu(weights)
                neg_w = torch.relu(-weights)
                total_herf_long += torch.sum(pos_w ** 2)
                total_herf_short += torch.sum(neg_w ** 2)
                if margin_lambda > 0:
                    total_margin += margin_ranking_loss(raw_bets, s["y_target"], margin_n_pairs)

            rets = torch.stack(day_rets)
            loss = sharpe_loss(rets)
            n_chunk = len(idx_chunk)
            loss = loss + l1_lambda * (total_l1 / n_chunk)
            loss = loss + concentration_penalty * ((total_herf_long + total_herf_short) / n_chunk)
            if margin_lambda > 0:
                loss = loss + margin_lambda * (total_margin / n_chunk)

            loss.backward()
            torch.nn.utils.clip_grad_norm_(bet_model.parameters(), 1.0)
            optimizer.step()

            epoch_train_loss += loss.item()
            num_batches += 1

        if scheduler is not None:
            scheduler.step()

        avg_train_loss = epoch_train_loss / max(num_batches, 1)

        bet_model.eval()
        with torch.no_grad():
            val_day_rets = []
            for s in val_samples:
                weights, _ = bet_model(s["x_seq"])
                val_day_rets.append(torch.sum(weights * s["y_target"]))
            if len(val_day_rets) >= 2:
                val_rets = torch.stack(val_day_rets)
                val_loss = sharpe_loss(val_rets).item()
            else:
                val_loss = avg_train_loss
        bet_model.train()

        current_lr = optimizer.param_groups[0]['lr']
        tqdm.write(
            f"[{prefix}] Epoch {epoch+1}/{epochs} | "
            f"Train: {avg_train_loss:.4f} | Val: {val_loss:.4f} | "
            f"LR: {current_lr:.6f} | Patience: {no_improve_count}/{patience}"
        )

        if val_loss < best_val_loss - 1e-4:
            best_val_loss = val_loss
            best_state = copy.deepcopy(bet_model.state_dict())
            no_improve_count = 0
        else:
            no_improve_count += 1

        if no_improve_count >= patience:
            tqdm.write(f"[{prefix}] Early stopping at epoch {epoch+1} (best val: {best_val_loss:.4f})")
            break

    if best_state is not None:
        bet_model.load_state_dict(best_state)
        tqdm.write(f"[{prefix}] Restored best model (val: {best_val_loss:.4f})")


def create_fresh_optimizer(bet_model, lr, weight_decay=None):
    if weight_decay is None:
        weight_decay = Config.BET_WEIGHT_DECAY
    return torch.optim.AdamW(bet_model.parameters(), lr=lr, weight_decay=weight_decay)


# ==========================================
# 7. Diagnostic Utils
# ==========================================
def compute_rank_ic(raw_bets: torch.Tensor, y_target: torch.Tensor) -> float:
    n = raw_bets.shape[0]
    if n < 5:
        return 0.0
    pred_ranks = raw_bets.argsort().argsort().float()
    tgt_ranks = y_target.argsort().argsort().float()
    pred_dm = pred_ranks - pred_ranks.mean()
    tgt_dm = tgt_ranks - tgt_ranks.mean()
    denom = pred_dm.norm() * tgt_dm.norm()
    if denom < 1e-12:
        return 0.0
    return (pred_dm * tgt_dm).sum().item() / denom.item()


def compute_theta_diversity(theta: torch.Tensor) -> tuple:
    norms = theta.norm(dim=1)
    theta_norm_std = norms.std().item() if theta.shape[0] > 1 else 0.0
    n = theta.shape[0]
    if n < 2:
        return theta_norm_std, 0.0
    unit = F.normalize(theta, dim=1)
    sum_unit = unit.sum(dim=0)
    cos_mean = (sum_unit.dot(sum_unit).item() - n) / (n * (n - 1))
    return theta_norm_std, cos_mean


def compute_attn_stats(attn_weights: torch.Tensor) -> tuple:
    attn_profile = attn_weights.mean(dim=0).cpu().numpy()
    entropy = -(attn_weights * (attn_weights + 1e-10).log()).sum(dim=1)
    attn_entropy = entropy.mean().item()
    attn_peak_pos = attn_weights.argmax(dim=1).float().mean().item()
    return attn_profile, attn_entropy, attn_peak_pos


def compute_cluster_stats(labels_np: np.ndarray) -> dict:
    _, counts = np.unique(labels_np, return_counts=True)
    return {
        "cl_size_mean": float(counts.mean()),
        "cl_size_std": float(counts.std()),
        "cl_size_min": int(counts.min()),
        "cl_size_max": int(counts.max()),
    }


# ==========================================
# 8. Loggers
# ==========================================
class CSVLogger:
    def __init__(self):
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filename = os.path.join(Config.OUTPUT_DIR, f"log_sponge_l1norm_{ts}.csv")
        self.fieldnames = [
            "Date", "DailyPnL", "CumulativePnL", "AnnReturn", "Sharpe",
            "MaxDrawdown", "N_Clusters", "N_Long", "N_Short",
            "GrossLeverage", "NetExposure", "VolScalar",
        ]
        with open(self.filename, mode="w", newline="") as f:
            csv.DictWriter(f, fieldnames=self.fieldnames).writeheader()
        print(f"Log: {self.filename}")

    def log(self, row: dict) -> None:
        with open(self.filename, mode="a", newline="") as f:
            csv.DictWriter(f, fieldnames=self.fieldnames).writerow(row)


class DiagCSVLogger:
    def __init__(self):
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filename = os.path.join(Config.OUTPUT_DIR, f"diag_{ts}.csv")
        self.fieldnames = [
            "Date", "N_Stocks",
            "ThetaNormStd", "ThetaCosineMean",
            "TimePoolEntropy", "TimePoolPeakPos",
            "RankIC", "RawBetStd", "LongRatio", "ActiveBetRatio",
            "ClSizeMean", "ClSizeStd", "ClSizeMin", "ClSizeMax",
            "SpongePhase",
        ]
        with open(self.filename, mode="w", newline="") as f:
            csv.DictWriter(f, fieldnames=self.fieldnames).writeheader()
        print(f"Diag log: {self.filename}")

    def log(self, row: dict) -> None:
        with open(self.filename, mode="a", newline="") as f:
            csv.DictWriter(f, fieldnames=self.fieldnames).writerow(row)


# ==========================================
# 9. Main Pipeline
# ==========================================
def run_pipeline():
    if not HAS_SIGNET:
        print("FATAL: signet not installed. Cannot run SPONGE_sym.")
        return

    try:
        print("Loading data...")
        prices = pd.read_pickle(os.path.join(Config.CLEAN_DIR, "prices.pkl"))
        caps = pd.read_pickle(os.path.join(Config.CLEAN_DIR, "caps.pkl"))
        mask = pd.read_pickle(os.path.join(Config.CLEAN_DIR, "mask.pkl"))
    except Exception as e:
        print(f"Data load failed: {e}")
        return

    residuals, raw_returns = calculate_residuals_and_returns(
        prices, mask, beta_window=Config.BETA_WINDOW,
    )

    logger = CSVLogger()
    diag_logger = DiagCSVLogger()

    all_indices = list(range(max(Config.BETA_WINDOW, Config.HISTORY_WINDOW) + 1, len(prices)))
    init_pack = None
    init_pos = 0
    for p, idx in enumerate(all_indices):
        init_pack = prepare_day_pack(idx, residuals, raw_returns, caps, prices.index)
        if init_pack is not None:
            init_pos = p
            break

    if init_pack is None:
        print("No valid day found.")
        return

    bet_model = DSABettingModel().to(Config.DEVICE)
    bet_opt = create_fresh_optimizer(bet_model, lr=Config.BET_LR)

    total_params = sum(p.numel() for p in bet_model.parameters())
    print(f"\n{'='*60}")
    print(f"EXP1.2: SPONGE_sym + L1 Norm")
    print(f"  Clustering:         SPONGE_sym (signet, retry + shrinkage fallback)")
    print(f"  Signal extractor:   MultiScaleCNNFFTAgg + LongConv (v2.1)")
    print(f"  LongConv Squash λ:  {Config.LONGCONV_SQUASH_LAMBDA}")
    print(f"  Total params:       {total_params}")
    print(f"  Normalization:      L1 norm (NO separate long/short rescaling)")
    print(f"  Bias decay:         {Config.BIAS_DECAY_FACTOR}")
    print(f"{'='*60}\n")

    dash_dir = os.path.join(Config.OUTPUT_DIR, "dashboards")
    diag_dash_dir = os.path.join(Config.OUTPUT_DIR, "diag_dashboards")
    os.makedirs(dash_dir, exist_ok=True)
    os.makedirs(diag_dash_dir, exist_ok=True)

    # ----------------------------
    # Phase 1: Pre-train
    # ----------------------------
    history_samples = deque(maxlen=Config.FINE_TUNE_DAYS)
    used_pretrain = 0
    cursor = init_pos

    print(f"\n>>> Phase 1: Build pretrain set ({Config.PRETRAIN_DAYS} days)")
    for pos in tqdm(range(init_pos, len(all_indices)), desc="Pretrain Days"):
        idx = all_indices[pos]
        day_pack = prepare_day_pack(idx, residuals, raw_returns, caps, prices.index)
        if day_pack is None:
            continue

        # [MR-Net] Try to load pre-computed refined cluster; fallback to SPONGE if stale/missing.
        labels_np, sponge_phase = None, None
        if Config.USE_REFINED_CLUSTERS:
            labels_np, sponge_phase = get_refined_cluster_for_day(
                day_pack["date"], day_pack["tickers"], day_pack["corr"], Config.N_CLUSTERS
            )
        if labels_np is None or sponge_phase == 3:
            labels_np, sponge_phase = run_sponge_clustering(
                day_pack["corr"], Config.N_CLUSTERS,
                min_size=Config.SPONGE_MIN_CLUSTER_SIZE,
            )

        if sponge_phase == 3:
            tqdm.write(
                f"[Pretrain] SPONGE Phase 3 (fallback) on "
                f"{day_pack['date'].strftime('%Y-%m-%d')} — skipping"
            )
            continue

        bet_sample = build_bet_sample(day_pack, labels_np)
        history_samples.append(bet_sample)
        used_pretrain += 1
        cursor = pos + 1

        if used_pretrain % 100 == 0:
            tqdm.write(f"[Pretrain] Collected {used_pretrain} days...")

        if used_pretrain >= Config.PRETRAIN_DAYS:
            break

    if len(history_samples) < 2:
        print("Insufficient pretrain samples.")
        return

    print(f"\n>>> Phase 1b: Pre-train on {len(history_samples)} days")
    train_betting_model(
        bet_model, bet_opt, list(history_samples),
        epochs=Config.BET_EPOCHS_PRETRAIN, prefix="Pretrain",
        val_ratio=Config.VAL_RATIO, patience=Config.EARLY_STOP_PATIENCE,
        cosine_t0=Config.COSINE_T0,
    )

    # ----------------------------
    # === WEIGHT EXPORT (no-op unless WEIGHT_DUMP_PATH is set) ===
    _wt_dump = []
    _wt_bad = [0]
    _wt_path = os.environ.get('WEIGHT_DUMP_PATH', '')
    if _wt_path:
        import atexit as _atexit, pickle as _wpkl
        def _wt_flush():
            try:
                with open(_wt_path, 'wb') as _fh:
                    _wpkl.dump(_wt_dump, _fh, protocol=4)
                print(f'[weights] wrote {len(_wt_dump)} days -> {_wt_path} '
                      f'({_wt_bad[0]} length mismatches)', flush=True)
            except Exception as _e:
                print(f'[weights] dump FAILED: {_e}', flush=True)
        _atexit.register(_wt_flush)
    # Phase 2: Online trading
    # ----------------------------
    print("\n>>> Phase 2: Online trading (SPONGE+L1Norm)")
    pnl_hist = []
    hist_pnl_bot, hist_pnl_mid, hist_pnl_top = [], [], []
    online_day_counter = 0
    diag_hist = {
        "theta_std": [], "cosine": [], "rank_ic": [],
        "long_ratio": [], "attn_entropy": [], "sponge_phase": [],
    }
    diag_attn_profiles = []

    for pos in tqdm(range(cursor, len(all_indices)), desc="Online Days"):
        idx = all_indices[pos]
        day_pack = prepare_day_pack(idx, residuals, raw_returns, caps, prices.index)
        if day_pack is None:
            continue

        # [MR-Net] Try to load pre-computed refined cluster; fallback to SPONGE if stale/missing.
        labels_np, sponge_phase = None, None
        if Config.USE_REFINED_CLUSTERS:
            labels_np, sponge_phase = get_refined_cluster_for_day(
                day_pack["date"], day_pack["tickers"], day_pack["corr"], Config.N_CLUSTERS
            )
        if labels_np is None or sponge_phase == 3:
            labels_np, sponge_phase = run_sponge_clustering(
                day_pack["corr"], Config.N_CLUSTERS,
                min_size=Config.SPONGE_MIN_CLUSTER_SIZE,
            )
        n_active = len(np.unique(labels_np))

        if sponge_phase == 3:
            tqdm.write(f"[WARNING] SPONGE Phase 3 on {day_pack['date'].strftime('%Y-%m-%d')}")

        # Periodic re-estimation
        if online_day_counter > 0 and online_day_counter % Config.RE_ESTIMATE_FREQ == 0:
            if len(history_samples) >= Config.MIN_TRAIN_DAYS:
                with torch.no_grad():
                    last_layer = bet_model.betting_head.ffn[-1]
                    last_layer.bias.data *= Config.BIAS_DECAY_FACTOR
                tqdm.write(f"[Re-Est] Bias decay applied (factor={Config.BIAS_DECAY_FACTOR})")

                tqdm.write(f"\n[Re-Est] Retraining on {len(history_samples)} days...")
                bet_opt = create_fresh_optimizer(bet_model, lr=Config.BET_LR_FINETUNE)
                train_betting_model(
                    bet_model, bet_opt, list(history_samples),
                    epochs=Config.BET_EPOCHS_FINETUNE,
                    prefix=f"Re-Est - {day_pack['date'].strftime('%Y-%m-%d')}",
                    val_ratio=Config.VAL_RATIO,
                    patience=Config.EARLY_STOP_PATIENCE_FINETUNE,
                    cosine_t0=Config.COSINE_T0_FINETUNE,
                )

        today_sample = build_bet_sample(day_pack, labels_np)

        # Inference
        bet_model.eval()
        with torch.no_grad():
            weights, raw_bets, diag_out = bet_model(today_sample["x_seq"], return_diag=True)

            vol_scalar = 1.0
            if len(pnl_hist) >= Config.VOL_LOOKBACK:
                recent_pnl = np.array(pnl_hist[-Config.VOL_LOOKBACK:])
                realized_vol = np.std(recent_pnl) * np.sqrt(252)
                if realized_vol > 1e-6:
                    vol_scalar = min(Config.VOL_TARGET_ANNUAL / realized_vol, Config.VOL_SCALAR_CAP)
                    weights = weights * vol_scalar

            weights = torch.clamp(weights, -Config.POSITION_CLIP_MAX, Config.POSITION_CLIP_MAX)
            # L1 re-normalization after clipping (整体 scale, 不分别 rescale 正负)
            l1 = torch.sum(torch.abs(weights))
            if l1 > 1e-8:
                weights = weights / l1

            day_pnl = torch.sum(weights * today_sample["y_target"]).item()

            abs_w = torch.abs(weights)
            q70 = torch.quantile(abs_w, 0.70)
            q95 = torch.quantile(abs_w, 0.95)
            mask_bot = abs_w <= q70
            mask_mid = (abs_w > q70) & (abs_w <= q95)
            mask_top = abs_w > q95
            pnl_bot = torch.sum(weights[mask_bot] * today_sample["y_target"][mask_bot]).item()
            pnl_mid = torch.sum(weights[mask_mid] * today_sample["y_target"][mask_mid]).item()
            pnl_top = torch.sum(weights[mask_top] * today_sample["y_target"][mask_top]).item()

            theta = diag_out["theta"]
            time_w = diag_out["attn_weights"]

            rank_ic = compute_rank_ic(raw_bets, today_sample["y_target"])
            theta_norm_std, theta_cosine_mean = compute_theta_diversity(theta)
            attn_profile, attn_entropy, attn_peak_pos = compute_attn_stats(time_w)
            cl_stats = compute_cluster_stats(labels_np)

            n_stocks = today_sample["x_seq"].shape[0]
            n_long = int((raw_bets > 1e-8).sum().item())
            n_short = int((raw_bets < -1e-8).sum().item())
            long_ratio = n_long / max(n_long + n_short, 1)
            active_bet_ratio = float((abs_w > 1e-3).sum().item()) / max(n_stocks, 1)
            raw_bet_std = raw_bets.std().item() if n_stocks > 1 else 0.0

        pnl_hist.append(day_pnl)
        hist_pnl_bot.append(pnl_bot)
        hist_pnl_mid.append(pnl_mid)
        hist_pnl_top.append(pnl_top)

        if sponge_phase < 3:
            history_samples.append(today_sample)

        gross_lev = float(torch.sum(torch.abs(weights)).item())
        net_exp = float(torch.sum(weights).item())
        if _wt_path:  # === WEIGHT EXPORT ===
            # `weights` is computed on the MASKED universe: build_bet_sample drops
            # stocks whose cluster is smaller than SPONGE_MIN_CLUSTER_SIZE (:607).
            # Exporting day_pack['tickers'] unmasked mis-keys the vector and makes
            # turnover uncomputable — measured 99.6% of days wrong on kmeans_ret.
            _u, _c = np.unique(labels_np, return_counts=True)
            _keep = set(_u[_c >= Config.SPONGE_MIN_CLUSTER_SIZE].tolist())
            _tk = [t for t, l in zip(day_pack['tickers'], labels_np) if l in _keep]
            _wv = weights.detach().cpu().numpy().astype('float32')
            if len(_tk) != len(_wv):
                _wt_bad[0] += 1
                if _wt_bad[0] <= 3:
                    print(f'[weights] LENGTH MISMATCH at {day_pack["date"]}: '
                          f'tickers={len(_tk)} weights={len(_wv)}', flush=True)
            _wt_dump.append((day_pack['date'], _tk, _wv))
        cum_pnl = float(np.sum(pnl_hist))
        ann_ret = float(np.mean(pnl_hist) * 252.0) if pnl_hist else 0.0
        sharpe = (float(np.mean(pnl_hist) / (np.std(pnl_hist) + 1e-12) * np.sqrt(252.0))
                  if len(pnl_hist) > 5 else 0.0)
        max_dd = (float(np.max(np.maximum.accumulate(np.cumsum(pnl_hist)) - np.cumsum(pnl_hist)))
                  if pnl_hist else 0.0)

        logger.log({
            "Date": day_pack["date"], "DailyPnL": day_pnl,
            "CumulativePnL": cum_pnl, "AnnReturn": ann_ret,
            "Sharpe": sharpe, "MaxDrawdown": max_dd,
            "N_Clusters": n_active, "N_Long": n_long, "N_Short": n_short,
            "GrossLeverage": gross_lev, "NetExposure": net_exp,
            "VolScalar": vol_scalar,
        })

        diag_logger.log({
            "Date": day_pack["date"], "N_Stocks": n_stocks,
            "ThetaNormStd": theta_norm_std, "ThetaCosineMean": theta_cosine_mean,
            "TimePoolEntropy": attn_entropy, "TimePoolPeakPos": attn_peak_pos,
            "RankIC": rank_ic, "RawBetStd": raw_bet_std,
            "LongRatio": long_ratio, "ActiveBetRatio": active_bet_ratio,
            "ClSizeMean": cl_stats["cl_size_mean"], "ClSizeStd": cl_stats["cl_size_std"],
            "ClSizeMin": cl_stats["cl_size_min"], "ClSizeMax": cl_stats["cl_size_max"],
            "SpongePhase": sponge_phase,
        })

        diag_hist["theta_std"].append(theta_norm_std)
        diag_hist["cosine"].append(theta_cosine_mean)
        diag_hist["rank_ic"].append(rank_ic)
        diag_hist["long_ratio"].append(long_ratio)
        diag_hist["attn_entropy"].append(attn_entropy)
        diag_hist["sponge_phase"].append(sponge_phase)
        diag_attn_profiles.append(attn_profile)

        online_day_counter += 1

        if online_day_counter % 5 == 0:
            fig, axs = plt.subplots(2, 2, figsize=(16, 10))
            fig.suptitle(
                f"SPONGE+L1Norm - {day_pack['date'].strftime('%Y-%m-%d')} | Sharpe={sharpe:.2f}",
                fontsize=14,
            )

            sorted_indices = np.argsort(labels_np)
            sorted_corr = day_pack["corr"][sorted_indices][:, sorted_indices]
            im = axs[0, 0].imshow(sorted_corr, aspect='auto', cmap='RdBu_r', interpolation='none', vmin=-1, vmax=1)
            axs[0, 0].set_title("SPONGE Clustered Correlation"); fig.colorbar(im, ax=axs[0, 0])

            unique_lbl, counts_lbl = np.unique(labels_np, return_counts=True)
            axs[0, 1].bar(unique_lbl, counts_lbl, color='skyblue', edgecolor='black')
            axs[0, 1].set_title("Cluster Size Distribution")

            axs[1, 0].hist(weights.cpu().numpy(), bins=50, color='coral', edgecolor='black', alpha=0.7)
            axs[1, 0].set_title("Bet Size Distribution")

            axs[1, 1].plot(np.cumsum(hist_pnl_bot), label="Bottom 70%")
            axs[1, 1].plot(np.cumsum(hist_pnl_mid), label="70%-95%")
            axs[1, 1].plot(np.cumsum(hist_pnl_top), label="Top 5%")
            axs[1, 1].set_title("PnL by Bet Quantiles"); axs[1, 1].legend()

            plt.tight_layout(rect=[0, 0.03, 1, 0.95])
            plt.savefig(os.path.join(dash_dir, f"dash_{day_pack['date'].strftime('%Y%m%d')}.png"))
            plt.close(fig)

        if online_day_counter % Config.DIAG_DASH_FREQ == 0 and online_day_counter > 0:
            n_pts = len(diag_hist["theta_std"])
            win = min(252, n_pts)
            fig, axs = plt.subplots(3, 2, figsize=(18, 16))
            fig.suptitle(
                f"Diagnostics SPONGE+L1Norm - {day_pack['date'].strftime('%Y-%m-%d')} "
                f"(day {online_day_counter})",
                fontsize=16,
            )

            arr = np.array(diag_hist["theta_std"])
            roll = pd.Series(arr).rolling(win).mean().values if n_pts >= win else arr
            axs[0, 0].plot(arr, alpha=0.2, color='gray', linewidth=0.5)
            axs[0, 0].plot(roll, color='teal', linewidth=1.2)
            axs[0, 0].set_title(f"Theta norm std (rolling {win}d)")

            arr = np.array(diag_hist["rank_ic"])
            roll = pd.Series(arr).rolling(win).mean().values if n_pts >= win else arr
            axs[0, 1].plot(arr, alpha=0.12, color='gray', linewidth=0.5)
            axs[0, 1].plot(roll, color='royalblue', linewidth=1.2)
            axs[0, 1].axhline(0, color='black', linewidth=0.5, linestyle='--')
            axs[0, 1].set_title(f"Rank IC (rolling {win}d)")

            recent = diag_attn_profiles[-Config.DIAG_DASH_FREQ:]
            mean_prof = np.mean(recent, axis=0)
            axs[1, 0].bar(range(len(mean_prof)), mean_prof, color='coral', alpha=0.8)
            axs[1, 0].set_title(f"LongConv kernel (last {Config.DIAG_DASH_FREQ}d)")

            arr = np.array(diag_hist["long_ratio"])
            roll = pd.Series(arr).rolling(win).mean().values if n_pts >= win else arr
            axs[1, 1].plot(arr, alpha=0.12, color='gray', linewidth=0.5)
            axs[1, 1].plot(roll, color='green', linewidth=1.2)
            axs[1, 1].axhline(0.5, color='black', linewidth=0.5, linestyle='--')
            axs[1, 1].set_ylim(-0.05, 1.05)
            axs[1, 1].set_title(f"Long ratio (rolling {win}d)")

            ax5 = axs[2, 0]
            cum = np.cumsum(pnl_hist)
            ax5.plot(cum, color='black', linewidth=1.0)
            ax5.set_ylabel("Cumulative PnL")
            if n_pts >= 252:
                ax5b = ax5.twinx()
                pnl_s = pd.Series(pnl_hist)
                r_sh = (pnl_s.rolling(252).mean() / (pnl_s.rolling(252).std() + 1e-12) * np.sqrt(252)).values
                ax5b.plot(r_sh, color='purple', linewidth=0.8, alpha=0.7)
                ax5b.set_ylabel("Rolling 252d Sharpe", color='purple')
            ax5.set_title("Cumulative PnL & Rolling Sharpe")

            ph_arr = np.array(diag_hist["sponge_phase"])
            n_days = np.arange(len(ph_arr)) + 1
            cum_p2 = np.cumsum(ph_arr >= 2) / n_days
            cum_p3 = np.cumsum(ph_arr == 3) / n_days
            axs[2, 1].plot(cum_p2, color='orange', linewidth=1.0, label="Phase 2 (shrinkage)")
            axs[2, 1].plot(cum_p3, color='red', linewidth=1.0, label="Phase 3 (random)")
            axs[2, 1].set_title("SPONGE fallback rates")
            axs[2, 1].legend(fontsize=8)

            plt.tight_layout(rect=[0, 0.02, 1, 0.96])
            plt.savefig(os.path.join(diag_dash_dir, f"diag_{day_pack['date'].strftime('%Y%m%d')}.png"))
            plt.close(fig)

    if pnl_hist:
        plt.figure(figsize=(10, 5))
        plt.plot(np.cumsum(pnl_hist))
        plt.title("SPONGE + L1 Norm — Cumulative PnL")
        plt.grid(True, alpha=0.3)
        plt.savefig(os.path.join(Config.OUTPUT_DIR, "final_pnl.png"))
        plt.close()

    print("\n>>> Pipeline complete.")


if __name__ == "__main__":
    run_pipeline()
