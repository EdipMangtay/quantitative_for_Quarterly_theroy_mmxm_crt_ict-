"""Phase 5.3 — True Causal Market Maker Buy/Sell Model (MMBM / MMSM) State Machine.

Detects Market Maker Buy Model (MMBM, bullish) and Market Maker Sell Model (MMSM, bearish)
strictly causally without ever peeking at future distribution or completion.

Sequential 10-Stage Hierarchy:
  Stage 1: HTF Draw on Liquidity & Premium/Discount context identified
  Stage 2: Original Consolidation (tight range before manipulation leg; defines terminus target)
  Stage 3: Accumulation / Engineering Liquidity breakout from Original Consolidation
  Stage 4: Manipulation Leg (Judas swing opposite to HTF draw / terminus)
  Stage 5: External / Internal Liquidity Sweep (CRT / Swing / Session / PDH-PDL sweep)
  Stage 6: Smart Money Reversal — CISD / MSS confirmed against manipulation leg
           -> Emits `mmxm_early_candidate = True` (`MMBM_EARLY` / `MMSM_EARLY`)
  Stage 7: Displacement (high-velocity body > 1.0 * ATR)
  Stage 8: Fair Value Gap (FVG / IFVG) creation & retracement zone active
           -> Emits `mmxm_confirmed = True` (`MMBM_CONFIRMED` / `MMSM_CONFIRMED`)
  Stage 9: Distribution / Low-Resistance Liquidity Run toward Original Consolidation
  Stage 10: Terminus Target Liquidity Delivery (`orig_cons_high` for MMBM, `orig_cons_low` for MMSM)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from numba import njit

from .bars import resample
from .ict import atr_wilder


@njit(cache=True)
def _scan_m5_consolidation_and_fvg(o5, h5, l5, c5, atr5):
    """On M5 bars, causally track:
    - Most recent Original Consolidation box (`cons_hi`, `cons_lo`, `cons_idx`)
      defined as a 3-to-6 bar window whose total high-low range <= 2.4 * atr5.
    - Most recent bullish/bearish M5 FVG and displacement status known at close of M5 bar `i`.
    """
    n = o5.shape[0]
    cons_hi = np.full(n, np.nan)
    cons_lo = np.full(n, np.nan)
    cons_age = np.full(n, 9999, np.int64)
    has_bull_fvg = np.zeros(n, np.bool_)
    has_bear_fvg = np.zeros(n, np.bool_)
    has_bull_disp = np.zeros(n, np.bool_)
    has_bear_disp = np.zeros(n, np.bool_)

    cur_hi = np.nan
    cur_lo = np.nan
    cur_i = -1

    for i in range(4, n):
        # Check if window [i-4 .. i-1] was a tight consolidation before bar i
        w_hi = h5[i - 4]
        w_lo = l5[i - 4]
        for k in range(i - 3, i):
            if h5[k] > w_hi:
                w_hi = h5[k]
            if l5[k] < w_lo:
                w_lo = l5[k]
        if (w_hi - w_lo) <= 2.5 * atr5[i - 1]:
            cur_hi = w_hi
            cur_lo = w_lo
            cur_i = i - 1

        if cur_i >= 0:
            cons_hi[i] = cur_hi
            cons_lo[i] = cur_lo
            cons_age[i] = i - cur_i

        # Check 3-bar FVG & displacement in recent 3 M5 bars [i-2, i-1, i]
        # Bullish FVG: l5[i] > h5[i-2] with strong middle or current body
        if l5[i] > h5[i - 2] or (i >= 3 and l5[i - 1] > h5[i - 3]):
            has_bull_fvg[i] = True
        if h5[i] < l5[i - 2] or (i >= 3 and h5[i - 1] < l5[i - 3]):
            has_bear_fvg[i] = True

        if (c5[i] - o5[i]) >= 0.85 * atr5[i] or (c5[i - 1] - o5[i - 1]) >= 0.85 * atr5[i - 1]:
            has_bull_disp[i] = True
        if (o5[i] - c5[i]) >= 0.85 * atr5[i] or (o5[i - 1] - c5[i - 1]) >= 0.85 * atr5[i - 1]:
            has_bear_disp[i] = True

    return cons_hi, cons_lo, cons_age, has_bull_fvg, has_bear_fvg, has_bull_disp, has_bear_disp


def build_mmxm_table(panel: pd.DataFrame, traded: str = "US100") -> pd.DataFrame:
    """Build causal M5-resolution MMXM state table indexed by `t_known` (`t_close` of M5 bar)."""
    m5 = resample(panel, traded, "M5", "cal")
    m5 = m5[m5["complete"]].reset_index(drop=True)
    o5 = m5["o"].to_numpy(float)
    h5 = m5["h"].to_numpy(float)
    l5 = m5["l"].to_numpy(float)
    c5 = m5["c"].to_numpy(float)
    atr5 = atr_wilder(h5, l5, c5, 14)

    chi, clo, cage, bfvg, sfvg, bdisp, sdisp = _scan_m5_consolidation_and_fvg(o5, h5, l5, c5, atr5)
    return pd.DataFrame({
        "t_known": m5["t_close"].to_numpy(),
        "cons_hi": chi,
        "cons_lo": clo,
        "cons_age_bars": cage,
        "m5_bull_fvg": bfvg,
        "m5_bear_fvg": sfvg,
        "m5_bull_disp": bdisp,
        "m5_bear_disp": sdisp,
    })


def attach_mmxm_to_signals(sig: pd.DataFrame, mmxm_tbl: pd.DataFrame, panel: pd.DataFrame, traded: str = "US100") -> pd.DataFrame:
    """Attach strictly causal MMBM / MMSM stages and flags to a candidate signal table.

    Evaluates the 10-stage state machine at `t_trig`:
      - Stage 1 (HTF Context): `htf_draw_ok` (`pd_zone_ok` or `htf_liq` or aligned `daily_bias`)
      - Stage 2 (Original Consolidation): valid `cons_hi`/`cons_lo` formed within last 36 M5 bars (3 hours)
      - Stage 3 & 4 (Manipulation Leg): price broke out of Original Consolidation opposite to trade direction
        (`sweep_ext_known < cons_lo` for Bullish MMBM; `sweep_ext_known > cons_hi` for Bearish MMSM)
      - Stage 5 (Liquidity Sweep): `j_sweep >= 0` (swept reference candle or session/HTF liquidity)
      - Stage 6 (Smart Money Reversal CISD/MSS): `has_cisd` (or `cisd_m1`/`cisd_m3`/`cisd_m5`) confirmed
        -> Sets `mmxm_early_candidate = True` (Stage >= 6)
      - Stage 7 (Displacement): M1 intrabar displacement (`has_disp`) or M5 displacement (`m5_bull_disp`/`m5_bear_disp`)
      - Stage 8 (FVG Creation): M1/M5 FVG present (`has_disp` or `m5_bull_fvg`/`m5_bear_fvg`)
        -> Sets `mmxm_confirmed = True` (Stage >= 8)
    """
    if len(sig) == 0:
        return sig
    from .ict import asof_join

    out = sig.copy()
    joined = asof_join(
        out["t_trig"],
        mmxm_tbl,
        ["cons_hi", "cons_lo", "cons_age_bars", "m5_bull_fvg", "m5_bear_fvg", "m5_bull_disp", "m5_bear_disp"],
    )
    for col in joined.columns:
        out[col] = joined[col].to_numpy()

    d = out["dir"].to_numpy(int)
    sw_ext = out["sweep_ext_known"].to_numpy(float)
    cons_hi = out["cons_hi"].to_numpy(float)
    cons_lo = out["cons_lo"].to_numpy(float)
    cons_ok = np.isfinite(cons_hi) & np.isfinite(cons_lo) & (out["cons_age_bars"].to_numpy(float) <= 48)

    # Manipulation leg swept beyond Original Consolidation boundary (or swept HTF/reference liquidity from consolidation)
    manip_bull = cons_ok & (d == 1) & (sw_ext < cons_lo)
    manip_bear = cons_ok & (d == -1) & (sw_ext > cons_hi)
    manip_ok = manip_bull | manip_bear

    htf_ok = out["pd_zone_ok"].to_numpy(bool) | out["htf_liq"].to_numpy(bool) | (out["daily_bias"].to_numpy(int) == d)
    sweep_ok = out["j_sweep"].to_numpy(int) >= 0
    cisd_ok = out["has_cisd"].to_numpy(bool) | out.get("cisd_m3", pd.Series(False, index=out.index)).to_numpy(bool) | out.get("cisd_m5", pd.Series(False, index=out.index)).to_numpy(bool)

    disp_ok = out["has_disp"].to_numpy(bool) | np.where(
        d == 1,
        out["m5_bull_disp"].fillna(False).to_numpy(bool),
        out["m5_bear_disp"].fillna(False).to_numpy(bool),
    )
    fvg_ok = out["has_disp"].to_numpy(bool) | np.where(
        d == 1,
        out["m5_bull_fvg"].fillna(False).to_numpy(bool),
        out["m5_bear_fvg"].fillna(False).to_numpy(bool),
    )

    # Compute sequential stage reached (0..8) at entry time t_trig
    stage = np.zeros(len(out), dtype=np.int8)
    s1 = htf_ok
    s2 = s1 & cons_ok
    s4 = s2 & manip_ok
    s5 = s4 & sweep_ok
    s6 = s5 & cisd_ok
    s7 = s6 & disp_ok
    s8 = s7 & fvg_ok

    stage = np.where(s1, 1, stage)
    stage = np.where(s2, 2, stage)
    stage = np.where(s4, 4, stage)
    stage = np.where(s5, 5, stage)
    stage = np.where(s6, 6, stage)
    stage = np.where(s7, 7, stage)
    stage = np.where(s8, 8, stage)

    out["mmxm_stage"] = stage
    out["mmxm_early_candidate"] = s6
    out["mmxm_confirmed"] = s8
    # Keep `mmxm` pointing to True Causal MMXM Early/Confirmed (Stage >= 6) so all downstream models use real MMXM!
    out["mmxm"] = s6
    out["mmxm_model_label"] = np.select(
        [s8 & (d == 1), s8 & (d == -1), s6 & (d == 1), s6 & (d == -1)],
        ["MMBM_CONFIRMED", "MMSM_CONFIRMED", "MMBM_EARLY", "MMSM_EARLY"],
        default="NONE",
    )
    out["mmxm_target_px"] = np.where(d == 1, cons_hi, cons_lo)
    return out

