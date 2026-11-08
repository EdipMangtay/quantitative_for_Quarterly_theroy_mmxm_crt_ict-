"""Quarterly-Theory Sequential SMT (SSMT) engine + standard SMT helpers.

Levels
------
* macro  = 90M quarters inside each 6H block  (q90 = 1..4)
* micro  = 22.5M quarters inside each 90M block (q22 = 1..4)

Pairs (reference quarter -> trigger quarter): Q1→Q2, Q1→Q3, Q1→Q4, Q2→Q3,
Q2→Q4, Q3→Q4 within the same parent block, plus previous-parent Q4 → Q1.

Bearish SSMT, traded-led ("A"): while the trigger quarter is running, the traded
instrument's running high exceeds its reference-quarter high while the
comparator's running high is still <= the comparator's reference-quarter high.
Comparator-led ("B"): comparator exceeds, traded instrument has not.
Formation is observable at the close of the M1 bar where the condition first
holds.  Invalidation = first later M1 bar (trigger quarter or the following quarter)
where the lagging instrument also takes its reference extreme.  Bullish symmetric.
The trigger quarter does **not** need to be complete for the event to fire.

Resolution caveat: 22.5M boundaries fall on :30 seconds; with M1 data each M1
bar is assigned to the quarter containing its start (≤30 s boundary error).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from numba import njit

PAIRS = [(1, 2), (1, 3), (1, 4), (2, 3), (2, 4), (3, 4), (4, 1)]


@njit(cache=True)
def _block_extremes(h, l, starts, ends):
    nb = starts.shape[0]
    H = np.empty(nb)
    L = np.empty(nb)
    for b in range(nb):
        H[b] = h[starts[b]:ends[b]].max()
        L[b] = l[starts[b]:ends[b]].min()
    return H, L


@njit(cache=True)
def _scan_pair(ha, la, hb, lb, s, e, e_inv, HA, LA, HB, LB):
    """Return formation/invalidation indices for 8 cases:
    [bear_A_form, bear_A_inv, bear_B_form, bear_B_inv, bull_A_form, bull_A_inv, bull_B_form, bull_B_inv]"""
    res = np.full(8, -1, np.int64)
    ra_h = -1e18
    rb_h = -1e18
    ra_l = 1e18
    rb_l = 1e18
    for j in range(s, e_inv):
        canform = j < e
        if ha[j] > ra_h:
            ra_h = ha[j]
        if hb[j] > rb_h:
            rb_h = hb[j]
        if la[j] < ra_l:
            ra_l = la[j]
        if lb[j] < rb_l:
            rb_l = lb[j]
        a_up = ra_h > HA
        b_up = rb_h > HB
        a_dn = ra_l < LA
        b_dn = rb_l < LB
        # bearish A-led
        if res[0] < 0:
            if canform and a_up and not b_up:
                res[0] = j
        elif res[1] < 0 and b_up:
            res[1] = j
        if res[2] < 0:
            if canform and b_up and not a_up:
                res[2] = j
        elif res[3] < 0 and a_up:
            res[3] = j
        if res[4] < 0:
            if canform and a_dn and not b_dn:
                res[4] = j
        elif res[5] < 0 and b_dn:
            res[5] = j
        if res[6] < 0:
            if canform and b_dn and not a_dn:
                res[6] = j
        elif res[7] < 0 and a_dn:
            res[7] = j
    return res


def ssmt_events(panel: pd.DataFrame, qlab: pd.DataFrame, traded: str, comp: str, level: str) -> pd.DataFrame:
    """All SSMT events for one traded/comparator pair at one fractal level.

    Returns rows: level, comp, b_ref, b_trig, q_ref, q_trig, dir(-1 bear/+1 bull),
    lead('A'/'B'), j_form, j_inv (M1 panel indices), parent block id.
    """
    bcol, qcol, parent = ("b90", "q90", "b6") if level == "macro" else ("b22", "q22", "b90")
    ha = panel[f"{traded}_h"].to_numpy(float)
    la = panel[f"{traded}_l"].to_numpy(float)
    hb = panel[f"{comp}_h"].to_numpy(float)
    lb = panel[f"{comp}_l"].to_numpy(float)
    bid = qlab[bcol].to_numpy()
    # contiguous runs of the same block id
    brk = np.r_[0, np.nonzero(np.diff(bid))[0] + 1]
    starts = brk
    ends = np.r_[brk[1:], len(bid)]
    blk_ids = bid[starts]
    qs = qlab[qcol].to_numpy()[starts]
    par = qlab[parent].to_numpy()[starts]
    HA, LA = _block_extremes(ha, la, starts, ends)
    HB, LB = _block_extremes(hb, lb, starts, ends)
    pos = {int(b): i for i, b in enumerate(blk_ids)}
    rows = []
    for i in range(len(starts)):
        qk = int(qs[i])
        for (qr, qt) in PAIRS:
            if qt != qk:
                continue
            if (qr, qt) == (4, 1):
                ref_blk = blk_ids[i] - 1  # previous quarter == previous parent's Q4
            else:
                ref_blk = blk_ids[i] - (qt - qr)
            r = pos.get(int(ref_blk))
            if r is None:
                continue
            if (qr, qt) != (4, 1) and par[r] != par[i]:
                continue
            e_inv = ends[i + 1] if i + 1 < len(starts) else ends[i]
            res = _scan_pair(ha, la, hb, lb, starts[i], ends[i], e_inv, HA[r], LA[r], HB[r], LB[r])
            for k, (dr, lead) in enumerate([(-1, "A"), (-1, "B"), (1, "A"), (1, "B")]):
                jf = res[2 * k]
                if jf >= 0:
                    rows.append((level, comp, int(blk_ids[r]), int(blk_ids[i]), qr, qt, dr, lead,
                                 int(jf), int(res[2 * k + 1]), int(par[i]), int(starts[i]), int(ends[i])))
    cols = ["level", "comp", "b_ref", "b_trig", "q_ref", "q_trig", "dir", "lead", "j_form", "j_inv",
            "parent", "trig_start", "trig_end"]
    return pd.DataFrame(rows, columns=cols).sort_values("j_form").reset_index(drop=True)


def attach_ssmt(sig: pd.DataFrame, ev: pd.DataFrame, level: str, max_age_quarters: int = 1,
                lead: str | None = None) -> pd.DataFrame:
    """For each signal (columns j_trig, j_sweep, dir) find the most recent SSMT event
    in the trade direction that is formed at or before j_trig, not invalidated by
    j_trig, and whose trigger quarter is the current or (max_age) previous quarter.
    Adds columns  {level}_ssmt (bool), {level}_pair, {level}_lead, {level}_jform.
    """
    bcol = "b90" if level == "macro" else "b22"
    out = {f"{level}_ssmt": np.zeros(len(sig), bool), f"{level}_pair": np.array([""] * len(sig), dtype=object),
           f"{level}_lead": np.array([""] * len(sig), dtype=object), f"{level}_jform": np.full(len(sig), -1),
           f"{level}_qref": np.zeros(len(sig), np.int8), f"{level}_qtrig": np.zeros(len(sig), np.int8)}
    if len(ev) == 0 or len(sig) == 0:
        return sig.assign(**out)
    e = ev if lead is None else ev[ev["lead"] == lead]
    jf = e["j_form"].to_numpy()
    ji = e["j_inv"].to_numpy()
    dr = e["dir"].to_numpy()
    bt = e["b_trig"].to_numpy()
    pairs = (e["q_ref"].astype(str) + "→" + e["q_trig"].astype(str)).to_numpy()
    leads = e["lead"].to_numpy()
    qr = e["q_ref"].to_numpy()
    qt = e["q_trig"].to_numpy()
    jt = sig["j_trig"].to_numpy()
    sd = sig["dir"].to_numpy()
    sb = sig[f"{bcol}_trig"].to_numpy()
    order = np.argsort(jf, kind="stable")
    jf_s = jf[order]
    for i in range(len(sig)):
        k = np.searchsorted(jf_s, jt[i], side="right") - 1
        steps = 0
        while k >= 0 and steps < 400:
            m = order[k]
            if sb[i] - bt[m] > max_age_quarters:
                break
            if dr[m] == sd[i] and (ji[m] < 0 or ji[m] > jt[i]):
                out[f"{level}_ssmt"][i] = True
                out[f"{level}_pair"][i] = pairs[m]
                out[f"{level}_lead"][i] = leads[m]
                out[f"{level}_jform"][i] = jf[m]
                out[f"{level}_qref"][i] = qr[m]
                out[f"{level}_qtrig"][i] = qt[m]
                break
            k -= 1
            steps += 1
    return sig.assign(**out)
