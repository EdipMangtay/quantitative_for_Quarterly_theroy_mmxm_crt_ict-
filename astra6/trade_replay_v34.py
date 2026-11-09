"""Render genuine recorded-quote replays from the V3.5 order ledger.

The V3.4 replay JSON, illustrations and reports stay in their original paths.
"""

from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path

import pandas as pd

from astra6 import bars
from astra6.execution_v35 import MINUTE
from astra6.research_v35 import OUTPUT


ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "reports" / "figures" / "v35_replays"


def generate_svg_chart(replay, quotes):
    """Render only OHLC from the recorded exit-side quote stream."""
    width, height = 900, 390
    left, right, top, bottom = 72, 768, 54, 320
    side = "" if replay["direction"] == 1 else "a"
    price = quotes[[f"US100_{side}{part}" for part in "ohlc"]]
    levels = [
        (label, replay[key], color) for label, key, color in (
            ("Giriş", "entry_price", "#2563eb"), ("Stop", "stop_price", "#be123c"),
            ("Hedef", "target_price", "#047857"), ("Çıkış", "exit_price", "#7c3aed"),
        ) if replay.get(key) is not None
    ]
    low = min(price.min().min(), *(value for _, value, _ in levels))
    high = max(price.max().max(), *(value for _, value, _ in levels))
    span = max(high - low, 1e-6)
    first, last = quotes.index[[0, -1]]
    seconds = max((last - first).total_seconds(), 60)
    candle_width = max(1, min(10, (right - left) * 40 / seconds))

    def x(t):
        return left + (right - left) * (t - first).total_seconds() / seconds

    def y(value):
        return bottom - (bottom - top) * (value - low) / span

    title = escape(f'{replay["underlying_event_id"]} · {replay["policy_id"]}')
    quote_name = "Bid" if not side else "Ask"
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="{title}">',
        '<rect width="900" height="390" fill="white"/>',
        '<g font-family="Arial, sans-serif" font-size="12" fill="#172033">',
        f'<text x="24" y="24" font-size="16" font-weight="bold">{title}</text>',
        f'<text x="24" y="43">{quote_name} M1 · Kayıtlı OHLC · {escape(replay["execution_status"])}</text>',
    ]
    for t, ohlc in zip(quotes.index, price.itertuples(index=False, name=None)):
        o, h, lo, c = ohlc
        loc = x(t)
        color = "#047857" if c >= o else "#be123c"
        svg.append(f'<line x1="{loc:.2f}" x2="{loc:.2f}" y1="{y(h):.2f}" y2="{y(lo):.2f}" stroke="{color}"/>')
        svg.append(
            f'<rect x="{loc - candle_width / 2:.2f}" y="{min(y(o), y(c)):.2f}" '
            f'width="{candle_width:.2f}" height="{max(1, abs(y(c) - y(o))):.2f}" fill="{color}"/>'
        )
    for label, value, color in levels:
        cy = y(value)
        svg.append(f'<line x1="{left}" x2="{right}" y1="{cy:.2f}" y2="{cy:.2f}" stroke="{color}" stroke-dasharray="4 3"/>')
    for i, (label, value, color) in enumerate(levels):
        svg.append(f'<text x="{right + 12}" y="{top + 20 * i}" fill="{color}">{label} {value:.2f}</text>')
    for value in (first, first + (last - first) / 2, last):
        svg.append(f'<text text-anchor="middle" x="{x(value):.2f}" y="343">{value:%d.%m %H:%M} UTC</text>')
    markers = [("Süpürme", replay["event_observed_at"]), ("Dolum", replay["t_fill"]), ("Çıkış barı", replay["exit_bar_open"])]
    markers += [(f"{kind} {tf}", when) for kind, tf, when in zip(
        replay["factor_types"], replay["factor_timeframes"], replay["factor_available_at"],
    )]
    if replay["target_available_at"]:
        markers.append(("Yapısal hedef bilinebilir", replay["target_available_at"]))
    for label, time in markers:
        if time is None:
            continue
        time = pd.Timestamp(time)
        if first <= time <= last:
            pos = x(time)
            svg.append(f'<line x1="{pos:.2f}" x2="{pos:.2f}" y1="{top}" y2="{bottom}" stroke="#64748b" stroke-dasharray="2 5"><title>{escape(label)} {time.isoformat()}</title></line>')
    svg += ['<text x="24" y="371">Bar içindeki kesin temas sırası OHLC çözünürlüğünde gözlenmez.</text>', '</g></svg>']
    return "\n".join(svg)


def build_trade_replays(ledger_path=OUTPUT / "sample_1300_ledger.parquet"):
    """Select 20 distinct executed events and write consistent JSON and SVGs."""
    trades = pd.read_parquet(ledger_path)
    executed = trades[trades["j_fill"] >= 0]
    focus = executed[
        (executed["underlying_event_id"] == "UEV_US100_M5_884_S") & (executed["policy_id"] == "00_No_CISD")
    ]
    eligible = executed[executed["policy_id"] == "CFG64_00"].sort_values(["j_fill", "underlying_event_id"])
    ranked = pd.concat([
        focus,
        eligible[eligible.execution_status == "TARGET_HIT"].head(6),
        eligible[eligible.execution_status == "STOP_HIT"].head(6),
        eligible[eligible.execution_status.isin(["TIMEOUT", "AMBIGUOUS", "DATA_END"])].head(7),
        eligible,
    ]).drop_duplicates("underlying_event_id").head(20)
    panel = bars.load_panel()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    replays = []
    for number, row in enumerate(ranked.itertuples(index=False), 1):
        if panel.index[row.j_fill] != row.t_fill or panel.index[row.j_exit] != row.exit_bar_open:
            raise ValueError("Replay index does not match recorded quotes")
        start = max(0, min(row.j_fill, panel.index.searchsorted(row.event_observed_at)) - 8)
        # Scope the chart to the exact window observed by this research sample.
        quotes = panel.iloc[start:row.j_exit + 1]
        record = {
            key: getattr(row, key) for key in (
                "underlying_event_id", "policy_id", "direction", "j_confirm", "j_fill", "j_exit",
                "entry_price", "stop_price", "target_price", "exit_price", "realized_net_r",
                "execution_status", "target_event_id", "factor_event_ids", "factor_types", "factor_timeframes",
                "entry_quote_provenance", "exit_quote_provenance", "parent_structure_id",
            )
        }
        for key in ("factor_event_ids", "factor_types", "factor_timeframes"):
            record[key] = list(record[key])
        for key in ("event_observed_at", "t_confirm_available", "t_fill", "t_exit", "exit_bar_open", "target_available_at"):
            timestamp = getattr(row, key)
            record[key] = timestamp.isoformat() if pd.notna(timestamp) else None
        record["factor_available_at"] = [pd.Timestamp(t).isoformat() for t in row.factor_available_at]
        record.update(
            replay_id=number, quote_start=quotes.index[0].isoformat(),
            quote_end=quotes.index[-1].isoformat(), n_recorded_bars=len(quotes),
            chart=f"figures/v35_replays/replay_{number:02d}.svg",
        )
        (ROOT / "reports" / record["chart"]).write_text(generate_svg_chart(record, quotes))
        replays.append(record)
    (OUTPUT / "sample_trade_replays.json").write_text(json.dumps(replays, ensure_ascii=False, indent=2) + "\n")
    return replays


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render recorded V3.5 behavioral replays")
    parser.add_argument("--ledger", type=Path, default=OUTPUT / "sample_1300_ledger.parquet")
    args = parser.parse_args()
    print(f"recorded quote replays={len(build_trade_replays(args.ledger))}")
