"""Faz 22 — CRN'den program yükleme.

Kullanıcı isteği 23.08.2026: *"CRN ile program yükleme olursa iyi olur"*.
OBS'de kaydını yaptıktan sonra CRN'leri yapıştırıp GERÇEK programını görmek.

★ İki kararın testleri burada:
  1. Planında OLMAYAN ders de yükleniyor — gizleseydik kullanıcı gerçek
     programını göremezdi (serbest seçmeli, ortak zorunlu, başka bölüm dersi).
  2. Bulunamayan CRN sessizce ATILMIYOR — 8 yapıştırıp 6 ders görürsen
     hangi ikisinin düştüğünü bilmelisin.
"""
import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import config, db, ui as UI


@pytest.fixture()
def state(tmp_path, monkeypatch):
    from itucap import server as SRV

    monkeypatch.setattr(config, "REF_DB", tmp_path / "r.sqlite3")
    monkeypatch.setattr(config, "USER_DB", tmp_path / "u.sqlite3")
    monkeypatch.setattr(config.Settings, "load",
                        classmethod(lambda cls, path=None: config.Settings(
                            anadal_program="HTAE", cap_program="BLG",
                            second_kind="cap", program_codes=["HTAE", "BLG"],
                            term="202610")))
    con = db.connect(tmp_path / "r.sqlite3", "schema.sql")
    con.executemany("INSERT INTO course(code,name,credits,ects) VALUES (?,?,?,?)",
                    [("GEO 303E", "Kadastro", 3.0, 3.0),
                     ("BLG 212E", "Mikroişlemci", 3.0, 7.0),
                     ("ITB 121", "Serbest Seçmeli", 2.0, 3.0)])
    con.execute("INSERT INTO plan(id,program_code,plan_type,title,source) "
                "VALUES (10,'HTAE','lisans','anadal','obs')")
    con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,credits,position) "
                "VALUES (10,'REQUIRED','GEO 303E',3.0,0)")
    con.execute("INSERT INTO plan(id,program_code,plan_type,title,source,is_term_based) "
                "VALUES (20,'BLG','cap','ÇAP','obs',0)")
    con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,credits,position) "
                "VALUES (20,'REQUIRED','BLG 212E',3.0,0)")
    for crn, code, gun in [("13524", "GEO 303E", 1), ("12486", "BLG 212E", 3),
                           ("10123", "ITB 121", 5)]:
        con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled,building) "
                    "VALUES (?,?,40,12,'INB')", (crn, code))
        con.execute("""INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min,building)
                       VALUES (?,?,510,630,'INB')""", (crn, gun))
    con.commit()
    con.close()
    return SRV.State()


def _coz(state, *crns):
    return state.dispatch("/api/crn", {"crns": list(crns)})["crn"]


# ------------------------------------------------------------- çözümleme
def test_crn_derse_cevriliyor(state):
    out = _coz(state, "13524")
    assert [(x["crn"], x["course"], x["name"]) for x in out["found"]] == \
        [("13524", "GEO 303E", "Kadastro")]
    assert out["found"][0]["meetings"][0]["day"] == 1


def test_rol_plandan_geliyor(state):
    rol = {x["course"]: x["role"] for x in _coz(state, "13524", "12486")["found"]}
    assert rol == {"GEO 303E": "ANADAL", "BLG 212E": "CAP"}


def test_plan_disi_ders_de_YUKLENIYOR(state):
    """★ Gizleseydik kullanıcı gerçek programını göremezdi."""
    out = _coz(state, "10123")
    assert out["found"][0]["course"] == "ITB 121"
    assert out["found"][0]["role"] == "PLAN_DISI"


def test_bulunamayan_crn_RAPORLANIYOR(state):
    """★ Sessizce atmak, yanlış derse kayıt olmuş sanmaya yol açardı."""
    out = _coz(state, "13524", "99999")
    assert [x["crn"] for x in out["found"]] == ["13524"]
    assert out["missing"] == ["99999"]


def test_tekrar_eden_crn_bir_kez(state):
    assert len(_coz(state, "13524", "13524", " 13524 ")["found"]) == 1


def test_metin_icinden_ayiklaniyor(state):
    """Kullanıcı OBS'den kopyaladığını olduğu gibi yapıştırabilmeli."""
    out = _coz(state, "CRN: 13524,", "12486;")
    assert {x["crn"] for x in out["found"]} == {"13524", "12486"}


def test_bos_girdi_patlamiyor(state):
    out = _coz(state)
    assert out == {"found": [], "missing": []}


def test_sira_KORUNUYOR(state):
    """Yapıştırma sırası, kullanıcının OBS ekranındaki sırası olabilir."""
    assert [x["crn"] for x in _coz(state, "12486", "13524")["found"]] == \
        ["12486", "13524"]


# ------------------------------------------------------------------ arayüz
def test_sablon_crn_yukleme_kuruyor(state):
    html = UI.render(state.snapshot())
    for parca in ("crnLoad", "crnLoadDialog", "loadFromCrn", "/api/crn",
                  "PLAN_DISI"):
        assert parca in html, parca


def test_plan_disi_rengi_tanimli(state):
    html = UI.render(state.snapshot())
    assert ".tag.PLAN_DISI{" in html
    assert '.blk[data-role="PLAN_DISI"]' in html
