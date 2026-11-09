# ASTRA 6 V3.5 · P0 yeniden doğrulaması

**Durum `NOT_VERIFIED`.** Altı yerel pencere üzerinde kapsama ve davranış tanısı yürütüldü. Tam tarihsel backtest ve kombinasyon sıralaması başlatılmadı.

## Kapsam ve olay kanıtı

- US100 ve US500 için doğrudan kaydedilmiş Dukascopy Bid/Ask kesişimi kullanılıyor. Bütün planlanan dakikaları mevcut mum `FULL`. Karşılaştırılan kaynaklardan en az birinde eksik dakikaya ait gözlem varsa ortak kapsam `INCOMPLETE`. İki kaynakta da gözlem yoksa `UNKNOWN`. Açık son kova `OPEN`. Tamamen boş aralıklar ayrı kaydediliyor. Yerel kaynaklarda tarihli broker seans takvimi bulunmadığı için `UNKNOWN` aralıklarına planlı kapanış etiketi verilmiyor.
- M5/M15/H1 saat ve fiyat sınırları altı 2021–2026 penceresinde üç çıpa ile doğrulandı. NY ve Londra DST geçişleri ile gerçekten boş olan dakikalar dahil. H1/M15/M5 OC ve MMXM kayıtları her yıl için üç zaman kesitinde karşılaştırıldı. Önceki 17.000 gözlem ve 11 kesit testi de uyumluluk koşusunda yer aldı.
- 21 Ekim 2025 SHORT örneğinde H1 tepe süpürmesi **12:01 UTC**, önceden teyitli H1 swing low **25.089,055**, H1 yapısal kırılım ve bağımsız H1 CISD **14:00 UTC**. H1 CISD çıkarılınca veya kırılım mumunda gözlem eksilince dönüş üretilmedi. H1 dönüşü en son önceden teyit edilmiş 2+2 swing, tek taraflı H1 süpürmesi ve en çok iki sonraki tam H1 mumunda yönlü kapanışla sınandı.
- Aynı gün `MMXM_US100_H1_1761030000_S08` için doğrulanan alt OC `OC_US100_M5_1761042600`. 20 kayıtlı dakikadan hesaplanan M5 OC üst sınırı **25.117,403**. Teyit **10:55 UTC**. Yanlış model ID, OC ID, araç, timeframe, yön veya geç bilgi zamanı eşlemeyi engelliyor.
- Macro SSMT için 90 tam dakika, Micro SSMT için 45 tam yarım dakika gerekir. Eksik referansla oluşan eski sinyal iki çözünürlükte de elendi. Kesintili açık emir yolunda temas gözlenmediyse `DATA_END` kaydediliyor ve gerçekleşmiş R boş bırakılıyor.

## İki playbook için uygulanan sözleşmeler

**Model 1.** Tek taraflı M5 sweep/reclaim adayından sonra tam M5 CRT ve sweep sonrası bağımsız M1 veya M5 CISD beklenir. Son kapanmış H1 gövdesi yükseliş yönünde olmalı. NY veya Londra sabahı, 90M Q2/Q3, aktif M5/H1 MMBM 04–06 ve US100 öncülüğünde Micro SSMT birlikte aranır. Sweep ile reclaim arasındaki dip ve önceki tam M5 ATR’nin 0,15 katı stopu belirler. Sonraki dip ihlali bekleyen adayı iptal eder. Süpürmeden sonra dolum için 15 dakika vardır. Karar anında önceki tam M15 tepesinin kullanılmamış olması ve dolumda 0,75–1,50R bandına girmesi gerekir. Çıkışta stop, hedef, 60 dakika ve bağımsız ters M15 CISD uygulanır.

**Model 2.** Tam H1 tepe süpürmesi, önceden teyitli H1 swing kırılımı ve bağımsız H1 CISD bir dönüş olayı oluşturur. M15 bearish CISD daha sonra teyit edilmeli ve en yakın önceki yükseliş mumunun dibinin altında kapanmalı. NY sabahında 90M Q3 veya aynı 6H bloğunda gerçek NY sabahı H1 süpürmesi gerekir. Macro SSMT ve aktif H1/M15 MMSM 08–09 aranır. Stage 08’in gözlenen tepe fiyatı ve zamanı aynı H1 süpürmesine bağlanır. M5 OC, üst modelin OC aralığına ve zamanına uyan tek teyitli alt kayıt olmalı. Hedef için yayımlanmış nihai playbook’taki **OC üst sınırı** kullanıldı. H1 tepesine önceki H1 ATR’nin 0,15 katı eklenir. Beklerken tepe aşılırsa aday iptal edilir. En az 1,50R mesafeli kullanılmamış hedef ve 120 dakikalık çıkış uygulanır. Günlük PDH alternatifi tam D1 kanıtı olmadan kullanılmadı.

Her iki modelde giriş ve çıkış gerçek Ask/Bid kotasyonları ve 0,25 puan yönlü kayma ile hesaplanır. Model 2’nin 6H alternatifinde yayımlanmış “NY açılış manipülasyon zirvesi” ifadesi, karar anında bilinebilir aynı bloktaki H1 sweep tepesiyle tanımlandı. Açık bir alt OC bağı bulunmadığında tekil zaman ve fiyat kapsaması şartı uygulandı.

## Önce başarısız, sonra başarılı

