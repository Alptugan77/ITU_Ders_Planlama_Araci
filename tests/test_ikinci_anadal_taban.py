"""Faz 13 — ikinci anadaldan asgari yarıyıl kredisi.

ÇAP/Yandal Yönergesi: 3. yarıyılda başlayan her yarıyıl en az 6, 5. yarıyılda
başlayan en az 9 kredilik dersi **ikinci anadaldan** almak zorunda. Talep +
ÇAP Koordinatörü uygun görüşü + FYK kararı ile taban yarıya kadar düşürülebilir.

Bu dosyanın kilitlediği üç şey:

1. Bu kural MADDE 17'deki banttan **ayrı**. ÇAP öğrencisi toplam alt sınırdan
   muaf ama bu tabandan değil. İkisini karıştırmak öğrenciyi ÇAP'tan ilişik
   kesilmeye götürebilirdi.
2. İndirim **otomatik değil**. Yönerge "düşürülebilir" diyor.
3. Beyan yoksa taban **iddia edilmiyor**.
"""
import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import config, policy as POL

KURALLAR = """
[[ikinci_anadal_taban]]
baslangic_yariyili = 3
min_kredi = 6
dogrulandi = true
kaynak = "Yönerge"

[[ikinci_anadal_taban]]
baslangic_yariyili = 5
min_kredi = 9
dogrulandi = true
kaynak = "Yönerge"

[ikinci_anadal_taban_indirim]
oran = 0.5
kosullar = ["öğrencinin talebi", "ÇAP Koordinatörünün uygun görüşü",
            "Fakülte Yönetim Kurulu Kararı"]
son_tarih = "dersten tümüyle çekilme tarihi"
otomatik = false
dogrulandi = true
kaynak = "Yönerge"
"""

# MADDE 17 bandı — ÇAP öğrencisini alt sınırdan MUAF tutan kural.
BANT = """
[kredi_yuku_bant]
min_kredi = 13
max_kredi = 22
muaf = ["birinci_yariyil", "cap", "son_sinif"]
dogrulandi = true

[[kredi_yuku]]
ad = "genel"
max_kredi = 22
min_gno = 0.0
"""


def _rules(tmp_path, text):
    p = tmp_path / "kurallar.toml"
    p.write_text(text, encoding="utf-8")
    return p


# ------------------------------------------------------------ basamaklar
@pytest.mark.parametrize("start,expected", [
    (3, 6.0),
    (5, 9.0),
])
def test_declared_tiers(tmp_path, start, expected):
    f = POL.second_floor(start, _rules(tmp_path, KURALLAR))
    assert f is not None and f.minimum == expected


def test_between_tiers_rounds_down(tmp_path):
    """★ 4. yarıyılda başlayan → 3'ün tabanı (6), 5'inki (9) DEĞİL.

    Yukarı yuvarlamak yönergenin söylemediği bir yükümlülük yaratırdı:
    öğrenciye almak zorunda olmadığı 3 krediyi aldırmak."""
    p = _rules(tmp_path, KURALLAR)
    assert POL.second_floor(4, p).minimum == 6.0
    assert POL.second_floor(6, p).minimum == 9.0
    assert POL.second_floor(8, p).minimum == 9.0


def test_below_the_lowest_tier_claims_nothing(tmp_path):
    """1.–2. yarıyılda başlamak yönergede yok; uydurmuyoruz."""
    assert POL.second_floor(2, _rules(tmp_path, KURALLAR)) is None


def test_undeclared_start_term_claims_nothing(tmp_path):
    """★ Beyan yoksa (0) taban İDDİA EDİLMEZ.

    Yanlış bir taban iki yönde de zarar: uydurma bir kuralla "az aldın"
    demek, ya da gerçek tabanı atlayıp ilişik kesilmesine götürmek."""
    assert POL.second_floor(0, _rules(tmp_path, KURALLAR)) is None


def test_missing_declaration_file(tmp_path):
    assert POL.second_floor(5, tmp_path / "yok.toml") is None


