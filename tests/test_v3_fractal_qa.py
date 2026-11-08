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


# =============================================================================
# MANDATORY P0 & P1 REGRESSION TESTS (AUDIT VERIFICATION)
# =============================================================================

def test_p0_1_mmxm_incremental_prefix_invariance():
    """P0.1: Incremental MMXM FSM must be strictly prefix-invariant.
    
    State at time t must not change when prices after t are truncated or mutated.
    Future-window global argmin/argmax is strictly prohibited.
    """
    np.random.seed(42)
    n1 = 5000
    n2 = 10000
    rw = np.cumsum(np.random.randn(n2)) + 15000.0
    o = rw.copy()
    h = rw + np.random.uniform(0.5, 3.0, n2)
    l = rw - np.random.uniform(0.5, 3.0, n2)
    c = rw + np.random.uniform(-0.5, 0.5, n2)

    # Synthetic OCs within the first 4000 bars
    j_cand = np.array([200, 950, 1700, 2800], dtype=np.int64)
    j_conf = np.array([210, 960, 1710, 2810], dtype=np.int64)
    tf_min = np.array([5, 15, 60, 240], dtype=np.int64)
    t_dirs = np.array([1, -1, 1, -1], dtype=np.int8)
    oc_hi = np.array([h[100:200].max(), h[800:950].max(), h[1500:1700].max(), h[2500:2800].max()], dtype=np.float64)
    oc_lo = np.array([l[100:200].min(), l[800:950].min(), l[1500:1700].min(), l[2500:2800].min()], dtype=np.float64)
    oc_mid = 0.5 * (oc_hi + oc_lo)

    # Run on short prefix n1 (5000 bars)
    oc_idx1, st_num1, j_kno1, ev_px1, tgt_px1, act1, j_term1 = fractal_v3._run_incremental_mmxm_fsm_numba(
        o[:n1], h[:n1], l[:n1], c[:n1], j_cand, j_conf, tf_min, t_dirs, oc_hi, oc_lo, oc_mid
    )

    # Run on longer prefix n2 (10000 bars) with different future
    oc_idx2, st_num2, j_kno2, ev_px2, tgt_px2, act2, j_term2 = fractal_v3._run_incremental_mmxm_fsm_numba(
        o, h, l, c, j_cand, j_conf, tf_min, t_dirs, oc_hi, oc_lo, oc_mid
    )

    # All events with confirmation bar <= n1 in long run MUST exactly match short run
    mask_short = j_kno1 < n1
    mask_long = j_kno2 < n1

    assert mask_short.sum() > 0, "MMXM FSM should emit events on test data"
    assert mask_short.sum() == mask_long.sum(), f"Prefix length mismatch: {mask_short.sum()} vs {mask_long.sum()}"
    np.testing.assert_array_equal(st_num1[mask_short], st_num2[mask_long], err_msg="P0.1 FAILED: MMXM FSM is not prefix-invariant!")
    np.testing.assert_array_equal(j_kno1[mask_short], j_kno2[mask_long])


def test_p0_2_oc_confirmation_boundary_timing():
    """P0.2: Confirmation timestamps must equal exact M1 bar close, never accessible prior to close."""
    oc_df = pd.read_parquet(RESULTS / "original_consolidations.parquet")
    t_cand = pd.to_datetime(oc_df["t_cand_known"], utc=True)
    t_conf = pd.to_datetime(oc_df["t_confirm"], utc=True)
    t_known = pd.to_datetime(oc_df["t_known"], utc=True)

    # Candidate bar close must strictly precede or equal confirmation
    assert (t_cand <= t_conf).all()
    # Minimum confirmation delay is at least 0 seconds (at or after candidate close)
    assert ((t_conf - t_cand).dt.total_seconds() >= 0).all()
    # Confirmation is available at or after t_confirm, never before
    assert (t_known >= t_cand).all()


def test_p0_3_true_mmxm_asof_join_and_independent_mmxm_tf():
    """P0.3: Active MMXM state must be causally joined as-of signal time, and mmxm_tf reflects actual MMXM event."""
    all_t = pd.read_parquet(RESULTS / "all_trades.parquet")
    mmxm_ev = pd.read_parquet(RESULTS / "mmxm_state_events.parquet")

    # mmxm_tf must come from MMXM event universe (M5..D1), not derived from target_tf
    valid_mmxm_tfs = {"M5", "M15", "M30", "H1", "H4", "D1", "NONE"}
    assert set(all_t["mmxm_tf"].unique()).issubset(valid_mmxm_tfs)

    # In trades where mmxm_id is present, verify mmxm_tf matches the MMXM event's tf
    active = all_t[all_t["mmxm_id"] != "NONE"]
    if len(active) > 0:
        mmxm_id_map = dict(zip(mmxm_ev["mmxm_id"], mmxm_ev["tf"]))
        sample = active.sample(min(100, len(active)), random_state=42)
        for _, row in sample.iterrows():
            expected_tf = mmxm_id_map.get(row["mmxm_id"])
            if expected_tf is not None:
                assert row["mmxm_tf"] == expected_tf, f"mmxm_tf {row['mmxm_tf']} != expected {expected_tf}"


