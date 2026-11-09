"""Evidence checks for named narratives. Historical V3.4 reports are read-only."""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class NarrativeEvent:
    event_id: str
    kind: str
    instrument: str
    timeframe: str
    direction: int
    observed_at: pd.Timestamp
    available_at: pd.Timestamp
    parent_event_id: str | None = None
    invalidated_at: pd.Timestamp | None = None


NARRATIVES = {
    "M5_MMBM_TO_H1_BSL": (
        ("MMXM_REVERSAL", ("M5",), 1),
        ("CISD", ("M1", "M5"), 1),
        ("BSL_TARGET", ("H1",), 1),
    ),
    "H1_SSL_TO_M5_OC": (
        ("SSL_SWEEP", ("H1",), 1),
        ("STRUCTURAL_REVERSAL", ("H1",), 1),
        ("MMXM_REVERSAL", ("M5",), 1),
        ("CISD", ("M15",), 1),
        ("OC_TARGET", ("M5",), 1),
    ),
    "H4_BEARISH_TO_D1_SSL": (
        ("STRUCTURAL_BIAS", ("H4",), -1),
        ("CORRECTION", ("M15",), 1),
        ("CISD", ("M5",), -1),
        ("SSL_TARGET", ("D1",), -1),
    ),
}


def verify_narrative(narrative_id, events, instrument, decision_at):
    """Verify a supplied chain of event identities and explicit parent edges.

    The final target is a pre-existing event selected at decision. Its source
    may predate the setup, so it need not follow the trigger in event time.
    """
    specification = NARRATIVES[narrative_id]
    if len(events) != len(specification) or len({event.event_id for event in events}) != len(events):
        return False
    previous = None
    for i, (event, (kind, timeframes, direction)) in enumerate(zip(events, specification)):
        if (
            not event.event_id or event.kind != kind or event.instrument != instrument
            or event.timeframe not in timeframes or event.direction != direction
            or not event.observed_at <= event.available_at <= decision_at
            or (event.invalidated_at is not None and event.invalidated_at <= decision_at)
        ):
            return False
        if previous is not None:
            if event.parent_event_id != previous.event_id:
                return False
            if i < len(events) - 1 and event.available_at < previous.available_at:
                return False
        previous = event
    return True


def run_narrative_validation(evidence=()):
    """Evaluate supplied event chains; never infer narratives from old trade masks."""
    rows = []
    for name in NARRATIVES:
        matching = [row for row in evidence if row["narrative_id"] == name]
        passed = sum(verify_narrative(name, row["events"], row["instrument"], row["decision_at"]) for row in matching)
        rows.append({
            "narrative_id": name,
            "supplied_chains": len(matching),
            "verified_chains": passed,
            "validation_status": "EVENT_SEQUENCE_SUPPORTED" if passed else "NOT_VERIFIED",
        })
    return pd.DataFrame(rows), {"narratives": rows}


if __name__ == "__main__":
    table, _ = run_narrative_validation()
    print(table.to_string(index=False))
