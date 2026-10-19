from decimal import Decimal

import pytest

from stokcu.fiyat import kdvli, tl_bicimle


def test_kdvli():
    assert kdvli(Decimal("10.00")) == Decimal("12.00")
    assert kdvli(Decimal("0.125"), Decimal("0")) == Decimal("0.13")
    with pytest.raises(ValueError):
        kdvli(Decimal("-1"))


@pytest.mark.parametrize("deger,beklenen", [
    ("1234.5", "1.234,50 TL"), ("0", "0,00 TL"), ("1000000", "1.000.000,00 TL"),
    ("-12.345", "-12,35 TL"),
])
def test_tl_bicimle(deger, beklenen):
    assert tl_bicimle(Decimal(deger)) == beklenen
