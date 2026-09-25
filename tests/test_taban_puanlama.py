"""Faz 22 — yarıyıl kredi tabanı MOTORA giriyor (yapılacaklar 1.4).

Taban Faz 13'te eklenmişti ama yalnız bir **uyarıydı**: motor onu bilmiyordu.
Gerçek veride sonuç şuydu — önerilen program ikinci anadaldan **4 kredi**
içeriyordu, taban ise **9**. Yani motor kabul edilemez bir programı "en iyi
program" diye sunuyordu.

★ SERT KISIT DEĞİL, SIRALAMA. Yönerge tabanın "ÇAP Koordinatörünün uygun
görüşü ve Fakülte Yönetim Kurulu Kararı ile yarıya kadar düşürülebileceğini"
söylüyor; ayrıca o dönem açılan ders yetmiyor olabilir. Karşılayan hiç program
yoksa eleyip boş liste döndürmek, çözülebilir bir durumu imkânsız göstermek
olurdu. Bu dosyadaki testlerin yarısı tam olarak bunu kolluyor.
"""
import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import recommend as REC


def _sec(crn, day, start=510, end=630, course="X"):
    return REC.Section(crn=crn, course=course, instructor=None, capacity=30,
                       enrolled=0,
                       meetings=(REC.Meeting(day, start, end, None, None, None),))


# ★ Slot kimliği BELİRLEYİCİ. Eskiden `abs(hash(course)) % 10_000` idi:
# Python dizgi hash'i her süreçte rastgele (PYTHONHASHSEED) ve binde bir
# olasılıkla iki ders aynı slota düşüyordu; Faz 81'in slot eşleştirmesi o
# zaman ikisini birlikte almıyor ve taban testi rastgele kırmızıya dönüyordu
# (PYTHONHASHSEED=1702 ile yeniden üretildi).
_SLOTLAR: dict[str, int] = {}


def _slot_no(course: str) -> int:
    return _SLOTLAR.setdefault(course, len(_SLOTLAR) + 1)


def _cand(course, role, credits, day, score=10.0, slot=0):
    return REC.Candidate(course=course, name=course, role=role, ects=credits * 2,
                         credits=credits, unlocks=0, tier=0, critical=False,
                         required=True, sections=[_sec(course, day, course=course)],
                         slot_id=slot or _slot_no(course), score=score)


# Anadal dersleri yüksek puanlı ve çakışmasız; ÇAP dersi düşük puanlı.
# Taban olmadan motor anadalı doldurup ÇAP'ı dışarıda bırakıyor.
def _havuz():
    return [
        _cand("GEO 101", "ANADAL", 4, 1, score=90),
        _cand("GEO 102", "ANADAL", 4, 2, score=85),
        _cand("GEO 103", "ANADAL", 4, 3, score=80),
        _cand("BLG 201", "CAP", 5, 4, score=10),
        _cand("BLG 202", "CAP", 5, 5, score=9),
    ]


def _cap_kredi(sched):
    return sched.credits_by_role().get("CAP", 0.0)


# ------------------------------------------------------------ ölçüm araçları
def test_credits_by_role_ayiriyor():
    s = REC.build_schedules(_havuz(), max_load=40, limit=1)[0]
    toplam = s.credits_by_role()
    assert set(toplam) <= {"ANADAL", "CAP"}
    assert sum(toplam.values()) == s.credits


def test_floor_gaps_eksigi_veriyor():
    s = REC.Schedule(picks=[REC.Pick(_cand("BLG 201", "CAP", 4, 1), _sec("1", 1))])
    assert s.floor_gaps({"CAP": 9}) == {"CAP": 5.0}
    assert s.floor_gaps({"CAP": 4}) == {}
    assert s.floor_gaps(None) == {}
    assert s.meets_floors({"CAP": 4}) is True


