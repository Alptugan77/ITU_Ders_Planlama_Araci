"""Faz 104 — "-" bir program kodu değil: ilan edilmemiş şube.

Gerçek katalog gezisinde (BLGE, 26.09.2026) BLG 322E ve BLG 354E için
"Alınamayan dersler" şunu yazıyordu: *"1 şube bulunmaktadır; yalnızca -
alabilir"*. Kaynak, alabilecek programları ilan edilmemiş şubeye "-" yazıyor
(2026 Güz: 3807 şubenin 70'i; 68'inde kontenjan 0, hoca ve bina "-", yalnız
3'ünde saat var). Ders "başka programlara ayrılmış" (PROGRAMA_KAPALI)
sayılıyor ve arz uyarısında yanlış gruba düşüyordu. Doğrusu: henüz ilan
edilmemiş (ACILMAMIS).
"""
from itucap import recommend as REC
from test_recommend import dbs  # noqa: F401  (fixture)


def _ekle(con, kod, subeler):
    con.execute("INSERT INTO course(code,name,ects) VALUES (?,?,5)", (kod, kod))
    n = con.execute("SELECT COUNT(*) FROM plan_slot WHERE plan_id=20").fetchone()[0]
    con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,ects,position)"
                " VALUES (20,'REQUIRED',?,5,?)", (kod, n))
    for crn, progs, kont in subeler:
        con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled) VALUES (?,?,?,0)",
                    (crn, kod, kont))
        for p in progs:
            con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES (?,?)",
                        (crn, p))


def _engeller(dbs):  # noqa: F811
    con, ucon, sid = dbs
    _ekle(con, "BLG 401E", [("900", ["-"], 0)])                          # yalnız ilansız
    _ekle(con, "BLG 402E", [("901", ["-"], 0), ("902", ["SECE"], 30)])   # biri ilanlı, başka programa
    _ekle(con, "BLG 403E", [("903", ["-"], 0), ("904", ["-"], 0)])       # iki ilansız şube
    con.commit()
    return {b.course: b for b in REC.cap_blockers(con, ucon, sid, 20, "BLG", {"HTAE", "BLG", "BLGE"})}


def test_ILANSIZ_sube_ACILMAMIS(dbs):  # noqa: F811
    e = _engeller(dbs)
    assert e["BLG 401E"].reason == "ACILMAMIS"
    assert e["BLG 401E"].detail == ("1 şube listelenmiş, ancak saati, kontenjanı ve alabilecek "
                                    "programlar henüz ilan edilmemiştir")
    assert e["BLG 403E"].reason == "ACILMAMIS" and e["BLG 403E"].detail.startswith("2 şube")


def test_ILANLI_subesi_varsa_gercek_programlar(dbs):  # noqa: F811
    e = _engeller(dbs)
    assert e["BLG 402E"].reason == "PROGRAMA_KAPALI"
    assert e["BLG 402E"].detail == "2 şube bulunmaktadır; yalnızca SECE alabilir"   # "-" yazılmıyor


def test_ESKI_davranis_degismedi(dbs):  # noqa: F811
    e = _engeller(dbs)
    assert e["BLG 223E"].reason == "PROGRAMA_KAPALI"                   # yalnız SECE'ye açık
    assert e["BLG 223E"].detail == "1 şube bulunmaktadır; yalnızca SECE alabilir"
