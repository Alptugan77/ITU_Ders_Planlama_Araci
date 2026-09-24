#!/usr/bin/env python3
"""Tahmini zorluğun SABİT tablolarını gerçek katalogdan üretir (Faz 86).

`notlar.ZORLUK_SABIT` katalogda yeterli ders yokken (vitrin, kısmi çekim)
kullanılan 21 noktalık yüzdelik tablolarıdır: FF oranı, not ortalaması ve
birleşik puan. Bu araç, not dağılımı TAM çekilmiş bir veritabanından aynı
yöntemle (`notlar.zorluk_olcegi`) ölçüp yapıştırılacak metni basar.

    python tools/zorluk_olcegi.py data/reference.sqlite3
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from itucap import notlar as ND  # noqa: E402


def main(yol: str) -> int:
    con = sqlite3.connect(yol)
    olcek = ND.zorluk_olcegi(con)
    if olcek.kaynak != "katalog":
        print(f"⚠ Katalogda {ND.ZORLUK_CANLI_MIN} dersten az derecelenebilir ders var; "
              "tablo üretilmedi.", file=sys.stderr)
        return 1
    print(f"# {olcek.n} ders")
    for ad, liste in (("ff", olcek.ff), ("ort", olcek.ort), ("skor", olcek.skor)):
        tablo = ND._yuzdelikler(list(liste))
        print(f'    "{ad}": ({", ".join(repr(round(x, 3)) for x in tablo)}),')
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "data/reference.sqlite3"))
