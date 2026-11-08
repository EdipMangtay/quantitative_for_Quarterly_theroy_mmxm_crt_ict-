"""ASTRA 6 v2.0 — 13-Panel Quantitative Research Dashboard with Full Combination × Time-of-Day Explorer."""
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
    page_title="ASTRA 6 v2.0 — Verified Intraday Fractal Research Lab",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data
def load_table(name: str) -> pd.DataFrame:
    p = RESULTS / f"{name}.parquet"
    return pd.read_parquet(p) if p.exists() else pd.DataFrame()


@st.cache_data
def load_json(name: str) -> dict:
    p = RESULTS / name
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


st.sidebar.title("ASTRA 6 v2.0 Quant Lab")
st.sidebar.caption("Verified Next-Bar Fill · Causal MMXM · Multi-TF CISD · 30S Micro-QT")
panel_choice = st.sidebar.radio(
    "Araştırma Paneli Seçin (13 Panel):",
    [
        "Panel 0 — Full Combination × Time-of-Day Explorer",
        "Panel 1 — Session Explorer (DST)",
        "Panel 2 — CRT Research",
        "Panel 3 — CRT × SSMT Matrix",
        "Panel 4 — QT Fractal & Multi-Anchor Explorer",
        "Panel 5 — Quarter-to-Quarter Rankings",
        "Panel 6 — Nasdaq Open Research",
        "Panel 7 — London Open Research",
        "Panel 8 — Causal MMXM & Narrative Explorer",
        "Panel 9 — R:R and Stop Research",
        "Panel 10 — Full Trade Replay (Causal)",
        "Panel 11 — Statistical Robustness & Autopsy",
        "Panel 12 — Data Forensics & v1 vs v2 Audit",
    ],
)

dq = load_json("data_quality.json")
st.sidebar.markdown("---")
if dq:
    st.sidebar.metric("Toplam Hizalanmış M1 Bar", f"{dq.get('total_aligned_m1_bars', 0):,}")
    st.sidebar.caption(f"Dönem: {dq.get('period_start', '')[:10]} → {dq.get('period_end', '')[:10]}")
    st.sidebar.caption(f"Execution: {dq.get('execution_fill_model', 'Next-Bar Open')[:32]}")

