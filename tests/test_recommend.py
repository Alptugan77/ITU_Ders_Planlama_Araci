"""Faz 5 — öneri motoru, program kısıtı, çakışma çözücü."""
import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    """Testler projenin gerçek config/denklikler.toml dosyasından etkilenmesin."""
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")

from itucap import db, prereq as P, recommend as REC, student as S


def _meeting(day, start, end, building=None, campus=None):
    return REC.Meeting(day, start, end, None, building, campus)


def _section(crn, course, meetings, capacity=50, enrolled=0):
    return REC.Section(crn, course, None, capacity, enrolled, tuple(meetings))


# ------------------------------------------------------------------ çakışma
def test_overlap_detection():
    a = _meeting(1, 480, 600)          # Pzt 08:00-10:00
    assert REC.overlaps(a, _meeting(1, 540, 660)) is True     # 09:00-11:00
    assert REC.overlaps(a, _meeting(1, 600, 720)) is False    # bitişik, çakışmaz
    assert REC.overlaps(a, _meeting(2, 540, 660)) is False    # başka gün


def test_section_conflict_any_meeting():
    x = _section("1", "A 101", [_meeting(1, 480, 600), _meeting(3, 480, 600)])
    y = _section("2", "B 102", [_meeting(3, 540, 660)])
    z = _section("3", "C 103", [_meeting(2, 480, 600)])
    assert REC.section_conflict(x, y) is True
    assert REC.section_conflict(x, z) is False


# ------------------------------------------------------------ veri fixture
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
            ("BLG 212E", "Mikroişlemci", 7.0, None),
            ("BLG 351E", "Mikrobilgisayar Lab", 2.0, "BLG 212E MIN DD"),
            ("BLG 223E", "Veri Yapıları", 8.0, None),
            ("GEO 303E", "Kadastro", 3.0, None),
        ],
    )
    con.executemany("INSERT INTO building(code,name,campus) VALUES (?,?,?)",
                    [("INB", "İnşaat", "Ayazağa"), ("MAC", "Maçka", "Maçka")])
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title,source,is_term_based)
                   VALUES (20,'BLG','cap','ÇAP','obs',0)""")
    for i, code in enumerate(["BLG 212E", "BLG 351E", "BLG 223E"]):
        ects = con.execute("SELECT ects FROM course WHERE code=?", (code,)).fetchone()[0]
        con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,ects,position)
                       VALUES (20,'REQUIRED',?,?,?)""", (code, ects, i))
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title,source)
                   VALUES (10,'HTAE','lisans','anadal','obs')""")
    con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,ects,position,term_no)
                   VALUES (10,'REQUIRED','GEO 303E',3.0,0,5)""")

    def add_lesson(crn, code, day, start, end, progs, building="INB", cap=50, enr=0):
        con.execute("""INSERT INTO lesson(crn,course_code,capacity,enrolled,building)
                       VALUES (?,?,?,?,?)""", (crn, code, cap, enr, building))
        con.execute("""INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min,building)
                       VALUES (?,?,?,?,?)""", (crn, day, start, end, building))
        for prog in progs:
            con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES (?,?)",
                        (crn, prog))

    add_lesson("100", "BLG 212E", 1, 480, 660, ["BLG", "BLGE"])
    add_lesson("101", "BLG 212E", 2, 480, 660, ["BLG", "BLGE"])
    add_lesson("200", "BLG 223E", 1, 480, 660, ["SECE"])          # programa KAPALI
    add_lesson("300", "GEO 303E", 1, 480, 660, ["HTAE", "GEO"], building="MAC")
    add_lesson("400", "BLG 351E", 3, 480, 600, ["BLG", "BLGE"])
    con.commit()
    P.parse_all(con)

    sid = S.ensure_student(ucon)
    S.enroll(ucon, sid, 10, "ANADAL", "HTAE")
    S.enroll(ucon, sid, 20, "CAP", "BLG")
    return con, ucon, sid


