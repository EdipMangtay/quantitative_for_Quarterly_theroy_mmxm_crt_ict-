"""Dukascopy historical data access (bi5 = LZMA-compressed big-endian records).

Two sanctioned access paths are supported:

1. ``https://datafeed.dukascopy.com/datafeed/...``  (public HTTP datafeed;
   currently answers HTTP 429 and points to the S3 path below — we *respect*
   429 and never try to circumvent it)
2. ``s3://cfg-public-proper-wallaby/...``  Requester-Pays S3 bucket documented at
   https://wiki.dukascopy.com/en/development/data-export/  (needs the user's own
   AWS credentials; transfer costs are billed to that account)

File layout (month is 0-based):
  {SYM}/{YYYY}/{MM-1:02d}/{DD:02d}/{HH:02d}h_ticks.bi5
  {SYM}/{YYYY}/{MM-1:02d}/{DD:02d}/{BID|ASK}_candles_min_1.bi5

Records:
  ticks   : >IIIff  (ms_from_hour, ask, bid, ask_vol, bid_vol)
  candles : >IIIIIf (sec_from_day, open, close, low, high, volume)
"""
from __future__ import annotations

import lzma
import struct
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

SYMBOLS = {
    "US100": "USATECHIDXUSD",
    "US500": "USA500IDXUSD",
    "US30": "USA30IDXUSD",
}
POINT = {"USATECHIDXUSD": 1000.0, "USA500IDXUSD": 1000.0, "USA30IDXUSD": 1000.0}

HTTP_BASE = "https://datafeed.dukascopy.com/datafeed"
S3_BUCKET = "cfg-public-proper-wallaby"

TICK_DT = np.dtype([("ms", ">u4"), ("ask", ">u4"), ("bid", ">u4"), ("askv", ">f4"), ("bidv", ">f4")])
CANDLE_DT = np.dtype([("sec", ">u4"), ("o", ">u4"), ("c", ">u4"), ("l", ">u4"), ("h", ">u4"), ("v", ">f4")])


def candle_key(sym: str, d: date, side: str) -> str:
    return f"{sym}/{d.year}/{d.month - 1:02d}/{d.day:02d}/{side}_candles_min_1.bi5"


def tick_key(sym: str, d: date, hour: int) -> str:
    return f"{sym}/{d.year}/{d.month - 1:02d}/{d.day:02d}/{hour:02d}h_ticks.bi5"


def _decompress(raw: bytes) -> bytes:
    if not raw:
        return b""
    return lzma.decompress(raw)


def decode_candles(raw: bytes, sym: str, d: date) -> pd.DataFrame:
    buf = _decompress(raw)
    if not buf:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])
    a = np.frombuffer(buf, dtype=CANDLE_DT)
    p = POINT[sym]
    base = pd.Timestamp(d.year, d.month, d.day, tz="UTC")
    df = pd.DataFrame({
        "ts": base + pd.to_timedelta(a["sec"].astype(np.int64), unit="s"),
        "open": a["o"] / p, "high": a["h"] / p, "low": a["l"] / p, "close": a["c"] / p,
        "volume": a["v"].astype(np.float64),
    })
    return df


def decode_ticks(raw: bytes, sym: str, d: date, hour: int) -> pd.DataFrame:
    buf = _decompress(raw)
    if not buf:
        return pd.DataFrame(columns=["ts", "bid", "ask", "bidv", "askv"])
    a = np.frombuffer(buf, dtype=TICK_DT)
    p = POINT[sym]
    base = pd.Timestamp(d.year, d.month, d.day, hour, tz="UTC")
    return pd.DataFrame({
        "ts": base + pd.to_timedelta(a["ms"].astype(np.int64), unit="ms"),
        "bid": a["bid"] / p, "ask": a["ask"] / p,
        "bidv": a["bidv"].astype(np.float64), "askv": a["askv"].astype(np.float64),
    })

