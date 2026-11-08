"""ICT primitives (strictly causal): ATR, fractal swings with confirmation
times, FVG, displacement, previous-period liquidity levels.

Every derived quantity carries the index/time at which it becomes *known*.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from numba import njit


@njit(cache=True)
def atr_wilder(h, l, c, n):
    out = np.full(h.shape[0], np.nan)
    if h.shape[0] == 0:
        return out
    tr_prev = h[0] - l[0]
    a = tr_prev
    for i in range(h.shape[0]):
        if i == 0:
            tr = h[0] - l[0]
        else:
            tr = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
        if i < n:
            a = (a * i + tr) / (i + 1)
        else:
            a = (a * (n - 1) + tr) / n
        out[i] = a  # known at close of bar i
    return out


@njit(cache=True)
def fractal_swings(h, l, left, right):
    """Return (sh_flag, sl_flag). A swing at i is *confirmed* at close of i+right."""
    n = h.shape[0]
    sh = np.zeros(n, np.bool_)
    sl = np.zeros(n, np.bool_)
    for i in range(left, n - right):
        okh = True
        okl = True
        for k in range(1, left + 1):
            if h[i - k] >= h[i]:
                okh = False
            if l[i - k] <= l[i]:
                okl = False
        for k in range(1, right + 1):
            if h[i + k] > h[i]:
                okh = False
            if l[i + k] < l[i]:
                okl = False
        sh[i] = okh
        sl[i] = okl
    return sh, sl


def swing_table(bars: pd.DataFrame, left=2, right=2, tf_minutes=5) -> pd.DataFrame:
    """Confirmed swings with ``t_known`` = close time of the (i+right)-th bar."""
    h = bars["h"].to_numpy(float)
    l = bars["l"].to_numpy(float)
    sh, sl = fractal_swings(h, l, left, right)
    rows = []
    tclose = bars["t_close"].to_numpy()
    for kind, flag, px in (("H", sh, h), ("L", sl, l)):
        idx = np.nonzero(flag)[0]
        k = np.minimum(idx + right, len(bars) - 1)
        rows.append(pd.DataFrame({"kind": kind, "price": px[idx], "t_pivot": bars["t_open"].to_numpy()[idx],
                                  "t_known": tclose[k]}))
    return pd.concat(rows, ignore_index=True).sort_values("t_known").reset_index(drop=True)


@njit(cache=True)
def last_known_swing(t_query, sw_t_known, sw_price, sw_kind_is_high, want_high, above, ref_price, max_back):
    """For each query time, most recent confirmed swing (known <= t) of the
    wanted kind that lies above (or below) ref_price[q].  Returns NaN if none.
    Arrays must be sorted by sw_t_known."""
    out = np.full(t_query.shape[0], np.nan)
    m = sw_t_known.shape[0]
    for q in range(t_query.shape[0]):
        # binary search last index with t_known <= t
        lo, hi = 0, m
        while lo < hi:
            mid = (lo + hi) // 2
            if sw_t_known[mid] <= t_query[q]:
                lo = mid + 1
            else:
                hi = mid
        k = lo - 1
        steps = 0
        while k >= 0 and steps < max_back:
            if sw_kind_is_high[k] == want_high:
                p = sw_price[k]
                if (above and p > ref_price[q]) or ((not above) and p < ref_price[q]):
                    out[q] = p
                    break
            k -= 1
            steps += 1
    return out


def fvg_table(bars: pd.DataFrame) -> pd.DataFrame:
    """3-candle FVGs; known at close of the 3rd candle."""
    h, l = bars["h"].to_numpy(float), bars["l"].to_numpy(float)
    bull = l[2:] > h[:-2]
    bear = h[2:] < l[:-2]
    t = bars["t_close"].to_numpy()[2:]
    out = []
    for kind, flag, top, bot in (("bull", bull, l[2:], h[:-2]), ("bear", bear, l[:-2], h[2:])):
        i = np.nonzero(flag)[0]
        out.append(pd.DataFrame({"kind": kind, "top": top[i], "bottom": bot[i], "t_known": t[i]}))
    return pd.concat(out, ignore_index=True).sort_values("t_known").reset_index(drop=True)


def period_levels(bars: pd.DataFrame, prefix: str) -> pd.DataFrame:
    """Previous-period high/low known from that period's close (e.g. PDH/PDL)."""
    df = pd.DataFrame({
        "t_known": bars["t_close"].to_numpy(),
        f"{prefix}H": bars["h"].to_numpy(), f"{prefix}L": bars["l"].to_numpy(),
        f"{prefix}O": bars["o"].to_numpy(), f"{prefix}C": bars["c"].to_numpy(),
    })
    return df


def asof_join(times: pd.Series | np.ndarray, table: pd.DataFrame, cols, time_col="t_known") -> pd.DataFrame:
    """Value of table columns most recently known at or before each time."""
    q = pd.DataFrame({"t": pd.DatetimeIndex(pd.to_datetime(np.asarray(times), utc=True)).as_unit("ms")}).reset_index()
    tb = table[[time_col] + list(cols)].copy()
    tb[time_col] = pd.DatetimeIndex(pd.to_datetime(tb[time_col], utc=True)).as_unit("ms")
    tb = tb.sort_values(time_col)
    m = pd.merge_asof(q.sort_values("t"), tb, left_on="t", right_on=time_col, direction="backward",
                      allow_exact_matches=True)
    return m.sort_values("index").set_index("index")[list(cols)]

