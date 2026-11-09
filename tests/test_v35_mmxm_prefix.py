"""Raw quote → OC lifecycle → MMXM state regressions."""

import json
import os
from pathlib import Path

import pandas as pd

from astra6 import bars, fractal_v3


TIMEFRAMES = ("M5", "M15", "M30", "H1", "H4", "D1")
CUTOFFS = (500, 884, 889, 900, 1500, 2000, 2048, 4096, 8192, 12000, 16384)
OC_KEYS = ("oc_id", "event_kind", "tf", "available_at", "high", "low", "midpoint", "target_dir", "is_accessible")
MMXM_KEYS = (
    "mmxm_event_id", "mmxm_id", "oc_id", "tf", "direction", "stage_num",
    "j_m1_known", "available_at", "event_price", "target_price", "is_active", "j_terminal_m1",
)


def _build(panel):
    oc = fractal_v3.extract_original_consolidations(
        panel, timeframes=TIMEFRAMES, include_lifecycle=True,
    )
    mmxm = fractal_v3.build_fractal_mmxm_state_events(panel, oc, timeframes=TIMEFRAMES)
    return oc, mmxm


def _keys(frame, columns):
    return set(frame[list(columns)].astype("str").fillna("<NA>").itertuples(index=False, name=None))


def test_real_quote_prefix_state_and_selection():
    panel = bars.load_panel().iloc[:17000]
    base_oc, base_mmxm = _build(panel)
    diffs = []
    for n in CUTOFFS:
        cutoff = panel.index[n - 1] + pd.Timedelta(minutes=1)
        oc, mmxm = _build(panel.iloc[:n])
        expected = (
            _keys(base_oc[base_oc["available_at"] <= cutoff], OC_KEYS),
            _keys(base_mmxm[base_mmxm["j_m1_known"] < n], MMXM_KEYS),
        )
        actual = (_keys(oc, OC_KEYS), _keys(mmxm, MMXM_KEYS))
        diff = {"observations": n, "cutoff_utc": cutoff.isoformat()}
        for name, want, got in zip(("oc", "mmxm"), expected, actual):
            diff[name] = {"missing": sorted(want - got), "unexpected": sorted(got - want)}
        selection_changes = []
        for j in range(n - 80, n):
            want = fractal_v3.active_mmxm_asof(base_mmxm, j)
            got = fractal_v3.active_mmxm_asof(mmxm, j)
            if _keys(want, MMXM_KEYS) != _keys(got, MMXM_KEYS):
                selection_changes.append(j)
        diff["asof_changed_bars"] = selection_changes
        diffs.append(diff)

    destination = os.environ.get("ASTRA6_PREFIX_DIFF")
    if destination:
        Path(destination).write_text(json.dumps(diffs, indent=2) + "\n")
    for diff in diffs:
        assert all(not x for key in ("oc", "mmxm") for x in diff[key].values()), diff
        assert not diff["asof_changed_bars"], diff


def test_oc_candidate_has_no_future_direction_and_terminal_never_reappears():
    oc, events = _build(bars.load_panel().iloc[:17000])
    candidate = oc[oc["event_kind"] == "CANDIDATE"]
    assert len(candidate) > 0
    assert candidate["target_dir"].isna().all()
    confirmed = oc[oc["event_kind"] == "CONFIRMED"].set_index("oc_id")
    for row in events[events["stage_num"] == 1].itertuples():
        assert row.available_at == confirmed.loc[row.oc_id, "available_at"]
    assert (events.loc[events["is_active"], "j_terminal_m1"] == -1).all()
    terminals = events[~events["is_active"]]
    assert len(terminals) > 0
    for row in terminals.iloc[::17].itertuples():
        assert row.mmxm_id not in set(fractal_v3.active_mmxm_asof(events, row.j_m1_known)["mmxm_id"])
