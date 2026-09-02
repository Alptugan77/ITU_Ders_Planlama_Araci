"""Faz 37 — tercih karşılanamıyorsa NE BIRAKMALI (docs/fikirler.md §3.5).

Faz 27 ölçümü: "Pzt + Cuma boş" istendiğinde motor ikisini birden sağlayamıyor
ve −10 farkla en yakınını sunuyor. Doğru davranış ama kullanıcı çıkışın nerede
olduğunu göremiyordu — "tercihine uymuyor" diyoruz, "şunu çıkarırsan uyar"
demiyorduk.

★ Öneri TEK ADIMLIK: iki ders birden çıkarmak programı baştan kurmak olurdu ve
o işi zaten motor yapıyor (öbür öneriler).
"""
import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import recommend as REC                            # noqa: E402


def _sec(crn, gun, baslangic, *, hoca=None):
    m = REC.Meeting(gun, baslangic, baslangic + 90, None, "X", None)
    return REC.Section(crn, "X 101", hoca, 30, 0, (m,), "Physical (Face to face)")


def _cand(code, sections, **kw):
    v = dict(course=code, name="", role="ANADAL", ects=5.0, credits=3.0,
             unlocks=0, tier=0, critical=False, required=False,
             sections=list(sections))
    v.update(kw)
    return REC.Candidate(**v)


def _prog(cands, prefs):
    REC.score_all(cands)
    return REC.Schedule([REC.Pick(c, c.sections[0]) for c in cands], prefs)


def test_tek_ders_cikarinca_gun_BOSALIYOR():
    cuma = _cand("ITB 037E", [_sec("1", 5, 780)])       # Cuma
    sali = _cand("MAT 103E", [_sec("2", 2, 780)])
    s = _prog([cuma, sali], REC.Preferences(bos_gunler=(5,)))
    care = s.pref_relief()
    assert [c["course"] for c in care] == ["ITB 037E"]
    assert "boş" in care[0]["gains"][0]
    assert care[0]["credits"] == 3.0


def test_iki_ders_ayni_gundeyse_TEK_ADIM_yetmiyor():
    """İkisini birden çıkarmayı önermiyoruz — o, programı baştan kurmak."""
    a = _cand("A 101", [_sec("1", 5, 780)])
    b = _cand("B 101", [_sec("2", 5, 600)])
    s = _prog([a, b], REC.Preferences(bos_gunler=(5,)))
    assert s.pref_relief() == []


def test_erken_ders_icin_de_calisiyor():
    erken = _cand("A 101", [_sec("1", 1, 510)])          # 08:30
    gec = _cand("B 101", [_sec("2", 1, 780)])
    s = _prog([erken, gec], REC.Preferences(en_erken=630))
    assert [c["course"] for c in s.pref_relief()] == ["A 101"]


def test_ISTENEN_hoca_kaybi_care_SAYILMIYOR():
    """"İstediğin hoca" sayısını sıfıra indirmek kazanç değil, kayıp."""
    a = _cand("A 101", [_sec("1", 1, 780, hoca="Feza Buzluca")])
    b = _cand("B 101", [_sec("2", 2, 780)])
    s = _prog([a, b], REC.Preferences(istenen_hocalar=("buzluca",)))
    assert s.pref_relief() == []


def test_istenmeyen_hoca_icin_care_VAR():
    a = _cand("A 101", [_sec("1", 1, 780, hoca="Ali Veli")])
    b = _cand("B 101", [_sec("2", 2, 780)])
    s = _prog([a, b], REC.Preferences(istenmeyen_hocalar=("ali veli",)))
    assert [c["course"] for c in s.pref_relief()] == ["A 101"]


def test_ZORUNLU_ders_en_sona_konuyor():
    """En ucuz hamle önde olsun: zorunlu dersi çıkarmayı ilk sırada önerme."""
    # İki AYRI tercih, her birini tek bir ders ihlal ediyor:
    #   Z 101 → Pazartesi 08:30 (erken)     S 101 → Cuma (boş istenen gün)
    zor = _cand("Z 101", [_sec("1", 1, 510)], required=True, credits=1.0)
    ser = _cand("S 101", [_sec("2", 5, 900)], required=False, credits=9.0)
    s = _prog([zor, ser], REC.Preferences(en_erken=630, bos_gunler=(5,)))
    care = s.pref_relief()
    assert [c["course"] for c in care] == ["S 101", "Z 101"]
    assert care[-1]["required"] is True


def test_tercih_yoksa_care_de_YOK():
    a = _cand("A 101", [_sec("1", 1, 780)])
    b = _cand("B 101", [_sec("2", 2, 780)])
    assert _prog([a, b], None).pref_relief() == []
    assert _prog([a, b], REC.Preferences()).pref_relief() == []


def test_tek_derslik_programda_care_ONERILMIYOR():
    """Tek dersi çıkarmak 'program' bırakmaz — öneri değil, iptal olurdu."""
    a = _cand("A 101", [_sec("1", 5, 780)])
    assert _prog([a], REC.Preferences(bos_gunler=(5,))).pref_relief() == []


def test_puan_ile_care_AYNI_sayimi_kullaniyor():
    """İkisi ayrı sayarsa arayüz 'Cuma boşalıyor' der, puan değişmez."""
    cuma = _cand("A 101", [_sec("1", 5, 780)])
    sali = _cand("B 101", [_sec("2", 2, 780)])
    s = _prog([cuma, sali], REC.Preferences(bos_gunler=(5,)))
    assert s.pref_delta < 0
    kalan = REC.Schedule([p for p in s.picks if p.candidate.course != "A 101"],
                         s.prefs)
    assert kalan.pref_delta == 0.0        # care gerçekten tercihi sağlıyor
