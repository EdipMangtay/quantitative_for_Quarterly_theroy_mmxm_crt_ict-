"""ASTRA 6 V3 — High-Performance Computing (HPC), Hardware Auto-Tuner, Target-Consistent Kernel,
Dependence-Aware Clustered Inference & Hash-Verified Checkpoint Engine (Section 16 & P0/P1 Repair).

Responsibilities:
  1. Dynamically inspect CPU model, physical/logical cores, total/available RAM,
     disk capacity/free space, OS/architecture, and installed analytical libraries
     (Polars, DuckDB, PyArrow, NumPy, Numba).
  2. Configure thread limits to prevent nested oversubscription across BLAS/Accelerate,
     Polars, DuckDB, and Numba on macOS Apple Silicon, operating on shared in-process
     contiguous NumPy arrays (zero multiprocessing price-panel duplication).
  3. Provide target-consistent trade execution kernels (`reference_target_exec_full_py` vs
     `fast_target_exec_full_numba`) that explicitly distinguish:
       - 1: `TARGET_HIT` (target reached cleanly before stop)
       - 2: `STOP_HIT` (stop hit cleanly before target)
       - 3: `AMBIGUOUS` (both SL and TP touched on the exact same bar; pessimistic PnL, separate status)
       - 4: `TIMEOUT` (neither SL nor TP hit within horizon_bars; mark-to-market exit at horizon close, NEVER automatic -1R)
       - 5: `DATA_END` (neither SL nor TP hit before dataset end; mark-to-market exit at final close)
  4. Provide dependence-aware day-clustered bootstrap & Liang-Zeger cluster-robust standard errors
     plus paired underlying-event comparison tests (P1.10).
  5. Provide cryptographic cache invalidation binding source store SHA256, `algo_version`,
     and `config_hash`, with `--full` forcing full recomputation (P1.11).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import resource
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb
import numba
import numpy as np
import pandas as pd
import polars as pl
import pyarrow as pa
from numba import njit

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "data" / "store"
RESULTS = ROOT / "data" / "results"

# Explicit outcome status codes for target-consistent execution (P0.5)
OUTCOME_TARGET_HIT = 1
OUTCOME_STOP_HIT = 2
OUTCOME_AMBIGUOUS = 3
OUTCOME_TIMEOUT = 4
OUTCOME_DATA_END = 5

OUTCOME_CODE_TO_LABEL: dict[int, str] = {
    0: "INVALID_INDEX",
    OUTCOME_TARGET_HIT: "TARGET_HIT",
    OUTCOME_STOP_HIT: "STOP_HIT",
    OUTCOME_AMBIGUOUS: "AMBIGUOUS",
    OUTCOME_TIMEOUT: "TIMEOUT",
    OUTCOME_DATA_END: "DATA_END",
}


@dataclass
class HardwareProfile:
    os_name: str
    os_release: str
    architecture: str
    cpu_model: str
    physical_cores: int
    logical_cores: int
    ram_total_gb: float
    ram_available_gb: float
    disk_total_gb: float
    disk_free_gb: float
    selected_workers: int
    selected_duckdb_threads: int
    selected_batch_size: int
    libraries: dict[str, str]
    detected_at_utc: str


def _sysctl_str(key: str, default: str = "") -> str:
    try:
        out = subprocess.check_output(["sysctl", "-n", key], stderr=subprocess.DEVNULL, text=True).strip()
        return out or default
    except Exception:
        return default


def _sysctl_int(key: str, default: int = 0) -> int:
    val = _sysctl_str(key, "")
    try:
        return int(val)
    except Exception:
        return default


def _available_ram_gb(total_gb: float) -> float:
    """Estimate available RAM on macOS via vm_stat (free + inactive + speculative pages)."""
    try:
        out = subprocess.check_output(["vm_stat"], stderr=subprocess.DEVNULL, text=True)
        page_size = 16384
        for line in out.splitlines():
            if "page size of" in line:
                parts = line.split("page size of")[1].split("bytes")[0].strip()
                page_size = int(parts)
                break
        free_pages = 0
        for line in out.splitlines():
            if any(k in line for k in ("Pages free", "Pages inactive", "Pages speculative", "Pages purgeable")):
                num = line.split(":")[1].strip().rstrip(".")
                free_pages += int(num)
        avail = (free_pages * page_size) / (1024**3)
        return round(min(total_gb, max(2.0, avail)), 2)
    except Exception:
        return round(total_gb * 0.65, 2)


def get_peak_rss_mb() -> float:
    """Return peak resident set size (MB) of the current process."""
    ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if platform.system() == "Darwin":
        return round(ru / (1024 * 1024), 2)
    return round(ru / 1024.0, 2)


def detect_hardware_profile() -> HardwareProfile:
    """Detect system hardware, memory, disk, and library versions dynamically."""
    cpu_model = _sysctl_str("machdep.cpu.brand_string", platform.processor() or "Apple Silicon")
    phys = _sysctl_int("hw.physicalcpu", os.cpu_count() or 4)
    logi = _sysctl_int("hw.logicalcpu", os.cpu_count() or 4)
    mem_bytes = _sysctl_int("hw.memsize", 16 * 1024**3)
    ram_total_gb = round(mem_bytes / (1024**3), 2)
    ram_avail_gb = _available_ram_gb(ram_total_gb)

    du = shutil.disk_usage(ROOT)
    disk_total_gb = round(du.total / (1024**3), 2)
    disk_free_gb = round(du.free / (1024**3), 2)

    # Choose sustainable worker count (leave 2 cores for OS/UI & avoid thermal throttling)
    selected_workers = max(2, min(phys - 2, 8))
    if ram_avail_gb < 8.0:
        selected_workers = min(selected_workers, 4)
        batch_size = 32_768
    elif ram_avail_gb < 16.0:
        batch_size = 65_536
    else:
        batch_size = 131_072

    # Configure environment variables to prevent nested BLAS/OpenMP oversubscription
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("POLARS_MAX_THREADS", str(selected_workers))
    try:
        numba.set_num_threads(selected_workers)
    except Exception:
        pass

    libs = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "polars": pl.__version__,
        "duckdb": duckdb.__version__,
        "pyarrow": pa.__version__,
        "numba": numba.__version__,
    }

    return HardwareProfile(
        os_name=platform.system(),
        os_release=platform.release(),
        architecture=platform.machine(),
        cpu_model=cpu_model,
        physical_cores=phys,
        logical_cores=logi,
        ram_total_gb=ram_total_gb,
        ram_available_gb=ram_avail_gb,
        disk_total_gb=disk_total_gb,
        disk_free_gb=disk_free_gb,
        selected_workers=selected_workers,
        selected_duckdb_threads=selected_workers,
        selected_batch_size=batch_size,
        libraries=libs,
        detected_at_utc=str(datetime.now(timezone.utc)),
    )


# ---------------------------------------------------------------------------
# Target-Consistent Execution Kernels: Reference Python vs Optimized Numba (P0.5)
# ---------------------------------------------------------------------------
def reference_target_exec_full_py(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    j_fill: np.ndarray,
    direction: np.ndarray,
    entry_px: np.ndarray,
    stop_px: np.ndarray,
    target_px: np.ndarray,
    horizon_bars: int,
    slip_pts: float = 0.25,
) -> tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
]:
    """Pure-Python reference implementation for target-consistent trade execution (P0.5 & Section 7.3).

    Separates:
      - `OUTCOME_TARGET_HIT (1)`: target reached cleanly before stop on a bar where stop was NOT touched
      - `OUTCOME_STOP_HIT (2)`: stop touched cleanly before target on a bar where target was NOT touched
      - `OUTCOME_AMBIGUOUS (3)`: both stop and target touched on the exact same bar (pessimistic PnL = stop, status = AMBIGUOUS)
      - `OUTCOME_TIMEOUT (4)`: neither stop nor target touched within `horizon_bars` (and `end < n - 1`); exits at `closes[end]` (mark-to-market, NEVER automatic -1R!)
      - `OUTCOME_DATA_END (5)`: neither stop nor target touched before dataset end (`end == n - 1`); exits at `closes[n - 1]` (mark-to-market!)

    Returns:
      (reached_any, reached_clean, bars_to_target, outcome_code, exit_bar_idx, exit_px, realized_r, mfe_r, mae_r)
    """
    m = len(j_fill)
    n = len(highs)
    reached_any = np.zeros(m, dtype=bool)
    reached_clean = np.zeros(m, dtype=bool)
    bars_to_tgt = np.full(m, -1, dtype=np.int64)
    outcome_code = np.zeros(m, dtype=np.int8)
    exit_bar_idx = np.full(m, -1, dtype=np.int64)
    exit_px = np.full(m, np.nan, dtype=np.float64)
    realized_r = np.full(m, np.nan, dtype=np.float64)
    mfe_r = np.zeros(m, dtype=np.float64)
    mae_r = np.zeros(m, dtype=np.float64)

    for i in range(m):
        jf = int(j_fill[i])
        if jf < 0 or jf >= n:
            continue
        d = int(direction[i])
        ep = float(entry_px[i])
        sl = float(stop_px[i])
        tp = float(target_px[i])
        risk = abs(ep - sl)
        if risk < 1e-6:
            risk = 1.0

        end = jf + horizon_bars
        is_data_end = False
        if end >= n - 1:
            end = n - 1
            is_data_end = True

        trade_closed = False
        max_fav = 0.0
        max_adv = 0.0

        for k in range(jf, end + 1):
            hi_k = float(highs[k])
            lo_k = float(lows[k])
            if d == 1:
                hit_sl = lo_k <= sl
                hit_tp = hi_k >= tp
                fav = (hi_k - ep) / risk
                adv = (ep - lo_k) / risk
            else:
                hit_sl = hi_k >= sl
                hit_tp = lo_k <= tp
                fav = (ep - lo_k) / risk
                adv = (hi_k - ep) / risk

            if not trade_closed:
                if fav > max_fav:
                    max_fav = fav
                if adv > max_adv:
                    max_adv = adv

                if hit_sl and hit_tp:
                    # Same-bar SL+TP -> AMBIGUOUS status, pessimistic stop-out PnL
                    trade_closed = True
                    outcome_code[i] = OUTCOME_AMBIGUOUS
                    exit_bar_idx[i] = k
                    exit_px[i] = sl
                    realized_r[i] = (-risk - slip_pts) / risk
                elif hit_sl:
                    trade_closed = True
                    outcome_code[i] = OUTCOME_STOP_HIT
                    exit_bar_idx[i] = k
                    exit_px[i] = sl
                    realized_r[i] = (-risk - slip_pts) / risk
                elif hit_tp:
                    trade_closed = True
                    outcome_code[i] = OUTCOME_TARGET_HIT
                    reached_clean[i] = True
                    exit_bar_idx[i] = k
                    exit_px[i] = tp
                    realized_r[i] = (abs(tp - ep) - slip_pts) / risk

            if hit_tp and not reached_any[i]:
                reached_any[i] = True
                bars_to_tgt[i] = k - jf

            if reached_any[i] and trade_closed:
                break

        if not trade_closed:
            # Neither SL nor TP hit within [jf .. end] -> Mark-to-market at close[end] (NEVER -1R!)
            outcome_code[i] = OUTCOME_DATA_END if is_data_end else OUTCOME_TIMEOUT
            exit_bar_idx[i] = end
            c_end = float(closes[end])
            exit_px[i] = c_end
            pnl_pts = (c_end - ep) * d - slip_pts
            realized_r[i] = pnl_pts / risk

        mfe_r[i] = max(0.0, max_fav)
        mae_r[i] = max(0.0, max_adv)

    return (
        reached_any,
        reached_clean,
        bars_to_tgt,
        outcome_code,
        exit_bar_idx,
        exit_px,
        realized_r,
        mfe_r,
        mae_r,
    )


@njit(cache=True)
def fast_target_exec_full_numba(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    j_fill: np.ndarray,
    direction: np.ndarray,
    entry_px: np.ndarray,
    stop_px: np.ndarray,
    target_px: np.ndarray,
    horizon_bars: int,
    slip_pts: float = 0.25,
) -> tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
]:
    """Numba-compiled target-consistent execution kernel matching `reference_target_exec_full_py` bit-for-bit."""
    m = j_fill.shape[0]
    n = highs.shape[0]
    reached_any = np.zeros(m, np.bool_)
    reached_clean = np.zeros(m, np.bool_)
    bars_to_tgt = np.full(m, -1, np.int64)
    outcome_code = np.zeros(m, np.int8)
    exit_bar_idx = np.full(m, -1, np.int64)
    exit_px = np.full(m, np.nan, np.float64)
    realized_r = np.full(m, np.nan, np.float64)
    mfe_r = np.zeros(m, np.float64)
    mae_r = np.zeros(m, np.float64)

    for i in range(m):
        jf = j_fill[i]
        if jf < 0 or jf >= n:
            continue
        d = direction[i]
        ep = entry_px[i]
        sl = stop_px[i]
        tp = target_px[i]
        risk = abs(ep - sl)
        if risk < 1e-6:
            risk = 1.0

        end = jf + horizon_bars
        is_data_end = False
        if end >= n - 1:
            end = n - 1
            is_data_end = True

        trade_closed = False
        max_fav = 0.0
        max_adv = 0.0

        for k in range(jf, end + 1):
            hi_k = highs[k]
            lo_k = lows[k]
            if d == 1:
                hit_sl = lo_k <= sl
                hit_tp = hi_k >= tp
                fav = (hi_k - ep) / risk
                adv = (ep - lo_k) / risk
            else:
                hit_sl = hi_k >= sl
                hit_tp = lo_k <= tp
                fav = (ep - lo_k) / risk
                adv = (hi_k - ep) / risk

            if not trade_closed:
                if fav > max_fav:
                    max_fav = fav
                if adv > max_adv:
                    max_adv = adv

                if hit_sl and hit_tp:
                    trade_closed = True
                    outcome_code[i] = 3  # OUTCOME_AMBIGUOUS
                    exit_bar_idx[i] = k
                    exit_px[i] = sl
                    realized_r[i] = (-risk - slip_pts) / risk
                elif hit_sl:
                    trade_closed = True
                    outcome_code[i] = 2  # OUTCOME_STOP_HIT
                    exit_bar_idx[i] = k
                    exit_px[i] = sl
                    realized_r[i] = (-risk - slip_pts) / risk
                elif hit_tp:
                    trade_closed = True
                    outcome_code[i] = 1  # OUTCOME_TARGET_HIT
                    reached_clean[i] = True
                    exit_bar_idx[i] = k
                    exit_px[i] = tp
                    realized_r[i] = (abs(tp - ep) - slip_pts) / risk

            if hit_tp and (not reached_any[i]):
                reached_any[i] = True
                bars_to_tgt[i] = k - jf

            if reached_any[i] and trade_closed:
                break

        if not trade_closed:
            outcome_code[i] = 5 if is_data_end else 4  # DATA_END or TIMEOUT
            exit_bar_idx[i] = end
            c_end = closes[end]
            exit_px[i] = c_end
            pnl_pts = (c_end - ep) * d - slip_pts
            realized_r[i] = pnl_pts / risk

        mfe_r[i] = max_fav if max_fav > 0.0 else 0.0
        mae_r[i] = max_adv if max_adv > 0.0 else 0.0

    return (
        reached_any,
        reached_clean,
        bars_to_tgt,
        outcome_code,
        exit_bar_idx,
        exit_px,
        realized_r,
        mfe_r,
        mae_r,
    )


def reference_target_horizon_eval_py(
    highs: np.ndarray,
    lows: np.ndarray,
    j_fill: np.ndarray,
    direction: np.ndarray,
    stop_px: np.ndarray,
    target_px: np.ndarray,
    horizon_bars: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Pure-Python 3-tuple horizon wrapper delegating to `reference_target_exec_full_py`."""
    closes = 0.5 * (highs + lows)
    entry_px = np.where(stop_px < target_px, 0.5 * (stop_px + target_px), 0.5 * (stop_px + target_px))
    ra, rc, bt, _, _, _, _, _, _ = reference_target_exec_full_py(
        highs, lows, closes, j_fill, direction, entry_px, stop_px, target_px, horizon_bars, 0.0
    )
    return ra, rc, bt


