# ASTRA 6 — V3 BEFORE VS AFTER RESEARCH RESULTS
## Düzeltmeler Öncesi ve Sonrası Kapsamlı Sayısal Karşılaştırma ve Metrik Değişim Analizi

**Referans Önbellek Snapshot:** `data/results/v3_before_repair_snapshot.json`  
**Güncel Sonuç Tabloları:** `data/results/*.parquet` (29 Tablo + DuckDB)  
**Tarih:** 2026-11-08  
**Değerlendirilen Veri Havuzu:** Dukascopy (2021-11..2026-03) + OANDA (2026-03..2026-11) 5 Yıllık US100/US500/US30 M1 Paneli (1.76M M1 Barı)  

---

## 1. TABLO BOYUTLARI VE EVREN KAPSAMI DEĞİŞİMLERİ (ROW COUNT DELTAS)

Aşağıdaki tablo, 29 analitik araştırma tablosunun onarım öncesi ve sonrası satır sayılarını ve değişim yüzdelerini göstermektedir:

| Tablo Adı | Öncesi (Before) | Sonrası (After) | Fark (Delta) | Değişim Nedeni |
| :--- | :---: | :---: | :---: | :--- |
| `original_consolidations.parquet` | 159,180 | 159,180 | 0 | OC tanımı korundu; onay barı kapanış anına (`m1_close_idx`) eşitlendi. |
| `mmxm_state_events.parquet` | 316,173 | 458,336 | +142,163 | `ext_pos // 4` yapay pencereleme silindi; %100 tam OC evreni üzerinde artırımlı nedensel FSM çalıştırıldı. |
| `multitf_cisd_events.parquet` | 394,880 | 394,880 | 0 | M1, M3, M5, M15, M30, H1, H4 CISD olay evreni eksiksiz korundu. |
| `crt_events.parquet` | 815,053 | 1,315,768 | +500,715 | M3..W1 CRT olay havuzunda örnekleme kaldırıldı, %100 tam evren tarandı. |
| `ssmt_events.parquet` | 440,838 | 440,838 | 0 | US500 ve US30 karşılaştırmalı makro/mikro SSMT olayları korundu. |
| `liquidity_events.parquet` | 641,776 | 1,142,491 | +500,715 | Tam CRT evreni ile genişletilmiş likidite süpürme gölü oluşturuldu. |
| `atomic_events.parquet` | 924,513 | 2,253,795 | +1,329,282 | Örneklenmiş kısmi göl yerine tüm yapısal olayların birleşimi (`FULL_UNIVERSE`). |
| `candidate_opportunities.parquet` | 711,903 | 644,237 | -67,666 | Pre-trade tablosundan yinelenen veya geleceğe bakan sentetik satırlar temizlendi. |
| `pretrade_narratives.parquet` | 425,634 | 375,860 | -49,774 | Post-trade değişkenler tablodan çıkarıldı; yalnızca pre-trade nedensel alanlar korundu. |
| `fractal_narrative_graph.parquet` | 60,808 | 1,127,580 | +1,066,772 | Fraktal grafiğe 1.12M kenar eklenerek tüm zaman dilimi ilişkileri bağlandı. |
| `target_candidates.parquet` | 3,424,568 | 2,658,437 | -766,131 | Geçersiz veya negatif mesafeli hedefler nedensel filtre ile elendi. |
| `target_outcomes.parquet` | 3,424,568 | 2,658,437 | -766,131 | Hedefler gerçek fiyatlarla simüle edildi; timeout'lar mark-to-market yapıldı. |
| `all_trades.parquet` | 711,903 | 644,237 | -67,666 | 644.237 bağımsız tetiklenen işlem (`j_fill = j_exec + 1`). |
| `long_trades.parquet` | 346,436 | 312,574 | -33,862 | LONG yönlü işlemler eksiksiz ve simetrik olarak ayrıldı (%48.5). |
| `short_trades.parquet` | 365,467 | 331,663 | -33,804 | SHORT yönlü işlemler eksiksiz ve simetrik olarak ayrıldı (%51.5). |
| `combination_results.parquet` | 384 | 384 | 0 | 64 kombinasyon × (All_Sessions, NY_Open) × (BOTH, LONG, SHORT). |
| `v3_family_15_subsets.parquet` | 90 | 90 | 0 | 15 strateji ailesi alt kümesi eksiksiz korundu. |
| `timeframe_alignment_matrix.parquet` | 288 | 312 | +24 | 4-TF Quad ve Triple zincirlerinde tüm alt rejimler ayrıldı. |
| `entry_target_timeframe_matrix.parquet` | 1,568 | 1,354 | -214 | Yetersiz örneklemli (<5 işlem) hücreler elendi. |
| `mmxm_qt_narrative_matrix.parquet` | 178 | 253 | +75 | Gerçek MMXM aşama dağılımı ve 90M çeyrek eşleşmesi detaylandırıldı. |
| `macro_micro_ssmt_matrix.parquet` | 55 | 55 | 0 | 10 SSMT durumu × oturum/yön dilimleri eksiksiz. |
| `liquidity_cisd_pair_matrix.parquet` | 181 | 197 | +16 | Gerçek süpürme gecikmesi ve bağımsız CISD zaman dilimi tetiklemeleri. |
| `reversal_vs_continuation_matrix.parquet` | 229 | 44 | -185 | 9 yapısal rejim × yön × hipotez ayrımı temizlendi. |
| `nq_open_long_short_5min.parquet` | 714 | 630 | -84 | Nasdaq 09:30 5M ve 15M öncelikli dilimleri LONG/SHORT olarak modellendi. |
| `hourly_combination_matrix.parquet` | 648 | 576 | -72 | 24 NY saati × yön × model matrisi. |
| `strategy_ablation_results.parquet` | 54 | 54 | 0 | 6 çekirdek faktör marjinal ablasyonu (paired t-test ve delta R). |
| `statistical_robustness.parquet` | 135 | 270 | +135 | Split, yıllık, sağlayıcı ve spread duyarlılığı analizleri genişletildi. |
| `v3_rankings_25.parquet` | 25 | 25 | 0 | Algoritmik arama motoru ile seçilen 25 zorunlu sıralama hücresi. |

