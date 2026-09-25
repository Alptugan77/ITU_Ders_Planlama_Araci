"""Faz 102 — zorlukta AKTS (iş yükü).

Kullanıcı 25.09.2026: *"dönem ve ders zorluğunu hesaplarken aktsyi de hesaba
kat akts ne kadar emek gerektirdiğinin de bir göstergesi dersin"*.

* **Ders zorluğu:** not tabanlı genel puana 0.1 × (AKTS − 5) ekleniyor, en
  çok ±1. Ağırlıklı ortalama değil: o FIZ 102E'yi (4.5 AKTS) "çok zor"dan
  düşürüyordu; 0.1'in üstü MAT 103E'yi (6 AKTS) "çok zor"a itiyordu — ikisi
  de kullanıcının Faz 87 yargısına aykırı.
* **Dönem zorluğu:** yük artık AKTS (60 ağırlıklı AKTS = 10). Ağırlık not
  tabanlı puandan; AKTS iki kez sayılmıyor. AKTS'si bilinmeyen ders
  kredisinin 1.75 katı.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import notlar as ND, ui as UI
from test_faz57_yol_haritasi import ANADAL, _katalog, _kur
from test_faz85_zorluk import _ref


# ============================================================ ders düzeyi
@pytest.mark.parametrize("akts,etki", [
    (5, 0.0), (8, 0.3), (2, -0.3), (12, 0.7), (6, 0.1), (4.5, -0.05),
    (20, 1.0), (31.5, 1.0),                 # en çok +1
    (None, None), (0, None)])               # bilinmiyor → düzeltme YOK
def test_AKTS_etkisi(akts, etki):
    assert ND.akts_etkisi(akts) == etki


def test_KULLANICI_YARGISI_korunuyor():
    """Faz 87: "MAT 103 zor (çok zor değil), FIZ 102 çok zor" — gerçek
    katalogdaki not puanları ve AKTS'leriyle."""
    k = lambda puan, akts: ND.zorluk_kademesi(ND.akts_ile(puan, ND.akts_etkisi(akts)))
    assert k(8.3, 6.0) == 4                 # MAT 103E: 8.4, zor
    assert k(9.2, 4.5) == 5                 # FIZ 102E: 9.2, çok zor
    assert ND.akts_ile(0.0, -0.4) == 0.0 and ND.akts_ile(9.8, 1.0) == 10.0   # 0–10


def test_ZORLUK_AKTSyi_tasiyor(tmp_path):
    con = _ref(tmp_path, [("MAT 103", "202610", {"AA": 10, "CC": 30, "FF": 20, "VF": 40}),
                          ("LAB 101", "202610", {"AA": 10, "CC": 30, "FF": 20, "VF": 40}),
                          ("YOK 100", "202610", {"AA": 10, "CC": 30, "FF": 20, "VF": 40})])
    con.executemany("INSERT INTO course(code,name,credits,ects) VALUES (?,?,?,?)",
                    [("MAT 103", "M", 4, 12.0), ("LAB 101", "L", 1, None), ("YOK 100", "Y", 3, None)])
    # LAB 101'in katalogda AKTS'si yok ama bir planda var → oradan.
    con.execute("INSERT INTO plan(id,program_code,plan_type,title,source) VALUES (1,'A','lisans','x','obs')")
    con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,ects,position) "
                "VALUES (1,'REQUIRED','LAB 101',2.0,0)")
    con.commit()
    m = ND.zorluk(con, "MAT 103")
    # Not tabanlı 9.3 (Faz 85 testindeki dağılım); 12 AKTS → +0.7 → 10'da kırpılır.
    assert (m["gradeOverall"], m["ects"], m["ectsEffect"], m["score"]) == (9.3, 12.0, 0.7, 10.0)
    lab = ND.zorluk(con, "LAB 101")
    assert (lab["ects"], lab["ectsEffect"], lab["score"]) == (2.0, -0.3, 9.0)
    y = ND.zorluk(con, "YOK 100")
    assert (y["ects"], y["ectsEffect"], y["score"]) == (None, None, 9.3)   # AKTS yok: dokunulmuyor


