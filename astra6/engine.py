"""Master Research & Experiment Pipeline for ASTRA 6 (Sections 1–15, 20).

Runs the chronological event-driven signal extractor and trade simulator across
the 5-year historical CFD dataset (7 Nov 2021 – 7 Nov 2026) and persists all
tables into ``data/results/`` for the dashboard, reports, and QA verification.
"""
from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl

from . import bars, clock, crt, ict, opening, signals, sim, smt, stats

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "data" / "store"
RESULTS = ROOT / "data" / "results"

RR_LIST = [1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0]


def _sim_df(
    ctx: dict,
    df: pd.DataFrame,
    rr: float = 2.0,
    stop_col: str = "sweep_ext_known",
    exit_model: int = sim.EX_FIXED,
    max_hold: int = 360,
    slip: float = 0.25,
    stop_buffer: float = 1.5,
    non_overlap: bool = False,
    target_col: str | None = None,
) -> pd.DataFrame:
    """Run ``sim.sim_batch`` on a candidate DataFrame and return a copy with trade results."""
    if len(df) == 0:
        return df.assign(r=np.nan, mfe=np.nan, mae=np.nan, hold=0, j_exit=-1, px_entry=np.nan, px_exit=np.nan)
    panel = ctx["panel"]
    traded = ctx["traded"]
    bo = panel[f"{traded}_o"].to_numpy(float)
    bh = panel[f"{traded}_h"].to_numpy(float)
    bl = panel[f"{traded}_l"].to_numpy(float)
    bc = panel[f"{traded}_c"].to_numpy(float)
    ao = panel[f"{traded}_ao"].to_numpy(float)
    ah = panel[f"{traded}_ah"].to_numpy(float)
    al = panel[f"{traded}_al"].to_numpy(float)
    ac = panel[f"{traded}_ac"].to_numpy(float)

    je = df["j_trig"].to_numpy(np.int64)
    d = df["dir"].to_numpy(np.int64)
    raw_sl = df[stop_col].to_numpy(float)
    sl0 = np.where(d == -1, raw_sl + stop_buffer, raw_sl - stop_buffer)
    ep_est = np.where(d == 1, ac[je] + slip, bc[je] - slip)
    risk = np.where(d == 1, ep_est - sl0, sl0 - ep_est)
    # enforce reasonable minimum structural risk (at least 3.0 pts on US100)
    min_r = np.maximum(3.0, 0.25 * df["atr_ref"].fillna(12.0).to_numpy(float))
    too_tight = risk < min_r
    sl0 = np.where(too_tight & (d == 1), ep_est - min_r, np.where(too_tight & (d == -1), ep_est + min_r, sl0))
    risk = np.where(d == 1, ep_est - sl0, sl0 - ep_est)

    if target_col is not None and target_col in df.columns:
        tp0 = df[target_col].to_numpy(float)
    else:
        tp0 = np.where(d == 1, ep_est + rr * risk, ep_est - rr * risk)

    sw = ctx["sw_m5"]
    sw_j = sw["j_known"].to_numpy(np.int64)
    sw_p = sw["price"].to_numpy(float)
    sw_hi = (sw["kind"] == "H").to_numpy(bool)

    r_out, mfe, mae, hold, j_ex, px_en, px_ex, n_mod, ambig, reason = sim.sim_batch(
        bo, bh, bl, bc, ao, ah, al, ac,
        je, d, sl0, tp0,
        exit_model, max_hold, slip, 1.0,
        sw_j, sw_p, sw_hi,
    )
    out = df.copy()
    out["r"] = r_out
    out["mfe"] = mfe
    out["mae"] = mae
    out["hold"] = hold
    out["j_exit"] = j_ex
    out["px_entry"] = px_en
    out["px_exit"] = px_ex
    out["sl_init"] = sl0
    out["tp_init"] = tp0
    out["n_mod"] = n_mod
    out["ambig"] = ambig
    out["exit_reason"] = reason
    out = out[out["r"].notna()].reset_index(drop=True)
    if non_overlap and len(out) > 0:
        out = out.sort_values("j_trig").reset_index(drop=True)
        keep = sim.filter_non_overlapping(out["j_trig"].to_numpy(np.int64), out["j_exit"].to_numpy(np.int64))
        out = out[keep].reset_index(drop=True)
    return out


def _add_mtf_cisd_and_nested(ctx: dict, df: pd.DataFrame, h1_events: pd.DataFrame | None = None) -> pd.DataFrame:
    """Attach M3 and M5 CISD flags, CRT-G/I/L flags, SSMT stop, and failed_breakout narrative."""
    if len(df) == 0:
        return df
    out = df.copy()
    panel = ctx["panel"]
    traded = ctx["traded"]
    h = panel[f"{traded}_h"].to_numpy(float)
    l = panel[f"{traded}_l"].to_numpy(float)
    c = panel[f"{traded}_c"].to_numpy(float)
    o = panel[f"{traded}_o"].to_numpy(float)

    # M3 and M5 CISD approximation (causal at j_trig): requires M1 CISD plus 3-min / 5-min opposing close displacement
    jt = out["j_trig"].to_numpy(int)
    jsw = np.maximum(out["j_sweep"].to_numpy(int), out["j_open"].to_numpy(int))
    d = out["dir"].to_numpy(int)
    j3 = np.maximum(0, jt - 3)
    j5 = np.maximum(0, jt - 5)
    out["cisd_m1"] = out["has_cisd"]
    out["cisd_m3"] = out["has_cisd"] & np.where(d == -1, c[jt] < np.minimum(o[j3], c[j3]), c[jt] > np.maximum(o[j3], c[j3]))
    out["cisd_m5"] = out["has_cisd"] & np.where(d == -1, c[jt] < np.minimum(o[j5], c[j5]), c[jt] > np.maximum(o[j5], c[j5]))

    # CRT-G (Sweep + LTF CISD) and CRT-I (Wick rejection / early reclaim)
    out["G"] = out["sw"] & out["has_cisd"] & ~out["ot"]
    out["I"] = out["sw"] & (out["j_reclaim"] >= 0) & ~out["ot"]

    # CRT-L: Nested M15 inside an active or just-closed H1 CRT sweep in the same direction (vectorised via searchsorted)
    if h1_events is not None and len(h1_events) > 0:
        nested = np.zeros(len(out), dtype=bool)
        for di in (-1, 1):
            ref_h1 = h1_events[(h1_events["dir"] == di) & (h1_events["j_sweep"] >= 0)].sort_values("j_open")
            if len(ref_h1) == 0:
                continue
            ho = ref_h1["j_open"].to_numpy(np.int64)
            hc = ref_h1["j_close"].to_numpy(np.int64)
            hsw = ref_h1["j_sweep"].to_numpy(np.int64)
            mask_d = np.nonzero(d == di)[0]
            t_sub = jt[mask_d]
            pos = np.searchsorted(ho, t_sub, side="right") - 1
            for k_off in (0, -1):
                p = np.clip(pos + k_off, 0, len(ho) - 1)
                ok = (pos + k_off >= 0) & (ho[p] <= t_sub) & (hsw[p] <= t_sub) & (hc[p] + 15 >= t_sub)
                nested[mask_d[ok]] = True
        out["L"] = nested & out["A"]
    else:
        out["L"] = False

    # SSMT sweep extreme stop (causal extreme since micro/macro SSMT formation up to j_trig)
    ssmt_stop = np.copy(out["sweep_ext_known"].to_numpy(float))
    jform = np.where(out["micro_ssmt"], out["micro_jform"], np.where(out["macro_ssmt"], out["macro_jform"], jsw))
    for i in range(len(out)):
        a = int(max(0, min(jform[i], jsw[i])))
        b = int(jt[i])
        if b >= a:
            ssmt_stop[i] = crt.running_extreme(h, l, a, b, d[i] == -1)
    out["ssmt_stop"] = ssmt_stop

    # Opposing range target & midpoint target
    out["mid_target"] = 0.5 * (out["Hr"] + out["Lr"])
    out["opp_range_target"] = np.where(d == -1, out["Lr"], out["Hr"])

    # Enrich narrative with failed_breakout when PDH/PDL or OR15 is swept and reclaimed without HTF trend continuation
    fb = (out["pd_swept"] | out["pw_swept"]) & ~out["has_cisd"] & out["A"]
    out["narrative"] = np.where(fb, "failed_breakout", out["narrative"])
    return out


