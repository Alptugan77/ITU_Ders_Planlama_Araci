"""Faz 48 — tarama: *"eklenebilecek başka düzeltmeler var mı"* (18.09.2026).

Fikir üretilmedi; **on bir görünüm ve dokuz pencere** iki genişlikte tek tek
gezildi (`tarama48.py`, `pencere48.py`, `kagit48.py`, `klavye48.py`).
Bulunan yedi kusurun hepsi Faz 46/47'nin kabuğunun **eski bağlamlara
sızmasıydı**:

| bulgu | ölçüm (önce) | sonra |
|---|---|---|
| "kaldır" hedefi | 46×**22**px | 46×**24**px |
| pencerelerde `<summary>` | 9 pencerenin 6'sında **19–21**px | **24**px |
| ölü `scrollIntoView` | 2 yer daha (sınıfın 3. görülüşü) | `gorunumAc` |
| kâğıtta ızgara | **660**px (ray + bağlam sütunu sızıyordu) | **1512**px |
| gece şemasında kâğıt | saat sütunu beyazda ~**2,6:1** | gündüz paleti |
| program görünümü dışında Cmd+P | **166 karakter**, boş kâğıt | 2172 |
| kâğıda ne çıktığı | **açık görünüme göre değişiyordu** | hep aynı |

Ölçülüp **temiz çıkanlar** (değişiklik yok, kayıt için): odak halkası 24
durakta eksiksiz · 119 Tab durağının **0'ı** kapalı görünümde · pencereler
`:modal` ve Esc'te odak çağırana dönüyor · 320px'te yatay taşma yok ·
%200 yazıda taşma yok · kayan tek kutu kaydırma işaretini taşıyor ·
kesilen ders adı yok.
"""
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import ui as UI

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")
CSS = re.search(r"<style>(.*?)</style>", KAYNAK, re.S).group(1)
YAZDIRMA = re.search(r"@media print\{(.*?)\n\}", CSS, re.S).group(1)


def _kod(blok: str) -> str:
    """Yorumları söküp tek satıra indirir.

    ⚠️ Yorum bloğu neyin NEDEN değiştiğini anlatıyor ve içinde seçici adları
    geçiyor; yorumlu metinde arama yapan bir muhafız, KODDAN silinen bir
    seçiciyi kendi yorumunda bulup yeşil kalıyor. Bu dosyada iki muhafız
    tam bu yüzden kırmızıya dönmedi (muhafız denemesi, 18.09.2026).
    """
    return re.sub(r"/\*.*?\*/", " ", blok, flags=re.S).replace("\n", " ")


def _jetonlar(blok: str) -> dict:
    return {k: v.strip() for k, v in
            re.findall(r"(--[a-z0-9-]+):\s*([^;}]+)", blok)}


_PALET = {
    "medya": _jetonlar(re.search(
        r"@media \(prefers-color-scheme:light\)\{(.*?)\n  \}", CSS, re.S).group(1)),
    "acik": _jetonlar(re.search(
        r':root\[data-theme="light"\]\{(.*?)\n\}', CSS, re.S).group(1)),
    "kagit": _jetonlar(re.search(
        r"\n  :root\{(.*?)\}", YAZDIRMA, re.S).group(1)),
}


def _kural(ad: str) -> str:
    """Satır başına çapalı kural gövdesi.

    ⚠️ `split("<seçici>{")` KIRILGAN: nitelenmiş bir kural (`.trtable .rm{…}`)
    eklenince ilk parça o oluyor ve test temel kuralı hiç görmüyor. Faz 47'de
    tam bu yüzden bir test yanlış kuralı okudu.
    """
    m = re.search(r"(?m)^" + re.escape(ad) + r"\{([^}]*)\}", CSS)
    assert m, f"temel {ad} kuralı yok"
    return m.group(1).replace("\n", "").replace(" ", "")


# ============================================ 1. dokunma hedefi tabanı (2.5.8)
def test_KATLANAN_BASLIK_da_bir_hedef():
    """★ Ölçüm: dokuz pencerenin altısında `<summary>` 19–21px yüksekliğinde,
    yani WCAG 2.2 AA 2.5.8'in 24px tabanının altındaydı — puan kırılımı,
    "Gelişmiş", yedek listeleri. İpucu/arz başlıkları zaten 24'tü."""
    taban = _kural("summary")
    assert "min-height:24px" in taban, taban


