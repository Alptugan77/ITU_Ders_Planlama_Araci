#!/usr/bin/env python3
"""Uygulama simgesi — ana ekrana ekleme, sekme simgesi (Faz 130).

    python tools/simge_uret.py          # web/simge/ altını yeniden yazar

Simge, aracın kendi diliyle çizilmiş bir HAFTALIK PROGRAM: lacivert (seal)
zeminde kalın bir cetvel (Şematik'in bölüm cetveli) ve altında ders
blokları — biri anadal, biri ÇAP renginde. Yazı yok: 48 px'te harf okunmuyor,
blok okunuyor. Köşe yok, gölge yok, degrade yok (tasarım sisteminin kuralı).

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

# tasarim.RENKLER'den (gündüz seal; veri renkleri gece tonları — lacivert
# zeminde gündüz tonları kararıyor, gece tonları seçiliyor).
SEAL = "#3B4E9E"
BEYAZ = "#FFFFFF"
SOLUK = "#5A6BB0"        # beyazın seal üstünde %15'i — boş saat
ANADAL = "#6FCDB3"
CAP = "#E3AE6C"

# Haftalık ızgara: 3 sütun × 3 satır; dolu hücreler ders, soluklar boş saat.
DUZEN = [
    [ANADAL, SOLUK, BEYAZ],
    [SOLUK, CAP, SOLUK],
    [BEYAZ, SOLUK, ANADAL],
]


def sekiller(boy: float = 512, olcek: float = 1.0) -> list[tuple[float, float, float, float, str]]:
    """(x, y, g, y, renk) — `olcek` < 1 içeriği merkeze doğru küçültür
    (maskable simgenin güvenli dairesi için)."""
    k = boy / 512
    # İçerik kutusu (512 tabanında): 104..408 yatay, 100..412 dikey.
    sol, ust, gen = 104, 100, 304
    cetvel = 40                 # cetvel kalınlığı
    bosluk = 26                 # cetvel ile ızgara arası
    ara = 20                    # hücre arası
    hucre = (gen - 2 * ara) / 3
    izgara_ust = ust + cetvel + bosluk
    satir = (412 - izgara_ust - 2 * ara) / 3
    sek = [(sol, ust, gen, cetvel, BEYAZ)]
    for i, sira in enumerate(DUZEN):
        for j, renk in enumerate(sira):
            sek.append((sol + j * (hucre + ara), izgara_ust + i * (satir + ara),
                        hucre, satir, renk))
    m = 256
    return [(((x - m) * olcek + m) * k, ((y - m) * olcek + m) * k,
             g * olcek * k, h * olcek * k, r) for x, y, g, h, r in sek]


def svg(olcek: float = 1.0) -> str:
    govde = "".join(f'<rect x="{x:g}" y="{y:g}" width="{g:g}" height="{h:g}" fill="{r}"/>'
                    for x, y, g, h, r in sekiller(512, olcek))
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
            f'<rect width="512" height="512" fill="{SEAL}"/>{govde}</svg>\n')


def png(boy: int, olcek: float = 1.0) -> bytes:
    from PIL import Image, ImageDraw
    ss = 4                                   # kenar yumuşatma: 4x çiz, küçült
    im = Image.new("RGB", (boy * ss, boy * ss), SEAL)
    d = ImageDraw.Draw(im)
    for x, y, g, h, r in sekiller(boy * ss, olcek):
        d.rectangle([round(x), round(y), round(x + g) - 1, round(y + h) - 1], fill=r)
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