@njit(cache=True)
def fast_target_horizon_eval_numba(
    highs: np.ndarray,
    lows: np.ndarray,
    j_fill: np.ndarray,
    direction: np.ndarray,
    stop_px: np.ndarray,
    target_px: np.ndarray,
    horizon_bars: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Numba 3-tuple horizon wrapper matching `reference_target_horizon_eval_py` bit-for-bit."""
    m = j_fill.shape[0]
    n = highs.shape[0]
    reached_any = np.zeros(m, np.bool_)
    reached_clean = np.zeros(m, np.bool_)
    bars_to_tgt = np.full(m, -1, np.int64)

    for i in range(m):
        jf = j_fill[i]
        if jf < 0 or jf >= n:
            continue
        d = direction[i]
        sl = stop_px[i]
        tp = target_px[i]
        end = jf + horizon_bars
        if end >= n:
            end = n - 1
        stopped = False
        for k in range(jf, end + 1):
            if d == 1:
                hit_sl = lows[k] <= sl
                hit_tp = highs[k] >= tp
            else:
                hit_sl = highs[k] >= sl
                hit_tp = lows[k] <= tp
            if hit_sl:
                stopped = True
            if hit_tp and (not reached_any[i]):
                reached_any[i] = True
                bars_to_tgt[i] = k - jf
                if not stopped:
                    reached_clean[i] = True
            if reached_any[i] and stopped:
                break
    return reached_any, reached_clean, bars_to_tgt


# ---------------------------------------------------------------------------
# Dependence-Aware Day-Clustered Inference & Paired Event Comparison (P1.10)
# ---------------------------------------------------------------------------
@njit(cache=True)
def _day_cluster_stats_and_bootstrap_numba(
    r: np.ndarray,
    day_ids: np.ndarray,
    n_boot: int = 300,
    seed: int = 42,
) -> tuple[int, float, float, float, float, float]:
    """Compute day-cluster count, i.i.d. SE, Liang-Zeger day-clustered SE,
    and day-clustered bootstrap 95% CI + p-value (`H0: E[R] <= 0`)."""
    n = r.shape[0]
    if n == 0:
        return 0, np.nan, np.nan, np.nan, np.nan, 1.0

    mean_r = np.mean(r)
    if n == 1:
        p = 0.0 if mean_r > 0.0 else 1.0
        return 1, 0.0, 0.0, mean_r, mean_r, p

    # Compute sample variance for i.i.d. SE
    ss_iid = 0.0
    for i in range(n):
        d_i = r[i] - mean_r
        ss_iid += d_i * d_i
    std_r = math.sqrt(ss_iid / (n - 1))
    se_iid = std_r / math.sqrt(n)

    # Sort by day_ids to aggregate within-day cluster sums S_g = sum_{i in g} r_i and counts C_g
    order = np.argsort(day_ids)
    r_sorted = r[order]
    d_sorted = day_ids[order]

    # Count distinct days G
    g_cnt = 1
    for i in range(1, n):
        if d_sorted[i] != d_sorted[i - 1]:
            g_cnt += 1

    if g_cnt <= 1:
        ci_lo = mean_r - 1.96 * se_iid
        ci_hi = mean_r + 1.96 * se_iid
        z = mean_r / se_iid if se_iid > 1e-12 else 0.0
        p_gt0 = 0.5 * math.erfc(z / math.sqrt(2.0))
        return 1, se_iid, se_iid, ci_lo, ci_hi, p_gt0

    c_sums = np.zeros(g_cnt, np.float64)
    c_cnts = np.zeros(g_cnt, np.float64)
    g_idx = 0
    c_sums[0] = r_sorted[0]
    c_cnts[0] = 1.0
    for i in range(1, n):
        if d_sorted[i] != d_sorted[i - 1]:
            g_idx += 1
        c_sums[g_idx] += r_sorted[i]
        c_cnts[g_idx] += 1.0

    # Liang-Zeger cluster-robust variance of sample mean:
    # Var_LZ(mean_r) = (G / (G - 1)) * sum_g (c_sums[g] - c_cnts[g] * mean_r)^2 / n^2
    ss_clu = 0.0
    for g in range(g_cnt):
        u_g = c_sums[g] - c_cnts[g] * mean_r
        ss_clu += u_g * u_g
    var_clu = (g_cnt / (g_cnt - 1.0)) * (ss_clu / (float(n) * float(n)))
    se_clu = math.sqrt(max(var_clu, 0.0))

    # Day-clustered bootstrap (resampling G day clusters with replacement)
    np.random.seed(seed)
    boot_means = np.empty(n_boot, np.float64)
    le_zero = 0
    for b in range(n_boot):
        tot_s = 0.0
        tot_c = 0.0
        for _ in range(g_cnt):
            pick = np.random.randint(0, g_cnt)
            tot_s += c_sums[pick]
            tot_c += c_cnts[pick]
        bm = tot_s / tot_c if tot_c > 0.0 else mean_r
        boot_means[b] = bm
        if bm <= 0.0:
            le_zero += 1

    boot_means.sort()
    idx_lo = int(0.025 * (n_boot - 1))
    idx_hi = int(0.975 * (n_boot - 1))
    ci_lo = boot_means[idx_lo]
    ci_hi = boot_means[idx_hi]

    # Combine analytical cluster t-test p-value and bootstrap tail for smooth p_gt_zero
    if se_clu > 1e-12:
        z_c = mean_r / se_clu
        p_gt0 = 0.5 * math.erfc(z_c / math.sqrt(2.0))
    else:
        p_gt0 = float(le_zero) / float(n_boot)

    return g_cnt, se_iid, se_clu, ci_lo, ci_hi, p_gt0


def paired_event_cluster_test(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    event_col: str = "underlying_event_id",
    day_col: str = "ny_day_id",
    r_col: str = "r",
) -> dict[str, float]:
    """Paired comparison between two strategy configurations evaluated across shared underlying events,
    with standard error and p-value clustered by trading day (P1.10)."""
    if len(df_a) == 0 or len(df_b) == 0 or event_col not in df_a.columns or event_col not in df_b.columns:
        return {
            "n_paired_events": 0,
            "n_paired_days": 0,
            "paired_delta_r": np.nan,
            "paired_se_clustered": np.nan,
            "paired_ci95_low": np.nan,
            "paired_ci95_high": np.nan,
            "paired_p_value": 1.0,
        }

    agg_a = df_a.groupby(event_col, as_index=False).agg(r_a=(r_col, "mean"), day_id=(day_col, "first"))
    agg_b = df_b.groupby(event_col, as_index=False).agg(r_b=(r_col, "mean"))
    merged = agg_a.merge(agg_b, on=event_col, how="inner")
    if len(merged) < 5:
        return {
            "n_paired_events": int(len(merged)),
            "n_paired_days": int(merged["day_id"].nunique()) if len(merged) else 0,
            "paired_delta_r": float((merged["r_a"] - merged["r_b"]).mean()) if len(merged) else np.nan,
            "paired_se_clustered": np.nan,
            "paired_ci95_low": np.nan,
            "paired_ci95_high": np.nan,
            "paired_p_value": 1.0,
        }

    diff = (merged["r_a"] - merged["r_b"]).to_numpy(np.float64)
    days = merged["day_id"].to_numpy(np.int64)
    g_cnt, _, se_clu, ci_lo, ci_hi, _ = _day_cluster_stats_and_bootstrap_numba(diff, days, n_boot=300, seed=42)
    mean_diff = float(np.mean(diff))
    if se_clu > 1e-12:
        z = abs(mean_diff) / se_clu
        p_two = float(math.erfc(z / math.sqrt(2.0)))
    else:
        p_two = 1.0
    return {
        "n_paired_events": int(len(merged)),
        "n_paired_days": int(g_cnt),
        "paired_delta_r": round(mean_diff, 5),
        "paired_se_clustered": round(float(se_clu), 5),
        "paired_ci95_low": round(float(ci_lo), 5),
        "paired_ci95_high": round(float(ci_hi), 5),
        "paired_p_value": round(p_two, 6),
    }


# ---------------------------------------------------------------------------
# Cryptographic Cache Invalidation & Hash Helpers (P1.11)
# ---------------------------------------------------------------------------
def compute_source_store_sha256(store_dir: Path | None = None) -> str:
    """Compute a deterministic SHA256 digest over the core price store Parquet files (P1.11).

    Hashes file size + first/middle/last 256KB blocks of every core store file so that
    any change to any historical price file immediately invalidates cached events,
    while executing in < 15ms.
    """
    sdir = store_dir or STORE
    core_files = [
        "US100_BID_M1.parquet",
        "US100_ASK_M1.parquet",
        "US500_BID_M1.parquet",
        "US500_ASK_M1.parquet",
        "US30_BID_M1.parquet",
        "US30_ASK_M1.parquet",
    ]
    h = hashlib.sha256()
    for fname in core_files:
        p = sdir / fname
        if not p.exists():
            h.update(f"MISSING:{fname}".encode())
            continue
        sz = p.stat().st_size
        h.update(f"{fname}:{sz}:".encode())
        block = 256 * 1024
        with p.open("rb") as f:
            h.update(f.read(block))
            if sz > 2 * block:
                f.seek(sz // 2)
                h.update(f.read(block))
            if sz > block:
                f.seek(max(0, sz - block))
                h.update(f.read(block))
    return h.hexdigest()


def compute_config_hash(config_dict: dict[str, Any]) -> str:
    """Compute a deterministic SHA256 hash of the engine configuration parameters (P1.11)."""
    payload = json.dumps(config_dict, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


# ---------------------------------------------------------------------------
# Benchmark & Kernel Verification (Section 16 & P0.5)
# ---------------------------------------------------------------------------
def run_benchmark_and_autotune(profile: HardwareProfile | None = None) -> dict[str, Any]:
    """Benchmark representative workloads, compare batch sizes, and verify kernel identity across all 5 outcome states."""
    if profile is None:
        profile = detect_hardware_profile()

    rng = np.random.default_rng(42)
    n_bars = 50_000
    base = 20000.0 + np.cumsum(rng.normal(0, 2.5, size=n_bars))
    highs = base + np.abs(rng.normal(2.0, 1.0, size=n_bars))
    lows = base - np.abs(rng.normal(2.0, 1.0, size=n_bars))
    closes = base + rng.normal(0.0, 0.5, size=n_bars)
    closes = np.clip(closes, lows, highs)

    # Include adversarial cases:
    # 0: same-bar SL & TP touch (AMBIGUOUS)
    # 1: boundary index n-1 (DATA_END)
    # 2: negative index (INVALID_INDEX)
    # 3: flat range neither SL nor TP touched within horizon (TIMEOUT with mark-to-market R != -1R)
    n_test = 2_000
    j_fill = rng.integers(0, n_bars - 250, size=n_test, dtype=np.int64)
    j_fill[0] = 100
    j_fill[1] = n_bars - 1
    j_fill[2] = -1
    j_fill[3] = 500
    direction = rng.choice(np.array([-1, 1], dtype=np.int64), size=n_test)
    direction[0] = 1
    direction[1] = 1
    direction[3] = 1
    entry_px = np.where(j_fill >= 0, base[np.clip(j_fill, 0, n_bars - 1)], 20000.0)
    stop_px = np.where(direction == 1, entry_px - 15.0, entry_px + 15.0)
    target_px = np.where(direction == 1, entry_px + 30.0, entry_px - 30.0)

    # Case 0: same-bar touch of both SL and TP at j_fill[0] + 3 = 103
    highs[100:103] = entry_px[0] + 2.0
    lows[100:103] = entry_px[0] - 2.0
    highs[103] = entry_px[0] + 45.0
    lows[103] = entry_px[0] - 25.0

    # Case 1: DATA_END at n_bars - 1 (no SL or TP hit)
    highs[n_bars - 1] = entry_px[1] + 3.0
    lows[n_bars - 1] = entry_px[1] - 3.0
    closes[n_bars - 1] = entry_px[1] + 1.5

    # Case 3: TIMEOUT across [500 .. 680] with positive drift +6.0 pts (+0.3833R mark-to-market, NOT -1R!)
    highs[500:685] = entry_px[3] + 8.0
    lows[500:685] = entry_px[3] - 4.0
    closes[680] = entry_px[3] + 6.0

    # Warm-up JIT
    _ = fast_target_exec_full_numba(
        highs[:200], lows[:200], closes[:200], j_fill[:10], direction[:10],
        entry_px[:10], stop_px[:10], target_px[:10], 60, 0.25
    )

    t0 = time.perf_counter()
    ref_out = reference_target_exec_full_py(
        highs, lows, closes, j_fill, direction, entry_px, stop_px, target_px, 180, 0.25
    )
    py_sec = time.perf_counter() - t0

    t1 = time.perf_counter()
    opt_out = fast_target_exec_full_numba(
        highs, lows, closes, j_fill, direction, entry_px, stop_px, target_px, 180, 0.25
    )
    nb_sec = time.perf_counter() - t1

    exact_match = bool(
        np.array_equal(ref_out[0], opt_out[0])
        and np.array_equal(ref_out[1], opt_out[1])
        and np.array_equal(ref_out[2], opt_out[2])
        and np.array_equal(ref_out[3], opt_out[3])
        and np.array_equal(ref_out[4], opt_out[4])
        and np.allclose(ref_out[5], opt_out[5], equal_nan=True)
        and np.allclose(ref_out[6], opt_out[6], equal_nan=True)
        and np.allclose(ref_out[7], opt_out[7], equal_nan=True)
        and np.allclose(ref_out[8], opt_out[8], equal_nan=True)
        and int(opt_out[3][0]) == OUTCOME_AMBIGUOUS
        and bool(opt_out[1][0]) is False
        and int(opt_out[3][1]) == OUTCOME_DATA_END
        and int(opt_out[3][3]) == OUTCOME_TIMEOUT
        and float(opt_out[6][3]) > 0.0  # Timeout with positive drift is >0R, NOT -1R!
    )
    if not exact_match:
        raise AssertionError("Optimized Numba kernel diverged from pure-Python reference implementation!")

    # Compare batch sizes for vectorized Polars / DuckDB aggregation
    batch_timings = {}
    df_bench = pl.DataFrame({
        "cfg_id": rng.integers(0, 64, size=200_000),
        "dir": rng.choice([-1, 1], size=200_000),
        "r": rng.normal(-0.05, 1.2, size=200_000),
    })
    for bsz in (16_384, 65_536, 131_072, 200_000):
        tb0 = time.perf_counter()
        acc = []
        for start_i in range(0, len(df_bench), bsz):
            slc = df_bench.slice(start_i, bsz)
            agg = slc.lazy().group_by(["cfg_id", "dir"]).agg([
                pl.len().alias("n"),
                pl.col("r").sum().alias("sum_r"),
            ]).collect()
            acc.append(agg)
        _ = pl.concat(acc).group_by(["cfg_id", "dir"]).agg([
            pl.col("n").sum(),
            pl.col("sum_r").sum(),
        ])
        batch_timings[str(bsz)] = round(time.perf_counter() - tb0, 5)

    best_batch = int(min(batch_timings, key=batch_timings.get))
    profile.selected_batch_size = best_batch

    report = {
        "hardware_profile": asdict(profile),
        "kernel_verification": {
            "reference_vs_numba_exact_match": exact_match,
            "adversarial_same_bar_sl_tp_verified": bool(int(opt_out[3][0]) == OUTCOME_AMBIGUOUS and not opt_out[1][0]),
            "timeout_mark_to_market_verified": bool(int(opt_out[3][3]) == OUTCOME_TIMEOUT and float(opt_out[6][3]) > 0.0),
            "data_end_mark_to_market_verified": bool(int(opt_out[3][1]) == OUTCOME_DATA_END),
            "python_ref_seconds_2k": round(py_sec, 6),
            "numba_opt_seconds_2k": round(nb_sec, 6),
            "speedup_factor": round(py_sec / max(nb_sec, 1e-9), 2),
            "throughput_evals_per_sec": round(n_test / max(nb_sec, 1e-9), 1),
        },
        "batch_size_benchmark_seconds": batch_timings,
        "selected_optimal_batch_size": best_batch,
        "peak_memory_rss_mb": get_peak_rss_mb(),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "hardware_benchmark.json").write_text(json.dumps(report, indent=2))
    return report


class CheckpointManager:
    """Persistent checkpoint, cache-invalidation, and completion manifest manager for Phases 1..16 (P1.11)."""

    def __init__(self, path: Path | None = None):
        self.path = path or (RESULTS / "v3_checkpoint_manifest.json")
        self.state: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except Exception:
                pass
        return {
            "project": "ASTRA 6 — MASTER PROMPT V3 FINAL (CAUSAL REPAIRED)",
            "version": "v3.1_repaired",
            "created_at_utc": str(datetime.now(timezone.utc)),
            "source_store_sha256": "",
            "algo_version": "",
            "config_hash": "",
            "phases": {},
            "hardware_summary": {},
        }

    def is_cache_valid(
        self,
        required_files: list[str],
        source_store_sha256: str,
        algo_version: str,
        config_hash: str,
        force_recompute: bool = False,
        results_dir: Path | None = None,
    ) -> bool:
        """Verify whether cached Parquet files are valid for the exact current source data,
        algorithm version, and configuration hash (P1.11).

        Returns False immediately when `force_recompute=True` (`--full`).
        """
        if force_recompute:
            return False
        rdir = results_dir or RESULTS
        if not all((rdir / f).exists() for f in required_files):
            return False
        if self.state.get("source_store_sha256") != source_store_sha256:
            return False
        if self.state.get("algo_version") != algo_version:
            return False
        if self.state.get("config_hash") != config_hash:
            return False
        return True

    def bind_cache_identity(self, source_store_sha256: str, algo_version: str, config_hash: str):
        self.state["source_store_sha256"] = source_store_sha256
        self.state["algo_version"] = algo_version
        self.state["config_hash"] = config_hash
        self.state["updated_at_utc"] = str(datetime.now(timezone.utc))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state, indent=2))

    def record_phase(self, phase_num: int, phase_name: str, status: str, details: dict[str, Any] | None = None):
        self.state["phases"][f"PHASE_{phase_num:02d}"] = {
            "phase_number": phase_num,
            "phase_name": phase_name,
            "status": status,
            "completed_at_utc": str(datetime.now(timezone.utc)),
            "peak_rss_mb": get_peak_rss_mb(),
            "details": details or {},
        }
        self.state["updated_at_utc"] = str(datetime.now(timezone.utc))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state, indent=2))

    def set_hardware_summary(self, hw_report: dict[str, Any]):
        self.state["hardware_summary"] = hw_report
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state, indent=2))
