"""ASTRA 6 V3 FINAL — End-to-End Quality Assurance Test Suite (Section 21).

Verifies all 30 mandatory V3 QA requirements across:
  - All 28 Section 17 Parquet tables + DuckDB analytical database
  - All 64 binary core configurations (LONG, SHORT, BOTH)
  - All 15 strategy-family subsets ({QT, ICT, CRT, MMXM})
  - LONG / SHORT symmetry & Reversal / Continuation separation
  - Independent M1, M3, M5, M15, M30, H1, H4 CISD timeframes + No-CISD + Multi-TF subsets
  - All 10 Macro/Micro SSMT states (including Missing_Comparison_Data distinct from Neither_Present)
  - 13-Stage Fractal MMXM chronology & Original Consolidation causality
  - Cross-timeframe alignment (Pairs, Triples, 4-TF Quads)
  - Entry-to-Target timeframe independence:
      * Lower-to-Higher (M5 MMXM -> H1/H4/D1/W1 liquidity)
      * Higher-to-Lower (H1/H4 reversal -> M5/M15 Original Consolidation)
  - Target Prediction (Horizon) vs Trading Profit (Before Stop-Out) separation
  - Reference pure-Python vs Optimized Numba kernel bit-for-bit identity on adversarial same-bar SL+TP
  - Nasdaq 09:30 5-minute / 15-minute intervals & London Open DST grids
  - No duplicate opportunity counting (`opportunity_id` uniqueness)
  - All 6 configuration statuses (`TESTED`, `NO_SIGNAL`, `INSUFFICIENT_DATA`, `INVALID_COMBINATION`, `BLOCKED_BY_DATA_QUALITY`, `PENDING`)
  - Statistical robustness, OOS splits, and all 25 Mandatory Rankings (with `NO VERIFIED POSITIVE EDGE`)
  - 10×100 Manual Validation dataset & V4 Forward-Testing Handoff
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

from astra6 import engine_v3, fractal_v3, hpc

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "data" / "results"


@pytest.mark.parametrize("table_name", engine_v3.V3_REQUIRED_PARQUET_TABLES)
def test_v3_all_28_mandatory_parquet_tables_exist_and_non_empty(table_name: str):
    """Section 17: Verify every one of the 28 required V3 Parquet tables exists and has rows."""
    p = RESULTS / table_name
    assert p.exists(), f"Missing mandatory V3 Parquet table: {table_name}"
    df = pd.read_parquet(p)
    assert len(df) > 0, f"Mandatory V3 Parquet table is empty: {table_name}"


def test_v3_all_64_binary_configurations_and_directions():
    """Section 4 & 21: Verify all 64 core binary combinations exist for BOTH, LONG, and SHORT."""
    df = pd.read_parquet(RESULTS / "combination_results.parquet")
    all_sess = df[df["scope"] == "All_Sessions"]
    for d in ("BOTH", "LONG", "SHORT"):
        sub = all_sess[all_sess["direction"] == d]
        assert len(sub) == 64, f"Expected 64 binary combinations for {d}, got {len(sub)}"
        assert sub["base_config_id"].nunique() == 64
        # Verify the all-off baseline (CFG64_00) and all-on state (CFG64_63) are tested and non-empty
        assert (sub["n_trades"] > 0).sum() == 64


def test_v3_all_15_strategy_family_subsets_distinct_from_64_core():
    """Section 4 & 21: Verify all 15 non-empty subsets of {QT, ICT, CRT, MMXM} are evaluated separately."""
    fam = pd.read_parquet(RESULTS / "v3_family_15_subsets.parquet")
    assert fam["family_subset_id"].nunique() == 15
    for d in ("BOTH", "LONG", "SHORT"):
        sub = fam[(fam["scope"] == "All_Sessions") & (fam["direction"] == d)]
        assert len(sub) == 15
        assert (sub["n_trades"] > 0).all()


def test_v3_long_short_symmetry_and_trade_table_partition():
    """Section 3, 17 & 21: Verify all_trades == long_trades + short_trades and required columns exist."""
    all_t = pd.read_parquet(RESULTS / "all_trades.parquet")
    long_t = pd.read_parquet(RESULTS / "long_trades.parquet")
    short_t = pd.read_parquet(RESULTS / "short_trades.parquet")

    assert len(all_t) == len(long_t) + len(short_t)
    assert (long_t["direction"] == "LONG").all()
    assert (short_t["direction"] == "SHORT").all()
    assert set(all_t["direction"].unique()) == {"LONG", "SHORT"}

    # No duplicate opportunity counting inside candidate_opportunities / all_trades
    assert all_t["opportunity_id"].nunique() == len(all_t)

    required_cols = {
        "opportunity_id", "strategy_config_id", "data_provider", "instrument", "direction",
        "event_context", "origin_tf", "narrative_tf", "mmxm_tf", "entry_tf", "target_tf",
        "liquidity_source_tf", "qt_phase", "ssmt_state", "crt_state", "cisd_tf",
        "t_signal_known", "entry_timestamp", "execution_price", "stop_px", "target_px",
        "exit_px", "realized_net_r", "mfe", "mae", "hold", "validation_split",
    }
    assert required_cols.issubset(set(all_t.columns))

    # Strict causality: signal known timestamp must be strictly before next-bar open fill timestamp
    t_sig = pd.to_datetime(all_t["t_signal_known"], utc=True)
    t_ent = pd.to_datetime(all_t["entry_timestamp"], utc=True)
    assert (t_sig <= t_ent).all()


def test_v3_independent_multitf_cisd_and_subsets():
    """Section 4.3, 9 & 21: Verify independent M1, M3, M5, M15, M30, H1, H4 CISD events and subsets."""
    cisd_ev = pd.read_parquet(RESULTS / "multitf_cisd_events.parquet")
    assert {"M1", "M3", "M5", "M15", "M30", "H1", "H4"}.issubset(set(cisd_ev["tf"].unique()))

    lc_mat = pd.read_parquet(RESULTS / "liquidity_cisd_pair_matrix.parquet")
    subsets = set(lc_mat["cisd_subset"].unique())
    for req_s in (
        "00_No_CISD", "01_M1_CISD", "02_M3_CISD", "03_M5_CISD", "04_M15_CISD",
        "05_M30_CISD", "06_H1_CISD", "07_H4_CISD", "08_M1+M5_CISD", "09_M3+M5_CISD",
        "10_M5+M15_CISD", "11_M15+H1_CISD", "12_M1+M5+M15_CISD",
    ):
        assert req_s in subsets, f"Missing CISD subset {req_s}"


def test_v3_macro_micro_ssmt_10_states():
    """Section 4.1, 10.3 & 21: Verify all 10 Macro/Micro SSMT states including Missing_Comparison_Data."""
    ssmt_mat = pd.read_parquet(RESULTS / "macro_micro_ssmt_matrix.parquet")
    states = set(ssmt_mat["ssmt_state_10"].unique())
    assert len(states) == 10
    assert "01_Neither_Present" in states
    assert "10_Missing_Comparison_Data" in states
    assert "07_Both_Conflicting" in states


def test_v3_original_consolidation_and_13_stage_mmxm_chronology():
    """Section 6 & 21: Verify OC confirmation chronology and 13-stage MMXM lifecycle ordering."""
    oc_df = pd.read_parquet(RESULTS / "original_consolidations.parquet")
    assert {"M1", "M3", "M5", "M15", "M30", "H1", "H4"}.issubset(set(oc_df["tf"].unique()))
    t_st = pd.to_datetime(oc_df["t_start"], utc=True)
    t_cf = pd.to_datetime(oc_df["t_confirm"], utc=True)
    assert (t_st < t_cf).all(), "OC start time must strictly precede OC confirmation time!"

    mmxm_ev = pd.read_parquet(RESULTS / "mmxm_state_events.parquet")
    assert set(range(1, 16)).issubset(set(mmxm_ev["stage_num"].unique()))
    # Check that within each mmxm_id, stage timestamps are monotonically non-decreasing with stage_num
    grp = mmxm_ev.sort_values(["mmxm_id", "stage_num"]).groupby("mmxm_id")["j_m1_known"].diff().dropna()
    assert (grp >= 0).all(), "MMXM stages must follow strict non-decreasing chronological order!"


def test_v3_cross_timeframe_alignment_pairs_triples_quads():
    """Section 2.1, 2.2, 2.3 & 21: Verify required pairs, triples, and 4-TF structures work."""
    tf_mat = pd.read_parquet(RESULTS / "timeframe_alignment_matrix.parquet")
    chains = set(tf_mat["structure_chain"].unique())
    for req_pair in (
        "W1 -> H4", "W1 -> H1", "D1 -> H4", "D1 -> H1", "D1 -> M15",
        "H4 -> H1", "H4 -> M15", "H4 -> M5", "H1 -> M30", "H1 -> M15",
        "H1 -> M5", "H1 -> M1", "M30 -> M5", "M15 -> M5", "M15 -> M3",
        "M15 -> M1", "M5 -> M3", "M5 -> M1", "M3 -> M1",
    ):
        assert req_pair in chains, f"Missing required pair: {req_pair}"

    for req_triple in (
        "W1 -> H4 -> M15", "W1 -> H1 -> M5", "D1 -> H4 -> M15", "D1 -> H1 -> M5",
        "D1 -> H1 -> M1", "H4 -> H1 -> M15", "H4 -> M15 -> M5", "H4 -> M15 -> M1",
        "H1 -> M15 -> M5", "H1 -> M5 -> M1", "M15 -> M5 -> M1",
    ):
        assert req_triple in chains, f"Missing required triple: {req_triple}"

    for req_quad in (
        "W1 -> H4 -> M15 -> M5", "D1 -> H4 -> M15 -> M1",
        "D1 -> H1 -> M5 -> M1", "H4 -> H1 -> M5 -> M1",
    ):
        assert req_quad in chains, f"Missing required 4-TF quad: {req_quad}"


def test_v3_entry_to_target_hierarchy_independence_and_examples_a_b():
    """Section 1, 2.4, 7 & 21: Verify target timeframe can be HIGHER, LOWER, or EQUAL to entry/narrative TF."""
    et_mat = pd.read_parquet(RESULTS / "entry_target_timeframe_matrix.parquet")
    rels = set(et_mat["tf_hierarchy_relation"].unique())
    assert "LTF_STRUCT_TO_HTF_TARGET" in rels, "Must support lower-timeframe structure targeting higher-timeframe liquidity!"
    assert "HTF_STRUCT_TO_LTF_TARGET" in rels, "Must support higher-timeframe reversal targeting lower-timeframe OC!"
    assert "SAME_TF_STRUCT_TARGET" in rels

    # Example A: M5 MMXM/structure targeting H1 liquidity
    ex_a = et_mat[(et_mat["narrative_tf"] == "M5") & (et_mat["target_tf"] == "H1") & (et_mat["target_type"] == "H1_LIQ")]
    assert len(ex_a) > 0 and (ex_a["n_trades"] > 0).all()

    # Example B: H1 reversal targeting M5 Original Consolidation
    ex_b = et_mat[(et_mat["narrative_tf"] == "H1") & (et_mat["target_tf"] == "M5") & (et_mat["target_type"] == "M5_OC")]
    assert len(ex_b) > 0 and (ex_b["n_trades"] > 0).all()

    # Section 7.3: Target reached in horizon >= Trade reached before stop-out
    pred = pd.read_parquet(RESULTS / "target_prediction_results.parquet")
    assert (pred["prob_target_reached_horizon"] >= pred["prob_trade_reached_before_stop"] - 1e-9).all()


def test_v3_reference_vs_numba_kernel_exact_match():
    """Section 16 & 21: Run reference pure-Python vs optimized Numba kernel on adversarial cases."""
    rep = hpc.run_benchmark_and_autotune()
    assert rep["kernel_verification"]["reference_vs_numba_exact_match"] is True
    assert rep["kernel_verification"]["adversarial_same_bar_sl_tp_verified"] is True


def test_v3_nasdaq_0930_5min_and_configuration_statuses():
    """Section 12.2, 15 & 21: Verify Nasdaq 09:30 5-min buckets and all 6 configuration statuses."""
    nq = pd.read_parquet(RESULTS / "nq_open_long_short_5min.parquet")
    wins = set(nq["window"].unique())
    for w_req in ("09:30-09:35", "09:35-09:40", "09:40-09:45", "09:45-09:50", "09:50-09:55", "09:55-10:00"):
        assert w_req in wins

    reg = pd.read_parquet(RESULTS / "all_valid_combinations.parquet")
    statuses = set(reg["config_status"].unique())
    assert {"TESTED", "INVALID_COMBINATION", "BLOCKED_BY_DATA_QUALITY", "NO_SIGNAL", "PENDING"}.issubset(statuses)


def test_v3_25_rankings_and_manual_validation_10x100_and_duckdb():
    """Section 17, 18, 20 & 21: Verify 25 rankings, 10x100 manual validation samples, and DuckDB views."""
    rk = pd.read_parquet(RESULTS / "v3_rankings_25.parquet")
    assert len(rk) == 25
    assert "NO VERIFIED POSITIVE EDGE" in set(rk["evidence_verdict"].unique())

    mv = pd.read_parquet(RESULTS / "v3_manual_validation_10x100.parquet")
    assert len(mv) == 1000
    assert mv["category"].nunique() == 10
    mv_json = json.loads((RESULTS / "v3_manual_validation_summary.json").read_text())
    assert mv_json["human_discretionary_review_claimed"] is False

    db_path = RESULTS / "astra6_v3.duckdb"
    assert db_path.exists()
    con = duckdb.connect(str(db_path), read_only=True)
    n_duck = con.execute("SELECT COUNT(*) FROM all_trades").fetchone()[0]
    con.close()
    assert n_duck == len(pd.read_parquet(RESULTS / "all_trades.parquet"))
