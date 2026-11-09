# ASTRA 6 test kapsamı denetimi

Denetlenen commit `9274803d002a14bc18e0a918d8a90fd615b0ed8f`. Kaynakta 48 test fonksiyonu ve 2.630 pytest case toplandı. Case sayısının büyük çoğunluğu aynı açılış saati testinin tarih parametreleridir. V3.4 checkpoint'teki 67 ve önceki raporlardaki 2.628, bu checkout'un tam collection sayısı değildir.

## Test envanteri

Kategoriler **statik** hazır dosya, sayı veya koşul kontrolü, **şema** alan/etiket kontrolü, **fixture** deterministik yerel girdi, **referans** ayrı hesapla karşılaştırma, **entegrasyon** birkaç canlı fonksiyon veya depolama yolu. Test adının “independent”, “causal” veya “complete” olması kapsamı genişletmez.

### `tests/test_clock_dst.py`

| Fonksiyon ve satır | Kategori | Kanıt / açık |
|---|---|---|
| [`test_transitions_derived_match_statute`](../tests/test_clock_dst.py#L49) | Referans | nth/last Sunday yardımcılarıyla IANA geçiş günlerini karşılaştırır. Kova kapanışını sınamaz. |
| [`test_2026_transition_dates`](../tests/test_clock_dst.py#L57) | Statik | NY/Londra 2026 bilinen günleri. |
| [`test_every_day_open_times`](../tests/test_clock_dst.py#L63) | Parametrik referans | Her gün 09:30 NY/08:00 Londra UTC saati, aynı iki fonksiyon. |
| [`test_test_E_ny_dst_2026`](../tests/test_clock_dst.py#L68) | Statik | NY dört sınır tarihinin açılışı. |
| [`test_test_F_uk_dst_2026`](../tests/test_clock_dst.py#L76) | Statik | Londra dört sınır tarihi. |
| [`test_test_G_mismatch_weeks`](../tests/test_clock_dst.py#L83) | Fixture | İlkbahar/sonbahar farklı DST haftaları ve 330/390 dakika aralık. |
| [`test_local_stamps_independent`](../tests/test_clock_dst.py#L101) | Referans | NY/Londra/İstanbul dönüşümü ve yerel saat. |
| [`test_reference_calendar_flags`](../tests/test_clock_dst.py#L113) | Entegrasyon | Tatil ve erken kapanış üç örnek. Quote panelinin filtrelenmesi yok. |

### `tests/test_qa_suite.py`

| Fonksiyon ve satır | Kategori | Kanıt / açık |
|---|---|---|
| [`test_cat01_timezone_dst_and_multi_anchor_qt`](../tests/test_qa_suite.py#L55) | Fixture ve şema | Saat, üç anchor için fazlar 1–4. Tam 22:30 mikro sınır ve fall-back çift saat karşılaştırması yok. |
| [`test_cat02_data_integrity_and_sha256_manifest`](../tests/test_qa_suite.py#L77) | Hazır artefakt | Hash uzunluğu, etiketi, hazır JSON PASS. Ham veri veya hash yeniden hesaplanmaz. |
| [`test_cat03_crt_detection_and_anchoring`](../tests/test_qa_suite.py#L102) | Fixture ve entegrasyon | Belirli sweep, confirmed/developing ve anchor farkı. Kesit ve eşitlik adversarial kapsamı yok. |
| [`test_cat04_ssmt_detection_and_simultaneous_events`](../tests/test_qa_suite.py#L144) | Fixture ve entegrasyon | Bir CRT/SMT örneği ve micro count ≥1. Eşzamanlı iki event kimliği, yön ve invalidation karşılaştırılmaz. |
| [`test_cat05_true_mtf_cisd_engine`](../tests/test_qa_suite.py#L171) | Fixture ve şema | Dört TF'de kolon, varsa close/ref eşitsizliği. Hiç olay çıkmazsa koşullu kontroller atlanır. M30/H1/H4 ve ilk icra sınırı yok. |
| [`test_cat06_causal_mmxm_state_machine`](../tests/test_qa_suite.py#L190) | Statik | V2 hazır trade_features aşamaları ve MMBM etiketlerinin iç tutarlılığı. V3 raw→OC→FSM kapsamı yok. |
| [`test_cat07_next_bar_trade_execution_and_quarter_continuation`](../tests/test_qa_suite.py#L209) | Statik + fixture | V2 fill indeksleri ve QT sınırını geçen timeout. Kayıp bar ve politika-specific saat yok. |
| [`test_cat08_portfolio_financial_accounting`](../tests/test_qa_suite.py#L236) | Elle hesaplı fixture | LONG, TP ve aynı bar SL önceliği. SHORT, portföy riski ve gap yok. |
| [`test_cat09_statistical_validation_and_zero_future_leakage`](../tests/test_qa_suite.py#L275) | Statik + sınırlı entegrasyon | V2 `dev_cisd` M15'te 100 sonrası fiyat perturbation, 90 öncesi sütunlar. V3 MMXM, hedef, politikalar yok. |
| [`test_cat10_report_consistency_and_500_audit_samples`](../tests/test_qa_suite.py#L322) | Hazır artefakt + metin entegrasyonu | Dosya boyutu, JSON 500 PASS, V2 HTML'de tek sayı. V3.4 PDF/JSON/Parquet eşlemesi veya audit rerun yok. |

### `tests/test_v3_fractal_qa.py`

| Fonksiyon ve satır | Kategori | Kanıt / açık |
|---|---|---|
| [`test_v3_all_28_mandatory_parquet_tables_exist_and_non_empty`](../tests/test_v3_fractal_qa.py#L40) | Statik | Dosya ve >0 satır. Olay içeriği yok. |
| [`test_v3_all_64_binary_configurations_and_directions`](../tests/test_v3_fractal_qa.py#L48) | Statik | 64 registry etiketi ve pozitif sayı/yön. Motor çağrısı yok. |
| [`test_v3_all_15_strategy_family_subsets_distinct_from_64_core`](../tests/test_v3_fractal_qa.py#L60) | Statik | 15 ayrı aile etiketi. Aynı ortak sonuç havuzu kullanılabilir. |
| [`test_v3_long_short_symmetry_and_trade_table_partition`](../tests/test_v3_fractal_qa.py#L70) | Şema/statik | Bölüm ve ID sayıları, `known<=entry`. Ekonomik yön simetrisi yok. |
| [`test_v3_independent_multitf_cisd_and_subsets`](../tests/test_v3_fractal_qa.py#L99) | Şema | Yedi TF ve subset isimleri. Kendi seri/kapanış kanıtı yok. |
| [`test_v3_macro_micro_ssmt_10_states`](../tests/test_v3_fractal_qa.py#L114) | Şema | Hazır 10 durum adı. Çelişki ve eksik comparator gerçek davranışı yok. |
| [`test_v3_original_consolidation_and_13_stage_mmxm_chronology`](../tests/test_v3_fractal_qa.py#L124) | Statik | Olay sıraları ve 1–15 aşama varlığı. Geç bilgiyle geriye yazılmış olaylar da geçer. |
| [`test_v3_cross_timeframe_alignment_pairs_triples_quads`](../tests/test_v3_fractal_qa.py#L139) | Statik | Hazır TF zinciri dizgileri. Bağımsız event bağlantısı yok. |
| [`test_v3_entry_to_target_hierarchy_independence_and_examples_a_b`](../tests/test_v3_fractal_qa.py#L165) | Statik | TF ilişkileri, iki hücre, hedef-before-stop oranı. Fiyat, ID ve ilk bilinebilir zaman yok. |
| [`test_v3_reference_vs_numba_kernel_exact_match`](../tests/test_v3_fractal_qa.py#L186) | Referans fixture | Benchmark iki çekirdeği aynı üretilen dizide karşılaştırır. Aynı varsayımlar ve pazar fiyatı yok. |
| [`test_v3_nasdaq_0930_5min_and_configuration_statuses`](../tests/test_v3_fractal_qa.py#L193) | Statik | Açılış kovaları ve statüler. Fiilî fill saati yok. |
| [`test_v3_25_rankings_and_manual_validation_10x100_and_duckdb`](../tests/test_v3_fractal_qa.py#L205) | Statik + depolama entegrasyonu | 25/1000/kategori, view count. Satırların insan doğrulaması iddia edilmez. |
| [`test_p0_1_mmxm_incremental_prefix_invariance`](../tests/test_v3_fractal_qa.py#L229) | İç FSM fixture | Dört sabit OC, stage numarası ve indeksi. OC oluşturma, terminal, fiyatlar, as-of ve gerçek panel yok. |
| [`test_p0_2_oc_confirmation_boundary_timing`](../tests/test_v3_fractal_qa.py#L273) | Statik | `candidate<=confirm` ve `known>=candidate`. `known>=confirm` ve gerçek kapanış bağı test edilmez. |
| [`test_p0_3_true_mmxm_asof_join_and_independent_mmxm_tf`](../tests/test_v3_fractal_qa.py#L288) | Statik örnek | 100 ID→TF eşleşmesi, tanınmayan ID koşullu atlanır. Stage as-of ve terminal yok. |
| [`test_p0_4_independent_strategy_execution`](../tests/test_v3_fractal_qa.py#L308) | Statik | Çeşitli N ve WR. Sonradan maskeleme ile de geçebilir. |
| [`test_p0_5_target_consistent_execution_and_timeout_mtm`](../tests/test_v3_fractal_qa.py#L323) | Fixture + referans | LONG temassız MTM, iki kernel eşitliği. Giriş anında hedef kaynağı ve gap yok. |
| [`test_p0_6_cisd_confirmation_delay_valid_sweeps`](../tests/test_v3_fractal_qa.py#L363) | Statik | Toplulaştırılmış gecikme ≥0. İlk teyit, saat farkı ve eksik sweep sınıflaması yok. |
| [`test_p1_7_complete_event_universe_coverage`](../tests/test_v3_fractal_qa.py#L373) | Statik | Minimum satır ve bir coverage etiketi. Tam evren, tarih ve kaynak karşılaştırılmaz. |
| [`test_p1_8_causal_pretrade_snapshots_zero_leakage`](../tests/test_v3_fractal_qa.py#L386) | Şema | Yasak sütun isimleri yok. Eski bağlamdan gelen gelecekteki seviyeyi göremez. |
| [`test_p1_9_genuine_ranking_engine_and_honest_verdicts`](../tests/test_v3_fractal_qa.py#L406) | Statik | Hazır sıralama kolonları ve en az bir olumsuz statü. Seçim ve düzeltme bağımsız hesaplanmaz. |
| [`test_p1_10_dependence_aware_statistics_cluster_test`](../tests/test_v3_fractal_qa.py#L421) | Sayısal fixture | Dört küme, SE>0, GA ortalamayı kapsıyor. Exact SE/p ve tek gün sonucu yok. |
| [`test_p1_11_cryptographic_cache_invalidation`](../tests/test_v3_fractal_qa.py#L432) | İzole fixture | Force, config, sürüm. İç dosya mutasyonu ve gerçek Parquet içeriği sınanmıyor. |
| [`test_p1_12_hardware_benchmark_and_zero_duplication`](../tests/test_v3_fractal_qa.py#L455) | Statik | Hazır JSON pozitif RAM ve true kernel flag. Tekilleşme testi yok. |
| [`test_manual_excel_trade_log_integrity`](../tests/test_v3_fractal_qa.py#L470) | Gerçek dosya regresyonu | 18/13/5, toplam ve Trade ID 2. Kaydedilmiş R'nin fiyatla doğrulanması yok. |
| [`test_true_factorial_same_event_different_policies`](../tests/test_v3_fractal_qa.py#L536) | Mock olay + gerçek panel | Üç elle verilen tetik ile yardımcı çağrılır. 64 loop, eligibility ve assert edilen stop/fiyat yok. |
| [`test_forensic_structural_target_vs_fixed_2r_inspection`](../tests/test_v3_fractal_qa.py#L606) | Tarihsel artefakt regresyonu | Tek H1_OC sonucu önceki sabit rakamlarla kontrol. Ham fiyat ve geçmişteki availability yeniden hesaplanmaz. |
| [`test_multitf_cisd_narrative_integration_unconstrained_baseline`](../tests/test_v3_fractal_qa.py#L643) | Şema | Politika etiketleri. Baseline/absence matematiği yok. |
| [`test_adversarial_single_event_independent_policy_execution`](../tests/test_v3_fractal_qa.py#L659) | Tarihsel artefakt regresyonu | Aynı UEV için CF 00/32 çıktı sayıları. Motor, olay ve fiyat yolunu çalıştırmaz. |
| [`test_adversarial_single_event_multitf_cisd_progression`](../tests/test_v3_fractal_qa.py#L695) | Tarihsel artefakt regresyonu | MTF 4 tetik ve R. `j_exit`, kaynak M1 ve gerçek teyit zamanı sınanmıyor. TF büyüdükçe monoton teyit bu örneğe özgü. |

## Çalıştırma ve kaçak kapsamı

İlk salt okunur seçim **2.595 geçti**, 25 seçilmedi. Üç dosyada genişletilmiş salt okunur koşu 2.619 geçti, 11 seçilmedi. Dokuz uyarı Pandas zaman damgası uyumluluğu ve openpyxl validation okumasıyla ilgiliydi. Yeni yapay fiyat üretmemek için synthetic panel, sentetik benchmark ve sentetik dizi testleri seçilmedi. Tam beş yıllık context'i yalnız mock aday testi için yeniden kurmak kapsam dışı bırakıldı. NumPy günlük R fixture'ı fiyat üretmediği için koşabilir. `pytest` disk cache devre dışı, Numba cache ve test geçici dosyaları denetim dizininde.

Kaynak testlerde açık skip veya xfail işareti bulunmadı. Olay yoksa iç assertion'ı geçebilen `cat05` ve P0.3 koşulları var. `run_pipeline.main` pytest dönüş kodunu kontrol eder. V2 “500” raporu production CRT resample'ı kullanır, SSMT audit micro olaylarını çıkarıp yalnız macro örneği döngüsüne alır, CISD production çıktısının eşitsizliğini kontrol eder ve MMXM hazır V2 etiketlerini okur. `audit_100_completed_trades` gerçek Bid/Ask üzerinde ayrı bar döngüsüdür ama depodaki stop/hedefle başlar. [Denetim kaynakları](../astra6/audit.py#L90), [test çıkış kodu](../run_pipeline.py#L187)

## Eklenen bağımsız kanıt ve gerekli adversarial testler

Bu denetimde üretim test dosyaları değişmedi. 17.000 gerçek M1 ve 11 prefix ile raw→OC→FSM→as-of testi **başarısız**. Tek UEV'nin dört politika sonucu ve ayrı standalone M1, ayrıca dört modelden 32 fiyat yolu yeniden üretildi. Gerçek LONG ve SHORT iki temas ve data-end örnekleri karşılaştırıldı. Bunlar mevcut testlerin önceden kaydedilmiş sonuç kontrolünden ayrı deneylerdir.

- **P0 zaman sözleşmesi.** Bir sonraki kova henüz görünmemiş, nominal kapanışta veri eksik, planlı gap, DST fall-back, 22,5 dakika sınırı, kaynak TF'de son teyit yok. Her kaynak olayın kapanışı ≤ karar ≤ fill.
- **P0 raw prefix.** Yön, event/target fiyat, availability, etkinlik, terminal, OC seçimi, sabit TF warm-up ve as-of satırı dahil. Sadece FSM'nin sabit girdi çıktısına bakma.
- **P0 politika.** İleri macro/micro, geçersiz StdSMT, başka TF CISD, teyit öncesi stop, no-sweep, weekend gap, çoklu anchor, aynı tetik eşitliği, yönü yanlış stop. Aday, plan ve sonuç ayrı kaydedilmeli.
- **P0 hedef.** Model 1/2 geç hedef örnekleri fail closed. Gerçek M15 kapanışı ve OC ID/zamanı ile bağımsız as-of karşılaştırma. Sabit 2R ve yapısal fiyat bire bir kontrol.
- **P1 yürütme.** Her iki yön, touch/gap, aynı bar ambiguity, 360 bar ile 360 takvim dakikası, veri sonu, son barda fill, zaman alanlarının tutarlılığı. Kayıtlı `j_exit`, çıkış fiyatı ve R aynı yürütmeyi anlatmalı.
- **P1 rapor ve inferans.** Boş model fallback'i, M3 p/CI statüsü, Stage 13/4–12 ayrımı, kronolojik DD, aynı UEV eşli etki, gerçek rapor ID/fiyat/timestamp. `known_before_entry` bayrağına güvenmek yerine kaynak zaman farkını assert et.
