"""Faz 51 — UX/UI incelemesi: ekran okuyucu, zorlanmış renk, dokunmatik.

*19.09.2026 · kullanıcı: **"ux ve ui açısından uygulamayı inceleyip
eksiklerini giderir misin"***

Şimdiye kadarki turlar ölçülebilir olanı ölçtü: hedef boyu, kaydırma
derinliği, kontrast, yazdırma. Bu tur **hiç bakılmamış üç boyuta** baktı ve
üçünde de bilgi kaybı buldu.

| ölçüm | önce | sonra |
|---|---|---|
| `main` yer işareti | **yok** (banner/nav/contentinfo vardı) | var |
| açılışta canlı bölge (`aria-live`) | **yok** — bildirimler sessizdi | var |
| arama kutusunun etiketi | **yok** (yalnız yer tutucu) | `aria-label` |
| adı olan pencere | **0 / 6** | 6 / 6 |
| zorlanmış renkte ızgara blokları | 11 tondan **1 renge** düşüyor | rol YAZIYLA |
| zorlanmış renkte doluluk/ilerleme çubuğu | dolu ile kanal **aynı renk** (görünmez) | sistem renkleriyle |
| zorlanmış renkte seçili sekme/kip | "seçili" **görünmüyor** | kalın çerçeve |
| uç hatası ekran okuyucuya | **hiç** (yalnız düğme etiketi) | canlı bölgeye düşüyor |
| dokunmatikte ulaşılmaz `title` | **82** öğe (24'ü gerçek açıklama) | dokunulabilir |

⚠️ Bu turda kendi ÖLÇÜM ARACIM da yanlış çıktı: `getBoundingClientRect()`
kapalı bir `<details>` içindeki öğe için sıfırdan büyük kutu veriyor, yani
"görünür" sayıyordum. Doğrusu `checkVisibility()`. Faz 48/50'nin sonuçları
bundan etkilenmedi (fazla sayıyordu, eksik değil) ama sondalar düzeltildi.
"""
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import ui as UI                                    # noqa: E402

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")
CSS = re.search(r"<style>(.*?)</style>", KAYNAK, re.S).group(1)


def _blok(basla: str) -> str:
    """Süslü parantez sayarak bir medya bloğunun gövdesi."""
    m = re.search(re.escape(basla) + r"\{", CSS)
    assert m, f"{basla} bloğu yok"
    i, derinlik = m.end(), 1
    while i < len(CSS) and derinlik:
        if CSS[i] == "{":
            derinlik += 1
        elif CSS[i] == "}":
            derinlik -= 1
        i += 1
    return CSS[m.end():i - 1]


def _kod(blok: str) -> str:
    """Yorumları söküp tek satıra indirir.

    ⚠️ Bu yardımcının yokluğu bu repoda ÜÇÜNCÜ kez hataya yol açtı (Faz 48,
    50 ve yine burada): yorum, neyin neden YAPILMADIĞINI anlatırken yasak
    dizgeyi de yazıyor, muhafız onu kodda sanıyor.
    """
    return re.sub(r"/\*.*?\*/", " ", blok, flags=re.S).replace("\n", " ")


ZORLANMIS = _kod(_blok("@media (forced-colors: active)"))


# ===================================================== 1. yer işareti ve adlar
def test_MAIN_yer_isareti_var():
    """★ Ölçüldü: sayfada `banner`, `navigation` ve `contentinfo` vardı ama
    `main` YOKTU — ekran okuyucu kullanıcısı asıl içeriğe atlayamıyordu."""
    assert '<main class="icerik" id="icerik">' in KAYNAK
    assert "</main><!-- /icerik -->" in KAYNAK


def test_ARAMA_kutusunun_ETIKETI_var():
    """⚠️ Yer tutucu etiket değildir: yazmaya başlayınca kayboluyor ve
    ekran okuyucu yalnız "arama" diyordu."""
    m = re.search(r'<input type="search" id="candQ"([^>]*)>', KAYNAK)
    assert m and 'aria-label="Aday derslerde ara"' in m.group(1), m and m.group(1)


