"""Hidden acceptance tests for the karagoz fifo scenario (stokcu v3).

Never visible to the agents; the runner drops them in after the run. Every rule
they check is stated in the plan, but the Observer checks name the rules
without examples. Each rule has a tempting shortcut that fails here:
ASCII-only, zero-padded dates (`\\d` and int() accept other digits); FIFO
returns that bring back the *last-consumed* units as separate lots, only
against the latest issue; same-day order by file line, not by type; strict
number formats (Decimal() accepts NaN, exponents and spaces); totals rounded
from exact sums; processing only up to the cut-off date; error messages that
name the file.
"""
import subprocess
import sys
from datetime import date
from decimal import Decimal as D

import pytest

from stokcu import tarih
from stokcu.degerleme import degerle
from stokcu.fifo import Defter, Hareket, isle_hepsi
from stokcu.hareket import hareket_yukle
from stokcu.kar import aylik_kar
from stokcu.model import StokHatasi, Urun

URUNLER = ("sku,ad,adet,birim_fiyat\n"
           "KLM-0001,Kalem,0,5\nDFT-0002,Defter,0,40\nSLG-0003,Silgi,0,3\n")
HAREKETLER = ("tarih,sku,tur,adet,birim_fiyat\n"
              "05.01.2024,KLM-0001,giris,10,1.00\n"   # 2
              "2024-01-03,KLM-0001,giris,5,0.80\n"    # 3  earlier date, later line
              "10.01.2024,KLM-0001,cikis,8,2.50\n"    # 4
              "10.01.2024,DFT-0002,giris,4,20\n"      # 5
              "15.01.2024,KLM-0001,iade,4,\n"         # 6  spans two consumed lots
              "01.02.2024,KLM-0001,cikis,6,3\n"       # 7
              "2024-02-10,DFT-0002,cikis,3,35\n"      # 8
              "05.03.2024,KLM-0001,iade,1,\n")        # 9  against line 7 only


def dosyalar(tmp_path, urunler=URUNLER, hareketler=HAREKETLER):
    u, h = tmp_path / "urunler.csv", tmp_path / "hareketler.csv"
    u.write_text(urunler, encoding="utf-8")
    h.write_text(hareketler, encoding="utf-8")
    return u, h


def cli(*args):
    return subprocess.run([sys.executable, "-m", "stokcu", *map(str, args)],
                          capture_output=True, text=True)


def H(no, tur, adet, fiyat=None, gun=1, sku="AAA-0001"):
    return Hareket(no, date(2024, 1, gun), sku, tur, adet, None if fiyat is None else D(fiyat))


# --- tarih ---------------------------------------------------------------

@pytest.mark.parametrize("s,beklenen", [
    ("29.02.2024", date(2024, 2, 29)), ("2024-02-29", date(2024, 2, 29)),
    ("01.12.1999", date(1999, 12, 1)), ("1999-12-01", date(1999, 12, 1)),
])
def test_tarih_gecerli(s, beklenen):
    assert tarih.coz(s) == beklenen


@pytest.mark.parametrize("s", [
    "29.02.2023", "2024-02-30", "31.04.2024", "1.02.2024", "01.2.2024", "2024-2-01",
    "01.02.24", " 01.02.2024", "01.02.2024 ", "2024/02/01", "01-02-2024", "",
    "٠١.٠٢.٢٠٢٤",   # Arabic-Indic digits
    "０１.０２.２０２４",   # full-width digits
])
def test_tarih_gecersiz(s):
    with pytest.raises(ValueError):
        tarih.coz(s)


def test_ay_coz():
    assert tarih.ay_coz("2024-02") == (2024, 2)
    for s in ("2024-13", "2024-00", "2024-2", "24-02", "2024-02-01", "02.2024",
              "٢٠٢٤-٠٢"):
        with pytest.raises(ValueError):
            tarih.ay_coz(s)


# --- fifo ----------------------------------------------------------------