---

## 2. MMXM AŞAMA DAĞILIMI DEĞİŞİMİ: YAPAY İNTERPOLASYON VS GERÇEK NEDENSEL FSM

Eski kodda MMXM aşamaları, gelecekteki tepe noktasına göre sabit zaman aralıklarına bölünerek oluşturuluyordu. Bu sebeple 15 aşamanın neredeyse hepsinde yapay olarak ~26.477 adet eşit olay görünmekteydi.

Yeni **Artırımlı FSM (`_run_incremental_mmxm_fsm_numba`)** uygulandığında ise aşamalar piyasanın gerçek yapısal akışını yansıtan doğal bir hiyerarşik süzgeç oluşturmuştur:

```
[Aşama Dağılımı ve Aşama Düşüş Oranları]
Aşama 01 (OC Adayı)         : 46,466 olay (%100.0)
Aşama 02 (Departure Start)  : 46,466 olay (%100.0)
Aşama 03 (Departure Conf.)  : 46,466 olay (%100.0)
  ↓ Judas Swing Gelişimi
Aşama 04 (Judas Swing)      : 39,506 olay (%85.0)  --> %15.0 Judas yapmadan doğrudan gitti
Aşama 05 (Likidite Süpürme) : 39,314 olay (%84.6)
  ↓ Smart Money Reversal
Aşama 06 (SMR Displacement) : 33,619 olay (%72.4)  --> %12.2 SMR yapamadı
Aşama 07 (CISD MSS Kırılım) : 33,493 olay (%72.1)
  ↓ Birikim ve Dağıtım
Aşama 08 (İlk Yeniden Birik): 32,196 olay (%69.3)
Aşama 09 (Konsolidasyon Kır): 32,118 olay (%69.1)
Aşama 10 (İkinci Birikim)   : 32,118 olay (%69.1)
  ↓ Hedefe İlerleme
Aşama 11 (Terminal İvme)    : 19,618 olay (%42.2)  --> %26.9 trendi tamamlayamadı
Aşama 12 (Hedef OC Teması)  : 10,492 olay (%22.6)  --> Orijinal konsolidasyona tam varış
  ↓ Hedef Sonrası / Başarısızlık
Aşama 13 (Hedef Sonrası Dağ):  7,039 olay (%15.1)
Aşama 14 (Gelişirken İptal) : 25,079 olay (%54.0)  --> Karşı yöne stop oldu
Aşama 15 (Zaman Aşımı)      : 14,346 olay (%30.9)  --> 360 bar içinde hedefe/stopa varamadı
```

### Bilimsel Çıkarım:
1. Bir MMXM modelinin başlangıç konsolidasyonundan sonra karşı taraftaki orijinal konsolidasyonuna ulaşma olasılığı koşulsuz olarak yaklaşık **%22.6**'dır.
2. Modellerin **%54.0**'ı gelişim esnasında iptal olmakta (`Stage 14`), **%30.9**'u ise ufuk süresi içinde hedefe varamadan sönümlenmektedir (`Stage 15`).
3. Eski sistemin "her OC bir MMXM üretir ve her aşama eşit süre sonra tetiklenir" varsayımı matematiksel olarak çökmüş; yerine piyasanın gerçek tükeniş dinamikleri gelmiştir.

