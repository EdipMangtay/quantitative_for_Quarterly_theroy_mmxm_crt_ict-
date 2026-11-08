"""ASTRA 6 V3 FINAL — Universal Fractal Market Narrative & Multi-Timeframe Quant Lab Dashboard.

Extends the verified V2 13-panel application with all 12 mandatory V3 Research Modules (Section 19: A through L):
  * Module A: Universal Narrative Combination Builder (64 Core Binary States + 15 Strategy Families + Live Opportunity Filter)
  * Module B: Fractal Structure Explorer (Nested W1/D1/H4/H1/M15/M5/M3/M1 Pairs, Triples & Quads)
  * Module C: Entry-to-Target Timeframe Matrix (LTF -> HTF Liquidity & HTF -> LTF Original Consolidation)
  * Module D: MMXM × QT Narrative Explorer (13-Stage Lifecycle × 6H/90M/22.5M QT Phases & Transitions)
  * Module E: Macro/Micro SSMT Explorer (All 10 SSMT States × LONG/SHORT/BOTH)
  * Module F: CISD Timeframe Comparison (No-CISD vs M1/M3/M5/M15/M30/H1/H4 & Multi-TF Subsets)
  * Module G: Nasdaq Open (09:30 NY 5-Min) & London Open LONG/SHORT Heatmap
  * Module H: Original Consolidation & Liquidity Target Map
  * Module I: Strategy Ablation (Marginal Contribution of CRT, SSMT, CISD, MMXM, QT, Target TF)
  * Module J: Causal Trade Replay with Future-Candles-Hidden Step-by-Step Bar Slider
  * Module K: Statistical Robustness, OOS Splits, Cost Sensitivity & Hardware Benchmark
  * Module L: 25 Statistical Rankings, No-Trade Conditions, 10×100 Manual Validation & V4 Handoff
  * Plus all V2 Legacy Panels (V2 Panel 0 .. V2 Panel 12) preserved intact.
"""
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
    page_title="ASTRA 6 V3 FINAL — Universal Fractal Market Narrative Quant Lab",
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


st.sidebar.title("ASTRA 6 V3 FINAL Quant Lab")
st.sidebar.caption("Universal Fractal Market Narrative · QT × MMXM × ICT × CRT × SSMT × CISD · LONG/SHORT")

MODULES = [
    "V3 Module A — Universal Narrative Combination Builder",
    "V3 Module B — Fractal Structure Explorer (W1..M1)",
    "V3 Module C — Entry-to-Target Timeframe Matrix (LTF↔HTF)",
    "V3 Module D — MMXM × QT Narrative Explorer",
    "V3 Module E — Macro/Micro SSMT 10-State Explorer",
    "V3 Module F — Multi-TF CISD Comparison (M1..H4)",
    "V3 Module G — Nasdaq 09:30 5-Min & London Heatmap",
    "V3 Module H — Original Consolidation & Liquidity Map",
    "V3 Module I — Strategy Ablation (Marginal Delta R)",
    "V3 Module J — Causal Trade Replay (Hide Future Bars)",
    "V3 Module K — Statistical Robustness & HPC Benchmark",
    "V3 Module L — 25 Rankings, No-Trade, 10×100 & V4 Handoff",
    "V2 Panel 0 — Legacy 18-Model × Time-of-Day Explorer",
    "V2 Panel 1 — Session Explorer (DST)",
    "V2 Panel 2 — CRT Research",
    "V2 Panel 3 — CRT × SSMT Matrix",
    "V2 Panel 4 — QT Fractal & Multi-Anchor Explorer",
    "V2 Panel 5 — Quarter-to-Quarter Rankings",
    "V2 Panel 6 — Nasdaq Open Research",
    "V2 Panel 7 — London Open Research",
    "V2 Panel 8 — Causal MMXM & Narrative Explorer",
    "V2 Panel 9 — R:R and Stop Research",
    "V2 Panel 11 — Statistical Robustness & Autopsy",
    "V2 Panel 12 — Data Forensics & v1 vs v2 Audit",
]
panel_choice = st.sidebar.radio("Araştırma Modülü Seçin:", MODULES)

dq = load_json("data_quality.json")
hw = load_json("hardware_benchmark.json")
st.sidebar.markdown("---")
if dq:
    st.sidebar.metric("Toplam Hizalanmış M1 Bar", f"{dq.get('total_aligned_m1_bars', 0):,}")
    st.sidebar.caption(f"Dönem: {dq.get('period_start', '')[:10]} → {dq.get('period_end', '')[:10]}")
if hw:
    hp = hw.get("hardware_profile", {})
    st.sidebar.caption(f"Donanım: {hp.get('cpu_model', 'Apple Silicon')} ({hp.get('physical_cores', 0)}P/{hp.get('logical_cores', 0)}L Core, {hp.get('ram_total_gb', 0)}GB RAM)")