# ---------------------------------------------------------------- karşılama
@pytest.mark.parametrize("credits,ok", [
    (8.5, False),
    (9.0, True),        # tam taban — dahil
    (12.0, True),
])
def test_satisfied_by(tmp_path, credits, ok):
    f = POL.second_floor(5, _rules(tmp_path, KURALLAR))
    assert f.satisfied_by(credits) is ok


# ------------------------------------------------------------------ indirim
def test_relief_is_not_automatic(tmp_path):
    """★ Yönerge "düşürülebilir" diyor, "düşürülür" demiyor.

    Tabanı kendiliğinden yarıya çekmek, alınmamış bir FYK kararını alınmış
    varsaymak olurdu — öğrenci tabanı karşıladığını sanıp talebi hiç
    yapmayabilirdi."""
    f = POL.second_floor(5, _rules(tmp_path, KURALLAR))
    assert f.relief is not None
    assert f.relief.automatic is False
    # Taban indirilmemiş hâliyle duruyor:
    assert f.minimum == 9.0
    # İndirim ONAYLANIRSA ne olacağı ayrıca hesaplanıyor:
    assert f.relieved_minimum == 4.5


def test_relief_carries_its_conditions_and_deadline(tmp_path):
    """Şartları yazmadan "yarıya inebilir" demek eksik bilgi olurdu —
    öğrenci talebi zamanında yapmazsa hak kullanılamıyor."""
    f = POL.second_floor(3, _rules(tmp_path, KURALLAR))
    assert len(f.relief.conditions) == 3
    assert "Fakülte Yönetim Kurulu Kararı" in f.relief.conditions
    assert "çekilme" in f.relief.deadline
    assert f.relieved_minimum == 3.0


def test_relief_absent_when_undeclared(tmp_path):
    only_tiers = KURALLAR.split("[ikinci_anadal_taban_indirim]")[0]
    f = POL.second_floor(5, _rules(tmp_path, only_tiers))
    assert f.relief is None
    assert f.relieved_minimum is None


# --------------------------------- MADDE 17 ile KARIŞTIRILMAMASI (en kritik)
def test_floor_is_independent_of_the_madde_17_exemption(tmp_path):
    """★ Bu testin varlık sebebi: iki kuralı karıştırmak.

    MADDE 17/1 ÇAP öğrencisini TOPLAM alt sınırdan muaf tutuyor. Yönergenin
    bu maddesi ise İKİNCİ ANADALDAN bir taban koyuyor. "ÇAP muaf" diye
    tabanı da atlamak, öğrenciyi karşılamadığı bir şartla ÇAP'tan ilişik
    kesilmeye götürebilirdi.
    """
    p = _rules(tmp_path, KURALLAR + BANT)
    # MADDE 17: ÇAP öğrencisinin TOPLAM alt sınırı yok.
    limit = POL.load_limit(3.0, second_kind="cap", path=p)
    assert limit.exempt_from_minimum is True
    assert limit.minimum == 0.0
    # Ama ikinci anadal TABANI duruyor ve bağımsız:
    floor = POL.second_floor(5, p)
    assert floor is not None and floor.minimum == 9.0


def test_project_config_declares_both_tiers():
    """Projenin kendi kuralları: iki basamak da yerinde ve doğrulanmış."""
    p = config.ROOT / "config" / "kurallar.toml"
    assert POL.second_floor(3, p).minimum == 6.0
    assert POL.second_floor(5, p).minimum == 9.0
    for t in (3, 5):
        f = POL.second_floor(t, p)
        assert f.verified and f.source


def test_project_config_relief_is_not_automatic():
    """⚠️ Bu bayrak true'ya çekilirse motor alınmamış bir kararı varsayar."""
    f = POL.second_floor(5, config.ROOT / "config" / "kurallar.toml")
    assert f.relief is not None and f.relief.automatic is False
    assert f.relieved_minimum == 4.5