def verify_30s_micro_quarters() -> dict:
    """Section 1 & 6: Verify 22.5M micro-quarter SSMT on exact 30-second bars
    (where 22.5M = 45 x 30s is exact to the second) vs 1-minute bars on Dukascopy data."""
    d100_30s = pl.read_parquet(STORE / "DUKA_US100_30S.parquet")
    d500_30s = pl.read_parquet(STORE / "DUKA_US500_30S.parquet")
    # Evaluate on a 6-month recent window (2025-11 .. 2026-05) for exact 30S vs 1M comparison
    sub100 = d100_30s.filter(pl.col("ts") >= pl.datetime(2025, 11, 1, time_zone="UTC")).to_pandas()
    sub500 = d500_30s.filter(pl.col("ts") >= pl.datetime(2025, 11, 1, time_zone="UTC")).to_pandas()
    p30 = (
        sub100.set_index("ts")[["open", "high", "low", "close"]]
        .rename(columns={"open": "US100_o", "high": "US100_h", "low": "US100_l", "close": "US100_c"})
        .join(
            sub500.set_index("ts")[["open", "high", "low", "close"]].rename(
                columns={"open": "US500_o", "high": "US500_h", "low": "US500_l", "close": "US500_c"}
            ),
            how="inner",
        )
    )
    # Exact 1350-second (22.5M) quarter labels on 30S timestamps
    sec = bars.ny_wall_seconds(p30.index).astype(np.float64) - bars.CYCLE_ORIGIN * 60.0
    ql30 = pd.DataFrame({
        "b90": np.floor(sec / 5400.0).astype(np.int64),
        "b22": np.floor(sec / 1350.0).astype(np.int64),
        "q90": (np.mod(np.floor(sec / 5400.0), 4) + 1).astype(np.int8),
        "q22": (np.mod(np.floor(sec / 1350.0), 4) + 1).astype(np.int8),
    }, index=p30.index)
    ev30 = smt.ssmt_events(p30, ql30, "US100", "US500", "micro")

    # Compare with 1M on the exact same date range
    p1m = p30.resample("1min").agg({
        "US100_o": "first", "US100_h": "max", "US100_l": "min", "US100_c": "last",
        "US500_o": "first", "US500_h": "max", "US500_l": "min", "US500_c": "last",
    }).dropna()
    ql1m = bars.quarter_labels(p1m.index)
    ev1m = smt.ssmt_events(p1m, ql1m, "US100", "US500", "micro")

    # Concordance of (b_trig, dir, lead) events between 30S-exact and 1M
    set30 = set(zip(ev30["b_trig"], ev30["q_ref"], ev30["q_trig"], ev30["dir"], ev30["lead"]))
    set1m = set(zip(ev1m["b_trig"], ev1m["q_ref"], ev1m["q_trig"], ev1m["dir"], ev1m["lead"]))
    overlap = len(set30 & set1m) / max(1, len(set30 | set1m))
    return {
        "window": "2025-11-01 .. 2026-05-24",
        "n_30s_bars": int(len(p30)),
        "n_1m_bars": int(len(p1m)),
        "n_micro_ssmt_30s_exact": int(len(ev30)),
        "n_micro_ssmt_1m_approx": int(len(ev1m)),
        "jaccard_concordance": float(overlap),
    }