# ------------------------------------------------------------ program kısıtı
def test_sections_filtered_by_program(dbs):
    """★ BLG dersleri yalnız BLG/BLGE'ye açık; HTAE koduyla alınamıyor."""
    con, _ucon, _sid = dbs
    assert len(REC.load_sections(con, "BLG 212E", {"BLG"})) == 2
    assert REC.load_sections(con, "BLG 212E", {"HTAE"}) == []
    assert REC.load_sections(con, "BLG 223E", {"BLG"}) == []      # sadece SECE
    assert len(REC.load_sections(con, "GEO 303E", {"HTAE"})) == 1


def test_candidates_respect_program_codes(dbs):
    con, ucon, sid = dbs
    cands = {c.course: c for c in REC.candidates(con, ucon, sid, 10, 20, "HTAE", "BLG", {"HTAE","BLG","BLGE"}, "akts")}
    assert "BLG 212E" in cands and cands["BLG 212E"].role == "CAP"
    assert "GEO 303E" in cands and cands["GEO 303E"].role == "ANADAL"
    assert "BLG 223E" not in cands          # şubeleri programa kapalı
    assert "BLG 351E" not in cands          # önşartı yok


def test_passed_course_not_recommended(dbs):
    con, ucon, sid = dbs
    S.add_entries(ucon, sid, S.parse_text("BLG 212E AA")[0])
    codes = {c.course for c in REC.candidates(con, ucon, sid, 10, 20, "HTAE", "BLG", {"HTAE","BLG","BLGE"}, "akts")}
    assert "BLG 212E" not in codes
    assert "BLG 351E" in codes              # önşartı artık sağlandı


def test_equivalence_unlocks_candidate(dbs):
    """Beyan edilen denklik önşartı açmalı."""
    con, ucon, sid = dbs
    cur = con.execute(
        """INSERT INTO equivalence(target_course,applies_to_cap,confidence,note_raw)
           VALUES ('BLG 212E',1,'user_declared','beyan')""")
    con.execute("""INSERT INTO equivalence_source(equivalence_id,course_code,min_grade)
                   VALUES (?,'GEO 303E','DD')""", (cur.lastrowid,))
    con.commit()
    S.add_entries(ucon, sid, S.parse_text("GEO 303E BB")[0])
    codes = {c.course for c in REC.candidates(con, ucon, sid, 10, 20, "HTAE", "BLG", {"HTAE","BLG","BLGE"}, "akts")}
    assert "BLG 351E" in codes              # BLG 212E denklikle sağlandı


# ------------------------------------------------------------------ puanlama
def test_cap_courses_ranked_above_equal_anadal(dbs):
    con, ucon, sid = dbs
    cands = REC.candidates(con, ucon, sid, 10, 20, "HTAE", "BLG", {"HTAE","BLG","BLGE"}, "akts")
    assert cands[0].role == "CAP"


def test_scarcity_bonus_for_full_sections():
    a = REC.Candidate("A 101", "", "CAP", 5, 3, 0, 0, False, True,
                      [_section("1", "A 101", [_meeting(1, 480, 600)], 50, 49)])
    b = REC.Candidate("B 102", "", "CAP", 5, 3, 0, 0, False, True,
                      [_section("2", "B 102", [_meeting(2, 480, 600)], 50, 0),
                       _section("3", "B 102", [_meeting(3, 480, 600)], 50, 0)])
    REC.score_all([a, b])
    assert a.score > b.score
    assert "kontenjan kritik" in a.reasons


def test_critical_path_from_deepest_course():
    from itucap.sequence import Step
    steps = [
        Step("A 100", 0, 5, 3, 3, blockers=[]),
        Step("B 200", 1, 5, 3, 2, blockers=["A 100"]),
        Step("C 300", 2, 5, 3, 0, blockers=["B 200"]),
        Step("D 100", 0, 5, 3, 0, blockers=[]),          # zincir dışı
    ]
    assert REC.critical_courses(steps) == {"A 100", "B 200", "C 300"}


