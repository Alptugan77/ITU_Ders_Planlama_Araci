"""Aracın adı — İTÜ DEPAR (kullanıcı kararı 27.08.2026).

★ Kısaltma UYDURMA DEĞİL, açılımın kendisi:

        DErs Planlama ARacı  →  DEPAR

Bu dosya iki şeyi kolluyor:

1. **Vurgu türetiliyor, elle boyanmıyor.** Açılımdaki hangi harflerin
   kısaltmaya gittiği `acilim_html()` tarafından hesaplanıyor. Elle
   `<b>DE</b>rs…` yazılsaydı ad değiştiğinde vurgu sessizce yanlış kalırdı —
   ve ekranda DOĞRU görünürdü.
2. **Ad tek kaynakta.** Sekme başlığı, sayfa başlığı ve açılım aynı
   sabitlerden geliyor; üçü ayrı yazılsaydı biri değişip öbürü kalırdı.
"""
import re

import pytest

from itucap import ui as UI


def _duz(h: str) -> str:
    return re.sub(r"<[^>]+>", "", h)


# ============================================== 1. türetme
def test_acilim_kisaltmayi_ceviriyor():
    assert UI.acilim_html() == "<b>De</b>rs <b>P</b>lanlama <b>Ar</b>acı"


def test_vurgulu_harfler_KISALTMAYI_yaziyor():
    """Asıl iddia bu: koyu harfler yan yana gelince kısaltma çıkmalı."""
    vurgulu = "".join(re.findall(r"<b>([^<]*)</b>", UI.acilim_html()))
    assert UI._tr_upper(vurgulu) == UI.AD_KISA


def test_vurgu_metni_DEGISTIRMIYOR():
    """⚠️ Etiketler kalkınca açılımın kendisi aynen kalmalı — vurgu bir
    sunum tercihi, metnin kendisi değil."""
    assert _duz(UI.acilim_html()) == UI.AD_ACILIM


def test_uymayan_kisaltma_SESSIZCE_gecmiyor():
    """★ Sessizce vurgusuz metin döndürmek, "kısaltma açılımdan geliyor"
    iddiasını ekranda yalanlamadan ölü bırakırdı."""
    with pytest.raises(ValueError) as e:
        UI.acilim_html("Ders Planlama Aracı", "DEPARX")
    assert "X" in str(e.value)


def test_baska_ad_ciftleri_de_calisiyor():
    assert UI.acilim_html("Ders Seçim Aracı", "DESA") == \
        "<b>De</b>rs <b>S</b>eçim <b>A</b>racı"
    assert UI.acilim_html("Kredi Planı", "KP") == "<b>K</b>redi <b>P</b>lanı"


def test_turkce_buyuk_harf():
    """i→İ, ı→I. `str.upper()` tek başına 'ı'yı 'I' yapıyor ama 'i'yi 'I'
    yapıp Türkçe'yi bozuyor."""
    assert UI._tr_upper("iı") == "İI"
    assert UI._tr_upper("Aracı") == "ARACI"


def test_kacis_yapiliyor():
    """Açılım şablona HAM giriyor; kaçış olmasaydı `<` enjeksiyon olurdu."""
    cikti = UI.acilim_html("D<ers P&lanı", "DP")
    assert "&lt;" in cikti and "&amp;" in cikti
    assert "<b>D</b>" in cikti


# ============================================== 2. tek kaynak
def test_ad_sabitleri_tutarli():
    assert UI.AD_TAM == f"{UI.AD_KURUM} {UI.AD_KISA}"
    assert UI.AD_TAM == "İTÜ DEPAR"


def test_sablonda_yer_tutucu_var():
    t = UI._TEMPLATE
    for anahtar in ("__AD_TAM__", "__AD_KURUM__", "__AD_KISA__",
                    "__AD_ACILIM__", "__AD_ACILIM_DUZ__"):
        assert anahtar in t, anahtar


def test_ADI_DEGISTIRINCE_SAYFA_DA_DEGISIYOR(monkeypatch):
    """★★ "Tek kaynak" iddiasının gerçek sınavı: sabitleri değiştir, sayfa
    peşinden gelsin. Şablona elle yazılmış bir ad kalsaydı bu test onu
    yakalardı — sayfada eski ad görünürdü."""
    monkeypatch.setattr(UI, "AD_KISA", "DESA")
    monkeypatch.setattr(UI, "AD_KURUM", "ODTÜ")
    monkeypatch.setattr(UI, "AD_TAM", "ODTÜ DESA")
    monkeypatch.setattr(UI, "AD_ACILIM", "Ders Seçim Aracı")
    html = UI.render({"schedules": [], "candidates": []})
    assert "<title>ODTÜ DESA — Ders Seçim Aracı</title>" in html
    assert '<span class="kurum">ODTÜ</span> DESA' in html
    assert "<b>De</b>rs <b>S</b>eçim <b>A</b>racı" in html
    assert "DEPAR" not in html.split("<style>")[0] + html.split("</style>")[-1]


def test_JS_basligi_EZMIYOR():
    """Şablon başlığı yazıyorsa JS'in de yazması ikinci bir kaynak olurdu."""
    src = open(UI.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
    assert '$("#doctitle").textContent =' not in src


# ============================================== 3. sayfada gerçekten var
def test_sayfada_ad_ve_acilim_var():
    from itucap import config, db, student as S
    import tempfile
    import pathlib

    with tempfile.TemporaryDirectory() as d:
        yol = pathlib.Path(d)
        con = db.connect(yol / "r.sqlite3", "schema.sql")
        ucon = db.connect(yol / "u.sqlite3", "schema_user.sql")
        sid = S.ensure_student(ucon)
        data = UI.collect(con, ucon, sid, config.Settings(anadal_program="HTAE"),
                          None, None)
    html = UI.render(data)
    assert "<title>İTÜ DEPAR — Ders Planlama Aracı</title>" in html
    assert '<h1 id="doctitle"><span class="kurum">İTÜ</span> DEPAR</h1>' in html
    assert f'<div class="acilim">{UI.acilim_html()}</div>' in html


def test_acilim_bicimi_TANIMLI():
    """Vurgulu harfler görsel olarak ayrışmalı; yoksa kısaltmanın nereden
    geldiği görünmez ve açılım süs olurdu."""
    t = UI._TEMPLATE
    assert ".acilim{" in t and ".acilim b{" in t
    # Büyük harf CSS'te — metinde değil (kopyalama ve ekran okuyucu için).
    acilim_css = t.split(".acilim{")[1].split("}")[0]
    assert "text-transform:uppercase" in acilim_css


def test_takvim_adi_ASCII_ve_TURETILMIS():
    """⚠️ ICS `PRODID` ASCII olmak zorunda; "İTÜ" oraya olduğu gibi yazılamaz.
    Katlama tek yerde — elle yazılsaydı ad değişince biri kalırdı."""
    assert UI.ad_ascii() == "ITU DEPAR Ders Planlama Araci"
    assert UI.ad_ascii().isascii()


def test_takvim_adi_da_AD_DEGISINCE_degisiyor(monkeypatch):
    monkeypatch.setattr(UI, "AD_TAM", "ODTÜ DESA")
    monkeypatch.setattr(UI, "AD_ACILIM", "Ders Seçim Aracı")
    assert UI.ad_ascii() == "ODTU DESA Ders Secim Araci"
