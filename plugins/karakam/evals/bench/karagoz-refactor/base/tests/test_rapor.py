import subprocess
import sys


def calistir(tmp_path, govde):
    p = tmp_path / "stok.csv"
    p.write_text(govde, encoding="utf-8")
    return subprocess.run([sys.executable, "-m", "stokcu", "rapor", str(p)],
                          capture_output=True, text=True)


def test_rapor_cli(tmp_path):
    r = calistir(tmp_path, "sku,ad,adet,birim_fiyat\n"
                           "KLM-0001,Kalem,100,2.50\nDFT-0002,Defter,3,40\n")
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines() == [
        "KLM-0001 | Kalem | 100 | 300,00 TL",
        "! DFT-0002 | Defter | 3 | 144,00 TL",
        "GENEL TOPLAM: 444,00 TL",
    ]


def test_rapor_hatali_satir(tmp_path):
    r = calistir(tmp_path, "sku,ad,adet,birim_fiyat\nKLM-0001,Kalem,-1,1\n")
    assert r.returncode == 2
    assert r.stdout == ""
    assert r.stderr.startswith("hata: satır 2:")
