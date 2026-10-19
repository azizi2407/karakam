from decimal import ROUND_HALF_UP, Decimal

KURUS = Decimal("0.01")


def kdvli(tutar: Decimal, oran: Decimal = Decimal("0.20")) -> Decimal:
    if tutar < 0 or oran < 0:
        raise ValueError("tutar ve oran negatif olamaz")
    return (tutar * (1 + oran)).quantize(KURUS, ROUND_HALF_UP)


def tl_bicimle(tutar: Decimal) -> str:
    t = tutar.quantize(KURUS, ROUND_HALF_UP)
    tam, kurus = f"{abs(t):.2f}".split(".")
    gruplar = []
    while len(tam) > 3:
        gruplar.insert(0, tam[-3:])
        tam = tam[:-3]
    gruplar.insert(0, tam)
    return ("-" if t < 0 else "") + ".".join(gruplar) + "," + kurus + " TL"