# ============================================================================
# PANEL 0 — FULL COMBINATION x TIME-OF-DAY EXPLORER (PHASE 10)
# ============================================================================
if panel_choice.startswith("Panel 0"):
    st.header("Panel 0 — Full Combination × Time-of-Day Explorer (18 Models × 24H / 15M / 5M)")
    tf_feats = load_table("trade_features")
    h24_df = load_table("intraday_24h_18models")
    ny_gran = load_table("ny_5m_15m_18models")
    ldn_gran = load_table("ldn_18models")

    st.subheader("1. İnteraktif Trade Feature Küpü Filtreleri (`trade_features.parquet`)")
    if len(tf_feats) > 0:
        f1, f2, f3, f4 = st.columns(4)
        with f1:
            prov_sel = st.selectbox("Veri Sağlayıcı Senaryosu:", ["All", "DUKASCOPY_OBSERVED_BID_ASK", "OANDA_BASIS_EXTENDED"])
            crt_tf_sel = st.multiselect("CRT Timeframe:", sorted(tf_feats["tf"].unique()), default=["M15"])
            entry_mode_sel = st.multiselect("CRT Giriş Modu:", sorted(tf_feats["entry_mode"].unique()), default=["confirmed"])
        with f2:
            ssmt_sel = st.selectbox("SMT / SSMT Filtresi:", ["All", "Macro SSMT", "Micro SSMT", "Both Macro+Micro SSMT", "Standard SMT"])
            q90_sel = st.multiselect("90M Macro Quarter:", [1, 2, 3, 4], default=[1, 2, 3, 4])
            q22_sel = st.multiselect("22.5M Micro Quarter:", [1, 2, 3, 4], default=[1, 2, 3, 4])
        with f3:
            cisd_sel = st.selectbox("CISD Timeframe:", ["All", "M1 CISD", "M3 CISD", "M5 CISD", "M15 CISD"])
            mmxm_sel = st.selectbox("Causal MMXM Filtresi:", ["All", "Confirmed Stage 8 (MMBM/MMSM)", "Early Candidate Stage 6+", "MMBM Only", "MMSM Only"])
            htf_sel = st.selectbox("HTF Bias / Likidite:", ["All", "HTF Swept + Aligned", "HTF Swept Only"])
        with f4:
            sess_sel = st.selectbox("Oturum:", ["All", "NY_AM_Open_0930_1100", "NY_Midday_PM_1100_1600", "London_Open_0800_1100", "Overnight_Asia"])
            hr_range = st.slider("NY Giriş Saati (0–23):", 0, 23, (0, 23))
            ny_min_range = st.slider("Nasdaq 09:30 Açılışına Göre Dakika:", -120, 390, (-60, 180))

        sub = tf_feats.copy()
        if prov_sel != "All":
            sub = sub[sub["dataset_provider"] == prov_sel]
        if crt_tf_sel:
            sub = sub[sub["tf"].isin(crt_tf_sel)]
        if entry_mode_sel:
            sub = sub[sub["entry_mode"].isin(entry_mode_sel)]
        if q90_sel:
            sub = sub[sub["q90_trig"].isin(q90_sel)]
        if q22_sel:
            sub = sub[sub["q22_trig"].isin(q22_sel)]
        sub = sub[(sub["ny_hour_trig"] >= hr_range[0]) & (sub["ny_hour_trig"] <= hr_range[1])]

        if ssmt_sel == "Macro SSMT":
            sub = sub[sub["macro_ssmt"]]
        elif ssmt_sel == "Micro SSMT":
            sub = sub[sub["micro_ssmt"]]
        elif ssmt_sel == "Both Macro+Micro SSMT":
            sub = sub[sub["both_ssmt"]]
        elif ssmt_sel == "Standard SMT":
            sub = sub[sub["std_smt"]]

        if cisd_sel == "M1 CISD":
            sub = sub[sub["cisd_m1"]]
        elif cisd_sel == "M3 CISD":
            sub = sub[sub["cisd_m3"]]
        elif cisd_sel == "M5 CISD":
            sub = sub[sub["cisd_m5"]]
        elif cisd_sel == "M15 CISD":
            sub = sub[sub["cisd_m15"]]

        if mmxm_sel == "Confirmed Stage 8 (MMBM/MMSM)":
            sub = sub[sub["mmxm_confirmed"]]
        elif mmxm_sel == "Early Candidate Stage 6+":
            sub = sub[sub["mmxm_early_candidate"]]
        elif mmxm_sel == "MMBM Only":
            sub = sub[sub["mmxm_early_candidate"] & (sub["dir"] == 1)]
        elif mmxm_sel == "MMSM Only":
            sub = sub[sub["mmxm_early_candidate"] & (sub["dir"] == -1)]

        if htf_sel == "HTF Swept + Aligned":
            sub = sub[sub["htf_liq"] & (sub["daily_bias"] == sub["dir"])]
        elif htf_sel == "HTF Swept Only":
            sub = sub[sub["htf_liq"]]

        if sess_sel != "All":
            sub = sub[sub["session"] == sess_sel]
        sub = sub[(sub["min_from_ny_open_trig"] >= ny_min_range[0]) & (sub["min_from_ny_open_trig"] <= ny_min_range[1])]

        k1, k2, k3, k4 = st.columns(4)
        n_tr = len(sub)
        wr = float((sub["r"] > 0).mean()) if n_tr > 0 else 0.0
        exp_r = float(sub["r"].mean()) if n_tr > 0 else 0.0
        tot_r = float(sub["r"].sum()) if n_tr > 0 else 0.0
        k1.metric("Filtrelenen İşlem Sayısı", f"{n_tr:,}")
        k2.metric("Win Rate", f"{wr * 100:.2f}%")
        k3.metric("Net Expectancy (R)", f"{exp_r:+.4f} R")
        k4.metric("Toplam Net R", f"{tot_r:+.2f} R")

    st.subheader("2. 24 Saat NY Saat Dilimi × 18 Strateji Modeli Net Expectancy (R) Isı Haritası")
    if len(h24_df) > 0:
        tf_h24 = st.selectbox("24H Isı Haritası CRT Timeframe:", ["M15", "H1"], key="h24_tf")
        h24_sub = h24_df[h24_df["tf"] == tf_h24]
        piv_24 = h24_sub.pivot(index="model", columns="ny_hour", values="expectancy")
        st.plotly_chart(px.imshow(piv_24, text_auto=".2f", aspect="auto", color_continuous_scale="RdYlGn",
                                  title=f"Heatmap 1 ({tf_h24}): 24H NY Hour (00..23) × 18 Strategy Models Expectancy (R)"), use_container_width=True)

    st.subheader("3. Nasdaq 09:00–16:00 (15M Non-Overlapping & 5M Granular) × 18 Model Isı Haritası")
    if len(ny_gran) > 0:
        ny_m15 = ny_gran[ny_gran["tf"] == "M15"]
        g15 = ny_m15[ny_m15["bin_type"] == "NY_15M_NonOverlap"]
        piv_15 = g15.pivot(index="model", columns="window", values="expectancy")
        st.plotly_chart(px.imshow(piv_15, text_auto=".2f", aspect="auto", color_continuous_scale="RdYlGn",
                                  title="Heatmap 2 (M15): 09:00–16:00 15-Minute Non-Overlapping Bins × 18 Models Expectancy (R)"), use_container_width=True)

        g5 = ny_m15[ny_m15["bin_type"] == "NY_Granular_5M_15M"]
        piv_5 = g5.pivot(index="model", columns="window", values="expectancy")
        st.plotly_chart(px.imshow(piv_5, text_auto=".2f", aspect="auto", color_continuous_scale="RdYlGn",
                                  title="Heatmap 3 (M15): 09:30–11:00 5M & 15M NY Open Windows × 18 Models Expectancy (R)"), use_container_width=True)

    st.subheader("4. London Open (07:00–11:00) Pencereleri × 18 Model Isı Haritası")
    if len(ldn_gran) > 0:
        ldn_m15 = ldn_gran[ldn_gran["tf"] == "M15"]
        piv_ldn = ldn_m15.pivot(index="model", columns="window", values="expectancy")
        st.plotly_chart(px.imshow(piv_ldn, text_auto=".2f", aspect="auto", color_continuous_scale="RdYlGn",
                                  title="Heatmap 4 (M15): London 07:00–11:00 Windows × 18 Models Expectancy (R)"), use_container_width=True)

