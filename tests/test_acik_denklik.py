"""Denkliği açık gereken dersler (kullanıcı isteği 27.08.2026).

*"küçük bir sekmede almam gereken derslerin eğer denkliği olan bir ders
açıksa onları listeleyip bilgilerini gösteren bir kısım ekler misin"*

Denklik yönü: `{kaynaklar} → hedef`. Kaynak dersleri alınca hedef sağlanır.
Yani gereken 'hedef' yerine bu dönem AÇIK olan 'kaynak' alınabilir.
"""
import sqlite3

import pytest

from itucap import db
from itucap import rules as R
from itucap import ui as UI


def _sj(sec):
    """section_json yerine sade bir seri hâl — testte yeter."""
    return {"crn": sec.crn, "free": sec.free, "capacity": sec.capacity,
            "enrolled": sec.enrolled, "online": sec.online,
            "instructor": sec.instructor,
            "meetings": [{"day": m.day, "start": m.start, "end": m.end,
                          "building": m.building, "campus": m.campus}
                         for m in sec.meetings]}


@pytest.fixture()
def con(tmp_path):
    c = db.connect(tmp_path / "r.sqlite3", "schema.sql")
    c.executemany("INSERT INTO course(code,name,credits,ects) VALUES (?,?,?,?)",
                  [("MAT 210E", "Engineering Math", 3, 4),
                   ("GEO 220E", "Geomatik Mat", 3, 4),
                   ("MAT 281E", "Linear Algebra", 3, 4),
                   ("GEO 109E", "Vector Algebra", 3, 4),
                   ("KAPALI 1", "Kapali Ders", 3, 4)])
    # GEO 220E ve GEO 109E AÇIK (şubesi var); KAPALI 1 kapalı.
    for crn, code in (("100", "GEO 220E"), ("200", "GEO 109E")):
        c.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled) VALUES (?,?,40,0)",
                  (crn, code))
        c.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES (?,'HTAE')", (crn,))
        c.execute("""INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min,building)
                     VALUES (?,1,540,630,'INB')""", (crn,))
    c.commit()
    return c


def _eq(tid, target, sources, conf="user_declared"):
    return R.Equivalence(tid, target, tuple((s, "DD") for s in sources), conf, True)


def _names(con):
    return {r[0]: r[1] for r in con.execute("SELECT code, name FROM course")}


# ============================================== temel dava
def test_gereken_dersin_ACIK_denkligi_LISTELENIYOR(con):
    """★ MAT 210E gerekiyor (beyan), denkliği GEO 220E açık → görünmeli,
    bilgileriyle (CRN, şube)."""
    eq = [_eq(1, "MAT 210E", ["GEO 220E"])]
    out = UI._acik_denklikler(con, eq, {}, set(), {"HTAE"}, _names(con), _sj)
    assert len(out) == 1
    e = out[0]
    assert e["target"] == "MAT 210E" and e["declared"] is True
    k = e["sources"][0]
    assert k["code"] == "GEO 220E" and k["open"] is True
    assert k["sections"][0]["crn"] == "100"


def test_KAPALI_denklik_gosterilmiyor(con):
    """Kaynağın şubesi yoksa eyleme dönük bir şey yok."""
    eq = [_eq(1, "MAT 210E", ["KAPALI 1"])]
    assert UI._acik_denklikler(con, eq, {}, set(), {"HTAE"}, _names(con), _sj) == []


def test_ZATEN_SAGLANMIS_hedef_gosterilmiyor(con):
    """Hedefi zaten almışsan (ya da denklikle kazandıysan) gösterme."""
    eq = [_eq(1, "MAT 210E", ["GEO 220E"])]
    expanded = {"MAT 210E": "BB"}       # zaten geçilmiş sayılıyor
    assert UI._acik_denklikler(con, eq, expanded, set(), {"HTAE"}, _names(con), _sj) == []


