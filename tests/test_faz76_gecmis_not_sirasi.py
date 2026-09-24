"""Faz 76 — seçmeli seçerken geçmiş not dağılımı aday listesinde.

Kullanıcı 24.09.2026: *"eklenebilecek çok işe yarar şeyleri düşün ve
ekleyebileceklerini ekle"*. Faz 38'in not dağılımı yalnız dersin
penceresindeydi; seçmeli arayan öğrenci dersleri tek tek açıyordu. Liste artık
satırda kısa özet gösteriyor ve isteğe bağlı sıralanıyor — Faz 38'in kuralı
aynen: öneri PUANINA girmiyor.
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
    g = _js("gecmisOzet")
    # Dersin penceresindeki varsayılan dönemle aynı; mevsim dışı işaretleniyor.
    assert "g.terms.find(t => t.term === g.selected) || g.terms[0]" in g
    assert "mevsimDisi: !!g.wantedSeason && d.season !== g.wantedSeason" in g
    s = _js("siralanmis")
    # Kararlı sıralama; verisi olmayan sona.
    assert "(y ? y.ort : -1) - (x ? x.ort : -1) || i - j" in s
    assert "const hepsi = siralanmis(filteredCandidates());" in _js("renderCandidates")
    assert "öneri puanına dahil değildir" in _js("renderCandidates")


def test_PUANA_GIRMIYOR():
    """Sunucu tarafı puanlama not dağılımını hâlâ kullanmıyor (Faz 38)."""
    rec = (pathlib.Path(UI.__file__).parent / "recommend.py").read_text(encoding="utf-8")
    assert "meanPoints" not in rec and "passRate" not in rec


_CANLI = r'''
import sys, os, json
sys.path.insert(0, os.environ["ITUCAP_SRC"]); sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import vitrin
adres, h = vitrin.ac()
from playwright.sync_api import sync_playwright
LISTE = "() => [...document.querySelectorAll('#cands tbody tr[data-course]')].map(tr => tr.dataset.course)"
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 1000})
    hatalar = []
    pg.on("pageerror", lambda e: hatalar.append(str(e)))
    pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(1000)
    pg.evaluate("() => gorunumAc('candSection')"); pg.wait_for_timeout(300)
    print("PUAN:" + json.dumps(pg.evaluate("() => M().candidates.map(c => [c.course, c.score])")))
    print("L0:" + json.dumps(pg.evaluate(LISTE)))
    print("K0:" + str(pg.evaluate("() => document.querySelectorAll('#cands .ndkisa').length")))
    pg.select_option("#candSort", "ort"); pg.wait_for_timeout(200)
    print("L1:" + json.dumps(pg.evaluate(LISTE)))
    print("K1:" + json.dumps(pg.evaluate("() => [...document.querySelectorAll('#cands .ndkisa')].map(e => e.innerText.replace(/\\s+/g,' '))"), ensure_ascii=False))
    print("S1:" + pg.evaluate("() => document.querySelector('#candCount').textContent"))
    print("PUAN2:" + json.dumps(pg.evaluate("() => M().candidates.map(c => [c.course, c.score])")))
    pg.select_option("#candSort", "bos"); pg.wait_for_timeout(200)
    print("L2:" + json.dumps(pg.evaluate("() => [...document.querySelectorAll('#cands tbody tr[data-course]')].map(tr => bosYer(candOf(tr.dataset.course)))")))
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
    l0 = json.loads(c["L0"])
    # Varsayılan: öneri puanı sırası; zorunlu derste özet yok (vitrinde seçmeli
    # havuz derslerinin dağılım verisi yok).
    assert c["K0"] == "0"
    # Ortalama: 2.69, 2.67, 2.55, 2.33, 1.68; verisi olmayanlar sonda, eski sırayla.
    l1 = json.loads(c["L1"])
    assert l1[:5] == ["GEO 321E", "GEO 315E", "GEO 341E", "BLG 223E", "MAT 210E"], l1
    assert l1[5:] == [x for x in l0 if x not in l1[:5]], (l0, l1)
    k1 = json.loads(c["K1"])
    assert len(k1) == 5 and k1[0].startswith("geçmiş dönem: ortalama 2.69"), k1
    assert "öneri puanına dahil değildir" in c["S1"]
    assert c["PUAN"] == c["PUAN2"]                  # puan değişmedi
    bos = json.loads(c["L2"])
    assert bos == sorted(bos, reverse=True), bos
