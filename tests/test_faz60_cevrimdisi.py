"""Faz 60 — kayıt günü çevrimdışı (fikirler Y.8).

Kayıt günü bağlantı en kötü anında. Statik site her açılışta motoru,
kataloğu ve Pyodide'i ağdan indiriyordu; bağlantı yoksa planladığın
program, CRN listesi ve yedek plan dahil HİÇBİR ŞEY açılmıyordu.

`web/sw.js` (site_kur `site/sw.js`e yazıyor):
* yalnız kendi kökenimiz, yalnız GET/HEAD — CDN'e ve başka yere dokunmuyor;
* kabuk ağ önce (bağlantı varsa taze), yoksa kopya; Pyodide önbellek önce;
* ★ kopyadan gelen cevap `X-Itucap-Onbellek: 1` taşıyor ve sayfa "cihazdaki
  kopyadan açıldı — kontenjan şu tarihte tazelendi" diyor. Eski kontenjanı
  canlıymış gibi göstermek bu aracın yapmadığı şey.

Gerçek site burada kurulamıyor (katalog ve Pyodide yok); katman, AYNI
`site_kur.cevrimdisi_katman` ile yazılmış küçük bir sitede, gerçek
Chromium'da ölçülüyor: çevrimiçi aç → çevrimdışı yenile → açılıyor ve
işaretli; katalog değişince eski kopya siliniyor.
"""
import json
import pathlib
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import ui as UI

KOK = Path(UI.__file__).resolve().parents[2]
SW = (KOK / "web" / "sw.js").read_text(encoding="utf-8")
APP = (KOK / "web" / "app.js").read_text(encoding="utf-8")
KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


def _kod(metin):
    return re.sub(r"/\*.*?\*/", " ", metin, flags=re.S)


# ------------------------------------------------------------------ statik
def test_SW_yalniz_KENDI_KOKENIMIZ_ve_OKUMA():
    k = _kod(SW)
    assert "if(url.origin !== self.location.origin) return;" in k
    assert 'if(r.method !== "GET" && r.method !== "HEAD") return;' in k
    # Hiçbir dış adres, hiçbir gönderim.
    assert "http://" not in k and "https://" not in k
    assert "postMessage" not in k and "sendBeacon" not in k


def test_KOPYA_ISARETLI_ve_SAYFA_SOYLUYOR():
    assert 'const ISARET = "X-Itucap-Onbellek";' in SW
    assert 'if(res.headers.get("X-Itucap-Onbellek")) window.__ITUCAP_ONBELLEK__ = true;' in APP
    f = KAYNAK[KAYNAK.index("function cevrimdisiDurumu(){"):]
    f = f[:f.index("\n}\n")]
    assert "veriYasiMetni()" in f and "CRN'leri OBS'de doğrula" in f
    b = KAYNAK[KAYNAK.index("function boot(onceki){"):]
    assert "cevrimdisiDurumu();" in b[:b.index("\n}\n")]


def test_KAYIT_SITE_ACILDIKTAN_SONRA():
    """İlk ziyarette büyük indirmeyle yarışmasın."""
    i = APP.index("cevrimdisiKatmanKur();")
    assert APP.index("if(yuk) yuk.remove();") < i
    assert "window.isSecureContext" in APP


