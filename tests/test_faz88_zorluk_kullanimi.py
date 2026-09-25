"""Faz 88 — tahmini zorluk kararın verildiği yerlerde.

Kullanıcı 24.09.2026: *"geliştirmelere devam et ve sonrasında pr oluştur"*.
Faz 85–87 zorluğu dersin satırında ve penceresinde gösteriyordu; öğrencinin
programlar ARASINDA seçtiği ve "kalırsam ne olur" diye baktığı yerlerde
yoktu. Ayrıca not dağılımı kutusu "VF zorluğu göstermez" diyordu — Faz 87'de
VF geçemeyenlere sayılmaya başlanınca bu cümle hesapla çelişiyordu.

1. Karşılaştırma: kredi ağırlıklı ortalama zorluk + zor ders sayısı.
2. Program özeti: aynı ortalama.
3. Kalma riski: geçmişte kalma oranı (FF + VF), öncelik satırı.
4. Not senaryosu: geçmişteki ortanca notla doldur.
5. VF metni tutarlı.
"""
import json
import pathlib
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import notlar as ND
from itucap import ui as UI

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


@pytest.mark.parametrize("sayilar,ortanca", [
    ({"AA": 1, "BB": 1, "CC": 1}, "BB"),                         # tek sayı: ortadaki
    ({"AA": 1, "BB": 1, "CC": 1, "FF": 1}, "CC"),                # çift: ortadaki ikisinden düşüğü
    ({"AA": 1, "BB": 1, "CC": 1, "FF": 1, "VF": 50}, "CC"),      # VF ortancaya girmiyor
    ({"BA+": 3, "CC": 1}, "BA+"),
])
def test_ORTANCA(sayilar, ortanca):
    assert ND.zorluk_ortalamasi({"202610": sayilar})["median"] == ortanca


