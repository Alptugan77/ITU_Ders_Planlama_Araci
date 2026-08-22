"""Faz 3+4 — transkript girişi, slot eşlemesi, ilerleme paneli."""
import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    """Testler projenin gerçek config/denklikler.toml dosyasından etkilenmesin."""
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")

from itucap import db, prereq as P, progress as PR, student as S


@pytest.fixture()
def dbs(tmp_path, monkeypatch):
    from itucap import config
    monkeypatch.setattr(config, "REF_DB", tmp_path / "ref.sqlite3")
    monkeypatch.setattr(config, "USER_DB", tmp_path / "user.sqlite3")
    con = db.connect(tmp_path / "ref.sqlite3", "schema.sql")
    ucon = db.connect(tmp_path / "user.sqlite3", "schema_user.sql")
    con.executemany(
        "INSERT INTO course(code,name,ects,prereq_raw) VALUES (?,?,?,?)",
        [
            ("MAT 103E", "Matematik I", 6.0, None),
            ("BLG 102E", "Giriş", 8.0, None),
            ("BLG 223E", "Veri Yapıları", 8.0, "BLG 102E MIN CC"),
            ("BLG 335E", "Algoritma", 4.5, "BLG 223E MIN DD"),
            ("SEC 301", "Seçmeli", 4.0, None),
        ],
    )
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title,source)
                   VALUES (10,'HTAE','lisans','anadal','obs')""")
    con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,ects,position,term_no)
                   VALUES (10,'REQUIRED','MAT 103E',6.0,0,1)""")
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title,source,is_term_based)
                   VALUES (20,'BLG','cap','ÇAP','obs',0)""")
    for i, code in enumerate(["BLG 102E", "BLG 223E", "BLG 335E"]):
        ects = con.execute("SELECT ects FROM course WHERE code=?", (code,)).fetchone()[0]
        con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,ects,position)
                       VALUES (20,'REQUIRED',?,?,?)""", (code, ects, i))
    cur = con.execute(
        """INSERT INTO plan_slot(plan_id,slot_kind,pool_label_raw,pool_category,ects,position)
           VALUES (20,'ELECTIVE_POOL','Seçmeli (MT)','MT',4.0,3)""")
    con.execute("INSERT INTO pool_option(slot_id,course_code) VALUES (?,'SEC 301')",
                (cur.lastrowid,))
    con.commit()
    P.parse_all(con)
    return con, ucon


# --------------------------------------------------------------- satır çözme
@pytest.mark.parametrize("line,code,grade,status", [
    ("MAT 103E AA", "MAT 103E", "AA", "PASSED"),
    ("MAT103E,BB", "MAT 103E", "BB", "PASSED"),
    ("  mat 103e cc  ", "MAT 103E", "CC", "PASSED"),
    ("MAT 103E FF", "MAT 103E", "FF", "FAILED"),
    ("MAT 103E --", "MAT 103E", None, "IN_PROGRESS"),
    ("MAT 103E ?", "MAT 103E", None, "IN_PROGRESS"),
])
def test_parse_line(line, code, grade, status):
    entry = S.parse_line(line)
    assert (entry.course_code, entry.grade, entry.status) == (code, grade, status)


def test_missing_grade_assumes_worst_case():
    """Not yazılmadıysa geçti sayılır ama DD kabul edilir — yanlış 'alabilirsin' demesin."""
    entry = S.parse_line("MAT 103E")
    assert entry.status == "PASSED"
    assert entry.grade == "DD"
    assert entry.grade_known is False


def test_comments_and_blanks_ignored():
    entries, bad = S.parse_text("# hiç almadım\nMAT 103E AA\n\n   \nBLG 102E BB  # notum")
    assert [e.course_code for e in entries] == ["MAT 103E", "BLG 102E"]
    assert bad == []


