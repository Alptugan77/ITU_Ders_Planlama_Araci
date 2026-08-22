"""Faz 2 — kural motoru: alınabilirlik, denklik grafı, slot karşılanması."""
import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    """Testler projenin gerçek config/denklikler.toml dosyasından etkilenmesin."""
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")

from itucap import db, prereq as P, rules as R
from itucap.rules import Status


@pytest.fixture()
def con(tmp_path):
    con = db.connect(tmp_path / "ref.sqlite3", "schema.sql")
    con.executemany(
        "INSERT INTO course(code,name,ects,prereq_raw) VALUES (?,?,?,?)",
        [
            ("MAT 103E", "Mathematics I", 6.0, None),
            ("MAT 104E", "Mathematics II", 6.0, "MAT 103E MIN DD"),
            ("BLG 102E", "Intro to Comp", 8.0, None),
            ("BLG 223E", "Data Structures", 8.0, "BLG 102E MIN DD"),
            ("BLG 335E", "Algorithms I", 4.5, "(BLG 223E MIN DDveya BLG 233E MIN DD)"),
            ("BLG 233E", "Data Str. alt", 8.0, None),
            ("BOZ 101", "Bozuk önşart", 3.0, "Deniz Kazalarıve Emniyet"),
            ("SEC 201", "Seçmeli A", 4.0, None),
            ("SEC 202", "Seçmeli B", 4.0, None),
        ],
    )
    con.commit()
    P.parse_all(con)
    return con


# ------------------------------------------------------------ alınabilirlik
def test_no_prereq_is_ok(con):
    assert R.can_take(con, "BLG 102E", {}).status is Status.OK


def test_blocked_lists_missing(con):
    verdict = R.can_take(con, "BLG 223E", {})
    assert verdict.status is Status.BLOCKED
    assert verdict.missing == [("BLG 102E", "DD")]
    assert not verdict          # __bool__


def test_satisfied_after_passing(con):
    assert R.can_take(con, "BLG 223E", {"BLG 102E": "CC"}).status is Status.OK


def test_failing_grade_does_not_satisfy(con):
    assert R.can_take(con, "BLG 223E", {"BLG 102E": "FF"}).status is Status.BLOCKED


def test_or_alternative_counts(con):
    assert R.can_take(con, "BLG 335E", {"BLG 233E": "DD"}).status is Status.OK


def test_unparsable_prereq_is_unknown_not_ok(con):
    """★ GÜVENLİK: çözülemeyen önşart 'önşartı yok' sayılmamalı."""
    verdict = R.can_take(con, "BOZ 101", {})
    assert verdict.status is Status.UNKNOWN
    assert not verdict
    assert "çözülemedi" in verdict.note


def test_unknown_course_is_unknown(con):
    assert R.can_take(con, "YOK 999", {}).status is Status.UNKNOWN


# ----------------------------------------------------------------- denklik
def _add_equivalence(con, target, sources, confidence="official"):
    cur = con.execute(
        """INSERT INTO equivalence(target_course,confidence,applies_to_cap,note_raw)
           VALUES (?,?,1,'test')""", (target, confidence))
    for code in sources:
        con.execute(
            "INSERT INTO equivalence_source(equivalence_id,course_code,min_grade) VALUES (?,?,'DD')",
            (cur.lastrowid, code))
    con.commit()
    return cur.lastrowid


def test_multi_source_equivalence(con):
    """Yol haritasındaki gerçek örnek: {KIM 211E, KIM 212} -> KIM 206."""
    eq_id = _add_equivalence(con, "KIM 206", ["KIM 211E", "KIM 212"])
    eqs = R.load_equivalences(con)

    # tek kaynak yetmez
    expanded, _ = R.expand_with_equivalences({"KIM 211E": "AA"}, eqs)
    assert "KIM 206" not in expanded

    # ikisi birden -> hedef kazanılır
    expanded, via = R.expand_with_equivalences({"KIM 211E": "AA", "KIM 212": "CC"}, eqs)
    assert "KIM 206" in expanded
    assert via["KIM 206"] == eq_id
    assert expanded["KIM 206"] == "CC"        # en düşük not devredilir


