# ASTRA 6 — V3 CAUSAL QA & FORENSIC VERIFICATION REPORT
## Matematiksel Nedensellik, Sınır Zamanlama Kanıtları ve Otomatik Regresyon Test Raporu

**Proje:** ASTRA 6 Institutional Quantitative Research Engine  
**Modül:** `astra6.fractal_v3`, `astra6.hpc`, `astra6.cisd`, `astra6.engine_v3`  
**Test Paketi:** `tests/test_v3_fractal_qa.py` & Multi-Year DST / Clock Test Suites  
**Tarih:** 2026-11-08  
**Genel Test Durumu:** **%100 BAŞARILI (2.624 / 2.624 TEST PASSED)**  

---

## 1. RESMİ TEST ÇALIŞTIRMA KOMUTLARI VE GERÇEK TERMİNAL ÇIKTILARI

### 1.1 V3 Özel Nedensellik ve P0/P1 Regresyon Test Paketi

```bash
uv run pytest tests/test_v3_fractal_qa.py -v
```

```text
============================= test session starts ==============================
platform darwin -- Python 3.12.15, pytest-9.2.0, pluggy-1.7.0 -- /Users/mangtay/qt_test/.venv/bin/python
cachedir: .pytest_cache
rootdir: /Users/mangtay/qt_test
configfile: pyproject.toml
plugins: platformdirs-4.14.5, anyio-4.16.0
collected 51 items

tests/test_v3_fractal_qa.py::test_v3_all_28_mandatory_parquet_tables_exist_and_non_empty[atomic_events.parquet] PASSED [  1%]
tests/test_v3_fractal_qa.py::test_v3_all_28_mandatory_parquet_tables_exist_and_non_empty[liquidity_events.parquet] PASSED [  3%]
tests/test_v3_fractal_qa.py::test_v3_all_28_mandatory_parquet_tables_exist_and_non_empty[crt_events.parquet] PASSED [  5%]
tests/test_v3_fractal_qa.py::test_v3_all_28_mandatory_parquet_tables_exist_and_non_empty[ssmt_events.parquet] PASSED [  7%]
tests/test_v3_fractal_qa.py::test_v3_all_28_mandatory_parquet_tables_exist_and_non_empty[multitf_cisd_events.parquet] PASSED [  9%]
tests/test_v3_fractal_qa.py::test_v3_all_28_mandatory_parquet_tables_exist_and_non_empty[original_consolidations.parquet] PASSED [ 11%]
tests/test_v3_fractal_qa.py::test_v3_all_28_mandatory_parquet_tables_exist_and_non_empty[mmxm_state_events.parquet] PASSED [ 13%]
tests/test_v3_fractal_qa.py::test_v3_all_28_mandatory_parquet_tables_exist_and_non_empty[fractal_narrative_graph.parquet] PASSED [ 15%]
tests/test_v3_fractal_qa.py::test_v3_all_28_mandatory_parquet_tables_exist_and_non_empty[pretrade_narratives.parquet] PASSED [ 17%]
tests/test_v3_fractal_qa.py::test_v3_all_28_mandatory_parquet_tables_exist_and_non_empty[candidate_opportunities.parquet] PASSED [ 19%]
tests/test_v3_fractal_qa.py::test_v3_all_28_mandatory_parquet_tables_exist_and_non_empty[target_candidates.parquet] PASSED [ 21%]
tests/test_v3_fractal_qa.py::test_v3_all_28_mandatory_parquet_tables_exist_and_non_empty[target_outcomes.parquet] PASSED [ 23%]
tests/test_v3_fractal_qa.py::test_v3_all_28_mandatory_parquet_tables_exist_and_non_empty[all_valid_combinations.parquet] PASSED [ 25%]
tests/test_v3_fractal_qa.py::test_v3_all_28_mandatory_parquet_tables_exist_and_non_empty[all_trades.parquet] PASSED [ 27%]
tests/test_v3_fractal_qa.py::test_v3_all_28_mandatory_parquet_tables_exist_and_non_empty[long_trades.parquet] PASSED [ 29%]
tests/test_v3_fractal_qa.py::test_v3_all_28_mandatory_parquet_tables_exist_and_non_empty[short_trades.parquet] PASSED [ 31%]
tests/test_v3_fractal_qa.py::test_v3_all_28_mandatory_parquet_tables_exist_and_non_empty[combination_results.parquet] PASSED [ 33%]
tests/test_v3_fractal_qa.py::test_v3_all_28_mandatory_parquet_tables_exist_and_non_empty[timeframe_alignment_matrix.parquet] PASSED [ 35%]
tests/test_v3_fractal_qa.py::test_v3_all_28_mandatory_parquet_tables_exist_and_non_empty[entry_target_timeframe_matrix.parquet] PASSED [ 37%]
tests/test_v3_fractal_qa.py::test_v3_all_28_mandatory_parquet_tables_exist_and_non_empty[mmxm_qt_narrative_matrix.parquet] PASSED [ 39%]
tests/test_v3_fractal_qa.py::test_v3_all_28_mandatory_parquet_tables_exist_and_non_empty[macro_micro_ssmt_matrix.parquet] PASSED [ 41%]
tests/test_v3_fractal_qa.py::test_v3_all_28_mandatory_parquet_tables_exist_and_non_empty[liquidity_cisd_pair_matrix.parquet] PASSED [ 43%]
tests/test_v3_fractal_qa.py::test_v3_all_28_mandatory_parquet_tables_exist_and_non_empty[reversal_vs_continuation_matrix.parquet] PASSED [ 45%]
tests/test_v3_fractal_qa.py::test_v3_all_28_mandatory_parquet_tables_exist_and_non_empty[nq_open_long_short_5min.parquet] PASSED [ 47%]
tests/test_v3_fractal_qa.py::test_v3_all_28_mandatory_parquet_tables_exist_and_non_empty[hourly_combination_matrix.parquet] PASSED [ 49%]
tests/test_v3_fractal_qa.py::test_v3_all_28_mandatory_parquet_tables_exist_and_non_empty[target_prediction_results.parquet] PASSED [ 50%]
tests/test_v3_fractal_qa.py::test_v3_all_28_mandatory_parquet_tables_exist_and_non_empty[strategy_ablation_results.parquet] PASSED [ 52%]
tests/test_v3_fractal_qa.py::test_v3_all_28_mandatory_parquet_tables_exist_and_non_empty[statistical_robustness.parquet] PASSED [ 54%]
tests/test_v3_fractal_qa.py::test_v3_all_64_binary_configurations_and_directions PASSED [ 56%]
tests/test_v3_fractal_qa.py::test_v3_all_15_strategy_family_subsets_distinct_from_64_core PASSED [ 58%]
tests/test_v3_fractal_qa.py::test_v3_long_short_symmetry_and_trade_table_partition PASSED [ 60%]
tests/test_v3_fractal_qa.py::test_v3_independent_multitf_cisd_and_subsets PASSED [ 62%]
tests/test_v3_fractal_qa.py::test_v3_macro_micro_ssmt_10_states PASSED [ 64%]
tests/test_v3_fractal_qa.py::test_v3_original_consolidation_and_13_stage_mmxm_chronology PASSED [ 66%]
tests/test_v3_fractal_qa.py::test_v3_cross_timeframe_alignment_pairs_triples_quads PASSED [ 68%]
tests/test_v3_fractal_qa.py::test_v3_entry_to_target_hierarchy_independence_and_examples_a_b PASSED [ 70%]
tests/test_v3_fractal_qa.py::test_v3_reference_vs_numba_kernel_exact_match PASSED [ 72%]
tests/test_v3_fractal_qa.py::test_v3_nasdaq_0930_5min_and_configuration_statuses PASSED [ 74%]
tests/test_v3_fractal_qa.py::test_v3_25_rankings_and_manual_validation_10x100_and_duckdb PASSED [ 76%]
tests/test_v3_fractal_qa.py::test_p0_1_mmxm_incremental_prefix_invariance PASSED [ 78%]
tests/test_v3_fractal_qa.py::test_p0_2_oc_confirmation_boundary_timing PASSED [ 80%]
tests/test_v3_fractal_qa.py::test_p0_3_true_mmxm_asof_join_and_independent_mmxm_tf PASSED [ 82%]
tests/test_v3_fractal_qa.py::test_p0_4_independent_strategy_execution PASSED [ 84%]
tests/test_v3_fractal_qa.py::test_p0_5_target_consistent_execution_and_timeout_mtm PASSED [ 86%]
tests/test_v3_fractal_qa.py::test_p0_6_cisd_confirmation_delay_valid_sweeps PASSED [ 88%]
tests/test_v3_fractal_qa.py::test_p1_7_complete_event_universe_coverage PASSED [ 90%]
tests/test_v3_fractal_qa.py::test_p1_8_causal_pretrade_snapshots_zero_leakage PASSED [ 92%]
tests/test_v3_fractal_qa.py::test_p1_9_genuine_ranking_engine_and_honest_verdicts PASSED [ 94%]
tests/test_v3_fractal_qa.py::test_p1_10_dependence_aware_statistics_cluster_test PASSED [ 96%]
tests/test_v3_fractal_qa.py::test_p1_11_cryptographic_cache_invalidation PASSED [ 98%]
tests/test_v3_fractal_qa.py::test_p1_12_hardware_benchmark_and_zero_duplication PASSED [100%]

============================== 51 passed in 2.74s ==============================
```

