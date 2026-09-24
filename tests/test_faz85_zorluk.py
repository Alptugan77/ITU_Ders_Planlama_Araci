"""Faz 85 — derslerin tahmini zorluğu (geçmiş not ortalamasından).

Kullanıcı 24.09.2026: *"derslerin önceki dönemlerdeki not ortalaması ve
dağılımına göre tahmini zorluk derecelendirilmesi yapabilir misin ve bunu
kullanıcıya uygun bir şekilde sunar mısın"*.

Yan bulgu: BL/BZ ile notlanan derslerde (ATA 121, TUR 121) ortalama BL=1.0
sayılarak "0.84" çıkıyor, BZ "geçti" sayılıyordu.
"""
import json
import pathlib
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import db
from itucap import notlar as ND
from itucap import ui as UI

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


# ------------------------------------------------------------ BL/BZ düzeltmesi
def test_BLBZ_ortalamaya_girmiyor_BZ_basarisiz():
    o = ND.summarise({"BL": 1579, "BZ": 336, "VF": 374})
    assert o["meanPoints"] is None                     # eskiden 0.84 / 0.0
    assert o["failed"] == 336 and o["passed"] == 1579 and o["passFail"] == 1915
    # Harf notlu ders değişmedi (VF GNO ölçeğinde 0 — Faz 38 kuralı).
    assert ND.summarise({"AA": 1, "VF": 99})["meanPoints"] == 0.04
    assert ND.summarise({"AA": 1})["passFail"] == 0


def test_BLBZ_kovasi_yalniz_varsa():
    assert [b["key"] for b in ND.bucketise({"AA": 3})][-1] == "VF"
    k = ND.bucketise({"BL": 5, "BZ": 1})
    assert [b["key"] for b in k][-2:] == ["BL", "BZ"] and k[-1]["total"] == 1


# ------------------------------------------------------------ ölçü
def test_ORTALAMA_VFsiz_ve_tekrar_sinifi_haric():
    z = ND.zorluk_ortalamasi({
        "202610": {"AA": 50, "FF": 50, "VF": 400},    # olağan dönem, VF yok sayılır
        "202620": {"FF": 3},                           # bütünleme sınıfı (%3) → havuz dışı
    })
    assert z == {"mean": 2.0, "n": 100, "failRate": 50.0, "terms": ["202610"]}
    assert ND.zorluk_ortalamasi({"202610": {"BL": 9, "VF": 2}}) is None


def test_KADEME_sabit_tablolar_ve_canli_yuzdelik():
    """(Faz 86: kademe geçme oranı + ortalamadan; ayrıntı test_faz86.)"""
    S = ND.SABIT_OLCEK
    assert ND.zorluk_kademesi(25.0, 1.8, S)["level"] == 5
    assert ND.zorluk_kademesi(0.0, 3.8, S)["level"] == 1
    assert ND.zorluk_kademesi(5.0, 2.7, S)["level"] == 3
    k = ND.zorluk_kademesi(25.0, 1.8, S)
    assert k["scale"] == "sabit" and k["passLowerShare"] is None and k["catalog"] is None


def _ref(tmp_path, dagilim):
    con = db.connect(tmp_path / "ref.sqlite3", "schema.sql")
    for kod, donem, sayilar in dagilim:
        for harf, n in sayilar.items():
            con.execute("INSERT INTO grade_distribution(course_key,term,grade,students,"
                        "announced) VALUES (?,?,?,?,?)", (kod, donem, harf, n, 0))
        con.execute("INSERT OR IGNORE INTO grade_distribution_alias(course_code,course_key)"
                    " VALUES (?,?)", (kod, kod))
    con.commit()
    return con


def test_ZORLUK_ucu(tmp_path):
    con = _ref(tmp_path, [
        ("ATA 121", "202610", {"BL": 90, "BZ": 10, "VF": 5}),
        ("SEM 101", "202610", {"AA": 5, "BB": 5}),
        ("MAT 103", "202610", {"AA": 10, "CC": 30, "FF": 20, "VF": 40}),
        ("ING 100", "202610", {"AA": 300, "BA": 100}),
    ])
    assert ND.zorluk(con, "YOK 999") is None
    assert ND.zorluk(con, "ATA 121") == {"level": None, "reason":
        "Ders başarılı/başarısız (BL/BZ) ile notlanmaktadır; harf notu ortalaması yoktur."}
    az = ND.zorluk(con, "SEM 101")
    assert az["level"] is None and "yalnızca 10 harf notu" in az["reason"]
    m = ND.zorluk(con, "MAT 103")
    assert (m["level"], m["label"], m["mean"], m["n"], m["failRate"], m["passRate"]) == (
        5, "çok zor", 1.67, 60, 33.3, 66.7)
    assert m["scale"] == "sabit" and m["passLowerShare"] is None and m["lowData"] is False
    assert m["termLabels"] == ["2025-2026 Güz"]
    i = ND.zorluk(con, "ING 100")
    assert (i["level"], i["label"]) == (1, "çok kolay")
    # Önbellek veri değişince tazeleniyor (yeni çekim satır ekler).
    con.execute("INSERT INTO grade_distribution(course_key,term,grade,students,announced)"
                " VALUES ('SEM 101','202620','CC',40,0)")
    con.commit()
    assert ND.zorluk(con, "SEM 101")["level"] is not None