def test_equivalence_respects_min_grade(con):
    _add_equivalence(con, "KIM 206", ["KIM 211E"])
    eqs = R.load_equivalences(con)
    expanded, _ = R.expand_with_equivalences({"KIM 211E": "FF"}, eqs)
    assert "KIM 206" not in expanded


def test_equivalence_transitive_closure(con):
    """{A,B} -> C ve {C} -> D  =>  A+B alan D'yi de almış sayılır."""
    _add_equivalence(con, "KIM 206", ["KIM 211E", "KIM 212"])
    _add_equivalence(con, "KIM 301", ["KIM 206"])
    eqs = R.load_equivalences(con)
    expanded, _ = R.expand_with_equivalences({"KIM 211E": "BB", "KIM 212": "BB"}, eqs)
    assert "KIM 301" in expanded


def test_equivalence_cycle_terminates(con):
    _add_equivalence(con, "X 101", ["Y 101"])
    _add_equivalence(con, "Y 101", ["X 101"])
    eqs = R.load_equivalences(con)
    expanded, _ = R.expand_with_equivalences({"Z 101": "AA"}, eqs)   # tetiklenmez
    assert expanded == {"Z 101": "AA"}


# ------------------------------------------------------- slot ve ilerleme
def _make_plan(con):
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title,source)
                   VALUES (1,'BLG','cap','test planı','obs')""")
    con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,ects,position)
                   VALUES (1,'REQUIRED','BLG 102E',8.0,0)""")
    con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,ects,position)
                   VALUES (1,'REQUIRED','BLG 223E',8.0,1)""")
    cur = con.execute(
        """INSERT INTO plan_slot(plan_id,slot_kind,pool_label_raw,pool_category,ects,position)
           VALUES (1,'ELECTIVE_POOL','Seçmeli (MT)','MT',4.0,2)""")
    for code in ("SEC 201", "SEC 202"):
        con.execute("INSERT INTO pool_option(slot_id,course_code) VALUES (?,?)",
                    (cur.lastrowid, code))
    con.commit()
    return cur.lastrowid


def test_required_slot(con):
    _make_plan(con)
    slot = con.execute(
        "SELECT id FROM plan_slot WHERE course_code='BLG 102E'").fetchone()[0]
    assert R.slot_satisfied(con, slot, {"BLG 102E": "DD"}).satisfied is True
    assert R.slot_satisfied(con, slot, {"BLG 102E": "FF"}).satisfied is False
    assert R.slot_satisfied(con, slot, {}).satisfied is False


def test_pool_slot_any_option(con):
    pool_id = _make_plan(con)
    result = R.slot_satisfied(con, pool_id, {"SEC 202": "BB"})
    assert result.satisfied is True and result.course == "SEC 202"
    empty = R.slot_satisfied(con, pool_id, {})
    assert empty.satisfied is False and set(empty.candidates) == {"SEC 201", "SEC 202"}


def test_slot_filled_via_equivalence(con):
    _make_plan(con)
    eq_id = _add_equivalence(con, "BLG 223E", ["BLG 233E"])
    slot = con.execute(
        "SELECT id FROM plan_slot WHERE course_code='BLG 223E'").fetchone()[0]
    result = R.slot_satisfied(con, slot, {"BLG 233E": "BB"}, R.load_equivalences(con))
    assert result.satisfied is True
    assert result.via_equivalence == eq_id


def test_plan_progress(con):
    _make_plan(con)
    progress = R.plan_progress(con, 1, {"BLG 102E": "AA"})
    assert progress["slots_done"] == 1
    assert progress["slots_total"] == 3
    assert progress["ects_done"] == 8.0
    assert progress["ects_total"] == 20.0
    assert progress["by_category"]["ZORUNLU"] == (1, 2)
    assert progress["by_category"]["MT"] == (0, 1)
    assert len(progress["open_slots"]) == 2


def test_progress_is_per_plan(con):
    """ÇAP ve anadal AKTS'si KARIŞMAMALI (yol haritası §1.7)."""
    _make_plan(con)
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title,source)
                   VALUES (2,'HTAE','lisans','anadal','obs')""")
    con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,ects,position)
                   VALUES (2,'REQUIRED','MAT 103E',6.0,0)""")
    con.commit()
    grades = {"BLG 102E": "AA", "MAT 103E": "AA"}
    assert R.plan_progress(con, 1, grades)["ects_done"] == 8.0
    assert R.plan_progress(con, 2, grades)["ects_done"] == 6.0


