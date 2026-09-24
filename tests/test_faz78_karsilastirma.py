"""Faz 78 — karşılaştırma öneriler, ızgara, kaydedilen ve alternatifleri kapsıyor.

Kullanıcı 24.09.2026: *"geliştirmelere devam et ve sonrasında pr oluştur"*.
Faz 77'de alternatif programlar geldi ama karşılaştırma ekranı yalnız motorun
önerilerini gösteriyordu; "Plan B mi Plan C mi" sorusu yine sekme ezberlemekti.
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


def test_TEK_OLCU_ve_TEK_SUTUN():
    k = _js("karsilastirmaSutunlari")
    # Aynı program iki adla → tek sütun.
    assert "if(var_){ var_.adlar.push(ad); return; }" in k
    for parca in ('"Izgaradaki"', '"Kaydedilen"', "(DATA.alternatives || []).forEach"):
        assert parca in k, parca
    assert "olcu: programOlcu(liste)" in k
    assert "altYukle({name: s.adlar[0], picks: s.liste})" in _js("karsilastirDialog")


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
    # İstemcideki ölçü, önerilerde sunucunun şekliyle AYNI.
    print("ESIT:" + json.dumps(pg.evaluate("""() => M().schedules.map(s => {
        const o = programOlcu(s.picks.map(p => ({course: p.course, crn: p.section.crn})));
        return JSON.stringify(o.shape) === JSON.stringify(s.shape) && o.campusChanges === s.campusChanges
          && o.credits === s.credits; })""")))
    print("ONCE:" + json.dumps(pg.evaluate("() => karsilastirmaSutunlari().map(s => s.adlar)")))
    # Alternatif: BLG 252E çıkarılmış program.
    pg.evaluate("() => removeCourse('BLG 252E')"); pg.wait_for_timeout(200)
    pg.click("#altKaydet"); pg.wait_for_timeout(300)
    pg.click("#altKaydetOk"); pg.wait_for_timeout(3000)
    print("SONRA:" + json.dumps(pg.evaluate("() => karsilastirmaSutunlari().map(s => s.adlar)"), ensure_ascii=False))
    pg.evaluate("() => karsilastirDialog()"); pg.wait_for_timeout(300)
    print("BASLIK:" + json.dumps(pg.evaluate("() => [...document.querySelectorAll('#detail .cmp thead th')].map(e => e.textContent.trim())"), ensure_ascii=False))
    print("SATIR:" + json.dumps(pg.evaluate("() => [...document.querySelectorAll('#detail .cmp tbody th')].map(e => e.textContent.trim())"), ensure_ascii=False))
    print("SECILI:" + json.dumps(pg.evaluate("() => [...document.querySelectorAll('#detail .cmp thead th.secili')].map(e => e.textContent.trim())"), ensure_ascii=False))
    # Öneri 1'e dön, sonra karşılaştırmadan alternatifi yükle.
    pg.evaluate("() => { document.querySelector('#detail').close(); resetTo(0); }"); pg.wait_for_timeout(200)
    pg.evaluate("() => karsilastirDialog()"); pg.wait_for_timeout(300)
    i = pg.evaluate("() => karsilastirmaSutunlari().findIndex(s => s.adlar.includes('Plan B'))")
    pg.click(f"#detail [data-kyas='{i}']"); pg.wait_for_timeout(300)
    print("YUK:" + json.dumps(pg.evaluate("() => sel.length")))
    print("SEKME:" + str(pg.evaluate("() => !!document.querySelector('#karsilastir')")))
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
    esit = json.loads(c["ESIT"])
    assert esit and all(esit), esit
    once = json.loads(c["ONCE"])
    # Açılışta ızgara = Öneri 1: tek sütun, iki ad.
    assert once[0] == ["Öneri 1", "Izgaradaki"], once
    sonra = json.loads(c["SONRA"])
    # Izgara şimdi Plan B ile aynı: tek sütun.
    assert ["Izgaradaki", "Plan B"] in sonra, sonra
    baslik = json.loads(c["BASLIK"])
    assert "Izgaradaki = Plan B" in baslik and baslik[1] == "Öneri 1", baslik
    satir = json.loads(c["SATIR"])
    for s in ("Kredi", "Dolu günler", "Kampüs değişimi", "Dolu şube", "Değişen dersler"):
        assert s in satir, (s, satir)
    assert json.loads(c["SECILI"]) == ["Izgaradaki = Plan B"]
    assert json.loads(c["YUK"]) == 7
    assert c["SEKME"] == "True"
