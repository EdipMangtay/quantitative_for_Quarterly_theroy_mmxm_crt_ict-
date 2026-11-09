"""Recorded-price acceptance tests for the strict P0 lane."""

from dataclasses import replace

import pandas as pd
import pytest

from astra6 import bars, cisd, fractal_v3, ict, smt
from astra6.coverage_v35 import candle_coverage, load_observed_quotes, observed_runs, quote_gaps
from astra6.execution_v35 import MINUTE, Factor, FactorBook, Opportunity, OrderEngine, Policy, Target
from astra6.playbooks_v35 import MODEL1, MODEL2, _active_stages, _model1_inputs, _model2_oc, audit_window
from astra6.research_v35 import load_micro_panel
from astra6.structure_v35 import h1_reversals, linked_mmxm_stages


WINDOWS = (
    ("2021-11-07", "2021-11-12"), ("2022-03-11", "2022-03-16"),
    ("2023-10-27", "2023-11-01"), ("2024-03-08", "2024-03-13"),
    ("2025-10-31", "2025-11-05"), ("2026-03-27", "2026-04-01"),
)


def utc(date):
    return pd.Timestamp(date, tz="UTC")


def quotes(start, end):
    a, b = (load_observed_quotes(symbol, start, end) for symbol in ("US100", "US500"))
    return a.join(b, how="inner"), a.index.union(b.index)


@pytest.mark.parametrize(("start", "end"), WINDOWS)
@pytest.mark.parametrize(("anchor", "offset"), (("cal", 0), ("ny0930", 30), ("ldn0800", 0)))
@pytest.mark.parametrize("tf", ("M5", "M15", "H1"))
def test_observed_boundary_and_coverage_across_years(start, end, anchor, offset, tf):
    panel, union = quotes(utc(start), utc(end))
    candles = candle_coverage(panel, "US100", tf, union, anchor)
    width = bars.TF_MIN[tf] * MINUTE
    assert len(candles) > 20
    for row in candles.itertuples(index=False):
        # Whole-hour UTC offsets preserve the M5/M15/H1 grid. NY open shifts
        # H1 by 30 minutes. Both folds of a repeated hour are real UTC hours.
        start = (row.ts_first - offset * MINUTE).floor(width) + offset * MINUTE
        assert (row.bucket_start, row.scheduled_bucket_end) == (start, start + width)
        reference = panel.loc[(panel.index >= start) & (panel.index < start + width), "US100_h"]
        assert (row.h, row.n) == (reference.max(), len(reference))
        expected = pd.date_range(start, start + width - MINUTE, freq=MINUTE)
        missing = expected.difference(reference.index)
        if panel.index[-1] + MINUTE < start + width:
            assert row.strict_coverage == "OPEN"
        else:
            unmatched = len(missing.intersection(union))
            assert row.strict_coverage == ("FULL" if not len(missing) else "INCOMPLETE" if unmatched else "UNKNOWN")
            assert row.unmatched_observed_minutes == unmatched


def test_real_unmatched_quotes_and_unknown_silence_were_previously_indistinguishable():
    panel, union = quotes(utc("2021-11-07"), utc("2021-11-12"))
    legacy = bars.resample(panel, "US100", "H1").set_index("bucket_start")
    strict = candle_coverage(panel, "US100", "H1", union).set_index("bucket_start")
    for kind in ("UNKNOWN", "INCOMPLETE"):
        bucket = strict[strict["strict_coverage"] == kind].index[0]
        assert legacy.at[bucket, "data_coverage_status"] == "PARTIAL_UNCLASSIFIED"
        assert strict.at[bucket, "strict_coverage"] == kind
    runs = list(observed_runs(panel))
    assert len(runs) > 1 and sum(map(len, runs)) == len(panel)
    assert all((r.index[1:] - r.index[:-1] == MINUTE).all() for r in runs)
    gaps = quote_gaps(panel, union)
    assert set(gaps.coverage) == {"UNKNOWN", "INCOMPLETE"}
    for gap in gaps.itertuples(index=False):
        assert gap.unmatched_observed_minutes == ((union >= gap.start) & (union < gap.end)).sum()


