"""Opening Session & Opening Range Research Engine (Sections 3, 10, 11).

Strictly causal rules:
* An Opening Range (OR5, OR15, OR30, OR60) has a *completed* High/Low/Midpoint
   ONLY at or after ``t_open + duration``.
* Before ``t_open + duration`` only the *running* high/low since ``t_open`` is
  observable, stored in separate columns ``run_or_h``, ``run_or_l``.
* Calendar-aligned H1 (09:00–10:00 NY) and NY-open-anchored H1 (09:30–10:30 NY)
  are kept strictly separate; a 09:30–10:30 H1 candle is never marked confirmed
  before 10:30 NY.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .clock import LDN, NY

NY_WINDOWS: list[tuple[str, int, int]] = [
    ("08:30-09:00", -60, -30),
    ("09:00-09:15", -30, -15),
    ("09:15-09:30", -15, 0),
    ("09:30-09:35", 0, 5),
    ("09:30-09:45", 0, 15),
    ("09:30-10:00", 0, 30),
    ("09:30-10:30", 0, 60),
    ("10:00-11:00", 30, 90),
    ("11:00-12:00", 90, 150),
]

NY_NORM_WINDOWS: list[tuple[str, int, int]] = [
    ("Open -60..-30m", -60, -30),
    ("Open -30..-15m", -30, -15),
    ("Open -15..0m", -15, 0),
    ("Open 0..+5m", 0, 5),
    ("Open +5..+15m", 5, 15),
    ("Open +15..+30m", 15, 30),
    ("Open +30..+60m", 30, 60),
    ("Open +60..+90m", 60, 90),
]

LDN_NORM_WINDOWS: list[tuple[str, int, int]] = [
    ("LDN -60..-30m", -60, -30),
    ("LDN -30..-15m", -30, -15),
    ("LDN -15..0m", -15, 0),
    ("LDN 0..+15m", 0, 15),
    ("LDN +15..+30m", 15, 30),
    ("LDN +30..+60m", 30, 60),
    ("LDN +60..+90m", 60, 90),
]

OR_MINUTES = (5, 15, 30, 60)


def compute_opening_ranges(panel: pd.DataFrame, traded: str = "US100", session: str = "NY") -> pd.DataFrame:
    """Compute completed and running Opening Ranges (5m, 15m, 30m, 60m) per day.

    Returns a daily summary table AND attaches causal OR columns onto the M1
    index when requested via ``attach_opening_ranges``.
    """
    idx = panel.index
    if session == "NY":
        loc = idx.tz_convert(NY)
        open_mod = 9 * 60 + 30
    else:
        loc = idx.tz_convert(LDN)
        open_mod = 8 * 60

    mod = (loc.hour * 60 + loc.minute).to_numpy()
    rel = mod - open_mod
    dates = loc.date
    h = panel[f"{traded}_h"].to_numpy(float)
    l = panel[f"{traded}_l"].to_numpy(float)
    c = panel[f"{traded}_c"].to_numpy(float)

    df = pd.DataFrame({"ts": idx, "date": dates, "rel": rel, "h": h, "l": l, "c": c})
    in_post = df[(df["rel"] >= 0) & (df["rel"] < 180)].copy()
    if len(in_post) == 0:
        return pd.DataFrame()

    rows = []
    for d, g in in_post.groupby("date", sort=True):
        r = g["rel"].to_numpy()
        gh = g["h"].to_numpy()
        gl = g["l"].to_numpy()
        gc = g["c"].to_numpy()
        if (r < 5).sum() == 0:
            continue
        rec: dict = {"date": d, "session": session}
        for m in OR_MINUTES:
            mask = (r >= 0) & (r < m)
            if not mask.any():
                continue
            orh = float(gh[mask].max())
            orl = float(gl[mask].min())
            orm = 0.5 * (orh + orl)
            ors = orh - orl
            rec[f"or{m}_h"] = orh
            rec[f"or{m}_l"] = orl
            rec[f"or{m}_mid"] = orm
            rec[f"or{m}_size"] = ors
            # Post-OR action (strictly after minute m, up to +120m from open)
            after = (r >= m) & (r < 120)
            if after.any():
                ah = gh[after]
                al = gl[after]
                ac = gc[after]
                sw_up = bool((ah > orh).any())
                sw_dn = bool((al < orl).any())
                # False breakout + return into range
                fb_up = bool(((ah > orh) & (ac <= orh)).any())
                fb_dn = bool(((al < orl) & (ac >= orl)).any())
                rec[f"or{m}_sweep"] = "both" if (sw_up and sw_dn) else ("high" if sw_up else ("low" if sw_dn else "none"))
                rec[f"or{m}_false_break"] = fb_up or fb_dn
                rec[f"or{m}_return_in"] = bool(((ah > orh) & (ac <= orm)).any() or ((al < orl) & (ac >= orm)).any())
            else:
                rec[f"or{m}_sweep"] = "none"
                rec[f"or{m}_false_break"] = False
                rec[f"or{m}_return_in"] = False
        rows.append(rec)
    return pd.DataFrame(rows)


def attach_causal_or_to_signals(sig: pd.DataFrame, or_daily: pd.DataFrame, session: str = "NY") -> pd.DataFrame:
    """Attach OR5 and OR15 levels to signals ONLY when the signal trigger time
    is at or after the OR completion minute (rel >= 5 for OR5, rel >= 15 for OR15).
    Before completion, the completed OR columns are strictly NaN (no look-ahead).
    """
    if len(sig) == 0 or len(or_daily) == 0:
        return sig
    out = sig.copy()
    tz = NY if session == "NY" else LDN
    rel_col = "min_from_ny_open_trig" if session == "NY" else "min_from_ldn_open_trig"
    sig_dates = pd.to_datetime(out["t_trig"]).dt.tz_convert(tz).dt.date
    or_map = or_daily.set_index("date")
    for m in (5, 15, 30):
        col_h = f"{session.lower()}_or{m}_h"
        col_l = f"{session.lower()}_or{m}_l"
        col_sw = f"{session.lower()}_or{m}_swept"
        if f"or{m}_h" not in or_map.columns:
            continue
        raw_h = sig_dates.map(or_map[f"or{m}_h"]).to_numpy(float)
        raw_l = sig_dates.map(or_map[f"or{m}_l"]).to_numpy(float)
        known = out[rel_col].to_numpy(float) >= m
        out[col_h] = np.where(known, raw_h, np.nan)
        out[col_l] = np.where(known, raw_l, np.nan)
        out[col_sw] = np.where(
            known & (out["dir"] == -1),
            out["sweep_ext_known"] > out[col_h],
            np.where(known & (out["dir"] == 1), out["sweep_ext_known"] < out[col_l], False),
        )
    return out


def classify_ny_open_models(sig: pd.DataFrame) -> dict[str, pd.Series]:
    """Boolean masks for Section 10.1 Models NY-A through NY-J on a candidate table.

    Focused on the NY AM opening window (09:30–11:00 NY, i.e. 0 <= min_from_ny_open <= 90).
    """
    in_ny = (sig["min_from_ny_open_trig"] >= 0) & (sig["min_from_ny_open_trig"] <= 90)
    is_m15 = sig["tf"] == "M15"
    is_h1 = sig["tf"] == "H1"
    is_conf = sig["entry_mode"].isin(["confirmed", "confirmed_cisd"])
    is_dev = sig["entry_mode"] == "dev_cisd"

    return {
        "NY-A (Open Sweep + M1 CISD)": in_ny & is_m15 & is_dev & sig["has_cisd"],
        "NY-B (Open Sweep + M15 CRT)": in_ny & is_m15 & (sig["entry_mode"] == "confirmed") & sig["A"],
        "NY-C (M15 CRT + Any SSMT)": in_ny & is_m15 & is_conf & sig["A"] & sig["any_ssmt"],
        "NY-D (H1 CRT + Any SSMT)": in_ny & is_h1 & is_conf & sig["A"] & sig["any_ssmt"],
        "NY-E (Developing H1 CRT + M1 CISD)": in_ny & is_h1 & is_dev & sig["has_cisd"],
        "NY-F (M15 CRT + 90M SSMT + CISD)": in_ny & is_m15 & sig["A"] & sig["macro_ssmt"] & sig["has_cisd"],
        "NY-G (M15 CRT + 22.5M SSMT + CISD)": in_ny & is_m15 & sig["A"] & sig["micro_ssmt"] & sig["has_cisd"],
        "NY-H (H1 CRT + 22.5M SSMT + MMXM + CISD)": in_ny & is_h1 & (sig["A"] | is_dev) & sig["micro_ssmt"] & sig["mmxm"] & sig["has_cisd"],
        "NY-I (Macro + Micro SSMT + CRT + CISD)": in_ny & (sig["A"] | is_dev) & sig["both_ssmt"] & sig["has_cisd"],
        "NY-J (Full Narrative + QT + CRT + SSMT + CISD + MMXM)": (
            in_ny
            & (sig["A"] | is_dev)
            & sig["any_ssmt"]
            & sig["has_cisd"]
            & sig["mmxm"]
            & (sig["htf_liq"] | sig["pd_zone_ok"])
            & (sig["narrative"] != "contradictory")
        ),
    }

