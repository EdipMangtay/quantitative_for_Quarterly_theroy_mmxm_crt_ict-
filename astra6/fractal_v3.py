"""ASTRA 6 V3 — Universal Fractal Market Structure, Atomic Event Data Lake,
Original Consolidation, Incremental 13-Stage MMXM FSM, Liquidity Engine & Cross-Timeframe Target Graph.

Repaired for P0.1–P0.6 and P1.7–P1.12:
  * P0.1: `build_fractal_mmxm_state_events()` uses a strictly causal bar-by-bar incremental
          Finite State Machine (`_run_incremental_mmxm_fsm_numba`) with zero future `argmin`/`argmax`
          and 100% prefix invariance (`events[j_m1_known <= T]` are invariant to data `> T`).
  * P0.2: Exact bar-close confirmation timing (`m1_close_idx = panel.index + 1min`), so no OC or MMXM
          stage event is ever marked known before its candle close timestamp `t_confirm` / `t_known`.
  * P0.3: `attach_full_fractal_context()` joins active `mmxm_state_events` causally as-of `(t_signal_known, dir)`
          and sets `mmxm_stage_v3`, `mmxm_id`, and `mmxm_tf` directly from the verified MMXM event.
  * P0.4: Independent strategy execution for all 64 binary combinations and M1/M3/M5/M15/M30/H1/H4 CISD
          strategies at each configuration's own causal confirmation timestamp `j_exec` (`j_fill = j_exec + 1`).
  * P0.5: Target-consistent execution via `hpc.fast_target_exec_full_numba` simulating actual structural
          target prices (`H1_LIQ`, `M5_OC`, etc.) and separating `TARGET_HIT`, `STOP_HIT`, `AMBIGUOUS`,
          `TIMEOUT` (mark-to-market, never automatic -1R), and `DATA_END`.
  * P0.6: True CISD confirmation delay `t_cisd_confirm - t_sweep_confirm` matched against valid liquidity
          sweeps (`j_sweep >= 0`), keeping `j_sweep == -1` distinct.
  * P1.7: Complete event universe (`100% FULL_UNIVERSE` across M5..D1 OCs & MMXM FSM, M1..H4 CISD, M3..W1 CRT).
  * P1.8: Pre-trade tables (`pretrade_narratives.parquet`, `candidate_opportunities.parquet`) contain
          zero post-trade outcome fields.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from numba import njit

from . import bars, cisd, clock, crt, hpc, ict, sim, smt

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "data" / "results"

ALGO_VERSION = "ASTRA6_V3.5_CAUSAL_REPAIR"

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

# Section 6: 13-Stage MMXM Lifecycle Definitions (+ Failed & Invalidated)
MMXM_STAGE_NAMES = {
    0: "00_OFF",
    1: "01_OC_CANDIDATE",
    2: "02_OC_CONFIRMED",
    3: "03_FIRST_DEPARTURE",
    4: "04_LEFT_SIDE",
    5: "05_INTERMEDIATE_CONSOLIDATION",
    6: "06_LIQUIDITY_ENGINEERING",
    7: "07_STRUCTURAL_EXTENSION_POI_ZONE",
    8: "08_REVERSAL_CANDIDATE",
    9: "09_REVERSAL_DISPLACEMENT_STAGE",
    10: "10_RIGHT_SIDE_CANDIDATE",
    11: "11_INTERMEDIATE_DELIVERY",
    12: "12_TERMINUS_DELIVERY",
    13: "13_COMPLETED",
    14: "14_FAILED",
    15: "15_INVALIDATED",
}


# ---------------------------------------------------------------------------
# Phase 4: Original Consolidation Engine (Section 6.2 & P0.2)
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
    Tracks subsequent revisits and invalidation strictly forward from `i + 1` for causal query-time filtering.
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
                if h[k] >= w_lo:
                    r_cnt += 1
                    if f_rev < 0:
                        f_rev = k
                if h[k] > w_hi + 0.25 * a_ref:
                    inv_k = k
                    break
            else:
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
    *,
    include_lifecycle: bool = False,
) -> pd.DataFrame:
    """Return confirmed OC summaries or immutable candidate/lifecycle events.

    The default summary includes retrospective revisit/invalidation columns
    for legacy consumers. With `include_lifecycle`, those observations are
    separate events, and formation has no departure direction or target.
    """
    idx = panel.index
    frames = []
    for tf in timeframes:
        b = bars.resample(panel, traded, tf, "cal")
        b = b[b["is_closed"]].reset_index(drop=True)
        if len(b) < 5:
            continue

        o = b["o"].to_numpy(float)
        h = b["h"].to_numpy(float)
        l = b["l"].to_numpy(float)
        c = b["c"].to_numpy(float)
        atr = ict.atr_wilder(h, l, c, 14)

        min_dep = 0.55 if tf in ("M1", "M3") else 0.35
        max_w = 2.0 if tf in ("M1", "M3") else 2.4
        t_open = b["t_open"].to_numpy()
        t_close = b["available_at"].to_numpy()
        coverage = b["data_coverage_status"].to_numpy()
        opens_sec = pd.DatetimeIndex(t_open).as_unit("s").asi8
        if include_lifecycle:
            ends = np.arange(4, len(b))
            cand_high = b["h"].rolling(4).max().to_numpy()[ends]
            cand_low = b["l"].rolling(4).min().to_numpy()[ends]
            width = cand_high - cand_low
            selected = (width > 0) & (width <= max_w * atr[ends])
            ends = ends[selected]
            frames.append(pd.DataFrame({
                "oc_id": [f"OC_{traded}_{tf}_{opens_sec[k - 3]}" for k in ends],
                "event_kind": "CANDIDATE",
                "instrument": traded,
                "tf": tf,
                "tf_minutes": bars.TF_MIN[tf],
                "t_start": t_open[ends - 3],
                "t_cand_known": t_close[ends],
                "j_cand_m1": bars.minute_confirmation_index(idx, t_close[ends]),
                "t_known": t_close[ends],
                "available_at": t_close[ends],
                "data_coverage_status": coverage[ends],
                "high": cand_high[selected],
                "low": cand_low[selected],
                "midpoint": (cand_high[selected] + cand_low[selected]) / 2,
                "is_accessible": False,
            }))
        st_i, cf_i, hi, lo, mid, watr, ddir, ddisp, rcnt, frev, invi = _scan_original_consolidations_numba(
            o, h, l, c, atr, min_bars=4, max_width_atr=max_w, min_depart_atr=min_dep, max_horizon_bars=96
        )
        if len(cf_i) == 0:
            continue

        t_start = t_open[st_i]
        # Candidate finishes at close of bar (cf_i - 1), which equals t_open[cf_i]
        t_cand_close = t_close[cf_i - 1]
        j_cand_m1 = bars.minute_confirmation_index(idx, t_cand_close)
        t_cand_known = t_cand_close

        # Confirmation occurs strictly at close of departure bar cf_i (t_close[cf_i])
        t_conf = t_close[cf_i]
        j_conf_m1 = bars.minute_confirmation_index(idx, t_conf)

        t_frev = pd.Series(pd.NaT, index=range(len(cf_i)), dtype="datetime64[ms, UTC]")
        has_rev = frev >= 0
        if has_rev.any():
            t_frev.loc[has_rev] = t_close[frev[has_rev]]

        t_inv = pd.Series(pd.NaT, index=range(len(cf_i)), dtype="datetime64[ms, UTC]")
        j_inv_m1 = np.full(len(cf_i), -1, dtype=np.int64)
        has_inv = invi >= 0
        if has_inv.any():
            t_inv_vals = t_close[invi[has_inv]]
            t_inv.loc[has_inv] = t_inv_vals
            j_inv_m1[has_inv] = bars.minute_confirmation_index(idx, t_inv_vals)

        target_dir = (-ddir).astype(np.int8)
        oc_ids = [f"OC_{traded}_{tf}_{opens_sec[k]}" for k in st_i]
        mmxm_ids = [f"MMXM_{traded}_{tf}_{opens_sec[k]}" for k in st_i]

        df_tf = pd.DataFrame({
            "oc_id": oc_ids,
            "event_kind": "CONFIRMED",
            "instrument": traded,
            "tf": tf,
            "tf_minutes": bars.TF_MIN[tf],
            "t_start": t_start,
            "j_cand_m1": j_cand_m1,
            "t_cand_known": t_cand_known,
            "t_confirm": t_conf,
            "t_known": t_conf,
            "available_at": t_conf,
            "data_coverage_status": b["data_coverage_status"].to_numpy()[cf_i],
            "departure_close": c[cf_i],
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
            "is_accessible_at_confirm": True,
            "is_accessible": ~has_inv,
            "connected_mmxm_id": mmxm_ids,
            "universe_coverage": "FULL_UNIVERSE",
            "algo_version": ALGO_VERSION,
            "dataset_hash": dataset_hash[:16] if dataset_hash else "VERIFIED_STORE",
        })
        if include_lifecycle:
            for kind, present, timestamps in (
                ("REVISITED", has_rev, t_frev), ("INVALIDATED", has_inv, t_inv),
            ):
                events = df_tf.loc[present, [
                    "oc_id", "instrument", "tf", "tf_minutes", "t_start",
                    "target_dir", "high", "low", "midpoint", "connected_mmxm_id",
                ]].copy()
                events["event_kind"] = kind
                events["available_at"] = timestamps[present]
                events["t_known"] = events["available_at"]
                events["is_accessible"] = kind != "INVALIDATED"
                frames.append(events)
            df_tf = df_tf.drop(columns=[
                "age_bars", "revisit_count", "t_first_revisit", "t_invalidated", "j_inv_m1",
            ])
            df_tf["is_accessible"] = True
        frames.append(df_tf)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).sort_values(
        ["available_at", "oc_id"], kind="stable",
    ).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Phase 3 & 6: True Incremental Causal 13-Stage MMXM FSM Engine (Section 6 & P0.1, P0.2, P1.7)
# ---------------------------------------------------------------------------
@njit(cache=True)
def _run_incremental_mmxm_fsm_numba(
    o_m1: np.ndarray,
    h_m1: np.ndarray,
    l_m1: np.ndarray,
    c_m1: np.ndarray,
    j_cand_arr: np.ndarray,
    j_conf_arr: np.ndarray,
    tf_min_arr: np.ndarray,
    t_dir_arr: np.ndarray,
    oc_hi_arr: np.ndarray,
    oc_lo_arr: np.ndarray,
    oc_mid_arr: np.ndarray,
    departure_close_arr: np.ndarray | None = None,
) -> tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
]:
    """Strictly causal bar-by-bar incremental Finite State Machine for MMXM stages 1..15 (P0.1).

    Prefix-Invariance Guarantee:
      - At every M1 bar `j > j0`, state transitions depend ONLY on M1 prices at or before `j` (`[j0 .. j]`).
      - Zero future `argmin`/`argmax` over `[j0+1 : horizon]`.
      - Zero retroactive `ext_pos // 4` timestamp interpolation.
      - If the price series is truncated at any bar `T` or modified after `T`, every emitted event
        with `j_m1_known <= T` is 100% bit-for-bit identical!

    Returns flat arrays for all emitted stage events across all input OCs:
      (oc_row_idx, stage_num, j_m1_known, event_price, target_price, is_active, j_terminal_m1)
    """
    n_oc = j_conf_arr.shape[0]
    n_m1 = o_m1.shape[0]
    max_events = n_oc * 14 + 1

    out_oc_idx = np.empty(max_events, np.int64)
    out_stage = np.empty(max_events, np.int8)
    out_j_known = np.empty(max_events, np.int64)
    out_ev_px = np.empty(max_events, np.float64)
    out_tgt_px = np.empty(max_events, np.float64)
    out_active = np.empty(max_events, np.bool_)
    out_j_term = np.empty(max_events, np.int64)
    ev_cnt = 0

    for i in range(n_oc):
        j0 = j_conf_arr[i]
        jcand = j_cand_arr[i]
        if j0 < 0 or j0 >= n_m1 or jcand < 0 or jcand >= n_m1:
            continue

        tf_min = tf_min_arr[i]
        t_dir = t_dir_arr[i]  # +1 for Bullish MMBM, -1 for Bearish MMSM
        oc_hi = oc_hi_arr[i]
        oc_lo = oc_lo_arr[i]
        oc_mid = oc_mid_arr[i]
        rng = oc_hi - oc_lo
        if rng < 1.0:
            rng = 1.0
        tgt_px = oc_hi if t_dir == 1 else oc_lo

        # The directional MMXM candidate exists once the OC departure is known.
        # The earlier, directionless OC candidate is a separate event.
        out_oc_idx[ev_cnt] = i
        out_stage[ev_cnt] = 1
        out_j_known[ev_cnt] = j0
        out_ev_px[ev_cnt] = oc_mid
        out_tgt_px[ev_cnt] = tgt_px
        out_active[ev_cnt] = True
        ev_cnt += 1

        # Stage 2 (OC Confirmed) & Stage 3 (First Departure) known at j0 (close of departure bar)
        out_oc_idx[ev_cnt] = i
        out_stage[ev_cnt] = 2
        out_j_known[ev_cnt] = j0
        out_ev_px[ev_cnt] = oc_mid
        out_tgt_px[ev_cnt] = tgt_px
        out_active[ev_cnt] = True
        ev_cnt += 1

        dep_close = c_m1[j0] if departure_close_arr is None else departure_close_arr[i]
        out_oc_idx[ev_cnt] = i
        out_stage[ev_cnt] = 3
        out_j_known[ev_cnt] = j0
        out_ev_px[ev_cnt] = dep_close
        out_tgt_px[ev_cnt] = tgt_px
        out_active[ev_cnt] = True
        ev_cnt += 1

        max_walk = 36 * tf_min
        if max_walk > 1440:
            max_walk = 1440
        horizon_m1 = j0 + max_walk
        if horizon_m1 >= n_m1:
            horizon_m1 = n_m1 - 1

        state = 3
        run_ext = l_m1[j0] if t_dir == 1 else h_m1[j0]
        interm_ext = run_ext
        manip_ext = run_ext
        rev_bound = h_m1[j0] if t_dir == 1 else l_m1[j0]
        terminated = False

        # Step strictly bar-by-bar using ONLY current bar j (and j-1)
        for j in range(j0 + 1, horizon_m1 + 1):
            oj = o_m1[j]
            hj = h_m1[j]
            lj = l_m1[j]
            cj = c_m1[j]
            bar_rng = hj - lj
            if bar_rng < 1e-6:
                bar_rng = 1e-6

            if t_dir == 1:
                # Bullish MMBM: downward left-side departure, sweeps manipulation low, reverses up toward oc_lo / oc_mid
                if state < 9:
                    # Causal invalidation check before reversal confirmation:
                    # If price returns to oc_mid before forming left-side progression (state < 6) or drops > 6*rng
                    if (state < 6 and hj >= oc_mid) or (lj < oc_lo - 6.0 * rng):
                        out_oc_idx[ev_cnt] = i
                        out_stage[ev_cnt] = 15
                        out_j_known[ev_cnt] = j
                        out_ev_px[ev_cnt] = cj
                        out_tgt_px[ev_cnt] = tgt_px
                        out_active[ev_cnt] = False
                        ev_cnt += 1
                        terminated = True
                        break

                    if state == 3:
                        if lj <= dep_close - 0.15 * rng:
                            state = 4
                            out_oc_idx[ev_cnt] = i
                            out_stage[ev_cnt] = 4
                            out_j_known[ev_cnt] = j
                            out_ev_px[ev_cnt] = cj
                            out_tgt_px[ev_cnt] = tgt_px
                            out_active[ev_cnt] = True
                            ev_cnt += 1
                    elif state == 4:
                        # Local pause / counter-candle during left-side progression forms intermediate consolidation
                        if cj > oj or lj >= l_m1[j - 1]:
                            state = 5
                            interm_ext = run_ext
                            out_oc_idx[ev_cnt] = i
                            out_stage[ev_cnt] = 5
                            out_j_known[ev_cnt] = j
                            out_ev_px[ev_cnt] = cj
                            out_tgt_px[ev_cnt] = tgt_px
                            out_active[ev_cnt] = True
                            ev_cnt += 1
                    elif state == 5:
                        # Liquidity engineering: tests or sweeps intermediate low
                        if lj <= interm_ext + 0.05 * rng:
                            state = 6
                            out_oc_idx[ev_cnt] = i
                            out_stage[ev_cnt] = 6
                            out_j_known[ev_cnt] = j
                            out_ev_px[ev_cnt] = lj
                            out_tgt_px[ev_cnt] = tgt_px
                            out_active[ev_cnt] = True
                            ev_cnt += 1
                    elif state == 6:
                        # HTF POI interaction: reaches displacement zone below OC
                        if lj <= oc_lo - 0.40 * rng or lj < interm_ext:
                            state = 7
                            out_oc_idx[ev_cnt] = i
                            out_stage[ev_cnt] = 7
                            out_j_known[ev_cnt] = j
                            out_ev_px[ev_cnt] = lj
                            out_tgt_px[ev_cnt] = tgt_px
                            out_active[ev_cnt] = True
                            ev_cnt += 1
                    elif state == 7:
                        # Reversal candidate: sweeps/tests running low and closes with bullish rejection
                        if lj <= run_ext + 0.10 * rng and (cj >= oj or (cj - lj) >= 0.35 * bar_rng):
                            state = 8
                            manip_ext = lj if lj < run_ext else run_ext
                            rev_bound = hj
                            out_oc_idx[ev_cnt] = i
                            out_stage[ev_cnt] = 8
                            out_j_known[ev_cnt] = j
                            out_ev_px[ev_cnt] = manip_ext
                            out_tgt_px[ev_cnt] = tgt_px
                            out_active[ev_cnt] = True
                            ev_cnt += 1
                    elif state == 8:
                        # While in Stage 8 candidate, check if deeper manipulation low occurs or reversal confirms
                        if lj < manip_ext:
                            manip_ext = lj
                            rev_bound = hj
                        conf_thresh = manip_ext + 0.35 * rng
                        if rev_bound < conf_thresh and rev_bound > manip_ext:
                            conf_thresh = rev_bound
                        if cj >= conf_thresh and cj > manip_ext + 0.20 * rng:
                            state = 10
                            out_oc_idx[ev_cnt] = i
                            out_stage[ev_cnt] = 9
                            out_j_known[ev_cnt] = j
                            out_ev_px[ev_cnt] = cj
                            out_tgt_px[ev_cnt] = tgt_px
                            out_active[ev_cnt] = True
                            ev_cnt += 1

                            out_oc_idx[ev_cnt] = i
                            out_stage[ev_cnt] = 10
                            out_j_known[ev_cnt] = j
                            out_ev_px[ev_cnt] = cj
                            out_tgt_px[ev_cnt] = tgt_px
                            out_active[ev_cnt] = True
                            ev_cnt += 1

                    if lj < run_ext:
                        run_ext = lj

                else:
                    # Right-side delivery (state in 10, 11, 12)
                    # Pessimistic failure check first: breach of confirmed manipulation low before completion -> Stage 14 FAILED
                    if lj < manip_ext:
                        out_oc_idx[ev_cnt] = i
                        out_stage[ev_cnt] = 14
                        out_j_known[ev_cnt] = j
                        out_ev_px[ev_cnt] = manip_ext
                        out_tgt_px[ev_cnt] = tgt_px
                        out_active[ev_cnt] = False
                        ev_cnt += 1
                        terminated = True
                        break

                    mid_way = 0.5 * (manip_ext + oc_lo)
                    if state == 10 and hj >= mid_way:
                        state = 11
                        out_oc_idx[ev_cnt] = i
                        out_stage[ev_cnt] = 11
                        out_j_known[ev_cnt] = j
                        out_ev_px[ev_cnt] = mid_way
                        out_tgt_px[ev_cnt] = tgt_px
                        out_active[ev_cnt] = True
                        ev_cnt += 1

                    if state in (10, 11) and hj >= oc_lo:
                        state = 12
                        out_oc_idx[ev_cnt] = i
                        out_stage[ev_cnt] = 12
                        out_j_known[ev_cnt] = j
                        out_ev_px[ev_cnt] = oc_lo
                        out_tgt_px[ev_cnt] = tgt_px
                        out_active[ev_cnt] = True
                        ev_cnt += 1

                    if state == 12 and hj >= oc_mid:
                        state = 13
                        out_oc_idx[ev_cnt] = i
                        out_stage[ev_cnt] = 13
                        out_j_known[ev_cnt] = j
                        out_ev_px[ev_cnt] = oc_mid
                        out_tgt_px[ev_cnt] = tgt_px
                        out_active[ev_cnt] = False
                        ev_cnt += 1
                        terminated = True
                        break

            else:
                # Bearish MMSM: upward left-side departure, sweeps manipulation high, reverses down toward oc_hi / oc_mid
                if state < 9:
                    if (state < 6 and lj <= oc_mid) or (hj > oc_hi + 6.0 * rng):
                        out_oc_idx[ev_cnt] = i
                        out_stage[ev_cnt] = 15
                        out_j_known[ev_cnt] = j
                        out_ev_px[ev_cnt] = cj
                        out_tgt_px[ev_cnt] = tgt_px
                        out_active[ev_cnt] = False
                        ev_cnt += 1
                        terminated = True
                        break

                    if state == 3:
                        if hj >= dep_close + 0.15 * rng:
                            state = 4
                            out_oc_idx[ev_cnt] = i
                            out_stage[ev_cnt] = 4
                            out_j_known[ev_cnt] = j
                            out_ev_px[ev_cnt] = cj
                            out_tgt_px[ev_cnt] = tgt_px
                            out_active[ev_cnt] = True
                            ev_cnt += 1
                    elif state == 4:
                        if cj < oj or hj <= h_m1[j - 1]:
                            state = 5
                            interm_ext = run_ext
                            out_oc_idx[ev_cnt] = i
                            out_stage[ev_cnt] = 5
                            out_j_known[ev_cnt] = j
                            out_ev_px[ev_cnt] = cj
                            out_tgt_px[ev_cnt] = tgt_px
                            out_active[ev_cnt] = True
                            ev_cnt += 1
                    elif state == 5:
                        if hj >= interm_ext - 0.05 * rng:
                            state = 6
                            out_oc_idx[ev_cnt] = i
                            out_stage[ev_cnt] = 6
                            out_j_known[ev_cnt] = j
                            out_ev_px[ev_cnt] = hj
                            out_tgt_px[ev_cnt] = tgt_px
                            out_active[ev_cnt] = True
                            ev_cnt += 1
                    elif state == 6:
                        if hj >= oc_hi + 0.40 * rng or hj > interm_ext:
                            state = 7
                            out_oc_idx[ev_cnt] = i
                            out_stage[ev_cnt] = 7
                            out_j_known[ev_cnt] = j
                            out_ev_px[ev_cnt] = hj
                            out_tgt_px[ev_cnt] = tgt_px
                            out_active[ev_cnt] = True
                            ev_cnt += 1
                    elif state == 7:
                        if hj >= run_ext - 0.10 * rng and (cj <= oj or (hj - cj) >= 0.35 * bar_rng):
                            state = 8
                            manip_ext = hj if hj > run_ext else run_ext
                            rev_bound = lj
                            out_oc_idx[ev_cnt] = i
                            out_stage[ev_cnt] = 8
                            out_j_known[ev_cnt] = j
                            out_ev_px[ev_cnt] = manip_ext
                            out_tgt_px[ev_cnt] = tgt_px
                            out_active[ev_cnt] = True
                            ev_cnt += 1
                    elif state == 8:
                        if hj > manip_ext:
                            manip_ext = hj
                            rev_bound = lj
                        conf_thresh = manip_ext - 0.35 * rng
                        if rev_bound > conf_thresh and rev_bound < manip_ext:
                            conf_thresh = rev_bound
                        if cj <= conf_thresh and cj < manip_ext - 0.20 * rng:
                            state = 10
                            out_oc_idx[ev_cnt] = i
                            out_stage[ev_cnt] = 9
                            out_j_known[ev_cnt] = j
                            out_ev_px[ev_cnt] = cj
                            out_tgt_px[ev_cnt] = tgt_px
                            out_active[ev_cnt] = True
                            ev_cnt += 1

                            out_oc_idx[ev_cnt] = i
                            out_stage[ev_cnt] = 10
                            out_j_known[ev_cnt] = j
                            out_ev_px[ev_cnt] = cj
                            out_tgt_px[ev_cnt] = tgt_px
                            out_active[ev_cnt] = True
                            ev_cnt += 1

                    if hj > run_ext:
                        run_ext = hj

                else:
                    if hj > manip_ext:
                        out_oc_idx[ev_cnt] = i
                        out_stage[ev_cnt] = 14
                        out_j_known[ev_cnt] = j
                        out_ev_px[ev_cnt] = manip_ext
                        out_tgt_px[ev_cnt] = tgt_px
                        out_active[ev_cnt] = False
                        ev_cnt += 1
                        terminated = True
                        break

                    mid_way = 0.5 * (manip_ext + oc_hi)
                    if state == 10 and lj <= mid_way:
                        state = 11
                        out_oc_idx[ev_cnt] = i
                        out_stage[ev_cnt] = 11
                        out_j_known[ev_cnt] = j
                        out_ev_px[ev_cnt] = mid_way
                        out_tgt_px[ev_cnt] = tgt_px
                        out_active[ev_cnt] = True
                        ev_cnt += 1

                    if state in (10, 11) and lj <= oc_hi:
                        state = 12
                        out_oc_idx[ev_cnt] = i
                        out_stage[ev_cnt] = 12
                        out_j_known[ev_cnt] = j
                        out_ev_px[ev_cnt] = oc_hi
                        out_tgt_px[ev_cnt] = tgt_px
                        out_active[ev_cnt] = True
                        ev_cnt += 1

                    if state == 12 and lj <= oc_mid:
                        state = 13
                        out_oc_idx[ev_cnt] = i
                        out_stage[ev_cnt] = 13
                        out_j_known[ev_cnt] = j
                        out_ev_px[ev_cnt] = oc_mid
                        out_tgt_px[ev_cnt] = tgt_px
                        out_active[ev_cnt] = False
                        ev_cnt += 1
                        terminated = True
                        break

        # If horizon_m1 was reached inside the available data (j0 + max_walk < n_m1) without terminating,
        # emit terminal timeout stage at horizon_m1
        if (not terminated) and (j0 + max_walk < n_m1):
            st_end = 14 if state >= 10 else 15
            out_oc_idx[ev_cnt] = i
            out_stage[ev_cnt] = st_end
            out_j_known[ev_cnt] = horizon_m1
            out_ev_px[ev_cnt] = c_m1[horizon_m1]
            out_tgt_px[ev_cnt] = tgt_px
            out_active[ev_cnt] = False
            ev_cnt += 1

    for k_ev in range(ev_cnt):
        out_j_term[k_ev] = -1 if out_active[k_ev] else out_j_known[k_ev]

    return (
        out_oc_idx[:ev_cnt],
        out_stage[:ev_cnt],
        out_j_known[:ev_cnt],
        out_ev_px[:ev_cnt],
        out_tgt_px[:ev_cnt],
        out_active[:ev_cnt],
        out_j_term[:ev_cnt],
    )


def build_fractal_mmxm_state_events(
    panel: pd.DataFrame,
    oc_df: pd.DataFrame,
    traded: str = "US100",
    timeframes: tuple[str, ...] = ("M5", "M15", "M30", "H1", "H4", "D1"),
) -> pd.DataFrame:
    """Track all 13+2 MMXM lifecycle stages causally from every confirmed Original Consolidation
    across `M5`, `M15`, `M30`, `H1`, `H4`, `D1` (`mmxm_state_events.parquet`) (P0.1, P0.2, P1.7).

    Zero Sub-Sampling (`FULL_UNIVERSE`):
      - Runs `_run_incremental_mmxm_fsm_numba` across 100% of all confirmed OCs on `timeframes`.
    Strict Confirmation Timing (P0.2):
      - `t_known = m1_close_idx[j_m1_known]` (exact M1 bar close timestamp, never bar open!).
    Prefix Invariance (P0.1):
      - Truncating `panel` at any bar `T` leaves all events with `j_m1_known <= T` bit-for-bit identical.
    """
    if len(oc_df) == 0:
        return pd.DataFrame()
    if "event_kind" in oc_df:
        oc_df = oc_df[oc_df["event_kind"] == "CONFIRMED"]
    idx = panel.index
    m1_close_idx = idx + pd.Timedelta(minutes=1)
    n_m1 = len(idx)

    work_oc = (
        oc_df[oc_df["tf"].isin(timeframes) & (oc_df["j_conf_m1"] < n_m1)]
        .sort_values(["j_conf_m1", "oc_id"])
        .reset_index(drop=True)
    )
    if len(work_oc) == 0:
        return pd.DataFrame()

    o_m1 = panel[f"{traded}_o"].to_numpy(np.float64)
    h_m1 = panel[f"{traded}_h"].to_numpy(np.float64)
    l_m1 = panel[f"{traded}_l"].to_numpy(np.float64)
    c_m1 = panel[f"{traded}_c"].to_numpy(np.float64)

    j_conf_arr = work_oc["j_conf_m1"].to_numpy(np.int64)
    if "j_cand_m1" in work_oc.columns:
        j_cand_arr = work_oc["j_cand_m1"].to_numpy(np.int64)
    else:
        j_cand_arr = np.maximum(0, j_conf_arr - work_oc["tf_minutes"].to_numpy(np.int64))
    tf_min_arr = work_oc["tf_minutes"].to_numpy(np.int64)
    t_dir_arr = work_oc["target_dir"].to_numpy(np.int8)
    oc_hi_arr = work_oc["high"].to_numpy(np.float64)
    oc_lo_arr = work_oc["low"].to_numpy(np.float64)
    oc_mid_arr = work_oc["midpoint"].to_numpy(np.float64)

    oc_idx, st_num, j_known, ev_px, tgt_px, is_act, j_term = _run_incremental_mmxm_fsm_numba(
        o_m1, h_m1, l_m1, c_m1,
        j_cand_arr, j_conf_arr, tf_min_arr, t_dir_arr, oc_hi_arr, oc_lo_arr, oc_mid_arr,
        work_oc["departure_close"].to_numpy(np.float64) if "departure_close" in work_oc else None,
    )
    if len(oc_idx) == 0:
        return pd.DataFrame()

    mmxm_ids_src = work_oc["connected_mmxm_id"].to_numpy()
    oc_ids_src = work_oc["oc_id"].to_numpy()
    tfs_src = work_oc["tf"].to_numpy()
    dirs_src = work_oc["target_dir"].to_numpy(np.int8)

    parent_mmxm = mmxm_ids_src[oc_idx]
    parent_oc = oc_ids_src[oc_idx]
    parent_tf = tfs_src[oc_idx]
    parent_dir = dirs_src[oc_idx]
    stage_names = np.array([MMXM_STAGE_NAMES[int(s)] for s in st_num], dtype=object)
    model_types = np.where(parent_dir == 1, "MMBM", "MMSM")
    ev_ids = [f"{m_id}_S{int(s):02d}" for m_id, s in zip(parent_mmxm, st_num)]
    t_known = pd.Series(m1_close_idx[j_known])
    source_confirmation = st_num <= 3
    if "available_at" in work_oc:
        t_known.loc[source_confirmation] = work_oc["available_at"].array[oc_idx[source_confirmation]]

    out = pd.DataFrame({
        "mmxm_event_id": ev_ids,
        "mmxm_id": parent_mmxm,
        "oc_id": parent_oc,
        "instrument": traded,
        "tf": parent_tf,
        "direction": parent_dir,
        "model_type": model_types,
        "stage_num": st_num.astype(np.int64),
        "stage_name": stage_names,
        "j_m1_known": j_known,
        "t_known": t_known,
        "available_at": t_known,
        "oc_high": oc_hi_arr[oc_idx],
        "oc_low": oc_lo_arr[oc_idx],
        "event_price": ev_px,
        "target_price": tgt_px,
        "is_active": is_act,
        "j_terminal_m1": j_term,
        "universe_coverage": "FULL_UNIVERSE",
    })
    return out.sort_values(["j_m1_known", "stage_num", "mmxm_id"]).reset_index(drop=True)


def active_mmxm_asof(events: pd.DataFrame, query_j: int) -> pd.DataFrame:
    """Return the latest active state of every observed candidate and timeframe."""
    if events.empty:
        return events
    known = events[events["j_m1_known"] <= query_j].sort_values(
        ["j_m1_known", "stage_num", "mmxm_id"], kind="stable",
    )
    latest = known.drop_duplicates(["tf", "mmxm_id"], keep="last")
    return latest[latest["is_active"]]


# ---------------------------------------------------------------------------
# Phase 3 & Section 8: Complete Liquidity Event Engine (`liquidity_events.parquet`)
# ---------------------------------------------------------------------------
def build_liquidity_events_table(
    ctx: dict,
    raw_crt: dict[tuple[str, str], pd.DataFrame],
    oc_df: pd.DataFrame,
    dataset_hash: str = "",
) -> pd.DataFrame:
    """Build `liquidity_events.parquet` modeling all 8 liquidity interaction classes (Section 8)."""
    panel = ctx["panel"]
    idx = panel.index
    m1_close_idx = idx + pd.Timedelta(minutes=1)
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
                trade_dir = -int(d[k])
            else:
                body_sz = abs(c[k] - o[k])
                inter_type = "Accepted_Breakout" if body_sz >= 0.45 * atr[k] else "Sweep"
                reclaim_state = "Closed_Outside_Level"
                hyp_mode = "CONTINUATION"
                trade_dir = -int(d[k])

            jf_clip = int(np.clip(j_first, 0, len(idx) - 1))
            jc_clip = int(np.clip(j_conf, 0, len(idx) - 1))
            rows.append((
                f"LIQ_{traded}_{tf_name}_{k:06d}",
                traded,
                tf_name,
                f"PREV_{tf_name}_{'HIGH' if d[k] == -1 else 'LOW'}",
                inter_type,
                reclaim_state,
                hyp_mode,
                int(d[k]),
                int(trade_dir),
                lvl,
                opp_lvl,
                pen,
                round(pen / max(atr[k], 1e-6), 4),
                int(jsw[k]),
                j_first,
                j_conf,
                m1_close_idx[jf_clip],
                m1_close_idx[jc_clip],
                "FULL_UNIVERSE",
                ALGO_VERSION,
                dataset_hash[:16] if dataset_hash else "VERIFIED_STORE",
            ))

    cols = [
        "liq_event_id", "instrument", "source_tf", "pool_type",
        "interaction_type", "reclaim_state", "hypothesis_mode",
        "reversal_dir", "hypothesis_dir", "level_px", "opposing_level_px",
        "penetration_pts", "penetration_atr", "j_sweep_raw", "j_first_obs", "j_confirm",
        "t_first_obs", "t_confirm", "universe_coverage", "algo_version", "dataset_hash",
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
    """Combine all atomic events into `atomic_events.parquet` with standardized schema (Section 14 & P1.7).

    Includes 100% of all liquidity, SSMT, CISD, Original Consolidation, and MMXM stage events
    with `universe_coverage = "FULL_UNIVERSE"`.
    """
    traded = ctx["traded"]
    h_tag = dataset_hash[:16] if dataset_hash else "VERIFIED_STORE"
    parts = []

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
            "universe_coverage": "FULL_UNIVERSE",
            "algo_version": ALGO_VERSION,
            "dataset_hash": h_tag,
        }))

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
                "universe_coverage": "FULL_UNIVERSE",
                "algo_version": ALGO_VERSION,
                "dataset_hash": h_tag,
            }))

    for tf_k, c_df in ctx["cisd_tables"].items():
        if len(c_df) == 0:
            continue
        parts.append(pd.DataFrame({
            "event_id": [f"CISD_{traded}_{tf_k}_{k:06d}" for k in range(len(c_df))],
            "event_family": f"CISD_{tf_k}",
            "instrument": traded,
            "source_provider": "DUKA_OANDA_VERIFIED",
            "source_tf": tf_k,
            "direction": c_df["dir"],
            "t_event": c_df["t_deliv_open"],
            "t_confirm": c_df["t_confirm"],
            "t_invalidated": pd.NaT,
            "price_level": c_df["ref_open"],
            "price_low": np.minimum(c_df["ref_open"], c_df["extreme_px"]),
            "price_high": np.maximum(c_df["ref_open"], c_df["extreme_px"]),
            "related_event_ids": "Variant_" + c_df["variant"].astype(str),
            "universe_coverage": "FULL_UNIVERSE",
            "algo_version": ALGO_VERSION,
            "dataset_hash": h_tag,
        }))

    if len(oc_df) > 0:
        parts.append(pd.DataFrame({
            "event_id": oc_df["oc_id"],
            "event_family": "ORIGINAL_CONSOLIDATION",
            "instrument": oc_df["instrument"],
            "source_provider": "DUKA_OANDA_VERIFIED",
            "source_tf": oc_df["tf"],
            "direction": oc_df["target_dir"],
            "t_event": oc_df["t_start"],
            "t_confirm": oc_df["t_confirm"],
            "t_invalidated": oc_df["t_invalidated"],
            "price_level": oc_df["midpoint"],
            "price_low": oc_df["low"],
            "price_high": oc_df["high"],
            "related_event_ids": oc_df["connected_mmxm_id"],
            "universe_coverage": "FULL_UNIVERSE",
            "algo_version": ALGO_VERSION,
            "dataset_hash": h_tag,
        }))

    if len(mmxm_ev_df) > 0:
        parts.append(pd.DataFrame({
            "event_id": mmxm_ev_df["mmxm_event_id"],
            "event_family": "MMXM_" + mmxm_ev_df["stage_name"].astype(str),
            "instrument": mmxm_ev_df["instrument"],
            "source_provider": "DUKA_OANDA_VERIFIED",
            "source_tf": mmxm_ev_df["tf"],
            "direction": mmxm_ev_df["direction"],
            "t_event": mmxm_ev_df["t_known"],
            "t_confirm": mmxm_ev_df["t_known"],
            "t_invalidated": pd.NaT,
            "price_level": mmxm_ev_df["event_price"],
            "price_low": mmxm_ev_df["oc_low"],
            "price_high": mmxm_ev_df["oc_high"],
            "related_event_ids": mmxm_ev_df["oc_id"],
            "universe_coverage": "FULL_UNIVERSE",
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
# Phase 2 & 5: Causal As-Of MMXM Event Join & Multi-Timeframe Structure Context (P0.3)
# ---------------------------------------------------------------------------
@njit(cache=True)
def _asof_join_active_mmxm_numba(
    jt_query: np.ndarray,
    dir_query: np.ndarray,
    ev_j_known: np.ndarray,
    ev_j_term: np.ndarray,
    ev_dir: np.ndarray,
    ev_stage: np.ndarray,
    ev_tf_code: np.ndarray,
    ev_row_idx: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Causal as-of join linking each candidate opportunity `(jt_query[i], dir_query[i])`
    with the most recent active `mmxm_state_events` record where:
      - `ev_dir[k] == dir_query[i]`
      - `ev_j_known[k] <= jt_query[i]` (strictly confirmed at or before `t_signal_known`)
      - `ev_j_term[k] >= jt_query[i]` (model has not terminated prior to `jt_query[i]`)

    Returns:
      (matched_stage, matched_tf_code, matched_j_known, matched_ev_row_idx)
    """
    n_q = jt_query.shape[0]
    n_e = ev_j_known.shape[0]
    m_stage = np.zeros(n_q, np.int8)
    m_tf = np.full(n_q, -1, np.int8)
    m_j_known = np.full(n_q, -1, np.int64)
    m_row = np.full(n_q, -1, np.int64)

    if n_e == 0:
        return m_stage, m_tf, m_j_known, m_row

    for i in range(n_q):
        jq = jt_query[i]
        dq = dir_query[i]
        # Binary search right-most event with ev_j_known[k] <= jq
        lo = 0
        hi = n_e
        while lo < hi:
            mid = (lo + hi) // 2
            if ev_j_known[mid] <= jq:
                lo = mid + 1
            else:
                hi = mid
        k = lo - 1
        best_stage = 0
        best_tf = -1
        best_jk = -1
        best_r = -1
        while k >= 0:
            if jq - ev_j_known[k] > 1440:
                break
            if ev_dir[k] == dq and ev_j_term[k] >= jq:
                st_k = ev_stage[k]
                # Prefer active progression/reversal/delivery stages (4..12) over mere OC confirmation (1..3)
                if st_k > best_stage and st_k <= 13:
                    best_stage = st_k
                    best_tf = ev_tf_code[k]
                    best_jk = ev_j_known[k]
                    best_r = ev_row_idx[k]
                    if best_stage >= 8:
                        break
                elif best_stage == 0:
                    best_stage = st_k
                    best_tf = ev_tf_code[k]
                    best_jk = ev_j_known[k]
                    best_r = ev_row_idx[k]
            k -= 1
        m_stage[i] = best_stage
        m_tf[i] = best_tf
        m_j_known[i] = best_jk
        m_row[i] = best_r

    return m_stage, m_tf, m_j_known, m_row


