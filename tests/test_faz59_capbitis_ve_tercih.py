"""Faz 59 — "ya ÇAP'ı şurada yapsaydım", azami süre, tercihi kaydetmeden dene.

Kullanıcı 24.09.2026: *"continue on your improvements and changes"*.

* Y.1 — başvuru penceresi her ÇAP programı için TAHMİNİ BİTİŞİ yazıyor
  (yol haritası motoru, anadal + aday ÇAP). İstek üzerine, salt okunur
  `/api/capbitis`. ⚠️ Kalan KREDİ yazmıyor: pencerenin 22.08.2026 kararı.
* Y.7 — azami öğrenim süresi `kurallar.toml`'da beyan ediliyor; bu ortamdan
  İTÜ maddesine ulaşılamadığı için DOĞRULANMAMIŞ (⚠) ve yalnız anadala
  uygulanıyor.
* §3.6 — tercihi kaydetmeden dene: ayarların bellekteki kopyasıyla rapor,
  dosyaya hiçbir şey yazılmıyor; doğrulama kaydetmeyle aynı.
"""
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import db
from itucap import policy as POL
from itucap import prereq as P
from itucap import server as SRV
from itucap import ui as UI
from itucap import yolharitasi as YH

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")
SUNUCU = pathlib.Path(SRV.__file__).read_text(encoding="utf-8")


def _js(ad):
    f = KAYNAK[KAYNAK.index(f"function {ad}("):]
    return f[:f.index("\n}\n")]


# ------------------------------------------------------------------ Y.7 — azami süre
def test_AZAMI_SURE_teyitli_ve_ISTISNALARI_yazili():
    az = POL.load_max_duration()
    assert az.semesters == 14
    # 24.09.2026 kullanıcı teyidi: "14 yarıyıl çoğu durumda doğru". İstisnalar
    # açıklamada kalmalı — sayı kesin son gün gibi sunulmasın.
    assert az.verified is True
    assert "hazırlık" in az.note and "ÖİDB" in az.note
    assert "2547" in az.source and "44/c" in az.source


def test_AZAMI_SURE_yoksa_UYDURULMUYOR(tmp_path):
    assert POL.load_max_duration(tmp_path / "yok.toml") is None
    bos = tmp_path / "k.toml"
    bos.write_text("[azami_sure]\nyariyil = \"on dört\"\n", encoding="utf-8")
    assert POL.load_max_duration(bos) is None


def _katalog(tmp_path):
    con = db.connect(tmp_path / "ref.sqlite3", "schema.sql")
    con.execute("INSERT INTO program(code,name,level) VALUES ('AAA','A','LS')")
    for kod, onsart in (("XXX 101", None), ("YYY 102", "XXX 101 MIN DD")):
        con.execute("INSERT INTO course(code,name,credits,ects,prereq_raw) VALUES (?,?,3,5,?)",
                    (kod, "Ders " + kod, onsart))
    con.execute("INSERT INTO plan(id,program_code,plan_type,title,source)"
                " VALUES (1,'AAA','lisans','x','obs')")
    for i, (kod, d) in enumerate((("XXX 101", 5), ("YYY 102", 6))):
        con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,credits,position,"
                    "term_no) VALUES (1,'REQUIRED',?,3,?,?)", (kod, i, d))
    P.parse_all(con)
    con.commit()
    return con


def test_BITIS_YARIYILI_donemden_sayiliyor(tmp_path):
    con = _katalog(tmp_path)
    plan = [{"planId": 1, "role": "ANADAL", "label": "anadal", "program": "AAA"}]
    h = YH.kur(con, {}, plan, term="202610", donem=5, max_load=21, bu_donem=[])
    p = h["programs"][0]
    # XXX Güz (sıra 2), YYY Bahar (sıra 3) → 5 + 3 = 8. yarıyıl.
    assert (p["finish"]["index"], p["finishSemester"]) == (3, 8)
    # Dönem bilinmiyorsa yarıyıl TAHMİN EDİLMİYOR.
    h0 = YH.kur(con, {}, plan, term="202610", donem=0, max_load=21, bu_donem=[])
    assert h0["programs"][0]["finishSemester"] is None


def test_AZAMI_SURE_yalniz_ANADALA_ve_isaretli():
    f = _js("yariyilSatiri")
    assert "const asti = anadal && md && p.finishSemester > md.semesters;" in f
    assert 'md && !md.verified ? " ⚠"' in f


# ------------------------------------------------------------------ Y.1 — ÇAP bitişi
def test_CAP_BITISI_salt_okunur_ve_KREDISIZ():
    assert "/api/capbitis" in SRV.READ_ONLY_PATHS
    f = re.sub(r"/\*.*?\*/", " ", _js("capBitisHucre"), flags=re.S)
    assert "kredi" not in f.lower(), \
        "başvuru penceresi kalan kredi yazmıyor (22.08.2026 kararı)"
    k = KAYNAK[KAYNAK.index("def cap_bitisleri("):KAYNAK.index("def _plan_uyarisi(")]
    assert '"remainingCredits"' not in k


def test_CAP_BITISI_girdiyi_SINIRLIYOR():
    k = KAYNAK[KAYNAK.index("def cap_bitisleri("):KAYNAK.index("def _plan_uyarisi(")]
    # Faz 61: kredi ve ders sınırı senaryoyla ORTAK `_harita_girdisi`nde.
    g = KAYNAK[KAYNAK.index("def _harita_girdisi("):KAYNAK.index("def yol_senaryosu(")]
    assert "_harita_girdisi(" in k
    assert "if not 1 <= max_load <= 60:" in g
    assert "for pid in list(plan_ids or [])[:60]:" in k
    assert "for x in (bu_donem or [])[:20]" in g


