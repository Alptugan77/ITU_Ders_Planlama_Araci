"""Faz 101 — ızgara hangi programı gösteriyor.

Kullanıcı 25.09.2026: *"kaydedilen program gözüktüğünde üstte önerilen
program seçilmiş gözüktüğü için karıştırılabilir programın kredisi ve kaç
çevrimiçi ders olduğu onu da düzelt"*.

Açılışta kaydedilen program yükleniyordu ama şeritte "Öneri 1 · 24 kredi"
seçiliydi ve "değiştirildi" yazıyordu. Artık "Kaydedilen" sekmesi kendi
kredisi ve çevrimiçi ders sayısıyla seçili; özet de çevrimiçi sayısını yazıyor.
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
    pg = b.new_page(viewport={"width": 1400, "height": 1000})
    hatalar = []
    pg.on("pageerror", lambda e: hatalar.append(str(e)))
    pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(800)
    D = """() => ({
      secili: [...document.querySelectorAll('#tabs .tab[aria-selected="true"]')].map(e => e.textContent.replace(/\\s+/g,' ').trim()),
      kayitliSekme: !!document.querySelector('#tabs .kaynaktab'),
      ozet: document.querySelector('#schedSummary .ozetsatir').textContent.replace(/\\s+/g,' ').trim(),
      degisti: !document.querySelector('#editState').hidden,
      donBtn: !document.querySelector('#reset').hidden,
      kredi: totals().credits, cev: picks().filter(p => p.sec.online).length})"""
    print("ACILIS:" + json.dumps(pg.evaluate(D), ensure_ascii=False))
    # Öneri 2'den bir ders eksik bir program kaydedilmiş olsun; açılıştaki gibi yükle.
    pg.evaluate("""() => { const s = M().schedules[1].picks.slice(1);
       DATA.savedPicks = {picks: s.map(p => ({course: p.course, crn: p.section.crn})), savedAt: '2026-09-20T10:00'};
       startFromSaved(); }""")
    print("KAYITLI:" + json.dumps(pg.evaluate(D), ensure_ascii=False))
    pg.evaluate("() => removeCourse(sel[0].course)")
    print("DUZEN:" + json.dumps(pg.evaluate(D), ensure_ascii=False))
    pg.evaluate("() => document.querySelector('#reset').click()")
    print("ONERI:" + json.dumps(pg.evaluate(D), ensure_ascii=False))
    print("KAYITSEKME:" + pg.evaluate("() => document.querySelector('#tabs [data-kayitli]').textContent.replace(/\\s+/g,' ').trim()"))
    pg.evaluate("() => document.querySelector('#tabs [data-kayitli]').click()")
    print("GERIYUKLE:" + json.dumps(pg.evaluate(D), ensure_ascii=False))
    # Kaydedilen, bir öneriyle aynıysa öneri sekmesi seçili (tekrar yok).
    pg.evaluate("""() => { const s = M().schedules[2].picks;
       DATA.savedPicks = {picks: s.map(p => ({course: p.course, crn: p.section.crn})), savedAt: ''};
       startFromSaved(); }""")
    print("ESIT:" + json.dumps(pg.evaluate(D), ensure_ascii=False))
    # Alternatif (Plan B) yüklenince onun adı.
    pg.evaluate("""() => { const s = M().schedules[1].picks.slice(2);
       DATA.alternatives = [{name: 'Plan B', picks: s.map(p => ({course: p.course, crn: p.section.crn}))}];
       altYukle(DATA.alternatives[0]); }""")
    print("ALT:" + json.dumps(pg.evaluate(D), ensure_ascii=False))
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
    c = {k: (json.loads(v) if v.startswith("{") else v) for k, v in
         (s.split(":", 1) for s in r.stdout.strip().splitlines()
          if ":" in s and s.split(":", 1)[0].isupper())}
    assert c["HATA"].startswith("0"), c["HATA"]
    a = c["ACILIS"]                                  # kayıt yok: eski davranış
    assert a["secili"][0].startswith("Öneri 1") and not a["kayitliSekme"] and not a["degisti"]

    k = c["KAYITLI"]
    assert len(k["secili"]) == 1, k                   # Öneri 1 artık seçili DEĞİL
    assert k["secili"][0].startswith(f"Kaydedilen · {k['kredi']:g} kredi"), k
    assert k["cev"] and f"{k['cev']} çevrimiçi" in k["secili"][0], k
    assert k["ozet"].endswith(f"· {k['cev']} çevrimiçi"), k
    assert not k["degisti"] and k["donBtn"], k        # "değiştirildi" yok, "Öneriye dön" var

    d = c["DUZEN"]                                   # kaydedilen düzenlendi
    assert d["secili"][0].startswith("Kaydedilen") and d["degisti"], d
    assert d["kredi"] < k["kredi"] and f"{d['kredi']:g} kredi" in d["secili"][0]

    o = c["ONERI"]                                   # öneriye dönüldü
    assert o["secili"][0].startswith("Öneri") and len(o["secili"]) == 1 and not o["degisti"], o
    assert c["KAYITSEKME"].startswith(f"Kaydedilen · {k['kredi']:g} kredi"), c["KAYITSEKME"]
    assert c["GERIYUKLE"]["secili"] == k["secili"], c["GERIYUKLE"]

    e = c["ESIT"]
    assert e["secili"][0].startswith("Öneri 3") and len(e["secili"]) == 1, e
    alt = c["ALT"]
    assert alt["secili"][0].startswith("Plan B · ") and not alt["degisti"], alt
