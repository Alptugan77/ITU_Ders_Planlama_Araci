#!/usr/bin/env python3
"""Ders tonu merdivenini ÖLÇ (Faz 40).

`ui.py`'deki ton merdiveni tahminle değil ölçüyle seçildi. Bu araç o ölçümü
tekrar üretiyor: paleti **`itucap.tasarim`dan okuyor** (Faz 56'dan beri CSS
de oradan üretiliyor — palet değişirse ölçüm de değişsin), `color-mix(in oklab, …)`'i
Python'da aynı şekilde hesaplıyor ve her basamak için üç sayıya bakıyor:

  1. yazı kontrastı (WCAG)          — taban 4.5 (AA)
  2. zemin farkı ΔE (OKLab)         — taban 0.035; blok boş hücreden ayrılmalı
  3. basamaklar arası en küçük ΔE   — büyük olsun: "iki dersi ayırabiliyor muyum"

  python tools/ton_merdiveni.py          # şimdiki merdiveni doğrula
  python tools/ton_merdiveni.py --ara    # daha iyisi var mı diye ara

⚠️ PLAN_DISI rolü bilerek dışarıda: rengi gri (`--soft`=yüzey, `--accent`=
`--ink-3`), gri bir aileden merdiven çıkmıyor — ölçüldü, yazı 4.39 (AA altı)
ve zemin ΔE 0.021 (blok kayboluyor).
"""
from __future__ import annotations

import argparse
import itertools
import pathlib
import re
import sys

UI = pathlib.Path(__file__).resolve().parent.parent / "src" / "itucap" / "ui.py"

YAZI_TABANI = 4.5
ZEMIN_TABANI = 0.035

# ui.py'deki TON_BASAMAK ile aynı olmalı; test bunu karşılaştırıyor.
MERDIVEN = [("soft", 0), ("ground", 38),
            ("accent", 5), ("accent", 9), ("accent", 15), ("accent", 19),
            ("accent", 23), ("accent", 29), ("accent", 33)]

ROLLER = {"ANADAL": "anadal", "CAP": "cap", "YANDAL": "yandal"}


# ------------------------------------------------------------ palet okuma
def palet() -> dict[str, dict[str, str]]:
    """Gece ve gündüz paleti — `itucap.tasarim`dan (Faz 56).

    ★ Eskiden `ui.py`'nin `<style>` bloğu düzenli ifadeyle okunuyordu. Faz
    56'da palet tek kaynağa taşındı (`src/itucap/tasarim.py`) ve CSS ondan
    ÜRETİLİYOR; araç da aynı sözlüğü okuyor — üç okuyucu, tek kaynak.
    """
    sys.path.insert(0, str(UI.parents[1]))
    from itucap import tasarim as T

    def blok(tema: str) -> dict[str, str]:
        return {f"--{k}": v for k, v in T.palet(tema).items()
                if re.fullmatch(r"#[0-9A-Fa-f]{6}", v)}

    return {"gece": blok("gece"), "gündüz": blok("gunduz")}


# ------------------------------------------------------------------ renk
def hex2rgb(h: str) -> tuple[float, float, float]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lin(c: float) -> float:
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _unlin(c: float) -> float:
    c = min(1.0, max(0.0, c))
    return (12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055) * 255


def rgb2oklab(rgb):
    r, g, b = (_lin(c) for c in rgb)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l, m, s = l ** (1 / 3), m ** (1 / 3), s ** (1 / 3)
    return (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
            0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s)


def oklab2rgb(lab):
    L, a, b2 = lab
    l = (L + 0.3963377774 * a + 0.2158037573 * b2) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b2) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b2) ** 3
    return tuple(round(_unlin(c)) for c in (
        +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s))


def karistir(a_hex: str, b_hex: str, pct: float):
    """CSS `color-mix(in oklab, a, b pct%)` — aynı hesap."""
    A, B = rgb2oklab(hex2rgb(a_hex)), rgb2oklab(hex2rgb(b_hex))
    t = pct / 100
    return oklab2rgb(tuple(x * (1 - t) + y * t for x, y in zip(A, B)))


def dE(c1, c2) -> float:
    a, b = rgb2oklab(c1), rgb2oklab(c2)
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def kontrast(c1, c2) -> float:
    def lum(c):
        r, g, b = (_lin(x) for x in c)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    a, b = lum(c1), lum(c2)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


