"""Faz 119 — yol haritası senaryosunda dönem kredisi SERBEST giriliyor
(kullanıcı isteği 28.09.2026: "dönem başına en çok kredi kısmında istenilen
değerin girilmesine izin verebilir misin").

Eskiden açılır liste yalnız mevcut sınır, 21, 18, 15, 12'yi ve yalnız sınırın
ALTINDAKİLERİ sunuyordu: 17 ya da 24 kredi denenemiyordu. Artık 1–60 arası
tam ya da buçuklu her değer (sunucu aynı aralığı zaten doğruluyordu). Mevcut
sınırın üstündeki değer reddedilmiyor — "GNO'm yükselirse" sorusu meşru — ama
şerit yönetmeliğin istediği GNO'yu yazıyor (MADDE 17/2 basamakları).
"""
import pathlib
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import policy as POL
from itucap import ui as UI

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


def _js(ad):
    i = KAYNAK.index(f"function {ad}(")
    return KAYNAK[i:KAYNAK.index("\n}\n", i)]


def test_BASAMAK_yonetmelikten():
    """kurallar.toml: 22 (GNO 0), 25 (GNO 2.25), 40 (GNO 3.00)."""
    b = UI.yuk_basamagi(22)
    assert (b["minGpa"], b["max"], b["aboveMax"]) == (0.0, 22, False)
    assert UI.yuk_basamagi(17.5)["minGpa"] == 0.0
    assert UI.yuk_basamagi(22.5)["minGpa"] == 2.25
    assert UI.yuk_basamagi(25)["minGpa"] == 2.25
    b = UI.yuk_basamagi(26)
    assert (b["minGpa"], b["max"]) == (3.0, 40)
    b = UI.yuk_basamagi(41)
    assert b["aboveMax"] is True and b["max"] == 40 and b["minGpa"] is None


def test_BASAMAK_beyan_yoksa_UYDURULMUYOR(monkeypatch):
    monkeypatch.setattr(POL, "load_bands", lambda path=None: ([], {}))
    assert UI.yuk_basamagi(30) is None


def test_SENARYO_basamagi_donduruyor():
    k = KAYNAK[KAYNAK.index("def yol_senaryosu("):KAYNAK.index("def yuk_basamagi(")]
    assert '"loadBand": yuk_basamagi(g["max_load"])' in k
    g = KAYNAK[KAYNAK.index("def _harita_girdisi("):KAYNAK.index("def _senaryo_planlari(")]
    assert "if not 1 <= max_load <= 60:" in g, "sunucu aralığı arayüzle aynı olmalı"


def test_ARAYUZ_serbest_giris_ve_dogrulama():
    p = _js("yhSenaryoPaneli")
    assert '<input id="yhYuk" type="number"' in p and 'min="1" max="60" step="0.5"' in p
    assert "<select id=\"yhYuk\"" not in p, "sabit liste geri geldi"
    assert 'list="yhYukOneri"' in p and "<datalist id=\"yhYukOneri\">" in p
    r = KAYNAK[KAYNAK.index("function renderRoadmap("):]
    r = r[:r.index("\n}\n")]
    assert "v < 1 || v > 60 || Math.round(v * 2) !== v * 2" in r
    assert "1 ile 60 arasında, tam ya da buçuklu bir kredi değeri giriniz." in r
    s = _js("yukSarti")
    assert "if(!(sc.maxLoad > sinir)) return" in s
    assert "yönetmelikteki en yüksek sınır" in s and "GNO gerekir" in s


