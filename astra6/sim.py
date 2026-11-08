"""Phase 1.2 & Phase 8 — Realistic Event-Driven Trade Simulator (Next-Executable-Quote Fill).

Strict Execution Rules (v2.0):
------------------------------
* A signal confirmed at the close of bar `j_trig` (`t_signal_known = t_open[j_trig] + bar_duration`)
  CANNOT be filled at `close[j_trig]`.
* Order is submitted at `t_order_submit = t_signal_known` and filled at the **next executable
  bar open** `j_fill = j_trig + 1` (`t_fill = t_open[j_fill]`):
    - Long entry fill : `ask_o[j_fill] + slip` (exit on `bid - slip`, SL/TP checked vs `bid`)
    - Short entry fill: `bid_o[j_fill] - slip` (exit on `ask + slip`, SL/TP checked vs `ask`)
* Intrabar SL/TP checking starts on bar `j_fill` itself (immediately after the open fill).
* Same-bar SL & TP touch ambiguity is resolved **pessimistically** (SL wins, `ambig=True`).
* Positions **never** auto-close at quarter boundaries unless `exit_model == EX_TIME`.
* Trailing stops use only swings whose `t_known <= t_bar_close`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from numba import njit

# exit_model codes
EX_FIXED = 0
EX_BE1 = 1
EX_BE2 = 2
EX_SWING = 3
EX_PARTIAL = 4
EX_TIME = 5
EX_NO_TP_SWING = 6
EX_STRUCT_TRAIL = 7


@njit(cache=True)
def sim_batch(
    bid_o, bid_h, bid_l, bid_c,
    ask_o, ask_h, ask_l, ask_c,
    j_trig, direction, sl0, tp0,
    exit_model, max_hold, slip, min_risk,
    sw_j_known, sw_price, sw_is_high,
):
    """Simulate trades triggered at close of `j_trig` and filled at open of `j_fill = j_trig + 1`."""
    nt = j_trig.shape[0]
    n = bid_c.shape[0]
    m_sw = sw_j_known.shape[0]
    r_out = np.full(nt, np.nan)
    mfe = np.full(nt, np.nan)
    mae = np.full(nt, np.nan)
    hold = np.zeros(nt, np.int64)
    j_fill_out = np.full(nt, -1, np.int64)
    j_exit = np.full(nt, -1, np.int64)
    px_entry = np.full(nt, np.nan)
    px_exit = np.full(nt, np.nan)
    n_mod = np.zeros(nt, np.int64)
    ambig = np.zeros(nt, np.bool_)
    reason = np.zeros(nt, np.int8)  # 1=SL, 2=TP, 3=trail_SL, 4=BE, 5=time

    for t in range(nt):
        jt = j_trig[t]
        jf = jt + 1  # Next executable bar after signal confirmation at close of jt
        if jt < 0 or jf >= n - 1:
            continue
        d = direction[t]  # +1 long, -1 short
        ep = (ask_o[jf] + slip) if d == 1 else (bid_o[jf] - slip)
        sl = sl0[t]
        risk = (ep - sl) if d == 1 else (sl - ep)
        if not (risk >= min_risk):
            continue
        tp = tp0[t]
        use_tp = exit_model != EX_NO_TP_SWING and np.isfinite(tp)
        # Re-scale TP relative to actual executable fill ep when using fixed R:R
        j_fill_out[t] = jf
        px_entry[t] = ep
        sl_cur = sl
        be_armed = False
        half_taken = False
        realized_half = 0.0
        best_fav = 0.0
        worst_adv = 0.0
        end = min(jf + max_hold, n - 1)

        # Binary search starting cursor in swing table (swings known <= jt)
        lo, hi = 0, m_sw
        while lo < hi:
            mid = (lo + hi) // 2
            if sw_j_known[mid] <= jt:
                lo = mid + 1
            else:
                hi = mid
        sw_cur = lo

        out_j = end
        out_px = (bid_c[end] - slip) if d == 1 else (ask_c[end] + slip)
        out_reason = 5

        # Walk from jf (the fill bar itself, after its open!) through end
        for j in range(jf, end + 1):
            if d == 1:
                fav = (bid_h[j] - ep) / risk
                adv = (ep - bid_l[j]) / risk
                sl_hit = bid_l[j] <= sl_cur
                tp_hit = use_tp and (bid_h[j] >= tp)
            else:
                fav = (ep - ask_l[j]) / risk
                adv = (ask_h[j] - ep) / risk
                sl_hit = ask_h[j] >= sl_cur
                tp_hit = use_tp and (ask_l[j] <= tp)

            if fav > best_fav:
                best_fav = fav
            if adv > worst_adv:
                worst_adv = adv

            if sl_hit and tp_hit:
                ambig[t] = True
                tp_hit = False  # Pessimistic rule: SL wins on same-bar touch

            if sl_hit:
                out_j = j
                out_px = (sl_cur - slip) if d == 1 else (sl_cur + slip)
                out_reason = 4 if be_armed and abs(sl_cur - ep) < 1e-9 else (3 if n_mod[t] > 0 else 1)
                break

            if exit_model == EX_PARTIAL and (not half_taken) and fav >= 1.0:
                half_taken = True
                realized_half = 1.0 - (2 * slip / risk)
                sl_cur = ep
                be_armed = True
                n_mod[t] += 1

            if tp_hit:
                out_j = j
                out_px = (tp - slip) if d == 1 else (tp + slip)
                out_reason = 2
                break

            # End-of-bar stop updates (effective from j+1 onwards)
            if exit_model == EX_BE1 and (not be_armed) and fav >= 1.0:
                sl_cur = ep
                be_armed = True
                n_mod[t] += 1
            elif exit_model == EX_BE2 and (not be_armed) and fav >= 2.0:
                sl_cur = ep
                be_armed = True
                n_mod[t] += 1

            if exit_model in (EX_SWING, EX_NO_TP_SWING, EX_STRUCT_TRAIL):
                while sw_cur < m_sw and sw_j_known[sw_cur] <= j:
                    if d == 1 and (not sw_is_high[sw_cur]):
                        cand = sw_price[sw_cur]
                        if cand > sl_cur and cand < bid_c[j]:
                            sl_cur = cand
                            n_mod[t] += 1
                    elif d == -1 and sw_is_high[sw_cur]:
                        cand = sw_price[sw_cur]
                        if cand < sl_cur and cand > ask_c[j]:
                            sl_cur = cand
                            n_mod[t] += 1
                    sw_cur += 1

        j_exit[t] = out_j
        px_exit[t] = out_px
        hold[t] = out_j - jf + 1
        reason[t] = out_reason
        r_leg = ((out_px - ep) if d == 1 else (ep - out_px)) / risk
        r_out[t] = 0.5 * realized_half + 0.5 * r_leg if half_taken else r_leg
        mfe[t] = best_fav
        mae[t] = worst_adv

    return r_out, mfe, mae, hold, j_exit, px_entry, px_exit, n_mod, ambig, reason


@njit(cache=True)
def filter_non_overlapping(j_entry, j_exit):
    """Keep trade i iff j_entry[i] > j_exit of the previously kept trade (same stream)."""
    keep = np.zeros(j_entry.shape[0], np.bool_)
    free_at = -1
    for i in range(j_entry.shape[0]):
        if j_entry[i] < 0 or j_exit[i] < 0:
            continue
        if j_entry[i] > free_at:
            keep[i] = True
            free_at = j_exit[i]
    return keep