# ============================================================================
# PANEL 1 — SESSION EXPLORER
# ============================================================================
elif panel_choice.startswith("Panel 1"):
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
    if len(tf_stats) > 0:
        st.plotly_chart(px.bar(tf_stats, x="tf", y="expectancy", error_y=tf_stats["ci95_high"] - tf_stats["expectancy"],
                               color="stat_status", title="Timeframe Bazında CRT-A Net Expectancy (R) — Next-Bar Fill"), use_container_width=True)

    st.subheader("4.4 CRT Varyantları (CRT-A .. CRT-L)")
    vdf = load_table("crt_variants")
    if len(vdf) > 0:
        tf_sel = st.selectbox("CRT Varyant Timeframe Filtresi:", vdf["tf"].unique())
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
    st.header("Panel 3 — CRT × SSMT × CISD Matrix, Baselines (A..J) & Incremental Contribution")
    base_df = load_table("crt_ssmt_baselines")
    hyp_df = load_table("hypothesis_tests")
    mat_df = load_table("crt_ssmt_matrix")
    inc_df = load_table("incremental_contribution")

    c1, c2 = st.columns(2)
    with c1:
        tf_b = st.selectbox("Timeframe:", ["M15", "H1"], key="p3_tf")
    with c2:
        sc_b = st.selectbox("Oturum Kapsamı:", base_df["scope"].unique() if len(base_df) else ["All_Sessions"], key="p3_sc")

    bsub = base_df[(base_df["tf"] == tf_b) & (base_df["scope"] == sc_b)] if len(base_df) else pd.DataFrame()
    st.subheader(f"5.4 Baseline Strateji Merdiveni A..J ({tf_b} — {sc_b})")
    st.dataframe(bsub, use_container_width=True)
    if len(bsub) > 0:
        st.plotly_chart(px.bar(bsub, x="strategy", y="expectancy", color="stat_status",
                               error_y=bsub["ci95_high"] - bsub["expectancy"],
                               title=f"{tf_b} ({sc_b}) — Strateji A..J Net Expectancy (R) ve %95 Güven Aralığı"), use_container_width=True)

    st.subheader("Katmanlı Marjinal Katkı Analizi (Incremental Contribution Ladder)")
    st.dataframe(inc_df, use_container_width=True)

    st.subheader("İstatistiksel Hipotez Testleri (Holm-Bonferroni & BH-FDR Düzeltmeli)")
    st.dataframe(hyp_df[(hyp_df["tf"] == tf_b) & (hyp_df["scope"] == sc_b)] if len(hyp_df) else hyp_df, use_container_width=True)

    st.subheader("Heatmap 5: CRT Timeframe × SSMT Seviyesi × Gerçek CISD Timeframe Matrisi")
    if len(mat_df) > 0:
        cisd_sel = st.selectbox("CISD Timeframe:", mat_df["cisd_tf"].unique())
        msub = mat_df[mat_df["cisd_tf"] == cisd_sel]
        piv = msub.pivot(index="crt_tf", columns="ssmt_level", values="expectancy")
        st.plotly_chart(px.imshow(piv, text_auto=".3f", aspect="auto", color_continuous_scale="RdYlGn",
                                  title=f"Net Expectancy (R) Isı Haritası — CISD: {cisd_sel}"), use_container_width=True)

