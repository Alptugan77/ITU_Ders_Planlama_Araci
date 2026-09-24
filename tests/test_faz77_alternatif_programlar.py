"""Faz 77 — alternatif programlar (Plan B, Plan C…).

Kullanıcı 24.09.2026: *"eklenebilecek çok işe yarar şeyleri düşün ve
ekleyebileceklerini ekle"*. Araç dönem başına tek program saklıyordu; kayıt
gününde bir şube dolunca çoğu zaman bütün program değişiyor. Alternatifler
adlarıyla kullanıcı veritabanında; ana program dokunulmadan duruyor.
"""
import json
import pathlib
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import db
from itucap import server as SRV
from itucap import student as S
from itucap import ui as UI

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


@pytest.fixture
def u(tmp_path):
    con = db.connect(tmp_path / "u.sqlite3", "schema_user.sql")
    return con, S.ensure_student(con, "ben")


def test_KAYDET_OKU_SIL(u):
    con, sid = u
    S.save_picks(con, sid, "202710", [("GEO 331E", "1")])
    assert S.save_alt(con, sid, "202710", "  Plan   B ", [("blg 223e", "10"), ("GEO 331E", "11"),
                                                          ("", "5"), ("X 1", "")]) == "Plan B"
    a = S.load_alts(con, sid, "202710")
    assert [x["name"] for x in a] == ["Plan B"]
    assert a[0]["picks"] == [{"course": "BLG 223E", "crn": "10"}, {"course": "GEO 331E", "crn": "11"}]
    # Ana program değişmedi; başka dönem ayrı.
    assert S.load_picks(con, sid, "202710")["picks"] == [{"course": "GEO 331E", "crn": "1"}]
    assert S.load_alts(con, sid, "202720") == []
    # Aynı ad → üzerine.
    S.save_alt(con, sid, "202710", "Plan B", [("MAT 210E", "7")])
    assert S.load_alts(con, sid, "202710")[0]["picks"] == [{"course": "MAT 210E", "crn": "7"}]
    assert S.delete_alt(con, sid, "202710", "Plan B") == 1
    assert S.load_alts(con, sid, "202710") == []


def test_SINIR_ve_RED(u):
    con, sid = u
    for i in range(S.ALT_MAX):
        S.save_alt(con, sid, "202710", f"P{i}", [("X 1", "1")])
    with pytest.raises(ValueError, match="en çok 5 alternatif"):
        S.save_alt(con, sid, "202710", "fazla", [("X 1", "1")])
    S.save_alt(con, sid, "202710", "P0", [("Y 2", "2")])       # var olanın üzerine: izin
    with pytest.raises(ValueError, match="adı boş"):
        S.save_alt(con, sid, "202710", "   ", [("X 1", "1")])
    with pytest.raises(ValueError, match="programda ders bulunmadığından"):
        S.save_alt(con, sid, "202710", "P1", [("", "1")])
    assert len(S.load_alts(con, sid, "202710")) == S.ALT_MAX


def test_UC_YAZAN_UC():
    """Alternatif kaydetmek durumu DEĞİŞTİRİYOR — salt okunur listede olamaz."""
    assert "/api/alternatif" not in SRV.READ_ONLY_PATHS
    assert "/api/alternatif/sil" not in SRV.READ_ONLY_PATHS


