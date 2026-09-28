"""Faz 111 — "Ek Sınav" yöntemli şube bir ders değil.

Kullanıcı (28.09.2026): *"derslerde öğretim yöntemi ek sınav olanları ek
sınav olarak göster yönetmeliğe uygun şekilde o yüzden saatleri yok bazı
derslerin"*.

2547 s. Kanun m. 44/c: azami süre sonunda mezun olamayan öğrenciye
başarısız olduğu dersler için iki EK SINAV, tek dersi kalana SINIRSIZ SINAV
hakkı. OBS bunları "Ek Sınav" / "Sınırsız Sınav" yöntemli, saatsiz ve
kontenjansız şube olarak listeliyor (gerçek katalog: 71 + 2 şube; 71 dersin
69'unun tek şubesi). Motor onları "saati ilan edilmemiş" normal şube
sanıyordu: programa açık olanlar öneriye girebiliyor, "-" programlılar
"henüz ilan edilmemiştir" diye gösteriliyordu.
"""
import pytest

from itucap import config, db, progress as PR, recommend as REC, ui as UI, yolharitasi as YH
from test_crn_yukle import state  # noqa: F401  (fixture)
from test_recommend import dbs  # noqa: F401  (fixture)


@pytest.mark.parametrize("yontem,tur", [
    ("Ek Sınav", "Ek sınav"), ("Sınırsız Sınav", "Sınırsız sınav"), ("EK SINAV", "Ek sınav"),
    ("  ek   sınav ", "Ek sınav"), ("Physical (Face to face)", None), ("Virtual (Online)", None),
    (None, None), ("", None)])
def test_SINAV_TURU(yontem, tur):
    assert REC.sinav_turu(yontem) == tur
    assert REC.Section("1", "X", None, 0, 0, (), yontem).sinav == tur


def _ekle(con, kod, subeler):
    """subeler: [(crn, yöntem, [programlar], saatli_mi)]"""
    con.execute("INSERT INTO course(code,name,ects) VALUES (?,?,5)", (kod, kod))
    n = con.execute("SELECT COUNT(*) FROM plan_slot WHERE plan_id=20").fetchone()[0]
    con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,ects,position)"
                " VALUES (20,'REQUIRED',?,5,?)", (kod, n))
    for crn, yontem, progs, saatli in subeler:
        con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled,teaching_method)"
                    " VALUES (?,?,?,0,?)", (crn, kod, 40 if saatli else 0, yontem))
        for p in progs:
            con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES (?,?)", (crn, p))
        if saatli:
            con.execute("INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min)"
                        " VALUES (?,2,600,720)", (crn,))


@pytest.fixture()
def katalog(dbs):  # noqa: F811
    con, ucon, sid = dbs
    _ekle(con, "BLG 322E", [("801", "Ek Sınav", ["BLG"], False)])            # programa açık
    _ekle(con, "BLG 354E", [("802", "Ek Sınav", ["-"], False)])              # "-" programlı
    _ekle(con, "MAD 302E", [("803", "Sınırsız Sınav", ["-"], False)])
    _ekle(con, "BLG 336E", [("804", "Ek Sınav", ["BLG"], False),
                            ("805", "Physical (Face to face)", ["BLG"], True)])  # ikisi de var
    _ekle(con, "BLG 401E", [("806", "Physical (Face to face)", ["-"], False)])   # Faz 104 aynen
    con.commit()
    return con, ucon, sid


def test_SINAV_subesi_programa_girmez(katalog):
    con = katalog[0]
    assert REC.load_sections(con, "BLG 322E", {"BLG"}) == []
    assert [s.crn for s in REC.load_sections(con, "BLG 336E", {"BLG"})] == ["805"]


