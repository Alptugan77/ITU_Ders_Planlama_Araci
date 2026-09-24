"""Faz 71 — dönem sonu not senaryosu ("bu notları alırsam ne olur").

Kullanıcı 24.09.2026: *"make the site more usefull and add new features and
improve the site overall"*.

GNO hedefi (Faz 57/69) soruyu tersinden soruyordu: eşik için hangi ortalama
gerekir. Öğrencinin dönem sonunda kurduğu cümle ise "MAT 210E'den CC,
BLG 223E'den BB alırsam GNO'm, ÇAP ortalamam, gelecek dönem kredi sınırım ne
olur". Her ders için beklenen not seçiliyor; sonuç aynı kurallardan
(`gnoTabani`, `DATA.gpa.thresholds`, kurallar.toml bantları) hesaplanıyor.
"""
import json
import pathlib
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import policy as POL
from itucap import ui as UI

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


def _js(ad):
    f = KAYNAK[KAYNAK.index(f"function {ad}("):]
    return f[:f.index("\n}\n")]


def test_TABAN_GNO_hedefiyle_ayni():
    """Tekrar alınan dersin eski notu düşülüyor — GNO hedefiyle AYNI taban."""
    h = _js("senaryoHesapla")
    assert "gnoTabani(g.credits, g.points, notlu)" in h
    assert "gnoTabani(ik.credits, ik.points, l)" in h
    # Tekrar edilen ders tabloda işaretleniyor.
    assert "tekrar · eski ${" in _js("renderNotSenaryo")
    # Not seçilmeyen ders hesaba girmiyor (sessizce "DD" ya da "AA" sayılmıyor).
    assert "notlar[p.cand.course] in NS_PUAN" in h
    # Transkriptte harf notu yokken GNO uydurulmuyor.
    assert "if(g.counted && T){" in h


def test_KREDI_SINIRI_ayni_kuraldan():
    b = _js("bantSiniri")
    assert "gno + 1e-9 >= b.minGpa" in b and "Math.max(...tutan.map(b => b.max))" in b
    i = KAYNAK.index("def collect(")
    k = KAYNAK[i:KAYNAK.index("\ndef ", i + 1)]
    assert '"bands": [{"label": b.label, "minGpa": b.min_gpa, "max": b.max_credits}' in k
    assert "for b in POL.load_bands()[0]]" in k
    # Sınır yalnız kredi birimli programda ve GNO biliniyorken yazılıyor.
    r = _js("renderNotSenaryo")
    assert 'r.gno !== null && DATA.unit === "kredi" ? bantSiniri(yuvarla2(r.gno))' in r


def test_ESIKLER_kayitli_programin_basvurusunu_gostermiyor():
    r = _js("renderNotSenaryo")
    assert ".filter(t => t.min > 0 && !kayitliBasvuru(t))" in r     # Faz 72: tek kural
    assert 't.basis === "ikinci anadal" ? r.ikinci : r.gno' in r
    # Eşik, transkriptin yuvarladığı gibi iki basamakta karşılaştırılıyor.
    assert "const ok = (v, min) => yuvarla2(v) + 1e-9 >= min;" in r


def test_SECIMLER_yalniz_tarayicida():
    r = _js("renderNotSenaryo")
    assert r.count('localStorage_set("notSenaryo", JSON.stringify(notlar));') == 2
    assert "api(" not in r            # sunucuya/kayda hiçbir şey gitmiyor
    assert 'localStorage_get("notSenaryo")' in _js("notSenaryo")
    assert "renderNotSenaryo();" in _js("render")


def test_BANT_hesabi_policy_ile_ayni():
    """JS'teki bant kuralı `policy.load_limit` ile aynı sonucu veriyor."""
    bantlar = POL.load_bands()[0]
    assert bantlar, "kurallar.toml'da [[kredi_yuku]] yok"

    def js_kurali(gno):
        tutan = [b.max_credits for b in bantlar if gno + 1e-9 >= b.min_gpa]
        return max(tutan) if tutan else None

    for gno in (0.0, 1.5, 2.24, 2.25, 2.99, 3.0, 3.5, 4.0):
        assert js_kurali(gno) == POL.load_limit(gno).maximum, gno