# ============================================================================
# V3 MODULE A — UNIVERSAL NARRATIVE COMBINATION BUILDER (SECTION 19.A)
# ============================================================================
if panel_choice.startswith("V3 Module A"):
    st.header("V3 Module A — Universal Narrative Combination Builder (64 Core Binary States + 15 Strategy Families)")
    cands = load_table("candidate_opportunities")
    comb_res = load_table("combination_results")
    fam_15 = load_table("v3_family_15_subsets")

    st.subheader("1. Canlı 20-Boyutlu Fraktal Narrative Kombinasyon Oluşturucu (`candidate_opportunities.parquet`)")
    if len(cands) > 0:
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            dir_sel = st.selectbox("Yön (Direction):", ["BOTH", "LONG", "SHORT"])
            hyp_sel = st.selectbox("Hipotez (Reversal / Continuation):", ["ALL", "REVERSAL", "CONTINUATION"])
            orig_sel = st.multiselect("Origin Timeframe:", sorted(cands["origin_tf"].astype(str).unique()), default=[])
            narr_sel = st.multiselect("Narrative Timeframe:", sorted(cands["narrative_tf"].astype(str).unique()), default=[])
        with c2:
            mmxm_tf_sel = st.multiselect("MMXM Timeframe:", sorted(cands["mmxm_tf"].astype(str).unique()), default=[])
            mmxm_on_sel = st.selectbox("MMXM Durumu:", ["ALL", "MMXM Active (Stage >= 5)", "MMXM OFF"])
            q6_sel = st.multiselect("6H Macro Quarter:", [1, 2, 3, 4], default=[1, 2, 3, 4])
            q90_sel = st.multiselect("90M Quarter:", [1, 2, 3, 4], default=[1, 2, 3, 4])
        with c3:
            q22_sel = st.multiselect("22.5M Micro Quarter:", [1, 2, 3, 4], default=[1, 2, 3, 4])
            crt_sel = st.selectbox("CRT Durumu:", ["ALL", "CRT Confirmed (A=True)", "CRT Developing (Intrabar)", "CRT OFF (Sweep Only)"])
            mac_sel = st.selectbox("90M Macro SSMT:", ["ALL", "ON", "OFF"])
            mic_sel = st.selectbox("22.5M Micro SSMT:", ["ALL", "ON", "OFF"])
        with c4:
            cisd_sel = st.selectbox("CISD Durumu:", ["ALL", "Any CISD ON", "No CISD (OFF)"])
            ent_tf_sel = st.multiselect("Entry Timeframe:", sorted(cands["entry_tf"].astype(str).unique()), default=[])
            tgt_tf_sel = st.multiselect("Target Timeframe:", sorted(cands["target_tf"].astype(str).unique()), default=[])
            tgt_type_sel = st.multiselect("Target Type:", sorted(cands["target_type"].astype(str).unique()), default=[])
        with c5:
            reg_sel = st.multiselect("HTF/LTF Yapısal Rejim:", sorted(cands["structural_regime"].astype(str).unique()), default=[])
            sess_sel = st.selectbox("Oturum (Session):", ["ALL"] + sorted(cands["session"].astype(str).unique()))
            ny_min_rng = st.slider("Nasdaq 09:30'a Göre Dakika:", -120, 390, (-120, 390))
            split_sel = st.selectbox("Validation Split:", ["ALL", "TRAIN_DEV", "VALIDATION", "OOS_TEST"])

        sub = cands.copy()
        if dir_sel != "BOTH":
            sub = sub[sub["direction_label"] == dir_sel]
        if hyp_sel != "ALL":
            sub = sub[sub["hypothesis_type"] == hyp_sel]
        if orig_sel:
            sub = sub[sub["origin_tf"].isin(orig_sel)]
        if narr_sel:
            sub = sub[sub["narrative_tf"].isin(narr_sel)]
        if mmxm_tf_sel:
            sub = sub[sub["mmxm_tf"].isin(mmxm_tf_sel)]
        if mmxm_on_sel == "MMXM Active (Stage >= 5)":
            sub = sub[sub["f_mmxm"]]
        elif mmxm_on_sel == "MMXM OFF":
            sub = sub[~sub["f_mmxm"]]
        if q6_sel:
            sub = sub[sub["q6_trig"].isin(q6_sel)]
        if q90_sel:
            sub = sub[sub["q90_trig"].isin(q90_sel)]
        if q22_sel:
            sub = sub[sub["q22_trig"].isin(q22_sel)]
        if crt_sel == "CRT Confirmed (A=True)":
            sub = sub[sub["f_crt"]]
        elif crt_sel == "CRT Developing (Intrabar)":
            sub = sub[sub["entry_mode"] == "dev_cisd"]
        elif crt_sel == "CRT OFF (Sweep Only)":
            sub = sub[(~sub["f_crt"]) & (sub["entry_mode"] != "dev_cisd")]
        if mac_sel == "ON":
            sub = sub[sub["f_macro_ssmt"]]
        elif mac_sel == "OFF":
            sub = sub[~sub["f_macro_ssmt"]]
        if mic_sel == "ON":
            sub = sub[sub["f_micro_ssmt"]]
        elif mic_sel == "OFF":
            sub = sub[~sub["f_micro_ssmt"]]
        if cisd_sel == "Any CISD ON":
            sub = sub[sub["f_cisd"]]
        elif cisd_sel == "No CISD (OFF)":
            sub = sub[~sub["f_cisd"]]
        if ent_tf_sel:
            sub = sub[sub["entry_tf"].isin(ent_tf_sel)]
        if tgt_tf_sel:
            sub = sub[sub["target_tf"].isin(tgt_tf_sel)]
        if tgt_type_sel:
            sub = sub[sub["target_type"].isin(tgt_type_sel)]
        if reg_sel:
            sub = sub[sub["structural_regime"].isin(reg_sel)]
        if sess_sel != "ALL":
            sub = sub[sub["session"] == sess_sel]
        if split_sel != "ALL":
            sub = sub[sub["validation_split"] == split_sel]
        sub = sub[(sub["min_from_ny_open_trig"] >= ny_min_rng[0]) & (sub["min_from_ny_open_trig"] <= ny_min_rng[1])]

        m1, m2, m3, m4, m5 = st.columns(5)
        n_tr = len(sub)
        n_opp = int(sub["opportunity_id"].nunique()) if n_tr > 0 else 0
        wr = float((sub["r"] > 0).mean()) if n_tr > 0 else 0.0
        exp_r = float(sub["r"].mean()) if n_tr > 0 else 0.0
        tot_r = float(sub["r"].sum()) if n_tr > 0 else 0.0
        m1.metric("Toplam İşlem (N)", f"{n_tr:,}")
        m2.metric("Bağımsız Fırsat Sayısı", f"{n_opp:,}")
        m3.metric("Win Rate", f"{wr * 100:.2f}%")
        m4.metric("Net Expectancy (R)", f"{exp_r:+.4f} R")
        m5.metric("Toplam Realized R", f"{tot_r:+.2f} R")

    st.subheader("2. 64 Çekirdek Binary Faktör Kombinasyonu (`combination_results.parquet` — LONG vs SHORT vs BOTH)")
    if len(comb_res) > 0:
        sc_f = st.selectbox("Oturum Kapsamı:", sorted(comb_res["scope"].unique()), index=1 if "NY_Open_0930_1100" in comb_res["scope"].values else 0)
        dir_f = st.selectbox("64 Kombinasyon Yön Filtresi:", ["BOTH", "LONG", "SHORT"])
        c_sub = comb_res[(comb_res["scope"] == sc_f) & (comb_res["direction"] == dir_f)].sort_values("expectancy_r", ascending=False)
        st.dataframe(c_sub, use_container_width=True)
        st.plotly_chart(
            px.bar(c_sub.head(25), x="base_config_id", y="expectancy_r", color="config_label",
                   title=f"En Yüksek 25 Binary Kombinasyon ({sc_f} — {dir_f}) Net Expectancy (R)"),
            use_container_width=True,
        )

    st.subheader("3. 15 Strateji Ailesi Alt Kümesi (`{QT, ICT, CRT, MMXM}` — `v3_family_15_subsets.parquet`)")
    if len(fam_15) > 0:
        st.dataframe(fam_15, use_container_width=True)