# --------------------------------------------------------- program üretimi
def test_schedule_has_no_conflicts(dbs):
    con, ucon, sid = dbs
    cands = REC.candidates(con, ucon, sid, 10, 20, "HTAE", "BLG", {"HTAE","BLG","BLGE"}, "akts")
    schedules = REC.build_schedules(cands, max_load=30, limit=3)
    assert schedules
    for schedule in schedules:
        picks = schedule.picks
        for i, p in enumerate(picks):
            for q in picks[i + 1:]:
                assert not REC.section_conflict(p.section, q.section)


def test_load_cap_respected(dbs):
    con, ucon, sid = dbs
    cands = REC.candidates(con, ucon, sid, 10, 20, "HTAE", "BLG", {"HTAE","BLG","BLGE"}, "akts")
    for schedule in REC.build_schedules(cands, max_load=7.0, limit=3):
        assert schedule.load <= 7.0


def test_pinned_course_always_present(dbs):
    con, ucon, sid = dbs
    cands = REC.candidates(con, ucon, sid, 10, 20, "HTAE", "BLG", {"HTAE","BLG","BLGE"}, "akts")
    schedules = REC.build_schedules(cands, max_load=30, limit=3, pinned=["GEO 303E"])
    assert schedules
    assert all("GEO 303E" in s.courses() for s in schedules)


def test_campus_change_counted():
    a = REC.Candidate("A 101", "", "CAP", 5, 3, 0, 0, False, True, [])
    b = REC.Candidate("B 102", "", "CAP", 5, 3, 0, 0, False, True, [])
    schedule = REC.Schedule([
        REC.Pick(a, _section("1", "A 101", [_meeting(1, 480, 600, "INB", "Ayazağa")])),
        REC.Pick(b, _section("2", "B 102", [_meeting(1, 660, 780, "MAC", "Maçka")])),
    ])
    assert schedule.campus_changes() == 1


def test_alternatives_exclude_conflicting_crns(dbs):
    con, ucon, sid = dbs
    cands = REC.candidates(con, ucon, sid, 10, 20, "HTAE", "BLG", {"HTAE","BLG","BLGE"}, "akts")
    schedule = REC.build_schedules(cands, max_load=30, limit=1)[0]
    alts = REC.alternatives(schedule, cands)
    for course, others in alts.items():
        assert all(course not in o for o in others)   # sadece CRN listeleniyor


# --------------------------------------------------------------- darboğaz
def test_blockers_classify_supply_vs_prereq(dbs):
    con, ucon, sid = dbs
    blockers = {b.course: b.reason
                for b in REC.cap_blockers(con, ucon, sid, 20, "BLG", {"HTAE","BLG","BLGE"})}
    assert blockers["BLG 223E"] == "PROGRAMA_KAPALI"
    assert blockers["BLG 351E"] == "ONSART"
    assert "BLG 212E" not in blockers          # alınabilir


def test_blocker_report_flags_partial_schedule(dbs):
    con, ucon, sid = dbs
    blockers = REC.cap_blockers(con, ucon, sid, 20, "BLG", {"HTAE","BLG","BLGE"})
    text = REC.format_blockers(blockers, n_lessons=100)
    assert "kademeli yayınlanıyor" in text
    assert "kademeli yayınlanıyor" not in REC.format_blockers(blockers, n_lessons=9000)


# ------------------------------------------------------------ birim: kredi
def test_load_uses_credits_when_unit_is_kredi(dbs):
    """★ İTÜ kredi sistemi birincil birim. AKTS ile sınır koymak yanıltıcıydı:
    kullanıcının gerçek programı 24 kredi ama 50 AKTS (20.08.2026)."""
    con, ucon, sid = dbs
    con.execute("UPDATE course SET credits=3.0 WHERE code='BLG 212E'")
    con.commit()
    cands = REC.candidates(con, ucon, sid, 10, 20, "HTAE", "BLG",
                           {"HTAE", "BLG", "BLGE"}, "kredi")
    blg = next(c for c in cands if c.course == "BLG 212E")
    assert blg.ects == 7.0 and blg.credits == 3.0
    assert blg.load == 3.0                      # yük krediden sayılıyor

    akts = REC.candidates(con, ucon, sid, 10, 20, "HTAE", "BLG",
                          {"HTAE", "BLG", "BLGE"}, "akts")
    assert next(c for c in akts if c.course == "BLG 212E").load == 7.0


