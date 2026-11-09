# ASTRA 6 V3.4 sonuç uzlaştırması

**Aşama 5–6 kontrol noktası** Dört model satırlarından yeniden hesaplandı. İki yapısal modelin tüm stop ve hedef fiyatları ve hedefin ilk bilinebilir zamanı karşılaştırıldı. Tek olayda dört politika kayıtlı fiyatlardan yürütüldü.

## Yöntem ve kanıt kapsamı

- Sorgular yerel Parquet dosyalarını doğrudan okudu. Model 1, 2 ve 4 için `target_outcomes` ile `target_candidates` tekil `target_candidate_id` üzerinden eşlendi. Model 3 için `counterfactual_policy_trades` kullanıldı. Yayımlanmış özet sayıları hesaplara girmedi. [Üretimdeki maskeler](../astra6/audit_v34_models.py#L118)
- `win = count(R>0)/N`, `PF = sum(R>0)/abs(sum(R<0))`, beklenti aritmetik ortalama. En büyük düşüşü çıkış barı sırasına göre, eşit çıkışlarda sinyal zamanı ve ID ile, 0R başlangıç zirvesi dahil hesapladım. Tüm aynı bar çıkışlarını tek toplu hareket saymak dört yuvarlanmış değeri değiştirmedi. Bu, sabit 1R satır muhasebesidir. Mark-to-market portföy veya tahsis simülasyonu yoktur.
- Gün kümelerinde `u_g = sum(R_g) - n_g × mean(R)`. `SE = sqrt(G/(G-1) × sum(u_g²)/N²)`. Bir yönlü `p=P(Z>=mean/SE)`, aynı günlerden ağırlıklı 300 bootstrap çekilişi, seed 42. Hassasiyet için 10.000 bağımsız gün bootstrap çekilişi ve (t_{G-1}) kontrolü. Holm ve BH dört rapor modeli üzerinde tam hassasiyetle hesaplandı. Üretim p'yi önce altı haneye yuvarladığı için çok küçük p'yi 0 kaydeder. [Üretim formülü](../astra6/hpc.py#L591), [düzeltmeler](../astra6/audit_v34_models.py#L258)
- Her modelde tarihe yayılmış sekiz kaydın giriş kotasyonu ve gerçek Bid/Ask yolundan çıkış barı, kodu, fiyatı ve net R bağımsız tekrarlandı. 32/32 eşleşti. Bu örneklerde depodaki stop/hedef önce sabit girdi alındı. Model 1/2 için ayrı kontrolde tüm 1.117 satırın hedef kaynağı ve stop fiyatı baştan çözüldü. Beş yıllık motor veya tüm işlem çıkış yolları baştan çalıştırılmadı.

## Dört iddia ve yeniden hesaplama

| Model ve gerçek popülasyon | Satır / fırsat / UEV / gün | Kazanç | Ortalama R | PF | Toplam R | Düşüş R, kronolojik |
|---|---:|---:|---:|---:|---:|---:|
| 1 · H1 etiketi, M5 giriş etiketi, M15_LIQ LONG | 325 / 325 / 325 / 283 | %82,15 | +0,82789 | 5,6270 | +269,06 | 3,37 |
| 2 · H1 etiketi, M15 giriş etiketi, M5_OC SHORT | 792 / 792 / 792 / 586 | %44,57 | +0,18931 | 1,3424 | +149,93 | 20,48 |
| 3 · CFG64_57, temel sinyal NY 09:30–11:00, sabit 2R | 658 / 658 / 658 / 305 | %37,69 | +0,07152 | 1,1143 | +47,06 | 36,02 |
| 4 · Aktif 4–12 MMXM × 90M Q2 × LONG × genel reversal, yapısal hedef satırları | 96.803 / 13.397 / 10.212 / 1.250 | %28,60 | −0,18079 | 0,7482 | −17.500,76 | 17.680,60 |

Yayımlanan Model 4 PF **0,6729** ve JSON **0,7482**. Bağımsız hesap JSON ile eşleşti. JSON Model 3/4 düşüşü 37,03R / 17.505,25R. Üretim `np.cumsum` öncesi kronolojik sıralama yapmaz. Model 4'te tablolar hedef türü bloklarıyla birleşir. Kronolojik fark bir sayısal tolerans farkı değildir. [Model tablosu](ASTRA6_V3_4_FINAL_VALIDATION.md#L111), [üretim düşüşü](../astra6/engine_v3.py#L153), [hedef birleştirmesi](../astra6/fractal_v3.py#L1665)

| Model | Küme SE | %95 GA, 300 | %95 GA, 10.000 | Ham p | Holm | BH | Tarihsel OOS N / gün / ort. R / yaklaşık %95 GA |
|---|---:|---|---|---:|---:|---:|---|
| 1 | 0,06568 | [0,71279, 0,96007] | [0,70105, 0,95819] | 9,90e−37 | 3,96e−36 | 3,96e−36 | 92 / 81 / +0,89557 / [0,6535, 1,1376] |
| 2 | 0,06143 | [0,05593, 0,30301] | [0,06952, 0,31229] | 0,001030 | 0,003089 | 0,002059 | 206 / 149 / +0,29128 / [0,0600, 0,5226] |
| 3 | 0,07122 | [−0,05414, 0,20731] | [−0,06562, 0,20678] | 0,157649 | 0,315298 | 0,210199 | 232 / 98 / +0,09350 / [−0,1398, 0,3268] |
| 4 | 0,02506 | [−0,22592, −0,12693] | [−0,22996, −0,12927] | ≈1,000000 | ≈1,000000 | ≈1,000000 | 27.437 / 341 / −0,08955 / [−0,1964, 0,0173] |

OOS GA `mean ± 1,96 × day-cluster SE`. Testin yönü **pozitif ortalama**. Model 4'ün p≈1 değeri bu yönde kanıt bulunmadığını anlatır. Model 4 negatif tarihsel ortalaması, terminal Stage 13 hipotezinin testi değildir.

| Model | TRAIN_DEV N / R | VALIDATION N / R | TP / SL / iki temas / timeout / veri sonu | Ek 0,50 puan sabit maliyetle R |
|---|---:|---:|---|---:|
| 1 | 175 / +0,80935 | 58 / +0,77647 | 266 / 56 / 1 / 2 / 0 | +0,80907 |
| 2 | 420 / +0,11401 | 166 / +0,25328 | 343 / 426 / 1 / 22 / 0 | +0,16315 |
| 3 | 342 / +0,01253 | 84 / +0,25098 | 222 / 402 / 2 / 32 / 0 | +0,04746 |
| 4 | 51.116 / −0,24167 | 18.250 / −0,14744 | 20.767 / 68.037 / 166 / 7.827 / 6 | −0,20858 |

Ek maliyet yalnız mevcut net R'den `0,50 / risk` düşer. Yeniden teklif, latency, gap ve tetik davranışına karşı stres testi sayılmaz. Geometri bakımından dört grupta yanlış tarafta **kaydedilmiş** stop yok. Yürütücü, yanlış tarafta hesaplanan ön stopu mutlak mesafe alarak karşı tarafa taşıyabildiği için bu kontrol tek başına yeterli değildir. Tüm tablolarda `direction × (exit_px-entry_px) / risk − 0,25/risk` yayımlanan R ile 4e−15 altında fark verdi. Giriş fiyatında ayrıca 0,25 puan slippage ve karşı Bid/Ask kotasyonu vardır.

### Model 1 ve 2'nin hedef erişilebilirliği

**Sonuç `CAUSALITY_FAILURE`.** Hedef seviyesi orijinal aday zamanındaki bağlamdan hesaplanır. Ortak politika adayı daha erken bir bara yeniden zamanlayabilir. `build_cross_timeframe_targets_and_outcomes` eski bağlam hedefini yeni girişle yürütür ve bütün satırlara `known_before_entry=True` yazar. Yapısal senaryo hedefleri arasındaki seçim, yeni giriş fiyatına göre uzaklık filtresinden de geçer. [Bağlam sırası](../astra6/engine_v3.py#L610), [yeniden tetik](../astra6/engine_v3.py#L637), [hedef bayrağı](../astra6/fractal_v3.py#L1627)

1. Model 1'in **200/325** hedefi, teyit ve fiilî dolumdan sonra kapanmış M15 mumunun tepesidir. Kaynak H1 `confirmed` satırı UEV ile eşleştirildi. Önceki M15 yüksekliği mevcut Bid serisinden orijinal bilgi anına göre yeniden hesaplandı. 325/325 hedef ve stop fiyatı eşleşti. `OPP_US100_H1_confirmed_10894_L` 18 Kasım 2021 **14:47 UTC**'de doluyor. TP 16423,399, **15:00 UTC** kapanışlı M15 barından. `A=False` olan 245 satır, sweep indeksi bulunmayan 44 satır var. 203 satır 0,75–1,50R hedef bandı dışında. 18 çıkış 60 bardan sonra. Kodda ters M15 CISD çıkışı, 60 dakika sınırı ve playbook'un giriş seans/evre/SSMT koşulları yok. Stop, V2 aday sweep stopu ile yeni tetik mumunun 0,15 ATR tamponlu ekstreminden geniş olanı alır, bağımsız swing-low şartı yoktur. [Model 1 maskesi](../astra6/audit_v34_models.py#L134), [playbook ve final çıkış](ASTRA6_V3_4_FINAL_VALIDATION.md#L215), [stop](../astra6/fractal_v3.py#L1744)
2. Model 2'nin **18/792** OC'si, fiilî dolumdan sonra teyit edilmiştir. Eski tetik anında aynı yön ve fiyat tarafında, geçersizleşmemiş son 50 OC içinden seçim yapıldı. Yerel OC arşivi ile 792/792 hedef, V2 stop ve yeni tetik barı ile 792/792 stop yeniden eşleşti. 356 emir temel H1 onayından önce, 62 satır sweep indeksi olmadan ve 497 satır CRT-A olmadan çalıştı. `OPP_US100_H1_confirmed_6986_S` 15 Kasım 2021 **09:02 UTC** dolumunda, **10:00 UTC**'de teyit edilecek `OC_US100_M5_000135` midpoint 16219,269'u kullanır. 141 çıkış 120 bar sonrasında. 428 hedef 1,50R altında. Gerçek geçmiş M5 OC kaydı vardır ancak maske bir H1 dönüş olayı, bağımsız M15 kapanış sırası veya ilgili MMXM modelinin başladığı OC bağını şart koşmaz. [Model 2 maskesi](../astra6/audit_v34_models.py#L161), [OC seçimi](../astra6/fractal_v3.py#L1284), [playbook](V3_4_STRATEGY_PLAYBOOKS.md#L47)

Model 1 ve 2 için yayımlanan **rakamlar yeniden üretildi**, strateji **`NOT_VERIFIED`**. Bu popülasyonlardan geç teyitli hedefleri sonradan çıkarmak, aynı playbook'u nedensel olarak yeniden yürütmüş sayılmaz. Model 2'nin yapısal hedefi sabit 2R'den üstün sayan cümlesi, aynı olay/giriş/stop üzerinde eşli hedef kıyasını sunmaz. [Sabit sonuç](../astra6/audit_v34_models.py#L279)

### Model 3 ve Model 4'ün yeniden adlandırılması

- **Model 3 — `EXPLORATORY_POSITIVE`, `STATISTICAL_EVIDENCE_INSUFFICIENT`.** CFG64_57 bitleri CRT + Macro + Micro + MMXM, CISD ve StdSMT devre dışı. 658 satırın yalnız 398'i M5 kaynaklı, 129 M15 ve 131 diğer TF. 144 dolum gerçek NY 09:30–10:59 dışında. 230 satırda bir önceki herhangi bir işlem henüz kapanmadan yeni dolum gerçekleşir. SHORT 363 işlemde +0,13590R, LONG 295 işlemde −0,00770R. JSON karar ağacı `n>=30`, `days>=15`, pozitif mean/OOS ve `OOS_N>=15` ile destek etiketini verir. p, CI, nedensellik ve bağımsız gelecek verisi şart değildir. PDF'nin keşif statüsü kanıta daha yakın. [Karar](../astra6/audit_v34_models.py#L74), [model maskesi](../astra6/audit_v34_models.py#L188)
- **Model 4 — geniş hedef havuzu `NEGATIVE_EXPECTANCY`, terminal stratejisi `NOT_VERIFIED`.** Geniş maske 4–12 aşamalarını içerir, 11/12 toplamı 40.376 hedef satırıdır. Stage 13 yok. 96.803 sayısı işlem portföyü değil, 13.397 fırsat ve 10.212 UEV üzerinde hedef alternatifleridir. Stage 13 + Q2 + LONG + REVERSAL için `all_trades` sabit 2R havuzunda 42 satır, +0,365108R, tarihsel OOS −0,003985R yeniden bulundu. Aynı Stage 13 filtresi hedef havuzuna uygulanırsa 266 hedef değerlendirmesi, +0,810034R ve OOS −0,380329R verir. Ayrı popülasyonlardır. PDF'nin ilk sonuçla geniş havuzu aynı tamamlanma hipotezinin önce/sonra testi diye karşılaştırması geçersizdir. [Geniş seçim ve fallback](../astra6/audit_v34_models.py#L225)
- **Fallback — `CONFIRMED_BUG`, yüksek önem.** Boş hedef seçimi tetikler. Stage 12 veya 13 + Q2 + LONG + REVERSAL bulunan mevcut aday tablosunda bu yol 3.727 satırın her birine yapay +0,3651R atardı. Geçerli V3.4 koşusunda ana maske 96.803 olduğundan devreye girmedi. Eski +0,3651R metrik mevcut 42 adet sabit-2R satırından yeniden bulunabiliyor. İncelenen artefaktlarda fallback'in geçmiş bir rapora sayısal kaynak olduğu gösterilmedi. Sıfır adayda `compute_model_metrics` kısmi dict döndürdüğü için sonraki alan erişimi hata da verebilir. [Fallback ataması](../astra6/audit_v34_models.py#L231)

## UEV_US100_M5_884_S · ham fiyat replay

8 Kasım 2021 UTC. Kayıtlı panelin ilk 1.300 M1 gözleminden CRT ve CISD olaylarını yeniden çıkardım. Bağımsız M5 gruplaması ve M1 eşitsizlikleri sweep/reclaim barlarını doğruladı. Ayrı V1 hesap M1/M3/M5/M15 kapanışlarını ve referans fiyatlarını eşledi. Önceki M5 high 16383,749, sweep barı 884 (o barın Bid high'ı 16393,059), tüm M5 penceresinin gözlenen ekstremi 16401,809. Reclaim 887. H1 dışarıdan filtre olarak kullanılmadı. M5 ATR(14) 11,194562924. V2 kaynak stopu `16401,809 + 1,50 = 16403,309`. Olay kimliğinin 884 kısmı M5 kovasının ilk M1 indeksidir. Bu örnekte ilk sweep de aynı bardadır. Bütün aşağıdaki girişler **SHORT** ve 2R'dir. [CRT kaynak penceresi](../astra6/signals.py#L134), [V2 stop](../astra6/engine.py#L31), [V3 stop ve giriş](../astra6/fractal_v3.py#L1736)

| Politika | Onay bar / UTC kapanış | Fill bar / UTC açılış | Açılış Bid / Ask | İcra girişi | Stop | Hedef | Çıkış bar / UTC bar açılışı | Çıkış kotasyonu | Net R |
|---|---|---|---:|---:|---:|---:|---|---:|---:|
| 00_No_CISD | 887 / 14:39 | 888 / 14:39 | 16379,079 / 16380,481 | 16378,829 | 16403,309 | 16329,869 | 902 / 14:53, TP | 16329,869 | +1,989788 |
| 01_M1_CISD · CRT içi | 888 / 14:40 | 889 / 14:40 | 16366,379 / 16367,821 | 16366,129 | 16403,309 | 16291,769 | 1249 / 20:40, TIMEOUT | 16351,131 | +0,396665 |
| 03_M5_CISD | 903 / 14:55 | 904 / 14:55 | 16341,719 / 16343,251 | 16341,469 | 16403,309 | 16217,789 | 1264 / 20:55, TIMEOUT | 16343,741 | −0,040783 |
| 04_M15_CISD | 908 / 15:00 | 909 / 15:00 | 16346,489 / 16347,761 | 16346,239 | 16403,309 | 16232,099 | 1269 / 21:00, TIMEOUT | 16331,751 | +0,249483 |
| Ayrı M1 V1 tarayıcısı | 901 / 14:53 | 902 / 14:53 | 16343,077 / 16344,331 | 16342,827 | 16403,309 | 16221,863 | 1262 / 20:53, TIMEOUT | 16343,231 | −0,010813 |

TIMEOUT kotasyonu satırdaki M1 **kapanışında** alınır. TP satırında dakikanın içindeki kesin işlem saniyesi M1 OHLC'den bilinemez. Çıkış kotasyonu sütunu çıkış slippage'ı öncesidir. Basit bağımsız döngü fill barından `fill+360` dahil tarar, SHORT için Ask high stop, Ask low TP, iki temas varsa stop, temassızsa son Ask close. Giriş Bid−0,25. `R=(entry−exit−0,25)/abs(entry−stop)`. Dört üretim satırı ve bağımsız M1 V1 deneyi için Python döngüsü ile üretim Numba kodu, barı, fiyatı ve R'yi tolerans içinde eşledi. [Numba](../astra6/hpc.py#L375)

- M5 V1 ref open 16355,689, kıran kapanış 16341,409. M15 V1 ref open 16350,079, kıran kapanış 16346,297. Standalone M1 ilk sweep sonrası bearish ref open 16352,799, kıran kapanış 16343,039. M1 politikası daha erken CRT içi olaya `cisd.py:385–398` ile geçer. `CFG64_32` (yalnız CRT) ve `CFG64_34` (CRT+CISD) bu örnekte aynı bar 888 sonucunu verir. 64-bit etiket ve MTF politika etiketi farklı sözleşmelerdir.
- `multitf_cisd_policy_trades` dört kayıt için **hep 1249** çıkış indeksini taşır. `hold`, fiyat ve R yeni yürütmeden, `j_exit` eski adaydan. Örnekte No-CISD gerçek çıkışı 902, M5 1264, M15 1269. Tüm MTF tabloda **1.343.233** satırda `j_exit<j_fill`, `hold=1` özel kodlaması dışarıda bırakılınca **1.939.942** satırda `j_exit ≠ j_fill + hold`. `execute_strategy_at_custom_triggers` hesapladığı `exit_j` alanını döndürmelidir. [Atama bloğu](../astra6/fractal_v3.py#L1793)
- `counterfactual_policy_trades.t_confirm` bar **açılışıdır**, gerçek teyit kapanıştan okunur. Örneğin CFG64_00 için 14:38 UTC yazılır, reclaim bilgisi 14:39 UTC'de mevcuttur. Çıkış zamanı aynı biçimde bar açılışıdır. Tabloda 10.224 satırda kayıtlı confirm-open ile fill-open farkı >5 dakika. `engine._sim_df` V2'de böyle boşlukları eler, V3 aynı kuralı uygulamaz. [CF zamanları](../astra6/engine_v3.py#L994), [V2 gap filtresi](../astra6/engine.py#L89)

## Finding A/B · SVG, JSON ve PDF

A **`CONFIRMED_BUG`**. `build_trade_replays` gerçek paneli yükler, OHLC dizilerini alır ve kullanmadan bırakır. 45 mumluk yol, trade entry–exit doğrusal drift ve seed 42'li uniform gürültüyle üretilir. `generate_svg_chart` bu OHLC'yi çizer. Yirmi SVG'nin her birinde 45 fitil var ve başlık/fiyatlar JSON ile uyumlu. Sabit seed ile yalnız Parquet satır seçimini tekrar ettim. 20/20 JSON ID eşleşti. Replay 01 kaynak hedef ID `TC_OPP_US100_M30_dev_cisd_1165989_L_H4_LIQ`, ham net R +5,759292409. Görsellerin kanıt statüsü **illüstrasyon**. Kazanç/kayıp/timeout sayıları Parquet örneklerinden gelir. Winner/loser/timeout CISD/exit saatleri, SMT ve birçok MMXM etiketi sabit. Üç missed-entry satırı yalnız `f_cisd & dev_cisd` örneklenip geçersiz ilan edilir, fiyat yolunda stop ihlali aranmaz. [Panel ve seçim](../astra6/trade_replay_v34.py#L118), [örnek etiketler](../astra6/trade_replay_v34.py#L181), [missed](../astra6/trade_replay_v34.py#L220), [SVG yolu](../astra6/trade_replay_v34.py#L280)

B **`CONFIRMED_BUG`**. Dokuz sayfalık mevcut PDF'nin 8. sayfasında 20 Markdown tablo ID'sinin tamamı metinde bulundu. PDF ve Markdown Replay 01 satırı `OPP_US100_M5_884_S`, SHORT, entry 16378,83, stop 16403,31, target 16329,87, +1,9898R. Rakamlar aynı sayfalardaki CFG64_00/No-CISD örneğine ve fiyat replay'ine uyar. JSON/SVG Replay 01 `OPP_US100_M30_dev_cisd_1165989_L`, LONG, 21183,51 / 21168,64 / 21269,40, +5,76R. 20/20 PDF/Markdown ID'si aynı sıra numarasındaki JSON ID'sinden farklı. PDF'nin tablosu Markdown'a önceden yazılmıştır. İlk satırın sayısal kökeni eşleşmeyle bulunabildi. PDF ID'lerini UEV biçimine çevirince yerel CF tablosunda yalnız 01 ve 09 bulundu. Replay 09 CF girişi 16359,363 iken PDF 18100,50 yazıyor. Kalan satırların sayısal kaynağı dosyada belirlenemedi. [Markdown satırı](ASTRA6_V3_4_FINAL_VALIDATION.md#L252), [JSON](../data/results/v3_4_trade_replays.json), [SVG](figures/trade_replays/replay_01.svg), [PDF oluşturucu](../build_v34_report.py#L267)

## Finding C–G ve istatistiksel yorum

| Bulgu | Karar |
|---|---|
| C · Model 4 sabit fallback | Ulaşılabilir ve sahte sonuç yaratır. Mevcut rapor ana maskesinin boş olmadığı kanıtlandı. |
| D · Model 3 statü | JSON ve PDF ayrı. JSON'un pozitif mean/OOS kuralı p veya GA şart koşmaz. Keşifsel pozitif ve yetersiz inferans. |
| E · Eski metin | `audit_v34_models.py:274–292` sabit sayılar yazar. M3 metin +0,1343/−0,0065 ve SE 0,066 iken satırlar +0,13590/−0,00770 ve SE 0,07122. M4 metin 42/−0,0040 ve `INSUFFICIENT_DATA` iken güncel audit geniş 96.803/−0,08955 ve negatif. PDF M4 PF ayrı hatalı. `build_v34_report` bu farkları uzlaştırmaz. |
| F · Narrative | Üç arşiv grubunun yeniden hesaplanan (N, ort. R, PF) değerleri (28.969, −0,25170, 0,6471), (5.995, −0,18508, 0,6852), (22.665, −0,19259, 0,7511). Üç tam olay zinciri test edilmemiştir. [Olay matrisi](ASTRA6_TRADING_LOGIC_SEMANTICS.md#v34-adlandırılmış-anlatılar) |
| G · Veri | İstenen tüm büyük tablolar yerelde mevcut. Git'in dışladığı dosyalar remote checkout'la taşınmıyor. Bu yerel denetimde dört model için `ARTIFACT_UNAVAILABLE` gerekmedi. |

| Yıl, NY sinyal/dolum tarihi | M1 N / R | M2 N / R | M3 N / R | M4 N / R |
|---|---:|---:|---:|---:|
| 2021 | 10 / +0,540 | 22 / +0,231 | 18 / +0,383 | 3.109 / −0,118 |
| 2022 | 86 / +0,748 | 160 / +0,306 | 110 / +0,098 | 21.145 / −0,240 |
| 2023 | 52 / +0,709 | 164 / −0,017 | 157 / −0,119 | 17.971 / −0,236 |
| 2024 | 53 / +1,049 | 162 / +0,084 | 102 / +0,243 | 17.825 / −0,240 |
| 2025 | 63 / +0,862 | 167 / +0,206 | 120 / +0,206 | 18.932 / −0,085 |
| 2026 | 61 / +0,860 | 117 / +0,433 | 151 / −0,009 | 17.821 / −0,108 |

OOS, **1 Temmuz 2025 UTC** sınırından sonraki tarihsel etikettir. V1/V2 `yearly_perf` ve `splits_eval` Git geçmişinde, V3/V3.3 bu dönem üzerinden sıralama ve anlatı seçmiştir. V3.3 metni ayrıca Kasım 2025 sınırı yazar. V3.4 motoru Temmuz 2025 kullanır. Tarihsel test aralığı geliştirme sürecinde incelenmiştir. V4 handoff ilk 10 ranking satırını donduran dosyadır. Yeni forward gerçekleşmeleri ve tam yürütülebilir sabitlenmiş politika kimliği yoktur. [Split](../astra6/engine_v3.py#L246), [V3.3 metni](V3_3_STATISTICAL_VALIDATION.md#L49), [handoff](../astra6/engine_v3.py#L1943)

Dört p'nin düzeltilmesi, önceki sürümlerle birlikte aranan 64 × yön × seans, 15 aile, hedef/TF matrisi ve 25 sıralamanın seçim yanlılığını karşılamaz. Gün kümesi aynı günün tekrarını hesaba katar. Günler arası taşınan risk, üst üste hedefler ve alternatif emirler sürer. `strategy_ablation_results` aynı UEV'nin ON/OFF yürütmesine değil, ortak aday havuzundaki ayrı faktör gruplarına ve ortak gün ortalamalarına bakar. V2 walk-forward 12/6 ay seçimi yapar, V3.4'ün dört sabit playbook'u için bağımsız WFA değildir. V2 maliyet duyarlılığı ayrı rerun yapabilir, V3 robustness ek slippage'ı R'den düşer. [Sıralama](../astra6/engine_v3.py#L284), [ablation](../astra6/engine_v3.py#L1587), [V2 WFA](../astra6/stats.py#L261), [V3 maliyet](../astra6/engine_v3.py#L1847)

## Yürütme sınırları ve yeniden üretim

| Gerçek fiyat kontrolü | Kimlik | Bağımsız döngü ve Numba |
|---|---|---|
| LONG aynı bar stop + TP | `CFG64_00_UEV_US100_M5_3763_L` | Fill ve exit 3768, stop 15905,576453, −1,035845R. |
| SHORT aynı bar stop + TP | `CFG64_01_UEV_US100_M5_13376_S` | Fill ve exit 13381, stop 16733,716965, −1,078915R. |
| LONG data-end | `CFG64_00_UEV_US100_M30_1677461_L` | Exit 1677730 Bid close 26997,5335, −0,413191R. |
| SHORT data-end | `CFG64_00_UEV_US100_H4_1677311_S` | Exit 1677730 Ask close 26998,9725, +0,522808R. |
| Seans boşluğuna taşan fill | `CFG64_00_UEV_US100_M15_15064_S` | Teyit 23 Kasım 2021 21:15 UTC, dolum 23:00 UTC. CF emri bekletiyor, V2'nin 5 dakika filtresi burada çalışmıyor. |

`hpc.fast_target_exec_full_numba` stop/target için fill ve son barı dahil eder. `jf+360 == n−1` durumunda tam horizon olmasına rağmen DATA_END sınıfı seçilir. Ayrıca stop sonrası ilk hedef teması izlenir. `reached_only_after_stop = reached_any & ~reached_clean` iki seviyenin aynı barda dokunduğu belirsiz durumları da kapsar, kesin “sonra” ölçümü değildir. V2 `sim.sim_batch` stop/TP fiyatında slippage'ı düşülmüş çıkış fiyatı yazar, V3 ham çıkış kotasyonunu saklayıp maliyeti R'den düşer. [Horizon ve iki temas](../astra6/hpc.py#L387), [hedef takip alanı](../astra6/fractal_v3.py#L1654), [V2 çıkış](../astra6/sim.py#L113)

Hedef sızıntısını tekrar ölçmek için yerel `target_outcomes` ve `target_candidates` tablolarını `target_candidate_id` üzerinden birleştir. H1 modellerinin UEV'sindeki kova açılış indeksini `trade_features` içindeki `j_open` ile eşleştir. `tf=H1`, `anchor=cal`, `entry_mode=confirmed` ve aynı yönü seç. Model 1 için kaynak V2 `t_signal_known` anındaki son kapalı M15 Bid yüksekliğini yeniden hesapla. Model 2 için kaynak V2 `j_trig` anında son 50 aynı yön M5 OC'de `j_conf<=j`, `j_inv<0 or j_inv>j` ve midpoint'in Bid close'dan 3 puan aşağıda oluşunu sırayla uygula. Gerçek hedef fiyatının eşitliğini ve seviye teyidinin yeni dolumdan önce olup olmadığını ayrı say. Yeni dolum, V3 sinyal kapanışındaki veya sonraki ilk ortak M1 açılışıdır.

```sql
SELECT strategy_config_id, count(*) AS n,
       count(DISTINCT underlying_event_id) AS events,
       min(abs(target_price-entry_price)/abs(entry_price-stop_price)) AS min_rr,
       max(abs(target_price-entry_price)/abs(entry_price-stop_price)) AS max_rr
FROM read_parquet('data/results/counterfactual_policy_trades.parquet')
GROUP BY 1
ORDER BY 1
```

64 politika satırını MTF tablonun `00_No_CISD` ve `17_Missing_Liquidity_Sweep (j_sweep=-1)` taban satırlarıyla UEV üzerinden eşleştirmek, donmuş kaynak bilgisiyle politika tetik indeksini kıyaslamayı sağlar. İlgili bit açıkken `j_trig < macro_jform`, `j_trig < micro_jform` ve `0 <= j_cmp0 <= j_trig` sayımları ana rapordaki faktör bulgusunu üretir. Bu sorgular veri gölünü güncellemez.
