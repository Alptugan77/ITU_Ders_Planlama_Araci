"""Faz 123 — ilerleme yüzdesi AKTS ağırlıklı (kullanıcı isteği 28.09.2026:
"ilerleme durumunu AKTS'ye göre hesaplar mısın").

Yuva sayısı 2 AKTS'lik dersle 7,5 AKTS'lik dersi eşit sayıyordu; mezuniyet
şartı AKTS. Kullanıcının verisinde ÇAP (BLG) %18,2 → %15,4 (18/117 AKTS).
Planda hiç AKTS yoksa yuva sayısına düşülüyor (`percent_basis`).
"""
import pathlib

from itucap import db, prereq as P, rules as R, ui as UI


def _plan(tmp_path, ects):
    con = db.connect(tmp_path / "r.sqlite3", "schema.sql")
    con.execute("INSERT INTO plan(id,program_code,plan_type,title,source) VALUES (1,'AAA','lisans','x','obs')")
    for i, (kod, a) in enumerate([("AAA 101", ects[0]), ("AAA 102", ects[1])]):
        con.execute("INSERT INTO course(code,name,credits) VALUES (?,?,3)", (kod, kod))
        con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,ects,position) "
                    "VALUES (1,'REQUIRED',?,?,?)", (kod, a, i))
    P.parse_all(con); con.commit()
    return con


def test_YUZDE_akts_agirlikli(tmp_path):
    s = R.plan_progress(_plan(tmp_path, (2, 8)), 1, {"AAA 102": "BB"}, [])
    assert (s["percent"], s["percent_basis"], s["percent_slots"]) == (80.0, "akts", 50.0)


def test_AKTS_yoksa_yuva_sayisi(tmp_path):
    s = R.plan_progress(_plan(tmp_path, (None, None)), 1, {"AAA 102": "BB"}, [])
    assert (s["percent"], s["percent_basis"]) == (50.0, "slot")


def test_ARAYUZ_akts_ile_ileri_yansitma():
    k = pathlib.Path(UI.__file__).read_text(encoding="utf-8")
    assert '"percentBasis": stats["percent_basis"]' in k
    assert "(p.ectsDone + (plan.ects || 0)) / p.ectsTotal" in k
    assert 'tamamlandı${aktsli ? " (AKTS)" : ""}' in k