def test_cap_is_measured_in_the_configured_unit(dbs):
    """Sınır 5 iken: 3 kredilik ders girer, aynı dersin 7 AKTS'si girmez."""
    con, ucon, sid = dbs
    con.execute("UPDATE course SET credits=3.0 WHERE code='BLG 212E'")
    con.commit()
    kredi = REC.candidates(con, ucon, sid, 10, 20, "HTAE", "BLG",
                           {"HTAE", "BLG", "BLGE"}, "kredi")
    akts = REC.candidates(con, ucon, sid, 10, 20, "HTAE", "BLG",
                          {"HTAE", "BLG", "BLGE"}, "akts")
    in_kredi = REC.build_schedules(kredi, max_load=5, limit=1)
    in_akts = REC.build_schedules(akts, max_load=5, limit=1)
    assert any("BLG 212E" in s.courses() for s in in_kredi)
    assert not any("BLG 212E" in s.courses() for s in in_akts)


def test_single_program_list_covers_both_plans(dbs):
    """Öğrenci HTAE + BLG + BLGE ile kayıt yapabiliyor; ayrım rol bazlı değil."""
    con, ucon, sid = dbs
    codes = {c.course for c in REC.candidates(
        con, ucon, sid, 10, 20, "HTAE", "BLG", {"HTAE", "BLG", "BLGE"}, "kredi")}
    assert {"BLG 212E", "GEO 303E"} <= codes
    dar = {c.course for c in REC.candidates(
        con, ucon, sid, 10, 20, "HTAE", "BLG", {"HTAE"}, "kredi")}
    assert "BLG 212E" not in dar          # BLG kodu olmadan alınamaz


# ------------------------------------------------- havuz ve şube seçimi
def test_one_course_per_elective_pool(dbs):
    """★ Bir seçmeli havuz slotu TEK ders ile dolar.

    Motor aynı ITB havuzu için HUK 217 + HUK 218'i birlikte öneriyordu (20.08.2026).
    """
    con, ucon, sid = dbs
    con.executemany("INSERT INTO course(code,name,ects,credits,prereq_raw) VALUES (?,?,?,?,NULL)",
                    [("HUK 217", "Hukuk A", 3.0, 3.0), ("HUK 218", "Hukuk B", 3.0, 3.0)])
    cur = con.execute(
        """INSERT INTO plan_slot(plan_id,slot_kind,pool_label_raw,pool_category,
                                 ects,credits,position)
           VALUES (10,'ELECTIVE_POOL','ITB havuzu','ITB',3.0,3.0,9)""")
    for code, day in (("HUK 217", 4), ("HUK 218", 5)):
        con.execute("INSERT INTO pool_option(slot_id,course_code) VALUES (?,?)",
                    (cur.lastrowid, code))
        crn = "9" + code[-3:]
        con.execute("""INSERT INTO lesson(crn,course_code,capacity,enrolled)
                       VALUES (?,?,50,0)""", (crn, code))
        con.execute("""INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min)
                       VALUES (?,?,480,600)""", (crn, day))
        con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES (?,'HTAE')",
                    (crn,))
    con.commit()
    cands = REC.candidates(con, ucon, sid, 10, 20, "HTAE", "BLG",
                           {"HTAE", "BLG", "BLGE"}, "kredi")
    for schedule in REC.build_schedules(cands, max_load=99, limit=3):
        chosen = {p.candidate.course for p in schedule.picks}
        assert not {"HUK 217", "HUK 218"} <= chosen


