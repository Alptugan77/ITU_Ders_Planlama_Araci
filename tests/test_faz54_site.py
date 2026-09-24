"""Faz 54 — siteyi ziyaretçi gibi gezmek (kullanıcı 23.09.2026: *"siteyi
gözden geçirip ux ve ui konusunda geliştirip eklenicek şeyleri ekler misin"*).

Yayınlanan statik site (Pyodide) baştan sona yeni bir ziyaretçi olarak
gezildi. Çıkanlar, ağırlığına göre:

1. ★★★ **Site ÇAP/yandal planını başka bölümden seçiyordu.** Kurulum
   `plan_host_program`ı siliyordu; motorun "anadalına uygun plan" süzgeci
   (ilk kullanıcı incelemesi A3) sitede hiçbir şey bulamayıp EN YENİ planı
   alıyordu. 5437 (anadal × ikinci program) çiftinin **1802'si (%33)**
   başka bölümün planına düşüyordu: HTAE + BLG → `ROS_BLG` (doğrusu
   `TUMMUH_BLG`). Tablo tutulunca 272'ye indi; kalanın sebebi aynı çiftin
   YENİ iterasyonunun bir anadalı listeden düşürmesiydi → yerelin seçeceği
   her plan da tutuluyor: **17 653 çiftin 0'ında fark**.
2. ★★ **Faz 53'ün sitede kırdığı şey:** sitenin ilk durumu `applyState`ten
   geliyor; Faz 53 onu "durum değişikliği" sandı → kaydedilen program
   yüklenmiyor, paylaşılan bağlantı (#crn=…) uygulanmıyor, açılış DEPAR'da.
3. ★★ **Kontenjan tarihi yanlış damgaydı:** dört yer sayfanın ÜRETİLDİĞİ anı
   yazıyordu; sitede bu hep "şimdi" — 23 gün önceki kontenjan "bugün
   itibarıyla" görünüyordu, aynı sayfanın tepesi "23 gün önce" derken.
4. ★★ **Sitede verinin yedeği yoktu.** Transkript yalnız tarayıcının
   deposunda; silinince, cihaz değişince geri almanın yolu yoktu.
5. Dönem seçilince "N. dönem + alttan" kipi açılmıyordu (Faz 53'ün kip
   korumasının yan etkisi; ilk kart bunu vaat ediyor).
6. Sitede hiç çalışmayacak "tazele" düğmesi; sitede "bu dosya notlarını
   içerir" (dosya yok); ilk kartta kapalı adımların metni 2,0–3,5:1.
"""
import gzip
import json
import os
import pathlib
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest

from itucap import db
from itucap import plans as PL
from itucap import ui as UI
from itucap.normalize import base_program_code

KOK = pathlib.Path(UI.__file__).resolve().parents[2]
sys.path.insert(0, str(KOK / "tools"))
import site_kur  # noqa: E402

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")
APP_JS = (KOK / "web" / "app.js").read_text(encoding="utf-8")


