"""Event-driven candidate extractor & narrative annotator (strictly causal, v2.0).

Every signal produced here carries:
  * Full execution lifecycle timestamps (Phase 1.2 & Phase 8):
    `t_sweep` -> `t_trig` (bar open of confirming M1 bar) -> `t_signal_known`
    (bar close of confirming M1 bar) -> `t_order_submit` -> `t_earliest_exec`
    -> `t_fill` (open of `j_fill = j_trig + 1`).
  * True independent M1, M3, M5, M15 CISD (`astra6/cisd.py`).
  * True 10-stage causal MMBM / MMSM state machine (`astra6/mmxm.py`).
  * Multi-anchor Quarterly Theory labels (`ny1800`, `ny0930`, `ldn0800`) and
    multi-event SSMT preservation (`astra6/smt.py`).
  * Stop levels for all 5 structural stop models using only data known at `t_signal_known`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .bars import TF_MIN, minute_confirmation_index, quarter_labels, resample
from .cisd import attach_true_cisd_to_signals, extract_tf_cisd_events
from .clock import LDN, NY, dst_regime
from .crt import classify_confirmed, running_extreme, scan_crt
from .ict import asof_join, atr_wilder, fvg_table, last_known_swing, period_levels, swing_table
from .mmxm import attach_mmxm_to_signals, build_mmxm_table
from .smt import attach_ssmt, ssmt_events


def build_context(
    panel: pd.DataFrame,
    traded: str = "US100",
    comps: tuple[str, ...] = ("US500", "US30"),
    qt_anchor: str = "ny1800",
    dataset_tag: str = "C_MIXED_EXTENDED",
) -> dict:
    """Precompute strictly-causal indicator, CISD, MMXM, and SSMT tables on the M1 panel."""
    avail_comps = tuple(c for c in comps if f"{c}_h" in panel.columns)
    idx = panel.index
    ql = quarter_labels(idx, qt_anchor=qt_anchor)
    ql_ny0930 = quarter_labels(idx, qt_anchor="ny0930")
    ql_ldn0800 = quarter_labels(idx, qt_anchor="ldn0800")

    loc = idx.tz_convert(NY)
    ldn_loc = idx.tz_convert(LDN)
    mod = (loc.hour * 60 + loc.minute).to_numpy()
    ny_dates = pd.Series(loc.date, index=idx)
    regimes = pd.Series({d: dst_regime(d) for d in pd.unique(ny_dates)})

    ql["ny_hour"] = loc.hour.to_numpy(np.int8)
    ql["ny_minute"] = loc.minute.to_numpy(np.int8)
    ql["ny_mod"] = mod
    ql["min_from_ny_open"] = mod - (9 * 60 + 30)
    ql["ldn_mod"] = (ldn_loc.hour * 60 + ldn_loc.minute).to_numpy()
    ql["min_from_ldn_open"] = ql["ldn_mod"] - 8 * 60
    ql["regime"] = ny_dates.map(regimes).to_numpy()
    ql["year"] = loc.year.to_numpy()
    ql["month"] = loc.strftime("%Y-%m").to_numpy()
    ql["date_ny"] = loc.strftime("%Y-%m-%d").to_numpy()

    # M1 ATR
    atr1 = atr_wilder(
        panel[f"{traded}_h"].to_numpy(float),
        panel[f"{traded}_l"].to_numpy(float),
        panel[f"{traded}_c"].to_numpy(float),
        14,
    )

    # HTF bars & swings
    d1 = resample(panel, traded, "D1")
    h4 = resample(panel, traded, "H4")
    h1_cal = resample(panel, traded, "H1", "cal")
    m5 = resample(panel, traded, "M5")
    sw_m5 = swing_table(m5[m5["is_closed"]], 2, 2)
    sw_h1 = swing_table(h1_cal[h1_cal["is_closed"]], 2, 2)
    sw_h4 = swing_table(h4[h4["is_closed"]], 2, 2)
    sw_m5["j_known"] = idx.searchsorted(sw_m5["t_known"], side="left")

    # PDH/PDL and PWH/PWL
    pd_tbl = period_levels(d1[d1["complete"]], "PD")
    w_bars = resample(panel, traded, "W1")
    pw_tbl = period_levels(w_bars[w_bars["is_closed"]], "PW")

    # True Multi-Timeframe CISD tables (M1, M3, M5, M15, M30, H1, H4)
    cisd_tables = {
        tf_c: extract_tf_cisd_events(panel, traded=traded, tf=tf_c, variant="v1")
        for tf_c in ("M1", "M3", "M5", "M15", "M30", "H1", "H4")
    }
    cisd_v2_m1 = extract_tf_cisd_events(panel, traded=traded, tf="M1", variant="v2")

    # True Causal MMXM State Machine table (M5 resolution)
    mmxm_tbl = build_mmxm_table(panel, traded=traded)

    # SSMT tables (macro & micro) on primary comparator (US500) and secondary (US30)
    c0 = avail_comps[0]
    ssmt_mac = ssmt_events(panel, ql, traded, c0, "macro")
    ssmt_mic = ssmt_events(panel, ql, traded, c0, "micro")
    ssmt_mac_ny0930 = ssmt_events(panel, ql_ny0930, traded, c0, "macro")
    ssmt_mic_ny0930 = ssmt_events(panel, ql_ny0930, traded, c0, "micro")
    ssmt_mac_ldn0800 = ssmt_events(panel, ql_ldn0800, traded, c0, "macro")
    ssmt_mic_ldn0800 = ssmt_events(panel, ql_ldn0800, traded, c0, "micro")

    if len(avail_comps) > 1:
        c1 = avail_comps[1]
        ssmt_mac_30 = ssmt_events(panel, ql, traded, c1, "macro")
        ssmt_mic_30 = ssmt_events(panel, ql, traded, c1, "micro")
        ssmt_mac_500_30 = ssmt_events(panel, ql, c0, c1, "macro")
        ssmt_mic_500_30 = ssmt_events(panel, ql, c0, c1, "micro")
    else:
        ssmt_mac_30 = pd.DataFrame()
        ssmt_mic_30 = pd.DataFrame()
        ssmt_mac_500_30 = pd.DataFrame()
        ssmt_mic_500_30 = pd.DataFrame()

    return {
        "panel": panel, "ql": ql, "ql_ny0930": ql_ny0930, "ql_ldn0800": ql_ldn0800,
        "atr1": atr1, "traded": traded, "comps": avail_comps,
        "qt_anchor": qt_anchor, "dataset_tag": dataset_tag,
        "d1": d1, "h4": h4, "h1_cal": h1_cal, "m5": m5,
        "sw_m5": sw_m5, "sw_h1": sw_h1, "sw_h4": sw_h4,
        "pd_tbl": pd_tbl, "pw_tbl": pw_tbl,
        "cisd_tables": cisd_tables, "cisd_v2_m1": cisd_v2_m1,
        "mmxm_tbl": mmxm_tbl,
        "ssmt_mac": ssmt_mac, "ssmt_mic": ssmt_mic,
        "ssmt_mac_30": ssmt_mac_30, "ssmt_mic_30": ssmt_mic_30,
        "ssmt_mac_500_30": ssmt_mac_500_30, "ssmt_mic_500_30": ssmt_mic_500_30,
        "ssmt_mac_ny0930": ssmt_mac_ny0930, "ssmt_mic_ny0930": ssmt_mic_ny0930,
        "ssmt_mac_ldn0800": ssmt_mac_ldn0800, "ssmt_mic_ldn0800": ssmt_mic_ldn0800,
    }


def extract_crt_events(
    ctx: dict, tf: str = "M15", anchor: str = "cal", max_bars: int | None = None,
    *, include_developing: bool = False, require_full: bool = False,
) -> pd.DataFrame:
    """Scan one (tf, anchor) stream and return a flat table of sweep events
    (both directions) with all confirmation & early-entry indices attached."""
    panel = ctx["panel"]
    traded = ctx["traded"]
    comps = ctx["comps"]
    idx = panel.index
    bars = resample(panel, traded, tf, anchor)
    if require_full:
        selected = bars["is_complete"] | (include_developing & ~bars["is_closed"])
        bars = bars[selected].reset_index(drop=True)
    elif not include_developing:
        bars = bars[bars["is_closed"]].reset_index(drop=True)
    if max_bars is not None and len(bars) > max_bars:
        bars = bars.iloc[-max_bars:].reset_index(drop=True)
    m = TF_MIN[tf]
    i0 = idx.searchsorted(bars["t_open"].to_numpy(), side="left")
    i1 = idx.searchsorted(bars["t_close"].to_numpy(), side="left")
    j_confirm = minute_confirmation_index(idx, bars["available_at"])

    Href = np.roll(bars["h"].to_numpy(float), 1)
    Lref = np.roll(bars["l"].to_numpy(float), 1)
    Oref = np.roll(bars["o"].to_numpy(float), 1)
    Cref = np.roll(bars["c"].to_numpy(float), 1)
    prev_close = np.roll(bars["t_close"].to_numpy(), 1)
    gap_min = (bars["t_open"].to_numpy() - prev_close) / np.timedelta64(1, "m")
    max_gap = 4320 if tf in ("D1", "W1") else 5
    min_n = max(1, m // 4) if tf in ("D1", "W1") else max(1, m // 2)
    previous_closed = bars["is_closed"].shift(1, fill_value=False)
    valid = (previous_closed & (gap_min <= (0 if require_full else max_gap))).to_numpy(copy=True)
    if not include_developing:
        valid = valid & (bars["n"].to_numpy() >= min_n)

    ch = np.vstack([panel[f"{c}_h"].to_numpy(float) for c in comps])
    cl = np.vstack([panel[f"{c}_l"].to_numpy(float) for c in comps])
    cHref = np.full((len(comps), len(bars)), np.nan)
    cLref = np.full((len(comps), len(bars)), np.nan)
    for k in range(len(comps)):
        for b in range(1, len(bars)):
            if i1[b - 1] > i0[b - 1]:
                cHref[k, b] = ch[k, i0[b - 1]:i1[b - 1]].max()
                cLref[k, b] = cl[k, i0[b - 1]:i1[b - 1]].min()

    o = panel[f"{traded}_o"].to_numpy(float)
    h = panel[f"{traded}_h"].to_numpy(float)
    l = panel[f"{traded}_l"].to_numpy(float)
    c = panel[f"{traded}_c"].to_numpy(float)
    atr_htf = atr_wilder(bars["h"].to_numpy(float), bars["l"].to_numpy(float), bars["c"].to_numpy(float), 14)
    atr_ref = np.roll(atr_htf, 1)
    reference_coverage = bars["data_coverage_status"].shift(1)
    ev, ext_cisd = scan_crt(o, h, l, c, ctx["atr1"], ch, cl, i0, i1, Href, Lref, cHref, cLref,
                            valid, ext=15, disp_k=1.2)
    rows = []
    for d, direction in ((0, -1), (1, 1)):
        jsw = ev[:, d, 0]
        jot = ev[:, d, 1]
        jrc = ev[:, d, 2]
        jci = ev[:, d, 3]
        jdp = ev[:, d, 4]
        jc0 = ev[:, d, 5]
        jc1 = ev[:, d, 6] if len(comps) > 1 else np.full(len(bars), -1)
        sub = bars.assign(
            Hr=Href, Lr=Lref, Or=Oref, Cr=Cref, sw=jsw >= 0, ot=jot >= 0,
            j_open=i0, j_close=j_confirm, j_sweep=jsw, j_other=jot, j_reclaim=jrc,
            j_cisd=jci, j_disp=jdp, j_cmp0=jc0, j_cmp1=jc1,
            ext_at_cisd=ext_cisd[:, d], atr_ref=atr_ref, dir=direction,
            tf=tf, anchor=anchor, reference_coverage_status=reference_coverage,
            reference_bucket_start=bars["bucket_start"].shift(1),
        )
        flags = classify_confirmed(sub, d)
        if include_developing:
            flags.loc[~sub["is_closed"]] = False
        sub = pd.concat([sub, flags], axis=1)
        sub["E"] = sub["A"] & (sub["j_disp"] >= 0) & (sub["j_disp"] <= sub["j_close"])
        nxt_c = bars["c"].shift(-1)
        nxt_j = pd.Series(j_confirm).shift(-1, fill_value=-1)
        sub["F"] = sub["A"] & ((nxt_c < np.minimum(sub.o, sub.c)) if direction == -1 else (nxt_c > np.maximum(sub.o, sub.c)))
        sub["j_next_close"] = nxt_j
        sw_out = (jsw >= 0) & (jot < 0) & ((bars["c"] > Href) if direction == -1 else (bars["c"] < Lref))
        prev_sw_out = sw_out.shift(1, fill_value=False)
        Hr2 = np.roll(Href, 1)
        Lr2 = np.roll(Lref, 1)
        sub["H"] = prev_sw_out & (bars["c"] >= Lr2) & (bars["c"] <= Hr2)
        sub["Hr_h"] = np.where(sub["H"], Hr2, sub["Hr"])
        sub["Lr_h"] = np.where(sub["H"], Lr2, sub["Lr"])
        sub = sub[sub["sw"] | sub["H"]].copy()
        rows.append(sub)
    df = pd.concat(rows, ignore_index=True)
    df["sweep_depth"] = np.where(df["dir"] == -1, df["h"] - df["Hr"], df["Lr"] - df["l"])
    df["return_depth"] = np.where(df["dir"] == -1, df["Hr"] - df["c"], df["c"] - df["Lr"])
    df["sweep_atr"] = df["sweep_depth"] / df["atr_ref"].replace(0, np.nan)
    rng = (df["h"] - df["l"]).replace(0, np.nan)
    body = (df["c"] - df["o"]).abs()
    df["wick_body_ratio"] = (rng - body) / (body + 1e-6)
    df["body_pos"] = (df["c"] - df["l"]) / rng
    return df.sort_values(["j_close", "dir"]).reset_index(drop=True)


def materialize_entries(ctx: dict, crt_df: pd.DataFrame, mode: str) -> pd.DataFrame:
    """Turn raw CRT events into causal trade candidates for a given entry mode.

    Separates:
      * `j_trig`         : M1 bar whose close confirms the signal (`t_signal_known = t_open[j_trig] + 1m`)
      * `j_fill`         : Next executable M1 bar `j_trig + 1` where order is filled at open (`t_fill = t_open[j_fill]`)
    """
    panel = ctx["panel"]
    ql = ctx["ql"]
    traded = ctx["traded"]
    h = panel[f"{traded}_h"].to_numpy(float)
    l = panel[f"{traded}_l"].to_numpy(float)
    c = panel[f"{traded}_c"].to_numpy(float)
    df = crt_df.copy()
    if mode == "confirmed":
        df = df[df["A"] | df["J"] | df["K"] | df["H"]].copy()
        df["j_trig"] = df["j_close"]
        df["sweep_ext_known"] = np.where(df["dir"] == -1, df["h"], df["l"])
    elif mode == "confirmed_next":
        df = df[df["F"]].copy()
        df["j_trig"] = df["j_next_close"]
        df["sweep_ext_known"] = np.where(
            df["dir"] == -1,
            np.maximum(df["h"], h[df["j_trig"]]),
            np.minimum(df["l"], l[df["j_trig"]]),
        )
    elif mode == "confirmed_cisd":
        ok = df["A"] & (df["j_cisd"] >= 0) & (df["j_cisd"] <= df["j_close"] + 15)
        df = df[ok].copy()
        df["j_trig"] = np.maximum(df["j_close"], df["j_cisd"])
        ext = [running_extreme(h, l, int(s), int(t), d == -1)
               for s, t, d in zip(df["j_open"], df["j_trig"], df["dir"])]
        df["sweep_ext_known"] = ext
    elif mode == "dev_cisd":
        ok = (df["j_sweep"] >= 0) & (df["j_cisd"] >= 0) & (df["j_cisd"] < df["j_close"]) & \
             ((df["j_other"] < 0) | (df["j_other"] > df["j_cisd"]))
        df = df[ok].copy()
        df["j_trig"] = df["j_cisd"]
        df["sweep_ext_known"] = df["ext_at_cisd"]
    elif mode == "dev_reclaim":
        ok = (df["j_sweep"] >= 0) & (df["j_reclaim"] >= 0) & (df["j_reclaim"] < df["j_close"]) & \
             ((df["j_other"] < 0) | (df["j_other"] > df["j_reclaim"]))
        df = df[ok].copy()
        df["j_trig"] = df["j_reclaim"]
        ext = [running_extreme(h, l, int(s), int(t), d == -1)
               for s, t, d in zip(df["j_sweep"], df["j_trig"], df["dir"])]
        df["sweep_ext_known"] = ext
    else:
        raise ValueError(mode)

    df["entry_mode"] = mode
    if len(df) == 0:
        return df

    jt = df["j_trig"].to_numpy(int)
    jf = np.minimum(jt + 1, len(panel) - 1)
    jsw = np.maximum(df["j_sweep"].to_numpy(int), df["j_open"].to_numpy(int))
    idx = panel.index

    df["j_fill"] = jf
    df["t_sweep"] = idx[jsw]
    df["t_trig"] = idx[jt]
    df["t_signal_known"] = idx[jt] + pd.Timedelta(minutes=1)
    df["t_order_submit"] = df["t_signal_known"]
    df["t_earliest_exec"] = idx[jf]
    df["t_fill"] = idx[jf]
    df["dataset_tag"] = ctx.get("dataset_tag", "C_MIXED_EXTENDED")
    df["qt_anchor"] = ctx.get("qt_anchor", "ny1800")

    # Quarter / session context at trigger AND at sweep
    for prefix, jarr in (("trig", jt), ("sw", jsw)):
        for col in ("q6", "q90", "q22", "q5", "b6", "b90", "b22", "ny_hour", "ny_minute", "ny_mod",
                    "min_from_ny_open", "min_from_ldn_open", "regime", "year", "month", "date_ny"):
            df[f"{col}_{prefix}"] = ql[col].to_numpy()[jarr]

    # Also attach NY0930 and LDN0800 QT anchor quarter labels at trigger
    ql_ny930 = ctx["ql_ny0930"]
    ql_ldn800 = ctx["ql_ldn0800"]
    df["q90_ny0930"] = ql_ny930["q90"].to_numpy()[jt]
    df["q22_ny0930"] = ql_ny930["q22"].to_numpy()[jt]
    df["b90_ny0930_trig"] = ql_ny930["b90"].to_numpy()[jt]
    df["b22_ny0930_trig"] = ql_ny930["b22"].to_numpy()[jt]
    df["q90_ldn0800"] = ql_ldn800["q90"].to_numpy()[jt]
    df["q22_ldn0800"] = ql_ldn800["q22"].to_numpy()[jt]
    df["b90_ldn0800_trig"] = ql_ldn800["b90"].to_numpy()[jt]
    df["b22_ldn0800_trig"] = ql_ldn800["b22"].to_numpy()[jt]

    # Standard SMT at trigger
    df["std_smt"] = (df["j_sweep"] >= 0) & ((df["j_cmp0"] < 0) | (df["j_cmp0"] > df["j_trig"]))
    df["std_smt_30"] = (df["j_sweep"] >= 0) & ((df["j_cmp1"] < 0) | (df["j_cmp1"] > df["j_trig"]))

    # Attach macro & micro SSMT (primary comparator US500)
    df = attach_ssmt(df, ctx["ssmt_mac"], "macro")
    df = attach_ssmt(df, ctx["ssmt_mic"], "micro")

    # Attach secondary comparator (US30) SSMT if available
    if len(ctx["ssmt_mac_30"]) > 0:
        df = attach_ssmt(df, ctx["ssmt_mac_30"], "macro", prefix="macro_30")
        df = attach_ssmt(df, ctx["ssmt_mic_30"], "micro", prefix="micro_30")
    else:
        df["macro_30_ssmt"] = False
        df["micro_30_ssmt"] = False

    df["any_ssmt"] = df["macro_ssmt"] | df["micro_ssmt"]
    df["any_ssmt_30"] = df["macro_30_ssmt"] | df["micro_30_ssmt"]
    df["three_idx_ssmt"] = df["any_ssmt"] & df["any_ssmt_30"]
    df["both_ssmt"] = df["macro_ssmt"] & df["micro_ssmt"]
    df["macro_then_micro"] = df["both_ssmt"] & (df["macro_jform"] <= df["micro_jform"])
    df["micro_then_macro"] = df["both_ssmt"] & (df["micro_jform"] < df["macro_jform"])

    # Check conflicting direction macro vs micro
    opp = df.assign(dir=-df["dir"])
    opp = attach_ssmt(opp, ctx["ssmt_mac"], "macro")
    df["macro_opp_ssmt"] = opp["macro_ssmt"].to_numpy()

    df["ssmt_dt_min"] = np.where(
        df["micro_ssmt"], df["j_trig"] - df["micro_jform"],
        np.where(df["macro_ssmt"], df["j_trig"] - df["macro_jform"], np.nan),
    )
    df["sw_ssmt_dt_min"] = np.where(df["micro_ssmt"], df["j_sweep"] - df["micro_jform"], np.nan)

    # CISD flag at or before trigger + True Independent M1/M3/M5/M15 CISD
    df["has_cisd"] = (df["j_cisd"] >= 0) & (df["j_cisd"] <= df["j_trig"])
    df = attach_true_cisd_to_signals(df, ctx["cisd_tables"])
    df["cisd_after_ssmt_min"] = np.where(
        df["micro_ssmt"] & df["has_cisd"], df["j_cisd"] - df["micro_jform"], np.nan
    )

    # HTF / PDH-PDL / PWH-PWL / structure narrative (strictly as-of t_signal_known)
    pd_at = asof_join(df["t_signal_known"], ctx["pd_tbl"], ["PDH", "PDL", "PDO", "PDC"])
    pw_at = asof_join(df["t_signal_known"], ctx["pw_tbl"], ["PWH", "PWL"])
    for col in pd_at.columns:
        df[col] = pd_at[col].to_numpy()
    for col in pw_at.columns:
        df[col] = pw_at[col].to_numpy()
    df["daily_bias"] = np.where(df["PDC"] > df["PDO"], 1, -1)

    df["pd_swept"] = np.where(
        df["dir"] == -1,
        (df["sweep_ext_known"] > df["PDH"]) & (df["Lr"] < df["PDH"]),
        (df["sweep_ext_known"] < df["PDL"]) & (df["Hr"] > df["PDL"]),
    )
    df["pw_swept"] = np.where(
        df["dir"] == -1,
        (df["sweep_ext_known"] > df["PWH"]) & (df["Lr"] < df["PWH"]),
        (df["sweep_ext_known"] < df["PWL"]) & (df["Hr"] > df["PWL"]),
    )
    df["htf_liq"] = df["pd_swept"] | df["pw_swept"]

    pd_mid = 0.5 * (df["PDH"] + df["PDL"])
    df["pd_zone_ok"] = np.where(df["dir"] == -1, c[jt] >= pd_mid, c[jt] <= pd_mid)

    # Causal M5 swing stop & structural invalidation (using t_signal_known)
    sw = ctx["sw_m5"]
    t_q = pd.to_datetime(df["t_signal_known"], utc=True).dt.as_unit("ms").astype("int64").to_numpy()
    sw_t = pd.to_datetime(sw["t_known"], utc=True).dt.as_unit("ms").astype("int64").to_numpy()
    sw_p = sw["price"].to_numpy(float)
    sw_hi = (sw["kind"] == "H").to_numpy()
    ref_px = c[jt]
    sh_above = last_known_swing(t_q, sw_t, sw_p, sw_hi, True, True, ref_px, 40)
    sl_below = last_known_swing(t_q, sw_t, sw_p, sw_hi, False, False, ref_px, 40)
    df["swing_stop"] = np.where(
        df["dir"] == -1,
        np.nanmax(np.vstack([sh_above, df["sweep_ext_known"]]), axis=0),
        np.nanmin(np.vstack([sl_below, df["sweep_ext_known"]]), axis=0),
    )

    # H1 structural swing for HTF bias & structural stop
    swh1 = ctx["sw_h1"]
    h1_t = pd.to_datetime(swh1["t_known"], utc=True).dt.as_unit("ms").astype("int64").to_numpy()
    h1_p = swh1["price"].to_numpy(float)
    h1_hi = (swh1["kind"] == "H").to_numpy()
    h1_sh = last_known_swing(t_q, h1_t, h1_p, h1_hi, True, True, ref_px, 20)
    h1_sl = last_known_swing(t_q, h1_t, h1_p, h1_hi, False, False, ref_px, 20)
    df["struct_stop"] = np.where(
        df["dir"] == -1,
        np.nanmax(np.vstack([h1_sh, df["sweep_ext_known"]]), axis=0),
        np.nanmin(np.vstack([h1_sl, df["sweep_ext_known"]]), axis=0),
    )
    df["ref_ext_stop"] = np.where(
        df["dir"] == -1,
        np.maximum(df["Hr"], df["sweep_ext_known"]),
        np.minimum(df["Lr"], df["sweep_ext_known"]),
    )
    atr_buf = 0.35 * df["atr_ref"].fillna(12.0).to_numpy(float)
    df["atr_struct_stop"] = np.where(
        df["dir"] == -1, df["swing_stop"] + atr_buf, df["swing_stop"] - atr_buf
    )

    # True Causal MMXM State Machine (Stages 1..8)
    df["has_disp"] = (df["j_disp"] >= 0) & (df["j_disp"] <= df["j_trig"])
    df = attach_mmxm_to_signals(df, ctx["mmxm_tbl"], panel, traded=traded)

    # Narrative classification (pre-trade only)
    same_bias = df["dir"] == df["daily_bias"]
    df["narrative"] = np.select(
        [
            df["htf_liq"] & df["has_cisd"] & (df["dir"] == 1),
            df["htf_liq"] & df["has_cisd"] & (df["dir"] == -1),
            same_bias & df["pd_zone_ok"] & (df["dir"] == 1),
            same_bias & df["pd_zone_ok"] & (df["dir"] == -1),
            df["K"],
            ~df["pd_zone_ok"] & ~same_bias,
        ],
        [
            "bullish_reversal", "bearish_reversal", "bullish_continuation", "bearish_continuation",
            "contradictory", "contradictory",
        ],
        default="range_rejection",
    )
    return df.reset_index(drop=True)