def test_fifo_kismi_lot_ve_iade_parcalari():
    d = Defter()
    assert d.isle(H(2, "giris", 2, "1")).maliyet == D("2")
    d.isle(H(3, "giris", 3, "2"))
    s = d.isle(H(4, "cikis", 5, "10"))
    assert (s.maliyet, s.gelir) == (D("8"), D("50"))
    assert d.kalan("AAA-0001") == []
    s = d.isle(H(5, "iade", 1))                 # the last consumed unit: 1@2
    assert (s.maliyet, s.gelir) == (D("2"), D("10"))
    assert d.kalan("AAA-0001") == [(1, D("2"))]
    s = d.isle(H(6, "iade", 3))                 # next ones back: 1@1 then 2@2, in consumption order
    assert (s.maliyet, s.gelir) == (D("5"), D("30"))
    assert d.kalan("AAA-0001") == [(1, D("2")), (1, D("1")), (2, D("2"))]
    with pytest.raises(StokHatasi) as e:
        d.isle(H(7, "iade", 2))                 # only 1 unit of that issue is left to return
    assert e.value.satir_no == 7
    s = d.isle(H(8, "cikis", 2, "10"))
    assert s.maliyet == D("3") and d.kalan("AAA-0001") == [(2, D("2"))]


def test_fifo_lotlar_birlesmez_ve_kismi_lot_ayri_kalir():
    d = Defter()
    d.isle(H(2, "giris", 1, "5"))
    d.isle(H(3, "giris", 1, "5"))
    assert d.kalan("AAA-0001") == [(1, D("5")), (1, D("5"))]
    d.isle(H(4, "giris", 4, "7"))
    d.isle(H(5, "cikis", 3, "9"))               # 1@5, 1@5, 1@7
    d.isle(H(6, "iade", 1))                     # 1@7 back, as its own lot at the end
    assert d.kalan("AAA-0001") == [(3, D("7")), (1, D("7"))]
    assert d.kalan("YOK-0001") == []


def test_fifo_iade_yalnizca_son_cikisa():
    d = Defter()
    with pytest.raises(StokHatasi) as e:
        d.isle(H(2, "iade", 1))
    assert e.value.satir_no == 2
    d.isle(H(3, "giris", 10, "1"))
    d.isle(H(4, "cikis", 5, "2"))
    d.isle(H(5, "cikis", 1, "2"))
    with pytest.raises(StokHatasi) as e:
        d.isle(H(6, "iade", 2))                 # the latest issue was 1 unit
    assert e.value.satir_no == 6


def test_fifo_yetersiz_stok_ve_sku_ayri():
    d = Defter()
    d.isle(H(2, "giris", 3, "1", sku="AAA-0001"))
    with pytest.raises(StokHatasi) as e:
        d.isle(H(3, "cikis", 1, "1", sku="BBB-0002"))
    assert e.value.satir_no == 3
    with pytest.raises(StokHatasi):
        d.isle(H(4, "cikis", 4, "1"))
    assert d.kalan("AAA-0001") == [(3, D("1"))]     # a rejected issue changes nothing


def test_isle_hepsi_sira_ve_sinir():
    hs = [H(4, "cikis", 1, "3", gun=2), H(3, "giris", 1, "1", gun=2),
          H(2, "giris", 1, "2", gun=5)]
    defter, sonuclar = isle_hepsi(hs)
    assert [s.hareket.satir_no for s in sonuclar] == [3, 4, 2]
    assert sonuclar[1].maliyet == D("1")
    defter, sonuclar = isle_hepsi(hs, date(2024, 1, 2))
    assert [s.hareket.satir_no for s in sonuclar] == [3, 4]
    # same day: file order decides, even when the issue comes first
    with pytest.raises(StokHatasi) as e:
        isle_hepsi([H(3, "giris", 1, "1"), H(2, "cikis", 1, "1")])
    assert e.value.satir_no == 2


# --- hareket_yukle -------------------------------------------------------

def test_hareket_yukle(tmp_path):
    _, h = dosyalar(tmp_path)
    hs = hareket_yukle(h)
    assert [x.satir_no for x in hs] == list(range(2, 10))
    assert hs[1] == Hareket(3, date(2024, 1, 3), "KLM-0001", "giris", 5, D("0.80"))
    assert hs[4].birim_fiyat is None and hs[4].tur == "iade"


