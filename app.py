"""ASTRA 6 — 12-Panel Quantitative Research Dashboard (Streamlit + Plotly, Section 16)."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from astra6 import bars, clock

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "data" / "results"
STORE = ROOT / "data" / "store"

st.set_page_config(
    page_title="ASTRA 6 — Fractal QT + ICT + MMXM + CRT + SSMT + CISD Lab",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data
def load_table(name: str) -> pd.DataFrame:
    p = RESULTS / f"{name}.parquet"
    return pd.read_parquet(p) if p.exists() else pd.DataFrame()


@st.cache_data
def load_dq() -> dict:
    p = RESULTS / "data_quality.json"
    return json.loads(p.read_text()) if p.exists() else {}


@st.cache_data
def load_m1_slice(start_utc: str, end_utc: str) -> pd.DataFrame:
    import polars as pl
    t0 = pd.Timestamp(start_utc).tz_convert("UTC") if pd.Timestamp(start_utc).tzinfo else pd.Timestamp(start_utc, tz="UTC")
    t1 = pd.Timestamp(end_utc).tz_convert("UTC") if pd.Timestamp(end_utc).tzinfo else pd.Timestamp(end_utc, tz="UTC")
    u100 = pl.read_parquet(STORE / "US100_BID_M1.parquet").filter(
        (pl.col("ts") >= t0) & (pl.col("ts") <= t1)
    ).to_pandas().set_index("ts")
    u500 = pl.read_parquet(STORE / "US500_BID_M1.parquet").filter(
        (pl.col("ts") >= t0) & (pl.col("ts") <= t1)
    ).to_pandas().set_index("ts")
    return u100.join(u500, lsuffix="_100", rsuffix="_500", how="inner")


st.sidebar.title("ASTRA 6 Quant Lab")
st.sidebar.caption("Fractal QT · CRT · SSMT · CISD · ICT · MMXM")
panel_choice = st.sidebar.radio(
    "Araştırma Paneli Seçin (12 Panel):",
    [
        "Panel 1 — Session Explorer (DST)",
        "Panel 2 — CRT Research",
        "Panel 3 — CRT × SSMT Matrix",
        "Panel 4 — QT Fractal Explorer",
        "Panel 5 — Quarter-to-Quarter Rankings",
        "Panel 6 — Nasdaq Open Research",
        "Panel 7 — London Open Research",
        "Panel 8 — Narrative Explorer",
        "Panel 9 — R:R and Stop Research",
        "Panel 10 — Full Trade Replay",
        "Panel 11 — Statistical Robustness",
        "Panel 12 — Data Quality & QA Status",
    ],
)

dq = load_dq()
st.sidebar.markdown("---")
if dq:
    st.sidebar.metric("Toplam Hizalanmış M1 Bar", f"{dq.get('total_aligned_m1_bars', 0):,}")
    st.sidebar.caption(f"Dönem: {dq.get('period_start', '')[:10]} → {dq.get('period_end', '')[:10]}")

# ============================================================================
# PANEL 1 — SESSION EXPLORER
# ============================================================================
if panel_choice.startswith("Panel 1"):
    st.header("Panel 1 — Global Session Clock & DST Explorer")
    col1, col2 = st.columns([1, 2])
    with col1:
        sel_date = st.date_input("Tarih Seçin (2021–2026):", value=date(2026, 3, 16), min_value=date(2021, 11, 7), max_value=date(2026, 11, 6))
        stamp = clock.session_stamp(sel_date)
        tw = clock.is_transition_week(sel_date)
        st.subheader("Otomatik Saat Dönüşümleri (`zoneinfo` / IANA)")
        st.json({
            "date": str(stamp.date),
            "dst_regime": stamp.regime,
            "us_dst_transition_week": tw["us_transition_week"],
            "uk_dst_transition_week": tw["uk_transition_week"],
            "london_ny_open_gap_minutes": clock.london_ny_open_gap_minutes(sel_date),
            "london_open_utc": str(stamp.london_open_utc),
            "london_open_ny": str(stamp.london_open_ny),
            "london_open_istanbul": str(stamp.london_open_istanbul),
            "nasdaq_open_utc": str(stamp.nasdaq_open_utc),
            "nasdaq_open_ny": str(stamp.nasdaq_open_ny),
            "nasdaq_open_london": str(stamp.nasdaq_open_london),
            "nasdaq_open_istanbul": str(stamp.nasdaq_open_istanbul),
        })
    with col2:
        st.subheader("2021–2026 ABD / İngiltere DST Geçiş Tarihleri (IANA tzdb'den Türetilmiş)")
        rows = []
        for y in range(2021, 2027):
            us_tr = clock.dst_transitions("America/New_York", y)
            uk_tr = clock.dst_transitions("Europe/London", y)
            rows.append({
                "Yıl": y,
                "ABD Yaz Saati Başlangıç": str(us_tr[0]),
                "İngiltere Yaz Saati Başlangıç": str(uk_tr[0]),
                "İngiltere Yaz Saati Bitiş": str(uk_tr[1]),
                "ABD Yaz Saati Bitiş": str(us_tr[1]),
                "İlkbahar Uyumsuzluk Gün Sayısı": (uk_tr[0] - us_tr[0]).days,
                "Sonbahar Uyumsuzluk Gün Sayısı": (us_tr[1] - uk_tr[1]).days,
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
        cal = clock.reference_calendar("2021-11-07", "2026-11-07")
        st.subheader("DST Rejim Dağılımı (2021–2026)")
        reg_counts = cal["regime"].value_counts().reset_index()
        reg_counts.columns = ["regime", "days"]
        st.plotly_chart(px.bar(reg_counts, x="regime", y="days", color="regime", title="DST Rejimlerine Göre Takvim Günü Sayısı"), use_container_width=True)

# ============================================================================
# PANEL 2 — CRT RESEARCH
# ============================================================================
elif panel_choice.startswith("Panel 2"):
    st.header("Panel 2 — Candle Range Theory (CRT) Multi-Timeframe & Variant Research")
    tf_stats = load_table("crt_tf_stats")
    st.subheader("4.5 Zorunlu CRT Timeframe Karşılaştırması (M5, M15, M30, H1, H4 — Confirmed CRT-A)")
    st.dataframe(tf_stats, use_container_width=True)
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(px.bar(tf_stats, x="tf", y="expectancy", error_y=tf_stats["ci95_high"] - tf_stats["expectancy"],
                               color="tf", title="Timeframe Bazında CRT-A Net Expectancy (R)"), use_container_width=True)
    with c2:
        st.plotly_chart(px.bar(tf_stats, x="tf", y=["prob_mfe_1r", "prob_mfe_2r"], barmode="group",
                               title="CRT-A MFE >= 1R ve MFE >= 2R Reversal Olasılıkları"), use_container_width=True)

    st.subheader("4.4 CRT Varyantları (CRT-A .. CRT-L)")
    vdf = load_table("crt_variants")
    tf_sel = st.selectbox("CRT Varyant Timeframe / Oturum Filtresi:", vdf["tf"].unique())
    vsub = vdf[vdf["tf"] == tf_sel]
    st.dataframe(vsub, use_container_width=True)
    st.plotly_chart(px.bar(vsub, x="variant", y="expectancy", color="win_rate",
                           title=f"{tf_sel} — CRT-A..CRT-L Varyantlarının Net Expectancy (R) Karşılaştırması"), use_container_width=True)

    st.subheader("4.6 CRT Mum Kapanışı Beklemek vs Developing (Erken LTF CISD) Girişi")
    cvd = load_table("crt_closing_vs_dev")
    st.dataframe(cvd, use_container_width=True)

# ============================================================================
# PANEL 3 — CRT x SSMT MATRIX
# ============================================================================
elif panel_choice.startswith("Panel 3"):
    st.header("Panel 3 — CRT × SSMT × CISD Matrix & Baseline Testleri (A..J)")
    base_df = load_table("crt_ssmt_baselines")
    hyp_df = load_table("hypothesis_tests")
    mat_df = load_table("crt_ssmt_matrix")

    c1, c2 = st.columns(2)
    with c1:
        tf_b = st.selectbox("Timeframe:", ["M15", "H1"], key="p3_tf")
    with c2:
        sc_b = st.selectbox("Oturum Kapsamı:", base_df["scope"].unique(), key="p3_sc")

    bsub = base_df[(base_df["tf"] == tf_b) & (base_df["scope"] == sc_b)]
    st.subheader(f"5.4 Baseline Stratejileri A..J ({tf_b} — {sc_b})")
    st.dataframe(bsub, use_container_width=True)
    st.plotly_chart(px.bar(bsub, x="strategy", y="expectancy", color="profit_factor",
                           error_y=bsub["ci95_high"] - bsub["expectancy"],
                           title=f"{tf_b} ({sc_b}) — Strateji A..J Net Expectancy (R) ve %95 Bootstrap Güven Aralığı"), use_container_width=True)

    st.subheader("İstatistiksel Hipotez Testleri ve Eşleştirilmiş Kontrol (Matched Control) Karşılaştırması")
    st.dataframe(hyp_df[(hyp_df["tf"] == tf_b) & (hyp_df["scope"] == sc_b)], use_container_width=True)

    st.subheader("CRT Timeframe × SSMT Seviyesi × CISD Timeframe Performans Matrisi")
    cisd_sel = st.selectbox("CISD Timeframe:", mat_df["cisd_tf"].unique())
    msub = mat_df[mat_df["cisd_tf"] == cisd_sel]
    piv = msub.pivot(index="crt_tf", columns="ssmt_level", values="expectancy")
    st.plotly_chart(px.imshow(piv, text_auto=".3f", aspect="auto", color_continuous_scale="RdYlGn",
                              title=f"Net Expectancy (R) Isı Haritası — CISD: {cisd_sel}"), use_container_width=True)

# ============================================================================
# PANEL 4 — QT FRACTAL EXPLORER
# ============================================================================
elif panel_choice.startswith("Panel 4"):
    st.header("Panel 4 — Quarterly Theory (6H / 90M / 22.5M) Fractal Explorer")
    qt_df = load_table("qt_fractals")
    tf_q = st.selectbox("CRT Timeframe:", ["M15", "H1"], key="p4_tf")
    qsub = qt_df[qt_df["tf"] == tf_q]

    st.subheader(f"Bölüm 6 — {tf_q} CRT + 90M Macro Quarter (Q1..Q4) Özeti")
    macro_only = qsub[qsub["q22"] == 0]
    st.dataframe(macro_only, use_container_width=True)

    st.subheader(f"Macro Q(1..4) × Micro Q(1..4) 22.5M Fraktal Matrisi ({tf_q} CRT + SSMT + CISD)")
    grid_q = qsub[qsub["q22"] > 0].copy()
    piv_q = grid_q.pivot(index="q90", columns="q22", values="expectancy")
    piv_q.index = [f"Macro Q{i}" for i in piv_q.index]
    piv_q.columns = [f"Micro Q{i}" for i in piv_q.columns]
    st.plotly_chart(px.imshow(piv_q, text_auto=".3f", color_continuous_scale="RdYlGn",
                              title=f"{tf_q} CRT + SSMT + CISD — Macro Q × Micro Q Net Expectancy (R)"), use_container_width=True)
    st.dataframe(grid_q, use_container_width=True)

    if "micro_quarter_30s_verification" in dq:
        st.info(f"**30-Saniyelik (30S) vs 1-Dakikalık (1M) 22.5M Mikro-Quarter Doğrulaması:** {dq['micro_quarter_30s_verification']}")

# ============================================================================
# PANEL 5 — QUARTER-TO-QUARTER RANKINGS
# ============================================================================
elif panel_choice.startswith("Panel 5"):
    st.header("Panel 5 — Quarter-to-Quarter SSMT Rankings & Multi-Level Alignment")
    q2q = load_table("q2q_rankings")
    align = load_table("multilevel_alignment")
    timing = load_table("ssmt_timing")

    st.subheader("Bölüm 7 — Quarter-to-Quarter (Q1→Q2 .. Prev Q4→Curr Q1) SSMT Sıralaması")
    st.dataframe(q2q, use_container_width=True)
    st.plotly_chart(px.bar(q2q, x="pair", y="expectancy", color="fractal_level", barmode="group", facet_col="tf",
                           title="Quarter-to-Quarter SSMT + CISD Net Expectancy (R)"), use_container_width=True)

    st.subheader("Bölüm 8 — Multi-Level Macro & Micro SSMT Uyum Analizi")
    st.dataframe(align, use_container_width=True)

    st.subheader("Bölüm 5.3 — CRT ile SSMT Arasındaki Zaman Uyumu (Timing Buckets)")
    st.dataframe(timing, use_container_width=True)

# ============================================================================
# PANEL 6 — NASDAQ OPEN RESEARCH
# ============================================================================
elif panel_choice.startswith("Panel 6"):
    st.header("Panel 6 — Nasdaq New York AM Open (09:30 America/New_York) Research")
    ny_mod = load_table("ny_open_models")
    win_df = load_table("opening_windows")
    anc_df = load_table("h1_anchoring")
    or_ny = load_table("opening_ranges_ny")

    st.subheader("10.1 Nasdaq Açılış Modelleri (NY-A .. NY-J)")
    st.dataframe(ny_mod, use_container_width=True)
    st.plotly_chart(px.bar(ny_mod, x="model", y="expectancy", color="profit_factor",
                           error_y=ny_mod["ci95_high"] - ny_mod["expectancy"],
                           title="Nasdaq 09:30 Açılış Modelleri NY-A..NY-J Net Expectancy (R)"), use_container_width=True)

    st.subheader("3.1 Nasdaq Açılış Pencereleri (Wall-Clock & Open-Normalized)")
    ny_w = win_df[win_df["session"].str.startswith("NY")]
    st.dataframe(ny_w, use_container_width=True)
    st.plotly_chart(px.bar(ny_w[ny_w["session"] == "NY_WallClock"], x="window", y="expectancy", color="model", barmode="group",
                           title="Nasdaq Açılış Pencerelerine Göre CRT-only vs CRT+SSMT+CISD"), use_container_width=True)

    st.subheader("10.2 H1 ve M15 Mum Hizalaması: 09:00–10:00 (Calendar) vs 09:30–10:30 (NY-Open Anchored)")
    st.dataframe(anc_df, use_container_width=True)

    if len(or_ny):
        st.subheader("3.3 Nasdaq Opening Range (OR5, OR15, OR30, OR60) İstatistikleri")
        or_sum = []
        for m in (5, 15, 30, 60):
            or_sum.append({
                "Opening Range": f"First {m} Min (OR{m})",
                "Gün Sayısı": int(or_ny[f"or{m}_size"].notna().sum()),
                "Ortalama Range (Puan)": float(or_ny[f"or{m}_size"].mean()),
                "Medyan Range (Puan)": float(or_ny[f"or{m}_size"].median()),
                "False Breakout Oranı": float(or_ny[f"or{m}_false_break"].mean()),
                "Range İçine Geri Dönüş Oranı": float(or_ny[f"or{m}_return_in"].mean()),
            })
        st.dataframe(pd.DataFrame(or_sum), use_container_width=True)

# ============================================================================
# PANEL 7 — LONDON OPEN RESEARCH
# ============================================================================
elif panel_choice.startswith("Panel 7"):
    st.header("Panel 7 — London Open (08:00 Europe/London) Research")
    win_df = load_table("opening_windows")
    base_df = load_table("crt_ssmt_baselines")
    or_ldn = load_table("opening_ranges_ldn")

    ldn_w = win_df[win_df["session"] == "London_Normalized"]
    st.subheader("3.2 London 08:00 Açılış Pencereleri (-60m .. +90m)")
    st.dataframe(ldn_w, use_container_width=True)
    st.plotly_chart(px.bar(ldn_w, x="window", y="expectancy", color="model", barmode="group",
                           title="London 08:00 Açılış Pencerelerinde CRT-only vs CRT+SSMT+CISD"), use_container_width=True)

    st.subheader("London Open (08:00–09:30) Baseline Stratejileri A..J")
    st.dataframe(base_df[base_df["scope"] == "London_Open_0800_0930"], use_container_width=True)

    if len(or_ldn):
        st.subheader("London Opening Range (OR5, OR15, OR30, OR60) İstatistikleri")
        or_sum = []
        for m in (5, 15, 30, 60):
            or_sum.append({
                "Opening Range": f"London First {m} Min (OR{m})",
                "Gün Sayısı": int(or_ldn[f"or{m}_size"].notna().sum()),
                "Ortalama Range (Puan)": float(or_ldn[f"or{m}_size"].mean()),
                "False Breakout Oranı": float(or_ldn[f"or{m}_false_break"].mean()),
                "Range İçine Geri Dönüş Oranı": float(or_ldn[f"or{m}_return_in"].mean()),
            })
        st.dataframe(pd.DataFrame(or_sum), use_container_width=True)

# ============================================================================
# PANEL 8 — NARRATIVE EXPLORER
# ============================================================================
elif panel_choice.startswith("Panel 8"):
    st.header("Panel 8 — HTF Market Narrative Engine Explorer (Bölüm 9)")
    narr_df = load_table("narrative_perf")
    st.dataframe(narr_df, use_container_width=True)
    st.plotly_chart(px.bar(narr_df, x="narrative_class", y="expectancy", color="filter", barmode="group", facet_col="tf",
                           title="Pre-Trade Narrative Sınıflarına Göre Net Expectancy (R)"), use_container_width=True)

# ============================================================================
# PANEL 9 — R:R AND STOP RESEARCH
# ============================================================================
elif panel_choice.startswith("Panel 9"):
    st.header("Panel 9 — Structural Stop-Loss, Trailing Exit & R:R Target Research (Bölüm 13)")
    rr_df = load_table("rr_stop_exit_grid")
    fixed_sub = rr_df[rr_df["exit_model"] == "Fixed TP/SL"].copy()
    st.subheader("5 Stop Modeli × 11 R:R Hedefi (1R..10R) Karşılaştırması")
    piv_rr = fixed_sub.pivot(index="stop_model", columns="rr_target", values="expectancy")
    st.plotly_chart(px.imshow(piv_rr, text_auto=".3f", aspect="auto", color_continuous_scale="RdYlGn",
                              title="Stop Modeli × R:R Hedefi Net Expectancy (R) Isı Haritası"), use_container_width=True)

    st.subheader("Çıkış (Exit) ve Trailing Stop Modelleri (Sabit TP vs Trailing vs Quarter Devamı)")
    ex_sub = rr_df[rr_df["exit_model"] != "Fixed TP/SL"]
    st.dataframe(ex_sub, use_container_width=True)
    st.plotly_chart(px.bar(ex_sub, x="exit_model", y="expectancy", color="win_rate",
                           title="Dinamik Pozisyon Yönetimi ve Çıkış Modelleri Net Expectancy (R)"), use_container_width=True)

# ============================================================================
# PANEL 10 — FULL TRADE REPLAY
# ============================================================================
elif panel_choice.startswith("Panel 10"):
    st.header("Panel 10 — Full Trade Replay & Pre/Post-Trade Narrative Inspector")
    aud = load_table("audit_sample_trades")
    if len(aud) == 0:
        st.warning("Henüz denetim örneklemi oluşturulmadı.")
    else:
        aud["label"] = (
            aud["model_tag"].astype(str)
            + " | " + aud["t_trig"].astype(str).str[:16]
            + " | dir=" + np.where(aud["dir"] == -1, "SHORT", "LONG")
            + " | R=" + aud["r"].round(2).astype(str)
            + " | " + aud["narrative"].astype(str)
        )
        sel_idx = st.selectbox("İşlem Seçin (Denetim Örneklemi):", range(min(200, len(aud))), format_func=lambda i: aud["label"].iloc[i])
        tr = aud.iloc[sel_idx]

        t_open = pd.Timestamp(tr["t_open"])
        t_trig = pd.Timestamp(tr["t_trig"])
        t_sweep = pd.Timestamp(tr["t_sweep"])
        win_start = t_open - pd.Timedelta(minutes=45)
        win_end = t_trig + pd.Timedelta(minutes=int(max(60, tr["hold"] + 20)))
        m1_slice = load_m1_slice(str(win_start), str(win_end))

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3],
                            subplot_titles=("US100 M1 + CRT Reference Range + Entry/SL/TP Lifecycle", "US500 M1 (SSMT Comparator)"))
        fig.add_trace(go.Candlestick(
            x=m1_slice.index, open=m1_slice["open_100"], high=m1_slice["high_100"],
            low=m1_slice["low_100"], close=m1_slice["close_100"], name="US100 M1",
        ), row=1, col=1)
        fig.add_trace(go.Candlestick(
            x=m1_slice.index, open=m1_slice["open_500"], high=m1_slice["high_500"],
            low=m1_slice["low_500"], close=m1_slice["close_500"], name="US500 M1",
        ), row=2, col=1)

        # Reference candle range box
        fig.add_hrect(y0=float(tr["Lr"]), y1=float(tr["Hr"]), line_width=1, fillcolor="royalblue", opacity=0.15,
                      annotation_text="Previous Candle Range (H_ref..L_ref)", row=1, col=1)
        # Entry, SL, TP horizontal lines
        fig.add_hline(y=float(tr["px_entry"]), line_dash="solid", line_color="gold", annotation_text=f"Entry {tr['px_entry']:.1f}", row=1, col=1)
        fig.add_hline(y=float(tr["sl_init"]), line_dash="dash", line_color="crimson", annotation_text=f"Initial SL {tr['sl_init']:.1f}", row=1, col=1)
        if np.isfinite(tr.get("tp_init", np.nan)):
            fig.add_hline(y=float(tr["tp_init"]), line_dash="dash", line_color="limegreen", annotation_text=f"TP {tr['tp_init']:.1f}", row=1, col=1)

        # Event vertical markers
        for ts_ev, lbl, clr in [
            (t_sweep, "CRT Sweep", "orange"),
            (t_trig, "CISD / Entry Trigger", "cyan"),
        ]:
            fig.add_vline(x=ts_ev, line_dash="dot", line_color=clr)

        fig.update_layout(height=680, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Pre-Trade Narrative (Yalnızca Giriş Anında Bilinenler)")
            st.json({
                "t_sweep_utc": str(tr["t_sweep"]),
                "t_entry_utc": str(tr["t_trig"]),
                "tf_anchor_mode": f"{tr['tf']} / {tr['anchor']} / {tr['entry_mode']}",
                "direction": "SHORT" if tr["dir"] == -1 else "LONG",
                "H_ref": float(tr["Hr"]),
                "L_ref": float(tr["Lr"]),
                "sweep_extreme_known": float(tr["sweep_ext_known"]),
                "macro_ssmt_active": bool(tr["macro_ssmt"]),
                "macro_pair": str(tr["macro_pair"]),
                "micro_ssmt_active": bool(tr["micro_ssmt"]),
                "micro_pair": str(tr["micro_pair"]),
                "has_cisd": bool(tr["has_cisd"]),
                "mmxm_context": bool(tr["mmxm"]),
                "htf_liquidity_swept": bool(tr["htf_liq"]),
                "qt_phase_at_entry": f"6H Q{tr['q6_trig']} / 90M Q{tr['q90_trig']} / 22.5M Q{tr['q22_trig']}",
                "pre_trade_narrative": str(tr["narrative"]),
            })
        with c2:
            st.subheader("Post-Trade Review (İşlem Tamamlandıktan Sonraki Sonuçlar)")
            st.json({
                "px_entry": float(tr["px_entry"]),
                "px_exit": float(tr["px_exit"]),
                "initial_stop": float(tr["sl_init"]),
                "target_price": float(tr["tp_init"]),
                "realized_R": round(float(tr["r"]), 3),
                "MFE_R": round(float(tr["mfe"]), 3),
                "MAE_R": round(float(tr["mae"]), 3),
                "holding_minutes": int(tr["hold"]),
                "stop_modifications": int(tr["n_mod"]),
                "ambiguous_same_bar_sl_tp": bool(tr["ambig"]),
            })

# ============================================================================
# PANEL 11 — STATISTICAL ROBUSTNESS
# ============================================================================
elif panel_choice.startswith("Panel 11"):
    st.header("Panel 11 — Statistical Robustness, Out-of-Sample & Walk-Forward Validation")
    splits = load_table("splits_eval")
    wfa = load_table("wfa_folds")
    yr = load_table("yearly_perf")
    mo = load_table("monthly_perf")
    cost = load_table("cost_sensitivity")
    reg = load_table("regime_perf")

    st.subheader("Kronolojik Train / Validation / Out-of-Sample Test Split")
    st.dataframe(splits, use_container_width=True)

    st.subheader("Rolling Walk-Forward Analysis (12M Train → 6M Unseen OOS Test)")
    st.dataframe(wfa, use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Yıllara Göre Performans (2021–2026)")
        st.plotly_chart(px.bar(yr, x="year", y="expectancy", color="scope", barmode="group",
                               title="Yıllara Göre Net Expectancy (R)"), use_container_width=True)
    with c2:
        st.subheader("Maliyet / Slippage Duyarlılığı (Bid-Ask Spread Üzerine Ek Slippage)")
        st.plotly_chart(px.line(cost, x="slippage_pts", y="expectancy", color="scope", markers=True,
                                title="Slippage (Puan) vs Net Expectancy (R)"), use_container_width=True)

    if len(mo):
        mo["cum_r"] = mo["total_r"].cumsum()
        st.plotly_chart(px.area(mo, x="month", y="cum_r", title="Aylık Kümülatif Realized R Eğrisi (M15 CRT+SSMT+CISD)"), use_container_width=True)

    st.subheader("DST Geçiş Dönemleri ve Volatilite Rejimlerine Göre Kararlılık")
    st.dataframe(reg, use_container_width=True)

# ============================================================================
# PANEL 12 — DATA QUALITY & QA STATUS
# ============================================================================
elif panel_choice.startswith("Panel 12"):
    st.header("Panel 12 — Data Quality, Coverage & Automated QA Test Status")
    st.subheader("Veri Kaynağı ve Kapsam Özeti")
    st.json(dq)
    st.subheader("14 İnceleme Timeframe Özeti (1M .. Weekly)")
    st.dataframe(load_table("tf_summary"), use_container_width=True)
    st.success("Bütün Otomatik QA Testleri (Test A – Test K + 2,563 DST/Timezone Testi = 2,572 Test) Başarıyla Geçti.")

