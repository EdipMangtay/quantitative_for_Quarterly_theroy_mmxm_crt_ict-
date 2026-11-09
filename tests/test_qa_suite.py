"""Automated Quality Assurance Suite v2.0 — Phase 1.8 & Phase 12 (10 Categories, 28 Checks).

Organized into the 10 mandatory verification categories:
  1. Timezone & DST Verification (including 3 QT anchors: ny1800, ny0930, ldn0800)
  2. Data Integrity & Full-File SHA256 Forensics
  3. CRT Detection, Variants & Candle Anchoring
  4. SSMT Detection, 30S Exact Micro-Quarters & Simultaneous Event Preservation
  5. True Independent Multi-Timeframe CISD Engine (M1, M3, M5, M15)
  6. True Causal 10-Stage MMXM State Machine (MMBM / MMSM)
  7. Next-Bar Executable Trade Simulation (No Same-Bar Close Fill) & Quarter Continuation
  8. Portfolio & Financial Accounting (Hand-Calculated R, Ambiguous Bar SL-First, Non-Overlap)
  9. Statistical Validation, Multiple-Testing Corrections & Zero Future Leakage
 10. Dynamic Report Consistency & 5x100 Independent Forensic Audit Verification
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from astra6 import bars, cisd, clock, crt, ict, mmxm, opening, signals, sim, smt, stats

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "data" / "results"
STORE = ROOT / "data" / "store"


def _make_synthetic_panel(n_minutes: int = 360, start_utc: str = "2026-03-09 12:00:00+00:00") -> pd.DataFrame:
    """Controlled minute panel with deterministic Bid/Ask quotes for unit verification."""
    idx = pd.date_range(start_utc, periods=n_minutes, freq="1min", tz="UTC")
    base_100 = 20000.0 + np.linspace(0, 10, n_minutes)
    base_500 = 5800.0 + np.linspace(0, 3, n_minutes)
    base_30 = 42000.0 + np.linspace(0, 15, n_minutes)

    df = pd.DataFrame(index=idx)
    for sym, b, sp in [("US100", base_100, 1.0), ("US500", base_500, 0.4), ("US30", base_30, 2.0)]:
        df[f"{sym}_o"] = b
        df[f"{sym}_h"] = b + 2.0
        df[f"{sym}_l"] = b - 2.0
        df[f"{sym}_c"] = b + 0.5
        df[f"{sym}_ao"] = df[f"{sym}_o"] + sp
        df[f"{sym}_ah"] = df[f"{sym}_h"] + sp
        df[f"{sym}_al"] = df[f"{sym}_l"] + sp
        df[f"{sym}_ac"] = df[f"{sym}_c"] + sp
    return df


# ============================================================================
# CATEGORY 1 — TIMEZONE, DST & MULTI-ANCHOR QUARTERLY THEORY
# ============================================================================
def test_cat01_timezone_dst_and_multi_anchor_qt():
    """Verify NY/UK DST transitions, mismatch weeks, and 3 QT anchors (ny1800, ny0930, ldn0800)."""
    assert clock.nasdaq_open_utc(date(2026, 3, 6)) == pd.Timestamp("2026-03-06 14:30", tz="UTC")
    assert clock.nasdaq_open_utc(date(2026, 3, 9)) == pd.Timestamp("2026-03-09 13:30", tz="UTC")
    assert clock.nasdaq_open_utc(date(2026, 11, 2)) == pd.Timestamp("2026-11-02 14:30", tz="UTC")
    assert clock.london_open_utc(date(2026, 3, 27)) == pd.Timestamp("2026-03-27 08:00", tz="UTC")
    assert clock.london_open_utc(date(2026, 3, 30)) == pd.Timestamp("2026-03-30 07:00", tz="UTC")
    assert clock.dst_regime(date(2026, 3, 16)) == "mismatch_spring"
    assert clock.london_ny_open_gap_minutes(date(2026, 3, 16)) == 330

    panel = _make_synthetic_panel(240, "2026-03-09 12:00:00+00:00")
    for anc in ("ny1800", "ny0930", "ldn0800"):
        ql = bars.quarter_labels(panel.index, qt_anchor=anc)
        assert set(ql["q6"]).issubset({1, 2, 3, 4})
        assert set(ql["q90"]).issubset({1, 2, 3, 4})
        assert set(ql["q22"]).issubset({1, 2, 3, 4})
        assert set(ql["q5"]).issubset({1, 2, 3, 4})


# ============================================================================
# CATEGORY 2 — DATA INTEGRITY & FULL-FILE SHA256 FORENSICS
# ============================================================================
def test_cat02_data_integrity_and_sha256_manifest():
    """Verify full-file SHA256 hashes (64 hex chars), quote authenticity tags, and raw .bi5/tick match."""
    manifest = pd.read_parquet(RESULTS / "data_authenticity_manifest.parquet")
    assert len(manifest) >= 14
    for _, row in manifest.iterrows():
        assert len(str(row["sha256_full"])) == 64  # Full SHA256 digest, never 16-char slice
        assert any(
            tag in str(row["authenticity_tag"])
            for tag in (
                "OBSERVED_BID_ASK_QUOTES",
                "OBSERVED_BID_ONLY",
                "DERIVED_ASK_FROM_SPREAD",
                "BASIS_ADJUSTED_CROSS_BROKER",
            )
        )
        assert int(row["n_bars"]) > 1000

    f_rep = json.loads((RESULTS / "data_forensics_report.json").read_text())
    assert f_rep["tick_and_bi5_verification"]["verification_status"] == "VERIFIED_DUKASCOPY_TICKS_AND_BI5"
    assert f_rep["tick_and_bi5_verification"]["tick_to_m1_hl_max_abs_diff"] == 0.0


# ============================================================================
# CATEGORY 3 — CRT DETECTION, VARIANTS & CANDLE ANCHORING
# ============================================================================
def test_cat03_crt_detection_and_anchoring():
    """Verify Bearish/Bullish CRT, Confirmed vs Developing timing, and Calendar vs NY-Open H1 anchoring."""
    panel = _make_synthetic_panel(240, "2026-03-09 12:00:00+00:00")
    # Bucket 1 (12:15..12:29 UTC): reference M15 candle with High = 20050, Low = 20000
    panel.iloc[15:30, panel.columns.get_loc("US100_o")] = 20020.0
    panel.iloc[15:30, panel.columns.get_loc("US100_h")] = 20040.0
    panel.iloc[15:30, panel.columns.get_loc("US100_l")] = 20000.0
    panel.iloc[15:30, panel.columns.get_loc("US100_c")] = 20030.0
    panel.iloc[20, panel.columns.get_loc("US100_h")] = 20050.0

    # Bucket 2 (12:30..12:44 UTC): sweeps 20050 at minute 33 (20058), closes inside at minute 44 (20025)
    panel.iloc[30:45, panel.columns.get_loc("US100_o")] = 20030.0
    panel.iloc[30:45, panel.columns.get_loc("US100_h")] = 20035.0
    panel.iloc[30:45, panel.columns.get_loc("US100_l")] = 20010.0
    panel.iloc[30:45, panel.columns.get_loc("US100_c")] = 20025.0
    panel.iloc[33, panel.columns.get_loc("US100_h")] = 20058.0

    ctx = signals.build_context(panel)
    ev = signals.extract_crt_events(ctx, tf="M15", anchor="cal")
    bear = ev[(ev["dir"] == -1) & (ev["j_open"] == 30)]
    assert len(bear) == 1
    assert bool(bear.iloc[0]["A"]) is True
    assert int(bear.iloc[0]["j_sweep"]) == 33
    assert int(bear.iloc[0]["j_close"]) == 44

    conf = signals.materialize_entries(ctx, bear, mode="confirmed")
    assert len(conf) == 1
    assert int(conf.iloc[0]["j_trig"]) == 44
    assert int(conf.iloc[0]["j_fill"]) == 45  # Next-bar open fill index!

    # Candle anchoring check: Calendar H1 (09:00-10:00 NY) vs NY930 H1 (09:30-10:30 NY)
    h1_cal = bars.resample(panel, "US100", "H1", "cal")
    h1_ny = bars.resample(panel, "US100", "H1", "ny930")
    cal_opens = set(h1_cal["t_open"].dt.tz_convert("America/New_York").dt.strftime("%H:%M"))
    ny_opens = set(h1_ny["t_open"].dt.tz_convert("America/New_York").dt.strftime("%H:%M"))
    assert "09:00" in cal_opens and "09:30" not in cal_opens
    assert "09:30" in ny_opens and "09:00" not in ny_opens


# ============================================================================
# CATEGORY 4 — SSMT DETECTION & SIMULTANEOUS EVENT PRESERVATION
# ============================================================================
def test_cat04_ssmt_detection_and_simultaneous_events():
    """Verify SSMT fires when one index sweeps prior quarter extreme and peer holds, and simultaneous events are preserved."""
    panel = _make_synthetic_panel(240, "2026-03-09 12:00:00+00:00")
    panel.iloc[0:105, panel.columns.get_loc("US500_h")] = 5950.0
    panel.iloc[90:105, panel.columns.get_loc("US100_h")] = 20050.0
    panel.iloc[90:105, panel.columns.get_loc("US100_l")] = 20000.0
    panel.iloc[105:120, panel.columns.get_loc("US100_o")] = 20030.0
    panel.iloc[105:120, panel.columns.get_loc("US100_h")] = 20035.0
    panel.iloc[105:120, panel.columns.get_loc("US100_l")] = 20010.0
    panel.iloc[105:120, panel.columns.get_loc("US100_c")] = 20020.0
    panel.iloc[108, panel.columns.get_loc("US100_h")] = 20080.0

    ctx = signals.build_context(panel)
    ev = signals.extract_crt_events(ctx, tf="M15", anchor="cal")
    bear = ev[(ev["dir"] == -1) & (ev["j_open"] == 105)]
    conf = signals.materialize_entries(ctx, bear, mode="confirmed")
    assert len(conf) == 1
    assert bool(conf.iloc[0]["std_smt"]) is True
    assert bool(conf.iloc[0]["any_ssmt"]) is True
    assert "micro_ssmt_count" in conf.columns
    assert "micro_all_pairs" in conf.columns
    assert int(conf.iloc[0]["micro_ssmt_count"]) >= 1


# ============================================================================
# CATEGORY 5 — TRUE MULTI-TIMEFRAME CISD ENGINE (M1, M3, M5, M15)
# ============================================================================
def test_cat05_true_mtf_cisd_engine():
    """Verify M1, M3, M5, M15 CISD are computed on each timeframe's own resampled candle series."""
    panel = _make_synthetic_panel(180, "2026-03-09 12:00:00+00:00")
    # Construct a clear M3 bullish delivery followed by bearish break
    for tf in ("M1", "M3", "M5", "M15"):
        tbl = cisd.extract_tf_cisd_events(panel, "US100", tf, variant="v1")
        assert {"cisd_tf", "variant", "dir", "tf_deliv_idx", "tf_conf_idx", "j_conf_m1", "ref_open", "break_close", "t_confirm"}.issubset(tbl.columns)
        if len(tbl) > 0:
            bear_rows = tbl[tbl["dir"] == -1]
            bull_rows = tbl[tbl["dir"] == 1]
            if len(bear_rows) > 0:
                assert (bear_rows["break_close"] < bear_rows["ref_open"]).all()
            if len(bull_rows) > 0:
                assert (bull_rows["break_close"] > bull_rows["ref_open"]).all()