def test_SURUM_katalog_ve_motordan_PYODIDE_haric(tmp_path):
    sys.path.insert(0, str(KOK / "tools"))
    import site_kur
    (tmp_path / "pyodide").mkdir()
    (tmp_path / "pyodide" / "pyodide.js").write_text("1")
    (tmp_path / "katalog.sqlite3.gz").write_bytes(b"a")
    s1 = site_kur.cevrimdisi_katman(tmp_path).read_text()
    (tmp_path / "pyodide" / "pyodide.js").write_text("2")
    s2 = site_kur.cevrimdisi_katman(tmp_path).read_text()
    (tmp_path / "katalog.sqlite3.gz").write_bytes(b"b")
    s3 = site_kur.cevrimdisi_katman(tmp_path).read_text()
    surum = lambda s: re.search(r'const SURUM = "(\w+)";', s).group(1)
    assert surum(s1) == surum(s2), "Pyodide değişince kabuk önbelleği boşuna silindi"
    assert surum(s1) != surum(s3), "katalog değişti ama eski kopya yeni sanılacaktı"
    dosyalar = json.loads(re.search(r"const DOSYALAR = (\[.*?\]);", s3).group(1))
    assert "katalog.sqlite3.gz" in dosyalar and "pyodide/pyodide.js" in dosyalar
    assert "sw.js" not in dosyalar
    assert f'"itucap-pyodide-{site_kur.PYODIDE_VERSION}"' in s3
    assert "__" not in re.sub(r"__ITUCAP_ONBELLEK__", "", s3.split('"use strict";')[1])


# ------------------------------------------------------------------ uçtan uca
_SAYFA = """<!doctype html><meta charset="utf-8"><title>t</title>
<script>
window.olc = async () => {
  const r = await fetch("./katalog.sqlite3.gz");
  const h = await fetch("./pyodide/pyodide.js", {method: "HEAD"});
  return {katalog: await r.text(), isaret: r.headers.get("X-Itucap-Onbellek") || "",
          head: h.status};
};
window.kaydol = async () => {
  await navigator.serviceWorker.register("./sw.js");
  await navigator.serviceWorker.ready;
  return true;
};
</script>"""

_CANLI = r'''
import sys, os, json, threading, http.server, pathlib
sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import site_kur
kok = pathlib.Path(os.environ["SITE"])
site_kur.cevrimdisi_katman(kok)
# ⚠️ Playwright'ın `set_offline`ı service worker'ın isteklerini KESMİYOR
# (ölçüldü: "çevrimdışı" yenilemede sunucu iki istek aldı). Gerçek kopukluk
# için sunucu, KAPALI iken bağlantıyı cevapsız kapatıyor.
KAPALI = [False]
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(s, *a, **k): super().__init__(*a, directory=str(kok), **k)
    def log_message(s, *a): pass
    def end_headers(s):
        # GitHub Pages gibi: 10 dk taze. sw.js'in `no-cache`ı olmasa çevrimdışı
        # istek bu HTTP önbelleğinden İŞARETSİZ dönerdi.
        s.send_header("Cache-Control", "max-age=600")
        super().end_headers()
    def handle(s):
        if KAPALI[0]:
            s.close_connection = True
            return
        super().handle()
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
adres = f"http://127.0.0.1:{srv.server_address[1]}/"
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context()
    pg = ctx.new_page()
    pg.goto(adres); pg.evaluate("() => kaydol()")
    pg.reload(); pg.wait_for_function("() => !!navigator.serviceWorker.controller")
    print("CEVRIMICI:" + json.dumps(pg.evaluate("() => olc()")))
    ctx.set_offline(True); KAPALI[0] = True
    pg.reload()
    print("CEVRIMDISI:" + json.dumps(pg.evaluate("() => olc()")))
    # Başka kökene istek önbellekten KARŞILANMIYOR (dokunmuyoruz).
    print("DIS:" + pg.evaluate("""() => fetch('http://localhost:9/x').then(() => 'geldi', () => 'yok')"""))
    ctx.set_offline(False); KAPALI[0] = False
    # Katalog değişti → yeni sürüm → eski kopya silinmeli.
    (kok / "katalog.sqlite3.gz").write_text("YENI")
    # ⚠️ KÖK SEBEP (24.09.2026, ~%50 kırmızı): HTTP `Last-Modified` saniye
    # çözünürlüklü. Test 1,4 sn sürüyor; ESKI ile YENI aynı saniyede yazılınca
    # yeniden doğrulama 304 alıyor ve tarayıcı ESKI gövdeyi kullanıyordu.
    # Yayında olmaz (GitHub Pages ETag kullanıyor, dağıtımlar saniyelerce ayrı);
    # düzenekte dosya zamanı ileri alınıyor.
    # sw.js İÇİN DE: aynı saniyede yeniden yazılınca tarayıcının güncelleme
    # denetimi 304 alıp "değişmedi" diyordu — yeni sürüm hiç kurulmuyordu.
    import os, re, time
    ileri = time.time() + 10
    os.utime(kok / "katalog.sqlite3.gz", (ileri, ileri))
    yeni_sw = site_kur.cevrimdisi_katman(kok)
    os.utime(yeni_sw, (ileri, ileri))
    yeni_ad = "itucap-kabuk-" + re.search(r'const SURUM = "(\w+)";', yeni_sw.read_text()).group(1)
    # Gerçek akış: güncellenmiş siteye ÇEVRİMİÇİ yeni bir ziyaret. Eski sekme
    # kapanıyor (devir teslimde eski SW'nin hizmet ettiği sayfa kalmasın).
    # ⚠️ Sabit bekleme DEĞİL: sürüm değişiminin süresi değişken — 1,5 sn'lik
    # uyku zaman zaman yetmiyordu (24.09.2026, 4 koşuda 2 kırmızı).
    pg.close()
    pg = ctx.new_page(); pg.goto(adres)
    pg.evaluate("() => navigator.serviceWorker.getRegistration().then(r => r.update())")
    # Beklenen önbellek ADI yeni sw.js'ten — koşul boşuna sağlanamasın.
    pg.wait_for_function("""(ad) => caches.keys().then(k => {
        const kab = k.filter(a => a.startsWith('itucap-kabuk-'));
        return kab.length === 1 && kab[0] === ad; })""", arg=yeni_ad, timeout=20000)
    pg.close()
    pg = ctx.new_page(); pg.goto(adres)
    pg.wait_for_function("() => !!navigator.serviceWorker.controller")
    print("ONBELLEK:" + json.dumps(pg.evaluate("() => caches.keys()")))
    ctx.set_offline(True); KAPALI[0] = True
    pg.reload()
    print("YENI:" + json.dumps(pg.evaluate("() => olc()")))
    b.close()
srv.shutdown()
'''