# ============================================================================
# V3 MODULE B — FRACTAL STRUCTURE EXPLORER (SECTION 19.B)
# ============================================================================
elif panel_choice.startswith("V3 Module B"):
    st.header("V3 Module B — Fractal Structure Explorer (W1 / D1 / H6 / H4 / H2 / H1 / M90 / M30 / M15 / M5 / M3 / M1)")
    tf_mat = load_table("timeframe_alignment_matrix")
    pre_df = load_table("pretrade_narratives")
    graph_df = load_table("fractal_narrative_graph")

    if len(tf_mat) > 0:
        lvl_sel = st.selectbox("Fraktal Hiyerarşi Seviyesi:", ["ALL"] + sorted(tf_mat["hierarchy_level"].unique()))
        dir_b = st.selectbox("Yön:", ["BOTH", "LONG", "SHORT"], key="modb_dir")
        tsub = tf_mat[tf_mat["direction"] == dir_b].copy()
        if lvl_sel != "ALL":
            tsub = tsub[tsub["hierarchy_level"] == lvl_sel]
        st.subheader("Çoklu Zaman Dilimi Uyum Matrisi (Pairs, Triples & 4-Timeframe Quads)")
        st.dataframe(tsub.sort_values("expectancy_r", ascending=False), use_container_width=True)
        st.plotly_chart(
            px.bar(tsub.sort_values("expectancy_r", ascending=False).head(30),
                   x="structure_chain", y="expectancy_r", color="alignment_state", barmode="group",
                   title=f"Fraktal Zaman Dilimi Zincirleri ({dir_b}) Net Expectancy (R)"),
            use_container_width=True,
        )

    st.subheader("Pre-Trade 16-Soruluk Nedensel Narrative Kayıtları (`pretrade_narratives.parquet`)")
    if len(pre_df) > 0:
        st.dataframe(pre_df.head(200), use_container_width=True)

    st.subheader("Nedensel Olay Grafiği Kenarları (`fractal_narrative_graph.parquet`)")
    if len(graph_df) > 0:
        st.dataframe(graph_df.head(200), use_container_width=True)

