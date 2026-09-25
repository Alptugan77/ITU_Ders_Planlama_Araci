"""Faz 94 — arka arkaya iki ders farklı yerleşkede.

Kullanıcı 25.09.2026: *"continue"* (Faz 93'ün "programa bakarak derse
gidilebilsin" isteğinin devamı).

İTÜ'de ders :29'da bitiyor, sonraki :30'da başlıyor. Ölçüm (gerçek katalog,
11 profil): önerilerdeki 17 yerleşke değişiminin 10'unda arada **1 dakika**
vardı (ISL 224E Maçka → BLG 351E Ayazağa). Motor bunu görmüyordu, arayüz
de söylemiyordu. Ayrıca katalogdaki 67 binanın 32'sinin yerleşkesi boştu.
"""
import json
import pathlib
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import config, db, declared as DEC, recommend as REC, ui as UI

AYZ, MCK = "Ayazağa Yerleşkesi", "Maçka Yerleşkesi"


def _sec(crn, course, gun, bas, bit, kampus, online=False):
    return REC.Section(crn, course, None, 40, 0,
                       (REC.Meeting(gun, bas, bit, "D1", "X", kampus),),
                       "Virtual (Online)" if online else None)


def _cand(course, secs, score=50.0):
    c = REC.Candidate(course=course, name=course, role="ANADAL", ects=5.0, credits=3.0,
                      unlocks=0, tier=0, critical=False, required=True, sections=list(secs))
    c.score = score
    return c


def _prog(*secs):
    return REC.Schedule([REC.Pick(_cand(s.course, [s]), s) for s in secs])


# ============================================================ sayım
@pytest.mark.parametrize("ikinci,beklenen", [
    (_sec("2", "B", 1, 690, 749, AYZ), 1),     # 11:29 → 11:30, Maçka → Ayazağa
    (_sec("2", "B", 1, 749, 809, AYZ), 0),     # arada tam 60 dk: eşik altı değil
    (_sec("2", "B", 1, 690, 749, MCK), 0),     # aynı yerleşke
    (_sec("2", "B", 1, 690, 749, None), 0),    # yerleşke bilinmiyor → iddia yok
    (_sec("2", "B", 1, 690, 749, AYZ, online=True), 0),   # çevrimiçi
    (_sec("2", "B", 2, 690, 749, AYZ), 0),     # başka gün
])
def test_SIKISIK_GECIS_sayimi(ikinci, beklenen):
    ilk = _sec("1", "A", 1, 510, 689, MCK)
    assert _prog(ilk, ikinci).sikisik_gecisler() == beklenen


def test_PUAN_cezasi():
    ilk = _sec("1", "A", 1, 510, 689, MCK)
    siki = _prog(ilk, _sec("2", "B", 1, 690, 749, AYZ))
    rahat = _prog(ilk, _sec("3", "B", 1, 810, 869, AYZ))
    assert siki.base_score == rahat.base_score
    assert rahat.score - siki.score == REC.SIKISIK_GECIS_CEZASI == 30.0


def test_CEZA_ders_kumesini_siraliyor():
    """Yük yalnız iki derse yetiyor: A+B (puan 140, 1 dk'lık geçiş) ile A+C
    (135, geçişsiz). Ceza A+C'yi öne geçiriyor."""
    a = _cand("A", [_sec("1", "A", 1, 510, 689, MCK)], 80)
    b = _cand("B", [_sec("2", "B", 1, 690, 749, AYZ)], 60)
    c = _cand("C", [_sec("3", "C", 1, 870, 929, AYZ)], 55)
    en_iyi = REC.build_schedules([a, b, c], max_load=6, limit=3)[0]
    assert set(en_iyi.courses()) == {"A", "C"}


def test_CRN_yukleme_beyani_kullaniyor(tmp_path, monkeypatch):
    from itucap import server as SRV
    monkeypatch.setattr(config, "REF_DB", tmp_path / "r.sqlite3")
    monkeypatch.setattr(config, "USER_DB", tmp_path / "u.sqlite3")
    monkeypatch.setattr(config.Settings, "load", classmethod(lambda cls, path=None: config.Settings(
        anadal_program="BLG", program_codes=["BLG"], term="202610")))
    con = db.connect(tmp_path / "r.sqlite3", "schema.sql")
    con.execute("INSERT INTO course(code,name,credits,ects) VALUES ('BLG 101','X',3,5)")
    con.execute("INSERT INTO building(code,name,campus) VALUES ('BBB','Bilgisayar',NULL)")
    con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled,building) VALUES ('1','BLG 101',9,0,'BBB')")
    con.execute("INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min,building,room)"
                " VALUES ('1',1,510,629,'BBB','Z-18')")
    con.commit(); con.close()
    m = SRV.State().dispatch("/api/crn", {"crns": ["1"]})["crn"]["found"][0]["meetings"][0]
    assert m["campus"] == AYZ                    # config/katalog-duzeltmeleri.toml beyanı