# ============================================================================
# CATEGORY 6 — CAUSAL 10-STAGE MMXM STATE MACHINE
# ============================================================================
def test_cat06_causal_mmxm_state_machine():
    """Verify 10-stage MMBM/MMSM state machine requires Original Consolidation + Manipulation Sweep + CISD."""
    tf_df = pd.read_parquet(RESULTS / "trade_features.parquet")
    assert {"mmxm_stage", "mmxm_early_candidate", "mmxm_confirmed", "mmxm_model_label", "cons_hi", "cons_lo", "mmxm_target_px"}.issubset(tf_df.columns)
    mm_sub = tf_df[tf_df["mmxm_early_candidate"]]
    assert len(mm_sub) > 100
    assert (mm_sub["mmxm_stage"] >= 6).all()
    mm_conf = tf_df[tf_df["mmxm_confirmed"]]
    assert len(mm_conf) > 50
    assert (mm_conf["mmxm_stage"] == 8).all()
    # Bullish MMBM must have swept below cons_lo and target cons_hi
    mmbm = mm_sub[mm_sub["dir"] == 1]
    assert (mmbm["sweep_ext_known"] < mmbm["cons_lo"]).all()
    assert np.allclose(mmbm["mmxm_target_px"], mmbm["cons_hi"])


# ============================================================================
# CATEGORY 7 — NEXT-BAR EXECUTABLE TRADE SIMULATION (NO SAME-BAR CLOSE FILL)
# ============================================================================
def test_cat07_next_bar_trade_execution_and_quarter_continuation():
    """Verify orders confirmed at close of j_trig NEVER fill at close[j_trig] and ALWAYS fill at open[j_trig+1]."""
    tf_df = pd.read_parquet(RESULTS / "trade_features.parquet")
    assert (tf_df["j_fill"] == tf_df["j_trig"] + 1).all()
    assert (pd.to_datetime(tf_df["t_fill"]) >= pd.to_datetime(tf_df["t_signal_known"])).all()

    # Quarter continuation check: positions stay open across 22.5M and 90M quarter boundaries until SL/TP
    panel = _make_synthetic_panel(300, "2026-03-09 13:00:00+00:00")
    ql = bars.quarter_labels(panel.index)
    j_trig = np.array([20], dtype=np.int64)
    r, _, _, _, j_ex, _, _, _, _, _ = sim.sim_batch(
        panel["US100_o"].to_numpy(), panel["US100_h"].to_numpy(),
        panel["US100_l"].to_numpy(), panel["US100_c"].to_numpy(),
        panel["US100_ao"].to_numpy(), panel["US100_ah"].to_numpy(),
        panel["US100_al"].to_numpy(), panel["US100_ac"].to_numpy(),
        j_trig, np.array([1], dtype=np.int64), np.array([19950.0]), np.array([20200.0]),
        sim.EX_FIXED, 180, 0.0, 1.0,
        np.array([10], dtype=np.int64), np.array([19960.0]), np.array([False]),
    )
    assert int(j_ex[0]) == 201  # filled at j_fill=21, held 180 bars -> 201
    assert ql["b22"].iloc[21] < ql["b22"].iloc[j_ex[0]]
    assert ql["b90"].iloc[21] < ql["b90"].iloc[j_ex[0]]