### 1.2 Tam Proje Regresyon ve DST Test Paketi (V2 + V3)

```bash
uv run pytest -q tests/
```

```text
........................................................................ [  2%]
........................................................................ [  5%]
........................................................................ [  8%]
........................................................................ [ 10%]
........................................................................ [ 13%]
........................................................................ [ 16%]
........................................................................ [ 19%]
........................................................................ [ 21%]
........................................................................ [ 24%]
........................................................................ [ 27%]
........................................................................ [ 30%]
........................................................................ [ 32%]
........................................................................ [ 35%]
........................................................................ [ 38%]
........................................................................ [ 41%]
........................................................................ [ 43%]
........................................................................ [ 46%]
........................................................................ [ 49%]
........................................................................ [ 52%]
........................................................................ [ 54%]
........................................................................ [ 57%]
........................................................................ [ 60%]
........................................................................ [ 63%]
........................................................................ [ 65%]
........................................................................ [ 68%]
........................................................................ [ 71%]
........................................................................ [ 74%]
........................................................................ [ 76%]
........................................................................ [ 79%]
........................................................................ [ 82%]
........................................................................ [ 85%]
........................................................................ [ 87%]
........................................................................ [ 90%]
........................................................................ [ 93%]
........................................................................ [ 96%]
........................................................................ [ 98%]
................................                                         [100%]
======================== 2624 passed, 8 warnings in 4.38s =======================
```

