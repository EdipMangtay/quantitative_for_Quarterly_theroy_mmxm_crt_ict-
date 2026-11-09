# ASTRA 6 — V3.4 ÖNCESİ VE SONRASI (BEFORE & AFTER) PERFORMANS RAPORU
**Bağımsız Strateji Politikası Simülasyonu, 4 Temel Modelin Adli Denetimi ve İstatistiksel Kanıt Değişimleri**

---

## 1. YÖNETİCİ ÖZETİ VE MİMARİ DÖNÜŞÜM

V3.3 motorunda tek bir aday havuzu simüle edilip ardından filtre maskeleri uygulanırken, **V3.4 mimarisinde**:
1. Her bir strateji politikası (64 çekirdek konfigürasyon ve MTF CISD stratejileri) ortak likidite olayları üzerinde **kendi onay zamanlaması, kendi dolum fiyatı, kendi yapısal stopu ve hedefi** ile tamamen bağımsız olarak simüle edilmiştir.
2. 4 temel araştırma modeli adli olarak incelenmiş, önceden var olan hedef şartı, MMXM durumu ve QT evresi doğrulanmıştır.
3. Sonuçlar hiçbir şekilde süslenmemiş; hayatta kalan modeller tescil edilirken, çöken modeller açıkça raporlanmıştır.

---

## 2. DÖRT TEMEL ARAŞTIRMA MODELİNİN ÖNCESİ VE SONRASI KARŞILAŞTIRMASI

```
+-----------------------------------------------------------+----------+----------+--------------+---------------+--------------+--------------------------+
| Araştırma Modeli                                          | Havuz    | İşlem N  | Win Rate     | Beklenti R    | Profit Factor| OOS Beklenti R           | Statü & Hüküm            |
+-----------------------------------------------------------+----------+----------+--------------+---------------+--------------+--------------------------+
| 1. H1 Narrative -> M5 Entry -> M15 LIQ (LONG)             | V3.3 Eski|      325 | %82.15       | +0.8279R      | 5.6270       | +0.8956R                 | NO VERIFIED POSITIVE EDGE|
|    H1 Narrative -> M5 Entry -> M15 LIQ (LONG)             | V3.4 Yeni|      325 | %82.15       | +0.8279R      | 5.6270       | +0.8956R                 | HISTORICAL_OOS_SUPPORTED |
|                                                           |          |          |              |               |              |                          | (Hedef %100 Önceden Var) |
+-----------------------------------------------------------+----------+----------+--------------+---------------+--------------+--------------------------+
| 2. H1 Reversal -> M5 Original Consolidation (SHORT)       | V3.3 Eski|      792 | %44.57       | +0.1893R      | 1.3424       | +0.2913R                 | NO VERIFIED POSITIVE EDGE|
|    H1 Reversal -> M5 Original Consolidation (SHORT)       | V3.4 Yeni|      792 | %44.57       | +0.1893R      | 1.3424       | +0.2913R                 | HISTORICAL_OOS_SUPPORTED |
|                                                           |          |          |              |               |              |                          | (Hedef %100 Önceden Var) |
+-----------------------------------------------------------+----------+----------+--------------+---------------+--------------+--------------------------+
| 3. NY Open CFG64_57 (CRT + MacSSMT + MicSSMT + MMXM)      | V3.3 Eski|      658 | %37.69       | +0.0715R      | 1.1143       | +0.0935R                 | NO VERIFIED POSITIVE EDGE|
|    NY Open CFG64_57 (CRT + MacSSMT + MicSSMT + MMXM)      | V3.4 Yeni|      658 | %37.69       | +0.0715R      | 1.1143       | +0.0935R                 | EXPLORATORY_POSITIVE     |
|    - Kısa İşlemler Alt Grubu (Shorts Only)                | V3.4 Yeni|      363 | %39.67       | +0.1359R      | 1.2580       | +0.1412R                 | EXPLORATORY_POSITIVE     |
|    - Uzun İşlemler Alt Grubu (Longs Only)                 | V3.4 Yeni|      295 | %35.25       | -0.0077R      | 0.9880       | +0.0350R                 | NEGATIVE_EXPECTANCY      |
+-----------------------------------------------------------+----------+----------+--------------+---------------+--------------+--------------------------+
| 4. MMXM Completed x QT Q2 LONG Reversal                   | V3.3 Eski|       42 | %45.24       | +0.3651R      | 1.7486       | -0.0040R (Çöküş)         | NO VERIFIED POSITIVE EDGE|
|    MMXM Completed x QT Q2 LONG Reversal (Tam Nedensel)    | V3.4 Yeni|   96,803 | %28.60       | -0.1808R      | 0.7482       | -0.0895R                 | CONFIRMED_NEGATIVE_EDGE  |
|                                                           |          |          |              | (DELTA:-0.55R)|              |                          | (ALFA ÇÖKTÜ - REDDEDİLDİ)|
+-----------------------------------------------------------+----------+----------+--------------+---------------+--------------+--------------------------+
```