def attach_full_fractal_context(
    ctx: dict,
    cands: pd.DataFrame,
    oc_df: pd.DataFrame,
    mmxm_ev_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Attach full multi-timeframe structural directions (`W1..M1`),
    causal Original Consolidations (`m5_oc`, `m15_oc`, `h1_oc`, `h4_oc`),
    and TRUE causal as-of joined `mmxm_state_events` (`mmxm_stage_v3`, `mmxm_tf`, `mmxm_id`) (P0.2 & P0.3).
    """
    if len(cands) == 0:
        return cands
    out = cands.copy()
    panel = ctx["panel"]
    traded = ctx["traded"]
    idx = panel.index

    # 1. Assign stable unique `opportunity_id` and `underlying_event_id` + `ny_day_id` (P1.10)
    out["opportunity_id"] = [
        f"OPP_{traded}_{tf}_{md}_{jt}_{ 'L' if d == 1 else 'S' }"
        for tf, md, jt, d in zip(out["tf"], out["entry_mode"], out["j_trig"], out["dir"])
    ]
    out["underlying_event_id"] = [
        f"UEV_{traded}_{tf}_{jo}_{ 'L' if d == 1 else 'S' }"
        for tf, jo, d in zip(out["tf"], out["j_open"], out["dir"])
    ]
    t_sig = pd.to_datetime(out["t_signal_known"], utc=True)
    # NY trading day ID (shifted by +6h so 18:00 NY starts the next session day)
    ny_shifted = t_sig.dt.tz_convert("America/New_York") + pd.Timedelta(hours=6)
    out["ny_day_id"] = (ny_shifted.dt.year * 10000 + ny_shifted.dt.month * 100 + ny_shifted.dt.day).to_numpy(np.int64)

    # Attach all 7 CISD timeframes (both as-of context and post-sweep confirmation delay, P0.4 & P0.6)
    if "j_post_cisd_m1" not in out.columns or "cisd_m30" not in out.columns or out["cisd_m30"].isna().any():
        out = cisd.attach_true_cisd_to_signals(out, ctx["cisd_tables"])

    for tf_c in ("m1", "m3", "m5", "m15", "m30", "h1", "h4"):
        for pref in ("cisd_", "cisd_opp_", "cisd_exp_"):
            cname = f"{pref}{tf_c}"
            if cname in out.columns:
                out[cname] = out[cname].fillna(False).astype(bool)
            else:
                out[cname] = False

    # 2. Compute strictly causal structure bias across ALL V3 timeframes (known at candle close <= t_signal_known)
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

    jt_idx = np.clip(out["j_trig"].to_numpy(np.int64), 0, len(panel) - 1)
    m1_o = panel[f"{traded}_o"].to_numpy(float)[jt_idx]
    m1_c = panel[f"{traded}_c"].to_numpy(float)[jt_idx]
    out["bias_m1"] = np.where(m1_c >= m1_o, 1, -1).astype(np.int8)
    out["prev_h_m1"] = panel[f"{traded}_h"].to_numpy(float)[jt_idx]
    out["prev_l_m1"] = panel[f"{traded}_l"].to_numpy(float)[jt_idx]
    out["prev_mid_m1"] = 0.5 * (out["prev_h_m1"] + out["prev_l_m1"])

    # 3. Attach most recent active Original Consolidation on M5, M15, H1, H4 for the candidate's direction (P0.2)
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

        px_arr = np.full(len(out), np.nan, dtype=np.float64)
        id_arr = np.array([""] * len(out), dtype=object)
        age_arr = np.full(len(out), np.nan, dtype=np.float64)
        jt = out["j_trig"].to_numpy(np.int64)
        d = out["dir"].to_numpy(np.int8)
        c_trig = panel[f"{traded}_c"].to_numpy(float)[jt_idx]

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
                # Strictly causal: jc[k] <= j_q means OC bar close t_confirm <= t_signal_known!
                k = np.searchsorted(jc, j_q, side="right") - 1
                steps = 0
                while k >= 0 and steps < 50:
                    if ji[k] < 0 or ji[k] > j_q:
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

    # 4. TRUE MMXM × QT Integration via causal as-of event join on `mmxm_state_events` (P0.3)
    mmxm_tfs_list = ["M5", "M15", "M30", "H1", "H4", "D1"]
    tf_to_code = {t: idx_t for idx_t, t in enumerate(mmxm_tfs_list)}
    code_to_tf = {idx_t: t for idx_t, t in enumerate(mmxm_tfs_list)}

    if mmxm_ev_df is not None and len(mmxm_ev_df) > 0:
        ev_sorted = mmxm_ev_df.sort_values(
            ["j_m1_known", "stage_num", "mmxm_id"], kind="stable",
        ).reset_index(drop=True)
        # The next observation supersedes the prior state at that bar. This
        # index is private to the join and never written onto historical events.
        next_update = ev_sorted.groupby(["tf", "mmxm_id"], sort=False)["j_m1_known"].shift(-1)
        ev_sorted["j_valid_through"] = next_update.fillna(len(panel)).astype(np.int64) - 1
        ev_sorted = ev_sorted[ev_sorted["is_active"]].reset_index(drop=True)
        ev_jk = ev_sorted["j_m1_known"].to_numpy(np.int64)
        ev_jt = ev_sorted["j_valid_through"].to_numpy(np.int64)
        ev_dr = ev_sorted["direction"].to_numpy(np.int8)
        ev_st = ev_sorted["stage_num"].to_numpy(np.int8)
        ev_tc = np.array([tf_to_code.get(str(t), 0) for t in ev_sorted["tf"]], dtype=np.int8)
        ev_ri = np.arange(len(ev_sorted), dtype=np.int64)

        m_st, m_tf, m_jk, m_row = _asof_join_active_mmxm_numba(
            out["j_trig"].to_numpy(np.int64),
            out["dir"].to_numpy(np.int8),
            ev_jk, ev_jt, ev_dr, ev_st, ev_tc, ev_ri,
        )
        out["mmxm_stage_v3"] = m_st.astype(np.int64)
        out["j_mmxm_known"] = m_jk
        mmxm_ids_col = ev_sorted["mmxm_id"].to_numpy()
        out["mmxm_id"] = [str(mmxm_ids_col[r]) if r >= 0 else "NONE" for r in m_row]
        # P0.3: `mmxm_tf` is strictly the timeframe of the verified MMXM event, NOT derived from OC target!
        out["mmxm_tf"] = [code_to_tf.get(int(tc), "NONE") if tc >= 0 else "NONE" for tc in m_tf]
    else:
        out["mmxm_stage_v3"] = 0
        out["j_mmxm_known"] = -1
        out["mmxm_id"] = "NONE"
        out["mmxm_tf"] = "NONE"

    # Active MMXM progression/reversal/delivery flag (Stages 4..12 from true V3 MMXM state machine, independent of CISD)
    out["f_mmxm"] = ((out["mmxm_stage_v3"] >= 4) & (out["mmxm_stage_v3"] <= 12)).astype(bool)

    # 5. Classify Pre-Entry Reversal vs Continuation & HTF/LTF Alignment States (Section 3 & 6.1)
    d = out["dir"].to_numpy(int)
    b_d1 = out["bias_d1"].to_numpy(int)
    b_h4 = out["bias_h4"].to_numpy(int)
    b_h1 = out["bias_h1"].to_numpy(int)
    b_m15 = out["bias_m15"].to_numpy(int)
    b_m5 = out["bias_m5"].to_numpy(int)

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

    f_mmxm_arr = out["f_mmxm"].to_numpy(bool)
    out["mmxm_directional_relation"] = np.select(
        [
            f_mmxm_arr & (d == 1) & (b_h1 == 1) & (b_m15 == 1),
            f_mmxm_arr & (d == -1) & (b_h1 == -1) & (b_m15 == -1),
            f_mmxm_arr & (d == 1) & (b_h1 == 1) & (b_m15 == -1),
            f_mmxm_arr & (d == -1) & (b_h1 == -1) & (b_m15 == 1),
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

    # Determine explicit Origin TF, Narrative TF, and Entry TF (Section 1)
    out["origin_tf"] = np.select(
        [out["pw_swept"], out["pd_swept"], out["tf"] == "H4", out["tf"] == "H1", out["tf"] == "M30", out["tf"] == "M15"],
        ["W1", "D1", "H4", "H1", "M30", "M15"],
        default=out["tf"],
    )
    out["narrative_tf"] = out["tf"]
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
            (out["tf"] == "H1") & out["cisd_m15"],
            (out["tf"] == "H4") & out["cisd_m1"],
            (out["tf"] == "H4") & out["cisd_m5"],
            (out["tf"] == "H4") & out["cisd_m15"],
        ],
        [
            "M1", "M3", "M5", "M1",
            "M1", "M3",
            "M1", "M3", "M5",
            "M5",
            "M1", "M5", "M15",
            "M1", "M5", "M15",
        ],
        default=out["tf"],
    )

    return out


# ---------------------------------------------------------------------------
# Phase 5: Target-Consistent Cross-Timeframe Target Engine (Sections 1, 2.4, 7 & P0.5)
# ---------------------------------------------------------------------------
def build_cross_timeframe_targets_and_outcomes(
    ctx: dict,
    cands: pd.DataFrame,
    horizon_bars: int = 360,
    slip: float = 0.25,
    universe_coverage: str = "FULL_UNIVERSE",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Evaluate all pre-existing structural targets across LOWER, EQUAL, and HIGHER timeframes
    with true target-consistent trade execution (`hpc.fast_target_exec_full_numba`) (P0.5).

    Separates:
      - `TARGET_HIT` (cleanly reached target before stop)
      - `STOP_HIT` (stop touched before target)
      - `AMBIGUOUS` (both SL and TP touched on same M1 bar; pessimistic stop-out PnL, separate status)
      - `TIMEOUT` (neither SL nor TP touched within `horizon_bars`; mark-to-market exit at horizon close, NEVER automatic -1R!)
      - `DATA_END` (neither SL nor TP touched before dataset end; mark-to-market exit at final close)
    """
    panel = ctx["panel"]
    traded = ctx["traded"]
    bh = panel[f"{traded}_h"].to_numpy(np.float64)
    bl = panel[f"{traded}_l"].to_numpy(np.float64)
    bc = panel[f"{traded}_c"].to_numpy(np.float64)
    ah = panel[f"{traded}_ah"].to_numpy(np.float64)
    al = panel[f"{traded}_al"].to_numpy(np.float64)
    ac = panel[f"{traded}_ac"].to_numpy(np.float64)

    n_c = len(cands)
    if n_c == 0:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    opp_ids = cands["opportunity_id"].to_numpy()
    uev_ids = cands["underlying_event_id"].to_numpy() if "underlying_event_id" in cands.columns else opp_ids
    day_ids = cands["ny_day_id"].to_numpy(np.int64) if "ny_day_id" in cands.columns else np.arange(n_c, dtype=np.int64)
    t_sig_arr = cands["t_signal_known"].to_numpy()
    j_fills = np.clip(cands["j_trig"].to_numpy(np.int64) + 1, 0, len(bh) - 1)
    dirs = cands["dir"].to_numpy(np.int64)
    ep_arr = cands["px_entry"].to_numpy(np.float64)
    sl_arr = cands["sl_init"].to_numpy(np.float64)
    atr_arr = cands["atr_ref"].fillna(15.0).to_numpy(np.float64)
    risk_arr = np.maximum(np.abs(ep_arr - sl_arr), 3.0)

    orig_tfs = cands["origin_tf"].to_numpy()
    narr_tfs = cands["narrative_tf"].to_numpy()
    mmxm_tfs = cands["mmxm_tf"].to_numpy()
    ent_tfs = cands["entry_tf"].to_numpy()
    hyp_type = cands["hypothesis_type"].to_numpy()
    q90_arr = cands["q90_trig"].to_numpy(np.int8)
    mmxm_flag = cands["f_mmxm"].to_numpy(bool)
    val_split = cands["validation_split"].to_numpy() if "validation_split" in cands.columns else np.array(["OOS_TEST"] * n_c)

    hr_arr = cands["Hr"].to_numpy(float) if "Hr" in cands.columns else cands["h"].to_numpy(float)
    lr_arr = cands["Lr"].to_numpy(float) if "Lr" in cands.columns else cands["l"].to_numpy(float)
    d1_h = cands["prev_h_d1"].to_numpy(float) if "prev_h_d1" in cands.columns else (cands["pdh"].to_numpy(float) if "pdh" in cands.columns else hr_arr)
    d1_l = cands["prev_l_d1"].to_numpy(float) if "prev_l_d1" in cands.columns else (cands["pdl"].to_numpy(float) if "pdl" in cands.columns else lr_arr)
    w1_h = cands["prev_h_w1"].to_numpy(float) if "prev_h_w1" in cands.columns else (cands["pwh"].to_numpy(float) if "pwh" in cands.columns else hr_arr)
    w1_l = cands["prev_l_w1"].to_numpy(float) if "prev_l_w1" in cands.columns else (cands["pwl"].to_numpy(float) if "pwl" in cands.columns else lr_arr)

    target_specs = [
        ("CRT_OPP_BOUNDARY", narr_tfs, np.where(dirs == 1, hr_arr, lr_arr)),
        ("M5_OC", np.array(["M5"] * n_c), cands["oc_target_m5"].to_numpy(float)),
        ("M15_OC", np.array(["M15"] * n_c), cands["oc_target_m15"].to_numpy(float)),
        ("H1_OC", np.array(["H1"] * n_c), cands["oc_target_h1"].to_numpy(float)),
        ("H4_OC", np.array(["H4"] * n_c), cands["oc_target_h4"].to_numpy(float)),
        ("M15_LIQ", np.array(["M15"] * n_c), np.where(dirs == 1, cands["prev_h_m15"].to_numpy(float), cands["prev_l_m15"].to_numpy(float))),
        ("H1_LIQ", np.array(["H1"] * n_c), np.where(dirs == 1, cands["prev_h_h1"].to_numpy(float), cands["prev_l_h1"].to_numpy(float))),
        ("H4_LIQ", np.array(["H4"] * n_c), np.where(dirs == 1, cands["prev_h_h4"].to_numpy(float), cands["prev_l_h4"].to_numpy(float))),
        ("D1_LIQ", np.array(["D1"] * n_c), np.where(dirs == 1, d1_h, d1_l)),
        ("W1_LIQ", np.array(["W1"] * n_c), np.where(dirs == 1, w1_h, w1_l)),
    ]

    cand_frames = []
    outcome_frames = []

    for tgt_type, tgt_tf_arr, tgt_px in target_specs:
        dist_pts = (tgt_px - ep_arr) * dirs
        dist_r = dist_pts / risk_arr
        dist_atr = dist_pts / np.maximum(atr_arr, 1.0)
        valid_mask = np.isfinite(tgt_px) & (dist_pts >= 3.0) & (dist_r >= 0.35) & (dist_r <= 25.0)
        valid_idx = np.nonzero(valid_mask)[0]
        if len(valid_idx) == 0:
            continue

        sub_jf = j_fills[valid_idx]
        sub_dir = dirs[valid_idx]
        sub_ep = ep_arr[valid_idx]
        sub_sl = sl_arr[valid_idx]
        sub_tp = tgt_px[valid_idx]

        m_len = len(valid_idx)
        reached_any = np.zeros(m_len, dtype=bool)
        reached_clean = np.zeros(m_len, dtype=bool)
        bars_to_tgt = np.full(m_len, -1, dtype=np.int64)
        out_code = np.zeros(m_len, dtype=np.int8)
        exit_j = np.full(m_len, -1, dtype=np.int64)
        exit_p = np.full(m_len, np.nan, dtype=np.float64)
        realized_r = np.full(m_len, np.nan, dtype=np.float64)
        mfe_r = np.zeros(m_len, dtype=np.float64)
        mae_r = np.zeros(m_len, dtype=np.float64)

        long_m = np.nonzero(sub_dir == 1)[0]
        if len(long_m) > 0:
            ra_l, rc_l, bt_l, oc_l, ej_l, ep_l, rr_l, mf_l, ma_l = hpc.fast_target_exec_full_numba(
                bh, bl, bc,
                sub_jf[long_m], sub_dir[long_m], sub_ep[long_m], sub_sl[long_m], sub_tp[long_m],
                horizon_bars, slip,
            )
            reached_any[long_m] = ra_l
            reached_clean[long_m] = rc_l
            bars_to_tgt[long_m] = bt_l
            out_code[long_m] = oc_l
            exit_j[long_m] = ej_l
            exit_p[long_m] = ep_l
            realized_r[long_m] = rr_l
            mfe_r[long_m] = mf_l
            mae_r[long_m] = ma_l

        short_m = np.nonzero(sub_dir == -1)[0]
        if len(short_m) > 0:
            ra_s, rc_s, bt_s, oc_s, ej_s, ep_s, rr_s, mf_s, ma_s = hpc.fast_target_exec_full_numba(
                ah, al, ac,
                sub_jf[short_m], sub_dir[short_m], sub_ep[short_m], sub_sl[short_m], sub_tp[short_m],
                horizon_bars, slip,
            )
            reached_any[short_m] = ra_s
            reached_clean[short_m] = rc_s
            bars_to_tgt[short_m] = bt_s
            out_code[short_m] = oc_s
            exit_j[short_m] = ej_s
            exit_p[short_m] = ep_s
            realized_r[short_m] = rr_s
            mfe_r[short_m] = mf_s
            mae_r[short_m] = ma_s

        sub_dist_pts = dist_pts[valid_idx]
        sub_dist_r = dist_r[valid_idx]
        sub_dist_atr = dist_atr[valid_idx]

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
        obstacles = np.where(sub_dist_atr <= 1.5, 0, np.where(sub_dist_atr <= 3.5, 1, 2))
        out_status = np.array([hpc.OUTCOME_CODE_TO_LABEL.get(int(c), "UNKNOWN") for c in out_code], dtype=object)

        t_cand_ids = [f"TC_{opp_ids[i]}_{tgt_type}" for i in valid_idx]
        cand_frames.append(pd.DataFrame({
            "target_candidate_id": t_cand_ids,
            "opportunity_id": opp_ids[valid_idx],
            "underlying_event_id": uev_ids[valid_idx],
            "ny_day_id": day_ids[valid_idx],
            "t_signal_known": t_sig_arr[valid_idx],
            "direction": np.where(sub_dir == 1, "LONG", "SHORT"),
            "dir": sub_dir.astype(np.int8),
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
            "universe_coverage": universe_coverage,
        }))

        outcome_frames.append(pd.DataFrame({
            "target_candidate_id": t_cand_ids,
            "opportunity_id": opp_ids[valid_idx],
            "underlying_event_id": uev_ids[valid_idx],
            "ny_day_id": day_ids[valid_idx],
            "validation_split": val_split[valid_idx],
            "direction": np.where(sub_dir == 1, "LONG", "SHORT"),
            "dir": sub_dir.astype(np.int8),
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
            "outcome_code": out_code,
            "outcome_status": out_status,
            "exit_bar_idx": exit_j,
            "exit_px": exit_p,
            "target_reached_horizon": reached_any,
            "trade_reached_before_stop": reached_clean,
            "reached_only_after_stop": reached_any & (~reached_clean),
            "bars_to_target": bars_to_tgt,
            "realized_net_r": realized_r,
            "mfe": mfe_r,
            "mae": mae_r,
            "hold": np.maximum(1, exit_j - sub_jf),
            "universe_coverage": universe_coverage,
        }))

    df_cands = pd.concat(cand_frames, ignore_index=True) if cand_frames else pd.DataFrame()
    df_out = pd.concat(outcome_frames, ignore_index=True) if outcome_frames else pd.DataFrame()

    if len(df_out) > 0:
        pred_summary = (
            df_out.groupby(
                ["direction", "narrative_tf", "entry_tf", "target_tf", "target_type", "tf_relation_to_narrative"],
                dropna=False,
            )
            .agg(
                n_evaluations=("opportunity_id", "size"),
                n_unique_opportunities=("opportunity_id", "nunique"),
                n_unique_days=("ny_day_id", "nunique"),
                mean_target_r=("distance_r", "mean"),
                prob_target_reached_horizon=("target_reached_horizon", "mean"),
                prob_trade_reached_before_stop=("trade_reached_before_stop", "mean"),
                prob_reached_after_stop=("reached_only_after_stop", "mean"),
                prob_target_hit=("outcome_status", lambda s: float((s == "TARGET_HIT").mean())),
                prob_stop_hit=("outcome_status", lambda s: float((s == "STOP_HIT").mean())),
                prob_ambiguous=("outcome_status", lambda s: float((s == "AMBIGUOUS").mean())),
                prob_timeout=("outcome_status", lambda s: float((s == "TIMEOUT").mean())),
                prob_data_end=("outcome_status", lambda s: float((s == "DATA_END").mean())),
                expectancy_net_r=("realized_net_r", "mean"),
                total_net_r=("realized_net_r", "sum"),
                median_bars_to_target=("bars_to_target", lambda s: float(s[s >= 0].median()) if (s >= 0).any() else np.nan),
            )
            .reset_index()
            .sort_values(["expectancy_net_r"], ascending=False)
            .reset_index(drop=True)
        )
        pred_summary["universe_coverage"] = universe_coverage
    else:
        pred_summary = pd.DataFrame()

    return df_cands, df_out, pred_summary


# ---------------------------------------------------------------------------
# P0.4 & P0.6: Independent Strategy Execution for Multi-TF CISD & 64 Combinations
# ---------------------------------------------------------------------------
def execute_strategy_at_custom_triggers(
    ctx: dict,
    base_df: pd.DataFrame,
    j_exec_arr: np.ndarray,
    rr_target: float = 2.0,
    horizon_bars: int = 360,
    slip_pts: float = 0.25,
) -> pd.DataFrame:
    """Execute a strategy cohort where each candidate row enters at its OWN causal trigger bar `j_exec_arr[i]`
    (`j_fill = j_exec_arr[i] + 1`), with its own next-bar open fill price, structural stop-loss known at `j_exec`,
    and target-consistent outcome (`TARGET_HIT`, `STOP_HIT`, `AMBIGUOUS`, `TIMEOUT`, `DATA_END`) (P0.4 & P0.5).
    """
    panel = ctx["panel"]
    traded = ctx["traded"]
    idx = panel.index
    n_m1 = len(idx)

    bo = panel[f"{traded}_o"].to_numpy(np.float64)
    bh = panel[f"{traded}_h"].to_numpy(np.float64)
    bl = panel[f"{traded}_l"].to_numpy(np.float64)
    bc = panel[f"{traded}_c"].to_numpy(np.float64)
    ao = panel[f"{traded}_ao"].to_numpy(np.float64)
    ah = panel[f"{traded}_ah"].to_numpy(np.float64)
    al = panel[f"{traded}_al"].to_numpy(np.float64)
    ac = panel[f"{traded}_ac"].to_numpy(np.float64)

    valid_m = (j_exec_arr >= 0) & (j_exec_arr + 1 < n_m1)
    valid_idx = np.nonzero(valid_m)[0]
    if len(valid_idx) == 0:
        return base_df.iloc[0:0].copy()

    sub = base_df.iloc[valid_idx].copy().reset_index(drop=True)
    j_ex = j_exec_arr[valid_idx].astype(np.int64)
    j_fl = j_ex + 1
    dirs = sub["dir"].to_numpy(np.int64)

    # Executable fill price at j_fill (Ask Open + slip for LONG, Bid Open - slip for SHORT)
    ep = np.where(dirs == 1, ao[j_fl] + slip_pts, bo[j_fl] - slip_pts)

    # Causal structural stop-loss known at j_exec: sweep extreme / reference extreme + buffer
    sl_base = sub["sl_init"].to_numpy(np.float64)
    atr_ref = sub["atr_ref"].fillna(15.0).to_numpy(np.float64)
    # If price moved between base j_trig and j_exec, ensure stop is causally valid relative to ep
    sl_px = np.where(
        dirs == 1,
        np.minimum(sl_base, bl[j_ex] - 0.15 * atr_ref),
        np.maximum(sl_base, bh[j_ex] + 0.15 * atr_ref),
    )
    risk = np.maximum(np.abs(ep - sl_px), 3.0)
    sl_px = np.where(dirs == 1, ep - risk, ep + risk)
    tp_px = np.where(dirs == 1, ep + rr_target * risk, ep - rr_target * risk)

    m_len = len(sub)
    out_code = np.zeros(m_len, dtype=np.int8)
    exit_j = np.full(m_len, -1, dtype=np.int64)
    exit_p = np.full(m_len, np.nan, dtype=np.float64)
    realized_r = np.full(m_len, np.nan, dtype=np.float64)
    mfe_r = np.zeros(m_len, dtype=np.float64)
    mae_r = np.zeros(m_len, dtype=np.float64)

    long_m = np.nonzero(dirs == 1)[0]
    if len(long_m) > 0:
        _, _, _, oc_l, ej_l, ep_l, rr_l, mf_l, ma_l = hpc.fast_target_exec_full_numba(
            bh, bl, bc,
            j_fl[long_m], dirs[long_m], ep[long_m], sl_px[long_m], tp_px[long_m],
            horizon_bars, slip_pts,
        )
        out_code[long_m] = oc_l
        exit_j[long_m] = ej_l
        exit_p[long_m] = ep_l
        realized_r[long_m] = rr_l
        mfe_r[long_m] = mf_l
        mae_r[long_m] = ma_l

    short_m = np.nonzero(dirs == -1)[0]
    if len(short_m) > 0:
        _, _, _, oc_s, ej_s, ep_s, rr_s, mf_s, ma_s = hpc.fast_target_exec_full_numba(
            ah, al, ac,
            j_fl[short_m], dirs[short_m], ep[short_m], sl_px[short_m], tp_px[short_m],
            horizon_bars, slip_pts,
        )
        out_code[short_m] = oc_s
        exit_j[short_m] = ej_s
        exit_p[short_m] = ep_s
        realized_r[short_m] = rr_s
        mfe_r[short_m] = mf_s
        mae_r[short_m] = ma_s

    m1_close_idx = idx + pd.Timedelta(minutes=1)
    sub["j_trig"] = j_ex
    sub["j_confirm"] = j_ex
    sub["j_fill"] = j_fl
    sub["t_signal_known"] = m1_close_idx[j_ex]
    sub["t_confirm_available"] = sub["t_signal_known"]
    sub["t_fill"] = idx[j_fl]
    sub["j_exit"] = exit_j
    exit_times = pd.Series(pd.NaT, index=sub.index, dtype=m1_close_idx.dtype)
    valid_exits = exit_j >= 0
    exit_times.loc[valid_exits] = m1_close_idx[exit_j[valid_exits]]
    sub["t_exit"] = exit_times
    sub["px_entry"] = ep
    sub["sl_init"] = sl_px
    sub["tp_init"] = tp_px
    sub["px_exit"] = exit_p
    sub["outcome_code"] = out_code
    sub["outcome_status"] = [hpc.OUTCOME_CODE_TO_LABEL.get(int(c), "UNKNOWN") for c in out_code]
    sub["r"] = realized_r
    sub["mfe"] = mfe_r
    sub["mae"] = mae_r
    sub["hold"] = np.maximum(1, exit_j - j_fl)
    return sub


# ---------------------------------------------------------------------------
# Phase 6: Causal Narrative Graph & Pre-Trade Narratives (Sections 5, 11 & P1.8)
# ---------------------------------------------------------------------------
def build_narrative_graph_and_snapshots(
    cands: pd.DataFrame,
    target_candidates: pd.DataFrame,
    universe_coverage: str = "FULL_UNIVERSE",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build `fractal_narrative_graph.parquet`, `pretrade_narratives.parquet` (100% causal pre-trade),
    and `posttrade_outcomes.parquet` (post-trade outcomes kept strictly separate per P1.8).
    """
    if len(cands) == 0:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    has_mmxm = cands["f_mmxm"].to_numpy(bool)
    has_ssmt = (cands["macro_ssmt"] | cands["micro_ssmt"]).to_numpy(bool)
    has_cisd_any = (
        cands["cisd_m1"] | cands["cisd_m3"] | cands["cisd_m5"] | cands["cisd_m15"]
        | cands.get("cisd_m30", False) | cands.get("cisd_h1", False) | cands.get("cisd_h4", False)
    ).to_numpy(bool)

    seq_label = np.select(
        [
            has_mmxm & has_ssmt & has_cisd_any,
            has_mmxm & (~has_ssmt) & has_cisd_any,
            (~has_mmxm) & has_ssmt & has_cisd_any,
            has_ssmt & (~has_cisd_any),
            cands["A"].to_numpy(bool),
        ],
        [
            "Liquidity_Sweep -> MMXM_Stage -> QT_SSMT -> CISD -> Target",
            "Liquidity_Sweep -> MMXM_Stage -> CISD (No_SSMT) -> Target",
            "Liquidity_Sweep -> CRT -> QT_SSMT -> CISD -> Target",
            "Liquidity_Sweep -> CRT_Confirmed -> SSMT",
            "Liquidity_Sweep -> CRT_Confirmed",
        ],
        default="Liquidity_Sweep -> Structural_Trigger",
    )

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

    # Select best pre-existing target strictly from PRE-TRADE `target_candidates` (P1.8)
    best_tgt_map: dict[str, dict[str, Any]] = {}
    if len(target_candidates) > 0:
        sub_t = target_candidates[target_candidates["distance_r"] >= 1.2].sort_values(["opportunity_id", "distance_r"])
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

    # P1.8: `pretrade_narratives.parquet` contains ZERO post-trade fields!
    pretrade_df = pd.DataFrame({
        "opportunity_id": cands["opportunity_id"],
        "underlying_event_id": cands.get("underlying_event_id", cands["opportunity_id"]),
        "ny_day_id": cands.get("ny_day_id", 0),
        "t_signal_known": cands["t_signal_known"],
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
        "mmxm_id": cands.get("mmxm_id", "NONE"),
        "mmxm_tf": cands["mmxm_tf"],
        "target_tf": tgt_tf_list,
        "temporal_sequence": seq_label,
        "narrative_archetype": narrative_archetype,
        "mmxm_directional_relation": cands["mmxm_directional_relation"],
        "universe_coverage": universe_coverage,
    })

    # Separate post-trade outcome table (P1.8)
    posttrade_df = pd.DataFrame({
        "opportunity_id": cands["opportunity_id"],
        "t_fill": cands["t_fill"],
        "px_entry": cands["px_entry"],
        "px_exit": cands["px_exit"],
        "realized_r": cands["r"],
        "mfe_r": cands["mfe"],
        "mae_r": cands["mae"],
        "hold_min": cands["hold"],
        "validation_split": cands.get("validation_split", "OOS_TEST"),
    })

    # Vectorized edge construction for `fractal_narrative_graph.parquet` (Section 11)
    oids = pretrade_df["opportunity_id"].astype(str).to_numpy()
    ts_arr = pretrade_df["t_signal_known"].to_numpy()
    seq_arr = pretrade_df["temporal_sequence"].astype(str).to_numpy()

    n_p = len(pretrade_df)
    e1_id = [f"EDGE_{oid}_1" for oid in oids]
    e1_src = (pretrade_df["q01_origin_tf"].astype(str) + ":" + pretrade_df["q02_liquidity_pool"].astype(str)).to_numpy()
    e1_rel = np.where(pretrade_df["q03_interaction_class"].astype(str).str.contains("Sweep"), "swept", "approached")
    e1_tgt = pretrade_df["q05_mmxm_stage_observable"].astype(str).to_numpy()

    e2_id = [f"EDGE_{oid}_2" for oid in oids]
    e2_src = (pretrade_df["q07_active_qt_phases"].astype(str) + "|" + pretrade_df["q09_ssmt_state"].astype(str)).to_numpy()
    e2_rel = np.where(pretrade_df["q09_ssmt_state"].astype(str) != "Conflict", "confirms", "contradicts")
    q11_s = pretrade_df["q11_cisd_timeframes"].astype(str)
    e2_tgt = np.where(q11_s != "", q11_s, "NO_CISD")

    e3_id = [f"EDGE_{oid}_3" for oid in oids]
    e3_src = (pretrade_df["q12_executable_entry_tf"].astype(str) + ":" + pretrade_df["direction"].astype(str)).to_numpy()
    e3_tgt = (
        pretrade_df["target_tf"].astype(str) + ":" + pretrade_df["q13_known_target_type"].astype(str)
        + " (" + pretrade_df["q14_target_tf_relation"].astype(str) + ")"
    ).to_numpy()

    graph_df = pd.DataFrame({
        "edge_id": np.concatenate([e1_id, e2_id, e3_id]),
        "opportunity_id": np.concatenate([oids, oids, oids]),
        "source_node_type": np.concatenate([
            np.repeat("Liquidity", n_p),
            np.repeat("QT_SSMT_Context", n_p),
            np.repeat("Entry", n_p),
        ]),
        "source_node_label": np.concatenate([e1_src, e2_src, e3_src]),
        "relation": np.concatenate([e1_rel, e2_rel, np.repeat("targets", n_p)]),
        "target_node_type": np.concatenate([
            np.repeat("MMXM_Stage", n_p),
            np.repeat("CISD", n_p),
            np.repeat("Target", n_p),
        ]),
        "target_node_label": np.concatenate([e1_tgt, e2_tgt, e3_tgt]),
        "t_known": np.concatenate([ts_arr, ts_arr, ts_arr]),
        "sequence_pattern": np.concatenate([seq_arr, seq_arr, seq_arr]),
        "universe_coverage": universe_coverage,
    })
    return graph_df, pretrade_df, posttrade_df