# ============================================================================
# V3 MODULE C — ENTRY-TO-TARGET TIMEFRAME MATRIX (SECTION 19.C)
# ============================================================================
elif panel_choice.startswith("V3 Module C"):
    st.header("V3 Module C — Entry-to-Target Timeframe Matrix (Lower-to-Higher & Higher-to-Lower Targets)")
    st.info(
        "**Bölüm 1 & 7 Zorunlu Kuralı:** Hedef zaman dilimi giriş/yapı zaman diliminden DAHA BÜYÜK (`M5 MMXM → H1/H4/D1/W1 Likidite`), "
        "DAHA KÜÇÜK (`H1/H4 Reversal → M5/M15 Original Consolidation`) veya EŞİT olabilir."
    )
    et_mat = load_table("entry_target_timeframe_matrix")
    pred_res = load_table("target_prediction_results")

    if len(et_mat) > 0:
        rel_sel = st.selectbox(
            "Hedef / Yapı Zaman Dilimi İlişkisi:",
            ["ALL", "LTF_STRUCT_TO_HTF_TARGET", "HTF_STRUCT_TO_LTF_TARGET", "SAME_TF_STRUCT_TARGET"],
        )
        dir_c = st.selectbox("Yön:", ["ALL", "LONG", "SHORT"], key="modc_dir")
        esub = et_mat[et_mat["qt_phase"] == "ALL_QT"].copy()
        if rel_sel != "ALL":
            esub = esub[esub["tf_hierarchy_relation"] == rel_sel]
        if dir_c != "ALL":
            esub = esub[esub["direction"] == dir_c]

        st.subheader("1. Entry TF × Narrative TF × Target TF × Target Type Performans Tablosu")
        st.dataframe(esub, use_container_width=True)

        piv_et = esub.groupby(["entry_tf", "target_tf"])["expectancy_r"].mean().unstack()
        st.plotly_chart(
            px.imshow(piv_et, text_auto=".3f", aspect="auto", color_continuous_scale="RdYlGn",
                      title="Entry Timeframe (Satır) × Target Timeframe (Sütun) Ortalama Net Expectancy (R)"),
            use_container_width=True,
        )

    st.subheader("2. Hedef Tahmini (Horizon İçinde Ulaşma) vs İşlem Karlılığı (Stop Olmadan Ulaşma) — Bölüm 7.3")
    if len(pred_res) > 0:
        st.dataframe(pred_res, use_container_width=True)
        st.plotly_chart(
            px.scatter(
                pred_res, x="prob_target_reached_horizon", y="prob_trade_reached_before_stop",
                color="tf_relation_to_narrative", size="n_evaluations", hover_data=["narrative_tf", "entry_tf", "target_tf", "target_type", "expectancy_net_r"],
                title="Hedefe Ulaşma Olasılığı (Ham Horizon) vs Stop Olmadan Hedefe Ulaşma Olasılığı (Gerçek İşlem)",
            ),
            use_container_width=True,
        )

