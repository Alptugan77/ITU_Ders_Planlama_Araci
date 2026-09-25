"""Faz 92 — aynı dersin öbür dildeki kodu (EHB 222 ↔ EHB 222E).

Gerçek katalogda BLGE öğrencisi, ÇAP = EHB (plan "BLG_EHB", Türkçe kodlar):

* Anadalında EHB 222E'yi CC ile geçmiş. ÇAP planı aynı dersi "EHB 222" diye
  yazıyor. ÇAP paneli 0/16, "EHB 222 — bu dönem şube açılmamıştır" engeli,
  ÇAP ortalaması "bilinmiyor". (BLG öğrencisinin geçtiği EHB 222 ise iki
  planı da dolduruyordu — aynı ders, dile göre farklı hüküm.)
* ÇAP'ın EEF 262'sinin o dönem yalnız İngilizce şubesi açık (EEF 262E, EHB'ye
  açık). Araç "açılmamış" diyor ve önermiyordu. 13 ÇAP seçeneğinden 7'sinde
  aynı durum (MAT 175E, END 232E, KON 303E, FIZ 284E…).
* Dersi henüz almamış öğrencinin yol haritası dersi İKİ KEZ planlıyordu:
  anadalın EHB 222E'si 2026 Güz, ÇAP'ın EHB 222'si 2027 Güz.
"""
import sqlite3

import pytest

from itucap import basvuru as B
from itucap import config, db, plans as PL, prereq as P, recommend as REC
from itucap import rules as R, sequence as SEQ, student as S, ui as UI
from itucap import yolharitasi as YH


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


ANADAL, CAP = 10, 20


@pytest.fixture()
def dbs(tmp_path, monkeypatch):
    """BLGE anadal (EHB 222E, GEO 303) + EHB ÇAP (EHB 222, EEF 262, ABC 100)."""
    monkeypatch.setattr(config, "REF_DB", tmp_path / "ref.sqlite3")
    monkeypatch.setattr(config, "USER_DB", tmp_path / "user.sqlite3")
    con = db.connect(tmp_path / "ref.sqlite3", "schema.sql")
    ucon = db.connect(tmp_path / "user.sqlite3", "schema_user.sql")
    con.executemany(
        "INSERT INTO course(code,name,ects,credits,prereq_raw) VALUES (?,?,?,?,?)",
        [("EHB 222", "Elektroniğe Giriş", 5.0, 3.0, None),
         ("EHB 222E", "Introduction to Electronics", 5.0, 3.0, None),
         ("EEF 262", "Elektroniğin Temelleri", 6.0, 4.0, None),
         ("EEF 262E", "Fundamentals of Electronics", 6.0, 4.0, None),
         # Kredisi FARKLI: aynı ders olduğundan emin değiliz → eş sayılmaz.
         ("ABC 100", "Bir Ders", 5.0, 3.0, None),
         ("ABC 100E", "Another Course", 6.0, 4.0, None),
         ("GEO 303", "Kadastro", 3.0, 3.0, None),
         ("GEO 303E", "Cadastre", 3.0, 3.0, None),
         ("EHB 335", "Haberleşme", 5.0, 3.0, "EEF 262 MIN DD veya EEF 262E MIN DD"),
         ("EHB 335E", "Communication", 5.0, 3.0, "EEF 262 MIN DD veya EEF 262E MIN DD"),
         # ÇAP slotu İNGİLİZCE kodlu; yalnız Türkçe şubesi açık.
         ("FIZ 101", "Fizik I", 5.0, 3.0, None),
         ("FIZ 101E", "Physics I", 5.0, 3.0, None)])
    con.executemany("INSERT INTO program(code,name,level) VALUES (?,?,'LS')",
                    [("BLGE", "Bilgisayar Mühendisliği (İngilizce) Lisans"),
                     ("EHB", "Elektronik ve Haberleşme Mühendisliği Lisans")])
    con.execute("INSERT INTO plan(id,program_code,plan_type,title,source) "
                "VALUES (?,'BLGE','lisans','anadal','obs')", (ANADAL,))
    con.executemany(
        """INSERT INTO plan_slot(plan_id,slot_kind,course_code,credits,ects,position,term_no)
           VALUES (?,'REQUIRED',?,3.0,5.0,?,?)""",
        [(ANADAL, "EHB 222E", 0, 3), (ANADAL, "GEO 303", 1, 3)])
    con.execute("INSERT INTO plan(id,program_code,plan_type,title,source,is_term_based) "
                "VALUES (?,'EHB','cap','BLG_EHB','obs',0)", (CAP,))
    con.executemany(
        """INSERT INTO plan_slot(plan_id,slot_kind,course_code,credits,ects,position)
           VALUES (?,'REQUIRED',?,3.0,5.0,?)""",
        [(CAP, "EHB 222", 0), (CAP, "EEF 262", 1), (CAP, "ABC 100", 2), (CAP, "EHB 335", 3),
         (CAP, "FIZ 101E", 4)])
    # Şubeler: EHB 222 iki dilde de açık (farklı saatlerde — ikisi de sığar);
    # EEF 262 ve ABC 100 YALNIZ İngilizce; GEO 303 yalnız İngilizce.
    for crn, code, prog, gun in [("1", "EHB 222", "EHB", 1), ("2", "EHB 222E", "BLGE", 2),
                                 ("3", "EEF 262E", "EHB", 3), ("4", "ABC 100E", "EHB", 4),
                                 ("5", "GEO 303E", "BLGE", 5), ("6", "EHB 335E", "EHB", 1),
                                 ("7", "FIZ 101", "EHB", 4)]:
        con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled,building) "
                    "VALUES (?,?,50,0,'INB')", (crn, code))
        con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES (?,?)",
                    (crn, prog))
        con.execute("""INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min,building)
                       VALUES (?,?,510,630,'INB')""", (crn, gun))
    con.commit()
    con.row_factory = sqlite3.Row
    P.parse_all(con)
    sid = S.ensure_student(ucon)
    return con, ucon, sid


