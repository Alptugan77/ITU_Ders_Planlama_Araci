"""OBS DersPlanDenklikleri scraper + arayüz eşleşmesi (kullanıcı isteği
28.08.2026: *"ders denkliklerini bu siteden çekmek lazım"*).

Gerçek sayfanın biçimi:
*   Sütun 0 "Course At The Plan" = HEDEF; kod isme YAPIŞIK ("BLG 202Numerical").
*   Sütun 1 "Equivalent Course" = <br> ile ayrılmış ALTERNATİFLER (OR).
Eski parser `\\b...\\b` ile yapışık koddan hiçbir şey çıkaramıyordu (satırlar
sessizce düşüyordu) ve tüm kaynakları TEK denkliğin AND kaynağı sanıyordu.
"""
import re
import pathlib

import pytest

from itucap import db
from itucap import rules as R
from itucap import ui as UI
from itucap.sources import obs_equivalence as EQ

FIX = pathlib.Path(__file__).parent / "fixtures" / "ders_denklik_blg.html"
KOD = re.compile(r"^[A-ZÇĞİÖŞÜ]{2,4} \d{3,4}[A-Z]?$")


# ============================================== _lead_code birim
@pytest.mark.parametrize("text,expected", [
    ("BLG 202Numerical Methods in CE", "BLG 202"),      # ★ yapışık: isim harfi yutulmaz
    ("GEO 220Mathematics for Geomatics Eng.", "GEO 220"),
    ("MAT 210 Mühendislik Matematiği", "MAT 210"),      # boşluklu
    ("BLG 202E Something", "BLG 202E"),                 # gerçek dil eki (ardında boşluk) korunur
    ("BLG 4901Advanced Design", "BLG 4901"),            # 4 haneli, isim yutulmaz
    ("Sadece isim, kod yok", None),
])
def test_lead_code(text, expected):
    assert EQ._lead_code(text) == expected


# ============================================== parse_table (gerçek fixture)
@pytest.fixture()
def parsed(tmp_path):
    con = db.connect(tmp_path / "r.sqlite3", "schema.sql")
    EQ.parse_table(con, FIX.read_text(encoding="utf-8"), 2229, "obs://test")
    con.commit()
    return con


def _pairs(con):
    return {(t, s) for t, s in con.execute(
        "SELECT e.target_course, x.course_code FROM equivalence e "
        "JOIN equivalence_source x ON x.equivalence_id=e.id")}


def test_OR_alternatifleri_AYRI_denklik(parsed):
    """★ 'BLG 202 ≡ BBF 202 / CEN 202 / MAT 202' — üçü ALTERNATİF (OR).
    Tek denklikte üç AND-kaynağı sanılırsa 'hepsini al' derdi; AYRI olmalı."""
    pairs = _pairs(parsed)
    assert ("BLG 202", "MAT 202") in pairs
    assert ("BLG 202", "CEN 202") in pairs
    assert ("BLG 202", "BBF 202") in pairs
    # Her denklik TEK kaynaklı (OR alternatifleri ayrı satır).
    counts = [c for (c,) in parsed.execute(
        "SELECT COUNT(*) FROM equivalence_source GROUP BY equivalence_id")]
    assert counts and all(c == 1 for c in counts)


def test_YAPISIK_koddan_isim_SIZMIYOR(parsed):
    """Hedef ve kaynak kodları temiz — 'BLG 202NUMERICAL' gibi sızıntı yok."""
    for (t,) in parsed.execute("SELECT DISTINCT target_course FROM equivalence"):
        assert KOD.match(t), f"kirli hedef: {t!r}"
    for (s,) in parsed.execute("SELECT DISTINCT course_code FROM equivalence_source"):
        assert KOD.match(s), f"kirli kaynak: {s!r}"


def test_RESMI_ve_ham_metin(parsed):
    """Denklikler 'official'; ham satır note_raw'da (yanlış ayrıştırma görülsün)."""
    confs = {c for (c,) in parsed.execute("SELECT DISTINCT confidence FROM equivalence")}
    assert confs == {"official"}
    raw = parsed.execute("SELECT note_raw FROM equivalence WHERE target_course='BLG 202' "
                         "LIMIT 1").fetchone()[0]
    assert "≡" in raw and re.search(r"(BBF|CEN|MAT) 202", raw)


def test_BASKA_BOLUM_kaynagi_yakalaniyor(parsed):
    """BLG 317 ← BBF 302: başka bölüm dersi (dilekçe kazancı) kaynak olabiliyor."""
    assert ("BLG 317", "BBF 302") in _pairs(parsed)


# ============================================== arayüz eşleşmesi (taban↔E dil eşi)
def _sj(s):
    return {"crn": s.crn, "free": s.free, "capacity": s.capacity, "enrolled": s.enrolled,
            "online": s.online, "instructor": s.instructor,
            "meetings": [{"day": m.day, "start": m.start, "end": m.end,
                          "building": m.building, "campus": m.campus} for m in s.meetings]}


