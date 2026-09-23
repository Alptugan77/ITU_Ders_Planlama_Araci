"""Faz 52 — yüklenme ekranı (kullanıcı 21.09.2026: *"açılış ekranını
güncelleyip yazıları büyütebilirsin — açılış ekranı dediğim yüklenme
ekranı"*) ve bütün sekmelerde aynı genişlik.

Ölçüm (statik site, ~200 KB/s'lik bağlantı, toplam ~92 sn):

| | önce | sonra |
|---|---|---|
| yükleyici görünmeden önce inen | **571 KB** (486'sı yazı tipi) | **90 KB** |
| ilk boyama (beyaz sayfa süresi) | **2984 ms** | **632 ms** |
| çubuk, Python indirilirken | **68 sn %16,7'de donuk** | bayta bağlı, sürekli ilerliyor |
| çubuk %100 iken süren iş | **4,7 sn** | 0 — %100 ancak bitince |
| sayılan bayt | — (adım sayıyordu) | 17,3 / 17,3 MB |
| durum satırı | 12px, gri, eş aralıklı | 19px, koyu |
| çubuk kalınlığı | 3px | 8px |
| hata olunca | gri metin, düğme yok | açıklama + "Yeniden dene" |
| ekran okuyucu | hiçbir şey duymuyordu | `status` + `progressbar` |

⚠️ İlk sürümün kendisi de ölçümle yakalandı: Pyodide `fetch`e DİZGE değil
`URL` NESNESİ veriyor, sayaç onu okuyamıyordu — 17,3 MB'ın yalnız 5,2'si
sayıldı ve indirme sürerken yanlış "takıldı" uyarısı çıktı. Aşağıdaki sahte
Pyodide TAM OLARAK bunu yapıyor, yani o hata geri gelirse test kırılır.
"""
import gzip
import json
import os
import pathlib
import re
import shutil
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest

from itucap import ui as UI

KOK = pathlib.Path(UI.__file__).resolve().parents[2]
sys.path.insert(0, str(KOK / "tools"))
import site_kur  # noqa: E402

APP_JS = (KOK / "web" / "app.js").read_text(encoding="utf-8")
APP_KOD = re.sub(r"/\*.*?\*/", " ", APP_JS, flags=re.S)       # yorumsuz


# ===================================================== 1. kabuğun sırası
def test_YUKLEYICIDEN_ONCE_az_bayt():
    """★★ Yükleyiciden önce 571 KB iniyordu, 486'sı gömülü yazı tipi —
    yavaş bağlantıda 3 sn beyaz sayfa. Yazı tipleri sona alındı."""
    h = site_kur.kabuk(UI)
    once = h[:h.index('id="yukleniyor"')]
    assert len(once.encode("utf-8")) < 150_000, \
        f"yükleyiciden önce {len(once.encode()) / 1e3:.0f} KB var"
    assert "@font-face" not in once, "yazı tipleri yine <head>'de"
    # Yazı tipleri KAYBOLMADI: sayfanın sonunda, hepsi.
    son = h[h.index("</main>"):]
    assert 'id="gomuluFontlar"' in son
    assert son.count("@font-face") == len(UI._FONT_YUZLERI)


def test_YEREL_ciktilar_DEGISMEDI():
    """`make app` ve `make ui` yerelden açılıyor; orada sıra değişmedi."""
    h = UI.render({})
    bas = h[:h.index("<body>")]
    assert bas.count("@font-face") == len(UI._FONT_YUZLERI)
    assert 'id="gomuluFontlar"' not in h


def test_APP_JS_yukleyicinin_ARKASINDA_async():
    """Eskiden sayfanın en sonundaydı: Pyodide indirmesi 835 KB'lık HTML
    bitmeden başlamıyordu."""
    h = site_kur.kabuk(UI)
    assert '<script src="./app.js" async></script>' in h, "app.js `async` değil"
    i_yuk = h.index('id="yukleniyor"')
    i_app = h.index('<script src="./app.js" async></script>')
    assert i_yuk < i_app < h.index("<main"), "app.js yükleyicinin hemen ardında değil"
    assert h.count('src="./app.js"') == 1
    # `async` betik erken çalışıyor: arayüzü beslemeden önce DOM beklenmeli.
    assert "await domHazir();" in APP_KOD
    assert APP_KOD.index("await domHazir();") < APP_KOD.index("window.__ITUCAP_APPLY__(data)")


