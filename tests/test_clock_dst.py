"""Daylight-saving test suite (Section 2.5 / QA tests E, F, G).

Verification is *independent* of zoneinfo: expected values are computed with
pure calendar arithmetic from the statutory rules (US: 2nd Sun Mar → 1st Sun Nov,
Energy Policy Act 2005; UK/EU: last Sun Mar → last Sun Oct) and fixed standard
offsets, then compared to the engine (which uses tzdb only).
"""
from datetime import date, timedelta, time

import pandas as pd
import pytest

from astra6 import clock


def nth_sunday(y, m, n):
    d = date(y, m, 1)
    d += timedelta(days=(6 - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def last_sunday(y, m):
    d = date(y, m + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - 6) % 7)


def us_dst(d):
    return nth_sunday(d.year, 3, 2) <= d < nth_sunday(d.year, 11, 1)


def uk_dst(d):
    return last_sunday(d.year, 3) <= d < last_sunday(d.year, 10)


def expected_ny_open_utc(d):
    h = 13 if us_dst(d) else 14
    return pd.Timestamp(d.year, d.month, d.day, h, 30, tz="UTC")


def expected_ldn_open_utc(d):
    h = 7 if uk_dst(d) else 8
    return pd.Timestamp(d.year, d.month, d.day, h, 0, tz="UTC")


YEARS = range(2021, 2028)
ALL_DAYS = [date(y, 1, 1) + timedelta(days=i) for y in YEARS for i in range(366) if (date(y, 1, 1) + timedelta(days=i)).year == y]


def test_transitions_derived_match_statute():
    for y in YEARS:
        us = clock.dst_transitions("America/New_York", y)
        uk = clock.dst_transitions("Europe/London", y)
        assert us == (nth_sunday(y, 3, 2), nth_sunday(y, 11, 1)), y
        assert uk == (last_sunday(y, 3), last_sunday(y, 10)), y


def test_2026_transition_dates():
    assert clock.dst_transitions("America/New_York", 2026) == (date(2026, 3, 8), date(2026, 11, 1))
    assert clock.dst_transitions("Europe/London", 2026) == (date(2026, 3, 29), date(2026, 10, 25))


@pytest.mark.parametrize("d", ALL_DAYS[::1])
def test_every_day_open_times(d):
    assert clock.nasdaq_open_utc(d) == expected_ny_open_utc(d)
    assert clock.london_open_utc(d) == expected_ldn_open_utc(d)


def test_test_E_ny_dst_2026():
    # winter before 8 Mar 2026
    assert clock.nasdaq_open_utc(date(2026, 3, 6)) == pd.Timestamp("2026-03-06 14:30", tz="UTC")
    assert clock.nasdaq_open_utc(date(2026, 3, 9)) == pd.Timestamp("2026-03-09 13:30", tz="UTC")
    assert clock.nasdaq_open_utc(date(2026, 10, 30)) == pd.Timestamp("2026-10-30 13:30", tz="UTC")
    assert clock.nasdaq_open_utc(date(2026, 11, 2)) == pd.Timestamp("2026-11-02 14:30", tz="UTC")


def test_test_F_uk_dst_2026():
    assert clock.london_open_utc(date(2026, 3, 27)) == pd.Timestamp("2026-03-27 08:00", tz="UTC")
    assert clock.london_open_utc(date(2026, 3, 30)) == pd.Timestamp("2026-03-30 07:00", tz="UTC")
    assert clock.london_open_utc(date(2026, 10, 23)) == pd.Timestamp("2026-10-23 07:00", tz="UTC")
    assert clock.london_open_utc(date(2026, 10, 26)) == pd.Timestamp("2026-10-26 08:00", tz="UTC")


def test_test_G_mismatch_weeks():
    for y in YEARS:
        a, b = nth_sunday(y, 3, 2), last_sunday(y, 3)
        d = a + timedelta(days=1)
        while d < b:
            assert clock.dst_regime(d) == "mismatch_spring"
            assert clock.london_ny_open_gap_minutes(d) == 330  # 5.5h instead of 6.5h
            d += timedelta(days=1)
        c, e = last_sunday(y, 10), nth_sunday(y, 11, 1)
        d = c + timedelta(days=1)
        while d < e:
            assert clock.dst_regime(d) == "mismatch_autumn"
            assert clock.london_ny_open_gap_minutes(d) == 330
            d += timedelta(days=1)
    assert clock.london_ny_open_gap_minutes(date(2026, 1, 15)) == 390
    assert clock.london_ny_open_gap_minutes(date(2026, 7, 15)) == 390


def test_local_stamps_independent():
    for d in [date(2022, 1, 10), date(2023, 3, 20), date(2024, 7, 1), date(2025, 10, 28), date(2026, 11, 2)]:
        s = clock.session_stamp(d)
        assert (s.nasdaq_open_ny.hour, s.nasdaq_open_ny.minute) == (9, 30)
        exp_ldn_hour = 14 + (1 if uk_dst(d) else 0) - (1 if us_dst(d) else 0)
        assert (s.nasdaq_open_london.hour, s.nasdaq_open_london.minute) == (exp_ldn_hour, 30)
        # Istanbul: UTC+3 permanently since Sept 2016
        assert s.nasdaq_open_istanbul.hour == expected_ny_open_utc(d).hour + 3
        assert s.london_open_istanbul.hour == expected_ldn_open_utc(d).hour + 3
        assert s.london_open_ny == expected_ldn_open_utc(d).tz_convert("America/New_York")


def test_reference_calendar_flags():
    cal = clock.reference_calendar("2025-12-20", "2026-01-05")
    assert not cal.loc[date(2025, 12, 25), "nasdaq_session"]
    assert cal.loc[date(2025, 12, 24), "nasdaq_early_close"]
    assert not cal.loc[date(2025, 12, 26), "lse_session"]  # Boxing day
    assert cal.loc[date(2025, 12, 26), "nasdaq_session"]
