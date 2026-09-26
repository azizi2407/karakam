import argparse
import sys

from .model import StokHatasi, stok_yukle
from .rapor import rapor_satirlari


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="stokcu")
    alt = parser.add_subparsers(dest="komut", required=True)
    rapor = alt.add_parser("rapor", help="KDV dahil değer raporu")
    rapor.add_argument("csv_yolu")
    args = parser.parse_args(argv)

    try:
        urunler = stok_yukle(args.csv_yolu)
    except FileNotFoundError:
        print(f"hata: dosya bulunamadı: {args.csv_yolu}", file=sys.stderr)
        return 2
    except StokHatasi as e:
        print(f"hata: {e}", file=sys.stderr)
        return 2
    for satir in rapor_satirlari(urunler):
        print(satir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
