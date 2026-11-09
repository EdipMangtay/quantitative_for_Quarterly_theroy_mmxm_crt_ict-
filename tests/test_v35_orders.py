"""Behavioral tests for V3.5 decisions, orders, and target provenance."""

import numpy as np
import pandas as pd
import pytest

from astra6 import bars, fractal_v3, research_v35, signals
from astra6.execution_v35 import (
    MINUTE, Factor, FactorBook, Opportunity, OrderEngine, Policy, Target,
    _exit_path, cisd_policies,
)


@pytest.fixture(scope="module")
def evidence():
    panel = bars.load_panel().iloc[:1300]
    ctx = signals.build_context(panel)
    opportunities, scoped = research_v35.build_opportunities(ctx)
    mmxm = fractal_v3.build_fractal_mmxm_state_events(
        panel, fractal_v3.extract_original_consolidations(panel, timeframes=("M5", "M15", "H1")),
    )
    factors = FactorBook(scoped + research_v35.context_factors(ctx, mmxm))
    return panel, {op.underlying_event_id: op for op in opportunities}, factors


@pytest.mark.parametrize(
    ("policy_id", "confirmation"),
    [
        ("00_No_CISD", 887), ("01_M1_CRT_CISD", 888), ("M1_STANDALONE_CISD", 901),
        ("M5_STANDALONE_CISD", 903), ("M15_STANDALONE_CISD", 908),
    ],
)
def test_audited_short_matches_independent_ask_path(evidence, policy_id, confirmation):
    panel, ops, book = evidence
    op = ops["UEV_US100_M5_884_S"]
    policy = next(p for p in cisd_policies() if p.policy_id == policy_id)
    result = OrderEngine(panel, "US100", panel.index[-1]).execute(op, policy, book)

    fill = confirmation + 1
    ep = panel["US100_o"].iloc[fill] - 0.25
    stop = panel["US100_h"].iloc[884:888].max() + 1.5
    risk = stop - ep
    target = ep - 2 * risk
    exit_j = fill + 360
    exit_quote = panel["US100_ac"].iloc[exit_j]
    for j in range(fill, exit_j + 1):
        quote = panel.iloc[j]
        if quote.US100_ao >= stop:
            exit_j, exit_quote = j, quote.US100_ao
            break
        if quote.US100_ah >= stop:
            exit_j, exit_quote = j, stop
            break
        if quote.US100_al <= target:
            exit_j, exit_quote = j, target
            break

    assert result["j_confirm"] == confirmation
    assert result["t_confirm_available"] == panel.index[confirmation] + MINUTE
    assert result["j_fill"] == fill
    assert result["entry_price"] == pytest.approx(ep)
    assert result["stop_price"] == pytest.approx(stop)
    assert result["target_price"] == pytest.approx(target)
    assert result["j_exit"] == exit_j
    assert result["exit_quote"] == pytest.approx(exit_quote)
    assert result["realized_net_r"] == pytest.approx((ep - exit_quote - 0.25) / risk)


def test_early_stop_does_not_change_when_lower_future_low_is_added(evidence):
    panel, ops, _ = evidence
    op = ops["UEV_US100_M5_54_L"]
    prefix = signals.build_context(panel.iloc[:56])
    early, _ = research_v35.build_opportunities(prefix, timeframes=("M5",), anchors=("cal", "ny0930", "ldn0800"))
    matches = [x for x in early if x.underlying_event_id.startswith(op.underlying_event_id)]
    assert len(matches) == 1
    assert matches[0].event_available_at == op.event_available_at
    assert matches[0].stop_price == op.stop_price == pytest.approx(panel["US100_l"].iloc[54:56].min() - 1.5)
    assert op.stop_price > panel["US100_l"].iloc[54:59].min() - 1.5
    assert all(x.event_observed_at <= x.event_available_at for x in early)


@pytest.mark.parametrize("kind,tf", [("MACRO_SSMT", "M90"), ("MICRO_SSMT", "M22.5")])
def test_required_ssmt_waits_for_the_event_while_disabled_ignores_it(evidence, kind, tf):
    _, ops, _ = evidence
    op = ops["UEV_US100_M5_884_S"]
    start = op.event_available_at
    book = FactorBook([Factor("later", kind, "US100", tf, -1, start + 2 * MINUTE, start + 8 * MINUTE)])
    assert book.choose(op, Policy("disabled"), start + MINUTE) == (start, ())
    assert book.choose(op, Policy("required", ((kind, (tf,)),)), start + MINUTE) is None
    assert book.choose(op, Policy("required", ((kind, (tf,)),)), start + 3 * MINUTE)[0] == start + 2 * MINUTE


def test_invalid_or_conflicting_factor_does_not_qualify(evidence):
    _, ops, _ = evidence
    op = ops["UEV_US100_M5_884_S"]
    start = op.event_available_at
    end = start + 5 * MINUTE
    facts = [
        Factor("invalid", "STD_SMT", "US100", "M5", -1, start - MINUTE, end, start),
        Factor("other_instrument", "CISD", "US500", "M5", -1, start, end),
        Factor("other_timeframe", "CISD", "US100", "M15", -1, start, end),
        Factor("conflict", "CISD", "US100", "M1", 1, start, end),
        Factor("aligned", "CISD", "US100", "M1", -1, start, end),
    ]
    book = FactorBook(facts)
    for required in (("STD_SMT", ()), ("CISD", ("M5",)), ("CISD", ("M1",))):
        assert book.choose(op, Policy("required", (required,)), end) is None
    assert book.choose(op, Policy("absent", absent=(("CISD", ("M5",)),)), end) == (start, ())


