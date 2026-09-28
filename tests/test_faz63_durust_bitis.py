"""Faz 63 — yol haritası bilmediği bitişi göstermiyor.

Kullanıcı 24.09.2026: *"continue on your improvements and additions"*.
Gerçek katalogla 127 anadal programının hepsi kuruldu (`docs/faz63-…`):

* 2+. yarıyılda olduğunu söyleyip geçtiğin dersleri girmeyene harita planın
  TAMAMINI kalan sayıyordu → "13. yarıyılda bitersin, azami süreyi aşıyorsun".
  Artık harita kurulmuyor (sayfadaki de, istek üzerine kurulanlar da); yerine
  "Dersleri gir" ve danışmana bir soru.
* 20 UOLP (ortak lisans) programının planı yalnız İTÜ'deki dönemleri içeriyor
  (BES 3.–6., CES 5.–8. yarıyıl); "son İTÜ dersi" mezuniyet gibi yazılıyordu.
"""
import json
import pathlib
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import db
from itucap import prereq as P
from itucap import ui as UI
from itucap import yolharitasi as YH

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


def _js(ad):
    f = KAYNAK[KAYNAK.index(f"function {ad}("):]
    return f[:f.index("\n}\n")]


def _katalog(tmp_path, ad):
    con = db.connect(tmp_path / "ref.sqlite3", "schema.sql")
    con.execute("INSERT INTO program(code,name,level) VALUES ('AAA',?,'LS')", (ad,))
    for kod in ("XXX 101", "YYY 102"):
        con.execute("INSERT INTO course(code,name,credits,ects) VALUES (?,?,3,5)",
                    (kod, "Ders " + kod))
    con.execute("INSERT INTO plan(id,program_code,plan_type,title,source)"
                " VALUES (1,'AAA','lisans','x','obs')")
    for i, (kod, d) in enumerate((("XXX 101", 5), ("YYY 102", 6))):
        con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,credits,position,"
                    "term_no) VALUES (1,'REQUIRED',?,3,?,?)", (kod, i, d))
    P.parse_all(con)
    con.commit()
    return con


def _kur(con):
    return YH.kur(con, {}, [{"planId": 1, "role": "ANADAL", "label": "anadal",
                             "program": "AAA"}],
                  term="202610", donem=5, max_load=21, bu_donem=[])


# ------------------------------------------------------------------ UOLP
def test_UOLP_bitis_TAHMIN_EDILMIYOR(tmp_path):
    h = _kur(_katalog(tmp_path, "Bilgisayar Mühendisliği (İngilizce) UOLP (Saraybosna-IUS)"))
    p = h["programs"][0]
    assert p["jointDegree"] == "Saraybosna-IUS"
    assert p["finish"] is None and p["nominal"] is None and p["finishSemester"] is None
    # Dersler yine yerleşiyor (sıra işe yarıyor), yalnız bitiş yazılmıyor.
    assert p["unplaced"] == 0 and p["remaining"] == 2
    assert any("Ortak program (UOLP · Saraybosna-IUS)" in a and "bitiş tahmini yapılmamıştır" in a
               for a in h["assumptions"])


def test_OLAGAN_program_ETKILENMIYOR(tmp_path):
    h = _kur(_katalog(tmp_path, "Bilgisayar Mühendisliği (İngilizce)"))
    p = h["programs"][0]
    assert p["jointDegree"] is None and p["finish"] is not None
    assert p["finishSemester"] and p["nominal"] is not None
    assert not any("UOLP" in a for a in h["assumptions"])


def test_UOLP_arayuzde_yaziyor():
    r = _js("renderRoadmap")
    assert 'p.jointDegree ? "tahmin edilmedi" : "hesaplanamadı"' in r
    assert "ortak üniversitedeki dönemler veride bulunmamaktadır" in r
    assert "tahmin edilmedi — ortak program" in _js("danismanOzeti")
  # Faz 112: özet yalnız DİLEKÇE gerektirenleri listeliyor.
    assert "Ortak lisans programına kayıtlıyım" not in _js("danismanSorulari")


# ------------------------------------------------------------------ transkript
def test_TRANSKRIPT_KURALI():
    e = UI._transkript_eksik
    assert e(1, {}) is False          # 1. yarıyılda boş transkript doğru
    assert e(0, {}) is False          # dönem bilinmiyor: eski davranış
    assert e(2, {}) is True
    assert e(5, {"MAT 103": "FF", "FIZ 101": "VF"}) is True   # geçilmiş ders yok
    assert e(5, {"MAT 103": "CC"}) is False


