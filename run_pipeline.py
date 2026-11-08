#!/usr/bin/env python3
"""ASTRA 6 v2.0 — Verified Reproducible Research Pipeline Runner.

Usage:
  uv run python run_pipeline.py           # Verify store, run audit, build/update dynamic reports, run QA tests
  uv run python run_pipeline.py --full    # Full 5-year M1/30S engine re-computation from scratch + audit + reports + QA
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STORE = ROOT / "data" / "store"
RESULTS = ROOT / "data" / "results"
REPORTS = ROOT / "reports"

REQUIRED_STORE_FILES = [
    "US100_BID_M1.parquet",
    "US100_ASK_M1.parquet",
    "US500_BID_M1.parquet",
    "US500_ASK_M1.parquet",
    "US30_BID_M1.parquet",
    "US30_ASK_M1.parquet",
    "DUKA_US100_M1.parquet",
    "DUKA_US500_M1.parquet",
    "DUKA_US100_30S.parquet",
    "DUKA_US500_30S.parquet",
    "DUKA_US100_TICKS_SAMPLE.parquet",
    "OANDA_US100_M1.parquet",
    "OANDA_US500_M1.parquet",
    "OANDA_US30_M1.parquet",
]

REQUIRED_RESULT_FILES = [
    "data_quality.json",
    "data_authenticity_manifest.parquet",
    "data_forensics_report.json",
    "trade_features.parquet",
    "events.parquet",
    "intraday_24h_18models.parquet",
    "ny_5m_15m_18models.parquet",
    "ldn_18models.parquet",
    "dataset_provider_comparison.parquet",
    "qt_anchor_comparison.parquet",
    "micro_30s_vs_1m_perf.parquet",
    "incremental_contribution.parquet",
    "losing_trades_autopsy.parquet",
    "tf_summary.parquet",
    "crt_tf_stats.parquet",
    "crt_variants.parquet",
    "crt_closing_vs_dev.parquet",
    "crt_ssmt_baselines.parquet",
    "hypothesis_tests.parquet",
    "ssmt_timing.parquet",
    "crt_ssmt_matrix.parquet",
    "qt_fractals.parquet",
    "q2q_rankings.parquet",
    "multilevel_alignment.parquet",
    "narrative_perf.parquet",
    "opening_windows.parquet",
    "opening_ranges_ny.parquet",
    "opening_ranges_ldn.parquet",
    "ny_open_models.parquet",
    "h1_anchoring.parquet",
    "rr_stop_exit_grid.parquet",
    "splits_eval.parquet",
    "wfa_folds.parquet",
    "yearly_perf.parquet",
    "monthly_perf.parquet",
    "cost_sensitivity.parquet",
    "regime_perf.parquet",
    "audit_sample_trades.parquet",
    "independent_audit_samples.json",
    "v1_vs_v2_comparison.parquet",
]


def _sha256_full(path: Path) -> str:
    """Compute full-file SHA256 digest (entire file, not a partial slice)."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="ASTRA 6 v2.0 Reproducible Research Pipeline")
    parser.add_argument("--full", action="store_true", help="Re-run full 5-year engine calculation from parquet store")
    parser.add_argument("--ingest", action="store_true", help="Re-run data ingestion if store files are missing")
    args = parser.parse_args()

    t0 = time.time()
    print("=" * 78)
    print("ASTRA 6 v2.0 — VERIFIED INTRADAY FRACTAL RESEARCH LAB PIPELINE")
    print("=" * 78)

    # 1. Verify Data Store
    missing_store = [f for f in REQUIRED_STORE_FILES if not (STORE / f).exists()]
    if missing_store:
        if args.ingest:
            print(f"[1/5] Missing store files {missing_store}; running astra6.data.ingest_hf...")
            subprocess.run([sys.executable, "-u", "-m", "astra6.data.ingest_hf"], cwd=ROOT, check=True)
        else:
            raise FileNotFoundError(f"Missing store files: {missing_store}. Run with --ingest.")
    else:
        print(f"[1/5] Historical CFD Data Store verified ({len(REQUIRED_STORE_FILES)} core Parquet stores present).")

    # 2. Run Research Engine if requested or if any result table is missing
    missing_res = [
        f for f in REQUIRED_RESULT_FILES
        if f not in ("independent_audit_samples.json", "v1_vs_v2_comparison.parquet")
        and not (RESULTS / f).exists()
    ]
    if args.full or missing_res:
        print("[2/5] Executing Master Research Engine v2.0 (astra6.engine.run_all)...")
        from astra6.engine import run_all
        run_all()
    else:
        print(f"[2/5] Core engine result tables present in data/results/.")

    # 3. Run Independent 5x100 Forensic Audit & v1 vs v2 Comparison
    if args.full or not (RESULTS / "independent_audit_samples.json").exists():
        print("[3/5] Running Independent 5x100 Forensic Audit (astra6.audit)...")
        from astra6.audit import run_independent_audit
        run_independent_audit()
    else:
        print("[3/5] Independent 5x100 Forensic Audit present.")

    # 4. Build Turkish HTML & PDF Research Reports + Figures (100% Live-Computed)
    print("[4/5] Generating Dynamic Turkish HTML & PDF Reports and Figures (astra6.report)...")
    from astra6.report import build_all_reports
    rep_paths = build_all_reports()

    # 5. Run Automated QA & DST Test Suites (10 Categories)
    print("[5/5] Running Automated QA Suite (10 Categories) & Multi-Year DST Test Suite...")
    res = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/"], cwd=ROOT)
    if res.returncode != 0:
        print("[ERROR] QA Test Suite failed!")
        return res.returncode

    # Write Full-File SHA256 Reproducibility Manifest
    manifest = {
        "version": "v2.0",
        "pipeline_completed_at_utc": str(datetime.now(timezone.utc)),
        "elapsed_seconds": round(time.time() - t0, 2),
        "store_files": {
            f: {"size_bytes": (STORE / f).stat().st_size, "sha256_full": _sha256_full(STORE / f)}
            for f in REQUIRED_STORE_FILES
        },
        "result_files": {
            f: {"size_bytes": (RESULTS / f).stat().st_size, "sha256_full": _sha256_full(RESULTS / f)}
            for f in REQUIRED_RESULT_FILES
            if (RESULTS / f).exists()
        },
        "reports": {
            k: str(v.relative_to(ROOT)) for k, v in rep_paths.items()
        },
    }
    manifest_path = RESULTS / "reproducibility_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"[DONE] Pipeline v2.0 succeeded in {manifest['elapsed_seconds']}s. Manifest -> {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
