# V3.5 istatistiksel doğrulama durumu

**Tam tarihsel inferans yayımlanmadı.** Sıralama ve kârlılık için tam P0 kapısı ve düzeltilmiş model defteri gerekli. Önceden incelenen tarihler, split adı değişince ileri doğrulamaya dönüşmez.

Kronolojik düşüş çıkış sırasını kullanır. Aynı anda kapanan işlemler tek değişimde toplanır. Eşli ablation iki politikada da dolmuş aynı UEV'leri seçer. Örtüşmeyen tek pozisyon portföyü, aynı politikaya ayrı uygulanır. Gün ve hafta etiketleri eşli satırlarda ayrı. Walk-forward, çıkış zamanı varsa pencereyi aşan işlemi dışarıda bırakır.

Tam geçmişte haftalık blok çıkarımı, maliyet senaryosu, portföy tahsisi, model seçimi düzeltmesi ve ileri dönem testi tamamlanmadı. Model 4 terminal, 11/12 ve geniş aktif hedef evreni ayrı kimliklerde. Eksik deftere sabit R atama kaldırıldı. Modellerin hiçbirinde ileri doğrulama statüsü yok.
