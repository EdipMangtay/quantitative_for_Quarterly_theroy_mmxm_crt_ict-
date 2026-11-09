# ASTRA 6 bağımsız kaynak denetimi

**Karar** `NOT_VERIFIED` · 9 Kasım 2026  
**Kaynak** `main` · `9274803d002a14bc18e0a918d8a90fd615b0ed8f`

V3.4, 64 konfigürasyon için ayrı sabit 2R yürütme yapıyor. İncelenen tek olayda fiyat yolu ve dört politika sonucu yeniden üretildi. Temel adayın daha geç bilgisinin erken emirlerde kullanılması, MMXM geçmişinin yeni veriyle değişmesi ve yapısal hedeflerin dolumdan sonra belli olması uçtan uca nedenselliği bozuyor. Model 1 ve 2'nin yayımlanan ortalamaları yeniden üretildi. Model 1'de 200/325, Model 2'de 18/792 hedef işlem açıldıktan sonra bilinebilir hale geliyor.

| İnceleme | Belge |
|---|---|
| Giriş noktaları, modüller, veri ve rapor yolları | [Mimari harita](ASTRA6_ARCHITECTURE_MAP.md) |
| Fonksiyonların girdi, hesap, çağrı, test ve durum kaydı | [Fonksiyon kataloğu](ASTRA6_FUNCTION_CATALOG.md) |
| MMXM, QT, CRT, SMT/SSMT, CISD ve Excel | [İşlem mantığı](ASTRA6_TRADING_LOGIC_SEMANTICS.md) |
| Dört model, bağımsız replay, PDF/JSON/SVG | [Sonuç uzlaştırması](ASTRA6_V34_RESULT_RECONCILIATION.md) |
| Testlerin gerçek kapsamı ve eksikler | [Test denetimi](ASTRA6_TEST_COVERAGE_GAPS.md) |
| Sıralı onarımlar | [Onarım planı](ASTRA6_PRIORITY_REPAIR_PLAN.md) |

## Sürüm ve kanıt zinciri