def test_UCTAN_UCA_cevrimdisi_acilis(tmp_path, monkeypatch):
    try:
        import playwright  # noqa: F401
    except ImportError:
        pytest.skip("playwright yok")
    site = tmp_path / "site"
    (site / "pyodide").mkdir(parents=True)
    (site / "index.html").write_text(_SAYFA, encoding="utf-8")
    (site / "katalog.sqlite3.gz").write_text("ESKI")
    (site / "pyodide" / "pyodide.js").write_text("// py")
    monkeypatch.setenv("ITUCAP_TOOLS", str(KOK / "tools"))
    monkeypatch.setenv("SITE", str(site))
    betik = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, dir=str(tmp_path))
    betik.write(_CANLI); betik.close()
    r = subprocess.run([sys.executable, betik.name], capture_output=True, text=True,
                       timeout=180, cwd=str(tmp_path))
    if r.returncode != 0:
        if "Executable doesn't exist" in r.stderr or "BrowserType.launch" in r.stderr:
            pytest.skip("tarayıcı başlatılamadı")
        pytest.fail(r.stderr[-2000:])
    c = dict(s.split(":", 1) for s in r.stdout.strip().splitlines()
             if ":" in s and s.split(":", 1)[0].isupper())
    on, off = json.loads(c["CEVRIMICI"]), json.loads(c["CEVRIMDISI"])
    assert on == {"katalog": "ESKI", "isaret": "", "head": 200}, on
    # Çevrimdışı: sayfa açıldı, katalog kopyadan ve İŞARETLİ; Pyodide HEAD'i
    # CDN'e düşmüyor.
    assert off == {"katalog": "ESKI", "isaret": "1", "head": 200}, off
    assert c["DIS"] == "yok"
    anahtar = json.loads(c["ONBELLEK"])
    assert len([a for a in anahtar if a.startswith("itucap-kabuk-")]) == 1, anahtar
    assert json.loads(c["YENI"])["katalog"] == "YENI", "eski katalog kopyası kaldı"
