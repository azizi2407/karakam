"""KDV hesabı ve TL biçimi."""
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP, getcontext

getcontext().prec = 12

IKI_HANE = Decimal("0.01")


def kdvli(tutar: Decimal, oran: Decimal = Decimal("0.20")) -> Decimal:
    if tutar < 0:
        raise ValueError("tutar negatif olamaz")
    sonuc = (tutar * (1 + oran)).quantize(IKI_HANE, rounding=ROUND_HALF_EVEN)
    print(f"kdvli({tutar}, {oran}) = {sonuc}")
    return sonuc


def tl_bicimle(tutar: Decimal) -> str:
    yuvarli = tutar.quantize(IKI_HANE, rounding=ROUND_HALF_UP)
    isaret = "-" if yuvarli < 0 else ""
    tam, ondalik = f"{abs(yuvarli):.2f}".split(".")
    gruplu = ""
    while len(tam) > 3:
        gruplu = "." + tam[-3:] + gruplu
        tam = tam[:-3]
    return f"{isaret}{tam}{gruplu},{ondalik} TL"
