"""Automated Quality Assurance Suite — Section 18 (Tests A through K).

Covers unit, integration, regression, financial accounting, and strict
no-look-ahead (causality) tests.
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from astra6 import bars, clock, crt, ict, signals, sim, smt


def _make_synthetic_panel(n_minutes: int = 360, start_utc: str = "2026-03-09 12:00:00+00:00") -> pd.DataFrame:
    """Controlled minute panel with deterministic Bid/Ask quotes for unit verification
    of state transitions (Tests A, B, C, D, H, I, J, K).
    """
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


def test_A_bearish_m15_crt():
    """Test A — Bearish M15 CRT:
    Previous M15 high is swept, current candle closes back inside previous range,
    and the confirmed CRT event is emitted at the exact M15 close (minute 14 of the bucket).
    """
    panel = _make_synthetic_panel(180, "2026-03-09 13:00:00+00:00")
    # Bucket 1 (13:15..13:29 UTC): reference M15 candle with High = 20050, Low = 20000
    panel.iloc[15:30, panel.columns.get_loc("US100_o")] = 20020.0
    panel.iloc[15:30, panel.columns.get_loc("US100_h")] = 20040.0
    panel.iloc[15:30, panel.columns.get_loc("US100_l")] = 20000.0
    panel.iloc[15:30, panel.columns.get_loc("US100_c")] = 20030.0
    panel.iloc[20, panel.columns.get_loc("US100_h")] = 20050.0  # H_ref = 20050.0

    # Bucket 2 (13:30..13:44 UTC): sweeps 20050 at minute 33 (20058), closes inside at minute 44 (20025)
    panel.iloc[30:45, panel.columns.get_loc("US100_o")] = 20030.0
    panel.iloc[30:45, panel.columns.get_loc("US100_h")] = 20035.0
    panel.iloc[30:45, panel.columns.get_loc("US100_l")] = 20010.0
    panel.iloc[30:45, panel.columns.get_loc("US100_c")] = 20025.0
    panel.iloc[33, panel.columns.get_loc("US100_h")] = 20058.0  # sweep > 20050

    ctx = signals.build_context(panel)
    ev = signals.extract_crt_events(ctx, tf="M15", anchor="cal")
    bear = ev[(ev["dir"] == -1) & (ev["j_open"] == 30)]
    assert len(bear) == 1
    row = bear.iloc[0]
    assert bool(row["A"]) is True
    assert int(row["j_sweep"]) == 33
    assert int(row["j_close"]) == 44  # confirmed only at the 15th minute (13:44 bar close = 13:45)

    conf = signals.materialize_entries(ctx, bear, mode="confirmed")
    assert len(conf) == 1
    assert int(conf.iloc[0]["j_trig"]) == 44


def test_B_h1_developing_vs_confirmed_crt():
    """Test B — H1 Developing CRT:
    Sweep + M1 reclaim + M1 CISD happen inside the H1 candle before it closes.
    Early entry is allowed ONLY in ``dev_cisd`` (before j_close) and NEVER early in ``confirmed``.
    """
    panel = _make_synthetic_panel(240, "2026-03-09 12:00:00+00:00")
    # Hour 1 (indices 60..119, 13:00..13:59 UTC): H_ref = 20060, L_ref = 19990
    panel.iloc[60:120, panel.columns.get_loc("US100_o")] = 20010.0
    panel.iloc[60:120, panel.columns.get_loc("US100_h")] = 20030.0
    panel.iloc[60:120, panel.columns.get_loc("US100_l")] = 19990.0
    panel.iloc[60:120, panel.columns.get_loc("US100_c")] = 20020.0
    panel.iloc[90, panel.columns.get_loc("US100_h")] = 20060.0

    # Hour 2 (indices 120..179, 14:00..14:59 UTC):
    panel.iloc[120:180, panel.columns.get_loc("US100_o")] = 20035.0
    panel.iloc[120:180, panel.columns.get_loc("US100_h")] = 20040.0
    panel.iloc[120:180, panel.columns.get_loc("US100_l")] = 20010.0
    panel.iloc[120:180, panel.columns.get_loc("US100_c")] = 20035.0
    # Up-close delivery into sweep high at index 125 (14:05 UTC), then bearish close below series open at 127
    panel.iloc[124, panel.columns.get_loc("US100_o")] = 20045.0
    panel.iloc[124, panel.columns.get_loc("US100_c")] = 20055.0
    panel.iloc[124, panel.columns.get_loc("US100_h")] = 20056.0
    panel.iloc[125, panel.columns.get_loc("US100_o")] = 20055.0
    panel.iloc[125, panel.columns.get_loc("US100_h")] = 20075.0  # sweeps 20060
    panel.iloc[125, panel.columns.get_loc("US100_c")] = 20062.0
    panel.iloc[126, panel.columns.get_loc("US100_o")] = 20062.0
    panel.iloc[126, panel.columns.get_loc("US100_h")] = 20063.0
    panel.iloc[126, panel.columns.get_loc("US100_c")] = 20040.0  # closes < 20045 (CISD) & <= 20060 (inside range)

    ctx = signals.build_context(panel)
    ev = signals.extract_crt_events(ctx, tf="H1", anchor="cal")
    bear = ev[(ev["dir"] == -1) & (ev["j_open"] == 120)]
    assert len(bear) == 1

    dev = signals.materialize_entries(ctx, bear, mode="dev_cisd")
    conf = signals.materialize_entries(ctx, bear, mode="confirmed")
    assert len(dev) == 1
    assert len(conf) == 1
    assert int(dev.iloc[0]["j_trig"]) == 126  # early entry at 14:06 UTC
    assert int(conf.iloc[0]["j_trig"]) == 179  # confirmed entry only at 14:59 bar close (15:00 UTC)
    assert int(dev.iloc[0]["j_trig"]) < int(conf.iloc[0]["j_trig"])


def test_C_crt_plus_ssmt():
    """Test C — CRT + SSMT:
    US100 sweeps previous high & previous quarter high; US500 does NOT sweep its
    corresponding previous high / reference quarter high. Both std_smt and micro_ssmt fire.
    """
    panel = _make_synthetic_panel(240, "2026-03-09 12:00:00+00:00")
    # Set US500 high in earlier buckets (including 90..104 ref bucket) very high so US500 never sweeps
    panel.iloc[0:105, panel.columns.get_loc("US500_h")] = 5950.0
    # M15 bucket at 90..104 (ref): US100 H_ref = 20050
    panel.iloc[90:105, panel.columns.get_loc("US100_h")] = 20050.0
    panel.iloc[90:105, panel.columns.get_loc("US100_l")] = 20000.0
    # M15 bucket at 105..119 (current): US100 sweeps 20050 -> 20080 and closes at 20020
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


def test_D_quarter_continuation():
    """Test D — Quarter Continuation:
    Signal triggers before quarter ends, position opens immediately and stays open
    across multiple 22.5M and 90M quarter boundaries until TP/SL is reached.
    """
    panel = _make_synthetic_panel(300, "2026-03-09 13:00:00+00:00")
    ql = bars.quarter_labels(panel.index)
    j_en = np.array([20], dtype=np.int64)
    direction = np.array([1], dtype=np.int64)
    sl0 = np.array([19950.0])
    tp0 = np.array([20200.0])  # far TP so trade stays open across quarters
    sw_j = np.array([10], dtype=np.int64)
    sw_p = np.array([19960.0])
    sw_hi = np.array([False])

    r, mfe, mae, hold, j_ex, _, _, _, _, _ = sim.sim_batch(
        panel["US100_o"].to_numpy(), panel["US100_h"].to_numpy(),
        panel["US100_l"].to_numpy(), panel["US100_c"].to_numpy(),
        panel["US100_ao"].to_numpy(), panel["US100_ah"].to_numpy(),
        panel["US100_al"].to_numpy(), panel["US100_ac"].to_numpy(),
        j_en, direction, sl0, tp0,
        sim.EX_FIXED, 180, 0.0, 1.0,
        sw_j, sw_p, sw_hi,
    )
    assert int(j_ex[0]) == 200
    assert ql["b22"].iloc[j_en[0]] < ql["b22"].iloc[j_ex[0]]
    assert ql["b90"].iloc[j_en[0]] < ql["b90"].iloc[j_ex[0]]


def test_E_F_G_dst_suite():
    """Tests E, F, G — NY DST, UK DST, and NY/UK mismatch weeks."""
    assert clock.nasdaq_open_utc(date(2026, 3, 6)) == pd.Timestamp("2026-03-06 14:30", tz="UTC")
    assert clock.nasdaq_open_utc(date(2026, 3, 9)) == pd.Timestamp("2026-03-09 13:30", tz="UTC")
    assert clock.nasdaq_open_utc(date(2026, 11, 2)) == pd.Timestamp("2026-11-02 14:30", tz="UTC")
    assert clock.london_open_utc(date(2026, 3, 27)) == pd.Timestamp("2026-03-27 08:00", tz="UTC")
    assert clock.london_open_utc(date(2026, 3, 30)) == pd.Timestamp("2026-03-30 07:00", tz="UTC")
    assert clock.dst_regime(date(2026, 3, 16)) == "mismatch_spring"
    assert clock.london_ny_open_gap_minutes(date(2026, 3, 16)) == 330


def test_H_candle_anchoring():
    """Test H — Candle Anchoring:
    Calendar H1 (09:00–10:00 NY) vs NY-open-anchored H1 (09:30–10:30 NY) never mix,
    and 09:30–10:30 NY is never complete before 10:30 NY (14:30 UTC in EDT).
    """
    panel = _make_synthetic_panel(240, "2026-03-09 12:00:00+00:00")  # EDT: 08:00..11:59 NY
    h1_cal = bars.resample(panel, "US100", "H1", "cal")
    h1_ny = bars.resample(panel, "US100", "H1", "ny930")

    cal_opens = set(h1_cal["t_open"].dt.tz_convert("America/New_York").dt.strftime("%H:%M"))
    ny_opens = set(h1_ny["t_open"].dt.tz_convert("America/New_York").dt.strftime("%H:%M"))
    assert "09:00" in cal_opens and "09:30" not in cal_opens
    assert "09:30" in ny_opens and "09:00" not in ny_opens

    bar_930 = h1_ny[h1_ny["t_open"].dt.tz_convert("America/New_York").dt.strftime("%H:%M") == "09:30"].iloc[0]
    assert bar_930["t_close"].tz_convert("America/New_York").strftime("%H:%M") == "10:30"


def test_I_no_future_leakage():
    """Test I — No Future Leakage:
    Perturbing or truncating all bars strictly after a trigger index leaves every
    signal emitted up to that trigger index 100% unchanged.
    """
    panel_a = _make_synthetic_panel(300, "2026-03-09 12:00:00+00:00")
    # Create a valid CRT+CISD event in M15 bucket 60..74
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
    # Massively alter future prices after index 100
    for col in panel_b.columns:
        panel_b.iloc[100:, panel_b.columns.get_loc(col)] += 5000.0

    ctx_a = signals.build_context(panel_a)
    ctx_b = signals.build_context(panel_b)
    ev_a = signals.materialize_entries(ctx_a, signals.extract_crt_events(ctx_a, "M15", "cal"), "dev_cisd")
    ev_b = signals.materialize_entries(ctx_b, signals.extract_crt_events(ctx_b, "M15", "cal"), "dev_cisd")
    early_a = ev_a[ev_a["j_trig"] < 90].reset_index(drop=True)
    early_b = ev_b[ev_b["j_trig"] < 90].reset_index(drop=True)
    assert len(early_a) == len(early_b) and len(early_a) >= 1
    for col in ["j_trig", "j_sweep", "sweep_ext_known", "swing_stop", "std_smt", "any_ssmt"]:
        np.testing.assert_allclose(early_a[col].to_numpy(float), early_b[col].to_numpy(float))


def test_J_financial_accounting():
    """Test J — Financial Accounting:
    Independent hand-calculated verification of entry price (Ask+slip for long,
    Bid-slip for short), risk, TP/SL fills, and same-bar SL/TP pessimistic tie-break.
    """
    panel = _make_synthetic_panel(30, "2026-03-09 13:30:00+00:00")
    # Trade 0 (long): enters at j=5 where ask_c=20001.5, slip=0.5 -> ep=20002.0, sl=19992.0 (risk=10)
    # At j=8, bid_h reaches tp=20022.0, exit fill = tp - slip = 20021.5 -> R = (20021.5 - 20002.0)/10 = +1.95R
    panel.iloc[5, panel.columns.get_loc("US100_ac")] = 20001.5
    panel.iloc[8, panel.columns.get_loc("US100_h")] = 20023.0
    panel.iloc[8, panel.columns.get_loc("US100_l")] = 19998.0

    # Trade 1 (long, ambiguous bar): at j=15 both SL (19992) and TP (20022) are touched -> SL wins (-1.05R)
    panel.iloc[12, panel.columns.get_loc("US100_ac")] = 20001.5
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
    assert int(reason[1]) == 1  # SL wins on ambiguous bar
    assert np.isclose(r[1], -1.05)


def test_K_reproducibility():
    """Test K — Reproducibility: identical inputs & configuration yield bit-identical outputs."""
    panel = _make_synthetic_panel(180, "2026-03-09 13:00:00+00:00")
    panel.iloc[15:30, panel.columns.get_loc("US100_h")] = 20050.0
    panel.iloc[33, panel.columns.get_loc("US100_h")] = 20060.0
    ctx1 = signals.build_context(panel)
    ctx2 = signals.build_context(panel)
    s1 = signals.materialize_entries(ctx1, signals.extract_crt_events(ctx1, "M15", "cal"), "confirmed")
    s2 = signals.materialize_entries(ctx2, signals.extract_crt_events(ctx2, "M15", "cal"), "confirmed")
    pd.testing.assert_frame_equal(s1, s2)


def test_L_real_data_deliverables_and_reports():
    """Verify 5-year historical CFD data store, all 26 result tables, and Turkish HTML/PDF reports."""
    from pathlib import Path
    from astra6.report import get_21_questions_answers
    from run_pipeline import REQUIRED_RESULT_FILES, REQUIRED_STORE_FILES

    root = Path(__file__).resolve().parent.parent
    for sf in REQUIRED_STORE_FILES:
        p = root / "data" / "store" / sf
        assert p.exists() and p.stat().st_size > 100_000, f"Missing or empty store file: {sf}"

    for rf in REQUIRED_RESULT_FILES:
        p = root / "data" / "results" / rf
        assert p.exists() and p.stat().st_size > 100, f"Missing or empty result file: {rf}"

    qa_list = get_21_questions_answers()
    assert len(qa_list) == 21
    for idx, (q, a) in enumerate(qa_list, start=1):
        assert q.startswith(f"{idx}.") and len(a) > 80

    html_rep = root / "reports" / "ASTRA6_Arastirma_Raporu.html"
    pdf_rep = root / "reports" / "ASTRA6_Arastirma_Raporu.pdf"
    assert html_rep.exists() and html_rep.stat().st_size > 500_000
    assert pdf_rep.exists() and pdf_rep.stat().st_size > 500_000