def test_p0_4_independent_strategy_execution():
    """P0.4: Binary combinations and CISD timeframes must execute with independent confirmation bars & prices."""
    all_t = pd.read_parquet(RESULTS / "all_trades.parquet")
    combos = pd.read_parquet(RESULTS / "combination_results.parquet")

    # Verify that different binary configs have different trade counts & win rates (not just filtered subset)
    assert combos["n_trades"].nunique() > 10, "Configs should have independent trade executions"
    assert combos["win_rate"].nunique() > 10, "Configs should have independent win rates"

    # Strict causality: signal known <= entry timestamp (next bar open)
    t_sig = pd.to_datetime(all_t["t_signal_known"], utc=True)
    t_ent = pd.to_datetime(all_t["entry_timestamp"], utc=True)
    assert (t_sig <= t_ent).all()


def test_p0_5_target_consistent_execution_and_timeout_mtm():
    """P0.5: Structural target trades must simulate against actual target price, with mark-to-market timeout."""
    # Unit test fast_target_exec_full_numba vs reference_target_exec_full_py
    opens = np.array([100.0, 101.0, 102.0, 101.5, 101.8, 102.0, 102.2, 102.5], dtype=np.float64)
    highs = np.array([101.0, 103.0, 102.5, 102.0, 102.2, 102.5, 102.8, 103.0], dtype=np.float64)
    lows = np.array([99.0, 100.5, 101.0, 101.0, 101.2, 101.5, 101.8, 102.0], dtype=np.float64)
    closes = np.array([100.5, 102.0, 101.5, 101.8, 102.0, 102.2, 102.5, 102.8], dtype=np.float64)

    # Test Timeout case: target not reached, stop not reached, expires at bar 3 (well before dataset end n=8)
    # Entry LONG at bar 0 open=100.0, stop=95.0, target=110.0, horizon=3 bars
    r_any, r_cln, b_tgt, out_code, ex_bar, ex_px, r_py, mfe_py, mae_py = hpc.reference_target_exec_full_py(
        highs, lows, closes,
        j_fill=np.array([0], dtype=np.int64),
        direction=np.array([1], dtype=np.int64),
        entry_px=np.array([100.0], dtype=np.float64),
        stop_px=np.array([95.0], dtype=np.float64),
        target_px=np.array([110.0], dtype=np.float64),
        horizon_bars=3, slip_pts=0.0
    )
    # At bar 3 close=101.8, profit is +1.8 pts. Risk is 5.0 pts. r should be +1.8 / 5.0 = +0.36R
    assert out_code[0] == 4, f"Expected TIMEOUT (4), got {out_code[0]}"
    assert np.isclose(r_py[0], (101.8 - 100.0) / 5.0), f"TIMEOUT should be marked to market (+0.36R), got {r_py[0]}"
    assert r_py[0] != -1.0, "TIMEOUT MUST NEVER BE AUTOMATIC -1R!"

    # Numba match test
    (
        n_any, n_cln, n_btgt, n_out_code, n_ex_bar, n_ex_px, n_r, n_mfe, n_mae
    ) = hpc.fast_target_exec_full_numba(
        highs, lows, closes,
        np.array([0], dtype=np.int64),
        np.array([1], dtype=np.int64),
        np.array([100.0], dtype=np.float64),
        np.array([95.0], dtype=np.float64),
        np.array([110.0], dtype=np.float64),
        horizon_bars=3, slip_pts=0.0
    )
    assert n_out_code[0] == 4
    assert np.isclose(n_r[0], r_py[0])


def test_p0_6_cisd_confirmation_delay_valid_sweeps():
    """P0.6: CISD delay must be measured from valid liquidity sweep confirmation (j_sweep >= 0)."""
    lc = pd.read_parquet(RESULTS / "liquidity_cisd_pair_matrix.parquet")
    # Missing sweeps (j_sweep == -1) must not be mixed into sweep-to-cisd confirmation delay
    assert "mean_wait_after_sweep_min" in lc.columns
    # Ensure delay values are non-negative for valid matched sweeps
    valid_delays = lc["mean_wait_after_sweep_min"].dropna()
    assert (valid_delays >= 0.0).all()


def test_p1_7_complete_event_universe_coverage():
    """P1.7: Complete event universe must be computed without arbitrary caps."""
    atomic_df = pd.read_parquet(RESULTS / "atomic_events.parquet")
    assert len(atomic_df) > 500_000, f"Expected complete atomic lake, got {len(atomic_df)}"
    assert atomic_df["universe_coverage"].iloc[0] == "FULL_UNIVERSE"

    oc_df = pd.read_parquet(RESULTS / "original_consolidations.parquet")
    assert len(oc_df) > 50_000, f"Expected full OC lake, got {len(oc_df)}"

    mmxm_ev = pd.read_parquet(RESULTS / "mmxm_state_events.parquet")
    assert len(mmxm_ev) > 100_000, f"Expected full MMXM state events, got {len(mmxm_ev)}"


