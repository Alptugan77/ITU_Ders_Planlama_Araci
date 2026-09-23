#!/usr/bin/env python3
"""Tasarım envanteri ve denetimi (Faz 56).

Faz 56 bu araçla BAŞLADI: v1 tasarım sistemi "9 yazı boyu, 2px ızgarası,
her renk jeton" diyordu; `ui.py`'nin CSS'i ölçülünce 21 yazı boyu, 55 ayrı
dolgu değeri ve 51 ayrı hex çıktı. Sistem ile kod arasındaki fark bir
kerelik bir temizlikle kapanmaz — her faz yeni bir `font-size:12.5px`
ekleyebilir. O yüzden araç iki iş yapıyor:

  python tools/tasarim_envanteri.py            # envanter: hangi değer kaç kez
  python tools/tasarim_envanteri.py --denetle  # v2 ölçeğinin dışı → çıkış 1
  python tools/tasarim_envanteri.py --jetonlar # tasarım sistemi tokens.json

Denetim yalnız ELLE YAZILAN CSS'e bakıyor: şablonun `<style>` bloğu
(`__JETONLAR__` üretilmeden önceki hâli) ve HTML/JS içindeki satır içi
`style="…"` öznitelikleri. Jetonların kendisi `src/itucap/tasarim.py`de.

⚠️ Bilerek DIŞARIDA bırakılanlar (her biri gerekçeli):
  · `mask-image` degradelerindeki `#000` — renk değil, saydamlık maskesi;
  · kâğıt tablosundaki `pt` boyları — kâğıdın birimi nokta;
  · `${…}` içeren satır içi değerler — JS çalışma anında hesaplıyor;
  · kenar kalınlığı ve `min-height` — ölçeği var (`line-*`, `hit-*`) ama
    değerler az ve testlerle tek tek tutuluyor; denetim onları SAYIYOR.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys

KOK = pathlib.Path(__file__).resolve().parent.parent
UI = KOK / "src" / "itucap" / "ui.py"
sys.path.insert(0, str(KOK / "src"))

from itucap import tasarim as T  # noqa: E402

ARALIK_OZ = re.compile(
    r"\b((?:padding|margin)(?:-(?:top|right|bottom|left|block|inline))?"
    r"|gap|row-gap|column-gap)\s*:\s*([^;}\"]+)")


def sablon() -> tuple[str, str]:
    """(şablonun elle yazılan CSS'i, </style> sonrası HTML+JS)."""
    kaynak = UI.read_text(encoding="utf-8")
    t0 = kaynak.index('_TEMPLATE = r"""')
    s0 = kaynak.index("<style>", t0) + len("<style>")
    s1 = kaynak.index("</style>", t0)
    return kaynak[s0:s1], kaynak[s1:]


def _yorumsuz(css: str) -> str:
    # Satır sayısını koruyarak yorumları sök (bulgular satır numarası taşısın).
    return re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), css,
                  flags=re.S)


def bildirimler():
    """(nerede, satır, özellik, değer) — CSS ve satır içi stillerin hepsi."""
    css, govde = sablon()
    kaynak = UI.read_text(encoding="utf-8")
    # Denetim bir kopya üzerinde de çalışabilsin (test ölçek dışı bir değer
    # ekleyip muhafızı deniyor): metin kaynakta yoksa satırlar 1'den sayılır.
    css_bas = kaynak[:max(0, kaynak.find(css))].count("\n") + 1
    for i, satir in enumerate(_yorumsuz(css).split("\n")):
        for ozellik, deger in re.findall(r"([a-z-]+)\s*:\s*([^;{}]+)", satir):
            if ozellik.startswith("--"):
                continue
            yield "css", css_bas + i, ozellik, deger.strip()
    govde_bas = kaynak[:max(0, kaynak.find(govde))].count("\n") + 1
    for m in re.finditer(r'style="([^"]*)"', govde):
        satir = govde_bas + govde[:m.start()].count("\n")
        for ozellik, deger in re.findall(r"([a-z-]+)\s*:\s*([^;]+)", m.group(1)):
            yield "satır içi", satir, ozellik, deger.strip()


def envanter() -> dict[str, collections.Counter]:
    say: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for _yer, _s, ozellik, deger in bildirimler():
        say[ozellik][deger] += 1
    return say


def denetle() -> list[str]:
    """v2 ölçeğinin DIŞINDA kalan her bildirim — boş liste = temiz."""
    bulgu = []
    for yer, satir, oz, deger in bildirimler():
        if "${" in deger:
            continue
        neden = None
        if oz == "font-size" and not re.fullmatch(r"var\(--fs-[a-z0-9]+\)|[\d.]+pt|inherit", deger):
            neden = "yazı boyu ölçek jetonu değil (`--fs-*`)"
        elif oz == "letter-spacing" and not re.fullmatch(r"var\(--ls-[a-z0-9]+\)", deger):
            neden = "harf aralığı jetonu değil (`--ls-*`)"
        elif oz == "line-height" and not re.fullmatch(r"var\(--lh-[a-z]+\)|0", deger):
            neden = "satır aralığı jetonu değil (`--lh-*`)"
        elif oz == "font-family" and not re.fullmatch(r"var\(--font-[a-z]+\)|inherit", deger):
            neden = "yazı ailesi jetonu değil (`--font-*`)"
        elif oz == "z-index" and not re.fullmatch(r"var\(--z-[a-z]+\)", deger):
            neden = "katman jetonu değil (`--z-*`)"
        elif oz == "border-radius" and not re.fullmatch(r"var\(--r(?:-round)?\)", deger):
            neden = "köşe jetonu değil (`--r`)"
        elif oz != "mask-image" and re.search(r"#[0-9A-Fa-f]{3,8}\b|rgba?\(", deger):
            neden = "renk değeri satır içinde (jeton kullan)"
        elif ARALIK_OZ.fullmatch(f"{oz}:{deger}"):
            for parca in deger.replace("!important", "").split():
                m = re.fullmatch(r"-?(\d+)px", parca)
                if m and int(m.group(1)) not in T.ARALIK_KUMESI:
                    neden = f"aralık {parca} ölçekte değil ({sorted(T.ARALIK_KUMESI)})"
        if neden:
            bulgu.append(f"ui.py:{satir} [{yer}] {oz}:{deger} — {neden}")
    return bulgu


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--denetle", action="store_true", help="ölçek dışı → çıkış 1")
    ap.add_argument("--jetonlar", action="store_true",
                    help="tasarım sistemi tokens.json'unu yaz")
    a = ap.parse_args()
    if a.jetonlar:
        json.dump(T.jetonlar_json(), sys.stdout, ensure_ascii=False, indent=1)
        print()
        return 0
    if a.denetle:
        bulgu = denetle()
        for b in bulgu:
            print(b)
        print(f"{'✅' if not bulgu else '❌'} {len(bulgu)} bildirim v2 ölçeğinin dışında.")
        return 1 if bulgu else 0
    say = envanter()
    for oz in ("font-size", "font-weight", "letter-spacing", "line-height",
               "font-family", "padding", "gap", "margin-top", "min-height",
               "z-index", "border-radius", "box-shadow", "transition", "opacity"):
        c = say.get(oz, collections.Counter())
        print(f"\n{oz}: {len(c)} ayrı değer, {sum(c.values())} bildirim")
        print("   " + ", ".join(f"{k}×{n}" for k, n in c.most_common(24)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
