"""Faz 99 — ilerleme kartında dönem şeridi ve kalan yuvalar.

Kullanıcı 25.09.2026: *"bir de ilerleme durumu kısmı biraz boş kaldı gibi
ona eklenebilecek iyi bir şey varsa ekler misin"*.

Kart yüzde ve sayı veriyordu ("%62 · kalan zorunlu 14") ama HANGİ derslerin
kaldığını ve planın neresinde olunduğunu söylemiyordu. Artık her dönemin
doluluğu bir şerit, önceki dönemlerden kalan yuvalar ayrı ve uyarı renginde,
bulunulan dönemin yuvaları altında; ders adına tıklanınca ekleme/şube
penceresi açılıyor.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import db, ui as UI


@pytest.fixture()
def con(tmp_path):
    c = db.connect(tmp_path / "r.sqlite3", "schema.sql")
    c.executemany("INSERT INTO course(code,name,credits,ects) VALUES (?,?,3,5)",
                  [("MAT 101", "Matematik I"), ("MAT 102", "Matematik II"),
                   ("BLG 201", "Veri Yapıları"), ("BLG 301", "Algoritmalar")])
    c.execute("INSERT INTO plan(id,program_code,plan_type,title,source) VALUES (1,'BLG','lisans','a','obs')")
    c.execute("INSERT INTO plan(id,program_code,plan_type,title,source) VALUES (2,'MAT','cap','c','obs')")
    c.executemany("""INSERT INTO plan_slot(id,plan_id,term_no,slot_kind,course_code,
                     pool_label_raw,pool_category,position) VALUES (?,?,?,?,?,?,?,?)""", [
        (10, 1, 1, "REQUIRED", "MAT 101", None, None, 0),
        (11, 1, 2, "REQUIRED", "MAT 102", None, None, 0),
        (12, 1, 2, "ELECTIVE_POOL", None, "TM Elective I", "TM", 1),
        (13, 1, 3, "REQUIRED", "BLG 201", None, None, 0),
        (20, 2, None, "REQUIRED", "BLG 301", None, None, 0),
        (21, 2, None, "ELECTIVE_POOL", None, None, "MT", 1)])
    c.commit()
    return c


def test_DONEMLI_plan_serit_ve_acik_yuvalar(con):
    d = UI._panel_donemleri(con, 1, [11, 12, 13])
    assert d["terms"] == [{"term": 1, "done": 1, "total": 1},
                          {"term": 2, "done": 0, "total": 2},
                          {"term": 3, "done": 0, "total": 1}]
    assert d["open"] == [
        {"code": "MAT 102", "label": "MAT 102", "name": "Matematik II", "term": 2, "required": True},
        {"code": None, "label": "TM Elective I", "name": "", "term": 2, "required": False},
        {"code": "BLG 201", "label": "BLG 201", "name": "Veri Yapıları", "term": 3, "required": True}]


def test_DONEMSIZ_plan_serit_uydurmuyor(con):
    """ÇAP/yandal planlarında `term_no` NULL: şerit yok, liste var."""
    d = UI._panel_donemleri(con, 2, [20, 21])
    assert d["terms"] == []
    assert [o["label"] for o in d["open"]] == ["BLG 301", "MT"]   # etiket yoksa kategori


def test_TAMAMLANMIS_plan(con):
    d = UI._panel_donemleri(con, 1, [])
    assert d["open"] == [] and all(t["done"] == t["total"] for t in d["terms"])


# ======================================================= arayüz (vitrin)
_CANLI = r'''
import sys, os, json
sys.path.insert(0, os.environ["ITUCAP_SRC"]); sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import vitrin
adres, h = vitrin.ac()
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 1000})
    hatalar = []
    pg.on("pageerror", lambda e: hatalar.append(str(e)))
    pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(800)
    pg.evaluate("() => gorunumAc('panels', true)"); pg.wait_for_timeout(300)
    print("SERIT:" + json.dumps(pg.evaluate("""() => {
      const k = document.querySelector('#panels .panel[data-role=ANADAL]');
      const p = DATA.panels.find(x => x.role === 'ANADAL');
      return {donem: DATA.donem, terms: p.terms,
        hucre: [...k.querySelectorAll('.dnm')].map(e => [+e.dataset.term, e.className]),
        geride: p.open.filter(o => o.term < DATA.donem).map(o => o.label),
        gerideCip: [...k.querySelectorAll('.kbas.geride + .kliste .kders')].map(e => e.textContent.trim()),
        cap: [...document.querySelectorAll('#panels .panel[data-role=CAP] .dnm')].length,
        capBaslik: (document.querySelector('#panels .panel[data-role=CAP] .kbas') || {}).textContent};
    }"""), ensure_ascii=False))
    # Bu dönem seçili ders ✓ ile; çıkarınca işaret kalkıyor.
    ders = pg.evaluate("""() => { const b = document.querySelector('#panels button.kders.secili');
        return b ? b.dataset.ders : null; }""")
    print("SECILI:" + json.dumps(ders))
    pg.evaluate("(k) => removeCourse(k)", ders); pg.wait_for_timeout(200)
    print("CIKTI:" + pg.evaluate("""(k) => { const b = [...document.querySelectorAll('#panels button.kders')]
        .find(e => e.dataset.ders === k); return b ? b.className + '|' + b.textContent.trim() : 'YOK'; }""", ders))
    # Tıklama: seçili olmayan ders ekleme penceresini açıyor.
    pg.evaluate("(k) => [...document.querySelectorAll('#panels button.kders')].find(e => e.dataset.ders === k).click()", ders)
    pg.wait_for_timeout(300)
    print("PENCERE:" + str(pg.evaluate("() => document.querySelector('#detail').open")) + "|"
          + str(pg.evaluate("() => document.querySelectorAll('#detail .opt').length")))
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
    s = json.loads(c["SERIT"])
    donem = s["donem"]
    assert donem and len(s["hucre"]) == len(s["terms"]) == 8
    for (no, sinif), t in zip(s["hucre"], s["terms"]):
        assert no == t["term"]
        assert ("simdi" in sinif) == (no == donem), (no, sinif)
        assert ("geride" in sinif) == (no < donem and t["done"] < t["total"]), (no, sinif)
        assert ("tamam" in sinif) == (t["done"] == t["total"]), (no, sinif)
    assert s["geride"] and [x.lstrip("✓ ") for x in s["gerideCip"]] == s["geride"]
    assert s["cap"] == 0                                      # ÇAP planında dönem yok
    assert s["capBaslik"].startswith("Kalan zorunlu dersler")
    assert json.loads(c["SECILI"])
    sinif, metin = c["CIKTI"].split("|")
    assert "secili" not in sinif and not metin.startswith("✓"), c["CIKTI"]
    acik, secenek = c["PENCERE"].split("|")
    assert acik == "True" and int(secenek) > 0, c["PENCERE"]