def test_MOTOR_gecissiz_subeyi_seciyor():
    """Aynı dersin iki şubesi: 11:30 (Maçka dersinden hemen sonra, Ayazağa)
    ve 14:30. Motor 14:30'u öne koymalı; ders programdan düşmemeli."""
    a = _cand("A", [_sec("1", "A", 1, 510, 689, MCK)], 80)
    b = _cand("B", [_sec("2", "B", 1, 690, 749, AYZ), _sec("3", "B", 1, 870, 929, AYZ)], 60)
    en_iyi = REC.build_schedules([a, b], max_load=30, limit=3)[0]
    assert set(en_iyi.courses()) == {"A", "B"}
    assert {p.candidate.course: p.section.crn for p in en_iyi.picks}["B"] == "3"
    assert en_iyi.sikisik_gecisler() == 0


# ============================================================ yerleşke beyanı
def test_BEYAN_dosyasi():
    b = DEC.load_campus_overrides()
    assert b == {"MEDC": AYZ, "BBB": AYZ, "MSB": MCK}
    assert "YDY" not in b                        # emin olunmayan beyan edilmez


def test_BEYAN_yalniz_katalog_bosken(tmp_path, monkeypatch):
    dosya = tmp_path / "k.toml"
    dosya.write_text('[[kampus_beyani]]\nbina = "BBB"\nkampus = "Ayazağa Yerleşkesi"\nnot_ = "t"\n'
                     '[[kampus_beyani]]\nbina = "EEB"\nkampus = "Maçka Yerleşkesi"\nnot_ = "yanlış"\n',
                     encoding="utf-8")
    monkeypatch.setattr(DEC, "CATALOG_PATH", dosya)
    con = db.connect(tmp_path / "r.sqlite3", "schema.sql")
    con.executemany("INSERT INTO building(code,name,campus) VALUES (?,?,?)",
                    [("BBB", "Bilgisayar", None), ("EEB", "Elektrik", AYZ)])
    for crn, bina in [("1", "BBB"), ("2", "EEB")]:
        con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled) VALUES (?,'X 101',9,0)", (crn,))
        con.execute("INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min,building,room)"
                    " VALUES (?,1,510,629,?,'D1')", (crn, bina))
    con.commit()
    kampus = {s.crn: s.meetings[0].campus for s in REC._load_sections(con, "X 101", set())}
    assert kampus == {"1": AYZ, "2": AYZ}         # beyan boşu doldurdu, dolu olanı EZMEDİ


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
    # Pazartesi arka arkaya iki ders bul; öncekini Maçka, sonrakini Ayazağa yap.
    print("CIFT:" + json.dumps(pg.evaluate("""() => {
      const ms = picks().filter(p => !p.sec.online).flatMap(p => p.sec.meetings.map(m => ({p, m})))
        .sort((x, y) => x.m.day - y.m.day || x.m.start - y.m.start);
      for(let i = 1; i < ms.length; i++){
        const a = ms[i-1], b = ms[i];
        if(a.m.day === b.m.day && b.m.start - a.m.end < 60 && a.p !== b.p){
          a.m.campus = 'Maçka Yerleşkesi'; b.m.campus = 'Ayazağa Yerleşkesi';
          render(); return [a.p.cand.course, b.p.cand.course];
        }
      }
      return null; }""")))
    print("NOT:" + pg.evaluate("() => [...document.querySelectorAll('#grid .gecis')].map(e => e.textContent + '|' + e.title).join(' ;; ')"))
    print("AYNI:" + str(pg.evaluate("""() => { const x = picks().filter(p => !p.sec.online);
        x.forEach(p => p.sec.meetings.forEach(m => m.campus = 'Ayazağa Yerleşkesi')); render();
        return document.querySelectorAll('#grid .gecis').length; }""")))
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
    once, sonra = json.loads(c["CIFT"])
    metin, ipucu = c["NOT"].split(" ;; ")[0].split("|")
    assert metin == "⚠ Maçka → Ayazağa · 1 dk", c["NOT"]
    assert f"Önceki ders ({once}) Maçka yerleşkesinde, bu ders Ayazağa" in ipucu, ipucu
    assert "yetişmeyebilir" in ipucu
    assert c["AYNI"] == "0"                      # aynı yerleşke: işaret yok