def test_taban_summary_ESNEK_KUTU_DEGIL():
    """⚠️⚠️ Tabanı `display:flex` ile kurmak KOLAY ama iki şeyi bozuyor ve
    ikisi de bu depoda ölçülmüş hatalar:

    1. Esnek kutu, iki metin düğümü arasındaki boşluğu yutuyor —
       "11 dersbu dönem" (arz başlığındaki nota bak). Pencere başlıkları
       `Puan <b>132.5</b> — neden?` gibi karışık içerikli.
    2. `list-item` kutusu kalkınca yerleşik açılma üçgeni siliniyor; o
       başlıkların TEK açılma işareti o (ipucu/arz kendi ▸'sını çiziyor,
       diğerleri çizmiyor).

    Dikey dolgu ikisine de dokunmadan tabanı sağlıyor."""
    taban = _kural("summary")
    assert "display:flex" not in taban, (
        "taban summary kuralı esnek kutuya çevrilmiş: başlıktaki boşluk "
        "yutulur ve yerleşik açılma üçgeni kaybolur")
    # İpucu ve arz başlıkları KENDİ işaretini çiziyor, onlar esnek kalabilir.
    assert ".ipucu>summary::before" in CSS and ".arzdetay>summary::before" in CSS


def test_KALDIR_dugmesi_24px():
    """★ Tarama: öneri görünümündeki "kaldır" 46×**22**px'ti. Nitelenmiş
    kurallar (`.trtable .rm`) yalnız renk/yazı boyutu veriyor; taban kural
    hepsine zemin oluyor."""
    assert "min-height:24px" in _kural(".rm")


# ====================================== 2. ölü kaydırma — SINIF olarak kapalı
def test_SCROLLINTOVIEW_sinifi_KAPALI():
    """★★★ Aynı hatanın ÜÇÜNCÜ görülüşü: Faz 46 (bölüm bağlantıları),
    Faz 47 (kaydedilen programı yükle), Faz 48 (["Haftalık programa bak"] ve
    CRN'den yükleme). Görünüm kipinde kapalı bir bölüme kaydırmak **hiçbir
    şey yapmaz** — düğme tıklanıyor, kullanıcı hiçbir şey görmüyor.

    Bu yüzden tek tek düğmeleri değil SINIFI tutuyoruz: kaynakta kalan tek
    `scrollIntoView`, açık görünümün İÇİNDEKİ bir satırı hizalayan
    `candOdakla`. Yeni bir "bir yere götür" çağrısı bu testi kırar."""
    kod = re.sub(r"/\*.*?\*/", " ", KAYNAK, flags=re.S)       # yorumlar hariç
    yerler = [m.start() for m in re.finditer(r"scrollIntoView", kod)]
    assert len(yerler) == 1, f"beklenmeyen scrollIntoView sayısı: {len(yerler)}"
    govde = re.search(r"function candOdakla\(i\)\{(.*?)\n\}", kod, re.S).group(1)
    assert "scrollIntoView" in govde, "tek kalan çağrı candOdakla'da değil"


def test_SONRAKI_dugmeleri_GORUNUM_aciyor():
    """"Programın hazır. Şimdi:" panelindeki düğmeler."""
    govde = re.search(r'el\.querySelectorAll\("\[data-go\]"\)(.*?)\}\)\);',
                      KAYNAK, re.S).group(1)
    kod = re.sub(r"/\*.*?\*/", " ", govde, flags=re.S)
    assert "gorunumAc(b.dataset.go, true)" in kod
    assert "scrollIntoView" not in kod


def test_CRN_ile_yuklemede_GORUNUM_aciliyor():
    """Kayıt günü penceresinden CRN yapıştırıp yükleyince program açılsın."""
    govde = re.search(r"function loadFromCrn\((.*?)\n\}", KAYNAK, re.S).group(1)
    kod = re.sub(r"/\*.*?\*/", " ", govde, flags=re.S)
    assert 'gorunumAc("schedSection", true)' in kod
    assert "scrollIntoView" not in kod


# ============================================================ 3. kâğıt
def test_KAGIT_HEP_gunduz_paleti():
    """★★ Ölçüldü: gece şemasındayken yazdırınca saat sütunu (08:00, 09:00…)
    beyaz kâğıda rgb(132,142,161), özet satırı rgb(154,165,184) çıkıyordu —
    ~2,6:1, okunmuyor.

    ⚠️ Kâğıt paleti UYDURULMUYOR: açık şemanın jetonlarının BİREBİR aynısı.
    Test ikisini karşılaştırıyor, sabit değer yazmıyor — açık şema
    değişirse kâğıt da değişmeli."""
    acik, kagit = _PALET["acik"], _PALET["kagit"]
    assert kagit, "yazdırma bloğunda palet yok"
    # `--shadow` bilerek farklı: kâğıtta gölge yok.
    fark = {k: (acik.get(k), v) for k, v in kagit.items()
            if k != "--shadow" and acik.get(k) != v}
    assert not fark, f"kâğıt paleti açık şemadan sapmış: {fark}"
    eksik = set(acik) - set(kagit) - {"--shadow"}
    assert not eksik, f"kâğıtta gece değerinde kalan jeton: {eksik}"
    assert kagit["--shadow"] == "none"
    # Boş hücrenin "+" daveti kâğıtta anlamsız.
    assert '#grid td.free::after{content:"" !important}' in _kod(YAZDIRMA)