def test_modeled_extension_is_excluded_from_strict_prices():
    start, end = utc("2026-10-05"), utc("2026-10-06")
    actual = load_observed_quotes("US100", start, end)
    stored_ask = pd.read_parquet(bars.STORE / "US100_ASK_M1.parquet", columns=["ts"], filters=[
        ("ts", ">=", start), ("ts", "<", end),
    ])
    assert len(stored_ask) > 100
    assert actual.empty


def _context(panel):
    return dict(panel=panel, traded="US100", comps=("US500",),
                atr1=ict.atr_wilder(*(panel[f"US100_{x}"].to_numpy() for x in "hlc"), 14),
                cisd_tables={"H1": cisd.extract_tf_cisd_events(panel, tf="H1", require_full=True)})


def test_real_h1_short_requires_sweep_confirmed_swing_and_separate_cisd():
    day, _ = quotes(utc("2025-10-21"), utc("2025-10-22"))
    panel = next(x for x in observed_runs(day) if utc("2025-10-21 13:00") in x.index)
    ctx = _context(panel)
    expected = utc("2025-10-21 14:00")
    reversal = next(r for r in h1_reversals(ctx) if r.available_at == expected and r.direction == -1)
    # Aggregate recorded minutes independently and inspect the exact bars.
    h1 = panel.resample("1h").agg({"US100_h": "max", "US100_l": "min", "US100_o": "first", "US100_c": "last"})
    prev, swept, broken = (h1.loc[utc(f"2025-10-21 {h}:00")] for h in (11, 12, 13))
    piv = utc("2025-10-21 08:00")
    pivot = h1.at[piv, "US100_l"]
    lows = h1.loc[piv - 2 * 60 * MINUTE:piv + 2 * 60 * MINUTE, "US100_l"]
    assert pivot == lows.min() == reversal.swing_price
    assert reversal.swing_available_at == piv + 3 * 60 * MINUTE
    assert swept.US100_h > prev.US100_h and prev.US100_l <= swept.US100_c <= prev.US100_h
    sweep_quotes = panel.loc[utc("2025-10-21 12:00"):utc("2025-10-21 12:59")]
    assert reversal.sweep_available_at == sweep_quotes[sweep_quotes.US100_h > prev.US100_h].index[0] + MINUTE
    assert broken.US100_c < min(broken.US100_o, pivot) and swept.US100_h >= broken.US100_h
    assert reversal.extreme == swept.US100_h
    assert reversal.cisd_available_at == expected
    # A real sweep and break alone are insufficient. Withhold the confirming event.
    table = ctx["cisd_tables"]["H1"]
    ctx["cisd_tables"]["H1"] = table[table.available_at != expected]
    assert all(r.event_id != reversal.event_id for r in h1_reversals(ctx))
    for cut in (expected - MINUTE, expected):
        rebuilt = list(h1_reversals(_context(panel.loc[panel.index < cut])))
        assert any(r.event_id == reversal.event_id for r in rebuilt) == (cut == expected)
    with_gap = panel.drop(utc("2025-10-21 13:25"))
    assert all(r.event_id != reversal.event_id for r in h1_reversals(_context(with_gap)))