- Başlangıçta yerel Git ağacı temizdi. Yerel HEAD, takip edilen origin/main ve iki GitHub URL'sinin `git ls-remote … refs/heads/main` değeri aynı. V3.3 karşılaştırma commit'i `b501784`. V3.4 PDF, JSON ve SVG'ler HEAD'de izlenir. [Denetlenen commit](https://github.com/EdipMangtay/Quantetive_for_-Quarterly_theroy_mmxm_crt_ict-/commit/9274803d002a14bc18e0a918d8a90fd615b0ed8f)
- Yerel veri yaklaşık 3,1 GiB. Git'in dışladığı altı M1 store dosyası, ham/tick cache, `trade_features`, `target_candidates`, `target_outcomes`, `counterfactual_policy_trades` ve `multitf_cisd_policy_trades` mevcut. Beş sonuç tablosu sırasıyla 633.440, 2.658.888, 2.658.888, 3.685.678 ve 3.302.765 satır. `candidate_opportunities` ve `all_trades` 644.237 satır. DuckDB yerel mutlak yollara bağlanan görünümler. [Git kapsamı](../.gitignore), [görünümler](../astra6/engine_v3.py#L1976)
- 8 Kasım 2026 20:15:42 UTC manifesti ile 14/14 store ve 72/73 sonuç dosyası tam SHA256 eşleşti. `v4_frozen_candidates.parquet` farklı. Manifest `trade_features` ve hedef tablolarını içerir. CF/MTF politika tabloları ve V3.4 audit/narrative/replay çıktıları kapsam dışı. Atomik cache'in **kısmi** SHA'sı `17ddcb9ae521eefd6d881eebb95fcc108fb9d4063b0cca581bdcfaac4fce144f` kayıtla eşleşti. Kaynak commit, tüm sonuç hash'leri, komut ve config'i tek V3.4 üretim kimliğinde bağlayan kayıt yok. [Manifest](../data/results/reproducibility_manifest.json), [cache hash](../astra6/hpc.py#L689)
- Kanıt düzeyleri ayrı. Kaynak okuma, tam tablodan aritmetik, fiyat örneklerinden emir simülasyonu, tüm Model 1/2 stop/hedef zaman izi ve gerçek fiyat prefix testi. 64 stratejinin beş yıllık bütün fiyat yolları yeniden yürütülmedi.

## Veri ve yürütme

| Yerel M1 | Bid ve Ask başına satır | Ortak panel dışında | Açılış spread P01 / medyan / P99 |
|---|---:|---:|---:|
| US100 | 1.715.545 | 37.814 | 0,702 / 3,222 / 3,559 |
| US500 | 1.695.396 | 17.665 | 0,215 / 0,517 / 0,731 |
| US30 | 1.748.461 | 70.730 | 1,800 / 2,800 / 2,800 |

7 Kasım 2021 23:00 UTC ile 6 Kasım 2026 21:59 UTC arasında 1.677.731 ortak gözlem. Altı dosya sıralı ve zaman damgaları tekil. OHLC sınır ihlali veya sıfır/negatif ortak açılış spread'i görülmedi. Ortak panelde 27.866 aralık >1 dakika, 1.850 aralık >5 dakika, en uzun 265.920 saniye. 950.209 boş UTC dakika planlı kapanışları, hafta sonlarını ve kesişimde düşen barları da kapsar. Tam beklenen seans-dakika envanteri yapılmadı. [Panel](../astra6/bars.py#L85)

- US100, 24 Mayıs 2026 23:59 UTC ve US500, 22 Mayıs 2026 20:14 UTC son Dukascopy tick-türetilmiş Bid/Ask gözlemlerine sahip. Uzatma her simgenin kendi maksimum zamanından başlar. OANDA kuyruğunda son 2.000 Dukascopy gözleminin örtüşmesinden medyan baz farkı çıkarılır. Ask, UTC saate göre Dukascopy medyan spread'i eklenerek modellenir. US30 tüm dönem OANDA tabanlı. Ask modeli UTC saat 13–20 dahil 1,8, diğer saatlerde 2,8 puan. Bu sınırlar NY seansının DST değişimini izlemez. [Store üretimi](../astra6/data/ingest_hf.py#L241)
- 8–12 Kasım 2021 beş BI5 Bid gününde 6.615 örtüşen M1 OHLC farkı 0. Tick örneğinde 5.987 M1 ve 11.967 30s örtüşme, high/low azami fark 0, close tam eşleşme %99,9833 ve %99,9916. Genel doğrulama işareti tick koşulundan gelir. BI5 karşılaştırması ayrı ve 0,05 toleranslıdır. [Forensics](../astra6/data/forensics.py#L257)
- V3 LONG giriş Ask open +0,25, çıkış Bid. SHORT giriş Bid open −0,25, çıkış Ask. Çıkış maliyeti R'den ayrıca 0,25. Stop/TP high/low, aynı bar ikisinde stop, timeout/data-end uygun taraf close. Gerçek LONG/SHORT iki temas ve veri sonu örnekleri bağımsız hesapla eşleşti. Stop gap'te nominal stop seviyesinden yürür. M1 OHLC kesin emir sırası, komisyon, finansman ve latency içermez. [CF yürütme](../astra6/engine_v3.py#L946), [çekirdek](../astra6/hpc.py#L340)

## Doğrulanmış kusurlar

| Önem | Sınıf ve bulgu | Kanıt ve etkisi |
|---|---|---|
| P0 | `CAUSALITY_FAILURE` · Daha geç hesaplanan hedef erken dolumda kullanılıyor. | Model 1 ve 2'de 200/325 ve 18/792. Tüm seviyeler yeniden eşlendi. `known_before_entry=True` sabit. [Hedef kodu](../astra6/fractal_v3.py#L1600), [kanıt](ASTRA6_V34_RESULT_RECONCILIATION.md#model-1-ve-2nin-hedef-erişilebilirliği) |
| P0 | `CAUSALITY_FAILURE` · CF stop ve faktörleri eski adaydan. | `UEV_US100_M5_54_L` CFG64_00 tetik 55. O ana kadar dip 16316,239. Daha geç bar 58'e kadar dip 16315,909 ve kaydedilen stop 16314,409 = daha geç dip −1,50. Macro gerekli 15.362 ve micro gerekli 44.169 politika satırında formation indeksi politika tetik indeksinden ileri. 50.408 StdSMT gerekli satırda comparator ekstremi tetikte veya önce kırmış. Sayılar politika satırlarıdır. [Faktör ve stop](../astra6/engine_v3.py#L828) |
| P0 | `CAUSALITY_FAILURE` · Fırsat evreni daha geç koşulları içeriyor. | 518.957 UEV temel havuzu V2 confirmed/dev_cisd ve ek adaylardan gelir. CFG64_00 içinde 32.128 kayıt `j_sweep<0`, 345.323 kayıt kaynak TF kapanışından erken. İlk UEV satırı seçilir ve anchor kimlikte yoktur. [Aday](../astra6/engine_v3.py#L583), [tekilleştirme](../astra6/engine_v3.py#L828) |
| P0 | `CAUSALITY_FAILURE` · Raw → OC → FSM prefix invariance başarısız. | 2.000 satırlık gerçek prefix'te 53 as-of farkı. Ayrılışla üretilen Stage 1 önceye yazılır. Son kova, minimum seri boyu ve final terminal de etkili. [FSM](../astra6/fractal_v3.py#L412), [deney](ASTRA6_TRADING_LOGIC_SEMANTICS.md#gerçek-fiyatla-prefix-invariance) |
| P0 | `SEMANTIC_MISMATCH` · Başlıkların zorunlu olayları sorgulanmıyor. | V3 FSM'nin HTF POI, CRT, SMT/SSMT, CISD girdisi yok. Üç narrative tam olay dizisini test etmiyor. Model 4'ün 96.803 satırında Stage 13 yok. [FSM](../astra6/fractal_v3.py#L346), [narrative](../astra6/fractal_narrative_v34.py#L64), [M4](../astra6/audit_v34_models.py#L225) |
| P1 | `CONFIRMED_BUG` · Yapısal hedef adı sabit 2R icrasına yazılıyor. | `all_trades` 644.237/644.237 sabit 2R, 636.990 satır yapısal isimli. CF 3.685.678/3.685.678 sabit 2R. Yapısal sonuç ayrı hedef dalında. [Ortak yürütme](../astra6/engine_v3.py#L655), [etiket/fiyat](../astra6/engine_v3.py#L759), [CF 2R](../astra6/engine_v3.py#L960) |
| P1 | `CONFIRMED_BUG` · MTF exit indeksi, CF teyit saati ve split eski/yanlış zaman taşır. | 1.343.233 MTF satırda `j_exit<j_fill`. CF `t_confirm` açılış. 12 CF kaydında fiilî UTC fill tarihi ve etiket split'i farklı. [MTF dönüş](../astra6/fractal_v3.py#L1793), [CF zamanları](../astra6/engine_v3.py#L994) |
| P1 | `CAUSALITY_FAILURE` · CISD kaynağı ve bekleme sırasında iptal. | 274.687 CISD gerekli politika satırında hem CRT içi hem post-sweep M1 indeksi yok. Diğer as-of bayrakları eligibility'yi açabilir, beklenen event ID saklanmaz. `OPP_US100_M3_confirmed_11_S` örneğinde 9'daki sweep sonrası 22'de baseline ve gecikmiş stop seviyesi ihlal edilir, M15 politikası 58'de tetiklenip 59'da girer. [CISD bit](../astra6/engine_v3.py#L619), [MTF yürütme](../astra6/engine_v3.py#L1495) |
| P1 | `CONFIRMED_BUG` · Replay'ler ve hardcode fallback. | Yirmi SVG random mum yolu, PDF/JSON 20/20 ID farkı. Model 4 boş seçim +0,3651R atar. Mevcut 96.803'lü koşuda fallback kullanılmadı. [Replay](../astra6/trade_replay_v34.py#L280), [fallback](../astra6/audit_v34_models.py#L231) |
| P1 | `STATISTICAL_FAILURE` · Destek statüsü ve eski sayılar. | M3 p=0,157649, Holm=0,315298, GA sıfırı içeriyor. JSON pozitif mean+OOS ile doğrulanmış edge der. M4 PDF PF 0,6729, hesap 0,7482. [Karar](../astra6/audit_v34_models.py#L74), [sabit metin](../astra6/audit_v34_models.py#L273) |
| P2 | `CONFIRMED_BUG` · Cache kimliği eksik. | İlk/orta/son 256 KiB ve boyut, aradaki aynı boyutlu değişikliği göremez. Çıktı içeriği kontrol edilmez. V4 dosyası manifest ile uyuşmuyor. [Hash](../astra6/hpc.py#L689), [cache](../astra6/hpc.py#L890) |

W1 yeniden örneklemesi, iki gerçek DST haftasında sonraki Pazar 18:00 NY sınırından bir saat ayrıştı. [Zaman deneyi](ASTRA6_TRADING_LOGIC_SEMANTICS.md#quarterly-theory-zaman-ve-fiyat-bütünlüğü)

## Açık riskler

Eşit tetik sıralaması, ilk aday seçimi ve anchor eksikliğine duyarlılık tüm evrende ölçülmedi. Geçmiş seviyenin seçilmesi, tüketilmemiş olduğunu veya fiyatın hedef ve stopu hangi sırayla gördüğünü ispatlamaz. Gap-stop farkı tüm tarih için yeniden fiyatlanmadı. DST ve eksik barların etkisi her TF için ayrı ölçülmedi. Portföy tahsisi, açık pozisyon riski ve broker maliyetleri satır getirilerinden çıkarılamaz. [Test denetimi](ASTRA6_TEST_COVERAGE_GAPS.md)

## Sekiz nihai cevap

1. **MMXM × QT anlatısı** — Bileşenler var. Zorunlu, sıralı ve farklı TF'lerdeki anlatı uçtan uca emir kuralına dönüşmemiş.
2. **Fraktal yapı** — Çok TF OC, swing, CISD ve hedef geometrisi hesaplanıyor. MMXM aşamalarının piyasa anlamı ve iç içe yapı ilişkileri için kanıt eksik.
3. **Nedensellik** — Hedef, stop, faktör zamanı ve raw-prefix ihlalleri doğrulandı.
4. **64 politika** — 64 ayrı yürütme, 3.685.678 tekil politika–UEV satırı. Ortak aday bağlamı ve sabit 2R yüzünden tam bağımsız nedensel strateji olarak doğrulanmadı.
5. **20 replay** — SVG'ler sentetik fiyat illüstrasyonu. PDF satırları farklı kayıtlar. Tek olay ayrıca gerçek fiyatla doğrulandı.
6. **Pozitif sonuçlar** — Model 1/2/3 aritmetiği yeniden üretildi. 1/2 hedef sızıntısı nedeniyle `NOT_VERIFIED`. 3 `EXPLORATORY_POSITIVE` ve `STATISTICAL_EVIDENCE_INSUFFICIENT`. Model 4 geniş havuzda `NEGATIVE_EXPECTANCY`, terminal hipotezi `NOT_VERIFIED`.
7. **Paper trading** — Nedensel emir zamanı, aday iptali, Bid/Ask maliyet sözleşmesi, gerçek replay, sabitlenmiş politika, eşli kontroller ve yeni gözlemler gerekli. `INDEPENDENT_FORWARD_VALIDATED` kanıtı yok.
8. **Onarım** — Önce resample, OC/FSM, bağlam/teyit/stop/hedef yürütmesi. Sonra audit/metrics, anlatı, replay ve rapor. Ölçülen doğru kotasyon tarafını koruyarak sınır durumlarını düzeltmek yeterli bir başlangıç.

## Aşama kontrol noktaları

1. Sürüm ve veri · Git, Parquet, DuckDB, SHA, PDF, Excel.
2. Mimari · V2 / V3 / V3.4, ayrı popülasyonlar ve fonksiyonlar.
3. Semantik · gerçek prefix, QT/CISD ve aşama şartları.
4. Yürütme · UEV replay, faktör/zaman, stop/hedef kaynakları.
5. Sonuç · dört modelin aritmetiği, istatistik ve yayın farkları.
6. Teslim · test kapsamı, kanıt sınırları, onarım kabul ölçütleri.

Üretim kodu, testler, mevcut veri ve önceki raporlar salt okunur tutuldu. Yeni dosyalar yedi Markdown denetim raporudur.
