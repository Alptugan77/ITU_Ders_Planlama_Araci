"""Faz 129 — kullanılabilirlik: telefonda kısa üst çubuk; "taban
karşılanamıyor" mesajının SEBEBİ ölçülüyor.

Kullanıcı (29.09.2026): *"ekleyebileceğin işe yarar şeyler varsa ekler
misin lütfen kullanılabilirliğini de arttır"*. Kullanıcının verisiyle
gezildi (HTAE + BLG ÇAP, 5. dönem):

* Telefonda (390 px) içerik 240 px'ten sonra başlıyordu; ad, Kılavuz/Tema,
  dönem satırı, durum satırı ve "tazele" ayrı satırlardaydı.
* Üç önerinin üçü "TABAN ✗"; mesaj "arz, saat çakışması veya önşart" diye
  üç ihtimal sayıyordu. Oysa bu dönem alınabilecek BÜTÜN ÇAP dersleri
  7,5 kredi (BLG 223E 3,5 + BLG 212E 3 + BLG 351E 1) — taban 9.
"""
import json
import pathlib
import shutil
import subprocess

import pytest

from itucap import ui as UI

K = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


def _js(ad):
    i = K.index(f"function {ad}(")
    return K[i:K.index("\n}\n", i)]


def test_UST_CUBUK_telefonda_kisa():
    i = K.index("Faz 129 — telefonda üst çubuk")
    css = K[i:K.index(".ray a[data-alt]", i)]
    # Düğmeler adla aynı satırda, sağda; ad sütunu esnek.
    assert "header .basdugme{order:2;margin-left:auto;display:flex" in css
    assert "header .masthead>div:first-child{flex:1 1 0}" in css
    # Durum satırı yalnız program görünümünde.
    assert ':root:not([data-gorunum="schedSection"]) body:not(.kurulum) header #subtitle{display:none}' in css
    # Veri yaşı ile "tazele" aynı satır.
    assert "header .veriyasi{flex-wrap:nowrap}" in css
    # Dokunma hedefi küçülmedi.
    assert css.count("min-height:44px") == 2
    # Telefon kuralı: masaüstünü etkilemiyor.
    medya = K.rindex("@media", 0, i)
    assert "max-width:700px" in K[medya:medya + 40]


def _arz(adaylar):
    node = shutil.which("node")
    if not node:
        pytest.skip("node yok")
    betik = (f"const DATA = {{}}; function M(){{ return {{candidates: {json.dumps(adaylar)}}}; }}\n"
             + _js("tabanArzi") + "\n}\nconsole.log(JSON.stringify(tabanArzi()));")
    r = subprocess.run([node, "-e", betik], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_ARZ_yalniz_ikinci_anadal_ve_yuva_basina_bir():
    a = _arz([
        {"course": "BLG 223E", "credits": 3.5, "role": "CAP", "slotId": "s1"},
        {"course": "BLG 212E", "credits": 3, "role": "CAP"},
        {"course": "BLG 351E", "credits": 1, "role": "CAP"},
        {"course": "BLG 223",  "credits": 3.5, "role": "CAP", "slotId": "s1"},   # aynı yuvanın denki
        {"course": "GEO 307E", "credits": 3, "role": "ANADAL"},
    ])
    assert a["kredi"] == 7.5
    assert [d["course"] for d in a["dersler"]] == ["BLG 223E", "BLG 212E", "BLG 351E"]


def test_ARZ_bos_ve_kredisiz():
    assert _arz([]) == {"dersler": [], "kredi": 0}
    assert _arz([{"course": "X", "role": "CAP"}])["kredi"] == 0


def test_MESAJ_arz_yetmiyorsa_sebep_arz():
    r = _js("renderFloor")
    assert "const arzYetmiyor = arz.kredi + 1e-9 < F.min;" in r
    i = r.index("${arzYetmiyor")
    evet, hayir = r[i:].split("\n      : `", 1)
    assert "derslerin tamamı" in evet and "hiçbir program" in evet
    assert "tabanı karşılayamaz" in evet and "Alınamayan dersler" in evet
    assert "saat çakışması" not in evet, "arz yetmiyorken çakışma suçlanmamalı"
    assert "sebep saat çakışması veya yük" in hayir
    # Eski üç ihtimalli cümle geri gelmesin.
    assert "arzı, saat çakışması veya önşart" not in K


def test_DANISMAN_dilekcesinde_arz():
    d = _js("danismanSorulari")
    assert "const arz = tabanArzi();" in d
    assert "arz.kredi + 1e-9 < F.min" in d
    assert "alınabilecek derslerin tamamı ${arz.kredi} krediden" in d
