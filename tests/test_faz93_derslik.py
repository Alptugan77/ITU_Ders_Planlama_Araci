"""Faz 93 — programda DERSLİK.

Kullanıcı 25.09.2026: *"ders programında dersin fakültesi gözüküyor ama
sınıfı gözükmüyor sadece programa bakarak derslere gidilebilecek şekilde
sınıfları gösterir misin"*.

Derslik veride vardı (`lesson_meeting.room`; gerçek katalogda 3900
buluşmanın 1725'i) ama sunucu onu arayüze hiç göndermiyordu. Izgara "MED"
yazıyordu; öğrenci hangi sınıfa gideceğini OBS'de ayrıca arıyordu.

İlke aynı (bkz. `_building`, `_hoca`): ilan edilmemiş derslik ("--") BOŞ
gönderilir ve arayüz bunu SÖYLER — "--" bir sınıf adı değil.
"""
import json
import pathlib
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import config, db, recommend as REC, ui as UI


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


@pytest.mark.parametrize("ham,temiz", [
    ("D102", "D102"), ("  A31 ", "A31"), ("--", ""), ("-", ""), ("", ""), (None, ""),
    ("undeclared", ""), ("B3_Z01-Z03", "B3_Z01-Z03")])
def test_DERSLIK_temizligi(ham, temiz):
    assert UI._derslik(ham) == temiz


# ============================================== sunucu: şube ve CRN yükleme
@pytest.fixture()
def state(tmp_path, monkeypatch):
    from itucap import server as SRV

    monkeypatch.setattr(config, "REF_DB", tmp_path / "r.sqlite3")
    monkeypatch.setattr(config, "USER_DB", tmp_path / "u.sqlite3")
    monkeypatch.setattr(config.Settings, "load",
                        classmethod(lambda cls, path=None: config.Settings(
                            anadal_program="HTAE", program_codes=["HTAE"],
                            term="202610")))
    con = db.connect(tmp_path / "r.sqlite3", "schema.sql")
    con.executemany("INSERT INTO course(code,name,credits,ects) VALUES (?,?,?,?)",
                    [("GEO 303E", "Kadastro", 3.0, 3.0), ("GEO 305E", "Fotogrametri", 3.0, 3.0)])
    con.execute("INSERT INTO plan(id,program_code,plan_type,title,source) "
                "VALUES (10,'HTAE','lisans','anadal','obs')")
    con.executemany("INSERT INTO plan_slot(plan_id,slot_kind,course_code,credits,position) "
                    "VALUES (10,'REQUIRED',?,3.0,?)", [("GEO 303E", 0), ("GEO 305E", 1)])
    # 13524: derslik ilan edilmiş · 13525: bina var, derslik "--" ·
    # 13526: bina da ilan edilmemiş.
    for crn, code, gun, bina, oda in [("13524", "GEO 303E", 1, "INB", "D102"),
                                      ("13525", "GEO 305E", 2, "INB", "--"),
                                      ("13526", "GEO 305E", 4, "undeclared", "--")]:
        con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled,building) "
                    "VALUES (?,?,40,12,?)", (crn, code, bina))
        con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES (?,'HTAE')",
                    (crn,))
        con.execute("""INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min,
                       building,room) VALUES (?,?,510,630,?,?)""", (crn, gun, bina, oda))
    con.commit()
    con.close()
    return SRV.State()


def test_SUBE_verisi_dersligi_tasiyor(state):
    d = state.snapshot()
    bul = {(c["course"], s["crn"]): s["meetings"][0]
           for c in d["candidates"] for s in c["sections"]}
    assert bul[("GEO 303E", "13524")]["building"] == "INB"
    assert bul[("GEO 303E", "13524")]["room"] == "D102"
    assert bul[("GEO 305E", "13525")]["room"] == ""           # "--" gönderilmiyor
    assert bul[("GEO 305E", "13526")] ["building"] == ""


def test_CRN_yukleme_dersligi_tasiyor_ve_temizliyor(state):
    out = state.dispatch("/api/crn", {"crns": ["13524", "13526"]})["crn"]["found"]
    m = {x["crn"]: x["meetings"][0] for x in out}
    assert (m["13524"]["building"], m["13524"]["room"]) == ("INB", "D102")
    # Eskiden ham "undeclared" bina adı diye gidiyordu.
    assert (m["13526"]["building"], m["13526"]["room"]) == ("", "")


