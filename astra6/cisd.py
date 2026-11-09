"""Phase 5.2 — True Independent Multi-Timeframe CISD Engine (M1, M3, M5, M15).

Computes Change in State of Delivery (CISD) on each timeframe's actual resampled
candle series (`M1`, `M3`, `M5`, `M15`), never as a price-lag approximation on M1.

For every timeframe candle stream:
  1. Tracks the delivery candle sequence into each local high (for bearish CISD)
     or local low (for bullish CISD):
       - `delivery_start_idx`: first candle of the consecutive up-close (`c > o`)
         sequence delivering into the high (or down-close `c < o` into the low).
       - `ref_open`: opening price `o[delivery_start_idx]` of that delivery sequence.
       - `extreme_px`: highest high (bearish) or lowest low (bullish) of the sequence.
  2. Confirmation:
       - Variant `v1` (Standard ICT CISD): first candle whose close crosses beyond
         `ref_open` (`c < ref_open` for bearish, `c > ref_open` for bullish).
       - Variant `v2` (Displacement-Confirmed CISD): allows 1 small pause candle in
         the delivery sequence and requires the breaking candle to close beyond
         `ref_open` with an opposing body larger than `0.35 * ATR`.
  3. Causality:
       - A CISD is known at the confirming candle's availability timestamp.
         Its bar-index projection cannot precede that timestamp.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from numba import njit

from .bars import minute_confirmation_index, resample
from .ict import atr_wilder


@njit(cache=True)
def _scan_tf_cisd(o, h, l, c, atr, allow_pause: bool, req_disp: bool):
    """Scan a single timeframe candle array and emit all bearish (dir=-1) and
    bullish (dir=+1) CISD confirmation events on that timeframe."""
    n = o.shape[0]
    # Preallocate max possible events (2 * n)
    ev_dir = np.empty(2 * n, np.int8)
    ev_deliv_i = np.empty(2 * n, np.int64)
    ev_ext_i = np.empty(2 * n, np.int64)
    ev_conf_i = np.empty(2 * n, np.int64)
    ev_inv_i = np.full(2 * n, -1, np.int64)
    ev_ref_open = np.empty(2 * n, np.float64)
    ev_ext_px = np.empty(2 * n, np.float64)
    ev_break_c = np.empty(2 * n, np.float64)
    cnt = 0

    # --- Bearish CISD state tracking (up-close delivery into local high, broken down) ---
    in_up = False
    deliv_start = 0
    ext_idx = 0
    ext_hi = -1e18
    ref_op = np.nan
    pause_used = False

    for i in range(1, n):
        is_up = c[i] > o[i]
        if is_up:
            if not in_up:
                in_up = True
                deliv_start = i
                ref_op = o[i]
                ext_hi = h[i]
                ext_idx = i
                pause_used = False
            else:
                if h[i] >= ext_hi:
                    ext_hi = h[i]
                    ext_idx = i
        else:
            if in_up:
                if h[i] > ext_hi:
                    ext_hi = h[i]
                    ext_idx = i
                # Check if this candle confirms a bearish CISD below ref_op
                disp_ok = (not req_disp) or ((o[i] - c[i]) >= 0.35 * atr[i])
                if c[i] < ref_op and c[i] < o[i] and disp_ok:
                    # Find invalidation index (first future candle exceeding ext_hi within 20 bars)
                    inv = -1
                    for k in range(i + 1, min(n, i + 25)):
                        if h[k] > ext_hi:
                            inv = k
                            break
                    ev_dir[cnt] = -1
                    ev_deliv_i[cnt] = deliv_start
                    ev_ext_i[cnt] = ext_idx
                    ev_conf_i[cnt] = i
                    ev_inv_i[cnt] = inv
                    ev_ref_open[cnt] = ref_op
                    ev_ext_px[cnt] = ext_hi
                    ev_break_c[cnt] = c[i]
                    cnt += 1
                    in_up = False
                elif allow_pause and (not pause_used) and c[i] >= ref_op:
                    pause_used = True
                elif c[i] < ref_op:
                    in_up = False
                else:
                    # Wait up to 4 bars after ext_idx for break below ref_op
                    if i - ext_idx > 4:
                        in_up = False

    # --- Bullish CISD state tracking (down-close delivery into local low, broken up) ---
    in_dn = False
    deliv_start = 0
    ext_idx = 0
    ext_lo = 1e18
    ref_op = np.nan
    pause_used = False

    for i in range(1, n):
        is_dn = c[i] < o[i]
        if is_dn:
            if not in_dn:
                in_dn = True
                deliv_start = i
                ref_op = o[i]
                ext_lo = l[i]
                ext_idx = i
                pause_used = False
            else:
                if l[i] <= ext_lo:
                    ext_lo = l[i]
                    ext_idx = i
        else:
            if in_dn:
                if l[i] < ext_lo:
                    ext_lo = l[i]
                    ext_idx = i
                disp_ok = (not req_disp) or ((c[i] - o[i]) >= 0.35 * atr[i])
                if c[i] > ref_op and c[i] > o[i] and disp_ok:
                    inv = -1
                    for k in range(i + 1, min(n, i + 25)):
                        if l[k] < ext_lo:
                            inv = k
                            break
                    ev_dir[cnt] = 1
                    ev_deliv_i[cnt] = deliv_start
                    ev_ext_i[cnt] = ext_idx
                    ev_conf_i[cnt] = i
                    ev_inv_i[cnt] = inv
                    ev_ref_open[cnt] = ref_op
                    ev_ext_px[cnt] = ext_lo
                    ev_break_c[cnt] = c[i]
                    cnt += 1
                    in_dn = False
                elif allow_pause and (not pause_used) and c[i] <= ref_op:
                    pause_used = True
                elif c[i] > ref_op:
                    in_dn = False
                else:
                    if i - ext_idx > 4:
                        in_dn = False

    return (
        ev_dir[:cnt], ev_deliv_i[:cnt], ev_ext_i[:cnt], ev_conf_i[:cnt],
        ev_inv_i[:cnt], ev_ref_open[:cnt], ev_ext_px[:cnt], ev_break_c[:cnt],
    )


def extract_tf_cisd_events(
    panel: pd.DataFrame,
    traded: str = "US100",
    tf: str = "M1",
    variant: str = "v1",
    *,
    require_full: bool = False,
) -> pd.DataFrame:
    """Build true candle series for `tf` (`M1`, `M3`, `M5`, `M15`) and detect CISD events."""
    idx = panel.index
    bars = resample(panel, traded, tf, "cal")
    bars = bars[bars["is_complete" if require_full else "is_closed"]].reset_index(drop=True)

    o = bars["o"].to_numpy(float)
    h = bars["h"].to_numpy(float)
    l = bars["l"].to_numpy(float)
    c = bars["c"].to_numpy(float)
    atr = atr_wilder(h, l, c, 14)

    allow_pause = variant == "v2"
    req_disp = variant == "v2"
    dr, di, ei, ci, ii, rop, epx, bc = _scan_tf_cisd(o, h, l, c, atr, allow_pause, req_disp)

    t_open = bars["t_open"].to_numpy()
    availability = bars["available_at"].to_numpy()
    t_conf = availability[ci]
    j_m1_conf = minute_confirmation_index(idx, t_conf)
    j_m1_deliv = np.clip(idx.searchsorted(t_open[di], side="left"), 0, len(idx) - 1)
    j_m1_ext = np.clip(idx.searchsorted(t_open[ei], side="left"), 0, len(idx) - 1)
    j_m1_inv = np.full(len(ci), -1, dtype=np.int64)
    has_inv = ii >= 0
    t_invalidated = pd.Series(pd.NaT, index=range(len(ci)), dtype="datetime64[us, UTC]")
    if has_inv.any():
        j_m1_inv[has_inv] = minute_confirmation_index(idx, availability[ii[has_inv]])
        t_invalidated.loc[has_inv] = availability[ii[has_inv]]

    df = pd.DataFrame({
        "cisd_tf": tf,
        "variant": variant,
        "dir": dr,
        "tf_deliv_idx": di,
        "tf_ext_idx": ei,
        "tf_conf_idx": ci,
        "j_deliv_m1": j_m1_deliv,
        "j_ext_m1": j_m1_ext,
        "j_conf_m1": j_m1_conf,
        "j_inv_m1": j_m1_inv,
        "ref_open": rop,
        "extreme_px": epx,
        "break_close": bc,
        "t_deliv_open": t_open[di],
        "t_confirm": t_conf,
        "available_at": t_conf,
        "invalidated_at": t_invalidated,
        "source_instrument": traded,
        "data_coverage_status": bars["data_coverage_status"].to_numpy()[ci],
    })
    return df.sort_values("j_conf_m1").reset_index(drop=True)


@njit(cache=True)
def _match_post_sweep_cisd_numba(
    jsw: np.ndarray,
    sd: np.ndarray,
    jc: np.ndarray,
    ji: np.ndarray,
    dr: np.ndarray,
    ro: np.ndarray,
    epx: np.ndarray,
    max_wait_m1: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Match each valid liquidity sweep (`jsw[i] >= 0`) with the first subsequent CISD confirmation
    on timeframe `tf` (`jc[k] >= jsw[i]` and `jc[k] <= jsw[i] + max_wait_m1`) in direction `sd[i]`.

    If `jsw[i] < 0` (missing sweep event), returns `j_post = -1` and `delay_min = np.nan` (P0.6).
    """
    n = jsw.shape[0]
    m = jc.shape[0]
    j_post = np.full(n, -1, np.int64)
    delay_min = np.full(n, np.nan, np.float64)
    ref_lvl = np.full(n, np.nan, np.float64)
    ext_lvl = np.full(n, np.nan, np.float64)
    if m == 0:
        return j_post, delay_min, ref_lvl, ext_lvl

    for i in range(n):
        sw_i = jsw[i]
        if sw_i < 0:
            continue
        d_i = sd[i]
        # Binary search first CISD with jc[k] >= sw_i
        lo_k = 0
        hi_k = m
        while lo_k < hi_k:
            mid = (lo_k + hi_k) // 2
            if jc[mid] < sw_i:
                lo_k = mid + 1
            else:
                hi_k = mid
        max_j = sw_i + max_wait_m1
        for k in range(lo_k, min(m, lo_k + 64)):
            if jc[k] > max_j:
                break
            if dr[k] == d_i:
                # Must not already be invalidated at the moment of confirmation
                if ji[k] < 0 or ji[k] > jc[k]:
                    j_post[i] = jc[k]
                    delay_min[i] = float(jc[k] - sw_i)
                    ref_lvl[i] = ro[k]
                    ext_lvl[i] = epx[k]
                    break
    return j_post, delay_min, ref_lvl, ext_lvl


