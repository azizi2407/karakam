from decimal import Decimal

import pytest

from stokcu.model import StokHatasi, Urun, stok_yukle


def yaz(tmp_path, govde):
    p = tmp_path / "stok.csv"
    p.write_text(govde, encoding="utf-8")
    return p


def test_gecerli_yukleme(tmp_path):
    p = yaz(tmp_path, "sku,ad,adet,birim_fiyat\nKLM-0001,Kalem,10,2.50\n")
    assert stok_yukle(p) == [Urun("KLM-0001", "Kalem", 10, Decimal("2.50"))]


def test_hatali_satir_numarasi(tmp_path):
    p = yaz(tmp_path, "sku,ad,adet,birim_fiyat\nKLM-0001,Kalem,1,1\nDFT-0002,Defter,x,1\n")
    with pytest.raises(StokHatasi) as e:
        stok_yukle(p)
    assert e.value.satir_no == 3


def test_baslik_hatasi(tmp_path):
    with pytest.raises(StokHatasi) as e:
        stok_yukle(yaz(tmp_path, "sku,ad\n"))
    assert e.value.satir_no == 1


@pytest.mark.parametrize("sku,ad,adet,fiyat", [
    ("klm-0001", "Kalem", 1, "1"), ("KLM-0001", " ", 1, "1"),
    ("KLM-0001", "Kalem", -1, "1"), ("KLM-0001", "Kalem", 1, "-1"),
])
def test_dogrulama(sku, ad, adet, fiyat):
    with pytest.raises(ValueError):
        Urun(sku, ad, adet, Decimal(fiyat))
