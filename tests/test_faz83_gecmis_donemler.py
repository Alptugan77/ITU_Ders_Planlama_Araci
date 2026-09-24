"""Faz 83 — dersin geçmişte açıldığı dönemler (not dağılımından), belirsizliğiyle.

Kullanıcı 24.09.2026: *"bir de geçmişteki not dağılımlarından derslerin hangi
dönemlerde açıldığı ile ilgili küçük bir bilgi geç doğruluğunun belirsiz
olduğunu belirterek"*.
"""
import json
import pathlib
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import ui as UI
from itucap import yolharitasi as YH

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


def test_GECMIS_DONEMLERI():
    g = {"terms": {"202610": 80, "202620": 3, "202630": 0, "202510": 120,
                   "202410": 5, "202420": 7, "202310": 9, "202320": 1}}
    d = YH.gecmis_donemleri(g)
    # Yeniden eskiye, öğrencisi 0 olan dönem yok, en çok 6.
    assert [x["term"] for x in d] == ["202620", "202610", "202510", "202420", "202410", "202320"]
    assert d[0] == {"term": "202620", "label": "2025-2026 Bahar", "n": 3}
    assert YH.gecmis_donemleri(None) == [] and YH.gecmis_donemleri({"terms": {}}) == []


def test_BELIRSIZLIK_YAZIYOR():
    for yer in ("Doğruluğu belirsizdir; dersin ileride",       # pencere + kart üstü
                "Doğruluğu belirsizdir: dersin ileride"):       # varsayımlar
        assert yer in KAYNAK or yer in (pathlib.Path(YH.__file__).read_text(encoding="utf-8")), yer


_CANLI = r'''
import sys, os, json
sys.path.insert(0, os.environ["ITUCAP_SRC"]); sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import vitrin
adres, h = vitrin.ac()
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 1000})
    hatalar = []
    pg.on("pageerror", lambda e: hatalar.append(str(e)))
    pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(800)
    pg.evaluate("() => gorunumAc('roadmapSection')"); pg.wait_for_timeout(400)
    print("YH:" + json.dumps(pg.evaluate("() => Object.fromEntries([...document.querySelectorAll('.yhad.gecmis')].map(e => [e.closest('li').querySelector('.mono').textContent, e.textContent.replace(/\\s+/g,' ').trim()]))"), ensure_ascii=False))
    print("SIMDI:" + str(pg.evaluate("() => document.querySelectorAll('.yhdonem.simdi .yhad.gecmis').length")))
    print("NOT:" + pg.evaluate("() => (document.querySelector('.yhgecmisnot')||{textContent:''}).textContent.replace(/\\s+/g,' ')"))
    pg.evaluate("() => addDialog('MAT 210E')"); pg.wait_for_timeout(300)
    print("PENCERE:" + pg.evaluate("() => (document.querySelector('#detail .gecmisnot')||{textContent:''}).textContent.replace(/\\s+/g,' ')"))
    print("HATA:" + str(len(hatalar)) + " " + " | ".join(hatalar)[:300])
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
    assert c["HATA"].startswith("0"), c["HATA"]
    yh = json.loads(c["YH"])
    assert yh["MAT 210E"] == "geçmişte: 2025-26 Güz (115)", yh
    assert yh["BLG 335E"] == "geçmişte: 2025-26 Bahar (3) · 2025-26 Güz (80)", yh
    assert c["SIMDI"] == "0"                      # bu dönemin dersinde gösterilmiyor
    assert "Doğruluğu belirsizdir" in c["NOT"]
    assert c["PENCERE"].startswith("Geçmişte açıldığı dönemler (not dağılımına göre): 2025-26 Güz (115 öğrenci)")
    assert "Doğruluğu belirsizdir" in c["PENCERE"]
