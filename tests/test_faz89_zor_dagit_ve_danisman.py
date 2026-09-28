"""Faz 89 — "zor dersleri dağıt" senaryosu ve danışman özetinde zorluk.

Kullanıcı 24.09.2026: *"geliştirmelere devam et ve sonrasında pr oluştur"*.
Yol haritası (Faz 85) dönem kartında "N zor ders" diyordu ama öğrenci "zor
dersleri dağıtırsam ne zaman biterim" sorusunu soramıyordu. Danışman özeti
(Faz 61) zorluktan hiç söz etmiyordu.
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
ZOR = {"AA": 5, "CC": 40, "DD": 20, "FF": 25, "VF": 10}      # geçme %65 → çok zor
KOLAY = {"AA": 60, "BA": 30, "BB": 10}
# "zor" kademesi (4, çok zor DEĞİL): geçme %80 → 6.7, ortalama 1.80 → 7.3 → 6.9.
ZOR4 = {"AA": 10, "BB": 20, "CC": 30, "DD": 20, "FF": 20}


def _katalog(tmp_path, dersler):
    """dersler: [(kod, dağılım ya da None)] — hepsi 7. yarıyıl (Güz)."""
    con = db.connect(tmp_path / "ref.sqlite3", "schema.sql")
    con.execute("INSERT INTO program(code,name,level) VALUES ('AAA','A Müh.','LS')")
    con.execute("INSERT INTO plan(id,program_code,plan_type,title,source) "
                "VALUES (1,'AAA','lisans','x','obs')")
    for i, (kod, dagilim) in enumerate(dersler):
        con.execute("INSERT INTO course(code,name,credits,ects) VALUES (?,?,3,5)",
                    (kod, "Ders " + kod))
        con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,credits,position,"
                    "term_no) VALUES (1,'REQUIRED',?,3,?,7)", (kod, i))
        for g, n in (dagilim or {}).items():
            con.execute("INSERT INTO grade_distribution(course_key,term,grade,students,"
                        "announced) VALUES (?,?,?,?,0)", (kod, "202610", g, n))
        if dagilim:
            con.execute("INSERT INTO grade_distribution_alias VALUES (?,?)", (kod, kod))
    P.parse_all(con)
    con.commit()
    return con


def _kur(con, zor=None, ufuk=YH.UFUK, rol="ANADAL", taban=None):
    return YH.kur(con, {}, [{"planId": 1, "role": rol, "label": rol.lower(),
                             "program": "AAA"}],
                  term="202710", donem=5, max_load=21, bu_donem=[], zor_siniri=zor,
                  ufuk=ufuk, taban=taban)


def _yer(h):
    return {i["course"]: t["label"] for t in h["terms"] for i in t["items"] if i["course"]}


def test_SINIRSIZ_hepsi_ayni_donemde(tmp_path):
    con = _katalog(tmp_path, [("AAA 401", ZOR), ("AAA 402", ZOR), ("AAA 403", ZOR)])
    h = _kur(con)
    assert set(_yer(h).values()) == {"2027-2028 Güz"}
    assert not any("zor ders" in a for a in h["assumptions"])


def test_SINIR_zor_dersleri_dagitiyor(tmp_path):
    # AAA 400 (kolay) öncelikte zor derslerden ÖNCE: sınır YALNIZ zor dersleri
    # saymalı. AAA 402 "zor" kademesinde (4) — "çok zor"la aynı sayılmalı.
    con = _katalog(tmp_path, [("AAA 400", KOLAY), ("AAA 401", ZOR), ("AAA 402", ZOR4),
                              ("AAA 403", ZOR), ("AAA 404", KOLAY), ("AAA 405", None)])
    h = _kur(con, zor=1)
    yer = _yer(h)
    assert yer["AAA 401"] == "2027-2028 Güz" and yer["AAA 402"] == "2028-2029 Güz"
    assert yer["AAA 403"] == "2029-2030 Güz"
    # Kolay ve zorluğu BİLİNMEYEN ders sınıra sayılmıyor.
    assert yer["AAA 400"] == yer["AAA 404"] == yer["AAA 405"] == "2027-2028 Güz", yer
    ilk = [t for t in h["terms"] if t["label"] == "2027-2028 Güz"][0]
    assert ilk["hardDeferred"] == ["AAA 402", "AAA 403"]
    assert h["programs"][0]["finish"]["label"] == "2029-2030 Güz"
    assert any(a.startswith("Her döneme en çok 1 zor ders") for a in h["assumptions"])
    iki = _yer(_kur(con, zor=2))
    assert iki["AAA 402"] == "2027-2028 Güz" and iki["AAA 403"] == "2028-2029 Güz"


def test_CAP_TABANI_gecisinde_de_sinir(tmp_path):
    """ÇAP yarıyıl tabanı varken motor önce ÇAP derslerini ayrı bir geçişte
    alıyor; sınır o geçişte de uygulanmalı."""
    from itucap import policy as POL
    con = _katalog(tmp_path, [("AAA 401", ZOR), ("AAA 402", ZOR)])
    taban = POL.SecondFloor(minimum=6.0, start_term=5)
    yer = _yer(_kur(con, zor=1, rol="CAP", taban=taban))
    assert yer["AAA 401"] != yer["AAA 402"], yer


def test_UFUK_asilirsa_gerekce(tmp_path):
    con = _katalog(tmp_path, [("AAA 401", ZOR), ("AAA 402", ZOR)])
    h = _kur(con, zor=1, ufuk=2)                      # yalnız bir Güz var
    neden = {u["course"]: u["reason"] for u in h["unplaced"]}
    assert neden["AAA 402"] == ("dönem başına en çok 1 zor ders senaryosunda "
                                "2 dönem içinde yerleştirilememiştir"), neden


def test_ARAYUZ_statik():
    assert 'bos: [...A.bos], zor: A.zor || null});' in KAYNAK
    assert "if(A.maxLoad === T.maxLoad && !A.bos.size && !A.zor)" in KAYNAK
    assert "Dönem başına zor ders\n        sınırı nedeniyle sonraki döneme bırakıldı" in KAYNAK


_CANLI = r'''
import sys, os, json
sys.path.insert(0, os.environ["ITUCAP_SRC"]); sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import vitrin
adres, h = vitrin.ac()
from itucap import server
st = server.State(label="ben")
R = st.snapshot()["roadmap"]
bu = [{"course": i["course"], "credits": i["credits"], "role": (i["roles"] or [""])[0]}
      for i in R["terms"][0]["items"]]
for zor in (9, "x", -1):
    try:
        st.dispatch("/api/yolharitasi", {"bu": bu, "maxLoad": 25, "bos": [], "zor": zor}); print("RED:yok")
    except ValueError as e:
        print("RED:" + str(e))
S = st.dispatch("/api/yolharitasi", {"bu": bu, "maxLoad": 25, "bos": [], "zor": 1})["senaryo"]
print("SEN:" + json.dumps(S["scenario"]))
S0 = st.dispatch("/api/yolharitasi", {"bu": bu, "maxLoad": 25, "bos": [], "zor": 0})["senaryo"]
print("SEN0:" + json.dumps(S0["scenario"]))
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 1000})
    hatalar = []
    pg.on("pageerror", lambda e: hatalar.append(str(e)))
    pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(800)
    pg.evaluate("() => gorunumAc('roadmapSection')"); pg.wait_for_timeout(1200)
    print("SECIM:" + json.dumps(pg.evaluate("() => [...document.querySelectorAll('#yhZor option')].map(o => o.textContent)")))
    pg.select_option("#yhZor", "1"); pg.wait_for_timeout(1200)
    print("SERIT:" + pg.evaluate("() => (document.querySelector('.yhseritsenaryo')||{textContent:''}).textContent.replace(/\\s+/g,' ').trim()"))
    print("AYAR:" + json.dumps(pg.evaluate("() => YH_AYAR.zor")))
    # Danışman özeti: gerçek vitrin (zor ders yok) ve üç zor dersli program.
    print("D0:" + pg.evaluate("() => { const d = document.createElement('div'); d.innerHTML = danismanOzeti(); return d.textContent.replace(/\\s+/g,' '); }"))
    pg.evaluate("""() => picks().slice(0, 3).forEach((p, i) =>
        p.cand.grades = {difficulty: {level: 5, label: 'çok zor', score: 9.0 - i, passRate: 70 + i, mean: 1.9}})""")
    pg.evaluate("""() => {
      const pr = (d) => [{role: 'ANADAL', label: 'anadal', delay: d, finish: {label: 'X'}, finishSemester: 9}];
      const ps = picks();
      KALMA = {anahtar: kalmaAnahtari(), yukleniyor: false, hata: '', veri: {
        courses: [{course: ps[0].cand.course, programs: pr(1)}, {course: ps[1].cand.course, programs: pr(0)}],
        base: [{label: 'anadal', finish: {label: 'Y'}}]}}; }""")
    print("D1:" + pg.evaluate("() => { const d = document.createElement('div'); d.innerHTML = danismanOzeti(); return d.textContent.replace(/\\s+/g,' '); }"))
    print("ILK:" + json.dumps(pg.evaluate("() => picks().slice(0, 3).map(p => p.cand.course)")))
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
    satir = [s for s in r.stdout.strip().splitlines() if ":" in s]
    red = [s.split(":", 1)[1] for s in satir if s.startswith("RED:")]
    assert red == ["zor ders sınırı geçersiz"] * 3, red
    c = dict(s.split(":", 1) for s in satir if s.split(":", 1)[0].isupper())
    assert c["HATA"].startswith("0"), c["HATA"]
    assert json.loads(c["SEN"])["hardMax"] == 1
    assert json.loads(c["SEN0"])["hardMax"] is None                 # 0 → sınır yok
    assert json.loads(c["SECIM"]) == ["sınırsız", "1", "2", "3"]
    assert "dönem başına en çok 1 zor ders" in c["SERIT"], c["SERIT"]
    assert json.loads(c["AYAR"]) == 1
    d0, d1, ilk = c["D0"], c["D1"], json.loads(c["ILK"])
    # Tabloda sütun; vitrinde BLG 223E orta 5.5, verisizde "—".
    assert "Tahmini zorluk" in d0 and "orta 5.5" in d0, d0
    assert ("Tahmini dönem zorluğu 6.4 / 10 (zor; 8 ders, 40 AKTS; geçmiş not dağılımından) · "
            "ders ortalaması 3.8 · zor ders yok") in d0          # Faz 100
    assert "zor ders bulunmaktadır" not in d0 and "hazırlanmam önerilir" not in d0
  # Faz 112: özet yalnız DİLEKÇE gerektirenleri listeliyor: zor ders ve
    # kalma riski soruları yok (tablo ve kontroller satırı duruyor).
    assert "zor ders bulunmaktadır" not in d1 and "kalmam mezuniyetimi" not in d1, d1
    assert "3 zor ders" in d1, d1
    assert f"{ilk[1]} dersinden kalmam" not in d1                       # gecikme 0
