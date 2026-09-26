import csv
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

BASLIK = ["sku", "ad", "adet", "birim_fiyat"]


class StokHatasi(Exception):
    def __init__(self, satir_no: int, mesaj: str):
        self.satir_no = satir_no
        self.mesaj = mesaj
        super().__init__(f"satır {satir_no}: {mesaj}")


@dataclass(frozen=True)
class Urun:
    sku: str
    ad: str
    adet: int
    birim_fiyat: Decimal

    def __post_init__(self):
        if not re.fullmatch(r"[A-Z]{3}-\d{4}", self.sku):
            raise ValueError(f"geçersiz sku: {self.sku!r}")
        if not self.ad.strip():
            raise ValueError("ad boş olamaz")
        if not isinstance(self.adet, int) or self.adet < 0:
            raise ValueError(f"geçersiz adet: {self.adet!r}")
        if not isinstance(self.birim_fiyat, Decimal) or self.birim_fiyat < 0:
            raise ValueError(f"geçersiz birim fiyat: {self.birim_fiyat!r}")


def stok_yukle(yol) -> list[Urun]:
    with open(yol, encoding="utf-8", newline="") as f:
        satirlar = list(csv.reader(f))
    if not satirlar or satirlar[0] != BASLIK:
        raise StokHatasi(1, "başlık " + ",".join(BASLIK) + " olmalı")
    urunler = []
    for no, satir in enumerate(satirlar[1:], start=2):
        if len(satir) != len(BASLIK):
            raise StokHatasi(no, f"{len(BASLIK)} alan bekleniyordu")
        sku, ad, adet, fiyat = satir
        try:
            urunler.append(Urun(sku, ad, int(adet), Decimal(fiyat)))
        except (ValueError, InvalidOperation) as e:
            raise StokHatasi(no, str(e)) from None
    return urunler
