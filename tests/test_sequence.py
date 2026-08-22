"""Faz 2 — önşart kademelendirmesi ve gizli ön yük analizi."""
import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    """Testler projenin gerçek config/denklikler.toml dosyasından etkilenmesin."""
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")

from itucap import db, prereq as P, sequence


@pytest.fixture()
def con(tmp_path):
    con = db.connect(tmp_path / "ref.sqlite3", "schema.sql")
    con.executemany(
        "INSERT INTO course(code,name,ects,prereq_raw) VALUES (?,?,?,?)",
        [
            ("BLG 102E", "Giriş", 8.0, None),
            ("BLG 223E", "Veri Yapıları", 8.0, "BLG 102E MIN DD"),
            ("BLG 335E", "Algoritma I", 4.5, "BLG 223E MIN DD"),
            ("BLG 354E", "Sinyaller", 6.0, "(MAT 281 MIN DDveya MAT 281E MIN DD)"),
            ("MAT 281", "Lineer Cebir", 4.0, None),
            ("MAT 281E", "Linear Algebra", 4.0, None),
            ("MAT 103E", "Matematik I", 6.0, None),
            ("SEC 301", "Anadal seçmelisi", 4.0, None),
        ],
    )
    # ÇAP planı
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title,source,is_term_based)
                   VALUES (1,'BLG','cap','ÇAP','obs',0)""")
    for i, code in enumerate(["BLG 102E", "BLG 223E", "BLG 335E", "BLG 354E"]):
        ects = con.execute("SELECT ects FROM course WHERE code=?", (code,)).fetchone()[0]
        con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,ects,position)
                       VALUES (1,'REQUIRED',?,?,?)""", (code, ects, i))
    # anadal planı
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title,source)
                   VALUES (2,'HTAE','lisans','anadal','obs')""")
    con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,ects,position,term_no)
                   VALUES (2,'REQUIRED','MAT 103E',6.0,0,1)""")
    con.commit()
    P.parse_all(con)
    return con


def test_tiers_follow_prereq_chain(con):
    steps = {s.course: s for s in sequence.plan_sequence(con, 1)}
    assert steps["BLG 102E"].tier == 0
    assert steps["BLG 223E"].tier == 1
    assert steps["BLG 335E"].tier == 2
    # plan İÇİNDE önşartı yok -> kademe 0 (dış önşart kademeyi belirlemez)
    assert steps["BLG 354E"].tier == 0


def test_blockers_and_external_are_separated(con):
    steps = {s.course: s for s in sequence.plan_sequence(con, 1)}
    assert steps["BLG 223E"].blockers == ["BLG 102E"]
    assert steps["BLG 223E"].external == []
    assert steps["BLG 354E"].blockers == []
    assert set(steps["BLG 354E"].external) == {"MAT 281", "MAT 281E"}


def test_status_reflects_grades(con):
    steps = {s.course: s for s in sequence.plan_sequence(con, 1, {"BLG 102E": "BB"})}
    assert steps["BLG 102E"].status == "DONE"
    assert steps["BLG 223E"].status == "READY"      # önşartı sağlandı
    assert steps["BLG 335E"].status == "PENDING"


def test_unknown_status_for_unparsable(con):
    con.execute("UPDATE course SET prereq_raw='Türkçe' WHERE code='BLG 335E'")
    con.commit()
    P.parse_all(con)
    steps = {s.course: s for s in sequence.plan_sequence(con, 1)}
    assert steps["BLG 335E"].status == "UNKNOWN"


def test_hidden_prerequisites_found(con):
    """MAT 281 hiçbir planda yok ama BLG 354E için gerekli -> gizli yük."""
    hidden = sequence.hidden_prerequisites(con, 1, 2)
    assert hidden == {"BLG 354E": ["MAT 281", "MAT 281E"]}


def test_hidden_ignores_requirements_covered_by_anadal(con):
    """Anadal planı dersi karşılıyorsa gizli yük DEĞİLDİR."""
    con.execute("UPDATE course SET prereq_raw='MAT 103E MIN DD' WHERE code='BLG 354E'")
    con.commit()
    P.parse_all(con)
    assert sequence.hidden_prerequisites(con, 1, 2) == {}


def test_hidden_respects_or_alternatives(con):
    """OR dalının bir üyesi planlardan karşılanıyorsa gizli yük yok."""
    con.execute(
        "UPDATE course SET prereq_raw='(MAT 281 MIN DDveya MAT 103E MIN DD)' "
        "WHERE code='BLG 354E'")
    con.commit()
    P.parse_all(con)
    assert sequence.hidden_prerequisites(con, 1, 2) == {}


def test_ects_falls_back_to_course_catalog(con):
    """Eski taramalarda plan_slot.ects boş; AKTS katalogdan tamamlanmalı.

    Aksi halde 'kalan 0 AKTS' gibi yanlış özet çıkıyordu (18.08.2026).
    """
    con.execute("UPDATE plan_slot SET ects=NULL WHERE plan_id=1")
    con.commit()
    steps = {s.course: s for s in sequence.plan_sequence(con, 1)}
    assert steps["BLG 102E"].ects == 8.0
    assert sum(s.ects or 0 for s in steps.values()) == 26.5


def test_format_runs(con):
    steps = sequence.plan_sequence(con, 1)
    text = sequence.format_sequence(steps, "test")
    assert "KADEME 0" in text and "Toplam: 4 ders" in text
    assert "GİZLİ ÖN YÜK" in sequence.format_hidden(
        sequence.hidden_prerequisites(con, 1, 2), con)