def _gecti(ucon, sid, code, grade="CC"):
    ucon.execute("""INSERT INTO earned_course(student_id,course_code,grade,status,source)
                    VALUES (?,?,?,'PASSED','test')""", (sid, code, grade))
    ucon.commit()


def _slot(con, plan, code):
    return con.execute("SELECT id FROM plan_slot WHERE plan_id=? AND course_code=?",
                       (plan, code)).fetchone()[0]


# ================================================================ kural
@pytest.mark.parametrize("kod,es", [
    ("EHB 222", "EHB 222E"), ("EHB 222E", "EHB 222"),
    ("ABC 100", None),            # kredi farklı
    ("ZZZ 999", None),            # katalogda yok
    ("", None)])
def test_DIL_ESI_katalogla_dogrulaniyor(dbs, kod, es):
    con, _, _ = dbs
    assert R.dil_esi(con, kod) == es


# ============================================ geçilmiş ders öbür dilde
def test_GECILMIS_es_CAP_slotunu_dolduruyor(dbs):
    con, ucon, sid = dbs
    _gecti(ucon, sid, "EHB 222E")
    g = S.grades(ucon, sid)
    f = R.slot_satisfied(con, _slot(con, CAP, "EHB 222"), g)
    assert f.satisfied and f.course == "EHB 222E"
    assert R.slot_satisfied(con, _slot(con, ANADAL, "EHB 222E"), g).satisfied
    # Kredisi farklı "eş" doldurmuyor.
    _gecti(ucon, sid, "ABC 100E")
    assert not R.slot_satisfied(con, _slot(con, CAP, "ABC 100"), S.grades(ucon, sid)).satisfied


