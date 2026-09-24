"""Faz 67 — İTÜ Helper, OBS, Kepler ve yönergeye yönlendirme.

Kullanıcı 24.09.2026: *"gelişmelere devam et ve gerektiğinde site içinde itü
helper gibi sitelere yönlendir ve bahset"*.

* Adresler TEK yerde (`config.DIS_BAGLANTILAR`) ve uydurma değil: İTÜ
  adresleri İTÜ Helper ana sayfasının "İTÜ KISAYOLLARI" listesinden, OBS
  sayfaları aracın kullandığı uçlardan.
* Ders kaydı Kepler'de yapılıyor ("Ders Kayıt İşlemleri" ekranına CRN) —
  arayüz "OBS'ye girilecek numaralar" diyordu; düzeltildi.
* Bağlantılar yeni sekmede ve `noreferrer`: paylaşım bağlantısındaki CRN'ler
  bile karşı siteye gitmez.
"""
import json
import pathlib
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import config
from itucap import ui as UI
from itucap.sources import obs_notdagilimi

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


def _js(ad):
    f = KAYNAK[KAYNAK.index(f"function {ad}("):]
    return f[:f.index("\n}\n")]


def test_ADRESLER_tek_yerde_ve_KULLANILANLAR_tanimli():
    L = config.DIS_BAGLANTILAR
    for k, v in L.items():
        assert v["url"].startswith("https://"), k
        assert v["ad"] and v["aciklama"], k
    kullanilan = set(re.findall(r'disLink\("([A-Za-z]+)"', KAYNAK))
    assert kullanilan and kullanilan <= set(L), kullanilan - set(L)
    # Arayüzde elle yazılmış dış adres yok (tek istisna: kâğıda basılan
    # kayıt listesi — kâğıtta bağlantı tıklanamaz, adres metin olarak yazılı).
    js = KAYNAK[KAYNAK.index("<script>"):]
    elle = set(re.findall(r'https://[a-z0-9.-]+', js)) - {"https://www.w3.org"}
    assert not elle, elle


def test_NOT_DAGILIMI_adresi_aracin_okudugu_UC():
    u = config.notdagilimi_url("MAT 103E", 2026)
    assert u == obs_notdagilimi.ENDPOINT + "?bransKodu=MAT&dersNo=103E&yil=2026"
    assert config.notdagilimi_url("BLG 4901", "2025").endswith("bransKodu=BLG&dersNo=4901&yil=2025")
    assert '"url": config.notdagilimi_url(code, config.term_year(t["term"]) or 0)' in KAYNAK
    assert 'disLink("obsNot", "İTÜ OBS Ders Not Dağılımı", donem.url)' in _js("notDagilimi")


def test_YENI_SEKME_ve_NOREFERRER():
    i = KAYNAK.index("const disLink = ")
    f = KAYNAK[i:KAYNAK.index("\n};", i)]
    assert 'target="_blank" rel="noopener noreferrer"' in f
    assert "esc(u)" in f and "esc(etiket" in f


def test_KAYIT_KEPLERDE_yapiliyor():
    assert "OBS'ye girilecek" not in KAYNAK
    assert "ders kaydı OBS üzerinden" not in KAYNAK
    assert 'disLink("kepler")' in _js("crnDialog")


def test_PLAN_linki_yalniz_OBS_planinda():
    i = KAYNAK.index('"title": plan["title"],')
    k = KAYNAK[i:i + 400]
    assert 'startswith(config.OBS + "/public/DersPlan/DersPlanDetay/")' in k
    p = _js("panelHTML")
    assert "p.url" in p and 'p.source === "itu-helper"' in p


_CANLI = r'''
import sys, os, json
sys.path.insert(0, os.environ["ITUCAP_SRC"]); sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import vitrin
adres, h = vitrin.ac()
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1400, "height": 1000})
    hatalar = []; pg.on("pageerror", lambda e: hatalar.append(str(e)))
    pg.goto(adres, wait_until="networkidle"); pg.wait_for_timeout(1000)
    L = "(sel) => [...document.querySelectorAll(sel + ' a.dislink')].map(a => [a.href, a.target, a.rel])"
    print("FOOTER:" + json.dumps(pg.evaluate(L, "footer")))
    pg.evaluate("() => courseDialog('BLG 223E')"); pg.wait_for_timeout(400)
    print("DERS:" + json.dumps(pg.evaluate(L, "#detail")))
    pg.evaluate("() => document.querySelector('#detail').close()")
    pg.click("#crnBtn"); pg.wait_for_timeout(400)
    print("KAYIT:" + json.dumps(pg.evaluate(L, "#detail")))
    print("HATA:" + str(len(hatalar)) + " " + " | ".join(hatalar)[:300])
    b.close()
h.shutdown()
'''


def test_UCTAN_UCA_baglantilar(tmp_path, monkeypatch):
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
    L = config.DIS_BAGLANTILAR
    footer = json.loads(c["FOOTER"])
    for k in ("kepler", "obsProgram", "obsPlan", "yonerge", "ituHelper",
              "ituHelperOnsart", "ituHelperProgram", "ituHelperVeri"):
        assert any(h == L[k]["url"] for h, _, _ in footer), k
    assert all(t == "_blank" and "noreferrer" in r for _, t, r in footer)
    ders = [h for h, _, _ in json.loads(c["DERS"])]
    assert L["obsProgram"]["url"] in ders and L["obsPlan"]["url"] in ders
    assert any("NotDagilimiSearch?bransKodu=BLG&dersNo=223E&yil=" in h for h in ders), ders
    kayit = [h for h, _, _ in json.loads(c["KAYIT"])]
    assert L["kepler"]["url"] in kayit and L["obsProgram"]["url"] in kayit
