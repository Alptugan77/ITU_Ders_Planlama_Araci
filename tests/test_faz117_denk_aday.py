"""Faz 117 — dilekçesiz denk dersler öneride.

Kullanıcı (28.09.2026): *"programda olan derslerin dilekçe gerektirmeyen
denklerini öneride kullanabilirsin ve kullanıcı bunları diğer dersler gibi
kullanabilir olacak şekilde ayarla"*.

Zorunlu plan dersinin resmî denkliği olan ders, şubesi öğrencinin kendi
programına (anadal/ÇAP/yandal; BLG/BLGE/_LS) açıksa aday oluyor ve plan
dersinin YUVASINA bağlanıyor. Plan dersi de açıksa denk ders puan cezası
alıyor (öneri planın dersini seçer). Gerçek katalogda 127 planda 430 denk
aday; 290'ında plandaki ders bu dönem açık değil.
"""
import pytest

from itucap import normalize as N, prereq as P, recommend as REC
from test_crn_yukle import state  # noqa: F401  (fixture)
from test_recommend import dbs  # noqa: F401  (fixture)


def _denk(con, kod, ad="Denk", progs=("BLG",), hedef="BLG 212", crn="777", gun=4):
    con.execute("INSERT INTO course(code,name,ects,credits) VALUES (?,?,6,3)", (kod, ad))
    con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled) VALUES (?,?,40,0)", (crn, kod))
    con.execute("INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min) VALUES (?,?,510,689)", (crn, gun))
    for p in progs:
        con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES (?,?)", (crn, p))
    cur = con.execute("INSERT INTO equivalence(target_course,confidence) VALUES (?,'official')", (hedef,))
    taban = kod[:-1] if kod.endswith("E") else kod
    con.execute("INSERT INTO equivalence_source(equivalence_id,course_code,min_grade) VALUES (?,?,'DD')",
                (cur.lastrowid, taban))
    con.commit()


def _adaylar(dbs, ek=()):  # noqa: F811
    con, ucon, sid = dbs
    P.parse_all(con)
    return {c.course: c for c in REC.candidates(con, ucon, sid, 10, 20, "HTAE", "BLG",
                                                 {"HTAE", "BLG", "BLGE", *ek})}


def test_KENDI_PROGRAM_KODLARI():
    k = N.kendi_program_kodlari(["BLGE", "blg_ls", "", None])
    assert {"BLG", "BLGE", "BLG_LS", "BLGE_LS"} <= k and "" not in k


def test_DILEKCESIZ_DENK_aday_ve_yuvaya_bagli(dbs):  # noqa: F811
    dbs[0].execute("UPDATE plan_slot SET credits=4 WHERE plan_id=20 AND course_code='BLG 212E'")
    _denk(dbs[0], "DNK 212E")
    c = _adaylar(dbs)
    d, asil = c["DNK 212E"], c["BLG 212E"]
    assert d.denk_of == "BLG 212E" and d.slot_id == asil.slot_id and d.required
    assert d.reasons[0] == "BLG 212E yerine (resmî denklik, dilekçesiz)"
    # plandaki ders de açık → ceza, öneri planın dersini seçer
    assert any(p["key"] == "denk" for p in d.parts) and d.score < asil.score
    assert REC.yuva_ata([asil, d]) is None                  # aynı yuva: ikisi birlikte seçilemez
    assert d.credits == 3 and d.ects == 6                    # yük denk dersin kendisinden


def test_PLAN_DERSI_KAPALIYSA_ceza_yok(dbs):  # noqa: F811
    con = dbs[0]
    con.execute("DELETE FROM lesson_allowed_program WHERE crn IN ('100','101')")
    con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES ('100','MAK'),('101','MAK')")
    con.commit()
    _denk(con, "DNK 212E")
    c = _adaylar(dbs)
    assert "BLG 212E" not in c
    assert not any(p["key"] == "denk" for p in c["DNK 212E"].parts)


def test_BASKA_PROGRAMA_ACIK_denk_aday_degil(dbs):  # noqa: F811
    """Ek program kodu (MAK) kayıt izni veriyor ama öğrencinin KENDİ programı
    değil: şube yalnız MAK'a açıksa denk ders dilekçe ister, aday değil."""
    _denk(dbs[0], "DNK 212E", progs=("MAK",))
    assert "DNK 212E" not in _adaylar(dbs, ek=("MAK",))


def test_YABANCI_OGRENCI_dersi_denk_degil(dbs):  # noqa: F811
    _denk(dbs[0], "TUR 112E", ad="Yabancı Öğr. İçin Türk Dili II")
    _denk(dbs[0], "TUR 113E", ad="Türk Dili", crn="778", gun=5)
    c = _adaylar(dbs)
    assert "TUR 112E" not in c and "TUR 113E" in c


def test_ARAYUZ_etiketi():
    from itucap import ui as UI
    src = open(UI.__file__, encoding="utf-8").read()
    assert '"denkOf": c.denk_of,' in src
    assert "${esc(c.denkOf)} yerine</span>" in src


def test_CRN_ile_denk_ders_plan_dersi_yerine(state, tmp_path):  # noqa: F811
    """OBS'den yapıştırılan CRN plandaki dersin resmî denkliğiyse "plan dışı"
    değil, o dersin rolüyle ve "yerine" bilgisiyle geliyor."""
    from itucap import db
    con = db.connect(tmp_path / "r.sqlite3", "schema.sql")
    con.execute("INSERT INTO course(code,name,credits) VALUES ('DNK 303E','Denk',3)")
    con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled) VALUES ('55555','DNK 303E',40,0)")
    cur = con.execute("INSERT INTO equivalence(target_course,confidence) VALUES ('GEO 303','official')")
    con.execute("INSERT INTO equivalence_source(equivalence_id,course_code,min_grade) VALUES (?,'DNK 303','DD')",
                (cur.lastrowid,))
    con.commit(); con.close()
    f = {x["crn"]: x for x in state.dispatch("/api/crn", {"crns": ["55555", "13524"]})["crn"]["found"]}
    assert f["55555"]["role"] == "ANADAL" and f["55555"]["denkOf"] == "GEO 303E"
    assert f["13524"]["denkOf"] == ""
