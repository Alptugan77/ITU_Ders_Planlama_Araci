#!/usr/bin/env python3
"""Palet kontrast ölçümü (Faz 43).

Tasarım sistemi bir taban koyuyor: *"Yazı her temada, düştüğü her zeminde
≥4.5:1; denetim kenarı ve odak halkası ≥3:1."* Bu araç o tabanı ÖLÇÜYOR.

Paleti **`itucap.tasarim`dan okuyor** (Faz 56'dan beri CSS de oradan
üretiliyor) — elle kopyalanmış bir liste değil; bir jeton değişince ölçüm
de değişir. Çiftler aşağıda BEYAN edilmiş: hangi yazının
hangi zemine düştüğü koddan çıkarılamaz, o yüzden burada yazılı ve her satır
nerede kullanıldığını söylüyor.

    python tools/kontrast_olcumu.py          # tabanı tutmayan varsa çıkış 1
    python tools/kontrast_olcumu.py --hepsi  # geçenleri de dök

⚠️ Bu araç "tasarım güzel mi" demiyor; yalnız okunabilirlik tabanını tutuyor.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

KOK = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK / "tools"))

from ton_merdiveni import hex2rgb, kontrast          # noqa: E402

UI = KOK / "src" / "itucap" / "ui.py"

YAZI_TABANI = 4.5      # WCAG AA, normal boy yazı
BUYUK_TABANI = 3.0     # ≥24px ya da ≥18.66px kalın
KENAR_TABANI = 3.0     # denetim kenarı, odak halkası, ayırıcı çizgi

# (yazı/kenar jetonu, zemin jetonu, taban, nerede)
CIFTLER = [
    ("ink",    "ground",    YAZI_TABANI, "gövde yazısı"),
    ("ink",    "surface",   YAZI_TABANI, "kart içi gövde"),
    ("ink",    "surface-2", YAZI_TABANI, "not kutusu, ikincil yüzey"),
    ("ink-2",  "ground",    YAZI_TABANI, "açıklama, uzun metin"),
    ("ink-2",  "surface",   YAZI_TABANI, "kart içi açıklama"),
    ("ink-2",  "surface-2", YAZI_TABANI, "not kutusu açıklaması"),
    ("ink-3",  "ground",    YAZI_TABANI, "meta, ipucu, CRN"),
    ("ink-3",  "surface",   YAZI_TABANI, "kart içi meta"),
    ("ink-3",  "surface-2", YAZI_TABANI, "kaydedilen kartta CRN"),
    ("seal",   "ground",    YAZI_TABANI, "bağlantı, eyebrow"),
    ("seal",   "surface",   YAZI_TABANI, "kart içi bağlantı"),
    ("seal",   "seal-soft", YAZI_TABANI, "seçili kip/sekme yazısı"),
    ("danger", "ground",    YAZI_TABANI, "çakışma, kredi aşımı"),
    ("danger", "surface-2", YAZI_TABANI, "uyarı kutusunda hata"),
    ("warn",   "ground",    YAZI_TABANI, "bayat veri uyarısı"),
    # Faz 56 — şubenin yeri rozeti (ızgara bloğunda, kendi zemininde).
    ("danger", "surface",   YAZI_TABANI, "\"dolu\" rozeti"),
    ("warn",   "surface",   YAZI_TABANI, "\"son N\" rozeti"),
    ("warn-ink", "warn-soft", YAZI_TABANI, "uyarı kutusu yazısı"),
    ("anadal-ink", "anadal-soft", YAZI_TABANI, "anadal bloğu yazısı"),
    ("cap-ink",    "cap-soft",    YAZI_TABANI, "ÇAP bloğu yazısı"),
    # Faz 56 — çevrimiçi blok dolgusuz: rolün mürekkebi zeminin üstünde.
    ("anadal-ink", "ground", YAZI_TABANI, "çevrimiçi anadal bloğu"),
    ("cap-ink",    "ground", YAZI_TABANI, "çevrimiçi ÇAP bloğu"),
    ("yandal-ink", "ground", YAZI_TABANI, "çevrimiçi yandal bloğu"),
    ("yandal-ink", "yandal-soft", YAZI_TABANI, "yandal bloğu yazısı"),
    ("ground", "seal",      YAZI_TABANI, "seçili sekmede yazı (ters)"),
    # Faz 57 — yol haritası: dönem kartı surface-2, "bu dönem" kartı seal-soft.
    ("warn",   "surface-2", YAZI_TABANI, "dönem kartında uyarı"),
    ("warn",   "seal-soft", YAZI_TABANI, "bu dönem kartında uyarı"),
    ("ink-3",  "seal-soft", YAZI_TABANI, "bu dönem kartında ders adı"),
    ("anadal", "surface",   YAZI_TABANI, "\"planındaki bitişle aynı ✓\" (--ok = --anadal)"),
    # Kenar ve halka — 3:1
    ("border-strong", "ground",  KENAR_TABANI, "cetvel, tablo çizgisi"),
    ("border-strong", "surface", KENAR_TABANI, "kart kenarı"),
    # Faz 56 — denetim kenarı cetvelden ayrıldı; düştüğü dört yüzeyde ölçülür.
    ("border-control", "ground",    KENAR_TABANI, "düğme kenarı"),
    ("border-control", "surface",   KENAR_TABANI, "kart içi düğme/alan kenarı"),
    ("border-control", "surface-2", KENAR_TABANI, "not kutusunda düğme"),
    ("border-control", "seal-soft", KENAR_TABANI, "üzerine gelinen düğme"),
    ("seal",   "ground",    KENAR_TABANI, "odak halkası"),
    ("anadal", "ground",    KENAR_TABANI, "anadal şeridi"),
    ("cap",    "ground",    KENAR_TABANI, "ÇAP şeridi"),
    ("yandal", "ground",    KENAR_TABANI, "yandal şeridi"),
]


def palet() -> dict[str, dict[str, str]]:
    """Gece ve gündüz paleti — `itucap.tasarim`dan (Faz 56).

    ★ Faz 43'te `ui.py`'nin `<style>` bloğundan düzenli ifadeyle okunuyordu;
    Faz 56'da palet tek kaynağa taşındı ve CSS ondan üretiliyor. Araç artık
    CSS'in KAYNAĞINI okuyor, kopyasını değil.
    """
    sys.path.insert(0, str(KOK / "src"))
    from itucap import tasarim as T

    def blok(tema: str) -> dict[str, str]:
        return {k: v for k, v in T.palet(tema).items()
                if re.fullmatch(r"#[0-9A-Fa-f]{6}", v)}

    return {"gece": blok("gece"), "gündüz": blok("gunduz")}


def olc(P: dict | None = None) -> list[tuple]:
    """Tabanı TUTMAYAN çiftler: (tema, yazı, zemin, oran, taban, nerede)."""
    P = P or palet()
    kotu = []
    for tema, jeton in P.items():
        for fg, bg, taban, nerede in CIFTLER:
            if fg not in jeton or bg not in jeton:
                continue          # o temada tanımlı değilse atla
            oran = kontrast(hex2rgb(jeton[fg]), hex2rgb(jeton[bg]))
            if oran < taban:
                kotu.append((tema, fg, bg, oran, taban, nerede))
    return kotu


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hepsi", action="store_true", help="geçenleri de dök")
    a = ap.parse_args()
    P = palet()

    sayi = 0
    for tema, jeton in P.items():
        if a.hepsi:
            print(f"\n=== {tema} ===")
        for fg, bg, taban, nerede in CIFTLER:
            if fg not in jeton or bg not in jeton:
                if a.hepsi:
                    print(f"  {fg:14s} / {bg:12s}  — jeton yok")
                continue
            sayi += 1
            oran = kontrast(hex2rgb(jeton[fg]), hex2rgb(jeton[bg]))
            if a.hepsi:
                isaret = "✅" if oran >= taban else "❌"
                print(f"  {isaret} {fg:14s} / {bg:12s} {oran:5.2f} "
                      f"(taban {taban}) · {nerede}")

    kotu = olc(P)
    print(f"\n{sayi} çift ölçüldü, iki temada.")
    if kotu:
        print("\nTABAN ALTINDA:")
        for tema, fg, bg, oran, taban, nerede in kotu:
            print(f"  ❌ {tema:6s} {fg} / {bg} → {oran:.2f} "
                  f"(taban {taban}) · {nerede}")
        return 1
    print("✅ Bütün çiftler tabanın üstünde.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
