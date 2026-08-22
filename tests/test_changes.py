"""Faz 9 — değişim raporu, GNO ve devam eden ders kuralı."""
import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import changes as CH, config, db, policy as POL, prereq as P, student as S


@pytest.fixture()
def con(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "REF_DB", tmp_path / "ref.sqlite3")
    monkeypatch.setattr(config, "USER_DB", tmp_path / "user.sqlite3")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(POL, "DEFAULT_PATH", tmp_path / "kurallar.toml")
    con = db.connect(tmp_path / "ref.sqlite3", "schema.sql")
    con.executemany(
        "INSERT INTO course(code,name,credits,ects,prereq_raw) VALUES (?,?,?,?,?)",
        [("BLG 102E", "Intro", 3.0, 8.0, None),
         ("GEO 401E", "Proje", 3.0, 5.0, None),
         ("GEO 313E", "Ölçme", 3.0, 4.0, None),
         ("MAT 103E", "Matematik I", 4.0, 6.0, None),
         ("DAN 102", "Danışmanlık", 0.0, 1.0, None),
         ("STJ 100", "Staj", None, None, None)])
    con.commit()
    return con


def _lesson(con, crn, code, capacity=40, enrolled=0):
    con.execute("""INSERT INTO lesson(crn,course_code,capacity,enrolled)
                   VALUES (?,?,?,?)""", (crn, code, capacity, enrolled))
    con.commit()


# =============================================================== anlık görüntü
def test_first_snapshot_cannot_diff(con):
    _lesson(con, "1", "GEO 401E")
    CH.take(con, "2026-01-01T00:00:00")
    diff = CH.compare(con)
    assert diff.empty and "iki anlık görüntü" in CH.format_diff(diff)


def test_detects_newly_opened_course(con):
    """★ Asıl işe yarayan bulgu: beklediğin ders AÇILDI mı?"""
    _lesson(con, "1", "GEO 401E")
    CH.take(con, "2026-01-01T00:00:00")
    _lesson(con, "2", "BLG 102E")
    _lesson(con, "3", "BLG 102E")
    CH.take(con, "2026-01-02T00:00:00")
    diff = CH.compare(con)
    assert [o["course"] for o in diff.opened] == ["BLG 102E"]
    assert diff.opened[0]["sections"] == 2
    assert diff.opened[0]["name"] == "Intro"


def test_new_section_on_existing_course_is_not_opened(con):
    """Ders zaten açıktı, şube eklendi — ayrı bir olay."""
    _lesson(con, "1", "GEO 401E")
    CH.take(con, "2026-01-01T00:00:00")
    _lesson(con, "2", "GEO 401E")
    CH.take(con, "2026-01-02T00:00:00")
    diff = CH.compare(con)
    assert not diff.opened
    assert [s["crn"] for s in diff.new_sections] == ["2"]


def test_detects_filled_and_freed_capacity(con):
    _lesson(con, "1", "GEO 401E", capacity=40, enrolled=39)
    _lesson(con, "2", "GEO 313E", capacity=40, enrolled=40)
    CH.take(con, "2026-01-01T00:00:00")
    con.execute("UPDATE lesson SET enrolled=40 WHERE crn='1'")
    con.execute("UPDATE lesson SET enrolled=38 WHERE crn='2'")
    con.commit()
    CH.take(con, "2026-01-02T00:00:00")
    diff = CH.compare(con)
    assert [f["crn"] for f in diff.filled] == ["1"]
    assert [f["crn"] for f in diff.freed] == ["2"]


def test_detects_closed_section(con):
    _lesson(con, "1", "GEO 401E")
    CH.take(con, "2026-01-01T00:00:00")
    con.execute("DELETE FROM lesson WHERE crn='1'")
    con.commit()
    CH.take(con, "2026-01-02T00:00:00")
    assert [c["crn"] for c in CH.compare(con).closed] == ["1"]


def test_watch_filters_to_your_courses(con):
    """★ 3400 şubelik dökümde kendi dersini bulamazsın — süzgeç şart."""
    CH.take(con, "2026-01-01T00:00:00")
    _lesson(con, "1", "BLG 102E")
    _lesson(con, "2", "MAT 103E")
    CH.take(con, "2026-01-02T00:00:00")
    everything = CH.compare(con)
    mine = CH.compare(con, watch={"BLG 102E"})
    assert {o["course"] for o in everything.opened} == {"BLG 102E", "MAT 103E"}
    assert {o["course"] for o in mine.opened} == {"BLG 102E"}


