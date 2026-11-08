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
       - An `M3`, `M5`, or `M15` CISD is ONLY known at `t_close` of that timeframe's
         confirming candle (`j_m1_known = idx.searchsorted(t_close, side="left") - 1`).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from numba import njit

from .bars import resample
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
) -> pd.DataFrame:
    """Build true candle series for `tf` (`M1`, `M3`, `M5`, `M15`) and detect CISD events."""
    idx = panel.index
    if tf == "M1":
        bars = pd.DataFrame({
            "o": panel[f"{traded}_o"].to_numpy(float),
            "h": panel[f"{traded}_h"].to_numpy(float),
            "l": panel[f"{traded}_l"].to_numpy(float),
            "c": panel[f"{traded}_c"].to_numpy(float),
            "t_open": idx,
            "t_close": idx + pd.Timedelta(minutes=1),
            "complete": True,
        })
    else:
        bars = resample(panel, traded, tf, "cal")
        bars = bars[bars["complete"]].reset_index(drop=True)

    o = bars["o"].to_numpy(float)
    h = bars["h"].to_numpy(float)
    l = bars["l"].to_numpy(float)
    c = bars["c"].to_numpy(float)
    atr = atr_wilder(h, l, c, 14)

    allow_pause = variant == "v2"
    req_disp = variant == "v2"
    dr, di, ei, ci, ii, rop, epx, bc = _scan_tf_cisd(o, h, l, c, atr, allow_pause, req_disp)

    t_open = bars["t_open"].to_numpy()
    t_close = bars["t_close"].to_numpy()
    t_conf = t_close[ci]
    # Map confirmation timestamp to the M1 bar index whose close equals t_conf
    j_m1_conf = np.clip(idx.searchsorted(t_conf, side="left") - 1, 0, len(idx) - 1)
    j_m1_deliv = np.clip(idx.searchsorted(t_open[di], side="left"), 0, len(idx) - 1)
    j_m1_ext = np.clip(idx.searchsorted(t_open[ei], side="left"), 0, len(idx) - 1)
    j_m1_inv = np.full(len(ci), -1, dtype=np.int64)
    has_inv = ii >= 0
    if has_inv.any():
        j_m1_inv[has_inv] = np.clip(idx.searchsorted(t_close[ii[has_inv]], side="left") - 1, 0, len(idx) - 1)

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
    })
    return df.sort_values("j_conf_m1").reset_index(drop=True)


def attach_true_cisd_to_signals(
    sig: pd.DataFrame,
    cisd_tables: dict[str, pd.DataFrame],
    max_lookback_m1: int = 30,
) -> pd.DataFrame:
    """Attach true independent M1, M3, M5, M15 CISD flags and confirmation indices to signals.

    A CISD on timeframe `tf` is valid for a signal with `(j_sweep, j_trig, dir)` iff:
      - `cisd.dir == sig.dir`
      - `cisd.j_conf_m1 >= sig.j_sweep` (formed at or after the sweep)
      - `cisd.j_conf_m1 <= sig.j_trig + ext_window` (known by trigger or confirmation window)
      - Not invalidated by `j_trig` (`j_inv_m1 < 0` or `j_inv_m1 > j_trig`)
    """
    if len(sig) == 0:
        return sig
    out = sig.copy()
    jt = out["j_trig"].to_numpy(np.int64)
    jsw = np.maximum(out["j_sweep"].to_numpy(np.int64), out["j_open"].to_numpy(np.int64) - max_lookback_m1)
    sd = out["dir"].to_numpy(np.int8)

    for tf_key, tbl in cisd_tables.items():
        col_flag = f"cisd_{tf_key.lower()}"
        col_j = f"j_cisd_{tf_key.lower()}"
        col_lvl = f"lvl_cisd_{tf_key.lower()}"
        n = len(out)
        flags = np.zeros(n, dtype=bool)
        j_arr = np.full(n, -1, dtype=np.int64)
        lvl_arr = np.full(n, np.nan, dtype=np.float64)
        if len(tbl) > 0:
            jc = tbl["j_conf_m1"].to_numpy(np.int64)
            ji = tbl["j_inv_m1"].to_numpy(np.int64)
            dr = tbl["dir"].to_numpy(np.int8)
            ro = tbl["ref_open"].to_numpy(np.float64)
            for i in range(n):
                # Latest CISD confirmed at or before jt[i] and after jsw[i] - 5
                k = np.searchsorted(jc, jt[i], side="right") - 1
                steps = 0
                while k >= 0 and steps < 60:
                    if jc[k] < jsw[i] - 5:
                        break
                    if dr[k] == sd[i] and (ji[k] < 0 or ji[k] > jt[i]):
                        flags[i] = True
                        j_arr[i] = jc[k]
                        lvl_arr[i] = ro[k]
                        break
                    k -= 1
                    steps += 1
        out[col_flag] = flags
        out[col_j] = j_arr
        out[col_lvl] = lvl_arr

    # Combine M1 scan_crt intrabar CISD with standalone M1 CISD
    out["cisd_m1"] = out["has_cisd"] | out.get("cisd_m1", False)
    return out

