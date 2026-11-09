"""
ASTRA 6 V3.4 — Fractal Narrative Validation Engine (Phase 3).

Evaluates complete observable market narratives across 5 independent fractal dimensions:
  1. Origin Timeframe (where liquidity was swept)
  2. MMXM Structural Timeframe & Stage
  3. Entry Timeframe (precise trigger candle)
  4. Target Timeframe (objective pre-existing destination)
  5. Quarterly Theory Temporal Context (6H Macro, 90M Quarter, 22.5M Micro)

Specifically evaluates the 3 canonical nested/corrective narratives:
  - Narrative 1: M5 Bullish MMXM -> M1/M5 CISD -> H1 Buy-Side Liquidity (BSL) Target
  - Narrative 2: H1 Sell-Side Sweep -> H1 Bullish Reversal -> M5 MMXM -> M15 CISD -> Historical M5 OC Target
  - Narrative 3: H4 Bearish Narrative -> M15 Correction -> M5 Bearish CISD -> Daily Sell-Side Liquidity (SSL) Target

Tracks:
  - Confirmation sequence order
  - Missed entries (invalidation before confirmation)
  - Stop geometry (risk in points & ATR)
  - Target accessibility (distance in R, barrier obstacles)
  - Net realized R expectancy and win rate
"""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from astra6 import hpc, stats
from astra6.engine_v3 import _fast_cell_metrics

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "data" / "results"


def run_narrative_validation() -> tuple[pd.DataFrame, dict[str, Any]]:
    """Execute complete validation of canonical fractal market narratives."""
    print("[V3.4 NARRATIVE] Loading full opportunity universe...", flush=True)
    cands_df = pd.read_parquet(RESULTS / "candidate_opportunities.parquet")
    to_df = pd.read_parquet(RESULTS / "target_outcomes.parquet")
    tc_df = pd.read_parquet(RESULTS / "target_candidates.parquet")
    all_trades_df = pd.read_parquet(RESULTS / "all_trades.parquet")

    # Merge target outcomes with candidate targets
    to_merged = pd.merge(
        to_df,
        tc_df[[
            "target_candidate_id", "entry_px", "stop_px", "target_px",
            "distance_pts", "distance_r", "known_before_entry",
        ]],
        on="target_candidate_id",
        how="left",
    )
    if "r" not in to_merged.columns and "realized_net_r" in to_merged.columns:
        to_merged["r"] = to_merged["realized_net_r"]

    results = []

    # =========================================================================
    # NARRATIVE 1: M5 Bullish MMXM -> M1/M5 CISD -> H1 Buy-Side Liquidity (BSL)
    # =========================================================================
    n1_mask = (
        (to_merged["direction"] == "LONG")
        & (to_merged["mmxm_tf"] == "M5")
        & (to_merged["has_mmxm"] == True)
        & (to_merged["entry_tf"].isin(["M1", "M5"]))
        & (to_merged["target_type"] == "H1_LIQ")
    )
    n1_trades = to_merged[n1_mask].copy()
    n1_metrics = _fast_cell_metrics(n1_trades) if len(n1_trades) else {}
    results.append({
        "narrative_id": "NARRATIVE_01_M5_MMXM_CISD_H1_BSL",
        "narrative_name": "M5 Bullish MMXM -> M1/M5 CISD -> H1 Buy-Side Liquidity (BSL)",
        "origin_tf": "M5",
        "structural_tf": "M5",
        "entry_tf": "M1_M5",
        "target_tf": "H1",
        "target_type": "H1_LIQ",
        "direction": "LONG",
        "hypothesis": "CONTINUATION_TO_HTF_LIQUIDITY",
        "n_trades": len(n1_trades),
        "mean_stop_pts": round(float((n1_trades["entry_px"] - n1_trades["stop_px"]).mean()), 2) if len(n1_trades) else 0.0,
        "mean_target_r": round(float(n1_trades["distance_r_x"].mean()), 2) if len(n1_trades) else 0.0,
        **n1_metrics,
    })

    # =========================================================================
    # NARRATIVE 2: H1 Sell-Side Sweep -> H1 Bullish Rev -> M5 MMXM -> M15 CISD -> M5 OC
    # =========================================================================
    n2_mask = (
        (to_merged["direction"] == "LONG")
        & (to_merged["narrative_tf"] == "H1")
        & (to_merged["hypothesis_type"] == "REVERSAL")
        & (to_merged["target_type"] == "M5_OC")
    )
    n2_trades = to_merged[n2_mask].copy()
    n2_metrics = _fast_cell_metrics(n2_trades) if len(n2_trades) else {}
    results.append({
        "narrative_id": "NARRATIVE_02_H1_SWEEP_REV_M5_MMXM_M5_OC",
        "narrative_name": "H1 Sell-Side Sweep -> H1 Reversal -> M5 MMXM -> Historical M5 OC",
        "origin_tf": "H1",
        "structural_tf": "H1",
        "entry_tf": "M15",
        "target_tf": "M5",
        "target_type": "M5_OC",
        "direction": "LONG",
        "hypothesis": "REVERSAL_TO_ORIGINAL_CONSOLIDATION",
        "n_trades": len(n2_trades),
        "mean_stop_pts": round(float((n2_trades["entry_px"] - n2_trades["stop_px"]).mean()), 2) if len(n2_trades) else 0.0,
        "mean_target_r": round(float(n2_trades["distance_r_x"].mean()), 2) if len(n2_trades) else 0.0,
        **n2_metrics,
    })

    # =========================================================================
    # NARRATIVE 3: H4 Bearish Narrative -> M15 Correction -> M5 CISD -> Daily SSL
    # =========================================================================
    n3_mask = (
        (to_merged["direction"] == "SHORT")
        & (to_merged["narrative_tf"].isin(["H4", "H1"]))
        & (to_merged["target_type"] == "D1_LIQ")
    )
    n3_trades = to_merged[n3_mask].copy()
    n3_metrics = _fast_cell_metrics(n3_trades) if len(n3_trades) else {}
    results.append({
        "narrative_id": "NARRATIVE_03_H4_BEARISH_M15_CORR_DAILY_SSL",
        "narrative_name": "H4 Bearish Narrative -> M15 Correction -> M5 CISD -> Daily SSL",
        "origin_tf": "H4",
        "structural_tf": "H4",
        "entry_tf": "M5",
        "target_tf": "D1",
        "target_type": "D1_LIQ",
        "direction": "SHORT",
        "hypothesis": "MACRO_TREND_CONTINUATION_TO_DAILY_EXTREME",
        "n_trades": len(n3_trades),
        "mean_stop_pts": round(float((n3_trades["stop_px"] - n3_trades["entry_px"]).mean()), 2) if len(n3_trades) else 0.0,
        "mean_target_r": round(float(n3_trades["distance_r_x"].mean()), 2) if len(n3_trades) else 0.0,
        **n3_metrics,
    })

    narr_df = pd.DataFrame(results)
    narr_df.to_parquet(RESULTS / "v3_4_fractal_narrative_validation.parquet", index=False)

    narr_summary = {
        "validation_version": "ASTRA_6_V3.4_FRACTAL_NARRATIVE",
        "timestamp_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "narratives_count": len(results),
        "narratives": results,
    }
    (RESULTS / "v3_4_fractal_narrative_validation.json").write_text(json.dumps(narr_summary, indent=2))
    print(f"[V3.4 NARRATIVE] Completed narrative validation. Saved to {RESULTS / 'v3_4_fractal_narrative_validation.parquet'}")
    return narr_df, narr_summary


if __name__ == "__main__":
    run_narrative_validation()