def test_ENGEL_yalniz_ek_sinav(katalog):
    con, ucon, sid = katalog
    e = {b.course: b for b in REC.cap_blockers(con, ucon, sid, 20, "BLG", {"HTAE", "BLG"})}
    for kod in ("BLG 322E", "BLG 354E"):
        assert e[kod].reason == "EK_SINAV", e[kod]
        assert e[kod].detail.startswith("bu dönem yalnızca ek sınav şubesi açılmıştır; ders saati yoktur")
        assert "2547 s. Kanun m. 44/c" in e[kod].detail
    assert e["MAD 302E"].reason == "EK_SINAV" and "yalnızca sınırsız sınav şubesi" in e["MAD 302E"].detail
    assert "BLG 336E" not in e                                     # normal şubesi alınabilir
    assert e["BLG 401E"].reason == "ACILMAMIS"                    # Faz 104: ilansız şube
    assert "YALNIZ EK SINAV AÇILMIŞ (3 ders)" in REC.format_blockers(list(e.values()))


def test_ONERIYE_girmez(katalog):
    """Programa açık ek sınav şubesi saatsiz "son çare" şube diye öneriye
    giriyordu; artık dersin yalnız normal şubesi aday."""
    con, ucon, sid = katalog
    adaylar = {c.course: c for c in REC.candidates(con, ucon, sid, None, 20, "HTAE", "BLG",
                                                     {"HTAE", "BLG"})}
    assert "BLG 322E" not in adaylar
    assert [s.crn for s in adaylar["BLG 336E"].sections] == ["805"]


def test_ILERLEME_ozeti(katalog):
    con = katalog[0]
    assert PR._open_sections(con, "BLG 322E", {"BLG"}) == "[bu dönem yalnız ek sınav açılmış]"
    assert PR._open_sections(con, "BLG 336E", {"BLG"}).startswith("[1 şube")


def test_YOL_HARITASI_ek_sinavi_okutulan_saymaz(katalog):
    acik = YH.bu_donem_okutulan(katalog[0])
    assert "BLG 336E" in acik and "BLG 401E" in acik
    assert not {"BLG 322E", "BLG 354E", "MAD 302E"} & acik


# ------------------------------------------------------------ sunucu
def _sinav_ekle(tmp_path):
    con = db.connect(tmp_path / "r.sqlite3", "schema.sql")
    con.execute("INSERT INTO course(code,name,credits,ects) VALUES ('BLG 322E','Ek',3,5)")
    con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled,teaching_method)"
                " VALUES ('15282','BLG 322E',0,0,'Ek Sınav')")
    con.execute("UPDATE lesson SET teaching_method='Physical (Face to face)' WHERE crn!='15282'")
    con.commit(); con.close()


def test_CRN_ile_yuklenen_sinav_etiketli(state, tmp_path):  # noqa: F811
    _sinav_ekle(tmp_path)
    bulunan = {f["crn"]: f for f in state.dispatch("/api/crn", {"crns": ["15282", "13524"]})["crn"]["found"]}
    assert bulunan["15282"]["sinav"] == "Ek sınav" and bulunan["15282"]["meetings"] == []
    assert bulunan["13524"]["sinav"] is None


def test_KATALOGDAN_eklemede_sinav_yok(state, tmp_path):  # noqa: F811
    _sinav_ekle(tmp_path)
    assert state.course_sections("BLG 322E")["found"] == []
    assert [i["course"] for i in state.search_catalog("BLG 322")["items"]] == []
    assert [i["course"] for i in state.search_catalog("GEO 303")["items"]] == ["GEO 303E"]


# ------------------------------------------------------------ arayüz
def test_ARAYUZ_etiketleri():
    src = open(UI.__file__, encoding="utf-8").read()
    assert "const saatsizYazi = (sec, kip) => sec && sec.sinav ? sec.sinav" in src
    assert "sinav: x.sinav || null," in src                       # CRN'den gelen şubede taşınıyor
    assert 'EK_SINAV:["yalnız ek sınav açılmış","unknown"]' in src
    assert '"BILINMIYOR","EK_SINAV"].forEach' in src
    assert "ek sınav şubesinin ders saati olmadığından takvim dosyasına" in src
    assert 'notimeGrup(sinavli, "Ek sınav",' in src
    # saatsiz şube yazısı TEK yerde (yardımcıda); başka yerde elle yazılmıyor
    assert src.count('"saati ilan edilmemiş"') == 1 and src.count('"saat ilan edilmemiş"') == 1


