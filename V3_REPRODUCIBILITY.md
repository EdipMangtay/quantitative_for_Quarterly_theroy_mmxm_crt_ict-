# ASTRA 6 — V3 REPRODUCIBILITY & HARDWARE OPTIMIZATION REPORT
## Donanım Profili, Kriptografik Manifest ve Tam Tekrarlanabilirlik Rehberi

**Proje:** ASTRA 6 Institutional Quantitative Research Engine  
**Sürüm:** V3.1 Causal Repaired (`ALGO_VERSION = "ASTRA6_V3.1_CAUSAL_REPAIRED"`)  
**Tarih:** 2026-11-08  
**Çalışma Alanı:** `/Users/mangtay/qt_test`  

---

## 1. DONANIM PROFİLİ VE SİSTEM KAYNAKLARI (HARDWARE PROFILE)

Sistem kaynakları `astra6/hpc.py` içerisindeki `run_benchmark_and_autotune()` fonksiyonu tarafından dinamik olarak ölçülmüş ve `data/results/hardware_benchmark.json` dosyasına kaydedilmiştir:

```json
{
  "hardware_profile": {
    "os_name": "Darwin",
    "os_release": "27.2.0",
    "architecture": "arm64",
    "cpu_model": "Apple M3 Pro",
    "physical_cores": 12,
    "logical_cores": 12,
    "ram_total_gb": 18.0,
    "ram_available_gb": 6.8,
    "disk_total_gb": 460.4,
    "disk_free_gb": 169.6,
    "selected_workers": 6,
    "selected_duckdb_threads": 8,
    "selected_batch_size": 250000,
    "detected_at_utc": "2026-11-08T15:23:45.000000Z"
  }
}
```

### 1.1 HPC Kernel Doğrulaması ve Hızlanma
- **Referans Çekirdek:** Saf Python hedef simülasyonu (`reference_target_exec_full_py`).
- **Optimize Çekirdek:** Numba JIT paralel hedef simülasyonu (`fast_target_exec_full_numba`).
- **Exact Match Doğrulaması:** 10.000 barlık sentetik ve düşmanca (adversarial same-bar SL+TP) test serisinde Numba ve Python çıktıları **%100.0 bit-bazında özdeş** sonuç vermiştir (`reference_vs_numba_exact_match: true`).
- **Hızlanma Faktörü:** Numba çekirdeği saf Python'a göre **~64x** daha hızlı çalışarak 2.65M hedef sonucunu 78 saniyede hesaplamıştır.
- **Sıfır Bellek Kopyalama:** 1.76M M1 barı işçi süreçlerine kopyalanmayıp tek bir in-process bellek adresinden paralel olarak taranmıştır.

---

## 2. KRİPTOGRAFİK VERİ SETİ MANİFESTİ (DATA STORE SHA256)

Araştırma motorunun tükettiği 14 temel Parquet mağazası dosyasının tam dosya SHA256 özetleri:

| Dosya Adı | Boyut (Bayt) | Tam Dosya SHA256 Özeti |
| :--- | :---: | :--- |
| `US100_BID_M1.parquet` | 35,145,678 | `e192671a588d872b834927bdfa5a0cb1b198188ff6e5f187a5078512595ff9aa` |
| `US100_ASK_M1.parquet` | 31,760,284 | `85332e04ab612e434e402802d2427a9c80d4db1cfa444b0254c7dca326075677` |
| `US500_BID_M1.parquet` | 30,184,845 | `57429275146079df92a5ee7e54c866d925501867c4fa6161c5c6f6e5e0a6d1da` |
| `US500_ASK_M1.parquet` | 28,253,814 | `831c44087fcb0ef8cfa2b9846b0a1d5a7d901615f013217b7082e666993a4b69` |
| `US30_BID_M1.parquet` | 22,917,524 | `25112214ff063676cf7446fec34dbe226e632b7a972e2765d75d69ba2eb5fcb1` |
| `US30_ASK_M1.parquet` | 20,707,260 | `365f587711c99adbebf2bc14f6b1580220be216ce58032483d8e5e6df15be30b` |
| `DUKA_US100_M1.parquet` | 57,169,723 | `4d4c36fd6c5987b6ec4fe2076067b5e40a7b453e00e84ec10f0f5b1111663f7d` |
| `DUKA_US500_M1.parquet` | 50,139,904 | `b0e6e68485dde9886a066a3375cb080fc85ec92fdb3f6b9c9e83e954c346174d` |
| `DUKA_US100_30S.parquet` | 107,838,866 | `0f26f60f034714a511fe806509f6f69902640bc5a932c02c63f1737be0d1b54a` |
| `DUKA_US500_30S.parquet` | 90,144,706 | `fe37af2770c1ffd04e030a5ca66380c5cbcfb0b30fc955b233a76793f18b14e5` |
| `DUKA_US100_TICKS_SAMPLE.parquet`| 16,380,014 | `e642b129fa6165e4ff81efd3688126868dfb776c528652077b07e8ef6e6d1235` |
| `OANDA_US100_M1.parquet` | 23,824,150 | `989aa03758e96ebe0411516eeb260842db157d0799988e404bfbc49e9cb4e73e` |
| `OANDA_US500_M1.parquet` | 18,632,825 | `c94386dcb1db884d5df6110f0cf985e505a4175394be562f01eb0df828114f88` |
| `OANDA_US30_M1.parquet` | 19,958,833 | `156bf9319f415bb9f94f9b8aa751994e414c00d4a9f4c3981881ae0b2d3989c9` |

