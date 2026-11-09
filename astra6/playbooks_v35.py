"""Causal, coverage-qualified execution of the documented V3.4 playbooks."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

import pandas as pd

from . import bars, cisd, fractal_v3, ict, signals, smt
from .coverage_v35 import candle_coverage, load_observed_quotes, observed_runs, quote_gaps
from .execution_v35 import MINUTE, Factor, FactorBook, Opportunity, OrderEngine, Policy, Target
from .research_v35 import load_micro_panel
from .structure_v35 import h1_reversals, linked_mmxm_stages


MODEL1 = Policy(
    "MODEL_1_H1_M5_M15_LIQ", (("ENTRY_CHAIN", ("M5",)),), wait_minutes=15,
    horizon=60, horizon_unit="CLOCK_MINUTES", target_type="M15_LIQ",
    target_min_r=0.75, target_max_r=1.5, max_gap_minutes=1,
    require_observed_path=True, exit_cisd_tf="M15",
)
MODEL2 = Policy(
    "MODEL_2_H1_REV_M5_OC", (("ENTRY_CHAIN", ("M15",)),), wait_minutes=120,
    horizon=120, horizon_unit="CLOCK_MINUTES", target_type="M5_OC",
    target_min_r=1.5, max_gap_minutes=1, require_observed_path=True,
)
AUDIT_WINDOWS = (
    ("2021-11-07", "2021-12-01"), ("2022-03-07", "2022-03-20"), ("2023-10-23", "2023-11-06"),
    ("2024-03-01", "2024-03-25"), ("2025-10-20", "2025-11-10"), ("2026-03-01", "2026-03-31"),
)


def _local_minute(when, timezone):
    local = when.tz_convert(timezone)
    return local.hour * 60 + local.minute


def _ny_morning(when):
    return 570 <= _local_minute(when, bars.NY) < 690


def _model2_qt(when, swept_at):
    """Q3 or an observed NY opening sweep in the same morning 6H cycle."""
    if not _ny_morning(when):
        return False
    phase = bars.quarter_labels(pd.DatetimeIndex([swept_at, when]))
    return bool(phase.iloc[1].q90 == 3 or (
        _ny_morning(swept_at) and phase.iloc[0].b6 == phase.iloc[1].b6
    ))


def _active_cisd(ctx, timeframes, direction, earliest, latest):
    for tf in timeframes:
        data = ctx["cisd_tables"][tf]
        matches = data[
            data["data_coverage_status"].eq("FULL") & data["dir"].eq(direction)
            & data["available_at"].between(earliest, latest)
        ]
        yield from matches.itertuples(index=False)


def _active_stages(stages, frames, numbers, direction, when):
    if stages.empty:
        return stages
    return stages[
        stages["tf"].isin(frames) & stages["stage_num"].isin(numbers)
        & stages["direction"].eq(direction) & stages["is_active"]
        & (stages["available_at"] <= when)
        & (stages["stage_end"].isna() | (when < stages["stage_end"]))
        & (stages["oc_invalidated_at"].isna() | (when < stages["oc_invalidated_at"]))
    ]


def _ssmt_factors(panel, level):
    width = MINUTE if level == "macro" else MINUTE / 2
    tf = "M90" if level == "macro" else "M22.5"
    name = f"{level.upper()}_SSMT"
    age = 180 * MINUTE if level == "macro" else 45 * MINUTE
    for segment in observed_runs(panel, step=width):
        q = bars.quarter_labels(segment.index)
        table = smt.ssmt_events(segment, q, "US100", "US500", level, quote_width=width)
        idx = segment.index
        for row in table.itertuples(index=False):
            if row.lead != "A":
                continue
            when = idx[row.j_form] + width
            expires = min(idx[row.trig_start] + age, idx[row.j_last_tracked] + 2 * width)
            if when < expires:
                invalidated = idx[row.j_inv] + width if row.j_inv >= 0 else None
                yield Factor(
                    f"{name}:{row.inst_pair}:{row.b_ref}:{row.b_trig}:{row.dir}:{when.isoformat()}",
                    name, "US100", tf, row.dir, when, expires, invalidated,
                )


def _available_divergence(factors, direction, when):
    active = [x for x in factors if x.active_at(when)]
    if active and all(x.direction == direction for x in active):
        return active[-1]
    return None


def _active_reference(panel, timeframe, when):
    start = when.floor(f"{bars.TF_MIN[timeframe]}min") - bars.TF_MIN[timeframe] * MINUTE
    return panel.loc[start] if start in panel.index and panel.at[start, "is_complete"] else None


def _entry_trigger(op, policy, when, component_ids):
    return Factor(
        f"{policy.policy_id}:{op.underlying_event_id}:{when.isoformat()}",
        "ENTRY_CHAIN", op.source_instrument, policy.required[0][1][0], op.event_direction,
        when, when + MINUTE, underlying_event_id=op.underlying_event_id,
    ), tuple(component_ids)


def _cisd_id(row):
    return f"CISD:US100:{row.cisd_tf}:{row.available_at.isoformat()}:{row.dir}"


def _model1_inputs(ctx, stages, micro):
    panel = ctx["panel"]
    h1 = bars.resample(panel, "US100", "H1").set_index("bucket_start")
    m15 = bars.resample(panel, "US100", "M15").set_index("bucket_start")
    sweeps = signals.extract_crt_events(ctx, "M5", include_developing=True, require_full=True)
    for row in sweeps[sweeps["dir"].eq(1) & sweeps["reference_coverage_status"].eq("FULL")].itertuples(index=False):
        if (row.j_sweep < 0 or row.j_reclaim < row.j_sweep or (0 <= row.j_other <= row.j_reclaim)
                or row.reference_bucket_start != row.bucket_start - 5 * MINUTE):
            continue
        sweep = panel.index[row.j_sweep] + MINUTE
        reclaim = panel.index[row.j_reclaim] + MINUTE
        extreme = panel["US100_l"].iloc[row.j_sweep:row.j_reclaim + 1].min()
        invalid = panel["US100_l"].iloc[row.j_reclaim + 1:].loc[:sweep + 15 * MINUTE]
        invalid = invalid[invalid < extreme]
        uid = f"MODEL1_M5_SWEEP:{row.bucket_start.isoformat()}:{sweep.isoformat()}"
        invalidations = [invalid.index[0] + MINUTE] if len(invalid) else []
        if row.j_other >= 0:
            invalidations.append(panel.index[row.j_other] + MINUTE)
        op = Opportunity(uid, "US100", "M5", 1, sweep, reclaim, float(extreme - 0.15 * row.atr_ref),
                         min(invalidations, default=None))
        deadline = sweep + 15 * MINUTE
        policy = replace(MODEL1, wait_minutes=max(0, (deadline - reclaim) // MINUTE))
        trigger = None
        targets = []
        progress = {"M5_SWEEP_RECLAIM"}
        confirms = _active_cisd(ctx, ("M1", "M5"), 1, sweep, deadline) if row.A and row.is_complete else ()
        if row.A and row.is_complete:
            progress.add("M5_CRT")
        for confirm in sorted(confirms,
                              key=lambda x: (x.available_at, x.cisd_tf)):
            when = max(confirm.available_at, row.available_at)
            if pd.notna(confirm.invalidated_at) and confirm.invalidated_at <= when:
                continue
            if when > deadline:
                continue
            progress.add("CISD_WITHIN_15M")
            if not (_ny_morning(when) or 480 <= _local_minute(when, bars.LDN) < 630):
                continue
            progress.add("SESSION")
            phase = bars.quarter_labels(pd.DatetimeIndex([when])).iloc[0]
            trend = _active_reference(h1, "H1", when)
            active = _active_stages(stages, ("M5", "H1"), (4, 5, 6), 1, when)
            divergence = _available_divergence(micro, 1, when)
            if phase.q90 not in (2, 3) or trend is None or trend.c <= trend.o:
                continue
            progress.add("Q90_AND_H1_BIAS")
            if active.empty:
                continue
            progress.add("MMXM_04_06")
            if divergence is None:
                continue
            progress.add("MICRO_SSMT")
            state = active.iloc[-1]
            trigger = _entry_trigger(op, MODEL1, when, (
                uid, f"CRT:US100:M5:{row.available_at.isoformat()}:1",
                f"CANDLE:US100:H1:{trend.available_at.isoformat()}", state.mmxm_event_id, state.oc_id,
                divergence.event_id, _cisd_id(confirm),
            ))
            ref = _active_reference(m15, "M15", when)
            if ref is not None:
                origin = f"CANDLE:US100:M15:{ref.available_at.isoformat()}"
                targets.append(Target(f"LIQ:{origin}:1", "M15_LIQ", "M15", ref.h, 1, "US100",
                                      origin, ref.available_at, ref.available_at))
            break
        yield op, policy, trigger, targets, progress


def _model2_oc(oc, state, when):
    """Only an unambiguous M5 origin contained in the actual parent OC."""
    confirmed = oc[(oc["event_kind"] == "CONFIRMED") & oc["data_coverage_status"].eq("FULL")
                   & oc["tf"].eq("M5") & oc["instrument"].eq(state.instrument) & oc["target_dir"].eq(-1)]
    invalidated = oc[(oc["event_kind"] == "INVALIDATED") & (oc["available_at"] <= when)]["oc_id"]
    eligible = confirmed[
        (confirmed["t_start"] >= state.oc_start) & (confirmed["available_at"] <= state.oc_available_at)
        & (confirmed["high"] <= state.oc_high) & (confirmed["low"] >= state.oc_low)
        & ~confirmed["oc_id"].isin(invalidated)
    ]
    if len(eligible) == 1:
        return eligible.iloc[0]
    return None


def _model2_inputs(ctx, oc, stages, macro):
    panel = ctx["panel"]
    m15 = bars.resample(panel, "US100", "M15")
    up = m15[m15["is_complete"] & (m15["c"] > m15["o"])].set_index("available_at")
    for rev in h1_reversals(ctx):
        if rev.direction != -1:
            continue
        uid = f"MODEL2:{rev.event_id}"
        op = Opportunity(uid, "US100", "H1", -1, rev.sweep_available_at, rev.available_at,
                         rev.extreme + 0.15 * rev.atr, rev.invalidated_at, rev.event_id)
        trigger = None
        targets = []
        progress = {"H1_REVERSAL"}
        for confirm in _active_cisd(ctx, ("M15",), -1, rev.available_at + MINUTE, rev.available_at + 120 * MINUTE):
            when = confirm.available_at
            progress.add("M15_CISD")
            if not _model2_qt(when, rev.sweep_available_at):
                continue
            progress.add("NY_MORNING_QT")
            last_up = up.loc[:when].tail(1)
            if last_up.empty or last_up.index[-1] <= rev.sweep_available_at or confirm.break_close >= last_up.iloc[0].l:
                continue
            progress.add("M15_BODY_BREAK")
            active = _active_stages(stages, ("H1", "M15"), (8, 9), -1, when)
            divergence = _available_divergence(macro, -1, when)
            if active.empty or divergence is None:
                continue
            progress.add("MMXM_08_09_AND_MACRO_SSMT")
            active = active[(active["available_at"] >= rev.sweep_available_at)
                            & (active["oc_available_at"] <= rev.sweep_available_at)]
            # The model must reference the very H1 sweep high in its Stage 8.
            peaks = stages[stages["stage_num"].eq(8) & stages["event_price"].eq(rev.extreme)
                           & stages["available_at"].between(rev.sweep_available_at, rev.sweep_close)]
            active = active[active["mmxm_id"].isin(peaks["mmxm_id"])]
            if len(active) != 1:
                continue
            progress.add("SAME_SWEEP")
            state = active.iloc[0]
            parent = _model2_oc(oc, state, when)
            if parent is None:
                continue
            progress.add("M5_OC_ORIGIN")
            trigger = _entry_trigger(op, MODEL2, when, (
                rev.event_id, rev.sweep_id, rev.swing_id, rev.cisd_id,
                state.mmxm_event_id, state.oc_id, parent.oc_id, divergence.event_id, _cisd_id(confirm),
            ))
            invalid = oc[(oc["oc_id"] == parent.oc_id) & (oc["event_kind"] == "INVALIDATED")]["available_at"]
            targets.append(Target(f"TARGET:{parent.oc_id}:UPPER", "M5_OC", "M5", parent.high, -1, "US100",
                                  parent.oc_id, parent.t_confirm, parent.available_at,
                                  invalid.iloc[0] if len(invalid) else None))
            break
        yield op, MODEL2, trigger, targets, progress


def run_playbook_segment(panel, micro):
    """Execute on one continuous segment with original recorded quote inputs."""
    if panel.empty or not (panel.index[1:] - panel.index[:-1] == MINUTE).all():
        raise ValueError("Playbook execution requires a continuous observed quote segment")
    frames = ("M1", "M5", "M15", "H1")
    ctx = {
        "panel": panel, "traded": "US100", "comps": ("US500",),
        "atr1": ict.atr_wilder(*(panel[f"US100_{x}"].to_numpy() for x in "hlc"), 14),
        "cisd_tables": {tf: cisd.extract_tf_cisd_events(panel, tf=tf, require_full=True) for tf in frames},
    }
    oc = fractal_v3.extract_original_consolidations(
        panel, timeframes=("M5", "M15", "H1"), include_lifecycle=True, require_full=True,
    )
    mmxm = fractal_v3.build_fractal_mmxm_state_events(panel, oc)
    stages = linked_mmxm_stages(oc, mmxm)
    executor = OrderEngine(panel, "US100", panel.index[-1])
    exits = [Factor(_cisd_id(r), "CISD", "US100", "M15", r.dir, r.available_at, r.available_at + MINUTE)
             for r in _active_cisd(ctx, ("M15",), -1, panel.index[0], panel.index[-1] + MINUTE)]
    start, end = panel.index[0], panel.index[-1] + MINUTE
    micro = micro.loc[(micro.index >= start) & (micro.index < end)]
    micro_factors = sorted(_ssmt_factors(micro, "micro"), key=lambda x: x.available_at)
    macro_factors = sorted(_ssmt_factors(panel, "macro"), key=lambda x: x.available_at)
    for source in (_model1_inputs(ctx, stages, micro_factors), _model2_inputs(ctx, oc, stages, macro_factors)):
        for op, policy, trigger, targets, progress in source:
            factor, ids = trigger if trigger is not None else (None, ())
            row = executor.execute(op, policy, FactorBook([factor] if factor else []), targets, exit_factors=exits)
            row["playbook_component_event_ids"] = list(ids)
            row["playbook_checks_observed"] = sorted(progress)
            yield row


def _audit_inputs(start, end):
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    if start.tzinfo is None or end.tzinfo is None or not pd.Timedelta(0) < end - start <= pd.Timedelta(days=31):
        raise ValueError("P0 audit requires timezone-aware windows of 31 days or less")
    traded, compare = (load_observed_quotes(x, start, end) for x in ("US100", "US500"))
    panel = traded.join(compare, how="inner")
    return panel, traded.index.union(compare.index), load_micro_panel(start, end)


def _audit_orders(panel, micro):
    return pd.DataFrame(row for run in observed_runs(panel, minimum=120) for row in run_playbook_segment(run, micro))


def audit_window(start, end):
    """Use a small existing local window. This entry point publishes no ranks."""
    panel, _, micro = _audit_inputs(start, end)
    return _audit_orders(panel, micro)


def audit_report():
    """Reproducible P0 sample evidence. No full-history or ranking path."""
    from hashlib import file_digest

    inputs = {}
    for inst in ("US100", "US500"):
        for tf in ("M1", "30S"):
            source = bars.STORE / f"DUKA_{inst}_{tf}.parquet"
            with source.open("rb") as f:
                inputs[source.name] = file_digest(f, "sha256").hexdigest()
    windows = []
    for start, end in AUDIT_WINDOWS:
        panel, union, micro = _audit_inputs(pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC"))
        rows = _audit_orders(panel, micro)
        models = {}
        for model in (MODEL1, MODEL2):
            trades = rows[rows["policy_id"] == model.policy_id] if not rows.empty else rows
            models[model.policy_id] = {
                "candidates": len(trades),
                "fills": int(trades["j_fill"].ge(0).sum()) if len(trades) else 0,
                "completed_observed_paths": int(trades["j_exit"].ge(0).sum()) if len(trades) else 0,
                "checks": dict(Counter(x for checks in trades.get("playbook_checks_observed", ()) for x in checks)),
                "states": dict(Counter(trades.get("execution_status", ()))),
            }
        windows.append({
            "start": start, "end_exclusive": end,
            "observed_common_m1": len(panel), "observed_common_30s": len(micro),
            "gap_counts": quote_gaps(panel, union)["coverage"].value_counts().to_dict(),
            "coverage": {tf: candle_coverage(panel, "US100", tf, union)["strict_coverage"].value_counts().to_dict()
                         for tf in ("M5", "M15", "H1")},
            "models": models,
        })
    return {
        "scope": "P0_DIAGNOSTICS", "status": "NOT_VERIFIED", "historical_backtest_started": False,
        "inputs_sha256": inputs, "windows": windows,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(audit_report(), indent=2))
