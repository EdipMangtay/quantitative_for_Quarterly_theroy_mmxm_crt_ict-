# ASTRA 6 öncelikli onarım planı

Denetlenen sürüm `9274803d002a14bc18e0a918d8a90fd615b0ed8f`. Aşamalar kaydedilmiş fiyat ve zaman kesitleriyle denetlenebilir küçük değişikliklere ayrıldı.

| Öncelik | Değişiklik | Kabul ölçütü |
|---|---|---|
| P0.1 | `bars.resample`, OC ve CISD eşlemesi. Gerçek yerel kova bitişi, son gözlem, veri kapsamı ve `available_at` ayrı. En son tamamlanmış kovayı sonraki gözleme bağlama. | Hafta sonu, DST, kayıp M1 ve kesit sınırı testleri. Eksik kova açıkça işaretli. Kapanış ve bilgi zamanı bağımsız referansla eşleşir. |
| P0.2 | OC aday ve onay olayını ayır. FSM Stage 1'i geriye yazmasın. Terminali eski snapshot'a kopyalama. As-of model başına etkin durumu sorgulasın. | 17.000 kayıt ve 11 prefix deneyinde o ana kadar bilinen olaylar ve as-of seçimleri eşit. Terminal model yeniden aktif görünmez. |
| P0.3 | V3 hazırlık ve 64/MTF döngüsü. İlk gözlenebilir sweep/reclaim'den fırsat. REQUIRED için yön, event ID, `available_at`, invalidation. DISABLED, aday seçiminde rol oynamaz. | Gerekli olaylar ≤ teyit ≤ submit ≤ fill. İleri SSMT ve geçersiz StdSMT sorguları sıfır. Eksik sweep ayrı kontrol. `UEV_US100_M5_54_L` stopu ilerideki dipten türemez. |
| P0.4 | Ortak emir planlayıcı. Ön stopu bekleme sırasında denetle. Gap ve yönlü risk geçersizse iptal. `j_exit` ile timestamp alanlarını birlikte güncelle. CRT içi M1 ile standalone politikaları ayır. | `UEV_US100_M5_884_S` beş satır bağımsız referansla karşılaştırılır. MTF çıkışları 902/1249/1264/1269. Gerçek iki temas, gap ve data-end örneği. `INVALIDATED_BEFORE_ENTRY` fiyat ve olay izine bağlı. |
| P0.5 | Hedefi karar anına göre seç. Hedef ID, TF kapanış/availability, tüketilme, karar ve fill fiyatları ayrı. Sabit 2R ile yapısal emirleri ayrı etiketle. | Model 1'in 200 ve Model 2'nin 18 geç hedefi önceden bilinen olarak yazılmaz. Fiyat ile hedef türü eşleşir. LONG/SHORT yapısal emir gerçek fiyattan tekrar yürütülür. |
| P1.1 | V3 FSM POI/confirm ve `run_narrative_validation`. Zorunlu olayları yön, TF ve sıralı ID ile tanımla. Eski eşikleri fiyat geometrisi olarak ayrı göster. | Tam zincir pozitif, her zorunlu olayı ayrı eksilten örnek negatif. H1 kaydı tek başına H4→M15→M5 kurgusuna giremez. |
| P1.2 | `run_audit` sabit R fallback'ini kaldır. `compute_model_metrics` boş şema, nedensel uygunluk ve gerekçe döndürsün. Model 4 Stage 13, 11/12 ve geniş havuzu ayrı. | Boş seçim `INSUFFICIENT_DATA`. p/GA, OOS veya nedensellik kapısı sağlanmıyorsa doğrulama statüsü yok. PDF/JSON/Parquet tek hesap kaynağı. |
| P1.3 | `build_trade_replays` aynı trade/policy/target ID'den gerçek kotasyon penceresini alır. SVG, PDF, JSON aynı kaydı kullanır. | Yirmi ID ve tüm fiyat/zaman alanları eşit. Bid/Ask, gap ve eksik tick görünür. İptal iddiası gerçek iptal kaydına bağlanır. |
| P1.4 | `_fast_cell_metrics`, ablation ve ranking. Zaman sıralı düşüş, aynı olayda eşli politika, portföy çakışması, günlük/haftalık blok ve seçilen test ailesi. | Parquet sıra değişimi DD'yi değiştirmez. Aynı UEV üzerinde ON/OFF farkı. WFA katlarında açık pozisyonlar ile bilgi penceresi ayrılır. |
| P2 | Cache ve manifest. Tam dosya hash'i, kaynak commit, config, veri, üretici/çıktı ve taşınabilir DuckDB yolu. V3.4 komut zinciri açık. | Aynı boyutlu iç değişim cache'i geçersiz kılar. V4 manifest farkı rapora girer. Başka checkout yerel Parquet ile salt okunur açılır. |

## Paper trading kapısı

1. P0 kabul testleri geçmiş ve aynı olay kimliği için teyit, iptal, fill, stop/TP ve kapanışı gerçek bilgi zamanıyla taşıyan emir günlüğü.
2. Önceden sabitlenmiş model, seans, veri sağlayıcı, maliyet, risk tahsisi, çakışma, emir ömrü ve aday önceliği.
3. Kaynak ve config hash'i ile başlangıç tarihi önceden kayıtlı. Bundan sonraki paper emirleri ve gerçekleşebilir kotasyonlar toplanır.
4. Önceden belirlenmiş tarihte işlem/gün sayısı, maliyet duyarlılığı, çakışma, iptal ve veri kaybı incelenir. Destek yalnız çalıştırılan politika ile bire bir eşleşen gözlemler için değerlendirilir.