---

## 3. KRİPTOGRAFİK ÖNBELLEK GEÇERSİZ KILMA KURALLARI (CACHE INVALIDATION SPEC)

`astra6/hpc.py` içerisindeki `CheckpointManager`, sonuçların tekrarlanabilirliğini şu 4 kural ile garanti eder:

1. **Source SHA256 Eşleşmesi:** Yukarıdaki 14 temel mağaza dosyasının blok özetlerinden üretilen `source_store_sha256` değeri önbellek manifestosundakiyle eşleşmelidir. Mağazadaki tek bir bayt değişirse önbellek geçersiz kalır.
2. **Algoritma Versiyonu Eşleşmesi:** `fractal_v3.ALGO_VERSION = "ASTRA6_V3.1_CAUSAL_REPAIRED"` olarak tanımlıdır. Kodda versiyon değiştiğinde önbellek otomatik silinir.
3. **Konfigürasyon Hash Eşleşmesi:** Kayma puanı, horizon bar sayısı, zaman dilimi listeleri ve aynı-bar SL/TP politikaları JSON olarak hash'lenir (`config_hash`). Parametre değişimi önbelleği bozar.
4. **Zorunlu Yeniden Hesaplama (`--full`):** `--full` veya `--force` bayrağı verildiğinde, `is_cache_valid` doğrudan `False` döner ve 5 yıllık tüm evren sıfırdan hesaplanır.

---

## 4. DUCKDB ANALİTİK VERİTABANI VE SQL DOĞRULAMA (DUCKDB VERIFICATION)

Tüm 29 V3 Parquet tablosu, `data/results/astra6_v3.duckdb` analitik veritabanına birer SQL görünümü (view) olarak kaydedilmiştir.

### Doğrulama SQL Sorguları:

```bash
# 1. İşlem tablosu satır sayısını kontrol et
uv run python -c "
import duckdb
con = duckdb.connect('data/results/astra6_v3.duckdb', read_only=True)
print('Total Trades:', con.execute('SELECT COUNT(*) FROM all_trades').fetchone()[0])
print('Long Trades :', con.execute(\"SELECT COUNT(*) FROM all_trades WHERE direction='LONG'\").fetchone()[0])
print('Short Trades:', con.execute(\"SELECT COUNT(*) FROM all_trades WHERE direction='SHORT'\").fetchone()[0])
con.close()
"
```

```text
Total Trades: 644237
Long Trades : 312574
Short Trades: 331663
```

```bash
# 2. 64 Binary Kombinasyon Özetini Görüntüle
uv run python -c "
import duckdb
con = duckdb.connect('data/results/astra6_v3.duckdb', read_only=True)
res = con.execute('''
    SELECT base_config_id, config_label, n_trades, round(win_rate, 4) as wr, round(expectancy_r, 4) as exp_r
    FROM combination_results
    WHERE scope='All_Sessions' AND direction='BOTH'
    ORDER BY expectancy_r DESC
    LIMIT 5
''').fetchall()
for row in res:
    print(row)
con.close()
"
```

```text
('CFG64_56', 'CRT+MacSSMT+MicSSMT', 506, 0.2767, -0.1977)
('CFG64_30', 'MacSSMT+MicSSMT+StdSMT+CISD', 3381, 0.2644, -0.2312)
('CFG64_60', 'CRT+MacSSMT+MicSSMT+StdSMT', 236, 0.2627, -0.2437)
('CFG64_62', 'CRT+MacSSMT+MicSSMT+StdSMT+CISD', 3748, 0.2596, -0.2507)
('CFG64_35', 'CRT+CISD+MMXM', 62870, 0.2638, -0.2544)
```

---

## 5. SIFIRDAN TAM TEKRARLAMA TALİMATI (ONE-COMMAND REPRODUCTION)

Tüm sistemi ve raporları sıfırdan yeniden üretmek için tek bir komut yeterlidir:

```bash
# Adım 1: Tam pipeline'ı sıfırdan koştur (tüm V2 ve V3 hesaplamaları, raporlar ve testler dahil)
uv run python run_pipeline.py --full

# Adım 2: Bağımsız QA test paketini çalıştır
uv run pytest -v tests/test_v3_fractal_qa.py

# Adım 3: Üretilen dinamik raporları incele
open reports/ASTRA6_V3_Universal_Fractal_Raporu.html
open reports/ASTRA6_V3_Universal_Fractal_Raporu.pdf
```
