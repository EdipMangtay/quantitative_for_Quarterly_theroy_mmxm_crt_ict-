# Bağımsız emir yürütme doğrulaması

**UEV_US100_M5_884_S · 8 Kasım 2021 · SHORT**

| Politika | Onay | Dolum | Çıkış | Giriş | Stop | Hedef | Çıkış kotasyonu | Net R |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 00_No_CISD | 887 | 888 | 902 | 16378.829 | 16403.309 | 16329.869 | 16329.869 | +1.989788 |
| 01_M1_CRT_CISD | 888 | 889 | 1249 | 16366.129 | 16403.309 | 16291.769 | 16351.131 | +0.396665 |
| M1_STANDALONE_CISD | 901 | 902 | 1262 | 16342.827 | 16403.309 | 16221.863 | 16343.231 | -0.010813 |
| M5_STANDALONE_CISD | 903 | 904 | 1264 | 16341.469 | 16403.309 | 16217.789 | 16343.741 | -0.040783 |
| M15_STANDALONE_CISD | 908 | 909 | 1269 | 16346.239 | 16403.309 | 16232.099 | 16331.751 | +0.249483 |

Basit bağımsız döngü Bid girişten 0,25 puan düşer. Ask high/low ile ilk temas, temassız durumda Ask close kullanılır. Tablo çıkış kotasyonu, çıkış slippage'ı öncesidir. 360 gözlem ufku ve 360 takvim dakikası ayrı sözleşmelerdir. UEV 54 LONG stopu yalnız reclaim'e kadarki dipten türetilir. Gelecekteki düşük dip stopu değiştirmez. Beklerken stop ihlali adayın sonraki teyitle açılmasını engeller.

| İcra durumu | Politika–fırsat satırı |
| --- | --- |
| INVALIDATED_BEFORE_ENTRY | 29546 |
| CANCELLED | 3516 |
| STOP_HIT | 2304 |
| TARGET_HIT | 883 |
| DATA_END | 138 |
| TIMEOUT | 56 |

[Emir Parquet](../data/results/v3_5/sample_1300_ledger.parquet) · [Replay JSON](../data/results/v3_5/sample_trade_replays.json)
