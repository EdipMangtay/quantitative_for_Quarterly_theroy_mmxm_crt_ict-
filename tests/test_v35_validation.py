"""V3.5 evidence gates independent of market-price fixture generation."""

from dataclasses import replace

import pandas as pd
import pytest

from astra6.audit_v34_models import run_audit
from astra6.engine_v3 import _fast_cell_metrics
from astra6.fractal_narrative_v34 import NARRATIVES, NarrativeEvent, verify_narrative
from astra6.hpc import compute_source_store_sha256


def test_missing_model_outputs_never_create_synthetic_returns(tmp_path):
    df, report = run_audit(tmp_path / "absent.parquet")
    assert df.n_trades.eq(0).all()
    assert df.expectancy_r.isna().all()
    assert df.validation_status.eq("NOT_VERIFIED").all()
    assert len(df[df.model_id.str.startswith("MODEL_4")]) == 3
    assert not report["historical_gate_passed"]


def test_drawdown_uses_exit_chronology():
    df = pd.DataFrame({"j_exit": [4, 1, 2, 3], "r": [-3.0, -3.0, 5.0, 1.0]})
    assert _fast_cell_metrics(df)["max_dd_r"] == 3.0
    assert _fast_cell_metrics(df.iloc[::-1])["max_dd_r"] == 3.0


def test_same_size_internal_change_invalidates_full_hash(tmp_path):
    path = tmp_path / "US100_BID_M1.parquet"
    path.write_bytes(b"a" * (4 * 1024 * 1024))
    before = compute_source_store_sha256(tmp_path)
    with path.open("r+b") as handle:
        handle.seek(1024 * 1024)
        handle.write(b"b")
    assert compute_source_store_sha256(tmp_path) != before


@pytest.mark.parametrize("narrative", list(NARRATIVES))
def test_narrative_requires_every_event_and_parent(narrative):
    start = pd.Timestamp("2021-11-08 14:35Z")
    events = []
    for i, (kind, timeframes, direction) in enumerate(NARRATIVES[narrative]):
        available = start + pd.Timedelta(minutes=i)
        events.append(NarrativeEvent(
            f"e{i}", kind, "US100", timeframes[0], direction, available, available,
            events[-1].event_id if events else None,
        ))
    decision = start + pd.Timedelta(minutes=15)
    assert verify_narrative(narrative, events, "US100", decision)
    for i in range(len(events)):
        assert not verify_narrative(narrative, events[:i] + events[i + 1:], "US100", decision)
    assert not verify_narrative(narrative, [*events[:-1], replace(events[-1], parent_event_id="other")], "US100", decision)
    assert not verify_narrative(narrative, [*events[:-1], replace(events[-1], invalidated_at=decision)], "US100", decision)
    if narrative == "H4_BEARISH_TO_D1_SSL":
        assert not verify_narrative(narrative, [replace(events[0], timeframe="H1"), *events[1:]], "US100", decision)


def test_paired_ablation_and_portfolio_have_different_populations():
    from astra6.stats import non_overlapping_policy_trades, paired_policy_ledger

    start = pd.Timestamp("2021-11-08 14:35Z")
    rows = []
    for policy, event, fill, exit_at, result in (
        ("ON", "a", 0, 4, 1.0), ("ON", "b", 1, 6, -1.0),
        ("OFF", "a", 1, 7, -1.0), ("OFF", "c", 8, 9, 0.0),
    ):
        rows.append(dict(
            policy_id=policy, underlying_event_id=event, j_fill=fill,
            t_fill=start + pd.Timedelta(minutes=fill), t_exit=start + pd.Timedelta(minutes=exit_at),
            event_available_at=start, realized_net_r=result,
        ))
    ledger = pd.DataFrame(rows)
    assert non_overlapping_policy_trades(ledger, "ON").underlying_event_id.tolist() == ["a"]
    pairs = paired_policy_ledger(ledger, "ON", "OFF")
    assert pairs.underlying_event_id.tolist() == ["a"]
    assert pairs.delta_r.tolist() == [2.0]