# ============================================================================
# PANEL 4 — QT FRACTAL & MULTI-ANCHOR EXPLORER
# ============================================================================
elif panel_choice.startswith("Panel 4"):
    st.header("Panel 4 — Quarterly Theory (6H / 90M / 22.5M) & Multi-Anchor Explorer")
    qt_df = load_table("qt_fractals")
    anc_comp = load_table("qt_anchor_comparison")
    m30_comp = load_table("micro_30s_vs_1m_perf")

    tf_q = st.selectbox("CRT Timeframe:", ["M15", "H1"], key="p4_tf")
    qsub = qt_df[qt_df["tf"] == tf_q] if len(qt_df) else pd.DataFrame()

    st.subheader("Heatmap 6: 90M Macro Q(1..4) × 22.5M Micro Q(1..4) Fraktal Matrisi")
    if len(qsub) > 0:
        grid_q = qsub[qsub["q22"] > 0].copy()
        piv_q = grid_q.pivot(index="q90", columns="q22", values="expectancy")
        piv_q.index = [f"Macro Q{i}" for i in piv_q.index]
        piv_q.columns = [f"Micro Q{i}" for i in piv_q.columns]
        st.plotly_chart(px.imshow(piv_q, text_auto=".3f", color_continuous_scale="RdYlGn",
                                  title=f"{tf_q} CRT + SSMT + CISD — Macro Q × Micro Q Net Expectancy (R)"), use_container_width=True)
        st.dataframe(qsub, use_container_width=True)

    st.subheader("Phase 3 — 3 Farklı QT Çapası Karşılaştırması (`ny1800` vs `ny0930` vs `ldn0800`)")
    st.dataframe(anc_comp, use_container_width=True)

    st.subheader("Phase 1.5 — 4.5 Yıllık Tam 30-Saniye (30S Exact) vs 1-Dakika (1M Approx) 22.5M Mikro-Quarter SSMT")
    st.dataframe(m30_comp, use_container_width=True)

# ============================================================================
# PANEL 5 — QUARTER-TO-QUARTER RANKINGS
# ============================================================================
elif panel_choice.startswith("Panel 5"):
    st.header("Panel 5 — Quarter-to-Quarter SSMT Rankings & Multi-Level Alignment")
    q2q = load_table("q2q_rankings")
    align = load_table("multilevel_alignment")
    timing = load_table("ssmt_timing")

    st.subheader("Heatmap 7: Quarter-to-Quarter (Q1→Q2, Q2→Q3, Q3→Q4) SSMT Sıralaması")
    st.dataframe(q2q, use_container_width=True)
    if len(q2q) > 0:
        st.plotly_chart(px.bar(q2q, x="pair", y="expectancy", color="fractal_level", barmode="group", facet_col="tf",
                               title="Quarter-to-Quarter SSMT + CISD Net Expectancy (R)"), use_container_width=True)

    st.subheader("Multi-Level Macro & Micro SSMT Uyum Analizi")
    st.dataframe(align, use_container_width=True)

    st.subheader("CRT ile SSMT Arasındaki Zaman Uyumu")
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
    if len(ny_mod) > 0:
        st.plotly_chart(px.bar(ny_mod, x="model", y="expectancy", color="stat_status",
                               error_y=ny_mod["ci95_high"] - ny_mod["expectancy"],
                               title="Nasdaq 09:30 Açılış Modelleri NY-A..NY-J Net Expectancy (R)"), use_container_width=True)

    st.subheader("3.1 Nasdaq Açılış Pencereleri Performansı")
    ny_w = win_df[win_df["session"].str.startswith("NY")] if len(win_df) > 0 else pd.DataFrame()
    st.dataframe(ny_w, use_container_width=True)

    st.subheader("10.2 H1 ve M15 Mum Hizalaması: Calendar vs NY-Open Anchored (09:30)")
    st.dataframe(anc_df, use_container_width=True)

    if len(or_ny) > 0:
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
    ldn_18 = load_table("ldn_18models")
    or_ldn = load_table("opening_ranges_ldn")

    ldn_w = win_df[win_df["session"] == "London_Normalized"] if len(win_df) > 0 else pd.DataFrame()
    st.subheader("3.2 London 08:00 Açılış Pencereleri")
    st.dataframe(ldn_w, use_container_width=True)

    st.subheader("London Open × 18 Strateji Modeli Performans Tablosu")
    st.dataframe(ldn_18, use_container_width=True)

    if len(or_ldn) > 0:
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
# PANEL 8 — CAUSAL MMXM & NARRATIVE EXPLORER
# ============================================================================
elif panel_choice.startswith("Panel 8"):
    st.header("Panel 8 — Causal 10-Stage MMXM State Machine & HTF Narrative Explorer")
    narr_df = load_table("narrative_perf")
    st.subheader("Heatmap 8: Causal MMXM (MMBM / MMSM) & Pre-Trade Narrative Sınıfları")
    st.dataframe(narr_df, use_container_width=True)
    if len(narr_df) > 0:
        st.plotly_chart(px.bar(narr_df, x="narrative_class", y="expectancy", color="filter", barmode="group", facet_col="tf",
                               title="Pre-Trade Narrative Sınıflarına Göre Net Expectancy (R)"), use_container_width=True)