def test_PENCERE_ADI_tek_yerden():
    """★★ Altı pencerenin hiçbirinde ad yoktu; ekran okuyucu yalnız
    "iletişim kutusu" diyordu. Ad, pencerenin KENDİ başlığından türetiliyor
    — elle yazılsaydı ekrandaki ile kulaktaki ayrışabilirdi.

    ⚠️ Üç ayrı pencere açıcı var (`openDialog`, `openSetup`, `openBasvuru`);
    testin tuttuğu şey ÜÇÜNÜN DE aynı yardımcıdan geçmesi — yenisi
    eklenirse burada görünür."""
    assert "function pencereAdiVer(" in KAYNAK
    for fn in ("openDialog", "openSetup", "openBasvuru"):
        govde = re.search(r"function " + fn + r"\(.*?\n\}", KAYNAK, re.S).group(0)
        kod = re.sub(r"/\*.*?\*/", " ", govde, flags=re.S)
        assert "pencereAdiVer(" in kod, f"{fn} pencereye ad vermiyor"
    # Kaynakta showModal çağıran BAŞKA bir yer kalmadı mı?
    kod = re.sub(r"/\*.*?\*/", " ", KAYNAK, flags=re.S)
    assert kod.count(".showModal()") == 3, "yeni bir pencere açıcı var"


def test_CANLI_BOLGE_acilista_kuruluyor():
    """★★ Canlı bölge ilk bildirimle birlikte, İÇİ DOLU olarak DOM'a
    giriyordu; ekran okuyucular önceden tanımadıkları bölgenin hazır
    metnini çoğunlukla okumuyor. Yani bütün kısa bildirimler sessizdi."""
    assert "function bildirimBolgesi(" in KAYNAK
    # ⚠️ Faz 53: `boot(onceki)` — ilk açılış ile durum değişikliği ayrıldı;
    # desen parametreye izin veriyor, kontrol aynı.
    boot = re.search(r"function boot\((?:\w+)?\)\{(.*?)\n\}", KAYNAK, re.S).group(1)
    assert "bildirimBolgesi()" in boot, "canlı bölge açılışta kurulmuyor"


# ===================================================== 2. hata bildirimi
def test_HATA_canli_bolgeye_de_dusuyor():
    """★★ Ölçüldü: uç 500 dönünce hata yalnız DÜĞMENİN ETİKETİ oluyordu.
    İki sorun: ekran okuyucuya hiçbir şey gitmiyor, ve düğmenin erişilebilir
    adı hatayla değişiyor ("hata: …" adlı düğme).

    ⚠️ Görsel biçim korundu (hata eylemin durduğu yerde görünmeli);
    eklenen tek şey canlı bölge ve `aria-label`da korunan asıl ad."""
    assert "function hataBildir(" in KAYNAK
    fn = re.search(r"function hataBildir\((.*?)\n\}", KAYNAK, re.S).group(1)
    assert "say2(" in fn and 'setAttribute("aria-label"' in fn
    # Eski kalıp ("hata: " + err.message doğrudan etikete) kalmamalı.
    kod = re.sub(r"/\*.*?\*/", " ", KAYNAK, flags=re.S)
    kalan = re.findall(r'textContent = "hata: " \+ \w+\.message', kod)
    assert not kalan, f"doğrudan etikete yazan {len(kalan)} yer kaldı"


# ===================================================== 3. zorlanmış renk
def test_ZORLANMIS_RENK_rolu_YAZIYLA_soyluyor():
    """★★ Ölçüldü: `forced-colors: active`'te ızgara blokları 11 ayrı
    tondan TEK renge düşüyor — rol (anadal/ÇAP/yandal) bilgisi tamamen
    kayboluyordu. Renk gidiyorsa yazı gelir."""
    duz = ZORLANMIS
    for rol, yazi in (("ANADAL", "anadal"), ("CAP", "ÇAP"),
                      ("YANDAL", "yandal"), ("PLAN_DISI", "plan dışı")):
        assert f'.blk[data-role="{rol}"]::after' in duz, rol
        assert f'content:" · {yazi}"' in duz, yazi
        assert f'.daylist .row[data-role="{rol}"]::after' in duz, rol