# ------------------------------------------------------------------ uçtan uca (vitrin)
_CANLI = r'''
import sys, os, json
sys.path.insert(0, os.environ["ITUCAP_SRC"]); sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import vitrin
adres, h = vitrin.ac()
from playwright.sync_api import sync_playwright
metin = "() => document.querySelector('#notSenaryoBody').innerText.replace(/\\s+/g,' ')"
sonuc = "() => (document.querySelector('.nssonuc')||{innerText:''}).innerText.replace(/\\s+/g,' ')"
with sync_playwright() as p:
    b = p.chromium.launch()
    for W in (1400, 390):
        pg = b.new_page(viewport={"width": W, "height": 1000})
        hatalar = []
        pg.on("pageerror", lambda e: hatalar.append(str(e)))
        pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(1000)
        pg.evaluate("() => gorunumAc('creditSection')"); pg.wait_for_timeout(300)
        print(f"BOS{W}:" + pg.evaluate(metin))
        print(f"BANT{W}:" + json.dumps(pg.evaluate("() => DATA.load.bands")))
        # Vitrinde MAT 210E FF (3 kr) tekrar: yeni not eskisinin YERİNE sayılıyor.
        print(f"TEKRAR{W}:" + json.dumps(pg.evaluate(
            "() => senaryoHesapla([{cand:{course:'MAT 210E', credits: 3}}], {'MAT 210E': 'CC'})")))
        pg.select_option("#nsHepsi", "BB"); pg.wait_for_timeout(200)
        print(f"ODAK{W}:" + str(pg.evaluate("() => document.activeElement.id")))
        pg.select_option("select[data-ns='BLG 223E']", "AA"); pg.wait_for_timeout(200)
        print(f"ODAK2{W}:" + str(pg.evaluate("() => document.activeElement.dataset.ns")))
        print(f"IYI{W}:" + pg.evaluate(sonuc))
        print(f"CIP{W}:" + json.dumps(pg.evaluate("() => [...document.querySelectorAll('.nsesik .cat')].map(e => e.innerText)"), ensure_ascii=False))
        print(f"TASMA{W}:" + str(pg.evaluate("() => document.documentElement.scrollWidth > innerWidth + 1")))
        # Yeniden yüklemede seçimler duruyor (yalnız bu tarayıcıda).
        pg.reload(wait_until="networkidle"); pg.wait_for_timeout(1000)
        pg.evaluate("() => gorunumAc('creditSection')"); pg.wait_for_timeout(300)
        print(f"KALICI{W}:" + pg.evaluate(sonuc))
        pg.select_option("#nsHepsi", "FF"); pg.wait_for_timeout(200)
        print(f"KOTU{W}:" + pg.evaluate(sonuc))
        print(f"CIPK{W}:" + json.dumps(pg.evaluate("() => [...document.querySelectorAll('.nsesik .cat')].map(e => e.innerText)"), ensure_ascii=False))
        pg.select_option("select[data-ns='BLG 223E']", ""); pg.wait_for_timeout(200)
        print(f"EKSIK{W}:" + pg.evaluate(sonuc))
        pg.select_option("#nsHepsi", "temizle"); pg.wait_for_timeout(200)
        print(f"TEMIZ{W}:" + pg.evaluate(metin))
        print(f"DEPO{W}:" + str(pg.evaluate("() => localStorage.getItem('itucap.notSenaryo')")))
        print(f"HATA{W}:" + str(len(hatalar)) + " " + " | ".join(hatalar)[:300])
        pg.evaluate("() => localStorage.clear()")
        pg.close()
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
             if ":" in s and s.split(":", 1)[0].isalnum() and s.split(":", 1)[0].isupper())
    for W in (1400, 390):
        assert c[f"HATA{W}"].startswith("0"), c[f"HATA{W}"]
        assert "Dönem sonu not senaryosu" in c[f"BOS{W}"]
        assert "en az bir ders için beklenen notu seçiniz" in c[f"BOS{W}"]
        assert [b["max"] for b in json.loads(c[f"BANT{W}"])] == \
            [b.max_credits for b in POL.load_bands()[0]]
        assert c[f"ODAK{W}"] == "nsHepsi" and c[f"ODAK2{W}"] == "BLG 223E"
        # 214 puan / 77 kr; MAT 210E'nin eski FF'si (3 kr, 0 puan) düşülüyor:
        # (214 + 3×2) / (77 − 3 + 3) = 2.857. Düşülmeseydi 220 / 80 = 2.75.
        tk = json.loads(c[f"TEKRAR{W}"])
        assert round(tk["gno"], 3) == 2.857 and tk["donem"] == 2 and tk["eksik"] == 0, tk
        # Vitrin: GNO 2.78 (77 kr), ÇAP 2.75 (6 kr); 8 ders/24 kr, 7×BB + BLG 223E AA.
        iyi = c[f"IYI{W}"]
        for parca in ("Dönem ortalaması: 3.13 (8 ders, 24 kredi)", "GNO (tahmini): 2.78 → 2.86",
                      "ortalaması: 2.75 → 3.10", "Gelecek dönem kredi sınırı (yönetmelik): 25 → 25"):
            assert parca in iyi, (parca, iyi)
        cip = json.loads(c[f"CIP{W}"])
        assert cip and all(x.endswith("✓") for x in cip), cip
        assert c[f"TASMA{W}"] == "False"
        assert c[f"KALICI{W}"] == iyi
        # Hepsi FF: GNO 2.12 — 2.25 bandının altı, sınır 22'ye iniyor; ÇAP
        # eşikleri ✗, mezuniyetin 2.00'ı hâlâ ✓ (her eşik kendi ölçüsüyle).
        kotu = c[f"KOTU{W}"]
        for parca in ("Dönem ortalaması: 0.00", "2.78 → 2.12", "2.75 → 1.10", "25 → 22 kredi"):
            assert parca in kotu, (parca, kotu)
        cipk = json.loads(c[f"CIPK{W}"])
        assert [x[-1] for x in cipk] == ["✗", "✗", "✗", "✓"], cipk
        # Faz 72: GNO panelindeki gibi küçük harf (.chip BÜYÜK harf yazıyordu).
        assert cipk[-1].startswith("Mezuniyet ≥ 2.00"), cipk
        assert "1 ders için not seçilmediğinden hesaba katılmamıştır" in c[f"EKSIK{W}"]
        assert "7 ders, " in c[f"EKSIK{W}"]
        assert "en az bir ders için beklenen notu seçiniz" in c[f"TEMIZ{W}"]
        assert c[f"DEPO{W}"] == "{}"
