"""Faz 135 — yeni simge; program resminde önizleme, tema ve telefon biçimi.

Kullanıcı (13.10.2026): *"also can you improve the icon and save as png
part"*.

* Simge 3×3 eşit kare ızgaraydı; ders programı değil, tablo gibi okunuyordu.
  Artık üç gün sütununda farklı boyda, köşeli değil yuvarlak bloklar.
* "Resim (PNG)" doğrudan indiriyordu: önizleme yok, tema hep ekranınki,
  biçim hep yatay (telefonda paylaşınca okunmuyor). Artık bir pencere:
  önizleme, Açık/Koyu, Geniş/Telefon, İndir ve (destekleyen tarayıcıda)
  Paylaş.
* Resimde çevrimiçi dersin bloğu saydamdı (ızgara çizgileri içinden
  geçiyordu); bloklar köşesizdi; renk açıklaması yoktu.
* Koyu resimde bloklar açık temanın renginde çıkıyordu: Faz 133'ün renk
  geçişi sürerken hesaplanmış renk geçişin başındaki değer.
"""
import importlib
import json
import pathlib
import subprocess
import sys
import tempfile

import pytest

from itucap import ui as UI

KOK = pathlib.Path(UI.__file__).resolve().parents[2]
K = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


def _uretici():
    sys.path.insert(0, str(KOK / "tools"))
    try:
        return importlib.import_module("simge_uret")
    finally:
        sys.path.pop(0)


def _resim():
    i = K.index("async function resimIndir(")
    return K[i:K.index("\n}\n", i)]


def test_SIMGE_kademeli_bloklar_ve_yuvarlak():
    U = _uretici()
    renk = {U.ANADAL: "anadal", U.CAP: "cap", U.BEYAZ: "beyaz", U.SOLUK: "bos"}
    # Resmin köşesindeki küçük simge uygulama simgesiyle AYNI geometri.
    assert [(s, u, a, renk[r]) for s, u, a, r in U.BLOKLAR] == \
        [tuple(x) for x in UI.SIMGE_BLOKLAR]
    assert UI.simge_renkleri()["zemin"] == U.SEAL
    # Sütunlarda farklı boy: eşit kare ızgara değil.
    assert len({a - u for _, u, a, _ in U.BLOKLAR}) >= 4
    assert 'rx="' in U.svg()


def test_RESIM_tema_bicim_ve_pencere():
    r = _resim()
    assert 'kokEl.classList.add("gecissiz")' in r and 'kokEl.classList.remove("gecissiz")' in r
    assert r.index('classList.add("gecissiz")') < r.index("getComputedStyle(kokEl)")
    assert 'const dikey = opt.bicim === "dikey";' in r
    assert "if(opt.onizleme) return tuval;" in r
    assert "navigator.share({files: [dosya]" in r
    assert "if(png) png.onclick = resimDialog;" in K
    assert ".gecissiz .blk{transition:none!important}" in K


_CANLI = r'''
import sys, os, json
sys.path.insert(0, os.environ["ITUCAP_SRC"]); sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import vitrin
adres, h = vitrin.ac()
from playwright.sync_api import sync_playwright
OLC = """async (o) => { const t = await resimIndir(Object.assign({onizleme: true}, o));
  const c = t.getContext('2d');
  // Çevrimiçi blok (Pzt 15:30) içinden bir nokta ve zemin.
  const nokta = (x, y) => [...c.getImageData(x * 2, y * 2, 1, 1).data].slice(0, 3);
  return {g: t.width, y: t.height, zemin: nokta(3, 3)}; }"""
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1400, "height": 1000}, color_scheme="light",
                        accept_downloads=True)
    pg = ctx.new_page()
    hatalar = []
    pg.on("pageerror", lambda e: hatalar.append(str(e)))
    pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(900)
    out = {}
    for tema in ("light", "dark"):
        for bicim in ("yatay", "dikey"):
            out[tema + bicim] = pg.evaluate(OLC, {"tema": tema, "bicim": bicim})
    # Koyu ölçümün ardından sayfa açık temada kaldı; blok rengi açık temanın.
    out["sayfaTema"] = pg.evaluate("() => document.documentElement.getAttribute('data-theme')")
    out["blokRenk"] = pg.evaluate("() => getComputedStyle(document.querySelector('#grid .blk:not(.online)')).backgroundColor")
    # Koyu resimdeki bir ders bloğunun dolgusu koyu (açık temanın rengi değil).
    out["koyuBlok"] = pg.evaluate("""async () => { const t = await resimIndir({tema: 'dark', onizleme: true});
      const c = t.getContext('2d'); const d = c.getImageData(300, 600, 1, 1).data;
      return [d[0], d[1], d[2]]; }""")
    pg.click("#pngBtn"); pg.wait_for_timeout(800)
    out["onizleme"] = pg.evaluate("() => !!document.querySelector('#resimOnizleme img')")
    out["secenek"] = pg.evaluate("() => [...document.querySelectorAll('[data-resim-tema],[data-resim-bicim]')].map(b => b.textContent.trim())")
    out["tekSatir"] = pg.evaluate("""() => [...document.querySelectorAll('[data-resim-bicim]')]
      .every(b => b.getBoundingClientRect().height < 44)""")
    pg.click("[data-resim-bicim=dikey]"); pg.wait_for_timeout(500)
    with pg.expect_download() as d:
        pg.click("#resimKaydet")
    out["dosya"] = d.value.suggested_filename
    print("OUT:" + json.dumps(out))
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
    # Telefon biçimi dar ve uzun; geniş biçim yatay.
    assert o["lightdikey"]["g"] < o["lightdikey"]["y"]
    assert o["lightyatay"]["g"] > o["lightyatay"]["y"]
    # Tema zemini: açık resim açık, koyu resim koyu.
    assert sum(o["lightyatay"]["zemin"]) > 600 and sum(o["darkyatay"]["zemin"]) < 150
    # Koyu resimdeki ders bloğu koyu (geçişin başındaki açık renk değil).
    assert sum(o["koyuBlok"]) < 360, o["koyuBlok"]
    # Ölçüm ekrandaki temayı değiştirmedi.
    assert o["sayfaTema"] is None
    # Hesaplanmış renk oklab(L a b): açık temada blok açık (L > 0,7).
    assert o["blokRenk"].startswith("oklab(") and float(o["blokRenk"][6:].split()[0]) > 0.7, o["blokRenk"]
    assert o["onizleme"] is True
    assert o["secenek"] == ["Açık", "Koyu", "Geniş", "Telefon"]
    assert o["tekSatir"] is True
    assert o["dosya"] == "ders-programi-telefon.png"
