"""Negative control. Run explicitly with pytest; legacy paths should fail."""

from pathlib import Path

import pandas as pd

from astra6 import bars, fractal_v3, research_v35, smt
from astra6.coverage_v35 import load_observed_quotes, observed_runs
from astra6.execution_v35 import MINUTE, FactorBook, Opportunity, OrderEngine, Policy


def _utc(value):
    return pd.Timestamp(value, tz="UTC")


def _panel(start, end):
    return load_observed_quotes("US100", _utc(start), _utc(end)).join(
        load_observed_quotes("US500", _utc(start), _utc(end)), how="inner",
    )


def test_legacy_coverage_must_distinguish_unknown_from_incomplete():
    panel = _panel("2021-11-07", "2021-11-12")
    statuses = set(bars.resample(panel, "US100", "H1").data_coverage_status)
    assert {"UNKNOWN", "INCOMPLETE"} <= statuses


def test_legacy_ssmt_must_reject_incomplete_reference():
    panel = max(observed_runs(_panel("2025-10-21", "2025-10-22")), key=len).iloc[71:]
    labels = bars.quarter_labels(panel.index)
    events = smt.ssmt_events(panel, labels, "US100", "US500")
    assert not events.b_ref.eq(labels.iloc[0].b90).any()


def test_legacy_mmxm_must_reject_nonexistent_oc():
    panel = max(observed_runs(_panel("2025-10-21", "2025-10-22")), key=len)
    oc = fractal_v3.extract_original_consolidations(panel, timeframes=("M5", "M15", "H1"))
    events = fractal_v3.build_fractal_mmxm_state_events(panel, oc)
    evidence = events[events.stage_num.eq(4)].iloc[:1].assign(oc_id="nonexistent")
    ctx = dict(panel=panel, traded="US100", cisd_tables={}, ssmt_mac=pd.DataFrame())
    assert not research_v35.context_factors(ctx, evidence)


def _old_model_target(tf, entry_tf, uid):
    path = Path(__file__).resolve().parents[1] / "data" / "results" / "target_candidates.parquet"
    rows = pd.read_parquet(path, columns=["t_signal_known", "target_px", "distance_r"], filters=[
        ("underlying_event_id", "==", uid), ("target_type", "==", tf), ("entry_tf", "==", entry_tf),
    ])
    assert len(rows) == 1
    return rows.iloc[0]


def test_v34_model1_must_use_an_available_prior_m15_target_in_band():
    old = _old_model_target("M15_LIQ", "M5", "UEV_US100_H1_10835_L")
    panel = _panel("2021-11-18 14:45", "2021-11-18 15:00")
    assert old.target_px == panel.US100_h.max()
    assert (_utc("2021-11-18 15:00") <= old.t_signal_known, 0.75 <= old.distance_r <= 1.5) == (True, True)


def test_v34_model2_must_wait_for_the_h1_reversal_and_oc_source():
    old = _old_model_target("M5_OC", "M15", "UEV_US100_H1_6931_S")
    # The current H1 candle and the OC source both close at 10:00 UTC.
    assert (_utc("2021-11-15 10:00") <= old.t_signal_known, old.distance_r >= 1.5) == (True, True)


def test_legacy_engine_must_not_assign_r_across_unknown_gap():
    panel = _panel("2025-10-21", "2025-10-22")
    split = next(i for i in range(10, len(panel) - 5) if panel.index[i + 1] - panel.index[i] > MINUTE)
    fill = split - 3
    when = panel.index[fill]
    low = panel["US100_l"].iloc[fill:split + 1].min()
    opportunity = Opportunity("gap-test", "US100", "M5", 1, when, when, low - 100)
    result = OrderEngine(panel, "US100", panel.index[-1]).execute(
        opportunity, Policy("legacy", horizon=10), FactorBook([]),
    )
    assert result["realized_net_r"] is None