# ============================================================================
# V3 MODULE D — MMXM × QT NARRATIVE EXPLORER (SECTION 19.D)
# ============================================================================
elif panel_choice.startswith("V3 Module D"):
    st.header("V3 Module D — 13-Stage Fractal MMXM × Quarterly Theory (6H / 90M / 22.5M) Narrative Explorer")
    mq_df = load_table("mmxm_qt_narrative_matrix")
    mmxm_ev = load_table("mmxm_state_events")

    if len(mq_df) > 0:
        cat_sel = st.selectbox("Analiz Kategorisi:", sorted(mq_df["category"].unique()))
        msub = mq_df[mq_df["category"] == cat_sel].copy()
        st.dataframe(msub, use_container_width=True)
        st.plotly_chart(
            px.bar(msub, x="qt_phase", y="expectancy_r", color="mmxm_stage" if cat_sel != "MMXM_DIRECTIONAL_RELATION_x_QT" else "mmxm_relation",
                   facet_col="direction", barmode="group",
                   title=f"{cat_sel} — QT Evresi × MMXM Net Expectancy (R)"),
            use_container_width=True,
        )

    st.subheader("13-Aşamalı Nedensel MMXM Durum Olayları (`mmxm_state_events.parquet`)")
    if len(mmxm_ev) > 0:
        stg_counts = mmxm_ev.groupby(["tf", "stage_name"]).size().reset_index(name="event_count")
        st.plotly_chart(
            px.bar(stg_counts, x="stage_name", y="event_count", color="tf", barmode="group",
                   title="Timeframe Bazında 13 Aşamalı MMXM Durum Olay Sayıları"),
            use_container_width=True,
        )
        st.dataframe(mmxm_ev.head(200), use_container_width=True)

# ============================================================================
# V3 MODULE E — MACRO/MICRO SSMT 10-STATE EXPLORER (SECTION 19.E)
# ============================================================================
elif panel_choice.startswith("V3 Module E"):
    st.header("V3 Module E — Macro (90M) & Micro (22.5M) SSMT 10-State Explorer")
    ssmt_mat = load_table("macro_micro_ssmt_matrix")
    ssmt_ev = load_table("ssmt_events")

    if len(ssmt_mat) > 0:
        sc_e = st.selectbox("Kapsam:", sorted(ssmt_mat["scope"].unique()), key="mode_sc")
        s_sub = ssmt_mat[ssmt_mat["scope"] == sc_e]
        st.dataframe(s_sub, use_container_width=True)
        st.plotly_chart(
            px.bar(s_sub, x="ssmt_state_10", y="expectancy_r", color="direction", barmode="group",
                   title=f"10 Macro/Micro SSMT Durumu ({sc_e}) — LONG vs SHORT vs BOTH Expectancy (R)"),
            use_container_width=True,
        )

    st.subheader("Atomik SSMT Olay Tablosu (`ssmt_events.parquet`)")
    if len(ssmt_ev) > 0:
        st.dataframe(ssmt_ev.head(200), use_container_width=True)

# ============================================================================
# V3 MODULE F — MULTI-TF CISD COMPARISON (SECTION 19.F)
# ============================================================================
elif panel_choice.startswith("V3 Module F"):
    st.header("V3 Module F — Independent Multi-Timeframe CISD Comparison (No-CISD vs M1/M3/M5/M15/M30/H1/H4)")
    lc_df = load_table("liquidity_cisd_pair_matrix")
    cisd_ev = load_table("multitf_cisd_events")

    if len(lc_df) > 0:
        pool_sel = st.selectbox("Likidite Havuzu:", sorted(lc_df["liquidity_pool"].unique()))
        lsub = lc_df[lc_df["liquidity_pool"] == pool_sel]
        st.dataframe(lsub, use_container_width=True)
        st.plotly_chart(
            px.bar(lsub, x="cisd_subset", y="expectancy_r", color="direction", barmode="group",
                   title=f"Likidite Havuzu ({pool_sel}) × CISD Timeframe Alt Kümesi Net Expectancy (R)"),
            use_container_width=True,
        )

    st.subheader("Bağımsız Multi-TF CISD Olayları (`multitf_cisd_events.parquet`)")
    if len(cisd_ev) > 0:
        st.dataframe(cisd_ev.groupby(["tf", "dir"]).size().reset_index(name="event_count"), use_container_width=True)

# ============================================================================
# V3 MODULE G — NASDAQ 09:30 5-MIN & LONDON OPEN HEATMAP (SECTION 19.G)
# ============================================================================
elif panel_choice.startswith("V3 Module G"):
    st.header("V3 Module G — Nasdaq 09:30 (5-Min / 15-Min) & London Open LONG/SHORT Expectancy Heatmap")
    nq_df = load_table("nq_open_long_short_5min")
    hr_df = load_table("hourly_combination_matrix")
    ldn_df = load_table("v3_ldn_open_long_short")

    if len(nq_df) > 0:
        g_type = st.selectbox("Nasdaq Zaman Izgarası:", sorted(nq_df["grid_type"].unique()))
        dir_g = st.selectbox("Yön Filtresi:", ["BOTH", "LONG", "SHORT"], key="modg_dir")
        nsub = nq_df[(nq_df["grid_type"] == g_type) & (nq_df["direction"] == dir_g)]
        piv_nq = nsub.pivot(index="narrative_cohort", columns="window", values="expectancy_r")
        st.plotly_chart(
            px.imshow(piv_nq, text_auto=".2f", aspect="auto", color_continuous_scale="RdYlGn",
                      title=f"Nasdaq Açılış Isı Haritası ({g_type} — {dir_g}) Net Expectancy (R)"),
            use_container_width=True,
        )
        st.dataframe(nsub, use_container_width=True)

    st.subheader("24 Saatlik & 30 Dakikalık Tam Gün Matrisi (`hourly_combination_matrix.parquet`)")
    if len(hr_df) > 0:
        st.dataframe(hr_df, use_container_width=True)

    st.subheader("London 08:00 Açılış LONG / SHORT Matrisi (`v3_ldn_open_long_short.parquet`)")
    if len(ldn_df) > 0:
        st.dataframe(ldn_df, use_container_width=True)