def test_stop_hit_while_waiting_cannot_be_resurrected(evidence):
    panel, ops, _ = evidence
    op = ops["UEV_US100_M5_54_L"]
    start = op.event_available_at
    fact = Factor("late", "CISD", "US100", "M15", 1, start + 20 * MINUTE, start + 30 * MINUTE)
    out = OrderEngine(panel, "US100", panel.index[-1]).execute(
        op, Policy("wait", (("CISD", ("M15",)),)), FactorBook([fact]),
    )
    assert out["execution_status"] == "INVALIDATED_BEFORE_ENTRY"
    assert out["event_invalidated_at"] < fact.available_at
    assert out["entry_price"] is None
    assert out["j_fill"] == out["j_exit"] == -1


def test_gap_stop_uses_next_executable_quote_and_ambiguity_is_conservative(evidence):
    panel, _, _ = evidence
    data = panel[["US100_o", "US100_h", "US100_l", "US100_c"]].to_numpy().T.copy()
    op, hi, lo, _ = data[:, 888]
    assert lo < op < hi
    stop = (op + lo) / 2
    target = (op + hi) / 2
    assert _exit_path(*data, 888, 888, 1, stop, target, False) == (3, 888, stop, False)
    stop = (data[3, 887] + op) / 2
    assert op > stop > data[3, 887]
    assert _exit_path(*data, 888, 889, -1, stop, lo, False) == (2, 888, op, True)


def test_target_selection_excludes_future_consumed_and_unlinked_levels(evidence):
    panel, ops, _ = evidence
    op = ops["UEV_US100_M5_884_S"]
    decision = op.event_available_at
    target_price = panel["US100_al"].iloc[888:903].min()
    future = Target("late", "M5_OC", "M5", target_price, -1, "US100", "oc_late", decision + MINUTE, decision + MINUTE)
    consumed_price = panel["US100_al"].iloc[887]
    consumed = Target("consumed", "M5_OC", "M5", consumed_price, -1, "US100", "oc_consumed", decision - MINUTE, decision - MINUTE)
    valid = Target("valid", "M5_OC", "M5", target_price, -1, "US100", "oc_valid", decision, decision)
    unlinked = Target("unlinked", "M5_OC", "M5", target_price + 1, -1, "US100", "oc_unlinked", decision, decision)
    fact = Factor("parent", "MMXM", "US100", "M5", -1, decision, decision + MINUTE, parent_structure_id="oc_valid")
    engine = OrderEngine(panel, "US100", panel.index[-1])
    policy = Policy("causal", (("MMXM", ("M5",)),), target_type="M5_OC", require_linked_target=True)
    out = engine.execute(op, policy, FactorBook([fact]), (future, consumed, valid, unlinked))
    assert out["target_event_id"] == "valid"
    assert out["known_before_entry"] is True
    assert out["target_available_at"] <= out["decision_at"] <= out["t_fill"]
    assert out["target_price"] == target_price
    missing = engine.execute(op, policy, FactorBook([fact]), (future, consumed, unlinked))
    assert missing["reason"] == "NO_CAUSAL_TARGET"
    assert missing["entry_price"] is None


def test_real_model1_and_model2_late_targets_are_replanned_from_raw_quotes():
    panel = bars.load_panel().iloc[:11300]
    ctx = signals.build_context(panel)
    oc = fractal_v3.extract_original_consolidations(
        panel, timeframes=("M5", "M15", "H1"), include_lifecycle=True,
    )
    mmxm = fractal_v3.build_fractal_mmxm_state_events(panel, oc)
    ops, scoped = research_v35.build_opportunities(ctx, timeframes=("H1",))
    ops = {x.underlying_event_id: x for x in ops}
    book = FactorBook(scoped + research_v35.context_factors(ctx, mmxm))
    targets = research_v35.build_targets(panel, "US100", oc)
    engine = OrderEngine(panel, "US100", panel.index[-1])
    cases = (
        ("UEV_US100_H1_10835_L", "M15_LIQ", 16423.399, "2021-11-18 14:47Z", "2021-11-18 15:00Z"),
        ("UEV_US100_H1_6931_S", "M5_OC", 16219.269, "2021-11-15 09:02Z", "2021-11-15 10:00Z"),
    )
    for uid, target_type, old_price, old_fill, confirmed in cases:
        old_fill, confirmed = pd.Timestamp(old_fill), pd.Timestamp(confirmed)
        assert old_fill < confirmed
        source = [x for x in targets if x.target_type == target_type and abs(x.price - old_price) < 1e-8]
        assert not any(x.available_at == confirmed and x.available_at <= old_fill for x in source)
        if uid.endswith("_L"):
            previous = panel.loc["2021-11-18 13:00Z":"2021-11-18 13:59Z"]
            current = panel.loc["2021-11-18 14:00Z":old_fill - MINUTE]
            high_break = current[current.US100_h > previous.US100_h.max()].index[0]
            low_break = current[current.US100_l < previous.US100_l.min()].index[0]
            assert high_break < low_break
            assert uid not in ops
            continue
        op = ops[uid]
        out = engine.execute(op, research_v35.model_timing_probe(op.event_direction), book, targets)
        assert out["event_available_at"] == op.event_available_at
        if out["j_fill"] >= 0:
            assert out["target_available_at"] <= out["decision_at"] <= out["t_fill"]
        else:
            assert out["entry_price"] is None
            assert out["reason"] is not None
