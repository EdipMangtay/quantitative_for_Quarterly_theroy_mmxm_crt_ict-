"""CRT detection engine (Candle Range Theory) — causal intrabar scanner.

For every pair (reference candle k-1, current candle k) on a CRT timeframe the
scanner walks the lower-timeframe (LTF, normally M1) bars of candle k in
chronological order and records the LTF index at which each event is *first
observable* (i.e. at the close of that LTF bar):

  j_sweep      first LTF bar whose high > H_ref (bear side) / low < L_ref (bull)
  j_other      first LTF bar sweeping the *opposite* side (inside candle k)
  j_reclaim    first LTF close back inside the reference range after the sweep
  j_cisd       first LTF bar where a CISD against the sweep is confirmed *and*
               the close is back inside the reference range (may be after the
               candle close, up to ``ext`` LTF bars – used by confirmed+CISD)
  j_disp       first LTF displacement (3-bar FVG with large middle body) against
               the sweep, after the sweep, inside candle k
  j_cmp[k]     first LTF bar where comparator k sweeps ITS OWN reference level
               (same candle bucket) – used for standard SMT at the CRT level

CISD (Change in State of Delivery), bearish: after the latest new high, the
level is the open of the first candle of the consecutive up-close series that
delivered price into that high; CISD is confirmed when an LTF candle closes
below that level.  Any new extreme re-arms the state machine.
Bullish is symmetric.

Direction index: d=0 → high swept → bearish candidate; d=1 → low swept → bullish.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from numba import njit

EV = ["j_sweep", "j_other", "j_reclaim", "j_cisd", "j_disp", "j_cmp0", "j_cmp1"]
N_EV = len(EV)


@njit(cache=True)
def _series_open_bear(o, c, j, lo):
    """Open of the first candle of the up-close series delivering into the high at j."""
    s = j if c[j] > o[j] else j - 1
    if s < lo:
        return o[j]
    if not (c[s] > o[s]):
        return o[j] if c[j] > o[j] else max(o[j], c[j])
    while s - 1 >= lo and c[s - 1] > o[s - 1]:
        s -= 1
    return o[s]


@njit(cache=True)
def _series_open_bull(o, c, j, lo):
    s = j if c[j] < o[j] else j - 1
    if s < lo:
        return o[j]
    if not (c[s] < o[s]):
        return o[j] if c[j] < o[j] else min(o[j], c[j])
    while s - 1 >= lo and c[s - 1] < o[s - 1]:
        s -= 1
    return o[s]


@njit(cache=True)
def scan_crt(o, h, l, c, atr, ch, cl, i0, i1, Href, Lref, cHref, cLref, valid, ext, disp_k):
    n = o.shape[0]
    nb = i0.shape[0]
    ncmp = ch.shape[0]
    out = np.full((nb, 2, 7), -1, np.int64)
    ext_at_cisd = np.full((nb, 2), np.nan)
    for b in range(nb):
        if not valid[b]:
            continue
        s = i0[b]
        e = i1[b]
        E = min(e + ext, n)
        lookback_lo = max(0, s - 30)
        # opposite-side + comparators (inside candle, comparators also in ext window)
        for d in range(2):
            for j in range(s, e):
                if d == 0 and l[j] < Lref[b]:
                    out[b, 0, 1] = j
                    break
                if d == 1 and h[j] > Href[b]:
                    out[b, 1, 1] = j
                    break
            for k in range(ncmp):
                for j in range(s, E):
                    if d == 0 and ch[k, j] > cHref[k, b]:
                        out[b, 0, 5 + k] = j
                        break
                    if d == 1 and cl[k, j] < cLref[k, b]:
                        out[b, 1, 5 + k] = j
                        break
        # bearish side (high swept)
        jsw = -1
        extp = 0.0
        level = np.nan
        fired = False
        jrc = -1
        jcisd = -1
        jdisp = -1
        for j in range(s, E):
            if jsw < 0:
                if j >= e:
                    break
                if h[j] > Href[b]:
                    jsw = j
                    extp = h[j]
                    level = _series_open_bear(o, c, j, lookback_lo)
                    fired = c[j] < level and c[j] < o[j]
                    if c[j] <= Href[b] and jrc < 0:
                        jrc = j
                    if fired and c[j] <= Href[b]:
                        jcisd = j
                        break
                continue
            if h[j] > extp:
                extp = h[j]
                level = _series_open_bear(o, c, j, lookback_lo)
                fired = c[j] < level and c[j] < o[j]
            elif c[j] < level:
                fired = True
            if j < e and jrc < 0 and c[j] <= Href[b]:
                jrc = j
            if j < e and jdisp < 0 and j - 2 >= jsw and h[j] < l[j - 2] and \
                    (o[j - 1] - c[j - 1]) > disp_k * atr[j - 1]:
                jdisp = j
            if fired and c[j] <= Href[b]:
                jcisd = j
                ext_at_cisd[b, 0] = extp
                break
        if jsw >= 0 and jcisd >= 0 and np.isnan(ext_at_cisd[b, 0]):
            ext_at_cisd[b, 0] = extp
        out[b, 0, 0] = jsw
        out[b, 0, 2] = jrc
        out[b, 0, 3] = jcisd
        # displacement search may continue past CISD break -> finish inside candle
        if jsw >= 0 and jdisp < 0:
            for j in range(max(jsw + 2, s + 2), e):
                if h[j] < l[j - 2] and (o[j - 1] - c[j - 1]) > disp_k * atr[j - 1]:
                    jdisp = j
                    break
        out[b, 0, 4] = jdisp
        # bullish side (low swept)
        jsw = -1
        extp = 0.0
        level = np.nan
        fired = False
        jrc = -1
        jcisd = -1
        jdisp = -1
        for j in range(s, E):
            if jsw < 0:
                if j >= e:
                    break
                if l[j] < Lref[b]:
                    jsw = j
                    extp = l[j]
                    level = _series_open_bull(o, c, j, lookback_lo)
                    fired = c[j] > level and c[j] > o[j]
                    if c[j] >= Lref[b] and jrc < 0:
                        jrc = j
                    if fired and c[j] >= Lref[b]:
                        jcisd = j
                        ext_at_cisd[b, 1] = extp
                        break
                continue
            if l[j] < extp:
                extp = l[j]
                level = _series_open_bull(o, c, j, lookback_lo)
                fired = c[j] > level and c[j] > o[j]
            elif c[j] > level:
                fired = True
            if j < e and jrc < 0 and c[j] >= Lref[b]:
                jrc = j
            if j < e and jdisp < 0 and j - 2 >= jsw and l[j] > h[j - 2] and \
                    (c[j - 1] - o[j - 1]) > disp_k * atr[j - 1]:
                jdisp = j
            if fired and c[j] >= Lref[b]:
                jcisd = j
                ext_at_cisd[b, 1] = extp
                break
        out[b, 1, 0] = jsw
        out[b, 1, 2] = jrc
        out[b, 1, 3] = jcisd
        if jsw >= 0 and jdisp < 0:
            for j in range(max(jsw + 2, s + 2), e):
                if l[j] > h[j - 2] and (c[j - 1] - o[j - 1]) > disp_k * atr[j - 1]:
                    jdisp = j
                    break
        out[b, 1, 4] = jdisp
    return out, ext_at_cisd


@njit(cache=True)
def running_extreme(h, l, a, b, want_high):
    """max(h[a..b]) or min(l[a..b]) inclusive; NaN if invalid range."""
    if a < 0 or b < a:
        return np.nan
    if want_high:
        m = h[a]
        for j in range(a + 1, b + 1):
            if h[j] > m:
                m = h[j]
        return m
    m = l[a]
    for j in range(a + 1, b + 1):
        if l[j] < m:
            m = l[j]
    return m


def classify_confirmed(bars: pd.DataFrame, d: int, strong_body=0.5) -> pd.DataFrame:
    """Close-based CRT variants known at candle close (vectorised on HTF bars).

    bars must contain current (o,h,l,c) and reference (Hr,Lr,Or,Cr) columns plus
    ``sw`` (this side swept) and ``ot`` (other side swept) booleans.
    """
    o, h, l, c = bars.o, bars.h, bars.l, bars.c
    Hr, Lr = bars.Hr, bars.Lr
    mid = (Hr + Lr) / 2
    rng = (h - l).replace(0, np.nan)
    inside_close = (c >= Lr) & (c <= Hr)
    body_in = (np.minimum(o, c) >= Lr) & (np.maximum(o, c) <= Hr)
    one = bars.sw & ~bars.ot
    if d == 0:
        strong = (c < o) & ((o - c) / rng >= strong_body)
        beyond_mid = c < mid
    else:
        strong = (c > o) & ((c - o) / rng >= strong_body)
        beyond_mid = c > mid
    return pd.DataFrame({
        "A": one & inside_close,
        "B": one & body_in,
        "C": one & inside_close & strong,
        "D": one & inside_close & beyond_mid,
        "J": one,
        "K": bars.sw & bars.ot & inside_close,
    }, index=bars.index)

