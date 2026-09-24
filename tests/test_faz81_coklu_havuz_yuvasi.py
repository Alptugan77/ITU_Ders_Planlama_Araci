"""Faz 81 — seçmeli, uyduğu HER havuz yuvasına yerleşebiliyor.

Kullanıcı 24.09.2026: *"bunlardan sonra eklenebilecek şeyleri eklemeye ve
geliştirmeye devam et lütfen"*. Aday yalnız ilk göründüğü yuvayla
tutuluyordu; "havuz dolu" kontrolü o tek yuvaya bakıyordu. Gerçek katalogda
havuzdaki (plan, ders) çiftlerinin %38'i birden çok yuvaya uyuyor — ENDE'de
Functional-MT dersleri 5–8. yarıyılın dört yuvasına; motor bir dönemde o
gruptan en çok BİR ders önerebiliyordu.
"""
import json
import pathlib
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import db, recommend as REC, ui as UI


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


class _A:
    def __init__(self, *yuvalar):
        self.slot_ids = tuple(yuvalar)
        self.slot_id = yuvalar[0] if yuvalar else 0

    yuvalar = REC.Candidate.yuvalar


def test_ESLESTIRME():
    # A iki yuvaya, B yalnız birine uyuyor → A öbürüne kayıyor.
    assert REC.yuva_ata([_A(1, 2), _A(1)]) == {0: 2, 1: 1}
    # İkisi de tek ve aynı yuvaya → olmaz (eski "havuz tek dersle dolar" kuralı).
    assert REC.yuva_ata([_A(1), _A(1)]) is None
    # Üç ders, iki yuva → olmaz.
    assert REC.yuva_ata([_A(1, 2), _A(1, 2), _A(1, 2)]) is None
    # Yuvası olmayan (plan dışı) serbest.
    assert REC.yuva_ata([_A(), _A(1), _A()]) == {1: 1}
    # Zincirleme kaydırma: C yalnız 1'e, B 1/2'ye, A 2/3'e.
    at = REC.yuva_ata([_A(2, 3), _A(1, 2), _A(1)])
    assert at is not None and sorted(at.values()) == [1, 2, 3] and at[2] == 1


def _katalog(tmp_path, monkeypatch, iki_yuva):
    from itucap import config
    monkeypatch.setattr(config, "REF_DB", tmp_path / "ref.sqlite3")
    monkeypatch.setattr(config, "USER_DB", tmp_path / "user.sqlite3")
    con = db.connect(tmp_path / "ref.sqlite3", "schema.sql")
    ucon = db.connect(tmp_path / "user.sqlite3", "schema_user.sql")
    con.executemany("INSERT INTO course(code,name,ects,credits,prereq_raw) VALUES (?,?,?,?,NULL)",
                    [("MT 401E", "Seçmeli A", 5.0, 3.0), ("MT 402E", "Seçmeli B", 5.0, 3.0)])
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title,source)
                   VALUES (10,'ENDE','lisans','anadal','obs')""")
    for k in range(2 if iki_yuva else 1):
        cur = con.execute(
            """INSERT INTO plan_slot(plan_id,slot_kind,pool_label_raw,pool_category,
                                     ects,credits,position,term_no)
               VALUES (10,'ELECTIVE_POOL','Functional-MT','MT',5.0,3.0,?,?)""", (k, 5 + k))
        for kod in ("MT 401E", "MT 402E"):
            con.execute("INSERT INTO pool_option(slot_id,course_code) VALUES (?,?)",
                        (cur.lastrowid, kod))
    for crn, kod, gun in (("1", "MT 401E", 1), ("2", "MT 402E", 2)):
        con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled) VALUES (?,?,50,0)",
                    (crn, kod))
        con.execute("""INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min)
                       VALUES (?,?,480,600)""", (crn, gun))
        con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES (?,'ENDE')",
                    (crn,))
    con.commit()
    from itucap import student as S
    sid = S.ensure_student(ucon, "ben")
    return REC.candidates(con, ucon, sid, 10, None, "ENDE", "", {"ENDE"}, "kredi")


def test_MOTOR_iki_yuva_iki_ders(tmp_path, monkeypatch):
    cands = _katalog(tmp_path, monkeypatch, iki_yuva=True)
    assert {len(c.yuvalar) for c in cands} == {2}
    en_iyi = REC.build_schedules(cands, max_load=99, limit=3)[0]
    assert {p.candidate.course for p in en_iyi.picks} == {"MT 401E", "MT 402E"}


def test_MOTOR_tek_yuva_tek_ders(tmp_path, monkeypatch):
    """Eski kural bozulmadı: tek yuvaya iki ders sığmıyor."""
    cands = _katalog(tmp_path, monkeypatch, iki_yuva=False)
    for s in REC.build_schedules(cands, max_load=99, limit=3):
        assert len({p.candidate.course for p in s.picks} & {"MT 401E", "MT 402E"}) == 1


_CANLI = r'''
import sys, os, json
sys.path.insert(0, os.environ["ITUCAP_SRC"]); sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import vitrin
adres, h = vitrin.ac()
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    hatalar = []
    pg.on("pageerror", lambda e: hatalar.append(str(e)))
    pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(800)
    print("ATA:" + json.dumps(pg.evaluate("""() => [
      yuvaAta([{slotIds: [1, 2]}, {slotIds: [1]}]),
      yuvaAta([{slotIds: [1]}, {slotIds: [1]}]),
      yuvaAta([{slotId: 7}, {slotIds: []}])]""")))
    print("ALAN:" + json.dumps(pg.evaluate("() => M().candidates.every(c => Array.isArray(c.slotIds))")))
    # İstemci engeli: GEO 385E'nin havuzuna ikinci bir yuva eklenince GEO 381E artık engelli değil.
    print("ENGEL1:" + json.dumps(pg.evaluate("() => (poolBlocker(candOf('GEO 381E'), null) || {cand: {}}).cand.course || null")))
    print("ENGEL2:" + json.dumps(pg.evaluate("""() => { const c = candOf('GEO 381E');
        c.slotIds = [c.slotId, 999001]; return (poolBlocker(c, null) || {cand: {}}).cand.course || null; }""")))
    print("HATA:" + str(len(hatalar)) + " " + " | ".join(hatalar)[:300])
    b.close()
h.shutdown()
'''


def test_ISTEMCI_vitrin(tmp_path, monkeypatch):
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
    assert json.loads(c["ATA"]) == [[2, 1], None, [7, 0]]
    assert json.loads(c["ALAN"]) is True
    assert json.loads(c["ENGEL1"]) == "GEO 385E"      # tek yuva: yerine geçer
    assert json.loads(c["ENGEL2"]) is None            # boş ikinci yuva: engel yok
