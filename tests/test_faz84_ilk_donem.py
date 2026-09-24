"""Faz 84 — gerçek sitede 1. dönem (transkriptsiz) KMM öğrencisiyle bulunanlar.

Kullanıcı 24.09.2026: *"geliştirmelere devam et ve sonrasında pr oluştur"*.
Site gerçek katalogla kuruldu; KMM, ikinci program yok, 1. dönem, ders
girilmemiş:

1. Başvuru bölümü "✓ Çift anadal — denetlenebilen şartlar sağlanmaktadır"
   diyordu. Şartların HİÇBİRİ değerlendirilemiyordu (GNO yok, kredi yok,
   sıralama zaten bilinmiyor); boş bir doğru yeşil onay olarak basılıyordu.
2. Kip notu "0 alttan (1–0. dönem)" yazıyordu.
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


class _C:
    def __init__(self, t):
        self.term_no = t


def test_KIP_NOTU_birinci_donemde_alttan_yok():
    assert UI._term_note([_C(1), _C(1)], 1, "") == "2 dönemlik (1. dönem)"
    assert UI._term_note([_C(1), _C(2)], 2, "") == "1 dönemlik (2. dönem) · 1 alttan (1–1. dönem)"


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
    T = "() => document.querySelector('#basvuruSummary').textContent.replace(/\\s+/g,' ')"
    print("ONCE:" + pg.evaluate(T))
    # Transkriptsiz 1. dönem öğrencisi: bütün şartlar bilinmiyor.
    pg.evaluate("""() => { for(const k of ['cap', 'yandal']){ const s = DATA.basvuru[k];
        s.checks.forEach(c => c.ok = null); s.eligible = true; s.unknownCount = s.checks.length; }
      DATA.donem = 1; DATA.load = Object.assign({}, DATA.load, {noTranscript: true}); renderBasvuru(); }""")
    print("SONRA:" + pg.evaluate(T))
    print("ISARET:" + json.dumps(pg.evaluate("() => [...document.querySelectorAll('#basvuruSummary .mark')].map(e => e.textContent.trim())")))
    pg.evaluate("() => openBasvuru('cap')"); pg.wait_for_timeout(200)
    print("PENCERE:" + pg.evaluate("() => document.querySelector('#basvuruBody').textContent.replace(/\\s+/g,' ')"))
    print("HATA:" + str(len(hatalar)) + " " + " | ".join(hatalar)[:300])
    b.close()
h.shutdown()
'''


def test_BASVURU_bos_onay_yok_vitrin(tmp_path, monkeypatch):
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
    # Transkriptli vitrin öğrencisinde eski davranış yerinde.
    assert "değerlendirilememektedir" not in c["ONCE"], c["ONCE"]
    s = c["SONRA"]
    assert "sağlanmaktadır" not in s, s
    assert "şartlar değerlendirilememektedir (başarılan dersler girilmemiştir)" in s, s
    assert "3. yarıyıldan (30 kredi) itibaren açılır; şu an 1. dönemdesiniz" in s, s
    assert json.loads(c["ISARET"]) == ["—", "—"]
    assert "Şartların hiçbiri değerlendirilememektedir." in c["PENCERE"], c["PENCERE"]
    assert "Denetlenebilen şartlar sağlanmaktadır" not in c["PENCERE"]