# ------------------------------------------------ denk derste dilekçesiz
# Kullanıcı (28.09.2026): "denk derslerde bölümümün kodu alabilir gözüküyorsa
# dilekçesiz de alabiliyorum".
def test_DENKLIK_bolume_acik_sube_dilekcesiz(tmp_path):
    from itucap import rules as R
    from test_acik_denklik import _sj
    con = db.connect(tmp_path / "r.sqlite3", "schema.sql")
    con.executemany("INSERT INTO course(code,name) VALUES (?,?)",
                    [("MAT 210E", "Hedef"), ("GEO 220E", "Açık"), ("MAT 281E", "Başka"),
                     ("KIM 101E", "İlansız")])
    for crn, kod, progs in (("100", "GEO 220E", ["BLGE", "GEOE"]), ("101", "GEO 220E", ["GEOE"]),
                            ("200", "MAT 281E", ["MATE"]), ("300", "KIM 101E", [])):
        con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled) VALUES (?,?,40,0)", (crn, kod))
        for p in progs:
            con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES (?,?)", (crn, p))
    con.commit()
    eq = [R.Equivalence(i, "MAT 210E", ((k, "DD"),), "official", True)
          for i, k in enumerate(("GEO 220E", "MAT 281E", "KIM 101E"), 1)]
    names = {r[0]: r[1] for r in con.execute("SELECT code, name FROM course")}
    out = UI._acik_denklikler(con, eq, {}, {"MAT 210E"}, {"BLGE", "GEOE", "MATE"}, names, _sj,
                              kendi_program="blge")
    k = {s["code"]: s for s in out[0]["sources"]}
    assert k["GEO 220E"]["dilekcesiz"] is True and k["GEO 220E"]["dilekcesizCrn"] == ["100"]
    assert k["MAT 281E"]["dilekcesiz"] is False                 # başka bölüme açık
    assert k["KIM 101E"]["dilekcesiz"] is False                 # alabilecekler ilan edilmemiş
    out = UI._acik_denklikler(con, eq, {}, {"MAT 210E"}, {"BLGE", "GEOE", "MATE"}, names, _sj)
    assert not any(s["dilekcesiz"] for s in out[0]["sources"])  # program bilinmiyorsa iddia yok
    # Faz 115 — anadal GEOE, şube yalnız GEO'ya (aynı bölümün Türkçe programı) açık
    con.execute("DELETE FROM lesson_allowed_program WHERE crn='100' AND program_code='BLGE'")
    con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES ('200','MAT_LS')")
    con.commit()
    out = UI._acik_denklikler(con, eq, {}, {"MAT 210E"}, {"BLGE", "GEOE", "MATE"}, names, _sj,
                              kendi_program="MATE")
    k = {s["code"]: s for s in out[0]["sources"]}
    assert k["MAT 281E"]["dilekcesiz"] is True and k["GEO 220E"]["dilekcesiz"] is False
    # ÇAP kodu: anadal HTAE, ÇAP GEO → GEO'ya açık şube dilekçesiz
    con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES ('101','GEO')"); con.commit()
    out = UI._acik_denklikler(con, eq, {}, {"MAT 210E"}, {"BLGE", "GEOE", "MATE"}, names, _sj,
                              kendi_program=["HTAE", "GEO"])
    assert {s["code"]: s for s in out[0]["sources"]}["GEO 220E"]["dilekcesiz"] is True


def test_DENKLIK_arayuz_dilekcesiz():
    src = open(UI.__file__, encoding="utf-8").read()
    assert "şubesi programınıza açık olduğundan <b>dilekçe gerekmez</b>" in src
    assert "olduğundan dilekçesiz alınabilir, diğerleri dilekçeyle saydırılır" in src
    assert 'k.dilekcesiz ? `<span class="chip prereq"' in src
    assert "[settings.anadal_program, *(x[3] for x in settings.seconds)])," in src
