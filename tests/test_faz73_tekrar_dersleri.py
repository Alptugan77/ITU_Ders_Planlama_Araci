"""Faz 73 — başarısız olunan ders programda yoksa nedeni ve tek dokunuş.

Kullanıcı 24.09.2026: *"continue and create a pr"* (öncesinde: *"make the site
more usefull and add new features"*). Faz 72 gezintisinde MAT 104E'den FF alan
yandal öğrencisinin önerilen programında MAT 104E yoktu ve hiçbir yer nedenini
söylemiyordu (11 şubenin hepsi yandalın tek şubeli iki dersiyle çakışıyordu).
Özet artık her başarısız ders için nedeni yazıyor; uyan ya da çakışan şube
varsa tek dokunuşla ekliyor ve yan etkisini (dönem sınırı, ÇAP yarıyıl
tabanı) ÖNCEDEN söylüyor.
"""
import json
import pathlib
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import ui as UI

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


def _js(ad):
    f = KAYNAK[KAYNAK.index(f"function {ad}("):]
    return f[:f.index("\n}\n")]


def test_KURAL():
    d = _js("tekrarDurumu")
    assert '.filter(t => t.status === "FAILED" && !secili.has(t.course))' in d
    # Aday değil + darboğaz gerekçesi yok → planlarda kalan ders değil, yazılmıyor.
    assert "if(!b) return null;" in d
    # Kontenjanı ilan edilmemiş şube "dolu" sayılmıyor.
    assert "const acikOlabilir = (s) => !s.capacity || yerSayisi(s) > 0;" in d
    assert "!mesgulCakisir(s)" in d and "conflictsWith(s, t.course)" in d
    e = _js("eklemeEtkisi")
    assert "tabanDurumu(F).ok" in e and "DATA.maxLoad" in e


def test_OZET_ve_DANISMAN():
    r = _js("render")
    assert "${tekrarOzeti()}" in r
    assert 'querySelectorAll("[data-tekrar]")' in r
    assert "choose(b.dataset.tekrar, b.dataset.crn)" in r
    q = _js("danismanSorulari")
    assert 'tekrarDurumu().filter(x => x.tur !== "UYAR")' in q


