"""Faz 65 — kurulumda gerçek sitede görülen iki pürüz.

Kullanıcı 24.09.2026: *"can you continue and create a pr"*. Site gerçek
katalogla kurulup yeni bir öğrenci gibi gezildi (BLGE, ikinci program yok):

* Dönem penceresi ÇAP'ı OLMAYAN öğrenciye "ÇAP'a başladığın yarıyıl"
  soruyordu; kurulum listesi "Tek tıklama" dediği hâlde dönem iki tık
  (sayı + Kaydet) istiyordu.
* Kurulum listesi "en kolayı: transkriptini yapıştır" diyordu ama "Dersleri
  gir" plandan-işaretle penceresini açıyordu ve oradan yapıştırmaya yol
  yoktu. Tikle girilen ders notsuz (DD) sayılıyor; gerçek notlar — GNO,
  kredi tavanı — yalnız yapıştırmayla geliyor.
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


def _js(ad):
    f = KAYNAK[KAYNAK.index(f"function {ad}("):]
    return f[:f.index("\n}\n")]


def test_DONEM_penceresi_CAP_sorusu_yalniz_CAP_varken():
    d = _js("termDialog")
    assert 'const capVar = ["cap", "ikisi"].includes(SETUP.secondKind);' in d
    assert "${capVar ? `<label" in d
    assert "if(!capVar) kaydet();" in d


def test_PLANDAN_ISARETLE_yapistirmaya_yol_veriyor():
    d = _js("checklistDialog")
    assert 'id="ckYapistir"' in d
    i = d.index('$("#ckYapistir").addEventListener')
    assert '$("#setup").close();' in d[i:i + 200] and "courseDialogSetup();" in d[i:i + 200]


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
    pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(1000)
    acik = "() => (document.querySelector('dialog[open]')||{id:'yok'}).id"
    # (1) ÇAP'lı vitrin öğrencisi: soru var, sayıya basmak kaydetmiyor.
    pg.evaluate("() => termDialog()"); pg.wait_for_timeout(300)
    once = pg.evaluate("() => DATA.donem")
    pg.click("#fTerm button[data-t='6']"); pg.wait_for_timeout(600)
    print("CAPLI:" + json.dumps([pg.evaluate("() => !!document.querySelector('#fCap')"),
                                 pg.evaluate(acik), pg.evaluate("() => DATA.donem") == once]))
    pg.evaluate("() => document.querySelector('#setup').close()")
    # (2) İkinci program "Yok": soru yok, TEK tık kaydediyor.
    pg.evaluate("() => api('/api/programs', {anadalProgram: 'HTAE', secondKind: 'yok'}).then(r => applyState(r))")
    pg.wait_for_timeout(1500)
    pg.evaluate("() => termDialog()"); pg.wait_for_timeout(300)
    soru = pg.evaluate("() => !!document.querySelector('#fCap')")
    pg.click("#fTerm button[data-t='6']"); pg.wait_for_timeout(2000)
    print("CAPSIZ:" + json.dumps([soru, pg.evaluate(acik), pg.evaluate("() => DATA.donem")]))
    # (3) Plandan işaretle → transkript yapıştırma.
    pg.evaluate("() => checklistDialog()"); pg.wait_for_timeout(400)
    pg.click("#ckYapistir"); pg.wait_for_timeout(400)
    print("YAPISTIR:" + json.dumps([pg.evaluate(acik),
                                    pg.evaluate("() => !!document.querySelector('#trPaste')")]))
    print("HATA:" + str(len(hatalar)) + " " + " | ".join(hatalar)[:300])
    b.close()
h.shutdown()
'''


def test_UCTAN_UCA_kurulum(tmp_path, monkeypatch):
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
    assert json.loads(c["CAPLI"]) == [True, "setup", True], c["CAPLI"]
    assert json.loads(c["CAPSIZ"]) == [False, "yok", 6], c["CAPSIZ"]
    assert json.loads(c["YAPISTIR"]) == ["setup", True], c["YAPISTIR"]
