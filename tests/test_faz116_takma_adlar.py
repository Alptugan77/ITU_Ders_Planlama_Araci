"""Faz 116 — "açtıkları" dersin takma adlarıyla sayılıyor.

Önşart metinleri eski kodu anıyor (BLG 252E), plan yeni kodu koyuyor
(BBF 203E). "Açtığı ders" sayımı kodu birebir aradığı için gerçek BLGE
planında BBF 202E/204E/301E "0 dersin önşartı", BBF 203E "1" görünüyordu;
öneri puanı ve adayın "açtıkları" listesi bu dersleri küçümsüyordu.
Sonra: BBF 203E planda BBF 301E, BBF 302E, BLG 411E'yi; BBF 303E,
BLG 417E ve BLG 4901E'yi; BBF 301E, BBF 303E'yi açıyor.
"""
import pytest

from itucap import declared as DEC, prereq as P, recommend as REC, rules as R, ui as UI
from test_recommend import dbs  # noqa: F401  (fixture)


@pytest.fixture()
def gocsuz(tmp_path, monkeypatch):
    bos = tmp_path / "k.toml"
    bos.write_text("", encoding="utf-8")
    monkeypatch.setattr(DEC, "CATALOG_PATH", bos)
    return bos


def test_TAKMA_ADLAR(dbs, gocsuz):  # noqa: F811
    con = dbs[0]
    con.executemany("INSERT INTO course(code,name,credits) VALUES (?,?,3)",
                    [("NEW 101E", "n"), ("NEW 101", "n"), ("OLD 101", "o")])
    con.commit()
    esd = [R.Equivalence(1, "OLD 101", (("NEW 101", "DD"),), "official", True)]
    assert R.takma_adlar(con, "NEW 101E") == {"NEW 101E", "NEW 101"}          # dil eşi
    assert R.takma_adlar(con, "NEW 101E", esd) >= {"NEW 101E", "OLD 101E"}   # denklik (dil korunur)
    assert R.takma_adlar(con, "") == frozenset()
    um = {"OLD 101E": ["A 201", "B 202"], "NEW 101E": ["C 203"], "NEW 101": ["NEW 101E"]}
    assert R.acilan_hedefler(um, R.takma_adlar(con, "NEW 101E", esd)) == {"A 201", "B 202", "C 203"}


def test_KOD_GOCU_takma_ad(dbs, tmp_path, monkeypatch):  # noqa: F811
    dosya = tmp_path / "g.toml"
    dosya.write_text('[[kod_gocu]]\neski = "BLG 252E"\nyeni = "BBF 203E"\nnot_ = "t"\n', encoding="utf-8")
    monkeypatch.setattr(DEC, "CATALOG_PATH", dosya)
    assert "BLG 252E" in R.takma_adlar(dbs[0], "BBF 203E")


def test_ADAY_acilan_sayisi_takma_adla(dbs, gocsuz):  # noqa: F811
    """Plandaki yeni kodlu ders; önşartlar eski kodu anıyor, resmî denklik var."""
    con, ucon, sid = dbs
    con.executemany("INSERT INTO course(code,name,ects,prereq_raw) VALUES (?,?,5,?)",
                    [("BBF 203E", "OOP", None), ("BLG 252E", "OOP", None),
                     ("BBF 301E", "Alg", "BLG 252E MIN DD"), ("BLG 411E", "SE", "BLG 252E MIN DD")])
    con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,ects,position) VALUES (20,'REQUIRED','BBF 203E',5,9)")
    con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled) VALUES ('881','BBF 203E',40,0)")
    con.execute("INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min) VALUES ('881',5,510,689)")
    con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES ('881','BLG')")
    cur = con.execute("INSERT INTO equivalence(target_course,confidence) VALUES ('BLG 252','official')")
    con.execute("INSERT INTO equivalence_source(equivalence_id,course_code,min_grade) VALUES (?,'BBF 203','DD')",
                (cur.lastrowid,))
    con.commit()
    P.parse_all(con)
    c = {x.course: x for x in REC.candidates(con, ucon, sid, None, 20, "HTAE", "BLG", {"HTAE", "BLG"})}
    assert c["BBF 203E"].unlocks == 2, c["BBF 203E"].unlocks        # eskiden 0


def test_ARAYUZ_acilanlar_takma_adla():
    src = open(UI.__file__, encoding="utf-8").read()
    i = src.index("def _acilanlar(")
    f = src[i:src.index("return sorted(secili.values())", i)]
    assert "R.acilan_hedefler(_unlock_map, adlar)" in f and "R.takma_adlar(con, code, equivalences)" in f
