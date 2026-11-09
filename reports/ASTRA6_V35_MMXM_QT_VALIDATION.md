# MMXM × QT doğrulaması

On bir kesitte OC ve MMXM kimlikleri, aşama, yön, availability, hedef ve terminal alanları ile son 80 barın etkin model kümeleri eşleşti. OC adayında gelecekteki ayrılış yönü boş. MMXM terminal satırı gelince aday etkin sorgudan çıkar. [Makine farkları](../data/results/v3_5/p02_prefix_diff.json)

NY 18:00, NY 09:30 ve Londra 08:00 için 22,5 dakikanın yarım dakikalık sınırları bağımsız saat hesabıyla sınandı. V3.5 örnek micro SSMT hesabı mevcut 30 saniyelik fiyatları kullanıyor. Bu kaynağın dışındaki dönem için exact micro kapsamı varsayılmadı.

Üç adlandırılmış anlatının doğrulayıcısı olay kimliği, araç, yön, TF, zaman, geçerlilik ve parent bağı ister. Eksik adım, yanlış TF ve kopuk bağ testleri var. Fiyat geometrisiyle çıkan aşamalar bağımsız CRT/SMT/CISD veya HTF POI olayı sayılmaz. Gerçek üretim olaylarının üç tam zincire eşlenmesi henüz doğrulanmadı. Üçü için tarihsel durum `NOT_VERIFIED`.