@pytest.mark.parametrize("satir", [
    "05.01.2024,KLM-0001,giris,1,NaN", "05.01.2024,KLM-0001,giris,1,Infinity",
    "05.01.2024,KLM-0001,giris,1,1e2", "05.01.2024,KLM-0001,giris,1,-1",
    "05.01.2024,KLM-0001,giris,1, 5", "05.01.2024,KLM-0001,giris,1,5,5",
    "05.01.2024,KLM-0001,giris,1,", "05.01.2024,KLM-0001,cikis,1,.5",
    "05.01.2024,KLM-0001,iade,1,3", "05.01.2024,KLM-0001,giris,0,1",
    "05.01.2024,KLM-0001,giris,3.0,1", "05.01.2024,KLM-0001,giris,+3,1",
    "05.01.2024,KLM-0001,giris,٣,1", "1.1.2024,KLM-0001,giris,1,1",
    "31.02.2024,KLM-0001,giris,1,1", "05.01.2024,klm-0001,giris,1,1",
    "05.01.2024,KLM-0001,GIRIS,1,1", "05.01.2024,KLM-0001,giris,1",
])
def test_hareket_yukle_hatalar(tmp_path, satir):
    _, h = dosyalar(tmp_path, hareketler="tarih,sku,tur,adet,birim_fiyat\n"
                                         "05.01.2024,KLM-0001,giris,1,1\n" + satir + "\n")
    with pytest.raises(StokHatasi) as e:
        hareket_yukle(h)
    assert e.value.satir_no == 3


def test_hareket_basligi(tmp_path):
    _, h = dosyalar(tmp_path, hareketler="tarih,sku,tur,adet\n05.01.2024,KLM-0001,giris,1\n")
    with pytest.raises(StokHatasi) as e:
        hareket_yukle(h)
    assert e.value.satir_no == 1


# --- degerle / kar (functions) ------------------------------------------

def urunler(*skus):
    return [Urun(s, s.lower(), 0, D("1")) for s in skus]


def test_degerle_toplam_kesin_toplamdan_yuvarlanir():
    hs = [Hareket(i + 2, date(2024, 1, 1), s, "giris", 1, D("1.005"))
          for i, s in enumerate(("AAA-0001", "BBB-0002", "CCC-0003"))]
    satirlar = degerle(urunler("CCC-0003", "AAA-0001", "BBB-0002"), hs)
    assert satirlar == ["AAA-0001 | aaa-0001 | 1 | 1,01 TL", "BBB-0002 | bbb-0002 | 1 | 1,01 TL",
                        "CCC-0003 | ccc-0003 | 1 | 1,01 TL", "TOPLAM: 3,02 TL"]


def test_bilinmeyen_sku_sinirdan_sonra_da_hata():
    hs = [Hareket(2, date(2024, 1, 1), "AAA-0001", "giris", 1, D("1")),
          Hareket(3, date(2024, 5, 1), "ZZZ-0009", "giris", 1, D("1"))]
    with pytest.raises(StokHatasi) as e:
        degerle(urunler("AAA-0001"), hs, date(2024, 1, 31))
    assert e.value.satir_no == 3
    with pytest.raises(StokHatasi):
        aylik_kar(urunler("AAA-0001"), hs, 2024, 1)


def test_kar_farki_kesin_degerlerden():
    hs = [Hareket(2, date(2024, 1, 1), "AAA-0001", "giris", 1, D("0.004")),
          Hareket(3, date(2024, 1, 2), "AAA-0001", "cikis", 1, D("1.005"))]
    assert aylik_kar(urunler("AAA-0001"), hs, 2024, 1) == [
        "AAA-0001 | gelir 1,01 TL | maliyet 0,00 TL | kar 1,00 TL",
        "TOPLAM | gelir 1,01 TL | maliyet 0,00 TL | kar 1,00 TL"]


def test_kar_ay_sonundan_sonrasini_islemez():
    hs = [Hareket(2, date(2024, 1, 1), "AAA-0001", "giris", 1, D("1")),
          Hareket(3, date(2024, 1, 31), "AAA-0001", "cikis", 1, D("2")),
          Hareket(4, date(2024, 2, 1), "AAA-0001", "cikis", 5, D("2"))]
    assert aylik_kar(urunler("AAA-0001"), hs, 2024, 1)[-1] == \
        "TOPLAM | gelir 2,00 TL | maliyet 1,00 TL | kar 1,00 TL"
    with pytest.raises(StokHatasi) as e:
        aylik_kar(urunler("AAA-0001"), hs, 2024, 2)
    assert e.value.satir_no == 4


# --- CLI end to end -------------------------------------------------------

