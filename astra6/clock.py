"""Global Session Clock Engine.

All raw timestamps are stored in UTC.  Every session reference is defined in the
*local* time of its market and converted through the IANA tz database
(``zoneinfo``).  No fixed UTC offsets are used anywhere.

DST transition dates are *derived* from the tz database (never hard coded).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

UTC = ZoneInfo("UTC")
NY = ZoneInfo("America/New_York")
LDN = ZoneInfo("Europe/London")
IST = ZoneInfo("Europe/Istanbul")

NASDAQ_OPEN_LOCAL = time(9, 30)   # America/New_York
LONDON_OPEN_LOCAL = time(8, 0)    # Europe/London


def local_to_utc(d: date, t: time, tz: ZoneInfo) -> pd.Timestamp:
    """Wall-clock (d, t) in tz -> tz-aware UTC Timestamp (zoneinfo resolves DST)."""
    dt = datetime.combine(d, t, tzinfo=tz)
    return pd.Timestamp(dt.astimezone(UTC))


def nasdaq_open_utc(d: date) -> pd.Timestamp:
    return local_to_utc(d, NASDAQ_OPEN_LOCAL, NY)


def london_open_utc(d: date) -> pd.Timestamp:
    return local_to_utc(d, LONDON_OPEN_LOCAL, LDN)


def is_dst(d: date, tz: ZoneInfo, at: time = time(12, 0)) -> bool:
    dt = datetime.combine(d, at, tzinfo=tz)
    return bool(dt.dst() and dt.dst() != timedelta(0))


@lru_cache(maxsize=64)
def dst_transitions(tz_name: str, year: int) -> tuple[date, ...]:
    """Dates (local) on which the UTC offset of tz changes, derived from tzdb."""
    tz = ZoneInfo(tz_name)
    out = []
    d = date(year, 1, 1)
    prev = datetime.combine(d, time(12), tzinfo=tz).utcoffset()
    while d.year == year:
        d2 = d + timedelta(days=1)
        off = datetime.combine(d2, time(12), tzinfo=tz).utcoffset()
        if off != prev:
            out.append(d2)  # offset at noon of d2 differs -> transition happened in the night before
            prev = off
        d = d2
    return tuple(out)


def dst_regime(d: date) -> str:
    """Label a calendar date by joint US/UK DST state.

    * ``winter``            – both on standard time
    * ``summer``            – both on daylight time
    * ``mismatch_spring``   – US already on DST, UK still standard (March gap)
    * ``mismatch_autumn``   – UK back on standard, US still on DST (Oct/Nov gap)

    In both mismatch windows NY is on DST and London on standard time, so the
    London-08:00 → NY-09:30 distance shrinks from 6.5h to 5.5h.
    """
    us, uk = is_dst(d, NY), is_dst(d, LDN)
    if us and uk:
        return "summer"
    if not us and not uk:
        return "winter"
    if us and not uk:
        return "mismatch_spring" if d.month <= 6 else "mismatch_autumn"
    return "mismatch_other"  # never observed for US/UK rules since 2007


def is_transition_week(d: date) -> dict:
    """True if the ISO week of d contains a US or UK DST transition (derived)."""
    iso_y, iso_w, _ = d.isocalendar()
    us = any(t.isocalendar()[:2] == (iso_y, iso_w) for y in (d.year - 1, d.year, d.year + 1)
             for t in dst_transitions("America/New_York", y))
    uk = any(t.isocalendar()[:2] == (iso_y, iso_w) for y in (d.year - 1, d.year, d.year + 1)
             for t in dst_transitions("Europe/London", y))
    return {"us_transition_week": us, "uk_transition_week": uk}


def london_ny_open_gap_minutes(d: date) -> int:
    """Minutes between London 08:00 and NY 09:30 opens: 390 normally, 330 in mismatch weeks."""
    return int((nasdaq_open_utc(d) - london_open_utc(d)).total_seconds() // 60)


@dataclass(frozen=True)
class SessionStamp:
    date: date
    london_open_utc: pd.Timestamp
    nasdaq_open_utc: pd.Timestamp
    nasdaq_open_ny: pd.Timestamp
    nasdaq_open_london: pd.Timestamp
    nasdaq_open_istanbul: pd.Timestamp
    london_open_ny: pd.Timestamp
    london_open_istanbul: pd.Timestamp
    regime: str


def session_stamp(d: date) -> SessionStamp:
    lo, no = london_open_utc(d), nasdaq_open_utc(d)
    return SessionStamp(
        date=d,
        london_open_utc=lo,
        nasdaq_open_utc=no,
        nasdaq_open_ny=no.tz_convert(NY),
        nasdaq_open_london=no.tz_convert(LDN),
        nasdaq_open_istanbul=no.tz_convert(IST),
        london_open_ny=lo.tz_convert(NY),
        london_open_istanbul=lo.tz_convert(IST),
        regime=dst_regime(d),
    )


# ---------------------------------------------------------------------------
# Trading calendars (reference markets) — kept separate from broker quote hours
# ---------------------------------------------------------------------------
@lru_cache(maxsize=4)
def _calendar(code: str, start: str, end: str):
    import exchange_calendars as xc
    return xc.get_calendar(code, start=start, end=end)


def reference_calendar(start: str, end: str) -> pd.DataFrame:
    """Per-date flags for Nasdaq (XNAS) and London (XLON) sessions.

    Columns: nasdaq_session, nasdaq_early_close, nasdaq_close_utc,
    lse_session, regime, us_transition_week, uk_transition_week, ny_london_gap_min
    """
    days = pd.date_range(start, end, freq="D")
    nas = _calendar("XNAS", start, end).schedule
    lse = _calendar("XLON", start, end).schedule
    df = pd.DataFrame(index=days.date)
    df.index.name = "date"
    nas_idx = set(nas.index.date)
    lse_idx = set(lse.index.date)
    df["nasdaq_session"] = [d in nas_idx for d in df.index]
    df["lse_session"] = [d in lse_idx for d in df.index]
    close_map = {k.date(): v for k, v in nas["close"].items()}
    open_map = {k.date(): v for k, v in nas["open"].items()}
    df["nasdaq_close_utc"] = [close_map.get(d) for d in df.index]
    df["nasdaq_early_close"] = [
        (d in close_map) and (close_map[d] - open_map[d]) < pd.Timedelta(hours=6.5) for d in df.index
    ]
    df["regime"] = [dst_regime(d) for d in df.index]
    tw = [is_transition_week(d) for d in df.index]
    df["us_transition_week"] = [t["us_transition_week"] for t in tw]
    df["uk_transition_week"] = [t["uk_transition_week"] for t in tw]
    df["ny_london_gap_min"] = [london_ny_open_gap_minutes(d) for d in df.index]
    df["nasdaq_open_utc"] = [nasdaq_open_utc(d) for d in df.index]
    df["london_open_utc"] = [london_open_utc(d) for d in df.index]
    return df


def add_local_times(ts_utc: pd.Series | pd.DatetimeIndex) -> pd.DataFrame:
    """Vectorised UTC -> NY / London / Istanbul local wall-clock columns."""
    idx = pd.DatetimeIndex(ts_utc)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    return pd.DataFrame({
        "ts_utc": idx,
        "ts_ny": idx.tz_convert("America/New_York"),
        "ts_ldn": idx.tz_convert("Europe/London"),
        "ts_ist": idx.tz_convert("Europe/Istanbul"),
    })


def ny_minute_of_day(idx: pd.DatetimeIndex) -> np.ndarray:
    """Minutes since NY local midnight (float, includes seconds)."""
    loc = idx.tz_convert("America/New_York")
    return (loc.hour * 60 + loc.minute + loc.second / 60.0).to_numpy(dtype=float)
