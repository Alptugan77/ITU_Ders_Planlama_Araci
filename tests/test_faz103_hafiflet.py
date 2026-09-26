"""Faz 103 — "dönemi hafiflet" somut ders önerisi.

Özet dönem zor/çok zorken "ders sayısının azaltılması değerlendirilebilir"
diyordu ama HANGİ dersin çıkarılacağını söylemiyordu (genel uyarı — Faz 46).
Artık en çok hafifleten, eşitlikte öneri puanı en düşük iki ders "çıkar"
düğmesiyle. Kritik yoldaki, saate kilitli, ÇAP tabanını bozan ve daha önce
kalınan (tekrar alınan) ders önerilmiyor.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import ui as UI

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
    # Denetimli durum: her derse bilinen zorluk, puan ve kritiklik ver.
    KUR = """(ayar) => { DATA.secondFloor = null;
      picks().forEach((p, i) => { const a = ayar[i] || {};
        p.cand.grades = {difficulty: {level: zorlukKademesi(a.z ?? 5), score: a.z ?? 5,
                                      gradeOverall: a.z ?? 5, passRate: 85, mean: 2.5}};
        p.cand.ects = a.e ?? 5; p.cand.score = a.s ?? 50; p.cand.critical = !!a.k; });
      render();
      const k = document.querySelector('#schedSummary .hafiflet');
      return {kurs: picks().map(p => p.cand.course),
              oner: k ? [...k.querySelectorAll('[data-hafiflet]')].map(b => b.dataset.hafiflet) : null,
              metin: k ? k.textContent.replace(/\\s+/g,' ').trim() : ''}; }"""
    # 0: çok zor ama KRİTİK · 1: en zor kritik olmayan · 2 ve 3: eşit düşüş, puan farklı
    print("TEMEL:" + json.dumps(pg.evaluate(KUR, [
        {"z": 10, "e": 8, "k": True}, {"z": 9, "e": 6, "s": 200}, {"z": 5, "s": 90},
        {"z": 5, "s": 30}]), ensure_ascii=False))
    # Kilit: en çok hafifleten kilitliyse atlanır.
    print("KILIT:" + json.dumps(pg.evaluate("""(KUR) => {
        const p = picks()[1]; DATA.locked = DATA.locked || {};
        const eski = window.kilitliMi; window.kilitliMi = (c, crn) => c === p.cand.course || eski(c, crn);
        const r = (new Function('return ' + KUR))()([{z: 10, e: 8, k: true}, {z: 9, e: 6, s: 200}, {z: 5, s: 90}, {z: 5, s: 30}]);
        window.kilitliMi = eski; return r; }""", KUR), ensure_ascii=False))
    # Orta dönem: öneri yok.
    print("HAFIF:" + json.dumps(pg.evaluate(KUR, [{"z": 1, "e": 3}] * 8), ensure_ascii=False))
    # Hepsi kritik: açıklama.
    print("KRITIK:" + json.dumps(pg.evaluate(KUR, [{"z": 9, "k": True}] * 8), ensure_ascii=False))
    # ÇAP tabanı: tabanı tam karşılayan ikinci program dersi önerilmez.
    print("TABAN:" + json.dumps(pg.evaluate("""(KUR) => {
        const f = (new Function('return ' + KUR))();
        f([{z: 5}]);                              // durumu sıfırla
        const ps = picks(); const cap = ps.filter(p => p.cand.role !== 'ANADAL');
        const r = f(ps.map(p => p.cand.role !== 'ANADAL' ? {z: 10, e: 9, s: 1} : {z: 6, s: 500}));
        const kredi = cap.reduce((a, p) => a + (p.cand.credits || 0), 0);
        DATA.secondFloor = {min: kredi, kind: 'cap'}; render();
        const k = document.querySelector('#schedSummary .hafiflet');
        return {cap: cap.map(p => p.cand.course), once: r.oner,
                sonra: k ? [...k.querySelectorAll('[data-hafiflet]')].map(b => b.dataset.hafiflet) : null}; }""", KUR), ensure_ascii=False))
    # Kalınan (FAILED) ders önerilmiyor.
    print("KALINAN:" + json.dumps(pg.evaluate("""(KUR) => {
        const k = picks()[1].cand.course; const eski = SETUP.transcript;
        SETUP.transcript = [...(eski || []), {course: k, grade: 'FF', status: 'FAILED'}];
        const r = (new Function('return ' + KUR))()([{z: 10, e: 8, k: true}, {z: 9, e: 6, s: 200}, {z: 5, s: 90}, {z: 5, s: 30}]);
        SETUP.transcript = eski; return [k, r.oner]; }""", KUR), ensure_ascii=False))
    # Düğme: çıkarır, geri alınabilir.
    pg.evaluate(KUR, [{"z": 10, "e": 8, "k": True}, {"z": 9, "e": 6, "s": 200}, {"z": 5, "s": 90}, {"z": 5, "s": 30}])
    print("DUGME:" + json.dumps(pg.evaluate("""() => { const b = document.querySelector('#schedSummary [data-hafiflet]');
        const k = b.dataset.hafiflet; const n = sel.length; b.click();
        const cikti = !sel.some(x => x.course === k) && sel.length === n - 1;
        geriAl(); return [k, cikti, sel.some(x => x.course === k)]; }""")))
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
    c = {k: json.loads(v) if v[:1] in "{[" else v for k, v in
         (s.split(":", 1) for s in r.stdout.strip().splitlines()
          if ":" in s and s.split(":", 1)[0].isupper())}
    assert c["HATA"].startswith("0"), c["HATA"]
    t = c["TEMEL"]
    kurs = t["kurs"]
    # Kritik (0) hiç önerilmiyor; en çok hafifleten (1) önce; eşit düşüşte
    # öneri puanı düşük olan (3, puan 30) ikincisi (2, puan 90) değil.
    assert t["oner"] == [kurs[1], kurs[3]], t
    assert "Dönemi hafifletmek için" in t["metin"] and "ders sonraki dönemlere kalır" in t["metin"]
    assert "öneri puanı −200" in t["metin"] and "öneri puanı −30" in t["metin"], t["metin"]
    assert c["KILIT"]["oner"] and kurs[1] not in c["KILIT"]["oner"], c["KILIT"]
    assert c["HAFIF"]["oner"] is None, c["HAFIF"]             # orta/kolay dönemde öneri yok
    assert c["KRITIK"]["oner"] == [] and "tekrar alınan dersler dışında çıkarılabilecek ders bulunmamaktadır" in c["KRITIK"]["metin"]
    kal, oner = c["KALINAN"]
    assert oner and kal not in oner, c["KALINAN"]
    tb = c["TABAN"]
    assert tb["cap"] and set(tb["cap"]) & set(tb["once"]), tb      # taban yokken ÇAP dersi önerilebiliyor
    assert not set(tb["cap"]) & set(tb["sonra"] or []), tb         # taban tam sağlanınca önerilmiyor
    k, cikti, geri = c["DUGME"]
    assert k == kurs[1] and cikti and geri
