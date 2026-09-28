# Metodoloji: stokcu v3 — stok hareketleri ve FIFO maliyet

## Goal
Çalışan `stokcu` aracına (v1: ürün CSV'si → KDV dahil değer raporu) stok
hareketleri eklenir: giriş, çıkış ve müşteri iadesinden oluşan bir hareket
CSV'si FIFO yöntemiyle maliyetlendirilir. İki yeni komut:
`python3 -m stokcu degerle <urunler.csv> <hareketler.csv> [--tarih T]` belirli bir
tarihteki stok miktarını ve FIFO değerini, `python3 -m stokcu kar <urunler.csv>
<hareketler.csv> --ay YYYY-MM` bir ayın brüt kârını verir. Mevcut `rapor` komutu
aynen çalışmaya devam eder.

## Stack & libraries
- Python 3.10+ stdlib — dış bağımlılık yok.
- pytest — testler için.

## Methods & patterns
- Para ve maliyet her yerde `decimal.Decimal`; ara hesaplar yuvarlanmaz. Yuvarlama
  yalnızca yazdırırken, mevcut `fiyat.tl_bicimle` ile (kuruşa, ROUND_HALF_UP).
- Katmanlar: `tarih.py` (tarih ayrıştırma), `fifo.py` (hareket veri tipi + FIFO
  defteri, saf mantık, dosya okumaz), `hareket.py` (hareket CSV yükleyici),
  `degerleme.py` ve `kar.py` (raporlar, satır listesi döndürür, yazdırmaz),
  `__main__.py` (CLI, argparse alt komutları).
- Satır numaralı hatalar mevcut `model.StokHatasi(satir_no, mesaj)` ile verilir;
  `str(e)` → `"satır N: mesaj"`.

## Step ordering & dependencies
01 (tarih) ve 02 (FIFO defteri) birbirinden bağımsız. 03 (hareket yükleyici)
ikisini de kullanır. 04 (değerleme) ve 05 (kâr) 02 ve 03'ün üzerine kurulur,
birbirinden bağımsızdır. 06 (CLI) hepsini bağlar.

## Integrity principles
- **Tarih:** girişte tam olarak `GG.AA.YYYY` ya da `YYYY-MM-DD`; gün ve ay iki
  haneli, yıl dört haneli, yalnızca ASCII rakamlar (`0`–`9`), baş/son boşluk yok;
  takvimde olmayan tarih geçersiz. Ay parametresi tam olarak `YYYY-MM`, ay 01–12.
- **Hareket CSV'si:** başlık tam olarak `tarih,sku,tur,adet,birim_fiyat`; her satır
  5 alan. `sku` `[A-Z]{3}-[0-9]{4}`. `tur` ∈ `giris`, `cikis`, `iade`. `adet`
  yalnızca ASCII rakamlardan oluşan pozitif tamsayı. `birim_fiyat`: `giris`te alış
  birim maliyeti, `cikis`ta KDV hariç satış birim fiyatı — biçimi yalnızca ASCII
  rakamlar ve isteğe bağlı tek bir ondalık nokta ile ardından rakamlar (`12`,
  `12.5`); işaret, üs, boşluk, `NaN`/`Infinity` geçersiz. `iade`de `birim_fiyat`
  boş olmalı.
- **İşleme sırası:** hareketler tarihe göre, aynı tarihte dosyadaki satır sırasına
  göre işlenir (dosya tarih sırasında olmak zorunda değil).
- **FIFO:** her `giris` sıranın sonuna yeni bir lot ekler. `cikis` en eski lottan
  başlayarak tüketir; maliyeti tüketilen parçaların (adet × lot maliyeti)
  toplamıdır. Stok yetmezse hata ve hiçbir şey değişmez. Lotlar asla birleştirilmez.
- **İade:** yalnızca o SKU'nun en son çıkışına karşı yapılır ve o çıkışın henüz
  iade edilmemiş adedini aşamaz (aşarsa ya da hiç çıkış yoksa hata). Geri gelen
  birimler, o çıkışın tükettiği birimlerin henüz iade edilmemiş olanlarının
  **sonundakilerdir** (en son tüketilenler); her biri kendi lot maliyetiyle, çıkıştaki
  tüketim sırası korunarak, sıranın sonuna ayrı lot(lar) olarak eklenir. İadenin
  maliyeti bu parçaların maliyet toplamı, geliri iade adedi × o çıkışın satış birim
  fiyatıdır.
- **Raporlar:** toplamlar ve farklar yuvarlanmamış değerlerden hesaplanır, sonra
  bir kez yuvarlanır. Hareket dosyasında ürün dosyasında olmayan bir SKU varsa
  (hangi tarihte olursa olsun) hata. Ürün CSV'si v1 biçimindedir; `adet` sütunu bu
  komutlarda kullanılmaz — stok yalnızca hareketlerden gelir.
- **CLI hataları:** stderr'e `hata: ...`, çıkış kodu 2, stdout boş.

## Definition of Done + test strategy
Her adım kendi testleriyle gelir; `python3 -m pytest -q` tüm depoda yeşil olmalı.
CLI davranışı `subprocess` ile gerçek komut çalıştırılarak doğrulanır.

## Known limits (deliberately out of scope)
- Tedarikçiye iade, sayım farkı ve depo transferi yok.
- İade yalnızca en son çıkışa karşı; daha eski bir satışın iadesi desteklenmez.
