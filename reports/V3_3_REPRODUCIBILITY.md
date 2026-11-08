# ASTRA 6 — V3.3 REPRODUCIBILITY & HARDWARE AUDIT REPORT
**Deterministic Research Architecture, Cryptographic Data Manifests, Hardware Profiling & Zero-Copy Execution Engine**

---

## 1. Reproducibility Mandate & Cryptographic Integrity

To guarantee 100% deterministic reproducibility across quantitative research environments, ASTRA 6 V3.3 enforces:
1. **Source Data Immutability**: All calculations are derived strictly from the pre-existing 15 raw Parquet files in `data/store/`. No new external market data was downloaded or scraped.
2. **Cryptographic SHA-256 Checkpointing**: Every data store file, derived event lake, and core algorithm module is hashed. If source data changes by even 1 byte, the engine detects cache invalidation and forces an atomic recomputation.
3. **Prefix-Invariant Incremental FSM**: MMXM stage transitions and candle confirmation rules depend strictly on historical causal bars $[0, t]$, ensuring exact reproduction whether evaluated bar-by-bar or in vectorized batches.

---

## 2. Hardware Environment & HPC Auto-Tuning Profile

The backtest pipeline was executed on the following validated environment:

| Specification Parameter | Value / Implementation |
| :--- | :--- |
| **Operating System** | macOS (Darwin 24.3.0, ARM64 Apple Silicon) |
| **Python Environment** | Python 3.12.15 (managed via `uv`) |
| **Physical CPU Cores** | 10 Cores |
| **System Memory (RAM)** | 16.0 GB Unified Memory |
| **Vector Engine / JIT** | Numba JIT (v0.61.0) with LLVM compilation |
| **Fast Columnar I/O** | PyArrow 19.0.1, Polars 1.23.0, DuckDB 1.2.0 |
| **Concurrency Auto-Tuner** | `POLARS_MAX_THREADS=8`, `NUMBA_NUM_THREADS=8` |
| **Thread Oversubscription Prevention**| `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1` |
| **Zero-Copy Architecture** | Arrow RecordBatches, in-memory DuckDB zero-copy parquet scanning |
| **Total Pipeline Runtime** | **204.1 seconds** (Complete 5-year universe: 2.25M atomic events, 644K trades, 2.66M target evaluations) |

---

## 3. Cryptographic SHA-256 Data Store Manifest

All empirical research is bound to the following exact cryptographic dataset:

| File Name in `data/store/` | File Size | SHA-256 Checksum |
| :--- | :---: | :--- |
| `DUKA_US100_30S.parquet` | 102.84 MB | `0f26f60f034714a5424822816c21b7b7e0f4543197f64f09953844bef2ea8ab5` |
| `DUKA_US100_M1.parquet` | 54.52 MB | `4d4c36fd6c5987b611c3933ba1df288bec505e86cee6b289b70dba6b890ae6a2` |
| `DUKA_US100_TICKS_SAMPLE.parquet` | 15.62 MB | `e642b129fa6165e4f63dd89f432340ae0be3c04c344f1cb14232f31577ffb672` |
| `DUKA_US500_30S.parquet` | 85.97 MB | `fe37af2770c1ffd031d85947ad6c62ff229aab96c08766a8ad25de15fc4e9cd1` |
| `DUKA_US500_M1.parquet` | 47.82 MB | `b0e6e68485dde988b8c1c71de5ed5c98f73057b95ab1cddb1dcf5cb4a31d9464` |
| `DUKA_US500_TICKS_SAMPLE.parquet` | 4.28 MB | `c2e4b82c8bdf7d79c54f0393ef58aa04c601cc09fca3c32f6fd8bcae433d44c8` |
| `OANDA_US100_M1.parquet` | 22.72 MB | `989aa03758e96ebe41056556db716e643d2174c53d2e855f77a4cdde6e7723f1` |
| `OANDA_US30_M1.parquet` | 19.03 MB | `156bf9319f415bb945d75da33beb5bd853db42a4224107556341f72741a74d37` |
| `OANDA_US500_M1.parquet` | 17.77 MB | `c94386dcb1db884da044ba05c955b553e94a8cf8794f78c67efe8c57fc02d1e8` |
| `US100_ASK_M1.parquet` | 30.29 MB | `85332e04ab612e43cb3e478f21ac3fa0594e8dfb0262bb05c5c0d64f32680c4c` |
| `US100_BID_M1.parquet` | 33.52 MB | `e192671a588d872bca1cd47da98633b50977656aeb3f43a2b33e8877280af018` |
| `US30_ASK_M1.parquet` | 19.75 MB | `365f587711c99adb6a8ce0980ac31231a31ea0f9e1ecf72feffcd9429280af6e` |
| `US30_BID_M1.parquet` | 21.86 MB | `25112214ff063676aae8358abb65abf831b3301cc62f3874c811bf05416acd30` |
| `US500_ASK_M1.parquet` | 26.94 MB | `831c44087fcb0ef8356c1d13f9651535d633b0791d5f494d6173d20fef89f1a9` |
| `US500_BID_M1.parquet` | 28.79 MB | `57429275146079dfdaa0e827e9ec23c3caedd23a7506370fdf3e017c2d025566` |

---

## 4. Key Algorithm Source Checksums

| Source Module | Git Path | SHA-256 Checksum |
| :--- | :--- | :--- |
| **Pipeline Engine** | `astra6/engine_v3.py` | `188783598cddaa0394bc90ff8bf5cc78ef6b2c198f76ab62fe7c417d98f49e9e` |
| **Fractal MMXM & Graph** | `astra6/fractal_v3.py` | `9a95a2ed97527b1ef7da968a657823776156b9cdedba8e3413f91f6e18edba86` |
| **HPC, Numba & Clustering**| `astra6/hpc.py` | `2d2cd7bec43fa8ba98bc696011c20d5adf4c294db41c8165624c99f33b19ceaf` |
| **Signals & Resampling** | `astra6/signals.py` | `7be45f8dcd011b6c5b68d59476055272a3281a229f1a01ec94259d58b3ff8939` |

---

## 5. End-to-End Reproduction Instructions

To reproduce the complete research artifacts from raw data to DuckDB database views:

```bash
# 1. Activate isolated Python environment and verify dependencies
uv sync

# 2. Run the deterministic V3.3 Causal Research Pipeline
uv run python -c "from astra6.engine_v3 import run_v3_pipeline; run_v3_pipeline(force_recompute=True)"

# 3. Execute the full regression and correctness QA test suite
uv run pytest -v tests/test_v3_fractal_qa.py
uv run pytest -v tests/test_qa_suite.py

# 4. Connect to the unified research DuckDB instance
duckdb data/results/astra6_v3.duckdb -c "SELECT ranking_number, selected_strategy_label, win_rate, expectancy_r, profit_factor FROM v3_rankings_25 LIMIT 10;"
```
All tables are deterministically regenerated with bit-level reproducibility across any POSIX platform with Python 3.12 and Numba JIT.