@pytest.mark.parametrize("ek,beklenen", [
    ([], ["DFT-0002 | Defter | 1 | 20,00 TL", "KLM-0001 | Kalem | 6 | 5,80 TL",
          "SLG-0003 | Silgi | 0 | 0,00 TL", "TOPLAM: 25,80 TL"]),
    (["--tarih", "10.01.2024"], ["DFT-0002 | Defter | 4 | 80,00 TL", "KLM-0001 | Kalem | 7 | 7,00 TL",
                                 "SLG-0003 | Silgi | 0 | 0,00 TL", "TOPLAM: 87,00 TL"]),
    (["--tarih", "2024-01-09"], ["DFT-0002 | Defter | 0 | 0,00 TL", "KLM-0001 | Kalem | 15 | 14,00 TL",
                                 "SLG-0003 | Silgi | 0 | 0,00 TL", "TOPLAM: 14,00 TL"]),
])
def test_cli_degerle(tmp_path, ek, beklenen):
    u, h = dosyalar(tmp_path)
    r = cli("degerle", u, h, *ek)
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines() == beklenen


@pytest.mark.parametrize("ay,beklenen", [
    ("2024-01", ["KLM-0001 | gelir 10,00 TL | maliyet 3,20 TL | kar 6,80 TL",
                 "TOPLAM | gelir 10,00 TL | maliyet 3,20 TL | kar 6,80 TL"]),
    ("2024-02", ["DFT-0002 | gelir 105,00 TL | maliyet 60,00 TL | kar 45,00 TL",
                 "KLM-0001 | gelir 18,00 TL | maliyet 6,00 TL | kar 12,00 TL",
                 "TOPLAM | gelir 123,00 TL | maliyet 66,00 TL | kar 57,00 TL"]),
    ("2024-03", ["KLM-0001 | gelir -3,00 TL | maliyet -1,00 TL | kar -2,00 TL",
                 "TOPLAM | gelir -3,00 TL | maliyet -1,00 TL | kar -2,00 TL"]),
    ("2024-04", ["TOPLAM | gelir 0,00 TL | maliyet 0,00 TL | kar 0,00 TL"]),
])
def test_cli_kar(tmp_path, ay, beklenen):
    u, h = dosyalar(tmp_path)
    r = cli("kar", u, h, "--ay", ay)
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines() == beklenen


def hata(r, onek):
    assert r.returncode == 2 and r.stdout == "", (r.returncode, r.stdout, r.stderr)
    assert r.stderr.startswith(onek), r.stderr


def test_cli_hatalar(tmp_path):
    u, h = dosyalar(tmp_path)
    hata(cli("degerle", u, h, "--tarih", "31.02.2024"), "hata: geçersiz tarih: 31.02.2024")
    hata(cli("kar", u, h, "--ay", "2024-13"), "hata: geçersiz ay: 2024-13")
    hata(cli("degerle", tmp_path / "yok.csv", h), f"hata: dosya bulunamadı: {tmp_path / 'yok.csv'}")
    hata(cli("kar", u, tmp_path / "yok.csv", "--ay", "2024-01"),
         f"hata: dosya bulunamadı: {tmp_path / 'yok.csv'}")
    assert cli("kar", u, h).returncode == 2                     # --ay is required

    _, h2 = dosyalar(tmp_path, hareketler=HAREKETLER + "06.03.2024,KLM-0001,cikis,99,1\n")
    r = cli("degerle", u, h2)
    hata(r, f"hata: {h2}: satır 10:")
    assert "yetersiz stok" in r.stderr
    assert cli("kar", u, h2, "--ay", "2024-02").returncode == 0  # line 10 is after February

    _, h3 = dosyalar(tmp_path, hareketler=HAREKETLER.replace("0.80", "0,80"))
    hata(cli("degerle", u, h3), f"hata: {h3}: satır 3:")

    u2, _ = dosyalar(tmp_path, urunler="sku,ad,adet,birim_fiyat\nKLM-0001,,0,5\n")
    hata(cli("degerle", u2, h), f"hata: {u2}: satır 2:")


def test_rapor_hala_calisir(tmp_path):
    u, _ = dosyalar(tmp_path)
    r = cli("rapor", u)
    assert r.returncode == 0 and r.stdout.splitlines()[-1] == "GENEL TOPLAM: 0,00 TL"
