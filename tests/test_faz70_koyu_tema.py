"""Faz 70 — gece teması okunurluğu + kalan derslerde ulaşılamayan eşik sorusu.

Kullanıcı 24.09.2026: *"change dark theme it is less readable then light
theme"*. Kontrast ORANLARI iki temada yakındı; sorun algıdaydı: neredeyse
siyah zemin, sayfadan ayrılmayan kart, görünmeyen ince çizgi, koyu zeminde
soluk kalan küçük ikincil yazı. Bu test o dört ölçüyü sabitliyor — biri geri
kayarsa kırmızı.
"""
import json
import pathlib
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK / "tools"))
import ton_merdiveni as TM  # noqa: E402

from itucap import tasarim as T  # noqa: E402
from itucap import ui as UI  # noqa: E402

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")
G = T.palet("gece")


def _k(a, b):
    return TM.kontrast(TM.hex2rgb(G[a]), TM.hex2rgb(G[b]))


def _de(a, b):
    return TM.dE(TM.hex2rgb(G[a]), TM.hex2rgb(G[b]))


def test_GECE_ikincil_yazi_OKUNUR():
    # Eski: ink-2 6.95, ink-3 5.23 (kart üstünde). Gündüzde 7.65 / 5.62.
    assert _k("ink-2", "surface") >= 8.5
    assert _k("ink-3", "surface") >= 6.5
    assert _k("ink-3", "surface-2") >= 5.8


def test_GECE_katmanlar_AYRILIYOR():
    assert _de("surface", "ground") >= 0.036, "kart sayfadan ayrılmıyor"
    assert _k("border", "surface") >= 1.4, "ince çizgi kayboluyor"


def test_GECE_zemin_siyaha_yakin_DEGIL():
    L = TM.rgb2oklab(TM.hex2rgb(G["ground"]))[0]
    assert 0.22 <= L <= 0.30, L


def test_DANISMAN_sorusu_ayni_hesaptan():
    assert "const k = kalanGereken(h, g, ik);" in KAYNAK
    i = KAYNAK.index("function danismanSorulari(")
    f = KAYNAK[i:KAYNAK.index("\n}\n", i)]
  # Faz 112: özet yalnız DİLEKÇE gerektirenleri listeliyor (ulaşılamaz eşik
    # GNO panelinde gösteriliyor, danışman özetinde değil).
    assert "kalanGereken(" not in f


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
    print("ONCE:" + json.dumps(pg.evaluate("() => danismanSorulari().filter(s => s.includes('AA olsa'))")))
    # Aynı öğrenci, GNO çok düşük: 200 kredi, 0 puan → 2.00'a kalan 66 kredi yetmez.
    pg.evaluate("() => { DATA.gpa.credits = 200; DATA.gpa.points = 0; }")
    print("SONRA:" + json.dumps(pg.evaluate("() => danismanSorulari().filter(s => s.includes('AA olsa'))"), ensure_ascii=False))
    print("HATA:" + str(len(hatalar)) + " " + " | ".join(hatalar)[:300])
    b.close()
h.shutdown()
'''


def test_UCTAN_UCA_ulasilamaz_esik_danismana_soruluyor(tmp_path, monkeypatch):
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
    assert json.loads(c["ONCE"]) == [], "ulaşılabilir eşik için soru üretildi"
    sonra = json.loads(c["SONRA"])
    # 2.00 için: (2·(200−3+66) − 0)/66 > 4 → ulaşılamaz; en fazla 4·66/263 = 1.00.
  # Faz 112: özet yalnız DİLEKÇE gerektirenleri listeliyor.
    assert sonra == [], sonra