@pytest.mark.parametrize("field", ("oc_id", "mmxm_id", "tf", "instrument", "direction", "available_at"))
def test_real_mmxm_requires_matching_confirmed_origin(field):
    day, _ = quotes(utc("2025-10-21"), utc("2025-10-22"))
    panel = max(observed_runs(day), key=len)
    oc = fractal_v3.extract_original_consolidations(
        panel, timeframes=("M5", "M15", "H1"), include_lifecycle=True, require_full=True,
    )
    mmxm = fractal_v3.build_fractal_mmxm_state_events(panel, oc)
    linked = linked_mmxm_stages(oc, mmxm)
    row = linked[linked["stage_num"].isin([4, 5, 6])].iloc[0]
    assert row.oc_available_at <= row.available_at
    assert row.mmxm_event_id in set(_active_stages(
        linked, (row.tf,), (row.stage_num,), row.direction, row.available_at,
    )["mmxm_event_id"])
    broken = mmxm.loc[mmxm["mmxm_event_id"] == row.mmxm_event_id].copy()
    replacements = {
        "oc_id": "other_oc", "mmxm_id": "other_model", "tf": "H4", "instrument": "US500",
        "direction": -row.direction, "available_at": row.oc_available_at - MINUTE,
    }
    broken[field] = replacements[field]
    assert linked_mmxm_stages(oc, broken).empty


def test_real_m5_oc_upper_edge_has_same_parent_and_is_known_in_advance():
    day, _ = quotes(utc("2025-10-21"), utc("2025-10-22"))
    panel = max(observed_runs(day), key=len)
    oc = fractal_v3.extract_original_consolidations(
        panel, timeframes=("M5", "M15", "H1"), include_lifecycle=True, require_full=True,
    )
    states = linked_mmxm_stages(oc, fractal_v3.build_fractal_mmxm_state_events(panel, oc))
    stage = states.set_index("mmxm_event_id").loc["MMXM_US100_H1_1761030000_S08"]
    child = _model2_oc(oc, stage, stage.available_at)
    assert child.oc_id == "OC_US100_M5_1761042600"
    start = pd.Timestamp(1761042600, unit="s", tz="UTC")
    raw = panel.loc[(panel.index >= start) & (panel.index < start + 20 * MINUTE)]
    assert len(raw) == 20
    assert (child.high, child.low) == (raw.US100_h.max(), raw.US100_l.min())
    assert child.high == 25117.403 and child.high != child.midpoint
    assert child.available_at == start + 25 * MINUTE
    assert child.available_at <= stage.oc_available_at <= stage.available_at
    without_child = oc[oc.oc_id != child.oc_id]
    assert _model2_oc(without_child, stage, stage.available_at) is None
    with_late_child = oc.copy()
    with_late_child.loc[(oc.oc_id == child.oc_id) & (oc.event_kind == "CONFIRMED"), "available_at"] = stage.available_at + MINUTE
    assert _model2_oc(with_late_child, stage, stage.available_at) is None


def test_model1_real_stop_and_deadline_exist_before_m5_close():
    panel, _ = quotes(utc("2021-11-07 23:45"), utc("2021-11-08 00:16"))
    sweep, reclaim = utc("2021-11-07 23:56"), utc("2021-11-07 23:57")

    def opportunity(prices):
        ctx = _context(prices)
        ctx["cisd_tables"].update({tf: cisd.extract_tf_cisd_events(prices, tf=tf, require_full=True)
                                   for tf in ("M1", "M5")})
        return next(x for x in _model1_inputs(ctx, pd.DataFrame(), ()) if x[0].event_observed_at == sweep)

    before_close = panel.loc[panel.index < reclaim]
    early, early_policy, early_trigger, _, checks = opportunity(before_close)
    later, policy, _, _, _ = opportunity(panel)
    assert checks == {"M5_SWEEP_RECLAIM"} and early_trigger is None
    assert early.event_available_at == later.event_available_at == reclaim
    assert early_policy.wait_minutes == policy.wait_minutes == 14
    history = panel.loc[panel.index < utc("2021-11-07 23:55")]
    h = history.US100_h.resample("5min").max()
    l = history.US100_l.resample("5min").min()
    c = history.US100_c.resample("5min").last()
    trs = [h.iloc[0] - l.iloc[0], max(h.iloc[1] - l.iloc[1], abs(h.iloc[1] - c.iloc[0]), abs(l.iloc[1] - c.iloc[0]))]
    low = panel.loc[utc("2021-11-07 23:55"):reclaim - MINUTE, "US100_l"].min()
    assert early.stop_price == later.stop_price == pytest.approx(low - 0.15 * sum(trs) / 2)
    assert panel.loc[reclaim:, "US100_l"].min() < low
    assert later.event_invalidated_at is not None


