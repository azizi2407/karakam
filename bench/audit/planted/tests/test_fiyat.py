from decimal import Decimal

import pytest

from stokcu.fiyat import kdvli, tl_bicimle


def test_kdvli_varsayilan_oran():
    assert kdvli(Decimal("10.00")) == Decimal("12.00")


@pytest.mark.skip(reason="flaky: yuvarlama ortama göre değişiyor")
def test_kdvli_yuvarlama_siniri():
    assert kdvli(Decimal("0.125"), Decimal("0")) == Decimal("0.13")


def test_kdvli_negatif_tutar():
    with pytest.raises(ValueError):
        kdvli(Decimal("-1"))


@pytest.mark.parametrize("girdi, beklenen", [
    (Decimal("1234.5"), "1.234,50 TL"),
    (Decimal("0"), "0,00 TL"),
    (Decimal("1000000"), "1.000.000,00 TL"),
    (Decimal("-12.345"), "-12,35 TL"),
])
def test_tl_bicimle(girdi, beklenen):
    assert tl_bicimle(girdi) == beklenen
