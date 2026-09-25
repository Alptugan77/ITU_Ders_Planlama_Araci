"""Faz 96 — kullanım kılavuzu.

Kullanıcı 25.09.2026: *"can you create a help or info section for people to
know the usecases and abilities of DEPAR and how to use it"*.

95 fazda eklenen özelliklerin çoğu bir düğmenin ya da bir görünümün içinde;
yeni gelen öğrenci neyin var olduğunu bilmiyordu. Kılavuz bir görünüm (rayda
YARDIM, telefonda "Daha" altında) ve başlıkta bir "Kılavuz" düğmesi.

Bu dosyanın asıl işi KAYMAYI yakalamak: kılavuzun andığı her düğme adı
sayfanın geri kalanında GERÇEKTEN var olmalı, her "git" düğmesi var olan bir
görünüme gitmeli. Bir düğmenin adı değişirse kılavuz sessizce eskimesin.
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import ui as UI

KAYNAK = Path(UI.__file__).read_text(encoding="utf-8")
BAS = KAYNAK.index('<section class="card pad yardim" id="yardimSection">')
SON = KAYNAK.index("</section>", BAS)
KILAVUZ = KAYNAK[BAS:SON]
DUZ = " ".join(KILAVUZ.split())                  # satır kırılmasından bağımsız
GERISI = KAYNAK[:BAS] + KAYNAK[SON:]


def test_KILAVUZ_gorunum_listesinde():
    assert '["yardimSection", "Kullanım kılavuzu", "YARDIM", "Kılavuz", true]' in KAYNAK


def test_GIT_dugmeleri_var_olan_gorunume():
    hedefler = set(re.findall(r'data-git="([^"]+)"', KILAVUZ))
    gorunumler = set(re.findall(r'\["([A-Za-z]+)", "[^"]+", "[A-Z]+", "[^"]+", (?:true|false)\]', KAYNAK))
    assert hedefler and hedefler <= gorunumler, hedefler - gorunumler
    for h in hedefler:
        assert f'id="{h}"' in KAYNAK, h


@pytest.mark.parametrize("ad", [
    "Plandan işaretle", "Transkript yapıştır", "Program tercihleri", "Kayıt günü listesi", "Takvime aktar",
    "Resim (PNG)", "Yazdır", "CRN'den program yükle", "Ders ekle", "Danışman özeti",
    "Programı kaydet", "Alternatif olarak kaydet", "Kalma riski", "GNO hedefi"])
def test_KILAVUZUN_andigi_dugme_sayfada_var(ad):
    assert ad in DUZ.replace("<b>", "").replace("</b>", ""), ad
    assert ad in GERISI, f"kılavuz '{ad}' diyor ama sayfada öyle bir şey kalmamış"


def test_BASLARKEN_plandan_isaretle():
    """Kullanıcı 25.09.2026: kılavuzda "transkripten gir" yerine "dersleri
    plandan işaretle" adımı. Transkript notlar için seçenek olarak kalıyor."""
    adim = DUZ.split("<h3>Başlarken</h3>")[1].split("</ol>")[0]
    ikinci = adim.split("<li>")[2]
    assert ikinci.startswith("<b>Aldığınız dersleri plandan işaretleyiniz.</b>"), ikinci[:80]
    assert 'data-ac="plan">Plandan işaretle</button>' in ikinci
    assert "Transkriptinizi yapıştırınız" not in DUZ


def test_SINIRLAR_soyleniyor():
    for cumle in ("Hesaplar tahmindir; esas olan OBS, Kepler ve yönetmeliktir",
                  "ders kaydı Kepler'de",
                  "akademik takvim yoktur", "Kayıt yapmaz",
                  "başka bir yere gönderilmez"):
        assert cumle in DUZ, cumle


_CANLI = r'''
import sys, os, json
sys.path.insert(0, os.environ["ITUCAP_SRC"]); sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import vitrin
adres, h = vitrin.ac()
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 1000})
    hatalar = []; pg.on("pageerror", lambda e: hatalar.append(str(e)))
    pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(800)
    print("RAY:" + pg.evaluate("() => [...document.querySelectorAll('#secnav .raybaslik, #secnav a .rayad.uzun')].map(e => e.textContent).slice(-2).join('|')"))
    pg.click("#kilavuzBtn"); pg.wait_for_timeout(200)
    print("BASLIK:" + pg.evaluate("() => GORUNUM + '|' + document.querySelector('#yardimSection').hasAttribute('data-disgorunum')"))
    sonuc = []
    for hedef in pg.evaluate("() => [...new Set([...document.querySelectorAll('#yardimSection [data-git]')].map(b => b.dataset.git))]"):
        pg.evaluate("() => gorunumAc('yardimSection')")
        pg.click(f"#yardimSection [data-git={hedef}] >> nth=0"); pg.wait_for_timeout(100)
        sonuc.append([hedef, pg.evaluate("() => GORUNUM"),
                      pg.evaluate("() => acikGorunumler().some(([x]) => x === arguments[0])".replace("arguments[0]", json.dumps(hedef))),
                      pg.evaluate("() => (document.querySelector('#yardimSection .yardimnot')||{textContent:''}).textContent.replace(/\\s+/g,' ')")])
    print("GIT:" + json.dumps(sonuc))
    pg.evaluate("() => gorunumAc('yardimSection')")
    pg.click("#yardimSection [data-ac=plan]"); pg.wait_for_timeout(300)
    print("ISARET:" + pg.evaluate("() => [...document.querySelectorAll('dialog[open] h2')].map(h => h.textContent).join('|')"))
    m = b.new_page(viewport={"width": 390, "height": 900})
    m.goto(adres, wait_until="networkidle"); m.wait_for_timeout(800)
    m.click("#kilavuzBtn"); m.wait_for_timeout(200)
    print("MOBIL:" + str(m.evaluate("() => [GORUNUM, document.documentElement.scrollWidth > innerWidth]")))
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
    assert c["RAY"] == "YARDIM|Kullanım kılavuzu", c["RAY"]
    assert c["BASLIK"] == "yardimSection|false", c["BASLIK"]
    git = json.loads(c["GIT"])
    assert len(git) >= 10
    # Açık görünüme gidiliyor; kapalıysa (vitrinde kaydedilmiş program yok)
    # sessizce başka görünüme düşülmüyor.
    for hedef, gidilen, acik, notu in git:
        if acik:
            assert gidilen == hedef, git
        else:
            # Kapalı görünüm: kılavuzda kalınıyor ve nedeni yazıyor.
            assert gidilen == "yardimSection" and "veri olmadığı için kapalı" in notu, git
    assert any(not a for _, _, a, _ in git), "vitrinde kapalı görünüm kalmamış; durum sınanmadı"
    assert c["MOBIL"] == "['yardimSection', False]", c["MOBIL"]
    assert "Plandan işaretle" in c["ISARET"], c["ISARET"]      # aynı kurulum penceresi


def test_AD_tek_kaynaktan():
    """Aracın adı kılavuza elle yazılmıyor (bkz. test_ad): ad değişirse
    kılavuz da peşinden gelmeli."""
    assert "DEPAR" not in KILAVUZ and "İTÜ" not in KILAVUZ
    assert "__AD_KISA__, __AD_KURUM__ öğrencileri" in KILAVUZ
