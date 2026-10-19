from decimal import Decimal

from .fiyat import kdvli, tl_bicimle


def rapor_satirlari(urunler) -> list[str]:
    toplamlar = [(kdvli(u.adet * u.birim_fiyat), u) for u in urunler]
    toplamlar.sort(key=lambda t: (-t[0], t[1].sku))
    satirlar = [
        f"{'! ' if u.adet < 5 else ''}{u.sku} | {u.ad} | {u.adet} | {tl_bicimle(t)}"
        for t, u in toplamlar
    ]
    genel = sum((t for t, _ in toplamlar), Decimal("0"))
    satirlar.append(f"GENEL TOPLAM: {tl_bicimle(genel)}")
    return satirlar