# ===================================================== 2. çubuk bayta bağlı
def test_MANIFEST_beklenen_baytlari_biliyor(tmp_path):
    """Çubuğun paydası: her dosyanın boyu, kurulum anında ölçülüyor."""
    pyo = tmp_path / "pyo"; pyo.mkdir()
    (pyo / "pyodide.asm.wasm").write_bytes(b"x" * 1000)
    (pyo / "python_stdlib.zip").write_bytes(b"x" * 300)
    (pyo / "alakasiz.d.ts").write_bytes(b"x" * 50)          # yüklenmiyor → yok
    site = tmp_path / "site"
    (site / "itucap").mkdir(parents=True); (site / "config").mkdir()
    (site / "itucap" / "ui.py").write_bytes(b"x" * 70)
    (site / "config" / "k.toml").write_bytes(b"x" * 5)
    (site / "katalog.sqlite3.gz").write_bytes(b"x" * 200)
    y = site_kur._beklenen_baytlar(pyo, site)
    assert y["dosyalar"] == {"pyodide.asm.wasm": 1000, "python_stdlib.zip": 300,
                             "itucap/ui.py": 70, "config/k.toml": 5,
                             "katalog.sqlite3.gz": 200}
    assert y["toplam"] == 1575
    # Pyodide bilinmiyorsa (CDN) uydurma sayı YOK — yalnız bilinenler.
    y2 = site_kur._beklenen_baytlar(None, site)
    assert "pyodide.asm.wasm" not in y2["dosyalar"] and y2["toplam"] == 275


def test_SAYAC_URL_NESNESINI_okuyor():
    """⚠️⚠️ Pyodide `fetch(new URL(...))` çağırıyor. İlk sürüm yalnız dizge ve
    `Request.url` okuyordu: 17,3 MB'ın 5,2'si sayıldı, yanlış "takıldı"
    uyarısı çıktı."""
    m = re.search(r"window\.fetch = async function\(girdi, secenek\)\{(.*?)\n\};",
                  APP_KOD, re.S)
    assert m, "fetch sarmalayıcısı yok"
    govde = m.group(1)
    assert "String(girdi" in govde, "URL nesnesi dizgeye çevrilmiyor"
    # Başlıklar korunmalı: instantiateStreaming `application/wasm` istiyor.
    assert "headers: res.headers" in govde


def test_YUZDE_YUZ_ancak_BITINCE():
    """Eskiden son adımın BAŞINDA %100 oluyordu ve 4,7 sn daha çalışıyordu."""
    fn = re.search(r"function oran\(\)\{(.*?)\n\}", APP_KOD, re.S).group(1)
    assert "if(IZ.bitti) return 1;" in fn
    assert fn.count("Math.min(0.99") == 2, "bitmeden %100'e varılabiliyor"
    # Yükleme bitince sayaç sökülüyor — uygulamanın kendi istekleri sayılmasın.
    bitir = re.search(r"function izlemeyiBitir\(\)\{(.*?)\n\}", APP_KOD, re.S).group(1)
    assert "window.fetch = _asilFetch" in bitir


def test_ASAMALAR_iki_tarafta_ayni():
    """Liste site_kur'da çiziliyor, adımlar app.js'te ilerletiliyor —
    ayrışırsa bir adım hiç işaretlenmez."""
    js = re.search(r"const ASAMALAR = \[(.*?)\];", APP_KOD).group(1)
    js_adlar = re.findall(r'"(\w+)"', js)
    assert js_adlar == [a for a, _ in site_kur.YUK_ASAMALARI]
    for a in js_adlar:
        assert f'asama("{a}")' in APP_KOD, f"{a} adımı hiç başlatılmıyor"