def test_ZORLANMIS_RENK_cubuklari_geri_getiriyor():
    """★★ Doluluk ve ilerleme çubuklarının DOLU kısmı ile kanalı aynı
    renge düşüyordu — çubuk tamamen görünmez oluyordu."""
    duz = ZORLANMIS
    # Faz 56: haftalık programın yük ölçeği (`.yuk`) da aynı sınıftan bir çubuk.
    assert ".capbar,.meter,.gaugebar .track,.yuk{border:1px solid CanvasText" in duz
    assert ".capbar>i,.meter i,.gaugebar .track i,.yuk>i{background:Highlight}" in duz


def test_ZORLANMIS_RENK_secili_durumu_CERCEVEYLE():
    """⚠️⚠️ `background:Highlight; color:HighlightText` DENENDİ ve ölçümle
    çürütüldü: Chromium zorlanmış kipte yazının arkasına `Canvas` renginde
    arka levha çiziyor, HighlightText de beyaz olunca sekme BEYAZ ÜSTÜNE
    BEYAZ, yani boş bir şerit çıkıyordu (ekran görüntüsüyle doğrulandı).
    Seçili durum kalın çerçeveyle söyleniyor."""
    duz = ZORLANMIS
    assert "outline:3px solid Highlight" in duz
    assert "color:HighlightText" not in duz, (
        "seçili durum yeniden HighlightText ile yazılmış — yazı beyaz "
        "üstüne beyaz düşer")


def test_DOKUNMATIKTE_aciklamaya_ulasiliyor():
    """★★ Ölçüldü (390px): görünür 102 `title`ın 82'si tıklanamayan bir
    öğedeydi; 24'ü gerçek açıklama ve üçü bu projenin dürüstlük notları
    (*"'önşartı yok' demek DEĞİL"*). Fareyle okunuyordu, parmakla asla."""
    assert ".chip[title],.cat[title],.veriyasi .stale[title]" in CSS
    assert "text-decoration:underline dotted" in CSS
    kod = re.sub(r"/\*.*?\*/", " ", KAYNAK, flags=re.S)
    m = re.search(r'closest\("\.chip\[title\][^"]*"\)', kod)
    assert m, "dokunma işleyicisi yok"
    # ⚠️ YAKALAMA evresi şart: rozetlerin çoğu tıklanabilir satırın içinde.
    blok = kod[kod.index(m.group(0)):][:420]
    assert "stopPropagation" in blok and "}, true);" in blok, blok[:200]


