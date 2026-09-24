"""Faz 79 — gerçek sitede 7. yarıyıl (ÇAP'sız) öğrencisiyle bulunan üç hata.

Kullanıcı 24.09.2026: *"geliştirmelere devam et ve sonrasında pr oluştur"*.
Site gerçek katalogla kuruldu; ENDE, 7. yarıyıl, ikinci program yok, 34
derslik transkript (2021 planı):

1. "TUR 121 Türk Dili I 0 2 BL" satırında "Türk"ün "T"si not (T = çekilme)
   okunuyordu → ders BAŞARISIZ kaydedilip yeniden öneriliyordu.
2. İkinci programı olmayan öğrenci "ÇAP'a devam ≥ 2.50 ✗", "ÇAP mezuniyeti ✗"
   görüyor; danışman özeti ona ÇAP soruları yazıyordu.
3. İstek üzerine kurulan haritalar (kalma riski, senaryo, ÇAP seçenekleri)
   bu dönem alınan seçmelinin havuz yuvasını bilmiyordu → aynı program için
   sayfadaki harita "2027-2028 Güz", kalma riskinin tabanı "2027-2028 Bahar".
"""
import json
import pathlib
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import student as S
from itucap import ui as UI

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


def _js(ad):
    f = KAYNAK[KAYNAK.index(f"function {ad}("):]
    return f[:f.index("\n}\n")]


# ------------------------------------------------------------------ 1. ayrıştırıcı
@pytest.mark.parametrize("satir,kod,notu,durum", [
    ("TUR 121 Türk Dili I 0 2 BL", "TUR 121", "BL", "PASSED"),
    ("TUR 122 Türk Dili II 0 2 BL", "TUR 122", "BL", "PASSED"),
    ("MAT 103E Mühendislik Matematiği 4 6 CC", "MAT 103E", "CC", "PASSED"),
    ("EKO 201E Ekonomi 3 4 CB", "EKO 201E", "CB", "PASSED"),
    # Gerçek T (çekilme) ve kısa biçimler bozulmadı.
    ("TUR 121 T", "TUR 121", "T", "FAILED"),
    ("TUR 121 T # çekildim", "TUR 121", "T", "FAILED"),
    ("mat 103e cc", "MAT 103E", "CC", "PASSED"),
    ("MAT 103E, BB", "MAT 103E", "BB", "PASSED"),
    ("MAT 103E|AA", "MAT 103E", "AA", "PASSED"),
    ("MAT 103E BA+", "MAT 103E", "BA+", "PASSED"),
    ("MAT 103E    Mathematics I    4.0   6.0   BB", "MAT 103E", "BB", "PASSED"),
])
def test_NOT_ayracla_bitmeli(satir, kod, notu, durum):
    e = S.parse_line(satir)
    assert (e.course_code, e.grade, e.status) == (kod, notu, durum), e


def test_devam_isaretleri_bozulmadi():
    for satir in ("MAT 103E --", "MAT 103E ?"):
        assert S.parse_line(satir).status == "IN_PROGRESS"


# ------------------------------------------------------------------ 2-3. statik
def test_ESIK_ve_YUVA_kurallari():
    i = KAYNAK.index("def _threshold_info(")
    k = KAYNAK[i:KAYNAK.index("\ndef ", i + 1)]
    assert 'if scope == "genel" and t.program not in ("genel", "") and t.kind != "basvuru":' in k
    assert "_threshold_info(con, ucon, student_id, gpa, seconds + plansiz)" in KAYNAK
    assert '"slotId": _slot(x),' in KAYNAK
    # (Faz 81: yuva artık eşleştirmeden — birincil yuva yedek.)
    assert "slotId: atama[i] || p.cand.slotId || 0" in _js("kalmaGirdi")
    assert "slotId: i.slotId || 0" in _js("capBitisGirdi")
    yh = (pathlib.Path(UI.__file__).parent / "yolharitasi.py").read_text(encoding="utf-8")
    assert '"slotId": p.get("slotId") or 0,' in yh      # (Faz 85: ardından zorluk alanı)