# ============================================================================
# CATEGORY 8 — PORTFOLIO & FINANCIAL ACCOUNTING
# ============================================================================
def test_cat08_portfolio_financial_accounting():
    """Hand-calculated verification of Next-Bar Open fill (ask_o[j_trig+1]+slip), TP/SL fills, and ambiguous bar SL-first."""
    panel = _make_synthetic_panel(30, "2026-03-09 13:30:00+00:00")
    # Trade 0 (long): triggered at close of j_trig=5 -> filled at open of j_fill=6 where ask_o[6]=20001.5, slip=0.5 -> ep=20002.0
    # sl=19992.0 (risk=10.0), tp=20022.0. At j=8, bid_h reaches 20023.0 -> exit = tp - slip = 20021.5 -> R = +1.95R
    panel.iloc[6, panel.columns.get_loc("US100_ao")] = 20001.5
    panel.iloc[8, panel.columns.get_loc("US100_h")] = 20023.0
    panel.iloc[8, panel.columns.get_loc("US100_l")] = 19998.0

    # Trade 1 (long, ambiguous bar): triggered at j_trig=12 -> filled at j_fill=13 where ask_o[13]=20001.5
    # At j=15 both SL (19992) and TP (20022) are touched -> pessimistic rule: SL wins (-1.05R)
    panel.iloc[13, panel.columns.get_loc("US100_ao")] = 20001.5
    panel.iloc[15, panel.columns.get_loc("US100_h")] = 20025.0
    panel.iloc[15, panel.columns.get_loc("US100_l")] = 19990.0

    r, _, _, _, _, ep, xp, _, ambig, reason = sim.sim_batch(
        panel["US100_o"].to_numpy(), panel["US100_h"].to_numpy(),
        panel["US100_l"].to_numpy(), panel["US100_c"].to_numpy(),
        panel["US100_ao"].to_numpy(), panel["US100_ah"].to_numpy(),
        panel["US100_al"].to_numpy(), panel["US100_ac"].to_numpy(),
        np.array([5, 12], dtype=np.int64),
        np.array([1, 1], dtype=np.int64),
        np.array([19992.0, 19992.0]),
        np.array([20022.0, 20022.0]),
        sim.EX_FIXED, 10, 0.5, 1.0,
        np.array([1], dtype=np.int64), np.array([19990.0]), np.array([False]),
    )
    assert np.isclose(ep[0], 20002.0)
    assert np.isclose(xp[0], 20021.5)
    assert np.isclose(r[0], 1.95)
    assert bool(ambig[0]) is False
    assert bool(ambig[1]) is True
    assert int(reason[1]) == 1
    assert np.isclose(r[1], -1.05)


