"""Phase 4 — Complete Quarterly-Theory Sequential SMT (SSMT) & Multi-Instrument SMT Engine.

Levels
------
* macro    = 90M quarters inside each 6H block      (q90 = 1..4, parent = b6)
* micro    = 22.5M quarters inside each 90M block   (q22 = 1..4, parent = b90)
* submicro = 5.625M quarters inside each 22.5M block (q5  = 1..4, parent = b22)

Quarter Transitions (reference quarter -> trigger quarter)
----------------------------------------------------------
* Q1→Q2, Q1→Q3, Q1→Q4, Q2→Q3, Q2→Q4, Q3→Q4 (within same parent cycle)
* Prev Q4→Curr Q1 (previous parent cycle's Q4 -> current parent cycle's Q1)

Multi-Event Preservation (Phase 4.1 & 4.3)
------------------------------------------
* Every valid SSMT event across all 7 quarter pairs and both lead types ('A' = traded-led,
  'B' = comparator-led) is preserved in the event table with full sequencing timestamps
  (`j_sweep`, `j_form`, `j_inv`, `trig_start`, `elapsed_bars_in_quarter`, `macro_q`, `micro_q`).
* `attach_ssmt` preserves simultaneous active SSMT events (`{level}_ssmt_count`,
  `{level}_all_pairs`, `{level}_has_lead_A`, `{level}_has_lead_B`) as well as the primary
  most-recent active event.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from numba import njit

PAIRS = [(1, 2), (1, 3), (1, 4), (2, 3), (2, 4), (3, 4), (4, 1)]
PAIR_LABELS = {
    (1, 2): "Q1→Q2",
    (1, 3): "Q1→Q3",
    (1, 4): "Q1→Q4",
    (2, 3): "Q2→Q3",
    (2, 4): "Q2→Q4",
    (3, 4): "Q3→Q4",
    (4, 1): "Prev Q4→Curr Q1",
}


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
        # bearish A-led (traded sweeps high, comparator does not)
        if res[0] < 0:
            if canform and a_up and not b_up:
                res[0] = j
        elif res[1] < 0 and b_up:
            res[1] = j
        # bearish B-led (comparator sweeps high, traded does not)
        if res[2] < 0:
            if canform and b_up and not a_up:
                res[2] = j
        elif res[3] < 0 and a_up:
            res[3] = j
        # bullish A-led (traded sweeps low, comparator does not)
        if res[4] < 0:
            if canform and a_dn and not b_dn:
                res[4] = j
        elif res[5] < 0 and b_dn:
            res[5] = j
        # bullish B-led (comparator sweeps low, traded does not)
        if res[6] < 0:
            if canform and b_dn and not a_dn:
                res[6] = j
        elif res[7] < 0 and a_dn:
            res[7] = j
    return res


def ssmt_events(panel: pd.DataFrame, qlab: pd.DataFrame, traded: str, comp: str, level: str = "macro") -> pd.DataFrame:
    """All SSMT events for one traded/comparator pair at one fractal level (`macro`, `micro`, or `submicro`).

    Preserves all simultaneous quarter-pair and lead-type events with full sequencing info.
    """
    if level == "macro":
        bcol, qcol, parent = ("b90", "q90", "b6")
    elif level == "micro":
        bcol, qcol, parent = ("b22", "q22", "b90")
    elif level == "submicro":
        bcol, qcol, parent = ("b5", "q5", "b22")
    else:
        raise ValueError(f"Unknown SSMT level: {level}")

    if f"{traded}_h" not in panel.columns or f"{comp}_h" not in panel.columns:
        return pd.DataFrame()

    ha = panel[f"{traded}_h"].to_numpy(float)
    la = panel[f"{traded}_l"].to_numpy(float)
    hb = panel[f"{comp}_h"].to_numpy(float)
    lb = panel[f"{comp}_l"].to_numpy(float)
    bid = qlab[bcol].to_numpy()
    q90_arr = qlab["q90"].to_numpy()
    q22_arr = qlab["q22"].to_numpy()
    qt_anc = str(qlab["qt_anchor"].iloc[0]) if "qt_anchor" in qlab.columns and len(qlab) else "ny1800"

    brk = np.r_[0, np.nonzero(np.diff(bid))[0] + 1]
    starts = brk
    ends = np.r_[brk[1:], len(bid)]
    blk_ids = bid[starts]
    qs = qlab[qcol].to_numpy()[starts]
    par = qlab[parent].to_numpy()[starts]
    HA, LA = _block_extremes(ha, la, starts, ends)
    HB, LB = _block_extremes(hb, lb, starts, ends)
    pos = {int(b): i for i, b in enumerate(blk_ids)}

    idx = panel.index
    rows = []
    pair_tag = f"{traded}_{comp}"
    for i in range(len(starts)):
        qk = int(qs[i])
        for (qr, qt) in PAIRS:
            if qt != qk:
                continue
            if (qr, qt) == (4, 1):
                ref_blk = blk_ids[i] - 1
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
                jf = int(res[2 * k])
                if jf >= 0:
                    ji = int(res[2 * k + 1])
                    s_i = int(starts[i])
                    rows.append((
                        level, traded, comp, pair_tag, qt_anc,
                        int(blk_ids[r]), int(blk_ids[i]), qr, qt, PAIR_LABELS[(qr, qt)],
                        dr, lead, jf, jf, ji, int(par[i]), s_i, int(ends[i]),
                        jf - s_i, int(q90_arr[jf]), int(q22_arr[jf]),
                    ))

    cols = [
        "level", "traded", "comp", "inst_pair", "qt_anchor",
        "b_ref", "b_trig", "q_ref", "q_trig", "pair_label",
        "dir", "lead", "j_sweep", "j_form", "j_inv", "parent", "trig_start", "trig_end",
        "elapsed_bars", "macro_phase", "micro_phase",
    ]
    df = pd.DataFrame(rows, columns=cols)
    if len(df) == 0:
        return df
    df = df.sort_values(["j_form", "q_ref"]).reset_index(drop=True)
    df["t_form"] = idx[df["j_form"].to_numpy()]
    df["t_inv"] = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ms, UTC]")
    has_inv = df["j_inv"] >= 0
    if has_inv.any():
        df.loc[has_inv, "t_inv"] = idx[df.loc[has_inv, "j_inv"].to_numpy()]
    return df


def attach_ssmt(
    sig: pd.DataFrame,
    ev: pd.DataFrame,
    level: str,
    max_age_quarters: int = 1,
    lead: str | None = None,
    prefix: str | None = None,
) -> pd.DataFrame:
    """Attach active SSMT events at or before `j_trig` (not invalidated by `j_trig`).

    Preserves ALL simultaneous active SSMT events for each signal:
      - `{pfx}_ssmt`: bool (at least one active SSMT)
      - `{pfx}_ssmt_count`: number of simultaneous active SSMT events
      - `{pfx}_all_pairs`: pipe-delimited string of all active quarter transitions (e.g. '1→3|2→3')
      - `{pfx}_has_lead_A`: bool (traded instrument swept reference extreme)
      - `{pfx}_has_lead_B`: bool (comparator swept reference extreme)
      - `{pfx}_pair`: primary (most recently formed) transition 'q_ref→q_trig'
      - `{pfx}_lead`: primary lead ('A' or 'B')
      - `{pfx}_jform`: formation index of primary event
      - `{pfx}_qref`, `{pfx}_qtrig`: reference and trigger quarter numbers
    """
    pfx = prefix or level
    bcol = "b90" if level == "macro" else ("b22" if level == "micro" else "b5")
    n_sig = len(sig)
    out = {
        f"{pfx}_ssmt": np.zeros(n_sig, bool),
        f"{pfx}_ssmt_count": np.zeros(n_sig, np.int16),
        f"{pfx}_all_pairs": np.array([""] * n_sig, dtype=object),
        f"{pfx}_has_lead_A": np.zeros(n_sig, bool),
        f"{pfx}_has_lead_B": np.zeros(n_sig, bool),
        f"{pfx}_pair": np.array([""] * n_sig, dtype=object),
        f"{pfx}_lead": np.array([""] * n_sig, dtype=object),
        f"{pfx}_jform": np.full(n_sig, -1, dtype=np.int64),
        f"{pfx}_qref": np.zeros(n_sig, np.int8),
        f"{pfx}_qtrig": np.zeros(n_sig, np.int8),
    }
    if len(ev) == 0 or n_sig == 0:
        return sig.assign(**out)

    e = ev if lead is None else ev[ev["lead"] == lead]
    if len(e) == 0:
        return sig.assign(**out)

    jf = e["j_form"].to_numpy(np.int64)
    ji = e["j_inv"].to_numpy(np.int64)
    dr = e["dir"].to_numpy(np.int8)
    bt = e["b_trig"].to_numpy(np.int64)
    pairs = (e["q_ref"].astype(str) + "→" + e["q_trig"].astype(str)).to_numpy()
    leads = e["lead"].to_numpy()
    qr = e["q_ref"].to_numpy(np.int8)
    qt = e["q_trig"].to_numpy(np.int8)

    jt = sig["j_trig"].to_numpy(np.int64)
    sd = sig["dir"].to_numpy(np.int8)
    sb = sig[f"{bcol}_trig"].to_numpy(np.int64)

    order = np.argsort(jf, kind="stable")
    jf_s = jf[order]

    for i in range(n_sig):
        k = np.searchsorted(jf_s, jt[i], side="right") - 1
        steps = 0
        cnt = 0
        active_pairs = []
        has_a = False
        has_b = False
        while k >= 0 and steps < 500:
            m = order[k]
            if sb[i] - bt[m] > max_age_quarters:
                break
            if sb[i] >= bt[m] and dr[m] == sd[i] and (ji[m] < 0 or ji[m] > jt[i]):
                if cnt == 0:
                    out[f"{pfx}_ssmt"][i] = True
                    out[f"{pfx}_pair"][i] = pairs[m]
                    out[f"{pfx}_lead"][i] = leads[m]
                    out[f"{pfx}_jform"][i] = jf[m]
                    out[f"{pfx}_qref"][i] = qr[m]
                    out[f"{pfx}_qtrig"][i] = qt[m]
                cnt += 1
                if pairs[m] not in active_pairs:
                    active_pairs.append(str(pairs[m]))
                if leads[m] == "A":
                    has_a = True
                else:
                    has_b = True
            k -= 1
            steps += 1
        if cnt > 0:
            out[f"{pfx}_ssmt_count"][i] = cnt
            out[f"{pfx}_all_pairs"][i] = "|".join(active_pairs)
            out[f"{pfx}_has_lead_A"][i] = has_a
            out[f"{pfx}_has_lead_B"][i] = has_b

    return sig.assign(**out)