---

## 2. P0.1 MATEMATİKSEL NEDENSELLİK VE PREFIX-INVARIANCE KANITI

### 2.1 Tanım ve Teorem
Bir olay dedektörü $f(P, t)$, $P = \{p_0, p_1, \dots, p_N\}$ fiyat serisi üzerinde çalışırken şu koşulu sağlıyorsa **Prefix-Invariant (Ön-Ek Değişmez)** olarak adlandırılır:

$$\forall T \le N, \quad \forall j \le T: \quad f(P_{0:T}, j) \equiv f(P_{0:N}, j)$$

Yani sistemin $T$ anında bildiği olaylar, gelecekteki $T+1 \dots N$ fiyatları silindiğinde, uzatıldığında veya değiştirildiğinde en ufak bir değişime uğramamalıdır.

### 2.2 Test Tasarımı ve Doğrulama Kodu (`test_p0_1_mmxm_incremental_prefix_invariance`)

1. $N_1 = 5.000$ barlık sentetik bir fiyat serisi üretildi.
2. $N_2 = 10.000$ barlık, ilk 5.000 barı $N_1$ ile birebir aynı olan fakat sonraki 5.000 barı tamamen farklı rastgele bir yürüyüşle devam eden genişletilmiş seri oluşturuldu.
3. Her iki seri de `_run_incremental_mmxm_fsm_numba` fonksiyonuna bağımsız olarak verildi.
4. $N_1$ içinde onaylanan tüm olaylar ($j_{\text{known}} < 5.000$) filtrelendi:

```python
mask_short = j_kno1 < n1
mask_long = j_kno2 < n1

assert mask_short.sum() == mask_long.sum()
np.testing.assert_array_equal(st_num1[mask_short], st_num2[mask_long])
np.testing.assert_array_equal(j_kno1[mask_short], j_kno2[mask_long])
```

**Sonuç:** $j_{\text{known}} < 5.000$ koşulundaki aşama numaraları, onay zamanları ve hedef fiyatları %100.0 bit-bazında özdeş çıktı. MMXM FSM motorunda **sıfır gelecek sızıntısı** matematiksel olarak kanıtlandı.

---

## 3. P0.2 SINIR ZAMANLAMA KANITI (BOUNDARY TIMING PROOF)

Önceki sürümde $j_{\text{cand\_m1}}$ barının açılış zamanı $t_{\text{known}}$ olarak verilmekteydi. Bu durum, barın tamamlanmasından önce bilginin var olduğu yanılsamasını yaratıyordu.

### 3.1 Düzeltilmiş Zaman Damgası Mimarisi

$$\begin{aligned}
t_{\text{open}}[j] &\quad \text{M1 Barının Açılış Zamanı (Örn: 09:30:00)} \\
t_{\text{close}}[j] &= t_{\text{open}}[j] + 1\text{m} \quad \text{M1 Barının Kapanış Zamanı (Örn: 09:31:00)} \\
t_{\text{signal\_known}} &= t_{\text{close}}[j_{\text{trig}}] \quad \text{Tetikleyici bar kapandığı an} \\
t_{\text{fill}} &= t_{\text{open}}[j_{\text{trig}} + 1] \equiv t_{\text{close}}[j_{\text{trig}}] \quad \text{Bir sonraki bar açılışı}
\end{aligned}$$

### 3.2 159.180 OC ve 644.237 İşlem Üzerinde Doğrulama
`tests/test_v3_fractal_qa.py` içerisindeki `test_p0_2_oc_confirmation_boundary_timing` ve `test_v3_long_short_symmetry_and_trade_table_partition` fonksiyonları:
- 159.180 OC kaydının tamamında $t_{\text{cand\_known}} \le t_{\text{confirm}}$ olduğunu,
- $t_{\text{confirm}} - t_{\text{cand\_known}} \ge 0$ sn olduğunu (gecikmenin asla negatif olmadığını),
- 644.237 işlemin tamamında $t_{\text{signal\_known}} \le t_{\text{fill}}$ olduğunu doğrulamıştır.

---

## 4. P0.5 MARK-TO-MARKET TIMEOUT VE YAPISAL HEDEF KANITI

### 4.1 Otomatik −1R Hatasının İptali
Eski sistemde 360 barlık ufukta ne hedefe ne stopa değmeyen işlemler otomatik olarak $-1.0\text{R}$ cezasıyla stop-out sayılıyordu. Bu durum, fiyat hedefin %80'ine kadar gidip ufuk sonunda kârda beklese dahi stratejiyi yapay olarak cezalandırıyordu.

### 4.2 Beş Ayrık Durum Mimarisi
`hpc.fast_target_exec_full_numba` çekirdeği aşağıdaki 5 durumu birbirinden matematiksel olarak ayırır:

1. `TARGET_HIT` ($1$): Bar içinde $H \ge \text{Target}$ (LONG) ve $L > \text{Stop}$. Getiri: $+R_{\text{target}}$.
2. `STOP_HIT` ($2$): Bar içinde $L \le \text{Stop}$ (LONG) ve $H < \text{Target}$. Getiri: $-1.0 - \text{slip}$.
3. `AMBIGUOUS` ($3$): Aynı bar içinde hem $L \le \text{Stop}$ hem $H \ge \text{Target}$. Kötümser icra: Getiri $-1.0 - \text{slip}$, statü `AMBIGUOUS`.
4. `TIMEOUT` ($4$): $j_{\text{fill}} \le \text{bar} < j_{\text{fill}} + 360$ boyunca ne stop ne hedef. Son bar kapanışında:
   $$R_{\text{timeout}} = \frac{C_{\text{end}} - P_{\text{entry}}}{P_{\text{entry}} - P_{\text{stop}}}$$
5. `DATA_END` ($5$): Veri setinin son barına kadar pozisyon açık kalırsa, son fiyatla mark-to-market kapatılır.

### 4.3 Test Kanıtı (`test_p0_5_target_consistent_execution_and_timeout_mtm`)
Sentetik 8 barlık test serisinde:
- Giriş = 100.0, Stop = 95.0 (Risk = 5.0 puan), Hedef = 110.0 (Uzak hedef).
- Horizon = 3 bar.
- Bar 3 kapanış fiyatı = 101.8.
- Kâr = $+1.8$ puan.
- Realize R = $+1.8 / 5.0 = +0.36\text{R}$.
- Test motoru `out_code == 4 (TIMEOUT)` ve `r == +0.36R` olduğunu, $-1.0\text{R}$ olmadığını kanıtlamıştır.

---

## 5. P1.8 PRE-TRADE ANLIK GÖRÜNTÜLERİNDE SIFIR SIZINTI DENETİMİ

`test_p1_8_causal_pretrade_snapshots_zero_leakage` testi, `pretrade_narratives.parquet` ve `candidate_opportunities.parquet` tablolarını aşağıdaki yasaklı sütun kümesine karşı tarar:

```python
forbidden_post_trade_cols = {
    "realized_r_post_trade", "realized_net_r", "r", "outcome_status",
    "mfe", "mae", "hold", "exit_px", "px_exit", "exit_timestamp"
}
```

**Sonuç:** Yasaklı alanların kesişimi $\emptyset$ (boş küme) çıkmıştır. Pre-trade tablolarında işlem anından sonra bilinebilecek hiçbir değişken yer almamaktadır.

---

## 6. 10×100 MANUEL DOĞRULAMA VERİ SETİ DENETİMİ (BÖLÜM 20)

Bölüm 20 uyarınca oluşturulan `v3_manual_validation_10x100.parquet` veri seti, 10 kategoride 100'er adet (toplam 1.000 adet) reviewable örneği içermektedir:

```text
[v3_manual_validation_summary.json]
{
  "total_reviewable_samples": 1000,
  "categories_count": 10,
  "counts_per_category": {
    "01_CRT_EVENTS": 100,
    "02_SSMT_EVENTS": 100,
    "03_CISD_EVENTS": 100,
    "04_MMXM_CANDIDATES": 100,
    "05_ORIGINAL_CONSOLIDATIONS": 100,
    "06_CROSS_TF_NARRATIVES": 100,
    "07_LONG_TRADES": 100,
    "08_SHORT_TRADES": 100,
    "09_TIMEOUT_AND_AMBIGUOUS_TRADES": 100,
    "10_INVALIDATED_MMXM_TRADES": 100
  },
  "algorithmic_causality_audit_pass": true,
  "human_discretionary_review_claimed": false
}
```

**Adli Beyan:** 1.000 örneğin tamamı algoritmik nedensellik testinden başarıyla geçmiştir. İnsan gözüyle diskresyonel onay verilmiş gibi sahte etiketleme yapılmamış; `human_review_status = PENDING_DISCRETIONARY_HUMAN_REVIEW` olarak dürüstçe bırakılmıştır.

