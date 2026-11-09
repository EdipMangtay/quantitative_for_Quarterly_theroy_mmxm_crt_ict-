# ASTRA 6 fonksiyon kataloğu

**Aşama 2 kontrol noktası** Bu katalog `9274803d002a14bc18e0a918d8a90fd615b0ed8f` sürümündeki araştırma, altyapı, giriş noktası ve raporlama fonksiyonlarını kapsar. Test fonksiyonları [ayrı envanterde](ASTRA6_TEST_COVERAGE_GAPS.md).

185 fonksiyon incelendi. İmza ve statik çağrı başvuruları Python kaynak ağacından çıkarıldı. DataFrame alanları, zaman sözleşmesi, sonuç ve riskler elle incelendi. `ctx` panel/indikatör ve olay tabloları, `j` sıfır tabanlı ortak M1 bar indeksi, `R` ilk stop mesafesi birimidir. QA `test_qa_suite.py` kategori numarasını, V3 `test_v3_fractal_qa.py` satırını, DST `test_clock_dst.py` satırını gösterir.

**Durum kapsamı.** `VERIFIED_CORRECT` yalnız satırda yazılan giriş ve kanıt için geçerlidir. `IMPLEMENTED_NOT_VERIFIED` statik inceleme veya dar doğrulama demektir. `DEAD_OR_UNUSED_CODE` iç üretim çağrısı bulunmayan yardımcı veya stub. `DATA_LIMITATION` veri/çözünürlük sözleşmesi. Diğer durumlar belirlenen kusur veya test boşluğunu gösterir. Statik çağrı haritası dinamik çağrı, modül içe aktarımı ve dış kütüphanelerin içini içermez.

## Sayısal karar örnekleri

