# ASTRA 6 işlem mantığı ve nedensellik

**Aşama 3–4 kontrol noktası** MMXM, QT, CRT, SMT/SSMT, CISD, likidite ve hedef kaynak kodu izlendi. Aynı tarihsel olayın fiyat ve zaman kanıtı [sonuç uzlaştırmasında](ASTRA6_V34_RESULT_RECONCILIATION.md).

## Beş eksen ve olay sırası

| Eksen | Fiilî üretim | Araştırma anlamı |
|---|---|---|
| Orijin | `pw_swept` / `pd_swept` varsa W1/D1, yoksa CRT'nin `tf` alanı. [`attach_full_fractal_context`](../astra6/fractal_v3.py#L1405) | Seviye ailesi veya tetik mumu TF'si. Kimliği olan HTF sweep olayını temsil eden bir bağ yok. |
| MMXM yapısı | FSM'nin seçilmiş tek aynı yönlü olayının `tf` alanı. [As-of bağlama](../astra6/fractal_v3.py#L1310) | TF alanı gerçekten ayrı. Model ilişkileri, iç içe iki FSM kimliğiyle kurulmaz. `Nested_MMBM` H1/M15 mum rengi + bir etkin MMXM üzerinden atanır. [Yön ilişkisi](../astra6/fractal_v3.py#L1384) |
| Giriş | CRT adayının kipi ve as-of CISD bayrakları ile `np.select`. [`entry_tf`](../astra6/fractal_v3.py#L1412) | Bir TF adı daha önce görülmüş CISD bağlamını gösterebilir. Fiilî politika tetiğinin o TF kapanışı olduğunu kanıtlamaz. İşlem her dalda M1 açılışında simüle edilir. |
| Hedef | CRT karşı kenarı, M5/M15/H1/H4 OC midpoint veya M15/H1/H4/D1/W1 önceki mum high/low. [Hedef listesi](../astra6/fractal_v3.py#L1505) | TF küçük, eşit veya büyük olabilir. Önceki mum ekstremi, tüketilmemiş swing likiditesi için bir vekildir. |
| Zaman | Yerel duvar saati QT etiketleri, temel CRT tetik bağlamı ve SSMT referansları. [`quarter_labels`](../astra6/bars.py#L184), [politika satırı](../astra6/engine_v3.py#L1030) | Fazlar hesaplanır. Faz geçişi MMXM state machine'i yürütmez. Yeniden zamanlanan emrin QT, NY dakika, gün ve split alanları çoğunlukla temel adaydan taşınır. |

`build_narrative_graph_and_snapshots` üç kenar setini bir satırdaki metin etiketlerinden kurar. Üçüne aynı `t_known` yazılır. Olayların kendi `event_id`, kaynak TF ve teyit zamanları arasında yönlü, sıralı bağı doğrulayan bir sorgu yoktur. Örneğin `Conflict` harici QT/SSMT etiketi `NO_CISD` hedefine dahi `confirms` kenarı üretebilir. [Kenar üretimi](../astra6/fractal_v3.py#L1955)

## Original Consolidation ve MMXM

- OC taraması dört ardışık TF kovasının `max(H)-min(L)` genişliğini önceki Wilder ATR'ye böler. M1/M3 için genişlik ≤2,0 ATR ve ayrılış ≥0,55 ATR. Diğer TF'ler için ≤2,4 ve ≥0,35. Ayrılış kapanışı bandın dışında olmalı. Örnek olarak bant 100–110 ve ATR 5 ise 98 kapanışı, 0,35 eşiğinde aşağı ayrılıştır. Bu, yukarı dönüş yönlü MMBM girdisi oluşturur. En yakın önceki ayrılıştan iki TF barı geçmelidir. Tarayıcı ayrıca sonraki 96 TF barını ziyaret ve invalidation için etiketler. Bu ileri sonuçlar tarihi aday satırından ayrı yorumlanmalıdır. [Tarayıcı](../astra6/fractal_v3.py#L116), [TF ayarları](../astra6/fractal_v3.py#L261)
- `t_start` ilk pencere barı. `t_cand_known` ayrılıştan önceki mumun kapanışına geri yazılır. `t_confirm = t_known` ayrılış kapanışıdır. Olayın yönü ve aday olarak kaydedilmesi ayrılışa bağlı olduğu için FSM Stage 1 bu tarihe geri yazılamaz. `j_conf_m1` son `M1 open+1m <= TF close` indeksini kullanır. Eksik M1 sınırında bu indeks TF kapanışından önceki bir bilgi anına karşılık gelebilir. MMXM ve CISD olay çıktılarında gerçek TF kapanışı ile son M1 indeksi birlikte tutulmalıdır. [OC zamanları](../astra6/fractal_v3.py#L272), [FSM Stage 1–3](../astra6/fractal_v3.py#L412)
- Birden fazla model oluşabilir ve tarayıcı bunları ayrı kimliklerle simüle eder. İşlem eşlemesi en çok 120 yakın olaya ve 1.440 gözleme bakar, yön/terminal kontrolü yapar, yakın ≥8 aşamasında durabilir. `is_active` kullanılmaz. Terminal barı kapsayan koşul başarısız veya geçersiz olayı o bar için döndürebilir. Tek kazanan, iki bağımsız modelin iç içe bağını taşımaz. [As-of çekirdeği](../astra6/fractal_v3.py#L1116)
- V2 `mmxm.py` farklıdır. M5 bant/FVG/displacement tarayıcısı, sinyalde sweep, CRT ve CISD bayraklarından kademeler üretir. V3 faktörü V2 etiketiyle aynı değildir. [V2 MMXM](../astra6/mmxm.py#L31), [V3 faktörü](../astra6/engine_v3.py#L629)

### Durum makinesinin tam geçişi

| Aşama | Gözlenen işlem | Yorum |
|---|---|---|
| 1 | Yalnız daha sonra ayrılışı doğrulanan OC'ye, önceki M1 kapanışında aday yaz | `CAUSALITY_FAILURE` |
| 2–3 | Ayrılış kapanışında hem OC onayı hem ayrılış | Tek ayrılış olayının iki kaydı |
| 4 | Ayrılış kapanışının yönünde 0,15 × bant genişliği ek hareket | Sol taraf için fiyat vekili |
| 5 | Ters renkli mum veya önceki M1 ekstremine göre duraklama | Tek gözlemle ara konsolidasyon |
| 6 | Ara ekstremi test et veya 0,05 × bant genişliği toleransına gir | Gerçek harici likidite seviyesi şartı yok |
| 7 | OC dış sınırından 0,40 × genişlik uzaklaş veya ara ekstremi geç | HTF POI ID/fiyatı/teması yok |
| 8 | Yakın running extreme ve ters renk veya bar aralığının %35'i kadar geri kapanış | Reversal adayı. CRT/SMT/CISD olayı girmez |
| 9–10 | Manipülasyon ekstreminden bant genişliğinin 0,35'i ve 0,20'siyle kurulan kapanış eşiğini geç. İkisini aynı barda yaz | Yerel tersine hareket. Ayrı displacement, CISD, SMT, MSS veya CRT onayı yok |
| 11–12 | Manipülasyon ekstremi ile yakın OC kenarının orta noktasına, sonra yakın kenara dokun | Ask/Bid icrası değil, Bid yapı teması |
| 13 | OC midpoint'e temas | Terminal. FSM'nin yayınladığı `target_price` ise LONG'da OC high, SHORT'ta OC low. Tamamlanma ve yayınlanan hedef aynı fiyat değildir |
| 14 | Onay sonrası manipülasyon ekstremi ihlali veya sağ tarafta zaman aşımı | Stop/teslim aynı barda ise önce başarısızlık |
| 15 | Erken midpoint dönüşü, dış yönde 6 × bant genişliği aşımı veya onay öncesi zaman aşımı | Horizon `min(36 × TF dakika,1440)` kayıtlı M1 gözlemi |

LONG/SHORT eşikleri fiyat ekseninde aynalanmış. Yükseliş/düşüş yönlerinden biri için ayrı dış bilgi koşulu bulunmuyor. İlerleyen M1 döngüsü kendi geçmiş ekstremine bakıyor. Erken aşama geriye yazımı, final terminal indeksinin geçmiş satırlara kopyalanması ve alt resample/OC sınırı bağımsız nedensellik sorunlarıdır. [Yükseliş ve düşüş dalları](../astra6/fractal_v3.py#L464), [terminal yazımı](../astra6/fractal_v3.py#L759)

### Gerçek fiyatla prefix invariance

US100, US500 ve US30 yerel ortak M1 panelinin ilk 17.000 satırını referans aldım. 11 kesitte aynı veriyi baştan `resample → extract_original_consolidations → build_fractal_mmxm_state_events → as-of` akışından geçirdim. Önceden hesaplanmış OC listesi verilmedi. Eşleşmede `oc_id, tf, stage_num, j_m1_known, t_known, direction, event_price, target_price, is_active` ayrı tutuldu. Terminal, revisit ve erişilebilirlik alanları ayrıca karşılaştırıldı.

| Prefix M1 sayısı | Referans/prefix teyitli OC | Geçmişte referans/prefix MMXM satırı | Stage farkı | Ortak olaylarda terminal farkı | Son 80 M1 × 2 yön as-of farkı |
|---:|---:|---:|---:|---:|---:|
| 500 | 10 / 9 | 91 / 85 | 6 | 19 | 1 |
| 884 | 27 / 26 | 257 / 245 | 12 | 7 | 0 |
| 889 | 27 / 26 | 262 / 250 | 12 | 12 | 0 |
| 900 | 27 / 26 | 263 / 251 | 12 | 0 | 0 |
| 1.500 | 46 / 46 | 402 / 402 | 0 | 17 | 0 |
| 2.000 | 63 / 63 | 571 / 570 | 1 | 5 | 53 |
| 2.048 | 65 / 65 | 584 / 581 | 3 | 10 | 44 |
| 4.096 | 128 / 127 | 1.202 / 1.189 | 13 | 26 | 0 |
| 8.192 | 244 / 244 | 2.254 / 2.254 | 0 | 23 | 0 |
| 12.000 | 341 / 341 | 3.162 / 3.162 | 0 | 18 | 0 |
| 16.384 | 466 / 466 | 4.322 / 4.321 | 1 | 6 | 0 |

2.000 satırda `j=1937` LONG sorgusu referansta `MMXM_US100_H4_000000` Stage 1, prefix'te Stage 0 verir. Stage 1 zamanı 9 Kasım 2021 11:00 UTC, gerçek ayrılış onayı 15:00 UTC. 889 satırda H1 modelinin 12 geçmiş satırı kaybolur. H1 kova sayısı eşiği ve son kovanın koşulsuz atılması sonuçları etkiler. 1.500 satırda temel olaylar eşit olduğu halde 17 terminal alanı, 12 revisit sayısı ve 10 erişilebilirlik bayrağı değişir. Terminal zamanını sonradan etiketlemek bir sonuç alanı için olağandır. Canlı as-of sorgusu bu alanı geçmiş özellik olarak yayınlamamalıdır. [Minimum TF bar sayısı](../astra6/fractal_v3.py#L256), [resample](../astra6/bars.py#L153), [join](../astra6/fractal_v3.py#L1116)

50.000 M1'lik ikinci kesitte D1 dahil edildi. D1 üç OC ve 36 aşama üretti. İlk D1 modeli `OC_US100_D1_000000`, 17 Kasım 2021 21:15 UTC geçmiş aday damgası ve 18 Kasım 2021 23:00 UTC teyidi taşıyor. 10.046 barlık aday kapanışı kesitinde referansın bir D1 olayı prefix'te yok. 11.270 barlık teyit kesitinde referanstaki üç D1 olayı yok. 30.000 ve 45.000 kesitlerde D1 olay sayıları sırasıyla 24 ve 36 eşleşti.

## Quarterly Theory, zaman ve fiyat bütünlüğü

- Yerel saniye `s` ile `b = floor((s-anchor)/period)`, `q = b mod 4+1`. `q6` 24 saatin 6 saat dilimleri, `q90` bir 6 saatin 90 dakikaları, `q22` bir 90 dakikanın 22,5 dakikaları, `q5` bir 22,5 dakikanın 337,5 saniyelik alt dilimleridir. NY 18:00 anchor ile Q1 18:00, Q2 19:30, Q3 21:00, Q4 22:30'da başlar. İlk mikro sınır 18:22:30'dur. M1 serisinde açılış damgasıyla ilk yeni mikro bar 18:23. 30s serisinde 18:22:30 kaydı varsa sınır gözlenir. QT etiketi bar açılışına atanır. [`bars.py`](../astra6/bars.py#L184)
- NY 09:30 ve Londra 08:00 kendi IANA bölgelerine dönüştürülür. Ayrı açılış DST testleri geçti. Ayrıca üç anchor'ın her birinde 2026 ilkbahar ve sonbahar DST sınırlarını çevreleyen sekiz tarihte 2.880 adet 30 saniyelik zaman damgası ve dört QT katı bağımsız sayımla eşleşti. Bu kontrol fiyat üretmedi. Bununla birlikte `resample` yerel duvar saati ile gruplayıp kapanışı UTC başlangıca sabit süre ekleyerek üretir. Örneğin NY 18:00 Sunday anchor'dan sonraki W1 yerel sınırı DST değişiminde tam 168 saat olmayabilir. 13 Mart 2022 haftasının kod kapanışı 23:00 UTC, gerçek yerel sınır 22:00 UTC. 6 Kasım 2022 haftasında kod 22:00 UTC, yerel sınır 23:00 UTC. Ambiguous saatler aynı kova anahtarına düşer, dönüşümde ilk gözlemle düzeltilir. Son kova koşulsuz eksik, diğer kovalar kapsama bakılmadan tamamlanmış sayılır. Kayıtlı 7 Kasım 2022 19:00–23:00 UTC H4 kovası 240 yerine 135 gözlemle `complete=True`. Bu, seans boşluğu ve veri kaybını ayırt etmeyen sözleşmedir. [`wall_to_utc`](../astra6/bars.py#L148), [`resample`](../astra6/bars.py#L153)
- Faz etiketi zaman durumudur. Gelişen QT ekstremi `_scan_pair` içinde running max/min. Referans önceki QT kovasının gözlenen tam örneğidir, doluluk kontrolü yoktur. Atomik tabloda ileri invalidation/terminal alanları bulunur. [SSMT taraması](../astra6/smt.py#L102), [atomik arşiv](../astra6/fractal_v3.py#L981)

## CRT, likidite ve SMT/SSMT

- CRT referansı aynı TF'deki önceki gözlenen tamamlanmış kova. SHORT için `H > Hr` sweep, `C <= Hr` reclaim. LONG için `L < Lr` ve `C >= Lr`. Gelişen tetik reclaim veya CRT içi CISD kapanışı. `A` kapanmış mumda tek taraflı süpürme + range içine kapanış. J/K/H farklı varyantlar olarak confirmed havuzuna da girer. M1 `j_sweep`, `j_reclaim`, `j_close` ayrı alanlardır. İşlem zamanı bu M1 barın kapanışıdır. `F` sonraki kapanışı ister. `np.roll` son ve ilk satır sınırları maskelenmeden kullanıldığı için F/H'de sarma riski vardır. [CRT çekirdek](../astra6/crt.py#L63), [varyantlar](../astra6/signals.py#L186), [giriş kipleri](../astra6/signals.py#L233)
- Standart SMT, traded CRT sweep ve aynı referans kovası comparator ekstremine karşı `j_cmp<0 or j_cmp>j_trig`. SSMT ise ayrı QT referanslarıdır. Q1→Q2, Q2→Q3, Q3→Q4, Q4→Q1 ve atlamalı geçişler aynı araştırma akışında bulunur. Macro 90m kova, micro 22,5m. A ya da B yalnız kendi referans tepesini geçerse bearish, dibini geçerse bullish divergence. Diğer taraf aynı M1'de kırarsa tek taraflı event yoktur. Sonraki kırılım `j_inv` olarak işaretlenir. Arama tetik kovasından bir sonraki gözlenen kovaya kadar sürebilir. [`_scan_pair`](../astra6/smt.py#L53), [referans eşlemesi](../astra6/smt.py#L128)
- Ana comparator US500. US30 için ayrı SSMT ve standart SMT alanları vardır. Context US500–US30 çiftini de hesaplar, 64 politikaya taşınan macro/micro ana bitleri US100–US500'dür. Tüm altı stream kesişiminden gelen panel comparator yokken traded gözlemi de düşürür. `Missing_Comparison_Data` araştırma etiketini gerçek eksik bar olaylarıyla karıştırmamak gerekir. `build_context` hiç comparator yoksa ilk elemana erişir. Aynı yönde birden çok olay `attach_ssmt` tarafından korunur. Ters macro ayrıca aranır, bitler her politika tetiğinde yeniden geçerlilik kontrolü yapmaz. [`signals.build_context`](../astra6/signals.py#L96), [`materialize_entries`](../astra6/signals.py#L305), [`attach_ssmt`](../astra6/smt.py#L187)
- Likidite tablosu yalnız `cal` anchor CRT satırlarından gelir. OC argümanı kullanılmaz. Çıktıda 1.142.491 satır ve beş tür var. `Accepted_Breakout`, `Failed_Breakout`, `Reclaim`, `Rejection`, `Sweep`. Opening-range seviyeleri adaylara ayrı eklenir. `PDH/PDL/PWH/PWL` bayrakları as-of seviyeye karşı aday ekstrem kıyasından gelir. Bir seviyenin daha önce tüketilip tüketilmediğini, gerçek OB/FVG POI'sini ve olay sırasını kanıtlayan bağ yoktur. [Dönem sweep](../astra6/signals.py#L347), [likidite olayları](../astra6/fractal_v3.py#L878)
- Üç mum FVG tanımı `L[i] > H[i-2]` veya `H[i] < L[i-2]`. `ict.fvg_table` bağımsız genel yardımcıdır ve V3 FSM'ye bağlanmaz. CRT displacement buna ek olarak ortadaki gövdenin 1,2 × M1 ATR'yi geçmesini ister. IFVG, FPFVG ve bağımsız MSS/CHOCH ile bağlı HTF POI dizisi için V3 üretim yolu bulunmadı. [FVG](../astra6/ict.py#L101), [CRT displacement](../astra6/crt.py#L124)

İlk 17.000 gerçek M1 gözleminde her comparator ve QT katı için tarihe yayılmış 24 SSMT kaydını, önceki QT ekstremi ve güncel kümülatif ekstrem XOR koşuluyla yeniden hesapladım. US500/US30 × macro/micro toplam 96 form ve invalidation indeksi eşleşti. Örnekler mevcut eşleşme kuralını doğrular. Eksik blokla davranış ve faktörün daha sonra yeniden tetiklenen emir anında etkin olması ayrı sorunlardır.

## Bağımsız CISD

Aynı V1 matematiği her TF'nin kendi Bid mumlarına uygulanır. Bearish durumda yukarı kapanan teslimat dizisinin ilk açılışı `ref_open`. Düşüş mumu hem `close < ref_open` hem `close < open` olursa onay. Bullish aynası `close > ref_open` ve `close > open`. Daha sonraki TF barı ekstremi aşarsa 24 sonraki bara kadar invalidation kaydedilebilir. V2 bir duraklama ve `body >= 0,35 ATR` ister. V3 ana tabloları V1'dir. [Çekirdek](../astra6/cisd.py#L34), [seri üretimi](../astra6/cisd.py#L162)

| TF | Onay zamanı ve ilk icra | Bağlam yaşı / sweep sonrası bekleme üst sınırı, M1 gözlemi |
|---|---|---:|
| M1 | M1 `open+1m`, ilk sonraki M1 açılışı | 30 / 20 |
| M3 | M3 nominal kova kapanışı, ilk sonraki M1 açılışı | 45 / 30 |
| M5 | M5 nominal kova kapanışı, ilk sonraki M1 açılışı | 60 / 45 |
| M15 | M15 nominal kova kapanışı, ilk sonraki M1 açılışı | 120 / 90 |
| M30 | M30 nominal kova kapanışı, ilk sonraki M1 açılışı | 240 / 150 |
| H1 | H1 nominal kova kapanışı, ilk sonraki M1 açılışı | 360 / 240 |
| H4 | H4 nominal kova kapanışı, ilk sonraki M1 açılışı | 960 / 480 |

İlk 17.000 M1 üzerinde, bağımsız OHLC agregasyonu ve yönü aynalanmış ayrı V1 referansı, her iki yönde teyit zamanı, ref open, kıran kapanış ve ekstremi eşledi. Olay sayıları M1 2.348, M3 824, M5 535, M15 176, M30 91, H1 43 ve H4 14. Bu kontrol gap/DST civarı, V2 veya bütün piyasa evrenine genellenmez.

As-of yaş filtresi `min(sweep-5, trigger-max_age)` kullanır. Bu, tablo yaşını katı üst sınır yapmaz. İleri eşleme ilk aynı yönlü teyidi alır, 64 olaylık arama sınırı vardır. Adayın likidite stopunun, ters olayın veya hedefin beklerken vurulmasını denetlemez. Bar farkı dakika adıyla saklanır. M15 politika çıktısında 9 satır var olan reclaim’den önce tetiklendi, 26.150 satır reclaim indeksi taşımıyor. Bu deneyin uygulanan kuralı ilk aynı yönlü post-sweep CISD. Reclaim şartlı bir anlatı bu sonuçları doğrudan kullanamaz. M1'de CRT içi ve standalone zamanlar birleştirilir, erken CRT seçildiğinde `post_cisd_ext_m1` aynı kaynağa güncellenmez. M5/M15 gibi ayrı politikalar o TF onayıyla farklı emir oluşturur. Genel 64-bit CISD şartı ise herhangi bir as-of TF bayrağıyla geçebilir ve yalnız CRT/M1 indeksini bekler. [Eşleme](../astra6/cisd.py#L227), [yaş ve bekleme](../astra6/cisd.py#L302), [M1 birleşimi](../astra6/cisd.py#L385), [64-bit](../astra6/engine_v3.py#L619)

## V3.4 adlandırılmış anlatılar

| Anlatı | Gerçek maskede aranan | Eksik zorunlu kanıt |
|---|---|---|
| 1 · M5 bullish MMXM → M1/M5 CISD → H1 BSL | LONG, `mmxm_tf=M5`, `has_mmxm`, `entry_tf in M1/M5`, `H1_LIQ`. 28.969 satır. | M5 orijin/sweep, teyitli MMXM dönüş aşaması, MMXM sonrası bağımsız CISD event ID ve fill sırası. 2.023 satırda herhangi bir CISD bayrağı dahi yok. H1 geçmiş mum tepesi var, gerçek korunmuş BSL seçimi kanıtı yok. [Maske](../astra6/fractal_narrative_v34.py#L64) |
| 2 · H1 sell-side sweep → H1 bullish reversal → M5 MMXM → M15 CISD → M5 OC | LONG, `narrative_tf=H1`, genel `REVERSAL`, `M5_OC`. 5.995 satır. | H1 SSL sweep ID ve zamanı, bağımsız H1 reversal, M5 MMXM yön/aşama, bağımsız M15 CISD, sıranın tümü ve OC model bağı. Sadece 246 satırda giriş etiketi M15, kalan 5.749 başka TF. [Maske](../astra6/fractal_narrative_v34.py#L92) |
| 3 · H4 bearish → M15 correction → M5 bearish CISD → Daily SSL | SHORT, `narrative_tf in H4/H1`, `D1_LIQ`. 22.665 satır. | H4 bearish kanıtı, M15 düzeltme olayı, bağımsız M5 CISD ve zaman sırası. 17.412 satır H1, 5.253 H4. H4 satırlarının 5.138'i M1, 115'i H4 giriş etiketi taşır ve hiçbiri M5 etiketli değildir. Daily low bir önceki D1 mumundan gelir. [Maske](../astra6/fractal_narrative_v34.py#L119) |
| Daily bullish → M5 → Weekly BSL | D1 CRT adayları ve W1 hedef türü hesaplanabilir. | Bu zinciri zorunlu olaylar ve teyit zamanlarıyla test eden V3.4 maske bulunmadı. [D1/W1 ek adayları](../astra6/engine_v3.py#L585), [W1 hedefi](../astra6/fractal_v3.py#L1515) |

Üç V3.4 satırı için durum `SEMANTIC_MISMATCH`. Bunlar var olan yapısal hedef sonuçlarının gruplarıdır. Gözlenebilir anlatıyı sınamak için asgari sözleşme yön, seviye ID, TF, olay ID, `observed_at`, `available_at`, `invalidated_at` ve yürütme anından oluşur. Her olay arasında zorunlu kronolojik ilişki tanımlanmalıdır.

## Excel metodoloji referansı

`Trade_Log` başlığı 4. satırda, 67 sütun. 18 kayıt satırı 5–22. `AR5:AR22` değerlerinden 13 kazanç, 5 kayıp, toplam +52,78R, ortalama +2,9322R, %72,22. 15 NAS100, 3 SPX500. Seans **etiketleri** 16 NY AM ve 2 NY PM. 12:15 etiketli NY AM satırı ve tarih-seri biçiminde okunan F20:F22 nedeniyle etiketler gerçek 09:30–11:30 aralığına doğrudan eşitlenemez. `AM6:AN6` Trade ID 2, 2 Ocak 2020 SPX500 SHORT, 3246,20 / 3246,20 sıfır risk ve manuel +2,90R. Trade ID 14 farklı bir NAS100 kaydıdır. V3.4 checkpoint'in Trade #14 ve 16120 değeri dosyayla uyuşmaz. [Excel](../Copy%20of%20EXCEL_TEST.xlsx), [checkpoint](../data/results/v3_4_checkpoint.json)

Jurnal ayrık alanlarda HTF DOL ve PD array, QT fazı ve teyidi, FVG/FPFVG, SMT/SSMT, sweep tarafı/TF, CISD, displacement, MSS/CHOCH, emir, stop, hedef ve exit reason taşır. Bunlar araştırmanın semantik sözleşmesi için yararlı insan etiketleridir. Realized R giriş değeri, Outcome ve Cumulative R formüldür. Seçilmiş 2019–2020 örnekleri, 2021–2026 fiyat döneminden ayrı ve küçük bir gruptur. Workbook metrikleri otomasyonun net R veya forward doğrulaması olarak kullanılamaz.
