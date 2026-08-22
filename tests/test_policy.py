"""Faz 7 — mevzuat kısıtları: kredi eşiği (bitirme çalışması) ve program seçimi."""
import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import config, db, policy as POL


@pytest.fixture()
def con(tmp_path):
    con = db.connect(tmp_path / "ref.sqlite3", "schema.sql")
    con.executemany(
        "INSERT INTO course(code,name,credits,ects,prereq_raw) VALUES (?,?,?,?,?)",
        [("GEO 4901E", "Bitirme I", 3.0, 12.0, None),
         ("GEO 4902E", "Bitirme II", 5.0, 15.0, None),
         ("BLG 4901E", "Graduation I", 3.0, 12.0, None),
         ("GEO 401E", "Normal ders", 3.0, 5.0, None),
         ("MAT 103E", "Matematik I", 4.0, 6.0, None),
         ("ESKI 101", "Kredisi bilinmeyen", None, None, None)],
    )
    con.commit()
    return con


RULES = [POL.CreditRule("Bitirme çalışması", 95.0, patterns=("* 4901E", "* 4902E"))]


# ------------------------------------------------------------------ eşleşme
def test_pattern_matches_both_programs():
    r = RULES[0]
    assert r.matches("GEO 4901E") and r.matches("BLG 4901E")
    assert not r.matches("GEO 401E")


def test_explicit_course_list_matches():
    r = POL.CreditRule("Staj", 60.0, courses=("GEO 3001",))
    assert r.matches("geo 3001")           # büyük/küçük harf duyarsız
    assert not r.matches("GEO 3002")


# ------------------------------------------------------------- kredi sayımı
def test_only_passed_courses_count(con):
    grades = {"MAT 103E": "AA", "GEO 401E": "FF"}
    assert POL.earned_credits(con, grades) == 4.0


def test_unknown_credit_course_counts_zero_and_is_reported(con):
    """★ Katalogda kredisi olmayan ders 0 sayılır — eşik OLDUĞUNDAN ZOR görünür.

    Ters yön tehlikeli olurdu: eksik veriyi lehte yorumlayıp 'alabilirsin'
    demek, öğrenciyi OBS'de reddedilecek bir derse yönlendirirdi."""
    grades = {"MAT 103E": "AA", "ESKI 101": "BB"}
    assert POL.earned_credits(con, grades) == 4.0
    assert POL.unknown_credit_courses(con, grades) == ["ESKI 101"]


def test_waiver_does_not_earn_credit(con, tmp_path, monkeypatch):
    """★ Muafiyet önşartı açar ama KREDİ KAZANDIRMAZ.

    İkisi karışsaydı muaf sayılan dersler bitirme eşiğini erkenden doldurur,
    öğrenci alamayacağı derse yönlendirilirdi (21.08.2026)."""
    from itucap import declared, rules as R

    waiver = tmp_path / "denklikler.toml"
    waiver.write_text('[[muafiyet]]\ndersler = ["MAT 103E"]\nnot_ = "t"\n', encoding="utf-8")
    monkeypatch.setattr(declared, "DEFAULT_PATH", waiver)

    assert POL.earned_credits(con, {}) == 0.0            # gerçek not yok -> kredi yok
    assert R.prereq_view({}).get("MAT 103E")             # ama önşart görünümünde var


# -------------------------------------------------------------------- kontrol
def test_below_threshold_blocks():
    v = POL.check("GEO 4901E", 85.0, RULES)
    assert not v and v.missing == 10.0 and v.rule.name == "Bitirme çalışması"


def test_at_threshold_allows():
    assert POL.check("GEO 4901E", 95.0, RULES)
    assert POL.check("GEO 4901E", 120.0, RULES)


def test_unmatched_course_always_allowed():
    assert POL.check("GEO 401E", 0.0, RULES)


def test_strictest_rule_wins():
    rules = [POL.CreditRule("gevşek", 60.0, patterns=("GEO *",)),
             POL.CreditRule("katı", 95.0, courses=("GEO 4901E",))]
    v = POL.check("GEO 4901E", 70.0, rules)
    assert not v and v.rule.name == "katı"


# ------------------------------------------------------------------- beyan
def test_rules_come_from_toml_not_code(tmp_path):
    """Mevzuat değişince KOD değil dosya değişsin."""
    f = tmp_path / "kurallar.toml"
    f.write_text('[[kredi_esigi]]\nad = "Test"\nmin_kredi = 42\n'
                 'dersler = ["XXX 999"]\n', encoding="utf-8")
    rules = POL.load_rules(f)
    assert [r.name for r in rules] == ["Test"]
    assert not POL.check("XXX 999", 41.0, rules)
    assert POL.check("XXX 999", 42.0, rules)


def test_missing_file_falls_back_to_default(tmp_path):
    rules = POL.load_rules(tmp_path / "yok.toml")
    assert rules and rules[0].min_credits == 95.0
    assert not POL.check("GEO 4901E", 94.0, rules)


def test_shipped_config_declares_the_95_credit_rule():
    """★ Projenin kendi config'i kullanıcının beyanını taşımalı (21.08.2026)."""
    rules = POL.load_rules()
    hit = [r for r in rules if r.matches("GEO 4901E")]
    assert hit and hit[0].min_credits == 95.0


def test_describe_runs():
    assert "95" in POL.describe(RULES)


# ------------------------------------------------------- ikinci program seçimi
def test_second_kind_maps_to_role_and_plan(tmp_path):
    f = tmp_path / "s.toml"
    f.write_text('[student]\nanadal_program = "HTAE"\nsecond_kind = "yandal"\n'
                 'yandal_program = "BLG"\nyandal_plan_id = 77\n', encoding="utf-8")
    s = config.Settings.load(f)
    assert (s.second_role, s.second_label) == ("YANDAL", "Yandal")
    assert (s.second_program, s.second_plan_id) == ("BLG", 77)
    # yandal seçilince OBS'den yandal planı da çekilmeli
    assert "yandal" in s.scrape_plan_types
    # program kodları beyan edilmemişse kendi kodlarına düşer
    assert s.allowed_programs == {"HTAE", "BLG"}


def test_second_kind_cap_is_the_default(tmp_path):
    f = tmp_path / "s.toml"
    f.write_text('[student]\nanadal_program = "HTAE"\ncap_program = "BLG"\n'
                 'cap_plan_id = 2229\n', encoding="utf-8")
    s = config.Settings.load(f)
    assert (s.second_role, s.second_program, s.second_plan_id) == ("CAP", "BLG", 2229)


def test_second_kind_none_means_single_program(tmp_path):
    f = tmp_path / "s.toml"
    f.write_text('[student]\nanadal_program = "HTAE"\nsecond_kind = "yok"\n'
                 'cap_program = "BLG"\n', encoding="utf-8")
    s = config.Settings.load(f)
    assert s.second_role == "" and s.second_program == ""
    assert s.second_plan_id is None
    assert s.allowed_programs == {"HTAE"}


def test_unknown_second_kind_falls_back(tmp_path):
    f = tmp_path / "s.toml"
    f.write_text('[student]\nsecond_kind = "sacma"\n', encoding="utf-8")
    assert config.Settings.load(f).second_kind == "cap"
