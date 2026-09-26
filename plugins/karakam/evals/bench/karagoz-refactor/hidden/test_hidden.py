"""Hidden acceptance tests for the karagoz refactor scenario (stokcu v2).

Never visible to the agents; the runner drops them in after the run. They
check the finished product end to end — including the two places the plan is
deliberately flawed (step 01 labelled `low` effort although Turkish casing is a
trap for str.lower(); step 02's files_touched omitting tests/test_rapor.py).
"""
import subprocess
import sys
from decimal import Decimal

import pytest

from stokcu.metin import eslesir, tr_kucuk
from stokcu.model import StokHatasi, Urun, stok_yukle

V2 = "sku,ad,kategori,adet,birim_fiyat\n"
ROWS = ("ISP-0001,Isparta Gülü,Kozmetik,3,120\n"
        "IZM-0002,İzmir Lokumu,Gıda,20,15.50\n"
        "KLM-0003,Kalem Kutusu,Kırtasiye,100,2.50\n"
        "IGD-0004,IĞDIR Kayısısı,Gıda,7,40\n")


def cli(tmp_path, *args, body=None):
    argv = list(args)
    if body is not None:
        p = tmp_path / "stok.csv"
        p.write_text(body, encoding="utf-8")
        argv.insert(1, str(p))
    return subprocess.run([sys.executable, "-m", "stokcu", *argv],
                          capture_output=True, text=True)


@pytest.mark.parametrize("metin,sorgu,beklenen", [
    ("ISPARTA", "ısparta", True),
    ("ISPARTA", "isparta", False),
    ("İzmir", "izmir", True),
    ("izmir", "İZMİR", True),
    ("IĞDIR", "ığdır", True),
    ("Çanta", "ÇANTA", True),
    ("Kalem   Kutusu", " kalem kutusu ", True),
    ("Defter", "kalem", False),
    ("Defter", "", True),
])
def test_eslesir(metin, sorgu, beklenen):
    assert eslesir(metin, sorgu) is beklenen


def test_tr_kucuk():
    assert tr_kucuk("İSTANBUL") == "istanbul"
    assert tr_kucuk("ILIK") == "ılık"


def test_kategori_required():
    with pytest.raises(ValueError):
        Urun("KLM-0001", "Kalem", "  ", 1, Decimal("1"))


def test_v2_loader(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text(V2 + "KLM-0001,Kalem,Kırtasiye,1,2.50\n", encoding="utf-8")
    assert stok_yukle(p) == [Urun("KLM-0001", "Kalem", "Kırtasiye", 1, Decimal("2.50"))]


def test_v1_header_rejected(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text("sku,ad,adet,birim_fiyat\nKLM-0001,Kalem,1,1\n", encoding="utf-8")
    with pytest.raises(StokHatasi) as e:
        stok_yukle(p)
    assert e.value.satir_no == 1


def test_rapor_still_works_on_v2(tmp_path):
    r = cli(tmp_path, "rapor", body=V2 + "KLM-0001,Kalem,Kırtasiye,100,2.50\n"
                                        "DFT-0002,Defter,Kırtasiye,3,40\n")
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines() == [
        "KLM-0001 | Kalem | 100 | 300,00 TL",
        "! DFT-0002 | Defter | 3 | 144,00 TL",
        "GENEL TOPLAM: 444,00 TL",
    ]


@pytest.mark.parametrize("sorgu,beklenen", [
    ("ISPARTA", ["ISP-0001 | Isparta Gülü | Kozmetik | 3"]),
    ("İZMİR", ["IZM-0002 | İzmir Lokumu | Gıda | 20"]),
    ("ığdır", ["IGD-0004 | IĞDIR Kayısısı | Gıda | 7"]),
    ("i", ["IZM-0002 | İzmir Lokumu | Gıda | 20"]),
    ("klm", ["KLM-0003 | Kalem Kutusu | Kırtasiye | 100"]),
])
def test_ara(tmp_path, sorgu, beklenen):
    r = cli(tmp_path, "ara", sorgu, body=V2 + ROWS)
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines() == beklenen + [f"{len(beklenen)} ürün bulundu"]


def test_ara_sorted_and_empty(tmp_path):
    r = cli(tmp_path, "ara", "", body=V2 + ROWS)
    skus = [line.split(" | ")[0] for line in r.stdout.splitlines()[:-1]]
    assert skus == sorted(skus) and len(skus) == 4
    assert r.stdout.splitlines()[-1] == "4 ürün bulundu"
    r = cli(tmp_path, "ara", "zzz", body=V2 + ROWS)
    assert r.returncode == 0 and r.stdout.splitlines() == ["0 ürün bulundu"]


def test_ara_errors(tmp_path):
    r = cli(tmp_path, "ara", "x", body=V2 + "KLM-0001,Kalem,,1,1\n")
    assert r.returncode == 2 and r.stdout == "" and r.stderr.startswith("hata: satır 2:")
    r = subprocess.run([sys.executable, "-m", "stokcu", "ara",
                        str(tmp_path / "yok.csv"), "x"], capture_output=True, text=True)
    assert r.returncode == 2 and r.stdout == "" and "hata: dosya bulunamadı:" in r.stderr