def test_v34_future_model_targets_do_not_reappear_in_strict_playbooks():
    rows = audit_window("2021-11-15T00:00Z", "2021-11-19T00:00Z")
    assert len(rows) > 0
    old_fills = [utc("2021-11-15 09:02"), utc("2021-11-18 14:47")]
    assert not rows.t_fill.isin(old_fills).any()
    for row in rows[rows.j_fill >= 0].itertuples(index=False):
        assert row.target_available_at <= row.decision_at <= row.t_fill
        assert row.playbook_component_event_ids


@pytest.mark.parametrize(("start", "end"), WINDOWS)
def test_strict_oc_mmxm_prefix_across_years(start, end):
    panel, _ = quotes(utc(start), utc(end))
    panel = max(observed_runs(panel), key=len)
    assert len(panel) > 400
    tf = ("M5", "M15", "H1")

    def extract(prices):
        oc = fractal_v3.extract_original_consolidations(
            prices, timeframes=tf, include_lifecycle=True, require_full=True,
        )
        return oc, fractal_v3.build_fractal_mmxm_state_events(prices, oc, timeframes=tf)

    oc, states = extract(panel)
    for n in (len(panel) // 3, len(panel) * 2 // 3, len(panel) - 1):
        cutoff = panel.index[n - 1] + MINUTE
        truncated = extract(panel.iloc[:n])
        for original, prefix, keys in zip(
            (oc, states), truncated,
            (("oc_id", "event_kind", "tf", "available_at", "high", "low", "target_dir"),
             ("mmxm_event_id", "oc_id", "tf", "direction", "available_at", "stage_num", "target_price", "is_active")),
        ):
            expected = original.loc[original.available_at <= cutoff, list(keys)].reset_index(drop=True)
            actual = prefix.reindex(columns=list(keys)).reset_index(drop=True)
            pd.testing.assert_frame_equal(expected.astype(str), actual.astype(str))


def test_macro_ssmt_does_not_use_incomplete_reference():
    panel, _ = quotes(utc("2025-10-21"), utc("2025-10-22"))
    run = max(observed_runs(panel), key=len)
    truncated = run.iloc[71:]  # Real window begins inside its reference quarter.
    labels = bars.quarter_labels(truncated.index)
    legacy = smt.ssmt_events(truncated, labels, "US100", "US500")
    strict = smt.ssmt_events(truncated, labels, "US100", "US500", quote_width=MINUTE)
    first = labels.iloc[0]
    assert first.sec_in_q90 > 0
    assert (legacy.b_ref == first.b90).any()
    assert not (strict.b_ref == first.b90).any()
    for ref in strict.b_ref.unique():
        times = labels[labels.b90 == ref].index
        assert len(times) == 90 and times[-1] - times[0] == 89 * MINUTE


def test_micro_ssmt_reference_uses_all_45_recorded_half_minutes():
    start, end = utc("2025-10-21 12:00"), utc("2025-10-21 20:00")
    quotes_30s = load_micro_panel(start, end)
    panel = max(observed_runs(quotes_30s, step=MINUTE / 2), key=len)
    labels = bars.quarter_labels(panel.index)
    evidence = smt.ssmt_events(panel, labels, "US100", "US500", "micro", quote_width=MINUTE / 2)
    assert len(evidence) > 0
    for ref in evidence.b_ref.unique():
        times = labels[labels.b22 == ref].index
        assert len(times) == 45
        assert times[-1] - times[0] == 22 * MINUTE
        assert labels.at[times[0], "sec_in_q22"] == 0
    early = evidence.iloc[0]
    ref = labels[labels.b22 == early.b_ref].index[2]
    gapped = panel.drop(ref)
    legacy = smt.ssmt_events(gapped, labels.loc[gapped.index], "US100", "US500", "micro")
    strict = smt.ssmt_events(gapped, labels.loc[gapped.index], "US100", "US500", "micro", quote_width=MINUTE / 2)
    assert (legacy.b_ref == early.b_ref).any()
    assert not (strict.b_ref == early.b_ref).any()


def test_strict_execution_does_not_invent_exit_through_an_observed_gap():
    panel, _ = quotes(utc("2025-10-21"), utc("2025-10-22"))
    split = next(i for i in range(10, len(panel) - 5) if panel.index[i + 1] - panel.index[i] > MINUTE)
    fill = split - 3
    t = panel.index[fill]
    extreme = panel["US100_l"].iloc[fill:split + 1].min()
    op = Opportunity("gap-test", "US100", "M5", 1, t, t, extreme - 100)
    executor = OrderEngine(panel, "US100", panel.index[-1])
    policy = Policy("test_gap", horizon=10)
    legacy = executor.execute(op, policy, FactorBook([]))
    strict = executor.execute(op, replace(policy, require_observed_path=True), FactorBook([]))
    assert legacy["t_exit"] > panel.index[split] + MINUTE and legacy["realized_net_r"] is not None
    assert strict["j_fill"] == fill and strict["j_exit"] == -1
    assert strict["execution_status"] == "DATA_END" and strict["realized_net_r"] is None
    assert strict["status_at"] == panel.index[split] + MINUTE


def test_playbook_execution_enforces_distance_and_opposite_cisd_exit():
    panel, _ = quotes(utc("2025-10-21"), utc("2025-10-22"))
    panel = max(observed_runs(panel), key=len)
    t = panel.index[100]
    ep = panel.loc[t, "US100_ao"] + 0.25
    # A declared distant protective stop isolates the exit rule. All executed
    # prices still come from the recorded Bid/Ask path.
    op = Opportunity("cisd-exit-test", "US100", "M5", 1, t, t, ep - 100)
    table = cisd.extract_tf_cisd_events(panel, tf="M15", require_full=True)
    when = table[(table.dir == -1) & (table.available_at > t)].iloc[0].available_at
    signal = Factor("recorded-m15-cisd", "CISD", "US100", "M15", -1, when, when + MINUTE)
    target = Target("too-far", "M15_LIQ", "M15", ep + 200, 1, "US100", "prior", t, t)
    engine = OrderEngine(panel, "US100", panel.index[-1])
    policy = replace(MODEL1, required=())
    old = engine.execute(op, replace(policy, target_min_r=0, target_max_r=None, exit_cisd_tf=None), FactorBook([]), [target])
    assert old["j_fill"] >= 0
    assert engine.execute(op, policy, FactorBook([]), [target])["reason"] == "TARGET_DISTANCE_OUTSIDE_POLICY"
    valid = replace(target, price=ep + 125)
    result = engine.execute(op, replace(policy, horizon=240), FactorBook([]), [valid], exit_factors=[signal])
    assert result["execution_status"] == "OPPOSITE_CISD_EXIT"
    assert result["t_exit"] == when
    assert result["exit_price"] == panel.loc[when, "US100_o"] - 0.25
    assert result["realized_net_r"] == pytest.approx((panel.loc[when, "US100_o"] - 0.25 - ep) / 100)
    assert MODEL2.target_min_r == 1.5 and MODEL2.horizon == 120


def test_playbook_audit_rejects_oversize_windows():
    with pytest.raises(ValueError, match="31 days"):
        audit_window("2021-11-07T00:00Z", "2026-11-06T00:00Z")