# ===================================================== 3. okunur + erişilebilir
def _kural(secici: str) -> str:
    m = re.search(re.escape(secici) + r"\{([^}]*)\}", site_kur._LOADER_CSS)
    assert m, f"{secici} kuralı yok"
    return m.group(1).replace("\n", "").replace(" ", "")


def _px(kural: str, ozellik: str) -> float:
    m = re.search(ozellik + r":(?:clamp\([^,]+,[^,]+,)?([\d.]+)px", kural)
    assert m, f"{ozellik} yok: {kural}"
    return float(m.group(1))


def test_YAZILAR_BUYUK():
    """★ Kullanıcı: *"yazıları büyütebilirsin"*. Ölçüm (önce): izlenen durum
    satırı 12px ve GRİ; açılım 11,5px; gizlilik notu 13,5px; çubuk 3px."""
    assert _px(_kural("#yukleniyor .yukAdim"), "font-size") >= 18
    assert "color:var(--ink)" in _kural("#yukleniyor .yukAdim"), "durum yine gri"
    assert _px(_kural("#yukleniyor .gizlilik"), "font-size") >= 16
    assert _px(_kural("#yukleniyor .yukListe li"), "font-size") >= 15
    assert _px(_kural("#yukleniyor .acilim"), "font-size") >= 13
    assert _px(_kural("#yukleniyor .yukSayi"), "font-size") >= 14
    assert _px(_kural("#yukleniyor .cubuk"), "height") >= 6


def test_EKRAN_OKUYUCU_rolleri():
    """Görmeyen kullanıcı 90 sn'lik bekleyişte hiçbir şey duymuyordu."""
    h = site_kur._loader_html(UI)
    assert 'role="progressbar"' in h and 'aria-valuenow="0"' in h
    assert 'aria-label="Yükleme ilerlemesi"' in h
    assert 'id="yukAdim" role="status" aria-live="polite"' in h
    assert 'id="yukSayi" aria-hidden="true"' in h, "bayt satırı gürültü yapar"
    assert 'aria-busy="true"' in h
    assert 'kap.setAttribute("aria-valuenow"' in APP_KOD


def test_HAREKET_ve_ZORLANMIS_RENK():
    css = site_kur._LOADER_CSS
    m = re.search(r"@media \(prefers-reduced-motion:reduce\)\{(.*?)\}\}", css, re.S)
    assert m and "animation:none" in m.group(1)
    m = re.search(r"@media \(forced-colors:active\)\{(.*?)\}\}", css, re.S)
    assert m and "background:Highlight" in m.group(1), \
        "zorlanmış renkte çubuk görünmez olur (Faz 51 dersi)"


# ===================================================== 4. tarayıcıda (sahte Pyodide)
# Gerçek Pyodide 14 MB ve testte kurulmuyor. Sahtesi, gerçeğin ÖLÇÜLEN
# davranışını taklit ediyor: büyük dosyayı `URL` NESNESİYLE `fetch` ediyor ve
# gövdeyi akış olarak okuyor. Yükleyicinin HTML'i, CSS'i ve app.js GERÇEK.
_SAHTE_PYODIDE = r"""
window.loadPyodide = async ({indexURL}) => {
  const kok = new URL(indexURL, location.href);
  for(const ad of ["pyodide.asm.wasm", "python_stdlib.zip"]){
    const r = await fetch(new URL(ad, kok));            // ← URL NESNESİ
    if(!r.ok) throw new Error(ad + " yok");
    await r.arrayBuffer();
  }
  const fs = {};
  return {
    runPython(){}, async loadPackage(){},
    // Gerçekte son adım (motoru kurup programı hesaplamak) 4,7 sn sürüyor
    // ve eski çubuk O SÜRE BOYUNCA %100'dü. Sahtesi de beklesin ki
    // "bitmeden %100" davranışı ölçülebilsin.
    async runPythonAsync(){ await new Promise(ok => setTimeout(ok, 1500)); },
    FS: {mkdirTree(){}, writeFile(p, v){ fs[p] = v; },
         readFile(p){ if(!(p in fs)) throw new Error("yok"); return fs[p]; }},
    globals: {get(ad){
      return ad === "_cagir" ? (() => "{}") : (() => '{"hazir": true}'); }},
  };
};
"""


