"""Hidden acceptance tests for the karagoz benchmark.

Never copied into the run directory while karagoz works; the runner drops them
in afterwards and runs them from the project root. They check the spec in
plan/steps/*.md end to end, independent of whatever tests the Workers wrote.
"""
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from stokcu.fiyat import kdvli, tl_bicimle
from stokcu.model import StokHatasi, Urun, stok_yukle


def run_cli(tmp_path, body):
    p = tmp_path / "stok.csv"
    p.write_text(body, encoding="utf-8")
    return subprocess.run(
        [sys.executable, "-m", "stokcu", "rapor", str(p)],
        capture_output=True, text=True, cwd=Path.cwd(),
    )


@pytest.mark.parametrize("value,expected", [
    ("1234.5", "1.234,50 TL"),
    ("0", "0,00 TL"),
    ("1000000", "1.000.000,00 TL"),
    ("-12.345", "-12,35 TL"),
    ("999.995", "1.000,00 TL"),
    ("7.1", "7,10 TL"),
])
def test_tl_bicimle(value, expected):
    assert tl_bicimle(Decimal(value)) == expected


def test_kdvli_rounding():
    assert kdvli(Decimal("10.00")) == Decimal("12.00")
    assert kdvli(Decimal("0.125"), Decimal("0")) == Decimal("0.13")
    assert kdvli(Decimal("33.33")) == Decimal("40.00")
    with pytest.raises(ValueError):
        kdvli(Decimal("-1"))


@pytest.mark.parametrize("kwargs", [
    dict(sku="ab-1234", ad="x", adet=1, birim_fiyat=Decimal("1")),
    dict(sku="ABC-123", ad="x", adet=1, birim_fiyat=Decimal("1")),
    dict(sku="ABC-1234", ad="   ", adet=1, birim_fiyat=Decimal("1")),
    dict(sku="ABC-1234", ad="x", adet=-1, birim_fiyat=Decimal("1")),
    dict(sku="ABC-1234", ad="x", adet=1, birim_fiyat=Decimal("-0.01")),
])
def test_urun_validation(kwargs):
    with pytest.raises(ValueError):
        Urun(**kwargs)


def test_loader_line_numbers(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text("sku,ad,adet,birim_fiyat\nAAA-0001,a,1,1\nAAA-0002,b,1,1\n"
                 "AAA-0003,c,x,1\n", encoding="utf-8")
    with pytest.raises(StokHatasi) as ei:
        stok_yukle(p)
    assert ei.value.satir_no == 4
    assert str(ei.value).startswith("satır 4:")


def test_loader_bad_header(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text("sku,ad,adet\nAAA-0001,a,1\n", encoding="utf-8")
    with pytest.raises(StokHatasi) as ei:
        stok_yukle(p)
    assert ei.value.satir_no == 1


def test_loader_header_only(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text("sku,ad,adet,birim_fiyat\n", encoding="utf-8")
    assert stok_yukle(p) == []


def test_cli_report(tmp_path):
    r = run_cli(tmp_path,
                "sku,ad,adet,birim_fiyat\n"
                "KLM-0001,Kalem,100,2.50\n"      # 250.00 -> 300.00
                "DFT-0002,Defter,3,40\n"         # 120.00 -> 144.00, low stock
                "SLG-0003,Silgi,10,30\n"         # 300.00 -> 360.00
                "CNT-0004,Çanta,2,150\n")        # 300.00 -> 360.00, low stock
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines() == [
        "! CNT-0004 | Çanta | 2 | 360,00 TL",
        "SLG-0003 | Silgi | 10 | 360,00 TL",
        "KLM-0001 | Kalem | 100 | 300,00 TL",
        "! DFT-0002 | Defter | 3 | 144,00 TL",
        "GENEL TOPLAM: 1.164,00 TL",
    ]


def test_cli_bad_row(tmp_path):
    r = run_cli(tmp_path,
                "sku,ad,adet,birim_fiyat\nKLM-0001,Kalem,1,1\nDFT-0002,Defter,-1,1\n")
    assert r.returncode == 2
    assert r.stdout == ""
    assert r.stderr.startswith("hata: satır 3:")


def test_cli_missing_file(tmp_path):
    r = subprocess.run([sys.executable, "-m", "stokcu", "rapor",
                        str(tmp_path / "yok.csv")], capture_output=True, text=True)
    assert r.returncode == 2
    assert r.stdout == ""
    assert "hata: dosya bulunamadı:" in r.stderr