def test_snapshots_are_pruned(con):
    _lesson(con, "1", "GEO 401E")
    for i in range(CH.KEEP + 5):
        CH.take(con, f"2026-01-{i + 1:02d}T00:00:00")
    assert len(CH.stamps(con)) == CH.KEEP


def test_format_lists_every_category(con):
    _lesson(con, "1", "GEO 401E", enrolled=39)
    _lesson(con, "2", "GEO 313E")
    CH.take(con, "2026-01-01T00:00:00")
    con.execute("UPDATE lesson SET enrolled=40 WHERE crn='1'")
    con.execute("DELETE FROM lesson WHERE crn='2'")
    con.commit()
    _lesson(con, "3", "BLG 102E")
    CH.take(con, "2026-01-02T00:00:00")
    text = CH.format_diff(CH.compare(con))
    for heading in ("AÇILDI", "KONTENJAN DOLDU", "ŞUBE KAPANDI"):
        assert heading in text


# ======================================================================== GNO
def _ucon(tmp_path):
    ucon = db.connect(tmp_path / "user.sqlite3", "schema_user.sql")
    return ucon, S.ensure_student(ucon)


def test_gpa_is_credit_weighted(con, tmp_path):
    ucon, sid = _ucon(tmp_path)
    S.add_entries(ucon, sid, [S.make_entry("MAT 103E", "AA"),    # 4 kredi × 4.0
                              S.make_entry("GEO 401E", "CC")])   # 3 kredi × 2.0
    res = POL.gpa(con, S.graded(ucon, sid))
    assert res.value == round((16 + 6) / 7, 2) == 3.14
    assert (res.counted, res.credits) == (2, 7.0)


def test_failed_course_counts_as_zero(con, tmp_path):
    """★ Kalınan ders GNO'yu düşürür — yalnız geçilenlere bakmak yanlış olur."""
    ucon, sid = _ucon(tmp_path)
    S.add_entries(ucon, sid, [S.make_entry("MAT 103E", "AA"),
                              S.make_entry("GEO 401E", "FF")])
    assert POL.gpa(con, S.graded(ucon, sid)).value == round(16 / 7, 2)


def test_bl_and_mu_are_excluded(con, tmp_path):
    """★ BL/MU 4.00 sayılırsa GNO şişer ve 'eşiği geçiyorsun' der."""
    ucon, sid = _ucon(tmp_path)
    S.add_entries(ucon, sid, [S.make_entry("MAT 103E", "CC"),
                              S.make_entry("GEO 401E", "BL"),
                              S.make_entry("GEO 313E", "MU")])
    res = POL.gpa(con, S.graded(ucon, sid))
    assert res.value == 2.0 and res.counted == 1
    assert set(res.skipped_not_graded) == {"GEO 401E", "GEO 313E"}


def test_zero_credit_course_is_excluded_and_reported(con, tmp_path):
    ucon, sid = _ucon(tmp_path)
    S.add_entries(ucon, sid, [S.make_entry("MAT 103E", "AA"),
                              S.make_entry("DAN 102", "BB"),
                              S.make_entry("STJ 100", "AA")])
    res = POL.gpa(con, S.graded(ucon, sid))
    assert res.value == 4.0
    assert res.skipped_no_credit == ["DAN 102", "STJ 100"]
    assert res.partial is True


def test_retake_uses_the_better_grade(con, tmp_path):
    """Ders tekrar alındıysa yükseltilmiş not sayılır."""
    ucon, sid = _ucon(tmp_path)
    S.add_entries(ucon, sid, [S.make_entry("MAT 103E", "FF")], term="2024G")
    S.add_entries(ucon, sid, [S.make_entry("MAT 103E", "BB")], term="2025G")
    assert S.graded(ucon, sid)["MAT 103E"] == "BB"
    assert POL.gpa(con, S.graded(ucon, sid)).value == 3.0


def test_in_progress_course_has_no_grade_yet(con, tmp_path):
    ucon, sid = _ucon(tmp_path)
    S.add_entries(ucon, sid, [S.make_entry("MAT 103E", "AA"),
                              S.make_entry("GEO 401E", None, "--")])
    assert "GEO 401E" not in S.graded(ucon, sid)
    assert POL.gpa(con, S.graded(ucon, sid)).counted == 1


def test_empty_transcript_does_not_divide_by_zero(con, tmp_path):
    ucon, _sid = _ucon(tmp_path)
    assert POL.gpa(con, {}).value == 0.0