def test_UC_ACIK_PALET_ayni():
    """⚠️ Açık palet artık ÜÇ yerde yazıyor: işletim sistemi açık şemadayken
    (`prefers-color-scheme`), açık şema AÇIKÇA seçilince, ve kâğıtta. Elle
    tutulan üç kopya kayıyor — Faz 38b'de ortadaki blokta `--yandal*`
    unutulmuştu, bu taramada da `prefers-color-scheme` bloğunda aynı satır
    İKİ KEZ duruyordu (biri yanlış girintide). Üçünü karşılaştırıyoruz."""
    medya, acik, kagit = _PALET["medya"], _PALET["acik"], _PALET["kagit"]
    assert medya == acik, {k: (acik.get(k), v) for k, v in medya.items()
                           if acik.get(k) != v} or \
        f"jeton sayısı farklı: {len(medya)} / {len(acik)}"
    assert set(kagit) == set(acik)          # değerler bir üstteki testte
    for ad, d in (("medya", medya), ("acik", acik), ("kagit", kagit)):
        assert len(d) >= 25, f"{ad} paletinde jeton eksilmiş: {len(d)}"


def test_KABUK_kagida_sizmiyor():
    """★★ Ölçüldü: A4'te ızgara **660px**, sayfanın yarısı boştu. `.govde`
    iki sütunlu ızgara — ray `display:none` olsa bile 216px'lik SÜTUN
    duruyordu; `.prgduzen` de 240px'lik bağlam sütununu ayırıyordu."""
    duz = _kod(YAZDIRMA)
    assert ".govde,.prgduzen{display:block !important}" in duz
    assert ".icerik{display:block}" in duz
    for parca in (".ipucu", "#kilitNot", "#donemUyari", ".gridaralik"):
        assert parca in duz, parca


def test_HANGI_GORUNUMDE_OLURSA_OLSUN_program_basiliyor():
    """★★ Ölçüldü: "Alabileceğim dersler"deyken Cmd+P → **166 karakter**,
    179px — boş kâğıt. İki kural çarpışıyordu: görünüm kipi açık olmayan
    bölüme `[data-disgorunum]{display:none !important}` koyuyor, yazdırma
    bloğu da öbür bölümleri gizliyor; geriye hiçbir şey kalmıyordu."""
    assert "#schedSection[data-disgorunum]{display:block !important}" in _kod(YAZDIRMA)
    # Kimlik seçicisi şart: `!important`i ancak daha yüksek özgüllük yener.
    assert "[data-disgorunum]{display:none !important}" in CSS


def test_KAGIT_HEP_AYNI_kagit():
    """⚠️ Görünüm kipinden önce bütün bölümler birden açıktı; şimdi hangi
    görünümdeysen o kâğıda sızıyordu (ilerleme paneli, kaydedilen program).
    Aynı Cmd+P aynı kâğıdı vermeli: program + CRN listesi."""
    duz = _kod(YAZDIRMA)
    assert "#panels" in duz and "#savedSection" in duz
    assert "#printCrn{display:block !important}" in duz
    # Kâğıdın genişliği okuma ölçüsüne değil SAYFAYA bağlı.
    assert ".wrap{max-width:none !important" in duz


# ========================================================= 4. uçtan uca
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
for i, (kod, bas) in enumerate([("AAA 101E", 540), ("BBB 102E", 600)], 1):
    con.execute("INSERT INTO course(code,name,credits,ects) VALUES (?,?,3,4)",
                (kod, "Uzun Adli Ders " + kod))
    con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,position,term_no)"
                " VALUES (1,'REQUIRED',?,?,1)", (kod, i))
    con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled)"
                " VALUES (?,?,40,0)", (str(700+i), kod))
    con.execute("INSERT INTO lesson_allowed_program(crn,program_code)"
                " VALUES (?,'HTAE')", (str(700+i),))
    con.execute("INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min)"
                " VALUES (?,?,?,?)", (str(700+i), i, bas, bas+110))
con.commit(); con.close(); db.connect(config.USER_DB, "schema_user.sql").close()