# ============================================================================
# PANEL 9 — R:R AND STOP RESEARCH
# ============================================================================
elif panel_choice.startswith("Panel 9"):
    st.header("Panel 9 — Structural Stop-Loss, Trailing Exit & R:R Target Research")
    rr_df = load_table("rr_stop_exit_grid")
    if len(rr_df) > 0:
        fixed_sub = rr_df[rr_df["exit_model"] == "Fixed TP/SL"].copy()
        st.subheader("Heatmap 9: 6 Stop Modeli × 11 R:R Hedefi (1R..10R) Net Expectancy (R)")
        piv_rr = fixed_sub.pivot(index="stop_model", columns="rr_target", values="expectancy")
        st.plotly_chart(px.imshow(piv_rr, text_auto=".3f", aspect="auto", color_continuous_scale="RdYlGn",
                                  title="Stop Modeli × R:R Hedefi Net Expectancy (R) Isı Haritası"), use_container_width=True)

        st.subheader("Dinamik Çıkış (Exit) Modelleri (Fixed vs BE+1R vs 50%@1R vs Trail M5 vs MMXM Target vs TimeExit)")
        ex_sub = rr_df[rr_df["exit_model"] != "Fixed TP/SL"]
        st.dataframe(ex_sub, use_container_width=True)

