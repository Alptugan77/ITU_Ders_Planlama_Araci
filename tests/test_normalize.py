import pytest

from itucap import normalize as N


@pytest.mark.parametrize("raw,cat,term", [
    ("8.yy Seçime Bağlı Ders (MT)", "MT", 8),
    ("8.yy Elective Course (MT)", "MT", 8),
    ("7.yy Seçime Bağlı Ders(MT)", "MT", 7),          # boşluk yok
    ("5.yy Seçime Bağlı Ders(ITB)", "ITB", 5),
    ("3.yySınırlı Seçim Dersi(TB)", "TB", 3),
    ("4.yySınırlı Seçim Dersi(TM)", "TM", 4),
    ("5th Semester Elective Course (TM)", "TM", 5),
    ("English Course 1", "ENG", None),
    ("Selective", "OTHER", None),
])
def test_pool_label(raw, cat, term):
    assert N.normalize_pool_label(raw) == (cat, term)


def test_unmatched_is_logged():
    N.unmatched_labels.clear()
    N.normalize_pool_label("Selective")
    assert "Selective" in N.unmatched_labels  # sessizce yutulmuyor


@pytest.mark.parametrize("raw,out", [
    ("MAT103E", "MAT 103E"),
    ("MAT  103E", "MAT 103E"),
    ("blg 4901e", "BLG 4901E"),
    ("KIM 101EL", "KIM 101EL"),
])
def test_course_code(raw, out):
    assert N.normalize_course_code(raw) == out


def test_time_range():
    assert N.parse_time_range("11:30/13:29") == (690, 809)
    assert N.parse_time_range("--") is None
    assert N.parse_time_range("") is None


@pytest.mark.parametrize("day,idx", [
    ("Monday", 1), ("Tuesday", 2), ("Cuma", 5), ("Perşembe", 4), ("Sunday", 7),
])
def test_days(day, idx):
    assert N.day_to_index(day) == idx


def test_obs_code():
    assert N.obs_code_to_program("HTAE_LS") == "HTAE"
    assert N.obs_code_to_program("EHB_MTM_LS") == "EHB_MTM"


def test_split_cap_plan_code():
    # ★ ÇAP planları (anadal, çap) çiftine göre tanımlı
    assert N.split_cap_plan_code("TUMMUH_BLG") == ("TUMMUH", "BLG")
    assert N.split_cap_plan_code("GEO_BLG") == ("GEO", "BLG")
    assert N.split_cap_plan_code("BLG") == (None, "BLG")
