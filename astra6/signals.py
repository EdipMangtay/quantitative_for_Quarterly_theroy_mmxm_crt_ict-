"""Event-driven candidate extractor & narrative annotator (strictly causal).

Every signal produced here carries:
  * the full signal lifecycle timestamps:
    t_sweep -> t_reclaim -> t_crt_close (if confirmed) -> t_ssmt -> t_cisd -> t_entry
  * a **Pre-Trade Narrative** computed exclusively from quantities whose
    ``t_known <= t_entry`` (HTF structure, PDH/PDL, PWH/PWL, dealing-range
    premium/discount, FVG, displacement, MMXM early-stage state, opening-range
    context, session & quarter phase).
  * stop levels for all five stop models, each using only data observable at
    or before ``t_entry``.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .bars import TF_MIN, quarter_labels, resample
from .clock import NY, dst_regime
from .crt import classify_confirmed, running_extreme, scan_crt
from .ict import asof_join, atr_wilder, fvg_table, last_known_swing, period_levels, swing_table
from .smt import attach_ssmt, ssmt_events


def build_context(panel: pd.DataFrame, traded: str = "US100", comps=("US500", "US30")) -> dict:
    """Precompute strictly-causal indicator tables on the M1 panel."""
    idx = panel.index
    ql = quarter_labels(idx)
    loc = idx.tz_convert(NY)
    mod = (loc.hour * 60 + loc.minute).to_numpy()
    ny_dates = pd.Series(loc.date, index=idx)
    regimes = pd.Series({d: dst_regime(d) for d in pd.unique(ny_dates)})
    ql["ny_mod"] = mod
    ql["min_from_ny_open"] = mod - (9 * 60 + 30)
    ql["ldn_mod"] = (idx.tz_convert("Europe/London").hour * 60 + idx.tz_convert("Europe/London").minute).to_numpy()
    ql["min_from_ldn_open"] = ql["ldn_mod"] - 8 * 60
    ql["regime"] = ny_dates.map(regimes).to_numpy()
    ql["year"] = loc.year.to_numpy()
    ql["month"] = loc.strftime("%Y-%m").to_numpy()
    # M1 ATR
    atr1 = atr_wilder(panel[f"{traded}_h"].to_numpy(float), panel[f"{traded}_l"].to_numpy(float),
                      panel[f"{traded}_c"].to_numpy(float), 14)
    # HTF bars & swings
    d1 = resample(panel, traded, "D1")
    h4 = resample(panel, traded, "H4")
    h1_cal = resample(panel, traded, "H1", "cal")
    m5 = resample(panel, traded, "M5")
    sw_m5 = swing_table(m5, 2, 2)
    sw_h1 = swing_table(h1_cal, 2, 2)
    sw_h4 = swing_table(h4, 2, 2)
    # map sw_m5 t_known to M1 integer index for the numba simulator
    sw_m5["j_known"] = idx.searchsorted(sw_m5["t_known"], side="left")
    # PDH/PDL and PWH/PWL
    pd_tbl = period_levels(d1[d1["complete"]], "PD")
    # weekly: group D1 by ISO week of t_open
    d1c = d1[d1["complete"]].copy()
    wk = pd.to_datetime(d1c["t_open"]).dt.tz_convert(NY).dt.tz_localize(None).dt.to_period("W")
    w_bars = d1c.groupby(wk).agg(o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"),
                                 t_close=("t_close", "last")).reset_index(drop=True)
    pw_tbl = period_levels(w_bars, "PW")
    # SSMT tables (macro & micro) against primary comparator
    ssmt_mac = ssmt_events(panel, ql, traded, comps[0], "macro")
    ssmt_mic = ssmt_events(panel, ql, traded, comps[0], "micro")
    ssmt_mac_30 = ssmt_events(panel, ql, traded, comps[1], "macro") if len(comps) > 1 else pd.DataFrame()
    ssmt_mic_30 = ssmt_events(panel, ql, traded, comps[1], "micro") if len(comps) > 1 else pd.DataFrame()
    return {
        "panel": panel, "ql": ql, "atr1": atr1, "traded": traded, "comps": comps,
        "d1": d1, "h4": h4, "h1_cal": h1_cal, "m5": m5,
        "sw_m5": sw_m5, "sw_h1": sw_h1, "sw_h4": sw_h4,
        "pd_tbl": pd_tbl, "pw_tbl": pw_tbl,
        "ssmt_mac": ssmt_mac, "ssmt_mic": ssmt_mic,
        "ssmt_mac_30": ssmt_mac_30, "ssmt_mic_30": ssmt_mic_30,
    }


def extract_crt_events(ctx: dict, tf: str = "M15", anchor: str = "cal") -> pd.DataFrame:
    """Scan one (tf, anchor) stream and return a flat table of sweep events
    (both directions) with all confirmation & early-entry indices attached."""
    panel = ctx["panel"]
    traded = ctx["traded"]
    comps = ctx["comps"]
    idx = panel.index
    bars = resample(panel, traded, tf, anchor)
    bars = bars[bars["complete"]].reset_index(drop=True)
    m = TF_MIN[tf]
    # map each HTF bar to M1 slice [i0, i1)
    i0 = idx.searchsorted(bars["t_open"].to_numpy(), side="left")
    i1 = idx.searchsorted(bars["t_close"].to_numpy(), side="left")
    # previous candle is valid reference iff contiguous and sufficiently populated
    Href = np.roll(bars["h"].to_numpy(float), 1)
    Lref = np.roll(bars["l"].to_numpy(float), 1)
    Oref = np.roll(bars["o"].to_numpy(float), 1)
    Cref = np.roll(bars["c"].to_numpy(float), 1)
    prev_close = np.roll(bars["t_close"].to_numpy(), 1)
    gap_min = (bars["t_open"].to_numpy() - prev_close) / np.timedelta64(1, "m")
    valid = (np.arange(len(bars)) > 0) & (gap_min <= 5) & (bars["n"].to_numpy() >= max(1, m // 2))
    # comparator reference highs/lows on the exact same M1 slices
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
        sub = bars.assign(Hr=Href, Lr=Lref, Or=Oref, Cr=Cref, sw=jsw >= 0, ot=jot >= 0,
                          j_open=i0, j_close=i1 - 1, j_sweep=jsw, j_other=jot, j_reclaim=jrc,
                          j_cisd=jci, j_disp=jdp, j_cmp0=jc0, j_cmp1=jc1,
                          ext_at_cisd=ext_cisd[:, d], atr_ref=atr_ref, dir=direction,
                          tf=tf, anchor=anchor)
        flags = classify_confirmed(sub, d)
        sub = pd.concat([sub, flags], axis=1)
        # CRT-E (displacement inside candle + close inside) & CRT-F (next candle closes beyond current body in dir)
        sub["E"] = sub["A"] & (sub["j_disp"] >= 0) & (sub["j_disp"] <= sub["j_close"])
        nxt_c = np.roll(bars["c"].to_numpy(float), -1)
        nxt_j = np.roll(i1 - 1, -1)
        sub["F"] = sub["A"] & ((nxt_c < np.minimum(sub.o, sub.c)) if direction == -1 else (nxt_c > np.maximum(sub.o, sub.c)))
        sub["j_next_close"] = nxt_j
        # CRT-H: two-candle sweep & reclaim — candle b-1 swept and closed *outside*, candle b closes back inside Hr_{b-1}..Lr_{b-1}
        prev_sw_out = np.roll((jsw >= 0) & (jot < 0) & ((bars["c"] > Href) if direction == -1 else (bars["c"] < Lref)), 1)
        Hr2 = np.roll(Href, 1)
        Lr2 = np.roll(Lref, 1)
        sub["H"] = prev_sw_out & (bars["c"] >= Lr2) & (bars["c"] <= Hr2)
        sub["Hr_h"] = np.where(sub["H"], Hr2, sub["Hr"])
        sub["Lr_h"] = np.where(sub["H"], Lr2, sub["Lr"])
        sub = sub[sub["sw"] | sub["H"]].copy()
        rows.append(sub)
    df = pd.concat(rows, ignore_index=True)
    # sweep depth & wick metrics at candle close
    df["sweep_depth"] = np.where(df["dir"] == -1, df["h"] - df["Hr"], df["Lr"] - df["l"])
    df["return_depth"] = np.where(df["dir"] == -1, df["Hr"] - df["c"], df["c"] - df["Lr"])
    df["sweep_atr"] = df["sweep_depth"] / df["atr_ref"].replace(0, np.nan)
    rng = (df["h"] - df["l"]).replace(0, np.nan)
    body = (df["c"] - df["o"]).abs()
    df["wick_body_ratio"] = (rng - body) / (body + 1e-6)
    df["body_pos"] = (df["c"] - df["l"]) / rng
    return df.sort_values(["j_close", "dir"]).reset_index(drop=True)


def materialize_entries(ctx: dict, crt_df: pd.DataFrame, mode: str) -> pd.DataFrame:
    """Turn raw CRT events into causal trade candidates for a given entry mode:

      * ``confirmed``       : enter at ``j_close`` of the CRT candle (requires A/B/C/D/E/K/J/H)
      * ``confirmed_next``  : enter at ``j_next_close`` (CRT-F)
      * ``confirmed_cisd``  : enter at ``max(j_close, j_cisd)`` within 15 min of close
      * ``dev_cisd``        : enter at ``j_cisd`` STRICTLY BEFORE ``j_close`` (developing CRT + M1 CISD)
      * ``dev_reclaim``     : enter at ``j_reclaim`` strictly before ``j_close`` (CRT-I early reclaim)

    Developing modes NEVER peek at the eventual CRT candle close or high/low;
    their stop extreme is the running M1 extreme from ``j_sweep`` to ``j_trig``.
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
        df["sweep_ext_known"] = np.where(df["dir"] == -1,
                                         np.maximum(df["h"], h[df["j_trig"]]),
                                         np.minimum(df["l"], l[df["j_trig"]]))
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
    jsw = np.maximum(df["j_sweep"].to_numpy(int), df["j_open"].to_numpy(int))
    idx = panel.index
    df["t_trig"] = idx[jt]
    df["t_sweep"] = idx[jsw]
    # quarter / session context at trigger AND at sweep
    for prefix, jarr in (("trig", jt), ("sw", jsw)):
        for col in ("q6", "q90", "q22", "q5", "b6", "b90", "b22", "ny_mod", "min_from_ny_open",
                    "min_from_ldn_open", "regime", "year", "month"):
            df[f"{col}_{prefix}"] = ql[col].to_numpy()[jarr]
    # Standard SMT at trigger: traded swept its ref level, comparator 0 has NOT swept by j_trig
    df["std_smt"] = (df["j_sweep"] >= 0) & ((df["j_cmp0"] < 0) | (df["j_cmp0"] > df["j_trig"]))
    df["std_smt_30"] = (df["j_sweep"] >= 0) & ((df["j_cmp1"] < 0) | (df["j_cmp1"] > df["j_trig"]))
    # Attach macro & micro SSMT (active and formed <= j_trig)
    df = attach_ssmt(df, ctx["ssmt_mac"], "macro")
    df = attach_ssmt(df, ctx["ssmt_mic"], "micro")
    df["any_ssmt"] = df["macro_ssmt"] | df["micro_ssmt"]
    df["both_ssmt"] = df["macro_ssmt"] & df["micro_ssmt"]
    # check conflicting direction macro vs micro
    opp = df.assign(dir=-df["dir"])
    opp = attach_ssmt(opp, ctx["ssmt_mac"], "macro")
    df["macro_opp_ssmt"] = opp["macro_ssmt"].to_numpy()
    df["ssmt_dt_min"] = np.where(df["micro_ssmt"], df["j_trig"] - df["micro_jform"],
                                 np.where(df["macro_ssmt"], df["j_trig"] - df["macro_jform"], np.nan))
    df["sw_ssmt_dt_min"] = np.where(df["micro_ssmt"], df["j_sweep"] - df["micro_jform"], np.nan)
    # CISD flag at or before trigger
    df["has_cisd"] = (df["j_cisd"] >= 0) & (df["j_cisd"] <= df["j_trig"])
    df["cisd_after_ssmt_min"] = np.where(df["micro_ssmt"] & df["has_cisd"],
                                         df["j_cisd"] - df["micro_jform"], np.nan)
    # HTF / PDH-PDL / PWH-PWL / structure narrative (strictly as-of t_trig)
    pd_at = asof_join(df["t_trig"], ctx["pd_tbl"], ["PDH", "PDL", "PDO", "PDC"])
    pw_at = asof_join(df["t_trig"], ctx["pw_tbl"], ["PWH", "PWL"])
    for col in pd_at.columns:
        df[col] = pd_at[col].to_numpy()
    for col in pw_at.columns:
        df[col] = pw_at[col].to_numpy()
    df["daily_bias"] = np.where(df["PDC"] > df["PDO"], 1, -1)
    # PD/PW sweep inside the CRT candle up to j_trig
    df["pd_swept"] = np.where(df["dir"] == -1,
                              (df["sweep_ext_known"] > df["PDH"]) & (df["Lr"] < df["PDH"]),
                              (df["sweep_ext_known"] < df["PDL"]) & (df["Hr"] > df["PDL"]))
    df["pw_swept"] = np.where(df["dir"] == -1,
                              (df["sweep_ext_known"] > df["PWH"]) & (df["Lr"] < df["PWH"]),
                              (df["sweep_ext_known"] < df["PWL"]) & (df["Hr"] > df["PWL"]))
    df["htf_liq"] = df["pd_swept"] | df["pw_swept"]
    # Premium/discount inside previous day range
    pd_mid = 0.5 * (df["PDH"] + df["PDL"])
    df["pd_zone_ok"] = np.where(df["dir"] == -1, c[jt] >= pd_mid, c[jt] <= pd_mid)
    # Causal M5 swing stop & structural invalidation
    sw = ctx["sw_m5"]
    t_q = pd.to_datetime(df["t_trig"], utc=True).dt.as_unit("ms").astype("int64").to_numpy()
    sw_t = pd.to_datetime(sw["t_known"], utc=True).dt.as_unit("ms").astype("int64").to_numpy()
    sw_p = sw["price"].to_numpy(float)
    sw_hi = (sw["kind"] == "H").to_numpy()
    ref_px = c[jt]
    sh_above = last_known_swing(t_q, sw_t, sw_p, sw_hi, True, True, ref_px, 40)
    sl_below = last_known_swing(t_q, sw_t, sw_p, sw_hi, False, False, ref_px, 40)
    df["swing_stop"] = np.where(df["dir"] == -1, np.nanmax(np.vstack([sh_above, df["sweep_ext_known"]]), axis=0),
                                np.nanmin(np.vstack([sl_below, df["sweep_ext_known"]]), axis=0))
    # H1 structural swing for HTF bias & structural stop
    swh1 = ctx["sw_h1"]
    h1_t = pd.to_datetime(swh1["t_known"], utc=True).dt.as_unit("ms").astype("int64").to_numpy()
    h1_p = swh1["price"].to_numpy(float)
    h1_hi = (swh1["kind"] == "H").to_numpy()
    h1_sh = last_known_swing(t_q, h1_t, h1_p, h1_hi, True, True, ref_px, 20)
    h1_sl = last_known_swing(t_q, h1_t, h1_p, h1_hi, False, False, ref_px, 20)
    df["struct_stop"] = np.where(df["dir"] == -1, np.nanmax(np.vstack([h1_sh, df["sweep_ext_known"]]), axis=0),
                                 np.nanmin(np.vstack([h1_sl, df["sweep_ext_known"]]), axis=0))
    df["ref_ext_stop"] = np.where(df["dir"] == -1, np.maximum(df["Hr"], df["sweep_ext_known"]),
                                  np.minimum(df["Lr"], df["sweep_ext_known"]))
    # MMXM early-stage proxy (causal at t_trig): prior consolidation + manipulation leg sweeping liquidity + CISD (+ displacement)
    df["has_disp"] = (df["j_disp"] >= 0) & (df["j_disp"] <= df["j_trig"])
    df["mmxm"] = df["has_cisd"] & (df["has_disp"] | df["pd_zone_ok"])
    # Narrative classification (pre-trade only)
    same_bias = df["dir"] == df["daily_bias"]
    df["narrative"] = np.select(
        [df["htf_liq"] & df["has_cisd"] & (df["dir"] == 1),
         df["htf_liq"] & df["has_cisd"] & (df["dir"] == -1),
         same_bias & df["pd_zone_ok"] & (df["dir"] == 1),
         same_bias & df["pd_zone_ok"] & (df["dir"] == -1),
         df["K"],
         ~df["pd_zone_ok"] & ~same_bias],
        ["bullish_reversal", "bearish_reversal", "bullish_continuation", "bearish_continuation",
         "contradictory", "contradictory"],
        default="range_rejection",
    )
    return df.reset_index(drop=True)