def test_TEK_KURAL_uc_yerde():
    i = KAYNAK.index("def _yol_haritasi(")
    k = KAYNAK[i:KAYNAK.index("\ndef ", i + 1)]
    assert "if _transkript_eksik(donem, grades):" in k
    j = KAYNAK.index("def _harita_girdisi(")
    g = KAYNAK[j:KAYNAK.index("\ndef ", j + 1)]
    assert "if _transkript_eksik(int(settings.donem or 0), grades):" in g
    # Arayüz: harita dalı R'yi kullanmadan önce dönüyor; ÇAP bitiş sütunu ve
    # özet de bu durumu biliyor.
    r = _js("renderRoadmap")
    assert r.index("if(T.noTranscript){") < r.index("const R = (YH_SENARYO")
    assert "!R.noTranscript" in _js("capBitisHesaplanabilir")
    assert "!R.noTranscript" in _js("danismanOzeti")


# ------------------------------------------------------------------ uçtan uca (vitrin)
_CANLI = r'''
import sys, os, json
sys.path.insert(0, os.environ["ITUCAP_SRC"]); sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import vitrin
adres, h = vitrin.ac()
from itucap import server, config, db
u = db.connect(config.USER_DB, "schema_user.sql")
u.execute("DELETE FROM earned_course"); u.commit(); u.close()
st = server.State(label="ben")
print("R:" + json.dumps(st.snapshot()["roadmap"]))
for yol, govde in (("/api/yolharitasi", {"bu": [], "maxLoad": 25, "bos": []}),
                   ("/api/capbitis", {"plans": [], "bu": [], "maxLoad": 25})):
    try:
        st.dispatch(yol, govde); print("RED:yok")
    except ValueError as e:
        print("RED:" + str(e))
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 1000})
    hatalar = []
    pg.on("pageerror", lambda e: hatalar.append(str(e)))
    pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(1200)
    pg.evaluate("() => gorunumAc('roadmapSection')"); pg.wait_for_timeout(300)
    print("YH:" + pg.evaluate("() => document.querySelector('#roadmapBody').innerText.replace(/\\s+/g,' ')"))
    pg.click("#roadmapBody [data-setup]"); pg.wait_for_timeout(400)
    print("DLG:" + pg.evaluate("() => (document.querySelector('dialog[open]')||{id:'yok'}).id"))
    pg.keyboard.press("Escape")
    pg.evaluate("() => gorunumAc('schedSection')")
    pg.click("#danismanBtn"); pg.wait_for_timeout(400)
    print("SORU:" + json.dumps(pg.evaluate("() => [...document.querySelectorAll('#detail .dsoru li')].map(e => e.innerText.replace(/\\s+/g,' '))"), ensure_ascii=False))
    print("BITIS:" + str(pg.evaluate("() => /Tahmini bitiş/i.test(document.querySelector('#detail').innerText)")))
    print("CAPB:" + str(pg.evaluate("() => capBitisHesaplanabilir()")))
    print("HATA:" + str(len(hatalar)) + " " + " | ".join(hatalar)[:300])
    b.close()
h.shutdown()
'''


def test_UCTAN_UCA_transkriptsiz_vitrin(tmp_path, monkeypatch):
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
    satirlar = [s for s in r.stdout.strip().splitlines() if ":" in s]
    red = [s.split(":", 1)[1] for s in satirlar if s.startswith("RED:")]
    c = dict(s.split(":", 1) for s in satirlar if s.split(":", 1)[0].isupper())
    assert c["HATA"].startswith("0"), c["HATA"]
    assert json.loads(c["R"]) == {"noTranscript": True, "donem": 5}
    assert red == ["başarılan dersler girilmediği için bitiş tahmini yapılamıyor"] * 2, red
    assert c["YH"].startswith("Bitiş tahmini yapılamamaktadır. 5. yarıyılda"), c["YH"]
    assert "Dersleri girin" in c["YH"] and "yarıyılında" not in c["YH"]
    assert c["DLG"] == "setup"
    soru = json.loads(c["SORU"])
  # Faz 112: özet yalnız DİLEKÇE gerektirenleri listeliyor.
    assert not any(s.startswith("Başarılı olduğum dersleri araca girmedim") for s in soru), soru
    assert not any("tahmini bitişim" in s or "azami süre" in s for s in soru), soru
    assert c["BITIS"] == "False" and c["CAPB"] == "False"