# ============================================================================
# V3 MODULE H — ORIGINAL CONSOLIDATION & LIQUIDITY TARGET MAP (SECTION 19.H)
# ============================================================================
elif panel_choice.startswith("V3 Module H"):
    st.header("V3 Module H — Original Consolidation (`original_consolidations.parquet`) & Liquidity Event Map")
    oc_df = load_table("original_consolidations")
    liq_df = load_table("liquidity_events")
    tc_df = load_table("target_candidates")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("OriginalConsolidations (M1..H4)")
        if len(oc_df) > 0:
            oc_sum = oc_df.groupby(["tf", "target_dir"]).agg(
                oc_count=("oc_id", "count"),
                mean_range_pts=("range_pts", "mean"),
                mean_width_atr=("atr_norm_width", "mean"),
                mean_revisits=("revisit_count", "mean"),
            ).reset_index()
            st.dataframe(oc_sum, use_container_width=True)
            st.dataframe(oc_df.head(100), use_container_width=True)
    with c2:
        st.subheader("Liquidity Events (`liquidity_events.parquet`)")
        if len(liq_df) > 0:
            l_sum = liq_df.groupby(["source_tf", "interaction_type", "hypothesis_mode"]).size().reset_index(name="count")
            st.dataframe(l_sum, use_container_width=True)
            st.dataframe(liq_df.head(100), use_container_width=True)

    st.subheader("Aday Hedef Havuzu (`target_candidates.parquet`)")
    if len(tc_df) > 0:
        st.dataframe(tc_df.head(150), use_container_width=True)

# ============================================================================
# V3 MODULE I — STRATEGY ABLATION (SECTION 19.I)
# ============================================================================
elif panel_choice.startswith("V3 Module I"):
    st.header("V3 Module I — Complete Factor Ablation & Reversal vs Continuation Matrix")
    ab_df = load_table("strategy_ablation_results")
    rc_df = load_table("reversal_vs_continuation_matrix")

    if len(ab_df) > 0:
        sc_i = st.selectbox("Oturum Kapsamı:", sorted(ab_df["scope"].unique()), key="modi_sc")
        asub = ab_df[ab_df["scope"] == sc_i]
        st.subheader("9 Çekirdek Faktörün Marjinal Katkısı (ON vs OFF Delta Expectancy R)")
        st.dataframe(asub, use_container_width=True)
        st.plotly_chart(
            px.bar(asub, x="factor_name", y="marginal_delta_expectancy_r", color="direction", barmode="group",
                   title=f"Faktör Eklendiğinde Marjinal Net Expectancy Değişimi (Delta R — {sc_i})"),
            use_container_width=True,
        )

    st.subheader("Reversal vs Continuation × Yapısal Rejim Matrisi (`reversal_vs_continuation_matrix.parquet`)")
    if len(rc_df) > 0:
        st.dataframe(rc_df, use_container_width=True)