def test_section_choice_looks_ahead(dbs):
    """★ Şube seçilirken 'en boş' değil, 'en az değer yakan' tercih edilmeli.

    BLG 351E'nin bir şubesi zorunlu bir dersi bloke ediyor, diğeri etmiyordu.
    """
    con, ucon, sid = dbs
    # BLG 351E'ye ikinci bir şube: Çar (hiçbir şeyle çakışmıyor), daha DOLU
    con.execute("""INSERT INTO lesson(crn,course_code,capacity,enrolled)
                   VALUES ('401','BLG 351E',50,40)""")
    con.execute("""INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min)
                   VALUES ('401',3,480,600)""")
    con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES ('401','BLG')")
    # mevcut '400' şubesi Çar 08:00–10:00; onu GEO 303E ile çakıştır (Pzt 08:00)
    con.execute("UPDATE lesson_meeting SET day_of_week=1, start_min=480, end_min=660 "
                "WHERE crn='400'")
    con.execute("UPDATE course SET prereq_raw=NULL WHERE code='BLG 351E'")
    con.commit()
    P.parse_all(con)

    cands = REC.candidates(con, ucon, sid, 10, 20, "HTAE", "BLG",
                           {"HTAE", "BLG", "BLGE"}, "kredi")
    best = REC.build_schedules(cands, max_load=99, limit=1)[0]
    chosen = {p.candidate.course for p in best.picks}
    # daha dolu ama çakışmayan şube seçilerek İKİ ders birden alınabilmeli
    assert {"BLG 351E", "GEO 303E"} <= chosen


def test_timeless_section_is_last_resort(dbs):
    """Saati ilan edilmemiş şube hiçbir şeyle çakışmaz — bu avantaj sayılmamalı."""
    con, ucon, sid = dbs
    con.execute("""INSERT INTO lesson(crn,course_code,capacity,enrolled)
                   VALUES ('500','BLG 212E',50,0)""")     # saatsiz, bol kontenjan
    con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES ('500','BLG')")
    con.commit()
    cands = REC.candidates(con, ucon, sid, 10, 20, "HTAE", "BLG",
                           {"HTAE", "BLG", "BLGE"}, "kredi")
    best = REC.build_schedules(cands, max_load=99, limit=1)[0]
    pick = next(p for p in best.picks if p.candidate.course == "BLG 212E")
    assert pick.section.meetings, "saatli şube varken saatsiz seçilmemeli"


# =========================================================== FAZ 7 eklemeleri
@pytest.fixture()
def dbs7(dbs):
    """dbs + bitirme dersi, kredili dersler ve 8. dönem slotu."""
    con, ucon, sid = dbs
    con.executemany(
        "INSERT INTO course(code,name,credits,ects,prereq_raw) VALUES (?,?,?,?,?)",
        [("GEO 4901E", "Bitirme", 3.0, 12.0, None),
         ("GEO 305E", "8. dönem dersi", 3.0, 5.0, None),
         ("MAT 103E", "Matematik I", 4.0, 6.0, None)])
    con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,ects,position,term_no)
                   VALUES (10,'REQUIRED','GEO 4901E',12.0,1,8)""")
    con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,ects,position,term_no)
                   VALUES (10,'REQUIRED','GEO 305E',5.0,2,8)""")
    for crn, code in (("500", "GEO 4901E"), ("501", "GEO 305E")):
        con.execute("""INSERT INTO lesson(crn,course_code,capacity,enrolled,building)
                       VALUES (?,?,60,0,'INB')""", (crn, code))
        con.execute("""INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min,building)
                       VALUES (?,4,480,600,'INB')""", (crn,))
        con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES (?,'HTAE')",
                    (crn,))
    con.commit()
    P.parse_all(con)
    return con, ucon, sid


def _codes(con, ucon, sid, **kw):
    return {c.course for c in REC.candidates(
        con, ucon, sid, 10, 20, "HTAE", "BLG", {"HTAE", "BLG", "BLGE"}, "kredi", **kw)}