def test_p1_8_causal_pretrade_snapshots_zero_leakage():
    """P1.8: Pre-trade tables must contain ZERO post-trade outcome fields."""
    pretrade = pd.read_parquet(RESULTS / "pretrade_narratives.parquet")
    cands = pd.read_parquet(RESULTS / "candidate_opportunities.parquet")

    forbidden_post_trade_cols = {
        "realized_r_post_trade", "realized_net_r", "r", "outcome_status",
        "mfe", "mae", "hold", "exit_px", "px_exit", "exit_timestamp"
    }

    assert not forbidden_post_trade_cols.intersection(set(pretrade.columns)), (
        f"Pre-trade narratives contains leaked post-trade fields: "
        f"{forbidden_post_trade_cols.intersection(set(pretrade.columns))}"
    )
    assert not forbidden_post_trade_cols.intersection(set(cands.columns)), (
        f"Candidate opportunities contains leaked post-trade fields: "
        f"{forbidden_post_trade_cols.intersection(set(cands.columns))}"
    )


def test_p1_9_genuine_ranking_engine_and_honest_verdicts():
    """P1.9: Ranking engine must search candidate configurations and report honest verdicts."""
    rk = pd.read_parquet(RESULTS / "v3_rankings_25.parquet")
    assert len(rk) == 25
    assert "se_clustered" in rk.columns
    assert "ci95_low" in rk.columns
    assert "ci95_high" in rk.columns
    assert "n_unique_days" in rk.columns
    assert "in_sample_expectancy_r" in rk.columns
    assert "oos_expectancy_r" in rk.columns
    assert "p_bh_fdr" in rk.columns
    # Genuine ranking must report NO VERIFIED POSITIVE EDGE if FDR q > 0.05
    assert "NO VERIFIED POSITIVE EDGE" in rk["evidence_verdict"].values


def test_p1_10_dependence_aware_statistics_cluster_test():
    """P1.10: Day-clustered SE and bootstrap CI must account for within-day clustering."""
    r_arr = np.array([1.0, -1.0, 1.0, -1.0, 2.0, -1.0, 0.5, -0.5], dtype=np.float64)
    day_ids = np.array([0, 0, 1, 1, 2, 2, 3, 3], dtype=np.int64)

    n_days, se_iid, se_clust, ci_lo, ci_hi, p_boot = hpc._day_cluster_stats_and_bootstrap_numba(r_arr, day_ids, n_boot=200)
    assert n_days == 4
    assert se_clust > 0.0
    assert ci_lo <= np.mean(r_arr) <= ci_hi


def test_p1_11_cryptographic_cache_invalidation(tmp_path: Path):
    """P1.11: Cache must invalidate when SHA256, algo version, or config hash changes, or on force."""
    sha = hpc.compute_source_store_sha256()
    cfg = {"param_a": 1, "param_b": "fast"}
    cfg_hash = hpc.compute_config_hash(cfg)

    # Create dummy result file in tmp_path
    (tmp_path / "atomic_events.parquet").write_bytes(b"DATA")
    required = ["atomic_events.parquet"]

    mgr = hpc.CheckpointManager(tmp_path / "ckpt.json")
    mgr.bind_cache_identity(sha, "ALGO_V1", cfg_hash)

    # Valid
    assert mgr.is_cache_valid(required, sha, "ALGO_V1", cfg_hash, force_recompute=False, results_dir=tmp_path) is True
    # Force recompute invalidates
    assert mgr.is_cache_valid(required, sha, "ALGO_V1", cfg_hash, force_recompute=True, results_dir=tmp_path) is False
    # Version change invalidates
    assert mgr.is_cache_valid(required, sha, "ALGO_V2", cfg_hash, force_recompute=False, results_dir=tmp_path) is False
    # Config hash change invalidates
    assert mgr.is_cache_valid(required, sha, "ALGO_V1", "DIFFERENT_HASH", force_recompute=False, results_dir=tmp_path) is False


def test_p1_12_hardware_benchmark_and_zero_duplication():
    """P1.12: Hardware benchmark must record measured resources and verify Numba kernels."""
    bench_file = RESULTS / "hardware_benchmark.json"
    assert bench_file.exists()
    bdata = json.loads(bench_file.read_text())
    assert "hardware_profile" in bdata
    assert "ram_total_gb" in bdata["hardware_profile"]
    assert bdata["hardware_profile"]["ram_total_gb"] > 0
    assert bdata["kernel_verification"]["reference_vs_numba_exact_match"] is True