def _kod(metin: str) -> str:
    metin = re.sub(r"/\*.*?\*/", " ", metin, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", " ", metin)


def _fn(ad: str, kaynak: str = KAYNAK) -> str:
    m = re.search(r"(?:async )?function " + ad + r"\((.*?)\)\{(.*?)\n\}", kaynak, re.S)
    assert m, f"{ad} yok"
    return _kod(m.group(2))


# ===================================================== 1. plan seçimi sitede
def _katalog(yol: pathlib.Path) -> sqlite3.Connection:
    """HTAE anadal · BLG'nin iki ÇAP planı: TUMMUH_BLG (2018, HTAE'ye açık) ve
    ROS_BLG (2025, YENİ ama yalnız ROS'a) · MAD'ın aynı çiftten iki
    iterasyonu: 2018 ELE'ye açık, 2023 değil."""
    con = db.connect(yol, "schema.sql")
    con.executemany(
        "INSERT INTO program(code,name,level) VALUES (?,?,'LS')",
        [("HTAE", "Harita (İng.)"), ("ELE", "Elektronik"), ("ROS", "Robotik"),
         ("BLG", "Bilgisayar"), ("MAD", "Maden")])
    con.executemany(
        """INSERT INTO plan(id,program_code,plan_type,title,host_program_code,iteration,source)
           VALUES (?,?,?,?,?,?,'obs')""",
        [(1, "HTAE", "lisans", "HTAE lisans", None, "2024-2025 / Güz Dönemi Sonrası"),
         (2, "ELE", "lisans", "ELE lisans", None, "2024-2025 / Güz Dönemi Sonrası"),
         (10, "BLG", "cap", "TUMMUH_BLG ÇAP Programı", "TUMMUH",
          "2018-2019 / Güz Dönemi Sonrası"),
         (11, "BLG", "cap", "ROS_BLG ÇAP Programı", "ROS", "2025-2026 / Güz Dönemi Sonrası"),
         (20, "MAD", "cap", "TUMMUH_MAD 2018", "TUMMUH", "2018-2019 / Güz Dönemi Sonrası"),
         (21, "MAD", "cap", "TUMMUH_MAD 2023", "TUMMUH", "2023-2024 / Güz Dönemi Sonrası")])
    con.executemany(
        "INSERT INTO plan_host_program(plan_id,program_code,obs_code) VALUES (?,?,?)",
        [(10, "HTAE", "HTAE_LS"), (10, "HTA", "HTA_LS"), (10, "ELE", "ELE_LS"),
         (11, "ROS", "ROS_LS"),
         (20, "ELE", "ELE_LS"), (21, "HTA", "HTA_LS")])
    con.commit()
    return con


def test_KURULUM_host_tablosunu_TUTUYOR_ve_secim_AYNI(tmp_path):
    """★★★ Sitenin katalogunda otomatik plan seçimi, yerel araçla BİREBİR
    aynı olmalı. Eskiden `plan_host_program` siliniyordu: HTAE + BLG →
    ROS_BLG (en yeni, başka bölümün)."""
    tam = _katalog(tmp_path / "ref.sqlite3")
    tam.close()
    site_kur.prune(tmp_path / "ref.sqlite3", tmp_path / "site.sqlite3")
    t = sqlite3.connect(tmp_path / "ref.sqlite3"); t.row_factory = sqlite3.Row
    s = sqlite3.connect(tmp_path / "site.sqlite3"); s.row_factory = sqlite3.Row
    assert PL.ikinci_plan(t, "BLG", "cap", "HTAE") == 10
    assert PL.ikinci_plan(s, "BLG", "cap", "HTAE") == 10, "site başka bölümün planını seçti"
    # Aynı çiftin YENİ iterasyonu ELE'yi düşürmüş: yerel 2018'i seçiyor,
    # site de seçebilmeli (eski iterasyon tutulmalı).
    assert PL.ikinci_plan(t, "MAD", "cap", "ELE") == 20
    assert PL.ikinci_plan(s, "MAD", "cap", "ELE") == 20, "gereken eski iterasyon atıldı"
    # Budama işini yine yapıyor: kimsenin seçmeyeceği satır yok.
    assert s.execute("SELECT COUNT(*) FROM plan_host_program WHERE plan_id NOT IN "
                     "(SELECT id FROM plan)").fetchone()[0] == 0


def test_KURULUM_bekcisi_kaynakta():
    kod = open(site_kur.__file__, encoding="utf-8").read()
    govde = re.search(r"def prune\(.*?\n    return stats", kod, re.S).group(0)
    assert re.search(r'for t in \([^)]*\):', govde)
    silinen = re.search(r'for t in \(([^)]*)\):', govde).group(1)
    assert "plan_host_program" not in silinen, "host tablosu yine topluca siliniyor"
    assert "keep |= _gereken_planlar(con)" in govde


def test_PENCERE_plani_KIMIN_icin_oldugunu_soyluyor():
    g = KAYNAK[KAYNAK.index("const planUygunMu"):KAYNAK.index("const fillPlans")]
    assert "tabanKod(an)" in g
    f = _kod(KAYNAK[KAYNAK.index("const fillPlans"):KAYNAK.index("const turetilenKodlar")])
    assert "öğrencileri için (${uygun.length})" in f
    assert "başka bölümlerin planları (${diger.length})" in f
    assert "senin planın\n            olmayabilir" in f or "senin planın" in f
    # Anadal değişince plan listesi yeniden kuruluyor.
    assert re.search(r'\$\("#fAnadal"\)\.addEventListener\("change", \(\) => \{\s*'
                     r'kindsOf\(kind\)\.forEach\(k => fillPlans\(k\)\);', KAYNAK)
    # Sunucu her plana bağlı programları veriyor.
    srv = (KOK / "src" / "itucap" / "server.py").read_text(encoding="utf-8")
    assert "group_concat(program_code, ' ') FROM plan_host_program" in srv


def test_JS_taban_kod_PYTHON_ile_ayni():
    """İki yerde aynı kural — ayrışırsa pencere motordan farklı plan önerir."""
    if not shutil.which("node"):
        pytest.skip("node yok")
    js = re.search(r"const tabanKod = (\(c\) => .*?);\n", KAYNAK).group(1)
    kodlar = ["HTAE", "HTA", "BLGE", "BLG", "EE", "E", "", "CEVE", "ENDE", "MAKE"]
    r = subprocess.run(["node", "-e", f"const f = {js}; console.log(JSON.stringify("
                        f"{json.dumps(kodlar)}.map(f)))"], capture_output=True, text=True)
    assert json.loads(r.stdout) == [base_program_code(k) for k in kodlar]


# ===================================================== 2. ilk açılış = boot
def test_SITENIN_ilk_durumu_ILK_ACILIS():
    g = _fn("applyState")
    assert "boot(_acildi ? onceki : undefined);" in g
    b = _fn("boot")
    assert b.rstrip().endswith("_acildi = true;"), "boot bitince bayrak kalkmıyor"


def test_KURULUM_isleri_VARSAYILAN_kipe():
    """Dönem ilk kez seçilince dönemlik kip açılmalı (ilk kartın sözü)."""
    assert "async function save(fn, secenek = {varsayilanKip: true}){" in KAYNAK
    assert "applyState(await fn(), secenek);" in _fn("save")
    assert "const i = onceki.varsayilan ? -1 : MODES.findIndex(" in _fn("boot")
    # Tercih ve meşgul saat öneriyi değiştiriyor ama DURUMU değil: kip korunur.
    # ⚠️ Faz 59: tercih gövdesi `govde()`ye taşındı (önizlemeyle ortak); eskiden
    # burada `}), {});` kalıbı SAYILIYORDU — biçim değişince kural bozulmuş
    # gibi görünüyordu. Artık iki çağrının kendisi aranıyor.
    assert 'save(() => api("/api/tercih", govde()), {});' in KAYNAK
    assert 'label: $("#fAd").value}), {});' in KAYNAK       # meşgul saat


# ===================================================== 3. tarih
def test_KONTENJAN_tarihi_SON_TAZELEME():
    """Sayfanın üretildiği an (`generatedAt`) arayüzde HİÇBİR yerde tarih
    diye yazılmıyor; kontenjanın tarihi `veriTarihi()`."""
    js = KAYNAK[KAYNAK.index("<script>"):]
    assert "DATA.generatedAt" not in _kod(js)
    for fn in ("doluluk", "kayitKontrol"):
        assert "veriTarihi()" in _fn(fn), fn
    assert '$("#gen").textContent = veriTarihi();' in KAYNAK
    assert "Veriler <span" not in KAYNAK
    assert "return A && A.raw ? A.raw" in _fn("veriTarihi")


# ===================================================== 4. site ortamı
def test_SITEDE_olu_dugme_ve_yanlis_cumle_YOK():
    v = _fn("renderVeriYasi")
    assert re.search(r"siteMi\(\) \? `<span class=\"veriyazi sitenot\">", v), \
        "sitede tazele düğmesi yine çiziliyor"
    assert "return LIVE && DATA.canRefresh === false;" in _fn("siteMi")
    assert 'siteMi() ? "Notların yalnız bu tarayıcıda' in KAYNAK


def test_ADIMLAR_opaklikla_SOLDURULMUYOR():
    """opacity:.5 açıklamaları 2,0–3,5:1'e indiriyordu."""
    for kural in re.findall(r"\.step\.(?:kilit|done)\{([^}]*)\}", KAYNAK):
        assert "opacity" not in kural, kural


# ===================================================== 5. yedek
def test_YEDEK_yalniz_BILINEN_dosyalari_yaziyor():
    oku = APP_JS[APP_JS.index("async oku(dosya){"):APP_JS.index("async uygula(yedek){")]
    assert "KULLANICI_DOSYALARI.includes(y)" in oku, "yedekte keyfi yol yazılabilir"
    assert '"SQLite format 3"' in oku, "veritabanı başlığı doğrulanmıyor"
    assert "yedekOzet(" in oku, "içerik Python'da doğrulanmıyor"
    uyg = APP_JS[APP_JS.index("async uygula(yedek){"):APP_JS.index("async kalici(){")]
    # Yedekte olmayan dosya SİLİNİYOR — yoksa iki verinin karışımı kalırdı.
    assert "else await idbSil(yol);" in uyg
    assert "tomllib.loads(ayar_metni)" in APP_JS


def test_YEDEK_ONCE_soyluyor_SONRA_yaziyor():
    g = _fn("yedekDosyaSec")
    assert g.index("Y.oku(dosya)") < g.index("Y.uygula(sonuc.yedek)")
    assert "şimdiki verinin yerine geçecek" in g
    assert 'data-yedek="once"' in g, "önce şimdikini indirme yolu yok"
    # Kutu yalnız sitede — yerelde veri zaten dosyada ve yedekli.
    assert 'if(!siteMi() || !window.__ITUCAP_YEDEK__) return "";' in _fn("veriKutusu")


# ===================================================== 6. GERÇEK SİTE (Pyodide)
PYODIDE = KOK / "node_modules" / "pyodide"


class _Sessiz(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    """Sentetik katalogla GERÇEK siteyi kur (Pyodide dahil) ve sun.
    `site_kur.build` her şeyi `ROOT`tan okuyor: kaynak klasörleri gerçek,
    yalnız katalog sentetik."""
    if not (PYODIDE / "pyodide.asm.wasm").exists():
        pytest.skip("node_modules/pyodide yok — gerçek site kurulamaz")
    pytest.importorskip("playwright.sync_api")
    kok = tmp_path_factory.mktemp("sitekok")
    for ad in ("src", "web", "config"):
        (kok / ad).symlink_to(KOK / ad)
    (kok / "data").mkdir()
    con = _katalog(kok / "data" / "reference.sqlite3")
    # HTAE 1. dönem: iki zorunlu ders; BLG ÇAP: bir ders. Hepsinin şubesi var.
    dersler = [("GEO 101E", 1, 1, [("501", 1, 510, 629)]),
               ("GEO 103E", 1, 1, [("502", 2, 510, 629)]),
               ("BLG 101E", 10, None, [("601", 3, 510, 629)])]
    for i, (kod, plan, donem, subeler) in enumerate(dersler):
        con.execute("INSERT INTO course(code,name,credits,ects) VALUES (?,?,3,4)",
                    (kod, "Ders " + kod))
        con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,position,term_no)"
                    " VALUES (?,'REQUIRED',?,?,?)", (plan, kod, i, donem))
        for crn, gun, bas, bit in subeler:
            con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled,updated_at)"
                        " VALUES (?,?,40,0,'2026-08-31T10:34:00')", (crn, kod))
            for prog in ("HTAE", "BLG", "BLGE"):
                con.execute("INSERT INTO lesson_allowed_program(crn,program_code)"
                            " VALUES (?,?)", (crn, prog))
            con.execute("INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min)"
                        " VALUES (?,?,?,?)", (crn, gun, bas, bit))
    con.commit(); con.close()
    eski = (site_kur.ROOT, site_kur.SITE)
    site_kur.ROOT, site_kur.SITE = kok, kok / "site"
    try:
        site_kur.build(PYODIDE)
    finally:
        site_kur.ROOT, site_kur.SITE = eski
    h = ThreadingHTTPServer(("127.0.0.1", 0), partial(_Sessiz, directory=str(kok / "site")))
    threading.Thread(target=h.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{h.server_address[1]}/", kok
    h.shutdown()


HAZIR = "() => document.querySelector('main') && !document.getElementById('yukleniyor')"


def _ac(pw, profil, url):
    ctx = pw.chromium.launch_persistent_context(str(profil), viewport={"width": 1280, "height": 900},
                                                accept_downloads=True)
    pg = ctx.pages[0] if ctx.pages else ctx.new_page()
    pg.goto(url, wait_until="commit")
    pg.wait_for_function(HAZIR, timeout=180000)
    pg.wait_for_timeout(500)
    return ctx, pg


def _kaydet(pg):
    pg.click("#setupSave")
    pg.wait_for_function("() => !document.querySelector('#setup').open", timeout=120000)
    pg.wait_for_timeout(400)


def test_GERCEK_SITE_bastan_sona(site, tmp_path):
    """★★★ Gerçek Pyodide ile yeni ziyaretçi: tarih, plan seçimi, dönem,
    kaydedilen programın açılışta gelmesi, paylaşılan bağlantı, yedek ve
    yeni cihazda yedekten devam."""
    from playwright.sync_api import sync_playwright
    url, kok = site
    with sync_playwright() as pw:
        ctx, pg = _ac(pw, tmp_path / "p1", url)
        c = {}
        c["alt"] = pg.inner_text("footer")
        c["tazele"] = pg.evaluate("() => !!document.getElementById('veriTazele')")
        pg.click("button:has-text('Bölümünü seç')"); pg.wait_for_timeout(300)
        pg.select_option("#fAnadal", value="HTAE")
        pg.click("#setup button:has-text('ÇAP')")
        pg.select_option("#fProg-cap", value="BLG"); pg.wait_for_timeout(200)
        c["gruplar"] = pg.evaluate("() => [...document.querySelectorAll('#fPlan-cap optgroup')].map(g => g.label)")
        _kaydet(pg)
        c["plan"] = pg.evaluate("() => SECONDS().map(s => s.planId)")
        pg.click("button:has-text('Dönemi seç')"); pg.wait_for_timeout(300)
        pg.evaluate("() => [...document.querySelectorAll('dialog[open] button')]"
                    ".filter(b => b.textContent.trim() === '1')[0].click()")
        _kaydet(pg)
        c["donemKip"] = pg.evaluate("() => M().key")
        # Programı kaydet → yeniden aç: kaydedilen program gelmeli.
        pg.evaluate("() => gorunumAc('schedSection')")
        pg.click("#savePicks")
        pg.wait_for_function("() => (DATA.savedPicks && DATA.savedPicks.picks || []).length > 0",
                             timeout=120000)
        kayitli = pg.evaluate("() => sel.map(x => x.crn).sort().join(',')")
        pg.reload(wait_until="commit"); pg.wait_for_function(HAZIR, timeout=180000)
        pg.wait_for_timeout(500)
        c["acilisKip"] = pg.evaluate("() => M().key")
        c["acilisSel"] = pg.evaluate("() => sel.map(x => x.crn).sort().join(',')") == kayitli
        # Paylaşılan bağlantı
        # ⚠️ Yalnız karma değişimi sayfayı yeniden YÜKLEMİYOR — bağlantıya
        # tıklayan kişi gibi baştan aç.
        pg.goto(url + "#crn=502", wait_until="commit")
        pg.reload(wait_until="commit"); pg.wait_for_function(HAZIR, timeout=180000)
        pg.wait_for_function("() => sel.length === 1", timeout=30000)
        c["baglanti"] = pg.evaluate("() => sel.map(x => x.crn).join(',')")
        # Yedek
        pg.goto(url, wait_until="commit"); pg.wait_for_function(HAZIR, timeout=180000)
        pg.evaluate("() => gorunumAc('setupbar')"); pg.wait_for_timeout(300)
        with pg.expect_download() as d:
            pg.click("#yedekIndir")
        yedek = tmp_path / "yedek.json"
        d.value.save_as(yedek)
        ctx.close()
        # Yeni cihaz: ilk karttan yedekten devam.
        ctx, pg = _ac(pw, tmp_path / "p2", url)
        with pg.expect_file_chooser() as fc:
            pg.click("#heroYedek")
        fc.value.set_files(str(yedek)); pg.wait_for_timeout(800)
        c["onay"] = pg.inner_text("#heroYedekDurum")
        with pg.expect_navigation(timeout=60000):
            pg.click('#heroYedekDurum [data-yedek="uygula"]')
        pg.wait_for_function(HAZIR, timeout=180000); pg.wait_for_timeout(500)
        c["geri"] = pg.evaluate("() => [SETUP.anadalProgram, DATA.donem, "
                                "(DATA.savedPicks.picks || []).length].join('|')")
        # Bozuk yedek yazılmıyor.
        kotu = tmp_path / "kotu.json"
        kotu.write_text('{"tur":"itucap-yedek","surum":1,"dosyalar":{"/etc/x":{"metin":"1"}}}')
        pg.evaluate("() => gorunumAc('setupbar')"); pg.wait_for_timeout(300)
        with pg.expect_file_chooser() as fc:
            pg.click("#yedekSec")
        fc.value.set_files(str(kotu)); pg.wait_for_timeout(600)
        c["kotu"] = pg.inner_text("#veriYedek")
        ctx.close()
    assert "31.08.2026 10:34 itibarıyla" in c["alt"], c["alt"]
    assert c["tazele"] is False, "sitede çalışmayacak tazele düğmesi var"
    assert c["gruplar"][0].startswith("HTAE öğrencileri için (1)"), c["gruplar"]
    assert c["plan"] == [10], f"ÇAP planı başka bölümün: {c['plan']}"
    assert c["donemKip"] == "term", "dönem seçilince dönemlik kip açılmadı"
    assert c["acilisKip"] == "term", "sitenin ilk açılışı varsayılan kipte değil"
    assert c["acilisSel"], "kaydedilen program açılışta yüklenmedi"
    assert c["baglanti"] == "502", f"paylaşılan bağlantı uygulanmadı: {c['baglanti']}"
    assert "yerine geçecek" in c["onay"] and "HTAE" in c["onay"], c["onay"]
    assert c["geri"].startswith("HTAE|1|"), c["geri"]
    assert c["geri"].split("|")[2] != "0", "kaydedilen program yedekte yoktu"
    assert "beklenmeyen dosya" in c["kotu"], c["kotu"]


def test_TELEFONDA_arama_kutusu_44px():
    """Ölçüldü: aday listesinin arama kutusu telefonda 38px'ti."""
    govde = KAYNAK[KAYNAK.index("  .tickbox{min-height:44px}"):][:400]
    assert "#candQ{min-height:44px}" in govde