def run_all():
    t0 = time.time()
    RESULTS.mkdir(parents=True, exist_ok=True)
    print("[ENGINE] Loading 5-year 3-symbol M1 panel...", flush=True)
    panel = bars.load_panel(("US100", "US500", "US30"), with_ask=True)
    print(f"[ENGINE] Panel loaded: {len(panel):,} M1 bars [{panel.index.min()} .. {panel.index.max()}]", flush=True)

    ctx = signals.build_context(panel, traded="US100", comps=("US500", "US30"))
    print(f"[ENGINE] Context built in {time.time()-t0:.1f}s (Macro SSMT={len(ctx['ssmt_mac']):,}, Micro SSMT={len(ctx['ssmt_mic']):,})", flush=True)

    # 1. All 14 Timeframe summary stats (Section 1)
    tf_rows = []
    for tf_name in ("M1", "M2", "M3", "M5", "M10", "M15", "M30", "M45", "H1", "M90", "H4", "H6", "D1"):
        b = bars.resample(panel, "US100", tf_name, "cal") if tf_name != "M1" else pd.DataFrame({
            "o": panel["US100_o"], "h": panel["US100_h"], "l": panel["US100_l"], "c": panel["US100_c"],
            "t_open": panel.index, "t_close": panel.index + pd.Timedelta(minutes=1), "complete": True,
        })
        rng = (b["h"] - b["l"]).to_numpy(float)
        tf_rows.append({
            "timeframe": tf_name, "minutes": bars.TF_MIN[tf_name], "n_bars": int(len(b)),
            "mean_range_pts": float(np.nanmean(rng)), "median_range_pts": float(np.nanmedian(rng)),
            "p90_range_pts": float(np.nanpercentile(rng, 90)),
        })
    # Add Weekly
    d1c = ctx["d1"][ctx["d1"]["complete"]].copy()
    wk = pd.to_datetime(d1c["t_open"]).dt.tz_convert(clock.NY).dt.tz_localize(None).dt.to_period("W")
    wb = d1c.groupby(wk).agg(o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"))
    wrng = (wb["h"] - wb["l"]).to_numpy(float)
    tf_rows.append({
        "timeframe": "W1", "minutes": 10080, "n_bars": int(len(wb)),
        "mean_range_pts": float(np.nanmean(wrng)), "median_range_pts": float(np.nanmedian(wrng)),
        "p90_range_pts": float(np.nanpercentile(wrng, 90)),
    })
    pd.DataFrame(tf_rows).to_parquet(RESULTS / "tf_summary.parquet", index=False)

    # 2. Extract CRT events across mandatory timeframes (M5, M15, M30, H1, H4) + NY930 H1 anchor
    raw_crt: dict[tuple[str, str], pd.DataFrame] = {}
    for tf_name in ("M5", "M15", "M30", "H1", "H4"):
        raw_crt[(tf_name, "cal")] = signals.extract_crt_events(ctx, tf=tf_name, anchor="cal")
    raw_crt[("H1", "ny930")] = signals.extract_crt_events(ctx, tf="H1", anchor="ny930")
    raw_crt[("M15", "ny930")] = signals.extract_crt_events(ctx, tf="M15", anchor="ny930")

    # Opening ranges (NY & London)
    or_ny = opening.compute_opening_ranges(panel, "US100", "NY")
    or_ldn = opening.compute_opening_ranges(panel, "US100", "LDN")
    or_ny.to_parquet(RESULTS / "opening_ranges_ny.parquet", index=False)
    or_ldn.to_parquet(RESULTS / "opening_ranges_ldn.parquet", index=False)

    # Materialize candidate tables (confirmed, confirmed_cisd, dev_cisd, dev_reclaim, confirmed_next)
    h1_cal_raw = raw_crt[("H1", "cal")]
    cands: dict[tuple[str, str, str], pd.DataFrame] = {}
    for (tf_name, anc), ev_df in raw_crt.items():
        for mode in ("confirmed", "confirmed_cisd", "dev_cisd", "dev_reclaim", "confirmed_next"):
            if anc == "ny930" and mode not in ("confirmed", "dev_cisd", "confirmed_cisd"):
                continue
            m_df = signals.materialize_entries(ctx, ev_df, mode=mode)
            m_df = _add_mtf_cisd_and_nested(ctx, m_df, h1_cal_raw if tf_name == "M15" else None)
            m_df = opening.attach_causal_or_to_signals(m_df, or_ny, "NY")
            m_df = opening.attach_causal_or_to_signals(m_df, or_ldn, "LDN")
            m_df = _sim_df(ctx, m_df, rr=2.0, stop_col="sweep_ext_known", exit_model=sim.EX_FIXED, slip=0.25)
            cands[(tf_name, anc, mode)] = m_df

    print(f"[ENGINE] Candidate tables materialized & simulated in {time.time()-t0:.1f}s", flush=True)

    # 3. Section 4.5 Mandatory CRT Timeframe Stats (Confirmed CRT-A at 2R)
    crt_tf_rows = []
    for tf_name in ("M5", "M15", "M30", "H1", "H4"):
        ev_df = raw_crt[(tf_name, "cal")]
        sim_a = cands[(tf_name, "cal", "confirmed")]
        sim_a = sim_a[sim_a["A"]].copy()
        s = stats.summarize_trades(sim_a, n_boot=800)
        # Reversal probability = fraction of trades whose MFE >= 1.0R (and >= 2.0R)
        rev_1r = float((sim_a["mfe"] >= 1.0).mean()) if len(sim_a) else np.nan
        rev_2r = float((sim_a["mfe"] >= 2.0).mean()) if len(sim_a) else np.nan
        conf_time_min = float((sim_a["j_close"] - sim_a["j_sweep"]).mean()) if len(sim_a) else np.nan
        crt_tf_rows.append({
            "tf": tf_name,
            "total_sweeps": int(len(ev_df)),
            "crt_a_count": s["n_trades"],
            "mean_sweep_depth_pts": float(sim_a["sweep_depth"].mean()),
            "mean_return_depth_pts": float(sim_a["return_depth"].mean()),
            "mean_body_pos": float(sim_a["body_pos"].mean()),
            "median_wick_body_ratio": float(sim_a["wick_body_ratio"].median()),
            "mean_sweep_atr": float(sim_a["sweep_atr"].mean()),
            "mean_confirm_wait_min": conf_time_min,
            "prob_mfe_1r": rev_1r,
            "prob_mfe_2r": rev_2r,
            **s,
        })
    pd.DataFrame(crt_tf_rows).to_parquet(RESULTS / "crt_tf_stats.parquet", index=False)

    # 4. Section 4.4 All 12 CRT Variants (CRT-A .. CRT-L) on M15 and H1
    var_rows = []
    for tf_name in ("M15", "H1"):
        df_conf = cands[(tf_name, "cal", "confirmed")]
        df_next = cands[(tf_name, "cal", "confirmed_next")]
        df_dev_cisd = cands[(tf_name, "cal", "dev_cisd")]
        df_dev_rec = cands[(tf_name, "cal", "dev_reclaim")]
        variants = [
            ("CRT-A (Sweep + Close Inside)", df_conf[df_conf["A"]]),
            ("CRT-B (Sweep + Entire Body Inside)", df_conf[df_conf["B"]]),
            ("CRT-C (Sweep + Strong Opposing Body)", df_conf[df_conf["C"]]),
            ("CRT-D (Sweep + Close Beyond Midpoint)", df_conf[df_conf["D"]]),
            ("CRT-E (Sweep + Displacement Confirm)", df_conf[df_conf["E"]]),
            ("CRT-F (Sweep + Next Candle Confirm)", df_next),
            ("CRT-G (Sweep + LTF M1 CISD)", df_dev_cisd),
            ("CRT-H (Two-Candle Sweep & Reclaim)", df_conf[df_conf["H"]]),
            ("CRT-I (Wick Reclaim Early Entry, No Close Confirm)", df_dev_rec),
            ("CRT-J (One-Sided Sweep Only, Any Close)", df_conf[df_conf["J"]]),
            ("CRT-K (Both-Side Sweep Separate Class)", df_conf[df_conf["K"]]),
            ("CRT-L (Nested M15 inside H1 CRT)" if tf_name == "M15" else "CRT-L (H1 CRT with M15 CISD)",
             df_conf[df_conf["L"]] if tf_name == "M15" else df_conf[df_conf["A"] & df_conf["cisd_m5"]]),
        ]
        for vname, sub in variants:
            m = stats.summarize_trades(sub, n_boot=600)
            var_rows.append({"tf": tf_name, "variant": vname, **m})
            # Also in NY Open session (09:30-11:00 NY)
            sub_ny = sub[(sub["min_from_ny_open_trig"] >= 0) & (sub["min_from_ny_open_trig"] <= 90)]
            m_ny = stats.summarize_trades(sub_ny, n_boot=600)
            var_rows.append({"tf": f"{tf_name}_NY_OPEN", "variant": vname, **m_ny})
    pd.DataFrame(var_rows).to_parquet(RESULTS / "crt_variants.parquet", index=False)

    # 5. Section 4.6 Confirmed vs Developing Entry Models (M15 & H1, full & NY session & with SSMT)
    close_vs_dev = []
    for tf_name in ("M15", "H1"):
        for mode_label, mode_key, filt_a in [
            (f"Confirmed {tf_name} CRT Entry", "confirmed", True),
            (f"Confirmed {tf_name} CRT + M1 CISD Entry", "confirmed_cisd", True),
            (f"Developing {tf_name} CRT + M1 CISD Entry", "dev_cisd", False),
            (f"Developing {tf_name} CRT Wick Reclaim (No CISD)", "dev_reclaim", False),
        ]:
            base_df = cands[(tf_name, "cal", mode_key)]
            if filt_a and "A" in base_df.columns:
                base_df = base_df[base_df["A"]]
            for scope, mask in [
                ("All Sessions", pd.Series(True, index=base_df.index)),
                ("NY Open (09:30-11:00)", (base_df["min_from_ny_open_trig"] >= 0) & (base_df["min_from_ny_open_trig"] <= 90)),
                ("NY Open + SSMT", (base_df["min_from_ny_open_trig"] >= 0) & (base_df["min_from_ny_open_trig"] <= 90) & base_df["any_ssmt"]),
            ]:
                s = stats.summarize_trades(base_df[mask], n_boot=800)
                close_vs_dev.append({"tf": tf_name, "model": mode_label, "scope": scope, **s})
    pd.DataFrame(close_vs_dev).to_parquet(RESULTS / "crt_closing_vs_dev.parquet", index=False)

    # 6. Section 5.4 Baseline Comparisons A..J (Full & NY Session, on M15 and H1)
    base_rows = []
    hypothesis_tests = []
    for tf_name in ("M15", "H1"):
        # Combine confirmed CRT-A and developing CRT+CISD pool on confirmed CRT-A base
        df_c = cands[(tf_name, "cal", "confirmed")]
        df_a = df_c[df_c["A"]].copy()
        for scope_name, sc_mask in [
            ("All_Sessions", pd.Series(True, index=df_a.index)),
            ("NY_Open_0930_1100", (df_a["min_from_ny_open_trig"] >= 0) & (df_a["min_from_ny_open_trig"] <= 90)),
            ("London_Open_0800_0930", (df_a["min_from_ldn_open_trig"] >= 0) & (df_a["min_from_ldn_open_trig"] <= 90)),
        ]:
            sub = df_a[sc_mask].copy()
            qt_manip_dist = sub["q90_trig"].isin([2, 3]) & sub["q22_trig"].isin([2, 3])
            models = {
                "A. CRT only": sub,
                "B. CRT + Standard SMT": sub[sub["std_smt"]],
                "C. CRT + 90M SSMT": sub[sub["macro_ssmt"]],
                "D. CRT + 22.5M SSMT": sub[sub["micro_ssmt"]],
                "E. CRT + CISD": sub[sub["has_cisd"]],
                "F. CRT + SSMT + CISD": sub[sub["any_ssmt"] & sub["has_cisd"]],
                "G. CRT + SSMT + CISD + HTF Liquidity": sub[sub["any_ssmt"] & sub["has_cisd"] & (sub["htf_liq"] | sub["pd_zone_ok"])],
                "H. CRT + SSMT + CISD + MMXM": sub[sub["any_ssmt"] & sub["has_cisd"] & sub["mmxm"]],
                "I. CRT + SSMT + CISD + QT Phase (Q2/Q3)": sub[sub["any_ssmt"] & sub["has_cisd"] & qt_manip_dist],
                "J. Full Combination (CRT+SSMT+CISD+MMXM+QT+HTF)": sub[
                    sub["any_ssmt"] & sub["has_cisd"] & sub["mmxm"] & qt_manip_dist & (sub["narrative"] != "contradictory")
                ],
            }
            for mname, mdf in models.items():
                s = stats.summarize_trades(mdf, n_boot=800)
                base_rows.append({"tf": tf_name, "scope": scope_name, "strategy": mname, **s})

            # Formal statistical comparisons: F vs A, D vs A, H vs F, J vs F
            for t_name, b_name in [
                ("F. CRT + SSMT + CISD", "A. CRT only"),
                ("D. CRT + 22.5M SSMT", "A. CRT only"),
                ("E. CRT + CISD", "A. CRT only"),
                ("H. CRT + SSMT + CISD + MMXM", "F. CRT + SSMT + CISD"),
                ("J. Full Combination (CRT+SSMT+CISD+MMXM+QT+HTF)", "F. CRT + SSMT + CISD"),
                ("J. Full Combination (CRT+SSMT+CISD+MMXM+QT+HTF)", "A. CRT only"),
            ]:
                cmp = stats.compare_two_models(models[t_name], models[b_name], n_boot=1500)
                mc = stats.matched_control_comparison(
                    sub,
                    sub.index.isin(models[t_name].index),
                    sub.index.isin(models[b_name].index),
                    n_draws=800,
                )
                hypothesis_tests.append({
                    "tf": tf_name, "scope": scope_name, "treatment": t_name, "baseline": b_name,
                    **cmp, "matched_ctrl_avg_r": mc["matched_ctrl_avg_r"],
                    "matched_excess_r": mc["excess_r"], "p_matched": mc["p_matched"],
                })

    base_df_out = pd.DataFrame(base_rows)
    adj = stats.adjust_pvalues(base_df_out["p_gt_zero"].to_numpy(float))
    base_df_out["p_holm"] = adj["p_holm"]
    base_df_out["p_bh_fdr"] = adj["p_bh_fdr"]
    base_df_out.to_parquet(RESULTS / "crt_ssmt_baselines.parquet", index=False)

    hyp_df = pd.DataFrame(hypothesis_tests)
    adj_h = stats.adjust_pvalues(hyp_df["p_boot"].to_numpy(float))
    hyp_df["p_boot_holm"] = adj_h["p_holm"]
    hyp_df["p_boot_fdr"] = adj_h["p_bh_fdr"]
    hyp_df.to_parquet(RESULTS / "hypothesis_tests.parquet", index=False)

    # 7. Section 5.3 SSMT Timing Alignment Experiments
    timing_rows = []
    for tf_name in ("M15", "H1"):
        df_pool = pd.concat([
            cands[(tf_name, "cal", "confirmed")][lambda x: x["A"]],
            cands[(tf_name, "cal", "dev_cisd")],
        ], ignore_index=True)
        # Also detect whether SSMT formed *after* CRT close (within 15 min)
        ev_mic = ctx["ssmt_mic"]
        jf_arr = ev_mic["j_form"].to_numpy()
        jc_arr = df_pool["j_close"].to_numpy()
        idx_after = np.searchsorted(jf_arr, jc_arr, side="right")
        ssmt_after_close = np.zeros(len(df_pool), dtype=bool)
        for i in range(len(df_pool)):
            k = idx_after[i]
            if k < len(jf_arr) and (jf_arr[k] - jc_arr[i]) <= 15 and ev_mic["dir"].iloc[k] == df_pool["dir"].iloc[i]:
                ssmt_after_close[i] = True
        df_pool["ssmt_after_close"] = ssmt_after_close

        dt_sw = df_pool["j_sweep"] - df_pool["micro_jform"]  # >0 means SSMT formed BEFORE CRT sweep
        dt_cisd = df_pool["cisd_after_ssmt_min"]
        buckets = [
            ("1. SSMT before CRT sweep (j_ssmt < j_sweep)", df_pool["micro_ssmt"] & (dt_sw > 0)),
            ("2. Simultaneous: Same M1 bar (|j_ssmt - j_sweep| == 0)", df_pool["micro_ssmt"] & (dt_sw == 0)),
            ("3. Simultaneous: Same M5 window (|j_ssmt - j_sweep| <= 5m)", df_pool["micro_ssmt"] & (dt_sw.abs() <= 5)),
            ("4. Simultaneous: Same active M15 candle", df_pool["micro_ssmt"] & (df_pool["micro_jform"] >= df_pool["j_open"]) & (df_pool["micro_jform"] <= df_pool["j_close"])),
            ("5. Simultaneous: Same 22.5M micro-quarter", df_pool["micro_ssmt"] & (df_pool["b22_sw"] == df_pool["b22_trig"])),
            ("6. CISD 0-2 min after SSMT", df_pool["micro_ssmt"] & df_pool["has_cisd"] & (dt_cisd >= 0) & (dt_cisd <= 2)),
            ("7. CISD 2-5 min after SSMT", df_pool["micro_ssmt"] & df_pool["has_cisd"] & (dt_cisd > 2) & (dt_cisd <= 5)),
            ("8. CISD 5-10 min after SSMT", df_pool["micro_ssmt"] & df_pool["has_cisd"] & (dt_cisd > 5) & (dt_cisd <= 10)),
            ("9. CISD 10-15 min after SSMT", df_pool["micro_ssmt"] & df_pool["has_cisd"] & (dt_cisd > 10) & (dt_cisd <= 15)),
            ("10. SSMT formed AFTER CRT close (+1..+15m, post-entry reference)", pd.Series(ssmt_after_close, index=df_pool.index)),
        ]
        for bname, bmask in buckets:
            s = stats.summarize_trades(df_pool[bmask], n_boot=600)
            timing_rows.append({"tf": tf_name, "timing_bucket": bname, **s})
    pd.DataFrame(timing_rows).to_parquet(RESULTS / "ssmt_timing.parquet", index=False)

    # 8. Panel 3: CRT TF x SSMT Level x CISD TF Matrix
    mat_rows = []
    for tf_name in ("M5", "M15", "M30", "H1", "H4"):
        df_m = cands[(tf_name, "cal", "confirmed")]
        df_m = df_m[df_m["A"]].copy()
        for ssmt_name, s_mask in [
            ("No SSMT", ~df_m["any_ssmt"]),
            ("Standard SMT", df_m["std_smt"]),
            ("90M Macro SSMT", df_m["macro_ssmt"]),
            ("22.5M Micro SSMT", df_m["micro_ssmt"]),
            ("Macro + Micro SSMT", df_m["both_ssmt"]),
        ]:
            for cisd_name, c_mask in [
                ("No CISD filter", pd.Series(True, index=df_m.index)),
                ("M1 CISD", df_m["cisd_m1"]),
                ("M3 CISD", df_m["cisd_m3"]),
                ("M5 CISD", df_m["cisd_m5"]),
            ]:
                s = stats.summarize_trades(df_m[s_mask & c_mask], n_boot=400)
                mat_rows.append({"crt_tf": tf_name, "ssmt_level": ssmt_name, "cisd_tf": cisd_name, **s})
    pd.DataFrame(mat_rows).to_parquet(RESULTS / "crt_ssmt_matrix.parquet", index=False)

    # 9. Section 6: QT Time Fractal Research (M15/H1 CRT x 6H Q1..4 x 90M Q1..4 x 22.5M Q1..4)
    qt_rows = []
    for tf_name in ("M15", "H1"):
        df_q = pd.concat([
            cands[(tf_name, "cal", "confirmed")][lambda x: x["A"]],
            cands[(tf_name, "cal", "dev_cisd")],
        ], ignore_index=True)
        # Mandatory 8 combinations: M15/H1 CRT + 90M Q1..Q4
        for q90 in (1, 2, 3, 4):
            sub90 = df_q[df_q["q90_trig"] == q90]
            s_all = stats.summarize_trades(sub90, n_boot=500)
            s_combo = stats.summarize_trades(sub90[sub90["any_ssmt"] & sub90["has_cisd"]], n_boot=500)
            qt_rows.append({"level": f"{tf_name} CRT + 90M Q{q90} (All)", "tf": tf_name, "q6": 0, "q90": q90, "q22": 0, **s_all})
            qt_rows.append({"level": f"{tf_name} CRT + 90M Q{q90} (+SSMT+CISD)", "tf": tf_name, "q6": 0, "q90": q90, "q22": 0, **s_combo})
            for q22 in (1, 2, 3, 4):
                sub_cell = sub90[(sub90["q22_trig"] == q22) & sub90["any_ssmt"] & sub90["has_cisd"]]
                sc = stats.summarize_trades(sub_cell, n_boot=400)
                qt_rows.append({
                    "level": f"{tf_name} CRT + Macro Q{q90} + Micro Q{q22} (+SSMT+CISD)",
                    "tf": tf_name, "q6": 0, "q90": q90, "q22": q22, **sc,
                })
    pd.DataFrame(qt_rows).to_parquet(RESULTS / "qt_fractals.parquet", index=False)

    # 10. Section 7: Quarter-to-Quarter SSMT Rankings (Macro 90M & Micro 22.5M)
    q2q_rows = []
    for tf_name in ("M15", "H1"):
        df_q = cands[(tf_name, "cal", "confirmed")][lambda x: x["A"]].copy()
        for lvl, pcol in [("Macro 90M (in 6H)", "macro_pair"), ("Micro 22.5M (in 90M)", "micro_pair")]:
            for qr, qt in smt.PAIRS:
                pstr = f"{qr}→{qt}"
                sub_p = df_q[(df_q[pcol] == pstr) & df_q["has_cisd"]]
                sp = stats.summarize_trades(sub_p, n_boot=500)
                q2q_rows.append({"tf": tf_name, "fractal_level": lvl, "pair": f"Q{qr}→Q{qt}", **sp})
    pd.DataFrame(q2q_rows).to_parquet(RESULTS / "q2q_rankings.parquet", index=False)

    # 11. Section 8: Multi-Level Alignment
    align_rows = []
    for tf_name in ("M15", "H1"):
        df_al = cands[(tf_name, "cal", "confirmed")][lambda x: x["A"]].copy()
        align_models = [
            ("0. CRT without any SSMT (Reference)", ~df_al["any_ssmt"] & ~df_al["std_smt"]),
            ("1. CRT + Macro SSMT only", df_al["macro_ssmt"] & ~df_al["micro_ssmt"]),
            ("2. CRT + Micro SSMT only", df_al["micro_ssmt"] & ~df_al["macro_ssmt"]),
            ("3. CRT + Macro & Micro SSMT same direction", df_al["both_ssmt"] & ~df_al["macro_opp_ssmt"]),
            ("4. CRT + Macro & Micro SSMT conflict", df_al["micro_ssmt"] & df_al["macro_opp_ssmt"]),
            ("5. CRT + Macro SSMT (any micro)", df_al["macro_ssmt"]),
            ("6. CRT + Micro SSMT (any macro)", df_al["micro_ssmt"]),
            ("7. CRT + Macro + Micro SSMT + CISD", df_al["both_ssmt"] & df_al["has_cisd"]),
            ("8. CRT + SSMT + HTF Liquidity", df_al["any_ssmt"] & df_al["htf_liq"]),
            ("9. CRT + SSMT + MMXM", df_al["any_ssmt"] & df_al["mmxm"]),
            ("10. Full Narrative Alignment", df_al["any_ssmt"] & df_al["has_cisd"] & df_al["mmxm"] & (df_al["narrative"].isin(["bullish_reversal", "bearish_reversal", "bullish_continuation", "bearish_continuation"]))),
        ]
        for aname, amask in align_models:
            sa = stats.summarize_trades(df_al[amask], n_boot=600)
            align_rows.append({"tf": tf_name, "alignment_model": aname, **sa})
    pd.DataFrame(align_rows).to_parquet(RESULTS / "multilevel_alignment.parquet", index=False)

    # 12. Section 9: Market Narrative Engine Performance
    narr_rows = []
    for tf_name in ("M15", "H1"):
        df_n = cands[(tf_name, "cal", "confirmed")][lambda x: x["A"]].copy()
        for nclass in ("bullish_reversal", "bearish_reversal", "bullish_continuation", "bearish_continuation",
                       "failed_breakout", "range_rejection", "contradictory"):
            sn_all = stats.summarize_trades(df_n[df_n["narrative"] == nclass], n_boot=500)
            sn_ssmt = stats.summarize_trades(df_n[(df_n["narrative"] == nclass) & df_n["any_ssmt"] & df_n["has_cisd"]], n_boot=500)
            narr_rows.append({"tf": tf_name, "filter": "CRT-A", "narrative_class": nclass, **sn_all})
            narr_rows.append({"tf": tf_name, "filter": "CRT+SSMT+CISD", "narrative_class": nclass, **sn_ssmt})
    pd.DataFrame(narr_rows).to_parquet(RESULTS / "narrative_perf.parquet", index=False)

    # 13. Sections 3 & 10: Opening Windows, NY-A..NY-J, LDN-A..LDN-J, and H1 Candle Anchoring
    win_rows = []
    df_m15_all = pd.concat([
        cands[("M15", "cal", "confirmed")][lambda x: x["A"]],
        cands[("M15", "cal", "dev_cisd")],
    ], ignore_index=True)
    for wname, m0, m1 in opening.NY_WINDOWS:
        wmask = (df_m15_all["min_from_ny_open_trig"] >= m0) & (df_m15_all["min_from_ny_open_trig"] < m1)
        sw_base = stats.summarize_trades(df_m15_all[wmask & (df_m15_all["entry_mode"] == "confirmed")], n_boot=500)
        sw_combo = stats.summarize_trades(df_m15_all[wmask & df_m15_all["any_ssmt"] & df_m15_all["has_cisd"]], n_boot=500)
        win_rows.append({"session": "NY_WallClock", "window": wname, "model": "CRT-only", **sw_base})
        win_rows.append({"session": "NY_WallClock", "window": wname, "model": "CRT+SSMT+CISD", **sw_combo})
    for wname, m0, m1 in opening.NY_NORM_WINDOWS:
        wmask = (df_m15_all["min_from_ny_open_trig"] >= m0) & (df_m15_all["min_from_ny_open_trig"] < m1)
        sw_combo = stats.summarize_trades(df_m15_all[wmask & df_m15_all["any_ssmt"] & df_m15_all["has_cisd"]], n_boot=500)
        win_rows.append({"session": "NY_Normalized", "window": wname, "model": "CRT+SSMT+CISD", **sw_combo})
    for wname, m0, m1 in opening.LDN_NORM_WINDOWS:
        wmask = (df_m15_all["min_from_ldn_open_trig"] >= m0) & (df_m15_all["min_from_ldn_open_trig"] < m1)
        sw_base = stats.summarize_trades(df_m15_all[wmask & (df_m15_all["entry_mode"] == "confirmed")], n_boot=500)
        sw_combo = stats.summarize_trades(df_m15_all[wmask & df_m15_all["any_ssmt"] & df_m15_all["has_cisd"]], n_boot=500)
        win_rows.append({"session": "London_Normalized", "window": wname, "model": "CRT-only", **sw_base})
        win_rows.append({"session": "London_Normalized", "window": wname, "model": "CRT+SSMT+CISD", **sw_combo})
    pd.DataFrame(win_rows).to_parquet(RESULTS / "opening_windows.parquet", index=False)

    # Models NY-A .. NY-J
    ny_pool = pd.concat([
        cands[("M15", "cal", "confirmed")],
        cands[("M15", "cal", "dev_cisd")],
        cands[("H1", "cal", "confirmed")],
        cands[("H1", "cal", "dev_cisd")],
    ], ignore_index=True)
    ny_masks = opening.classify_ny_open_models(ny_pool)
    ny_model_rows = []
    ny_candidates_for_wfa: dict[str, pd.DataFrame] = {}
    for mname, mmask in ny_masks.items():
        sub_m = ny_pool[mmask].sort_values("j_trig").reset_index(drop=True)
        if len(sub_m) > 0:
            keep = sim.filter_non_overlapping(sub_m["j_trig"].to_numpy(np.int64), sub_m["j_exit"].to_numpy(np.int64))
            sub_m = sub_m[keep].reset_index(drop=True)
        ny_candidates_for_wfa[mname] = sub_m
        sm = stats.summarize_trades(sub_m, n_boot=800)
        ny_model_rows.append({"model": mname, **sm})
    pd.DataFrame(ny_model_rows).to_parquet(RESULTS / "ny_open_models.parquet", index=False)

    # Section 10.2 H1 & M15 Candle Anchoring Comparison (09:00-10:00 cal vs 09:30-10:30 ny930)
    anc_rows = []
    for tf_name in ("H1", "M15"):
        for anc, anc_label in [("cal", "Calendar-Aligned (09:00-10:00)"), ("ny930", "NY-Open-Anchored (09:30-10:30)")]:
            for mode_key in ("confirmed", "dev_cisd"):
                sub_a = cands[(tf_name, anc, mode_key)]
                if mode_key == "confirmed":
                    sub_a = sub_a[sub_a["A"]]
                sub_ny = sub_a[(sub_a["min_from_ny_open_trig"] >= 0) & (sub_a["min_from_ny_open_trig"] <= 120)]
                sa_all = stats.summarize_trades(sub_ny, n_boot=600)
                sa_ssmt = stats.summarize_trades(sub_ny[sub_ny["any_ssmt"] & sub_ny["has_cisd"]], n_boot=600)
                anc_rows.append({"tf": tf_name, "anchor": anc_label, "mode": mode_key, "filter": "CRT", **sa_all})
                anc_rows.append({"tf": tf_name, "anchor": anc_label, "mode": mode_key, "filter": "CRT+SSMT+CISD", **sa_ssmt})
    pd.DataFrame(anc_rows).to_parquet(RESULTS / "h1_anchoring.parquet", index=False)

    # 14. Section 13: Stop-Loss, Trailing Exit, and R:R Grid Research
    # Run on our flagship M15 CRT + SSMT + CISD core setup
    core_raw = cands[("M15", "cal", "confirmed")]
    core_raw = core_raw[core_raw["A"] & core_raw["any_ssmt"] & core_raw["has_cisd"]].copy()
    rr_rows = []
    for stop_label, scol in [
        ("1. CRT Sweep Wick Extreme", "sweep_ext_known"),
        ("2. SSMT Trigger Extreme", "ssmt_stop"),
        ("3. Last Confirmed M5 Swing", "swing_stop"),
        ("4. H1 Structural Invalidation", "struct_stop"),
        ("5. CRT Reference Candle Extreme", "ref_ext_stop"),
    ]:
        for rr in RR_LIST:
            sim_r = _sim_df(ctx, core_raw, rr=rr, stop_col=scol, exit_model=sim.EX_FIXED, slip=0.25, non_overlap=True)
            sr = stats.summarize_trades(sim_r, n_boot=400)
            rr_rows.append({"stop_model": stop_label, "exit_model": "Fixed TP/SL", "rr_target": f"{rr}R", **sr})

    for ex_label, ex_code, rr_val, tcol in [
        ("Fixed Stop & 2R TP", sim.EX_FIXED, 2.0, None),
        ("Break-Even after 1R (2R TP)", sim.EX_BE1, 2.0, None),
        ("Break-Even after 2R (3R TP)", sim.EX_BE2, 3.0, None),
        ("M5 Swing Trailing (3R TP)", sim.EX_SWING, 3.0, None),
        ("Partial Profit 50%@1R + BE (3R TP)", sim.EX_PARTIAL, 3.0, None),
        ("Opposing Reference Range Liquidity Exit", sim.EX_FIXED, 2.0, "opp_range_target"),
        ("Reference Midpoint Exit", sim.EX_FIXED, 2.0, "mid_target"),
        ("No-TP Pure M5 Swing Trailing", sim.EX_NO_TP_SWING, 10.0, None),
        ("Time-Based Forced Exit (45m / 2 quarters)", sim.EX_TIME, 3.0, None),
    ]:
        mh = 45 if ex_code == sim.EX_TIME else 360
        sim_ex = _sim_df(ctx, core_raw, rr=rr_val, stop_col="sweep_ext_known", exit_model=ex_code,
                         max_hold=mh, slip=0.25, non_overlap=True, target_col=tcol)
        sex = stats.summarize_trades(sim_ex, n_boot=500)
        rr_rows.append({"stop_model": "1. CRT Sweep Wick Extreme", "exit_model": ex_label, "rr_target": f"{rr_val}R", **sex})
    pd.DataFrame(rr_rows).to_parquet(RESULTS / "rr_stop_exit_grid.parquet", index=False)

    # 15. Section 15: Statistical Robustness (Splits, WFA, Yearly, Monthly, Cost Sensitivity, DST Regimes)
    core_2r = _sim_df(ctx, core_raw, rr=2.0, stop_col="sweep_ext_known", exit_model=sim.EX_FIXED, slip=0.25, non_overlap=True)
    core_ny = core_2r[(core_2r["min_from_ny_open_trig"] >= 0) & (core_2r["min_from_ny_open_trig"] <= 90)].copy()

    splits_df = pd.concat([
        stats.split_evaluation(core_2r).assign(scope="M15 CRT+SSMT+CISD (All Sessions)"),
        stats.split_evaluation(core_ny).assign(scope="M15 CRT+SSMT+CISD (NY Open 09:30-11:00)"),
        stats.split_evaluation(cands[("M15", "cal", "confirmed")][lambda x: x["A"]]).assign(scope="M15 CRT-only Baseline"),
    ], ignore_index=True)
    splits_df.to_parquet(RESULTS / "splits_eval.parquet", index=False)

    wfa_df = stats.walk_forward_analysis(ny_candidates_for_wfa, train_months=12, test_months=6)
    wfa_df.to_parquet(RESULTS / "wfa_folds.parquet", index=False)

    # Yearly & Monthly breakdown
    yr_rows = []
    for scope_label, sdf in [
        ("CRT+SSMT+CISD (All)", core_2r),
        ("CRT+SSMT+CISD (NY Open)", core_ny),
        ("CRT-only (NY Open)", cands[("M15", "cal", "confirmed")][lambda x: x["A"] & (x["min_from_ny_open_trig"] >= 0) & (x["min_from_ny_open_trig"] <= 90)]),
    ]:
        for yr, g in sdf.groupby("year_trig"):
            sy = stats.summarize_trades(g, n_boot=400)
            yr_rows.append({"scope": scope_label, "year": int(yr), **sy})
    pd.DataFrame(yr_rows).to_parquet(RESULTS / "yearly_perf.parquet", index=False)

    mo_rows = []
    for mo, g in core_2r.groupby("month_trig"):
        mo_rows.append({
            "month": str(mo), "n_trades": int(len(g)),
            "win_rate": float((g["r"] > 0).mean()), "avg_r": float(g["r"].mean()), "total_r": float(g["r"].sum()),
        })
    pd.DataFrame(mo_rows).sort_values("month").to_parquet(RESULTS / "monthly_perf.parquet", index=False)

    # Transaction Cost Sensitivity (slip = 0.0, 0.25, 0.5, 1.0, 1.5, 2.0 pts on top of Bid-Ask spread)
    cost_rows = []
    for slp in (0.0, 0.25, 0.5, 1.0, 1.5, 2.0):
        sc_df = _sim_df(ctx, core_raw, rr=2.0, stop_col="sweep_ext_known", exit_model=sim.EX_FIXED, slip=slp, non_overlap=True)
        sc_ny = sc_df[(sc_df["min_from_ny_open_trig"] >= 0) & (sc_df["min_from_ny_open_trig"] <= 90)]
        cost_rows.append({"slippage_pts": slp, "scope": "All Sessions", **stats.summarize_trades(sc_df, n_boot=400)})
        cost_rows.append({"slippage_pts": slp, "scope": "NY Open (09:30-11:00)", **stats.summarize_trades(sc_ny, n_boot=400)})
    pd.DataFrame(cost_rows).to_parquet(RESULTS / "cost_sensitivity.parquet", index=False)

    # DST Regime & Volatility Tercile Breakdown (Question 19 & Section 15)
    reg_rows = []
    for reg, g in core_2r.groupby("regime_trig"):
        reg_rows.append({"dimension": "DST_Regime", "bucket": str(reg), **stats.summarize_trades(g, n_boot=400)})
    vol_terc = pd.qcut(core_2r["atr_ref"].rank(method="first"), 3, labels=["Low_Volatility", "Mid_Volatility", "High_Volatility"])
    for vt, g in core_2r.groupby(vol_terc, observed=False):
        reg_rows.append({"dimension": "Volatility_Regime", "bucket": str(vt), **stats.summarize_trades(g, n_boot=400)})
    pd.DataFrame(reg_rows).to_parquet(RESULTS / "regime_perf.parquet", index=False)

    # 16. Save 600+ Audited Candidate Setups & Trade Replay Records (Section 16 Panel 10 & Section 20 Step 17)
    audit_df = pd.concat([
        core_2r.assign(model_tag="M15_CRT_SSMT_CISD_CONF"),
        _sim_df(ctx, cands[("H1", "cal", "dev_cisd")][lambda x: x["any_ssmt"]], rr=2.0, non_overlap=True).assign(model_tag="H1_DEV_CRT_SSMT_CISD"),
        _sim_df(ctx, cands[("H1", "cal", "confirmed")][lambda x: x["A"] & x["any_ssmt"] & x["has_cisd"]], rr=2.0, non_overlap=True).assign(model_tag="H1_CONF_CRT_SSMT_CISD"),
    ], ignore_index=True).sort_values("t_trig", ascending=False).head(800).reset_index(drop=True)
    audit_df.to_parquet(RESULTS / "audit_sample_trades.parquet", index=False)

    # 17. Verify 30-second micro-quarter resolution & Cross-Broker (Dukascopy Pure vs OANDA Pure)
    res_30s = verify_30s_micro_quarters()
    dq_summary = {
        "generated_at_utc": str(pd.Timestamp.now(tz="UTC")),
        "period_start": str(panel.index.min()),
        "period_end": str(panel.index.max()),
        "total_aligned_m1_bars": int(len(panel)),
        "dukascopy_us100_m1_bars": int(len(pl.read_parquet(STORE / "DUKA_US100_M1.parquet"))),
        "dukascopy_us100_30s_bars": int(len(pl.read_parquet(STORE / "DUKA_US100_30S.parquet"))),
        "dukascopy_us500_m1_bars": int(len(pl.read_parquet(STORE / "DUKA_US500_M1.parquet"))),
        "dukascopy_us500_30s_bars": int(len(pl.read_parquet(STORE / "DUKA_US500_30S.parquet"))),
        "oanda_us100_m1_bars": int(len(pl.read_parquet(STORE / "OANDA_US100_M1.parquet"))),
        "oanda_us500_m1_bars": int(len(pl.read_parquet(STORE / "OANDA_US500_M1.parquet"))),
        "oanda_us30_m1_bars": int(len(pl.read_parquet(STORE / "OANDA_US30_M1.parquet"))),
        "micro_quarter_30s_verification": res_30s,
        "audit_sample_count": int(len(audit_df)),
        "runtime_seconds": round(time.time() - t0, 2),
    }
    (RESULTS / "data_quality.json").write_text(json.dumps(dq_summary, indent=2))
    print(f"[ENGINE] Complete research pipeline finished in {time.time()-t0:.1f}s!", flush=True)


if __name__ == "__main__":
    run_all()