def _sahte_site(kok: pathlib.Path, katalog: bool = True) -> None:
    (kok / "pyodide").mkdir(parents=True)
    (kok / "itucap").mkdir(); (kok / "config").mkdir()
    (kok / "pyodide" / "pyodide.js").write_text(_SAHTE_PYODIDE, encoding="utf-8")
    (kok / "pyodide" / "pyodide.asm.wasm").write_bytes(os.urandom(1_500_000))
    (kok / "pyodide" / "python_stdlib.zip").write_bytes(os.urandom(400_000))
    (kok / "itucap" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (kok / "itucap" / "schema.sql").write_text("-- boş\n", encoding="utf-8")
    (kok / "config" / "k.toml").write_text("a = 1\n", encoding="utf-8")
    if katalog:
        (kok / "katalog.sqlite3.gz").write_bytes(gzip.compress(os.urandom(300_000)))
    shutil.copy(KOK / "web" / "app.js", kok / "app.js")
    (kok / "index.html").write_text(
        '<!doctype html><html lang="tr"><head><meta charset="utf-8">'
        f"{site_kur._LOADER_CSS}</head><body>{site_kur._loader_html(UI)}"
        '<script src="./app.js" async></script><main></main>'
        "<script>window.__ITUCAP_APPLY__ = d => { window.__uygulandi = d; };"
        "</script></body></html>", encoding="utf-8")
    manifest = {
        "engine": ["a"], "schema": ["schema.sql"], "config": ["k.toml"],
        "pyodide": {"version": "sahte", "local": True},
        "catalog": {"file": "katalog.sqlite3.gz",
                    "bytes": (kok / "katalog.sqlite3.gz").stat().st_size if katalog else 0},
        # ★ Paydayı GERÇEK işlev hesaplıyor — test onu da kapsıyor.
        "yuk": site_kur._beklenen_baytlar(kok / "pyodide", kok),
    }
    (kok / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


class _Sessiz(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@pytest.fixture
def sunucu(tmp_path):
    def kur(katalog=True):
        kok = tmp_path / ("site" if katalog else "site_eksik")
        _sahte_site(kok, katalog)
        h = ThreadingHTTPServer(("127.0.0.1", 0), partial(_Sessiz, directory=str(kok)))
        threading.Thread(target=h.serve_forever, daemon=True).start()
        kurulanlar.append(h)
        return f"http://127.0.0.1:{h.server_address[1]}/"
    kurulanlar = []
    yield kur
    for h in kurulanlar:
        h.shutdown()


def _tarayici():
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright
    try:
        pw = sync_playwright().start()
        return pw, pw.chromium.launch()
    except Exception as exc:                                   # pragma: no cover
        pytest.skip(f"playwright başlatılamadı: {exc}")


def test_TARAYICIDA_cubuk_GERCEK_BAYTI_izliyor(sunucu):
    """★★ Çubuk indirme sürerken İLERLİYOR (68 sn donmuyor), bütün baytlar
    sayılıyor (URL nesnesi dahil), %100'e ancak arayüz beslenince varıyor ve
    yavaş ama akan bir indirmede "takıldı" uyarısı ÇIKMIYOR."""
    url = sunucu()
    pw, b = _tarayici()
    try:
        ctx = b.new_context(viewport={"width": 390, "height": 844})
        pg = ctx.new_page()
        cdp = ctx.new_cdp_session(pg)
        cdp.send("Network.enable")
        cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": 20,
                 "downloadThroughput": 450_000, "uploadThroughput": 450_000})
        pg.goto(url, wait_until="commit")
        # ⚠️ "commit" yanıtın BAŞINDA dönüyor; belge henüz ayrıştırılmamış
        # olabilir. Tam pakette bir kez böyle oldu: ilk örnekte çubuk "yok"
        # sanıldı, döngü hemen bitti ("IZ is not defined"). Önce yükleyici.
        pg.wait_for_selector("#yukCubuk", state="attached", timeout=30000)
        ornek, hesap, erken_yuz, uyari = [], [], False, False
        for _ in range(240):
            r = pg.evaluate("""() => { const c = document.getElementById("yukCubuk");
              const u = document.getElementById("yukUyari");
              return {w: c ? parseFloat(c.style.width) || 0 : null,
                      asama: typeof IZ === "undefined" ? null : IZ.asama,
                      uyari: !!(u && !u.hidden), uygulandi: !!window.__uygulandi}; }""")
            if r["w"] is None:
                break
            if r["w"] >= 99.9 and not r["uygulandi"]:
                erken_yuz = True
            uyari = uyari or r["uyari"]
            if r["asama"] == "python":
                ornek.append(r["w"])
            elif r["asama"] == "hesap" and not r["uygulandi"]:
                hesap.append(r["w"])
            pg.wait_for_timeout(100)
        son = pg.evaluate("""() => ({uygulandi: window.__uygulandi,
          yukleyici: !!document.getElementById("yukleniyor"),
          sayilan: Object.values(IZ.alinan).reduce((a, b) => a + b, 0),
          beklenen: IZ.toplam,
          fetchGeri: /\\[native code\\]/.test(String(window.fetch))})""")
    finally:
        b.close(); pw.stop()
    farkli = sorted(set(ornek))
    assert len(farkli) >= 4, f"Python indirilirken çubuk kıpırdamadı: {farkli[:6]}"
    assert all(b2 >= a for a, b2 in zip(ornek, ornek[1:])), "çubuk geri gitti"
    assert son["sayilan"] == son["beklenen"] > 0, \
        f"baytların hepsi sayılmadı: {son['sayilan']} / {son['beklenen']}"
    # Son adım 1,5 sn sürüyor: o sırada çubuk ÖLÇÜLDÜ ve %100 DEĞİL.
    assert len(hesap) >= 5, f"son adım ölçülemedi: {hesap}"
    assert not erken_yuz and max(hesap) < 99.9, \
        f"arayüz beslenmeden %100 gösterildi: {hesap}"
    assert not uyari, "akan indirmede yanlış 'takıldı' uyarısı"
    assert son["uygulandi"] == {"hazir": True}, son
    assert not son["yukleyici"], "yükleyici kalkmadı"
    assert son["fetchGeri"], "sayaç sökülmedi — uygulamanın istekleri de sayılır"


def test_TARAYICIDA_HATA_yeniden_dene(sunucu):
    """Katalog yoksa: donmuş ekran değil, hangi adımda durduğu + düğme."""
    url = sunucu(katalog=False)
    pw, b = _tarayici()
    try:
        pg = b.new_page(viewport={"width": 390, "height": 844})
        pg.goto(url, wait_until="commit")
        pg.wait_for_function("() => { const h = document.getElementById('yukHata');"
                             " return h && !h.hidden; }", timeout=30000)
        r = pg.evaluate("""() => ({
          durum: document.getElementById("yukAdim").textContent,
          hataAdimi: (document.querySelector('#yukListe li[data-durum="hata"]')
                      || {dataset: {}}).dataset.a,
          odak: document.activeElement.id,
          mesgul: document.getElementById("yukleniyor").getAttribute("aria-busy"),
          dugme: Math.round(document.getElementById("yukTekrar")
                   .getBoundingClientRect().height)})""")
    finally:
        b.close(); pw.stop()
    assert r["durum"] == "Yüklenemedi", r
    assert r["hataAdimi"] == "katalog", f"hatanın adımı işaretlenmedi: {r}"
    assert r["odak"] == "yukTekrar", "odak 'Yeniden dene'ye gitmedi"
    assert r["mesgul"] is None, "aria-busy kalktı mı"
    assert r["dugme"] >= 44, f"'Yeniden dene' küçük: {r['dugme']}px"