from itucap import server
st = server.State(label="ben")
h = server.build(st, host="127.0.0.1", port=0); P = h.server_address[1]
threading.Thread(target=h.serve_forever, daemon=True).start(); time.sleep(0.4)

KAGIT = """() => { const g = document.querySelector("#grid");
  const gor = e => e && getComputedStyle(e).display !== "none" &&
                    e.getBoundingClientRect().height > 2;
  return {izgara: gor(g),
          gen: g ? Math.round(g.getBoundingClientRect().width) : 0,
          metin: (document.body.innerText||"").replace(/\s+/g," ").trim().length,
          saatYazi: (() => { const e = document.querySelector("#grid tbody th");
            return e ? getComputedStyle(e).color : null; })()}; }"""

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width":1440,"height":950})
    pg.goto(f"http://127.0.0.1:{P}/", wait_until="networkidle", timeout=30000)
    pg.wait_for_timeout(1500)
    # --- kâğıt: hangi görünümden yazdırırsan yazdır aynı çıktı
    olcum = {}
    for g in ("schedSection", "candSection", "tierSection"):
        pg.evaluate("(x) => gorunumAc(x)", g); pg.wait_for_timeout(250)
        pg.emulate_media(media="print"); pg.wait_for_timeout(250)
        olcum[g] = pg.evaluate(KAGIT)
        pg.emulate_media(media="screen"); pg.wait_for_timeout(120)
    print("KAGIT_GEN:" + ",".join(str(olcum[g]["gen"]) for g in olcum))
    print("KAGIT_METIN:" + ",".join(str(olcum[g]["metin"]) for g in olcum))
    # --- kâğıt paleti gece şemasında da gündüz
    renk = {}
    for tema in ("dark", "light"):
        pg.evaluate("(t) => document.documentElement.setAttribute('data-theme', t)", tema)
        pg.evaluate("() => gorunumAc('schedSection')"); pg.wait_for_timeout(200)
        pg.emulate_media(media="print"); pg.wait_for_timeout(250)
        renk[tema] = pg.evaluate(KAGIT)["saatYazi"]
        pg.emulate_media(media="screen"); pg.wait_for_timeout(100)
    print("KAGIT_RENK:" + str(renk["dark"] == renk["light"]) + "|" + str(renk["dark"]))
    # --- pencerelerde 24px altı hedef kaldı mı
    pg.evaluate("() => document.documentElement.setAttribute('data-theme','dark')")
    kucuk = []
    for js in ("() => tercihDialog()", "() => programDialog()", "() => crnDialog()"):
        pg.evaluate(js); pg.wait_for_timeout(400)
        kucuk += pg.evaluate("""() => { const d = document.querySelector("dialog[open]");
          if(!d) return ["ACILMADI"];
          return [...d.querySelectorAll("button, a[href], input, select, summary")]
            .filter(e => { const r = e.getBoundingClientRect();
              return r.width > 0 && r.height > 0 && r.height < 24 &&
                !(/checkbox|radio/.test(e.type||"") && e.closest("label") &&
                  e.closest("label").getBoundingClientRect().height >= 24); })
            .map(e => e.tagName + Math.round(e.getBoundingClientRect().height)); }""")
        pg.evaluate("() => { const d=document.querySelector('dialog[open]'); if(d) d.close(); }")
        pg.wait_for_timeout(150)
    print("KUCUK:" + (",".join(kucuk) if kucuk else "-"))
    b.close()
h.shutdown()
'''


def test_UCTAN_UCA_faz48(tmp_path, monkeypatch):
    """★★ Tarayıcıda ölçüyor: kâğıt her görünümden aynı, gece şemasında da
    gündüz renkleri, pencerelerde 24px altı hedef yok."""
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
                       text=True, timeout=240)
    if r.returncode != 0:
        pytest.fail(r.stderr[-1500:])
    c = dict(s.split(":", 1) for s in r.stdout.strip().splitlines()
             if ":" in s and s.split(":", 1)[0].isupper())
    genislikler = [int(x) for x in c["KAGIT_GEN"].split(",")]
    assert len(set(genislikler)) == 1, f"kâğıt görünüme göre değişiyor: {c}"
    assert genislikler[0] > 1000, f"ızgara kâğıtta hâlâ dar: {c}"
    metinler = [int(x) for x in c["KAGIT_METIN"].split(",")]
    assert len(set(metinler)) == 1 and metinler[0] > 200, \
        f"program görünümü dışında kâğıt boş: {c}"
    assert c["KAGIT_RENK"].startswith("True"), \
        f"gece şeması kâğıda sızıyor: {c['KAGIT_RENK']}"
    assert c["KUCUK"] == "-", f"pencerede 24px altı hedef: {c['KUCUK']}"