def test_TERMINAL_dersligi_yaziyor():
    sec = REC.Section("13524", "GEO 303E", None, 40, 12,
                      (REC.Meeting(1, 510, 630, "D102", "INB", None),
                       REC.Meeting(3, 510, 630, "--", "INB", None)))
    cand = REC.Candidate(course="GEO 303E", name="Kadastro", role="ANADAL",
                         ects=3.0, credits=3.0, unlocks=0, tier=0, critical=False,
                         required=True, sections=[sec])
    metin = REC.format_schedule(REC.Schedule([REC.Pick(cand, sec)]), [cand])
    assert "INB D102" in metin
    assert "INB/INB D102" in metin                # derslik ilan edilmemiş gün: yalnız bina


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
    ilk = "() => { const e = document.querySelector('#grid .blk'); return [e.textContent.replace(/\\s+/g,' ').trim(), e.title]; }"
    print("IZGARA:" + json.dumps(pg.evaluate(ilk), ensure_ascii=False))
    print("YER:" + json.dumps(pg.evaluate("""() => [
        yerYazi({building: 'MED', room: 'D102'}), yerYazi({building: 'MED', room: ''}),
        yerYazi({building: '', room: ''}), yerYazi('MED'),
        yerBaslik({building: 'INB', room: 'D01'}), yerBaslik({building: 'INB', room: ''}),
        yerBaslik({building: '', room: ''}), yerTakvim({building: 'INB', room: 'D01'})]"""),
        ensure_ascii=False))
    print("ICS:" + json.dumps([s for s in pg.evaluate("() => icsMetni().metin").split("\r\n")
                               if s.startswith("LOCATION:")][:3], ensure_ascii=False))
    pg.evaluate("() => renderPrintCrn()")
    print("BASKI:" + pg.evaluate("() => (document.querySelector('#printCrn')||{textContent:''}).textContent.replace(/\\s+/g,' ')")[:600])
    ders = pg.evaluate("() => document.querySelector('#grid .blk').dataset.course")
    pg.evaluate("(k) => courseDialog(k)", ders); pg.wait_for_timeout(300)
    print("SUBE:" + pg.evaluate("() => [...document.querySelectorAll('#detail .opt .yer')].map(e => e.textContent + '|' + e.title).slice(0,2).join(' ;; ')"))
    pg.keyboard.press("Escape")
    # CRN yapıştırarak yüklenen şube de dersliği taşıyor.
    print("CRNYUK:" + str(pg.evaluate("""() => { injectSections([{crn: '99001', course: 'GEO 315E',
        name: 'Cadastre', capacity: 10, enrolled: 1, role: 'ANADAL',
        meetings: [{day: 2, start: 510, end: 630, building: 'INB', room: 'Z-19'}]}]);
        const s = candOf('GEO 315E').sections.find(x => x.crn === '99001');
        return s ? yerYazi(s.meetings[0]) : 'YOK'; }""")))
    m = b.new_page(viewport={"width": 390, "height": 900})
    m.goto(adres, wait_until="networkidle"); m.wait_for_timeout(800)
    print("GUN:" + m.evaluate("() => (document.querySelector('.daylist .row .yer')||{textContent:''}).textContent"))
    print("NOWRAP:" + pg.evaluate("() => getComputedStyle(document.querySelector('#grid .blk .yer')).whiteSpace"))
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
    # Izgara: bina + derslik hücrede, tam ad ipucunda.
    metin, ipucu = json.loads(c["IZGARA"])
    assert "INB D01" in metin, metin
    assert "INB — İnşaat Fakültesi · derslik D01" in ipucu, ipucu
    yer = json.loads(c["YER"])
    assert yer[:4] == ["MED D102", "MED", "yer bildirilmedi", "MED"]
    assert yer[4] == "INB — İnşaat Fakültesi · derslik D01"
    assert yer[5] == "INB — İnşaat Fakültesi · derslik OBS'de bildirilmemiş"
    assert yer[6] == "OBS'de yer bildirilmemiş"
    assert yer[7] == "INB D01 — İnşaat Fakültesi"
    # Takvim dosyası, basılı liste, şube seçimi, telefon gün görünümü.
    import re
    assert all(re.fullmatch(r"LOCATION:[A-Z]+ D\d+ — .+", s) for s in json.loads(c["ICS"])), c["ICS"]
    assert "Gün / saat · yer" in c["BASKI"] and "INB D0" in c["BASKI"], c["BASKI"]
    assert re.search(r"[A-Z]+ D\d+\|[A-Z]+ — .+ · derslik D\d+", c["SUBE"]), c["SUBE"]
    assert c["CRNYUK"] == "INB Z-19", c["CRNYUK"]
    assert c["GUN"].startswith(("INB D", "EEB D")), c["GUN"]
    assert c["NOWRAP"] == "nowrap"                  # "INB D01" ikiye bölünmüyor
