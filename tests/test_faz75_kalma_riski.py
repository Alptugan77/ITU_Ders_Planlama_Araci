"""Faz 75 — kalma riski: "bu dersten kalırsam mezuniyetim ne kadar gecikir?"

Kullanıcı 24.09.2026: *"eklenebilecek çok işe yarar şeyleri düşün ve
ekleyebileceklerini ekle"*. Yol haritası bu dönemin programını geçilmiş
varsayıyordu; hangi dersin başarısızlığının bitişi ötelediğini söyleyen bir
yer yoktu. `/api/kalmariski` her ders için haritayı o ders çıkarılarak
yeniden kuruyor.
"""
import json
import pathlib
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import server as SRV
from itucap import ui as UI

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


def _js(ad):
    f = KAYNAK[KAYNAK.index(f"function {ad}("):]
    return f[:f.index("\n}\n")]


def test_UC_SALT_OKUNUR_ve_AYNI_GIRDI():
    assert "/api/kalmariski" in SRV.READ_ONLY_PATHS
    i = KAYNAK.index("def kalma_riski(")
    k = KAYNAK[i:KAYNAK.index("\ndef ", i + 1)]
    # Senaryo haritalarıyla AYNI girdi ve plan listesi (transkript kuralı dahil).
    assert "g = _harita_girdisi(con, ucon, student_id, settings, bu_donem, max_load)" in k
    assert "planlar, taban = _senaryo_planlari(con, settings, g)" in k
    assert '[y for y in g["bu"] if y["course"] != x["course"]]' in k
    # Bitişi bilinmeyen programda gecikme uydurulmuyor.
    assert '"delay": (sonra - once) if once is not None and sonra is not None else None' in k


def test_ARAYUZ():
    # Taban ızgaradaki program; sonuç program + sınır + durum sürümüne bağlı.
    assert "const ps = picks();" in _js("kalmaGirdi") and "bu: ps.map((p, i) =>" in _js("kalmaGirdi")
    assert "DURUM_SURUMU" in _js("kalmaAnahtari")
    assert "DURUM_SURUMU++;" in _js("applyState")
    # Yalnız yer tutucular yeniden doluyor (not senaryosunun odağı korunuyor).
    assert 'k.dataset.kalma === "ns" ? kalmaNsIcerik() : kalmaPanelIcerik()' in _js("kalmaCiz")
    assert '<div data-kalma="yh">${kalmaPanelIcerik()}</div>' in KAYNAK
    assert '<div class="nskalma" data-kalma="ns">${kalmaNsIcerik()}</div>' in KAYNAK
    assert "kalmaCiz();" in _js("render")
    # Kendiliğinden yalnız sonucun göründüğü yerde (yol haritası; FF seçilmiş not senaryosu).
    o = _js("kalmaOto")
    assert '(gor === "roadmapSection" || (gor === "creditSection" && ffVar))' in o
    assert "kalmaOto();" in _js("gorunumAc")


_CANLI = r'''
import sys, os, json
sys.path.insert(0, os.environ["ITUCAP_SRC"]); sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import vitrin
adres, h = vitrin.ac()
from itucap import server
st = server.State(label="ben")
R = st.snapshot()["roadmap"]
bu = [{"course": i["course"], "credits": i["credits"], "role": (i.get("roles") or [""])[0]}
      for i in R["terms"][0]["items"]]
k = st.dispatch("/api/kalmariski", {"bu": bu, "maxLoad": R["maxLoad"]})["kalmaRiski"]
print("API:" + json.dumps(k, ensure_ascii=False))
from playwright.sync_api import sync_playwright
T = "(s) => (document.querySelector(s)||{innerText:''}).innerText.replace(/\\s+/g,' ')"
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 1000})
    hatalar = []
    pg.on("pageerror", lambda e: hatalar.append(str(e)))
    pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(1000)
    # (1) Yol haritası görünümü açılınca kendiliğinden hesaplanıyor.
    pg.evaluate("() => gorunumAc('roadmapSection')"); pg.wait_for_timeout(1500)
    print("SONRA:" + pg.evaluate(T, "[data-kalma='yh']"))
    # (2) Başka görünümde program değişince HESAPLANMIYOR; eski sonuç gösterilmiyor.
    pg.evaluate("() => gorunumAc('schedSection')"); pg.wait_for_timeout(200)
    pg.evaluate("() => removeCourse('GEO 385E')"); pg.wait_for_timeout(800)
    print("GUNCEL:" + str(pg.evaluate("() => kalmaGuncel()")))
    print("YHDEG:" + pg.evaluate(T, "[data-kalma='yh']"))
    # (3) Not senaryosunda FF seçilince kendiliğinden hesaplanıyor; odak korunuyor.
    pg.evaluate("() => gorunumAc('creditSection')"); pg.wait_for_timeout(300)
    print("NSBOS:" + pg.evaluate(T, ".nskalma"))
    pg.select_option("select[data-ns='BLG 223E']", "FF"); pg.wait_for_timeout(1500)
    print("ODAK:" + str(pg.evaluate("() => document.activeElement.dataset.ns")))
    print("NS:" + pg.evaluate(T, ".nskalma"))
    print("GUNCEL2:" + str(pg.evaluate("() => kalmaGuncel()")))
    print("HATA:" + str(len(hatalar)) + " " + " | ".join(hatalar)[:300])
    pg.evaluate("() => localStorage.clear()")
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
    k = json.loads(c["API"])
    base = {b["role"]: b["finishSemester"] for b in k["base"]}
    assert base == {"ANADAL": 10, "CAP": 8}, base
    gec = {x["course"]: {p["role"]: p["delay"] for p in x["programs"]} for x in k["courses"]}
    assert len(gec) == 8
    # BLG 223E (Data Structures) ÇAP'ın kritik zincirinde: kalınırsa 2 dönem.
    assert gec["BLG 223E"] == {"ANADAL": 0, "CAP": 2}, gec
    assert all(v == {"ANADAL": 0, "CAP": 0} for d, v in gec.items() if d != "BLG 223E"), gec
    for parca in ("Kalma riski", "BLG 223E — ÇAP bitişi 2 dönem gecikir (2028-2029 Bahar)",
                  "anadal bitişini aşmadığından iki programın birlikte tamamlanacağı dönem değişmez",
                  "Diğer 7 dersten kalınması bitişi değiştirmemektedir",
                  "Taban: programdaki 8 dersin geçildiği varsayımı"):
        assert parca in c["SONRA"], (parca, c["SONRA"])
    assert c["GUNCEL"] == "False"
    assert "Program veya veriler değişmiştir" in c["YHDEG"] and "Yeniden hesapla" in c["YHDEG"]
    assert "dönem gecikir" not in c["YHDEG"]
    assert c["NSBOS"] == ""                       # FF seçilmeden satır yok
    assert c["ODAK"] == "BLG 223E"
    assert c["NS"].startswith("BLG 223E dersinden kalınırsa: anadal bitişi değişmez; "
                              "ÇAP bitişi 2 dönem gecikir"), c["NS"]
    assert c["GUNCEL2"] == "True"
