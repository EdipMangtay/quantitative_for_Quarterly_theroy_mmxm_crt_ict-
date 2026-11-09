"""Observed quote coverage for strict V3.5 validation."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import bars
from .execution_v35 import MINUTE


def load_observed_quotes(instrument, start=None, end=None):
    """Read original Dukascopy Bid/Ask without the modeled extension."""
    filters = []
    if start is not None:
        filters.append(("ts", ">=", pd.Timestamp(start)))
    if end is not None:
        filters.append(("ts", "<", pd.Timestamp(end)))
    names = ["open", "high", "low", "close", "ao", "ah", "al", "ac"]
    rows = pd.read_parquet(
        bars.STORE / f"DUKA_{instrument}_M1.parquet",
        columns=["ts", *names], filters=filters or None,
    ).set_index("ts").sort_index()
    valid = np.isfinite(rows).all(axis=1)
    return rows.loc[valid].set_axis([f"{instrument}_{x}" for x in ("o", "h", "l", "c", "ao", "ah", "al", "ac")], axis=1)


def candle_coverage(panel, instrument, tf, other_observations, anchor="cal"):
    """Distinguish an observed mismatch from silence without a broker calendar.

    Other observations prove that the joined panel missed a required quote at
    a recorded time. Silence across all local feeds gives no closure evidence.
    """
    candles = bars.resample(panel, instrument, tf, anchor)
    union = panel.index.union(other_observations)
    left = union.searchsorted(candles["bucket_start"])
    right = union.searchsorted(candles["scheduled_bucket_end"])
    candles["unmatched_observed_minutes"] = np.where(candles["is_closed"], right - left - candles["n"], 0)
    candles["strict_coverage"] = np.select(
        [~candles["is_closed"], candles["is_complete"], candles["unmatched_observed_minutes"] > 0],
        ["OPEN", "FULL", "INCOMPLETE"], default="UNKNOWN",
    )
    return candles


def observed_runs(panel, minimum=1):
    """Yield continuous observed segments. Scanners must reset at each break."""
    if not len(panel):
        return
    idx = panel.index
    if not idx.is_monotonic_increasing or not idx.is_unique or idx.tz is None:
        raise ValueError("Quote coverage requires ordered unique timezone-aware times")
    breaks = np.flatnonzero(idx[1:] - idx[:-1] != MINUTE) + 1
    boundaries = np.r_[0, breaks, len(panel)]
    for start, end in zip(boundaries[:-1], boundaries[1:]):
        if end - start >= minimum:
            yield panel.iloc[start:end]
