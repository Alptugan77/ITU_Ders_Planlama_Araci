"""Faz 11 — MADDE 17 kredi yükü, BL/BZ, plandan tikleme, yedekten geri yükleme."""
import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import config, db, policy as POL, student as S


MADDE17 = """\
[kredi_yuku_bant]
min_kredi  = 13
max_kredi  = 22
muaf       = ["birinci_yariyil", "cap", "son_sinif"]
dogrulandi = true
kaynak     = "MADDE 17/1"

[[kredi_yuku]]
ad = "genel"
max_kredi = 22
min_gno = 0.0

[[kredi_yuku]]
ad = "25 kredi dahil"
max_kredi = 25
min_gno = 2.25

[[kredi_yuku]]
ad = "25 üzeri"
max_kredi = 40
min_gno = 3.00
"""


@pytest.fixture()
def rules(tmp_path):
    path = tmp_path / "kurallar.toml"
    path.write_text(MADDE17, encoding="utf-8")
    return path


# ================================================ MADDE 17/2-a: GNO'ya bağlı tavan
@pytest.mark.parametrize("gno,expected", [
    (0.00, 22),      # şart yok -> genel sınır
    (2.24, 22),      # eşiğin altı
    (2.25, 25),      # "25 kredi DE DAHİL olmak üzere en az 2.25"
    (2.63, 25),      # kullanıcının GNO'su
    (2.99, 25),
    (3.00, 40),      # "25 kredinin üzerinde ... en az 3.00"
    (3.80, 40),
])
def test_ceiling_follows_gpa(rules, gno, expected):
    assert POL.load_limit(gno, "cap", path=rules).maximum == expected


def test_threshold_is_inclusive(rules):
    """★ '25 kredi DE DAHİL' — tam 2.25'te 25 kredi açılmalı, açılmazsa
    yönetmeliği öğrenci aleyhine yorumlamış oluruz."""
    assert POL.load_limit(2.25, "cap", path=rules).maximum == 25
    assert POL.load_limit(3.00, "cap", path=rules).maximum == 40


# ============================================== MADDE 17/1: 13–22 bandı ve muafiyet
def test_cap_student_has_no_minimum(rules):
    """★ ÇAP öğrencisi alt sınırdan MUAF (fıkra 1'de açıkça sayılıyor)."""
    limit = POL.load_limit(2.63, "cap", path=rules)
    assert limit.minimum == 0 and limit.exempt_from_minimum is True
    assert any("ÇAP öğrencisi" in r for r in limit.reasons)


def test_single_program_student_has_the_minimum(rules):
    limit = POL.load_limit(2.63, "yok", path=rules)
    assert limit.minimum == 13 and limit.exempt_from_minimum is False


def test_first_term_and_final_year_are_exempt(rules):
    assert POL.load_limit(2.0, "yok", first_term=True, path=rules).minimum == 0
    assert POL.load_limit(2.0, "yok", final_year=True, path=rules).minimum == 0


def test_exemption_does_not_lift_the_ceiling(rules):
    """★ İki fıkra AYRI: (1) bandın alt sınırından muaf eder, (2) üst sınırı
    GNO'ya bağlar ve 'her öğrenci' der. Muafiyeti tavana da uygulamak
    öğrenciyi kayıtta reddedilecek bir programa yönlendirirdi."""
    limit = POL.load_limit(2.63, "cap", path=rules)
    assert limit.exempt_from_minimum is True
    assert limit.maximum == 25          # tavan hâlâ GNO'dan


def test_next_band_explains_what_is_needed(rules):
    limit = POL.load_limit(2.63, "cap", path=rules)
    assert limit.next_band.max_credits == 40 and limit.next_band.min_gpa == 3.00
    assert any("3.00" in r for r in limit.reasons)


def test_verified_flag_travels(rules):
    assert POL.load_limit(2.5, "cap", path=rules).verified is True
    assert "MADDE 17" in POL.load_limit(2.5, "cap", path=rules).source


def test_missing_declaration_claims_nothing(tmp_path):
    """★ Kural beyan edilmemişse arayüz bir sayı UYDURMAMALI."""
    assert POL.load_limit(3.0, "cap", path=tmp_path / "yok.toml") is None


def test_shipped_config_declares_madde_17():
    limit = POL.load_limit(2.63, "cap",
                           path=config.ROOT / "config" / "kurallar.toml")
    assert limit and limit.maximum == 25 and limit.verified is True


