# ASTRA 6 — Quantitative Framework for Quarterly Theory, MMXM, CRT & ICT

ASTRA 6 is a rigorous, high-performance quantitative research lab and backtesting pipeline designed to validate and operationalize Price Action / ICT concepts:
- **Quarterly Theory (QT)**: Multi-timeframe fractals, 90-minute cycle decomposition, Q1–Q4 accumulation/manipulation/distribution/reversal phases.
- **MMXM (Market Maker Models)**: Market Maker Buy/Sell Models, consolidation profiles, and smart money reversal footprints.
- **CRT (Candle Range Theory)**: High-resolution candle range dynamics, closing vs. deviation analysis.
- **ICT (Inner Circle Trader)**: Fair Value Gaps (FVG), Liquidity Sweeps, Order Blocks, Breakers, and CISD (Change in State of Delivery).
- **SSMT / SMT Divergences**: Correlated asset divergence tracking across US100 (Nasdaq), US500 (S&P 500), and US30 (Dow).

---

## 🚀 Key Features

- **High-Performance Architecture**: Polars, DuckDB, NumPy, Numba, and PyArrow for ultra-fast processing of tick, 30-second, and 1-minute order book & bar data.
- **DST & Exchange Clock Engine**: Strict handling of New York session times, London fixing, DST transitions, and cash open macros.
- **Reproducible Research Pipeline**: Single-command runner (`run_pipeline.py`) validating results with reproducible manifests.
- **12-Panel Interactive Streamlit Dashboard**: Full quantitative exploration suite (`app.py`) powered by Plotly for visualizing regimes, opening ranges, SMT matrices, and trade replays.
- **Comprehensive Quality Assurance**: Strict pytest suites covering clock synchronization, regime detection, and backtesting fidelity.

---

## 📁 Repository Structure

```
├── astra6/                 # Core research engine & analytics modules
│   ├── bars.py             # Bar construction & tick aggregation
│   ├── clock.py            # NY/London exchange calendars & session timings
│   ├── crt.py              # Candle Range Theory models
│   ├── engine.py           # Multi-asset quantitative engine
│   ├── ict.py              # ICT constructs (FVG, sweeps, CISD, order blocks)
│   ├── opening.py          # Opening range macros & killzones
│   ├── report.py           # Automated HTML/PDF research report generator
│   ├── signals.py          # Signal generation & trade mechanics
│   ├── sim.py              # Execution simulator & cost sensitivity
│   ├── smt.py              # Multi-asset SMT divergence matrix
│   ├── stats.py            # Expectancy, bootstrap, and hypothesis tests
│   └── data/               # Data ingestion & normalization routines
├── app.py                  # 12-Panel Streamlit quantitative dashboard
├── run_pipeline.py         # End-to-end reproducible research pipeline runner
├── reports/                # Generated research reports & figures
├── data/
│   └── results/            # Computed analytical matrices & experiment results
└── tests/                  # Unit tests & verification suites
```

---

## 🛠️ Quick Start

### 📦 Full Project & Dataset Archive (Direct Download)
Tüm ham/işlenmiş veri setlerini (`data/store/`, `data/raw/`, `data/hf_cache/`), hazır sanal ortamı (`.venv`) ve tüm raporları içeren eksiksiz 1.2 GB arşiv dosyasını doğrudan indirebilirsiniz:
- **İndirme Bağlantısı**: [qt_test_full_project.zip (v1.0.0 Release)](https://github.com/EdipMangtay/Quantetive_for_-Quarterly_theroy_mmxm_crt_ict-/releases/download/v1.0.0/qt_test_full_project.zip)

### 1. Requirements & Setup

This project uses [`uv`](https://github.com/astral-sh/uv) for fast, deterministic dependency management (Python >= 3.12).

```bash
# Clone the repository
git clone https://github.com/EdipMangtay/Quantetive_for_-Quarterly_theroy_mmxm_crt_ict-.git
cd Quantetive_for_-Quarterly_theroy_mmxm_crt_ict-

# Install dependencies with uv
uv sync
```

### 2. Run the Interactive Dashboard

```bash
uv run streamlit run app.py
```

### 3. Run the Research Pipeline

```bash
# Verification & QA test suite
uv run python run_pipeline.py

# Full re-computation pipeline
uv run python run_pipeline.py --full
```

### 4. Run Tests

```bash
uv run pytest tests/
```

---

## 📜 License

MIT License. See [LICENSE](LICENSE) for details.

