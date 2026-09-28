"""Faz 112 — danışman özetinde yalnız DİLEKÇE gerektirenler.

Kullanıcı (28.09.2026): *"danışman özeti kısmında da dilekçe dışında
danışmana sorulacak diye yazdığın şeyleri çıkarabilirsin"*.

Kalan maddeler: dönem yük sınırı aşımı, ÇAP yarıyıl tabanı indirimi (yalnız
indirim varsa), dolu şubeye kontenjan, programdaki dersi gereken bir dersin
yerine resmî denklikle saydırma (şubesi bölüme açık değilse; Faz 111).
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import ui as UI

KAYNAK = open(UI.__file__, encoding="utf-8").read()


def _js(ad):
    i = KAYNAK.index(f"function {ad}(")
    return KAYNAK[i:KAYNAK.index("\n}\n", i)]


def test_YALNIZ_DILEKCE_maddeleri():
    f = _js("danismanSorulari")
    assert f.count("q.push(") == 4, f
    for kalkan in ("kalanGereken", "tekrarDurumu", "kalmaGuncel", "zorlukOf", "R.takeNow",
                   "noTranscript", "jointDegree", "saati ilan edilmemiştir"):
        assert kalkan not in f, kalkan
    assert "F.relief" in f                                       # indirim yoksa madde yok
    assert "<h3>Dilekçe gerektirenler</h3>" in KAYNAK
    assert "Dilekçe gerektiren bir durum bulunmamaktadır." in KAYNAK
    assert "Danışmana sorulacaklar" not in KAYNAK


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
    ders = pg.evaluate("() => picks()[0].cand.course")
    print("DERS:" + json.dumps(ders))
    kaynak = lambda dk: ("{code: '%s', name: '', open: true, passed: false, dilekcesiz: %s, "
                         "dilekcesizCrn: [], sections: []}" % (ders, dk))
    for ad, dk in (("DILEKCELI", "false"), ("DILEKCESIZ", "true")):
        pg.evaluate("() => { DATA.openEquivalents = [{target: 'MAT 210E', needed: true, declared: false, "
                    "confidence: 'official', mode: 'or', sources: [" + kaynak(dk) + "]}]; }")
        print(ad + ":" + json.dumps(pg.evaluate(
            "() => danismanSorulari().map(s => s.replace(/<[^>]+>/g, '').replace(/\\s+/g, ' ').trim())"),
            ensure_ascii=False))
    print("HATA:" + str(len(hatalar)))
    b.close()
h.shutdown()
'''


def test_DENKLIK_DILEKCESI_vitrin(tmp_path, monkeypatch):
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
    assert c["HATA"] == "0"
    ders = json.loads(c["DERS"])
    beklenen = f"{ders} dersini MAT 210E yerine saydırmak için denklik dilekçesi verilmelidir."
    assert beklenen in json.loads(c["DILEKCELI"]), c["DILEKCELI"]
    assert not any("denklik dilekçesi" in s for s in json.loads(c["DILEKCESIZ"])), c["DILEKCESIZ"]
