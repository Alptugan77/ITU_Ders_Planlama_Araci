"""Faz 139 — aday listesi: ders adı kodun yanında, süzgeç düğmeleri.

Kullanıcı (15.10.2026): *"continue developing and improving the site"*.
"Alınabilecek dersler" en çok kullanılan görünüm ve yeniden düzenleme
turlarında hiç ele alınmamıştı:

* dersin adı gerekçe satırının başında gri metindi ("Data Structures —
  kritik yolda — …"); öğrencinin tanıdığı şey en sönük yerdeydi;
* telefonda Plan sütunu gizli ve rol etiketi (ÇAP/ANADAL) hiçbir yerde
  görünmüyordu, yorum ise "rol zaten ders hücresinde" diyordu;
* telefonda gerekçe ~190px'lik sol sütuna sıkışıyordu;
* iki onay kutusu telefonda ayrı satırlar kaplıyordu.
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


def test_SATIR_ad_kodun_yaninda_gerekcede_yok():
    f = _fn("renderCandidates")
    assert '<span class="adayad">${esc(c.name)}</span>' in f
    assert '<span class="tag ${c.role} adayrol">' in f
    # Gerekçe satırı artık adla başlamıyor.
    assert '${esc(c.name)}${c.reasons.length' not in f
    # Ad, kod ile aynı satır kutusunda; gerekçeden önce.
    assert f.index('class="adaybas"') < f.index('class="adayad"') < f.index('<div class="why">')


def test_SUZGEC_dugmeleri_onay_kutusu_olarak_kaldi():
    # Görünüm düğme, öğe hâlâ onay kutusu: klavye ve ekran okuyucu aynı.
    assert '<label class="tickbox secim"><input type="checkbox" id="candFree">' in K
    assert '<label class="tickbox secim"><input type="checkbox" id="candFit">' in K
    assert ".candbar .tickbox.secim:has(input:checked)" in K


_CANLI = r'''
import sys, os, json
sys.path.insert(0, os.environ["ITUCAP_SRC"]); sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import vitrin
adres, h = vitrin.ac()
from playwright.sync_api import sync_playwright
OLC = """() => [...document.querySelectorAll('#cands tr[data-course]')].map(tr => {
  const r = s => { const e = tr.querySelector(s); if(!e) return null;
    const x = e.getBoundingClientRect(); return {top: x.top, w: x.width, h: x.height,
      gorunur: getComputedStyle(e).display !== 'none'}; };
  const c = DATA.candidates.find(x => x.course === tr.dataset.course) || {};
  return {kod: r('.adaybas>b'), ad: r('.adayad'), rol: r('.adayrol'), puan: r('td.score'),
          why: r('.why'), adMetin: (tr.querySelector('.adayad') || {}).textContent,
          beklenenAd: c.name || '', satirW: tr.getBoundingClientRect().width}; })"""
SUZ = """() => ['#candFree', '#candFit'].map(s => {
  const l = document.querySelector(s).closest('label').getBoundingClientRect();
  return {top: l.top, h: l.height}; })"""
with sync_playwright() as p:
    b = p.chromium.launch()
    hatalar = []
    for ad, vp, mob in (("masa", {"width": 1440, "height": 900}, False),
                        ("tel", {"width": 390, "height": 844}, True)):
        c = b.new_context(viewport=vp, is_mobile=mob, has_touch=mob)
        pg = c.new_page()
        pg.on("pageerror", lambda e: hatalar.append(str(e)))
        pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(800)
        pg.evaluate("() => gorunumAc('candSection')"); pg.wait_for_timeout(300)
        print(ad.upper() + ":" + json.dumps({"satir": pg.evaluate(OLC), "suz": pg.evaluate(SUZ)}))
        # Süzgeç düğmesi hâlâ süzüyor.
        once = pg.evaluate("() => document.querySelectorAll('#cands tr[data-course]').length")
        pg.click("label:has(#candFit)"); pg.wait_for_timeout(200)
        print(ad.upper() + "SUZ:" + json.dumps([once, pg.evaluate(
          "() => [document.querySelector('#candFit').checked, document.querySelectorAll('#cands tr[data-course]').length]")]))
        c.close()
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
    masa, tel = json.loads(c["MASA"]), json.loads(c["TEL"])
    assert len(masa["satir"]) >= 8
    for s in masa["satir"]:
        assert s["adMetin"] == s["beklenenAd"] and s["beklenenAd"], s
        # Masaüstünde ad kodla aynı satırda; rol kopyası gizli (Plan sütunu var).
        assert abs(s["ad"]["top"] + s["ad"]["h"] / 2 - s["kod"]["top"] - s["kod"]["h"] / 2) < 4, s
        assert not s["rol"]["gorunur"], s
    for s in tel["satir"]:
        # Telefonda rol etiketi görünüyor, puan kod satırının hizasında,
        # gerekçe satır genişliğinin çoğunu kullanıyor.
        assert s["rol"]["gorunur"], s
        assert abs(s["puan"]["top"] - s["kod"]["top"]) < 6, s
        if s["why"]:
            assert s["why"]["w"] > s["satirW"] * 0.8, s
    # Telefonda iki süzgeç düğmesi tek satırda, dokunma tabanında.
    a, b = tel["suz"]
    assert abs(a["top"] - b["top"]) < 2 and a["h"] >= 44 and b["h"] >= 44, tel["suz"]
    for k in ("MASASUZ", "TELSUZ"):
        once, (isaretli, sonra) = json.loads(c[k])
        assert isaretli and sonra <= once, c[k]
