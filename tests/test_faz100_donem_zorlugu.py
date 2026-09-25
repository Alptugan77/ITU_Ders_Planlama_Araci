"""Faz 100 — dönem zorluğu ders sayısı ve krediyle artıyor.

Kullanıcı 25.09.2026: *"ders programında tahmini zorluk kısmında alınan ders
sayısı artıkça zorluk artmalı 1 ders alındığında o ders çok zor olsa bile
kolay geçer ama 15 tane orta ders alınırsa dönem zor geçer"*.

Eskiden programın zorluğu derslerin kredi ağırlıklı ORTALAMASIYDI: tek çok
zor ders 9.5/10, on beş orta ders 5/10 çıkıyordu. Artık her dersin kredisi
zorluğuyla ağırlıklandırılıp TOPLANIYOR (0.5 … 1.5), 40 ağırlıklı kredi 10.
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
    print("PZ:" + json.dumps(pg.evaluate("""() => {
      const d = (s, k = 3) => ({credits: k, grades: {difficulty: {level: 3, score: s}}});
      const yok = (k = 3) => ({credits: k, grades: null});
      const f = (l) => { const z = programZorlugu(l); return [z.donem, z.donemKademe, z.ort]; };
      return {
        tekCokZor: f([d(9.5)]),
        onbesOrta: f(Array(15).fill(d(5))),
        yediOrta: f(Array(7).fill(d(5))),
        yediKolay: f(Array(7).fill(d(1))),
        sekizOrta: f(Array(8).fill(d(5))),
        verisizOrta: f([d(5), yok(), yok()]),
        ucOrta: f(Array(3).fill(d(5))),
        hicVeri: f([yok(), yok()]),
      }; }""")))
    # Özet: çok ağır yük uyarısı.
    print("AGIR:" + pg.evaluate("""() => { const ps = picks();
      ps.forEach(p => { p.cand.grades = {difficulty: {level: 5, score: 10.0, passRate: 60, mean: 1.2}}; });
      render(); return document.querySelector('#schedSummary .ozetzorluk').textContent.replace(/\\s+/g,' '); }"""))
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
    z = json.loads(c["PZ"])
    # Kullanıcının iki örneği: tek çok zor ders kolay, on beş orta ders çok zor.
    assert z["tekCokZor"] == [1.1, 1, 9.5]
    assert z["onbesOrta"] == [10, 5, 5]
    # Ölçek: 21 kredilik orta yük "orta"; aynı kredide kolay dersler daha hafif.
    assert z["yediOrta"] == [5.3, 3, 5]
    assert z["yediKolay"][0] < z["yediOrta"][0] and z["yediKolay"][1] == 2
    # Ders eklendikçe artıyor (ortalama değişmediği halde).
    assert z["ucOrta"][0] < z["yediOrta"][0] < z["sekizOrta"][0] < z["onbesOrta"][0]
    assert z["ucOrta"][2] == z["onbesOrta"][2] == 5
    # Verisiz ders ORTA sayılıyor: yükten düşmüyor.
    assert z["verisizOrta"] == z["ucOrta"]
    # Hiç veri yoksa krediden zorluk iddia edilmiyor.
    assert z["hicVeri"] == [None, None, None]
    assert "dönem yükü çok ağır" in c["AGIR"], c["AGIR"]
