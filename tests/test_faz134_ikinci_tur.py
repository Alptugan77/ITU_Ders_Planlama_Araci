"""Faz 134 — ikinci tur: rozet düğme değil, köşe kuralı her kutuda.

Kullanıcı (13.10.2026): *"continue improving ui/ux"*. Vitrin yeniden
gezildi (dokuz görünüm × masaüstü/telefon × iki tema):

* Aday satırındaki durum rozetleri tam renkli çerçeve ve 32px yükseklikle
  düğme gibi görünüyordu.
* Not senaryosunun seçimleri iki harflik not için satır genişliğindeydi.
* "en çok 25" sözcükleri sayıyla birlikte eş aralıklı yazıdaydı.
* Bitirme koşulunun göstergesi diğer göstergelerden geniş ve bir önceki
  bloğa yapışıktı.
* Yol haritasının dönem kutuları, program kartları, başvuru öğeleri ve
  "izle" düğmesi Faz 133'ün köşe kuralının dışındaydı (köşe 0).
"""
import json
import pathlib
import re
import subprocess
import sys
import tempfile

import pytest

from itucap import ui as UI

K = pathlib.Path(UI.__file__).read_text(encoding="utf-8")
_T = K[K.index("_TEMPLATE = r"):]
CSS = _T[_T.index("<style>"):_T.index("</style>")]
KATMAN = CSS[CSS.index("FAZ 134 — İKİNCİ TUR"):]


def test_ROZET_sonuk_cerceve_ve_basik():
    assert (".chip,.chip.online{padding:var(--sp-1) var(--sp-4);\n"
            "  border-color:color-mix(in oklab,currentColor 32%,transparent)}") in KATMAN


def test_NOT_SECIMI_icerik_genisliginde():
    assert ".nstablo select,.notsenaryo .nsust select{width:auto;" in KATMAN


def test_EN_COK_sozcukleri_es_aralikli_degil():
    assert '${L.min ? "" : "en çok "}<b class="mono"' in K
    assert '"en çok "}${L.max}</b>' not in K


def test_KATMAN_yalniz_jeton():
    govde = KATMAN[KATMAN.index("*/") + 2:]
    govde = re.sub(r"/\*.*?\*/", "", govde, flags=re.S)
    govde = govde[:govde.index("@media (prefers-reduced-motion")]
    assert not re.findall(r"#[0-9a-fA-F]{3,6}\b", govde)
    assert not re.findall(r"(?<![\w-])\d+px", govde)


_CANLI = r'''
import sys, os, json
sys.path.insert(0, os.environ["ITUCAP_SRC"]); sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import vitrin
adres, h = vitrin.ac()
from playwright.sync_api import sync_playwright
KOSE = """() => { const out = [];
  for(const el of document.querySelectorAll('body *')){
    const r = el.getBoundingClientRect(); if(r.width < 16 || r.height < 16) continue;
    if(['TD','TH','TR','TABLE','HR','I'].includes(el.tagName)) continue;
    const cs = getComputedStyle(el); if(cs.display === 'none') continue;
    const dort = ['Top','Right','Bottom','Left'].every(s =>
      parseFloat(cs['border' + s + 'Width']) > 0 && cs['border' + s + 'Style'] !== 'none');
    if(!dort) continue;
    if(parseFloat(cs.borderTopLeftRadius) > 0) continue;
    out.push(el.tagName + '.' + String(el.className).trim().replace(/\\s+/g, '.'));
  } return [...new Set(out)]; }"""
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    hatalar = []
    pg.on("pageerror", lambda e: hatalar.append(str(e)))
    pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(800)
    koseli = {}
    for g in vitrin.GORUNUMLER:
        pg.evaluate(f"() => gorunumAc && gorunumAc('{g}')"); pg.wait_for_timeout(200)
        k = pg.evaluate(KOSE)
        if k: koseli[g] = k
    print("KOSE:" + json.dumps(koseli))
    pg.evaluate("() => gorunumAc('candSection')"); pg.wait_for_timeout(200)
    print("ROZET:" + json.dumps(pg.evaluate("""() => {
      const c = document.querySelector('#cands .chip');
      return c ? c.getBoundingClientRect().height : null; }""")))
    pg.evaluate("() => gorunumAc('creditSection')"); pg.wait_for_timeout(200)
    print("NOT:" + json.dumps(pg.evaluate("""() => {
      const s = document.querySelector('.nstablo select');
      return s ? [s.getBoundingClientRect().width,
                  s.closest('table').getBoundingClientRect().width] : null; }""")))
    print("HATA:" + str(len(hatalar)) + " " + " | ".join(hatalar)[:300])
    b.close()
h.shutdown()
'''


def test_UCTAN_UCA_vitrin(tmp_path, monkeypatch):
    try:
        import playwright  # noqa: F401
    except ImportError:
        pytest.skip("playwright yok")
    kok = pathlib.Path(UI.__file__).resolve().parents[2]
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
    # Çerçeveli her kutu yuvarlak köşeli (tablo hücreleri ve lejant örnekleri hariç).
    assert json.loads(c["KOSE"]) == {}, c["KOSE"]
    # Rozet düğme yüksekliğinde (34px) değil.
    yuk = json.loads(c["ROZET"])
    assert yuk is not None and yuk < 26, yuk
    # Not seçimi tablonun dörtte birinden dar.
    s, t = json.loads(c["NOT"])
    assert s < t / 4, (s, t)
