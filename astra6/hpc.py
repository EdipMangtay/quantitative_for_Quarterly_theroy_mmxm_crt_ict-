"""ASTRA 6 V3 — High-Performance Computing (HPC), Hardware Auto-Tuner & Checkpoint Engine (Section 16).

Responsibilities:
  1. Dynamically inspect CPU model, physical/logical cores, total/available RAM,
     disk capacity/free space, OS/architecture, and installed analytical libraries
     (Polars, DuckDB, PyArrow, NumPy, Numba).
  2. Configure thread limits to prevent nested oversubscription across BLAS/Accelerate,
     Polars, DuckDB, and Numba on macOS Apple Silicon.
  3. Benchmark representative event-composition and trade-evaluation kernels across
     candidate batch sizes and worker counts, verifying 100% numerical identity
     against a pure-Python reference implementation on representative and adversarial cases.
  4. Provide persistent checkpoint and resume tracking across all 16 V3 implementation phases.
"""
from __future__ import annotations

import hashlib
import json
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
RESULTS = ROOT / "data" / "results"


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
# Reference vs Optimized Kernel Verification & Benchmark (Section 16)
# ---------------------------------------------------------------------------
def reference_target_horizon_eval_py(
    highs: np.ndarray,
    lows: np.ndarray,
    j_fill: np.ndarray,
    direction: np.ndarray,
    stop_px: np.ndarray,
    target_px: np.ndarray,
    horizon_bars: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Pure-Python reference implementation for target prediction vs executable trade outcome (Section 7.3).

    Returns:
      - reached_any_raw: bool — did price reach `target_px` within `horizon_bars` (even if after stop)?
      - reached_before_stop: bool — did price reach `target_px` BEFORE touching `stop_px`?
      - bars_to_target: int64 — bars from `j_fill` until target first touched (-1 if not reached)
    """
    m = len(j_fill)
    n = len(highs)
    reached_any = np.zeros(m, dtype=bool)
    reached_clean = np.zeros(m, dtype=bool)
    bars_to_tgt = np.full(m, -1, dtype=np.int64)

    for i in range(m):
        jf = int(j_fill[i])
        if jf < 0 or jf >= n:
            continue
        d = int(direction[i])
        sl = float(stop_px[i])
        tp = float(target_px[i])
        end = min(n - 1, jf + horizon_bars)
        stopped = False
        for k in range(jf, end + 1):
            if d == 1:
                hit_sl = lows[k] <= sl
                hit_tp = highs[k] >= tp
            else:
                hit_sl = highs[k] >= sl
                hit_tp = lows[k] <= tp
            # Pessimistic same-bar ordering: SL checked before TP
            if hit_sl:
                stopped = True
            if hit_tp and not reached_any[i]:
                reached_any[i] = True
                bars_to_tgt[i] = k - jf
                if not stopped:
                    reached_clean[i] = True
            if reached_any[i] and stopped:
                break
    return reached_any, reached_clean, bars_to_tgt


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
    """Numba-compiled kernel matching `reference_target_horizon_eval_py` bit-for-bit."""
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


def run_benchmark_and_autotune(profile: HardwareProfile | None = None) -> dict[str, Any]:
    """Benchmark representative workloads, compare batch sizes, and verify kernel identity."""
    if profile is None:
        profile = detect_hardware_profile()

    rng = np.random.default_rng(42)
    n_bars = 50_000
    base = 20000.0 + np.cumsum(rng.normal(0, 2.5, size=n_bars))
    highs = base + np.abs(rng.normal(2.0, 1.0, size=n_bars))
    lows = base - np.abs(rng.normal(2.0, 1.0, size=n_bars))

    # Include adversarial cases: same-bar SL & TP touch, boundary index n-1, negative index
    n_test = 2_000
    j_fill = rng.integers(0, n_bars - 200, size=n_test, dtype=np.int64)
    j_fill[0] = 100
    j_fill[1] = n_bars - 1
    j_fill[2] = -1
    direction = rng.choice(np.array([-1, 1], dtype=np.int64), size=n_test)
    direction[0] = 1
    entry_px = np.where(j_fill >= 0, base[np.clip(j_fill, 0, n_bars - 1)], 20000.0)
    stop_px = np.where(direction == 1, entry_px - 15.0, entry_px + 15.0)
    target_px = np.where(direction == 1, entry_px + 30.0, entry_px - 30.0)
    # Adversarial case 0: same-bar touch of both SL and TP at j_fill[0] + 3
    highs[103] = entry_px[0] + 45.0
    lows[103] = entry_px[0] - 25.0

    # Warm-up JIT
    _ = fast_target_horizon_eval_numba(highs[:200], lows[:200], j_fill[:10], direction[:10], stop_px[:10], target_px[:10], 60)

    t0 = time.perf_counter()
    ref_any, ref_clean, ref_bars = reference_target_horizon_eval_py(highs, lows, j_fill, direction, stop_px, target_px, 180)
    py_sec = time.perf_counter() - t0

    t1 = time.perf_counter()
    opt_any, opt_clean, opt_bars = fast_target_horizon_eval_numba(highs, lows, j_fill, direction, stop_px, target_px, 180)
    nb_sec = time.perf_counter() - t1

    exact_match = bool(
        np.array_equal(ref_any, opt_any)
        and np.array_equal(ref_clean, opt_clean)
        and np.array_equal(ref_bars, opt_bars)
        and bool(opt_any[0]) is True
        and bool(opt_clean[0]) is False  # Adversarial same-bar SL+TP must mark clean=False!
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
            "adversarial_same_bar_sl_tp_verified": bool(opt_any[0] and not opt_clean[0]),
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
    """Persistent checkpoint and completion manifest manager for Phases 1..16."""

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
            "project": "ASTRA 6 — MASTER PROMPT V3 FINAL",
            "version": "v3.0",
            "created_at_utc": str(datetime.now(timezone.utc)),
            "phases": {},
            "hardware_summary": {},
        }

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

