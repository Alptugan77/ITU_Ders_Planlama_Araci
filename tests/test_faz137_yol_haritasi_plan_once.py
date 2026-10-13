"""Faz 137 — yol haritası: plan öne, varsayımların özü açık, tamamı katlı.

Kullanıcı (13.10.2026): *"continue"* (arayüz ve kullanım iyileştirmesine
devam). Yol haritası ölçüldü (vitrin öğrencisi):

* Dönem planı masaüstünde 1555px, telefonda 3057px aşağıdaydı: bitiş
  kartlarından sonra yaz okulu, kalma riski ve 10 maddelik varsayım listesi
  geliyordu.
* "geçmişte" açıklaması gövde boyunda (sınıfı biçimsiz `.meta`) planın
  başlığından daha iri duruyordu.
* 6 dönem 4 + 2 diziliyordu (ikinci satırda iki yetim kart).

Faz 57'nin kuralı korunuyor: varsayımlar planın ÜSTÜNDE. Değişen,
listenin tamamının katlanması; özü (plan bir tahmindir, ilk denemede geçme,
dönem kredi sınırı, kontenjan ve yaz okulu yok) ve ⚠ uyarılar açık.
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


def test_SIRA_plan_yaz_ve_kalmadan_once():
    f = _fn("renderRoadmap")
    son = f.rindex("body.innerHTML = `")
    sira = f[son:f.index("`;", son)]
    i = [sira.index(x) for x in ("simdi}", "${varsayim}", "${donemler}", "${kalan}",
                                 "${yaz}", "${kalmaPanelIcerik()}")]
    assert i == sorted(i), i


def test_VARSAYIM_ozu_acik_tamami_katli():
    f = _fn("renderRoadmap")
    assert '<b>Bu plan bir tahmindir.</b>' in f
    assert 'tumV.filter(a => a.startsWith("⚠"))' in f
    assert '<details class="yhvtum"><summary>Hesaplama varsayımları (${tumV.length})</summary>' in f


def test_OZ_motorun_her_zaman_dondurdugu_maddeler():
    # Açıktaki özet uydurma değil: motorun koşulsuz maddelerinde var.
    m = (KOK / "src" / "itucap" / "yolharitasi.py").read_text(encoding="utf-8")
    i = m.index("    varsayimlar = [")
    temel = m[i:m.index("    ]\n", i)]
    for parca in ("ilk denemede başarıyla tamamlanacağı",
                  "Her dönem en fazla {max_load:g} kredi",
                  "Kontenjan dikkate alınmamıştır. Yaz okulu hesaba katılmamıştır."):
        assert parca in temel, parca


def test_SUTUN_dengeli():
    f = _fn("renderRoadmap")
    assert "Math.ceil(nD / Math.ceil(nD / m))" in f
    assert 'style="--yhkol4:${kol(4)};--yhkol3:${kol(3)}"' in f
    assert "#roadmapBody{container-type:inline-size}" in K


_CANLI = r'''
import sys, os, json
sys.path.insert(0, os.environ["ITUCAP_SRC"]); sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import vitrin
adres, h = vitrin.ac()
from playwright.sync_api import sync_playwright
OLC = """() => { const b = document.querySelector('#roadmapBody'), g = b.querySelector('.yhdonemler');
  const v = b.querySelector('.yhvarsayim'), t = v.querySelector('.yhvtum');
  return {planUst: Math.round(g.getBoundingClientRect().top + scrollY),
          kolon: getComputedStyle(g).gridTemplateColumns.split(' ').length,
          donem: g.children.length,
          acik: v.innerText.replace(/\\s+/g, ' '),
          ozet: t.querySelector('summary').textContent.trim(), katli: !t.open,
          varsayimSay: DATA.roadmap.assumptions.length, maxLoad: DATA.roadmap.maxLoad,
          uyari: DATA.roadmap.assumptions.filter(a => a.startsWith('⚠')),
          baslik: [...b.querySelectorAll('h3.yhbolum')].map(e => e.textContent.trim()),
          notBoy: parseFloat(getComputedStyle(b.querySelector('.yhgecmisnot')).fontSize),
          govdeBoy: parseFloat(getComputedStyle(document.body).fontSize)}; }"""
with sync_playwright() as p:
    b = p.chromium.launch()
    out = {}
    hatalar = []
    for ad, vp, mob in (("masaustu", {"width": 1440, "height": 900}, False),
                        ("telefon", {"width": 390, "height": 844}, True)):
        ctx = b.new_context(viewport=vp, is_mobile=mob, has_touch=mob, color_scheme="light")
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: hatalar.append(str(e)))
        pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(900)
        pg.evaluate("() => gorunumAc('roadmapSection')"); pg.wait_for_timeout(600)
        out[ad] = pg.evaluate(OLC)
        ctx.close()
    print("OUT:" + json.dumps(out, ensure_ascii=False))
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
    m, t = o["masaustu"], o["telefon"]
    # Plan yukarıda (önce: masaüstü 1555px, telefon 3057px).
    assert m["planUst"] < 1200 and t["planUst"] < 2100, (m["planUst"], t["planUst"])
    # 6 dönem 4 + 2 değil 3 + 3.
    assert m["donem"] == 6 and m["kolon"] == 3, m
    assert t["kolon"] == 1
    # Özet açık ve doğru sınırı söylüyor; tamamı katlı ama sayısı yazıyor.
    assert "Bu plan bir tahmindir." in m["acik"] and f"en çok {m['maxLoad']} kredi" in m["acik"]
    assert m["katli"] and m["ozet"] == f"Hesaplama varsayımları ({m['varsayimSay']})"
    # ⚠ uyarılar katlanmıyor (vitrinde mevsimi bilinmeyen dersler var).
    assert m["uyari"] and all(u[:40] in m["acik"] for u in m["uyari"])
    # Katlı maddeler görünür metinde değil.
    assert "Seçmeli havuzdan" not in m["acik"]
    assert m["baslik"] == ["Dönem planı", "Bitişi değiştirebilecek durumlar"]
    # "geçmişte" notu artık gövdeden küçük.
    assert m["notBoy"] < m["govdeBoy"], m
