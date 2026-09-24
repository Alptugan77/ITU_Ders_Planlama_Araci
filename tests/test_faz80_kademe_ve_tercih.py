"""Faz 80 — kademeler bölümünün tasarımı ve tercihler penceresindeki çakışma.

Kullanıcı 24.09.2026: *"kademeler kısmının tasarımını iyileştirir misin bir
de tercihler kısmında üst üste gelen öğeler var onlara bakar mısın"*.

* Tercihler: iki onay kutusu 190px'lik ızgara sütunlarındaydı ve `.tickbox`
  satır kaydırmıyor; "Aynı gün kampüs değiştirmek istemiyorum" yandaki
  kutunun üstüne taşıyordu (1400px'te ölçüldü).
* Kademeler: kutuda yalnız kod; tamamlanmış kademe tam boy; başlık zamanı
  söylemiyordu; 390px'te bütün çizgiler sağ olukta yumak oluyordu.
"""
import json
import pathlib
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import ui as UI

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


def test_STATIK():
    assert '<h2 style="margin-bottom:4px">Tercihler</h2>' in KAYNAK
    assert '<div class="tickliste" style="margin-top:14px">' in KAYNAK
    assert ".tickliste .tickbox{white-space:normal;" in KAYNAK
    assert "const kademeBitti = (t) => t.courses.length && t.courses.every(c => c.status === \"DONE\");" in KAYNAK
    # Dar ekranda çizgiler dinlenmede gizli, odakta yalnız zincir.
    assert ".tierlinks path{display:none}" in KAYNAK
    assert ".tierstage.focus .tierlinks path.line.on{display:inline}" in KAYNAK


_CANLI = r'''
import sys, os, json
sys.path.insert(0, os.environ["ITUCAP_SRC"]); sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import vitrin
adres, h = vitrin.ac()
from playwright.sync_api import sync_playwright
CAKISMA = """() => {
  const a = document.querySelector('#fKampus').closest('label').getBoundingClientRect();
  const b = document.querySelector('#fOnline').closest('label').getBoundingClientRect();
  const ox = Math.min(a.right, b.right) - Math.max(a.left, b.left);
  const oy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
  const tasma = document.querySelector('#fKampus').closest('label').scrollWidth
              > document.querySelector('#fKampus').closest('label').clientWidth + 1;
  return {cakisma: ox > 0 && oy > 0, tasma}; }"""
with sync_playwright() as p:
    b = p.chromium.launch()
    for W in (1400, 390):
        pg = b.new_page(viewport={"width": W, "height": 1000})
        hatalar = []
        pg.on("pageerror", lambda e: hatalar.append(str(e)))
        pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(800)
        pg.evaluate("() => tercihDialog()"); pg.wait_for_timeout(300)
        print(f"TERCIH{W}:" + json.dumps(pg.evaluate(CAKISMA)))
        print(f"BASLIK{W}:" + pg.evaluate("() => document.querySelector('#setup h2').textContent.trim()"))
        pg.evaluate("() => document.querySelector('#setup').close()")
        pg.evaluate("() => gorunumAc('tierSection')"); pg.wait_for_timeout(500)
        print(f"BITTI{W}:" + json.dumps(pg.evaluate("() => [...document.querySelectorAll('#tierStage0 .tier.bitti')].map(e => e.textContent.replace(/\\s+/g,' ').trim())"), ensure_ascii=False))
        print(f"DONEM{W}:" + json.dumps(pg.evaluate("() => [...document.querySelectorAll('#tierStage0 .tierdonem')].map(e => e.textContent.trim())"), ensure_ascii=False))
        print(f"AD{W}:" + json.dumps(pg.evaluate("() => (document.querySelector('#tierStage0 li[data-c=\"BLG 223E\"] .tad')||{}).textContent")))
        print(f"KUTUDONE{W}:" + str(pg.evaluate("() => document.querySelectorAll('#tierStage0 li[data-s=\"DONE\"]').length")))
        cizgi = "() => [...document.querySelectorAll('#tierStage0 .tierlinks path.line')].filter(p => getComputedStyle(p).display !== 'none').length"
        print(f"CIZGI{W}:" + str(pg.evaluate(cizgi)))
        pg.locator('#tierStage0 li[data-c="BLG 223E"]').click(); pg.wait_for_timeout(200)
        print(f"ODAKCIZGI{W}:" + str(pg.evaluate(cizgi)))
        print(f"TASMA{W}:" + str(pg.evaluate("() => document.documentElement.scrollWidth > innerWidth + 1")))
        print(f"HATA{W}:" + str(len(hatalar)) + " " + " | ".join(hatalar)[:300])
        pg.close()
    pg = b.new_page()
    pg.goto(adres, wait_until="networkidle"); pg.wait_for_timeout(500)
    print("ILERI:" + json.dumps(pg.evaluate("() => [donemIleri('202710', 0), donemIleri('202710', 1), donemIleri('202710', 2), donemIleri('202720', 1), donemIleri('bozuk', 1), donemIleri('202730', 1)]")))
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
             if ":" in s and s.split(":", 1)[0].isalnum() and s.split(":", 1)[0].isupper())
    for W in (1400, 390):
        assert c[f"HATA{W}"].startswith("0"), c[f"HATA{W}"]
        assert json.loads(c[f"TERCIH{W}"]) == {"cakisma": False, "tasma": False}, c[f"TERCIH{W}"]
        assert c[f"BASLIK{W}"] == "Tercihler"
        # Vitrin: kademe 0 (BLG 102E, BLG 231E) tamamlanmış → tek satır.
        assert json.loads(c[f"BITTI{W}"]) == ["Kademe 0 · tamamlandı BLG 102E · BLG 231E"], c[f"BITTI{W}"]
        assert c[f"KUTUDONE{W}"] == "0"
        assert json.loads(c[f"DONEM{W}"]) == ["bu dönem", "en erken 2026-2027 Bahar",
                                             "en erken 2027-2028 Güz"], c[f"DONEM{W}"]
        assert json.loads(c[f"AD{W}"]) == "Data Structures"
        assert c[f"TASMA{W}"] == "False"
    # Masaüstünde çizgiler dinlenmede görünür; telefonda gizli, odakta yalnız zincir.
    assert int(c["CIZGI1400"]) > 0
    assert c["CIZGI390"] == "0"
    assert 0 < int(c["ODAKCIZGI390"]) < int(c["CIZGI1400"])
    assert json.loads(c["ILERI"]) == ["2026-2027 Güz", "2026-2027 Bahar", "2027-2028 Güz",
                                      "2027-2028 Güz", "", ""]
