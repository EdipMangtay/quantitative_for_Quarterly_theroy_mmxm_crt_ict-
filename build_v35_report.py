"""Generate the Turkish V3.5 gate report from immutable comparison and sample ledgers."""

import json
import subprocess
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
RESULTS = ROOT / "data" / "results"
SAMPLE = RESULTS / "v3_5"


def table(headers, rows):
    def line(values):
        return "| " + " | ".join(map(str, values)) + " |"
    return "\n".join([line(headers), line(["---"] * len(headers)), *(line(row) for row in rows)])


def write(suffix, body):
    path = REPORTS / f"ASTRA6_V35_{suffix}.md"
    path.write_text(body.strip() + "\n", encoding="utf-8")
    return path


def main():
    ledger = pd.read_parquet(SAMPLE / "sample_1300_ledger.parquet")
    checkpoint = json.loads((RESULTS / "v3_5_checkpoint.json").read_text())
    p0 = json.loads((SAMPLE / "p0_resume_audit.json").read_text())
    run = json.loads((SAMPLE / "sample_1300_ledger.manifest.json").read_text())
    replays = json.loads((SAMPLE / "sample_trade_replays.json").read_text())
    before = json.loads((RESULTS / "v3_4_model_audit.json").read_text())["models"]
    counts = ledger.execution_status.value_counts()
    sample = table(["Davranışsal örnek", "Sayı"], [
        ("M1 gözlemi", run["config"]["observations"]),
        ("Benzersiz UEV", ledger.underlying_event_id.nunique()),
        ("Politika ve prob", ledger.policy_id.nunique()),
        ("Politika–fırsat satırı", len(ledger)),
        ("Dolum", int((ledger.j_fill >= 0).sum())),
        ("Dolum öncesi geçersizleşme", counts.get("INVALIDATED_BEFORE_ENTRY", 0)),
        ("Diğer iptal", counts.get("CANCELLED", 0)),
        ("Kayıtlı fiyat replay'i", len(replays)),
    ])
    events = ledger[(ledger.underlying_event_id == "UEV_US100_M5_884_S") & ledger.policy_id.isin([
        "00_No_CISD", "01_M1_CRT_CISD", "M1_STANDALONE_CISD", "M5_STANDALONE_CISD", "M15_STANDALONE_CISD",
    ])].sort_values("j_confirm")
    execution = table(["Politika", "Onay", "Dolum", "Çıkış", "Giriş", "Stop", "Hedef", "Çıkış kotasyonu", "Net R"], [
        (r.policy_id, r.j_confirm, r.j_fill, r.j_exit, f"{r.entry_price:.3f}", f"{r.stop_price:.3f}",
         f"{r.target_price:.3f}", f"{r.exit_quote:.3f}", f"{r.realized_net_r:+.6f}") for r in events.itertuples()
    ])
    comparison = table(["V3.4 kaynak grubu", "Önceki N", "Önceki ort. R", "V3.5 tarihsel sonuç"], [
        (r["model_id"], r["n_trades"], f"{r['expectancy_r']:+.5f}", "Hesaplanmadı") for r in before
    ])
    coverage = checkpoint["historical_revalidation"]["coverage_diagnostics"]
    coverage_table = table(["US100", "Tam", "Sınıflandırılamayan kısmi", "Açık"], [
        (tf, c.get("FULL", 0), c.get("PARTIAL_UNCLASSIFIED", 0), c.get("OPEN", 0))
        for tf, c in coverage["m1_cal_counts"].items()
    ])
    last_micro = min(coverage["exact_30s_last_quote_utc"].values())
    p0_counts = p0["counts"]
    p0_models = table(["Sıkı P0 playbook", "Aday", "Dolum", "Tam gözlenen çıkış"], [
        (model, values["candidates"], values["fills"], values["completed_observed_paths"])
        for model, values in p0_counts.items() if model.startswith("MODEL_")
    ])
    p0_coverage = table(["Son P0 tanısı", "Sayı"], [
        ("Ortak gerçek M1", p0_counts["common_m1"]),
        ("Ortak gerçek 30 saniye", p0_counts["common_30s"]),
        ("Kaynak uyuşmazlıklı boşluk", p0_counts["gaps"].get("INCOMPLETE", 0)),
        ("Açıklanamayan sessizlik", p0_counts["gaps"].get("UNKNOWN", 0)),
    ])
    replay_rows = table(["Replay", "Olay", "Politika", "Dolum / çıkış", "Durum"], [
        (f"[{r['replay_id']:02d}]({r['chart']})", r["underlying_event_id"], r["policy_id"],
         f"{r['j_fill']} / {r['j_exit']}", r["execution_status"]) for r in replays
    ])
    write("BEFORE_AFTER_RESULTS", f"""
# V3.4 ve V3.5 sonuç karşılaştırması

{comparison}

V3.4'te Model 1 için 200/325, Model 2 için 18/792 hedef dolumdan sonra biliniyordu. V3.5 hedefi karar anındaki kaynak ve geçerlilikten yeniden seçer. Model 4'ün önceki geniş 4–12 havuzu Stage 13 terminal stratejisinden ayrıdır.

- **UEV_US100_H1_10835_L.** Eski dolum 14:47 UTC, hedef teyidi 15:00 UTC. Ham fiyatlarda H1 üst sınırı alt sınırdan önce kırıldı. Tek taraflı LONG fırsatı oluşmadı.
- **UEV_US100_H1_6931_S.** Eski dolum 09:02 UTC, OC teyidi 10:00 UTC. Yeni aday 09:01 UTC'de gözlendi ve 09:06 UTC'de beklerken stopa değdi. Dolum yok.

{sample}

Bunlar politika–fırsat satırlarıdır. Bir olay birden fazla satır üretebilir. Dört model için düzeltilmiş N, PF, düşüş, OOS, GA ve p yok. Eski bulguların hangilerinin sürdüğü belirlenemiyor. [V3.4 uzlaştırması](ASTRA6_V34_RESULT_RECONCILIATION.md)
""")
    write("INDEPENDENT_EXECUTION_QA", f"""
# Bağımsız emir yürütme doğrulaması

**UEV_US100_M5_884_S · 8 Kasım 2021 · SHORT**

{execution}

Basit bağımsız döngü Bid girişten 0,25 puan düşer. Ask high/low ile ilk temas, temassız durumda Ask close kullanılır. Tablo çıkış kotasyonu, çıkış slippage'ı öncesidir. 360 gözlem ufku ve 360 takvim dakikası ayrı sözleşmelerdir. UEV 54 LONG stopu yalnız reclaim'e kadarki dipten türetilir. Gelecekteki düşük dip stopu değiştirmez. Beklerken stop ihlali adayın sonraki teyitle açılmasını engeller.

{table(["İcra durumu", "Politika–fırsat satırı"], list(counts.items()))}

[Emir Parquet](../data/results/v3_5/sample_1300_ledger.parquet) · [Replay JSON](../data/results/v3_5/sample_trade_replays.json)
""")
    tests = checkpoint["p0_resume"]["tests"]["compatibility"]
    focused = checkpoint["p0_resume"]["tests"]["after_focused"]
    negative = checkpoint["p0_resume"]["tests"]["before_negative_control"]
    write("TEST_RESULTS", f"""
# V3.5 test sonuçları

**{tests['passed']} geçti · {tests['deselected']} seçilmedi · {tests['warnings']} uyarı.**

Yeni sıkı P0 yolunda **{focused['passed']} odaklı test geçti**. Eski yolları doğrudan çağıran negatif kontrolde beklenen **{negative['observed_failures']} hata** yeniden üretildi.

Yeni testler kayıtlı fiyatları, saat ve olay metadata örneklerini kullanır. Eski sentetik fiyat testleri ile bütün tarihsel context'i kullanan mock test seçilmedi. P0 tam tarihsel kapısı bu test sayısından bağımsızdır.

```sh
{tests['command']}
```

- Zaman ve fiyat kapsamı. W1 DST, son kova, eksik gözlem, gap, CISD availability ve üç QT anchor'ı.
- OC/MMXM. 17.000 bar, 11 kesit, etkin aday ve terminal.
- İcra. Beş bağımsız Ask replay'i, gelecek stop, bekleme, gap, iki temas, geç faktör ve iki gerçek geç hedef.
- Doğrulama. Boş model, Model 4 ayrımı, kronolojik DD, eşli politika, portföy, dosya mutasyonu, üç olay zinciri.
""")
    final = write("FINAL_RESEARCH", f"""
# ASTRA 6 V3.5 onarım ve doğrulama raporu

**Durum `NOT_VERIFIED`.** Son P0 tanısı çalıştırıldı. Tam tarihsel P0 kapısı açık.

V3.4 denetimi stop ve hedef sızıntısını, geriye yazılan MMXM aşamalarını, emir zaman alanlarındaki tutarsızlığı ve sentetik replay yolunu kanıtladı. V3.5, ayrı kayıtlı olay ve fiyat kanıtı kullanan bir emir motoru ekliyor.

{sample}

## Emir zamanlaması

{execution}

Beş politika aynı gerçek SHORT olayında bağımsız Ask fiyat yoluyla eşleşti. CRT içi M1 ve bağımsız M1 farklı teyitlerdir. Bu tek örnek zaman dilimlerinin genel üstünlüğünü ölçmez.

## Dört model ve yayın kapısı

{comparison}

Model 1'in 200 ve Model 2'nin 18 geç hedefi V3.4 bulgularıdır. V3.5 karar anındaki teyitli, geçerli ve tüketilmemiş seviyeyi arar. İki gerçek karşı örnek ayrı yeniden yürütüldü. Tam model popülasyonları, üstün hedef tipi veya doğrulanmış MMXM × QT anlatısı henüz belirlenmedi.

## Son P0 çalıştırması

{p0_coverage}

{p0_models}

H1 dönüşü gerçek sweep, önceden teyitli swing kırılımı ve bağımsız H1 CISD ile sınandı. MMXM ile OC bağı olay kimliği, araç, zaman dilimi, yön ve bilgi zamanı üzerinden kuruldu. Altı tarih penceresinde Model 1 için 5.945 ve Model 2 için 3 sıkı aday izlendi. İki playbook'ta da bütün zorunlu olay zincirini geçip dolan emir bulunmadı. Bu sıfır dolum, tam tarihsel performans tahmini değildir. Uyumluluk koşusunda 2.729 test, yeni sıkı P0 yolunda 77 odaklı test geçti. Eski yollar altı negatif kontrolde beklenen nedenle başarısız oldu.

{coverage_table}

Tarihli broker seans takvimi eksik. Belirsiz boşluklar `UNKNOWN`, kaynak uyuşmazlığı görülenler `INCOMPLETE` olarak dışlandı. İki araçta gerçek 30 saniyelik kotasyonların ortak kapsamı en geç {last_micro} UTC'de biter. H1 dönüşü ve MMXM/OC olay bağları ayrı gerçek örneklerde geçti. İki playbook için bütünleşik dolum tanığı bulunmadı. 64 politika ve tüm yapısal hedef yolları aynı sıkı sözleşmeyle uçtan uca geçmedi. Beş yıllık çalışma başlatılmadı. Sıralama ve yeni finansal sonuç yayımlanmadı.

## Kayıtlı kotasyon

![Gerçek Ask M1 · UEV_US100_M5_884_S](figures/v35_replays/replay_01.svg)

Bar içindeki kesin temas sırası M1 OHLC'den bilinemez. Grafik ve tablo, aynı örnek emir defteri ve replay JSON'una bağlıdır.

{replay_rows}

## Paper trading öncesi

Kapsam dışı seans ve TF'leri sabitle, H1 dönüş ve OC ilişkisini bağımsız olaylarla bağla, geniş P0 testini geçir. Düzeltilmiş tarihsel işlemler ve portföy sonuçları ayrı hesaplanmalı. İleri paper emirleri dondurulmuş politika kimliğiyle kaydedilmeli.

[Son P0](ASTRA6_V35_P0_REVALIDATION.md) · [Onarım](ASTRA6_V35_CAUSAL_REPAIR_AUDIT.md) · [Önce/sonra](ASTRA6_V35_BEFORE_AFTER_RESULTS.md) · [MMXM × QT](ASTRA6_V35_MMXM_QT_VALIDATION.md) · [Emir QA](ASTRA6_V35_INDEPENDENT_EXECUTION_QA.md) · [İstatistik](ASTRA6_V35_STATISTICAL_VALIDATION.md) · [Testler](ASTRA6_V35_TEST_RESULTS.md)
""")
    body = subprocess.run(
        ["pandoc", "--from=gfm", "--to=html5", str(final)], check=True, capture_output=True, text=True,
    ).stdout
    html = final.with_suffix(".html")
    html.write_text(f"""<!doctype html>
<html lang="tr"><meta charset="utf-8"><title>ASTRA 6 V3.5 onarım ve doğrulama</title>
<style>
@page {{ size:A4; margin:14mm; }}
body {{ font:14px/1.45 Arial,sans-serif; color:#172033; max-width:960px; margin:30px auto; padding:0 18px; }}
h1 {{ font-size:30px; color:#10345a; border-bottom:3px solid #008080; padding-bottom:8px; }}
h2 {{ font-size:20px; color:#10345a; margin:24px 0 10px; break-after:avoid; }}
table {{ border-collapse:collapse; width:100%; font-size:12px; margin:12px 0 20px; }}
th {{ background:#10345a; color:white; text-align:left; }}
td,th {{ padding:5px 7px; border:1px solid #cbd5e1; overflow-wrap:anywhere; }}
tr {{ break-inside:avoid; }} tbody tr:nth-child(even) {{ background:#f1f5f9; }}
thead {{ display:table-header-group; }} a {{ color:#0b6379; }}
img {{ max-width:100%; }} figure {{ margin:0; break-inside:avoid; }}
@media print {{
  body {{ margin:0; padding:0; font-size:10px; }}
  h1 {{ font-size:24px; }} h2 {{ font-size:16px; margin:14px 0 8px; }}
  table {{ font-size:8.2px; margin:7px 0 10px; }} td,th {{ padding:3px 5px; }}
  img {{ max-height:270px; object-fit:contain; }}
}}
</style><body>{body}</body></html>
""", encoding="utf-8")
    subprocess.run(
        ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--headless", "--disable-gpu",
         "--no-pdf-header-footer", f"--print-to-pdf={final.with_suffix('.pdf')}", html.as_uri()],
        check=True, capture_output=True, text=True,
    )


if __name__ == "__main__":
    main()