def test_VF_METNI_tutarli():
    assert "VF devamsızlığı</b> gösterir, dersin zorluğunu göstermez" not in KAYNAK
    assert "dersin zorluğu hakkında bilgi vermez" not in KAYNAK
    assert "final sınavına girme koşulunu sağlayamayan öğrencileri" in KAYNAK


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
    T = lambda s: pg.evaluate("(s) => (document.querySelector(s)||{textContent:''}).textContent.replace(/\\s+/g,' ').trim()", s)
    print("PZ:" + json.dumps(pg.evaluate("""() => programZorlugu([
        {credits: 4, grades: {difficulty: {level: 5, score: 9.0}}},
        {credits: 1, grades: {difficulty: {level: 1, score: 1.0}}},
        {credits: 3, grades: null}])""")))
    print("OZET:" + T("#schedSummary .ozetzorluk"))
    # (Faz 90: öneriler değişti; farkı yaratan ders artık elle seçiliyor.)
    # Yalnız 2. sütunda olan bir derse yüksek zorluk ver: sütunlar ayrışır ama
    # derslerin yarısından azı bilindiği için "en hafif" yazılmamalı.
    print("FARK:" + pg.evaluate("""() => { const s = karsilastirmaSutunlari();
        const k = s[1].olcu.courses.find(x => !s[0].olcu.courses.includes(x));
        candOf(k).grades = {difficulty: {level: 5, score: 9.0, passRate: 60, mean: 1.5}}; return k; }"""))
    pg.evaluate("() => karsilastirDialog()"); pg.wait_for_timeout(200)
    sat = "() => [...document.querySelectorAll('#detail table.cmp tr')].filter(t => /Tahmini zorluk/.test(t.textContent)).map(t => [...t.querySelectorAll('td')].map(d => d.textContent.replace(/\\s+/g,' ').trim()))[0]"
    print("CMP1:" + json.dumps(pg.evaluate(sat), ensure_ascii=False))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    # Bütün derslerin verisi olsun → "en hafif" gösterilebilir.
    pg.evaluate("""() => [...(DATA.candidates || []), ...MODES.flatMap(m => m.candidates)].forEach(c => {
        if(!zorlukOf(c)) c.grades = {difficulty: {level: 3, score: 5.0, passRate: 88, mean: 2.6}}; })""")
    pg.evaluate("() => karsilastirDialog()"); pg.wait_for_timeout(200)
    print("CMP2:" + json.dumps(pg.evaluate(sat), ensure_ascii=False))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    pg.reload(wait_until="networkidle"); pg.wait_for_timeout(800)
    # Kalma riski — yapay sonuçla (hesap Faz 75'te sınanıyor; burada gösterim).
    print("KALMA:" + pg.evaluate("""() => {
      const pr = (d) => [{role: 'ANADAL', label: 'anadal', delay: d, finish: {label: '2028-2029 Güz'}, finishSemester: 9}];
      KALMA = {anahtar: kalmaAnahtari(), yukleniyor: false, hata: '', veri: {
        courses: [{course: 'GEO 331E', programs: pr(1)}, {course: 'BLG 223E', programs: pr(1)},
                  {course: 'MAT 210E', programs: pr(1)}, {course: 'GEO 315E', programs: pr(0)}],
        base: [{label: 'anadal', finish: {label: '2028-2029 Bahar'}}]}};
      const d = document.createElement('div'); d.innerHTML = kalmaPanelIcerik();
      return d.textContent.replace(/\\s+/g, ' ').trim(); }"""))
    # Not senaryosu — ortanca.
    pg.evaluate("() => gorunumAc('creditSection')"); pg.wait_for_timeout(300)
    pg.select_option('select[data-ns="BLG 222E"]', "AA"); pg.wait_for_timeout(150)
    pg.select_option("#nsHepsi", "ortanca"); pg.wait_for_timeout(200)
    print("NS:" + json.dumps(pg.evaluate("() => notSenaryo()"), sort_keys=True))
    print("NSMESAJ:" + T(".nsortancanot"))
    print("IPUCU:" + str(pg.evaluate("() => document.querySelectorAll('.nstablo .nsortanca').length")))
    pg.select_option('select[data-ns="GEO 331E"]', "CC"); pg.wait_for_timeout(150)
    print("NSMESAJ2:" + str(pg.evaluate("() => !!document.querySelector('.nsortancanot')")))
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
    # 1. Kredi ağırlıklı: (9×4 + 1×1) / 5 = 7.4; verisiz ders ortalamaya girmiyor.
    assert json.loads(c["PZ"]) == {"ort": 7.4, "zor": 1, "yok": 1, "bilinen": 2}
    # 2. Özet aynı sayıyı yazıyor.
    assert c["OZET"].startswith("tahmini zorluk 3.8/10: 1 orta · 2 kolay · 5 ders için veri yok"), c["OZET"]
    # 3. Karşılaştırma: sayı var; derslerin yarısından azı biliniyorken "en hafif" YOK.
    cmp1 = json.loads(c["CMP1"])
    assert cmp1[0].startswith("3.8 / 10") and " / 10 1 zor ders" in cmp1[1], (c["FARK"], cmp1)
    assert float(cmp1[1].split(" / ")[0]) >= 3.8 + 0.5, cmp1        # fark eşiği aşılıyor
    assert not any("en hafif" in x for x in cmp1), cmp1
    cmp2 = json.loads(c["CMP2"])
    hafif = [x for x in cmp2 if "en hafif" in x]
    assert hafif and all("zor ders yok" in x for x in hafif), cmp2
    assert "en hafif" not in cmp2[1], cmp2                    # zor dersli sütun
    # 4. Kalma riski: aynı gecikmede kalma oranı yüksek önce; bilinmeyen sonda.
    k = c["KALMA"]
    assert k.index("MAT 210E —") < k.index("BLG 223E —") < k.index("GEO 331E —"), k
    assert "geçmişte kalma oranı %27 (FF + VF)" in k and "%16.7" in k, k
    assert "GEO 331E — anadal bitişi 1 dönem gecikir (2028-2029 Güz) · geçmiş kalma oranı bilinmemektedir" in k, k
    assert "Öncelik: MAT 210E — hem mezuniyeti geciktirebilir" in k, k   # yalnız ≥ %20
    assert "BLG 223E, " not in k.split("Öncelik:")[1].split("—")[0]
    assert "kişisel bir tahmin değildir" in k
    # 5. Ortanca: verisi olana yazıldı; verisizin elle seçilen notuna dokunulmadı.
    assert json.loads(c["NS"]) == {"BLG 222E": "AA", "BLG 223E": "CB",
                                   "GEO 315E": "BB", "GEO 321E": "BB"}, c["NS"]
    assert c["NSMESAJ"].startswith("3 derse geçmişteki ortanca harf notu yazılmıştır; 5 ders"), c["NSMESAJ"]
    assert "kişisel bir tahmin değildir" in c["NSMESAJ"]
    assert c["IPUCU"] == "3"
    assert c["NSMESAJ2"] == "False"                             # tek seçim: toplu not eskidi