_CANLI = r'''
import sys, os
sys.path.insert(0, os.environ["ITUCAP_SRC"]); sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import vitrin
adres, h = vitrin.ac()
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    for ad, boyut in (("M", {"width": 1400, "height": 1000}), ("T", {"width": 390, "height": 844})):
        pg = b.new_page(viewport=boyut)
        hatalar = []
        pg.on("pageerror", lambda e: hatalar.append(str(e)))
        pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(1200)
        pg.evaluate("() => gorunumAc('roadmapSection')"); pg.wait_for_timeout(300)
        serit = "() => (document.querySelector('.yhseritsenaryo')||{innerText:''}).innerText.replace(/\\s+/g,' ')"
        durum = "() => document.querySelector('#yhSenaryoDurum').textContent"
        print(ad + "SINIR:" + str(pg.evaluate("() => DATA.roadmap.maxLoad")))
        pg.fill("#yhYuk", "17.5"); pg.press("#yhYuk", "Enter"); pg.wait_for_timeout(1500)
        print(ad + "S175:" + pg.evaluate(serit))
        pg.fill("#yhYuk", "30"); pg.press("#yhYuk", "Enter"); pg.wait_for_timeout(1500)
        print(ad + "S30:" + pg.evaluate(serit))
        pg.fill("#yhYuk", "45"); pg.press("#yhYuk", "Enter"); pg.wait_for_timeout(1500)
        print(ad + "S45:" + pg.evaluate(serit))
        pg.fill("#yhYuk", "0"); pg.press("#yhYuk", "Enter"); pg.wait_for_timeout(400)
        print(ad + "S0:" + pg.evaluate(serit) + "|" + pg.evaluate(durum) + "|"
              + str(pg.evaluate("() => document.querySelector('#yhYuk').getAttribute('aria-invalid')")))
        print(ad + "TASMA:" + str(pg.evaluate("() => document.documentElement.scrollWidth <= innerWidth")))
        print(ad + "HATA:" + str(len(hatalar)) + " " + " | ".join(hatalar)[:300])
        pg.close()
    b.close()
h.shutdown()
'''


def test_UCTAN_UCA_vitrin(tmp_path, monkeypatch):
    try:
        import playwright  # noqa: F401
    except ImportError:
        pytest.skip("playwright yok")
    kok = Path(UI.__file__).resolve().parents[2]
    monkeypatch.setenv("ITUCAP_SRC", str(kok / "src"))
    monkeypatch.setenv("ITUCAP_TOOLS", str(kok / "tools"))
    betik = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, dir=str(tmp_path))
    betik.write(_CANLI); betik.close()
    r = subprocess.run([sys.executable, betik.name], capture_output=True, text=True,
                       timeout=300, cwd=str(tmp_path))
    if r.returncode != 0:
        if "Executable doesn't exist" in r.stderr or "BrowserType.launch" in r.stderr:
            pytest.skip("tarayıcı başlatılamadı")
        pytest.fail(r.stderr[-2000:])
    c = dict(s.split(":", 1) for s in r.stdout.strip().splitlines()
             if ":" in s and s.split(":", 1)[0].isupper())
    for ad in "MT":
        assert c[ad + "HATA"].startswith("0"), c[ad + "HATA"]
        assert c[ad + "SINIR"] == "25"          # vitrin: GNO'ya göre otomatik sınır
        # Eski listede olmayan değer: 17,5.
        assert "dönem başına en çok 17.5 kredi" in c[ad + "S175"], c[ad + "S175"]
        assert "üzerindedir" not in c[ad + "S175"]
        # Mevcut sınırın üstü kabul ediliyor, şart yazılıyor.
        assert "dönem başına en çok 30 kredi" in c[ad + "S30"], c[ad + "S30"]
        assert ("mevcut sınırınızın, 25 kredinin, üzerindedir; yönetmeliğe göre en az "
                "3.00 GNO gerekir") in c[ad + "S30"], c[ad + "S30"]
        assert "en yüksek sınır 40 kredidir" in c[ad + "S45"], c[ad + "S45"]
        # Geçersiz değer: senaryo DEĞİŞMİYOR, sebep yazıyor.
        seritte, durum, gecersiz = c[ad + "S0"].split("|")
        assert "45 kredi" in seritte, "geçersiz değer senaryoyu değiştirdi"
        assert durum.startswith("1 ile 60 arasında") and gecersiz == "true"
        assert c[ad + "TASMA"] == "True", "telefonda yatay taşma"