@pytest.mark.parametrize("line", [
    "(seçmeli havuz: Elective Courses II(TB)) -> GEO 413E AA",
    "  -> GEO 413E AA",
    "7.yy seçmeli: GEO 413E AA",
])
def test_pool_line_written_by_hand(line):
    """Kullanıcı havuz satırını serbest biçimde doldurabiliyor (18.08.2026)."""
    entry = S.parse_line(line)
    assert entry is not None
    assert (entry.course_code, entry.grade) == ("GEO 413E", "AA")


@pytest.mark.parametrize("line", [
    "Elective Courses II(TB)",
    "2024-2025 Güz dönemi",
    "bu satır ders değil",
])
def test_prose_lines_are_not_mistaken_for_courses(line):
    """Serbest metin ders sanılmamalı — yanlış ders eklemek sessiz hatadır."""
    assert S.parse_line(line) is None


def test_unparsable_line_reported_not_swallowed():
    entries, bad = S.parse_text("MAT 103E AA\nbu satır ders değil")
    assert len(entries) == 1
    assert bad == ["bu satır ders değil"]


# ------------------------------------------------------------------ kayıtlar
def test_grades_excludes_in_progress_by_default(dbs):
    _con, ucon = dbs
    sid = S.ensure_student(ucon)
    entries, _ = S.parse_text("MAT 103E AA\nBLG 102E --")
    S.add_entries(ucon, sid, entries)
    assert S.grades(ucon, sid) == {"MAT 103E": "AA"}
    # 'MIN FF' (dersi almış olmak) için devam edenler de sayılır
    assert S.grades(ucon, sid, include_in_progress=True)["BLG 102E"] == "FF"


def test_failed_course_not_counted_as_passed(dbs):
    _con, ucon = dbs
    sid = S.ensure_student(ucon)
    S.add_entries(ucon, sid, S.parse_text("BLG 102E FF")[0])
    assert S.grades(ucon, sid) == {}


def test_in_progress_is_not_uncertain_grade(dbs):
    """'Devam ediyorum' ile 'notumu bilmiyorum' AYRI şeyler."""
    _con, ucon = dbs
    sid = S.ensure_student(ucon)
    S.add_entries(ucon, sid, S.parse_text("MAT 103E\nBLG 102E --")[0])
    assert S.uncertain_grades(ucon, sid) == ["MAT 103E"]


def test_reimport_replaces(dbs):
    _con, ucon = dbs
    sid = S.ensure_student(ucon)
    S.add_entries(ucon, sid, S.parse_text("MAT 103E AA")[0])
    S.add_entries(ucon, sid, S.parse_text("BLG 102E BB")[0], replace=True)
    assert set(S.grades(ucon, sid)) == {"BLG 102E"}


def test_same_course_updated_not_duplicated(dbs):
    _con, ucon = dbs
    sid = S.ensure_student(ucon)
    S.add_entries(ucon, sid, S.parse_text("MAT 103E DD")[0])
    S.add_entries(ucon, sid, S.parse_text("MAT 103E AA")[0])
    assert S.grades(ucon, sid) == {"MAT 103E": "AA"}


# -------------------------------------------------------------------- şablon
def test_template_lists_plan_courses_commented(dbs):
    con, _ucon = dbs
    text = S.template(con, [10, 20])
    assert "# MAT 103E" in text and "# BLG 223E" in text
    # şablon satırları KAPALI gelmeli, yanlışlıkla hepsi alınmış sayılmasın
    entries, _ = S.parse_text(text)
    assert entries == []


def test_template_never_clobbers_filled_file(dbs, tmp_path):
    """Doldurulmuş transkriptin üzerine yazmak saatlerce emeği siler."""
    con, _ucon = dbs
    dest = tmp_path / "transkript.txt"
    dest.write_text("MAT 103E AA\n", encoding="utf-8")
    written = S.write_template(con, [10, 20], dest)
    assert written != dest
    assert written.name == "transkript-yeni.txt"
    assert dest.read_text(encoding="utf-8") == "MAT 103E AA\n"     # dokunulmadı
    # açıkça istenirse üzerine yazar
    forced = S.write_template(con, [10, 20], dest, overwrite=True)
    assert forced == dest and "MAT 103E AA\n" not in dest.read_text(encoding="utf-8")


