"""Causal candidate, factor and execution contracts shared by V3.5 policies."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from itertools import product

import numpy as np
import pandas as pd
from numba import njit


MINUTE = pd.Timedelta(minutes=1)
CORE_FACTORS = ("CRT", "MACRO_SSMT", "MICRO_SSMT", "STD_SMT", "CISD", "MMXM")


@dataclass(frozen=True)
class Opportunity:
    underlying_event_id: str
    source_instrument: str
    source_timeframe: str
    event_direction: int
    event_observed_at: pd.Timestamp
    event_available_at: pd.Timestamp
    stop_price: float
    event_invalidated_at: pd.Timestamp | None = None
    parent_structure_id: str | None = None


@dataclass(frozen=True)
class Factor:
    event_id: str
    kind: str
    instrument: str
    timeframe: str
    direction: int
    available_at: pd.Timestamp
    expires_at: pd.Timestamp
    invalidated_at: pd.Timestamp | None = None
    underlying_event_id: str | None = None
    parent_structure_id: str | None = None

    def active_at(self, when: pd.Timestamp) -> bool:
        return (
            self.available_at <= when < self.expires_at
            and (self.invalidated_at is None or when < self.invalidated_at)
        )


@dataclass(frozen=True)
class Policy:
    policy_id: str
    required: tuple[tuple[str, tuple[str, ...]], ...] = ()
    absent: tuple[tuple[str, tuple[str, ...]], ...] = ()
    wait_minutes: int = 120
    horizon: int = 360
    horizon_unit: str = "OBSERVED_BARS"
    target_type: str = "FIXED_2R"
    require_linked_target: bool = False
    max_gap_minutes: int = 5
    slip: float = 0.25
    min_risk: float = 3.0

    def __post_init__(self):
        if self.horizon_unit not in ("OBSERVED_BARS", "CLOCK_MINUTES"):
            raise ValueError("Unknown execution horizon unit")
        if min(self.wait_minutes, self.horizon, self.max_gap_minutes, self.slip) < 0 or self.min_risk <= 0:
            raise ValueError("Invalid order policy bounds")


def factorial_policies() -> list[Policy]:
    """The CISD bit requires a standalone M1 confirmation after the sweep."""
    frames = ((), ("M90",), ("M22.5",), (), ("M1",), ())
    return [
        Policy(f"CFG64_{i:02d}", tuple((kind, tf) for bit, kind, tf in zip(bits, CORE_FACTORS, frames) if bit))
        for i, bits in enumerate(product((0, 1), repeat=6))
    ]


def cisd_policies() -> list[Policy]:
    return [
        Policy("00_No_CISD"),
        Policy("01_M1_CRT_CISD", (("CRT_CISD", ("M1",)),), wait_minutes=20),
        *[
            Policy(f"{tf}_STANDALONE_CISD", (("CISD", (tf,)),), wait_minutes=wait)
            for tf, wait in zip(("M1", "M3", "M5", "M15", "M30", "H1", "H4"), (20, 30, 45, 90, 150, 240, 480))
        ],
    ]


class FactorBook:
    """Time-indexed actual events with explicit lifetimes and source dimensions."""

    def __init__(self, events: list[Factor]):
        ids = set()
        groups: dict[tuple[str, str, str | None], list[Factor]] = {}
        for event in events:
            if event.event_id in ids:
                raise ValueError(f"Duplicate factor event: {event.event_id}")
            ids.add(event.event_id)
            groups.setdefault((event.instrument, event.kind, event.underlying_event_id), []).append(event)
        self.groups = {}
        for key, rows in groups.items():
            rows.sort(key=lambda row: (row.available_at, row.event_id))
            self.groups[key] = (
                [row.available_at for row in rows], rows,
                max(row.expires_at - row.available_at for row in rows),
            )

    def candidates(self, op, requirement, start, end) -> list[Factor]:
        kind, timeframes = requirement
        selected = []
        for scope in (None, op.underlying_event_id):
            group = self.groups.get((op.source_instrument, kind, scope))
            if group is None:
                continue
            times, rows, lifetime = group
            lo = bisect_left(times, start - lifetime)
            hi = bisect_right(times, end)
            selected.extend(
                row for row in rows[lo:hi]
                if (not timeframes or row.timeframe in timeframes)
                and (kind not in ("CISD", "CRT_CISD") or row.available_at >= op.event_observed_at)
            )
        return selected

    @staticmethod
    def evidence_at(required, time, direction):
        chosen = []
        for group in required:
            active = [row for row in group if row.active_at(time)]
            if not active or any(row.direction != direction for row in active):
                return None
            chosen.append(max(active, key=lambda row: (row.available_at, row.event_id)))
        return tuple(chosen)

    def choose(self, op, policy, end):
        start = op.event_available_at
        if end < start:
            return None
        required = [self.candidates(op, spec, start, end) for spec in policy.required]
        absent = [self.candidates(op, spec, start, start) for spec in policy.absent]
        # Absence is measured at the candidate decision, without looking at a
        # later confirmation window. A later event cannot redefine the sample.
        if any(any(x.active_at(start) and x.direction == op.event_direction for x in group) for group in absent):
            return None
        times = sorted({start} | {
            t for group in required for row in group
            for t in (row.available_at, row.expires_at, row.invalidated_at)
            if t is not None and start <= t <= end
        })
        for time in times:
            chosen = self.evidence_at(required, time, op.event_direction)
            if chosen is not None:
                return time, chosen
        return None


@dataclass(frozen=True)
class Target:
    event_id: str
    target_type: str
    timeframe: str
    price: float
    direction: int
    instrument: str
    origin_event_id: str
    source_candle_close: pd.Timestamp
    available_at: pd.Timestamp
    invalidated_at: pd.Timestamp | None = None


@njit(cache=True)
def _exit_path(opens, highs, lows, closes, fill, end, direction, stop, target, data_end):
    for j in range(fill, end + 1):
        if direction * (opens[j] - stop) <= 0:
            return 2, j, opens[j], True
        hit_stop = lows[j] <= stop if direction == 1 else highs[j] >= stop
        hit_target = highs[j] >= target if direction == 1 else lows[j] <= target
        if hit_stop:
            return (3 if hit_target else 2), j, stop, False
        if hit_target:
            return 1, j, target, False
    return (5 if data_end else 4), end, closes[end], False


class OrderEngine:
    """Plan, wait and execute against existing Bid/Ask quotes."""

    def __init__(self, panel: pd.DataFrame, instrument: str, observed_through: pd.Timestamp | None):
        idx = panel.index
        if idx.tz is None or not idx.is_unique or not idx.is_monotonic_increasing or not len(idx):
            raise ValueError("Execution requires ordered, unique timezone-aware quote timestamps")
        self.index = idx
        self.closes = idx + MINUTE
        self.instrument = instrument
        self.observed_through = observed_through
        self.bid = panel[[f"{instrument}_{x}" for x in "ohlc"]].to_numpy(dtype=float).T.copy()
        self.ask = panel[[f"{instrument}_a{x}" for x in "ohlc"]].to_numpy(dtype=float).T.copy()

    def target_consumed_at(self, target, when):
        j0 = self.index.searchsorted(target.available_at)
        j1 = self.closes.searchsorted(when, side="right")
        quotes = self.bid if target.direction == 1 else self.ask
        extreme = quotes[1 if target.direction == 1 else 2, j0:j1]
        crossed = np.flatnonzero(target.direction * (extreme - target.price) >= 0)
        return self.closes[j0 + crossed[0]] if len(crossed) else None

    def execute(self, op, policy, book, targets=()):
        idx = self.index
        direction = op.event_direction
        if op.source_instrument != self.instrument or direction not in (-1, 1):
            raise ValueError("Opportunity instrument and direction must match the quote stream")
        if op.event_observed_at > op.event_available_at:
            raise ValueError("Opportunity availability precedes its observed event")
        exit_quotes = self.bid if direction == 1 else self.ask
        entry_quotes = self.ask if direction == 1 else self.bid
        start = op.event_available_at
        deadline = start + policy.wait_minutes * MINUTE
        horizon = min(deadline, self.closes[-1])
        selected = book.choose(op, policy, horizon)
        decision, evidence = selected if selected is not None else (None, ())
        status = "WAITING_CONFIRMATION" if policy.required else "CANDIDATE"
        record = dict(
            policy_id=policy.policy_id, underlying_event_id=op.underlying_event_id,
            source_instrument=self.instrument, source_timeframe=op.source_timeframe, direction=direction,
            event_observed_at=op.event_observed_at, event_available_at=start,
            event_invalidated_at=op.event_invalidated_at, parent_structure_id=op.parent_structure_id,
            execution_status=status, lifecycle=["CANDIDATE"],
            j_confirm=-1, t_confirm_available=None, decision_at=None, order_submit_at=None,
            j_fill=-1, t_fill=None, j_exit=-1, t_exit=None, exit_bar_open=None,
            entry_price=None, stop_price=op.stop_price, target_price=None, exit_price=None,
            exit_quote=None, realized_net_r=None, factor_event_ids=[], factor_available_at=[],
            factor_types=[], factor_timeframes=[], factor_directions=[],
            target_event_id=None, target_type=policy.target_type, target_timeframe=None,
            target_source_candle_close=None, target_available_at=None, target_origin_event_id=None,
            target_invalidated_at=None, target_consumed_at=None, target_selection_at=None, known_before_entry=None,
            entry_quote_provenance=None, exit_quote_provenance=None,
            horizon_unit=policy.horizon_unit, horizon=policy.horizon,
            status_at=start, reason=None,
        )
        if policy.required:
            record["lifecycle"].append("WAITING_CONFIRMATION")

        def finish(status, reason, at):
            record["execution_status"] = status
            record["reason"] = reason
            record["status_at"] = at
            if record["lifecycle"][-1] != status:
                record["lifecycle"].append(status)
            return record

        if not np.isfinite(op.stop_price):
            return finish("CANCELLED", "INVALID_STOP", start)
        j_fill = idx.searchsorted(decision) if decision is not None else len(idx)
        wait_end = idx[j_fill] if j_fill < len(idx) else horizon
        j_wait = idx.searchsorted(start)
        wait_last = self.closes.searchsorted(wait_end, side="right")
        stop_side = exit_quotes[2 if direction == 1 else 1, j_wait:wait_last]
        hits = np.flatnonzero(direction * (stop_side - op.stop_price) <= 0)
        invalid_at = self.closes[j_wait + hits[0]] if len(hits) else None
        invalid_reason = "STRUCTURAL_STOP_WHILE_WAITING"
        if op.event_invalidated_at is not None and (invalid_at is None or op.event_invalidated_at < invalid_at):
            invalid_at = op.event_invalidated_at
            invalid_reason = "SOURCE_INVALIDATION"
        chain = idx[max(0, j_wait - 1):min(len(idx), wait_last + 1)]
        gaps = np.flatnonzero(chain[1:] - chain[:-1] > policy.max_gap_minutes * MINUTE)
        gap_at = chain[gaps[0] + 1] if len(gaps) else None
        if gap_at is not None and gap_at <= wait_end and (invalid_at is None or gap_at < invalid_at):
            return finish("CANCELLED", "GAP_WHILE_WAITING", gap_at)
        if invalid_at is not None and invalid_at <= wait_end:
            record["event_invalidated_at"] = invalid_at
            return finish("INVALIDATED_BEFORE_ENTRY", invalid_reason, invalid_at)
        if selected is None:
            final = "CANCELLED" if deadline <= self.closes[-1] else "WAITING_CONFIRMATION"
            return finish(final, "CONFIRMATION_EXPIRED" if final == "CANCELLED" else "SAMPLE_ENDED", horizon)

        j_confirm = self.closes.searchsorted(decision)
        record.update(
            j_confirm=int(j_confirm), t_confirm_available=decision,
            decision_at=decision, factor_event_ids=[x.event_id for x in evidence],
            factor_available_at=[x.available_at for x in evidence],
            factor_types=[x.kind for x in evidence],
            factor_timeframes=[x.timeframe for x in evidence],
            factor_directions=[x.direction for x in evidence],
        )
        record["lifecycle"].append("ELIGIBLE")
        if j_fill >= len(idx):
            return finish("CANCELLED", "NO_EXECUTABLE_QUOTE", decision)
        fill_at = idx[j_fill]
        if fill_at > deadline or fill_at - decision > policy.max_gap_minutes * MINUTE:
            return finish("CANCELLED", "LATE_EXECUTABLE_QUOTE", fill_at)
        if any(not factor.active_at(fill_at) for factor in evidence):
            return finish("CANCELLED", "FACTOR_EXPIRED_BEFORE_FILL", fill_at)
        if fill_at > decision:
            at_fill = [book.candidates(op, spec, fill_at, fill_at) for spec in policy.required]
            if book.evidence_at(at_fill, fill_at, direction) is None:
                return finish("CANCELLED", "FACTOR_CONFLICT_BEFORE_FILL", fill_at)
        if not np.isfinite(entry_quotes[0, j_fill]) or not np.isfinite(exit_quotes[0, j_fill]):
            return finish("CANCELLED", "MISSING_QUOTE", fill_at)
        reference_close = exit_quotes[3, self.closes.searchsorted(decision, side="right") - 1]
        if policy.target_type != "FIXED_2R":
            parent_ids = {row.parent_structure_id for row in evidence if row.parent_structure_id is not None}
            candidates = [
                target for target in targets
                if target.target_type == policy.target_type
                and target.instrument == self.instrument and target.direction == direction
                and target.source_candle_close <= target.available_at <= decision
                and (not policy.require_linked_target or target.origin_event_id in parent_ids)
                and (target.invalidated_at is None or decision < target.invalidated_at)
                and direction * (target.price - reference_close) > 0
                and self.target_consumed_at(target, decision) is None
            ]
            if not candidates:
                return finish("CANCELLED", "NO_CAUSAL_TARGET", decision)
            target = min(candidates, key=lambda t: (abs(t.price - reference_close), t.event_id))
            record.update(
                target_event_id=target.event_id, target_timeframe=target.timeframe,
                target_available_at=target.available_at, target_source_candle_close=target.source_candle_close,
                target_origin_event_id=target.origin_event_id, target_invalidated_at=target.invalidated_at,
                target_selection_at=decision, known_before_entry=target.available_at <= decision <= fill_at,
            )
            if target.invalidated_at is not None and target.invalidated_at <= fill_at:
                return finish("INVALIDATED_BEFORE_ENTRY", "TARGET_INVALIDATED", target.invalidated_at)
            consumed = self.target_consumed_at(target, fill_at)
            if consumed is not None or direction * (exit_quotes[0, j_fill] - target.price) >= 0:
                record["target_consumed_at"] = consumed if consumed is not None else fill_at
                return finish("INVALIDATED_BEFORE_ENTRY", "TARGET_CONSUMED", record["target_consumed_at"])

        entry = entry_quotes[0, j_fill] + direction * policy.slip
        risk = direction * (entry - op.stop_price)
        if direction * (exit_quotes[0, j_fill] - op.stop_price) <= 0:
            record["event_invalidated_at"] = fill_at
            return finish("INVALIDATED_BEFORE_ENTRY", "GAP_THROUGH_ENTRY_STOP", fill_at)
        if not np.isfinite(risk) or risk < policy.min_risk:
            return finish("CANCELLED", "WRONG_SIDE_OR_INSUFFICIENT_RISK", fill_at)
        take_profit = entry + direction * 2 * risk if policy.target_type == "FIXED_2R" else target.price
        if direction * (take_profit - entry) <= 0:
            return finish("CANCELLED", "TARGET_WRONG_SIDE_AT_FILL", fill_at)

        record["lifecycle"].extend(("SUBMITTED", "FILLED"))
        record.update(
            order_submit_at=decision, j_fill=int(j_fill), t_fill=fill_at,
            entry_price=float(entry), target_price=float(take_profit),
            entry_quote_provenance=self._provenance(fill_at),
        )
        if policy.horizon_unit == "CLOCK_MINUTES":
            deadline_exit = fill_at + max(1, policy.horizon) * MINUTE
            end = self.closes.searchsorted(deadline_exit, side="right") - 1
            data_end = deadline_exit > self.closes[-1]
        else:
            desired_end = j_fill + policy.horizon
            end = min(desired_end, len(idx) - 1)
            data_end = desired_end > end
        code, j_exit, exit_quote, at_open = _exit_path(
            *exit_quotes, j_fill, end, direction, op.stop_price, take_profit, data_end,
        )
        out = exit_quote - direction * policy.slip
        exit_at = idx[j_exit] if at_open else self.closes[j_exit]
        record.update(
            j_exit=int(j_exit), t_exit=exit_at, exit_bar_open=idx[j_exit],
            exit_quote=float(exit_quote), exit_price=float(out),
            realized_net_r=float(direction * (out - entry) / risk),
            exit_quote_provenance=self._provenance(idx[j_exit]),
        )
        return finish(("TARGET_HIT", "STOP_HIT", "AMBIGUOUS", "TIMEOUT", "DATA_END")[code - 1], None, exit_at)

    def _provenance(self, when):
        if self.observed_through is not None and when <= self.observed_through:
            return "OBSERVED_BID_ASK"
        return "MODELED_ASK"