| Negatif kontrol | Önce | Düzeltilmiş bağımsız kontrol |
|---|---|---|
| H1 veri kapsamı | İki ayrı durum tek `PARTIAL_UNCLASSIFIED` etiketi | Ham kaynakların zaman kümeleriyle `UNKNOWN` / `INCOMPLETE` ayrımı |
| Macro/Micro SSMT | Kısmi referans kullanılabiliyor | 90 M1 veya 45 gerçek 30 saniyelik gözlem zorunlu |
| MMXM kökeni | Geçersiz OC kimliği faktör olabiliyor | Tam eşleşen, önceden teyitli ve geçerli OC |
| Model 1 | 18 Kasım 2021, 14:47 dolumu 15:00 M15 hedefini kullandı. Hedef 0,356R. | Eski dolum yeniden oluşmadı. Reclaim stopu, hedef bandı ve ters M15 CISD çıkışı ayrı fiyat yolu testleriyle geçti. |
| Model 2 | 15 Kasım 2021, 09:02 dolumu 10:00 OC hedefini kullandı. Hedef 1,240R. | Eski dolum yeniden oluşmadı. Gerçek H1 dönüşü ve M5 OC üst sınırı ayrı pozitif örneklerle doğrulandı. |
| Gözlenemeyen çıkış | Eski yürütücü boşluğun ötesinde R yazdı. | Dolum kayıtlı, çıkış ve gerçekleşmiş R boş. |

Negatif kontrol dosyası özellikle eski yolları sınar ve normal test keşfinden ayrıdır. Çalıştırıldığında **6 beklenen başarısızlık** verir. Yeni yol için **77 odaklı test geçti**. [Önce testleri](../tests/p0_v35_before.py) · [Sonra testleri](../tests/test_v35_p0_resume.py)

```sh
PYTHONDONTWRITEBYTECODE=1 NUMBA_CACHE_DIR=/tmp/astra6-v35-numba .venv/bin/python -m pytest -q -p no:cacheprovider tests/p0_v35_before.py
PYTHONDONTWRITEBYTECODE=1 NUMBA_CACHE_DIR=/tmp/astra6-v35-numba .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_v35_p0_resume.py
PYTHONDONTWRITEBYTECODE=1 NUMBA_CACHE_DIR=/tmp/astra6-v35-numba .venv/bin/python -m astra6.playbooks_v35
```

Önceki kapsam filtresiyle çalışan uyumluluk koşusu **2.729 geçti, 11 seçilmedi, 9 uyarı**. Test komutu kontrol noktasında. İlk kontrolden devreden 11 test kapsam dışında kaldı. [Makine kontrol noktası](../data/results/v3_5_checkpoint.json)

## Tarihsel yayın kapısı

Altı tanı penceresi **116.876 ortak M1** ve **226.905 ortak 30 saniye** gözlemi kapsadı. 1.242 aralıkta en az bir kaynakta eşleşmeyen gözlem vardı. 79 aralıkta iki kaynak da sessizdi.

| Playbook | Gözlenen aday | Zincirden geçen ve dolan |
|---|---:|---:|
| Model 1 · M5 sweep/reclaim | 5.945 | 0 |
| Model 2 · H1 SHORT dönüş | 3 | 0 |

Model 1’de 92 aday seans, Q90 ve H1 yönüne kadar ilerledi. İkisi aktif MMXM 04–06 ile çakıştı. Hiçbirinde gereken Micro SSMT aynı karar anında geçerli değildi. Model 2’de üç gerçek SHORT H1 dönüşünün ardından M15 CISD gözlendi. Hiçbiri gerekli NY/QT zamanında teyit edilmedi. Ayrı testlerde doğrulanan yapı ve yürütme bileşenleriyle iki playbook için bütünleşik bir gerçek dolum bu örnekte doğrulanamadı. [Pencere ve kontrol sayımları](../data/results/v3_5/p0_resume_audit.json)

US100/US500 gerçek Ask ve 30 saniye ortak kapsamının üst sınırı **22 Mayıs 2026, 20:14:30 UTC**. Sonraki birleşik Ask serisi modellenmiş. Ayrıca 64 politikanın, üç QT çıpasının ve tüm yapısal hedef varyantlarının aynı sıkı kapsama koşullarıyla uçtan uca doğrulanması açık. Bu nedenle yeni N, win rate, R, PF, drawdown, yıl/OOS metrikleri ve güven aralıkları hesaplanmadı. **H1/M15/M5 üstünlüğü veya en iyi QT/CISD eşleşmesi için veriyle desteklenen bir sonuç yok.**

| V3.4 yayımlanmış grup | Eski N | Eski ortalama R | V3.5 tarihsel karşılık |
|---|---:|---:|---|
| Model 1 | 325 | +0,82789 | Hesaplanmadı |
| Model 2 | 792 | +0,18931 | Hesaplanmadı |
| Model 3 | 658 | +0,07152 | Hesaplanmadı |
| Model 4, geniş 4–12 havuzu | 96.803 | −0,18079 | Hesaplanmadı |

Model 1’in 200 ve Model 2’nin 18 hedefi eski dolumdan sonra bilinebilir oldu. Önceki sonuç tablosu denetim için korunuyor. Örnek tanıda sıfır dolum, tam dönem için getiri veya dolum sayısı tahmini olarak kullanılmadı. [V3.4 uzlaştırması](ASTRA6_V34_RESULT_RECONCILIATION.md)
