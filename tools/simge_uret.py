#!/usr/bin/env python3
"""Uygulama simgesi — ana ekrana ekleme, sekme simgesi (Faz 130).

    python tools/simge_uret.py          # web/simge/ altını yeniden yazar

Simge, aracın kendi diliyle çizilmiş bir HAFTALIK PROGRAM: mürekkep (seal)
zeminde üç gün sütunu ve sütunlarda farklı boyda ders blokları — anadal ve
ÇAP renginde, biri beyaz, ikisi boş saat. Yazı yok: 48 px'te harf okunmuyor,
blok okunuyor. Gölge yok, degrade yok; köşe Faz 133'ün kuralı.

★ Tek kaynak: geometri bir dikdörtgen listesi; PNG de SVG de ondan çıkıyor.
Elle çizilmiş iki dosya bir gün ayrışırdı.

PNG'ler depoya işleniyor (Pillow yalnız bu betiğe gerekiyor; site kurulumu ve
uygulama Pillow'suz çalışıyor). `tests/test_faz130_simge.py` dosyaların bu
betiğin çıktısıyla aynı olduğunu doğruluyor.
"""
from __future__ import annotations

import io
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEDEF = ROOT / "src" / "itucap" / "simge"

# tasarim.RENKLER'den (gündüz seal; veri renkleri gece tonları — koyu
# zeminde gündüz tonları kararıyor, gece tonları seçiliyor).
SEAL = "#26262B"
BEYAZ = "#FFFFFF"
SOLUK = "#474749"        # beyazın seal üstünde %15'i — boş saat
ANADAL = "#6FCDB3"
CAP = "#E3AE6C"

# ★ Faz 135 — kademeli bloklar. Eski simge 3×3 eşit kare ızgaraydı (cetvel +
# dokuz kare): bir tablo ya da takvim simgesi gibi okunuyordu, ders programı
# gibi değil. Programın asıl görüntüsü SÜTUNLARDA farklı boyda bloklar —
# dersler saatlere göre kayıyor. Üç gün sütunu, her birinde iki blok; köşe
# Faz 133'ün kuralı (blok 8px → 512'de 22).
# (sütun, üst, alt, renk) — 512 tabanında; içerik kutusu 108..404.
BLOKLAR = [
    (0, 108, 268, ANADAL), (0, 292, 404, SOLUK),
    (1, 108, 172, SOLUK), (1, 196, 404, BEYAZ),
    (2, 108, 236, CAP), (2, 260, 404, ANADAL),
]
KOSE = 22


def sekiller(boy: float = 512, olcek: float = 1.0) -> list[tuple[float, float, float, float, str]]:
    """(x, y, g, y, renk) — `olcek` < 1 içeriği merkeze doğru küçültür
    (maskable simgenin güvenli dairesi için)."""
    k = boy / 512
    sol, gen, ara = 108, 296, 24
    sutun = (gen - 2 * ara) / 3
    sek = [(sol + s * (sutun + ara), ust, sutun, alt - ust, renk)
           for s, ust, alt, renk in BLOKLAR]
    m = 256
    return [(((x - m) * olcek + m) * k, ((y - m) * olcek + m) * k,
             g * olcek * k, h * olcek * k, r) for x, y, g, h, r in sek]


def svg(olcek: float = 1.0) -> str:
    rx = KOSE * olcek
    govde = "".join(f'<rect x="{x:g}" y="{y:g}" width="{g:g}" height="{h:g}" rx="{rx:g}" fill="{r}"/>'
                    for x, y, g, h, r in sekiller(512, olcek))
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
            f'<rect width="512" height="512" fill="{SEAL}"/>{govde}</svg>\n')


def png(boy: int, olcek: float = 1.0) -> bytes:
    from PIL import Image, ImageDraw
    ss = 4                                   # kenar yumuşatma: 4x çiz, küçült
    im = Image.new("RGB", (boy * ss, boy * ss), SEAL)
    d = ImageDraw.Draw(im)
    for x, y, g, h, r in sekiller(boy * ss, olcek):
        d.rounded_rectangle([round(x), round(y), round(x + g) - 1, round(y + h) - 1],
                            radius=round(KOSE * olcek * boy * ss / 512), fill=r)
    im = im.resize((boy, boy), Image.LANCZOS)
    tampon = io.BytesIO()
    im.save(tampon, "PNG", optimize=True)
    return tampon.getvalue()


# Maskable: Android simgeyi daire/damla biçiminde kırpıyor; güvenli bölge
# merkezdeki %80'lik daire. İçeriğin köşesi merkezden 0,43·512 uzakta —
# 0,88 ölçekle 0,38·512.ye iniyor (sınır 0,40).
MASKABLE = 0.88

DOSYALAR = {
    "favicon.svg": lambda: svg().encode(),
    "icon-192.png": lambda: png(192),
    "icon-512.png": lambda: png(512),
    "icon-maskable-512.png": lambda: png(512, MASKABLE),
    "apple-touch-icon.png": lambda: png(180),
    "favicon-32.png": lambda: png(32),
}


def main() -> None:
    HEDEF.mkdir(parents=True, exist_ok=True)
    for ad, uret in DOSYALAR.items():
        (HEDEF / ad).write_bytes(uret())
        print(f"   {ad}")
    print(f"✅ {HEDEF}")


if __name__ == "__main__":
    main()