# ------------------------------------------------------------ slot eşlemesi
def test_rebuild_fulfillment(dbs):
    con, ucon = dbs
    sid = S.ensure_student(ucon)
    S.enroll(ucon, sid, 10, "ANADAL", "HTAE")
    S.enroll(ucon, sid, 20, "CAP", "BLG")
    S.add_entries(ucon, sid, S.parse_text("MAT 103E AA\nBLG 102E BB\nSEC 301 CC")[0])
    n = PR.rebuild_fulfillment(con, ucon, sid, [10, 20], S.grades(ucon, sid))
    assert n == 3          # MAT 103E, BLG 102E, havuz(SEC 301)
    assert ucon.execute(
        "SELECT COUNT(*) FROM slot_fulfillment WHERE student_id=?", (sid,)).fetchone()[0] == 3


def test_fulfillment_is_idempotent(dbs):
    con, ucon = dbs
    sid = S.ensure_student(ucon)
    S.add_entries(ucon, sid, S.parse_text("MAT 103E AA")[0])
    first = PR.rebuild_fulfillment(con, ucon, sid, [10, 20], S.grades(ucon, sid))
    second = PR.rebuild_fulfillment(con, ucon, sid, [10, 20], S.grades(ucon, sid))
    assert first == second == 1


def test_double_counting_detected_when_it_happens(dbs):
    """D5: bu çiftte olmuyor ama mekanizma çalışmalı."""
    con, ucon = dbs
    con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,ects,position)
                   VALUES (10,'REQUIRED','BLG 102E',8.0,1)""")   # anadalda da zorunlu
    con.commit()
    sid = S.ensure_student(ucon)
    S.add_entries(ucon, sid, S.parse_text("BLG 102E AA")[0])
    PR.rebuild_fulfillment(con, ucon, sid, [10, 20], S.grades(ucon, sid))
    assert PR.double_counted(con, ucon, sid) == [("BLG 102E", 2)]


# ------------------------------------------------------------------- rapor
def test_progress_separates_plans(dbs):
    con, ucon = dbs
    sid = S.ensure_student(ucon)
    S.enroll(ucon, sid, 10, "ANADAL", "HTAE")
    S.enroll(ucon, sid, 20, "CAP", "BLG")
    S.add_entries(ucon, sid, S.parse_text("MAT 103E AA\nBLG 102E BB")[0])
    text = PR.report(con, ucon, sid, 20)
    assert "ANADAL — HTAE" in text and "CAP — BLG" in text
    assert text.index("ANADAL") < text.index("CAP — BLG")      # anadal önce
    assert "6/6" in text          # anadal AKTS tamam
    assert "8/24.5" in text       # ÇAP AKTS ayrı sayılıyor


def test_ready_list_respects_grade_threshold(dbs):
    """BLG 223E, BLG 102E'den MIN CC istiyor."""
    con, ucon = dbs
    sid = S.ensure_student(ucon)
    S.enroll(ucon, sid, 20, "CAP", "BLG")

    S.add_entries(ucon, sid, S.parse_text("BLG 102E DD")[0], replace=True)
    assert "BLG 223E" not in PR.report(con, ucon, sid, 20).split("ALABİLECEKLERİN")[1]

    S.add_entries(ucon, sid, S.parse_text("BLG 102E BB")[0], replace=True)
    assert "BLG 223E" in PR.report(con, ucon, sid, 20).split("ALABİLECEKLERİN")[1]


def test_report_without_enrollment_is_graceful(dbs):
    con, ucon = dbs
    sid = S.ensure_student(ucon)
    assert "make student" in PR.report(con, ucon, sid)
