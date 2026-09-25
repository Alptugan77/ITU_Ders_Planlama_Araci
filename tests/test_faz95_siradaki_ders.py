"""Faz 95 — telefonda "sıradaki ders".

Kullanıcı 25.09.2026: *"continue"* (Faz 93–94: programa bakarak derse
gidebilmek). Gün listesi Pazartesi'den başlıyordu; okulda sorulan soru
"şimdi ne var, sıradaki ders nerede". Listenin başında tek satır: süren ders,
bugünün sıradaki dersi ya da bir sonraki ders günü — saat, bina, derslik.

Akademik takvim araçta yok: söz "programınıza göre", ders yapıldığı iddia
edilmiyor.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import ui as UI

_CANLI = r'''
import sys, os, json
sys.path.insert(0, os.environ["ITUCAP_SRC"]); sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import vitrin
adres, h = vitrin.ac()
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_context(viewport={"width": 390, "height": 900}).new_page()
    pg.clock.install(time="2026-09-28T07:30:00")          # Pazartesi 07:30
    hatalar = []; pg.on("pageerror", lambda e: hatalar.append(str(e)))
    pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(800)
    T = "() => (document.querySelector('#daylist .siradaki')||{textContent:'YOK'}).textContent.replace(/\\s+/g,' ').trim()"
    print("ACILIS:" + pg.evaluate(T))
    print("BUGUN:" + pg.evaluate("() => [...document.querySelectorAll('#daylist h3')].map(h => h.textContent.replace(/\\s+/g,' ').trim()).join('|')"))
    pg.clock.fast_forward("01:30:00"); pg.wait_for_timeout(200)          # 09:00, ders sürüyor
    print("TAZE:" + pg.evaluate(T))
    D = "(an) => { const d = document.createElement('div'); d.innerHTML = siradakiHTML(an); return d.textContent.replace(/\\s+/g,' ').trim(); }"
    print("DURUM:" + json.dumps([pg.evaluate(D, an) for an in (
        {"gun": 1, "dk": 700}, {"gun": 1, "dk": 920}, {"gun": 1, "dk": 1200},
        {"gun": 5, "dk": 1200}, {"gun": 6, "dk": 600})], ensure_ascii=False))
    print("IPUCU:" + pg.evaluate("() => document.querySelector('#daylist .siradaki').title"))
    print("BOS:" + json.dumps(pg.evaluate("() => { sel.length = 0; return siradakiHTML({gun: 1, dk: 600}); }")))
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
    # Pazartesi 07:30 → ilk ders 08:30, bir saat sonra; bina + derslik.
    assert c["ACILIS"] == "Sıradaki: 08:30 GEO 315E · INB D01 (1 sa sonra)", c["ACILIS"]
    assert c["BUGUN"].startswith("Pzt bugün|Sal|"), c["BUGUN"]
    # Sayfa açık kalınca satır tazeleniyor (09:00: ders sürüyor).
    assert c["TAZE"] == "Şimdi: GEO 315E · INB D01 · bitiş 11:29", c["TAZE"]
    d = json.loads(c["DURUM"])
    assert d[0] == "Şimdi: BLG 223E · EEB D01 · bitiş 13:29"
    assert d[1] == "Sıradaki: 15:30 BLG 222E · çevrimiçi (10 dk sonra)"
    assert d[2] == "Bugün başka ders yok. Salı ilk ders: 13:30 GEO 351E · INB D05"
    assert d[3] == d[4] == "Bugün başka ders yok. Pazartesi ilk ders: 08:30 GEO 315E · INB D01"
    assert "akademik takvim" in c["IPUCU"]
    assert json.loads(c["BOS"]) == ""                   # programda ders yoksa satır yok
