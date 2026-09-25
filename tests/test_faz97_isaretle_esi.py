"""Faz 97 — "Plandan işaretle" İngilizce eşiyle karşılanmış ÇAP dersini söylüyor.

Kullanıcı 25.09.2026: kılavuzun ikinci adımı artık "Plandan işaretle"; o
pencereyi ÇAP öğrencisi olarak açınca bulundu. Faz 92'den beri EHB 222E
(anadal, geçilmiş) ÇAP'ın EHB 222 slotunu dolduruyor ve ilerleme paneli
"tamam" diyor; ama bu pencere EHB 222'yi BOŞ gösteriyordu. Öğrenci düzeltmek
için tiklerse transkripte notsuz (DD sayılan) ikinci bir ders ekleniyor ve
GNO bozuluyordu.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import config, db, ui as UI


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


@pytest.fixture()
def state(tmp_path, monkeypatch):
    from itucap import server as SRV
    monkeypatch.setattr(config, "REF_DB", tmp_path / "r.sqlite3")
    monkeypatch.setattr(config, "USER_DB", tmp_path / "u.sqlite3")
    monkeypatch.setattr(config.Settings, "load", classmethod(lambda cls, path=None: config.Settings(
        anadal_program="BLGE", cap_program="EHB", second_kind="cap",
        program_codes=["BLGE", "EHB"], term="202610")))
    con = db.connect(tmp_path / "r.sqlite3", "schema.sql")
    con.executemany("INSERT INTO course(code,name,credits,ects) VALUES (?,?,?,?)",
                    [("EHB 222", "Elektroniğe Giriş", 3, 5), ("EHB 222E", "Intro Electronics", 3, 5),
                     ("FIZ 101", "Fizik", 3, 5), ("FIZ 101E", "Physics", 3, 5),
                     ("MAT 103", "Matematik I", 4, 6), ("MAT 103E", "Mathematics I", 4, 6)])
    con.execute("INSERT INTO plan(id,program_code,plan_type,title,source) VALUES (10,'BLGE','lisans','a','obs')")
    con.executemany("INSERT INTO plan_slot(plan_id,slot_kind,course_code,credits,position,term_no)"
                    " VALUES (10,'REQUIRED',?,3,?,3)", [("EHB 222E", 0), ("FIZ 101", 1), ("MAT 103", 2)])
    con.execute("INSERT INTO plan(id,program_code,plan_type,title,source,is_term_based)"
                " VALUES (20,'EHB','cap','BLG_EHB','obs',0)")
    con.executemany("INSERT INTO plan_slot(plan_id,slot_kind,course_code,credits,position)"
                    " VALUES (20,'REQUIRED',?,3,?)", [("EHB 222", 0), ("FIZ 101E", 1)])
    con.commit(); con.close()
    st = SRV.State()
    st.dispatch("/api/transcript/paste", {"text": "EHB 222E CC\nFIZ 101 BB\nMAT 103E BA", "replace": True})
    return st


def _ogeler(st):
    return {(p["role"], o["course"]): o for p in st.plan_checklist()
            for t in p["terms"] for sl in t["slots"] for o in sl["options"]}


def test_CAP_slotu_esiyle_karsilandi(state):
    o = _ogeler(state)
    assert o[("CAP", "EHB 222")]["taken"] is False
    assert (o[("CAP", "EHB 222")]["via"], o[("CAP", "EHB 222")]["viaGrade"]) == ("EHB 222E", "CC")
    assert o[("ANADAL", "EHB 222E")]["taken"] is True and "via" not in o[("ANADAL", "EHB 222E")]


def test_TERS_YON_ve_ANADAL_isaretlenmiyor(state):
    """Türkçe FIZ 101 İngilizce FIZ 101E slotunu doldurmuyor (Faz 10 ilkesi)."""
    o = _ogeler(state)
    assert "via" not in o[("CAP", "FIZ 101E")]
    assert "via" not in o[("ANADAL", "FIZ 101")]
    # Anadal planı dil eşiyle İŞARETLENMİYOR (Faz 92: dil şartı programın kuralı).
    assert "via" not in o[("ANADAL", "MAT 103")] and o[("ANADAL", "MAT 103")]["taken"] is False


_CANLI = r'''
import sys, os, json
sys.path.insert(0, os.environ["ITUCAP_SRC"]); sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import vitrin
adres, h = vitrin.ac()
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 1000})
    hatalar = []; pg.on("pageerror", lambda e: hatalar.append(str(e)))
    pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(800)
    pg.evaluate("""() => {
      SETUP.checklist = [{role: 'CAP', planId: 20, program: 'EHB', termBased: false, terms: [{term: 0, label: '', slots: [
        {slotId: 1, pool: '', category: '', required: true, options: [{course: 'EHB 222', name: 'Elektroniğe Giriş',
          credits: 3, grade: null, status: '', taken: false, via: 'EHB 222E', viaGrade: 'CC'}]},
        {slotId: 2, pool: '', category: '', required: true, options: [{course: 'EHB 206', name: 'İşaret',
          credits: 3, grade: null, status: '', taken: false}]}]}]}];
      window.__giden = null;
      window.api = async (yol, govde) => { window.__giden = [yol, govde]; return {}; };
      checklistDialog(); }""")
    pg.wait_for_timeout(300)
    print("SATIR:" + json.dumps(pg.evaluate("""() => { const cb = document.querySelector('input[data-via="EHB 222"]');
        return cb ? [cb.checked, cb.disabled, cb.closest('label').textContent.replace(/\\s+/g,' ').trim(),
                     !!document.querySelector('select.g[data-course="EHB 222"]')] : null; }"""), ensure_ascii=False))
    pg.click("#setupSave"); pg.wait_for_timeout(300)
    print("GIDEN:" + json.dumps(pg.evaluate("() => window.__giden"), ensure_ascii=False))
    print("HATA:" + str(len(hatalar)) + " " + " | ".join(hatalar)[:300])
    b.close()
h.shutdown()
'''


def test_UCTAN_UCA_pencere(tmp_path, monkeypatch):
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
    isaretli, kilitli, metin, notlu = json.loads(c["SATIR"])
    assert isaretli and kilitli and not notlu, c["SATIR"]
    assert "✓ EHB 222E ile karşılandı" in metin, metin
    yol, govde = json.loads(c["GIDEN"])
    assert yol == "/api/transcript"
    assert "EHB 222" not in [x["course"] for x in govde["items"]]      # ikinci ders EKLENMİYOR
    assert "EHB 222" not in govde["remove"]
