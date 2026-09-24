"""Faz 72 — gerçek sitede yandal öğrencisiyle yapılan gezintide görülen iki hata.

Kullanıcı 24.09.2026: *"make the site more usefull and add new features and
improve the site overall"*. Site gerçek katalogla kuruldu, MAKE + Ekonomi
yandalı (ECN_YD), 5. yarıyıl, 21 derslik transkript yapıştırıldı:

* "Bu 21 dersi ekle" sonrasında pencere ~0,5 sn açık kalıyor, liste hâlâ
  "Girilmiş dersler (0)" gösteriyor ve "Kaydet" yeniden açılıyordu. Kaydet'e
  basılınca ESKİ (boş) liste replace:true ile gidip yapıştırılan transkripti
  siliyordu — GNO "bilinmemektedir"e döndü. Tek tek eklenip kaydedilmemiş
  dersler de yapıştırmada sessizce kayboluyordu.
* GNO paneli, yandala KAYITLI öğrenciye "Başvuru · Yandal başvurusu ≥ 2.50 ✗"
  gösteriyordu. GNO hedefi, not senaryosu ve danışman özeti bu eşiği zaten
  gizliyordu; kural dört yerde ayrı yazılmıştı, biri atlanmıştı.
"""
import json
import pathlib
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import ui as UI

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


def _js(ad):
    f = KAYNAK[KAYNAK.index(f"function {ad}("):]
    return f[:f.index("\n}\n")]


# ------------------------------------------------------------------ başvuru eşiği
def test_KAYITLI_BASVURU_tek_kural_dort_yerde():
    assert ('const kayitliBasvuru = (t) => t.kind === "basvuru"\n'
            '  && SECONDS().some(x => x.kind === t.scope);') in KAYNAK
    assert "icinde.has(" not in KAYNAK          # eski kopyalar kalmadı
    assert "const esikler = g.thresholds.filter(t => !kayitliBasvuru(t));" in _js("renderGpa")
    assert "!kayitliBasvuru(t)" in _js("gnoHedefleri")
    assert "!kayitliBasvuru(t)" in _js("renderNotSenaryo")
    assert "!kayitliBasvuru(x)" in _js("danismanSorulari")


def test_GNO_paneli_eşikleri_süzülmüş_listeden_sayıyor():
    g = _js("renderGpa")
    # Gruplar, çipler ve alt not (doğrulanmamış / toleranslı / bekleyen)
    # AYNI süzülmüş listeden — gizlenen eşik sayıya da girmesin.
    for parca in ("esikler.some(t => t.kind === k)", "esikler.filter(t => t.kind === k)",
                  "esikler.filter(t => !t.verified)", "esikler.filter(t => t.tolerance)",
                  "esikler.filter(t => t.ok === null)"):
        assert parca in g, parca
    assert "g.thresholds.filter(t => t.kind === k)" not in g


# ------------------------------------------------------------------ yapıştırma
def test_YAPISTIRMA_bekleyeni_once_kaydediyor_sonra_listeyi_yeniliyor():
    s = _js("save")
    assert "return true;" in s and "return false;" in s
    d = _js("courseDialogSetup")
    assert "bekleyen: () => ozet() !== kayitli ? govde() : null," in d
    assert "yenile: () => { rows = SETUP.transcript.map(t => ({...t})); kayitli = ozet(); draw(); }," in d
    assert "trOnizlemeCiz(r.preview || {}, calisma);" in d
    # Kaydet ve yapıştırma AYNI gövdeyi kullanıyor.
    assert 'save(() => api("/api/transcript", govde()))' in d
    o = _js("trOnizlemeCiz")
    i = o.index('$("#trUygula")')
    k = o[i:]
    assert k.index("calisma.bekleyen()") < k.index('api("/api/transcript/paste"')
    assert "if(tamam && calisma) calisma.yenile();" in k