# ---------------------------------------------------------------- muafiyet
def test_waiver_satisfies_prereq_but_not_progress(con, tmp_path, monkeypatch):
    """★ Muafiyet önşartı açar ama dersi GEÇİLMİŞ yapmaz.

    İkisini karıştırmak ilerlemeyi olduğundan iyi gösterirdi (18.08.2026).
    """
    from itucap import declared

    waiver = tmp_path / "denklikler.toml"
    waiver.write_text(
        '[[muafiyet]]\ndersler = ["BLG 102E"]\nnot_ = "test"\n', encoding="utf-8")
    monkeypatch.setattr(declared, "DEFAULT_PATH", waiver)

    # önşart açılır
    assert R.can_take(con, "BLG 223E", {}).status is Status.OK

    # ama slot dolmaz, AKTS sayılmaz
    _make_plan(con)
    slot = con.execute(
        "SELECT id FROM plan_slot WHERE course_code='BLG 102E'").fetchone()[0]
    assert R.slot_satisfied(con, slot, {}).satisfied is False
    assert R.plan_progress(con, 1, {})["ects_done"] == 0.0


def test_real_grade_overrides_waiver(con, tmp_path, monkeypatch):
    """Gerçek not muafiyeti ezer — FF alınmış ders muaf sayılmamalı."""
    from itucap import declared

    waiver = tmp_path / "denklikler.toml"
    waiver.write_text(
        '[[muafiyet]]\ndersler = ["BLG 102E"]\nnot_ = "test"\n', encoding="utf-8")
    monkeypatch.setattr(declared, "DEFAULT_PATH", waiver)
    assert R.can_take(con, "BLG 223E", {"BLG 102E": "FF"}).status is Status.BLOCKED


# ------------------------------------------------------- bulunduğun dönem
def test_infer_term_is_deepest_passed_term(con):
    """5. dönem dersini geçen öğrenci en az 5. dönemdedir."""
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title,source)
                   VALUES (3,'HTAE','lisans','anadal','obs')""")
    for term, code in ((1, "MAT 103E"), (3, "BLG 102E"), (5, "BLG 223E")):
        con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,ects,position,term_no)
                       VALUES (3,'REQUIRED',?,6.0,?,?)""", (code, term, term))
    con.commit()
    assert R.infer_term(con, 3, {}) == 0
    assert R.infer_term(con, 3, {"MAT 103E": "AA"}) == 1
    assert R.infer_term(con, 3, {"MAT 103E": "AA", "BLG 223E": "CC"}) == 5
    assert R.infer_term(con, None, {}) == 0


def test_open_required_counts_only_required_slots(con):
    """'Kalan N zorunlu' seçmeli havuzları saymamalı."""
    _make_plan(con)                    # 2 zorunlu + 1 havuz
    stats = R.plan_progress(con, 1, {})
    assert stats["open_required"] == 2
    assert len(stats["open_slots"]) == 3
    done = R.plan_progress(con, 1, {"BLG 102E": "AA"})
    assert done["open_required"] == 1