---

## 3. YAPISAL HEDEF İCRASI DEĞİŞİMİ: EXAMPLE A VE EXAMPLE B

Eski sistemde yapısal hedefler sabit 2R risk/getiri kuralıyla simüle edilip sadece isimle etiketlenirken, timeout'lar da otomatik olarak −1R stop sayılıyordu. 

Yeni sistemde **gerçek hedef fiyatı (`tp_init = target_px`)** ve **mark-to-market timeout** devreye alınmıştır:

### 3.1 Example A: M5 Yapısı → H1 Likidite Hedefi (`M5 -> H1_LIQ`, LONG)

| Metrik | Öncesi (Lookahead + Dummy -1R) | Sonrası (Causal + Mark-to-Market) | Değişim Nedeni |
| :--- | :---: | :---: | :--- |
| **İşlem Sayısı (N)** | 18,441 | 11,017 | Hedef mesafesi filtreleri ve nedensel as-of eşleştirme ile temizlendi. |
| **Ortalama Hedef Mesafesi** | 4.82 R | 3.12 R | Gerçek H1 swing tepe fiyatı kullanıldı. |
| **Ufukta Hedefe Temas Oranı** | %64.40 | %61.85 | Zaman ufku içinde H1 tepeye varış oranı. |
| **Stop Öncesi Hedefe Temas (WR)** | %17.68 | %25.52 | Gerçek hedef fiyatı ve bağımsız M1 onay barı ile dolum yapıldı. |
| **Net Expectancy (R)** | **-0.3567 R** | **-0.2625 R** | **+0.0942 R İyileşme:** Hedefe varamayan işlemler otomatik −1R sayılmayıp son bardaki kâr/zararla mark-to-market kapatıldı. |
| **Kazanma Oranı / Risk Oranı Uyumsuzluğu** | Büyük Uçurum | Gerçekçi Dağılım | Timeout kârlarının realize edilmesi asimetrik cezayı ortadan kaldırdı. |

### 3.2 Example B: H1 Dönüşü → M5 Original Consolidation Hedefi (`H1 -> M5_OC`, SHORT)

| Metrik | Öncesi (Lookahead + Dummy -1R) | Sonrası (Causal + Mark-to-Market) | Değişim Nedeni |
| :--- | :---: | :---: | :--- |
| **İşlem Sayısı (N)** | 14,687 | 10,875 | Yalnızca $t_{\text{known}} \le t_{\text{signal}}$ olan onaylı M5 OC hedefleri eşleştirildi. |
| **Ortalama Hedef Mesafesi** | 1.94 R | 1.82 R | M5 OC orta nokta fiyatı (`midpoint`) hedef alındı. |
| **Ufukta Hedefe Temas Oranı** | %65.70 | %68.14 | H1 dönüşü sonrası M5 OC'ye varış frekansı. |
| **Stop Öncesi Hedefe Temas (WR)** | %34.42 | %36.25 | Temiz hedef teması oranı. |
| **Net Expectancy (R)** | **-0.2256 R** | **-0.1842 R** | **+0.0414 R İyileşme:** Stop olmadan ufuk sonuna gelen işlemlerin pozitif bölgedeki mark-to-market getirileri hesaba katıldı. |

---

## 4. 64 BİNARY KOMBİNASYON: ÖNCESİ VE SONRASI SIRALAMA FARKLARI

64 binary kombinasyon, filtreleme yerine **bağımsız onay barında bağımsız fiyatla (`j_fill = j_exec + 1`)** icra edildiğinde sonuçlar şu şekilde değişmiştir:

| Kombinasyon Kodu | Faktörler | Öncesi Beklenti (R) | Sonrası Beklenti (R) | Değişim $\Delta R$ | Değişim Nedeni |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **CFG64_00** | Pure Baseline (Tüm Filtreler Kapalı) | -0.2845 R | -0.2912 R | -0.0067 R | Yalnızca kayma/spread maliyetiyle net piyasa sürtünmesi. |
| **CFG64_34** | CRT + CISD | -0.2432 R | -0.2618 R | -0.0186 R | CISD onayı beklenirken fiyatın hareket etmesi (slippage/execution lag). |
| **CFG64_35** | CRT + CISD + MMXM | -0.1754 R | -0.2544 R | **-0.0790 R** | **Gelecek sızıntısı kaldırıldı!** Eski sahte kârlılık yok oldu. |
| **CFG64_51** | CRT + MacroSSMT + CISD + MMXM | -0.2136 R | -0.2684 R | -0.0548 R | MMXM FSM nedenselliği ve gün-kümelenmiş hata etkisi. |
| **CFG64_56** | CRT + MacroSSMT + MicroSSMT | -0.2612 R | -0.1977 R | +0.0635 R | Yüksek filtreleme nedeniyle küçük örneklem ($N=506$). |
| **CFG64_63** | Tüm Faktörler Aktif (Full Narrative) | -0.2439 R | -0.2715 R | -0.0276 R | Aşırı kısıtlama ($N=3,748$) ve çoklu teyit gecikmesi. |

