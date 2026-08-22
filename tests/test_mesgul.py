"""Faz 15 — ders konulamayacak saatler (okul dışı işler).

Kullanıcı isteği 22.08.2026: staj, antrenman, servis gibi işler için ızgarada
kapalı saat belirleyebilmek.

★ Motorda YENİ BİR ÇAKIŞMA MANTIĞI YOK. Aralık, zaten kayıtlı bir ders gibi
`build_schedules(fixed=…)` ile veriliyor. İki ayrı çakışma tanımı olsaydı biri
düzelirken öbürü unutulurdu — kayıt haftasında fark edilecek türden bir hata.
"""
import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import recommend as REC
from itucap.normalize import format_busy, parse_busy


# ------------------------------------------------------------- ayrıştırma
@pytest.mark.parametrize("metin,gun,bas,bit,ad", [
    ("PZT 12:30-14:30 iş",        1, 750, 870, "iş"),
    ("pzt 12:30-14:30",           1, 750, 870, "meşgul"),
    ("çarşamba 08:30-10:30 spor", 3, 510, 630, "spor"),
    ("CARSAMBA 08:30-10:30",      3, 510, 630, "meşgul"),
    ("3 9.00-11.00 antrenman",    3, 540, 660, "antrenman"),
    ("CUM 16:00-18:00 servis",    5, 960, 1080, "servis"),
])
def test_parse_busy(metin, gun, bas, bit, ad):
    b = parse_busy(metin)
    assert b == {"day": gun, "start": bas, "end": bit, "label": ad}


@pytest.mark.parametrize("kotu", [
    "", "saçma", "PZT", "PZT 12:30", "PZT 14:30-12:30",   # bitiş önce
    "PZT 12:30-12:30",                                    # sıfır uzunluk
    "XXX 12:30-14:30",                                    # gün yok
])
def test_parse_busy_rejects_garbage(kotu):
    """★ Anlaşılmayan bir KISIT tahmin edilmez.

    Tahmin etseydik yanlış saatte ders elenirdi ve kullanıcı bunu ancak
    kayıt gününde fark ederdi."""
    assert parse_busy(kotu) is None


def test_format_and_parse_round_trip():
    for gun in range(1, 8):
        metin = format_busy(gun, 510, 630, "iş")
        assert parse_busy(metin) == {"day": gun, "start": 510,
                                     "end": 630, "label": "iş"}


def test_format_without_label_still_parses():
    assert parse_busy(format_busy(2, 600, 720))["label"] == "meşgul"


# --------------------------------------------------------- motor kısıtı
def _sec(crn, day, start, end, course="X 101"):
    return REC.Section(crn=crn, course=course, instructor=None,
                       capacity=30, enrolled=0,
                       meetings=(REC.Meeting(day, start, end, None, None, None),))


def _cand(course, sections, score=10.0):
    return REC.Candidate(course=course, name=course, role="ANADAL", ects=5,
                         credits=3, unlocks=0, tier=0, critical=False,
                         required=True, sections=sections, score=score)


def test_busy_blocks_a_conflicting_section():
    """★ Kapalı saatle çakışan şube programa GİRMEMELİ."""
    cand = _cand("GEO 101", [_sec("1", 1, 750, 870, "GEO 101")])   # PZT 12:30
    busy = REC.busy_sections(["PZT 12:30-14:30 iş"])
    scheds = REC.build_schedules([cand], max_load=30, fixed=busy)
    secilen = {p.candidate.course for s in scheds for p in s.picks}
    assert "GEO 101" not in secilen

    # Kısıt olmayınca aynı ders seçilebiliyor — testin anlamlı olduğunun kanıtı.
    assert any(p.candidate.course == "GEO 101"
               for s in REC.build_schedules([cand], max_load=30) for p in s.picks)


def test_busy_leaves_another_section_available():
    """Dersin başka şubesi varsa o seçilmeli — ders tamamen elenmemeli."""
    cand = _cand("GEO 101", [_sec("1", 1, 750, 870, "GEO 101"),    # çakışıyor
                             _sec("2", 3, 750, 870, "GEO 101")])   # çakışmıyor
    scheds = REC.build_schedules([cand], max_load=30,
                                 fixed=REC.busy_sections(["PZT 12:30-14:30 iş"]))
    crn = [p.section.crn for s in scheds for p in s.picks
           if p.candidate.course == "GEO 101"]
    assert crn and set(crn) == {"2"}


def test_adjacent_times_are_not_blocked():
    """Bitişik ders engellenmemeli.

    Sınırı `<=` yazmak, 14:30'da biten bir kısıttan sonra 14:30'da başlayan
    dersi de elerdi — kullanıcının hiç istemediği bir daralma."""
    cand = _cand("GEO 101", [_sec("1", 1, 870, 990, "GEO 101")])   # 14:30 başlıyor
    scheds = REC.build_schedules([cand], max_load=30,
                                 fixed=REC.busy_sections(["PZT 12:30-14:30 iş"]))
    assert any(p.candidate.course == "GEO 101" for s in scheds for p in s.picks)


def test_unparsable_declaration_is_skipped_not_fatal():
    """Bozuk satır motoru düşürmemeli — ama kısıt da uygulanmamalı."""
    busy = REC.busy_sections(["saçma satır", "PZT 12:30-14:30 iş"])
    assert len(busy) == 1
    assert busy[0].meetings[0].day == 1


def test_busy_sections_carry_no_capacity():
    """Sahte şube kontenjan sayacına karışmamalı."""
    for s in REC.busy_sections(["PZT 12:30-14:30 iş"]):
        assert s.capacity == 0 and s.free == 0


def test_empty_declaration_changes_nothing():
    cand = _cand("GEO 101", [_sec("1", 1, 750, 870, "GEO 101")])
    a = REC.build_schedules([cand], max_load=30, fixed=REC.busy_sections([]))
    b = REC.build_schedules([cand], max_load=30)
    assert len(a) == len(b)


# ---------------------------------------------------------------- arayüz
def test_ui_reports_unparsable_declarations():
    """★ Anlaşılmayan satır SESSİZCE düşmüyor.

    Düşseydi kullanıcı koyduğunu sandığı bir kısıtın uygulanmadığını hiç
    öğrenemezdi."""
    from itucap import ui as UI

    out = UI._busy_info(["PZT 12:30-14:30 iş", "bozuk"])
    assert out[0]["ok"] is True and out[0]["label"] == "iş"
    assert out[1]["ok"] is False and out[1]["raw"] == "bozuk"


def test_ui_keeps_raw_text_for_removal():
    """Silme metinle yapılıyor; indeksle yapsaydık iki sekme açıkken
    kullanıcı yanlış aralığı silerdi."""
    from itucap import ui as UI

    out = UI._busy_info(["PZT 12:30-14:30 iş"])
    assert out[0]["raw"] == "PZT 12:30-14:30 iş"