_CANLI = r'''
import sys, os, json
sys.path.insert(0, os.environ["ITUCAP_SRC"]); sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import vitrin
adres, h = vitrin.ac()
from playwright.sync_api import sync_playwright
T = "(s) => (document.querySelector(s)||{innerText:''}).innerText.replace(/\\s+/g,' ')"
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 1000})
    hatalar = []
    pg.on("pageerror", lambda e: hatalar.append(str(e)))
    pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(1000)
    ana = pg.evaluate("() => JSON.stringify(DATA.savedPicks)")
    print("GORUNUR:" + str(pg.evaluate("() => !document.querySelector('#altKaydet').hidden")))
    pg.click("#altKaydet"); pg.wait_for_timeout(300)
    print("ONERI1:" + pg.evaluate("() => document.querySelector('#altAd').value"))
    pg.click("#altKaydetOk"); pg.wait_for_timeout(3000)
    pg.evaluate("() => removeCourse('BLG 252E')"); pg.wait_for_timeout(200)
    pg.click("#altKaydet"); pg.wait_for_timeout(300)
    print("ONERI2:" + pg.evaluate("() => document.querySelector('#altAd').value"))
    pg.click("#altKaydetOk"); pg.wait_for_timeout(3000)
    print("ANA:" + str(pg.evaluate("() => JSON.stringify(DATA.savedPicks)") == ana))
    print("ALTS:" + json.dumps(pg.evaluate("() => DATA.alternatives.map(a => [a.name, a.picks.length])")))
    pg.evaluate("() => gorunumAc('savedSection')"); pg.wait_for_timeout(300)
    # textContent: CSS büyük harfi (text-transform) uygulanmamış metin.
    print("LISTE:" + pg.evaluate("() => document.querySelector('#altList').textContent.replace(/\\s+/g,' ')"))
    pg.click("[data-altyukle='0']"); pg.wait_for_timeout(400)
    print("YUK:" + json.dumps(pg.evaluate("() => sel.map(x => x.course)")))
    pg.evaluate("() => geriAl()"); pg.wait_for_timeout(200)
    print("GERI:" + str(len(pg.evaluate("() => sel"))))
    pg.evaluate("() => crnDialog()"); pg.wait_for_timeout(300)
    print("KG:" + pg.evaluate("() => document.querySelector('#detail').textContent.replace(/\\s+/g,' ')"))
    pg.evaluate("() => document.querySelector('#detail').close()")
    # Boş ad: sunucu reddediyor, pencere açık kalıyor ve nedeni yazıyor.
    pg.click("#altKaydet"); pg.wait_for_timeout(300)
    pg.fill("#altAd", "   "); pg.click("#altKaydetOk"); pg.wait_for_timeout(2000)
    print("RED:" + pg.evaluate(T, "#altDurum"))
    pg.evaluate("() => document.querySelector('#detail').close()")
    pg.evaluate("() => gorunumAc('savedSection')"); pg.wait_for_timeout(300)
    pg.click("[data-altsil='1']"); pg.wait_for_timeout(200)
    print("ONAY:" + str(pg.evaluate("() => DATA.alternatives.length")))
    pg.click("[data-altsil='1']"); pg.wait_for_timeout(3000)
    print("SIL:" + json.dumps(pg.evaluate("() => DATA.alternatives.map(a => a.name)")))
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
    assert c["GORUNUR"] == "True"
    assert c["ONERI1"] == "Plan B" and c["ONERI2"] == "Plan C"
    assert c["ANA"] == "True"                       # ana program dokunulmadı
    assert json.loads(c["ALTS"]) == [["Plan B", 8], ["Plan C", 7]]
    for parca in ("Alternatif programlar", "2 / 5", "Plan B", "8 ders · 24 kredi",
                  "4 gün kampüste (Pzt Sal Çar Per)", "08:30–16:29", "dolu: GEO 331E",
                  "Plan C", "ızgarada", "7 ders · 21 kredi"):
        assert parca in c["LISTE"], (parca, c["LISTE"])
    assert "BLG 252E" in json.loads(c["YUK"]) and len(json.loads(c["YUK"])) == 8
    assert c["GERI"] == "7"                          # yükleme geri alınabiliyor
    assert "Alternatif programlar (2)" in c["KG"]
    assert "Plan B · 8 ders · 24 kredi" in c["KG"]
    assert "adı boş olamaz" in c["RED"]
    assert c["ONAY"] == "2"                          # ilk dokunuş silmiyor
    assert json.loads(c["SIL"]) == ["Plan B"]
