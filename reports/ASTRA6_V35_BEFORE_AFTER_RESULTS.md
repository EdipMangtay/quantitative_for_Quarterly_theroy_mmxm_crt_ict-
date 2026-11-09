# V3.4 ve V3.5 sonuç karşılaştırması

| V3.4 kaynak grubu | Önceki N | Önceki ort. R | V3.5 tarihsel sonuç |
| --- | --- | --- | --- |
| MODEL_1_H1_M5_M15_LIQ | 325 | +0.82789 | Hesaplanmadı |
| MODEL_2_H1_REV_M5_OC | 792 | +0.18931 | Hesaplanmadı |
| MODEL_3_NY_OPEN_CFG64_57 | 658 | +0.07152 | Hesaplanmadı |
| MODEL_4_MMXM_COMPLETED_QT_Q2_LONG | 96803 | -0.18079 | Hesaplanmadı |

V3.4'te Model 1 için 200/325, Model 2 için 18/792 hedef dolumdan sonra biliniyordu. V3.5 hedefi karar anındaki kaynak ve geçerlilikten yeniden seçer. Model 4'ün önceki geniş 4–12 havuzu Stage 13 terminal stratejisinden ayrıdır.

- **UEV_US100_H1_10835_L.** Eski dolum 14:47 UTC, hedef teyidi 15:00 UTC. Ham fiyatlarda H1 üst sınırı alt sınırdan önce kırıldı. Tek taraflı LONG fırsatı oluşmadı.
- **UEV_US100_H1_6931_S.** Eski dolum 09:02 UTC, OC teyidi 10:00 UTC. Yeni aday 09:01 UTC'de gözlendi ve 09:06 UTC'de beklerken stopa değdi. Dolum yok.

| Davranışsal örnek | Sayı |
| --- | --- |
| M1 gözlemi | 1300 |
| Benzersiz UEV | 499 |
| Politika ve prob | 75 |
| Politika–fırsat satırı | 36443 |
| Dolum | 3381 |
| Dolum öncesi geçersizleşme | 29546 |
| Diğer iptal | 3516 |
| Kayıtlı fiyat replay'i | 20 |

Bunlar politika–fırsat satırlarıdır. Bir olay birden fazla satır üretebilir. Dört model için düzeltilmiş N, PF, düşüş, OOS, GA ve p yok. Eski bulguların hangilerinin sürdüğü belirlenemiyor. [V3.4 uzlaştırması](ASTRA6_V34_RESULT_RECONCILIATION.md)
