"""Data store + multi-timeframe candle builder with explicit anchors.

Conventions
-----------
* Every bar is labelled by its **start** time (UTC) and carries ``t_close``
  (start + duration).  A bar's OHLC is *only known at t_close*.
* Intraday buckets are computed on **New York wall-clock** time so that 6H /
  90M / 22.5M quarters and H4/Daily candles follow DST automatically.
* Anchors:
    - ``cal``   : calendar aligned (H1 = 09:00-10:00 NY, M15 = :00/:15/:30/:45)
    - ``ny930`` : NY-open anchored (H1 = 09:30-10:30 NY)
    - ``ldn800``: London-open anchored (H1 on 08:00 London) – identical to
      ``cal`` for H1/M15 because London is a whole-hour offset; kept for clarity.
  Note that M15 ``cal`` == ``ny930`` because 09:30 is a quarter-hour boundary.
* Daily candle = 18:00→18:00 NY (CFD/futures trading-day convention),
  H4 = 18/22/02/06/10/14 NY, Weekly = Sunday 18:00 NY.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from .data.dukascopy import SYMBOLS, candle_key, decode_candles
from .data.download import RAW, trading_days

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "data" / "store"
NY = "America/New_York"
LDN = "Europe/London"
IST = "Europe/Istanbul"

# TF name -> minutes
TF_MIN = {"M1": 1, "M2": 2, "M3": 3, "M5": 5, "M10": 10, "M15": 15, "M30": 30, "M45": 45,
          "H1": 60, "M90": 90, "H2": 120, "H4": 240, "H6": 360, "D1": 1440, "W1": 10080}

# origin (NY wall-clock minute offset within the day) per candle anchor
ANCHOR_ORIGIN_MIN = {"cal": 0, "ny930": 9 * 60 + 30, "ldn800": None}
CYCLE_ORIGIN = 18 * 60  # 18:00 NY trading day start (default ny1800 QT anchor)

# Quarterly Theory cycle anchors (Phase 3.2):
#   - ny1800 : 18:00 America/New_York trading-day anchor (18*3600 = 64800s)
#   - ny0930 : 09:30 America/New_York cash-open anchor   ((9*60+30)*60 = 34200s)
#   - ldn0800: 08:00 Europe/London cash-open anchor      (8*3600 = 28800s in London wall clock)
QT_ANCHORS = {
    "ny1800": (NY, 18 * 3600.0),
    "ny0930": (NY, (9 * 60 + 30) * 60.0),
    "ldn0800": (LDN, 8 * 3600.0),
}


# ---------------------------------------------------------------------------
# Raw -> parquet
# ---------------------------------------------------------------------------
def build_symbol_minutes(sym_alias: str, start: date, end: date, side: str = "BID") -> pd.DataFrame:
    sym = SYMBOLS[sym_alias]
    frames = []
    for d in trading_days(start, end):
        p = RAW / candle_key(sym, d, side)
        if not p.exists():
            continue
        df = decode_candles(p.read_bytes(), sym, d)
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    # Dukascopy fills closed minutes with flat candles (volume 0): drop them
    df = df[df["volume"] > 0].reset_index(drop=True)
    return df


def write_store(start: date, end: date):
    STORE.mkdir(parents=True, exist_ok=True)
    for alias in SYMBOLS:
        for side in ("BID", "ASK"):
            df = build_symbol_minutes(alias, start, end, side)
            df.to_parquet(STORE / f"{alias}_{side}_M1.parquet", index=False)
            print(alias, side, len(df), df.ts.min(), df.ts.max(), flush=True)


def load_m1(alias: str, side: str = "BID") -> pd.DataFrame:
    return pd.read_parquet(STORE / f"{alias}_{side}_M1.parquet")


def load_panel(aliases=("US100", "US500", "US30"), with_ask=True) -> pd.DataFrame:
    """Wide minute panel on the intersection of timestamps (UTC index).

    Columns: {alias}_{o,h,l,c} (BID) and {alias}_ac / {alias}_ah / {alias}_al / {alias}_ao (ASK)
    """
    parts = []
    for a in aliases:
        b = load_m1(a, "BID").set_index("ts")[["open", "high", "low", "close"]]
        b.columns = [f"{a}_o", f"{a}_h", f"{a}_l", f"{a}_c"]
        parts.append(b)
        if with_ask:
            k = load_m1(a, "ASK").set_index("ts")[["open", "high", "low", "close"]]
            k.columns = [f"{a}_ao", f"{a}_ah", f"{a}_al", f"{a}_ac"]
            parts.append(k)
    df = pd.concat(parts, axis=1, join="inner").sort_index()
    return df


# ---------------------------------------------------------------------------
# Bucketing
# ---------------------------------------------------------------------------
def ny_wall_minutes(idx: pd.DatetimeIndex) -> np.ndarray:
    """Minutes since 1970-01-01 00:00 in NY *wall-clock* (DST-aware), unit-safe."""
    loc = idx.tz_convert(NY).tz_localize(None).as_unit("s")
    return (loc.asi8 // 60).astype(np.int64)


def ny_wall_seconds(idx: pd.DatetimeIndex) -> np.ndarray:
    """Seconds since 1970-01-01 00:00 in NY *wall-clock* (DST-aware), unit-safe."""
    loc = idx.tz_convert(NY).tz_localize(None).as_unit("s")
    return loc.asi8.astype(np.int64)


def ldn_wall_minutes(idx: pd.DatetimeIndex) -> np.ndarray:
    """Minutes since 1970-01-01 00:00 in London *wall-clock* (DST-aware), unit-safe."""
    loc = idx.tz_convert(LDN).tz_localize(None).as_unit("s")
    return (loc.asi8 // 60).astype(np.int64)


def ldn_wall_seconds(idx: pd.DatetimeIndex) -> np.ndarray:
    """Seconds since 1970-01-01 00:00 in London *wall-clock* (DST-aware), unit-safe."""
    loc = idx.tz_convert(LDN).tz_localize(None).as_unit("s")
    return loc.asi8.astype(np.int64)


def bucket_start_wall(wall_min: np.ndarray, tf_min: float, origin_min: float) -> np.ndarray:
    """Floor wall-clock minutes to bucket starts (float minutes, allows 22.5)."""
    return np.floor((wall_min - origin_min) / tf_min) * tf_min + origin_min


def anchor_origin(tf: str, anchor: str) -> float:
    m = TF_MIN[tf]
    if anchor in ("ny930", "ny0930"):
        return 9 * 60 + 30
    if anchor in ("ldn800", "ldn0800"):
        return 8 * 60  # evaluated on London wall-clock when anchor is ldn800
    if tf == "W1":
        return 3 * 1440 + CYCLE_ORIGIN  # Sunday 18:00 NY (1970-01-01 was Thursday)
    if tf in ("H2", "H4", "H6", "M90", "D1"):
        return CYCLE_ORIGIN
    return 0


def wall_to_utc(wall_min: np.ndarray, tz_name: str = NY) -> pd.DatetimeIndex:
    naive = pd.to_datetime(wall_min.astype(np.float64) * 60, unit="s")
    return naive.tz_localize(tz_name, ambiguous="NaT", nonexistent="shift_forward").tz_convert("UTC")


def resample(panel: pd.DataFrame, alias: str, tf: str, anchor: str = "cal") -> pd.DataFrame:
    """OHLC bars for one symbol (BID) with start/close timestamps.

    Only buckets that are entirely in the past at t_close are emitted; the last
    (possibly incomplete) bucket is flagged ``complete=False``.
    """
    m = TF_MIN[tf]
    tz_use = LDN if anchor in ("ldn800", "ldn0800") else NY
    wall = ldn_wall_minutes(panel.index) if tz_use == LDN else ny_wall_minutes(panel.index)
    b = bucket_start_wall(wall, m, anchor_origin(tf, anchor))
    g = pd.DataFrame({
        "b": b, "o": panel[f"{alias}_o"].to_numpy(), "h": panel[f"{alias}_h"].to_numpy(),
        "l": panel[f"{alias}_l"].to_numpy(), "c": panel[f"{alias}_c"].to_numpy(),
        "ts": panel.index,
    })
    agg = g.groupby("b", sort=True).agg(o=("o", "first"), h=("h", "max"), l=("l", "min"),
                                         c=("c", "last"), ts_first=("ts", "first"),
                                         ts_last=("ts", "last"), n=("o", "size"))
    agg = agg.reset_index()
    agg["t_open"] = wall_to_utc(agg["b"].to_numpy(), tz_use)
    agg["t_close"] = agg["t_open"] + pd.to_timedelta(m, unit="m")
    # fall back for ambiguous DST hours
    bad = agg["t_open"].isna()
    agg.loc[bad, "t_open"] = agg.loc[bad, "ts_first"]
    agg.loc[bad, "t_close"] = agg.loc[bad, "ts_first"] + pd.to_timedelta(m, unit="m")
    agg["complete"] = True
    if len(agg) > 0:
        agg.loc[agg.index[-1], "complete"] = False
    return agg


def quarter_labels(idx: pd.DatetimeIndex, qt_anchor: str = "ny1800") -> pd.DataFrame:
    """Quarterly-Theory labels for each timestamp (exact wall-clock seconds, DST-aware).

    Supports three distinct anchors (Phase 3.2):
      - ``ny1800`` : 18:00 America/New_York trading-day anchor
      - ``ny0930`` : 09:30 America/New_York cash-open anchor
      - ``ldn0800``: 08:00 Europe/London cash-open anchor

    Divisions (computed in exact seconds so 30S bars divide 22.5M = 1350s exactly):
      - q6  : 6H macro cycle (21,600s) -> Q1..Q4
      - q90 : 90M cycle inside 6H (5,400s) -> Q1..Q4
      - q22 : 22.5M micro-quarter inside 90M (1,350s) -> Q1..Q4
      - q5  : 5.625M sub-micro quarter inside 22.5M (337.5s) -> Q1..Q4
    """
    if qt_anchor not in QT_ANCHORS:
        raise ValueError(f"Unknown qt_anchor: {qt_anchor}. Valid: {list(QT_ANCHORS)}")
    tz_name, origin_sec = QT_ANCHORS[qt_anchor]
    sec = (ldn_wall_seconds(idx) if tz_name == LDN else ny_wall_seconds(idx)).astype(np.float64)
    rel = sec - origin_sec
    b6 = np.floor(rel / 21600.0)
    b90 = np.floor(rel / 5400.0)
    b22 = np.floor(rel / 1350.0)
    b5 = np.floor(rel / 337.5)
    return pd.DataFrame({
        "b6": b6.astype(np.int64), "b90": b90.astype(np.int64), "b22": b22.astype(np.int64),
        "b5": b5.astype(np.int64),
        "q6": (np.mod(b6, 4) + 1).astype(np.int8),
        "q90": (np.mod(b90, 4) + 1).astype(np.int8),
        "q22": (np.mod(b22, 4) + 1).astype(np.int8),
        "q5": (np.mod(b5, 4) + 1).astype(np.int8),
        "day_id": np.floor(rel / 86400.0).astype(np.int64),
        "qt_anchor": qt_anchor,
        "sec_in_q90": np.mod(rel, 5400.0),
        "sec_in_q22": np.mod(rel, 1350.0),
    }, index=idx)

