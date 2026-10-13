"""Faz 136 — ders penceresi: önce şube ve eylemler, sonra analiz.

Kullanıcı (13.10.2026): *"continue improving the ui and ux"*. Izgaradaki
derse tıklanınca açılan pencere ölçüldü (1440px):

* Seçili şubenin CRN'i, saati, dersliği ve hocası pencerenin HİÇBİR
  yerinde yoktu.
* "Programdan çıkar", "Bu saate kilitle", "Kontenjanı izle" en alttaydı:
  puan kırılımı, 334px'lik zorluk kutusu, not dağılımı ve alternatif
  derslerin altında (~900px aşağıda).
* Zorluk kutusunun yarısı yöntem paragrafıydı (formül ve ölçek).

Eylemler üste çıkınca ilk odaklanabilir öğe "Programdan çıkar" olurdu
(açılır açılmaz Enter dersi silerdi); odak artık başlıkta.
"""
import json
import pathlib
import subprocess
import sys
import tempfile

import pytest

from itucap import ui as UI

KOK = pathlib.Path(UI.__file__).resolve().parents[2]
K = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


def _fn(ad):
    i = K.index(f"function {ad}(")
    return K[i:K.index("\n}\n", i)]


def test_SIRA_sube_eylem_alternatif_analiz():
    f = _fn("courseDialog")
    sira = [f.index(x) for x in ("${mevcutSube(cand, cur.crn)}", 'id="removeCourse"',
                                 "başka şube", "yerine başka ders", "${puanKirilimi(cand)}",
                                 "${zorlukKutusu(cand)}", "${notDagilimi(cand)}")]
    assert sira == sorted(sira), sira


def test_ODAK_baslikta_silme_dugmesinde_degil():
    assert '<h2 class="mono" tabindex="-1" autofocus>${esc(cand.course)}</h2>' in _fn("courseDialog")


def test_ZORLUK_yontemi_katlanir_ama_ozet_gorunur():
    z = _fn("zorlukKutusu")
    assert '<details class="zorluknot zyontem"><summary>Nasıl hesaplanır?</summary>' in z
    # Dürüstlük notu katlanmıyor.
    acik = z[:z.index("<details")]
    assert "dahil edilmez" in acik


_CANLI = r'''
import sys, os, json
sys.path.insert(0, os.environ["ITUCAP_SRC"]); sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import vitrin
adres, h = vitrin.ac()
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    hatalar = []
    pg.on("pageerror", lambda e: hatalar.append(str(e)))
    pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(800)
    pg.locator("#grid .blk").first.click(); pg.wait_for_timeout(500)
    print("OUT:" + json.dumps(pg.evaluate("""() => {
      const d = document.querySelector('#detail'), kod = d.querySelector('h2').textContent.trim(), crn = sel.find(x => x.course === kod).crn;
      const ms = d.querySelector('.mevcutsube'), cik = d.querySelector('#removeCourse');
      const dr = d.getBoundingClientRect();
      return {crn, sube: ms ? ms.textContent.replace(/\\s+/g, ' ') : '',
              cikarUst: cik.getBoundingClientRect().top - dr.top,
              pencere: dr.height,
              odak: document.activeElement.tagName,
              yontemAcik: d.querySelector('.zyontem') ? d.querySelector('.zyontem').open : null}; }""")))
    print("HATA:" + str(len(hatalar)) + " " + " | ".join(hatalar)[:300])
    b.close()
h.shutdown()
'''


def test_UCTAN_UCA_vitrin(tmp_path, monkeypatch):
    try:
        import playwright  # noqa: F401
    except ImportError:
        pytest.skip("playwright yok")
    monkeypatch.setenv("ITUCAP_SRC", str(KOK / "src"))
    monkeypatch.setenv("ITUCAP_TOOLS", str(KOK / "tools"))
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
    o = json.loads(c["OUT"])
    # Programdaki şube pencerede: CRN ve saat.
    assert f"CRN {o['crn']}" in o["sube"] and ":" in o["sube"], o
    # "Programdan çıkar" pencerenin ilk ekranında (eskiden ~900px aşağıdaydı).
    assert o["cikarUst"] < 360, o
    assert o["odak"] == "H2", o
    assert o["yontemAcik"] is False
