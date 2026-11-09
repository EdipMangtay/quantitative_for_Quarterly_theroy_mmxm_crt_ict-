"""Strict structural evidence for the two existing V3.4 playbooks."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from . import bars, ict, signals
from .execution_v35 import MINUTE


@dataclass(frozen=True)
class H1Reversal:
    event_id: str
    instrument: str
    direction: int
    sweep_id: str
    sweep_available_at: pd.Timestamp
    sweep_close: pd.Timestamp
    swing_id: str
    swing_available_at: pd.Timestamp
    swing_price: float
    cisd_id: str
    cisd_available_at: pd.Timestamp
    available_at: pd.Timestamp
    extreme: float
    atr: float
    invalidated_at: pd.Timestamp | None


def h1_reversals(ctx):
    """Confirm a one-sided H1 sweep, an H1 body break and independent H1 CISD.

    Break the most recent intact 2+2 H1 swing known at sweep time. The sweep
    candle or either of the next two complete H1 candles can confirm. If the
    sweep extreme is exceeded first (including an ambiguous confirmation bar),
    discard the setup.
    """
    panel, inst = ctx["panel"], ctx["traded"]
    candles = bars.resample(panel, inst, "H1")
    swings = ict.swing_table(candles, 2, 2)
    complete_window = candles["is_complete"].rolling(5).sum().eq(5)
    consecutive = candles["bucket_start"].diff().eq(60 * MINUTE).rolling(4).sum().eq(4)
    confirmed_times = candles.loc[complete_window & consecutive, "available_at"]
    swings = swings[swings["t_known"].isin(confirmed_times)]
    cisd = ctx["cisd_tables"]["H1"]
    cisd = cisd[cisd["data_coverage_status"].eq("FULL")]
    sweep_rows = signals.extract_crt_events(ctx, "H1", require_full=True)
    sweep_rows = sweep_rows[sweep_rows["A"] & sweep_rows["is_complete"]
                            & sweep_rows["reference_coverage_status"].eq("FULL")]
    idx = panel.index
    starts = candles.set_index("bucket_start")
    for sweep in sweep_rows.itertuples(index=False):
        if sweep.reference_bucket_start != sweep.bucket_start - 60 * MINUTE or sweep.j_sweep < 0:
            continue
        if 0 <= sweep.j_other <= sweep.j_close:
            continue
        direction = sweep.dir
        observed = idx[sweep.j_sweep] + MINUTE
        pivots = swings[swings["kind"].eq("H" if direction == 1 else "L")
                        & (swings["t_known"] <= sweep.bucket_start)]
        if pivots.empty:
            continue
        pivot = pivots.iloc[-1]
        intervening = candles[(candles["available_at"] >= pivot.t_known)
                              & (candles["available_at"] <= sweep.bucket_start)]
        if not intervening["is_complete"].all() or len(intervening) != 1 + (sweep.bucket_start - pivot.t_known) // (60 * MINUTE):
            continue
        if (direction * (intervening["c"] - pivot.price) > 0).any():
            continue
        extreme = sweep.l if direction == 1 else sweep.h
        for hours in range(3):
            start = sweep.bucket_start + hours * 60 * MINUTE
            if start not in starts.index or not starts.at[start, "is_complete"]:
                break
            candle = starts.loc[start]
            if hours and direction * ((candle.l if direction == 1 else candle.h) - extreme) < 0:
                break
            if direction * (candle.c - pivot.price) <= 0 or direction * (candle.c - candle.o) <= 0:
                continue
            when = candle.available_at
            confirms = cisd[(cisd["dir"] == direction) & (cisd["available_at"] >= observed)
                            & (cisd["available_at"] <= when)
                            & (cisd["invalidated_at"].isna() | (cisd["invalidated_at"] > when))]
            if confirms.empty:
                continue
            confirmation = confirms.iloc[-1]
            post = idx.searchsorted(when)
            end = idx.searchsorted(when + 120 * MINUTE)
            future = panel[f"{inst}_{'l' if direction == 1 else 'h'}"].iloc[post:end]
            invalid = future[direction * (future - extreme) < 0]
            yield H1Reversal(
                f"H1_REVERSAL:{inst}:{direction}:{sweep.bucket_start.isoformat()}",
                inst, direction, f"H1_SWEEP:{inst}:{direction}:{observed.isoformat()}",
                observed, sweep.available_at,
                f"H1_SWING:{inst}:{pivot.kind}:{pivot.t_pivot.isoformat()}",
                pivot.t_known, float(pivot.price),
                f"CISD:{inst}:H1:{confirmation.available_at.isoformat()}:{direction}",
                confirmation.available_at, when, float(extreme), float(sweep.atr_ref),
                invalid.index[0] + MINUTE if not invalid.empty else None,
            )
            break


def linked_mmxm_stages(oc, mmxm):
    """Join only to the exact confirmed OC that originated the MMXM."""
    if oc.empty or mmxm.empty:
        return pd.DataFrame()
    parents = oc.loc[
        oc["event_kind"].eq("CONFIRMED") & oc["data_coverage_status"].eq("FULL"),
        ["oc_id", "connected_mmxm_id", "instrument", "tf", "target_dir", "available_at", "t_start"],
    ].rename(columns={"target_dir": "direction", "available_at": "oc_available_at", "t_start": "oc_start"})
    joined = mmxm.merge(
        parents, left_on=["oc_id", "mmxm_id", "instrument", "tf", "direction"],
        right_on=["oc_id", "connected_mmxm_id", "instrument", "tf", "direction"], validate="many_to_one",
    )
    joined = joined[joined["oc_available_at"] <= joined["available_at"]].copy()
    joined = joined.sort_values(["available_at", "stage_num", "mmxm_event_id"])
    joined["stage_end"] = joined.groupby("mmxm_id", sort=False)["available_at"].shift(-1)
    revoked = oc.loc[oc["event_kind"].eq("INVALIDATED"), ["oc_id", "available_at"]]
    return joined.merge(
        revoked.rename(columns={"available_at": "oc_invalidated_at"}),
        on="oc_id", how="left", validate="many_to_one",
    )