def test_YOL_HARITASI_kalemleri_AKTS_tasiyor(tmp_path):
    con = _katalog(tmp_path, [("AAA 101", 3, None), ("AAA 102", 4, None)],
                   plan=[("AAA 101", 5), ("AAA 102", 6)])
    h = _kur(con, {})
    akts = {i["course"]: i["ects"] for t in h["terms"] for i in t["items"]}
    assert akts == {"AAA 101": 5.0, "AAA 102": 6.0}          # _katalog: AKTS = kredi + 2


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
    print("DZ:" + json.dumps(pg.evaluate("""() => {
      const d = (s, e, k = 3, g) => ({akts: e, kredi: k, z: {level: zorlukKademesi(s), score: s,
                                       ...(g === undefined ? {} : {gradeOverall: g})}});
      const f = (l) => { const z = donemZorlugu(l); return [z.donem, z.akts, z.aktsTahmin, z.ort]; };
      return {
        ayniKrediFarkliAkts: [f([d(5, 3)]), f([d(5, 9)])],
        notTabanliAgirlik: f([d(5.7, 12, 3, 5.0)]),     // puan AKTS düzeltmeli, ağırlık notla
        aktsYok: f([{akts: 0, kredi: 4, z: {level: 3, score: 5}}]),
        ortalamaAktsAgirlikli: f([d(9, 10), d(1, 2)]),
      }; }""")))
    # Özet: bir dersin AKTS'si bilinmiyorsa söylüyor.
    print("OZET:" + pg.evaluate("""() => { picks()[0].cand.ects = 0; render();
      return document.querySelector('#schedSummary .ozetzorluk').textContent.replace(/\\s+/g,' '); }"""))
    # Ders penceresi: iş yükü satırı.
    print("KUTU:" + json.dumps(pg.evaluate("""() => {
      const c = candOf(sel.find(x => zorlukOf(candOf(x.course))).course), z = c.grades.difficulty;
      const g = z.score;
      Object.assign(z, {ects: 8, ectsEffect: 0.3, gradeOverall: g, score: +(g + 0.3).toFixed(1)});
      courseDialog(c.course);
      const a = document.querySelector('#detail .zakts').textContent.replace(/\\s+/g,' ').trim();
      document.querySelector('#detail').close();
      Object.assign(z, {ects: null, ectsEffect: null});
      courseDialog(c.course);
      const b = document.querySelector('#detail .zakts').textContent.replace(/\\s+/g,' ').trim();
      document.querySelector('#detail').close();
      return [a, b, zorlukIpucu(Object.assign({}, z, {ects: 2, ectsEffect: -0.3}))]; }"""), ensure_ascii=False))
    # Yol haritası kartı: aynı hesap.
    print("YH:" + pg.evaluate("""() => { const t = {items: [
        {ects: 30, credits: 18, difficulty: {level: 3, score: 5, gradeOverall: 5}},
        {ects: 6, credits: 4, difficulty: {level: 5, score: 9.4, gradeOverall: 9}}]};
      const d = document.createElement('div'); d.innerHTML = yhZorluk(t);
      return d.textContent.replace(/\\s+/g,' ').trim() + '|' + yhZorluk({items: [{ects: 5, credits: 3, difficulty: null}]}); }"""))
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
    d = json.loads(c["DZ"])
    # Aynı kredi, üç kat AKTS → üç kat yük.
    assert d["ayniKrediFarkliAkts"] == [[0.5, 3, 0, 5], [1.5, 9, 0, 5]]
    # Ağırlık not tabanlı puandan (5.0 → 1.0): 12 × 1.0 / 60 = 2.0. Düzeltmeli
    # puan (5.7) kullanılsaydı 2.1 olurdu — AKTS iki kez sayılırdı.
    assert d["notTabanliAgirlik"][0] == 2.0
    # AKTS yoksa kredi × 1.75 ve sayılıyor: 4 × 1.75 = 7 → 7 / 60 × 10 = 1.2.
    assert d["aktsYok"] == [1.2, 7, 1, 5]
    # Ders ortalaması AKTS ağırlıklı: (9×10 + 1×2) / 12 = 7.7.
    assert d["ortalamaAktsAgirlikli"][3] == 7.7
    assert "40 AKTS" not in c["OZET"] and " AKTS (1 dersin AKTS'si kredisinden tahmin edildi)" in c["OZET"], c["OZET"]
    a, b, ipucu = json.loads(c["KUTU"])
    assert a.startswith("İş yükü: 8 AKTS (tipik ders 5) → genel puana +0.3 (not tabanlı puan"), a
    assert b == "İş yükü: AKTS bilinmediğinden hesaba katılmadı.", b
    assert "İş yükü 2 AKTS (tipik ders 5): −0.3." in ipucu, ipucu
    yh, bos = c["YH"].split("|")
    # (30×1.0 + 6×1.4) / 60 × 10 = 6.4
    assert yh == "tahmini dönem zorluğu 6.4/10 (zor) · 1 zor ders", yh
    assert bos == ""                                 # zorluk verisi yoksa satır yok
