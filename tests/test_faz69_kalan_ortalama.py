"""Faz 69 — eşikler için mezuniyete kadar KALAN BÜTÜN derslerde gereken ortalama.

Kullanıcı 24.09.2026: *"eşikler için gereken dönem ortalamasının dışında kalan
bütün derslerden gereken dönem ortalamasını da hesaplayıp gösterir misin"*.

* Kalan dersler yol haritasıyla AYNI kaynaktan (`YH._birimler`): ortak ders
  tek, havuz kendi kredisiyle (yoksa 3 VARSAYILIYOR ve bu yazıyor).
* Kalan derslerden daha önce notu olup geçilmemiş olan (FF) TEKRAR: eski
  notun kredisi/puanı ortalamadan düşüyor — bu dönemki hesapla aynı kural.
* Dönem kredi sınırı hedefi yalnız bu dönemin sonucuna bağlı: kalan-ders
  satırı ona gösterilmiyor.
"""
import json
import pathlib
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import student as S
from itucap import ui as UI
from test_ui import _collect, dbs  # noqa: F401

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


def _js(ad):
    f = KAYNAK[KAYNAK.index(f"function {ad}("):]
    return f[:f.index("\n}\n")]


def test_KALAN_TABAN_ortak_kaynak_ve_TEKRAR(dbs):
    con, ucon, sid = dbs
    for kod in ("GEO 303E", "BLG 212E", "BLG 351E", "SEC 201", "SEC 202", "SEC 203"):
        con.execute("UPDATE course SET credits=3 WHERE code=?", (kod,))
    con.commit()
    S.add_entries(ucon, sid, [S.make_entry("BLG 212E", "FF")])      # tekrar edilecek
    d = _collect(dbs)
    R = d["gpa"]["remaining"]
    # anadal: GEO 303E + ITB havuzu (planda kredi yok → 3 varsayıldı);
    # ÇAP: BLG 212E + BLG 351E.
    assert R["genel"]["credits"] == 12 and R["genel"]["courses"] == 4
    assert R["genel"]["pools"] == 1 and R["genel"]["poolAssumed"] == 1
    assert R["genel"]["retake"] == ["BLG 212E"]
    assert R["genel"]["retakeCredits"] == 3 and R["genel"]["retakePoints"] == 0
    assert R["ikinci"]["credits"] == 6 and R["ikinci"]["retake"] == ["BLG 212E"]


def test_ARAYUZ_hesabi_ve_KURALLAR():
    # Faz 70: hesap ortak yardımcıda (kalanGereken) — satır ve danışman
    # sorusu aynı sayıyı kullanıyor.
    k = _js("kalanGereken")
    assert "const T = R.credits, C = C0 - R.retakeCredits, P = P0 - R.retakePoints;" in k
    assert "x: (h.min * (C + T) - P) / T" in k
    assert "if(!R || h.donemlik) return null;" in k
    assert "const k = kalanGereken(h, g, ik);" in _js("kalanSatiri")
    assert "${kalanSatiri(h, g, ik)}" in _js("renderGnoHedef")
    h = _js("gnoHedefleri")
    assert 'krediye çıkması`, "genel", true);' in h
    assert "h0.donemlik = h0.donemlik && donemlik" in h
    assert "3 kredi varsayılmıştır" in _js("kalanNotu")


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
    pg.evaluate("() => gorunumAc('creditSection')"); pg.wait_for_timeout(300)
    satir = """() => [...document.querySelectorAll('#gnoHedefBody .gnosatir')].map(r =>
      [r.querySelector('span').innerText, (r.querySelector('.gnokalan')||{innerText:''}).innerText])"""
    print("SATIR:" + json.dumps(pg.evaluate(satir), ensure_ascii=False))
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
    s = {ad: kalan for ad, kalan in json.loads(c["SATIR"])}
    # Vitrin: GNO 2.78 (77 kredi, 214 puan); kalan 66 kredi, MAT 210E (FF) tekrar.
    # 2.50 için: (2.5·(74+66) − 214) / 66 = 2.06… → 2.07 (CC+).
    k = next(v for a, v in s.items() if a.startswith("2.50"))
    assert "(66 kredi)" in k and "en az 2.07" in k and "CC+" in k, k
    k = next(v for a, v in s.items() if a.startswith("2.00 — Mezuniyet"))
    assert "en az 1.00" in k, k
    k = next(v for a, v in s.items() if "ikinci anadal" in a)
    assert "(27 kredi)" in k and "en az 1.84" in k, k
    k = next(v for a, v in s.items() if "dönem sınırının" in a)
    assert k == "", "dönem sınırı hedefine kalan-ders satırı çizildi"
