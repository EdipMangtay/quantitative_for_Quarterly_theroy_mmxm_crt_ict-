"""Data store + multi-timeframe candle builder with explicit anchors.

Conventions
-----------
* Quote timestamps are UTC minute opens. A minute's OHLC is known one minute
  later. Higher-timeframe boundaries are scheduled in the anchor's timezone.
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


def resample(
    panel: pd.DataFrame, alias: str, tf: str, anchor: str = "cal",
    *, as_of: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Aggregate observed M1 Bid quotes using a clock watermark.

    `is_closed` and `available_at` describe the final observed aggregate.
    `is_complete` requires an observation for every scheduled minute. Without
    a quote calendar, a closure and a feed outage are both unverified coverage.
    The legacy `complete` column retains its finalized-aggregate meaning.
    """
    if anchor not in ("cal", "ny930", "ny0930", "ldn800", "ldn0800"):
        raise ValueError(f"Unknown candle anchor: {anchor}")
    m = TF_MIN[tf]
    tz_use = LDN if anchor in ("ldn800", "ldn0800") else NY
    idx = panel.index
    if not isinstance(idx, pd.DatetimeIndex) or idx.tz is None:
        raise ValueError("M1 panel requires a timezone-aware DatetimeIndex")
    if not idx.is_monotonic_increasing or not idx.is_unique or idx.hasnans:
        raise ValueError("M1 timestamps must be sorted, unique and present")
    idx = idx.tz_convert("UTC")
    minute = pd.Timedelta(minutes=1)
    if not (idx == idx.floor("min")).all():
        raise ValueError("M1 timestamps must be aligned to UTC minute opens")
    watermark = pd.Timestamp(as_of) if as_of is not None else (
        idx[-1] + minute if len(idx) else pd.NaT
    )
    if pd.notna(watermark) and watermark.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    visible = idx + minute <= watermark
    idx = idx[visible]

    if not len(idx) or m == 1:
        starts, ends = idx, idx + minute
    else:
        local = idx.tz_convert(tz_use).tz_localize(None)
        wall = local.as_unit("s").asi8 // 60
        origin = anchor_origin(tf, anchor)
        left = int(bucket_start_wall(wall.min(), m, origin)) - m
        right = int(bucket_start_wall(wall.max(), m, origin)) + 2 * m
        boundaries = pd.date_range(
            pd.to_datetime(left, unit="m"), pd.to_datetime(right, unit="m"),
            freq=pd.Timedelta(minutes=m),
        )
        # Include both occurrences of repeated local boundaries. Nonexistent
        # boundaries move to the first real instant and may coincide there.
        early = boundaries.tz_localize(tz_use, ambiguous=True, nonexistent="shift_forward")
        late = boundaries.tz_localize(tz_use, ambiguous=False, nonexistent="shift_forward")
        utc = early.union(late).unique().sort_values().tz_convert("UTC")
        buckets = utc.searchsorted(idx, side="right") - 1
        starts, ends = utc[buckets], utc[buckets + 1]

    g = pd.DataFrame({
        "bucket_start": starts, "scheduled_bucket_end": ends, "ts": idx,
        **{side: panel[f"{alias}_{side}"].to_numpy()[visible] for side in ("o", "h", "l", "c")},
    })
    agg = g.groupby("bucket_start", as_index=False).agg(
        scheduled_bucket_end=("scheduled_bucket_end", "first"),
        o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"),
        ts_first=("ts", "first"), ts_last=("ts", "last"), n=("o", "size"),
    )
    agg["last_observed_at"] = agg["ts_last"] + minute
    agg["is_closed"] = agg["scheduled_bucket_end"] <= watermark
    expected = (agg["scheduled_bucket_end"] - agg["bucket_start"]) // minute
    agg["is_complete"] = agg["is_closed"] & (agg["n"] == expected)
    agg["data_coverage_status"] = np.select(
        [~agg["is_closed"], agg["is_complete"]], ["OPEN", "FULL"], default="PARTIAL_UNCLASSIFIED",
    )
    agg["available_at"] = agg["scheduled_bucket_end"].where(agg["is_closed"])
    agg["t_open"] = agg["bucket_start"]
    agg["t_close"] = agg["scheduled_bucket_end"]
    agg["complete"] = agg["is_closed"]
    local_start = pd.DatetimeIndex(agg["bucket_start"]).tz_convert(tz_use).tz_localize(None)
    agg["b"] = local_start.as_unit("s").asi8 // 60
    return agg


def minute_confirmation_index(idx: pd.DatetimeIndex, available_at) -> np.ndarray:
    """First M1 close at or after availability, or len(idx) when unavailable."""
    return (idx + pd.Timedelta(minutes=1)).searchsorted(available_at, side="left")


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