# ------------------------------------------------------------------ ölçüm
def olc(merdiven, P=None):
    """(en düşük yazı kontrastı, en düşük zemin ΔE, en küçük basamak ΔE)"""
    P = P or palet()
    yazi = zemin = adim = float("inf")
    for tema, jeton in P.items():
        for jetonad in ROLLER.values():
            soft = jeton[f"--{jetonad}-soft"]
            acc = jeton[f"--{jetonad}"]
            ink = jeton[f"--{jetonad}-ink"]
            hedefler = {"ground": jeton["--ground"], "accent": acc, "soft": soft}
            renkler = [karistir(soft, hedefler[h], p) for h, p in merdiven]
            for c in renkler:
                yazi = min(yazi, kontrast(c, hex2rgb(ink)))
                zemin = min(zemin, dE(c, hex2rgb(jeton["--ground"])))
            for x, y in itertools.combinations(renkler, 2):
                adim = min(adim, dE(x, y))
    return yazi, zemin, adim


def dokum(merdiven, P=None):
    P = P or palet()
    print(f"{len(merdiven)} basamak: {merdiven}\n")
    for tema, jeton in P.items():
        for rol, jetonad in ROLLER.items():
            y, z, a = olc(merdiven, {tema: {**jeton}})
            # tek rol için yeniden ölç
            soft, acc, ink = (jeton[f"--{jetonad}-soft"], jeton[f"--{jetonad}"],
                              jeton[f"--{jetonad}-ink"])
            hedefler = {"ground": jeton["--ground"], "accent": acc, "soft": soft}
            renkler = [karistir(soft, hedefler[h], p) for h, p in merdiven]
            y = min(kontrast(c, hex2rgb(ink)) for c in renkler)
            z = min(dE(c, hex2rgb(jeton["--ground"])) for c in renkler)
            a = min(dE(x, y2) for x, y2 in itertools.combinations(renkler, 2))
            bayrak = "  ⚠️" if y < YAZI_TABANI or z < ZEMIN_TABANI else ""
            print(f"  {rol:7s} {tema:6s} yazı≥{y:5.2f}  zeminΔE≥{z:.3f}  "
                  f"basamakΔE≥{a:.4f}{bayrak}")
    y, z, a = olc(merdiven, P)
    print(f"\nEN KÖTÜ  yazı {y:.2f} (taban {YAZI_TABANI}) · "
          f"zeminΔE {z:.3f} (taban {ZEMIN_TABANI}) · basamakΔE {a:.4f}")
    return y >= YAZI_TABANI and z >= ZEMIN_TABANI


def ara(n: int, P=None):
    """Tabanları tutan, basamak farkı en büyük n'li merdiveni ara."""
    P = P or palet()
    adaylar = ([("ground", p) for p in range(10, 50, 4)] + [("soft", 0)]
               + [("accent", p) for p in range(3, 37, 2)])

    def uygun(m):
        y, z, _ = olc(m, P)
        return y >= YAZI_TABANI and z >= ZEMIN_TABANI

    secim = [("soft", 0)]
    while len(secim) < n:
        en, skor = None, -1
        for a in adaylar:
            if a in secim:
                continue
            if uygun(secim + [a]) and olc(secim + [a], P)[2] > skor:
                en, skor = a, olc(secim + [a], P)[2]
        if en is None:
            break
        secim.append(en)
    for _ in range(3):
        for i in range(len(secim)):
            for a in adaylar:
                if a in secim:
                    continue
                aday = secim[:i] + [a] + secim[i + 1:]
                if uygun(aday) and olc(aday, P)[2] > olc(secim, P)[2]:
                    secim = aday
    return sorted(secim, key=lambda t: (t[0] != "soft", t[0], t[1]))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ara", action="store_true", help="daha iyi merdiven ara")
    ap.add_argument("--n", type=int, default=9, help="aranacak basamak sayısı")
    a = ap.parse_args()
    P = palet()
    if a.ara:
        m = ara(a.n, P)
        print(f"aranan {a.n} basamak → bulunan {len(m)}: {m}\n")
        dokum(m, P)
        return 0
    ok = dokum(MERDIVEN, P)
    print("✅ merdiven tabanları tutuyor." if ok else "❌ taban altına düşen var.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
