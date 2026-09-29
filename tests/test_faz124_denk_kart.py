"""Faz 124 — "açık denklikler" kartı dersin bu dönem ALINABİLİR olup olmadığını
söylüyor.

Kullanıcının kendi verisinde ölçüldü (HTAE + BLG ÇAP, 29.09.2026):
* BBF 302E "açık, dilekçe gerekmez" görünüyordu; önşartı BLG 252E geçilmemiş.
  Engel paneli (Faz 120) aynı dersi "önşart eksik" sayıyordu. Kart OBS'nin
  taban kodunu ("BBF 302") denetliyordu — katalogda yok, "önşart yok" sanıyordu.
* BLG 492 (bitirme çalışması, en az 95 kredi) alınabilir görünüyordu; kredi
  denklikle genişletilmiş notlardan hesaplanınca 85 → 329 çıkıyordu.
* TUR 111/112 ("Yabancı Öğr. İçin Türk Dili") TUR 121/122 yerine
  "dilekçesiz" gösteriliyordu (öneri motoru Faz 117'de dışlıyor).
"""
from itucap import db, prereq as P, rules as R, ui as UI
from test_acik_denklik import _sj


def _katalog(tmp_path):
    con = db.connect(tmp_path / "r.sqlite3", "schema.sql")
    con.executemany("INSERT INTO course(code,name,credits,prereq_raw,class_restriction) VALUES (?,?,?,?,?)", [
        ("BLG 317E", "Database Systems", 3, None, None),
        ("BBF 302E", "Database Systems", 3, "BLG 252E MIN DD", None),
        ("BLG 252E", "Data Structures", 3, None, None),
        ("BLG 4902E", "Design II", 3, None, None),
        ("BLG 492", "Bitirme Çalışması", 3, None, "95,00"),
        ("TUR 122", "Türk Dili II", 2, None, None),
        ("TUR 112", "Yabancı Öğr. İçin Türk Dili II", 2, None, None),
        ("ABC 101", "Geçilmiş", 90, None, None)])
    for crn, kod in (("1", "BBF 302E"), ("2", "BLG 492"), ("3", "TUR 112")):
        con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled) VALUES (?,?,40,0)", (crn, kod))
        con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES (?,'BLG')", (crn,))
    P.parse_all(con); con.commit()
    return con


def _kart(con, notlar=None, kredi=85.0):
    esd = [R.Equivalence(1, "BLG 317", (("BBF 302", "DD"),), "official", True),
           R.Equivalence(2, "BLG 4902E", (("BLG 492", "DD"),), "official", True),
           R.Equivalence(3, "TUR 122", (("TUR 112", "DD"),), "official", True)]
    names = {r[0]: r[1] for r in con.execute("SELECT code, name FROM course")}
    out = UI._acik_denklikler(con, esd, dict(notlar or {}), {"BLG 317E", "BLG 4902E", "TUR 122"},
                              {"BLG", "HTAE"}, names, _sj, ["HTAE", "BLG"], kazanilan_kredi=kredi)
    return {e["target"]: {k["code"]: k for k in e["sources"]} for e in out}


def test_TABAN_KODLU_kaynakta_ONSART_acik_yazimla(tmp_path):
    k = _kart(_katalog(tmp_path))["BLG 317E"]["BBF 302"]
    assert k["open"] and k["dilekcesiz"]
    assert k["notTakable"].startswith("önşart eksik: BLG 252E"), k
    k = _kart(_katalog(tmp_path / "b"), {"BLG 252E": "CC"})["BLG 317E"]["BBF 302"]
    assert k["notTakable"] == ""


def test_KREDI_ESIGI_ham_krediyle(tmp_path):
    con = _katalog(tmp_path)
    assert _kart(con, kredi=85.0)["BLG 4902E"]["BLG 492"]["notTakable"] == \
        "en az 95 kredi gerekir, tamamlanan 85"
    assert _kart(con, kredi=96.0)["BLG 4902E"]["BLG 492"]["notTakable"] == ""
    assert _kart(con, kredi=None)["BLG 4902E"]["BLG 492"]["notTakable"] == ""   # bilinmiyorsa iddia yok


def test_YABANCI_OGRENCI_dersi_kaynak_degil(tmp_path):
    assert "TUR 122" not in _kart(_katalog(tmp_path))


def test_ARAYUZ():
    src = open(UI.__file__, encoding="utf-8").read()
    assert "const serbest = acik.filter(k => k.dilekcesiz && !k.notTakable);" in src
    assert "<b>şartları sağlanmadığından bu dönem alınamaz</b>" in src
    assert "kazanilan_kredi=POL.earned_credits(con, grades))" in src


def test_ALINABILIR_OLAN_once_ve_baslik(tmp_path):
    con = _katalog(tmp_path)
    esd = [R.Equivalence(1, "BLG 317", (("BBF 302", "DD"),), "official", True),
           R.Equivalence(2, "BLG 4902E", (("BLG 492", "DD"),), "official", True)]
    names = {r[0]: r[1] for r in con.execute("SELECT code, name FROM course")}
    out = UI._acik_denklikler(con, esd, {}, {"BLG 317E", "BLG 4902E"}, {"BLG"}, names, _sj,
                              ["BLG"], kazanilan_kredi=96.0)
    assert [e["target"] for e in out] == ["BLG 4902E", "BLG 317E"]   # BLG 492 alınabilir
    src = open(UI.__file__, encoding="utf-8").read()
    assert "— denkliği bu dönem açık, ancak şartları sağlanmamaktadır:" in src
