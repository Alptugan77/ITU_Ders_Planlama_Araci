#!/usr/bin/env python3
"""Paletin yazı ve kenar kontrastını ÖLÇ (Faz 43).

Faz 40'ın ton merdiveni blok yazısını ölçmüştü; bu araç paletin geri kalanını
ölçüyor. Paleti **`ui.py`'den okuyor** (`ton_merdiveni.palet()` ile aynı
okuma — elle kopyalanmış bir liste değil), her yazı rengini **düştüğü her
zeminde** iki temada da hesaplıyor:

  1. yazı           — taban 4.5 (WCAG AA, küçük metin)
  2. denetim kenarı — taban 3.0 (WCAG 1.4.11: düğme ve alan sınırı, odak halkası)

  python tools/kontrast_olcumu.py          # tablo + başarısızlar

⚠️ Çiftler "bu renk nerede kullanılıyor" sorusunun cevabı; yeni bir yerde
yeni bir zemine yazı konursa buraya da eklenmeli — yoksa ölçülmez.
`tests/test_faz43_tasarim_sistemi.py` bu listeyi kullanıyor.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import ton_merdiveni as T  # noqa: E402

YAZI_TABANI = 4.5
KENAR_TABANI = 3.0

ZEMIN = ("--ground", "--surface", "--surface-2")

# yazı rengi → üstüne yazıldığı zeminler (kullanım yerleri yorumda)
YAZI = {
    "--ink": ZEMIN,
    # notlar, adım açıklaması, READY kademe kutusu, uyarı kutusu
    "--ink-2": ZEMIN + ("--seal-soft", "--cap-soft", "--warn-soft"),
    # 88 yerde küçük yazı: ipucu, sayaç, CRN, "tamamlandı", izle rozeti
    "--ink-3": ZEMIN + ("--seal-soft", "--cap-soft", "--warn-soft"),
    # eyebrow, tablo başlığı, etiket, bağlantı, seçili kip
    "--seal": ZEMIN + ("--seal-soft",),
    # yüzde, "+9", kategori rozeti
    "--anadal": ("--surface", "--surface-2", "--anadal-soft"),
    "--cap": ("--surface", "--surface-2", "--cap-soft"),
    "--yandal": ("--surface", "--surface-2", "--yandal-soft"),
    # rol etiketi
    "--anadal-ink": ("--anadal-soft",),
    "--cap-ink": ("--cap-soft",),
    "--yandal-ink": ("--yandal-soft",),
    "--danger": ZEMIN,
    "--warn": ZEMIN,
    "--warn-ink": ("--warn-soft",),
    # seçili sekme, birincil düğme, bildirim: zemin rengi mühür üstünde
    "--ground": ("--seal", "--seal-hover"),
}

# düğme / alan kenarı ve odak halkası → oturduğu zeminler
KENAR = {
    "--border-strong": ZEMIN,
    "--seal": ZEMIN,
}


def olc(P=None):
    """[(tema, tür, ön, zemin, oran, taban)] — tür: 'yazı' | 'kenar'."""
    P = P or T.palet()
    satirlar = []
    for tema, J in P.items():
        for tur, ciftler, taban in (("yazı", YAZI, YAZI_TABANI),
                                     ("kenar", KENAR, KENAR_TABANI)):
            for on, zeminler in ciftler.items():
                for z in zeminler:
                    oran = T.kontrast(T.hex2rgb(J[on]), T.hex2rgb(J[z]))
                    satirlar.append((tema, tur, on, z, oran, taban))
    return satirlar


def main() -> int:
    satirlar = olc()
    kotu = [s for s in satirlar if s[4] < s[5]]
    for tema, tur, on, z, oran, taban in satirlar:
        isaret = "✓" if oran >= taban else "✗"
        print(f"{isaret} {tema:7} {tur:5} {on:15} / {z:14} {oran:5.2f}  (taban {taban})")
    print(f"\n{len(satirlar)} çift · {len(kotu)} taban altında")
    return 1 if kotu else 0


if __name__ == "__main__":
    raise SystemExit(main())
