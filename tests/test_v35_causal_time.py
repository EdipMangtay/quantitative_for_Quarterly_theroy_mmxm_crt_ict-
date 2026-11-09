"""V3.5 time-contract regression tests using recorded quotes and clock fixtures."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from astra6 import bars, cisd


@pytest.fixture(scope="module")
def bid():
    return (
        bars.load_m1("US100")
        .set_index("ts")[["open", "high", "low", "close"]]
        .rename(columns=dict(zip(("open", "high", "low", "close"), ("US100_o", "US100_h", "US100_l", "US100_c"))))
    )


@pytest.mark.parametrize("sunday", ["2022-03-13", "2022-11-06"])
def test_weekly_close_follows_new_york_wall_boundary(bid, sunday):
    local_close = datetime.fromisoformat(sunday).replace(hour=18, tzinfo=ZoneInfo("America/New_York"))
    close = pd.Timestamp(local_close).tz_convert("UTC")
    history = bid.loc[close - pd.Timedelta(days=7, hours=2):close + pd.Timedelta(hours=1)]
    result = bars.resample(history, "US100", "W1")
    previous = result[result["bucket_start"] < close].iloc[-1]
    assert previous["scheduled_bucket_end"] == close
    assert previous["available_at"] == close
    assert previous["last_observed_at"] < close
    assert previous["is_closed"]
    assert not previous["is_complete"]
    assert previous["data_coverage_status"] == "PARTIAL_UNCLASSIFIED"


@pytest.mark.parametrize("anchor", ["cal", "ny0930", "ldn0800"])
def test_exact_end_finalizes_without_next_bucket(bid, anchor):
    first = pd.Timestamp("2021-11-08 14:35:00Z")
    end = first + pd.Timedelta(minutes=5)
    history = bid.loc[first:end - pd.Timedelta(minutes=1)]
    full = bars.resample(history, "US100", "M5", anchor).iloc[0]
    assert full["available_at"] == end
    assert full["last_observed_at"] == end
    assert full["is_complete"]
    assert full["h"] == history["US100_h"].max()
    assert full["c"] == history.iloc[-1]["US100_c"]
    before = bars.resample(history, "US100", "M5", anchor, as_of=end - pd.Timedelta(seconds=1)).iloc[0]
    assert pd.isna(before["available_at"])
    assert before["data_coverage_status"] == "OPEN"
    assert before["c"] == history.iloc[-2]["US100_c"]


def test_missing_minute_is_not_filled_or_marked_complete(bid):
    first = pd.Timestamp("2021-11-08 14:35:00Z")
    last = first + pd.Timedelta(minutes=4)
    recorded = bid.loc[first:last].drop(first + pd.Timedelta(minutes=2))
    candle = bars.resample(recorded, "US100", "M5").iloc[0]
    assert candle["n"] == 4
    assert candle["data_coverage_status"] == "PARTIAL_UNCLASSIFIED"
    assert not candle["is_complete"]
    assert candle["h"] == recorded["US100_h"].max()


def test_confirmation_projection_does_not_backdate_through_a_gap(bid):
    idx = bid.loc["2021-11-08"].index
    last_before_gap = idx[:-1][(idx[1:] - idx[:-1]) > pd.Timedelta(minutes=5)][0]
    j = idx.get_loc(last_before_gap)
    available = last_before_gap + pd.Timedelta(minutes=2)
    assert bars.minute_confirmation_index(idx, [available]).tolist() == [j + 1]
    assert bars.minute_confirmation_index(idx[:j + 1], [available]).tolist() == [j + 1]


def test_cisd_indices_do_not_precede_availability(bid):
    history = bid.iloc[:3000]
    for tf in ("M1", "M3", "M5", "M15", "M30", "H1", "H4"):
        events = cisd.extract_tf_cisd_events(history, tf=tf)
        j = events["j_conf_m1"].to_numpy()
        closes = history.index + pd.Timedelta(minutes=1)
        assert (closes[j] >= pd.DatetimeIndex(events["available_at"])).all()
        assert (closes[j - 1] < pd.DatetimeIndex(events["available_at"])).all()


@pytest.mark.parametrize(
    ("anchor", "start"),
    [("ny1800", "2026-03-09 22:00:00Z"), ("ny0930", "2026-03-09 13:30:00Z"), ("ldn0800", "2026-03-09 08:00:00Z")],
)
def test_micro_qt_uses_actual_half_minute_boundary(anchor, start):
    start = pd.Timestamp(start)
    offsets = pd.to_timedelta([0, 1349, 1350, 2699, 2700, 5400], unit="s")
    q = bars.quarter_labels(start + offsets, anchor)
    assert q["q22"].tolist() == [1, 1, 2, 2, 3, 1]
    assert q["q90"].tolist() == [1, 1, 1, 1, 1, 2]