# ===================================================== 4. uçtan uca
_CANLI = r'''
import os, sys, tempfile, threading, time
from pathlib import Path
sys.path.insert(0, os.environ["ITUCAP_SRC"])
_T = Path(tempfile.mkdtemp()); (_T/"config").mkdir(); (_T/"data").mkdir()
(_T/"config"/"settings.toml").write_text(
    '[student]\nanadal_program="HTAE"\nsecond_kind="yok"\n', encoding="utf-8")
import itucap.config as config
config.ROOT = _T; config.DATA_DIR = _T/"data"
config.REF_DB = _T/"data"/"reference.sqlite3"; config.USER_DB = _T/"data"/"user.sqlite3"
from itucap import db
con = db.connect(config.REF_DB, "schema.sql")
con.execute("INSERT INTO program(code,name,level) VALUES ('HTAE','H','LS')")
con.execute("INSERT INTO plan(id,program_code,plan_type,title,source)"
            " VALUES (1,'HTAE','lisans','x','obs')")
for i, kod in enumerate(("AAA 101E", "BBB 102E"), 1):
    con.execute("INSERT INTO course(code,name,credits,ects) VALUES (?,?,3,4)",
                (kod, "Ders " + kod))
    con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,position,term_no)"
                " VALUES (1,'REQUIRED',?,?,1)", (kod, i))
    crn = str(700 + i)
    con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled)"
                " VALUES (?,?,40,10)", (crn, kod))
    con.execute("INSERT INTO lesson_allowed_program(crn,program_code)"
                " VALUES (?,'HTAE')", (crn,))
    con.execute("INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min)"
                " VALUES (?,?,?,?)", (crn, i, 540, 650))
con.commit(); con.close(); db.connect(config.USER_DB, "schema_user.sql").close()

from itucap import server
st = server.State(label="ben")
h = server.build(st, host="127.0.0.1", port=0); P = h.server_address[1]
threading.Thread(target=h.serve_forever, daemon=True).start(); time.sleep(0.4)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width":1440,"height":950})
    hata = []
    pg.on("pageerror", lambda e: hata.append(str(e)[:150]))
    pg.goto(f"http://127.0.0.1:{P}/", wait_until="networkidle", timeout=30000)
    pg.wait_for_timeout(1500)
    print("MAIN:" + str(pg.evaluate("() => document.querySelectorAll('main').length")))
    print("CANLI:" + str(pg.evaluate(
        "() => [...document.querySelectorAll('[aria-live]')].map(e => e.id).join(',')")))
    print("ARAMA:" + str(pg.evaluate(
        "() => (document.querySelector('#candQ')||{}).getAttribute"
        " ? document.querySelector('#candQ').getAttribute('aria-label') : 'yok'")))
    # --- pencere adları
    adsiz = []
    for js in ("() => tercihDialog()", "() => programDialog()", "() => crnDialog()"):
        pg.evaluate("() => { const d=document.querySelector('dialog[open]'); if(d) d.close(); }")
        pg.wait_for_timeout(120)
        pg.evaluate(js); pg.wait_for_timeout(350)
        r = pg.evaluate("""() => { const d = document.querySelector("dialog[open]");
          if(!d) return "acilmadi";
          const id = d.getAttribute("aria-labelledby");
          const h = id && document.getElementById(id);
          return (h && (h.textContent||"").trim()) ? "" : "adsiz"; }""")
        if r: adsiz.append(r)
    pg.evaluate("() => { const d=document.querySelector('dialog[open]'); if(d) d.close(); }")
    print("PENCERE_ADSIZ:" + (",".join(adsiz) if adsiz else "-"))
    # --- hata canlı bölgeye düşüyor mu
    pg.route("**/api/picks", lambda r: r.fulfill(status=500,
             content_type="application/json", body='{"error":"deneme hatasi"}'))
    pg.evaluate("() => { const b = document.querySelector('#savePicks'); if(b) b.click(); }")
    pg.wait_for_timeout(2500)
    print("HATA_BILDIRIM:" + str(pg.evaluate("""() => { const e =
      document.querySelector("#bildirim");
      return e && e.classList.contains("acik") && /deneme/.test(e.textContent); }""")))
    print("HATA_ADI:" + str(pg.evaluate("""() => { const b =
      document.querySelector("#savePicks");
      return !!(b && (b.getAttribute("aria-label")||"").indexOf("Programı kaydet") === 0); }""")))
    pg.unroute("**/api/picks")
    # --- dokunmatikte açıklama (mekanizma testi: rozeti biz koyuyoruz)
    print("DOKUN:" + str(pg.evaluate("""() => {
      const tr = document.querySelector("#cands tbody tr[data-course]");
      if(!tr) return "satir yok";
      const s = document.createElement("span");
      s.className = "chip"; s.title = "deneme aciklamasi"; s.textContent = "x";
      tr.querySelector("td:nth-child(2)").appendChild(s);
      s.click();
      const bil = document.querySelector("#bildirim");
      return (bil && /deneme aciklamasi/.test(bil.textContent) ? "toast" : "yok")
        + (document.querySelector("dialog[open]") ? "+pencere" : ""); }""")))
    # --- zorlanmış renk kipi
    pg.evaluate("() => gorunumAc('schedSection')"); pg.wait_for_timeout(400)
    pg.emulate_media(forced_colors="active"); pg.wait_for_timeout(600)
    z = pg.evaluate("""() => {
      const blk = document.querySelector("#grid .blk[data-role]");
      const sonra = blk ? getComputedStyle(blk, "::after").content : "";
      const bar = document.querySelector(".capbar>i, .meter i, .gaugebar .track i");
      const kanal = bar && bar.parentElement;
      const sek = document.querySelector('.tab[aria-selected="true"]')
               || document.querySelector('.ray a[aria-current="page"]');
      const c = sek && getComputedStyle(sek);
      return {rolYazisi: sonra,
              cubukFarki: bar && kanal
                ? getComputedStyle(bar).backgroundColor !==
                  getComputedStyle(kanal).backgroundColor : null,
              seciliCerceve: c ? parseFloat(c.outlineWidth) : 0,
              seciliYazi: c ? c.color : null,
              seciliZemin: c ? c.backgroundColor : null}; }""")
    print("Z_ROL:" + str(z["rolYazisi"]))
    print("Z_CUBUK:" + str(z["cubukFarki"]))
    print("Z_CERCEVE:" + str(z["seciliCerceve"]))
    print("Z_OKUNUR:" + str(z["seciliYazi"] != z["seciliZemin"]))
    pg.emulate_media(forced_colors="none")
    print("HATA:" + ("|".join(hata[:3]) if hata else "-"))
    b.close()
h.shutdown()
'''