# ------------------------------------------------------------------ §3.6 — tercih önizlemesi
def test_ONIZLEME_salt_okunur_ve_DOGRULAMA_ORTAK():
    assert "/api/tercih/onizle" in SRV.READ_ONLY_PATHS
    kaydet = SUNUCU[SUNUCU.index("    def save_prefs("):SUNUCU.index("    def preview_prefs(")]
    onizle = SUNUCU[SUNUCU.index("    def preview_prefs("):SUNUCU.index("    def _tercih_degerleri(")]
    assert "self._tercih_degerleri(body)" in kaydet and "self._tercih_degerleri(body)" in onizle
    assert "update_settings" not in onizle, "önizleme ayar dosyasına yazıyor"
    assert "dataclasses.replace(self.settings(), **degerler)" in onizle
    # Arayüz: kaydet ve dene AYNI gövdeyi gönderiyor.
    t = _js("tercihDialog")
    assert 'api("/api/tercih", govde())' in t and '{...govde(), mode: M().key}' in t


# ------------------------------------------------------------------ uçtan uca (vitrin)
_CANLI = r'''
import sys, os, json
sys.path.insert(0, os.environ["ITUCAP_SRC"]); sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import vitrin
adres, h = vitrin.ac()
from itucap import config
ayar = (config.ROOT / "config" / "settings.toml")
once = ayar.read_text(encoding="utf-8")
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 1000})
    hatalar = []
    pg.on("pageerror", lambda e: hatalar.append(str(e)))
    pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(1200)
    # Y.1 — başvuru penceresi: INS ÇAP'ın tahmini bitişi.
    pg.evaluate("() => openBasvuru('cap')"); pg.wait_for_timeout(800)
    print("CAPBITIS:" + pg.evaluate("() => [...document.querySelectorAll('#basvuruBody td[data-bitis]')]"
                                    ".map(e => e.innerText.replace(/\\s+/g,' ')).join('|')"))
    print("CAPNOT:" + pg.evaluate("() => (document.querySelector('#capBitisNot')||{innerText:''}).innerText.replace(/\\s+/g,' ')"))
    pg.evaluate("() => document.querySelector('#basvuruDlg').close()")
    # Y.7 — yol haritası kartı: yarıyıl ve azami süre; süre kısaltılınca uyarı.
    pg.evaluate("() => gorunumAc('roadmapSection')"); pg.wait_for_timeout(300)
    kart = "() => document.querySelector('.yhprogram[data-role=ANADAL]').innerText.replace(/\\s+/g,' ')"
    print("KART1:" + pg.evaluate(kart))
    pg.evaluate("() => { DATA.roadmap.maxDuration.semesters = 9; renderRoadmap(); }")
    print("KART2:" + pg.evaluate(kart))
    print("CAPKART:" + pg.evaluate("() => document.querySelector('.yhprogram[data-role=CAP]').innerText.replace(/\\s+/g,' ')"))
    # §3.6 — tercihi kaydetmeden dene.
    pg.evaluate("() => tercihDialog()"); pg.wait_for_timeout(400)
    pg.click('#fErken button[data-v="630"]'); pg.click('#fGun button[data-v="1"]')
    pg.click("#fOnizle"); pg.wait_for_timeout(1500)
    print("ONIZLE:" + pg.evaluate("() => document.querySelector('#fOnizleSonuc').innerText.replace(/\\s+/g,' ')"))
    print("DUGME:" + pg.evaluate("() => document.querySelector('#fOnizle').textContent.trim()"))
    print("HATA:" + str(len(hatalar)) + " " + " | ".join(hatalar)[:300])
    b.close()
print("AYAR:" + str(once == ayar.read_text(encoding="utf-8")))
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

    # Y.1 — vitrinin ikinci ÇAP seçeneği INS: 4 halkalık zincir, 10. yarıyıl.
    assert c["CAPBITIS"].startswith("2027-2028 Bahar (10. yarıyıl)"), c["CAPBITIS"]
    assert "5 ders kaldı" in c["CAPBITIS"] and "kredi" not in c["CAPBITIS"]
    assert "yarıyıl tabanı tutmuyor" in c["CAPBITIS"]
    assert "6. yarıyılda" in c["CAPNOT"] and "kabulü, kontenjan ve sıralama" in c["CAPNOT"]

    # Y.7 — azami süre ⚠ ile; aşınca uyarı; ÇAP kartında azami YOK.
    assert "10. yarıyılında · azami 14" in c["KART1"] and "⚠" not in c["KART1"], c["KART1"]
    assert "aşıyor" not in c["KART1"]
    assert "azami öğrenim süresini 1 yarıyıl aşıyor" in c["KART2"], c["KART2"]
    assert "yarıyılında" in c["CAPKART"] and "azami" not in c["CAPKART"], c["CAPKART"]

    # §3.6 — önizleme: değişen şube, şekil, tercih puanı; AYAR DOSYASI AYNI.
    assert "BLG 223E şubesi 22301 → 22302" in c["ONIZLE"], c["ONIZLE"]
    assert "Tercih puanı -44" in c["ONIZLE"] and "Kaydedilmedi" in c["ONIZLE"]
    assert c["DUGME"] == "Kaydetmeden dene", "düğme meşgul hâlinde kaldı"
    assert c["AYAR"] == "True", "önizleme ayar dosyasını değiştirdi"
