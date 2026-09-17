#!/usr/bin/env python3
"""Hayalet önşart ölçümü (Faz 42).

**Hayalet önşart** = bir dersin önşartının, katalogda BULUNMAYAN bir ders adını
taşıması. İki sebebi olabilir ve ikisi de gerçek:

* **kod göçü / kapanmış ders** — `ELH 332`, `ISL 221`: artık açılmıyor.
  Öğrencinin transkriptinde eski koduyla duruyor OLABİLİR, ama gidip
  alamaz.
* **dil eşi** — `BIL 100` katalogda yok, `BIL 100E` var. Kaynak metin
  ikisini genelde "veya" ile zaten eşliyor, orada zarar yok.

Ölçülen zarar, önşartın kendisi değil **listenin sırası**: eksik önşartlar
alfabetik sıralanıp 4'e kesiliyordu, alınabilir ders kesilip hayaletler
ekranda kalabiliyordu.

    python tools/hayalet_onsart.py            # katalogdaki durumu ölç
    python tools/hayalet_onsart.py --liste    # açılamayan dersleri dök
"""
from __future__ import annotations

import argparse
import pathlib
import sqlite3
import sys

KOK = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK / "src"))

from itucap import config, prereq as P, recommend as REC   # noqa: E402


def dil_esi(kod: str) -> str:
    return kod[:-1] if kod.endswith("E") else kod + "E"


def cozulebilir(n, katalog: set[str]) -> bool:
    """Hayalet yaprak ASLA sağlanamaz; gerçek yaprak sağlanabilir sayılır.

    Yani: "bu dersin önşartı, katalogdaki derslerle açılabilir mi?"
    """
    if n.kind == "LEAF":
        return n.course in katalog
    if n.kind == "AND":
        return all(cozulebilir(c, katalog) for c in n.children)
    return any(cozulebilir(c, katalog) for c in n.children)


def olc(con: sqlite3.Connection) -> dict:
    katalog = {r[0] for r in con.execute("SELECT code FROM course")}
    yaprak = hayalet_yaprak = 0
    hayalet_kod: dict[str, int] = {}
    etkilenen: set[str] = set()
    cozulmez: list[tuple[str, list[str]]] = []
    kesilen: list[tuple[str, list[str], list[str]]] = []
    agacli = 0

    for kod, ham in con.execute(
            "SELECT code, prereq_raw FROM course "
            "WHERE prereq_raw IS NOT NULL AND prereq_raw <> ''"):
        p = P.parse(ham)
        if not p or not p.tree:
            continue
        agacli += 1
        for c in p.tree.courses():
            yaprak += 1
            if c not in katalog:
                hayalet_yaprak += 1
                hayalet_kod[c] = hayalet_kod.get(c, 0) + 1
                etkilenen.add(kod)
        if not cozulebilir(p.tree, katalog):
            cozulmez.append((kod, sorted(c for c in p.tree.courses()
                                         if c not in katalog)))
        # Kesme gerçek alternatifi yutuyor mu (ESKİ davranış)?
        eksik = sorted({n.course for n in p.tree.missing({}) if n.course})
        if eksik:
            eski_gosterim = eksik[:4]
            gercek = [c for c in eksik if c in katalog]
            if gercek and not any(c in katalog for c in eski_gosterim):
                kesilen.append((kod, eski_gosterim, gercek[:4]))

    esli = {k: n for k, n in hayalet_kod.items() if dil_esi(k) in katalog}
    return {
        "agacli": agacli, "yaprak": yaprak,
        "hayalet_yaprak": hayalet_yaprak, "hayalet_kod": hayalet_kod,
        "dil_esi_olan": esli, "etkilenen": etkilenen,
        "cozulmez": cozulmez, "kesilen": kesilen, "katalog": katalog,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--liste", action="store_true",
                    help="önşartı katalogda olmayan dersleri dök")
    a = ap.parse_args()

    con = sqlite3.connect(config.REF_DB)
    con.row_factory = sqlite3.Row
    r = olc(con)

    y, hy = r["yaprak"], r["hayalet_yaprak"]
    print(f"önşart ağacı olan ders        : {r['agacli']}")
    print(f"önşart yaprağı                : {y}")
    print(f"  katalogda OLMAYAN ders anan : {hy}  (%{100*hy/y:.1f})"
          if y else "")
    print(f"  farklı hayalet kod          : {len(r['hayalet_kod'])}"
          f"  (dil eşi katalogda olan: {len(r['dil_esi_olan'])})")
    print(f"  etkilenen ders              : {len(r['etkilenen'])}")
    print(f"\n★★ önşartı HİÇBİR katalog dersiyle açılamayan: {len(r['cozulmez'])}")
    print(f"★  eski sıralamada gerçek alternatifi kesilen : {len(r['kesilen'])}")

    if a.liste:
        print("\n— açılamayan dersler —")
        for kod, hy_kodlar in r["cozulmez"]:
            print(f"   {kod:11s} hayalet: {', '.join(hy_kodlar)}")
        print("\n— eski sıralamanın gizlediği alternatifler —")
        for kod, eski, gercek in r["kesilen"]:
            print(f"   {kod:11s} ekranda: {eski}")
            print(f"   {'':11s} oysa   : {gercek}")

    # Düzeltme yürürlükte mi: gerçek alternatifler ÖNE geçiyor mu?
    kotu = 0
    for kod, eski, gercek in r["kesilen"]:
        eksik = set(eski) | set(gercek)
        metin, _ = REC._onsart_ayikla(eksik, r["katalog"])
        if not any(g in metin for g in gercek):
            kotu += 1
    print(f"\ndüzeltmeden sonra hâlâ yalnız hayalet gösteren: {kotu}")
    return 0 if kotu == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