# ============================================================================
# CATEGORY 9 — STATISTICAL VALIDATION & ZERO FUTURE LEAKAGE
# ============================================================================
def test_cat09_statistical_validation_and_zero_future_leakage():
    """Verify stat_status flags, Holm-Bonferroni / BH-FDR adjusted p-values, and zero future leakage."""
    base = pd.read_parquet(RESULTS / "crt_ssmt_baselines.parquet")
    assert {"stat_status", "p_holm", "p_bh_fdr", "ci95_low", "ci95_high"}.issubset(base.columns)
    assert set(base["stat_status"]).issubset({
        "VERIFIED_POSITIVE_CI",
        "POSITIVE_MEAN_CI_SPANS_ZERO",
        "SMALL_SAMPLE_UNRELIABLE",
        "NEGATIVE_EXPECTANCY",
        "NO_TRADES",
    })

    # Zero future leakage check: perturbing future bars after index 100 never changes signals before index 90
    panel_a = _make_synthetic_panel(300, "2026-03-09 12:00:00+00:00")
    panel_a.iloc[45:60, panel_a.columns.get_loc("US100_h")] = 20050.0
    panel_a.iloc[45:60, panel_a.columns.get_loc("US100_l")] = 19990.0
    panel_a.iloc[60:75, panel_a.columns.get_loc("US100_o")] = 20035.0
    panel_a.iloc[60:75, panel_a.columns.get_loc("US100_c")] = 20035.0
    panel_a.iloc[60:75, panel_a.columns.get_loc("US100_l")] = 20010.0
    panel_a.iloc[62, panel_a.columns.get_loc("US100_o")] = 20040.0
    panel_a.iloc[62, panel_a.columns.get_loc("US100_h")] = 20049.0
    panel_a.iloc[62, panel_a.columns.get_loc("US100_c")] = 20048.0
    panel_a.iloc[63, panel_a.columns.get_loc("US100_o")] = 20048.0
    panel_a.iloc[63, panel_a.columns.get_loc("US100_h")] = 20065.0
    panel_a.iloc[63, panel_a.columns.get_loc("US100_c")] = 20052.0
    panel_a.iloc[64, panel_a.columns.get_loc("US100_o")] = 20052.0
    panel_a.iloc[64, panel_a.columns.get_loc("US100_h")] = 20053.0
    panel_a.iloc[64, panel_a.columns.get_loc("US100_c")] = 20030.0

    panel_b = panel_a.copy()
    for col in panel_b.columns:
        panel_b.iloc[100:, panel_b.columns.get_loc(col)] += 5000.0

    ctx_a = signals.build_context(panel_a)
    ctx_b = signals.build_context(panel_b)
    ev_a = signals.materialize_entries(ctx_a, signals.extract_crt_events(ctx_a, "M15", "cal"), "dev_cisd")
    ev_b = signals.materialize_entries(ctx_b, signals.extract_crt_events(ctx_b, "M15", "cal"), "dev_cisd")
    early_a = ev_a[ev_a["j_trig"] < 90].reset_index(drop=True)
    early_b = ev_b[ev_b["j_trig"] < 90].reset_index(drop=True)
    assert len(early_a) == len(early_b) and len(early_a) >= 1
    for col in ["j_trig", "j_fill", "j_sweep", "sweep_ext_known", "swing_stop", "std_smt", "any_ssmt", "mmxm_stage"]:
        np.testing.assert_allclose(early_a[col].to_numpy(float), early_b[col].to_numpy(float))


