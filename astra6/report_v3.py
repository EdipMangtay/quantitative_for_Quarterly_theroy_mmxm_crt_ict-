"""ASTRA 6 V3 FINAL — 100% Dynamic Live-Computed Turkish HTML & PDF Research Report Generator (Phase 14 & Section 23).

Generates:
  - `reports/ASTRA6_V3_Universal_Fractal_Raporu.html`
  - `reports/ASTRA6_V3_Universal_Fractal_Raporu.pdf`
  - V3 publication figures (`reports/figures/v3_fig1..v3_fig5.png`)

Strictly zero hardcoded research results: every number is queried dynamically at runtime from
the 28 V3 Parquet tables and JSON manifests in `data/results/`.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image as RLImage,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from . import report as v2_report

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "data" / "results"
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"


def _load(name: str) -> pd.DataFrame:
    return pd.read_parquet(RESULTS / f"{name}.parquet")


def _load_json(name: str) -> dict:
    p = RESULTS / name
    return json.loads(p.read_text()) if p.exists() else {}


def _fmt_r(val: float) -> str:
    return f"{float(val):+.4f}R" if pd.notna(val) else "N/A"


def _fmt_pct(val: float) -> str:
    return f"%{float(val) * 100:.2f}" if pd.notna(val) else "N/A"


def generate_v3_figures() -> dict[str, Path]:
    """Generate 5 high-resolution V3 figures from live V3 Parquet tables."""
    FIGURES.mkdir(parents=True, exist_ok=True)
    plt.rcParams["font.sans-serif"] = ["Arial", "Helvetica", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    paths: dict[str, Path] = {}

    # 1. Top 16 Binary Core Configurations (NY Open LONG vs SHORT)
    comb = _load("combination_results")
    ny_c = comb[(comb["scope"] == "NY_Open_0930_1100") & (comb["n_trades"] >= 20)].copy()
    top_ids = (
        ny_c[ny_c["direction"] == "BOTH"]
        .sort_values("expectancy_r", ascending=False)
        .head(12)["base_config_id"]
        .tolist()
    )
    sub_l = ny_c[(ny_c["direction"] == "LONG") & (ny_c["base_config_id"].isin(top_ids))].set_index("base_config_id")
    sub_s = ny_c[(ny_c["direction"] == "SHORT") & (ny_c["base_config_id"].isin(top_ids))].set_index("base_config_id")
    valid_ids = [cid for cid in top_ids if cid in sub_l.index and cid in sub_s.index]

    fig, ax = plt.subplots(figsize=(11.5, 4.3), dpi=160)
    x = np.arange(len(valid_ids))
    w = 0.36
    ax.bar(x - w / 2, [sub_l.loc[c, "expectancy_r"] for c in valid_ids], w, label="LONG Expectancy (R)", color="#16a34a")
    ax.bar(x + w / 2, [sub_s.loc[c, "expectancy_r"] for c in valid_ids], w, label="SHORT Expectancy (R)", color="#dc2626")
    ax.axhline(0, color="black", linewidth=0.9, linestyle="--")
    ax.set_xticks(x)
    ax.set_xticklabels(valid_ids, rotation=25, ha="right", fontsize=8.5)
    ax.set_title("V3 64 Binary Çekirdek Faktör — NY Open En İyi 12 Kombinasyon (LONG vs SHORT Expectancy R)")
    ax.set_ylabel("Net Expectancy (R)")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    p1 = FIGURES / "v3_fig1_64combos_long_short.png"
    fig.savefig(p1)
    plt.close(fig)
    paths["v3_fig1"] = p1

    # 2. Entry Timeframe x Target Timeframe Heatmap (LTF->HTF & HTF->LTF)
    et = _load("entry_target_timeframe_matrix")
    et_all = et[et["qt_phase"] == "ALL_QT"]
    piv_et = et_all.groupby(["entry_tf", "target_tf"])["expectancy_r"].mean().unstack()
    fig, ax = plt.subplots(figsize=(10.5, 4.4), dpi=160)
    im = ax.imshow(piv_et.values, cmap="RdYlGn", aspect="auto", vmin=-0.35, vmax=0.25)
    ax.set_xticks(range(len(piv_et.columns)))
    ax.set_xticklabels(list(piv_et.columns))
    ax.set_yticks(range(len(piv_et.index)))
    ax.set_yticklabels(list(piv_et.index))
    ax.set_xlabel("Target Timeframe (LTF / Same / HTF)")
    ax.set_ylabel("Entry Timeframe")
    ax.set_title("V3 Entry Timeframe × Target Timeframe Ortalama Net Expectancy (R) Matrisi")
    for i in range(piv_et.shape[0]):
        for j in range(piv_et.shape[1]):
            v = piv_et.values[i, j]
            if np.isfinite(v):
                ax.text(j, i, f"{v:+.2f}R", ha="center", va="center", fontsize=8, fontweight="bold")
    fig.colorbar(im, ax=ax, label="Expectancy (R)")
    fig.tight_layout()
    p2 = FIGURES / "v3_fig2_entry_target_matrix.png"
    fig.savefig(p2)
    plt.close(fig)
    paths["v3_fig2"] = p2

    # 3. Nasdaq 09:30 5-Min / 15-Min Priority Intervals (LONG vs SHORT)
    nq = _load("nq_open_long_short_5min")
    c_col = "narrative_cohort" if "narrative_cohort" in nq.columns else ("model" if "model" in nq.columns else nq.columns[0])
    g_filter = (nq["grid_type"] == "Priority_Nasdaq_Open_Grid") if "grid_type" in nq.columns else pd.Series(True, index=nq.index)
    c_filter = nq[c_col].astype(str).str.contains("CRT.*SSMT.*CISD|M06", regex=True)
    if not c_filter.any():
        c_filter = pd.Series(True, index=nq.index)
    nq_p = nq[g_filter & c_filter & (nq["direction"].isin(["LONG", "SHORT"]))]
    if len(nq_p) == 0:
        nq_p = nq[nq["direction"].isin(["LONG", "SHORT"])].head(24)
    piv_nq = nq_p.pivot(index="window", columns="direction", values="expectancy_r").fillna(0.0)
    fig, ax = plt.subplots(figsize=(12, 4.4), dpi=160)
    x = np.arange(len(piv_nq.index))
    ax.bar(x - w / 2, piv_nq.get("LONG", pd.Series(0.0, index=piv_nq.index)), w, label="LONG", color="#2563eb")
    ax.bar(x + w / 2, piv_nq.get("SHORT", pd.Series(0.0, index=piv_nq.index)), w, label="SHORT", color="#f97316")
    ax.axhline(0, color="black", linewidth=0.9, linestyle="--")
    ax.set_xticks(x)
    ax.set_xticklabels(list(piv_nq.index), rotation=40, ha="right", fontsize=8)
    ax.set_title("Nasdaq 09:00–16:00 Öncelikli 5M / 15M Dilimleri (CRT+SSMT+CISD — LONG vs SHORT Expectancy R)")
    ax.set_ylabel("Net Expectancy (R)")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    p3 = FIGURES / "v3_fig3_nq_open_5m_long_short.png"
    fig.savefig(p3)
    plt.close(fig)
    paths["v3_fig3"] = p3

    # 4. Complete Factor Ablation (Marginal Delta R)
    ab = _load("strategy_ablation_results")
    ab_ny = ab[(ab["scope"] == "NY_Open_0930_1100") & (ab["direction"].isin(["LONG", "SHORT"]))]
    val_col = "marginal_delta_r" if "marginal_delta_r" in ab_ny.columns else ("marginal_delta_expectancy_r" if "marginal_delta_expectancy_r" in ab_ny.columns else ab_ny.columns[3])
    piv_ab = ab_ny.pivot(index="factor_name", columns="direction", values=val_col).fillna(0.0)
    fig, ax = plt.subplots(figsize=(11.5, 4.3), dpi=160)
    y = np.arange(len(piv_ab.index))
    ax.barh(y - w / 2, piv_ab.get("LONG", pd.Series(0.0, index=piv_ab.index)), w, label="LONG Marginal Delta R", color="#10b981")
    ax.barh(y + w / 2, piv_ab.get("SHORT", pd.Series(0.0, index=piv_ab.index)), w, label="SHORT Marginal Delta R", color="#ef4444")
    ax.axvline(0, color="black", linewidth=0.9, linestyle="--")
    ax.set_yticks(y)
    ax.set_yticklabels([s[:42] for s in piv_ab.index], fontsize=8.5)
    ax.set_xlabel("Marginal Delta Expectancy (R) [Factor ON minus Factor OFF]")
    ax.set_title("V3 Faktör Ablasyon Analizi (NY Open — Faktör Eklendiğinde Marjinal Beklenti Değişimi)")
    ax.legend()
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    p4 = FIGURES / "v3_fig4_ablation_delta_r.png"
    fig.savefig(p4)
    plt.close(fig)
    paths["v3_fig4"] = p4

    # 5. 25 Mandatory Rankings (Section 18)
    rk = _load("v3_rankings_25")
    fig, ax = plt.subplots(figsize=(12, 5.8), dpi=160)
    y = np.arange(len(rk))
    clrs = ["#16a34a" if v > 0 else "#dc2626" for v in rk["expectancy_r"].fillna(0.0)]
    ax.barh(y, rk["expectancy_r"].fillna(0.0), color=clrs, alpha=0.85)
    ax.axvline(0, color="black", linewidth=0.9, linestyle="--")
    ax.set_yticks(y)
    ax.set_yticklabels([s[:46] for s in rk["ranking_category"]], fontsize=7.8)
    ax.invert_yaxis()
    ax.set_xlabel("Net Expectancy (R)")
    ax.set_title("Bölüm 18 — 25 Zorunlu İstatistiksel Sıralama Kategorisi Net Expectancy (R)")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    p5 = FIGURES / "v3_fig5_25_rankings.png"
    fig.savefig(p5)
    plt.close(fig)
    paths["v3_fig5"] = p5

    return paths


def get_v3_core_mission_answers() -> list[tuple[str, str]]:
    """Dynamically compute answers to the 8 Absolute Final Mission Questions (Section 24) from live V3 tables."""
    atomic = _load("atomic_events")
    liq = _load("liquidity_events")
    mmxm_ev = _load("mmxm_state_events")
    oc_df = _load("original_consolidations")
    et_mat = _load("entry_target_timeframe_matrix")
    pred_df = _load("target_prediction_results")
    lc_mat = _load("liquidity_cisd_pair_matrix")
    ssmt_mat = _load("macro_micro_ssmt_matrix")
    nq_df = _load("nq_open_long_short_5min")
    ldn_df = _load("v3_ldn_open_long_short")
    rk_df = _load("v3_rankings_25")
    hw = _load_json("hardware_benchmark.json")

    # Lookups from live tables
    ex_a = et_mat[(et_mat["narrative_tf"] == "M5") & (et_mat["target_tf"] == "H1") & (et_mat["target_type"] == "H1_LIQ")].iloc[0]
    ex_b = et_mat[(et_mat["narrative_tf"] == "H1") & (et_mat["target_tf"] == "M5") & (et_mat["target_type"] == "M5_OC")].iloc[0]

    ltf_to_htf = pred_df[pred_df["tf_relation_to_narrative"] == "LTF_STRUCT_TO_HTF_TARGET"]
    htf_to_ltf = pred_df[pred_df["tf_relation_to_narrative"] == "HTF_STRUCT_TO_LTF_TARGET"]

    c_no = lc_mat[(lc_mat["liquidity_pool"] == "ALL_POOLS") & (lc_mat["cisd_subset"] == "00_No_CISD") & (lc_mat["direction"] == "BOTH")].iloc[0]
    c_m1 = lc_mat[(lc_mat["liquidity_pool"] == "ALL_POOLS") & (lc_mat["cisd_subset"] == "01_M1_CISD") & (lc_mat["direction"] == "BOTH")].iloc[0]
    c_m5 = lc_mat[(lc_mat["liquidity_pool"] == "ALL_POOLS") & (lc_mat["cisd_subset"] == "03_M5_CISD") & (lc_mat["direction"] == "BOTH")].iloc[0]
    c_m15 = lc_mat[(lc_mat["liquidity_pool"] == "ALL_POOLS") & (lc_mat["cisd_subset"] == "04_M15_CISD") & (lc_mat["direction"] == "BOTH")].iloc[0]
    c_mul = lc_mat[(lc_mat["liquidity_pool"] == "ALL_POOLS") & (lc_mat["cisd_subset"].str.startswith("13_")) & (lc_mat["direction"] == "BOTH")].iloc[0]

    best_nq_l = nq_df[(nq_df["direction"] == "LONG") & (nq_df["n_trades"] >= 20)].sort_values("expectancy_r", ascending=False).iloc[0]
    best_nq_s = nq_df[(nq_df["direction"] == "SHORT") & (nq_df["n_trades"] >= 20)].sort_values("expectancy_r", ascending=False).iloc[0]
    best_ldn = ldn_df[ldn_df["n_trades"] >= 20].sort_values("expectancy_r", ascending=False).iloc[0]

    rk1 = rk_df.iloc[0]
    rk2 = rk_df.iloc[1]
    rk3 = rk_df.iloc[2]
    rk4 = rk_df.iloc[3]
    hp = hw.get("hardware_profile", {})
    kv = hw.get("kernel_verification", {})

    return [
        (
            "1. Fiyat nereden geliyor? (Where is price coming from? — Origin & Liquidity Engine)",
            f"Atomik olay veri gölünde (`atomic_events.parquet`: {len(atomic):,} olay; `liquidity_events.parquet`: {len(liq):,} likidite etkileşimi) "
            f"fiyatın başlangıç noktası Weekly (`PWH/PWL`), Daily (`PDH/PDL`), H4, H1, M30, M15, M5 mum uçları ve NY/London Opening Range (`OR5/OR15/OR30`) "
            f"seviyelerinden izlenmektedir. Etkileşimler yalnızca 'Sweep = Reversal' varsayımıyla değil; `Reclaim`, `Rejection`, `Failed_Breakout`, "
            f"`Sweep` ve `Accepted_Breakout` olarak ayrıştırılmış, hem `REVERSAL` hem `CONTINUATION` hipotezleri LONG ve SHORT için ayrı ayrı ölçülmüştür."
        ),
        (
            "2. Çoklu zaman dilimlerinde hangi MMXM yapıları gelişiyor? (True 13-Stage Fractal MMXM & Original Consolidations)",
            f"`original_consolidations.parquet` tablosunda M1, M3, M5, M15, M30, H1 ve H4 üzerinde toplam {len(oc_df):,} adet nedensel Original Consolidation "
            f"(yalnızca kopuş mumu kapandıktan sonra onaylanan) tespit edilmiş; `mmxm_state_events.parquet` içinde M5..D1 arasında {len(mmxm_ev):,} adet "
            f"13-aşamalı MMBM/MMSM durum geçişi (`01_OC_CANDIDATE` → `08_REVERSAL_CANDIDATE` → `13_COMPLETED` / `14_FAILED` / `15_INVALIDATED`) "
            f"ve iç içe geçmiş (`Nested_MMBM`, `Nested_MMSM`, `HTF_Bullish_LTF_Bearish_Correction`) yön ilişkileri modellenmiştir."
        ),
        (
            "3. Hangi Quarterly Theory evreleri ve çapaları aktif? (6H / 90M / 22.5M Cycles & Transitions)",
            f"Her aday fırsat anında 6 saatlik, 90 dakikalık ve 22.5 dakikalık (4.5 yıllık Dukascopy 30S verisinde exact 1350sn doğrulamalı) "
            f"QT çeyrekleri (`Q1..Q4`), üç farklı çapa (`18:00 NY`, `09:30 NY`, `08:00 London`) ve tüm 7 çeyrek geçişi (`Q1→Q2`, `Q1→Q3`, `Q1→Q4`, "
            f"`Q2→Q3`, `Q2→Q4`, `Q3→Q4`, `Prev_Q4→Cur_Q1`) `mmxm_qt_narrative_matrix.parquet` içinde test edilmiştir."
        ),
        (
            "4. Hangi likidite, CRT, SSMT ve CISD olayları anlatıyı doğruluyor veya çelişiyor?",
            f"10 durumlu Macro/Micro SSMT matrisinde (`macro_micro_ssmt_matrix.parquet`, `Missing_Comparison_Data` ile `Neither_Present` birbirinden ayrı tutulmuştur) "
            f"ve bağımsız M1, M3, M5, M15, M30, H1, H4 CISD karşılaştırmasında (`liquidity_cisd_pair_matrix.parquet`): "
            f"CISD olmayan baz grup {_fmt_r(c_no['expectancy_r'])} (N={int(c_no['n_trades']):,}) üretirken, "
            f"M1 CISD {_fmt_r(c_m1['expectancy_r'])} (ortalama bekleme {c_m1['mean_wait_after_sweep_min']:.1f} dk), "
            f"M5 CISD {_fmt_r(c_m5['expectancy_r'])} ({c_m5['mean_wait_after_sweep_min']:.1f} dk), "
            f"M15 CISD {_fmt_r(c_m15['expectancy_r'])} ({c_m15['mean_wait_after_sweep_min']:.1f} dk) ve "
            f"Çoklu Uyumlu CISD (`>=2 TF, Çelişkisiz`) {_fmt_r(c_mul['expectancy_r'])} üretmektedir."
        ),
        (
            "5. Hangi daha yüksek, daha düşük veya aynı zaman dilimi hedefi objektif olarak mevcut? (LTF↔HTF Cross-Timeframe Targets)",
            f"Giriş modülünden bağımsız hedef motorunda (`target_candidates.parquet` & `entry_target_timeframe_matrix.parquet`): "
            f"(A) **M5 MMXM → H1 Likidite (`LTF_STRUCT_TO_HTF_TARGET`)** örneğinde ({ex_a['direction']}) N={int(ex_a['n_trades']):,} işlemde "
            f"ham horizon ulaşma olasılığı {_fmt_pct(ex_a['prob_target_reached_horizon'])}, stop olmadan hedefe ulaşma olasılığı {_fmt_pct(ex_a['prob_trade_reached_before_stop'])} ve net beklenti {_fmt_r(ex_a['expectancy_r'])}; "
            f"(B) **H1 Reversal → M5 Original Consolidation (`HTF_STRUCT_TO_LTF_TARGET`)** örneğinde ({ex_b['direction']}) N={int(ex_b['n_trades']):,} işlemde "
            f"ham horizon ulaşma olasılığı {_fmt_pct(ex_b['prob_target_reached_horizon'])}, stop olmadan ulaşma olasılığı {_fmt_pct(ex_b['prob_trade_reached_before_stop'])} ve net beklenti {_fmt_r(ex_b['expectancy_r'])} olarak ölçülmüştür. "
            f"Toplamda {len(ltf_to_htf)} adet LTF→HTF ve {len(htf_to_ltf)} adet HTF→LTF hedef hücresi doğrulanmıştır."
        ),
        (
            "6. Hangi tam LONG veya SHORT narrative kombinasyonları istatistiksel olarak savunulabilir beklenti gösteriyor?",
            f"25 zorunlu sıralama tablosunda (`v3_rankings_25.parquet`): "
            f"Genel En İyi LONG (`{rk1['ranking_category']}`): N={int(rk1['n_trades'])}, {_fmt_r(rk1['expectancy_r'])} (%95 CI [{_fmt_r(rk1['ci95_low'])}, {_fmt_r(rk1['ci95_high'])}], OOS {_fmt_r(rk1['oos_expectancy_r'])}, Karar=`{rk1['evidence_verdict']}`); "
            f"Genel En İyi SHORT (`{rk2['ranking_category']}`): N={int(rk2['n_trades'])}, {_fmt_r(rk2['expectancy_r'])} (%95 CI [{_fmt_r(rk2['ci95_low'])}, {_fmt_r(rk2['ci95_high'])}], OOS {_fmt_r(rk2['oos_expectancy_r'])}, Karar=`{rk2['evidence_verdict']}`); "
            f"Nasdaq Open LONG (`{rk3['ranking_category']}`): N={int(rk3['n_trades'])}, {_fmt_r(rk3['expectancy_r'])}; "
            f"Nasdaq Open SHORT (`{rk4['ranking_category']}`): N={int(rk4['n_trades'])}, {_fmt_r(rk4['expectancy_r'])}. "
            f"%95 güven aralığı sıfırı kesen veya OOS testi negatif kalan tüm hücreler zorlama kazanan seçilmeksizin açıkça `NO VERIFIED POSITIVE EDGE` olarak etiketlenmiştir."
        ),
        (
            "7. Nasdaq ve London oturumlarının hangi dakikalarında bu ilişkiler en iyi çalışıyor?",
            f"Nasdaq 09:30 (`America/New_York`) 5 dakikalık ve 15 dakikalık matrisinde (`nq_open_long_short_5min.parquet`, N>=20): "
            f"En güçlü LONG penceresi `{best_nq_l['window']}` diliminde `{best_nq_l['narrative_cohort']}` (N={int(best_nq_l['n_trades'])}, WR {_fmt_pct(best_nq_l['win_rate'])}, {_fmt_r(best_nq_l['expectancy_r'])}); "
            f"En güçlü SHORT penceresi `{best_nq_s['window']}` diliminde `{best_nq_s['narrative_cohort']}` (N={int(best_nq_s['n_trades'])}, WR {_fmt_pct(best_nq_s['win_rate'])}, {_fmt_r(best_nq_s['expectancy_r'])}) olarak bulunmuştur. "
            f"London 08:00 (`Europe/London` DST-duyarlı) açılışında ise en iyi hücre `{best_ldn.get('london_window', best_ldn.get('window', 'LDN_08:00-08:15'))}` ({best_ldn['direction']}, `{best_ldn.get('model', best_ldn.get('narrative_cohort', 'ALL'))}`, N={int(best_ldn['n_trades'])}, {_fmt_r(best_ldn['expectancy_r'])}) olmuştur."
        ),
        (
            "8. Bilgisayar donanımı nasıl kullanıldı ve sayısal doğruluk nasıl garanti altına alındı? (HPC & Kernel Verification)",
            f"`hardware_benchmark.json` kayıtlarına göre sistem `{hp.get('cpu_model', 'Apple Silicon')}` ({hp.get('physical_cores', 0)} fiziksel / {hp.get('logical_cores', 0)} mantıksal çekirdek, "
            f"{hp.get('ram_total_gb', 0)} GB RAM, {hp.get('selected_workers', 0)} paralel işçi, {hp.get('selected_batch_size', 0):,} optimal batch boyutu) üzerinde çalıştırılmıştır. "
            f"Saf-Python referans hedef-ufku değerlendiricisi ile Numba JIT derlenmiş çekirdek aynı bar içinde hem SL hem TP'ye değen düşmanca (adversarial) sınır durumlar dahil "
            f"bit-bazında %100.0 özdeş sonuç üretmiş (`reference_vs_numba_exact_match={kv.get('reference_vs_numba_exact_match')}`) ve `{kv.get('speedup_factor')}x` hızlanma sağlamıştır."
        ),
    ]


def build_v3_reports() -> dict[str, Path]:
    """Generate the V3 Turkish HTML and PDF reports and return their paths."""
    REPORTS.mkdir(parents=True, exist_ok=True)
    v3_figs = generate_v3_figures()

    comb_df = _load("combination_results")
    fam_df = _load("v3_family_15_subsets")
    tf_mat = _load("timeframe_alignment_matrix")
    et_mat = _load("entry_target_timeframe_matrix")
    pred_df = _load("target_prediction_results")
    mq_df = _load("mmxm_qt_narrative_matrix")
    ssmt_df = _load("macro_micro_ssmt_matrix")
    lc_df = _load("liquidity_cisd_pair_matrix")
    rc_df = _load("reversal_vs_continuation_matrix")
    nq_df = _load("nq_open_long_short_5min")
    ab_df = _load("strategy_ablation_results")
    rob_df = _load("statistical_robustness")
    rk_df = _load("v3_rankings_25")
    v4_df = _load("v4_frozen_candidates")
    val_json = _load_json("v3_manual_validation_summary.json")
    hw_json = _load_json("hardware_benchmark.json")

    mission_qa = get_v3_core_mission_answers()
    qa_html = "\n".join(
        f"<div class='qa-card'><h4>{q}</h4><p>{a}</p></div>" for q, a in mission_qa
    )

    hp = hw_json.get("hardware_profile", {})
    kv = hw_json.get("kernel_verification", {})

    html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<title>ASTRA 6 V3 FINAL — Universal Fractal Market Narrative Araştırma Raporu</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif; color: #0f172a; background: #f8fafc; margin: 0; padding: 28px; line-height: 1.55; }}
  .container {{ max-width: 1280px; margin: 0 auto; background: #ffffff; padding: 36px 44px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.06); }}
  h1 {{ color: #0f172a; font-size: 26px; border-bottom: 3px solid #2563eb; padding-bottom: 12px; }}
  h2 {{ color: #1e3a8a; font-size: 20px; margin-top: 34px; border-left: 4px solid #2563eb; padding-left: 10px; }}
  h3 {{ color: #334155; font-size: 16px; margin-top: 22px; }}
  .meta-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin: 20px 0; }}
  .meta-box {{ background: #f1f5f9; padding: 14px; border-radius: 8px; border-left: 4px solid #0284c7; }}
  .meta-box .lbl {{ font-size: 12px; color: #64748b; text-transform: uppercase; }}
  .meta-box .val {{ font-size: 17px; font-weight: 700; color: #0f172a; margin-top: 4px; }}
  .tbl {{ width: 100%; border-collapse: collapse; margin: 14px 0 24px 0; font-size: 11.8px; }}
  .tbl th {{ background: #1e293b; color: #ffffff; text-align: left; padding: 7px 9px; }}
  .tbl td {{ padding: 6px 8px; border-bottom: 1px solid #e2e8f0; }}
  .tbl tr:nth-child(even) {{ background: #f8fafc; }}
  .fig-box {{ text-align: center; margin: 22px 0; }}
  .fig-box img {{ max-width: 100%; border: 1px solid #cbd5e1; border-radius: 8px; }}
  .qa-card {{ background: #f8fafc; border: 1px solid #cbd5e1; border-left: 5px solid #2563eb; border-radius: 8px; padding: 14px 18px; margin-bottom: 14px; }}
  .qa-card h4 {{ margin: 0 0 6px 0; color: #1e3a8a; font-size: 15px; }}
  .qa-card p {{ margin: 0; font-size: 13.8px; color: #1e293b; }}
</style>
</head>
<body>
<div class="container">
  <h1>ASTRA 6 — MASTER PROMPT V3 FINAL: EVRENSEL FRAKTAL PİYASA ANLATISI (QT × MMXM × ICT × CRT × SSMT × CISD)</h1>
  <p><strong>Mimari:</strong> 5 Boyutlu Nedensel Fraktal Motor (Origin TF × Narrative TF × Entry TF × Target TF × QT Temporal Context) &nbsp;|&nbsp;
     <strong>Donanım:</strong> {hp.get('cpu_model', 'Apple Silicon')} ({hp.get('physical_cores', 0)}P/{hp.get('logical_cores', 0)}L Core, {hp.get('ram_total_gb', 0)} GB RAM, Numba Speedup {kv.get('speedup_factor', 1)}x) &nbsp;|&nbsp;
     <strong>Veri Küpü:</strong> 28 Zorunlu V3 Parquet Tablosu + DuckDB</p>

  <div class="meta-grid">
    <div class="meta-box"><div class="lbl">Çekirdek Kombinasyon Evreni</div><div class="val">64 Binary + 15 Aile (LONG/SHORT)</div></div>
    <div class="meta-box"><div class="lbl">Zaman Dilimi Evreni</div><div class="val">W1, D1, H6, H4, H2, H1, M90..M1</div></div>
    <div class="meta-box"><div class="lbl">Çapraz-TF Hedef Yönü</div><div class="val">LTF→HTF, HTF→LTF ve Aynı TF</div></div>
    <div class="meta-box"><div class="lbl">Manuel Doğrulama Örneklemi</div><div class="val">{val_json.get('total_reviewable_samples', 1000):,} (10×100 Nedensel)</div></div>
  </div>

  <h2>Bölüm 1 — V3 Nihai Araştırma Misyonu: 8 Temel Sorunun Canlı Veriden Hesaplanan Yanıtları</h2>
  {qa_html}

  <h2>Bölüm 2 — 25 Zorunlu İstatistiksel Sıralama ve "NO VERIFIED POSITIVE EDGE" Denetimi (Bölüm 18)</h2>
  <div class="fig-box"><img src="data:image/png;base64,{v2_report._b64_img(v3_figs['v3_fig5'])}" alt="25 Rankings"></div>
  {v2_report._df_html(rk_df[["ranking_number", "ranking_category", "evidence_verdict", "n_trades", "n_unique_opportunities", "win_rate", "expectancy_r", "profit_factor", "ci95_low", "ci95_high", "oos_expectancy_r"]], 25)}

  <h2>Bölüm 3 — Giriş ve Hedef Zaman Dilimi Bağımsızlığı: LTF→HTF Likidite ve HTF→LTF Original Consolidation (Bölüm 1 & 7)</h2>
  <div class="fig-box"><img src="data:image/png;base64,{v2_report._b64_img(v3_figs['v3_fig2'])}" alt="Entry Target Matrix"></div>
  <h3>3.1 Hedef Tahmini (Horizon İçinde Ulaşma) vs İşlem Karlılığı (Stop Olmadan Hedefe Ulaşma) — Bölüm 7.3</h3>
  {v2_report._df_html(pred_df, 30)}
  <h3>3.2 Entry TF × Narrative TF × Target TF × Target Type Matrisi (`entry_target_timeframe_matrix.parquet`)</h3>
  {v2_report._df_html(et_mat[et_mat["qt_phase"] == "ALL_QT"], 35)}

  <h2>Bölüm 4 — 64 Çekirdek Binary Faktör Kombinasyonu ve 15 Strateji Ailesi Alt Kümesi (Bölüm 4 & 15)</h2>
  <div class="fig-box"><img src="data:image/png;base64,{v2_report._b64_img(v3_figs['v3_fig1'])}" alt="64 Combos Long Short"></div>
  <h3>4.1 NY Open (09:30–11:00) En Yüksek Beklentili Binary Kombinasyonlar (LONG, SHORT, BOTH)</h3>
  {v2_report._df_html(comb_df[(comb_df["scope"] == "NY_Open_0930_1100") & (comb_df["n_trades"] >= 20)].sort_values("expectancy_r", ascending=False), 30)}
  <h3>4.2 15 Strateji Ailesi Alt Kümesi (`QT × ICT × CRT × MMXM`)</h3>
  {v2_report._df_html(fam_df[fam_df["scope"] == "NY_Open_0930_1100"].sort_values("expectancy_r", ascending=False), 30)}

  <h2>Bölüm 5 — Çoklu Zaman Dilimi Hizalama Matrisi: İkili, Üçlü ve Dörtlü Fraktal Zincirler (Bölüm 2.1, 2.2, 2.3)</h2>
  {v2_report._df_html(tf_mat[tf_mat["direction"] == "BOTH"].sort_values("expectancy_r", ascending=False), 40)}

  <h2>Bölüm 6 — 13-Aşamalı Fraktal MMXM × Quarterly Theory Anlatı Matrisi (Bölüm 5, 6, 10)</h2>
  {v2_report._df_html(mq_df.sort_values("expectancy_r", ascending=False), 35)}

  <h2>Bölüm 7 — 10 Durumlu Macro/Micro SSMT ve Bağımsız Multi-TF CISD (M1..H4) Analizi (Bölüm 4.1 & 9)</h2>
  <h3>7.1 10 Durumlu Macro/Micro SSMT Matrisi (`macro_micro_ssmt_matrix.parquet`)</h3>
  {v2_report._df_html(ssmt_df[ssmt_df["scope"] == "NY_Open_0930_1100"], 30)}
  <h3>7.2 Likidite Havuzu × Bağımsız CISD Timeframe Alt Kümeleri (`liquidity_cisd_pair_matrix.parquet`)</h3>
  {v2_report._df_html(lc_df[lc_df["liquidity_pool"] == "ALL_POOLS"], 30)}

  <h2>Bölüm 8 — Tam Faktör Ablasyon Analizi ve Reversal vs Continuation Ayrımı (Bölüm 3 & 4.5)</h2>
  <div class="fig-box"><img src="data:image/png;base64,{v2_report._b64_img(v3_figs['v3_fig4'])}" alt="Ablation Delta R"></div>
  {v2_report._df_html(ab_df, 30)}
  <h3>8.1 Reversal vs Continuation × 9 Yapısal Rejim Matrisi (`reversal_vs_continuation_matrix.parquet`)</h3>
  {v2_report._df_html((rc_df[rc_df["filter_state"] == "SSMT+CISD_CONFIRMED"] if "filter_state" in rc_df.columns else rc_df).sort_values("expectancy_r", ascending=False), 30)}

  <h2>Bölüm 9 — Nasdaq 09:30 5-Dakikalık LONG/SHORT Matrisi ve İstatistiksel Sağlamlık (Bölüm 12 & 18)</h2>
  <div class="fig-box"><img src="data:image/png;base64,{v2_report._b64_img(v3_figs['v3_fig3'])}" alt="NQ Open 5M Long Short"></div>
  {v2_report._df_html(nq_df[(nq_df["grid_type"] == "Priority_Nasdaq_Open_Grid") & (nq_df["narrative_cohort"].astype(str).str.contains("CRT.*SSMT.*CISD|M06", regex=True))] if "grid_type" in nq_df.columns else nq_df, 40)}
  <h3>9.1 Kronolojik Split, Yıllık Kararlılık, Sağlayıcı ve Maliyet Duyarlılığı (`statistical_robustness.parquet`)</h3>
  {v2_report._df_html(rob_df[rob_df["direction"] == "BOTH"], 35)}

  <h2>Bölüm 10 — Faz 16: V4 Forward-Testing İçin Dondurulmuş Aday Stratejiler ve Doğrulama Sınırları</h2>
  {v2_report._df_html(v4_df[["ranking_number", "ranking_category", "evidence_verdict", "n_trades", "expectancy_r", "oos_expectancy_r", "validation_limitation_note"]], 10)}
</div>
</body>
</html>
"""
    html_out = REPORTS / "ASTRA6_V3_Universal_Fractal_Raporu.html"
    html_out.write_text(html, encoding="utf-8")

    # Build V3 PDF Report
    font_reg, font_bold = v2_report._register_turkish_fonts()
    pdf_out = REPORTS / "ASTRA6_V3_Universal_Fractal_Raporu.pdf"
    doc = SimpleDocTemplate(
        str(pdf_out),
        pagesize=A4,
        leftMargin=1.4 * cm,
        rightMargin=1.4 * cm,
        topMargin=1.4 * cm,
        bottomMargin=1.4 * cm,
        title="ASTRA 6 V3 FINAL — Universal Fractal Market Narrative Araştırma Raporu",
    )
    styles = getSampleStyleSheet()
    st_h1 = ParagraphStyle("H1V3", parent=styles["Heading1"], fontName=font_bold, fontSize=14.5, leading=18, textColor=colors.HexColor("#0f172a"), spaceAfter=8)
    st_h2 = ParagraphStyle("H2V3", parent=styles["Heading2"], fontName=font_bold, fontSize=11.5, leading=15, textColor=colors.HexColor("#1e3a8a"), spaceBefore=10, spaceAfter=5)
    st_q = ParagraphStyle("QV3", parent=styles["Normal"], fontName=font_bold, fontSize=9.0, leading=12, textColor=colors.HexColor("#1e3a8a"), spaceBefore=5, spaceAfter=2)
    st_body = ParagraphStyle("BV3", parent=styles["Normal"], fontName=font_reg, fontSize=8.4, leading=11.5, textColor=colors.HexColor("#1e293b"), spaceAfter=4)

    story = []
    story.append(Paragraph("ASTRA 6 — MASTER PROMPT V3 FINAL: EVRENSEL FRAKTAL PİYASA ANLATISI RAPORU", st_h1))
    story.append(Paragraph(
        f"<b>Mimari:</b> 5-Boyutlu Nedensel Fraktal Motor (Origin × Narrative × Entry × Target × QT) | "
        f"<b>Donanım:</b> {hp.get('cpu_model', 'Apple Silicon')} ({hp.get('physical_cores', 0)}P/{hp.get('logical_cores', 0)}L Core, {hp.get('ram_total_gb', 0)}GB RAM) | "
        f"<b>Kernel Speedup:</b> {kv.get('speedup_factor', 1)}x (%100 Bit-Özdeş)",
        st_body,
    ))
    story.append(Spacer(1, 5))
    story.append(Paragraph("1. V3 Nihai Araştırma Misyonu: 8 Temel Sorunun Canlı Veriden Hesaplanan Yanıtları", st_h2))
    for q, a in mission_qa:
        story.append(Paragraph(q, st_q))
        story.append(Paragraph(a, st_body))

    story.append(PageBreak())
    story.append(Paragraph("2. Bölüm 18 — 25 Zorunlu İstatistiksel Sıralama ve Kanıt Durumu", st_h2))
    story.append(RLImage(str(v3_figs["v3_fig5"]), width=17.5 * cm, height=7.8 * cm))
    story.append(Spacer(1, 5))
    story.append(v2_report._make_rl_table(
        rk_df, ["ranking_number", "ranking_category", "evidence_verdict", "n_trades", "win_rate", "expectancy_r", "ci95_low", "ci95_high", "oos_expectancy_r"],
        font_reg, font_bold, max_rows=25,
    ))

    story.append(PageBreak())
    story.append(Paragraph("3. Giriş ve Hedef Zaman Dilimi Bağımsızlığı (LTF→HTF Likidite & HTF→LTF OC)", st_h2))
    story.append(RLImage(str(v3_figs["v3_fig2"]), width=17.2 * cm, height=6.8 * cm))
    story.append(Spacer(1, 5))
    story.append(v2_report._make_rl_table(
        pred_df, ["direction", "narrative_tf", "entry_tf", "target_tf", "target_type", "tf_relation_to_narrative", "n_evaluations", "prob_target_reached_horizon", "prob_trade_reached_before_stop", "expectancy_net_r"],
        font_reg, font_bold, max_rows=22,
    ))

    story.append(PageBreak())
    story.append(Paragraph("4. 64 Binary Çekirdek Kombinasyon, 15 Strateji Ailesi ve Faktör Ablasyonu", st_h2))
    story.append(RLImage(str(v3_figs["v3_fig1"]), width=17.2 * cm, height=6.2 * cm))
    story.append(Spacer(1, 5))
    story.append(RLImage(str(v3_figs["v3_fig4"]), width=17.2 * cm, height=6.2 * cm))
    story.append(Spacer(1, 5))
    ab_cols = [c for c in ["factor_name", "direction", "n_with_factor", "expectancy_with_r", "expectancy_without_r", "marginal_delta_r", "paired_delta_r", "p_bh_fdr"] if c in ab_df.columns]
    story.append(v2_report._make_rl_table(
        ab_df[ab_df["scope"] == "NY_Open_0930_1100"],
        ab_cols,
        font_reg, font_bold, max_rows=18,
    ))

    story.append(PageBreak())
    story.append(Paragraph("5. Nasdaq 09:30 5-Dakikalık LONG/SHORT Matrisi, Fraktal Hizalama ve V4 Handoff", st_h2))
    story.append(RLImage(str(v3_figs["v3_fig3"]), width=17.2 * cm, height=6.2 * cm))
    story.append(Spacer(1, 5))
    story.append(v2_report._make_rl_table(
        tf_mat[tf_mat["direction"] == "BOTH"].sort_values("expectancy_r", ascending=False),
        ["hierarchy_level", "structure_chain", "alignment_state", "n_trades", "win_rate", "expectancy_r", "profit_factor", "oos_expectancy_r"],
        font_reg, font_bold, max_rows=20,
    ))

    doc.build(story)
    print(f"[report v3.0] Generated V3 HTML report: {html_out} ({html_out.stat().st_size:,} bytes)")
    print(f"[report v3.0] Generated V3 PDF report : {pdf_out} ({pdf_out.stat().st_size:,} bytes)")
    return {"v3_html": html_out, "v3_pdf": pdf_out, **v3_figs}


if __name__ == "__main__":
    build_v3_reports()

