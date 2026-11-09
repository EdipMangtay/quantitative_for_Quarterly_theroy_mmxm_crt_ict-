"""V3.5 research entry point. V3.4 stores and reports are immutable inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from . import bars, fractal_v3, signals, smt
from .hpc import compute_config_hash
from .execution_v35 import (
    MINUTE, Factor, FactorBook, Opportunity, OrderEngine, Policy, Target,
    cisd_policies, factorial_policies,
)


OUTPUT = Path(__file__).resolve().parents[1] / "data" / "results" / "v3_5"
OPPORTUNITY_TFS = ("M3", "M5", "M15", "M30", "H1", "H4", "D1", "W1")
CISD_AGE = {"M1": 30, "M3": 45, "M5": 60, "M15": 120, "M30": 240, "H1": 360, "H4": 960}


def build_opportunities(ctx, timeframes=OPPORTUNITY_TFS, anchors=("cal",)):
    """Observe sweeps and reclaims without requiring later CRT or CISD."""
    panel = ctx["panel"]
    inst = ctx["traded"]
    idx = panel.index
    closes = idx + MINUTE
    highs = panel[f"{inst}_h"].to_numpy()
    lows = panel[f"{inst}_l"].to_numpy()
    opportunities = {}
    scoped = {}

    for tf in timeframes:
        for anchor in anchors:
            rows = signals.extract_crt_events(ctx, tf, anchor, include_developing=True)
            for row in rows.itertuples(index=False):
                sw, reclaim, direction = row.j_sweep, row.j_reclaim, row.dir
                if sw < 0 or reclaim < sw or (0 <= row.j_other <= reclaim):
                    continue
                uid = f"UEV_{inst}_{tf}_{row.j_open}_{'L' if direction == 1 else 'S'}"
                observed, available = closes[sw], closes[reclaim]
                if np.any(idx[sw + 1:reclaim + 1] - idx[sw:reclaim] > 5 * MINUTE):
                    continue
                if direction == 1:
                    stop = float(lows[sw:reclaim + 1].min() - 1.5)
                else:
                    stop = float(highs[sw:reclaim + 1].max() + 1.5)
                invalid = closes[row.j_other] if row.j_other >= 0 else None
                parent = f"CANDLE:{inst}:{tf}:{row.reference_bucket_start.isoformat()}"
                op = Opportunity(uid, inst, tf, direction, observed, available, stop, invalid, parent)
                previous = opportunities.setdefault(uid, op)
                if previous != op:
                    # An alternative candle anchor may share a first raw row
                    # while defining a genuinely different source candle.
                    uid = f"{uid}_{anchor}"
                    op = Opportunity(uid, inst, tf, direction, observed, available, stop, invalid, parent)
                    opportunities[uid] = op

                def scoped_factor(kind, source_tf, when, expiry, invalidated=None):
                    event_id = f"{kind}:{uid}:{when.isoformat()}"
                    scoped[event_id] = Factor(
                        event_id, kind, inst, source_tf, direction, when, expiry,
                        invalidated, uid,
                    )

                if row.A and row.is_complete and row.reference_coverage_status == "FULL":
                    scoped_factor("CRT", tf, row.available_at, row.available_at + 120 * MINUTE)
                if row.j_cisd >= sw:
                    when = closes[row.j_cisd]
                    scoped_factor("CRT_CISD", "M1", when, when + 20 * MINUTE)
                if row.reference_coverage_status == "FULL" and ctx["comps"] and (row.j_cmp0 < 0 or row.j_cmp0 > sw):
                    cmp_invalidation = closes[row.j_cmp0] if row.j_cmp0 >= 0 else None
                    scoped_factor(
                        "STD_SMT", tf, observed, row.scheduled_bucket_end + 15 * MINUTE,
                        cmp_invalidation,
                    )
    return list(opportunities.values()), list(scoped.values())


def context_factors(ctx, mmxm, micro_panel=None):
    idx = ctx["panel"].index
    inst = ctx["traded"]
    events = []
    for tf, table in ctx["cisd_tables"].items():
        for row in table.itertuples(index=False):
            if row.data_coverage_status != "FULL":
                continue
            invalidated = row.invalidated_at if pd.notna(row.invalidated_at) else None
            when = row.available_at
            events.append(Factor(
                f"CISD:{inst}:{tf}:{when.isoformat()}:{row.dir}", "CISD", inst, tf, row.dir,
                when, when + CISD_AGE[tf] * MINUTE, invalidated,
            ))

    streams = [(ctx["ssmt_mac"], idx, MINUTE, "MACRO_SSMT", "M90", 180)]
    if micro_panel is not None and not micro_panel.empty:
        q = bars.quarter_labels(micro_panel.index, ctx["qt_anchor"])
        micro = smt.ssmt_events(micro_panel, q, inst, "US500", "micro")
        streams.append((micro, micro_panel.index, MINUTE / 2, "MICRO_SSMT", "M22.5", 45))
    for table, timestamps, width, kind, tf, maximum_age in streams:
        for row in table.itertuples(index=False):
            when = timestamps[row.j_form] + width
            invalidated = timestamps[row.j_inv] + width if row.j_inv >= 0 else None
            event_id = f"{kind}:{inst}:{row.inst_pair}:{row.b_ref}:{row.b_trig}:{row.dir}:{row.lead}:{when.isoformat()}"
            events.append(Factor(event_id, kind, inst, tf, row.dir, when, when + maximum_age * MINUTE, invalidated))

    if not mmxm.empty:
        ordered = mmxm.sort_values(["j_m1_known", "stage_num", "mmxm_id"])
        next_update = ordered.groupby(["tf", "mmxm_id"], sort=False)["available_at"].shift(-1)
        for row in ordered.assign(next_update=next_update).itertuples(index=False):
            if not row.is_active or not 4 <= row.stage_num <= 12:
                continue
            when = row.available_at
            expires = when + 1440 * MINUTE
            if pd.notna(row.next_update):
                expires = min(expires, row.next_update)
            if expires > when:
                events.append(Factor(
                    row.mmxm_event_id, "MMXM", inst, row.tf, row.direction, when, expires,
                    parent_structure_id=row.oc_id,
                ))
    return events


def load_micro_panel(start, end):
    """Load the already stored 30-second quotes within an analysis interval."""
    parts = []
    for instrument in ("US100", "US500"):
        source = bars.STORE / f"DUKA_{instrument}_30S.parquet"
        part = pd.read_parquet(
            source, columns=["ts", "high", "low"],
            filters=[("ts", ">=", start), ("ts", "<", end)],
        ).set_index("ts").rename(columns={"high": f"{instrument}_h", "low": f"{instrument}_l"})
        parts.append(part)
    return pd.concat(parts, axis=1, join="inner").sort_index()


def build_targets(panel, instrument, oc):
    """Return recorded prior liquidity and OC levels with immutable origins."""
    targets = []
    for tf in ("M15", "H1", "H4", "D1", "W1"):
        tf_bars = bars.resample(panel, instrument, tf)
        for row in tf_bars[tf_bars["is_complete"]].itertuples(index=False):
            origin = f"CANDLE:{instrument}:{tf}:{row.bucket_start.isoformat()}"
            for direction, price in ((1, row.h), (-1, row.l)):
                targets.append(Target(
                    f"LIQ:{origin}:{direction}", f"{tf}_LIQ", tf, price, direction,
                    instrument, origin, row.scheduled_bucket_end, row.available_at,
                ))
    if not oc.empty:
        invalidated = oc[oc["event_kind"] == "INVALIDATED"].set_index("oc_id")["available_at"]
        confirmed = oc[(oc["event_kind"] == "CONFIRMED") & (oc["data_coverage_status"] == "FULL")]
        for row in confirmed.itertuples(index=False):
            targets.append(Target(
                f"TARGET:{row.oc_id}", f"{row.tf}_OC", row.tf, row.midpoint, int(row.target_dir),
                instrument, row.oc_id, row.t_confirm, row.available_at, invalidated.get(row.oc_id),
            ))
    return targets


def model_timing_probe(direction):
    if direction == 1:
        return Policy(
            "P0_MODEL1_TIMING_PROBE", (("CISD", ("M5",)),), horizon=60,
            horizon_unit="CLOCK_MINUTES", target_type="M15_LIQ",
        )
    return Policy(
        "P0_MODEL2_TIMING_PROBE", (("CRT", ("H1",)), ("CISD", ("M15",)), ("MMXM", ("M5",))),
        horizon=120, target_type="M5_OC", require_linked_target=True,
    )


def run_sample(observations=1300):
    if not 100 <= observations <= 50_000:
        raise ValueError("The V3.5 sample gate accepts 100 to 50,000 observations")
    panel = bars.load_panel().iloc[:observations]
    ctx = signals.build_context(panel)
    oc = fractal_v3.extract_original_consolidations(
        panel, timeframes=("M5", "M15", "M30", "H1", "H4", "D1"), include_lifecycle=True,
    )
    mmxm = fractal_v3.build_fractal_mmxm_state_events(panel, oc)
    opportunities, scoped = build_opportunities(ctx)
    micro = load_micro_panel(panel.index[0], panel.index[-1] + MINUTE)
    book = FactorBook(scoped + context_factors(ctx, mmxm, micro))
    cutoff = pd.read_parquet(bars.STORE / "DUKA_US100_M1.parquet", columns=["ts"])["ts"].max()
    executor = OrderEngine(panel, ctx["traded"], cutoff)
    targets = build_targets(panel, ctx["traded"], oc)
    policies = factorial_policies() + cisd_policies()
    ledger = [executor.execute(op, policy, book) for op in opportunities for policy in policies]
    for op in opportunities:
        if op.source_timeframe == "H1":
            ledger.append(executor.execute(op, model_timing_probe(op.event_direction), book, targets))
    result = pd.DataFrame(ledger)
    executed = result[result["j_fill"] >= 0]
    if not ((executed["event_available_at"] <= executed["decision_at"])
            & (executed["decision_at"] <= executed["order_submit_at"])
            & (executed["order_submit_at"] <= executed["t_fill"])
            & (executed["j_exit"] >= executed["j_fill"])).all():
        raise ValueError("Invalid executed ledger chronology")
    if not executed.loc[executed["target_type"] != "FIXED_2R", "known_before_entry"].eq(True).all():
        raise ValueError("Executed structural order has no causal target")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="ASTRA 6 V3.5 recorded-quote behavioral sample")
    parser.add_argument("--observations", type=int, default=1300)
    args = parser.parse_args(argv)
    ledger = run_sample(args.observations)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT / f"sample_{args.observations}_ledger.parquet"
    scratch = path.with_suffix(".tmp")
    ledger.to_parquet(scratch, index=False)
    scratch.replace(path)
    root = OUTPUT.parents[2]
    input_names = [
        f"{instrument}_{side}_M1.parquet"
        for instrument in ("US100", "US500", "US30") for side in ("BID", "ASK")
    ] + ["DUKA_US100_M1.parquet", "DUKA_US100_30S.parquet", "DUKA_US500_30S.parquet"]

    def file_hash(file):
        with file.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()

    config = {
        "observations": args.observations, "opportunity_timeframes": OPPORTUNITY_TFS,
        "policies": [asdict(x) for x in factorial_policies() + cisd_policies()
                     + [model_timing_probe(1), model_timing_probe(-1)]],
    }
    source_files = sorted((root / "astra6").rglob("*.py"))
    manifest = {
        "scope": "BEHAVIORAL_SAMPLE", "status": "NOT_VERIFIED",
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
        "algo_version": fractal_v3.ALGO_VERSION, "config": config,
        "config_sha256": compute_config_hash(config),
        "inputs_sha256": {name: file_hash(bars.STORE / name) for name in input_names},
        "source_files_sha256": {str(file.relative_to(root)): file_hash(file) for file in source_files},
        "outputs_sha256": {path.name: file_hash(path)},
        "producer": "astra6.research_v35.run_sample",
        "command": shlex.join([sys.executable, *sys.orig_argv[1:]]),
    }
    manifest["run_id"] = compute_config_hash(manifest)
    path.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(ledger["execution_status"].value_counts().to_string())
    print(f"sample rows={len(ledger)} policies={ledger['policy_id'].nunique()} output={path}")


if __name__ == "__main__":
    main()