def test_KAYNAGI_ALINMIS_denklik_gosterilmiyor(con):
    """Kaynağı zaten aldıysan denklik zaten uygulanır; 'al' demek anlamsız."""
    eq = [_eq(1, "MAT 210E", ["GEO 220E"])]
    expanded = {"GEO 220E": "AA"}
    assert UI._acik_denklikler(con, eq, expanded, set(), {"HTAE"}, _names(con), _sj) == []


# ============================================== resmî vs beyan
def test_RESMI_denklik_yalniz_GEREKEN_hedefte(con):
    """⚠️ Resmî denklik katalog çapında; hedefi gerçekten gereken bir plan
    dersi değilse gürültü olur → gösterilmez. Beyan ise niyeti bildirir."""
    resmi = [_eq(1, "MAT 210E", ["GEO 220E"], conf="official")]
    # Gereken listede DEĞİL → resmî gösterilmez.
    assert UI._acik_denklikler(con, resmi, {}, set(), {"HTAE"}, _names(con), _sj) == []
    # Gereken listede → gösterilir.
    out = UI._acik_denklikler(con, resmi, {}, {"MAT 210E"}, {"HTAE"}, _names(con), _sj)
    assert len(out) == 1 and out[0]["needed"] is True


# ============================================== çok kaynaklı
def test_COK_KAYNAKLI_kapali_olan_DURUSTCE_isaretli(con):
    """{GEO 220E, KAPALI 1} → hedef. Biri açık biri kapalı: gösterilir ama
    allReady=False (tek başına açık kaynak hedefi tamamlamaz)."""
    eq = [_eq(1, "MAT 210E", ["GEO 220E", "KAPALI 1"])]
    out = UI._acik_denklikler(con, eq, {}, set(), {"HTAE"}, _names(con), _sj)
    assert len(out) == 1
    assert out[0]["allReady"] is False
    durum = {k["code"]: k["open"] for k in out[0]["sources"]}
    assert durum == {"GEO 220E": True, "KAPALI 1": False}


# ============================================== dil varyantı tekleşiyor
def test_DIL_VARYANTI_tek_satir(con):
    """MAT 210E ve MAT 210 aynı kaynaktan aynı şeyi anlatır; tek satır."""
    con.execute("INSERT INTO course(code,name,credits,ects) VALUES ('MAT 210','Muh Mat',3,4)")
    con.commit()
    eq = [_eq(1, "MAT 210E", ["GEO 220E"]), _eq(2, "MAT 210", ["GEO 220E"])]
    out = UI._acik_denklikler(con, eq, {}, set(), {"HTAE"}, _names(con), _sj)
    assert len(out) == 1


# ============================================== arayüz ve payload
def test_arayuzde_BOLUM_var():
    src = open(UI.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
    assert 'id="denklikSection"' in src
    assert "function renderAcikDenklik()" in src
    assert '"openEquivalents"' in src
    # Bölüm çubuğunda ve kurulum/yazdırma gizleme listelerinde.
    assert '"denklikSection", "Denkliği açık"' in src


def test_program_kapali_kaynak_ELENIYOR(con):
    """Şubesi öğrencinin programına kapalıysa 'açık' sayılmaz."""
    con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled) VALUES ('300','GEO 220E',40,0)")
    con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES ('100','BASKA')")
    # 100'ün tek izni BASKA'ya çevrildi; 300'ün hiç izni yok (herkese açık).
    con.execute("DELETE FROM lesson_allowed_program WHERE crn='100'")
    con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES ('100','BASKA')")
    con.commit()
    eq = [_eq(1, "MAT 210E", ["GEO 220E"])]
    out = UI._acik_denklikler(con, eq, {}, set(), {"HTAE"}, _names(con), _sj)
    # 300 herkese açık (izin satırı yok) → hâlâ açık görünür.
    assert len(out) == 1
    assert any(s["crn"] == "300" for s in out[0]["sources"][0]["sections"])
    assert all(s["crn"] != "100" for s in out[0]["sources"][0]["sections"])