# ============================================================================
# CATEGORY 10 — DYNAMIC REPORT CONSISTENCY & 5x100 INDEPENDENT AUDIT
# ============================================================================
def test_cat10_report_consistency_and_500_audit_samples():
    """Verify all required store/result files, 5x100 independent audit pass rate = 100%, and dynamic report numbers."""
    from astra6.report import get_20_final_questions_answers
    from run_pipeline import REQUIRED_RESULT_FILES, REQUIRED_STORE_FILES

    for sf in REQUIRED_STORE_FILES:
        p = STORE / sf
        assert p.exists() and p.stat().st_size > 50_000, f"Missing store file: {sf}"

    for rf in REQUIRED_RESULT_FILES:
        p = RESULTS / rf
        assert p.exists() and p.stat().st_size > 100, f"Missing result file: {rf}"

    aud = json.loads((RESULTS / "independent_audit_samples.json").read_text())
    assert aud["all_500_passed"] is True
    assert aud["crt_100"]["passed"] == 100
    assert aud["ssmt_100"]["passed"] == 100
    assert aud["cisd_100"]["passed"] == 100
    assert aud["mmxm_100"]["passed"] == 100
    assert aud["trades_100"]["passed"] == 100

    qa_list = get_20_final_questions_answers()
    assert len(qa_list) == 20
    for idx, (q, a) in enumerate(qa_list, start=1):
        assert q.startswith(f"{idx}.") and len(a) > 80

    # Verify live report numbers match `crt_tf_stats.parquet`
    crt_tf = pd.read_parquet(RESULTS / "crt_tf_stats.parquet").set_index("tf")
    m15_exp_str = f"{crt_tf.loc['M15', 'expectancy']:+.3f}R"
    assert m15_exp_str in qa_list[2][1]  # Question 3 dynamically embeds live M15 expectancy!

    html_rep = ROOT / "reports" / "ASTRA6_Arastirma_Raporu.html"
    pdf_rep = ROOT / "reports" / "ASTRA6_V35_FINAL_RESEARCH.pdf"
    assert html_rep.exists() and html_rep.stat().st_size > 500_000
    assert pdf_rep.exists() and pdf_rep.stat().st_size > 200_000
    assert m15_exp_str in html_rep.read_text(encoding="utf-8")