# ============================================================================
# V3 MODULE J — CAUSAL TRADE REPLAY WITH FUTURE CANDLES HIDDEN (SECTION 19.J)
# ============================================================================
elif panel_choice.startswith("V3 Module J"):
    st.header("V3 Module J — Causal Trade Replay (With Future-Candles-Hidden Step-by-Step Bar Slider)")
    aud = load_table("audit_sample_trades")
    if len(aud) > 0:
        aud["label"] = (
            aud["model_tag"].astype(str)
            + " | sig=" + aud["t_signal_known"].astype(str).str[:16]
            + " | dir=" + np.where(aud["dir"] == -1, "SHORT", "LONG")
            + " | R=" + aud["r"].round(2).astype(str)
            + " | MMXM=" + aud["mmxm_model_label"].astype(str)
        )
        c_top1, c_top2, c_top3 = st.columns([2, 1, 1])
        with c_top1:
            sel_idx = st.selectbox("İşlem Seçin:", range(min(300, len(aud))), format_func=lambda i: aud["label"].iloc[i])
        tr = aud.iloc[sel_idx]
        with c_top2:
            hide_future = st.checkbox("Gelecek Mumları Gizle (Causal Step-by-Step Replay)", value=False)
        with c_top3:
            bars_after_sig = st.slider("Sinyal Anından Sonra Gösterilecek M1 Bar Sayısı:", 0, int(max(60, tr["hold"] + 20)), 0 if hide_future else int(max(60, tr["hold"] + 20)))

        t_open = pd.Timestamp(tr["t_open"])
        t_sig = pd.Timestamp(tr["t_signal_known"])
        t_fill = pd.Timestamp(tr["t_fill"])
        t_sweep = pd.Timestamp(tr["t_sweep"])
        win_start = t_open - pd.Timedelta(minutes=45)
        full_end = t_fill + pd.Timedelta(minutes=int(max(60, tr["hold"] + 20)))
        visible_end = t_sig + pd.Timedelta(minutes=bars_after_sig) if hide_future else full_end
        m1_slice = load_m1_slice(str(win_start), str(visible_end))

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3],
                            subplot_titles=("US100 M1 + CRT/MMXM Range + Next-Bar Open Fill / SL / TP", "US500 M1 (SSMT Karşılaştırma)"))
        fig.add_trace(go.Candlestick(
            x=m1_slice.index, open=m1_slice["open_100"], high=m1_slice["high_100"],
            low=m1_slice["low_100"], close=m1_slice["close_100"], name="US100 M1",
        ), row=1, col=1)
        fig.add_trace(go.Candlestick(
            x=m1_slice.index, open=m1_slice["open_500"], high=m1_slice["high_500"],
            low=m1_slice["low_500"], close=m1_slice["close_500"], name="US500 M1",
        ), row=2, col=1)

        fig.add_hrect(y0=float(tr["Lr"]), y1=float(tr["Hr"]), line_width=1, fillcolor="royalblue", opacity=0.15,
                      annotation_text="Reference Range (H_ref..L_ref)", row=1, col=1)
        fig.add_hline(y=float(tr["px_entry"]), line_dash="solid", line_color="gold", annotation_text=f"Fill {tr['px_entry']:.1f}", row=1, col=1)
        fig.add_hline(y=float(tr["sl_init"]), line_dash="dash", line_color="crimson", annotation_text=f"Stop {tr['sl_init']:.1f}", row=1, col=1)
        if np.isfinite(tr.get("tp_init", np.nan)):
            fig.add_hline(y=float(tr["tp_init"]), line_dash="dash", line_color="limegreen", annotation_text=f"Target {tr['tp_init']:.1f}", row=1, col=1)
        fig.add_vline(x=t_sweep, line_dash="dot", line_color="orange")
        fig.add_vline(x=t_sig, line_dash="dot", line_color="cyan")
        if not hide_future or bars_after_sig >= 1:
            fig.add_vline(x=t_fill, line_dash="dot", line_color="gold")
        fig.update_layout(height=660, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

# ============================================================================
# V3 MODULE K — STATISTICAL ROBUSTNESS & HPC BENCHMARK (SECTION 19.K)
# ============================================================================
elif panel_choice.startswith("V3 Module K"):
    st.header("V3 Module K — Statistical Robustness, OOS Splits, Cost Sensitivity & Hardware Benchmark")
    rob_df = load_table("statistical_robustness")
    if len(rob_df) > 0:
        atype = st.selectbox("Sağlamlık Analiz Türü:", sorted(rob_df["analysis_type"].unique()))
        rsub = rob_df[rob_df["analysis_type"] == atype]
        st.dataframe(rsub, use_container_width=True)
        st.plotly_chart(
            px.bar(rsub, x="slice_label", y="expectancy_r", color="direction", facet_col="cohort", barmode="group",
                   title=f"{atype} — LONG vs SHORT vs BOTH Net Expectancy (R)"),
            use_container_width=True,
        )

    st.subheader("Donanım Otomatik Ayarlama ve Numba Kernel Doğrulama Raporu (`hardware_benchmark.json`)")
    if hw:
        st.json(hw)

# ============================================================================
# V3 MODULE L — 25 RANKINGS, NO-TRADE, 10x100 VALIDATION & V4 HANDOFF (SECTION 19.L)
# ============================================================================
elif panel_choice.startswith("V3 Module L"):
    st.header("V3 Module L — 25 Mandatory Rankings, No-Trade Conditions, 10×100 Manual Validation & V4 Handoff")
    rank_df = load_table("v3_rankings_25")
    val_df = load_table("v3_manual_validation_10x100")
    v4_df = load_table("v4_frozen_candidates")
    val_json = load_json("v3_manual_validation_summary.json")

    st.subheader("1. Bölüm 18 — 25 Zorunlu İstatistiksel Sıralama (`v3_rankings_25.parquet`)")
    if len(rank_df) > 0:
        st.dataframe(rank_df, use_container_width=True)
        st.plotly_chart(
            px.bar(rank_df, x="ranking_category", y="expectancy_r", color="evidence_verdict",
                   error_y=rank_df["ci95_high"] - rank_df["expectancy_r"],
                   title="25 Zorunlu Araştırma Kategorisi Net Expectancy (R) ve %95 Güven Aralığı"),
            use_container_width=True,
        )

    st.subheader("2. Bölüm 20 — 10×100 (1,000 Örnek) Manuel Etiket Doğrulama Veri Seti (`v3_manual_validation_10x100.parquet`)")
    if val_json:
        st.json(val_json)
    if len(val_df) > 0:
        cat_v = st.selectbox("Kategori Seçin (10×100):", ["ALL"] + sorted(val_df["category"].unique()))
        vsub = val_df if cat_v == "ALL" else val_df[val_df["category"] == cat_v]
        st.dataframe(vsub, use_container_width=True)

    st.subheader("3. Faz 16 — V4 Forward-Testing İçin Dondurulmuş Aday Stratejiler (`v4_frozen_candidates.parquet`)")
    if len(v4_df) > 0:
        st.dataframe(v4_df, use_container_width=True)

# ============================================================================
# V2 LEGACY PANELS PRESERVED INTACT
# ============================================================================
elif panel_choice.startswith("V2 Panel 0"):
    st.header("V2 Panel 0 — Legacy 18-Model × Time-of-Day Explorer")
    st.dataframe(load_table("intraday_24h_18models"), use_container_width=True)
    st.dataframe(load_table("ny_5m_15m_18models"), use_container_width=True)
elif panel_choice.startswith("V2 Panel 1"):
    st.header("V2 Panel 1 — Global Session Clock & DST Explorer")
    sel_date = st.date_input("Tarih Seçin (2021–2026):", value=date(2026, 3, 16), min_value=date(2021, 11, 7), max_value=date(2026, 11, 6))
    st.json(clock.session_stamp(sel_date).__dict__)
elif panel_choice.startswith("V2 Panel 2"):
    st.header("V2 Panel 2 — CRT Research")
    st.dataframe(load_table("crt_tf_stats"), use_container_width=True)
    st.dataframe(load_table("crt_variants"), use_container_width=True)
elif panel_choice.startswith("V2 Panel 3"):
    st.header("V2 Panel 3 — CRT × SSMT Matrix")
    st.dataframe(load_table("crt_ssmt_baselines"), use_container_width=True)
    st.dataframe(load_table("crt_ssmt_matrix"), use_container_width=True)
elif panel_choice.startswith("V2 Panel 4"):
    st.header("V2 Panel 4 — QT Fractal & Multi-Anchor Explorer")
    st.dataframe(load_table("qt_fractals"), use_container_width=True)
    st.dataframe(load_table("qt_anchor_comparison"), use_container_width=True)
elif panel_choice.startswith("V2 Panel 5"):
    st.header("V2 Panel 5 — Quarter-to-Quarter Rankings")
    st.dataframe(load_table("q2q_rankings"), use_container_width=True)
    st.dataframe(load_table("multilevel_alignment"), use_container_width=True)
elif panel_choice.startswith("V2 Panel 6"):
    st.header("V2 Panel 6 — Nasdaq Open Research")
    st.dataframe(load_table("ny_open_models"), use_container_width=True)
    st.dataframe(load_table("h1_anchoring"), use_container_width=True)
elif panel_choice.startswith("V2 Panel 7"):
    st.header("V2 Panel 7 — London Open Research")
    st.dataframe(load_table("ldn_18models"), use_container_width=True)
elif panel_choice.startswith("V2 Panel 8"):
    st.header("V2 Panel 8 — Causal MMXM & Narrative Explorer")
    st.dataframe(load_table("narrative_perf"), use_container_width=True)
elif panel_choice.startswith("V2 Panel 9"):
    st.header("V2 Panel 9 — R:R and Stop Research")
    st.dataframe(load_table("rr_stop_exit_grid"), use_container_width=True)
elif panel_choice.startswith("V2 Panel 11"):
    st.header("V2 Panel 11 — Statistical Robustness & Autopsy")
    st.dataframe(load_table("splits_eval"), use_container_width=True)
    st.dataframe(load_table("losing_trades_autopsy"), use_container_width=True)
elif panel_choice.startswith("V2 Panel 12"):
    st.header("V2 Panel 12 — Data Forensics & v1 vs v2 Audit")
    st.dataframe(load_table("data_authenticity_manifest"), use_container_width=True)
    st.dataframe(load_table("v1_vs_v2_comparison"), use_container_width=True)