_CANLI = r'''
import sys, os, json
sys.path.insert(0, os.environ["ITUCAP_SRC"]); sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import vitrin
adres, h = vitrin.ac()
from playwright.sync_api import sync_playwright
KAPALI = "() => !document.querySelector('#setup[open]')"
UYGULA = """async (kaydet) => {
  $("#trUygula").click();
  const bekle = () => new Promise(r => setTimeout(r, 10));
  const b = $("#setupSave");
  do { await bekle(); } while(b.disabled || b.innerText.trim() !== "Kaydet");
  const acik = !!document.querySelector('#setup[open]');
  const liste = +$("#trCount").textContent;
  if(kaydet){
    b.click();
    do { await bekle(); } while(b.disabled || b.innerText.trim() !== "Kaydet");
  }
  return {acik, liste};
}"""
DURUM = "() => Object.fromEntries(SETUP.transcript.map(t => [t.course, t.grade]))"
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 1000})
    hatalar = []
    pg.on("pageerror", lambda e: hatalar.append(str(e)))
    pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(1000)
    pg.evaluate("() => gorunumAc('creditSection')"); pg.wait_for_timeout(300)
    print("GNO:" + pg.evaluate("() => document.querySelector('#gpaBody').innerText.replace(/\\s+/g,' ')"))
    print("GRUP:" + json.dumps(pg.evaluate("() => [...document.querySelectorAll('#gpaBody .eyebrow')].map(e => e.textContent.trim())")))
    # Yalnız KAYITLI olunan programın başvurusu gizleniyor (vitrin: ÇAP'ta,
    # yandalda değil — yandal başvurusu hâlâ bir seçenek).
    print("KURAL:" + json.dumps(pg.evaluate("""() => [
      kayitliBasvuru({kind: 'basvuru', scope: 'cap'}),
      kayitliBasvuru({kind: 'basvuru', scope: 'yandal'}),
      kayitliBasvuru({kind: 'devam', scope: 'cap'})]""")))
    print("ONCE:" + json.dumps(pg.evaluate(DURUM)))
    # (A) Kaydedilmemiş not değişikliği + yapıştırma → ikisi de kalıyor.
    pg.evaluate("() => courseDialogSetup()"); pg.wait_for_timeout(400)
    pg.select_option("#trBody select.g >> nth=0", "AA")
    pg.fill("#trPaste", "BLG 222E  Computer Organization  3  5  BB")
    pg.click("#trOnizle"); pg.wait_for_timeout(800)
    print("A:" + json.dumps(pg.evaluate(UYGULA, False)))
    pg.wait_for_function(KAPALI, timeout=5000)
    print("ADURUM:" + json.dumps(pg.evaluate(DURUM)))
    # (B) Yapıştırmadan hemen sonra Kaydet → yapıştırılan ders silinmiyor.
    pg.evaluate("() => courseDialogSetup()"); pg.wait_for_timeout(400)
    pg.fill("#trPaste", "BLG 252E  Object Oriented Programming  3  5  CC")
    pg.click("#trOnizle"); pg.wait_for_timeout(800)
    print("B:" + json.dumps(pg.evaluate(UYGULA, True)))
    pg.wait_for_function(KAPALI, timeout=5000)
    print("BDURUM:" + json.dumps(pg.evaluate(DURUM)))
    print("GPA:" + json.dumps(pg.evaluate("() => [DATA.gpa.counted, DATA.gpa.credits]")))
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
    # ÇAP'a kayıtlı vitrin öğrencisi: ÇAP BAŞVURU eşiği panelde yok, devam var.
    assert "başvurusu" not in c["GNO"], c["GNO"]
    assert json.loads(c["GRUP"]) == ["Devam", "Mezuniyet"], c["GRUP"]
    assert "ÇAP'a devam ≥ 2.50" in c["GNO"] and "Mezuniyet ≥ 2.00" in c["GNO"]
    assert json.loads(c["KURAL"]) == [True, False, False], c["KURAL"]
    once = json.loads(c["ONCE"])
    ilk = next(iter(once))
    assert once[ilk] != "AA" and "BLG 222E" not in once and "BLG 252E" not in once
    # (A) Başarıdan hemen sonra (pencere açıkken) liste yeni transkripti gösteriyor;
    #     kaydedilmemiş not değişikliği yapıştırmayla birlikte kaydedildi.
    a = json.loads(c["A"])
    assert a == {"acik": True, "liste": len(once) + 1}, a
    ad = json.loads(c["ADURUM"])
    assert ad[ilk] == "AA" and ad["BLG 222E"] == "BB", ad
    # (B) Hemen Kaydet'e basmak yapıştırılan dersi silmiyor.
    bb = json.loads(c["B"])
    assert bb == {"acik": True, "liste": len(once) + 2}, bb
    bd = json.loads(c["BDURUM"])
    assert bd["BLG 252E"] == "CC" and bd["BLG 222E"] == "BB" and bd[ilk] == "AA", bd
    assert len(bd) == len(once) + 2