# ---------------------------------------------------------------- eşikler
def test_thresholds_carry_verified_flag(tmp_path):
    """★ Doğrulanmamış eşik kesinmiş gibi gösterilmemeli."""
    f = tmp_path / "kurallar.toml"
    f.write_text('[[gno_esigi]]\nanahtar="devam"\nad="Devam"\nmin_gno=2.5\n'
                 'dogrulandi=false\n'
                 '[[gno_esigi]]\nanahtar="x"\nad="Kesin"\nmin_gno=2.0\n'
                 'dogrulandi=true\n', encoding="utf-8")
    ts = {t.key: t for t in POL.load_thresholds(f)}
    assert ts["devam"].verified is False and ts["x"].verified is True


def test_shipped_config_declares_gno_thresholds():
    keys = {t.key for t in POL.load_thresholds(config.ROOT / "config" / "kurallar.toml")}
    assert {"basvuru", "devam"} <= keys


def test_missing_threshold_file_is_not_an_error(tmp_path):
    assert POL.load_thresholds(tmp_path / "yok.toml") == []


# ======================================================= devam eden dersler
def test_in_progress_courses_are_not_recommended(tmp_path, monkeypatch):
    """★ 21.08.2026'da bulunan hata: zaten aldığın ders yeniden öneriliyordu."""
    from itucap import recommend as REC

    monkeypatch.setattr(config, "REF_DB", tmp_path / "r2.sqlite3")
    monkeypatch.setattr(config, "USER_DB", tmp_path / "u2.sqlite3")
    con = db.connect(tmp_path / "r2.sqlite3", "schema.sql")
    con.executemany("INSERT INTO course(code,name,credits,ects) VALUES (?,?,?,?)",
                    [("GEO 401E", "Proje", 3.0, 5.0), ("GEO 313E", "Ölçme", 3.0, 4.0)])
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title,source)
                   VALUES (10,'HTAE','lisans','anadal','obs')""")
    for i, code in enumerate(["GEO 401E", "GEO 313E"]):
        con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,ects,position,term_no)
                       VALUES (10,'REQUIRED',?,4.0,?,5)""", (code, i))
        con.execute("""INSERT INTO lesson(crn,course_code,capacity,enrolled)
                       VALUES (?,?,40,0)""", (f"90{i}", code))
        con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES (?,'HTAE')",
                    (f"90{i}",))
    con.commit()
    P.parse_all(con)
    ucon = db.connect(tmp_path / "u2.sqlite3", "schema_user.sql")
    sid = S.ensure_student(ucon)
    S.add_entries(ucon, sid, [S.make_entry("GEO 401E", None, "--")])

    codes = {c.course for c in REC.candidates(
        con, ucon, sid, 10, None, "HTAE", "", {"HTAE"}, "kredi")}
    assert "GEO 401E" not in codes, "bu dönem aldığın ders yeniden önerilmemeli"
    assert "GEO 313E" in codes


# ============================================================ yedekleme
def test_backup_written_before_destructive_write(con, tmp_path):
    """★ Elle girilmiş transkript geri gelmez — silmeden önce yedek."""
    ucon, sid = _ucon(tmp_path)
    S.add_entries(ucon, sid, [S.make_entry("MAT 103E", "AA"),
                              S.make_entry("GEO 401E", None, "--")])
    dest = S.backup(ucon, sid, stamp="20260821-120000")
    assert dest and dest.exists()
    text = dest.read_text(encoding="utf-8")
    assert "MAT 103E AA" in text and "GEO 401E --" in text

    # yedek geri yüklenebilir olmalı — aynı ayrıştırıcıdan geçiyor
    entries, bad = S.parse_text(text)
    assert not bad
    assert {e.course_code: e.status for e in entries} == {
        "MAT 103E": "PASSED", "GEO 401E": "IN_PROGRESS"}


def test_empty_transcript_makes_no_backup(con, tmp_path):
    ucon, sid = _ucon(tmp_path)
    assert S.backup(ucon, sid) is None


def test_backups_are_pruned(con, tmp_path):
    ucon, sid = _ucon(tmp_path)
    S.add_entries(ucon, sid, [S.make_entry("MAT 103E", "AA")])
    for i in range(25):
        S.backup(ucon, sid, stamp=f"20260821-1200{i:02d}")
    S.prune_backups(keep=20)
    assert len(list((tmp_path / "yedek").glob("transkript-*.txt"))) == 20