# ============================================================================
# PANEL 10 — FULL TRADE REPLAY (CAUSAL NEXT-BAR FILL)
# ============================================================================
elif panel_choice.startswith("Panel 10"):
    st.header("Panel 10 — Causal Full Trade Replay (`t_signal_known` → `t_fill` Next-Bar Open)")
    aud = load_table("audit_sample_trades")
    if len(aud) == 0:
        st.warning("Henüz denetim örneklemi oluşturulmadı.")
    else:
        aud["label"] = (
            aud["model_tag"].astype(str)
            + " | sig=" + aud["t_signal_known"].astype(str).str[:16]
            + " | fill=" + aud["t_fill"].astype(str).str[:16]
            + " | dir=" + np.where(aud["dir"] == -1, "SHORT", "LONG")
            + " | R=" + aud["r"].round(2).astype(str)
            + " | MMXM=" + aud["mmxm_model_label"].astype(str)
        )
        sel_idx = st.selectbox("İşlem Seçin (Denetim Örneklemi):", range(min(200, len(aud))), format_func=lambda i: aud["label"].iloc[i])
        tr = aud.iloc[sel_idx]

        t_open = pd.Timestamp(tr["t_open"])
        t_sig = pd.Timestamp(tr["t_signal_known"])
        t_fill = pd.Timestamp(tr["t_fill"])
        t_sweep = pd.Timestamp(tr["t_sweep"])
        win_start = t_open - pd.Timedelta(minutes=45)
        win_end = t_fill + pd.Timedelta(minutes=int(max(60, tr["hold"] + 20)))
        m1_slice = load_m1_slice(str(win_start), str(win_end))

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3],
                            subplot_titles=("US100 M1 + CRT Range + Next-Bar Open Fill / SL / TP", "US500 M1 (SSMT Comparator)"))
        fig.add_trace(go.Candlestick(
            x=m1_slice.index, open=m1_slice["open_100"], high=m1_slice["high_100"],
            low=m1_slice["low_100"], close=m1_slice["close_100"], name="US100 M1",
        ), row=1, col=1)
        fig.add_trace(go.Candlestick(
            x=m1_slice.index, open=m1_slice["open_500"], high=m1_slice["high_500"],
            low=m1_slice["low_500"], close=m1_slice["close_500"], name="US500 M1",
        ), row=2, col=1)

        fig.add_hrect(y0=float(tr["Lr"]), y1=float(tr["Hr"]), line_width=1, fillcolor="royalblue", opacity=0.15,
                      annotation_text="Previous Candle Range (H_ref..L_ref)", row=1, col=1)
        fig.add_hline(y=float(tr["px_entry"]), line_dash="solid", line_color="gold", annotation_text=f"Next-Bar Fill {tr['px_entry']:.1f}", row=1, col=1)
        fig.add_hline(y=float(tr["sl_init"]), line_dash="dash", line_color="crimson", annotation_text=f"SL {tr['sl_init']:.1f}", row=1, col=1)
        if np.isfinite(tr.get("tp_init", np.nan)):
            fig.add_hline(y=float(tr["tp_init"]), line_dash="dash", line_color="limegreen", annotation_text=f"TP {tr['tp_init']:.1f}", row=1, col=1)

        for ts_ev, lbl, clr in [
            (t_sweep, "CRT Sweep", "orange"),
            (t_sig, "Signal Known / Submit", "cyan"),
            (t_fill, "Actual Fill (Next Open)", "gold"),
        ]:
            fig.add_vline(x=ts_ev, line_dash="dot", line_color=clr)

        fig.update_layout(height=680, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Pre-Trade Causal State (Yalnızca `t_signal_known` Anında Bilinenler)")
            st.json({
                "t_sweep_utc": str(tr["t_sweep"]),
                "t_signal_known_utc": str(tr["t_signal_known"]),
                "t_order_submit_utc": str(tr["t_order_submit"]),
                "t_fill_next_bar_open_utc": str(tr["t_fill"]),
                "j_trig": int(tr["j_trig"]),
                "j_fill": int(tr["j_fill"]),
                "tf_anchor_mode": f"{tr['tf']} / {tr['anchor']} / {tr['entry_mode']}",
                "direction": "SHORT" if tr["dir"] == -1 else "LONG",
                "H_ref": float(tr["Hr"]),
                "L_ref": float(tr["Lr"]),
                "macro_ssmt_active": bool(tr["macro_ssmt"]),
                "macro_all_pairs": str(tr.get("macro_all_pairs", "")),
                "micro_ssmt_active": bool(tr["micro_ssmt"]),
                "micro_all_pairs": str(tr.get("micro_all_pairs", "")),
                "cisd_m1": bool(tr["cisd_m1"]),
                "cisd_m3": bool(tr["cisd_m3"]),
                "cisd_m5": bool(tr["cisd_m5"]),
                "mmxm_model_label": str(tr["mmxm_model_label"]),
                "mmxm_stage": int(tr["mmxm_stage"]),
                "qt_phase_at_entry": f"6H Q{tr['q6_trig']} / 90M Q{tr['q90_trig']} / 22.5M Q{tr['q22_trig']}",
                "pre_trade_narrative": str(tr["narrative"]),
            })
        with c2:
            st.subheader("Post-Trade Realized Outcome (İşlem Sonrası)")
            st.json({
                "px_entry": float(tr["px_entry"]),
                "px_exit": float(tr["px_exit"]),
                "initial_stop": float(tr["sl_init"]),
                "target_price": float(tr["tp_init"]),
                "realized_R": round(float(tr["r"]), 4),
                "MFE_R": round(float(tr["mfe"]), 4),
                "MAE_R": round(float(tr["mae"]), 4),
                "holding_minutes": int(tr["hold"]),
                "stop_modifications": int(tr["n_mod"]),
                "exit_reason": int(tr["exit_reason"]),
                "ambiguous_same_bar_sl_tp": bool(tr["ambig"]),
            })

# ============================================================================
# PANEL 11 — STATISTICAL ROBUSTNESS & LOSING TRADES AUTOPSY
# ============================================================================
elif panel_choice.startswith("Panel 11"):
    st.header("Panel 11 — Statistical Robustness, WFA, Year×Month Matrix & Losing Trades Autopsy")
    splits = load_table("splits_eval")
    wfa = load_table("wfa_folds")
    yr = load_table("yearly_perf")
    mo = load_table("monthly_perf")
    cost = load_table("cost_sensitivity")
    reg = load_table("regime_perf")
    autopsy = load_table("losing_trades_autopsy")
    prov_comp = load_table("dataset_provider_comparison")

    st.subheader("Kronolojik Train / Validation / Out-of-Sample Test Split")
    st.dataframe(splits, use_container_width=True)

    st.subheader("Veri Sağlayıcı Senaryoları Karşılaştırması (Pure Dukascopy vs Pure OANDA vs Mixed Extended)")
    st.dataframe(prov_comp, use_container_width=True)

    st.subheader("Rolling Walk-Forward Analysis")
    st.dataframe(wfa, use_container_width=True)

    st.subheader("Heatmap 10: Yıl × Ay Performans Matrisi ve Maliyet Duyarlılığı")
    c1, c2 = st.columns(2)
    with c1:
        if len(yr) > 0:
            st.plotly_chart(px.bar(yr, x="year", y="expectancy", color="scope", barmode="group",
                                   title="Yıllara Göre Net Expectancy (R)"), use_container_width=True)
    with c2:
        if len(cost) > 0:
            st.plotly_chart(px.line(cost, x="slippage_pts", y="expectancy", color="scope", markers=True,
                                    title="Slippage (Puan) vs Net Expectancy (R)"), use_container_width=True)

    if len(mo) > 0:
        mo_copy = mo.copy()
        mo_copy["year"] = mo_copy["month"].str[:4]
        mo_copy["month_num"] = mo_copy["month"].str[5:7]
        piv_ym = mo_copy.pivot(index="year", columns="month_num", values="avg_r")
        st.plotly_chart(px.imshow(piv_ym, text_auto=".2f", aspect="auto", color_continuous_scale="RdYlGn",
                                  title="Heatmap 10: Year × Month Net Expectancy (R) Matrix"), use_container_width=True)

    st.subheader("Bölüm 11 — Kaybeden İşlemler Otopsisi (Losing Trades Autopsy)")
    st.dataframe(autopsy, use_container_width=True)

    st.subheader("DST Geçiş Dönemleri ve Volatilite Rejimlerine Göre Kararlılık")
    st.dataframe(reg, use_container_width=True)

# ============================================================================
# PANEL 12 — DATA FORENSICS & V1 VS V2 AUDIT
# ============================================================================
elif panel_choice.startswith("Panel 12"):
    st.header("Panel 12 — Historical Data Forensics, SHA256 Manifest & v1.0 vs v2.0 Comparison")
    st.subheader("Tam Dosya SHA256 ve Bid/Ask Gerçeklik Etiketleri (`data_authenticity_manifest.parquet`)")
    st.dataframe(load_table("data_authenticity_manifest"), use_container_width=True)

    st.subheader("v1.0 (Same-Bar Close) vs v2.0 (Next-Bar Open + Causal MMXM + Multi-TF CISD) Karşılaştırma Tablosu")
    st.dataframe(load_table("v1_vs_v2_comparison"), use_container_width=True)

    st.subheader("Bağımsız 5×100 (500 Olay/İşlem) Forensic Audit Özeti (`independent_audit_samples.json`)")
    aud_json = load_json("independent_audit_samples.json")
    if aud_json:
        st.json({
            "audit_version": aud_json.get("audit_version"),
            "all_500_passed": aud_json.get("all_500_passed"),
            "CRT_100_pass_rate": aud_json.get("crt_100", {}).get("pass_rate"),
            "SSMT_100_pass_rate": aud_json.get("ssmt_100", {}).get("pass_rate"),
            "CISD_100_pass_rate": aud_json.get("cisd_100", {}).get("pass_rate"),
            "MMXM_100_pass_rate": aud_json.get("mmxm_100", {}).get("pass_rate"),
            "TRADES_100_pass_rate": aud_json.get("trades_100", {}).get("pass_rate"),
        })