def test_ONERI_PUANINA_GIRMIYOR():
    """Faz 38 kuralı: gösteriyoruz, karar öğrencinin."""
    rec = (pathlib.Path(UI.__file__).parent / "recommend.py").read_text(encoding="utf-8")
    assert "zorluk" not in rec and "difficulty" not in rec
    assert "Bu bilgi öneri puanına <b>dahil edilmez</b>" in KAYNAK


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
    pg.evaluate("() => gorunumAc('candSection')"); pg.wait_for_timeout(300)
    print("ROZET:" + json.dumps(pg.evaluate("""() => Object.fromEntries([...document.querySelectorAll('#cands tbody tr')]
        .map(r => [r.dataset.course, (r.querySelector('.zorluk') || {textContent: ''}).textContent.replace(/\\s+/g,' ').trim()])
        .filter(x => x[1]))"""), ensure_ascii=False))
    pg.select_option("#candSort", "zor"); pg.wait_for_timeout(200)
    print("SIRA:" + json.dumps(pg.evaluate("() => [...document.querySelectorAll('#cands tbody tr')].map(r => r.dataset.course)")))
    # Faz 86 — aynı kademede geçme oranı ortalamadan önce gelir.
    print("ESIT:" + json.dumps(pg.evaluate("""() => siralanmis([
        {course: 'A', grades: {difficulty: {level: 3, passRate: 90, mean: 3.4}}},
        {course: 'B', grades: {difficulty: {level: 3, passRate: 97, mean: 2.2}}},
        {course: 'C', grades: {difficulty: {level: 3, passRate: 97, mean: 2.9}}},
        {course: 'D', grades: null}]).map(c => c.course)""")))
    print("OZET:" + pg.evaluate("() => (document.querySelector('#schedSummary .ozetzorluk')||{textContent:''}).textContent.replace(/\\s+/g,' ')"))
    pg.evaluate("() => addDialog('MAT 210E')"); pg.wait_for_timeout(300)
    print("KUTU:" + pg.evaluate("() => (document.querySelector('#detail .zorlukkutu')||{textContent:''}).textContent.replace(/\\s+/g,' ')"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    pg.evaluate("() => gorunumAc('roadmapSection')"); pg.wait_for_timeout(300)
    print("YH:" + json.dumps(pg.evaluate("""() => [...document.querySelectorAll('.yhdonem')].map(s =>
        [s.querySelector('h3 span').textContent, (s.querySelector('.yhzorluk')||{textContent:''}).textContent.replace(/\\s+/g,' ').trim(),
         [...s.querySelectorAll('li')].filter(li => li.querySelector('.zorluk')).map(li => li.querySelector('.mono').textContent)])""")))
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
    rozet = json.loads(c["ROZET"])
    assert rozet["MAT 210E"] == "tahmini zorluk: çok zor", rozet
    assert rozet["BLG 223E"] == "tahmini zorluk: zor"
    assert rozet["GEO 321E"] == "tahmini zorluk: orta · az veri"   # n=24 < 60
    sira = json.loads(c["SIRA"])
    # Kolaydan zora; verisi olmayan sonda. (Faz 86: GEO 315E FF ≈ %8 → zor.)
    assert sira[:5] == ["GEO 321E", "GEO 341E", "GEO 315E", "BLG 223E", "MAT 210E"], sira
    assert json.loads(c["ESIT"]) == ["C", "B", "A", "D"]
    # (Faz 86: GEO 315E FF ≈ %8 → orta'dan zor'a)
    assert c["OZET"].startswith("tahmini zorluk: 2 zor · 1 orta · 5 ders için veri yok"), c["OZET"]
    k = c["KUTU"]
    assert "Tahmini zorluk" in k and "5 / 5" in k, k
    assert "geçme oranı %79.2 ortalama 1.83 n=106" in k and "dahil edilmez" in k
    assert "Olağan dönemler: 2025-26 Güz; VF hariç." in k
    yh = json.loads(c["YH"])
    bahar = [x for x in yh if x[0] == "2026-2027 Bahar"][0]
    assert bahar[1] == "tahmini zorluk: 1 zor ders" and "MAT 210E" in bahar[2], bahar
    simdi = yh[0]
    assert "BLG 223E" in simdi[2], simdi          # bu dönemin kartında da
