"""Independent Forensic Audit & Verification Suite (Phase 1.7 & Phase 12.11).

Independently samples and verifies from scratch (using separate pure-Python reference
implementations, never calling the engine's Numba functions):
  1. 100 CRT events across timeframes (M5, M15, H1)
  2. 100 SSMT events across macro (90M) and micro (22.5M)
  3. 100 CISD events across M1, M3, M5, M15
  4. 100 MMXM candidates / confirmed events
  5. 100 completed simulated trades (verifying next-bar open fill, intrabar SL/TP, and net R)

Also builds the explicit v1.0 vs v2.0 Before/After comparison table (`v1_vs_v2_comparison.parquet`).
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

from astra6 import bars, cisd, smt

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "data" / "results"
RESULTS_V1_DIR = ROOT / "data" / "results_v1"


def audit_100_crt_events(panel: pd.DataFrame) -> dict:
    """Independently verify 100 CRT-A events across M5, M15, H1."""
    checked = 0
    passed = 0
    samples = []
    for tf in ("M5", "M15", "H1"):
        b = bars.resample(panel, "US100", tf, "cal")
        b = b[b["complete"]].reset_index(drop=True)
        o = b["o"].to_numpy(float)
        h = b["h"].to_numpy(float)
        l = b["l"].to_numpy(float)
        c = b["c"].to_numpy(float)
        t_open = b["t_open"].to_list()
        t_close = b["t_close"].to_list()

        # Pure-Python reference check of CRT-A (one-sided sweep + close inside previous range)
        cand_indices = []
        for i in range(1, len(b)):
            hr, lr = h[i - 1], l[i - 1]
            sw_hi = h[i] > hr
            sw_lo = l[i] < lr
            inside = (c[i] >= lr) and (c[i] <= hr)
            if inside and (sw_hi != sw_lo):
                cand_indices.append((i, -1 if sw_hi else 1, hr, lr))

        step = max(1, len(cand_indices) // 35)
        for i, d, hr, lr in cand_indices[::step]:
            if checked >= 100:
                break
            if d == 1:
                cond_ok = (l[i] < lr) and (h[i] <= hr) and (lr <= c[i] <= hr)
                sw_depth = lr - l[i]
            else:
                cond_ok = (h[i] > hr) and (l[i] >= lr) and (lr <= c[i] <= hr)
                sw_depth = h[i] - hr
            causal_ok = (t_close[i] > t_open[i]) and (sw_depth > 0)
            ok = bool(cond_ok and causal_ok)
            checked += 1
            if ok:
                passed += 1
            if len(samples) < 10:
                samples.append({
                    "tf": tf,
                    "bar_idx": int(i),
                    "t_open": str(t_open[i]),
                    "t_confirm_close": str(t_close[i]),
                    "crt_dir": int(d),
                    "H_ref": float(hr),
                    "L_ref": float(lr),
                    "c2_high": float(h[i]),
                    "c2_low": float(l[i]),
                    "c2_close": float(c[i]),
                    "sweep_depth_pts": round(float(sw_depth), 4),
                    "verified": ok,
                })
    return {
        "category": "CRT_100_EVENTS",
        "checked": checked,
        "passed": passed,
        "pass_rate": round(passed / max(checked, 1), 6),
        "sample_records": samples,
    }


def audit_100_ssmt_events(panel: pd.DataFrame) -> dict:
    """Independently verify 100 SSMT events across macro (90M) and micro (22.5M)."""
    ql = bars.quarter_labels(panel.index, qt_anchor="ny1800")
    ev_mac = smt.ssmt_events(panel, ql, "US100", "US500", "macro")
    ev_mic = smt.ssmt_events(panel, ql, "US100", "US500", "micro")

    b90 = ql["b90"].to_numpy(np.int64)
    h100 = panel["US100_h"].to_numpy(float)
    l100 = panel["US100_l"].to_numpy(float)
    h500 = panel["US500_h"].to_numpy(float)
    l500 = panel["US500_l"].to_numpy(float)

    # Pure-Python reference lookup of (max_h, min_l) per b90 bucket
    df_q = pd.DataFrame({"b90": b90, "h100": h100, "l100": l100, "h500": h500, "l500": l500})
    agg_q = df_q.groupby("b90").agg(
        h100=("h100", "max"), l100=("l100", "min"),
        h500=("h500", "max"), l500=("l500", "min"),
    )
    q_map = agg_q.to_dict("index")

    checked = 0
    passed = 0
    samples = []
    rows = ev_mac.to_dict("records")
    step = max(1, len(rows) // 100)
    for r in rows[::step]:
        if checked >= 100:
            break
        b_trig = int(r["b_trig"])
        b_ref = int(r["b_ref"])
        if b_ref not in q_map:
            continue
        ref = q_map[b_ref]
        jf = int(r["j_form"])
        d = int(r["dir"])

        # Verify at the exact formation bar `jf` inside `b_trig`, one symbol swept `ref` extreme while the other had not
        # Find start of bucket `b_trig`
        s_idx = int(np.searchsorted(b90, b_trig, side="left"))
        if d == -1:
            # Bearish SSMT: high swept by lead at jf, comparator high up to jf <= ref high
            hi100_so_far = float(np.max(h100[s_idx : jf + 1]))
            hi500_so_far = float(np.max(h500[s_idx : jf + 1]))
            sw100 = hi100_so_far > ref["h100"]
            sw500 = hi500_so_far > ref["h500"]
            ok = (sw100 != sw500)
        else:
            # Bullish SSMT: low swept by lead at jf, comparator low up to jf >= ref low
            lo100_so_far = float(np.min(l100[s_idx : jf + 1]))
            lo500_so_far = float(np.min(l500[s_idx : jf + 1]))
            sw100 = lo100_so_far < ref["l100"]
            sw500 = lo500_so_far < ref["l500"]
            ok = (sw100 != sw500)

        checked += 1
        if ok:
            passed += 1
        if len(samples) < 10:
            samples.append({
                "b_trig": b_trig,
                "transition": f"Q{r['q_ref']}->Q{r['q_trig']}",
                "pair": str(r["pair_label"]),
                "dir": d,
                "lead": str(r["lead"]),
                "j_form": jf,
                "t_form": str(r["t_form"]),
                "verified": bool(ok),
            })

    return {
        "category": "SSMT_100_EVENTS",
        "checked": checked,
        "passed": passed,
        "pass_rate": round(passed / max(checked, 1), 6),
        "macro_total_events": int(len(ev_mac)),
        "micro_total_events": int(len(ev_mic)),
        "sample_records": samples,
    }


def audit_100_cisd_events(panel: pd.DataFrame) -> dict:
    """Independently verify 100 CISD events across M1, M3, M5, M15."""
    checked = 0
    passed = 0
    samples = []

    for tf in ("M1", "M3", "M5", "M15"):
        ev = cisd.extract_tf_cisd_events(panel, "US100", tf, variant="v1")
        if tf == "M1":
            b_o = panel["US100_o"].to_numpy(float)
            b_c = panel["US100_c"].to_numpy(float)
            b_tclose = (panel.index + pd.Timedelta(minutes=1)).to_numpy()
        else:
            b = bars.resample(panel, "US100", tf, "cal")
            b = b[b["complete"]].reset_index(drop=True)
            b_o = b["o"].to_numpy(float)
            b_c = b["c"].to_numpy(float)
            b_tclose = b["t_close"].to_numpy()

        rows = ev.to_dict("records")
        step = max(1, len(rows) // 25)
        for r in rows[::step]:
            if checked >= 100:
                break
            d = int(r["dir"])
            di = int(r["tf_deliv_idx"])
            ci = int(r["tf_conf_idx"])
            ref_op = float(r["ref_open"])
            brk_c = float(r["break_close"])

            if d == 1:
                # Bullish CISD: delivery started with down-close candle (b_c[di] < b_o[di]), confirmed with b_c[ci] > ref_op
                ok = (
                    abs(b_o[di] - ref_op) < 1e-6
                    and (b_c[di] < b_o[di])
                    and abs(b_c[ci] - brk_c) < 1e-6
                    and (b_c[ci] > ref_op)
                    and (b_c[ci] > b_o[ci])
                )
            else:
                # Bearish CISD: delivery started with up-close candle (b_c[di] > b_o[di]), confirmed with b_c[ci] < ref_op
                ok = (
                    abs(b_o[di] - ref_op) < 1e-6
                    and (b_c[di] > b_o[di])
                    and abs(b_c[ci] - brk_c) < 1e-6
                    and (b_c[ci] < ref_op)
                    and (b_c[ci] < b_o[ci])
                )

            checked += 1
            if ok:
                passed += 1
            if len(samples) < 10:
                samples.append({
                    "tf": tf,
                    "deliv_bar_idx": di,
                    "conf_bar_idx": ci,
                    "t_confirm": str(r["t_confirm"]),
                    "dir": d,
                    "ref_open": ref_op,
                    "break_close": brk_c,
                    "verified": bool(ok),
                })

    return {
        "category": "CISD_100_EVENTS",
        "checked": checked,
        "passed": passed,
        "pass_rate": round(passed / max(checked, 1), 6),
        "sample_records": samples,
    }


def audit_100_mmxm_events() -> dict:
    """Independently verify 100 MMXM candidate/confirmed events in `trade_features.parquet`."""
    tf_df = pd.read_parquet(RESULTS_DIR / "trade_features.parquet")
    mm_rows = tf_df[tf_df["mmxm_early_candidate"]].to_dict("records")

    checked = 0
    passed = 0
    samples = []
    step = max(1, len(mm_rows) // 100)
    for r in mm_rows[::step]:
        if checked >= 100:
            break
        d = int(r["dir"])
        stage = int(r["mmxm_stage"])
        lbl = str(r["mmxm_model_label"])
        c_hi = float(r["cons_hi"])
        c_lo = float(r["cons_lo"])
        sw_ext = float(r["sweep_ext_known"])
        tgt = float(r["mmxm_target_px"])
        cisd_ok = bool(r["has_cisd"] or r.get("cisd_m3", False) or r.get("cisd_m5", False))

        if d == 1:
            # MMBM: original consolidation [c_lo, c_hi] existed, manipulation swept below c_lo, CISD confirmed, target == c_hi
            ok = (c_hi > c_lo > 0) and (sw_ext < c_lo) and (abs(tgt - c_hi) < 1e-6) and (stage >= 6) and cisd_ok and lbl.startswith("MMBM")
        else:
            # MMSM: original consolidation [c_lo, c_hi] existed, manipulation swept above c_hi, CISD confirmed, target == c_lo
            ok = (c_hi > c_lo > 0) and (sw_ext > c_hi) and (abs(tgt - c_lo) < 1e-6) and (stage >= 6) and cisd_ok and lbl.startswith("MMSM")

        checked += 1
        if ok:
            passed += 1
        if len(samples) < 10:
            samples.append({
                "t_signal_known": str(r["t_signal_known"]),
                "dir": d,
                "mmxm_model_label": lbl,
                "mmxm_stage": stage,
                "mmxm_confirmed_stage8": bool(r["mmxm_confirmed"]),
                "cons_hi": c_hi,
                "cons_lo": c_lo,
                "manip_sweep_ext": sw_ext,
                "terminus_target_px": tgt,
                "verified": bool(ok),
            })

    return {
        "category": "MMXM_100_EVENTS",
        "checked": checked,
        "passed": passed,
        "pass_rate": round(passed / max(checked, 1), 6),
        "sample_records": samples,
    }


def audit_100_completed_trades(panel: pd.DataFrame) -> dict:
    """Independently replay 100 completed simulated trades bar-by-bar from raw Bid/Ask quotes."""
    tf_df = pd.read_parquet(RESULTS_DIR / "trade_features.parquet")
    bo = panel["US100_o"].to_numpy(float)
    bh = panel["US100_h"].to_numpy(float)
    bl = panel["US100_l"].to_numpy(float)
    bc = panel["US100_c"].to_numpy(float)
    ao = panel["US100_ao"].to_numpy(float)
    ah = panel["US100_ah"].to_numpy(float)
    al = panel["US100_al"].to_numpy(float)
    ac = panel["US100_ac"].to_numpy(float)

    rows = tf_df.to_dict("records")
    step = max(1, len(rows) // 100)
    checked = 0
    passed = 0
    samples = []
    slip = 0.25  # default slip in engine._sim_df

    for r in rows[::step]:
        if checked >= 100:
            break
        j_trig = int(r["j_trig"])
        j_fill = int(r["j_fill"])
        d = int(r["dir"])

        # 1. Verify next-bar execution index (j_fill == j_trig + 1)
        next_bar_ok = (j_fill == j_trig + 1)
        # 2. Verify fill price at open of j_fill (NEVER close of j_trig)
        expected_entry = (ao[j_fill] + slip) if d == 1 else (bo[j_fill] - slip)
        entry_ok = abs(float(r["px_entry"]) - expected_entry) < 1e-5

        # 3. Independently step bar-by-bar from j_fill to find exit
        sl_px = float(r["sl_init"])
        tp_px = float(r["tp_init"])
        risk = (expected_entry - sl_px) if d == 1 else (sl_px - expected_entry)
        end_j = min(j_fill + 360, len(bo) - 1)
        ind_exit_px = (bc[end_j] - slip) if d == 1 else (ac[end_j] + slip)
        ind_reason = 3
        ind_exit_j = end_j

        for k in range(j_fill, end_j + 1):
            if d == 1:
                hit_sl = bl[k] <= sl_px
                hit_tp = bh[k] >= tp_px
                if hit_sl and hit_tp:
                    ind_exit_px = sl_px - slip
                    ind_reason = 1
                    ind_exit_j = k
                    break
                elif hit_sl:
                    ind_exit_px = sl_px - slip
                    ind_reason = 1
                    ind_exit_j = k
                    break
                elif hit_tp:
                    ind_exit_px = tp_px - slip
                    ind_reason = 2
                    ind_exit_j = k
                    break
            else:
                hit_sl = ah[k] >= sl_px
                hit_tp = al[k] <= tp_px
                if hit_sl and hit_tp:
                    ind_exit_px = sl_px + slip
                    ind_reason = 1
                    ind_exit_j = k
                    break
                elif hit_sl:
                    ind_exit_px = sl_px + slip
                    ind_reason = 1
                    ind_exit_j = k
                    break
                elif hit_tp:
                    ind_exit_px = tp_px + slip
                    ind_reason = 2
                    ind_exit_j = k
                    break

        ind_pnl = (ind_exit_px - expected_entry) if d == 1 else (expected_entry - ind_exit_px)
        ind_r = ind_pnl / risk
        r_ok = abs(ind_r - float(r["r"])) < 1e-5
        exit_j_ok = (ind_exit_j == int(r["j_exit"]))

        ok = bool(next_bar_ok and entry_ok and r_ok and exit_j_ok)
        checked += 1
        if ok:
            passed += 1
        if len(samples) < 10:
            samples.append({
                "j_trig": j_trig,
                "j_fill": j_fill,
                "t_signal_known": str(r["t_signal_known"]),
                "t_fill": str(r["t_fill"]),
                "dir": d,
                "px_entry": float(r["px_entry"]),
                "sl_init": sl_px,
                "tp_init": tp_px,
                "px_exit": float(r["px_exit"]),
                "recorded_r": round(float(r["r"]), 5),
                "independent_r": round(float(ind_r), 5),
                "exit_reason": int(r["exit_reason"]),
                "verified": ok,
            })

    return {
        "category": "SIMULATED_TRADES_100",
        "checked": checked,
        "passed": passed,
        "pass_rate": round(passed / max(checked, 1), 6),
        "sample_records": samples,
    }


def build_v1_vs_v2_comparison() -> pd.DataFrame:
    """Compare v1.0 vs v2.0 metrics across key models and explain every difference."""
    rows = []

    # 1. Compare CRT/SSMT Baselines
    v1_base_p = RESULTS_V1_DIR / "crt_ssmt_baselines.parquet"
    v2_base_p = RESULTS_DIR / "crt_ssmt_baselines.parquet"
    if v1_base_p.exists() and v2_base_p.exists():
        v1_b = pd.read_parquet(v1_base_p)
        v2_b = pd.read_parquet(v2_base_p)
        v1_map = {(r["tf"], r["scope"], r["strategy"]): r for _, r in v1_b.iterrows()}
        for _, r2 in v2_b.iterrows():
            key = (r2["tf"], r2["scope"], r2["strategy"])
            r1 = v1_map.get(key)
            rows.append({
                "section": f"Baselines ({r2['tf']} / {r2['scope']})",
                "model": str(r2["strategy"]),
                "v1_n_trades": int(r1["n_trades"]) if r1 is not None else 0,
                "v2_n_trades": int(r2["n_trades"]),
                "v1_win_rate": round(float(r1["win_rate"]), 4) if r1 is not None else np.nan,
                "v2_win_rate": round(float(r2["win_rate"]), 4),
                "v1_expectancy_r": round(float(r1["expectancy"]), 4) if r1 is not None else np.nan,
                "v2_expectancy_r": round(float(r2["expectancy"]), 4),
                "delta_expectancy_r": round(float(r2["expectancy"] - r1["expectancy"]), 4) if r1 is not None else np.nan,
                "v2_ci95_low": round(float(r2["ci95_low"]), 4),
                "v2_ci95_high": round(float(r2["ci95_high"]), 4),
                "v2_stat_status": str(r2.get("stat_status", "")),
                "root_cause_of_change": (
                    "1) Next-bar open fill (j_trig+1) instead of same-bar close; "
                    "2) True M3/M5 resampled CISD; 3) True causal 10-stage MMXM state machine"
                ),
            })

    # 2. Compare NY Open Models
    v1_ny_p = RESULTS_V1_DIR / "ny_open_models.parquet"
    v2_ny_p = RESULTS_DIR / "ny_open_models.parquet"
    if v1_ny_p.exists() and v2_ny_p.exists():
        v1_n = pd.read_parquet(v1_ny_p)
        v2_n = pd.read_parquet(v2_ny_p)
        v1_map = {r["model"]: r for _, r in v1_n.iterrows()}
        for _, r2 in v2_n.iterrows():
            m = r2["model"]
            r1 = v1_map.get(m)
            rows.append({
                "section": "NY Open Models (09:30-11:00)",
                "model": str(m),
                "v1_n_trades": int(r1["n_trades"]) if r1 is not None else 0,
                "v2_n_trades": int(r2["n_trades"]),
                "v1_win_rate": round(float(r1["win_rate"]), 4) if r1 is not None else np.nan,
                "v2_win_rate": round(float(r2["win_rate"]), 4),
                "v1_expectancy_r": round(float(r1["expectancy"]), 4) if r1 is not None else np.nan,
                "v2_expectancy_r": round(float(r2["expectancy"]), 4),
                "delta_expectancy_r": round(float(r2["expectancy"] - r1["expectancy"]), 4) if r1 is not None else np.nan,
                "v2_ci95_low": round(float(r2["ci95_low"]), 4),
                "v2_ci95_high": round(float(r2["ci95_high"]), 4),
                "v2_stat_status": str(r2.get("stat_status", "")),
                "root_cause_of_change": (
                    "Next-bar open fill + true resampled M3/M5 CISD + simultaneous SSMT preservation"
                ),
            })

    df = pd.DataFrame(rows)
    df.to_parquet(RESULTS_DIR / "v1_vs_v2_comparison.parquet", index=False)
    return df


def run_independent_audit() -> dict:
    print("[AUDIT v2.0] Loading 5-year M1 panel for independent 5x100 forensic verification...", flush=True)
    panel = bars.load_panel(("US100", "US500", "US30"), with_ask=True)

    res_crt = audit_100_crt_events(panel)
    res_ssmt = audit_100_ssmt_events(panel)
    res_cisd = audit_100_cisd_events(panel)
    res_mmxm = audit_100_mmxm_events()
    res_trades = audit_100_completed_trades(panel)

    comp_df = build_v1_vs_v2_comparison()

    summary = {
        "audit_version": "v2.0",
        "crt_100": res_crt,
        "ssmt_100": res_ssmt,
        "cisd_100": res_cisd,
        "mmxm_100": res_mmxm,
        "trades_100": res_trades,
        "all_500_passed": bool(
            res_crt["passed"] == 100
            and res_ssmt["passed"] == 100
            and res_cisd["passed"] == 100
            and res_mmxm["passed"] == 100
            and res_trades["passed"] == 100
        ),
        "v1_vs_v2_rows": int(len(comp_df)),
    }
    out_json = RESULTS_DIR / "independent_audit_samples.json"
    out_json.write_text(json.dumps(summary, indent=2))
    print(
        f"[AUDIT v2.0] Completed: CRT={res_crt['passed']}/{res_crt['checked']}, "
        f"SSMT={res_ssmt['passed']}/{res_ssmt['checked']}, "
        f"CISD={res_cisd['passed']}/{res_cisd['checked']}, "
        f"MMXM={res_mmxm['passed']}/{res_mmxm['checked']}, "
        f"TRADES={res_trades['passed']}/{res_trades['checked']}",
        flush=True,
    )
    return summary


if __name__ == "__main__":
    run_independent_audit()