def test_rolu_hic_olmayan_programda_eksik_TAM_taban():
    """ÇAP dersi hiç yoksa eksik, tabanın tamamı olmalı — 0 değil."""
    s = REC.Schedule(picks=[REC.Pick(_cand("GEO 101", "ANADAL", 4, 1), _sec("1", 1))])
    assert s.floor_gaps({"CAP": 9}) == {"CAP": 9.0}


# ------------------------------------------------------------- sıralama
def test_taban_YOKKEN_motor_capi_disliyor():
    """★ Testin anlamlı olduğunun kanıtı: taban verilmezse eski davranış."""
    en_iyi = REC.build_schedules(_havuz(), max_load=12, limit=1)[0]
    assert _cap_kredi(en_iyi) < 9


def test_taban_VERILINCE_karsilayan_program_one_geciyor():
    """★ Asıl düzeltme."""
    en_iyi = REC.build_schedules(_havuz(), max_load=12, limit=1,
                                 floors={"CAP": 9})[0]
    assert _cap_kredi(en_iyi) >= 9


def test_karsilamayan_programlar_ELENMIYOR():
    """★ Taban indirilebiliyor; elemek çözülebilir durumu imkânsız gösterirdi."""
    hepsi = REC.build_schedules(_havuz(), max_load=12, limit=5, floors={"CAP": 9})
    assert len(hepsi) > 1
    assert any(s.floor_gaps({"CAP": 9}) for s in hepsi), "yalnız karşılayanlar kalmış"


def test_karsilayanlar_HEP_once():
    hepsi = REC.build_schedules(_havuz(), max_load=12, limit=5, floors={"CAP": 9})
    durum = [s.meets_floors({"CAP": 9}) for s in hepsi]
    assert durum == sorted(durum, reverse=True), durum


def test_hicbiri_karsilamiyorsa_program_yine_uretiliyor():
    """★ Ulaşılamaz taban motoru susturmamalı."""
    hepsi = REC.build_schedules(_havuz(), max_load=12, limit=3,
                                floors={"CAP": 99})
    assert hepsi, "motor sustu"
    assert all(s.floor_gaps({"CAP": 99}) for s in hepsi)


def test_taban_esitlikte_puani_bozmuyor():
    """Taban KARŞILANDIĞINDA sıralama eskisi gibi puana göre olmalı."""
    havuz = _havuz()
    a = REC.build_schedules(havuz, max_load=40, limit=3, floors={"CAP": 5})
    b = REC.build_schedules(havuz, max_load=40, limit=3)
    assert [s.courses() for s in a if s.meets_floors({"CAP": 5})][:1] \
        == [s.courses() for s in b if s.meets_floors({"CAP": 5})][:1]


# --------------------------------------------------------------- arayüz
from test_ui import _collect, dbs  # noqa: E402,F401


def test_json_taban_eksigini_tasiyor(dbs):
    """Her önerinin yanında taban eksiği JSON'da olmalı."""
    from itucap import config, ui as UI

    con, ucon, sid = dbs
    s = config.Settings(anadal_program="HTAE", cap_program="BLG",
                        second_kind="cap",
                        program_codes=["HTAE", "BLG"], cap_baslangic_yariyili=5)
    data = UI.collect(con, ucon, sid, s, 10, 20)
    assert data["schedules"], "öneri yok"
    for prog in data["schedules"]:
        assert "floorGaps" in prog and "creditsByRole" in prog
    # Bu fixture'da ÇAP kredisi 0; taban 9 → eksik raporlanmalı.
    assert any(g["role"] == "CAP" for g in data["schedules"][0]["floorGaps"])


def test_sablon_taban_uyarisini_kuruyor():
    """Arayüz eksiği YAZMAK zorunda: sessizce sunmak, kabul edilemez bir
    programı 'en iyi' diye göstermek olurdu."""
    import inspect

    from itucap import ui as UI

    kaynak = inspect.getsource(UI)
    for parca in ("floorGaps", "taban ✗", "tabanı karşılayan çakışmasız bir program"):
        assert parca in kaynak, parca
