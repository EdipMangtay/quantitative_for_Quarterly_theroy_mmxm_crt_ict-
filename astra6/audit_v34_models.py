"""Compute model evidence from an explicit corrected ledger.

The published V3.4 JSON and Parquet are immutable comparison evidence.
"""

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from astra6 import stats
from astra6.engine_v3 import _fast_cell_metrics


MODEL_IDS = (
    "MODEL_1_H1_M5_M15_LIQ", "MODEL_2_H1_REV_M5_OC", "MODEL_3_NY_OPEN_CFG64_57",
    "MODEL_4_STAGE_13", "MODEL_4_STAGE_11_12", "MODEL_4_ACTIVE_TARGET_UNIVERSE",
)


def compute_model_metrics(
    df: pd.DataFrame,
    model_id: str,
    model_name: str,
    hypothesis: str,
    target_type: str,
    entry_rule: str,
    stop_rule: str,
    target_rule: str,
    min_trades_threshold: int = 30,
) -> dict[str, Any]:
    """Compute statistics without substituting a return for an unfilled order."""
    work = df.copy()
    r = "realized_net_r" if "realized_net_r" in work else "r"
    work = work[np.isfinite(work[r])] if r in work else work.iloc[:0]
    if "j_fill" in work:
        work = work[work["j_fill"] >= 0]
    if not work.empty:
        work["r"] = work[r]
    metrics = _fast_cell_metrics(work)
    required = {"event_available_at", "decision_at", "order_submit_at", "t_fill", "j_fill", "j_exit", "target_type"}
    causal = False
    if not work.empty and required.issubset(work):
        coherent = (
            (work["event_available_at"] <= work["decision_at"])
            & (work["decision_at"] <= work["order_submit_at"])
            & (work["order_submit_at"] <= work["t_fill"])
            & (work["j_exit"] >= work["j_fill"])
        )
        structural = work[work["target_type"] != "FIXED_2R"]
        targets_verified = structural.empty or (
            {"target_event_id", "target_available_at"}.issubset(structural)
            and structural["target_event_id"].notna().all()
            and (structural["target_available_at"] <= structural["decision_at"]).all()
        )
        causal = bool(coherent.all() and targets_verified)

    if metrics["n_trades"] < min_trades_threshold or metrics["n_unique_days"] < 15 or metrics["n_unique_events"] < min_trades_threshold:
        status = "INSUFFICIENT_DATA"
    elif not causal:
        status = "NOT_VERIFIED"
    elif metrics["expectancy_r"] <= 0:
        status = "NEGATIVE_EXPECTANCY"
    else:
        status = "EXPLORATORY_POSITIVE"

    return dict(
        model_id=model_id, model_name=model_name, hypothesis=hypothesis, target_type=target_type,
        entry_rule=entry_rule, stop_rule=stop_rule, target_rule=target_rule,
        **metrics, causal_eligibility_checked=causal, validation_status=status,
        verdict=status,
    )


def run_audit(ledger_path: Path | None = None, *, historical_gate_passed: bool = False):
    """Use explicit model IDs. Timing probes and legacy outcomes cannot qualify."""
    source = None if ledger_path is None else Path(ledger_path)
    ledger = pd.read_parquet(source) if source is not None and source.is_file() else pd.DataFrame()
    rows = []
    for model_id in MODEL_IDS:
        subset = ledger[ledger["model_id"] == model_id] if "model_id" in ledger else ledger.iloc[:0]
        target_type = subset["target_type"].iloc[0] if "target_type" in subset and len(subset) else "UNAVAILABLE"
        row = compute_model_metrics(subset, model_id, model_id, "", target_type, "", "", "")
        rows.append(row)
    adjusted = stats.adjust_pvalues([row["p_gt_zero"] if row["n_trades"] else np.nan for row in rows])
    for i, row in enumerate(rows):
        row["p_holm"] = adjusted.iloc[i]["p_holm"]
        row["p_bh_fdr"] = adjusted.iloc[i]["p_bh_fdr"]
        row["selection_history"] = "PREVIOUSLY_EXPLORED_HISTORICAL_DATA"
        if not historical_gate_passed or ledger.empty:
            row["validation_status"] = "NOT_VERIFIED"
            row["verdict"] = "NOT_VERIFIED"
        elif (
            row["validation_status"] == "EXPLORATORY_POSITIVE"
            and row["ci95_low"] > 0 and row["p_holm"] <= 0.05
            and row["oos_n_trades"] >= 15 and row["oos_expectancy_r"] > 0
        ):
            row["validation_status"] = "HISTORICAL_EVIDENCE_POSITIVE"
            row["verdict"] = row["validation_status"]
    return pd.DataFrame(rows), {
        "audit_version": "ASTRA_6_V3.5",
        "source": str(source) if source else None,
        "historical_gate_passed": historical_gate_passed,
        "models": rows,
    }


if __name__ == "__main__":
    table, _ = run_audit()
    print(table[["model_id", "n_trades", "validation_status"]].to_string(index=False))
