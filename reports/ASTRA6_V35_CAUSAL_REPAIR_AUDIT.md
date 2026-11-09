# ASTRA 6 V3.5 nedensel onarım denetimi

**Durum `NOT_VERIFIED`.** V3.4 temeli `9274803d002a14bc18e0a918d8a90fd615b0ed8f`.

| Aşama | Onarım ve kanıt | Açık kapsam |
|---|---|---|
| P0.1 | `bars.resample` gerçek yerel kapanış, kapsama ve availability alanlarını ayırır. İki 2022 W1 DST sınırı ve son tam kova düzeldi. CRT/CISD indeksleri bilinebilir zamanı geriye yuvarlamaz. | Tarihli CFD seans takvimi olmadan planlı kapanış ve eksik quote kesin ayrıştırılamıyor. |
| P0.2 | OC aday, teyit, ziyaret ve iptal ayrı. MMXM Stage 1 ayrılış öğrenilince yön kazanır. Terminal geçmiş aşamalara yazılmaz. 17.000 gerçek bar ve 11 kesitte fark yok. | Başka dönem ve sağlayıcı birleşimlerinde de çalıştırılmalı. |
| P0.3 | Tek taraflı sweep/reclaim ile fırsat, o ana kadarki ekstremden stop. REQUIRED olay ID, yön, araç, TF, availability ve invalidation taşır. | Tüm anchor ve eksik veri rejimlerinde faktör kapsamı ölçülmedi. Exact micro veri tüm uzatılmış dönemi kapsamıyor. |
| P0.4 | Ortak emir motoru fixed-2R, MTF ve yapısal hedefi kullanır. Bekleme, gap, süre aşımı ve yönlü risk denetlenir. Beş gerçek Ask replay'i bağımsız hesapla eşleşti. | Tüm evren ve stop varyantları genişletilmiş doğrulamadan geçmedi. |
| P0.5 | Karar anında teyitli ve tüketilmemiş hedef, kaynak ID ve bilgi zamanı. İki eski geç hedef vakası yeniden kuruldu. | Model 1 ve 2'nin tam playbook'u, bağımsız H1 dönüş ve MMXM/OC ilişkisi tam tarih için kapıyı geçmedi. |
| P1 | Olay zinciri doğrulayıcı, sabit R fallback'inin kaldırılması, gerçek replay, kronolojik DD, eşli ve portföy yardımcıları. | Anlatı üretim eşlemesi ve tarihsel istatistik tamamlanmadı. |
| P2 | Tam çekirdek dosya SHA256, aynı boyutlu mutasyon regresyonu, örnek çalışma manifesti. | Tam tarihsel çalışma manifesti ve taşınabilir araştırma kataloğu tamamlanmadı. |

Üç aracın ortak Bid/Ask M1 panelinde US100 için 3.814 H4 kovası tam, 3.881 H4 kovası kısmi. Kapanmış 1.290 D1 ve 260 W1 kovasının tamamı kısmi. Broker takvimi olmadan bu durumun ne kadarının planlı kapanıştan kaynaklandığı belirlenemiyor. 30 saniyelik iki araç kapsamı en geç 22 Mayıs 2026 20:14:30 UTC'de bitiyor.

V3.5 giriş noktası `.venv/bin/python run_pipeline.py --v35-sample 1300`. V3.4 çıktı ve verileri yerinde korunur. [Aşama günlüğü](../docs/ASTRA6_V35_PROGRESS.md) · [Kontrol noktası](../data/results/v3_5_checkpoint.json)