def test_TABAN_kod_E_li_gerekene_eslesiyor_ve_GRUPLANIYOR(tmp_path):
    """★★ OBS 'BLG 202' (taban) ↔ plan 'BLG 202E'. Eşleşmezse denklik sessizce
    görünmez. Ayrıca aynı hedefin OR alternatifleri TEK satırda gruplanır."""
    con = db.connect(tmp_path / "r.sqlite3", "schema.sql")
    con.executemany("INSERT INTO course(code,name,credits,ects) VALUES (?,?,3,4)",
                    [("BLG 202E", "Numerical Methods"), ("MAT 202", "Sayısal Yöntemler"),
                     ("MAT 202E", "Numerical Methods"), ("CEN 202E", "Prog")])
    # MAT 202 AÇIK (şube), CEN 202E kapalı.
    con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled) VALUES ('900','MAT 202',40,0)")
    con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES ('900','HTAE')")
    con.execute("INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min,building)"
                " VALUES ('900',1,540,630,'INB')")
    con.commit()
    names = {r[0]: r[1] for r in con.execute("SELECT code,name FROM course")}
    # İki resmi denklik, aynı hedef (BLG 202 tabanı), iki alternatif kaynak.
    eqs = [R.Equivalence(1, "BLG 202", (("MAT 202", "DD"),), "official", True),
           R.Equivalence(2, "BLG 202", (("CEN 202", "DD"),), "official", True)]
    out = UI._acik_denklikler(con, eqs, {}, {"BLG 202E"}, {"HTAE"}, names, _sj)
    assert len(out) == 1                       # gruplandı
    e = out[0]
    assert e["target"] == "BLG 202E"           # ★ E'li plan kodu gösteriliyor
    assert e["mode"] == "or" and e["needed"] is True and e["declared"] is False
    kodlar = {k["code"] for k in e["sources"]}
    assert {"MAT 202", "CEN 202"} <= kodlar
    acik = [k for k in e["sources"] if k["open"]]
    assert [k["code"] for k in acik] == ["MAT 202"]     # dil eşi şubesi bulundu, CEN kapalı


def test_RESMI_yalniz_GEREKEN_hedefte(tmp_path):
    """Resmi denklik hedefi gereken DEĞİLSE gösterilmez (katalog çapında gürültü)."""
    con = db.connect(tmp_path / "r.sqlite3", "schema.sql")
    con.executemany("INSERT INTO course(code,name,credits,ects) VALUES (?,?,3,4)",
                    [("BLG 202E", "Numerical"), ("MAT 202", "Sayısal")])
    con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled) VALUES ('900','MAT 202',40,0)")
    con.execute("INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min,building)"
                " VALUES ('900',1,540,630,'INB')")
    con.commit()
    names = {r[0]: r[1] for r in con.execute("SELECT code,name FROM course")}
    eqs = [R.Equivalence(1, "BLG 202", (("MAT 202", "DD"),), "official", True)]
    # gereken BOŞ → resmi denklik gösterilmez
    assert UI._acik_denklikler(con, eqs, {}, set(), {"HTAE"}, names, _sj) == []
    # gereken'de → gösterilir
    out = UI._acik_denklikler(con, eqs, {}, {"BLG 202E"}, {"HTAE"}, names, _sj)
    assert len(out) == 1 and out[0]["needed"] is True


# ============================================== tüm programlar (sweep_all)
def test_program_options_LISANS_suzuyor():
    """Program menüsünden id/ad; 'Undergraduate' süzgeci grad'ı eler."""
    html = ('<select id="programId">'
            '<option value="">Please select</option>'
            '<option value="871">Computer Engineering Undergraduate</option>'
            '<option value="907">Computer Engineering (English) Undergraduate</option>'
            '<option value="936">Computer Engineering MSc</option>'
            '<option value="1247">Geomatics Engineering Undergraduate</option>'
            '</select>')
    ug = EQ.program_options(html, undergrad_only=True)
    ids = {i for i, _ in ug}
    assert 871 in ids and 1247 in ids
    assert 936 not in ids                          # MSc elenir
    assert all("Undergraduate" in n for _, n in ug)
    assert len(EQ.program_options(html, undergrad_only=False)) == 4    # id'li hepsi


def test_PROGRAMLAR_ARASI_tekillestirme(tmp_path):
    """Aynı denklik iki programın sayfasında da çıkabilir; paylaşılan `seen`
    ile ikinci kez YAZILMAZ (yoksa tabloda çoğalırdı)."""
    con = db.connect(tmp_path / "r.sqlite3", "schema.sql")
    html = FIX.read_text(encoding="utf-8")
    seen: set = set()
    n1 = EQ.parse_table(con, html, 2229, "a", seen=seen)
    n2 = EQ.parse_table(con, html, 2229, "b", seen=seen)   # aynı içerik, paylaşılan seen
    assert n1 > 0 and n2 == 0


# ============================================== ayar + arayüz metni
def test_ayar_ve_arayuz_kancalari():
    import itucap.config as C
    assert "eq_program_ids" in C.Settings.__dataclass_fields__
    assert "eq_all_programs" in C.Settings.__dataclass_fields__
    src = open(UI.__file__, encoding="utf-8").read()
    assert 'mode === "or"' in src                 # OR/AND ayrımı arayüzde
    assert "dilekçeyle" in src                     # dilekçe çerçevesi
    assert "başka bölüm" in src.lower() or "başka bölümden" in src