### Önemli Çıkarım:
Önceki sürümde MMXM içeren kombinasyonların (`CFG64_35`, `CFG64_51`) görece "daha az negatif" çıkmasının tek nedeni, `build_fractal_mmxm_state_events` içindeki **lookahead bias** idi. Gerçek zamanlı FSM kurulduğunda, MMXM faktörü tek başına mucizevi bir kârlılık üretmemekte, genel piyasa sürtünmesine paralel negatif bir dağılım sergilemektedir.

---

## 5. BÖLÜM 18 — 25 ZORUNLU İSTATİSTİKSEL SIRALAMA KATEGORİSİ

Algoritmik sıralama motoru (`_select_genuine_25_rankings`) tarafından bağımsız olarak taranan ve Benjamini-Hochberg FDR düzeltmesi uygulanan 25 kategori:

| Sıra | Kategori Adı | Seçilen Aday Strateji | İşlem Sayısı (N) | WR (%) | Net Exp. (R) | Gün Kümelenmiş SE | BH-FDR $q$ | Bilimsel Kanıt Kararı |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **01** | En Yüksek Beklenti (Expectancy) | `CFG64_56_LONG_NY_Open` | 248 | %28.63 | -0.1412 R | 0.0612 | 0.7553 | **NO VERIFIED POSITIVE EDGE** |
| **02** | En Yüksek Win Rate | `H1->M5_OC_SHORT` | 1,277 | %40.17 | -0.2371 R | 0.0274 | 1.0000 | **NO VERIFIED POSITIVE EDGE** |
| **03** | En Yüksek Kâr Faktörü (PF) | `W1_PWH_PWL_M15_CISD` | 412 | %31.55 | -0.1624 R | 0.0481 | 0.8124 | **NO VERIFIED POSITIVE EDGE** |
| **04** | En Düşük Maksimum Drawdown | `CFG64_00_BOTH` | 214,500 | %24.12 | -0.2912 R | 0.0021 | 1.0000 | **NO VERIFIED POSITIVE EDGE** |
| **05** | En Düşük Standart Sapma | `M15_Candle_HL_No_CISD` | 42,110 | %26.04 | -0.2641 R | 0.0048 | 1.0000 | **NO VERIFIED POSITIVE EDGE** |
| **06** | En Yüksek Toplam R | `CFG64_56_BOTH` | 506 | %27.67 | -0.1977 R | 0.0432 | 0.8841 | **NO VERIFIED POSITIVE EDGE** |
| **07** | En Yüksek Ortalama MFE | `M5_MMXM->H1_LIQ_LONG` | 11,017 | %25.52 | -0.2625 R | 0.0094 | 1.0000 | **NO VERIFIED POSITIVE EDGE** |
| **08** | En Düşük Ortalama MAE | `H1_Candle_HL_M1_CISD` | 8,924 | %27.14 | -0.2418 R | 0.0105 | 1.0000 | **NO VERIFIED POSITIVE EDGE** |
| **09** | En Kısa Ortalama Bekleme Süresi | `M1_CISD_Dev_Reclaim` | 31,450 | %25.88 | -0.2512 R | 0.0055 | 0.7553 | **NO VERIFIED POSITIVE EDGE** |
| **10** | En İyi Çoklu Zaman Dilimi Hizalaması | `D1 -> H1 -> M5 Aligned` | 18,420 | %26.74 | -0.2415 R | 0.0072 | 1.0000 | **NO VERIFIED POSITIVE EDGE** |
| **11** | En İyi Çapraz Likidite-Hedef İlişkisi | `M15_Struct -> H4_Target` | 4,210 | %24.18 | -0.2185 R | 0.0152 | 0.9412 | **NO VERIFIED POSITIVE EDGE** |
| **12** | En İyi Reversal Konfigürasyonu | `NY_OR15_Sweep_Reversal` | 6,840 | %27.85 | -0.2214 R | 0.0121 | 0.8920 | **NO VERIFIED POSITIVE EDGE** |
| **13** | En İyi Continuation Konfigürasyonu | `D1_Trend_H1_Continuation` | 14,210 | %25.12 | -0.2684 R | 0.0083 | 1.0000 | **NO VERIFIED POSITIVE EDGE** |
| **14** | En İyi Nasdaq Açılış Modeli | `09:35-09:40_CRT+CISD_LONG` | 3,120 | %28.45 | -0.1845 R | 0.0178 | 0.7812 | **NO VERIFIED POSITIVE EDGE** |
| **15** | En İyi London Açılış Modeli | `08:05-08:10_CRT+SSMT_SHORT` | 1,840 | %29.12 | -0.1912 R | 0.0231 | 0.8145 | **NO VERIFIED POSITIVE EDGE** |
| **16** | En İyi MMXM Aşama Performansı | `Stage_11_Terminal_Target` | 2,410 | %34.12 | -0.1784 R | 0.0204 | 1.0000 | **NO VERIFIED POSITIVE EDGE** |
| **17** | En İyi Quarterly Theory Çeyrek Performansı | `90M_Q2_Manipulation_Sweep` | 24,180 | %26.85 | -0.2475 R | 0.0064 | 1.0000 | **NO VERIFIED POSITIVE EDGE** |
| **18** | En İyi SSMT Uyum Modeli | `04_Both_Aligned_US500_US30` | 8,450 | %27.42 | -0.2312 R | 0.0108 | 0.9124 | **NO VERIFIED POSITIVE EDGE** |
| **19** | En İyi CISD Zaman Dilimi Modeli | `M1+M5_Dual_CISD_Confirmed` | 12,180 | %27.15 | -0.2416 R | 0.0090 | 0.9512 | **NO VERIFIED POSITIVE EDGE** |
| **20** | En İyi OOS Kararlılık Oranı | `CFG64_34_BOTH_OOS` | 16,120 | %26.14 | -0.2485 R | 0.0078 | 1.0000 | **NO VERIFIED POSITIVE EDGE** |
| **21** | En Düşük Maliyet Duyarlılığı | `H4_Target_Wide_Stops` | 5,140 | %23.12 | -0.2245 R | 0.0138 | 1.0000 | **NO VERIFIED POSITIVE EDGE** |
| **22** | En Yüksek Yıllık İstikrar | `CRT_Confirmed_5Year_Stable` | 94,120 | %25.92 | -0.2584 R | 0.0032 | 1.0000 | **NO VERIFIED POSITIVE EDGE** |
| **23** | En Yüksek Örneklem Gücü | `All_Trades_Full_Lake` | 644,237 | %25.68 | -0.2694 R | 0.0012 | 1.0000 | **NO VERIFIED POSITIVE EDGE** |
| **24** | En İyi Yön Simetrisi (LONG vs SHORT) | `NY_Open_CRT_CISD_BOTH` | 18,420 | %27.05 | -0.2418 R | 0.0073 | 1.0000 | **NO VERIFIED POSITIVE EDGE** |
| **25** | V4 Forward-Testing İçin Dondurulan Aday | `CFG64_56_LONG_NY_Open` | 248 | %28.63 | -0.1412 R | 0.0612 | 1.0000 | **NO VERIFIED POSITIVE EDGE** |

---

## 6. ÖZET VE SONUÇ

1. **Hiçbir Kârlılık Sonucu Korunmaya Çalışılmamıştır:** Bağımsız adli denetimin temel talimatına harfiyen uyulmuş; hatalı pozitif kenar üreten sızıntılar temizlendiğinde ortaya çıkan tüm negatif değerler dürüstçe tablolara yansıtılmıştır.
2. **Day-Clustered SE ve FDR Düzeltmesi:** Finansal zaman serilerinde gün içi işlemlerin bağımsız varsayılması standart hatayı yapay olarak 3 ila 5 kat küçük göstermektedir. Liang-Zeger kümelenmiş standart hata ve Benjamini-Hochberg FDR uygulandığında, test edilen 64 çekirdek faktör ve yüzlerce varyantın hiçbirinde sıfır hipotezi ($H_0: \mathbb{E}[R] \le 0$) reddedilememiştir ($q > 0.05$).
3. **V4 Aşamasının Önemi:** 2021–2026 CFD verisi V1, V2 ve V3 boyunca keşfedildiği için, hiçbir in-sample veya split sonucu nihai alpha sayılamaz. Tüm dondurulmuş parametreler V4'te 2026 sonrası gerçek canlı/forward veride test edilmelidir.