def test_ANADAL_slotunu_es_doldurmuyor(dbs):
    """İngilizce programın zorunlu dersini öbür dildeki şubenin karşılayıp
    karşılamadığı programın kendi kuralı — araç bilemez, "tamamlandı"
    demiyor. (ÇAP planı ise bölüme tanımlı, dile değil.)"""
    con, ucon, sid = dbs
    _gecti(ucon, sid, "GEO 303E")
    g = S.grades(ucon, sid)
    assert not R.slot_satisfied(con, _slot(con, ANADAL, "GEO 303"), g).satisfied
    assert {s.course: s.status for s in SEQ.plan_sequence(con, ANADAL, g)}["GEO 303"] != "DONE"
    assert R.dil_serbest("cap") and R.dil_serbest("yandal") and not R.dil_serbest("lisans")


def test_YON_turkce_ders_ingilizce_slotu_doldurmuyor(dbs):
    """İngilizce → Türkçe slot otomatik; TERSİ değil (Faz 10, HTA/HTAE
    ilkesi: Türkçe ders İngilizce dersin yerine geçmeyebilir — `discover`
    düşük güvenli öneri yapar, karar kullanıcının)."""
    con, ucon, sid = dbs
    assert R.ingilizce_esi(con, "EHB 222") == "EHB 222E"
    assert R.ingilizce_esi(con, "EHB 222E") is None
    _gecti(ucon, sid, "FIZ 101")
    g = S.grades(ucon, sid)
    assert not R.slot_satisfied(con, _slot(con, CAP, "FIZ 101E"), g).satisfied
    assert "FIZ 101" not in R.plan_codes(con, CAP, esler=True)
    s = B.survey(con, ucon, sid, "cap", exclude={"BLGE"})
    assert "FIZ 101" not in [o for o in s.options if o.program_code == "EHB"][0].already
    # İngilizce slot için Türkçe şube önerilmiyor; engel "açılmamış".
    assert "FIZ 101" not in {c.course for c in _adaylar(con, ucon, sid)}
    engel = {b.course: b.reason for b in REC.cap_blockers(
        con, ucon, sid, CAP, "EHB", ["BLGE", "EHB"], dil_esi=True)}
    assert engel.get("FIZ 101E") == "ACILMAMIS"


def test_ILERLEME_ve_KADEME_ayni_hukum(dbs):
    con, ucon, sid = dbs
    _gecti(ucon, sid, "EHB 222E")
    g = S.grades(ucon, sid)
    assert R.plan_progress(con, CAP, g)["slots_done"] == 1
    durum = {s.course: s.status for s in SEQ.plan_sequence(con, CAP, g)}
    assert durum["EHB 222"] == "DONE"


def test_CAP_ORTALAMASI_esi_sayiyor(dbs):
    con, ucon, sid = dbs
    _gecti(ucon, sid, "EHB 222E", "BB")
    taban = UI._ikinci_gno_tabani(con, ucon, sid, [
        {"kind": "cap", "planId": CAP, "label": "ÇAP", "program": "EHB"}])
    assert taban and taban[0]["credits"] == 3.0 and "EHB 222E" in taban[0]["codes"]
    # Varsayılan `plan_codes` eşi KATMIYOR (katalog tabanı gibi gezenler için).
    assert "EHB 222E" not in R.plan_codes(con, CAP)
    assert "EHB 222E" in R.plan_codes(con, CAP, esler=True)


def test_BASVURU_zaten_sayilan_esi_goruyor(dbs):
    con, ucon, sid = dbs
    _gecti(ucon, sid, "EHB 222E")
    s = B.survey(con, ucon, sid, "cap", exclude={"BLGE"})
    ehb = [o for o in s.options if o.program_code == "EHB"][0]
    assert ehb.already == ["EHB 222E"]


# ============================================== bu dönem açık olan eş
def _adaylar(con, ucon, sid):
    return REC.candidates(con, ucon, sid, ANADAL, CAP, "BLGE", "EHB",
                          allowed_programs=["BLGE", "EHB"])