def test_UCTAN_UCA_erisim(tmp_path, monkeypatch):
    """★★ Tarayıcıda: yer işareti, canlı bölge, pencere adları, hata
    bildirimi, dokunmatik açıklama ve zorlanmış renk kipi."""
    if not shutil.which("node"):
        pytest.skip("node yok")
    try:
        import playwright  # noqa: F401
    except ImportError:
        pytest.skip("playwright yok")
    monkeypatch.setenv("ITUCAP_SRC", str(Path(UI.__file__).resolve().parents[1]))
    betik = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                        dir=str(tmp_path))
    betik.write(_CANLI); betik.close()
    r = subprocess.run([sys.executable, betik.name], capture_output=True,
                       text=True, timeout=300)
    if r.returncode != 0:
        pytest.fail(r.stderr[-1500:])
    c = dict(s.split(":", 1) for s in r.stdout.strip().splitlines()
             if ":" in s and s.split(":", 1)[0].isupper())
    assert c["MAIN"] == "1", f"main yer işareti yok: {c}"
    assert "bildirim" in c["CANLI"], f"açılışta canlı bölge yok: {c}"
    assert c["ARAMA"] == "Aday derslerde ara", f"arama kutusu etiketsiz: {c}"
    assert c["PENCERE_ADSIZ"] == "-", f"adsız pencere: {c}"
    assert c["HATA_BILDIRIM"] == "True", f"hata canlı bölgeye düşmüyor: {c}"
    assert c["HATA_ADI"] == "True", f"düğmenin erişilebilir adı kayboldu: {c}"
    assert c["DOKUN"] == "toast", \
        f"rozete dokununca açıklama çıkmıyor (ya da satır penceresi açılıyor): {c}"
    assert "anadal" in c["Z_ROL"] or "ÇAP" in c["Z_ROL"] or "yandal" in c["Z_ROL"], \
        f"zorlanmış renkte rol yazılmıyor: {c}"
    assert c["Z_CUBUK"] == "True", f"zorlanmış renkte çubuk görünmüyor: {c}"
    assert float(c["Z_CERCEVE"]) >= 2, f"seçili durum çerçevesiz: {c}"
    assert c["Z_OKUNUR"] == "True", f"seçili durumda yazı zeminle aynı renk: {c}"
    assert c["HATA"] == "-", f"JS hatası: {c['HATA']}"