- **CISD.** UEV 884 SHORT için bağımsız M5 teslimat açılışı 16355,689. M5 kapanışı 16341,409 ve gövde aşağı. Onay 14:55 UTC. M15 onayı 15:00 UTC. M1 politikasının CRT içi onayı 14:40 UTC, ayrı M1 V1 taraması 14:53 UTC. Aynı TF ismi farklı kaynağı gizleyebilir. [Replay](ASTRA6_V34_RESULT_RECONCILIATION.md#uev_us100_m5_884_s--ham-fiyat-replay)

- **Emir.** No-CISD SHORT giriş 16379,079 Bid −0,25 = 16378,829. Risk 16403,309 − 16378,829 = 24,480. Hedef 16329,869. Ask low hedefe ulaşınca R = (48,960 − 0,25)/24,480 = 1,989788. [Çekirdek](../astra6/hpc.py#L397)

- **MMXM ve hedef.** Geçmiş dar bant ayrılış kapanışında doğrulanır. Durum makinesi yerel eşikleri kullanır. Yapısal hedef motoru yakın TF ve uzak TF seviyelerini ayrı simüle eder. 18 Kasım 2021 örneğinde aday yeni 14:47 UTC dolumuna rağmen 15:00 UTC M15 high kullanır. [OC](../astra6/fractal_v3.py#L116), [Model 1](ASTRA6_V34_RESULT_RECONCILIATION.md#model-1-ve-2nin-hedef-erişilebilirliği)

## Modül dizini

- [`astra6/clock.py`](#astra6clockpy)
- [`astra6/bars.py`](#astra6barspy)
- [`astra6/data/dukascopy.py`](#astra6datadukascopypy)
- [`astra6/data/download.py`](#astra6datadownloadpy)
- [`astra6/data/ingest_hf.py`](#astra6dataingest_hfpy)
- [`astra6/data/forensics.py`](#astra6dataforensicspy)
- [`astra6/ict.py`](#astra6ictpy)
- [`astra6/crt.py`](#astra6crtpy)
- [`astra6/smt.py`](#astra6smtpy)
- [`astra6/cisd.py`](#astra6cisdpy)
- [`astra6/mmxm.py`](#astra6mmxmpy)
- [`astra6/signals.py`](#astra6signalspy)
- [`astra6/opening.py`](#astra6openingpy)
- [`astra6/fractal_v3.py`](#astra6fractal_v3py)
- [`astra6/engine.py`](#astra6enginepy)
- [`astra6/engine_v3.py`](#astra6engine_v3py)
- [`astra6/sim.py`](#astra6simpy)
- [`astra6/hpc.py`](#astra6hpcpy)
- [`astra6/stats.py`](#astra6statspy)
- [`astra6/audit.py`](#astra6auditpy)
- [`astra6/audit_v34_models.py`](#astra6audit_v34_modelspy)
- [`astra6/fractal_narrative_v34.py`](#astra6fractal_narrative_v34py)
- [`astra6/trade_replay_v34.py`](#astra6trade_replay_v34py)
- [`astra6/report.py`](#astra6reportpy)
- [`astra6/report_v3.py`](#astra6report_v3py)
- [`app.py`](#apppy)
- [`run_pipeline.py`](#run_pipelinepy)
- [`build_report_pdf.py`](#build_report_pdfpy)
- [`build_v34_report.py`](#build_v34_reportpy)
- [`src/astra6/__init__.py`](#srcastra6__init__py)

## Araştırma ve altyapı fonksiyonları

### `astra6/clock.py`

#### [`local_to_utc`](../astra6/clock.py#L28)

- **İmza** `(d: date, t: time, tz: ZoneInfo)`
- **Girdi ve çıktı** d, t ve ZoneInfo → UTC Timestamp.
- **Hesap ve işlem yorumu** Piyasa yerel gün/saatini timezone-aware oluşturup UTC'ye çevirir.
- **Zaman, hata ve risk** Normal seans anchor'ları tekil. Genel ambiguous/nonexistent yerel saat için fold/gap sözleşmesi yok.
- **Bağımlılıklar** `datetime.datetime`, `pandas`
- **Çağıranlar** [`clock.london_open_utc`](../astra6/clock.py#L38), [`clock.nasdaq_open_utc`](../astra6/clock.py#L34)
- **Maliyet ve test** O(1). DST 49–108, seans anchor'ları.
- **Durum** `VERIFIED_CORRECT`

#### [`nasdaq_open_utc`](../astra6/clock.py#L34)

- **İmza** `(d: date)`
- **Girdi ve çıktı** Gün → UTC Timestamp.
- **Hesap ve işlem yorumu** New York 09:30 duvar saatini çevirir.
- **Zaman, hata ve risk** Takvim tatil filtresi ayrı.
- **Bağımlılıklar** [`clock.local_to_utc`](../astra6/clock.py#L28)
- **Çağıranlar** [`clock.london_ny_open_gap_minutes`](../astra6/clock.py#L95), [`clock.reference_calendar`](../astra6/clock.py#L137), [`clock.session_stamp`](../astra6/clock.py#L113)
- **Maliyet ve test** O(1). DST 57–108.
- **Durum** `VERIFIED_CORRECT`

#### [`london_open_utc`](../astra6/clock.py#L38)

- **İmza** `(d: date)`
- **Girdi ve çıktı** Gün → UTC Timestamp.
- **Hesap ve işlem yorumu** Londra 08:00 duvar saatini çevirir.
- **Zaman, hata ve risk** Takvim tatil filtresi ayrı.
- **Bağımlılıklar** [`clock.local_to_utc`](../astra6/clock.py#L28)
- **Çağıranlar** [`clock.london_ny_open_gap_minutes`](../astra6/clock.py#L95), [`clock.reference_calendar`](../astra6/clock.py#L137), [`clock.session_stamp`](../astra6/clock.py#L113)
- **Maliyet ve test** O(1). DST 57–108.
- **Durum** `VERIFIED_CORRECT`

#### [`is_dst`](../astra6/clock.py#L42)

- **İmza** `(d: date, tz: ZoneInfo, at: time=time(12, 0))`
- **Girdi ve çıktı** Gün, bölge, isteğe bağlı saat → bool.
- **Hesap ve işlem yorumu** Yerel DST offset'i sıfırdan farklı mı.
- **Zaman, hata ve risk** Varsayılan öğlen, gün içi geçişte tam an yerine gün durumu.
- **Bağımlılıklar** `datetime.datetime`, `datetime.time`, `datetime.timedelta`
- **Çağıranlar** [`clock.dst_regime`](../astra6/clock.py#L64)
- **Maliyet ve test** O(1). DST 49 ve 83, dolaylı.
- **Durum** `VERIFIED_CORRECT`

#### [`dst_transitions`](../astra6/clock.py#L48)

- **İmza** `(tz_name: str, year: int)`
- **Girdi ve çıktı** IANA adı, yıl → tarih tuple.
- **Hesap ve işlem yorumu** Günlük offset durum değişimlerini tarar ve cache'ler.
- **Zaman, hata ve risk** Saat yerine gün verir. Geçersiz bölge hatası dışarı çıkar.
- **Bağımlılıklar** `datetime.date`, `datetime.datetime`, `datetime.time`, `datetime.timedelta`, `functools.lru_cache`, `zoneinfo.ZoneInfo`
- **Çağıranlar** [`clock.is_transition_week`](../astra6/clock.py#L85)
- **Maliyet ve test** O(365), cache. DST 49–57.
- **Durum** `VERIFIED_CORRECT`

#### [`dst_regime`](../astra6/clock.py#L64)

- **İmza** `(d: date)`
- **Girdi ve çıktı** Gün → rejim dizgesi.
- **Hesap ve işlem yorumu** NY/Londra DST kombinasyonu ve ilkbahar/sonbahar mismatch.
- **Zaman, hata ve risk** Faz seans çevrimi, fiyat bilgisi içermez.
- **Bağımlılıklar** [`clock.is_dst`](../astra6/clock.py#L42)
- **Çağıranlar** [`clock.reference_calendar`](../astra6/clock.py#L137), [`clock.session_stamp`](../astra6/clock.py#L113), [`signals.build_context`](../astra6/signals.py#L28)
- **Maliyet ve test** O(1), tarih cache. DST 83.
- **Durum** `VERIFIED_CORRECT`

#### [`is_transition_week`](../astra6/clock.py#L85)

- **İmza** `(d: date)`
- **Girdi ve çıktı** Gün → NY ve UK bayrak dict.
- **Hesap ve işlem yorumu** DST geçişi çevresindeki takvim günlerini işaretler.
- **Zaman, hata ve risk** Bölgesel tarih. Likidite veya kapanış kanıtı değildir.
- **Bağımlılıklar** [`clock.dst_transitions`](../astra6/clock.py#L48)
- **Çağıranlar** [`clock.reference_calendar`](../astra6/clock.py#L137)
- **Maliyet ve test** Yıl geçiş cache'i. DST 83 rejimi, doğrudan flag yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`london_ny_open_gap_minutes`](../astra6/clock.py#L95)

- **İmza** `(d: date)`
- **Girdi ve çıktı** Gün → dakika int.
- **Hesap ve işlem yorumu** İki UTC açılış farkı.
- **Zaman, hata ve risk** Yerel açık piyasa olup olmadığı ayrı.
- **Bağımlılıklar** [`clock.london_open_utc`](../astra6/clock.py#L38), [`clock.nasdaq_open_utc`](../astra6/clock.py#L34)
- **Çağıranlar** [`clock.reference_calendar`](../astra6/clock.py#L137)
- **Maliyet ve test** O(1). DST 83.
- **Durum** `VERIFIED_CORRECT`

#### [`session_stamp`](../astra6/clock.py#L113)

- **İmza** `(d: date)`
- **Girdi ve çıktı** Gün → SessionStamp.
- **Hesap ve işlem yorumu** İki UTC açılışı ve NY/Londra/İstanbul görünümleri.
- **Zaman, hata ve risk** Dönüşüm, sinyal zamanı değil.
- **Bağımlılıklar** [`clock.dst_regime`](../astra6/clock.py#L64), [`clock.london_open_utc`](../astra6/clock.py#L38), [`clock.nasdaq_open_utc`](../astra6/clock.py#L34)
- **Çağıranlar** [`app.py` modül akışı](../app.py)
- **Maliyet ve test** O(1). DST 101.
- **Durum** `VERIFIED_CORRECT`

#### [`_calendar`](../astra6/clock.py#L132)

- **İmza** `(code: str, start: str, end: str)`
- **Girdi ve çıktı** Kod, tarih aralığı → exchange_calendars takvimi.
- **Hesap ve işlem yorumu** Takvimi desteklenen tarih aralığında getirir.
- **Zaman, hata ve risk** Sembolün broker seansı değildir. Takvim hatası dışarı çıkar.
- **Bağımlılıklar** `exchange_calendars`, `functools.lru_cache`
- **Çağıranlar** [`clock.reference_calendar`](../astra6/clock.py#L137)
- **Maliyet ve test** Takvim inşa/cache. DST 113 dolaylı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`reference_calendar`](../astra6/clock.py#L137)

- **İmza** `(start: str, end: str)`
- **Girdi ve çıktı** Başlangıç, bitiş → tarih indeksli Nasdaq/LSE seans ve erken kapanış.
- **Hesap ve işlem yorumu** Resmi seans/erken kapanışları takvimden çıkarır.
- **Zaman, hata ve risk** Referans amaçlı. Üretim quote panelini kesmez.
- **Bağımlılıklar** [`clock._calendar`](../astra6/clock.py#L132), [`clock.dst_regime`](../astra6/clock.py#L64), [`clock.is_transition_week`](../astra6/clock.py#L85), [`clock.london_ny_open_gap_minutes`](../astra6/clock.py#L95), [`clock.london_open_utc`](../astra6/clock.py#L38), [`clock.nasdaq_open_utc`](../astra6/clock.py#L34) · `pandas`
- **Çağıranlar** Üretim ağacında statik çağrı bulunmadı.
- **Maliyet ve test** O(gün). DST 113, üç tarih.
- **Durum** `VERIFIED_CORRECT`

#### [`add_local_times`](../astra6/clock.py#L168)

- **İmza** `(ts_utc: pd.Series | pd.DatetimeIndex)`
- **Girdi ve çıktı** UTC Series/Index → ts_utc, ts_ny, ts_ldn, ts_ist alanlı DataFrame.
- **Hesap ve işlem yorumu** Aynı anın yerel gösterimlerini ekler.
- **Zaman, hata ve risk** Naive giriş UTC kabul edilir.
- **Bağımlılıklar** `pandas`
- **Çağıranlar** Üretim ağacında statik çağrı bulunmadı.
- **Maliyet ve test** O(n). Yerel dönüşümler DST 101 ile dolaylı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`ny_minute_of_day`](../astra6/clock.py#L181)

- **İmza** `(idx: pd.DatetimeIndex)`
- **Girdi ve çıktı** Aware DatetimeIndex → NY dakika dizisi.
- **Hesap ve işlem yorumu** hour×60+minute+second/60.
- **Zaman, hata ve risk** Saniyeyi kesirli dakika olarak taşır. Yerel fold farklı UTC anlarında aynı dakika olabilir.
- **Bağımlılıklar** Çekirdek dil, vektör işlemleri veya I/O.
- **Çağıranlar** Üretim ağacında statik çağrı bulunmadı.
- **Maliyet ve test** O(n). Doğrudan yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

### `astra6/bars.py`

#### [`build_symbol_minutes`](../astra6/bars.py#L57)

- **İmza** `(sym_alias: str, start: date, end: date, side: str='BID')`
- **Girdi ve çıktı** Alias, gün aralığı, taraf → ts/OHLCV.
- **Hesap ve işlem yorumu** Yerel BI5 günlük kayıtlarını decode, concat, dedup ve sort.
- **Zaman, hata ve risk** Eksik dosyalar atlanır. Tüm dosyalar yoksa boş tablo. UTC ofset decoder'dan.
- **Bağımlılıklar** [`download.trading_days`](../astra6/data/download.py#L135), [`dukascopy.candle_key`](../astra6/data/dukascopy.py#L44), [`dukascopy.decode_candles`](../astra6/data/dukascopy.py#L58) · `pandas`
- **Çağıranlar** [`bars.write_store`](../astra6/bars.py#L72)
- **Maliyet ve test** Dosya IO + concat/sort. Forensics BI5 karşılaştırması, doğrudan builder yok.
- **Durum** `DATA_LIMITATION`

#### [`write_store`](../astra6/bars.py#L72)

- **İmza** `(start: date, end: date)`
- **Girdi ve çıktı** Gün aralığı → kanonik M1 Parquet yazımı.
- **Hesap ve işlem yorumu** Alias ve taraflar için BI5 builder çağırır.
- **Zaman, hata ve risk** Mevcut depoyu yazabilir. Bu audit çağırmadı.
- **Bağımlılıklar** [`bars.build_symbol_minutes`](../astra6/bars.py#L57)
- **Çağıranlar** Üretim ağacında statik çağrı bulunmadı.
- **Maliyet ve test** IO, tarih aralığı. Doğrudan yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`load_m1`](../astra6/bars.py#L81)

- **İmza** `(alias: str, side: str='BID')`
- **Girdi ve çıktı** Alias/taraf → Parquet ts/OHLCV ve varsa tick alanları.
- **Hesap ve işlem yorumu** Taraf dosyasını okur.
- **Zaman, hata ve risk** Eksik dosya hata. Sıra/tekillik doğrulaması yok.
- **Bağımlılıklar** `pandas`
- **Çağıranlar** [`bars.load_panel`](../astra6/bars.py#L85)
- **Maliyet ve test** Dosya okuma. Altı mevcut dosya okundu, veri sözleşmesi örnekle doğrulandı.
- **Durum** `VERIFIED_CORRECT`

#### [`load_panel`](../astra6/bars.py#L85)

- **İmza** `(aliases=('US100', 'US500', 'US30'), with_ask=True)`
- **Girdi ve çıktı** Alias dizisi ve with_ask → UTC indeksli {alias}_o/h/l/c, ao/ah/al/ac.
- **Hesap ve işlem yorumu** Taraf/simge serilerinin iç zaman kesişimi ve sort.
- **Zaman, hata ve risk** Comparator kaybı traded barı da siler. Eksik dosya hata. Duplicate girdi doğrulaması yok.
- **Bağımlılıklar** [`bars.load_m1`](../astra6/bars.py#L81) · `pandas`
- **Çağıranlar** [`audit.run_independent_audit`](../astra6/audit.py#L477), [`forensics.load_dataset_scenario`](../astra6/data/forensics.py#L401), [`engine.run_all`](../astra6/engine.py#L237), [`engine_v3.run_v3_pipeline`](../astra6/engine_v3.py#L404), [`trade_replay_v34.build_trade_replays`](../astra6/trade_replay_v34.py#L118)
- **Maliyet ve test** O(n×stream), bellekte. QA 07 ve yerel tam panel denetimi.
- **Durum** `DATA_LIMITATION`

#### [`ny_wall_minutes`](../astra6/bars.py#L106)

- **İmza** `(idx: pd.DatetimeIndex)`
- **Girdi ve çıktı** UTC index → NY yerel epoch dakikaları.
- **Hesap ve işlem yorumu** NY wall clock, timezone kaldır, ölçekle.
- **Zaman, hata ve risk** Fallback tekrar saati aynı anahtara düşebilir.
- **Bağımlılıklar** Çekirdek dil, vektör işlemleri veya I/O.
- **Çağıranlar** [`bars.resample`](../astra6/bars.py#L153)
- **Maliyet ve test** O(n). QA 01 dolaylı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`ny_wall_seconds`](../astra6/bars.py#L112)

- **İmza** `(idx: pd.DatetimeIndex)`
- **Girdi ve çıktı** UTC index → NY yerel epoch saniyeleri.
- **Hesap ve işlem yorumu** NY wall clock ve epoch ölçeği.
- **Zaman, hata ve risk** Yerel tekrar saati ayrı UTC anı taşımaz.
- **Bağımlılıklar** Çekirdek dil, vektör işlemleri veya I/O.
- **Çağıranlar** [`bars.quarter_labels`](../astra6/bars.py#L184)
- **Maliyet ve test** O(n). QA 01 dolaylı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`ldn_wall_minutes`](../astra6/bars.py#L118)

- **İmza** `(idx: pd.DatetimeIndex)`
- **Girdi ve çıktı** UTC index → Londra yerel epoch dakikaları.
- **Hesap ve işlem yorumu** Londra wall clock ve epoch ölçeği.
- **Zaman, hata ve risk** Fallback tekrar saati birleşebilir.
- **Bağımlılıklar** Çekirdek dil, vektör işlemleri veya I/O.
- **Çağıranlar** [`bars.resample`](../astra6/bars.py#L153)
- **Maliyet ve test** O(n). QA 01/03 dolaylı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`ldn_wall_seconds`](../astra6/bars.py#L124)

- **İmza** `(idx: pd.DatetimeIndex)`
- **Girdi ve çıktı** UTC index → Londra yerel epoch saniyeleri.
- **Hesap ve işlem yorumu** Londra wall clock ve epoch ölçeği.
- **Zaman, hata ve risk** Tekrar saati aynı anahtar.
- **Bağımlılıklar** Çekirdek dil, vektör işlemleri veya I/O.
- **Çağıranlar** [`bars.quarter_labels`](../astra6/bars.py#L184)
- **Maliyet ve test** O(n). QA 01 dolaylı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`bucket_start_wall`](../astra6/bars.py#L130)

- **İmza** `(wall_min: np.ndarray, tf_min: float, origin_min: float)`
- **Girdi ve çıktı** Dakika dizisi, genişlik, orijin → kova başlangıcı.
- **Hesap ve işlem yorumu** floor((wall−origin)/TF)×TF+origin.
- **Zaman, hata ve risk** TF >0 varsayılır, sınır timestamp açık kovaya ait.
- **Bağımlılıklar** `numpy`
- **Çağıranlar** [`bars.resample`](../astra6/bars.py#L153)
- **Maliyet ve test** O(n). QA 03 dolaylı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`anchor_origin`](../astra6/bars.py#L135)

- **İmza** `(tf: str, anchor: str)`
- **Girdi ve çıktı** TF ve anchor → yerel dakika orijini.
- **Hesap ve işlem yorumu** NY 570, Londra 480, W1 Pazar 18:00 epoch orijini. Bazı HTF NY 18:00.
- **Zaman, hata ve risk** Bilinmeyen anchor varsayılana düşer. TF map yoksa hata.
- **Bağımlılıklar** Çekirdek dil, vektör işlemleri veya I/O.
- **Çağıranlar** [`bars.resample`](../astra6/bars.py#L153)
- **Maliyet ve test** O(1). QA 03 dolaylı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`wall_to_utc`](../astra6/bars.py#L148)

- **İmza** `(wall_min: np.ndarray, tz_name: str=NY)`
- **Girdi ve çıktı** Yerel epoch dakikası/bölge → UTC DatetimeIndex.
- **Hesap ve işlem yorumu** Yerelize, ambiguous→NaT, nonexistent→shift_forward.
- **Zaman, hata ve risk** Ambiguous kimliği korunmaz. resample kendi fallback'ini yapar.
- **Bağımlılıklar** `pandas`
- **Çağıranlar** [`bars.resample`](../astra6/bars.py#L153)
- **Maliyet ve test** O(n). DST seans testleri ayrı, kova testi yok.
- **Durum** `DATA_LIMITATION`

#### [`resample`](../astra6/bars.py#L153)

- **İmza** `(panel: pd.DataFrame, alias: str, tf: str, anchor: str='cal')`
- **Girdi ve çıktı** UTC panel ve alias Bid OHLC → b/o/h/l/c/ts_first/ts_last/n/t_open/t_close/complete.
- **Hesap ve işlem yorumu** Duvar saati kova ve first/max/min/last.
- **Zaman, hata ve risk** Nominal UTC kapanış sabit süre. Son kova koşulsuz false, diğerleri kapsama bakmadan true. Kayıp M1/DST ve prefix sorunu.
- **Bağımlılıklar** [`bars.anchor_origin`](../astra6/bars.py#L135), [`bars.bucket_start_wall`](../astra6/bars.py#L130), [`bars.ldn_wall_minutes`](../astra6/bars.py#L118), [`bars.ny_wall_minutes`](../astra6/bars.py#L106), [`bars.wall_to_utc`](../astra6/bars.py#L148) · `pandas`
- **Çağıranlar** [`audit.audit_100_cisd_events`](../astra6/audit.py#L170), [`audit.audit_100_crt_events`](../astra6/audit.py#L26), [`cisd.extract_tf_cisd_events`](../astra6/cisd.py#L162), [`engine.run_all`](../astra6/engine.py#L237), [`fractal_v3.attach_full_fractal_context`](../astra6/fractal_v3.py#L1191), [`fractal_v3.extract_original_consolidations`](../astra6/fractal_v3.py#L222), [`mmxm.build_mmxm_table`](../astra6/mmxm.py#L84), [`signals.build_context`](../astra6/signals.py#L28), [`signals.extract_crt_events`](../astra6/signals.py#L134)
- **Maliyet ve test** Groupby O(n), kova belleği. QA 03, bağımsız gerçek prefix ve H4 doluluk.
- **Durum** `CAUSALITY_FAILURE`

#### [`quarter_labels`](../astra6/bars.py#L184)

- **İmza** `(idx: pd.DatetimeIndex, qt_anchor: str='ny1800')`
- **Girdi ve çıktı** Aware index ve QT anchor → b6/b90/b22/b5, q*, day_id, saniye ofsetleri.
- **Hesap ve işlem yorumu** floor(seconds/period), mod4+1.
- **Zaman, hata ve risk** Açılış etiketi. M1 22,5 dakikalık sınırı 30s gecikmeli gözleyebilir. Bilinmeyen anchor ValueError.
- **Bağımlılıklar** [`bars.ldn_wall_seconds`](../astra6/bars.py#L124), [`bars.ny_wall_seconds`](../astra6/bars.py#L112) · `numpy`, `pandas`
- **Çağıranlar** [`audit.audit_100_ssmt_events`](../astra6/audit.py#L90), [`engine.extract_full_30s_micro_ssmt_and_attach`](../astra6/engine.py#L175), [`signals.build_context`](../astra6/signals.py#L28)
- **Maliyet ve test** O(n), vektör. QA 01, üç anchor ve sekiz DST sınırı gününde bağımsız kat hesabı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

### `astra6/data/dukascopy.py`

#### [`candle_key`](../astra6/data/dukascopy.py#L44)

- **İmza** `(sym: str, d: date, side: str)`
- **Girdi ve çıktı** Sembol, UTC gün, taraf → anahtar.
- **Hesap ve işlem yorumu** Dukascopy ayı 0 tabanlı dosya adı.
- **Zaman, hata ve risk** UTC tarih. Argüman doğrulaması çağıranda.
- **Bağımlılıklar** Çekirdek dil, vektör işlemleri veya I/O.
- **Çağıranlar** [`bars.build_symbol_minutes`](../astra6/bars.py#L57), [`download.candle_jobs`](../astra6/data/download.py#L143), [`download.priority_jobs`](../astra6/data/download.py#L191), [`forensics.verify_against_raw_bi5_and_ticks`](../astra6/data/forensics.py#L257)
- **Maliyet ve test** O(1). Yerel BI5 okumada dolaylı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`tick_key`](../astra6/data/dukascopy.py#L48)

- **İmza** `(sym: str, d: date, hour: int)`
- **Girdi ve çıktı** Sembol, UTC gün, saat → anahtar.
- **Hesap ve işlem yorumu** Saatlik tick dosya adı.
- **Zaman, hata ve risk** UTC saat. Kayıt zamanı decode'da.
- **Bağımlılıklar** Çekirdek dil, vektör işlemleri veya I/O.
- **Çağıranlar** [`download.tick_jobs`](../astra6/data/download.py#L148)
- **Maliyet ve test** O(1). Doğrudan yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`_decompress`](../astra6/data/dukascopy.py#L52)

- **İmza** `(raw: bytes)`
- **Girdi ve çıktı** BI5 bytes → açık bytes.
- **Hesap ve işlem yorumu** LZMA açılımı.
- **Zaman, hata ve risk** Boş veya bozuk dosya davranışı decoder'ı etkiler.
- **Bağımlılıklar** `lzma`
- **Çağıranlar** [`dukascopy.decode_candles`](../astra6/data/dukascopy.py#L58), [`dukascopy.decode_ticks`](../astra6/data/dukascopy.py#L73)
- **Maliyet ve test** O(bytes). Yerel BI5 örneği dolaylı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`decode_candles`](../astra6/data/dukascopy.py#L58)

- **İmza** `(raw: bytes, sym: str, d: date)`
- **Girdi ve çıktı** Bytes, sembol, UTC gün → ts/open/high/low/close/volume.
- **Hesap ve işlem yorumu** Big-endian kayıt, saniye ofseti ve sembol ölçeği.
- **Zaman, hata ve risk** Fiyatlar kayıt zamanıyla. Boş girdi boş tablo. Kayıt formatına bağımlı.
- **Bağımlılıklar** [`dukascopy._decompress`](../astra6/data/dukascopy.py#L52) · `numpy`, `pandas`
- **Çağıranlar** [`bars.build_symbol_minutes`](../astra6/bars.py#L57), [`forensics.verify_against_raw_bi5_and_ticks`](../astra6/data/forensics.py#L257)
- **Maliyet ve test** O(kayıt). Beş yerel BI5 Bid günü, 6.615 ortak OHLC.
- **Durum** `VERIFIED_CORRECT`

#### [`decode_ticks`](../astra6/data/dukascopy.py#L73)

- **İmza** `(raw: bytes, sym: str, d: date, hour: int)`
- **Girdi ve çıktı** Bytes, sembol, UTC gün/saat → ts/ask/bid/vol.
- **Hesap ve işlem yorumu** Big-endian tick ve milisaniye ofseti.
- **Zaman, hata ve risk** Boş girdi boş tablo. Denetimde HF cache tick'i kullanıldı.
- **Bağımlılıklar** [`dukascopy._decompress`](../astra6/data/dukascopy.py#L52) · `numpy`, `pandas`
- **Çağıranlar** Üretim ağacında statik çağrı bulunmadı.
- **Maliyet ve test** O(kayıt). Doğrudan BI5 tick decode yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

### `astra6/data/download.py`

#### [`RateGate.__init__`](../astra6/data/download.py#L33)

- **İmza** `(self, min_interval: float=4.0)`
- **Girdi ve çıktı** Min interval → paylaşılan kapı.
- **Hesap ve işlem yorumu** Lock, zaman ve bekleme durumu.
- **Zaman, hata ve risk** Araştırma saatiyle ilgisiz.
- **Bağımlılıklar** `threading`
- **Çağıranlar** Üretim ağacında statik çağrı bulunmadı.
- **Maliyet ve test** O(1). Yok, ağ yolu çağrılmadı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`RateGate.wait`](../astra6/data/download.py#L39)

- **İmza** `(self)`
- **Girdi ve çıktı** Kapı → bekleme.
- **Hesap ve işlem yorumu** Thread çağrılarını hız sınırına göre sırala.
- **Zaman, hata ve risk** Wall time ve throttle.
- **Bağımlılıklar** `time`
- **Çağıranlar** [`download.fetch_http`](../astra6/data/download.py#L70)
- **Maliyet ve test** Bloklayıcı. Yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`RateGate.penalise`](../astra6/data/download.py#L47)

- **İmza** `(self, seconds: float)`
- **Girdi ve çıktı** Saniye → kapı gecikmesi.
- **Hesap ve işlem yorumu** Hız sınırı yanıtında beklemeyi artırır.
- **Zaman, hata ve risk** Piyasa zamanına etkisi yok.
- **Bağımlılıklar** `time`
- **Çağıranlar** [`download.fetch_http`](../astra6/data/download.py#L70)
- **Maliyet ve test** O(1). Yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`RateGate.reward`](../astra6/data/download.py#L53)

- **İmza** `(self)`
- **Girdi ve çıktı** Kapı → ayarlanmış gecikme.
- **Hesap ve işlem yorumu** Başarıda beklemeyi azaltır.
- **Zaman, hata ve risk** Zaman yalnız ağ isteği.
- **Bağımlılıklar** Çekirdek dil, vektör işlemleri veya I/O.
- **Çağıranlar** [`download.fetch_http`](../astra6/data/download.py#L70)
- **Maliyet ve test** O(1). Yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`_path`](../astra6/data/download.py#L61)

- **İmza** `(key: str)`
- **Girdi ve çıktı** Uzak key → raw disk yolu.
- **Hesap ve işlem yorumu** Cache köküne birleştirir.
- **Zaman, hata ve risk** Yazım yapan fetch çağrılarının bağı.
- **Bağımlılıklar** Çekirdek dil, vektör işlemleri veya I/O.
- **Çağıranlar** [`download.fetch`](../astra6/data/download.py#L117), [`download.is_cached`](../astra6/data/download.py#L65)
- **Maliyet ve test** O(1). Yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`is_cached`](../astra6/data/download.py#L65)

- **İmza** `(key: str)`
- **Girdi ve çıktı** Key → bool.
- **Hesap ve işlem yorumu** Yerel cache kontrolü.
- **Zaman, hata ve risk** İçerik geçerliği değil.
- **Bağımlılıklar** [`download._path`](../astra6/data/download.py#L61)
- **Çağıranlar** [`download.fetch`](../astra6/data/download.py#L117), [`download.run`](../astra6/data/download.py#L165)
- **Maliyet ve test** Stat IO. Yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`fetch_http`](../astra6/data/download.py#L70)

- **İmza** `(key: str, max_tries: int=40)`
- **Girdi ve çıktı** Key/retry sayısı → bytes veya None.
- **Hesap ve işlem yorumu** RateGate ile HTTP, durum/exception retry.
- **Zaman, hata ve risk** Yerel fiyat denetiminde kullanılmaz. Boş/fail farkı sözleşmeye bağlı.
- **Bağımlılıklar** [`download.RateGate.penalise`](../astra6/data/download.py#L47), [`download.RateGate.reward`](../astra6/data/download.py#L53), [`download.RateGate.wait`](../astra6/data/download.py#L39) · `time`, `urllib.request`
- **Çağıranlar** [`download.fetch`](../astra6/data/download.py#L117)
- **Maliyet ve test** Ağ, retry. Yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`fetch_s3`](../astra6/data/download.py#L102)

- **İmza** `(key: str)`
- **Girdi ve çıktı** Key → bytes veya None.
- **Hesap ve işlem yorumu** S3 alternatifi.
- **Zaman, hata ve risk** Kayıp/erişim hatası sonuç None'a düşebilir.
- **Bağımlılıklar** `boto3`
- **Çağıranlar** [`download.fetch`](../astra6/data/download.py#L117)
- **Maliyet ve test** Ağ. Yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`fetch`](../astra6/data/download.py#L117)

- **İmza** `(key: str)`
- **Girdi ve çıktı** Key → başarı bool ve cache yazımı.
- **Hesap ve işlem yorumu** Cache kontrol, HTTP/S3, yazım.
- **Zaman, hata ve risk** Kısmi dosya ve yazım davranışı bağımsız denenmedi.
- **Bağımlılıklar** [`download._path`](../astra6/data/download.py#L61), [`download.fetch_http`](../astra6/data/download.py#L70), [`download.fetch_s3`](../astra6/data/download.py#L102), [`download.is_cached`](../astra6/data/download.py#L65) · `os`
- **Çağıranlar** Üretim ağacında statik çağrı bulunmadı.
- **Maliyet ve test** Ağ ve IO. Yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`trading_days`](../astra6/data/download.py#L135)

- **İmza** `(start: date, end: date)`
- **Girdi ve çıktı** Başlangıç/bitiş → günler.
- **Hesap ve işlem yorumu** İş oluşturma gün filtresi.
- **Zaman, hata ve risk** Broker seans manifesti değildir.
- **Bağımlılıklar** `datetime.timedelta`
- **Çağıranlar** [`bars.build_symbol_minutes`](../astra6/bars.py#L57), [`download.candle_jobs`](../astra6/data/download.py#L143), [`download.priority_jobs`](../astra6/data/download.py#L191), [`download.tick_jobs`](../astra6/data/download.py#L148)
- **Maliyet ve test** O(gün). Yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`candle_jobs`](../astra6/data/download.py#L143)

- **İmza** `(start: date, end: date, sides=('BID', 'ASK'), symbols=None)`
- **Girdi ve çıktı** Günler, taraflar, simgeler → BI5 key iterable.
- **Hesap ve işlem yorumu** M1 candle key kombinasyonları.
- **Zaman, hata ve risk** Gün bazında, UTC kaynak.
- **Bağımlılıklar** [`download.trading_days`](../astra6/data/download.py#L135), [`dukascopy.candle_key`](../astra6/data/dukascopy.py#L44) · `dukascopy.SYMBOLS`
- **Çağıranlar** [`astra6/data/download.py` modül akışı](../astra6/data/download.py)
- **Maliyet ve test** O(gün×taraf×simge). Yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`tick_jobs`](../astra6/data/download.py#L148)

- **İmza** `(start: date, end: date, ny_hours=(9, 10), symbols=None)`
- **Girdi ve çıktı** Günler, NY saatleri, simgeler → tick keys.
- **Hesap ve işlem yorumu** NY saatini UTC gün ve saate çevirir.
- **Zaman, hata ve risk** Seçilen saatlerle sınırlı.
- **Bağımlılıklar** [`download.trading_days`](../astra6/data/download.py#L135), [`dukascopy.tick_key`](../astra6/data/dukascopy.py#L48) · `datetime.datetime`, `datetime.time`, `dukascopy.SYMBOLS`, `zoneinfo.ZoneInfo`
- **Çağıranlar** [`astra6/data/download.py` modül akışı](../astra6/data/download.py)
- **Maliyet ve test** O(gün×saat×simge). Yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`run`](../astra6/data/download.py#L165)

- **İmza** `(jobs, workers: int=3, label: str='')`
- **Girdi ve çıktı** İş iterable, workers, label → özet dict.
- **Hesap ve işlem yorumu** Thread pool fetch ve sayaç.
- **Zaman, hata ve risk** Üretim cache'i değiştirebilir. Denetimde çağrılmadı.
- **Bağımlılıklar** [`download.is_cached`](../astra6/data/download.py#L65) · `concurrent.futures.ThreadPoolExecutor`, `concurrent.futures.as_completed`, `random`, `time`
- **Çağıranlar** [`astra6/data/download.py` modül akışı](../astra6/data/download.py)
- **Maliyet ve test** Ağ/thread. Yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`priority_jobs`](../astra6/data/download.py#L191)

- **İmza** `(start: date, end: date)`
- **Girdi ve çıktı** Gün aralığı → öncelikli key sırası.
- **Hesap ve işlem yorumu** Öncelikli tarih/iş listesi.
- **Zaman, hata ve risk** Fiyat toplama kararı, analitik emir değil.
- **Bağımlılıklar** [`download.trading_days`](../astra6/data/download.py#L135), [`dukascopy.candle_key`](../astra6/data/dukascopy.py#L44)
- **Çağıranlar** [`astra6/data/download.py` modül akışı](../astra6/data/download.py)
- **Maliyet ve test** O(iş). Yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

### `astra6/data/ingest_hf.py`

#### [`_list_duka_parquets`](../astra6/data/ingest_hf.py#L45)

- **İmza** `(repo: str)`
- **Girdi ve çıktı** Repo → göreli Parquet yolları.
- **Hesap ve işlem yorumu** HF liste cevabından veri parçaları seçilir.
- **Zaman, hata ve risk** Ağ ve yerel cache kaynağı.
- **Bağımlılıklar** `json`, `urllib.request`
- **Çağıranlar** [`ingest_hf.ingest_dukascopy_ticks`](../astra6/data/ingest_hf.py#L119)
- **Maliyet ve test** Ağ. Yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`_process_duka_part`](../astra6/data/ingest_hf.py#L63)

- **İmza** `(repo: str, rel_path: str)`
- **Girdi ve çıktı** Repo, rel_path, ts/Bid/Ask tick → M1, 30s, örnek.
- **Hesap ve işlem yorumu** Tick zaman normalize ve dinamik first/max/min/last.
- **Zaman, hata ve risk** Fiyat gözlenen quote, aynı zamanlı tick sırası etkileyebilir.
- **Bağımlılıklar** `pathlib.Path`, `polars`, `time`
- **Çağıranlar** Üretim ağacında statik çağrı bulunmadı.
- **Maliyet ve test** Polars groupby ve cache IO. Yerel tick→M1/30s örtüşme doğrulandı.
- **Durum** `DATA_LIMITATION`

#### [`ingest_dukascopy_ticks`](../astra6/data/ingest_hf.py#L119)

- **İmza** `(workers: int=8)`
- **Girdi ve çıktı** Workers → parça ve birleşik DUKA dosyaları.
- **Hesap ve işlem yorumu** Simgeleri indirir/okur, parça sonuçlarını birleştirir.
- **Zaman, hata ve risk** Audit mevcut veriyi okudu.
- **Bağımlılıklar** [`ingest_hf._list_duka_parquets`](../astra6/data/ingest_hf.py#L45), [`ingest_hf.ingest_dukascopy_ticks._merge_buckets`](../astra6/data/ingest_hf.py#L139) · `concurrent.futures.ThreadPoolExecutor`, `concurrent.futures.as_completed`, `polars`, `time`
- **Çağıranlar** [`astra6/data/ingest_hf.py` modül akışı](../astra6/data/ingest_hf.py)
- **Maliyet ve test** Thread ve Parquet IO. Yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`ingest_dukascopy_ticks._merge_buckets`](../astra6/data/ingest_hf.py#L139)

- **İmza** `(parts: list[pl.DataFrame], every: str)`
- **Girdi ve çıktı** OHLC bucket parçaları ve every → birleşik bucket frame.
- **Hesap ve işlem yorumu** Sınır kovalarını first/max/min/last ve adetle tekrar toplar.
- **Zaman, hata ve risk** Parça zaman sırası ve eşit tick sınırları önemli.
- **Bağımlılıklar** `polars`
- **Çağıranlar** [`ingest_hf.ingest_dukascopy_ticks`](../astra6/data/ingest_hf.py#L119)
- **Maliyet ve test** Polars groupby. Örtüşme örneği dolaylı.
- **Durum** `DATA_LIMITATION`

#### [`_fetch_oanda_month`](../astra6/data/ingest_hf.py#L174)

- **İmza** `(repo: str, path: str)`
- **Girdi ve çıktı** Repo/path → aylık ts/OHLCV.
- **Hesap ve işlem yorumu** CSV okuma ve zaman normalize.
- **Zaman, hata ve risk** OANDA tarafı gözlenen iki taraflı Bid/Ask değildir.
- **Bağımlılıklar** `pathlib.Path`, `polars`, `time`
- **Çağıranlar** Üretim ağacında statik çağrı bulunmadı.
- **Maliyet ve test** Ağ/cache IO. Yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`ingest_oanda_5y`](../astra6/data/ingest_hf.py#L192)

- **İmza** `(workers: int=8)`
- **Girdi ve çıktı** Workers → OANDA M1 dosyaları.
- **Hesap ve işlem yorumu** Aylık sonuçları concat/sort/dedup.
- **Zaman, hata ve risk** Kaynak CSV kapsamına bağımlı.
- **Bağımlılıklar** `concurrent.futures.ThreadPoolExecutor`, `concurrent.futures.as_completed`, `json`, `polars`, `time`, `urllib.request`
- **Çağıranlar** [`astra6/data/ingest_hf.py` modül akışı](../astra6/data/ingest_hf.py)
- **Maliyet ve test** Ağ ve Parquet IO. Yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`build_unified_stores`](../astra6/data/ingest_hf.py#L226)

- **İmza** `()`
- **Girdi ve çıktı** DUKA ve OANDA Parquet → altı kanonik store dosyası.
- **Hesap ve işlem yorumu** İki endekste örtüşme median basis ve saat median spread. US30 model spread.
- **Zaman, hata ve risk** Gözlenen/derived ayrımı gerekir. Örtüşme ve seans varsayımı sabit. Yeniden inşa edilmedi.
- **Bağımlılıklar** [`ingest_hf.build_unified_stores._extend_with_oanda`](../astra6/data/ingest_hf.py#L275) · `polars`
- **Çağıranlar** [`astra6/data/ingest_hf.py` modül akışı](../astra6/data/ingest_hf.py)
- **Maliyet ve test** Tam store IO. Forensics ve altı dosya audit.
- **Durum** `DATA_LIMITATION`

#### [`build_unified_stores._extend_with_oanda`](../astra6/data/ingest_hf.py#L275)

- **İmza** `(duka_df: pl.DataFrame, oanda_df: pl.DataFrame, basis: float, sp_map: dict)`
- **Girdi ve çıktı** DUKA/OANDA frame, basis, spread map → birleşik OHLC quote.
- **Hesap ve işlem yorumu** Kesim sonrası OANDA−basis ve Ask=OHLC+spread.
- **Zaman, hata ve risk** Model spread saat UTC. Örtüşme boşsa baz sorunu. h_first kapanış rengi vekili.
- **Bağımlılıklar** `polars`
- **Çağıranlar** [`ingest_hf.build_unified_stores`](../astra6/data/ingest_hf.py#L226)
- **Maliyet ve test** Polars vektör. Store kaynak ve spread denetimi.
- **Durum** `DATA_LIMITATION`

### `astra6/data/forensics.py`

#### [`sha256_full_file`](../astra6/data/forensics.py#L192)

- **İmza** `(path: Path)`
- **Girdi ve çıktı** Path → tam SHA256.
- **Hesap ve işlem yorumu** Blok blok bütün dosyayı hash'ler.
- **Zaman, hata ve risk** IO hatası çıkar.
- **Bağımlılıklar** `hashlib`
- **Çağıranlar** [`forensics.audit_all_store_files`](../astra6/data/forensics.py#L204)
- **Maliyet ve test** O(bytes). Bağımsız full manifest karşılaştırması.
- **Durum** `VERIFIED_CORRECT`

#### [`audit_all_store_files`](../astra6/data/forensics.py#L204)

- **İmza** `()`
- **Girdi ve çıktı** Yerel Parquet → dosya ve fiyat kalite DataFrame.
- **Hesap ve işlem yorumu** Hash, tarih, count, duplicate/gap/spread ve sağlayıcı etiketleri.
- **Zaman, hata ve risk** Etiketler metadata/config. Boş ya da missing store kapsamı sınırlı.
- **Bağımlılıklar** [`forensics.sha256_full_file`](../astra6/data/forensics.py#L192) · `datetime.datetime`, `numpy`, `pandas`, `polars`
- **Çağıranlar** [`forensics.run_data_forensics`](../astra6/data/forensics.py#L483)
- **Maliyet ve test** Tarama ve IO. QA 02 hazır tablo, bağımsız altı dosya.
- **Durum** `DATA_LIMITATION`

#### [`verify_against_raw_bi5_and_ticks`](../astra6/data/forensics.py#L257)

- **İmza** `()`
- **Girdi ve çıktı** Yerel BI5 ve tick sample → karşılaştırma dict.
- **Hesap ve işlem yorumu** OHLC karşılaştırma ve exact close oranı.
- **Zaman, hata ve risk** Örtüşen örnek. PASS tick high/low ve M1 close, tüm BI5 koşulu değil.
- **Bağımlılıklar** [`dukascopy.candle_key`](../astra6/data/dukascopy.py#L44), [`dukascopy.decode_candles`](../astra6/data/dukascopy.py#L58) · `datetime.date`, `polars`
- **Çağıranlar** [`forensics.run_data_forensics`](../astra6/data/forensics.py#L483)
- **Maliyet ve test** Örnek groupby + store okuma. QA 02 statik, gerçek fonksiyon bağımsız çalıştırıldı.
- **Durum** `DATA_LIMITATION`

#### [`analyze_cross_broker_divergence`](../astra6/data/forensics.py#L348)

- **İmza** `()`
- **Girdi ve çıktı** DUKA/OANDA store → karşılaştırma dict.
- **Hesap ve işlem yorumu** Örtüşme ve fark/return ölçümleri.
- **Zaman, hata ve risk** Benzer fiyat, aynı icra anlamına gelmez.
- **Bağımlılıklar** `numpy`, `polars`
- **Çağıranlar** [`forensics.run_data_forensics`](../astra6/data/forensics.py#L483)
- **Maliyet ve test** Join ve istatistik O(n). Yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`load_dataset_scenario`](../astra6/data/forensics.py#L401)

- **İmza** `(scenario: str='A_PURE_DUKASCOPY')`
- **Girdi ve çıktı** A/B/C → panel, provenance dict.
- **Hesap ve işlem yorumu** A iki DUKA, B üç OANDA + model spread, C birleşik store.
- **Zaman, hata ve risk** Kesişim ve UTC saati spread. Bilinmeyen senaryo ValueError.
- **Bağımlılıklar** [`bars.load_panel`](../astra6/bars.py#L85) · `numpy`, `pandas`, `polars`
- **Çağıranlar** [`engine.run_all`](../astra6/engine.py#L237)
- **Maliyet ve test** Tam store IO. C panel denetimi, A/B tam backtest yok.
- **Durum** `DATA_LIMITATION`

#### [`run_data_forensics`](../astra6/data/forensics.py#L483)

- **İmza** `()`
- **Girdi ve çıktı** Yerel store → manifest ve JSON.
- **Hesap ve işlem yorumu** Hash, örnek raw ve provider denetimini çağırır.
- **Zaman, hata ve risk** Çıktıları yazar. Status üretim ara varsayımına bağlı.
- **Bağımlılıklar** [`forensics.analyze_cross_broker_divergence`](../astra6/data/forensics.py#L348), [`forensics.audit_all_store_files`](../astra6/data/forensics.py#L204), [`forensics.verify_against_raw_bi5_and_ticks`](../astra6/data/forensics.py#L257) · `datetime.datetime`, `json`
- **Çağıranlar** [`engine.run_all`](../astra6/engine.py#L237), [`astra6/data/forensics.py` modül akışı](../astra6/data/forensics.py)
- **Maliyet ve test** Birkaç tam tarama. QA 02 hazır çıktı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

### `astra6/ict.py`

#### [`atr_wilder`](../astra6/ict.py#L14)

- **İmza** `(h, l, c, n)`
- **Girdi ve çıktı** Aligned H/L/C, period → ATR array.
- **Hesap ve işlem yorumu** TR=max(H−L,abs(H−prevC),abs(L−prevC)). Running mean first n, then ((n−1)ATR+TR)/n.
- **Zaman, hata ve risk** Kapanış i. Boşta boş. n pozitif/finite girdi varsayar.
- **Bağımlılıklar** `numba.njit`, `numpy`
- **Çağıranlar** [`cisd.extract_tf_cisd_events`](../astra6/cisd.py#L162), [`fractal_v3.extract_original_consolidations`](../astra6/fractal_v3.py#L222), [`mmxm.build_mmxm_table`](../astra6/mmxm.py#L84), [`signals.build_context`](../astra6/signals.py#L28), [`signals.extract_crt_events`](../astra6/signals.py#L134)
- **Maliyet ve test** Numba O(n). Gerçek olay ATR ve stop eşleşti, ayrı kapsamlı sayısal test yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`fractal_swings`](../astra6/ict.py#L34)

- **İmza** `(h, l, left, right)`
- **Girdi ve çıktı** H/L, sol/sağ genişlik → iki flag.
- **Hesap ve işlem yorumu** Pivot ekstremi komşularla kıyaslanır. Sol eşitlik reddedilir, sağ eşitlik kabul.
- **Zaman, hata ve risk** Sağ bar kapanmadan pivot bilinmez. Aynı boyut varsayılır.
- **Bağımlılıklar** `numba.njit`, `numpy`
- **Çağıranlar** [`ict.swing_table`](../astra6/ict.py#L57)
- **Maliyet ve test** Numba O(n×width). Doğrudan yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`swing_table`](../astra6/ict.py#L57)

- **İmza** `(bars: pd.DataFrame, left=2, right=2, tf_minutes=5)`
- **Girdi ve çıktı** OHLC h/l/t_open/t_close ve pencere → kind/price/t_pivot/t_known.
- **Hesap ve işlem yorumu** Pivotu right bar sonraki kapanışa bağlar.
- **Zaman, hata ve risk** Girdi complete filtresi burada yok. tf_minutes kullanılmaz.
- **Bağımlılıklar** [`ict.fractal_swings`](../astra6/ict.py#L34) · `numpy`, `pandas`
- **Çağıranlar** [`signals.build_context`](../astra6/signals.py#L28)
- **Maliyet ve test** Tarama/sort. QA 09 swing_stop dolaylı.
- **Durum** `TEST_COVERAGE_GAP`

#### [`last_known_swing`](../astra6/ict.py#L73)

- **İmza** `(t_query, sw_t_known, sw_price, sw_kind_is_high, want_high, above, ref_price, max_back)`
- **Girdi ve çıktı** Sıralı zaman/fiyat/tür dizileri, arama yönü ve max_back → fiyat veya NaN.
- **Hesap ve işlem yorumu** Binary search ardından uygun taraftaki en yakın swing.
- **Zaman, hata ve risk** <=t. Sıralı giriş varsayımı. Limit dışındaki seviye görülmez.
- **Bağımlılıklar** `numba.njit`, `numpy`
- **Çağıranlar** [`signals.materialize_entries`](../astra6/signals.py#L219)
- **Maliyet ve test** Numba O(q(log n + max_back)). QA 09 dolaylı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`fvg_table`](../astra6/ict.py#L101)

- **İmza** `(bars: pd.DataFrame)`
- **Girdi ve çıktı** h/l/t_close → kind/top/bottom/t_known.
- **Hesap ve işlem yorumu** Üç mumda L_i>H_i−2 veya H_i<L_i−2.
- **Zaman, hata ve risk** Üçüncü bar kapanışı. Aynı isimde ayrı CRT/MMXM hesapları var.
- **Bağımlılıklar** `numpy`, `pandas`
- **Çağıranlar** Üretim ağacında statik çağrı bulunmadı.
- **Maliyet ve test** O(n). İç çağrı ve doğrudan test yok.
- **Durum** `DEAD_OR_UNUSED_CODE`

#### [`period_levels`](../astra6/ict.py#L114)

- **İmza** `(bars: pd.DataFrame, prefix: str)`
- **Girdi ve çıktı** h/l/o/c/t_close, prefix → t_known/prefixed OHLC.
- **Hesap ve işlem yorumu** Son kapanan dönem OHLC'sini yayınlar.
- **Zaman, hata ve risk** Dönem kaydırma as-of seçicide. Complete kontrolü çağıranda.
- **Bağımlılıklar** `pandas`
- **Çağıranlar** [`signals.build_context`](../astra6/signals.py#L28)
- **Maliyet ve test** O(n). QA 09 dolaylı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`asof_join`](../astra6/ict.py#L124)

- **İmza** `(times: pd.Series | np.ndarray, table: pd.DataFrame, cols, time_col='t_known')`
- **Girdi ve çıktı** Times, olay tablosu, columns, time_col → seçilen sütunlar.
- **Hesap ve işlem yorumu** Milisaniye UTC backward merge ve orijinal sıra.
- **Zaman, hata ve risk** <= sorgu. Eşit zaman ve NaT sözleşmesi, ms çözünürlük. Geleceğe yanlış damgalı olayları ayırt etmez.
- **Bağımlılıklar** `numpy`, `pandas`
- **Çağıranlar** [`fractal_v3.attach_full_fractal_context`](../astra6/fractal_v3.py#L1191), [`mmxm.attach_mmxm_to_signals`](../astra6/mmxm.py#L107), [`signals.materialize_entries`](../astra6/signals.py#L219)
- **Maliyet ve test** Sort ve join. M15 fiyatı için tam Model 1 as-of eşleşmesi, kaynak zaman ayrı.
- **Durum** `VERIFIED_CORRECT`

### `astra6/crt.py`

#### [`_series_open_bear`](../astra6/crt.py#L38)

- **İmza** `(o, c, j, lo)`
- **Girdi ve çıktı** O/C, j, lookback lower → ref open.
- **Hesap ve işlem yorumu** Yukarı kapanan teslimat zincirinin ilk açılışı, yoksa mum gövde vekili.
- **Zaman, hata ve risk** Sadece j ve öncesi. İndeks doğrulaması çağıranda.
- **Bağımlılıklar** `numba.njit`
- **Çağıranlar** [`crt.scan_crt`](../astra6/crt.py#L63)
- **Maliyet ve test** Numba O(lookback). QA 03, tek olay CRT tetik.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`_series_open_bull`](../astra6/crt.py#L51)

- **İmza** `(o, c, j, lo)`
- **Girdi ve çıktı** O/C, j, lookback lower → ref open.
- **Hesap ve işlem yorumu** Aşağı kapanan zincirin ilk açılışı, yoksa ters gövde vekili.
- **Zaman, hata ve risk** Sadece j ve öncesi.
- **Bağımlılıklar** `numba.njit`
- **Çağıranlar** [`crt.scan_crt`](../astra6/crt.py#L63)
- **Maliyet ve test** Numba O(lookback). QA 03 dolaylı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`scan_crt`](../astra6/crt.py#L63)

- **İmza** `(o, h, l, c, atr, ch, cl, i0, i1, Href, Lref, cHref, cLref, valid, ext, disp_k)`
- **Girdi ve çıktı** M1 OHLC/ATR, comparator H/L, kova sınırları/referans H/L ve valid/extension → [bar,dir,7] olay indeksleri ve CISD ekstremi.
- **Hesap ve işlem yorumu** Sweep, opposing sweep, reclaim, gövde kırılımı, displacement FVG ve peer kırılımı.
- **Zaman, hata ve risk** Comparator/CRT içi CISD pencere sonu+ext bakar. İndeksler olay zamanı olarak sorgulanmalı. Sabit iki comparator çıktı kapasitesi.
- **Bağımlılıklar** [`crt._series_open_bear`](../astra6/crt.py#L38), [`crt._series_open_bull`](../astra6/crt.py#L51) · `numba.njit`, `numpy`
- **Çağıranlar** [`signals.extract_crt_events`](../astra6/signals.py#L134)
- **Maliyet ve test** Numba O(pencere×peer). QA 03/04, UEV 884 sweep/reclaim/CISD.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`running_extreme`](../astra6/crt.py#L195)

- **İmza** `(h, l, a, b, want_high)`
- **Girdi ve çıktı** H/L, a/b inclusive, high seçimi → max/min.
- **Hesap ve işlem yorumu** Kapsamın ekstremi.
- **Zaman, hata ve risk** a<0 veya b<a NaN. Üst sınır çağıranda.
- **Bağımlılıklar** `numba.njit`
- **Çağıranlar** [`engine._add_mtf_cisd_and_nested`](../astra6/engine.py#L119), [`signals.materialize_entries`](../astra6/signals.py#L219)
- **Maliyet ve test** Numba O(b−a). QA 03/09 dolaylı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`classify_confirmed`](../astra6/crt.py#L212)

- **İmza** `(bars: pd.DataFrame, d: int, strong_body=0.5)`
- **Girdi ve çıktı** o/h/l/c, Hr/Lr/Or/Cr, sw/ot, yön, eşik → A/B/C/D/J/K bayrakları.
- **Hesap ve işlem yorumu** Referans içinde kapanış, tek/çift sweep ve gövde konumu varyantları.
- **Zaman, hata ve risk** Kova kapanışından önce A veya diğer teyitli bayrak bilinmez.
- **Bağımlılıklar** `numpy`, `pandas`
- **Çağıranlar** [`signals.extract_crt_events`](../astra6/signals.py#L134)
- **Maliyet ve test** Vektör O(n). QA 03 ve UEV 884 A.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

### `astra6/smt.py`

#### [`_block_extremes`](../astra6/smt.py#L42)

- **İmza** `(h, l, starts, ends)`
- **Girdi ve çıktı** H/L ve başlangıç/son dizisi → Hmax/Lmin.
- **Hesap ve işlem yorumu** Her kova min/max.
- **Zaman, hata ve risk** Önceki tamamlanmış gözlem kümesi. Boş kova varsayılmaz.
- **Bağımlılıklar** `numba.njit`, `numpy`
- **Çağıranlar** [`smt.ssmt_events`](../astra6/smt.py#L102)
- **Maliyet ve test** Numba O(n). QA 04 dolaylı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`_scan_pair`](../astra6/smt.py#L53)

- **İmza** `(ha, la, hb, lb, s, e, e_inv, HA, LA, HB, LB)`
- **Girdi ve çıktı** İki H/L, baş/son/invalidation sınırı, iki ref range → dört yön/lead form-inv çifti.
- **Hesap ve işlem yorumu** Running ekstrem referansı tek taraflı geçerse oluşum, peer sonra geçerse invalidation.
- **Zaman, hata ve risk** Aynı barda ikisi geçerse tek taraflı sinyal yok. İleri inv geçmişte kullanılmamalı.
- **Bağımlılıklar** `numba.njit`, `numpy`
- **Çağıranlar** [`smt.ssmt_events`](../astra6/smt.py#L102)
- **Maliyet ve test** Numba O(window). QA 04, macro denetim çıktısı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`ssmt_events`](../astra6/smt.py#L102)

- **İmza** `(panel: pd.DataFrame, qlab: pd.DataFrame, traded: str, comp: str, level: str='macro')`
- **Girdi ve çıktı** Panel iki H/L, QT b/q kolonları, traded/comp, level → pair, dir/lead/j_form/j_inv/t_form/t_inv.
- **Hesap ve işlem yorumu** Altı aynı üst döngü geçişi ve Q4→Q1 dahil ref bulur, scan_pair uygular.
- **Zaman, hata ve risk** Girdi ref kova kapsaması yok, t_form/t_inv M1 açılışı, bilgi close. Eksik simge boş, kötü level ValueError.
- **Bağımlılıklar** [`smt._block_extremes`](../astra6/smt.py#L42), [`smt._scan_pair`](../astra6/smt.py#L53) · `numpy`, `pandas`
- **Çağıranlar** [`audit.audit_100_ssmt_events`](../astra6/audit.py#L90), [`engine.extract_full_30s_micro_ssmt_and_attach`](../astra6/engine.py#L175), [`signals.build_context`](../astra6/signals.py#L28)
- **Maliyet ve test** O(n×aktif geçişler). QA 04, ayrıca 96 gerçek macro/micro form ve invalidation.
- **Durum** `DATA_LIMITATION`

#### [`attach_ssmt`](../astra6/smt.py#L187)

- **İmza** `(sig: pd.DataFrame, ev: pd.DataFrame, level: str, max_age_quarters: int=1, lead: str | None=None, prefix: str | None=None)`
- **Girdi ve çıktı** j_trig/dir/b*_trig, SSMT tablo, yaş/lead/prefix → active, count, pairs, lead, jform/qref/qtrig.
- **Hesap ve işlem yorumu** Backward search, aynı yön, geçersiz olmamış ve yaş penceresi.
- **Zaman, hata ve risk** Boş olay default false. 500 sınır. Yeniden tetiklenen politika bağlamını çağıran yenilemez.
- **Bağımlılıklar** `numpy`
- **Çağıranlar** [`engine.extract_full_30s_micro_ssmt_and_attach`](../astra6/engine.py#L175), [`engine.run_all`](../astra6/engine.py#L237), [`signals.materialize_entries`](../astra6/signals.py#L219)
- **Maliyet ve test** O(q(log n+500)) Python. QA 04 ve kaynak faktör zaman denetimi.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

### `astra6/cisd.py`

#### [`_scan_tf_cisd`](../astra6/cisd.py#L34)

- **İmza** `(o, h, l, c, atr, allow_pause: bool, req_disp: bool)`
- **Girdi ve çıktı** O/H/L/C, ATR, pause ve displacement seçenekleri → yön/delivery/ext/conf/inv/ref/break dizileri.
- **Hesap ve işlem yorumu** Teslimat zinciri ilk açılışı ve ters gövde kırılımı. V2 ≥0,35 ATR.
- **Zaman, hata ve risk** Onay kapanışta. Sonraki 24 barda inv retrospektif bilgi. Sabit şekil varsayar.
- **Bağımlılıklar** `numba.njit`, `numpy`
- **Çağıranlar** [`cisd.extract_tf_cisd_events`](../astra6/cisd.py#L162)
- **Maliyet ve test** Numba O(n×24), iki yön. QA 05, ayrıca ilk 17.000 M1 ve 7 TF bağımsız V1 teyitleri.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`extract_tf_cisd_events`](../astra6/cisd.py#L162)

- **İmza** `(panel: pd.DataFrame, traded: str='US100', tf: str='M1', variant: str='v1')`
- **Girdi ve çıktı** UTC panel, traded, TF, variant → cisd_tf/dir/tf_*_idx/j_*_m1/ref_open/extreme_px/break_close/t_confirm.
- **Hesap ve işlem yorumu** M1 doğrudan, diğerleri ayrı resample ve ATR.
- **Zaman, hata ve risk** t_confirm TF close. Son M1 indeksine geri map gap'te daha erken. V2 dışı variant V1 davranışı.
- **Bağımlılıklar** [`bars.resample`](../astra6/bars.py#L153), [`cisd._scan_tf_cisd`](../astra6/cisd.py#L34), [`ict.atr_wilder`](../astra6/ict.py#L14) · `numpy`, `pandas`
- **Çağıranlar** [`audit.audit_100_cisd_events`](../astra6/audit.py#L170), [`signals.build_context`](../astra6/signals.py#L28)
- **Maliyet ve test** Groupby, Numba, searchsorted. QA 05, UEV gerçek teyitleri.
- **Durum** `DATA_LIMITATION`

#### [`_match_post_sweep_cisd_numba`](../astra6/cisd.py#L227)

- **İmza** `(jsw: np.ndarray, sd: np.ndarray, jc: np.ndarray, ji: np.ndarray, dr: np.ndarray, ro: np.ndarray, epx: np.ndarray, max_wait_m1: int)`
- **Girdi ve çıktı** Sweep/yön, sıralı event ve ref/ext dizileri, wait → j_post, delay, ref, ext.
- **Hesap ve işlem yorumu** İlk aynı yönlü teyit, 64 event cap, geçersiz olmayan teyit.
- **Zaman, hata ve risk** j>=sweep ve j<=sweep+wait. `j_inv>j_conf` aday stop ihlalini ölçmez. Delay gözlem sayısı.
- **Bağımlılıklar** `numba.njit`, `numpy`
- **Çağıranlar** [`cisd.attach_true_cisd_to_signals`](../astra6/cisd.py#L280)
- **Maliyet ve test** O(q(log n+64)). V3 363 yalnız toplulaştırma.
- **Durum** `TEST_COVERAGE_GAP`

#### [`attach_true_cisd_to_signals`](../astra6/cisd.py#L280)

- **İmza** `(sig: pd.DataFrame, cisd_tables: dict[str, pd.DataFrame], max_lookback_m1: int=30)`
- **Girdi ve çıktı** j_trig/j_sweep/j_open/dir/has_cisd + TF tabloları → cisd flags, karşı/expired, ref, post/delay/ext.
- **Hesap ve işlem yorumu** Backward active ve forward first. CRT içi M1'i erken ise birleştirir.
- **Zaman, hata ve risk** min yaş sınırı katı değil. Kaynak M1 event ve ext uyuşmazlığı. İleri eşleme ayrı kalmalı.
- **Bağımlılıklar** [`cisd._match_post_sweep_cisd_numba`](../astra6/cisd.py#L227) · `numpy`
- **Çağıranlar** [`fractal_v3.attach_full_fractal_context`](../astra6/fractal_v3.py#L1191), [`signals.materialize_entries`](../astra6/signals.py#L219)
- **Maliyet ve test** O(TF×q×(log n+80)). QA 05, V3 695 ve ham olay farkı.
- **Durum** `SEMANTIC_MISMATCH`

### `astra6/mmxm.py`

#### [`_scan_m5_consolidation_and_fvg`](../astra6/mmxm.py#L31)

- **İmza** `(o5, h5, l5, c5, atr5)`
- **Girdi ve çıktı** M5 O/H/L/C ve ATR → cons hi/lo/age ve bull/bear FVG/disp.
- **Hesap ve işlem yorumu** 4 bar bant ≤2,5 ATR, son iki 3-bar gap ve ≥0,85 ATR gövde.
- **Zaman, hata ve risk** M5 close. Docstring 3–6 ve 2,4 diyor, kod 4 ve 2,5.
- **Bağımlılıklar** `numba.njit`, `numpy`
- **Çağıranlar** [`mmxm.build_mmxm_table`](../astra6/mmxm.py#L84)
- **Maliyet ve test** Numba O(n). QA 06 yalnız hazır proxy.
- **Durum** `SEMANTIC_MISMATCH`

#### [`build_mmxm_table`](../astra6/mmxm.py#L84)

- **İmza** `(panel: pd.DataFrame, traded: str='US100')`
- **Girdi ve çıktı** Panel ve traded → M5 t_known ve bant/FVG/disp.
- **Hesap ve işlem yorumu** M5 resample + ATR + tarayıcı.
- **Zaman, hata ve risk** M5 kapanış, resample sınırı miras.
- **Bağımlılıklar** [`bars.resample`](../astra6/bars.py#L153), [`ict.atr_wilder`](../astra6/ict.py#L14), [`mmxm._scan_m5_consolidation_and_fvg`](../astra6/mmxm.py#L31) · `pandas`
- **Çağıranlar** [`signals.build_context`](../astra6/signals.py#L28)
- **Maliyet ve test** O(n) ve groupby. QA 06 dolaylı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`attach_mmxm_to_signals`](../astra6/mmxm.py#L107)

- **İmza** `(sig: pd.DataFrame, mmxm_tbl: pd.DataFrame, panel: pd.DataFrame, traded: str='US100')`
- **Girdi ve çıktı** Sinyal t_trig, sweep/HTF/CISD/disp, M5 tablo → stage, early/confirmed, model, target.
- **Hesap ve işlem yorumu** As-of M5 + boolean aşama 1/2/4–8. OC yaş ≤48. Hedef uzak kenar.
- **Zaman, hata ve risk** t_trig açılışı. V2 snapshot proxy, bağımsız yaşam döngüsü değil. Bazı argümanlar kullanılmaz.
- **Bağımlılıklar** [`ict.asof_join`](../astra6/ict.py#L124) · `numpy`, `pandas`
- **Çağıranlar** [`signals.materialize_entries`](../astra6/signals.py#L219)
- **Maliyet ve test** Sort/merge ve O(n). QA 06, QA 09.
- **Durum** `SEMANTIC_MISMATCH`

### `astra6/signals.py`

#### [`build_context`](../astra6/signals.py#L28)

- **İmza** `(panel: pd.DataFrame, traded: str='US100', comps: tuple[str, ...]=('US500', 'US30'), qt_anchor: str='ny1800', dataset_tag: str='C_MIXED_EXTENDED')`
- **Girdi ve çıktı** UTC M1 panel, traded, comps, anchor/tag → ctx dict.
- **Hesap ve işlem yorumu** ATR, D1/H4/H1/M5, swing, PD/PW, 7 CISD, M1 V2, QT, V2 MMXM ve SSMT.
- **Zaman, hata ve risk** Eksik tüm comparators için avail_comps[0] hatası. MTF ve haftalık zaman sınırları taşınır.
- **Bağımlılıklar** [`bars.quarter_labels`](../astra6/bars.py#L184), [`bars.resample`](../astra6/bars.py#L153), [`cisd.extract_tf_cisd_events`](../astra6/cisd.py#L162), [`clock.dst_regime`](../astra6/clock.py#L64), [`ict.atr_wilder`](../astra6/ict.py#L14), [`ict.period_levels`](../astra6/ict.py#L114), [`ict.swing_table`](../astra6/ict.py#L57), [`mmxm.build_mmxm_table`](../astra6/mmxm.py#L84), [`smt.ssmt_events`](../astra6/smt.py#L102) · `pandas`
- **Çağıranlar** [`engine.run_all`](../astra6/engine.py#L237), [`engine_v3.run_v3_pipeline`](../astra6/engine_v3.py#L404)
- **Maliyet ve test** Çoklu groupby ve tarayıcı, tam panel. QA 01/03/04/09, 1.300 gerçek bar örneği.
- **Durum** `DATA_LIMITATION`

#### [`extract_crt_events`](../astra6/signals.py#L134)

- **İmza** `(ctx: dict, tf: str='M15', anchor: str='cal', max_bars: int | None=None)`
- **Girdi ve çıktı** ctx, TF, anchor, max_bars → OHLC/ref, j_open/close/sweep/reclaim/cisd/disp/cmp, A–K, derinlik.
- **Hesap ve işlem yorumu** Kova M1 map, önceki ref/ATR, CRT taraması, `np.roll` varyantları.
- **Zaman, hata ve risk** F sonraki kapanış, H önceki sweep, sınır sarma riski. Kapsama ve gap filtresi nominal. Çok kısa bağlam hassas.
- **Bağımlılıklar** [`bars.resample`](../astra6/bars.py#L153), [`crt.classify_confirmed`](../astra6/crt.py#L212), [`crt.scan_crt`](../astra6/crt.py#L63), [`ict.atr_wilder`](../astra6/ict.py#L14) · `numpy`, `pandas`
- **Çağıranlar** [`engine.run_all`](../astra6/engine.py#L237), [`engine_v3.run_v3_pipeline`](../astra6/engine_v3.py#L404)
- **Maliyet ve test** Tarama O(bar×pencere), comparator ref Python. QA 03, UEV doğrulaması.
- **Durum** `CAUSALITY_FAILURE`

#### [`materialize_entries`](../astra6/signals.py#L219)

- **İmza** `(ctx: dict, crt_df: pd.DataFrame, mode: str)`
- **Girdi ve çıktı** ctx, CRT tablosu, mode → zaman/entry kip, QT, SSMT/CISD, likidite, stop proxy ve V2 MMXM.
- **Hesap ve işlem yorumu** Confirmed A/J/K/H, dev reclaim/CISD, next F, confirmed CISD. Trigger bazında özellikler.
- **Zaman, hata ve risk** known=M1 open+1m, fill j+1 (clip). Politika yeniden tetiğinde özellikler stale. Bilinmeyen mode ValueError.
- **Bağımlılıklar** [`cisd.attach_true_cisd_to_signals`](../astra6/cisd.py#L280), [`crt.running_extreme`](../astra6/crt.py#L195), [`ict.asof_join`](../astra6/ict.py#L124), [`ict.last_known_swing`](../astra6/ict.py#L73), [`mmxm.attach_mmxm_to_signals`](../astra6/mmxm.py#L107), [`smt.attach_ssmt`](../astra6/smt.py#L187) · `numpy`, `pandas`
- **Çağıranlar** [`engine.run_all`](../astra6/engine.py#L237), [`engine_v3.run_v3_pipeline`](../astra6/engine_v3.py#L404)
- **Maliyet ve test** DataFrame kopyaları, as-of ve loop. QA 03/04/07/09, hedef sızıntısı izinde kaynak.
- **Durum** `CAUSALITY_FAILURE`

### `astra6/opening.py`

#### [`compute_opening_ranges`](../astra6/opening.py#L98)

- **İmza** `(panel: pd.DataFrame, traded: str='US100', session: str='NY')`
- **Girdi ve çıktı** Panel H/L/C, traded, session → date/session, OR5/15/30/60 ve sonrası durumlar.
- **Hesap ve işlem yorumu** İlk m dakikada ekstrem ve midpoint, sonrası sweep/false break.
- **Zaman, hata ve risk** İlk 5 dakikada en az bir gözlem. Missing minute ve yanlış session guard yok. Sonrası durum ex-post.
- **Bağımlılıklar** `pandas`
- **Çağıranlar** [`engine.run_all`](../astra6/engine.py#L237)
- **Maliyet ve test** O(n) ve gün groupby. Doğrudan yok.
- **Durum** `DATA_LIMITATION`

#### [`attach_causal_or_to_signals`](../astra6/opening.py#L161)

- **İmza** `(sig: pd.DataFrame, or_daily: pd.DataFrame, session: str='NY')`
- **Girdi ve çıktı** t_trig, session dakika, dir, sweep_ext_known ve OR tablosu → or*_h/l/swept.
- **Hesap ve işlem yorumu** Gün map ve minute+1>=m.
- **Zaman, hata ve risk** Tamamlanma guard var. Ekstrem OR'den sonra gerçekleşmiş ID yok. Boşta orijinal döner.
- **Bağımlılıklar** `numpy`, `pandas`
- **Çağıranlar** [`engine.run_all`](../astra6/engine.py#L237), [`engine_v3.run_v3_pipeline`](../astra6/engine_v3.py#L404)
- **Maliyet ve test** O(n×3). Doğrudan yok.
- **Durum** `TEST_COVERAGE_GAP`

#### [`classify_18_models`](../astra6/opening.py#L191)

- **İmza** `(sig: pd.DataFrame)`
- **Girdi ve çıktı** CRT, kip, sweep, SMT/CISD/MMXM/QT ve HTF bayrakları → ad→bool Series.
- **Hesap ve işlem yorumu** 18 birleşim maskesi.
- **Zaman, hata ve risk** V2 araştırma grubu. Gereken zaman dizisi yok.
- **Bağımlılıklar** `numpy`, `pandas`
- **Çağıranlar** [`engine.run_all`](../astra6/engine.py#L237)
- **Maliyet ve test** O(18n). V3/QA hazır tablo dolaylı.
- **Durum** `SEMANTIC_MISMATCH`

#### [`classify_ny_open_models`](../astra6/opening.py#L233)

- **İmza** `(sig: pd.DataFrame)`
- **Girdi ve çıktı** Sinyal bağlamı → NY model maskeleri.
- **Hesap ve işlem yorumu** OR/CRT/SSMT/CISD ve diğer V2 hipotez filtreleri.
- **Zaman, hata ve risk** Giriş/portföy yürütmesi çağıranda. Eksik kolon hata/varsayım.
- **Bağımlılıklar** Çekirdek dil, vektör işlemleri veya I/O.
- **Çağıranlar** [`engine.run_all`](../astra6/engine.py#L237)
- **Maliyet ve test** O(n×model). Hazır NY tablo testleri.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

### `astra6/fractal_v3.py`

#### [`_scan_original_consolidations_numba`](../astra6/fractal_v3.py#L116)

- **İmza** `(o: np.ndarray, h: np.ndarray, l: np.ndarray, c: np.ndarray, atr: np.ndarray, min_bars: int=4, max_width_atr: float=2.4, min_depart_atr: float=0.35, max_horizon_bars: int=96)`
- **Girdi ve çıktı** TF OHLC/ATR ve 4 eşik → pencere/onay indeksleri, bant, ATR, departure, revisit/inv.
- **Hesap ve işlem yorumu** Önceki 4 bar range/ATR ve bandın dışında asgari kapanış. 96 TF barı sonuç taraması.
- **Zaman, hata ve risk** Ayrılışta bilinir. Revisit ve inv ileri bilgi. Geçersiz ATR atlanır.
- **Bağımlılıklar** `numba.njit`, `numpy`
- **Çağıranlar** [`fractal_v3.extract_original_consolidations`](../astra6/fractal_v3.py#L222)
- **Maliyet ve test** Numba O(n×horizon), ön tahsis. V3 273 statik, gerçek raw prefix.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`extract_original_consolidations`](../astra6/fractal_v3.py#L222)

- **İmza** `(panel: pd.DataFrame, traded: str='US100', timeframes: tuple[str, ...]=('M1', 'M3', 'M5', 'M15', 'M30', 'H1', 'H4'), dataset_hash: str='')`
- **Girdi ve çıktı** M1 panel, traded, TF listesi, dataset hash → OC IDs, zaman, bant/ATR/yön, erişim ve terminal alanları.
- **Hesap ve işlem yorumu** TF resample, ATR ve tarayıcı. M1 close index eşleme.
- **Zaman, hata ve risk** Minimum 20 TF barı, son kova düşümü, ileri erişim, candidate retroaktivitesi.
- **Bağımlılıklar** [`bars.resample`](../astra6/bars.py#L153), [`fractal_v3._scan_original_consolidations_numba`](../astra6/fractal_v3.py#L116), [`ict.atr_wilder`](../astra6/ict.py#L14) · `numpy`, `pandas`
- **Çağıranlar** [`engine_v3.run_v3_pipeline`](../astra6/engine_v3.py#L404)
- **Maliyet ve test** TF groupby ve Numba. V3 124/273 ve 11 gerçek prefix.
- **Durum** `CAUSALITY_FAILURE`

#### [`_run_incremental_mmxm_fsm_numba`](../astra6/fractal_v3.py#L346)

- **İmza** `(o_m1: np.ndarray, h_m1: np.ndarray, l_m1: np.ndarray, c_m1: np.ndarray, j_cand_arr: np.ndarray, j_conf_arr: np.ndarray, tf_min_arr: np.ndarray, t_dir_arr: np.ndarray, oc_hi_arr: np.ndarray, oc_lo_arr: np.ndarray, oc_mid_arr: np.ndarray)`
- **Girdi ve çıktı** M1 OHLC ve OC candidate/confirm, TF dakika, yön, hi/lo/mid → aşama, known, fiyat, active, terminal dizileri.
- **Hesap ve işlem yorumu** 15 aşama, running ekstrem, 0,15/0,40/0,35 × range eşikleri ve OC midpoint teslimi.
- **Zaman, hata ve risk** Stage 1 gelecekte doğrulanan OC. Son terminal tüm satırlara yazılır. Dış teyit girdisi yok.
- **Bağımlılıklar** `numba.njit`, `numpy`
- **Çağıranlar** [`fractal_v3.build_fractal_mmxm_state_events`](../astra6/fractal_v3.py#L786)
- **Maliyet ve test** Numba O(OC×min(36TF,1440)), ön tahsis. V3 229 sabit OC, gerçek prefix.
- **Durum** `CAUSALITY_FAILURE`

#### [`build_fractal_mmxm_state_events`](../astra6/fractal_v3.py#L786)

- **İmza** `(panel: pd.DataFrame, oc_df: pd.DataFrame, traded: str='US100', timeframes: tuple[str, ...]=('M5', 'M15', 'M30', 'H1', 'H4', 'D1'))`
- **Girdi ve çıktı** Panel, OC frame, traded/TF → mmxm_event/id/oc_id, stage, dir, known, fiyatlar, terminal.
- **Hesap ve işlem yorumu** OC sort, FSM, indeks→M1 close, ID ve stage isimleri.
- **Zaman, hata ve risk** Boşta boş. Standalone TF teyit saati ve bar eşlemesi ayrışabilir. Prefix geçmiyor.
- **Bağımlılıklar** [`fractal_v3._run_incremental_mmxm_fsm_numba`](../astra6/fractal_v3.py#L346) · `numpy`, `pandas`
- **Çağıranlar** [`engine_v3.run_v3_pipeline`](../astra6/engine_v3.py#L404)
- **Maliyet ve test** Sort, Numba ve O(event). V3 124/288, gerçek prefix.
- **Durum** `CAUSALITY_FAILURE`

#### [`build_liquidity_events_table`](../astra6/fractal_v3.py#L878)

- **İmza** `(ctx: dict, raw_crt: dict[tuple[str, str], pd.DataFrame], oc_df: pd.DataFrame, dataset_hash: str='')`
- **Girdi ve çıktı** ctx, CRT (TF,anchor) haritası, kullanılmayan OC frame ve hash → liquidity event kimlik, seviye, sınıf, zaman.
- **Hesap ve işlem yorumu** Yalnız cal CRT, beş sınıf ve önceki mum H/L.
- **Zaman, hata ve risk** Arşiv. Açılış aralığı veya OC kaynağı bağlanmaz. Seviye yaşam ömrü yok.
- **Bağımlılıklar** `numpy`, `pandas`
- **Çağıranlar** [`engine_v3.run_v3_pipeline`](../astra6/engine_v3.py#L404)
- **Maliyet ve test** Python O(event) ve sort. V3 coverage testleri dolaylı.
- **Durum** `SEMANTIC_MISMATCH`

#### [`build_atomic_events_database`](../astra6/fractal_v3.py#L981)

- **İmza** `(ctx: dict, liq_df: pd.DataFrame, oc_df: pd.DataFrame, mmxm_ev_df: pd.DataFrame, dataset_hash: str='')`
- **Girdi ve çıktı** ctx SSMT/CISD, liq_df, OC, MMXM, hash → birleşik event tablosu.
- **Hesap ve işlem yorumu** Beş ailede id/type/tf/dir, zaman ve fiyat normalizasyonu. CRT ve alternatif SSMT anchor ayrı.
- **Zaman, hata ve risk** Bazı zamanlar referans/tetik, ileri terminal bilgileri karışır. Fırsat motoru arşivden yürütülmez.
- **Bağımlılıklar** `numpy`, `pandas`
- **Çağıranlar** [`engine_v3.run_v3_pipeline`](../astra6/engine_v3.py#L404)
- **Maliyet ve test** Concat ve sort O(n log n). V3 373 yalnız sayım.
- **Durum** `DATA_LIMITATION`

#### [`_asof_join_active_mmxm_numba`](../astra6/fractal_v3.py#L1116)

- **İmza** `(jt_query: np.ndarray, dir_query: np.ndarray, ev_j_known: np.ndarray, ev_j_term: np.ndarray, ev_dir: np.ndarray, ev_stage: np.ndarray, ev_tf_code: np.ndarray, ev_row_idx: np.ndarray)`
- **Girdi ve çıktı** Sorgu j/yön, sıralı event known/term/yön/stage/TF/row → seçilen dört dizi.
- **Hesap ve işlem yorumu** Binary search ve sınırlı backward tarama. Yakın stage≥8 tercih.
- **Zaman, hata ve risk** Terminal eşitlik, is_active yok. Aynı yönde tek event. Stage 1 geriye yazım seçilebilir.
- **Bağımlılıklar** `numba.njit`, `numpy`
- **Çağıranlar** [`fractal_v3.attach_full_fractal_context`](../astra6/fractal_v3.py#L1191)
- **Maliyet ve test** Numba O(q(log e+120)). V3 288 zayıf, gerçek as-of prefix.
- **Durum** `CAUSALITY_FAILURE`

#### [`attach_full_fractal_context`](../astra6/fractal_v3.py#L1191)

- **İmza** `(ctx: dict, cands: pd.DataFrame, oc_df: pd.DataFrame, mmxm_ev_df: pd.DataFrame | None=None)`
- **Girdi ve çıktı** ctx, adaylar, OC, MMXM events → UEV/OPP IDs, bias/prev levels, OC, MMXM, rejim ve TF.
- **Hesap ve işlem yorumu** 13 mum rengi/ekstremi, son 50 geçerli OC, as-of MMXM, maskeler.
- **Zaman, hata ve risk** Bilinmeyen bias +1. Etiketler bağımsız event zinciri değil. Bağlam yeniden tetikten önce hesaplanır.
- **Bağımlılıklar** [`bars.resample`](../astra6/bars.py#L153), [`cisd.attach_true_cisd_to_signals`](../astra6/cisd.py#L280), [`fractal_v3._asof_join_active_mmxm_numba`](../astra6/fractal_v3.py#L1116), [`ict.asof_join`](../astra6/ict.py#L124) · `numpy`, `pandas`
- **Çağıranlar** [`engine_v3.run_v3_pipeline`](../astra6/engine_v3.py#L404)
- **Maliyet ve test** Çoklu groupby ve Python O(q×50). V3 288, Model 1/2 tüm hedef izi.
- **Durum** `CAUSALITY_FAILURE`

#### [`build_cross_timeframe_targets_and_outcomes`](../astra6/fractal_v3.py#L1448)

- **İmza** `(ctx: dict, cands: pd.DataFrame, horizon_bars: int=360, slip: float=0.25, universe_coverage: str='FULL_UNIVERSE')`
- **Girdi ve çıktı** ctx, px_entry/sl_init/j_trig/dir/ATR/levels/TF/split adayları, horizon/slip → aday, outcome, grup.
- **Hesap ve işlem yorumu** 10 hedef, dist≥3 ve 0,35≤R≤25, ayrı çekirdek. Engel ATR mesafe vekili.
- **Zaman, hata ve risk** Tarihi bağlam hedefi erken emirde kullanılabilir. known_before_entry sabit true. Level ID/zamanı yok.
- **Bağımlılıklar** [`hpc.fast_target_exec_full_numba`](../astra6/hpc.py#L340) · `hpc`, `numpy`, `pandas`
- **Çağıranlar** [`engine_v3.run_v3_pipeline`](../astra6/engine_v3.py#L404)
- **Maliyet ve test** O(aday×hedef×horizon) ve büyük concat. V3 165/606, 1.117 kaynak hedef denetimi.
- **Durum** `CAUSALITY_FAILURE`

#### [`execute_strategy_at_custom_triggers`](../astra6/fractal_v3.py#L1705)

- **İmza** `(ctx: dict, base_df: pd.DataFrame, j_exec_arr: np.ndarray, rr_target: float=2.0, horizon_bars: int=360, slip_pts: float=0.25)`
- **Girdi ve çıktı** ctx, base_df, j_exec, RR/horizon/slip → yeni yürütme satırları.
- **Hesap ve işlem yorumu** Ask/Bid fill, eski stop ve tetik ekstremi, 3 puan floor, fixed R ve kernel.
- **Zaman, hata ve risk** j_exit alanı güncellenmez. Girişte eski stop ve metadata. Gap/stop-before-confirm yok. Invalid index elenir.
- **Bağımlılıklar** [`hpc.fast_target_exec_full_numba`](../astra6/hpc.py#L340) · `hpc`, `numpy`, `pandas`
- **Çağıranlar** [`engine_v3.run_v3_pipeline`](../astra6/engine_v3.py#L404)
- **Maliyet ve test** Vektör + Numba O(n×horizon). V3 536/695, beş gerçek replay.
- **Durum** `CONFIRMED_BUG`

#### [`build_narrative_graph_and_snapshots`](../astra6/fractal_v3.py#L1814)

- **İmza** `(cands: pd.DataFrame, target_candidates: pd.DataFrame, universe_coverage: str='FULL_UNIVERSE')`
- **Girdi ve çıktı** cands ve hedef adaylar → graph/pretrade/posttrade.
- **Hesap ve işlem yorumu** En yakın dist≥1,2R, q01–q16, üç etiket kenarı. Outcome ayrı.
- **Zaman, hata ve risk** Kenarlar aynı timestamp, olay zinciri değil. Hedef seçimi fill geometrisi kullanır.
- **Bağımlılıklar** `numpy`, `pandas`
- **Çağıranlar** [`engine_v3.run_v3_pipeline`](../astra6/engine_v3.py#L404)
- **Maliyet ve test** Sort, map ve concat. V3 386 kolon testi.
- **Durum** `SEMANTIC_MISMATCH`

### `astra6/engine.py`

#### [`_sim_df`](../astra6/engine.py#L31)

- **İmza** `(ctx: dict, df: pd.DataFrame, rr: float=2.0, stop_col: str='sweep_ext_known', exit_model: int=sim.EX_FIXED, max_hold: int=360, slip: float=0.25, stop_buffer: float=1.5, non_overlap: bool=False, target_col: str | None=None)`
- **Girdi ve çıktı** ctx, aday j_trig/dir/stop/ATR, rr/model/hold/slip/buffer/overlap → V2 r, MFE/MAE/hold/exit/fiyat.
- **Hesap ve işlem yorumu** Sweep stop±1,5, risk floor max(3,0,25 ATR), sim_batch, >5 dk gap elenir.
- **Zaman, hata ve risk** j+1 açılışı. Non-overlap isteğe bağlı. Geçersiz r ayıklanır.
- **Bağımlılıklar** [`sim.filter_non_overlapping`](../astra6/sim.py#L173), [`sim.sim_batch`](../astra6/sim.py#L34) · `numpy`
- **Çağıranlar** [`engine.run_all`](../astra6/engine.py#L237), [`engine_v3.run_v3_pipeline`](../astra6/engine_v3.py#L404)
- **Maliyet ve test** Numba O(n×hold), vektör. QA 07/08, V2 audit, UEV kaynak stopu.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`_add_mtf_cisd_and_nested`](../astra6/engine.py#L119)

- **İmza** `(ctx: dict, df: pd.DataFrame, h1_events: pd.DataFrame | None=None)`
- **Girdi ve çıktı** ctx, aday frame, isteğe H1 olayları → G/I/L, SSMT stop, midpoint, karşı kenar ve narrative.
- **Hesap ve işlem yorumu** V2 G/I/L, aynı yön H1 sweep sırasında LTF A, SSMT stop ve CRT hedef geometrisi.
- **Zaman, hata ve risk** Gerçek nested MMXM olay bağı değildir. Kaynak zaman eşlemesine bağlı.
- **Bağımlılıklar** [`crt.running_extreme`](../astra6/crt.py#L195) · `numpy`
- **Çağıranlar** [`engine.run_all`](../astra6/engine.py#L237), [`engine_v3.run_v3_pipeline`](../astra6/engine_v3.py#L404)
- **Maliyet ve test** Join/loop. V2 hazır QA dolaylı.
- **Durum** `SEMANTIC_MISMATCH`

#### [`extract_full_30s_micro_ssmt_and_attach`](../astra6/engine.py#L175)

- **İmza** `(ctx: dict, m15_cands: pd.DataFrame)`
- **Girdi ve çıktı** ctx, M15 adayları ve DUKA 30s → 30s olay bağlamı, performans karşılaştırma.
- **Hesap ve işlem yorumu** US100/500 30s hizala, QT/SSMT bağla ve 1m ile grupla.
- **Zaman, hata ve risk** Daha kısa tarih, iki sembol. Eşdeğer aday evreni ayrı kontrol gerektirir.
- **Bağımlılıklar** [`bars.quarter_labels`](../astra6/bars.py#L184), [`smt.attach_ssmt`](../astra6/smt.py#L187), [`smt.ssmt_events`](../astra6/smt.py#L102), [`stats.summarize_trades`](../astra6/stats.py#L43) · `numpy`, `pandas`, `polars`
- **Çağıranlar** [`engine.run_all`](../astra6/engine.py#L237)
- **Maliyet ve test** Tam 30s IO ve groupby. Doğrudan yok.
- **Durum** `DATA_LIMITATION`

#### [`run_all`](../astra6/engine.py#L237)

- **İmza** `()`
- **Girdi ve çıktı** Yerel store → V2 Parquet, kalite JSON ve istatistikler.
- **Hesap ve işlem yorumu** Forensics, context, CRT ve giriş kipleri, exit/stop grid, 18 model, WFA, maliyet/provider, örnekler.
- **Zaman, hata ve risk** Yazıcı. OOS tarihsel. Sonuç seçimi ve aynı stream pozisyonlar ayrı.
- **Bağımlılıklar** [`bars.load_panel`](../astra6/bars.py#L85), [`bars.resample`](../astra6/bars.py#L153), [`forensics.load_dataset_scenario`](../astra6/data/forensics.py#L401), [`forensics.run_data_forensics`](../astra6/data/forensics.py#L483), [`engine._add_mtf_cisd_and_nested`](../astra6/engine.py#L119), [`engine._sim_df`](../astra6/engine.py#L31), [`engine.extract_full_30s_micro_ssmt_and_attach`](../astra6/engine.py#L175), [`opening.attach_causal_or_to_signals`](../astra6/opening.py#L161), [`opening.classify_18_models`](../astra6/opening.py#L191), [`opening.classify_ny_open_models`](../astra6/opening.py#L233), [`opening.compute_opening_ranges`](../astra6/opening.py#L98), [`signals.build_context`](../astra6/signals.py#L28), [`signals.extract_crt_events`](../astra6/signals.py#L134), [`signals.materialize_entries`](../astra6/signals.py#L219), [`sim.filter_non_overlapping`](../astra6/sim.py#L173), [`smt.attach_ssmt`](../astra6/smt.py#L187), [`stats.adjust_pvalues`](../astra6/stats.py#L220), [`stats.compare_two_models`](../astra6/stats.py#L171), [`stats.matched_control_comparison`](../astra6/stats.py#L322), [`stats.split_evaluation`](../astra6/stats.py#L242), [`stats.summarize_trades`](../astra6/stats.py#L43), [`stats.walk_forward_analysis`](../astra6/stats.py#L261) · `json`, `numpy`, `pandas`, `polars`, `time`
- **Çağıranlar** [`run_pipeline.main`](../run_pipeline.py#L131), [`astra6/engine.py` modül akışı](../astra6/engine.py)
- **Maliyet ve test** Tam tarih ve çoklu simülasyon. QA 02/06/07/10 hazır çıktı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

### `astra6/engine_v3.py`

#### [`_fast_cell_metrics`](../astra6/engine_v3.py#L89)

- **İmza** `(df_sub: pd.DataFrame, r_col: str='r')`
- **Girdi ve çıktı** df/r, day, optional outcomes/split/id → N/WR/PF/DD/GA/p/OOS dict.
- **Hesap ve işlem yorumu** Finite R, mean, gross PF, day cluster ve 300 bootstrap.
- **Zaman, hata ve risk** DD/seri kayıp girdi sırası. PF 99 sentinel, n/cluster bilgisi yoksa varsayımlar. p erken yuvarlanır.
- **Bağımlılıklar** [`engine_v3._fast_cell_metrics`](../astra6/engine_v3.py#L89), [`hpc._day_cluster_stats_and_bootstrap_numba`](../astra6/hpc.py#L537) · `numpy`
- **Çağıranlar** [`audit_v34_models.compute_model_metrics`](../astra6/audit_v34_models.py#L35), [`engine_v3._fast_cell_metrics`](../astra6/engine_v3.py#L89), [`engine_v3._select_genuine_25_rankings._pick_best`](../astra6/engine_v3.py#L284), [`engine_v3.run_v3_pipeline`](../astra6/engine_v3.py#L404), [`fractal_narrative_v34.run_narrative_validation`](../astra6/fractal_narrative_v34.py#L38)
- **Maliyet ve test** O(n log n+300×days). V3 421 dolaylı, dört model bağımsız aritmetik.
- **Durum** `STATISTICAL_FAILURE`

#### [`_assign_validation_split`](../astra6/engine_v3.py#L246)

- **İmza** `(t_series: pd.Series)`
- **Girdi ve çıktı** Timestamp Series → üç split.
- **Hesap ve işlem yorumu** UTC <2024-07-01, <2025-07-01, aksi OOS.
- **Zaman, hata ve risk** NaT default OOS olabilir. Politika tekrar zamanında etiket değişmez.
- **Bağımlılıklar** `numpy`, `pandas`
- **Çağıranlar** [`engine_v3.run_v3_pipeline`](../astra6/engine_v3.py#L404)
- **Maliyet ve test** O(n). Doğrudan sınır testi yok, 12 CF farkı.
- **Durum** `TEST_COVERAGE_GAP`

#### [`_select_genuine_25_rankings`](../astra6/engine_v3.py#L266)

- **İmza** `(combo_results_df: pd.DataFrame, tf_align_df: pd.DataFrame, entry_target_df: pd.DataFrame, mmxm_qt_df: pd.DataFrame, ssmt_mat_df: pd.DataFrame, liq_cisd_df: pd.DataFrame, rev_cont_df: pd.DataFrame)`
- **Girdi ve çıktı** Yedi özet tablo → 25 ranking satırı.
- **Hesap ve işlem yorumu** Kategori havuzları, _pick_best ve verdict.
- **Zaman, hata ve risk** Aynı tarihsel araştırmada seçim. Farklı hedef popülasyonlarını ayırmak gerekir.
- **Bağımlılıklar** [`engine_v3._select_genuine_25_rankings._pick_best`](../astra6/engine_v3.py#L284) · `pandas`
- **Çağıranlar** [`engine_v3.run_v3_pipeline`](../astra6/engine_v3.py#L404)
- **Maliyet ve test** 25 filtre/sort. V3 205/406 şema.
- **Durum** `STATISTICAL_FAILURE`

#### [`_select_genuine_25_rankings._pick_best`](../astra6/engine_v3.py#L284)

- **İmza** `(pool_df: pd.DataFrame, r_num: int, r_title: str, label_cols: list[str], ascending: bool=False, min_trades: int=30)`
- **Girdi ve çıktı** Havuz, kategori, label, sıra ve min N → ranking dict.
- **Hesap ve işlem yorumu** Min N, Holm/BH, in-sample sort veya fallback. DD skoru R−0,02 DD.
- **Zaman, hata ve risk** Min gün filtresi dokümana rağmen uygulanmaz. Boş OOS pozitif verdict'i engellemez.
- **Bağımlılıklar** [`engine_v3._fast_cell_metrics`](../astra6/engine_v3.py#L89), [`stats.adjust_pvalues`](../astra6/stats.py#L220) · `numpy`, `pandas`
- **Çağıranlar** [`engine_v3._select_genuine_25_rankings`](../astra6/engine_v3.py#L266)
- **Maliyet ve test** Sort O(k log k). V3 406 yalnız hazır dosya.
- **Durum** `STATISTICAL_FAILURE`

#### [`run_v3_pipeline`](../astra6/engine_v3.py#L404)

- **İmza** `(force_recompute: bool=False)`
- **Girdi ve çıktı** force_recompute ve yerel store/önceki adaylar → checkpoint, Parquet, DuckDB.
- **Hesap ve işlem yorumu** Atomik göl, ortak 2R, yapı hedefleri, 64 ayrı, 20 MTF, 15 filtre, matris ve sıralama.
- **Zaman, hata ve risk** As-of/stop sızıntısı. Stale cache, ID/etiket/zaman, ex-post audit. Tam yazıcı.
- **Bağımlılıklar** [`bars.load_panel`](../astra6/bars.py#L85), [`engine._add_mtf_cisd_and_nested`](../astra6/engine.py#L119), [`engine._sim_df`](../astra6/engine.py#L31), [`engine_v3._assign_validation_split`](../astra6/engine_v3.py#L246), [`engine_v3._fast_cell_metrics`](../astra6/engine_v3.py#L89), [`engine_v3._select_genuine_25_rankings`](../astra6/engine_v3.py#L266), [`engine_v3.run_v3_pipeline._sample_100`](../astra6/engine_v3.py#L1887), [`fractal_v3.attach_full_fractal_context`](../astra6/fractal_v3.py#L1191), [`fractal_v3.build_atomic_events_database`](../astra6/fractal_v3.py#L981), [`fractal_v3.build_cross_timeframe_targets_and_outcomes`](../astra6/fractal_v3.py#L1448), [`fractal_v3.build_fractal_mmxm_state_events`](../astra6/fractal_v3.py#L786), [`fractal_v3.build_liquidity_events_table`](../astra6/fractal_v3.py#L878), [`fractal_v3.build_narrative_graph_and_snapshots`](../astra6/fractal_v3.py#L1814), [`fractal_v3.execute_strategy_at_custom_triggers`](../astra6/fractal_v3.py#L1705), [`fractal_v3.extract_original_consolidations`](../astra6/fractal_v3.py#L222), [`hpc.CheckpointManager.bind_cache_identity`](../astra6/hpc.py#L917), [`hpc.CheckpointManager.is_cache_valid`](../astra6/hpc.py#L890), [`hpc.CheckpointManager.record_phase`](../astra6/hpc.py#L925), [`hpc.CheckpointManager.set_hardware_summary`](../astra6/hpc.py#L938), [`hpc.compute_config_hash`](../astra6/hpc.py#L725), [`hpc.compute_source_store_sha256`](../astra6/hpc.py#L689), [`hpc.detect_hardware_profile`](../astra6/hpc.py#L132), [`hpc.fast_target_exec_full_numba`](../astra6/hpc.py#L340), [`hpc.paired_event_cluster_test`](../astra6/hpc.py#L632), [`hpc.run_benchmark_and_autotune`](../astra6/hpc.py#L734), [`opening.attach_causal_or_to_signals`](../astra6/opening.py#L161), [`signals.build_context`](../astra6/signals.py#L28), [`signals.extract_crt_events`](../astra6/signals.py#L134), [`signals.materialize_entries`](../astra6/signals.py#L219), [`stats.adjust_pvalues`](../astra6/stats.py#L220) · `datetime.datetime`, `duckdb`, `fractal_v3`, `hpc`, `itertools`, `json`, `math`, `numpy`
- **Çağıranlar** [`run_pipeline.main`](../run_pipeline.py#L131), [`astra6/engine_v3.py` modül akışı](../astra6/engine_v3.py)
- **Maliyet ve test** Tam panel, milyonlar satır ve 64 sim. V3 40/48/308/659/695 artefakt; bu audit sınırlı replay.
- **Durum** `CAUSALITY_FAILURE`

#### [`run_v3_pipeline._sample_100`](../astra6/engine_v3.py#L1887)

- **İmza** `(df_src: pd.DataFrame, cat_code: str, id_col: str, ts_col: str, dir_col: str, desc_cols: list[str])`
- **Girdi ve çıktı** Aday kaynak, kategori, ID/timestamp/yön/desc kolonları → örnek frame.
- **Hesap ve işlem yorumu** Sabit seed ile örnekle, gerekli alanları normalize et.
- **Zaman, hata ve risk** İnsan doğrulaması değil. Boşta boş. Seçili kaynak önyargısı.
- **Bağımlılıklar** `numpy`, `pandas`
- **Çağıranlar** [`engine_v3.run_v3_pipeline`](../astra6/engine_v3.py#L404)
- **Maliyet ve test** Örnekleme ve kopya. V3 205 sayım.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

### `astra6/sim.py`

#### [`sim_batch`](../astra6/sim.py#L34)

- **İmza** `(bid_o, bid_h, bid_l, bid_c, ask_o, ask_h, ask_l, ask_c, j_trig, direction, sl0, tp0, exit_model, max_hold, slip, min_risk, sw_j_known, sw_price, sw_is_high)`
- **Girdi ve çıktı** Bid/Ask OHLC, j_trig/dir/SL/TP, exit mode/hold/slip/minrisk, swing dizileri → 10 execution array.
- **Hesap ve işlem yorumu** Next open, quote tarafı, SL/TP, BE/partial/trail, R muhasebesi.
- **Zaman, hata ve risk** Aynı bar stop önce. Update sonraki bar, gap nominal stop. Sonda last fill kısıtı. Geçersiz risk skip.
- **Bağımlılıklar** `numba.njit`, `numpy`
- **Çağıranlar** [`engine._sim_df`](../astra6/engine.py#L31)
- **Maliyet ve test** Numba O(trade×hold). QA 07/08, V2 audit replay.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`filter_non_overlapping`](../astra6/sim.py#L173)

- **İmza** `(j_entry, j_exit)`
- **Girdi ve çıktı** Sıralı j_entry/j_exit → keep bool.
- **Hesap ve işlem yorumu** j_entry önceki tutulan exit'ten büyükse al.
- **Zaman, hata ve risk** Sırasız girdi ve eşit fill önceliği çağıranda.
- **Bağımlılıklar** `numba.njit`, `numpy`
- **Çağıranlar** [`engine._sim_df`](../astra6/engine.py#L31), [`engine.run_all`](../astra6/engine.py#L237)
- **Maliyet ve test** Numba O(n). Doğrudan yok.
- **Durum** `TEST_COVERAGE_GAP`

### `astra6/hpc.py`

#### [`_sysctl_str`](../astra6/hpc.py#L87)

- **İmza** `(key: str, default: str='')`
- **Girdi ve çıktı** Key/default → host bilgi str.
- **Hesap ve işlem yorumu** macOS sysctl subprocess.
- **Zaman, hata ve risk** Hata default. Veri/broker zamanı yok.
- **Bağımlılıklar** `subprocess`
- **Çağıranlar** [`hpc._sysctl_int`](../astra6/hpc.py#L95), [`hpc.detect_hardware_profile`](../astra6/hpc.py#L132)
- **Maliyet ve test** OS IO. V3 455 hazır JSON.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`_sysctl_int`](../astra6/hpc.py#L95)

- **İmza** `(key: str, default: int=0)`
- **Girdi ve çıktı** Key/default → host bilgi int.
- **Hesap ve işlem yorumu** sysctl string→int.
- **Zaman, hata ve risk** Parse hatası default.
- **Bağımlılıklar** [`hpc._sysctl_str`](../astra6/hpc.py#L87)
- **Çağıranlar** [`hpc.detect_hardware_profile`](../astra6/hpc.py#L132)
- **Maliyet ve test** OS IO. V3 455 dolaylı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`_available_ram_gb`](../astra6/hpc.py#L103)

- **İmza** `(total_gb: float)`
- **Girdi ve çıktı** Toplam RAM → yaklaşık serbest GiB.
- **Hesap ve işlem yorumu** vm_stat ve fallback kestirimi.
- **Zaman, hata ve risk** Ölçüm anı, tahsis garantisi yok.
- **Bağımlılıklar** `subprocess`
- **Çağıranlar** [`hpc.detect_hardware_profile`](../astra6/hpc.py#L132)
- **Maliyet ve test** OS IO. V3 455 dolaylı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`get_peak_rss_mb`](../astra6/hpc.py#L124)

- **İmza** `()`
- **Girdi ve çıktı** Süreç → peak RSS.
- **Hesap ve işlem yorumu** resource usage, platform birim dönüşümü.
- **Zaman, hata ve risk** Araştırma metriği değil.
- **Bağımlılıklar** `platform`, `resource`
- **Çağıranlar** [`hpc.CheckpointManager.record_phase`](../astra6/hpc.py#L925), [`hpc.run_benchmark_and_autotune`](../astra6/hpc.py#L734)
- **Maliyet ve test** O(1). V3 455 dolaylı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`detect_hardware_profile`](../astra6/hpc.py#L132)

- **İmza** `()`
- **Girdi ve çıktı** Host → HardwareProfile.
- **Hesap ve işlem yorumu** RAM/CPU bilgisiyle worker ve batch seçer.
- **Zaman, hata ve risk** Fallback host, performans heuristiği.
- **Bağımlılıklar** [`hpc._available_ram_gb`](../astra6/hpc.py#L103), [`hpc._sysctl_int`](../astra6/hpc.py#L95), [`hpc._sysctl_str`](../astra6/hpc.py#L87) · `datetime.datetime`, `numba`, `os`, `platform`, `shutil`
- **Çağıranlar** [`engine_v3.run_v3_pipeline`](../astra6/engine_v3.py#L404), [`hpc.run_benchmark_and_autotune`](../astra6/hpc.py#L734)
- **Maliyet ve test** OS IO. V3 455 hazır JSON.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`reference_target_exec_full_py`](../astra6/hpc.py#L198)

- **İmza** `(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, j_fill: np.ndarray, direction: np.ndarray, entry_px: np.ndarray, stop_px: np.ndarray, target_px: np.ndarray, horizon_bars: int, slip_pts: float=0.25)`
- **Girdi ve çıktı** Tek quote tarafı H/L/C, fill/dir/entry/stop/TP, horizon/slip → 9 outcome array.
- **Hesap ve işlem yorumu** İlk temas, stop önceliği, MTM ve target horizon; R.
- **Zaman, hata ve risk** Bid/Ask seçimi çağıranda. Horizon dahil, data-end eşitliği. Fiyat ve boyut validasyonu sınırlı.
- **Bağımlılıklar** `numpy`
- **Çağıranlar** [`hpc.reference_target_horizon_eval_py`](../astra6/hpc.py#L468), [`hpc.run_benchmark_and_autotune`](../astra6/hpc.py#L734)
- **Maliyet ve test** Python O(trade×horizon). V3 186/323, audit ayrı referans yazdı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`fast_target_exec_full_numba`](../astra6/hpc.py#L340)

- **İmza** `(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, j_fill: np.ndarray, direction: np.ndarray, entry_px: np.ndarray, stop_px: np.ndarray, target_px: np.ndarray, horizon_bars: int, slip_pts: float=0.25)`
- **Girdi ve çıktı** Aynı sözleşme → reached_any/clean/bars, code, exit j/px, R/MFE/MAE.
- **Hesap ve işlem yorumu** SL/TP veya uygun close, risk ve çıkış slip.
- **Zaman, hata ve risk** TP'yi stop sonrası izlemeye devam. Stop fill nominal, zero risk 1'e dönüştürülür. Exit bar MFE/MAE sıra belirsiz.
- **Bağımlılıklar** `numba.njit`, `numpy`
- **Çağıranlar** [`engine_v3.run_v3_pipeline`](../astra6/engine_v3.py#L404), [`fractal_v3.build_cross_timeframe_targets_and_outcomes`](../astra6/fractal_v3.py#L1448), [`fractal_v3.execute_strategy_at_custom_triggers`](../astra6/fractal_v3.py#L1705), [`hpc.run_benchmark_and_autotune`](../astra6/hpc.py#L734)
- **Maliyet ve test** Numba O(trade×horizon). Sınırlı ölçülen temas/MTM sözleşmesi, gerçek 5 replay ve 4 edge. Gap modeli ayrı kusur.
- **Durum** `VERIFIED_CORRECT`

#### [`reference_target_horizon_eval_py`](../astra6/hpc.py#L468)

- **İmza** `(highs: np.ndarray, lows: np.ndarray, j_fill: np.ndarray, direction: np.ndarray, stop_px: np.ndarray, target_px: np.ndarray, horizon_bars: int)`
- **Girdi ve çıktı** H/L, fill/dir/SL/TP/horizon → üç erişim dizisi.
- **Hesap ve işlem yorumu** Full Python kernel wrapper, midpoint yardımcı dizileri.
- **Zaman, hata ve risk** Yalnız erişim çıkarır. Aktif yürütme çağrısı bulunmadı.
- **Bağımlılıklar** [`hpc.reference_target_exec_full_py`](../astra6/hpc.py#L198) · `numpy`
- **Çağıranlar** Üretim ağacında statik çağrı bulunmadı.
- **Maliyet ve test** O(trade×horizon). Doğrudan yok.
- **Durum** `DEAD_OR_UNUSED_CODE`

#### [`fast_target_horizon_eval_numba`](../astra6/hpc.py#L487)

- **İmza** `(highs: np.ndarray, lows: np.ndarray, j_fill: np.ndarray, direction: np.ndarray, stop_px: np.ndarray, target_px: np.ndarray, horizon_bars: int)`
- **Girdi ve çıktı** H/L, fill/dir/SL/TP/horizon → üç erişim dizisi.
- **Hesap ve işlem yorumu** Doğrudan SL/TP taraması.
- **Zaman, hata ve risk** Full model portföyü değil. Aktif çağrı bulunmadı.
- **Bağımlılıklar** `numba.njit`, `numpy`
- **Çağıranlar** Üretim ağacında statik çağrı bulunmadı.
- **Maliyet ve test** Numba O(trade×horizon). Doğrudan yok.
- **Durum** `DEAD_OR_UNUSED_CODE`

#### [`_day_cluster_stats_and_bootstrap_numba`](../astra6/hpc.py#L537)

- **İmza** `(r: np.ndarray, day_ids: np.ndarray, n_boot: int=300, seed: int=42)`
- **Girdi ve çıktı** R ve day_id, n_boot/seed → G, iid/cluster SE, CI, p.
- **Hesap ve işlem yorumu** Liang-Zeger day scores, cluster bootstrap, normal tail.
- **Zaman, hata ve risk** Tek gün IID fallback, tek satır p 0/1. Günler arası risk bağı ölçülmez.
- **Bağımlılıklar** `math`, `numba.njit`, `numpy`
- **Çağıranlar** [`engine_v3._fast_cell_metrics`](../astra6/engine_v3.py#L89), [`hpc.paired_event_cluster_test`](../astra6/hpc.py#L632)
- **Maliyet ve test** O(n log n + B×G). Dört modelde formül/CI replikasyonu, V3 421.
- **Durum** `VERIFIED_CORRECT`

#### [`paired_event_cluster_test`](../astra6/hpc.py#L632)

- **İmza** `(df_a: pd.DataFrame, df_b: pd.DataFrame, event_col: str='underlying_event_id', day_col: str='ny_day_id', r_col: str='r')`
- **Girdi ve çıktı** İki df, event/day/R kolon adları → eşli delta/SE/GA/p.
- **Hesap ve işlem yorumu** Olay başına mean ve inner merge. Day cluster farkları.
- **Zaman, hata ve risk** <5 çift boş ölçüm, p=1. V3 ablation event_col=day verir, UEV eşli etki değildir.
- **Bağımlılıklar** [`hpc._day_cluster_stats_and_bootstrap_numba`](../astra6/hpc.py#L537) · `math`, `numpy`
- **Çağıranlar** [`engine_v3.run_v3_pipeline`](../astra6/engine_v3.py#L404)
- **Maliyet ve test** Groupby ve bootstrap. Üretim çağrısında test açığı.
- **Durum** `STATISTICAL_FAILURE`

#### [`compute_source_store_sha256`](../astra6/hpc.py#L689)

- **İmza** `(store_dir: Path | None=None)`
- **Girdi ve çıktı** Store dir → çekirdek altı dosya kısmi SHA.
- **Hesap ve işlem yorumu** Ad+boyut ve ilk/orta/son 256 KiB.
- **Zaman, hata ve risk** Aynı boyutlu aralık değişimini kaçırır. Missing sentinel.
- **Bağımlılıklar** `hashlib`
- **Çağıranlar** [`engine_v3.run_v3_pipeline`](../astra6/engine_v3.py#L404)
- **Maliyet ve test** Sınırlı IO. V3 432 config/sürüm, bağımsız checksum.
- **Durum** `CONFIRMED_BUG`

#### [`compute_config_hash`](../astra6/hpc.py#L725)

- **İmza** `(config_dict: dict[str, Any])`
- **Girdi ve çıktı** Dict → SHA256.
- **Hesap ve işlem yorumu** JSON sort keys + default str.
- **Zaman, hata ve risk** Sadece verilen ayarlar. Kaynak kod hash'i değil.
- **Bağımlılıklar** `hashlib`, `json`
- **Çağıranlar** [`engine_v3.run_v3_pipeline`](../astra6/engine_v3.py#L404)
- **Maliyet ve test** O(config). V3 432.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`run_benchmark_and_autotune`](../astra6/hpc.py#L734)

- **İmza** `(profile: HardwareProfile | None=None)`
- **Girdi ve çıktı** HardwareProfile → benchmark dict.
- **Hesap ve işlem yorumu** Fiyat benzeri fixture, Python/Numba sonuç, throughput ve ayar.
- **Zaman, hata ve risk** Üretim fiyat doğrulaması değil. Bu audit çalıştırmadı.
- **Bağımlılıklar** [`hpc.detect_hardware_profile`](../astra6/hpc.py#L132), [`hpc.fast_target_exec_full_numba`](../astra6/hpc.py#L340), [`hpc.get_peak_rss_mb`](../astra6/hpc.py#L124), [`hpc.reference_target_exec_full_py`](../astra6/hpc.py#L198) · `dataclasses.asdict`, `json`, `numpy`, `polars`, `time`
- **Çağıranlar** [`engine_v3.run_v3_pipeline`](../astra6/engine_v3.py#L404)
- **Maliyet ve test** JIT + fixture sim. V3 186/455.
- **Durum** `TEST_COVERAGE_GAP`

#### [`CheckpointManager.__init__`](../astra6/hpc.py#L869)

- **İmza** `(self, path: Path | None=None)`
- **Girdi ve çıktı** Path → state yüklü manager.
- **Hesap ve işlem yorumu** Varsayılan sonuç path ve _load.
- **Zaman, hata ve risk** Bozuk JSON fallback riski.
- **Bağımlılıklar** [`hpc.CheckpointManager._load`](../astra6/hpc.py#L873)
- **Çağıranlar** Üretim ağacında statik çağrı bulunmadı.
- **Maliyet ve test** Disk IO. V3 432.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`CheckpointManager._load`](../astra6/hpc.py#L873)

- **İmza** `(self)`
- **Girdi ve çıktı** Dosya → dict.
- **Hesap ve işlem yorumu** JSON oku, başlangıç state'i.
- **Zaman, hata ve risk** Parse/missing durumunda state yeniden başlar.
- **Bağımlılıklar** `datetime.datetime`, `json`
- **Çağıranlar** [`hpc.CheckpointManager.__init__`](../astra6/hpc.py#L869)
- **Maliyet ve test** Disk IO. V3 432 dolaylı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`CheckpointManager.is_cache_valid`](../astra6/hpc.py#L890)

- **İmza** `(self, required_files: list[str], source_store_sha256: str, algo_version: str, config_hash: str, force_recompute: bool=False, results_dir: Path | None=None)`
- **Girdi ve çıktı** Gerekli dosyalar, store/algo/config, force/path → bool.
- **Hesap ve işlem yorumu** Varlık ve üç kimlik eşitliği.
- **Zaman, hata ve risk** Parquet şema/içerik/çıkış hash yok.
- **Bağımlılıklar** Çekirdek dil, vektör işlemleri veya I/O.
- **Çağıranlar** [`engine_v3.run_v3_pipeline`](../astra6/engine_v3.py#L404)
- **Maliyet ve test** O(dosya). V3 432 dummy file kabulü.
- **Durum** `CONFIRMED_BUG`

#### [`CheckpointManager.bind_cache_identity`](../astra6/hpc.py#L917)

- **İmza** `(self, source_store_sha256: str, algo_version: str, config_hash: str)`
- **Girdi ve çıktı** Store/algo/config → JSON güncellemesi.
- **Hesap ve işlem yorumu** Kimlik ve UTC yazım zamanı.
- **Zaman, hata ve risk** Doğrudan yazım. Eşzamanlı/atomik deneme yok.
- **Bağımlılıklar** `datetime.datetime`, `json`
- **Çağıranlar** [`engine_v3.run_v3_pipeline`](../astra6/engine_v3.py#L404)
- **Maliyet ve test** Disk IO. V3 432.
- **Durum** `TEST_COVERAGE_GAP`

#### [`CheckpointManager.record_phase`](../astra6/hpc.py#L925)

- **İmza** `(self, phase_num: int, phase_name: str, status: str, details: dict[str, Any] | None=None)`
- **Girdi ve çıktı** Faz no/ad/status/detail → JSON state.
- **Hesap ve işlem yorumu** Zaman, RSS ve faz kaydı.
- **Zaman, hata ve risk** Sonuç bütünlüğü kanıtı değil. Doğrudan yazım.
- **Bağımlılıklar** [`hpc.get_peak_rss_mb`](../astra6/hpc.py#L124) · `datetime.datetime`, `json`
- **Çağıranlar** [`engine_v3.run_v3_pipeline`](../astra6/engine_v3.py#L404)
- **Maliyet ve test** Disk IO. Doğrudan yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`CheckpointManager.set_hardware_summary`](../astra6/hpc.py#L938)

- **İmza** `(self, hw_report: dict[str, Any])`
- **Girdi ve çıktı** Donanım dict → JSON state.
- **Hesap ve işlem yorumu** Benchmark özetini yazar.
- **Zaman, hata ve risk** Hata/atomiklik doğrulanmadı.
- **Bağımlılıklar** `json`
- **Çağıranlar** [`engine_v3.run_v3_pipeline`](../astra6/engine_v3.py#L404)
- **Maliyet ve test** Disk IO. Doğrudan yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

### `astra6/stats.py`

#### [`max_consecutive_losses`](../astra6/stats.py#L22)

- **İmza** `(r: np.ndarray)`
- **Girdi ve çıktı** R array → en uzun negatif seri.
- **Hesap ve işlem yorumu** x<0 biriktir, diğerinde sıfırla.
- **Zaman, hata ve risk** Girdi sıra. V3 <=0 kullanır. NaN kayıp sayılmaz.
- **Bağımlılıklar** Çekirdek dil, vektör işlemleri veya I/O.
- **Çağıranlar** [`stats.summarize_trades`](../astra6/stats.py#L43)
- **Maliyet ve test** O(n). Doğrudan yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`max_drawdown_r`](../astra6/stats.py#L34)

- **İmza** `(r: np.ndarray)`
- **Girdi ve çıktı** Kronolojik R array → R düşüşü.
- **Hesap ve işlem yorumu** Kümülatif PnL ve 0 dahil running peak.
- **Zaman, hata ve risk** Girdi sırası ve finite değerler çağıranda. Boşta 0.
- **Bağımlılıklar** `numpy`
- **Çağıranlar** [`stats.summarize_trades`](../astra6/stats.py#L43)
- **Maliyet ve test** O(n). Dört modelde bağımsız formül, kronolojik seçim ayrı.
- **Durum** `VERIFIED_CORRECT`

#### [`summarize_trades`](../astra6/stats.py#L43)

- **İmza** `(df: pd.DataFrame, r_col: str='r', n_boot: int=1000, block_size: int=5, seed: int=42)`
- **Girdi ve çıktı** Trade df ve R/boot seçenekleri → V2 performans dict.
- **Hesap ve işlem yorumu** Finite R, PF/DD, UTC günlük Sharpe/Sortino, trade-block CI ve OOS.
- **Zaman, hata ve risk** Girdi sırası. Sharpe yalnız işlem olan UTC günleri. Küçük sample ve empty yönetilir.
- **Bağımlılıklar** [`stats.block_bootstrap_mean`](../astra6/stats.py#L148), [`stats.max_consecutive_losses`](../astra6/stats.py#L22), [`stats.max_drawdown_r`](../astra6/stats.py#L34), [`stats.summarize_trades`](../astra6/stats.py#L43) · `numpy`, `pandas`
- **Çağıranlar** [`engine.extract_full_30s_micro_ssmt_and_attach`](../astra6/engine.py#L175), [`engine.run_all`](../astra6/engine.py#L237), [`stats.split_evaluation`](../astra6/stats.py#L242), [`stats.summarize_trades`](../astra6/stats.py#L43), [`stats.walk_forward_analysis`](../astra6/stats.py#L261)
- **Maliyet ve test** O(n + bootstrap×n) bellek. QA 09 statü.
- **Durum** `STATISTICAL_FAILURE`

#### [`block_bootstrap_mean`](../astra6/stats.py#L148)

- **İmza** `(r: np.ndarray, n_boot: int=1000, block_size: int=5, seed: int=42)`
- **Girdi ve çıktı** R, B, block length, seed → CI low/high ve p.
- **Hesap ve işlem yorumu** Dairesel ardışık bloklar ve bootstrap ortalamaları.
- **Zaman, hata ve risk** n<3 NaN. Blok satır sırası. p sıfır altında ampirik oran.
- **Bağımlılıklar** `numpy`
- **Çağıranlar** [`stats.summarize_trades`](../astra6/stats.py#L43)
- **Maliyet ve test** O(B×n). Doğrudan yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`compare_two_models`](../astra6/stats.py#L171)

- **İmza** `(df_treat: pd.DataFrame, df_base: pd.DataFrame, r_col: str='r', n_boot: int=2000, seed: int=42)`
- **Girdi ve çıktı** İki R havuzu, B/seed → fark, CI, p_boot/Welch/MW.
- **Hesap ve işlem yorumu** İki ayrı bootstrap ve bağımsız test.
- **Zaman, hata ve risk** <5 örnekte NaN. Çakışan politika sonuçlarında bağımsızlık varsayımı.
- **Bağımlılıklar** [`stats.Math_block_means`](../astra6/stats.py#L211) · `numpy`, `scipy.stats`
- **Çağıranlar** [`engine.run_all`](../astra6/engine.py#L237)
- **Maliyet ve test** O(B×n). Doğrudan yok.
- **Durum** `STATISTICAL_FAILURE`

#### [`Math_block_means`](../astra6/stats.py#L211)

- **İmza** `(r: np.ndarray, n_boot: int, b: int, rng: np.random.Generator)`
- **Girdi ve çıktı** R, B, b, rng → B bootstrap mean.
- **Hesap ve işlem yorumu** Dairesel blok indeksleri ve ortalama.
- **Zaman, hata ve risk** Sıralı, boş olmayan dizi bekler.
- **Bağımlılıklar** `numpy`
- **Çağıranlar** [`stats.compare_two_models`](../astra6/stats.py#L171)
- **Maliyet ve test** O(B×n). Doğrudan yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`adjust_pvalues`](../astra6/stats.py#L220)

- **İmza** `(pvals: list[float] | np.ndarray)`
- **Girdi ve çıktı** P vektörü → raw/Holm/BH DataFrame.
- **Hesap ve işlem yorumu** Sıralı step-down max ve BH ters min, ilk sıra.
- **Zaman, hata ve risk** Finite olmayan NaN. p sınır doğrulaması yok.
- **Bağımlılıklar** `numpy`, `pandas`
- **Çağıranlar** [`audit_v34_models.run_audit`](../astra6/audit_v34_models.py#L109), [`engine.run_all`](../astra6/engine.py#L237), [`engine_v3._select_genuine_25_rankings._pick_best`](../astra6/engine_v3.py#L284), [`engine_v3.run_v3_pipeline`](../astra6/engine_v3.py#L404)
- **Maliyet ve test** O(n log n). Dört model statsmodels karşılaştırması.
- **Durum** `VERIFIED_CORRECT`

#### [`split_evaluation`](../astra6/stats.py#L242)

- **İmza** `(df: pd.DataFrame, r_col: str='r')`
- **Girdi ve çıktı** t_trig/R frame → 4 tarihsel özet.
- **Hesap ve işlem yorumu** Temmuz 2024, Temmuz 2025 ve tüm dönem.
- **Zaman, hata ve risk** Event bilgi ve kapanış aralığını ayrı purge etmez. Boşta boş.
- **Bağımlılıklar** [`stats.summarize_trades`](../astra6/stats.py#L43) · `pandas`
- **Çağıranlar** [`engine.run_all`](../astra6/engine.py#L237)
- **Maliyet ve test** Grup özet ve bootstrap. Hazır çıktı dolaylı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`walk_forward_analysis`](../astra6/stats.py#L261)

- **İmza** `(candidates_by_model: dict[str, pd.DataFrame], r_col: str='r', train_months: int=12, test_months: int=6)`
- **Girdi ve çıktı** Model→t_trig/R frame, train/test ay → fold sonuçları.
- **Hesap ve işlem yorumu** Train en yüksek mean, min 20, sonraki 6 ay varsayılan.
- **Zaman, hata ve risk** Doküman 25 der. Gap/embargo ve son trade sonucu sınır guard yok. Tümü boş concat hatası.
- **Bağımlılıklar** [`stats.summarize_trades`](../astra6/stats.py#L43) · `pandas`
- **Çağıranlar** [`engine.run_all`](../astra6/engine.py#L237)
- **Maliyet ve test** O(fold×model×n). Doğrudan yok.
- **Durum** `STATISTICAL_FAILURE`

#### [`matched_control_comparison`](../astra6/stats.py#L322)

- **İmza** `(df_all: pd.DataFrame, treat_mask: pd.Series, base_mask: pd.Series, r_col: str='r', n_draws: int=1000, seed: int=42)`
- **Girdi ve çıktı** Aday tf/t_trig/atr_ref/R ve maskeler → excess/CI/p.
- **Hesap ve işlem yorumu** TF×NY saat×tam örneklem vol-tercile ve replacement örnek.
- **Zaman, hata ve risk** Eş hücre yoksa tüm baseline. Sonuç dağılımı seçim ve bağımlılık içerir.
- **Bağımlılıklar** `numpy`, `pandas`
- **Çağıranlar** [`engine.run_all`](../astra6/engine.py#L237)
- **Maliyet ve test** O(draw×treat). Doğrudan yok.
- **Durum** `STATISTICAL_FAILURE`

### `astra6/audit.py`

#### [`audit_100_crt_events`](../astra6/audit.py#L26)

- **İmza** `(panel: pd.DataFrame)`
- **Girdi ve çıktı** Panel → count/rate/örnek dict.
- **Hesap ve işlem yorumu** Resample ve CRT-A koşulunu seçip aynı eşitsizliği doğrular.
- **Zaman, hata ve risk** Zaman close>open. Üretim CRT kayıtlarıyla eşleme yok.
- **Bağımlılıklar** [`bars.resample`](../astra6/bars.py#L153)
- **Çağıranlar** [`audit.run_independent_audit`](../astra6/audit.py#L477)
- **Maliyet ve test** Tam TF groupby ve tarama. QA 10 hazır JSON.
- **Durum** `TEST_COVERAGE_GAP`

#### [`audit_100_ssmt_events`](../astra6/audit.py#L90)

- **İmza** `(panel: pd.DataFrame)`
- **Girdi ve çıktı** Panel → macro/micro count ve macro doğrulama dict.
- **Hesap ve işlem yorumu** Üretim olayları, macro referans ve running extreme XOR.
- **Zaman, hata ve risk** Yalnız macro örneklenir. İlk form/lead/inv kapsamı sınırlı.
- **Bağımlılıklar** [`bars.quarter_labels`](../astra6/bars.py#L184), [`smt.ssmt_events`](../astra6/smt.py#L102) · `numpy`, `pandas`
- **Çağıranlar** [`audit.run_independent_audit`](../astra6/audit.py#L477)
- **Maliyet ve test** Tam panel ve block groupby. QA 10 hazır JSON.
- **Durum** `TEST_COVERAGE_GAP`

#### [`audit_100_cisd_events`](../astra6/audit.py#L170)

- **İmza** `(panel: pd.DataFrame)`
- **Girdi ve çıktı** Panel → CISD audit dict.
- **Hesap ve işlem yorumu** Üretim M1/M3/M5/M15 olaylarından ref/close ve zaman tutarlılığı.
- **Zaman, hata ve risk** Algoritmanın completeness/ilk onset referansı değil.
- **Bağımlılıklar** [`bars.resample`](../astra6/bars.py#L153), [`cisd.extract_tf_cisd_events`](../astra6/cisd.py#L162) · `pandas`
- **Çağıranlar** [`audit.run_independent_audit`](../astra6/audit.py#L477)
- **Maliyet ve test** TF groupby ve örnek. QA 10 hazır JSON.
- **Durum** `TEST_COVERAGE_GAP`

#### [`audit_100_mmxm_events`](../astra6/audit.py#L243)

- **İmza** `()`
- **Girdi ve çıktı** trade_features → V2 MMXM audit dict.
- **Hesap ve işlem yorumu** Saklanan stage, sweep, box, CISD, etiket ve target ilişkisi.
- **Zaman, hata ve risk** Raw OC/FSM bağımsız üretim yok.
- **Bağımlılıklar** `pandas`
- **Çağıranlar** [`audit.run_independent_audit`](../astra6/audit.py#L477)
- **Maliyet ve test** Parquet ve records kopyası. QA 10 hazır JSON.
- **Durum** `SEMANTIC_MISMATCH`

#### [`audit_100_completed_trades`](../astra6/audit.py#L297)

- **İmza** `(panel: pd.DataFrame)`
- **Girdi ve çıktı** Panel, trade_features → replay audit dict.
- **Hesap ve işlem yorumu** V2 fill+stop/TP/horizon için bağımsız bar döngüsü.
- **Zaman, hata ve risk** Saklanan stop/target. V3 politika, gerçek broker ve exit provenance sınanmaz.
- **Bağımlılıklar** `pandas`
- **Çağıranlar** [`audit.run_independent_audit`](../astra6/audit.py#L477)
- **Maliyet ve test** Tam tablo okuma, 100×360. QA 10 hazır JSON, bu audit ayrı V3 örneği.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`build_v1_vs_v2_comparison`](../astra6/audit.py#L411)

- **İmza** `()`
- **Girdi ve çıktı** V1/V2 özet tablosu → delta DataFrame ve çıktı.
- **Hesap ve işlem yorumu** Önce/sonra seçilmiş istatistiklerin karşılaştırması.
- **Zaman, hata ve risk** Veri/politika farkı nedensel atıf yapmaz. Eksik dosya davranışı veri yoluna bağlı.
- **Bağımlılıklar** `pandas`
- **Çağıranlar** [`audit.run_independent_audit`](../astra6/audit.py#L477)
- **Maliyet ve test** Parquet IO. Doğrudan yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`run_independent_audit`](../astra6/audit.py#L477)

- **İmza** `()`
- **Girdi ve çıktı** Yerel panel ve sonuçlar → 5×100 JSON ve V1/V2 karşılaştırma.
- **Hesap ve işlem yorumu** Beş örneği çağırır, her passed=100 ise overall.
- **Zaman, hata ve risk** Çağrı hazır çıktıları yazar. “Independent” kapsamı alt fonksiyonlarla sınırlı.
- **Bağımlılıklar** [`audit.audit_100_cisd_events`](../astra6/audit.py#L170), [`audit.audit_100_completed_trades`](../astra6/audit.py#L297), [`audit.audit_100_crt_events`](../astra6/audit.py#L26), [`audit.audit_100_mmxm_events`](../astra6/audit.py#L243), [`audit.audit_100_ssmt_events`](../astra6/audit.py#L90), [`audit.build_v1_vs_v2_comparison`](../astra6/audit.py#L411), [`bars.load_panel`](../astra6/bars.py#L85) · `json`
- **Çağıranlar** [`run_pipeline.main`](../run_pipeline.py#L131), [`astra6/audit.py` modül akışı](../astra6/audit.py)
- **Maliyet ve test** Tam IO ve örnek tarama. QA 10 JSON.
- **Durum** `TEST_COVERAGE_GAP`

### `astra6/audit_v34_models.py`

#### [`compute_model_metrics`](../astra6/audit_v34_models.py#L35)

- **İmza** `(df: pd.DataFrame, model_id: str, model_name: str, hypothesis: str, target_type: str, entry_rule: str, stop_rule: str, target_rule: str, min_trades_threshold: int=30)`
- **Girdi ve çıktı** R/day/validation/outcome frame, model metadata, N eşiği → metrics/status dict.
- **Hesap ve işlem yorumu** _fast_cell_metrics ve pozitif full+OOS status.
- **Zaman, hata ve risk** p/CI ve nedensellik kontrolü yok. Boş şema eksik. Bazı varsayımlar ölü değişken.
- **Bağımlılıklar** [`engine_v3._fast_cell_metrics`](../astra6/engine_v3.py#L89) · `numpy`
- **Çağıranlar** [`audit_v34_models.run_audit`](../astra6/audit_v34_models.py#L109)
- **Maliyet ve test** O(n+bootstrap). Dört model bağımsız yeniden hesap, Model 3 bulgusu.
- **Durum** `STATISTICAL_FAILURE`

#### [`run_audit`](../astra6/audit_v34_models.py#L109)

- **İmza** `()`
- **Girdi ve çıktı** Beş sonuç Parquet → 4 satır ve JSON.
- **Hesap ve işlem yorumu** Hazır hedef/policy sonuçlarını join/filter; M4 sabit fallback; 4 p düzeltme.
- **Zaman, hata ve risk** Raw fiyat veya pre-entry zaman doğrulaması yok. Statik anlatı. Eksik hedef/boş M4 hata.
- **Bağımlılıklar** [`audit_v34_models.compute_model_metrics`](../astra6/audit_v34_models.py#L35), [`stats.adjust_pvalues`](../astra6/stats.py#L220) · `json`, `numpy`, `pandas`
- **Çağıranlar** [`astra6/audit_v34_models.py` modül akışı](../astra6/audit_v34_models.py)
- **Maliyet ve test** Büyük tablo read/merge. Bağımsız model ve fallback denetimi.
- **Durum** `CONFIRMED_BUG`

### `astra6/fractal_narrative_v34.py`

#### [`run_narrative_validation`](../astra6/fractal_narrative_v34.py#L38)

- **İmza** `()`
- **Girdi ve çıktı** Aday/target/all_trades Parquet → 3 metrik satırı, JSON.
- **Hesap ve işlem yorumu** Basit TF/dir/target maskeleri ve özet.
- **Zaman, hata ve risk** Okunan aday/all_trades olay sıralaması için kullanılmaz. İddia edilen ayrı teyit ve gecikme yok.
- **Bağımlılıklar** [`engine_v3._fast_cell_metrics`](../astra6/engine_v3.py#L89) · `json`, `pandas`
- **Çağıranlar** [`astra6/fractal_narrative_v34.py` modül akışı](../astra6/fractal_narrative_v34.py)
- **Maliyet ve test** Büyük join/filter. Bu audit üç maske ve TF sayımı.
- **Durum** `SEMANTIC_MISMATCH`

### `astra6/trade_replay_v34.py`

#### [`generate_svg_chart`](../astra6/trade_replay_v34.py#L41)

- **İmza** `(replay: dict[str, Any], bars_df: pd.DataFrame)`
- **Girdi ve çıktı** Replay dict, o/h/l/c → SVG str.
- **Hesap ve işlem yorumu** Min/max ölçek, mum ve sabit yatay seviye etiketleri.
- **Zaman, hata ve risk** Timestamp ekseni yok. Boş/malformed frame guard sınırlı. Render verilen fiyatı çizer.
- **Bağımlılıklar** [`trade_replay_v34.generate_svg_chart.get_x`](../astra6/trade_replay_v34.py#L61), [`trade_replay_v34.generate_svg_chart.get_y`](../astra6/trade_replay_v34.py#L64) · `numpy`
- **Çağıranlar** [`trade_replay_v34.build_trade_replays`](../astra6/trade_replay_v34.py#L118)
- **Maliyet ve test** O(n). 20 SVG başlık ve fitil sayısı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`generate_svg_chart.get_x`](../astra6/trade_replay_v34.py#L61)

- **İmza** `(i: int)`
- **Girdi ve çıktı** Bar indeksi → SVG x.
- **Hesap ve işlem yorumu** Eşit aralıklı ölçek.
- **Zaman, hata ve risk** Gerçek zaman veya gap ölçeği değil.
- **Bağımlılıklar** Çekirdek dil, vektör işlemleri veya I/O.
- **Çağıranlar** [`trade_replay_v34.generate_svg_chart`](../astra6/trade_replay_v34.py#L41)
- **Maliyet ve test** O(1). SVG incelemesi.
- **Durum** `SEMANTIC_MISMATCH`

#### [`generate_svg_chart.get_y`](../astra6/trade_replay_v34.py#L64)

- **İmza** `(px: float)`
- **Girdi ve çıktı** Fiyat → SVG y.
- **Hesap ve işlem yorumu** Lineer ters y ölçeği.
- **Zaman, hata ve risk** Zaman yok. Y ölçeği çağıran fiyat aralığına bağlı.
- **Bağımlılıklar** Çekirdek dil, vektör işlemleri veya I/O.
- **Çağıranlar** [`trade_replay_v34.generate_svg_chart`](../astra6/trade_replay_v34.py#L41)
- **Maliyet ve test** O(1). SVG incelemesi.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`build_trade_replays`](../astra6/trade_replay_v34.py#L118)

- **İmza** `()`
- **Girdi ve çıktı** Panel ve sonuç Parquet → JSON 20 kayıt, 20 SVG.
- **Hesap ve işlem yorumu** 10 TP/5 SL/3 etiketlenen invalidation/2 timeout örneklemesi. Çizim random drift.
- **Zaman, hata ve risk** Fiyat OHLC kaynağı kullanılmaz, saat ve semantik etiketler sabit. Küçük popülasyon sample hatası.
- **Bağımlılıklar** [`bars.load_panel`](../astra6/bars.py#L85), [`trade_replay_v34.generate_svg_chart`](../astra6/trade_replay_v34.py#L41) · `json`, `numpy`, `pandas`
- **Çağıranlar** [`astra6/trade_replay_v34.py` modül akışı](../astra6/trade_replay_v34.py)
- **Maliyet ve test** Büyük okuma, 20×45 çizim. A/B denetimi, üretim generator çalıştırılmadı.
- **Durum** `CONFIRMED_BUG`

### `astra6/report.py`

#### [`_load`](../astra6/report.py#L46)

- **İmza** `(name: str)`
- **Girdi ve çıktı** Sonuç adı → V2 Parquet df.
- **Hesap ve işlem yorumu** Veri dosyası oku.
- **Zaman, hata ve risk** Missing hata. Sürüm bağı denetlenmez.
- **Bağımlılıklar** `pandas`
- **Çağıranlar** [`report.generate_figures`](../astra6/report.py#L85), [`report.generate_html_report`](../astra6/report.py#L556), [`report.generate_pdf_report`](../astra6/report.py#L761), [`report.get_20_final_questions_answers`](../astra6/report.py#L321)
- **Maliyet ve test** Dosya IO. QA 10 dolaylı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`_load_json`](../astra6/report.py#L50)

- **İmza** `(name: str)`
- **Girdi ve çıktı** Dosya adı → dict.
- **Hesap ve işlem yorumu** JSON decode.
- **Zaman, hata ve risk** Missing/parse hata.
- **Bağımlılıklar** `json`
- **Çağıranlar** [`report.generate_html_report`](../astra6/report.py#L556), [`report.generate_pdf_report`](../astra6/report.py#L761), [`report.get_20_final_questions_answers`](../astra6/report.py#L321)
- **Maliyet ve test** Dosya IO. QA 10 dolaylı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`_fmt_r`](../astra6/report.py#L54)

- **İmza** `(val: float)`
- **Girdi ve çıktı** Sayı → işaretli R dizgesi.
- **Hesap ve işlem yorumu** 3 ondalık ve N/A.
- **Zaman, hata ve risk** Hesap değil sunum.
- **Bağımlılıklar** `pandas`
- **Çağıranlar** [`report.generate_html_report`](../astra6/report.py#L556), [`report.get_20_final_questions_answers`](../astra6/report.py#L321)
- **Maliyet ve test** O(1). QA 10 M15 metni.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`_fmt_pct`](../astra6/report.py#L58)

- **İmza** `(val: float)`
- **Girdi ve çıktı** Oran → yüzde str.
- **Hesap ve işlem yorumu** 100×oran, 2 ondalık.
- **Zaman, hata ve risk** Hesap değil sunum.
- **Bağımlılıklar** `pandas`
- **Çağıranlar** [`report.get_20_final_questions_answers`](../astra6/report.py#L321)
- **Maliyet ve test** O(1). QA 10 dolaylı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`_row_stat`](../astra6/report.py#L62)

- **İmza** `(df: pd.DataFrame, mask: pd.Series)`
- **Girdi ve çıktı** df ve mask → dict.
- **Hesap ve işlem yorumu** İlk eşleşen satır veya default metrikler.
- **Zaman, hata ve risk** Çok eşleşmede ilk, zaman sırası çağıranda.
- **Bağımlılıklar** Çekirdek dil, vektör işlemleri veya I/O.
- **Çağıranlar** [`report.generate_html_report`](../astra6/report.py#L556), [`report.get_20_final_questions_answers`](../astra6/report.py#L321)
- **Maliyet ve test** O(n). QA 10 dolaylı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`_register_turkish_fonts`](../astra6/report.py#L70)

- **İmza** `()`
- **Girdi ve çıktı** Makine fontları → iki font adı.
- **Hesap ve işlem yorumu** Arial yolları ya da Helvetica.
- **Zaman, hata ve risk** Platform bağımlı, fallback Türkçe glif doğrulamaz.
- **Bağımlılıklar** `pathlib.Path`, `reportlab.pdfbase.pdfmetrics`, `reportlab.pdfbase.ttfonts.TTFont`
- **Çağıranlar** [`report.generate_pdf_report`](../astra6/report.py#L761), [`report_v3.build_v3_reports`](../astra6/report_v3.py#L300)
- **Maliyet ve test** Dosya IO. Doğrudan yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`generate_figures`](../astra6/report.py#L85)

- **İmza** `()`
- **Girdi ve çıktı** V2 result lake → 8 grafik yolu.
- **Hesap ve işlem yorumu** Metrik, QT, exit/cost ve trade örnek çizimleri.
- **Zaman, hata ve risk** Önceki özetlere bağlı. V3.4 replay yolu ayrı.
- **Bağımlılıklar** [`report._load`](../astra6/report.py#L46) · `matplotlib.pyplot`, `numpy`, `pandas`, `polars`
- **Çağıranlar** [`report.build_all_reports`](../astra6/report.py#L868)
- **Maliyet ve test** Tablo IO ve Matplotlib. Hazır rapor smoke.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`_b64_img`](../astra6/report.py#L310)

- **İmza** `(path: Path)`
- **Girdi ve çıktı** Dosya yolu → base64 str.
- **Hesap ve işlem yorumu** Dosya bytes encode.
- **Zaman, hata ve risk** Missing hata. Tarih yok.
- **Bağımlılıklar** `base64`
- **Çağıranlar** [`report.generate_html_report`](../astra6/report.py#L556), [`report_v3.build_v3_reports`](../astra6/report_v3.py#L300)
- **Maliyet ve test** O(bytes). QA 10 hazır HTML.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`_df_html`](../astra6/report.py#L314)

- **İmza** `(df: pd.DataFrame, max_rows: int=30)`
- **Girdi ve çıktı** df/max rows → HTML.
- **Hesap ve işlem yorumu** Sınırlı tablonun sunum dönüşümü.
- **Zaman, hata ve risk** Girdi sırası, no analytical calculations.
- **Bağımlılıklar** `pandas`
- **Çağıranlar** [`report.generate_html_report`](../astra6/report.py#L556), [`report_v3.build_v3_reports`](../astra6/report_v3.py#L300)
- **Maliyet ve test** O(gösterilen). Doğrudan yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`get_20_final_questions_answers`](../astra6/report.py#L321)

- **İmza** `()`
- **Girdi ve çıktı** Çoklu V2 tablo → 20 soru/yanıt.
- **Hesap ve işlem yorumu** Hazır metrikleri seçip Türkçe metne yerleştir.
- **Zaman, hata ve risk** Yorumların tümü veriden çıkarılmaz. V3.4 yolu değil.
- **Bağımlılıklar** [`report._fmt_pct`](../astra6/report.py#L58), [`report._fmt_r`](../astra6/report.py#L54), [`report._load`](../astra6/report.py#L46), [`report._load_json`](../astra6/report.py#L50), [`report._row_stat`](../astra6/report.py#L62)
- **Çağıranlar** [`report.generate_html_report`](../astra6/report.py#L556), [`report.generate_pdf_report`](../astra6/report.py#L761)
- **Maliyet ve test** Çoklu IO. QA 10, M15 sayı çapraz kontrolü.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`generate_html_report`](../astra6/report.py#L556)

- **İmza** `(figs: dict[str, Path])`
- **Girdi ve çıktı** Fig paths, V2 tablolar → HTML.
- **Hesap ve işlem yorumu** Template/tablolar ve base64 grafikler.
- **Zaman, hata ve risk** Var olan çıktı yazar. Sürüm id kontrolü yok.
- **Bağımlılıklar** [`report._b64_img`](../astra6/report.py#L310), [`report._df_html`](../astra6/report.py#L314), [`report._fmt_r`](../astra6/report.py#L54), [`report._load`](../astra6/report.py#L46), [`report._load_json`](../astra6/report.py#L50), [`report._row_stat`](../astra6/report.py#L62), [`report.get_20_final_questions_answers`](../astra6/report.py#L321)
- **Çağıranlar** [`report.build_all_reports`](../astra6/report.py#L868)
- **Maliyet ve test** IO ve rendering. QA 10 hazır çıktı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`_make_rl_table`](../astra6/report.py#L728)

- **İmza** `(df: pd.DataFrame, cols: list[str], font_reg: str, font_bold: str, max_rows: int=18)`
- **Girdi ve çıktı** df, kolonlar, font ve sınır → ReportLab Table.
- **Hesap ve işlem yorumu** Satır/format/layout.
- **Zaman, hata ve risk** Eksik kolon fail veya daraltma çağırana bağlı.
- **Bağımlılıklar** `reportlab.lib.colors`, `reportlab.platypus.Table`, `reportlab.platypus.TableStyle`
- **Çağıranlar** [`report.generate_pdf_report`](../astra6/report.py#L761), [`report_v3.build_v3_reports`](../astra6/report_v3.py#L300)
- **Maliyet ve test** O(gösterilen). Doğrudan yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`generate_pdf_report`](../astra6/report.py#L761)

- **İmza** `(figs: dict[str, Path])`
- **Girdi ve çıktı** Fig paths, V2 tablo → PDF.
- **Hesap ve işlem yorumu** ReportLab akışı.
- **Zaman, hata ve risk** Var olan çıktı yazar. Pazar kanıtı üretmez.
- **Bağımlılıklar** [`report._load`](../astra6/report.py#L46), [`report._load_json`](../astra6/report.py#L50), [`report._make_rl_table`](../astra6/report.py#L728), [`report._register_turkish_fonts`](../astra6/report.py#L70), [`report.get_20_final_questions_answers`](../astra6/report.py#L321) · `reportlab.lib.colors`, `reportlab.lib.styles.ParagraphStyle`, `reportlab.lib.styles.getSampleStyleSheet`, `reportlab.platypus.Image`, `reportlab.platypus.PageBreak`, `reportlab.platypus.Paragraph`, `reportlab.platypus.SimpleDocTemplate`, `reportlab.platypus.Spacer`
- **Çağıranlar** [`report.build_all_reports`](../astra6/report.py#L868)
- **Maliyet ve test** PDF IO. QA 10 boyut.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`build_all_reports`](../astra6/report.py#L868)

- **İmza** `()`
- **Girdi ve çıktı** Sonuç lake → V2/V3 yolları.
- **Hesap ve işlem yorumu** V2 grafik/HTML/PDF ve V3 rapor çağrısı.
- **Zaman, hata ve risk** V3.4 ayrı. Hata alt çağrıda.
- **Bağımlılıklar** [`report.generate_figures`](../astra6/report.py#L85), [`report.generate_html_report`](../astra6/report.py#L556), [`report.generate_pdf_report`](../astra6/report.py#L761), [`report_v3.build_v3_reports`](../astra6/report_v3.py#L300)
- **Çağıranlar** [`run_pipeline.main`](../run_pipeline.py#L131), [`astra6/report.py` modül akışı](../astra6/report.py)
- **Maliyet ve test** Rendering ve disk. run_pipeline, QA 10 dolaylı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

### `astra6/report_v3.py`

#### [`_load`](../astra6/report_v3.py#L43)

- **İmza** `(name: str)`
- **Girdi ve çıktı** Ad → V3 Parquet df.
- **Hesap ve işlem yorumu** Tablo oku.
- **Zaman, hata ve risk** Missing hata.
- **Bağımlılıklar** `pandas`
- **Çağıranlar** [`report_v3.build_v3_reports`](../astra6/report_v3.py#L300), [`report_v3.generate_v3_figures`](../astra6/report_v3.py#L60), [`report_v3.get_v3_core_mission_answers`](../astra6/report_v3.py#L195)
- **Maliyet ve test** Dosya IO. Doğrudan yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`_load_json`](../astra6/report_v3.py#L47)

- **İmza** `(name: str)`
- **Girdi ve çıktı** Ad → JSON dict.
- **Hesap ve işlem yorumu** Manifest ve audit metadata oku.
- **Zaman, hata ve risk** Missing/parse davranışı kaynak yoluna bağlı.
- **Bağımlılıklar** `json`
- **Çağıranlar** [`report_v3.build_v3_reports`](../astra6/report_v3.py#L300), [`report_v3.get_v3_core_mission_answers`](../astra6/report_v3.py#L195)
- **Maliyet ve test** IO. Doğrudan yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`_fmt_r`](../astra6/report_v3.py#L52)

- **İmza** `(val: float)`
- **Girdi ve çıktı** Sayı → R str.
- **Hesap ve işlem yorumu** R biçimi.
- **Zaman, hata ve risk** Sunum.
- **Bağımlılıklar** `pandas`
- **Çağıranlar** [`report_v3.get_v3_core_mission_answers`](../astra6/report_v3.py#L195)
- **Maliyet ve test** O(1). Doğrudan yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`_fmt_pct`](../astra6/report_v3.py#L56)

- **İmza** `(val: float)`
- **Girdi ve çıktı** Oran → yüzde str.
- **Hesap ve işlem yorumu** 100×oran.
- **Zaman, hata ve risk** Sunum.
- **Bağımlılıklar** `pandas`
- **Çağıranlar** [`report_v3.get_v3_core_mission_answers`](../astra6/report_v3.py#L195)
- **Maliyet ve test** O(1). Doğrudan yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`generate_v3_figures`](../astra6/report_v3.py#L60)

- **İmza** `()`
- **Girdi ve çıktı** V3 özet Parquet → fig yolları.
- **Hesap ve işlem yorumu** 64 grid, entry/target, NY, ablation, ranking.
- **Zaman, hata ve risk** 2R ve yapı popülasyonları tabloların sözleşmesini miras alır.
- **Bağımlılıklar** [`report_v3._load`](../astra6/report_v3.py#L43) · `matplotlib.pyplot`, `numpy`, `pandas`
- **Çağıranlar** [`report_v3.build_v3_reports`](../astra6/report_v3.py#L300)
- **Maliyet ve test** IO/Matplotlib. Doğrudan yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`get_v3_core_mission_answers`](../astra6/report_v3.py#L195)

- **İmza** `()`
- **Girdi ve çıktı** V3 tablolar ve metadata → metin çiftleri.
- **Hesap ve işlem yorumu** Seçilmiş metrikler ve sabit yorumlar.
- **Zaman, hata ve risk** Yeni işlem veya istatistik kanıtı yok.
- **Bağımlılıklar** [`report_v3._fmt_pct`](../astra6/report_v3.py#L56), [`report_v3._fmt_r`](../astra6/report_v3.py#L52), [`report_v3._load`](../astra6/report_v3.py#L43), [`report_v3._load_json`](../astra6/report_v3.py#L47)
- **Çağıranlar** [`report_v3.build_v3_reports`](../astra6/report_v3.py#L300)
- **Maliyet ve test** Çoklu IO. Doğrudan yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`build_v3_reports`](../astra6/report_v3.py#L300)

- **İmza** `()`
- **Girdi ve çıktı** V3 tablo/fig → HTML/PDF/fig yolları.
- **Hesap ve işlem yorumu** Dinamik özet biçimlemesi, ReportLab.
- **Zaman, hata ve risk** Sürüm doğrulaması yok. V3.4 Markdown dönüştürücüsünden ayrı.
- **Bağımlılıklar** [`report._b64_img`](../astra6/report.py#L310), [`report._df_html`](../astra6/report.py#L314), [`report._make_rl_table`](../astra6/report.py#L728), [`report._register_turkish_fonts`](../astra6/report.py#L70), [`report_v3._load`](../astra6/report_v3.py#L43), [`report_v3._load_json`](../astra6/report_v3.py#L47), [`report_v3.generate_v3_figures`](../astra6/report_v3.py#L60), [`report_v3.get_v3_core_mission_answers`](../astra6/report_v3.py#L195) · `reportlab.lib.colors`, `reportlab.lib.styles.ParagraphStyle`, `reportlab.lib.styles.getSampleStyleSheet`, `reportlab.platypus.Image`, `reportlab.platypus.PageBreak`, `reportlab.platypus.Paragraph`, `reportlab.platypus.SimpleDocTemplate`, `reportlab.platypus.Spacer`
- **Çağıranlar** [`report.build_all_reports`](../astra6/report.py#L868), [`astra6/report_v3.py` modül akışı](../astra6/report_v3.py)
- **Maliyet ve test** IO/render. Doğrudan yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

### `app.py`

#### [`load_table`](../app.py#L45)

- **İmza** `(name: str)`
- **Girdi ve çıktı** Ad → cached Parquet df veya boş.
- **Hesap ve işlem yorumu** Streamlit cache ile dosya okur.
- **Zaman, hata ve risk** Kayıp dosyayı boş gösterir. Cache anahtarı dosya hash'i değil.
- **Bağımlılıklar** `pandas`
- **Çağıranlar** [`app.py` modül akışı](../app.py)
- **Maliyet ve test** IO/bellek. Doğrudan yok.
- **Durum** `DATA_LIMITATION`

#### [`load_json`](../app.py#L51)

- **İmza** `(name: str)`
- **Girdi ve çıktı** Ad → cached dict veya boş.
- **Hesap ve işlem yorumu** Streamlit cache ile JSON.
- **Zaman, hata ve risk** Missing {}, malformed hata. Sürüm kontrolü yok.
- **Bağımlılıklar** `json`
- **Çağıranlar** [`app.py` modül akışı](../app.py)
- **Maliyet ve test** IO. Doğrudan yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

#### [`load_m1_slice`](../app.py#L57)

- **İmza** `(start_utc: str, end_utc: str)`
- **Girdi ve çıktı** UTC başlangıç/bitiş → US100/500 Bid df.
- **Hesap ve işlem yorumu** İki dosya filtre ve iç join.
- **Zaman, hata ve risk** Ask veya gerçek emir yeniden yürütmesi yok. Tam dosya okur.
- **Bağımlılıklar** `pandas`, `polars`
- **Çağıranlar** [`app.py` modül akışı](../app.py)
- **Maliyet ve test** Parquet IO. Doğrudan yok.
- **Durum** `DATA_LIMITATION`

### `run_pipeline.py`

#### [`_sha256_full`](../run_pipeline.py#L119)

- **İmza** `(path: Path)`
- **Girdi ve çıktı** Path → tam SHA256.
- **Hesap ve işlem yorumu** Tüm dosyayı bloklar halinde hash.
- **Zaman, hata ve risk** IO hatası dışarı çıkar.
- **Bağımlılıklar** `hashlib`
- **Çağıranlar** [`run_pipeline.main`](../run_pipeline.py#L131)
- **Maliyet ve test** O(bytes). Manifest bağımsız okuma.
- **Durum** `VERIFIED_CORRECT`

#### [`main`](../run_pipeline.py#L131)

- **İmza** `()`
- **Girdi ve çıktı** CLI argümanları, local store/result → exit int, rapor/manifest.
- **Hesap ve işlem yorumu** Koşullu ingest/V2 audit/V3, rapor, pytest, SHA.
- **Zaman, hata ve risk** Yazım ve ağ dalları. V3.4 script zinciri ayrı. pytest hata kodu döner.
- **Bağımlılıklar** [`audit.run_independent_audit`](../astra6/audit.py#L477), [`engine.run_all`](../astra6/engine.py#L237), [`engine_v3.run_v3_pipeline`](../astra6/engine_v3.py#L404), [`report.build_all_reports`](../astra6/report.py#L868), [`run_pipeline._sha256_full`](../run_pipeline.py#L119) · `argparse`, `datetime.datetime`, `json`, `subprocess`, `time`
- **Çağıranlar** [`run_pipeline.py` modül akışı](../run_pipeline.py)
- **Maliyet ve test** Tam pipeline. QA 10 gereksinim sabitleri, çağrılmadı.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

### `build_report_pdf.py`

#### [`build`](../build_report_pdf.py#L336)

- **İmza** `()`
- **Girdi ve çıktı** V3.3 Markdown → HTML/PDF.
- **Hesap ve işlem yorumu** Pandoc ve Chrome subprocess.
- **Zaman, hata ve risk** Read/write yolları sabit, süreç hatasında çıkar.
- **Bağımlılıklar** `subprocess`, `sys`
- **Çağıranlar** [`build_report_pdf.py` modül akışı](../build_report_pdf.py)
- **Maliyet ve test** Render/IO. Doğrudan yok.
- **Durum** `IMPLEMENTED_NOT_VERIFIED`

### `build_v34_report.py`

#### [`build`](../build_v34_report.py#L267)

- **İmza** `()`
- **Girdi ve çıktı** V3.4 Markdown → HTML/PDF.
- **Hesap ve işlem yorumu** Pandoc ve Chrome subprocess.
- **Zaman, hata ve risk** JSON ve model audit bağlı değil. Çıktı üretimi mevcut metni çoğaltır.
- **Bağımlılıklar** `subprocess`, `sys`
- **Çağıranlar** [`build_v34_report.py` modül akışı](../build_v34_report.py)
- **Maliyet ve test** Render/IO. Mevcut PDF ve Markdown satır karşılaştırması.
- **Durum** `SEMANTIC_MISMATCH`

### `src/astra6/__init__.py`

#### [`main`](../src/astra6/__init__.py#L1)

- **İmza** `()`
- **Girdi ve çıktı** CLI → stdout.
- **Hesap ve işlem yorumu** Hello mesajı.
- **Zaman, hata ve risk** Araştırma komutu değil.
- **Bağımlılıklar** Çekirdek dil, vektör işlemleri veya I/O.
- **Çağıranlar** Üretim ağacında statik çağrı bulunmadı.
- **Maliyet ve test** O(1). Paket giriş stub'ı, araştırma test kapsamı yok.
- **Durum** `DEAD_OR_UNUSED_CODE`

## Yapı sınıfları

- [`SessionStamp`](../astra6/clock.py#L101) aynı günün UTC/yerel açılış görünümleri ve DST rejimi. `session_stamp` üretir.
- [`HardwareProfile`](../astra6/hpc.py#L69) CPU/RAM/işçi/parti seçimi. `detect_hardware_profile` üretir. Analitik fiyat girdisi değildir.
- [`RateGate`](../astra6/data/download.py#L30) indirme hızı ve ortak lock durumu. Ağ yolu denetimde çalıştırılmadı.
- [`CheckpointManager`](../astra6/hpc.py#L866) JSON kimlik ve faz durumu. Tam üretim provenance kaydı değildir.
