"""Faz 74 — "programıma daha ne sığar?" süzgeci.

Kullanıcı 24.09.2026: *"eklenebilecek çok işe yarar şeyleri düşün ve
ekleyebileceklerini ekle"*. Aday listesi yalnız "kontenjanı olanlar" diye
süzülebiliyordu; programdaki derslerle çakışmadan ve dönem sınırını aşmadan
eklenebilecek dersi bulmak için her dersin penceresini açmak gerekiyordu.
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


def test_KURAL():
    s = _js("sigdigiSube")
    assert "sel.some(x => x.course === c.course) || poolBlocker(c, null)" in s
    assert "loadOf(c) > kalan + 1e-9" in s
    # Saati ilan edilmemiş şube "çakışmıyor" görünür ama bilinmiyor → sayılmıyor.
    assert "(s.meetings || []).length" in s
    # İlan edilmemiş kontenjan dolu sayılmıyor.
    assert "(!s.capacity || yerSayisi(s) > 0)" in s
    assert "!conflictsWith(s, c.course).length && !mesgulCakisir(s)" in s
    assert "if(FILT.fit && !sigdigiSube(c, kalan)) return false;" in _js("filteredCandidates")
    assert 'id="candFit"' in KAYNAK


_CANLI = r'''
import sys, os, json
sys.path.insert(0, os.environ["ITUCAP_SRC"]); sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import vitrin
adres, h = vitrin.ac()
from playwright.sync_api import sync_playwright
LISTE = "() => [...document.querySelectorAll('#cands tbody tr[data-course]')].map(tr => tr.dataset.course)"
SAYI = "() => document.querySelector('#candCount').textContent"
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 1000})
    hatalar = []
    pg.on("pageerror", lambda e: hatalar.append(str(e)))
    pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(1000)
    pg.evaluate("() => gorunumAc('candSection')"); pg.wait_for_timeout(300)
    print("YUK:" + json.dumps(pg.evaluate("() => [totals().load, DATA.maxLoad]")))
    pg.check("#candFit"); pg.wait_for_timeout(200)
    print("S1:" + pg.evaluate(SAYI))
    print("L1:" + json.dumps(pg.evaluate(LISTE)))
    # Program değişince süzgeç kendiliğinden güncelleniyor (render → renderCandidates).
    pg.evaluate("() => removeCourse('GEO 385E')"); pg.wait_for_timeout(200)
    print("S2:" + pg.evaluate(SAYI))
    print("L2:" + json.dumps(pg.evaluate(LISTE)))
    print("U2:" + pg.evaluate("() => document.querySelector('#cands .uyansube').innerText.replace(/\\s+/g,' ')"))
    # Saati ilan edilmemiş şube sığmış sayılmıyor.
    pg.evaluate("() => { candOf('GEO 381E').sections.forEach(s => s.meetings = []); render(); }")
    print("L3:" + json.dumps(pg.evaluate(LISTE)))
    # Meşgul saat: GEO 385E'nin şubesi meşgule düşünce çıkıyor.
    pg.evaluate("""() => { DATA.busy = candOf('GEO 385E').sections.flatMap(s => s.meetings)
        .map(m => ({day: m.day, start: m.start, end: m.end, ok: true})); render(); }""")
    print("L4:" + json.dumps(pg.evaluate(LISTE)))
    pg.evaluate("() => { DATA.busy = []; render(); }")
    # Dönem sınırı: sınır dolunca hiçbir kredili ders sığmıyor.
    pg.evaluate("() => { DATA.maxLoad = totals().load + 1; render(); }")
    print("L5:" + json.dumps(pg.evaluate(LISTE)))
    print("S5:" + pg.evaluate(SAYI))
    print("TASMA:" + str(pg.evaluate("() => document.documentElement.scrollWidth > innerWidth + 1")))
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
             if ":" in s and s.split(":", 1)[0].isalnum() and s.split(":", 1)[0].isupper())
    assert c["HATA"].startswith("0"), c["HATA"]
    assert json.loads(c["YUK"]) == [24, 25]
    # 24/25 kredi: 3 kredilik hiçbir ders sığmıyor.
    # Havuz yuvası dolu seçmeliler sayıyla ayrıca yazılıyor (gerçek sitede
    # 6 kredi boşken "0 ders" nedeni görünmüyordu).
    assert c["S1"] == ("0 ders programa sığıyor · sınıra 1 kredi kaldı · 2 seçmeli dersin"
                       " havuz yuvası programda dolu (eklenirse o yuvadaki dersin yerine geçer)"), c["S1"]
    assert json.loads(c["L1"]) == []
    assert c["S2"] == "2 ders programa sığıyor · sınıra 4 kredi kaldı", c["S2"]
    assert json.loads(c["L2"]) == ["GEO 385E", "GEO 381E"]
    assert c["U2"].startswith("uyan şube: CRN 13661 · Çar 12:30 · 1 boş yer"), c["U2"]
    assert json.loads(c["L3"]) == ["GEO 385E"]
    assert json.loads(c["L4"]) == []
    assert json.loads(c["L5"]) == [] and "sınıra 1 kredi kaldı" in c["S5"]
    assert c["TASMA"] == "False"