_CANLI = r'''
import sys, os, json
sys.path.insert(0, os.environ["ITUCAP_SRC"]); sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import vitrin
adres, h = vitrin.ac()
from playwright.sync_api import sync_playwright
OZET = "() => (document.querySelector('#schedSummary .ozettekrar')||{innerText:''}).innerText.replace(/\\s+/g,' ')"
DURUM = "() => tekrarDurumu()"
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 1000})
    hatalar = []
    pg.on("pageerror", lambda e: hatalar.append(str(e)))
    pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(1000)
    # (1) Vitrin: MAT 210E FF, şubesi ÇAP dersi BLG 252E ile çakışıyor.
    print("D1:" + json.dumps(pg.evaluate(DURUM)))
    print("O1:" + pg.evaluate(OZET))
    print("Q1:" + json.dumps(pg.evaluate("() => danismanSorulari()"), ensure_ascii=False))
    # (2) BLG 252E çıkınca şube uyuyor → "programa ekle"; danışman sorusu yok.
    pg.evaluate("() => removeCourse('BLG 252E')"); pg.wait_for_timeout(200)
    print("D2:" + json.dumps(pg.evaluate(DURUM)))
    print("O2:" + pg.evaluate(OZET))
    print("Q2:" + json.dumps(pg.evaluate("() => danismanSorulari().some(s => s.includes('Başarısız olduğum'))")))
    pg.click("#schedSummary [data-tekrar]"); pg.wait_for_timeout(200)
    print("SEL:" + json.dumps(pg.evaluate("() => sel.map(x => x.course)")))
    print("O3:" + pg.evaluate(OZET))
    pg.evaluate("() => removeCourse('MAT 210E')"); pg.wait_for_timeout(200)
    # (3) Dönem sınırı: sınır düşükse ekleme uyarısı.
    pg.evaluate("() => { DATA.maxLoad = 20; render(); }")
    print("SINIR:" + json.dumps(pg.evaluate(DURUM)[0]))
    print("OS:" + pg.evaluate(OZET))
    # (4) Meşgul saatler bütün açık şubeleri kapatıyor.
    pg.evaluate("""() => { DATA.busy = candOf('MAT 210E').sections.flatMap(s => s.meetings)
        .map(m => ({day: m.day, start: m.start, end: m.end, ok: true})); render(); }""")
    print("MESGUL:" + pg.evaluate(DURUM)[0]["tur"])
    pg.evaluate("() => { DATA.busy = []; render(); }")
    # (4b) İki şube de çakışıyorsa EN AZ krediyi düşüren seçiliyor: B iki
    #      dersle (6 kr), A tek dersle (3 kr) çakışıyor; B listede önde.
    print("ENAZ:" + json.dumps(pg.evaluate("""() => {
        const [x, y, z] = picks();
        const sube = (crn, ps) => ({crn, capacity: 30, enrolled: 20, free: 10, online: false,
                                    meetings: ps.flatMap(p => p.sec.meetings)});
        candOf('MAT 210E').sections = [sube('B', [y, z]), sube('A', [x])];
        DATA.maxLoad = 40; render();
        const d = tekrarDurumu()[0];
        return {crn: d.crn, cikar: d.cikar, x: x.cand.course}; }""")))
    # (5) Bütün şubeler ilan edilmiş kontenjanla dolu → "dolu"; ilan yoksa dolu değil.
    pg.evaluate("() => { candOf('MAT 210E').sections.forEach(s => { s.capacity = 40; s.enrolled = 40; s.free = 0; }); render(); }")
    print("DOLU:" + pg.evaluate(DURUM)[0]["tur"])
    pg.evaluate("() => { candOf('MAT 210E').sections.forEach(s => { s.capacity = 0; s.free = null; }); render(); }")
    print("ILANSIZ:" + pg.evaluate(DURUM)[0]["tur"])
    # (6) Aday olmayan başarısız ders: darboğaz gerekçesiyle ya da hiç yazılmaz.
    pg.evaluate("""() => { SETUP.transcript.push({course: 'XYZ 101', grade: 'VF', status: 'FAILED'},
                                               {course: 'QQQ 202', grade: 'FF', status: 'FAILED'});
        DATA.blockers = [...(DATA.blockers || []), {course: 'XYZ 101', reason: 'ACILMAMIS',
                                                    detail: 'bu dönem şube açılmamıştır'}];
        render(); }""")
    print("ENGEL:" + json.dumps(pg.evaluate(DURUM)))
    print("OE:" + pg.evaluate(OZET))
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
    d1 = json.loads(c["D1"])
    assert len(d1) == 1 and d1[0]["course"] == "MAT 210E" and d1[0]["grade"] == "FF"
    assert d1[0]["tur"] == "CAKISIYOR" and d1[0]["cikar"] == ["BLG 252E"], d1
    # BLG 252E ÇAP dersi: çıkarsa ÇAP yarıyıl tabanı bozuluyor — önceden yazıyor.
    assert d1[0]["tabanBozar"] is True and d1[0]["asar"] is False, d1
    for parca in ("Tekrar alınması gereken ders programda değil", "MAT 210E",
                  "ekle, BLG 252E çıkar", "BLG 252E ile çakışmaktadır",
                  "ÇAP yarıyıl tabanı (9 kredi) sağlanamaz"):
        assert parca in c["O1"], (parca, c["O1"])
    assert any("Başarısız olduğum <span class=\"mono\">MAT 210E (FF)</span>" in s and "çakışmaktadır" in s
               for s in json.loads(c["Q1"])), c["Q1"]
    d2 = json.loads(c["D2"])
    assert d2[0]["tur"] == "UYAR" and d2[0]["cikar"] == [] and d2[0]["crn"], d2
    assert "programa ekle" in c["O2"] and "programla çakışmamaktadır" in c["O2"]
    assert c["Q2"] == "false"
    assert "MAT 210E" in json.loads(c["SEL"]) and c["O3"] == ""
    s = json.loads(c["SINIR"])
    assert s["tur"] == "UYAR" and s["asar"] is True, s
    assert "ile sınırı aşar" in c["OS"] and "/ 20" in c["OS"], c["OS"]
    assert c["MESGUL"] == "MESGUL"
    enaz = json.loads(c["ENAZ"])
    assert enaz["crn"] == "A" and enaz["cikar"] == [enaz["x"]], enaz
    assert c["DOLU"] == "DOLU"
    assert c["ILANSIZ"] != "DOLU", c["ILANSIZ"]
    engel = {x["course"]: x for x in json.loads(c["ENGEL"])}
    assert engel["XYZ 101"]["tur"] == "ENGEL" and "QQQ 202" not in engel, engel
    assert "XYZ 101" in c["OE"] and "bu dönem şube açılmamıştır" in c["OE"]
