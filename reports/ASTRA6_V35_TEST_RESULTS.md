# V3.5 test sonuçları

**2652 geçti · 11 seçilmedi · 9 uyarı.**

Yeni testler kayıtlı fiyatları, saat ve olay metadata örneklerini kullanır. Eski sentetik fiyat testleri ile bütün tarihsel context'i kullanan mock test seçilmedi. P0 tam tarihsel kapısı bu test sayısından bağımsızdır.

```sh
PYTHONDONTWRITEBYTECODE=1 NUMBA_CACHE_DIR=/tmp/astra6-v35-numba .venv/bin/python -m pytest -q -p no:cacheprovider tests -k 'not test_cat01 and not test_cat03 and not test_cat04 and not test_cat05 and not test_cat07 and not test_cat08 and not test_cat09 and not test_v3_reference_vs_numba and not test_p0_1_mmxm_incremental and not test_p0_5_target_consistent and not test_true_factorial_same_event'
```

- Zaman ve fiyat kapsamı. W1 DST, son kova, eksik gözlem, gap, CISD availability ve üç QT anchor'ı.
- OC/MMXM. 17.000 bar, 11 kesit, etkin aday ve terminal.
- İcra. Beş bağımsız Ask replay'i, gelecek stop, bekleme, gap, iki temas, geç faktör ve iki gerçek geç hedef.
- Doğrulama. Boş model, Model 4 ayrımı, kronolojik DD, eşli politika, portföy, dosya mutasyonu, üç olay zinciri.
