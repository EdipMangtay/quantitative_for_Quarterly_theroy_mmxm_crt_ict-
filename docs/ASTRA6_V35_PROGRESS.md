# ASTRA 6 V3.5 ilerleme kaydı

Yerel dal `codex/astra6-v35`. V3.4 temeli `9274803d002a14bc18e0a918d8a90fd615b0ed8f`. Fiyat deposu ile önceki sonuçlar yerinde tutuluyor. Tam dosya SHA256 değerleri [makine kontrol noktasında](../data/results/v3_5_checkpoint.json).

## P0.1 · Mum ve bilgi zamanı

- Değişen kaynaklar `bars.py`, `cisd.py`, `signals.py`, `fractal_v3.py`. Regresyon `tests/test_v35_causal_time.py`.
- Önce haftalık bitiş, başlangıca sabit 168 saat ekliyordu. 13 Mart 2022'de 23:00 UTC ve 6 Kasım 2022'de 22:00 UTC yazılmıştı. Bağımsız New York Pazar 18:00 hesabına göre doğruları sırasıyla 22:00 ve 23:00 UTC. Yeni kod gerçek yerel sınırları kullanıyor.
- Önce son kova kesinlikle incomplete ve iç eksik kovalar complete idi. Yeni kod bilgi saatini son gözlenen M1 kapanışından veya açık `as_of` saatinden alıyor. Tam son kova gelecek gözlem olmadan kapanıyor. Eksik dakika `PARTIAL_UNCLASSIFIED` olarak saklanıyor ve OHLC'ye fiyat eklenmiyor. İleri kova için `available_at` boş.
- CISD ve CRT indeksleri, kaynak mumun bilinebilir zamanından önceki M1 kapanışına geri yuvarlanmıyor. W1 seviye zamanı, günlük barların son gözlemine bağlanmıyor. Son CRT satırından ilk satıra sarma kaldırıldı.
- Test sonucu **2.574 geçti**. 11 yeni kayıtlı fiyat/saat testi ve 2.563 mevcut seans testi. Sekiz Pandas uyumluluk uyarısı.
- Açık sınır. Kaynakta tarihli broker işlem saati takvimi olmadığı için planlı seans boşluğu ve kayıp quote kesin ayrıştırılamaz. `is_complete` yalnız tam dakika kapsaması. `complete` eski tüketiciler için finalize edilmiş gözlenen kova. Daha dar V3.5 yürütme kabulü ve hariç tutma kuralları ayrı test edilmeden P0 kapısı kapanmaz.

```sh
PYTHONDONTWRITEBYTECODE=1 NUMBA_CACHE_DIR=/tmp/astra6-v35-numba .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_v35_causal_time.py tests/test_clock_dst.py
```

## P0.2 · OC ve MMXM olay geçmişi

- `fractal_v3.py` ve `tests/test_v35_mmxm_prefix.py`. OC oluşumu, teyit, ilk ziyaret ve invalidation ayrı olaylar. Adayın yönü ve hedefi ayrılış teyidine kadar boş. Kimlik, fiyat penceresinin ilk zamanına dayanır.
- Önce 2.000 bar kesiminde 53 as-of farkı vardı. Stage 1 ayrılışla seçilip geçmişe yazılıyordu. Yeni Stage 1, 2 ve 3 ayrılışın bilinebilir anında başlıyor. Sonlanma geçmiş aşamalara yazılmıyor. Aynı adayın son aşaması terminal ise etkin sorguya girmiyor.
- İlk 17.000 gerçek ortak M1 barı ve 11 eski kesitte OC ve MMXM olayları, kimlik, yön, zaman, fiyat, hedef, etkinlik ve terminal alanları aynı. Her kesitin son 80 barında tüm etkin aday/TF kümeleri eşleşti. İki test geçti. [Makine diff](../data/results/v3_5/p02_prefix_diff.json)
- V3.4 uyumluluk görünümü olan varsayılan OC tablosunda sonuç alanları korunuyor. Yeni `include_lifecycle=True` olay tablosu gelecek sonuç alanlarını onay kaydına yazmıyor. FSM'deki fiyat eşikleri aynı. Dış SMT/CISD/POI olay bağları P1.1 kapsamı.

```sh
ASTRA6_PREFIX_DIFF=data/results/v3_5/p02_prefix_diff.json PYTHONDONTWRITEBYTECODE=1 NUMBA_CACHE_DIR=/tmp/astra6-v35-numba .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_v35_mmxm_prefix.py
```

## P0.3 · Fırsat ve faktörler

- `signals.py`, `execution_v35.py`, `research_v35.py` ve yeni emir regresyonları. Reclaim anında bilinen sweep ile aday kurulur. Önceki `UEV_US100_M5_54_L` stopu 16314,409 ile daha geç barın dibini kullanıyordu. Şimdi kayıtlı j54–55 dibi 16316,239 eksi 1,50 = 16314,739. Kesit ve uzatılmış veride aynı.
- Her REQUIRED faktör aynı araç, geçerli TF/yön, kendi olay ID ve availability ile karar anında seçilir. Dolum anında expiry ve yeni çelişki yeniden kontrol edilir. 64-bit CISD şartı standalone M1 olarak açıkça donduruldu. M1 CRT içi ayrı politika. Macro ve micro olay yaşamları UTC takvim dakikası. Exact micro örneği yerel 30s kaynaktan.
- Dört ilgili davranış testi geçti. Tüm tarih ve anchor kapsamı test edilmedi. [Makine kontrol noktası](../data/results/v3_5_checkpoint.json)

## P0.4 · İcra

