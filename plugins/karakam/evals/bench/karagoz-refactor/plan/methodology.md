# Metodoloji: stokcu v2

## Goal
Çalışan `stokcu` aracına (v1: CSV stok dosyası → KDV dahil değer raporu) iki
yetenek eklenir: ürünlerin bir `kategori` alanı olur ve `python3 -m stokcu ara
<csv> <sorgu>` komutu, ürün adında veya SKU'sunda Türkçe harf kurallarına uygun,
büyük/küçük harf duyarsız arama yapar. Mevcut `rapor` komutu aynen çalışmaya
devam eder.

## Stack & libraries
- Python 3.10+ stdlib — dış bağımlılık yok.
- pytest — testler için.

## Methods & patterns
- Para her yerde `decimal.Decimal`.
- Katmanlar: `model.py` (veri + CSV), `fiyat.py`, `rapor.py`, `metin.py` (metin
  karşılaştırma yardımcıları, saf fonksiyonlar), `__main__.py` (CLI, argparse alt
  komutları).

## Step ordering & dependencies
01 (metin) ve 02 (kategori) birbirinden bağımsız. 03 (`ara` komutu) ikisini de
kullanır.

## Integrity principles
- CSV başlığı v2'de tam olarak `sku,ad,kategori,adet,birim_fiyat`.
- `Urun` alanları: `sku`, `ad`, `kategori`, `adet`, `birim_fiyat`; `kategori`
  boş olamaz.
- Metin karşılaştırmaları Türkçe büyük/küçük harf kurallarına uyar: `I` ↔ `ı`,
  `İ` ↔ `i`; diğer harfler olağan eşleşmeleriyle.
- CLI hataları stderr'e `hata: ...` olarak yazılır, çıkış kodu 2; stdout boş kalır.

## Definition of Done + test strategy
Her adım kendi testleriyle gelir; `python3 -m pytest -q` tüm depoda yeşil
olmalı. CLI davranışı `subprocess` ile gerçek komut çalıştırılarak doğrulanır.

## Known limits (deliberately out of scope)
- v1 başlıklı eski CSV dosyaları v2'de okunmaz; dönüştürme aracı yok.