# ==================================================== BL / BZ — 0 kredili dersler
@pytest.fixture()
def con(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    con = db.connect(tmp_path / "ref.sqlite3", "schema.sql")
    con.executemany("INSERT INTO course(code,name,credits,ects) VALUES (?,?,?,?)",
                    [("MAT 103E", "Matematik", 4.0, 6.0),
                     ("STJ 300", "Staj", 0.0, 2.0),
                     ("DAN 102", "Danışmanlık", 0.0, 1.0)])
    con.commit()
    return con


def _ucon(tmp_path):
    ucon = db.connect(tmp_path / "user.sqlite3", "schema_user.sql")
    return ucon, S.ensure_student(ucon)


def test_bl_passes_and_bz_fails(con, tmp_path):
    """0 kredili derste başarı sistemi harf notu değil: BL geçti, BZ kaldı."""
    from itucap import rules as R
    ucon, sid = _ucon(tmp_path)
    S.add_entries(ucon, sid, [S.make_entry("STJ 300", "BL"),
                              S.make_entry("DAN 102", "BZ")])
    grades = S.grades(ucon, sid)
    assert "STJ 300" in grades and "DAN 102" not in grades
    assert R.passed("BL") and not R.passed("BZ")


def test_bl_bz_never_touch_the_gpa(con, tmp_path):
    """★ BL'yi 1.00, BZ'yi 0.00 saymak GNO'yu bozar — üçü de dışarıda."""
    ucon, sid = _ucon(tmp_path)
    S.add_entries(ucon, sid, [S.make_entry("MAT 103E", "BB"),
                              S.make_entry("STJ 300", "BL"),
                              S.make_entry("DAN 102", "BZ")])
    res = POL.gpa(con, S.graded(ucon, sid))
    assert res.value == 3.0 and res.counted == 1
    assert set(res.skipped_not_graded) == {"STJ 300", "DAN 102"}
    assert "BZ" in POL.GPA_EXCLUDED and "BL" in POL.GPA_EXCLUDED


def test_bl_does_not_earn_credit(con, tmp_path):
    """BL geçer ama 0 kredili ders kredi kazandırmaz — bitirme eşiğini şişirmez."""
    ucon, sid = _ucon(tmp_path)
    S.add_entries(ucon, sid, [S.make_entry("STJ 300", "BL")])
    assert POL.earned_credits(con, S.grades(ucon, sid)) == 0.0


def test_pass_fail_grades_are_published_for_the_ui():
    assert POL.PASS_FAIL_GRADES == ("BL", "BZ")


# ====================================================== yedekten geri yükleme
def test_restore_brings_back_the_previous_transcript(con, tmp_path):
    """★ Yanlışlıkla silinen transkript geri gelebilmeli."""
    ucon, sid = _ucon(tmp_path)
    S.add_entries(ucon, sid, [S.make_entry("MAT 103E", "AA"),
                              S.make_entry("STJ 300", "BL")])
    name = S.backup(ucon, sid, stamp="20260822-010000").name
    S.add_entries(ucon, sid, [S.make_entry("MAT 103E", "FF")], replace=True)
    assert len(S.backups()) == 1
    assert S.restore(ucon, sid, name) == 2
    grades = S.grades(ucon, sid)
    assert grades.get("MAT 103E") == "AA" and "STJ 300" in grades


def test_restore_backs_up_first(con, tmp_path):
    """Geri yükleme de silici — önce mevcut hâli yedekle, iki kez kaybetme."""
    ucon, sid = _ucon(tmp_path)
    S.add_entries(ucon, sid, [S.make_entry("MAT 103E", "AA")])
    name = S.backup(ucon, sid, stamp="20260822-010000").name
    S.add_entries(ucon, sid, [S.make_entry("STJ 300", "BL")], replace=True)
    S.restore(ucon, sid, name)
    assert len(S.backups()) == 2          # ilk yedek + geri yüklemeden önceki


def test_restore_refuses_paths_outside_the_backup_folder(con, tmp_path):
    """★ Dosya adı arayüzden geliyor — dizin çıkışı olmamalı."""
    ucon, sid = _ucon(tmp_path)
    S.add_entries(ucon, sid, [S.make_entry("MAT 103E", "AA")])
    S.backup(ucon, sid, stamp="20260822-010000")
    with pytest.raises(ValueError):
        S.restore(ucon, sid, "../../../etc/passwd")
    with pytest.raises(ValueError):
        S.restore(ucon, sid, "yok.txt")


def test_backups_list_counts_courses(con, tmp_path):
    ucon, sid = _ucon(tmp_path)
    S.add_entries(ucon, sid, [S.make_entry("MAT 103E", "AA"),
                              S.make_entry("STJ 300", "BL")])
    S.backup(ucon, sid, stamp="20260822-010000")
    assert S.backups()[0]["courses"] == 2
    assert S.backups()[0]["stamp"] == "20260822-010000"


# ============================================================ kontenjan nöbeti
def test_watch_interval_has_a_floor(monkeypatch):
    """★ OBS'yi yormamak: 5 dakikanın altına inilemiyor."""
    from itucap import watch
    seen = {}
    monkeypatch.setattr(watch, "tick", lambda s, skip_obs=False: __import__(
        "itucap.changes", fromlist=["Diff"]).Diff())
    monkeypatch.setattr(watch.time, "sleep", lambda n: seen.setdefault("slept", n))
    watch.run(every=5, once=True)          # once -> uyumadan çıkar
    assert watch.MIN_INTERVAL == 300


def test_watch_summary_puts_opportunities_first():
    from itucap import changes as CH, watch
    diff = CH.Diff(since="a", until="b",
                   freed=[{"course": "BLG 351E"}], filled=[{"course": "ATA 121"}])
    text = watch.summarize(diff)
    assert text.index("yer açıldı") < text.index("doldu")


def test_only_good_ignores_bad_news():
    """`--only-good`: dolan kontenjan bilgi ama gece yarısı uyandırmaya değmez."""
    from itucap import changes as CH, watch
    bad = CH.Diff(since="a", until="b", filled=[{"course": "X 101"}])
    good = CH.Diff(since="a", until="b", freed=[{"course": "X 101"}])
    assert watch.interesting(bad, only_good=True) is False
    assert watch.interesting(bad, only_good=False) is True
    assert watch.interesting(good, only_good=True) is True


def test_watch_uses_declared_courses_when_present(tmp_path, monkeypatch):
    from itucap import watch
    settings = config.Settings(watch_courses=["blg 351e", "BLG 335E"])
    assert watch.watch_codes(None, None, settings) == {"BLG 351E", "BLG 335E"}


def test_applescript_quoting_is_escaped():
    from itucap import watch
    assert watch.json_str('a"b') == '"a\\"b"'


def test_two_backups_in_the_same_second_do_not_collide(con, tmp_path):
    """★ Damga saniye çözünürlüklü. Aynı saniyedeki ikinci yedek birinciyi
    ezerse, kurtarma özelliği tam da önlemesi gereken kaybı yaratır."""
    ucon, sid = _ucon(tmp_path)
    S.add_entries(ucon, sid, [S.make_entry("MAT 103E", "AA")])
    first = S.backup(ucon, sid, stamp="20260822-010000")
    S.add_entries(ucon, sid, [S.make_entry("MAT 103E", "AA"),
                              S.make_entry("STJ 300", "BL")], replace=True)
    second = S.backup(ucon, sid, stamp="20260822-010000")
    assert first != second
    assert len(S.backups()) == 2
    assert len(S.parse_text(first.read_text(encoding="utf-8"))[0]) == 1
    assert len(S.parse_text(second.read_text(encoding="utf-8"))[0]) == 2


# =========================================== MADDE 20 — tam not ölçeği (artılar)
@pytest.mark.parametrize("grade,points", [
    ("AA", 4.00), ("BA+", 3.75), ("BA", 3.50), ("BB+", 3.25), ("BB", 3.00),
    ("CB+", 2.75), ("CB", 2.50), ("CC+", 2.25), ("CC", 2.00),
    ("DC+", 1.75), ("DC", 1.50), ("DD+", 1.25), ("DD", 1.00),
    ("FF", 0.00), ("VF", 0.00),
])
def test_madde20_scale(grade, points):
    """★ Ölçek 0.25 adımlı; artı notlar ara basamaklar (doğrulandı 22.08.2026)."""
    from itucap.prereq import GRADE_POINTS
    assert GRADE_POINTS[grade] == points


def test_plus_grades_parse_in_transcript_lines():
    """'MAT 103E BA+' girilebilmeli — desen iki harfle sınırlıydı."""
    for text, expect in (("MAT 103E BA+", "BA+"), ("fiz 101e cc+", "CC+"),
                         ("GEO 220E M", "M"), ("BLG 112E T", "T")):
        entry = S.make_entry(*text.split(maxsplit=1)) if False else S.parse_line(text)
        assert entry.grade == expect, text


def test_plus_grades_parse_in_prerequisites():
    """★ '+' regex metakarakteri — kaçırılmazsa 'BA+' deseni 'BAAA' ile eşleşir."""
    from itucap import prereq as P
    node = P.parse("BLG 212E MIN BB+").tree
    assert node.course == "BLG 212E" and node.min_grade == "BB+"
    both = P.parse("(MAT 103E MIN CC+ veya MAT 104E MIN DD+)").tree
    assert [c.min_grade for c in both.children] == ["CC+", "DD+"]


def test_plus_grade_satisfies_a_lower_threshold():
    from itucap import rules as R
    from itucap import db as _db
    import tempfile, pathlib
    tmp = pathlib.Path(tempfile.mkdtemp())
    con = _db.connect(tmp / "r.sqlite3", "schema.sql")
    con.execute("INSERT INTO course(code,name,prereq_raw) VALUES ('XYZ 200','x','WQR 100 MIN CC')")
    con.execute("INSERT INTO course(code,name) VALUES ('WQR 100','w')")
    con.commit()
    from itucap import prereq as P
    P.parse_all(con)
    assert R.can_take(con, "XYZ 200", {"WQR 100": "CC+"}).status is R.Status.OK
    assert R.can_take(con, "XYZ 200", {"WQR 100": "DC+"}).status is R.Status.BLOCKED


def test_withdrawal_and_incomplete_do_not_pass():
    from itucap import rules as R
    assert not R.passed("T") and not R.passed("E")
    assert R.passed("M") and R.passed("MU")      # muaf: önşart açar


def test_marks_excluded_from_gpa(con, tmp_path):
    """MADDE 20: 'BL, E, BZ veya M olan dersler hariç' + T (çekilme)."""
    ucon, sid = _ucon(tmp_path)
    S.add_entries(ucon, sid, [S.make_entry("MAT 103E", "BA+"),
                              S.make_entry("STJ 300", "BL"),
                              S.make_entry("DAN 102", "BZ")])
    res = POL.gpa(con, S.graded(ucon, sid))
    assert res.value == 3.75 and res.counted == 1
    assert {"BL", "BZ", "M", "MU", "T", "E"} <= POL.GPA_EXCLUDED


def test_conditional_pass_excludes_unknown_grades(con, tmp_path):
    """★ Notu GİRİLMEMİŞ ders DD varsayılıyor; onu 'şartlı geçer' diye
    raporlamak var olmayan bir sorun göstermek olurdu."""
    ucon, sid = _ucon(tmp_path)
    S.add_entries(ucon, sid, [S.make_entry("MAT 103E", "DD"),     # gerçek DD
                              S.make_entry("STJ 300", "")])       # not girilmedi
    con.execute("UPDATE course SET credits=3.0 WHERE code='STJ 300'")
    con.commit()
    res = POL.gpa(con, S.graded(ucon, sid), S.uncertain_grades(ucon, sid))
    assert res.conditional == ["MAT 103E"]
    assert res.uncertain == ["STJ 300"]


def test_cli_replace_backs_up_first(con, tmp_path, monkeypatch, capsys):
    """★ Silici yazma komut satırında da yedek bırakmalı — sunucuda vardı,
    komutta yoktu ve `--replace` ile yanlış dosya transkripti sildi
    (22.08.2026, gerçekten oldu)."""
    ucon, sid = _ucon(tmp_path)
    S.add_entries(ucon, sid, [S.make_entry("MAT 103E", "AA")])
    assert S.backups() == []
    S.backup(ucon, sid)                       # komutun yaptığı çağrı
    S.add_entries(ucon, sid, [], replace=True)
    assert S.grades(ucon, sid) == {}
    assert len(S.backups()) == 1
    name = S.backups()[0]["file"]
    assert S.restore(ucon, sid, name) == 1
    assert S.grades(ucon, sid) == {"MAT 103E": "AA"}