def attach_true_cisd_to_signals(
    sig: pd.DataFrame,
    cisd_tables: dict[str, pd.DataFrame],
    max_lookback_m1: int = 30,
) -> pd.DataFrame:
    """Attach true independent M1, M3, M5, M15, M30, H1, H4 CISD flags and confirmation indices to signals.

    Computes BOTH:
      1. As-of-trigger context CISD (`cisd_<tf>`, `j_cisd_<tf>`) strictly known `<= j_trig`
      2. Post-sweep executable CISD (`j_post_cisd_<tf>`, `cisd_delay_min_<tf>`, `post_cisd_sl_<tf>`)
         matching the actual liquidity sweep confirmation `j_sweep` (`>= 0`) with the first subsequent
         timeframe CISD confirmation `>= j_sweep`, keeping `j_sweep == -1` distinct (P0.4 & P0.6).
    """
    if len(sig) == 0:
        return sig
    out = sig.copy()
    jt = out["j_trig"].to_numpy(np.int64)
    jsw_exact = out["j_sweep"].to_numpy(np.int64)
    jsw_raw = np.maximum(jsw_exact, out["j_open"].to_numpy(np.int64) - max_lookback_m1)
    sd = out["dir"].to_numpy(np.int8)
    out["has_valid_liquidity_sweep"] = jsw_exact >= 0

    tf_max_age = {
        "M1": 30,
        "M3": 45,
        "M5": 60,
        "M15": 120,
        "M30": 240,
        "H1": 360,
        "H4": 960,
    }
    tf_max_wait_after_sweep = {
        "M1": 20,
        "M3": 30,
        "M5": 45,
        "M15": 90,
        "M30": 150,
        "H1": 240,
        "H4": 480,
    }

    for tf_key, tbl in cisd_tables.items():
        tk_lo = tf_key.lower()
        col_flag = f"cisd_{tk_lo}"
        col_j = f"j_cisd_{tk_lo}"
        col_lvl = f"lvl_cisd_{tk_lo}"
        col_opp = f"cisd_opp_{tk_lo}"
        col_exp = f"cisd_exp_{tk_lo}"
        col_j_post = f"j_post_cisd_{tk_lo}"
        col_delay = f"cisd_delay_min_{tk_lo}"
        col_post_sl = f"post_cisd_ext_{tk_lo}"
        n = len(out)
        flags = np.zeros(n, dtype=bool)
        opp_flags = np.zeros(n, dtype=bool)
        exp_flags = np.zeros(n, dtype=bool)
        j_arr = np.full(n, -1, dtype=np.int64)
        lvl_arr = np.full(n, np.nan, dtype=np.float64)
        max_age = tf_max_age.get(tf_key.upper(), 60)
        max_wait = tf_max_wait_after_sweep.get(tf_key.upper(), 60)
        if len(tbl) > 0:
            jc = tbl["j_conf_m1"].to_numpy(np.int64)
            ji = tbl["j_inv_m1"].to_numpy(np.int64)
            dr = tbl["dir"].to_numpy(np.int8)
            ro = tbl["ref_open"].to_numpy(np.float64)
            epx = tbl["extreme_px"].to_numpy(np.float64)
            for i in range(n):
                min_j = min(jsw_raw[i] - 5, jt[i] - max_age)
                k = np.searchsorted(jc, jt[i], side="right") - 1
                steps = 0
                while k >= 0 and steps < 80:
                    if jc[k] < min_j:
                        break
                    if dr[k] == sd[i]:
                        if ji[k] < 0 or ji[k] > jt[i]:
                            if not flags[i]:
                                flags[i] = True
                                j_arr[i] = jc[k]
                                lvl_arr[i] = ro[k]
                        else:
                            exp_flags[i] = True
                    else:
                        if ji[k] < 0 or ji[k] > jt[i]:
                            opp_flags[i] = True
                    if flags[i] and opp_flags[i]:
                        break
                    k -= 1
                    steps += 1

            j_post, delay_min, _, ext_lvl = _match_post_sweep_cisd_numba(
                jsw_exact, sd, jc, ji, dr, ro, epx, max_wait
            )
        else:
            j_post = np.full(n, -1, dtype=np.int64)
            delay_min = np.full(n, np.nan, dtype=np.float64)
            ext_lvl = np.full(n, np.nan, dtype=np.float64)

        out[col_flag] = flags
        out[col_j] = j_arr
        out[col_lvl] = lvl_arr
        out[col_opp] = opp_flags
        out[col_exp] = exp_flags
        out[col_j_post] = j_post
        out[col_delay] = delay_min
        out[col_post_sl] = ext_lvl

    # Combine M1 scan_crt intrabar CISD with standalone M1 CISD
    out["cisd_m1"] = out["has_cisd"] | out.get("cisd_m1", False)
    # If intrabar M1 `j_cisd` from scan_crt occurred at or after `j_sweep >= 0` and earlier than `j_post_cisd_m1`, use it
    if "j_cisd" in out.columns and "j_post_cisd_m1" in out.columns:
        jc_crt = out["j_cisd"].to_numpy(np.int64)
        jp_m1 = out["j_post_cisd_m1"].to_numpy(np.int64)
        valid_crt_c = (jsw_exact >= 0) & (jc_crt >= jsw_exact) & ((jp_m1 < 0) | (jc_crt < jp_m1))
        jp_m1 = np.where(valid_crt_c, jc_crt, jp_m1)
        out["j_post_cisd_m1"] = jp_m1
        out["cisd_delay_min_m1"] = np.where(
            (jsw_exact >= 0) & (jp_m1 >= jsw_exact),
            (jp_m1 - jsw_exact).astype(np.float64),
            np.nan,
        )
    return out