_CANLI = r'''
import sys, os, json
sys.path.insert(0, os.environ["ITUCAP_SRC"]); sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import vitrin
adres, h = vitrin.ac()
from itucap import server, ui as UI, policy as POL, student as S
st = server.State(label="ben")
R = st.snapshot()["roadmap"]
items = R["terms"][0]["items"]
print("ITEM:" + json.dumps([[i["course"], i["slotId"]] for i in items]))
bu = [{"course": i["course"], "credits": i["credits"], "role": i["roles"][0], "slotId": i["slotId"]}
      for i in items]
g = UI._harita_girdisi(st.con, st.ucon, st.student_id, st.settings(),
                       bu + [{"course": "X 1", "slotId": "bozuk"}, {"course": "Y 2", "slotId": -4}],
                       R["maxLoad"])
print("GIRDI:" + json.dumps([[x["course"], x["slotId"]] for x in g["bu"]]))
k = st.dispatch("/api/kalmariski", {"bu": bu, "maxLoad": R["maxLoad"]})["kalmaRiski"]
print("TABAN:" + json.dumps({b["role"]: b["finishSemester"] for b in k["base"]}))
print("HARITA:" + json.dumps({p["role"]: p["finishSemester"] for p in R["programs"]}))
# İkinci programı OLMAYAN öğrenci: yalnız genel + başvuru eşikleri.
st.dispatch("/api/programs", {"anadalProgram": "HTAE", "secondKind": "yok"})
print("YOK:" + json.dumps(sorted(t["key"] for t in st.snapshot()["gpa"]["thresholds"])))
# Planı bulunamayan ama beyan edilen ÇAP: ÇAP eşikleri kaybolmuyor.
gpa = POL.gpa(st.con, S.graded(st.ucon, st.student_id), S.uncertain_grades(st.ucon, st.student_id))
esik = UI._threshold_info(st.con, st.ucon, st.student_id, gpa,
                          [{"kind": "cap", "label": "ÇAP", "planId": None}])
print("PLANSIZ:" + json.dumps(sorted(t["key"] for t in esik)))
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 1000})
    hatalar = []
    pg.on("pageerror", lambda e: hatalar.append(str(e)))
    pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(1000)
    print("SORU:" + json.dumps(pg.evaluate("() => danismanSorulari().filter(s => /ÇAP'a devam|ÇAP mezuniyeti/.test(s)).length")))
    print("PANEL:" + pg.evaluate("() => document.querySelector('#gpaBody').textContent.replace(/\\s+/g,' ')"))
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
    item = json.loads(c["ITEM"])
    assert item and all(s > 0 for _, s in item), item          # yuva sayfada biliniyor
    girdi = dict(json.loads(c["GIRDI"]))
    assert all(girdi[k] == s for k, s in item), girdi           # istek ucu yuvayı koruyor
    assert girdi["X 1"] == 0 and girdi["Y 2"] == 0              # bozuk değer → 0
    assert json.loads(c["TABAN"]) == json.loads(c["HARITA"])    # aynı program, aynı bitiş
    yok = json.loads(c["YOK"])
    assert yok == ["basvuru", "mezuniyet", "yandal_basvuru"], yok
    plansiz = json.loads(c["PLANSIZ"])
    for k in ("basvuru", "devam", "cap_mezuniyet_universite", "cap_mezuniyet_ikinci", "mezuniyet"):
        assert k in plansiz, (k, plansiz)
    assert "yandal_devam" not in plansiz
    assert json.loads(c["SORU"]) == 0
    assert "ÇAP'a devam" not in c["PANEL"] and "ÇAP mezuniyeti" not in c["PANEL"], c["PANEL"]
    assert "Mezuniyet ≥ 2.00" in c["PANEL"]
