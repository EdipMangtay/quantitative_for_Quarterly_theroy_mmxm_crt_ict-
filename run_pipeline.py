#!/usr/bin/env python3
"""ASTRA 6 — Single-Command Reproducible Research Pipeline Runner (Section 20 Step 28).

Usage:
  uv run python run_pipeline.py           # Verify store, build/update reports, run 2,572+ QA tests
  uv run python run_pipeline.py --full    # Full 5-year M1/30S engine re-computation + reports + QA tests
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
    "DUKA_US100_30S.parquet",
    "DUKA_US500_30S.parquet",
]

REQUIRED_RESULT_FILES = [
    "data_quality.json",
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
]


def _sha256_head(path: Path, n_bytes: int = 65536) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        h.update(f.read(n_bytes))
    return h.hexdigest()[:16]


def main() -> int:
    parser = argparse.ArgumentParser(description="ASTRA 6 Reproducible Research Pipeline")
    parser.add_argument("--full", action="store_true", help="Re-run full 5-year engine calculation from parquet store")
    parser.add_argument("--ingest", action="store_true", help="Re-run data ingestion if store files are missing")
    args = parser.parse_args()

    t0 = time.time()
    print("=" * 78)
    print("ASTRA 6 — FRACTAL QT + ICT + MMXM + CRT + SSMT + CISD PIPELINE")
    print("=" * 78)

    # 1. Verify Data Store
    missing_store = [f for f in REQUIRED_STORE_FILES if not (STORE / f).exists()]
    if missing_store:
        if args.ingest:
            print(f"[1/4] Missing store files {missing_store}; running astra6.data.ingest_hf...")
            subprocess.run([sys.executable, "-u", "-m", "astra6.data.ingest_hf"], cwd=ROOT, check=True)
        else:
            raise FileNotFoundError(f"Missing store files: {missing_store}. Run with --ingest.")
    else:
        print(f"[1/4] Historical CFD Data Store verified ({len(REQUIRED_STORE_FILES)} core Parquet stores present).")

    # 2. Run Research Engine if requested or if any result table is missing
    missing_res = [f for f in REQUIRED_RESULT_FILES if not (RESULTS / f).exists()]
    if args.full or missing_res:
        print("[2/4] Executing Master Research Engine (astra6.engine)...")
        from astra6.engine import run_full_research
        run_full_research()
    else:
        print(f"[2/4] All {len(REQUIRED_RESULT_FILES)} research result tables present in data/results/.")

    # 3. Build Turkish HTML & PDF Research Reports + Figures
    print("[3/4] Generating Turkish HTML & PDF Reports and Figures (astra6.report)...")
    from astra6.report import build_all_reports
    rep_paths = build_all_reports()

    # 4. Run Automated QA & DST Test Suites
    print("[4/4] Running Automated QA Suite (Tests A–K) & Multi-Year DST Test Suite...")
    res = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/"], cwd=ROOT)
    if res.returncode != 0:
        print("[ERROR] QA Test Suite failed!")
        return res.returncode

    # Write Reproducibility Manifest
    manifest = {
        "pipeline_completed_at_utc": str(datetime.now(timezone.utc)),
        "elapsed_seconds": round(time.time() - t0, 2),
        "store_files": {
            f: {"size_bytes": (STORE / f).stat().st_size, "sha256_head": _sha256_head(STORE / f)}
            for f in REQUIRED_STORE_FILES
        },
        "result_files": {
            f: {"size_bytes": (RESULTS / f).stat().st_size}
            for f in REQUIRED_RESULT_FILES
        },
        "reports": {
            k: str(v.relative_to(ROOT)) for k, v in rep_paths.items()
        },
    }
    manifest_path = RESULTS / "reproducibility_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"[DONE] Pipeline succeeded in {manifest['elapsed_seconds']}s. Manifest -> {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

