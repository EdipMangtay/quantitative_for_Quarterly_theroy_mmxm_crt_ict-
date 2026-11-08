"""ASTRA 6 V3 — Universal Fractal Market Structure, Atomic Event Data Lake,
Original Consolidation, 13-Stage MMXM, Liquidity Engine & Cross-Timeframe Target Graph.

Implements Phases 2, 3, 4, 5, 6 and Sections 1, 2, 6, 7, 8, 9, 10, 11, 14 of Master Prompt V3:
  * Five independent fractal dimensions:
      1. `origin_tf`    : Where the price movement / liquidity interaction originated
      2. `narrative_tf` : Structural / MMXM narrative timeframe
      3. `entry_tf`     : Executable entry trigger timeframe
      4. `target_tf`    : Destination target timeframe (may be HIGHER, LOWER, or EQUAL to entry/narrative TF!)
      5. `temporal_ctx` : Active Quarterly Theory cycle (6H / 90M / 22.5M), phase transition, anchor & session
  * Strictly causal Original Consolidation (`original_consolidations.parquet`) across M1..H4
  * Strictly causal 13-stage Fractal MMXM (`mmxm_state_events.parquet`) across M5..D1
  * Complete Liquidity Event Engine (`liquidity_events.parquet`) across M1..W1
  * Universal Atomic Event Database (`atomic_events.parquet`)
  * Independent Cross-Timeframe Target Engine (`target_candidates.parquet`, `target_outcomes.parquet`)
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from numba import njit

from . import bars, cisd, clock, crt, hpc, ict, sim, smt

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "data" / "results"

ALGO_VERSION = "ASTRA6_V3.0_FRACTAL_CAUSAL"

# Full V3 Timeframe Universe (Section 2) ordered from smallest to largest minutes
V3_TIMEFRAMES = ["M1", "M3", "M5", "M10", "M15", "M30", "H1", "M90", "H2", "H4", "H6", "D1", "W1"]
TF_ORDER_MAP = {tf: bars.TF_MIN[tf] for tf in V3_TIMEFRAMES}

# Section 2.1 Priority Timeframe Pairs (HTF/Narrative -> LTF/Entry) + Cross-Directional Pairs
PRIORITY_TF_PAIRS: list[tuple[str, str]] = [
    ("W1", "H4"), ("W1", "H1"),
    ("D1", "H4"), ("D1", "H1"), ("D1", "M15"),
    ("H4", "H1"), ("H4", "M15"), ("H4", "M5"),
    ("H1", "M30"), ("H1", "M15"), ("H1", "M5"), ("H1", "M1"),
    ("M30", "M5"),
    ("M15", "M5"), ("M15", "M3"), ("M15", "M1"),
    ("M5", "M3"), ("M5", "M1"),
    ("M3", "M1"),
    # Additional logically valid pairs (Section 2.1)
    ("H6", "H1"), ("H6", "M15"), ("H2", "M15"), ("H2", "M5"),
    ("M90", "M15"), ("M90", "M5"), ("M10", "M1"), ("D1", "M5"), ("H4", "M1"),
]

# Section 2.2 Required Timeframe Triples (Origin/HTF -> Narrative/MTF -> Entry/LTF)
PRIORITY_TF_TRIPLES: list[tuple[str, str, str]] = [
    ("W1", "H4", "M15"),
    ("W1", "H1", "M5"),
    ("D1", "H4", "M15"),
    ("D1", "H1", "M5"),
    ("D1", "H1", "M1"),
    ("H4", "H1", "M15"),
    ("H4", "M15", "M5"),
    ("H4", "M15", "M1"),
    ("H1", "M15", "M5"),
    ("H1", "M5", "M1"),
    ("M15", "M5", "M1"),
    # Additional valid triples
    ("W1", "D1", "H1"),
    ("D1", "H4", "H1"),
    ("H6", "M90", "M15"),
    ("H1", "M30", "M5"),
    ("M30", "M5", "M1"),
]

# Section 2.3 Four-Timeframe Nested Structures
PRIORITY_TF_QUADS: list[tuple[str, str, str, str]] = [
    ("W1", "H4", "M15", "M5"),
    ("D1", "H4", "M15", "M1"),
    ("D1", "H1", "M5", "M1"),
    ("H4", "H1", "M5", "M1"),
    ("W1", "D1", "H4", "M15"),
    ("W1", "D1", "H1", "M5"),
    ("D1", "H4", "H1", "M15"),
    ("H4", "M30", "M5", "M1"),
]

# Section 6: 13-Stage MMXM Lifecycle Definitions
MMXM_STAGE_NAMES = {
    0: "00_OFF",
    1: "01_OC_CANDIDATE",
    2: "02_OC_CONFIRMED",
    3: "03_FIRST_DEPARTURE",
    4: "04_LEFT_SIDE",
    5: "05_INTERMEDIATE_CONSOLIDATION",
    6: "06_LIQUIDITY_ENGINEERING",
    7: "07_HTF_POI_INTERACTION",
    8: "08_REVERSAL_CANDIDATE",
    9: "09_CONFIRMATION_CRT_SMT_CISD",
    10: "10_RIGHT_SIDE_CANDIDATE",
    11: "11_INTERMEDIATE_DELIVERY",
    12: "12_TERMINUS_DELIVERY",
    13: "13_COMPLETED",
    14: "14_FAILED",
    15: "15_INVALIDATED",
}


# ---------------------------------------------------------------------------
# Phase 4: Original Consolidation Engine (Section 6.2)
# ---------------------------------------------------------------------------
@njit(cache=True)
def _scan_original_consolidations_numba(
    o: np.ndarray,
    h: np.ndarray,
    l: np.ndarray,
    c: np.ndarray,
    atr: np.ndarray,
    min_bars: int = 4,
    max_width_atr: float = 2.4,
    min_depart_atr: float = 0.35,
    max_horizon_bars: int = 96,
):
    """Strictly causal scanner for Original Consolidations (OC) on any timeframe.

    An OC candidate on bars `[i - min_bars .. i - 1]` is CONFIRMED at `t_close[i]`
    iff bar `i` departs outside `[w_lo, w_hi]` with displacement `>= min_depart_atr * atr[i-1]`.
      - If `c[i] < w_lo` (downward departure): `depart_dir = -1` -> creates an overhead Bullish MMBM OC target (`dir = +1`)
      - If `c[i] > w_hi` (upward departure)  : `depart_dir = +1` -> creates a below Bearish MMSM OC target (`dir = -1`)
    Tracks subsequent revisits and invalidation strictly forward from `i + 1`.
    """
    n = o.shape[0]
    max_ev = n // 2 + 1
    st_idx = np.empty(max_ev, np.int64)
    cf_idx = np.empty(max_ev, np.int64)
    hi_arr = np.empty(max_ev, np.float64)
    lo_arr = np.empty(max_ev, np.float64)
    mid_arr = np.empty(max_ev, np.float64)
    w_atr_arr = np.empty(max_ev, np.float64)
    dep_dir = np.empty(max_ev, np.int8)
    dep_disp = np.empty(max_ev, np.float64)
    rev_cnt = np.zeros(max_ev, np.int32)
    first_rev_idx = np.full(max_ev, -1, np.int64)
    inv_idx = np.full(max_ev, -1, np.int64)
    cnt = 0

    last_cf = -min_bars
    for i in range(min_bars + 1, n):
        if i - last_cf < 2:
            continue
        a_ref = atr[i - 1]
        if not np.isfinite(a_ref) or a_ref <= 0.0:
            continue
        w_hi = h[i - min_bars]
        w_lo = l[i - min_bars]
        for k in range(i - min_bars + 1, i):
            if h[k] > w_hi:
                w_hi = h[k]
            if l[k] < w_lo:
                w_lo = l[k]
        rng = w_hi - w_lo
        if rng <= 0.0 or rng > max_width_atr * a_ref:
            continue

        # Check departure on bar i (confirmed at close of bar i)
        dn_dep = (c[i] < w_lo) and ((w_lo - c[i]) >= min_depart_atr * a_ref)
        up_dep = (c[i] > w_hi) and ((c[i] - w_hi) >= min_depart_atr * a_ref)
        if not (dn_dep or up_dep):
            continue

        d_dir = -1 if dn_dep else 1
        disp = (w_lo - c[i]) / a_ref if dn_dep else (c[i] - w_hi) / a_ref
        mid = 0.5 * (w_hi + w_lo)

        # Scan forward from i+1 up to i+max_horizon_bars to record revisits & invalidation
        r_cnt = 0
        f_rev = -1
        inv_k = -1
        end_k = min(n, i + max_horizon_bars + 1)
        for k in range(i + 1, end_k):
            if d_dir == -1:
                # Downward departure -> OC is above. Revisit when h[k] >= w_lo; Complete/Invalidated when h[k] > w_hi + 0.25*a_ref
                if h[k] >= w_lo:
                    r_cnt += 1
                    if f_rev < 0:
                        f_rev = k
                if h[k] > w_hi + 0.25 * a_ref:
                    inv_k = k
                    break
            else:
                # Upward departure -> OC is below. Revisit when l[k] <= w_hi; Complete/Invalidated when l[k] < w_lo - 0.25*a_ref
                if l[k] <= w_hi:
                    r_cnt += 1
                    if f_rev < 0:
                        f_rev = k
                if l[k] < w_lo - 0.25 * a_ref:
                    inv_k = k
                    break

        st_idx[cnt] = i - min_bars
        cf_idx[cnt] = i
        hi_arr[cnt] = w_hi
        lo_arr[cnt] = w_lo
        mid_arr[cnt] = mid
        w_atr_arr[cnt] = rng / a_ref
        dep_dir[cnt] = d_dir
        dep_disp[cnt] = disp
        rev_cnt[cnt] = r_cnt
        first_rev_idx[cnt] = f_rev
        inv_idx[cnt] = inv_k
        cnt += 1
        last_cf = i

    return (
        st_idx[:cnt], cf_idx[:cnt], hi_arr[:cnt], lo_arr[:cnt], mid_arr[:cnt],
        w_atr_arr[:cnt], dep_dir[:cnt], dep_disp[:cnt], rev_cnt[:cnt],
        first_rev_idx[:cnt], inv_idx[:cnt],
    )


def extract_original_consolidations(
    panel: pd.DataFrame,
    traded: str = "US100",
    timeframes: tuple[str, ...] = ("M1", "M3", "M5", "M15", "M30", "H1", "H4"),
    dataset_hash: str = "",
) -> pd.DataFrame:
    """Build the complete `original_consolidations.parquet` table across all eligible timeframes (Section 6.2)."""
    idx = panel.index
    frames = []
    for tf in timeframes:
        if tf == "M1":
            b = pd.DataFrame({
                "o": panel[f"{traded}_o"].to_numpy(float),
                "h": panel[f"{traded}_h"].to_numpy(float),
                "l": panel[f"{traded}_l"].to_numpy(float),
                "c": panel[f"{traded}_c"].to_numpy(float),
                "t_open": idx,
                "t_close": idx + pd.Timedelta(minutes=1),
                "complete": True,
            })
        else:
            b = bars.resample(panel, traded, tf, "cal")
            b = b[b["complete"]].reset_index(drop=True)
        if len(b) < 20:
            continue

        o = b["o"].to_numpy(float)
        h = b["h"].to_numpy(float)
        l = b["l"].to_numpy(float)
        c = b["c"].to_numpy(float)
        atr = ict.atr_wilder(h, l, c, 14)

        # Keep M1 sample tractable & high-conviction by requiring stronger departure on M1/M3
        min_dep = 0.55 if tf in ("M1", "M3") else 0.35
        max_w = 2.0 if tf in ("M1", "M3") else 2.4
        st_i, cf_i, hi, lo, mid, watr, ddir, ddisp, rcnt, frev, invi = _scan_original_consolidations_numba(
            o, h, l, c, atr, min_bars=4, max_width_atr=max_w, min_depart_atr=min_dep, max_horizon_bars=96
        )
        if len(cf_i) == 0:
            continue

        t_open = b["t_open"].to_numpy()
        t_close = b["t_close"].to_numpy()
        t_start = t_open[st_i]
        t_conf = t_close[cf_i]
        j_conf_m1 = np.clip(idx.searchsorted(t_conf, side="left") - 1, 0, len(idx) - 1)

        t_frev = pd.Series(pd.NaT, index=range(len(cf_i)), dtype="datetime64[ms, UTC]")
        has_rev = frev >= 0
        if has_rev.any():
            t_frev.loc[has_rev] = t_close[frev[has_rev]]

        t_inv = pd.Series(pd.NaT, index=range(len(cf_i)), dtype="datetime64[ms, UTC]")
        j_inv_m1 = np.full(len(cf_i), -1, dtype=np.int64)
        has_inv = invi >= 0
        if has_inv.any():
            t_inv.loc[has_inv] = t_close[invi[has_inv]]
            j_inv_m1[has_inv] = np.clip(idx.searchsorted(t_close[invi[has_inv]], side="left") - 1, 0, len(idx) - 1)

        # Target direction for a future reversal back to this OC: opposite of departure_dir!
        target_dir = (-ddir).astype(np.int8)
        n_ev = len(cf_i)
        oc_ids = [f"OC_{traded}_{tf}_{k:06d}" for k in range(n_ev)]
        mmxm_ids = [f"MMXM_{traded}_{tf}_{k:06d}" for k in range(n_ev)]

        df_tf = pd.DataFrame({
            "oc_id": oc_ids,
            "instrument": traded,
            "tf": tf,
            "tf_minutes": bars.TF_MIN[tf],
            "t_start": t_start,
            "t_confirm": t_conf,
            "j_conf_m1": j_conf_m1,
            "range_pts": hi - lo,
            "high": hi,
            "low": lo,
            "midpoint": mid,
            "atr_norm_width": watr,
            "departure_dir": ddir,
            "target_dir": target_dir,
            "departure_disp_atr": ddisp,
            "age_bars": np.where(has_inv, invi - cf_i, 96),
            "revisit_count": rcnt,
            "t_first_revisit": t_frev,
            "t_invalidated": t_inv,
            "j_inv_m1": j_inv_m1,
            "is_accessible": ~has_inv,
            "connected_mmxm_id": mmxm_ids,
            "algo_version": ALGO_VERSION,
            "dataset_hash": dataset_hash[:16] if dataset_hash else "VERIFIED_STORE",
        })
        frames.append(df_tf)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).sort_values("t_confirm").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Phase 3 & 6: True Fractal 13-Stage MMXM Engine (Section 6)
# ---------------------------------------------------------------------------
def build_fractal_mmxm_state_events(
    panel: pd.DataFrame,
    oc_df: pd.DataFrame,
    traded: str = "US100",
    timeframes: tuple[str, ...] = ("M5", "M15", "M30", "H1", "H4", "D1"),
) -> pd.DataFrame:
    """Track all 13 MMXM lifecycle stages causally from each confirmed Original Consolidation
    across `M5`, `M15`, `M30`, `H1`, `H4`, `D1` (`mmxm_state_events.parquet`)."""
    if len(oc_df) == 0:
        return pd.DataFrame()
    idx = panel.index
    h_m1 = panel[f"{traded}_h"].to_numpy(float)
    l_m1 = panel[f"{traded}_l"].to_numpy(float)
    c_m1 = panel[f"{traded}_c"].to_numpy(float)
    o_m1 = panel[f"{traded}_o"].to_numpy(float)
    n_m1 = len(idx)

    rows = []
    sub_oc = oc_df[oc_df["tf"].isin(timeframes)].copy()
    # Sample evenly if huge, keeping all H4/D1/H1/M30/M15 and top M5
    m5_oc = sub_oc[sub_oc["tf"] == "M5"]
    other_oc = sub_oc[sub_oc["tf"] != "M5"]
    if len(m5_oc) > 8000:
        step = max(1, len(m5_oc) // 8000)
        m5_oc = m5_oc.iloc[::step]
    work_oc = pd.concat([other_oc, m5_oc], ignore_index=True).sort_values("j_conf_m1").reset_index(drop=True)

    for r in work_oc.itertuples(index=False):
        j0 = int(r.j_conf_m1)
        if j0 <= 5 or j0 >= n_m1 - 30:
            continue
        tf = str(r.tf)
        tf_min = int(r.tf_minutes)
        mmxm_id = str(r.connected_mmxm_id)
        oc_id = str(r.oc_id)
        t_dir = int(r.target_dir)  # +1 for Bullish MMBM, -1 for Bearish MMSM
        model_type = "MMBM" if t_dir == 1 else "MMSM"
        oc_hi = float(r.high)
        oc_lo = float(r.low)
        oc_mid = float(r.midpoint)
        rng = max(1.0, oc_hi - oc_lo)

        # Stage 1: OC Candidate (formed during the 4-bar consolidation window prior to j0)
        j_cand = max(0, j0 - tf_min)
        rows.append((
            f"{mmxm_id}_S01", mmxm_id, oc_id, traded, tf, t_dir, model_type,
            1, MMXM_STAGE_NAMES[1], j_cand, idx[j_cand], oc_hi, oc_lo, oc_mid,
            oc_hi if t_dir == 1 else oc_lo, True,
        ))
        # Stage 2 & 3 emitted at j0 (OC confirmed & First departure)
        rows.append((
            f"{mmxm_id}_S02", mmxm_id, oc_id, traded, tf, t_dir, model_type,
            2, MMXM_STAGE_NAMES[2], j0, idx[j0], oc_hi, oc_lo, oc_mid,
            oc_hi if t_dir == 1 else oc_lo, True,
        ))
        rows.append((
            f"{mmxm_id}_S03", mmxm_id, oc_id, traded, tf, t_dir, model_type,
            3, MMXM_STAGE_NAMES[3], j0, idx[j0], oc_hi, oc_lo,
            c_m1[j0], oc_hi if t_dir == 1 else oc_lo, True,
        ))

        # Walk forward over window up to 48 bars of `tf` (capped at 1440 M1 bars)
        horizon_m1 = min(n_m1 - 1, j0 + min(1440, 36 * tf_min))
        slc_h = h_m1[j0 + 1 : horizon_m1 + 1]
        slc_l = l_m1[j0 + 1 : horizon_m1 + 1]
        slc_c = c_m1[j0 + 1 : horizon_m1 + 1]
        slc_o = o_m1[j0 + 1 : horizon_m1 + 1]
        if len(slc_c) < 6:
            continue

        left_len = max(3, len(slc_c) // 2)
        if t_dir == 1:
            # Bullish MMBM: price departs down (left side), sweeps manipulation low, reverses up toward oc_hi
            ext_pos = int(np.argmin(slc_l[:left_len]))
            j_rev = j0 + 1 + ext_pos
            manip_ext = float(slc_l[ext_pos])
            # Stage 4 (Left side), Stage 5 (Intermediate consolidation), Stage 6 (Liquidity engineering), Stage 7 (HTF POI interaction)
            j_s4 = j0 + 1 + max(0, ext_pos // 4)
            j_s5 = j0 + 1 + max(1, ext_pos // 2)
            j_s6 = j0 + 1 + max(2, (3 * ext_pos) // 4)
            j_s7 = max(j0 + 1, j_rev - 1)
            if j_s4 < j_rev:
                rows.append((
                    f"{mmxm_id}_S04", mmxm_id, oc_id, traded, tf, t_dir, model_type,
                    4, MMXM_STAGE_NAMES[4], j_s4, idx[j_s4], oc_hi, oc_lo, float(c_m1[j_s4]), oc_hi, True,
                ))
            if j_s5 < j_rev:
                rows.append((
                    f"{mmxm_id}_S05", mmxm_id, oc_id, traded, tf, t_dir, model_type,
                    5, MMXM_STAGE_NAMES[5], j_s5, idx[j_s5], oc_hi, oc_lo, float(c_m1[j_s5]), oc_hi, True,
                ))
            if j_s6 < j_rev:
                rows.append((
                    f"{mmxm_id}_S06", mmxm_id, oc_id, traded, tf, t_dir, model_type,
                    6, MMXM_STAGE_NAMES[6], j_s6, idx[j_s6], oc_hi, oc_lo, float(c_m1[j_s6]), oc_hi, True,
                ))
            rows.append((
                f"{mmxm_id}_S07", mmxm_id, oc_id, traded, tf, t_dir, model_type,
                7, MMXM_STAGE_NAMES[7], j_s7, idx[j_s7], oc_hi, oc_lo, float(l_m1[j_s7]), oc_hi, True,
            ))
            # Stage 8: Reversal candidate at manipulation low sweep
            rows.append((
                f"{mmxm_id}_S08", mmxm_id, oc_id, traded, tf, t_dir, model_type,
                8, MMXM_STAGE_NAMES[8], j_rev, idx[j_rev], oc_hi, oc_lo,
                manip_ext, oc_hi, True,
            ))
            # Check Stage 9/10 confirmation after j_rev (close recovers above manipulation low + 0.35*rng)
            post_c = slc_c[ext_pos:]
            conf_rel = np.nonzero(post_c >= manip_ext + 0.35 * rng)[0]
            if len(conf_rel) > 0:
                j_conf_rev = j_rev + int(conf_rel[0])
                rows.append((
                    f"{mmxm_id}_S09", mmxm_id, oc_id, traded, tf, t_dir, model_type,
                    9, MMXM_STAGE_NAMES[9], j_conf_rev, idx[j_conf_rev], oc_hi, oc_lo,
                    float(c_m1[j_conf_rev]), oc_hi, True,
                ))
                rows.append((
                    f"{mmxm_id}_S10", mmxm_id, oc_id, traded, tf, t_dir, model_type,
                    10, MMXM_STAGE_NAMES[10], j_conf_rev, idx[j_conf_rev], oc_hi, oc_lo,
                    float(c_m1[j_conf_rev]), oc_hi, True,
                ))
                # Check Stage 11 (Intermediate delivery), Stage 12 (Terminus delivery), Stage 13 (Completed) vs Stage 14 (Failed)
                rem_h = h_m1[j_conf_rev + 1 : horizon_m1 + 1]
                rem_l = l_m1[j_conf_rev + 1 : horizon_m1 + 1]
                if len(rem_h) > 0:
                    mid_way = 0.5 * (manip_ext + oc_lo)
                    hit_int = np.nonzero(rem_h >= mid_way)[0]
                    hit_tgt = np.nonzero(rem_h >= oc_lo)[0]
                    hit_term = np.nonzero(rem_h >= oc_mid)[0]
                    hit_fail = np.nonzero(rem_l < manip_ext)[0]
                    t_fail = int(hit_fail[0]) if len(hit_fail) > 0 else 999999
                    if len(hit_int) > 0 and int(hit_int[0]) < t_fail:
                        j_s11 = j_conf_rev + 1 + int(hit_int[0])
                        rows.append((
                            f"{mmxm_id}_S11", mmxm_id, oc_id, traded, tf, t_dir, model_type,
                            11, MMXM_STAGE_NAMES[11], j_s11, idx[j_s11], oc_hi, oc_lo, mid_way, oc_hi, True,
                        ))
                    t_hit = int(hit_tgt[0]) if len(hit_tgt) > 0 else 999999
                    if t_hit < t_fail and t_hit < 999999:
                        j_done = j_conf_rev + 1 + t_hit
                        rows.append((
                            f"{mmxm_id}_S12", mmxm_id, oc_id, traded, tf, t_dir, model_type,
                            12, MMXM_STAGE_NAMES[12], j_done, idx[j_done], oc_hi, oc_lo, oc_lo, oc_hi, True,
                        ))
                        j_comp = j_conf_rev + 1 + int(hit_term[0]) if (len(hit_term) > 0 and int(hit_term[0]) < t_fail) else j_done
                        rows.append((
                            f"{mmxm_id}_S13", mmxm_id, oc_id, traded, tf, t_dir, model_type,
                            13, MMXM_STAGE_NAMES[13], j_comp, idx[j_comp], oc_hi, oc_lo,
                            oc_mid, oc_hi, False,
                        ))
                    else:
                        j_fail = j_conf_rev + 1 + t_fail if t_fail < 999999 else horizon_m1
                        rows.append((
                            f"{mmxm_id}_S14", mmxm_id, oc_id, traded, tf, t_dir, model_type,
                            14, MMXM_STAGE_NAMES[14], j_fail, idx[j_fail], oc_hi, oc_lo,
                            manip_ext, oc_hi, False,
                        ))
            else:
                rows.append((
                    f"{mmxm_id}_S15", mmxm_id, oc_id, traded, tf, t_dir, model_type,
                    15, MMXM_STAGE_NAMES[15], horizon_m1, idx[horizon_m1], oc_hi, oc_lo,
                    float(c_m1[horizon_m1]), oc_hi, False,
                ))
        else:
            # Bearish MMSM: price departs up (left side), sweeps manipulation high, reverses down toward oc_lo
            ext_pos = int(np.argmax(slc_h[:left_len]))
            j_rev = j0 + 1 + ext_pos
            manip_ext = float(slc_h[ext_pos])
            j_s4 = j0 + 1 + max(0, ext_pos // 4)
            j_s5 = j0 + 1 + max(1, ext_pos // 2)
            j_s6 = j0 + 1 + max(2, (3 * ext_pos) // 4)
            j_s7 = max(j0 + 1, j_rev - 1)
            if j_s4 < j_rev:
                rows.append((
                    f"{mmxm_id}_S04", mmxm_id, oc_id, traded, tf, t_dir, model_type,
                    4, MMXM_STAGE_NAMES[4], j_s4, idx[j_s4], oc_hi, oc_lo, float(c_m1[j_s4]), oc_lo, True,
                ))
            if j_s5 < j_rev:
                rows.append((
                    f"{mmxm_id}_S05", mmxm_id, oc_id, traded, tf, t_dir, model_type,
                    5, MMXM_STAGE_NAMES[5], j_s5, idx[j_s5], oc_hi, oc_lo, float(c_m1[j_s5]), oc_lo, True,
                ))
            if j_s6 < j_rev:
                rows.append((
                    f"{mmxm_id}_S06", mmxm_id, oc_id, traded, tf, t_dir, model_type,
                    6, MMXM_STAGE_NAMES[6], j_s6, idx[j_s6], oc_hi, oc_lo, float(c_m1[j_s6]), oc_lo, True,
                ))
            rows.append((
                f"{mmxm_id}_S07", mmxm_id, oc_id, traded, tf, t_dir, model_type,
                7, MMXM_STAGE_NAMES[7], j_s7, idx[j_s7], oc_hi, oc_lo, float(h_m1[j_s7]), oc_lo, True,
            ))
            rows.append((
                f"{mmxm_id}_S08", mmxm_id, oc_id, traded, tf, t_dir, model_type,
                8, MMXM_STAGE_NAMES[8], j_rev, idx[j_rev], oc_hi, oc_lo,
                manip_ext, oc_lo, True,
            ))
            post_c = slc_c[ext_pos:]
            conf_rel = np.nonzero(post_c <= manip_ext - 0.35 * rng)[0]
            if len(conf_rel) > 0:
                j_conf_rev = j_rev + int(conf_rel[0])
                rows.append((
                    f"{mmxm_id}_S09", mmxm_id, oc_id, traded, tf, t_dir, model_type,
                    9, MMXM_STAGE_NAMES[9], j_conf_rev, idx[j_conf_rev], oc_hi, oc_lo,
                    float(c_m1[j_conf_rev]), oc_lo, True,
                ))
                rows.append((
                    f"{mmxm_id}_S10", mmxm_id, oc_id, traded, tf, t_dir, model_type,
                    10, MMXM_STAGE_NAMES[10], j_conf_rev, idx[j_conf_rev], oc_hi, oc_lo,
                    float(c_m1[j_conf_rev]), oc_lo, True,
                ))
                rem_h = h_m1[j_conf_rev + 1 : horizon_m1 + 1]
                rem_l = l_m1[j_conf_rev + 1 : horizon_m1 + 1]
                if len(rem_l) > 0:
                    mid_way = 0.5 * (manip_ext + oc_hi)
                    hit_int = np.nonzero(rem_l <= mid_way)[0]
                    hit_tgt = np.nonzero(rem_l <= oc_hi)[0]
                    hit_term = np.nonzero(rem_l <= oc_mid)[0]
                    hit_fail = np.nonzero(rem_h > manip_ext)[0]
                    t_fail = int(hit_fail[0]) if len(hit_fail) > 0 else 999999
                    if len(hit_int) > 0 and int(hit_int[0]) < t_fail:
                        j_s11 = j_conf_rev + 1 + int(hit_int[0])
                        rows.append((
                            f"{mmxm_id}_S11", mmxm_id, oc_id, traded, tf, t_dir, model_type,
                            11, MMXM_STAGE_NAMES[11], j_s11, idx[j_s11], oc_hi, oc_lo, mid_way, oc_lo, True,
                        ))
                    t_hit = int(hit_tgt[0]) if len(hit_tgt) > 0 else 999999
                    if t_hit < t_fail and t_hit < 999999:
                        j_done = j_conf_rev + 1 + t_hit
                        rows.append((
                            f"{mmxm_id}_S12", mmxm_id, oc_id, traded, tf, t_dir, model_type,
                            12, MMXM_STAGE_NAMES[12], j_done, idx[j_done], oc_hi, oc_lo, oc_hi, oc_lo, True,
                        ))
                        j_comp = j_conf_rev + 1 + int(hit_term[0]) if (len(hit_term) > 0 and int(hit_term[0]) < t_fail) else j_done
                        rows.append((
                            f"{mmxm_id}_S13", mmxm_id, oc_id, traded, tf, t_dir, model_type,
                            13, MMXM_STAGE_NAMES[13], j_comp, idx[j_comp], oc_hi, oc_lo,
                            oc_mid, oc_lo, False,
                        ))
                    else:
                        j_fail = j_conf_rev + 1 + t_fail if t_fail < 999999 else horizon_m1
                        rows.append((
                            f"{mmxm_id}_S14", mmxm_id, oc_id, traded, tf, t_dir, model_type,
                            14, MMXM_STAGE_NAMES[14], j_fail, idx[j_fail], oc_hi, oc_lo,
                            manip_ext, oc_lo, False,
                        ))
            else:
                rows.append((
                    f"{mmxm_id}_S15", mmxm_id, oc_id, traded, tf, t_dir, model_type,
                    15, MMXM_STAGE_NAMES[15], horizon_m1, idx[horizon_m1], oc_hi, oc_lo,
                    float(c_m1[horizon_m1]), oc_lo, False,
                ))

    cols = [
        "mmxm_event_id", "mmxm_id", "oc_id", "instrument", "tf", "direction", "model_type",
        "stage_num", "stage_name", "j_m1_known", "t_known", "oc_high", "oc_low",
        "event_price", "terminus_target_px", "is_active",
    ]
    return pd.DataFrame(rows, columns=cols).sort_values("j_m1_known").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Phase 3: Complete Liquidity Event Engine (Section 8)
# ---------------------------------------------------------------------------
def build_liquidity_events_table(
    ctx: dict,
    raw_crt: dict[tuple[str, str], pd.DataFrame],
    oc_df: pd.DataFrame,
    dataset_hash: str = "",
) -> pd.DataFrame:
    """Build `liquidity_events.parquet` covering all observable liquidity interactions:
      - Approach, Sweep, Reclaim, Rejection, Accepted_Breakout, Failed_Breakout, Retest, Invalidation
      - Across M5, M15, M30, H1, H4, D1, W1, Session highs/lows, QT quarter highs/lows, EQH/EQL, OC boundaries.
    """
    panel = ctx["panel"]
    idx = panel.index
    traded = ctx["traded"]
    rows = []

    for (tf_name, anc), ev_df in raw_crt.items():
        if anc != "cal" or len(ev_df) == 0:
            continue
        jsw = ev_df["j_sweep"].to_numpy(int)
        jcl = ev_df["j_close"].to_numpy(int)
        jrc = ev_df["j_reclaim"].to_numpy(int)
        d = ev_df["dir"].to_numpy(int)
        hr = ev_df["Hr"].to_numpy(float)
        lr = ev_df["Lr"].to_numpy(float)
        c = ev_df["c"].to_numpy(float)
        o = ev_df["o"].to_numpy(float)
        h = ev_df["h"].to_numpy(float)
        l = ev_df["l"].to_numpy(float)
        atr = ev_df["atr_ref"].fillna(15.0).to_numpy(float)
        is_a = ev_df["A"].to_numpy(bool)
        is_c = ev_df["C"].to_numpy(bool)
        is_h = ev_df["H"].to_numpy(bool)
        sw_depth = ev_df["sweep_depth"].to_numpy(float)

        for k in range(len(ev_df)):
            j_first = int(jsw[k]) if jsw[k] >= 0 else int(jcl[k])
            j_conf = int(jcl[k])
            lvl = float(hr[k]) if d[k] == -1 else float(lr[k])
            opp_lvl = float(lr[k]) if d[k] == -1 else float(hr[k])
            pen = float(sw_depth[k])

            # Classify interaction type (Section 8)
            if is_h[k]:
                inter_type = "Failed_Breakout"
                reclaim_state = "Reclaimed_Next_Candle"
                hyp_mode = "REVERSAL"
                trade_dir = int(d[k])
            elif is_c[k]:
                inter_type = "Rejection"
                reclaim_state = "Reclaimed_Strong_Body"
                hyp_mode = "REVERSAL"
                trade_dir = int(d[k])
            elif is_a[k]:
                inter_type = "Reclaim"
                reclaim_state = "Reclaimed_Inside_Close"
                hyp_mode = "REVERSAL"
                trade_dir = int(d[k])
            elif jrc[k] >= 0 and jrc[k] < jcl[k]:
                inter_type = "Sweep"
                reclaim_state = "Intrabar_Reclaim_Then_Breakout"
                hyp_mode = "CONTINUATION"
                # Price swept and closed outside reference range -> continuation in sweep direction!
                trade_dir = -int(d[k])
            else:
                # Closed outside reference level -> Accepted Breakout / Continuation candidate
                body_sz = abs(c[k] - o[k])
                inter_type = "Accepted_Breakout" if body_sz >= 0.45 * atr[k] else "Sweep"
                reclaim_state = "Closed_Outside_Level"
                hyp_mode = "CONTINUATION"
                trade_dir = -int(d[k])

            rows.append((
                f"LIQ_{traded}_{tf_name}_{k:06d}",
                traded,
                tf_name,
                f"PREV_{tf_name}_{'HIGH' if d[k] == -1 else 'LOW'}",
                inter_type,
                reclaim_state,
                hyp_mode,
                int(d[k]),        # reversal direction (+1 bull after low sweep, -1 bear after high sweep)
                int(trade_dir),   # hypothesis direction (+1 LONG, -1 SHORT)
                lvl,
                opp_lvl,
                pen,
                round(pen / max(atr[k], 1e-6), 4),
                j_first,
                j_conf,
                idx[np.clip(j_first, 0, len(idx) - 1)],
                idx[np.clip(j_conf, 0, len(idx) - 1)] + pd.Timedelta(minutes=1),
                ALGO_VERSION,
                dataset_hash[:16] if dataset_hash else "VERIFIED_STORE",
            ))

    cols = [
        "liq_event_id", "instrument", "source_tf", "pool_type",
        "interaction_type", "reclaim_state", "hypothesis_mode",
        "reversal_dir", "hypothesis_dir", "level_px", "opposing_level_px",
        "penetration_pts", "penetration_atr", "j_first_obs", "j_confirm",
        "t_first_obs", "t_confirm", "algo_version", "dataset_hash",
    ]
    return pd.DataFrame(rows, columns=cols).sort_values("j_confirm").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Phase 3 & Section 14: Universal Atomic Event Database (`atomic_events.parquet`)
# ---------------------------------------------------------------------------
def build_atomic_events_database(
    ctx: dict,
    liq_df: pd.DataFrame,
    oc_df: pd.DataFrame,
    mmxm_ev_df: pd.DataFrame,
    dataset_hash: str = "",
) -> pd.DataFrame:
    """Combine all atomic events into `atomic_events.parquet` with standardized schema (Section 14)."""
    traded = ctx["traded"]
    h_tag = dataset_hash[:16] if dataset_hash else "VERIFIED_STORE"
    parts = []

    # 1. Liquidity & CRT events
    if len(liq_df) > 0:
        parts.append(pd.DataFrame({
            "event_id": liq_df["liq_event_id"],
            "event_family": "LIQUIDITY_" + liq_df["interaction_type"].astype(str).str.upper(),
            "instrument": liq_df["instrument"],
            "source_provider": "DUKA_OANDA_VERIFIED",
            "source_tf": liq_df["source_tf"],
            "direction": liq_df["hypothesis_dir"],
            "t_event": liq_df["t_first_obs"],
            "t_confirm": liq_df["t_confirm"],
            "t_invalidated": pd.NaT,
            "price_level": liq_df["level_px"],
            "price_low": np.minimum(liq_df["level_px"], liq_df["opposing_level_px"]),
            "price_high": np.maximum(liq_df["level_px"], liq_df["opposing_level_px"]),
            "related_event_ids": liq_df["pool_type"],
            "algo_version": ALGO_VERSION,
            "dataset_hash": h_tag,
        }))

    # 2. Macro & Micro SSMT events
    for ssmt_df, fam, tf_lbl in [
        (ctx["ssmt_mac"], "SSMT_MACRO_90M", "M90"),
        (ctx["ssmt_mic"], "SSMT_MICRO_22_5M", "22.5M"),
    ]:
        if len(ssmt_df) > 0:
            parts.append(pd.DataFrame({
                "event_id": [f"{fam}_{k:06d}" for k in range(len(ssmt_df))],
                "event_family": fam,
                "instrument": ssmt_df["traded"],
                "source_provider": "DUKA_OANDA_VERIFIED",
                "source_tf": tf_lbl,
                "direction": ssmt_df["dir"],
                "t_event": ssmt_df["t_form"],
                "t_confirm": ssmt_df["t_form"] + pd.Timedelta(minutes=1),
                "t_invalidated": ssmt_df["t_inv"],
                "price_level": np.nan,
                "price_low": np.nan,
                "price_high": np.nan,
                "related_event_ids": ssmt_df["inst_pair"].astype(str) + ":" + ssmt_df["pair_label"].astype(str) + ":Lead_" + ssmt_df["lead"].astype(str),
                "algo_version": ALGO_VERSION,
                "dataset_hash": h_tag,
            }))

    # 3. Multi-TF CISD events (M1, M3, M5, M15, M30, H1, H4)
    for tf_k, c_df in ctx["cisd_tables"].items():
        if len(c_df) == 0:
            continue
        # Keep full M5..H4 and cap M1/M3 at 25k in combined atomic lake to keep parquet compact & fast
        sub_c = c_df if tf_k not in ("M1", "M3") else c_df.iloc[::max(1, len(c_df) // 20000)]
        parts.append(pd.DataFrame({
            "event_id": [f"CISD_{traded}_{tf_k}_{k:06d}" for k in range(len(sub_c))],
            "event_family": f"CISD_{tf_k}",
            "instrument": traded,
            "source_provider": "DUKA_OANDA_VERIFIED",
            "source_tf": tf_k,
            "direction": sub_c["dir"],
            "t_event": sub_c["t_deliv_open"],
            "t_confirm": sub_c["t_confirm"],
            "t_invalidated": pd.NaT,
            "price_level": sub_c["ref_open"],
            "price_low": np.minimum(sub_c["ref_open"], sub_c["extreme_px"]),
            "price_high": np.maximum(sub_c["ref_open"], sub_c["extreme_px"]),
            "related_event_ids": "Variant_" + sub_c["variant"].astype(str),
            "algo_version": ALGO_VERSION,
            "dataset_hash": h_tag,
        }))

    # 4. Original Consolidations
    if len(oc_df) > 0:
        sub_oc = oc_df if len(oc_df) <= 30000 else oc_df.iloc[::max(1, len(oc_df) // 30000)]
        parts.append(pd.DataFrame({
            "event_id": sub_oc["oc_id"],
            "event_family": "ORIGINAL_CONSOLIDATION",
            "instrument": sub_oc["instrument"],
            "source_provider": "DUKA_OANDA_VERIFIED",
            "source_tf": sub_oc["tf"],
            "direction": sub_oc["target_dir"],
            "t_event": sub_oc["t_start"],
            "t_confirm": sub_oc["t_confirm"],
            "t_invalidated": sub_oc["t_invalidated"],
            "price_level": sub_oc["midpoint"],
            "price_low": sub_oc["low"],
            "price_high": sub_oc["high"],
            "related_event_ids": sub_oc["connected_mmxm_id"],
            "algo_version": ALGO_VERSION,
            "dataset_hash": h_tag,
        }))

    # 5. MMXM Stage Events
    if len(mmxm_ev_df) > 0:
        sub_m = mmxm_ev_df if len(mmxm_ev_df) <= 30000 else mmxm_ev_df.iloc[::max(1, len(mmxm_ev_df) // 30000)]
        parts.append(pd.DataFrame({
            "event_id": sub_m["mmxm_event_id"],
            "event_family": "MMXM_" + sub_m["stage_name"].astype(str),
            "instrument": sub_m["instrument"],
            "source_provider": "DUKA_OANDA_VERIFIED",
            "source_tf": sub_m["tf"],
            "direction": sub_m["direction"],
            "t_event": sub_m["t_known"],
            "t_confirm": sub_m["t_known"],
            "t_invalidated": pd.NaT,
            "price_level": sub_m["event_price"],
            "price_low": sub_m["oc_low"],
            "price_high": sub_m["oc_high"],
            "related_event_ids": sub_m["oc_id"],
            "algo_version": ALGO_VERSION,
            "dataset_hash": h_tag,
        }))

    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts, ignore_index=True)
    out["t_event"] = pd.to_datetime(out["t_event"], utc=True)
    out["t_confirm"] = pd.to_datetime(out["t_confirm"], utc=True)
    out["t_invalidated"] = pd.to_datetime(out["t_invalidated"], utc=True)
    return out.sort_values("t_confirm").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Phase 2 & 5: Multi-Timeframe Structure Context & Cross-Timeframe Target Engine
# ---------------------------------------------------------------------------
def attach_full_fractal_context(
    ctx: dict,
    cands: pd.DataFrame,
    oc_df: pd.DataFrame,
) -> pd.DataFrame:
    """Attach full multi-timeframe structural directions (`W1`, `D1`, `H4`, `H1`, `M15`, `M5`),
    historical Original Consolidations from both LOWER and HIGHER timeframes (`m5_oc`, `m15_oc`, `h1_oc`, `h4_oc`),
    and external HTF liquidity pools (`h1_liq`, `h4_liq`, `d1_liq`, `w1_liq`) known strictly at `t_signal_known`!
    """
    if len(cands) == 0:
        return cands
    out = cands.copy()
    panel = ctx["panel"]
    traded = ctx["traded"]
    idx = panel.index

    # 1. Assign stable unique `opportunity_id` so one opportunity is never double-counted (Section 14)
    out["opportunity_id"] = [
        f"OPP_{traded}_{tf}_{md}_{jt}_{ 'L' if d == 1 else 'S' }"
        for tf, md, jt, d in zip(out["tf"], out["entry_mode"], out["j_trig"], out["dir"])
    ]

    # Attach M30, H1, H4 CISD and opposing/expired CISD flags if not yet attached or if NaN exists after concat
    if "cisd_m30" not in out.columns or out["cisd_m30"].isna().any():
        out = cisd.attach_true_cisd_to_signals(
            out, {k: v for k, v in ctx["cisd_tables"].items() if k in ("M30", "H1", "H4")}
        )
    for tf_c in ("m1", "m3", "m5", "m15", "m30", "h1", "h4"):
        for pref in ("cisd_", "cisd_opp_", "cisd_exp_"):
            cname = f"{pref}{tf_c}"
            if cname in out.columns:
                out[cname] = out[cname].fillna(False).astype(bool)
            else:
                out[cname] = False

    # 2. Compute strictly causal structure bias across ALL V3 timeframes (known at candle close <= t_signal_known)
    t_sig = pd.to_datetime(out["t_signal_known"], utc=True)
    for tf_s in ("W1", "D1", "H6", "H4", "H2", "M90", "H1", "M30", "M15", "M10", "M5", "M3"):
        b = bars.resample(panel, traded, tf_s, "cal")
        bc = b[b["complete"]].copy()
        bc["bias"] = np.where(bc["c"] >= bc["o"], 1, -1)
        bc["prev_h"] = bc["h"]
        bc["prev_l"] = bc["l"]
        bc["prev_mid"] = 0.5 * (bc["h"] + bc["l"])
        joined = ict.asof_join(
            t_sig,
            bc.rename(columns={"t_close": "t_known"}),
            ["bias", "prev_h", "prev_l", "prev_mid"],
            time_col="t_known",
        )
        out[f"bias_{tf_s.lower()}"] = joined["bias"].fillna(1).to_numpy(np.int8)
        out[f"prev_h_{tf_s.lower()}"] = joined["prev_h"].to_numpy(float)
        out[f"prev_l_{tf_s.lower()}"] = joined["prev_l"].to_numpy(float)
        out[f"prev_mid_{tf_s.lower()}"] = joined["prev_mid"].to_numpy(float)

    # M1 bias & prev_h/prev_l directly from index j_trig
    jt_idx = np.clip(out["j_trig"].to_numpy(np.int64), 0, len(panel) - 1)
    m1_o = panel[f"{traded}_o"].to_numpy(float)[jt_idx]
    m1_c = panel[f"{traded}_c"].to_numpy(float)[jt_idx]
    out["bias_m1"] = np.where(m1_c >= m1_o, 1, -1).astype(np.int8)
    out["prev_h_m1"] = panel[f"{traded}_h"].to_numpy(float)[jt_idx]
    out["prev_l_m1"] = panel[f"{traded}_l"].to_numpy(float)[jt_idx]
    out["prev_mid_m1"] = 0.5 * (out["prev_h_m1"] + out["prev_l_m1"])

    # 3. Attach most recent active Original Consolidation on M5, M15, H1, H4 for the candidate's direction
    for oc_tf in ("M5", "M15", "H1", "H4"):
        sub_oc = oc_df[oc_df["tf"] == oc_tf].copy() if len(oc_df) > 0 else pd.DataFrame()
        col_px = f"oc_target_{oc_tf.lower()}"
        col_id = f"oc_id_{oc_tf.lower()}"
        col_age = f"oc_age_min_{oc_tf.lower()}"
        if len(sub_oc) == 0:
            out[col_px] = np.nan
            out[col_id] = ""
            out[col_age] = np.nan
            continue

        # Split by target_dir (+1 for Bullish MMBM target above, -1 for Bearish MMSM target below)
        px_arr = np.full(len(out), np.nan, dtype=np.float64)
        id_arr = np.array([""] * len(out), dtype=object)
        age_arr = np.full(len(out), np.nan, dtype=np.float64)
        jt = out["j_trig"].to_numpy(np.int64)
        d = out["dir"].to_numpy(np.int8)
        c_trig = panel[f"{traded}_c"].to_numpy(float)[jt]

        for tdir in (-1, 1):
            mask_d = np.nonzero(d == tdir)[0]
            if len(mask_d) == 0:
                continue
            oc_d = sub_oc[sub_oc["target_dir"] == tdir].sort_values("j_conf_m1")
            if len(oc_d) == 0:
                continue
            jc = oc_d["j_conf_m1"].to_numpy(np.int64)
            ji = oc_d["j_inv_m1"].to_numpy(np.int64)
            mid_p = oc_d["midpoint"].to_numpy(np.float64)
            oid = oc_d["oc_id"].to_numpy()
            for idx_i in mask_d:
                j_q = jt[idx_i]
                cur_px = c_trig[idx_i]
                k = np.searchsorted(jc, j_q, side="right") - 1
                steps = 0
                while k >= 0 and steps < 50:
                    # Must not be invalidated before j_q, and must lie in the trade direction!
                    if (ji[k] < 0 or ji[k] > j_q):
                        if (tdir == 1 and mid_p[k] > cur_px + 3.0) or (tdir == -1 and mid_p[k] < cur_px - 3.0):
                            px_arr[idx_i] = mid_p[k]
                            id_arr[idx_i] = str(oid[k])
                            age_arr[idx_i] = float(j_q - jc[k])
                            break
                    k -= 1
                    steps += 1
        out[col_px] = px_arr
        out[col_id] = id_arr
        out[col_age] = age_arr

    # 4. Classify Pre-Entry Reversal vs Continuation & HTF/LTF Alignment States (Section 3 & 6.1)
    d = out["dir"].to_numpy(int)
    b_d1 = out["bias_d1"].to_numpy(int)
    b_h4 = out["bias_h4"].to_numpy(int)
    b_h1 = out["bias_h1"].to_numpy(int)
    b_m15 = out["bias_m15"].to_numpy(int)
    b_m5 = out["bias_m5"].to_numpy(int)

    # Pre-entry hypothesis: Reversal (sweeping reference/HTF level and reclaiming inside) vs Continuation (aligned with structure / breakout)
    is_rev = out["A"].to_numpy(bool) | (out["entry_mode"].isin(["dev_cisd", "dev_reclaim"]).to_numpy(bool) & out["pd_zone_ok"].to_numpy(bool))
    out["hypothesis_type"] = np.where(is_rev, "REVERSAL", "CONTINUATION")
    out["direction_label"] = np.where(d == 1, "LONG", "SHORT")

    out["structural_regime"] = np.select(
        [
            (d == 1) & is_rev & (b_h1 == d) & (b_d1 == d),
            (d == -1) & is_rev & (b_h1 == d) & (b_d1 == d),
            (d == 1) & ~is_rev & (b_h1 == d),
            (d == -1) & ~is_rev & (b_h1 == d),
            (b_d1 == 1) & (b_m15 == -1) & (d == 1),
            (b_d1 == -1) & (b_m15 == 1) & (d == -1),
            (d == 1) & (b_d1 == -1),
            (d == -1) & (b_d1 == 1),
        ],
        [
            "Bullish_Reversal_LONG",
            "Bearish_Reversal_SHORT",
            "Bullish_Continuation_LONG",
            "Bearish_Continuation_SHORT",
            "Bullish_HTF_Bearish_LTF_Correction_LONG",
            "Bearish_HTF_Bullish_LTF_Correction_SHORT",
            "Countertrend_LONG",
            "Countertrend_SHORT",
        ],
        default="Mixed_HTF_LTF_State",
    )

    out["mmxm_directional_relation"] = np.select(
        [
            out["mmxm_early_candidate"] & (d == 1) & (b_h1 == 1) & (b_m15 == 1),
            out["mmxm_early_candidate"] & (d == -1) & (b_h1 == -1) & (b_m15 == -1),
            out["mmxm_early_candidate"] & (d == 1) & (b_h1 == 1) & (b_m15 == -1),
            out["mmxm_early_candidate"] & (d == -1) & (b_h1 == -1) & (b_m15 == 1),
            is_rev & (b_h4 != d) & (b_m5 == d),
            ~is_rev & (b_h4 == d) & (b_m5 != d),
        ],
        [
            "HTF_Bullish_MMXM_LTF_Bullish_MMXM (Nested_MMBM)",
            "HTF_Bearish_MMXM_LTF_Bearish_MMXM (Nested_MMSM)",
            "HTF_Bullish_MMXM_LTF_Bearish_Correction",
            "HTF_Bearish_MMXM_LTF_Bullish_Correction",
            "HTF_Reversal_LTF_Continuation",
            "HTF_Continuation_LTF_Reversal",
        ],
        default="Standard_Single_TF_MMXM",
    )

    # 5. Independent structural MMXM flag (Stage >= 5: OC + Departure + Liquidity Engineering + POI Sweep, independent of CISD!)
    out["f_mmxm"] = out["mmxm_stage"] >= 5
    # Map V2 mmxm_stage (0..8) onto V3 13-stage lifecycle (0..13)
    s_raw = out["mmxm_stage"].to_numpy(int)
    out["mmxm_stage_v3"] = np.select(
        [
            s_raw == 0,
            s_raw == 1,
            s_raw == 2,
            s_raw == 3,
            s_raw == 4,
            (s_raw == 5) & (~out["A"].to_numpy(bool)),
            (s_raw == 5) & out["A"].to_numpy(bool),
            s_raw == 6,
            s_raw == 7,
            s_raw >= 8,
        ],
        [0, 1, 2, 4, 6, 7, 8, 9, 10, 12],
        default=0,
    )

    # Determine explicit Origin TF, Narrative TF, MMXM TF, and Entry TF (Section 1)
    out["origin_tf"] = np.select(
        [out["pw_swept"], out["pd_swept"], out["tf"] == "H4", out["tf"] == "H1", out["tf"] == "M30", out["tf"] == "M15"],
        ["W1", "D1", "H4", "H1", "M30", "M15"],
        default=out["tf"],
    )
    out["narrative_tf"] = out["tf"]
    out["mmxm_tf"] = np.select(
        [
            out["oc_target_m5"].notna() & (out["tf"] == "M5"),
            out["oc_target_m15"].notna() & (out["tf"].isin(["M15", "M5"])),
            out["oc_target_h1"].notna() & (out["tf"].isin(["H1", "M30", "M15"])),
            out["oc_target_h4"].notna() & (out["tf"].isin(["H4", "H1"])),
            out["f_mmxm"],
        ],
        ["M5", "M15", "H1", "H4", "M5"],
        default=out["tf"],
    )
    out["entry_tf"] = np.select(
        [
            out["entry_mode"].isin(["dev_cisd", "dev_reclaim"]) & out["cisd_m1"],
            out["entry_mode"].isin(["dev_cisd", "dev_reclaim"]) & out["cisd_m3"],
            out["entry_mode"].isin(["dev_cisd", "dev_reclaim"]) & out["cisd_m5"],
            out["entry_mode"].isin(["dev_cisd", "dev_reclaim"]),
            (out["tf"] == "M5") & out["cisd_m1"] & (~out["cisd_m3"]),
            (out["tf"] == "M5") & out["cisd_m3"],
            (out["tf"] == "M15") & out["cisd_m1"] & (~out["cisd_m3"]) & (~out["cisd_m5"]),
            (out["tf"] == "M15") & out["cisd_m3"] & (~out["cisd_m5"]),
            (out["tf"] == "M15") & out["cisd_m5"],
            (out["tf"] == "M30") & out["cisd_m5"],
            (out["tf"] == "H1") & out["cisd_m1"] & (~out["cisd_m5"]) & (~out["cisd_m15"]),
            (out["tf"] == "H1") & out["cisd_m5"] & (~out["cisd_m15"]),
            (out["tf"] == "H1") & out["cisd_m15"] & (~out.get("cisd_m30", False)),
            (out["tf"] == "H1") & out.get("cisd_m30", False),
            (out["tf"] == "H4") & out["cisd_m5"] & (~out["cisd_m15"]),
            (out["tf"] == "H4") & out["cisd_m15"] & (~out.get("cisd_h1", False)),
            (out["tf"] == "H4") & out.get("cisd_h1", False),
        ],
        [
            "M1", "M3", "M5", "M1",
            "M1", "M3",
            "M1", "M3", "M5",
            "M5",
            "M1", "M5", "M15", "M30",
            "M5", "M15", "H1",
        ],
        default=out["tf"],
    )
    return out


def build_cross_timeframe_targets_and_outcomes(
    ctx: dict,
    cands: pd.DataFrame,
    horizon_bars: int = 360,
    slip: float = 0.25,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build `target_candidates.parquet`, `target_outcomes.parquet`, and `target_prediction_results.parquet` (Section 7).

    Evaluates HIGHER-timeframe targets (e.g., M5 MMXM -> H1/H4/D1/W1 liquidity),
    LOWER-timeframe targets (e.g., H1/H4 Reversal -> M5/M15 Original Consolidation),
    and SAME-timeframe targets for every candidate opportunity!
    """
    if len(cands) == 0:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    panel = ctx["panel"]
    traded = ctx["traded"]
    bh = panel[f"{traded}_h"].to_numpy(float)
    bl = panel[f"{traded}_l"].to_numpy(float)
    ah = panel[f"{traded}_ah"].to_numpy(float)
    al = panel[f"{traded}_al"].to_numpy(float)

    # Pre-extract arrays from cands
    opp_ids = cands["opportunity_id"].to_numpy()
    orig_tfs = cands["origin_tf"].to_numpy()
    narr_tfs = cands["narrative_tf"].to_numpy()
    mmxm_tfs = cands["mmxm_tf"].to_numpy()
    ent_tfs = cands["entry_tf"].to_numpy()
    dirs = cands["dir"].to_numpy(np.int64)
    j_fills = cands["j_fill"].to_numpy(np.int64)
    ep_arr = cands["px_entry"].to_numpy(float)
    sl_arr = cands["sl_init"].to_numpy(float)
    atr_arr = cands["atr_ref"].fillna(15.0).to_numpy(float)
    q90_arr = cands["q90_trig"].to_numpy(np.int8)
    mmxm_flag = cands["mmxm_early_candidate"].to_numpy(bool)
    hyp_type = cands["hypothesis_type"].to_numpy()
    t_sig_arr = cands["t_signal_known"].to_numpy()

    risk_arr = np.maximum(1.0, np.where(dirs == 1, ep_arr - sl_arr, sl_arr - ep_arr))

    # Define candidate target specs: (target_type, target_tf, price_array_bull, price_array_bear)
    target_specs = [
        ("M5_OC", "M5", cands["oc_target_m5"].to_numpy(float), cands["oc_target_m5"].to_numpy(float)),
        ("M15_OC", "M15", cands["oc_target_m15"].to_numpy(float), cands["oc_target_m15"].to_numpy(float)),
        ("H1_OC", "H1", cands["oc_target_h1"].to_numpy(float), cands["oc_target_h1"].to_numpy(float)),
        ("H4_OC", "H4", cands["oc_target_h4"].to_numpy(float), cands["oc_target_h4"].to_numpy(float)),
        ("M5_LIQ", "M5", cands["prev_h_m5"].to_numpy(float), cands["prev_l_m5"].to_numpy(float)),
        ("M15_LIQ", "M15", cands["prev_h_m15"].to_numpy(float), cands["prev_l_m15"].to_numpy(float)),
        ("H1_LIQ", "H1", cands["prev_h_h1"].to_numpy(float), cands["prev_l_h1"].to_numpy(float)),
        ("H4_LIQ", "H4", cands["prev_h_h4"].to_numpy(float), cands["prev_l_h4"].to_numpy(float)),
        ("D1_LIQ_PDH_PDL", "D1", cands["PDH"].to_numpy(float), cands["PDL"].to_numpy(float)),
        ("W1_LIQ_PWH_PWL", "W1", cands["PWH"].to_numpy(float), cands["PWL"].to_numpy(float)),
        ("CRT_MIDPOINT", "SAME", cands["mid_target"].to_numpy(float), cands["mid_target"].to_numpy(float)),
        ("CRT_OPP_BOUNDARY", "SAME", cands["opp_range_target"].to_numpy(float), cands["opp_range_target"].to_numpy(float)),
    ]

    cand_frames = []
    outcome_frames = []

    for tgt_type, tgt_tf_raw, px_bull, px_bear in target_specs:
        tgt_px = np.where(dirs == 1, px_bull, px_bear)
        tgt_tf_arr = np.where(tgt_tf_raw == "SAME", narr_tfs, tgt_tf_raw)

        # Target must be finite and in the trade's direction by at least 3.0 points (0.25 R minimum)
        dist_pts = np.where(dirs == 1, tgt_px - ep_arr, ep_arr - tgt_px)
        dist_r = dist_pts / risk_arr
        dist_atr = dist_pts / np.maximum(atr_arr, 1.0)
        valid_mask = np.isfinite(tgt_px) & (dist_pts >= 3.0) & (dist_r >= 0.35) & (dist_r <= 25.0)
        valid_idx = np.nonzero(valid_mask)[0]
        if len(valid_idx) == 0:
            continue

        sub_jf = j_fills[valid_idx]
        sub_dir = dirs[valid_idx]
        sub_sl = sl_arr[valid_idx]
        sub_tp = tgt_px[valid_idx]
        sub_ep = ep_arr[valid_idx]
        sub_risk = risk_arr[valid_idx]

        # Evaluate Longs on Bid highs/lows, Shorts on Ask highs/lows using verified Numba kernel
        # Split Long and Short so each uses its exact executable exit quote side (Bid for Long, Ask for Short)!
        reached_any = np.zeros(len(valid_idx), dtype=bool)
        reached_clean = np.zeros(len(valid_idx), dtype=bool)
        bars_to_tgt = np.full(len(valid_idx), -1, dtype=np.int64)

        long_m = np.nonzero(sub_dir == 1)[0]
        if len(long_m) > 0:
            ra_l, rc_l, bt_l = hpc.fast_target_horizon_eval_numba(
                bh, bl, sub_jf[long_m], sub_dir[long_m], sub_sl[long_m], sub_tp[long_m], horizon_bars
            )
            reached_any[long_m] = ra_l
            reached_clean[long_m] = rc_l
            bars_to_tgt[long_m] = bt_l

        short_m = np.nonzero(sub_dir == -1)[0]
        if len(short_m) > 0:
            ra_s, rc_s, bt_s = hpc.fast_target_horizon_eval_numba(
                ah, al, sub_jf[short_m], sub_dir[short_m], sub_sl[short_m], sub_tp[short_m], horizon_bars
            )
            reached_any[short_m] = ra_s
            reached_clean[short_m] = rc_s
            bars_to_tgt[short_m] = bt_s

        # Realized net R when trading toward this structural target (before stop-out)
        # If reached_clean: net R = (dist_pts - slip) / risk; else if stopped out: -1.0 - slip/risk
        sub_dist_pts = dist_pts[valid_idx]
        sub_dist_r = dist_r[valid_idx]
        sub_dist_atr = dist_atr[valid_idx]
        realized_r = np.where(
            reached_clean,
            (sub_dist_pts - slip) / sub_risk,
            -1.0 - (slip / sub_risk),
        )

        ent_min = np.array([TF_ORDER_MAP.get(str(x), 15) for x in ent_tfs[valid_idx]])
        nar_min = np.array([TF_ORDER_MAP.get(str(x), 15) for x in narr_tfs[valid_idx]])
        tgt_min = np.array([TF_ORDER_MAP.get(str(x), 15) for x in tgt_tf_arr[valid_idx]])

        tf_rel_entry = np.where(
            tgt_min > ent_min, "LTF_ENTRY_TO_HTF_TARGET",
            np.where(tgt_min < ent_min, "HTF_ENTRY_TO_LTF_TARGET", "SAME_TF_ENTRY_TARGET"),
        )
        tf_rel_narr = np.where(
            tgt_min > nar_min, "LTF_STRUCT_TO_HTF_TARGET",
            np.where(tgt_min < nar_min, "HTF_STRUCT_TO_LTF_TARGET", "SAME_TF_STRUCT_TARGET"),
        )
        # Count intervening obstacles (0 if <=1.5 ATR, 1 if <=3.5 ATR, 2+ if >3.5 ATR)
        obstacles = np.where(sub_dist_atr <= 1.5, 0, np.where(sub_dist_atr <= 3.5, 1, 2))

        t_cand_ids = [f"TC_{opp_ids[i]}_{tgt_type}" for i in valid_idx]
        cand_frames.append(pd.DataFrame({
            "target_candidate_id": t_cand_ids,
            "opportunity_id": opp_ids[valid_idx],
            "t_signal_known": t_sig_arr[valid_idx],
            "direction": np.where(sub_dir == 1, "LONG", "SHORT"),
            "hypothesis_type": hyp_type[valid_idx],
            "origin_tf": orig_tfs[valid_idx],
            "narrative_tf": narr_tfs[valid_idx],
            "mmxm_tf": mmxm_tfs[valid_idx],
            "entry_tf": ent_tfs[valid_idx],
            "target_tf": tgt_tf_arr[valid_idx],
            "target_type": tgt_type,
            "tf_relation_to_entry": tf_rel_entry,
            "tf_relation_to_narrative": tf_rel_narr,
            "qt_q90": q90_arr[valid_idx],
            "has_mmxm": mmxm_flag[valid_idx],
            "entry_px": sub_ep,
            "stop_px": sub_sl,
            "target_px": sub_tp,
            "distance_pts": sub_dist_pts,
            "distance_atr": sub_dist_atr,
            "distance_r": sub_dist_r,
            "intervening_obstacles": obstacles,
            "known_before_entry": True,
        }))

        outcome_frames.append(pd.DataFrame({
            "target_candidate_id": t_cand_ids,
            "opportunity_id": opp_ids[valid_idx],
            "direction": np.where(sub_dir == 1, "LONG", "SHORT"),
            "hypothesis_type": hyp_type[valid_idx],
            "narrative_tf": narr_tfs[valid_idx],
            "mmxm_tf": mmxm_tfs[valid_idx],
            "entry_tf": ent_tfs[valid_idx],
            "target_tf": tgt_tf_arr[valid_idx],
            "target_type": tgt_type,
            "tf_relation_to_entry": tf_rel_entry,
            "tf_relation_to_narrative": tf_rel_narr,
            "qt_q90": q90_arr[valid_idx],
            "has_mmxm": mmxm_flag[valid_idx],
            "distance_r": sub_dist_r,
            "target_reached_horizon": reached_any,
            "trade_reached_before_stop": reached_clean,
            "reached_only_after_stop": reached_any & (~reached_clean),
            "bars_to_target": bars_to_tgt,
            "realized_net_r": realized_r,
        }))

    df_cands = pd.concat(cand_frames, ignore_index=True) if cand_frames else pd.DataFrame()
    df_out = pd.concat(outcome_frames, ignore_index=True) if outcome_frames else pd.DataFrame()

    # Build aggregated `target_prediction_results.parquet` (Section 7.2 & 7.3)
    if len(df_out) > 0:
        pred_summary = (
            df_out.groupby(
                ["direction", "narrative_tf", "entry_tf", "target_tf", "target_type", "tf_relation_to_narrative"],
                dropna=False,
            )
            .agg(
                n_evaluations=("opportunity_id", "size"),
                n_unique_opportunities=("opportunity_id", "nunique"),
                mean_target_r=("distance_r", "mean"),
                prob_target_reached_horizon=("target_reached_horizon", "mean"),
                prob_trade_reached_before_stop=("trade_reached_before_stop", "mean"),
                prob_reached_after_stop=("reached_only_after_stop", "mean"),
                expectancy_net_r=("realized_net_r", "mean"),
                total_net_r=("realized_net_r", "sum"),
                median_bars_to_target=("bars_to_target", lambda s: float(s[s >= 0].median()) if (s >= 0).any() else np.nan),
            )
            .reset_index()
            .sort_values(["expectancy_net_r"], ascending=False)
            .reset_index(drop=True)
        )
    else:
        pred_summary = pd.DataFrame()

    return df_cands, df_out, pred_summary


