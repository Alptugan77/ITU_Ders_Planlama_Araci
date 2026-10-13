"""Faz 138 — alınamayan dersler: kartta dersin adı, gereksiz tekrar yok.

Kullanıcı (13.10.2026): *"continue"*. "Alınamayan dersler" görünümünde:

* kartta yalnız kod vardı ("BLG 336E"); dersin adı veride (`name`) olduğu
  hâlde gösterilmiyordu;
* "bu dönem açılmamış" grubundaki HER kart "bu dönem şube açılmamıştır"
  diyordu: grubun etiketini dört kez tekrar;
* "izle" düğmesi metnin altına kayıyordu.
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


def test_KART_ad_ve_tekrarsiz_aciklama():
    f = _fn("renderBlockers")
    assert '${b.name ? `<div class="enad">${esc(b.name)}</div>` : ""}' in f
    assert 'const tekrar = k === "ACILMAMIS" && b.detail === "bu dönem şube açılmamıştır";' in f
    # Düğme kodun satırında (ad ve açıklamadan önce).
    assert f.index('<button class="watchmini"') < f.index('class="enad"')


def test_TEKRAR_metni_motorla_ayni():
    # Gizlenen metin motorun ACILMAMIS açıklamasıyla birebir; motor metni
    # değişirse tekrar yeniden görünür, sessizce bilgi kaybolmaz.
    m = (KOK / "src" / "itucap" / "recommend.py").read_text(encoding="utf-8")
    assert '"ACILMAMIS", "bu dönem şube açılmamıştır")' in m


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
    pg.evaluate("() => gorunumAc('blockSection')"); pg.wait_for_timeout(400)
    print("OUT:" + json.dumps(pg.evaluate("""() => [...document.querySelectorAll('#blockers .blockitem')].map(e => {
      const d = e.querySelector('.watchmini'), k = e.querySelector('.enust b');
      return {metin: e.innerText.replace(/\\s+/g, ' '),
              ad: (DATA.blockers.find(x => x.course === k.textContent) || {}).name || '',
              dugmeHiza: d ? Math.abs(d.getBoundingClientRect().top + d.offsetHeight / 2
                - (k.getBoundingClientRect().top + k.offsetHeight / 2)) : null}; })"""), ensure_ascii=False))
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
    kartlar = json.loads(c["OUT"])
    assert len(kartlar) >= 4
    for k in kartlar:
        assert k["ad"] and k["ad"] in k["metin"], k
        assert "bu dönem şube açılmamıştır" not in k["metin"], k
        if k["dugmeHiza"] is not None:
            assert k["dugmeHiza"] < 6, k
    # Önşart grubunda açıklama duruyor (bilgi taşıyor).
    assert any("eksik:" in k["metin"] for k in kartlar)