# ------------------------------------------------------------- kredi eşiği
def test_credit_threshold_blocks_graduation_project(dbs7):
    """★ 95 kredi altında bitirme çalışması ÖNERİLMEZ (kullanıcı beyanı)."""
    from itucap import policy as POL
    con, ucon, sid = dbs7
    rules = [POL.CreditRule("Bitirme", 95.0, patterns=("* 4901E",))]
    assert "GEO 4901E" not in _codes(con, ucon, sid, credit_rules=rules)
    # eşik altındaki ders elenirken NORMAL ders etkilenmemeli
    assert "GEO 305E" in _codes(con, ucon, sid, credit_rules=rules)


def test_credit_threshold_opens_when_credits_suffice(dbs7):
    from itucap import policy as POL
    con, ucon, sid = dbs7
    ucon.execute("INSERT INTO earned_course(student_id,course_code,grade,status,source)"
                 " VALUES (?,'MAT 103E','AA','PASSED','manual')", (sid,))
    ucon.commit()                                    # 4 kredi
    rules = [POL.CreditRule("Bitirme", 4.0, patterns=("* 4901E",))]
    assert "GEO 4901E" in _codes(con, ucon, sid, credit_rules=rules)


def test_credit_threshold_appears_in_blocker_report(dbs7, tmp_path, monkeypatch):
    """Eleyen kural kendini göstermeli; sessiz eleme 'ders nereye gitti' yaratır."""
    from itucap import policy as POL
    con, ucon, sid = dbs7
    f = tmp_path / "kurallar.toml"
    f.write_text('[[kredi_esigi]]\nad = "Bitirme"\nmin_kredi = 95\n'
                 'dersler = ["BLG 212E"]\n', encoding="utf-8")
    monkeypatch.setattr(POL, "DEFAULT_PATH", f)
    reasons = {b.course: b.reason for b in
               REC.cap_blockers(con, ucon, sid, 20, "BLG", {"HTAE", "BLG", "BLGE"})}
    assert reasons.get("BLG 212E") == "KREDI_ESIGI"


# ------------------------------------------------------ dönemlik + alttan
def test_max_term_drops_later_terms(dbs7):
    """★ 'Dönemlik + alttan': ilerideki dönemin dersleri elenir."""
    con, ucon, sid = dbs7
    assert "GEO 305E" in _codes(con, ucon, sid)                 # sınırsız
    assert "GEO 305E" not in _codes(con, ucon, sid, max_term=7)  # 8. dönem


def test_max_term_keeps_termless_second_program(dbs7):
    """ÇAP planı dönemsiz — eleyecek dönem bilgisi yok, hepsi kalır."""
    con, ucon, sid = dbs7
    codes = _codes(con, ucon, sid, max_term=1)
    assert "BLG 212E" in codes
    assert "GEO 303E" not in codes                # anadal, 5. dönem


def test_candidates_carry_plan_and_term(dbs7):
    con, ucon, sid = dbs7
    cands = {c.course: c for c in REC.candidates(
        con, ucon, sid, 10, 20, "HTAE", "BLG", {"HTAE", "BLG", "BLGE"}, "kredi")}
    assert (cands["GEO 303E"].plan_id, cands["GEO 303E"].term_no) == (10, 5)
    assert (cands["BLG 212E"].plan_id, cands["BLG 212E"].term_no) == (20, None)


# ---------------------------------------------------------------- yandal
def test_second_program_can_be_yandal(dbs7):
    """Yandal aynı motorla çalışır: rol değişir, arz bonusu aynı kalır."""
    con, ucon, sid = dbs7
    cands = {c.course: c for c in REC.candidates(
        con, ucon, sid, 10, 20, "HTAE", "BLG", {"HTAE", "BLG", "BLGE"}, "kredi",
        second_role="YANDAL")}
    assert cands["BLG 212E"].role == "YANDAL"
    assert any("Yandal dersi" in r for r in cands["BLG 212E"].reasons)
    assert cands["BLG 212E"].score > cands["GEO 303E"].score


def test_no_second_program_means_anadal_only(dbs7):
    con, ucon, sid = dbs7
    codes = _codes(con, ucon, sid, second_role="")
    assert "BLG 212E" not in codes and "GEO 303E" in codes
