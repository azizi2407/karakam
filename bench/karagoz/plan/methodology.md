# Metodoloji: stokcu

## Goal
`stokcu`, bir CSV stok dosyasını okuyup KDV dahil değer raporu basan küçük bir
Python komut satırı aracıdır. Bittiğinde `python3 -m stokcu rapor <csv>` komutu
ürünleri toplam değere göre sıralı bir tablo olarak yazar, düşük stoğu işaretler
ve hatalı satırlarda satır numarasıyla birlikte anlamlı bir hata verir.

## Stack & libraries
- Python 3.10+ stdlib — dış bağımlılık yok (`csv`, `decimal`, `dataclasses`, `argparse`).
- pytest — testler için; başka test aracı yok.

## Methods & patterns
- Para her yerde `decimal.Decimal`; `float` yasak.
- Katmanlar: `model.py` (veri + doğrulama + CSV yükleme), `fiyat.py` (KDV ve TL
  biçimi, saf fonksiyonlar), `rapor.py` (satırları üretir), `__main__.py` (CLI).
- Her modülün testi `tests/test_<modül>.py` içinde.

## Step ordering & dependencies
01 (model) ve 02 (fiyat) birbirinden bağımsızdır, paralel koşabilir. 03 (rapor +
CLI) ikisini birden kullanır, bu yüzden ikisine de bağlıdır.

## Integrity principles
- `Urun` alanları: `sku: str`, `ad: str`, `adet: int`, `birim_fiyat: Decimal`.
- `stok_yukle(yol) -> list[Urun]`; hatalı satırda `StokHatasi(satir_no, mesaj)`
  fırlatır (`satir_no` başlık satırı 1 olmak üzere dosyadaki satır numarası).
- `kdvli(tutar, oran=Decimal("0.20")) -> Decimal` iki haneye ROUND_HALF_UP yuvarlar.
- `tl_bicimle(tutar) -> str` Türk biçimi: binlik ayırıcı nokta, ondalık virgül,
  iki hane, sonda " TL" (ör. `1.234,50 TL`).
- Rapor, fiyat hesaplarını yalnızca `fiyat.py` üzerinden yapar; kendi
  yuvarlama/biçimleme kodunu yazmaz.

## Definition of Done + test strategy
Her adım kendi testleriyle gelir; `python3 -m pytest -q` tüm depoda yeşil olmalı.
CLI davranışı, testlerde `subprocess` ile gerçek komut çalıştırılarak doğrulanır.

## Known limits (deliberately out of scope)
- Tek para birimi (TL), tek KDV oranı varsayılanı; çoklu oran yok.
- CSV kodlaması UTF-8 varsayılır.