def test_CAP_slotu_esin_subesini_oneriyor(dbs):
    con, ucon, sid = dbs
    kodlar = {c.course: c for c in _adaylar(con, ucon, sid)}
    assert kodlar["EEF 262E"].role == "CAP"             # Türkçesi açılmamış
    assert "ABC 100E" not in kodlar                     # kredi farklı → eş değil


def test_ANADAL_slotu_genisletilmiyor(dbs):
    """İngilizce programdaki öğrenciye anadal slotu için öbür dilin şubesi
    önerilmiyor (dil şartı ayrı bir karar)."""
    con, ucon, sid = dbs
    kodlar = {c.course for c in _adaylar(con, ucon, sid)}
    assert "GEO 303E" not in kodlar and "GEO 303" not in kodlar


def test_AYNI_DERSIN_IKI_DILI_ayni_programda_yok(dbs):
    """EHB 222 (ÇAP slotu) ile EHB 222E (anadal + ÇAP) ayrı slotlara
    eşleşebiliyor ve saatleri çakışmıyor — yine de ikisi birlikte olmaz."""
    con, ucon, sid = dbs
    adaylar = _adaylar(con, ucon, sid)
    kod = {c.course for c in adaylar}
    assert {"EHB 222", "EHB 222E"} <= kod
    sonuc = REC.build_schedules(adaylar, max_load=30, limit=10)
    assert sonuc
    for s in sonuc:
        dersler = set(s.courses())
        assert not {"EHB 222", "EHB 222E"} <= dersler, dersler
    assert any(dersler & {"EHB 222", "EHB 222E"} for dersler in map(set, (s.courses() for s in sonuc)))


def test_ENGEL_esin_subesine_bakiyor(dbs):
    con, ucon, sid = dbs
    cap = {b.course: b.reason for b in REC.cap_blockers(
        con, ucon, sid, CAP, "EHB", ["BLGE", "EHB"], dil_esi=True)}
    assert "EEF 262" not in cap                  # İngilizce şubesi açık, önşart yok
    assert cap.get("ABC 100") == "ACILMAMIS"     # eş değil
    # Önşart eşin üzerinden bakılıyor ama engel PLANIN koduyla yazılıyor.
    assert cap.get("EHB 335") == "ONSART" and "EHB 335E" not in cap
    eski = {b.course: b.reason for b in REC.cap_blockers(
        con, ucon, sid, CAP, "EHB", ["BLGE", "EHB"])}
    assert eski.get("EEF 262") == "ACILMAMIS"    # bayraksız (anadal) eski davranış


# ======================================================= yol haritası
def test_YOL_HARITASI_dersi_iki_kez_planlamiyor(dbs):
    con, ucon, sid = dbs
    names = {r[0]: r[1] for r in con.execute("SELECT code, name FROM course")}
    birimler = YH._birimler(con, [{"planId": ANADAL, "role": "ANADAL"},
                                  {"planId": CAP, "role": "CAP"}],
                            S.grades(ucon, sid), [], names)
    ehb = [b for b in birimler if b.kodlar & {"EHB 222", "EHB 222E"}]
    assert len(ehb) == 1, [(b.ders, b.roller) for b in ehb]
    assert ehb[0].roller == {"ANADAL", "CAP"}


def test_ARAYUZ_engel_listesi_esi_goruyor(dbs):
    """`ui.collect` ÇAP engellerini dil eşiyle soruyor; anadalınkini değil."""
    con, ucon, sid = dbs
    st = config.Settings(anadal_program="BLGE", cap_program="EHB", second_kind="cap",
                         program_codes=["BLGE", "EHB"])
    d = UI.collect(con, ucon, sid, st, 10, None, seconds=PL.resolve_seconds(con, st))
    cap = {b["course"]: b["reason"] for b in d["blockers"] if b["role"] == "CAP"}
    assert "EEF 262" not in cap and cap.get("ABC 100") == "ACILMAMIS", cap