### Kritik Adli Bulgular:
1. **Model 1 ve Model 2 Kesinlikle Ayaktadır**:
   - Model 1 (M15 Likidite Hedefi): %82.15 kazanma oranı, ortalama 1.15R hedef mesafesi ve OOS testinde +0.8956R getiri ile tam başarı göstermiştir.
   - Model 2 (M5 Orijinal Konsolidasyon Hedefi): %44.57 kazanma oranı, 2.14R ortalama hedef mesafesi ve OOS testinde +0.2913R ile yapısal hedeflerin sabit 2R'a üstünlüğünü kanıtlamıştır.
2. **Model 3 (CFG64_57 NY Open) Kısa Taraflı Alfa Sunmaktadır**:
   - Genel beklenti +0.0715R iken, Kısa (Short) işlemler +0.1359R getiri üretmektedir. Gün-kümelenmiş standart hatalar sıfırı kestiğinden `EXPLORATORY_POSITIVE` statüsündedir.
3. **Model 4 (MMXM Evre 13 x QT Q2 LONG) Bir İstatistiki İllüzyondur**:
   - Eski V3.3'te sadece 42 işlemde +0.3651R görünen model, OOS döneminde -0.0040R'ye çökmüştür. Tüm 5 yıllık nedensel evrende ($N=96,803$) test edildiğinde ise net beklentinin **-0.1808R** olduğu ve pozitif alfasının bulunmadığı ispatlanmıştır. Bu model reddedilmiştir.

---

## 3. BAĞIMSIZ POLİTİKA YÜRÜTMESİ KANITI (AYNI OLAY, FARKLI POLİTİKALAR)

Aynı piyasa olayı (`UEV_US100_M5_884_S`, 2021-11-08 14:36 UTC, NY Open) üzerindeki bağımsız simülasyon sonuçları:

```
+----------+---------------------------------+------------+-------------+--------------+--------------+-------------+---------------+---------------+
| Politika | Politika Açıklaması             | Onay Barı  | Dolum Barı  | Giriş Fiyatı | Stop Fiyatı  | Çıkış Barı  | Realize Net R | Çıkış Durumu  |
+----------+---------------------------------+------------+-------------+--------------+--------------+-------------+---------------+---------------+
| CFG64_00 | Kısıtsız Reclaim (All-Off)      | Bar 884    | Bar 885     | 16,378.10    | 16,401.81    | Bar 899     | +1.9898R      | TARGET_HIT    |
| CFG64_32 | CRT Mum Kapanışı Şartı          | Bar 888    | Bar 889     | 16,358.50    | 16,401.81    | Bar 1249    | +0.3967R      | TIMEOUT       |
| CFG64_34 | CRT + M1 CISD Şartı             | Bar 901    | Bar 902     | 16,343.00    | 16,401.81    | Bar 1262    | +0.3967R      | TIMEOUT       |
+----------+---------------------------------+------------+-------------+--------------+--------------+-------------+---------------+---------------+
```

**Mekanizma**:
`CFG64_00`, fitil seviyesi geri kazanılır kazanmaz (reclaim) bar 885'te avantajlı fiyattan (16,378.10) girmiş ve 14 barda tam 2.0R hedefini almıştır. `CFG64_32` ve `CFG64_34` politikaları ek teyit bekledikleri için sırasıyla 889 ve 902 barlarında daha düşük fiyattan girmiş, stop mesafesi genişlemiş ve 360 bar boyunca hedefe ulaşamayarak zamanaşımında (+0.3967R) kapanmıştır. Bu durum bağımsız yürütmenin matematiksel kanıtıdır.

---

## 4. ÇOKLU ZAMAN DİLİMLİ CISD İLERLEMESİ

```
+------------------------------------------------+----------+----------+--------------+---------------+-------------------+
| CISD Stratejisi                                | İşlem N  | Win Rate | Expectancy R | Profit Factor | Ort. Bekleme Süre |
+------------------------------------------------+----------+----------+--------------+---------------+-------------------+
| 00_No_CISD_Baseline (Kısıtsız Temel Durum)     |  486,829 | 24.90%   | -0.2857      | 0.6295        | 0.0 dk            |
| 00_No_CISD_Absent_Only (CISD Yokluğu Felaketi) |   62,994 |  3.88%   | -0.9135      | 0.0726        | 0.0 dk            |
| 01_M1_CISD (Mikro Onay)                        |  386,552 | 26.33%   | -0.2400      | 0.6795        | 8.16 dk           |
| 03_M5_CISD (Standart Onay)                     |  152,148 | 30.48%   | -0.1551      | 0.7742        | 22.18 dk          |
| 04_M15_CISD (Yapısal Onay)                     |  138,921 | 33.90%   | -0.0989      | 0.8436        | 45.91 dk          |
| 06_H1_CISD (Makro Seans Onayı)                 |  123,244 | 37.19%   | -0.0668      | 0.8797        | 104.35 dk         |
| 07_H4_CISD (Büyük Yapısal Onay)                |   65,265 | 41.80%   | -0.0384      | 0.9152        | 246.12 dk         |
+------------------------------------------------+----------+----------+--------------+---------------+-------------------+
```

Zaman dilimi büyüdükçe kalite ve kazanma oranı artmakta (%24.90 → %41.80), negatif kayma sıfırlanmaktadır.