# ---------------------------------------------------------------------------
# Phase 6: Causal Narrative Graph & Pre-Trade Narratives (Sections 5 & 11)
# ---------------------------------------------------------------------------
def build_narrative_graph_and_snapshots(
    cands: pd.DataFrame,
    target_outcomes: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build `fractal_narrative_graph.parquet` (Section 11) and `pretrade_narratives.parquet` (Section 5).

    Answers all 16 narrative questions at decision time `t_signal_known` and preserves exact event sequences:
      - Liquidity -> SSMT -> CISD
      - SSMT -> Liquidity -> CISD
      - CRT_Developing -> Micro_SSMT -> CISD
      - CRT_Confirmed -> CISD
      - MMXM_Reversal_Candidate -> QT_Transition -> CISD
      - QT_Transition -> Liquidity -> CRT -> CISD
    """
    if len(cands) == 0:
        return pd.DataFrame(), pd.DataFrame()

    # Classify exact temporal sequence of confirmations before `j_trig` (Section 11)
    jsw = cands["j_sweep"].to_numpy(int)
    jt = cands["j_trig"].to_numpy(int)
    j_ssmt = np.where(
        cands["micro_ssmt"], cands["micro_jform"].to_numpy(int),
        np.where(cands["macro_ssmt"], cands["macro_jform"].to_numpy(int), -1),
    )
    j_cisd = np.where(
        cands["cisd_m1"], cands["j_cisd_m1"].to_numpy(int),
        np.where(cands["cisd_m5"], cands["j_cisd_m5"].to_numpy(int), cands["j_cisd"].to_numpy(int)),
    )
    is_dev = (cands["entry_mode"] == "dev_cisd").to_numpy(bool)
    is_conf = (cands["entry_mode"] == "confirmed").to_numpy(bool)
    has_ssmt = cands["any_ssmt"].to_numpy(bool)
    has_cisd = (cands["cisd_m1"] | cands["cisd_m3"] | cands["cisd_m5"] | cands["cisd_m15"]).to_numpy(bool)
    has_mmxm = cands["mmxm_early_candidate"].to_numpy(bool)

    seq_label = np.select(
        [
            is_dev & has_ssmt & has_cisd & (jsw <= j_ssmt) & (j_ssmt <= j_cisd),
            is_dev & has_ssmt & has_cisd & (j_ssmt < jsw) & (jsw <= j_cisd),
            is_dev & cands["micro_ssmt"].to_numpy(bool) & has_cisd,
            is_conf & has_cisd & (~has_ssmt),
            has_mmxm & (cands["q90_trig"].isin([2, 3]).to_numpy(bool)) & has_cisd,
            (cands["q90_trig"].isin([2, 3]).to_numpy(bool)) & cands["A"].to_numpy(bool) & has_cisd,
            cands["A"].to_numpy(bool) & has_ssmt,
            cands["A"].to_numpy(bool),
        ],
        [
            "Liquidity_Sweep -> SSMT -> CISD",
            "SSMT -> Liquidity_Sweep -> CISD",
            "CRT_Developing -> Micro_SSMT -> CISD",
            "CRT_Confirmed -> CISD",
            "MMXM_Reversal_Candidate -> QT_Transition -> CISD",
            "QT_Transition -> Liquidity_Sweep -> CRT -> CISD",
            "Liquidity_Sweep -> CRT_Confirmed -> SSMT",
            "Liquidity_Sweep -> CRT_Confirmed",
        ],
        default="Liquidity_Sweep -> Structural_Trigger",
    )

    # Map Example Narratives A..F from Section 1 & Section 5
    d = cands["dir"].to_numpy(int)
    tf = cands["tf"].to_numpy()
    narrative_archetype = np.select(
        [
            (d == 1) & (tf == "H1") & has_mmxm & (cands["q90_trig"] == 2) & cands["micro_ssmt"] & cands["cisd_m1"],
            (d == -1) & (tf == "H1") & (cands["bias_m15"] == -1) & cands["cisd_m5"] & (cands["q90_trig"].isin([2, 3])),
            (d == 1) & (cands["bias_d1"] == 1) & (cands["bias_h1"] == -1) & (tf == "M15") & cands["cisd_m1"],
            (d == -1) & (cands["bias_h4"] == -1) & (cands["bias_m15"] == 1) & cands["cisd_m5"],
            (d == 1) & (tf == "M5") & has_mmxm & cands["cisd_m1"] & (~cands["macro_ssmt"]) & (~cands["micro_ssmt"]),
            (d == 1) & (tf == "M5") & has_mmxm & cands["oc_target_h1"].notna(),
            (d == 1) & (tf == "H1") & cands["oc_target_m5"].notna(),
        ],
        [
            "Narrative_A: H1_Sweep_M5_MMXM_QT_Q2_MicroSSMT_M1_CISD_LONG_to_H1_Liq",
            "Narrative_B: H1_Sweep_M15_MMSM_M5_CISD_QT_Q2Q3_SHORT_to_M5_OC",
            "Narrative_C: D1_Bull_H1_Corr_M15_Sweep_M1_CISD_LONG_to_W1_Liq",
            "Narrative_D: H4_Bear_M15_Corr_M5_CISD_SHORT_to_H1_D1_Liq",
            "Narrative_E: M5_MMXM_M1_CISD_No_SSMT_LONG_to_H1_Liq",
            "Example_A: M5_MMXM_LONG_to_H1_Liquidity",
            "Example_B: H1_Reversal_LONG_to_M5_OC",
        ],
        default="General_Causal_Fractal_Narrative",
    )

    # Best known target before entry for each opportunity
    best_tgt_map = {}
    if len(target_outcomes) > 0:
        # Select frozen pre-trade primary target (closest >= 1.5R structural target)
        sub_t = target_outcomes[target_outcomes["distance_r"] >= 1.2].sort_values(["opportunity_id", "distance_r"])
        first_t = sub_t.groupby("opportunity_id", as_index=False).first()
        best_tgt_map = first_t.set_index("opportunity_id").to_dict("index")

    tgt_tf_list = []
    tgt_type_list = []
    tgt_rel_list = []
    for oid, n_tf in zip(cands["opportunity_id"], cands["narrative_tf"]):
        info = best_tgt_map.get(oid)
        if info is not None:
            tgt_tf_list.append(str(info["target_tf"]))
            tgt_type_list.append(str(info["target_type"]))
            tgt_rel_list.append(str(info["tf_relation_to_narrative"]))
        else:
            tgt_tf_list.append(str(n_tf))
            tgt_type_list.append("FIXED_2R_BASELINE")
            tgt_rel_list.append("SAME_TF_STRUCT_TARGET")

    # Build immutable `pretrade_narratives.parquet` answering all 16 questions of Section 5
    pretrade_df = pd.DataFrame({
        "opportunity_id": cands["opportunity_id"],
        "t_signal_known": cands["t_signal_known"],
        "t_fill": cands["t_fill"],
        "instrument": cands.get("instrument", "US100"),
        "direction": cands["direction_label"],
        "q01_origin_tf": cands["origin_tf"],
        "q02_liquidity_pool": np.where(cands["pw_swept"], "PWH_PWL", np.where(cands["pd_swept"], "PDH_PDL", "REF_CANDLE_HL")),
        "q03_interaction_class": np.where(cands["H"], "Failed_Breakout", np.where(cands["C"], "Rejection", np.where(cands["A"], "Sweep_Reclaim", "Sweep"))),
        "q04_mtf_mmxm_context": (
            "W1:" + cands["bias_w1"].astype(str) + "|D1:" + cands["bias_d1"].astype(str)
            + "|H4:" + cands["bias_h4"].astype(str) + "|H1:" + cands["bias_h1"].astype(str)
            + "|M15:" + cands["bias_m15"].astype(str) + "|M5:" + cands["bias_m5"].astype(str)
        ),
        "q05_mmxm_stage_observable": cands["mmxm_stage_v3"].map(MMXM_STAGE_NAMES).fillna("00_OFF"),
        "q06_move_hypothesis": cands["hypothesis_type"],
        "q07_active_qt_phases": (
            "6H_Q" + cands["q6_trig"].astype(str) + "|90M_Q" + cands["q90_trig"].astype(str) + "|22.5M_Q" + cands["q22_trig"].astype(str)
        ),
        "q08_qt_transition": np.where(cands["macro_ssmt"], cands["macro_pair"].astype(str), np.where(cands["micro_ssmt"], cands["micro_pair"].astype(str), "Intra_Quarter")),
        "q09_ssmt_state": cands["macro_micro_align"],
        "q10_crt_state_tf": cands["tf"].astype(str) + ":" + cands["entry_mode"].astype(str),
        "q11_cisd_timeframes": (
            np.where(cands["cisd_m1"], "M1|", "")
            + np.where(cands["cisd_m3"], "M3|", "")
            + np.where(cands["cisd_m5"], "M5|", "")
            + np.where(cands["cisd_m15"], "M15|", "")
            + np.where(cands.get("cisd_m30", False), "M30|", "")
            + np.where(cands.get("cisd_h1", False), "H1|", "")
            + np.where(cands.get("cisd_h4", False), "H4|", "")
        ),
        "q12_executable_entry_tf": cands["entry_tf"],
        "q13_known_target_type": tgt_type_list,
        "q14_target_tf_relation": tgt_rel_list,
        "q15_structural_consistency": cands["structural_regime"],
        "q16_invalidation_price": cands["sl_init"],
        "target_tf": tgt_tf_list,
        "temporal_sequence": seq_label,
        "narrative_archetype": narrative_archetype,
        "mmxm_directional_relation": cands["mmxm_directional_relation"],
        "realized_r_post_trade": cands["r"],
    })

    # Build `fractal_narrative_graph.parquet` (Section 11 edge list for causal sequences)
    # Sample up to 15,000 representative opportunities -> ~60,000 causal graph edges
    sub_p = pretrade_df if len(pretrade_df) <= 15000 else pretrade_df.iloc[::max(1, len(pretrade_df) // 15000)]
    edges = []
    for row in sub_p.itertuples(index=False):
        oid = str(row.opportunity_id)
        ts = row.t_signal_known
        # Edge 1: Origin Liquidity -> CRT / MMXM Stage
        edges.append((
            f"EDGE_{oid}_1", oid, "Liquidity", f"{row.q01_origin_tf}:{row.q02_liquidity_pool}",
            "swept" if "Sweep" in str(row.q03_interaction_class) else "approached",
            "MMXM_Stage", str(row.q05_mmxm_stage_observable), ts, str(row.temporal_sequence),
        ))
        # Edge 2: QT Phase / SSMT -> CISD / Entry
        edges.append((
            f"EDGE_{oid}_2", oid, "QT_SSMT_Context", f"{row.q07_active_qt_phases}|{row.q09_ssmt_state}",
            "confirms" if row.q09_ssmt_state != "Conflict" else "contradicts",
            "CISD", str(row.q11_cisd_timeframes) or "NO_CISD", ts, str(row.temporal_sequence),
        ))
        # Edge 3: Entry -> Pre-Existing Target
        edges.append((
            f"EDGE_{oid}_3", oid, "Entry", f"{row.q12_executable_entry_tf}:{row.direction}",
            "targets",
            "Target", f"{row.target_tf}:{row.q13_known_target_type} ({row.q14_target_tf_relation})", ts, str(row.temporal_sequence),
        ))
        # Edge 4: Entry -> Invalidation Stop
        edges.append((
            f"EDGE_{oid}_4", oid, "Invalidation", f"SL@{row.q16_invalidation_price:.2f}",
            "invalidates",
            "Entry", f"{row.q12_executable_entry_tf}:{row.direction}", ts, str(row.temporal_sequence),
        ))

    graph_cols = [
        "edge_id", "opportunity_id", "source_node_type", "source_node_label",
        "relation", "target_node_type", "target_node_label", "t_known", "sequence_pattern",
    ]
    graph_df = pd.DataFrame(edges, columns=graph_cols)
    return graph_df, pretrade_df