- `execution_v35.py`, `fractal_v3.py` ve yedi ilgili gerçek fiyat testi. Eski MTF satırında kalıtılan çıkış indeksi yerine yeni çıkış ve kapanış zamanı yazılır. V3.5 tek emir yürütücüsünde beş 884 varyantı bağımsız Ask yolu ile aynı çıkış ve R'yi verdi. Önceden sabitlenen sayılar sonuç üretimine girmedi.
- Yönlü risk, gap açılışı, stop önce ambiguity, bekleme sırasında invalidation, olayın son tarihi ve örnek sonu ayrı. Dolum öncesi iptal satırı entry veya exit fiyatı taşımaz. [Örnek emir defteri](../data/results/v3_5/sample_1300_ledger.parquet)

## P0.5 · Yapısal hedefler

- `execution_v35.py`, `research_v35.py` ve iki ilgili hedef regresyonu. Teyit/availability, invalidation, tüketilme, fiyat tarafı ve ilişkili OC kaynağı karar zamanında denetlenir.
- 18 Kasım 2021 LONG örneğinde H1 üst sınırı önce kırıldı. Tek taraflı yeni aday yok. 15 Kasım SHORT örneği 09:01 UTC'de aday ve 09:06 UTC'de stop nedeniyle geçersiz. 10:00 UTC OC'si önceki emre eklenemez.
- Model 1/2 denemeleri zamanlama probları. Tam playbook sırası, H1 dönüş ve MMXM/OC ilişkisinin bütün tarihsel bağları açık. P0 kapısı tam tarih koşusuna geçmedi.

## P1 ve P2 · Güvenli alt parçalar

- Anlatı olay şeması ve negatif zincir testleri tamamlandı. V3.4 etiket maskesi güncel doğrulama çalıştırmıyor. Üretimde bütün tarihsel zincir eşleme açık.
- Model 4 sabit R fallback'i kaldırıldı. Stage 13, 11/12 ve geniş havuz ayrı. Eksik düzeltilmiş ledger statüsü `NOT_VERIFIED`.
- V3.5 ledger'dan 20 gerçek kotasyon replay'i. Önceki SVG, JSON ve raporlar yerinde. Replay kaynak zamanı, UEV, politika ve çıkış aynı kayıtla bağlı.
- Kronolojik DD, eşli UEV ve tek pozisyon yardımcıları ile fold çıkış sınırı eklendi. Tam inferans, maliyet ve portföy tarihsel çalışması açık.
- Tam çekirdek SHA256 ve aynı boyutlu iç mutasyon testi. Örnek manifestinde kod, config, bütün giriş/çıkış özetleri ve komut var. 108 V3.4 veri/sonuç dosyası aynı içerik hash'ini korudu.
- Son koşu **2.652 geçti, 11 seçilmedi, 9 uyarı**. Fiyat üreten eski testler ve tam tarih context'li mock test seçilmedi. Aşama bazında dosyalar ve devam komutları [kontrol noktasında](../data/results/v3_5_checkpoint.json).

## Sonraki doğrulama

Kapsam tanısı 1.677.731 ortak Bid/Ask M1 zamanını kapsadı. US100 H4'te 3.814 tam ve 3.881 sınıflandırılamayan kısmi kova var. D1'de 1.290 ve W1'de 260 kapanmış kovanın tamamı kısmi. Her zaman diliminde son kova açık. İki araç için 30 saniyelik ortak kotasyon kapsamı en geç 22 Mayıs 2026 20:14:30 UTC'de bitiyor. Bu tanıda emir simülasyonu çalıştırılmadı.

Kapsam koşulu çözüldüğünde P0.5 gerçek model regresyonlarından devam et. D1/W1 broker seans kapanışı ve eksik quote ayrımı, uzatılmış dönemde exact micro dışlaması ve tam Model 1/2 kural zincirleri çalıştırma konfigürasyonuna bağlanmalı. Tam tarihsel koşu, finansal sonuç ve sıralama bu kapıdan sonra.

```sh
PYTHONDONTWRITEBYTECODE=1 NUMBA_CACHE_DIR=/tmp/astra6-v35-numba .venv/bin/python run_pipeline.py --v35-sample 1300
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m astra6.trade_replay_v34
.venv/bin/python build_v35_report.py
```

## P0 devamı · Gözlenen Bid/Ask

- `coverage_v35.py` ortak kaynak eksikliğini `INCOMPLETE`, açıklanamayan sessizliği `UNKNOWN` olarak ayırır. Her fiyat boşluğunda doğrulama bölümü sıfırlanır. Model tabanlı Ask uzantısı sıkı yürütme dışında.
- `structure_v35.py` gerçek sweep, önceden teyitli H1 swing ve bağımsız H1 CISD ile dönüş üretir. MMXM kökeni OC kimliği, araç, timeframe, yön ve kullanılabilir zamanla doğrulanır.
- `playbooks_v35.py` iki mevcut playbook’u ortak emir yürütücüsüne bağlar. Gerçek M5 OC bağlantısı, ATR stopu, dolum öncesi iptal, hedef mesafesi, zaman ve ters CISD çıkışı sınandı. Gözlenmeyen çıkışa R yazılmaz.
- Altı eski yol kontrolü beklenen şekilde başarısız. 77 yeni odak testi ve toplam 2.729 uyumluluk testi geçti. Altı yerel örnekte iki tam zincir için dolum görülmedi. Tam tarihsel koşu ve sıralama kapalı.

[P0 yeniden doğrulaması](../reports/ASTRA6_V35_P0_REVALIDATION.md) · [Pencere tanısı](../data/results/v3_5/p0_resume_audit.json)
