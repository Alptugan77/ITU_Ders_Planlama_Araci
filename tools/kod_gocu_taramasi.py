#!/usr/bin/env python3
"""Kod göçü taraması (Faz 105).

Plana sadık bir öğrenci kendi planının derslerinden önşart yüzünden
ENGELLENMEMELİ. Bu araç her lisans planında, t. dönemdeki her zorunlu dersi
önceki dönemlerin bütün zorunluları geçilmiş sayarak dener (`prereq_view` —
beyan edilmiş kod göçleri dahil) ve engelli kalanları döker.

İkinci bölüm kod göçü ADAYLARINI listeler: eksik önşartla adı ve kredisi aynı
bir ders planın önceki dönemlerinde varsa, fakülte dersi yeni koduyla
okutuyor, önşart metni eski kodda kalmış olabilir. Aday OTOMATİK beyan
edilmez: `config/katalog-duzeltmeleri.toml` → `[[kod_gocu]]` ölçütü (Faz 105)
ad + kredi + AKTS aynılığı VE plan zinciri; AKTS'si farklı aday elle incelenir.

    python tools/kod_gocu_taramasi.py               # özet + adaylar
    python tools/kod_gocu_taramasi.py --liste       # engelli derslerin tamamı
    python tools/kod_gocu_taramasi.py --db yol.sqlite3
"""
from __future__ import annotations

import argparse
import collections
import pathlib
import sqlite3
import sys

KOK = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK / "src"))

from itucap import config, plans as PL, prereq as P, rules as R   # noqa: E402


def tara(con: sqlite3.Connection) -> dict:
    """{'incelenen', 'engelli': [(bölüm, plan, dönem, ders, eksik)], 'adaylar': [...]}"""
    con.row_factory = sqlite3.Row
    agac = P.parsed_trees(con)
    bilgi = {r[0]: (str(r[1] or "").strip().lower(), r[2], r[3])
             for r in con.execute("SELECT code, name, credits, ects FROM course")}
    engelli, incelenen = [], 0
    # Faz 106 — resmî denklikler (çekildiyse) de sayılıyor: kalan engel, OBS'nin
    # kendi denkliğiyle de açılmayan engel.
    denklik = R.load_equivalences(con)
    adaylar: dict = collections.defaultdict(lambda: {"bolum": set(), "engel": set()})
    programlar = sorted(r[0] for r in con.execute(
        "SELECT DISTINCT program_code FROM plan WHERE plan_type='lisans' AND program_code IS NOT NULL"))
    for pg in programlar:
        pid = PL.anadal_plan(con, config.Settings(anadal_program=pg, program_codes=[pg]))
        if pid is None:
            continue
        rows = con.execute(
            """SELECT term_no, course_code FROM plan_slot WHERE plan_id=? AND slot_kind='REQUIRED'
                 AND course_code IS NOT NULL AND term_no IS NOT NULL""", (pid,)).fetchall()
        for t in sorted({r[0] for r in rows}):
            onceki = [r[1] for r in rows if r[0] < t]
            view = R.prereq_view(R.expand_with_equivalences({k: "BB" for k in onceki}, denklik)[0])
            for r in rows:
                if r[0] != t or r[1] not in agac:
                    continue
                incelenen += 1
                if agac[r[1]].satisfied(view):
                    continue
                eksik = sorted({n.course for n in agac[r[1]].missing(view)})
                engelli.append((pg, pid, t, r[1], eksik))
                for m in eksik:
                    for o in onceki:
                        if (m in bilgi and o in bilgi and o != m
                                and bilgi[o][0] == bilgi[m][0] and bilgi[o][1] == bilgi[m][1]):
                            k = (m, o, bilgi[m][2] == bilgi[o][2])
                            adaylar[k]["bolum"].add(pg)
                            adaylar[k]["engel"].add(r[1])
    return {"incelenen": incelenen, "engelli": engelli,
            "adaylar": [(m, o, akts, sorted(v["bolum"]), sorted(v["engel"]))
                        for (m, o, akts), v in adaylar.items()]}


def beyan_karsilastir(con: sqlite3.Connection) -> dict:
    """Faz 107 — kod göçü beyanlarını RESMÎ denkliklerle karşılaştırır.

    Beyan (`[[kod_gocu]]`) resmî tablo boşken konmuş bir köprü (Faz 104–106).
    Tablo dolunca her beyan için: resmî listede aynı iki kodu bağlayan bir
    denklik var mı (hangi yönde olursa olsun, tek kaynaklı)? Karşılığı olan
    beyan gereksizleşir; olmayan yeniden değerlendirilmeli.
    Dönüş: {'resmi_sayi', 'karsilanan': [...], 'karsiliksiz': [...]}."""
    from itucap import declared as DEC
    resmi = con.execute("SELECT COUNT(*) FROM equivalence WHERE confidence='official'").fetchone()[0]
    baglar: set[frozenset] = set()
    for hedef, kaynaklar in con.execute(
            """SELECT e.target_course, group_concat(s.course_code, '|')
                 FROM equivalence e JOIN equivalence_source s ON s.equivalence_id = e.id
                WHERE e.confidence='official' GROUP BY e.id"""):
        ks = [k for k in (kaynaklar or "").split("|") if k]
        if len(ks) == 1:                 # "A + B → C" bir kod göçü değil
            baglar.add(frozenset({hedef, ks[0]}))
    karsilanan, karsiliksiz = [], []
    for eski, yeni in DEC.load_code_migrations():
        (karsilanan if frozenset({eski, yeni}) in baglar else karsiliksiz).append((eski, yeni))
    return {"resmi_sayi": resmi, "karsilanan": karsilanan, "karsiliksiz": karsiliksiz}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default=str(config.REF_DB))
    ap.add_argument("--liste", action="store_true")
    a = ap.parse_args(argv)
    s = tara(sqlite3.connect(a.db))
    print(f"İncelenen zorunlu ders: {s['incelenen']} · plana sadık öğrencide engelli: "
          f"{len(s['engelli'])} ({len({e[0] for e in s['engelli']})} bölüm)")
    if a.liste:
        for pg, _pid, t, ders, eksik in s["engelli"]:
            print(f"  {pg:6} {t}. dönem {ders:10} eksik: {', '.join(eksik[:6])}")
    print(f"Kod göçü adayı: {len(s['adaylar'])} (beyan ölçütü: ad + kredi + AKTS aynı, plan zinciri)")
    for m, o, akts, bolum, engel in sorted(s["adaylar"], key=lambda x: (not x[2], x[0])):
        print(f"  {m:10} → {o:10} AKTS {'aynı' if akts else 'FARKLI'} · {', '.join(bolum)} · "
              f"engellenen: {', '.join(engel[:4])}")
    k = beyan_karsilastir(sqlite3.connect(a.db))
    if not k["resmi_sayi"]:
        print("Resmî denklik tablosu BOŞ — beyanlar karşılaştırılamadı (make all-plans).")
    else:
        print(f"Kod göçü beyanları ({k['resmi_sayi']} resmî denklikle): "
              f"{len(k['karsilanan'])} resmî listede var, {len(k['karsiliksiz'])} YOK")
        for e, y in k["karsiliksiz"]:
            print(f"  ⚠ {e} → {y}: resmî karşılığı yok, beyanı yeniden değerlendiriniz")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
