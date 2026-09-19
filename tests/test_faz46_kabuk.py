"""Faz 46 — kabuk: program merkezde, gezinme görünüm değiştiriyor.

Kullanıcı 18.09.2026: *"bütün düzeltmeleri ve yeni tasarımı uygular mısın"*.
Uygulanan liste `docs/faz46-arayuz-olcumu.md`de ölçülmüştü.

Ölçüm — aynı betik, önce ve sonra (1440×900 ve 390×844, gerçek veri):

| | önce | sonra |
|---|---|---|
| sayfa yüksekliği · masaüstü | 6570px (7,3 ekran) | **1253px (1,4)** |
| sayfa yüksekliği · telefon | 13834px (16,4 ekran) | **2624px (3,1)** |
| haftalık programın tepesi · masaüstü | 1825px | **444px** |
| gün listesinin tepesi · telefon | 3354px | **728px** |
| 24px altı dokunma hedefi | 72 | **0** |
| sayfadaki toplam kelime | 1826 | **345** |
| bir ayar değişimi (yazma ucu) | 5,7 sn | **1,1 sn** |

⚠️ Bu dosya YENİ davranışı tutuyor. Eski davranışı tutan testler kaldırılmadı,
**yeniden yazıldı** ve her birinin başında neyin neden değiştiği duruyor:
`test_faz20_arayuz.test_ILK_GORUNUM_haftalik_program`,
`test_kullanim_kolayligi.test_ray_GORUNUM_degistiriyor_KAYDIRMIYOR`,
`test_ux_mobil.test_TELEFONDA_hicbir_gorunum_ULASILAMAZ_DEGIL`,
`test_faz39_tasarim.test_TELEFONDA_kucuk_denetim_KALMADI`.
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


from itucap import prereq as P                                # noqa: E402
from itucap import recommend as REC                           # noqa: E402
from itucap import ui as UI                                   # noqa: E402

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")
CSS = re.search(r"<style>(.*?)</style>", KAYNAK, re.S).group(1)


# ------------------------------------------------------------- iskelet
def test_KABUK_ray_ve_icerik_ayri():
    """★★ Üç sütunlu kabuk: ray + içerik. Bölümler `.icerik` içinde.

    ⚠️ Faz 51: içerik kabı `<div>` iken `<main>` oldu — sayfada `main` yer
    işareti YOKTU (ölçüldü) ve ekran okuyucu kullanıcısı asıl içeriğe
    atlayamıyordu. Test etikete değil, YER İŞARETİ + sınıf ikilisine
    bakıyor: `.icerik` bütün CSS'in dayanağı, `<main>` da erişilebilirlik
    sözü."""
    assert '<div class="govde">' in KAYNAK
    assert '<nav class="ray" id="secnav"' in KAYNAK
    assert '<main class="icerik" id="icerik">' in KAYNAK
    kural = re.search(r"(?m)^\.govde\{([^}]*)\}", CSS).group(1)
    assert "grid-template-columns:216px" in kural.replace(" ", "")


def test_PROGRAM_ORTADA_baglam_sagda():
    """★★ Ölçüm: ızgaranın ÜSTÜNDE 8 blokta 313 kelime vardı. Özet, arz
    uyarısı, kilit şeridi ve araç çubuğu sağ sütuna taşındı."""
    assert '<div class="prgduzen">' in KAYNAK
    assert '<aside class="prgyan">' in KAYNAK
    # Sağ sütunun içindekiler GERÇEKTEN orada:
    yan = re.search(r'<aside class="prgyan">(.*?)</aside>', KAYNAK, re.S).group(1)
    for parca in ('id="schedSummary"', 'id="arzUyari"', 'id="kilitNot"',
                  'id="donemUyari"', 'class="toolbar"'):
        assert parca in yan, parca
    # ⚠️ Dar ekranda ALTA düşüyor, üstüne değil — yoksa telefonda aynı sorun.
    dar = re.search(r"@media \(max-width:1100px\)\{(.*?)\n\}", CSS, re.S).group(1)
    assert ".prgyan{order:2}" in dar.replace(" ", "")
    assert ".prgorta{order:1}" in dar.replace(" ", "")


def test_gezinme_CAPA_DEGIL_gorunum_degistirici():
    """★★ Faz 46'nın çekirdeği. Eski `markCurrentSection` (kaydırma anında
    hangi bölümdeyiz) gitti; `gorunumAc` geldi."""
    assert "function gorunumAc(" in KAYNAK
    assert "function acikGorunumler(" in KAYNAK
    assert "markCurrentSection" not in KAYNAK
    assert "scrollIntoView" not in re.search(
        r"function renderSecNav\(\)\{(.*?)\n\}\n", KAYNAK, re.S).group(1)
    # Etkin olmayan görünüm KAPALI ama `hidden` DEĞİL — iki anlam ayrı.
    assert "[data-disgorunum]{display:none !important}" in CSS
    assert 'el.setAttribute("data-disgorunum", "")' in KAYNAK


def test_hidden_ile_gorunum_AYRI_KALIYOR():
    """⚠️ "veri yok" (`hidden`) ile "şu an bakmıyorsun" (`data-disgorunum`)
    tek bayrağa bindirilirse, veri gelince bölüm açılmaz ya da boş bölüm
    rayda görünür."""
    fn = re.search(r"function acikGorunumler\(\)\{(.*?)\n\}", KAYNAK, re.S).group(1)
    assert "!el.hidden" in fn
    assert "offsetParent" not in fn, "kapalı görünüm 'yok' sayılıyor"


def test_SAYFA_ICI_baglantilar_da_gorunum_aciyor():
    """⚠️ "Darboğaz bölümünde ayrıntı" gibi bağlantılar kaydırıyordu;
    görünüm kipinde kaydırmak hiçbir şey yapmaz. Çalışmaz bağlantı
    bırakmak Faz 25/44'te ölçtüğümüz hatanın aynısı olurdu."""
    assert 'a[href^="#"]:not([data-gorunum])' in KAYNAK
    assert "SECTIONS.some(([x]) => x === id)" in KAYNAK


def test_GIZLI_bolumun_OLCUSU_yeniden_aliniyor():
    """⚠️ Testte yakalandı: kademe diyagramının bağ çizgileri
    `getBoundingClientRect` ile kuruluyor; bölüm kapalıyken hepsi 0 çıkıyor
    ve görünüm açılınca çizgisiz diyagram kalıyordu."""
    fn = re.search(r"function gorunumAc\(id, odakla\)\{(.*?)\n\}", KAYNAK, re.S).group(1)
    assert "drawTierLinks" in fn


# ------------------------------------------------------------- hedefler
def test_IZGARA_SATIRI_28px():
    """★ Ölçüm: boş hücreler 235×19px'ti; WCAG 2.2 AA 2.5.8 tabanı 24×24.
    Faz 44'te düzelttiğimiz "boş saate tıkla" özelliğinin HEDEFİ tabanın
    altındaydı — 38 hücrede."""
    kural = re.search(r"(?m)^table\.grid td\{([^}]*)\}", CSS).group(1)
    m = re.search(r"height:(\d+)px", kural.replace(" ", ""))
    assert m and int(m.group(1)) >= 24, kural
    # Tıklanabilirliğin GÖRÜNÜR bir işareti var (eskiden yalnız hover vardı).
    assert 'table.grid td.free::after{content:"+"' in CSS.replace("\n", "")


def test_ONAY_KUTUSU_tabanin_ustunde():
    """★ 13×13px'ti (tarayıcı varsayılanı)."""
    kural = re.search(r'\.tickbox input\[type="checkbox"\]\{([^}]*)\}', CSS).group(1)
    g = kural.replace(" ", "").replace("\n", "")
    assert "width:18px" in g and "height:18px" in g


# ------------------------------------------------------------- katlama
def test_UYARI_KATLANDI_ama_SAYISI_gorunuyor():
    """★★ Ölçüm: arz kutusu 115px ve 47 kelimeydi, ızgaranın önünde.
    ⚠️ Bu depoda "genel uyarı" yasak: katlanmış hâlde bile SAYI yazıyor."""
    fn = re.search(r"function renderArzUyarisi\(\)\{(.*?)\n\}", KAYNAK, re.S).group(1)
    assert '<details class="arzdetay">' in fn
    assert "${arz.length} ders" in fn, "kapalıyken sayı yazmıyor"
    assert "<details class=\"arzdetay\" open" not in fn, "açık başlıyor"
    # İpuçları da katlandı ama SİLİNMEDİ (Faz 40'ın dersi).
    assert '<details class="ipucu">' in KAYNAK
    assert 'id="tonNot"' in KAYNAK


def test_TELEFONDA_yatay_kaydirma_IPUCU_var():
    """★ Aday tablosu 390px'te 418px; kaydırılabiliyordu ama işareti yoktu."""
    assert 'class="listwrap" id="candWrap"' in KAYNAK
    assert '.listwrap[data-more="right"]' in CSS
    assert "function listeKenarSolmasi()" in KAYNAK


def test_TAZELE_dugmesi_CUMLENIN_ICINDE_degil():
    """★ 390px'te satır düğmenin ortasından kırılıyordu."""
    assert '<span class="veriyazi">' in KAYNAK
    kural = re.search(r"(?m)^\.veriyasi\{([^}]*)\}", CSS).group(1)
    assert "display:flex" in kural.replace(" ", "")


# ------------------------------------------------------------- telefon
def _mobil_bloklar():
    r"""⚠️ `@media (max-width:700px)` bloğu stil sayfasında BİRDEN FAZLA.
    Basit bir `(.*?)\n\}` araması ilkini bulup orada kesiyor ve sonraki
    blokların kuralları "yok" sanılıyordu. Süslü parantez sayarak topluyoruz."""
    out = []
    bas = "@media (max-width:700px){"
    i = CSS.find(bas)
    while i >= 0:
        j = i + len(bas)
        derinlik = 1
        while j < len(CSS) and derinlik:
            if CSS[j] == "{":
                derinlik += 1
            elif CSS[j] == "}":
                derinlik -= 1
            j += 1
        out.append(CSS[i + len(bas):j - 1])
        i = CSS.find(bas, j)
    assert out, "mobil medya bloğu yok"
    return "\n".join(out)


def test_TELEFONDA_alt_sekme_cubugu():
    g = _mobil_bloklar().replace(" ", "")
    assert "position:fixed" in g and "bottom:0" in g
    assert "min-height:56px" in g, "sekme dokunma hedefi küçük"
    # ⚠️ Satır kırıcı olmadan alt sekmeler birincil satıra sızıyor.
    assert ".ray[data-acik].raykesme{display:block" in g
    assert "flex-wrap:wrap-reverse" in g, "açılan ızgara aşağı taşıyor"


# ------------------------------------------------------------- hız
def test_ONSART_AYRISTIRMA_onbellekli():
    """★★ Ölçüm: `snapshot()` 7,9 sn sürüyordu, 14,8'i (kümülatif) önşart
    ayrıştırmaydı — tek durum çıkarımında 55.560 ayrıştırma, hepsi aynı
    ~4.630 metin. Önbellekten sonra 0,95 sn."""
    assert hasattr(P.parse, "cache_info"), "parse önbelleksiz"
    P.parse.cache_clear()
    a = P.parse("BLG 102E MIN DD")
    b = P.parse("BLG 102E MIN DD")
    assert a is b, "aynı metin iki kez ayrıştırılıyor"
    assert P.parse.cache_info().hits >= 1


def test_SUBE_SIRASI_indeks_basina_bir_kez():
    """★★ `blocking_cost(s, index)` `chosen`a bakmıyor; arama ağacının her
    düğümünde yeniden hesaplanıyordu (46.549 çağrı)."""
    src = pathlib.Path(REC.__file__).read_text(encoding="utf-8")
    assert "_sira: dict[int, list[Section]] = {}" in src
    assert "ordered = _sira.get(index)" in src
    assert "_sira[index] = ordered" in src


def test_ONBELLEK_SONUCU_DEGISTIRMIYOR():
    """⚠️ Bir önbellek davranış değiştirmemeli. Aynı havuz, iki çağrı,
    birebir aynı program."""
    def sube(crn, kod, gun, bas, bit):
        return REC.Section(crn=crn, course=kod, instructor=None, capacity=40,
                           enrolled=0,
                           meetings=(REC.Meeting(gun, bas, bit, None, None, None),))

    def aday(kod, subeler):
        return REC.Candidate(course=kod, name=kod, role="ANADAL", ects=4.0,
                             credits=3.0, unlocks=0, tier=0, critical=False,
                             required=True, sections=subeler)

    havuz = [aday("AAA 101", [sube("1", "AAA 101", 1, 540, 660),
                              sube("2", "AAA 101", 2, 540, 660)]),
             aday("BBB 102", [sube("3", "BBB 102", 1, 540, 660)]),
             aday("CCC 103", [sube("4", "CCC 103", 2, 540, 660),
                              sube("5", "CCC 103", 3, 540, 660)])]
    imza = lambda r: [sorted((p.candidate.course, p.section.crn) for p in s.picks)
                      for s in r]
    bir = imza(REC.build_schedules(havuz, max_load=35, limit=3))
    iki = imza(REC.build_schedules(havuz, max_load=35, limit=3))
    assert bir == iki and bir


def test_URETILEN_JS_AYRISTIRILABILIYOR(tmp_path):
    """⚠️⚠️ BU TURDA GERÇEKTEN OLDU. Arayüzün tamamı Python'da bir JS
    ŞABLON DİZGESİ içinde duruyor. İçine ters tırnaklı bir HTML yorumu
    (``summary`` gibi) yazınca JS dizgeyi orada kapatıyor ve **sayfanın
    TAMAMI ölüyor** — `GORUNUM is not defined`. Tarayıcı testleri yakaladı
    ama 7 saniye sürdüler; bu kontrol 0,3 saniye sürüyor ve hata SINIFINI
    tutuyor, tek örneğini değil.
    """
    node = shutil.which("node")
    if not node:
        pytest.skip("node yok")
    from itucap import config, db
    from itucap import student as S
    con = db.connect(tmp_path / "ref.sqlite3", "schema.sql")
    con.execute("INSERT INTO program(code,name,level) VALUES ('X','X','LS')")
    con.commit()
    ucon = db.connect(tmp_path / "user.sqlite3", "schema_user.sql")
    sid = S.ensure_student(ucon)
    html = UI.render(UI.collect(con, ucon, sid, config.Settings(), None, None))
    betikler = re.findall(r"<script[^>]*>(.*?)</script>", html, re.S)
    assert betikler, "sayfada betik yok"
    js = max(betikler, key=len)
    yol = tmp_path / "sayfa.js"
    yol.write_text(js, encoding="utf-8")
    r = subprocess.run([node, "--check", str(yol)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]


# --------------------------------------------------------- uçtan uca
_CANLI = r'''
import sys, tempfile, threading, time, os
from pathlib import Path
sys.path.insert(0, os.environ["ITUCAP_SRC"])
_T = Path(tempfile.mkdtemp()); (_T/"config").mkdir(); (_T/"data").mkdir()
(_T/"config"/"settings.toml").write_text(
    '[student]\nanadal_program="HTAE"\nsecond_kind="yok"\ndonem=1\n', encoding="utf-8")
import itucap.config as config
config.ROOT = _T; config.DATA_DIR = _T/"data"
config.REF_DB = _T/"data"/"reference.sqlite3"; config.USER_DB = _T/"data"/"user.sqlite3"
from itucap import db
con = db.connect(config.REF_DB, "schema.sql")
con.execute("INSERT INTO program(code,name,level) VALUES ('HTAE','H','LS')")
con.execute("INSERT INTO plan(id,program_code,plan_type,title,source)"
            " VALUES (1,'HTAE','lisans','x','obs')")
for i, (kod, gun, bas, bit) in enumerate(
        [("AAA 101E", 1, 540, 660), ("BBB 102E", 2, 540, 660),
         ("CCC 103E", 3, 600, 720)]):
    con.execute("INSERT INTO course(code,name,credits,ects) VALUES (?,?,3,4)",
                (kod, "Ders " + kod))
    con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,position,term_no)"
                " VALUES (1,'REQUIRED',?,?,1)", (kod, i))
    crn = str(500 + i)
    con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled) VALUES (?,?,40,0)",
                (crn, kod))
    con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES (?,'HTAE')",
                (crn,))
    con.execute("INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min)"
                " VALUES (?,?,?,?)", (crn, gun, bas, bit))
con.commit(); con.close(); db.connect(config.USER_DB, "schema_user.sql").close()

from itucap import server
st = server.State(label="ben")
h = server.build(st, host="127.0.0.1", port=0); P = h.server_address[1]
threading.Thread(target=h.serve_forever, daemon=True).start(); time.sleep(0.4)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()

    # ---------------- masaüstü: tek görünüm, program ilk ekranda
    pg = b.new_page(viewport={"width":1440,"height":900})
    pg.goto(f"http://127.0.0.1:{P}/", wait_until="networkidle", timeout=30000)
    pg.wait_for_timeout(1500)
    print("ACILIS:" + pg.evaluate("() => GORUNUM"))
    # ⚠️ Karşılama kartı (`#hero`) yeni kullanıcıda ilk ekranı dolduruyor —
    # doğru davranış, Faz 24/26'nın kararı. Faz 46'nın ölçtüğü şey KABUĞUN
    # kendi payı, o yüzden kart kapatıldıktan sonra ölçülüyor.
    pg.evaluate("() => { const h = document.querySelector('#hero'); if (h) h.hidden = true; }")
    pg.wait_for_timeout(200)
    print("IZGARA_Y:" + str(pg.evaluate(
        "() => Math.round(document.querySelector('#grid').getBoundingClientRect().top + scrollY)")))
    print("KABUK_PAYI:" + str(pg.evaluate("""() => {
        const g = document.querySelector('#grid').getBoundingClientRect().top;
        const k = document.querySelector('.govde').getBoundingClientRect().top;
        return Math.round(g - k); }""")))
    print("USTTEKILER:" + pg.evaluate("""() => { const gy =
        document.querySelector('#grid').getBoundingClientRect().top + scrollY;
      return [...document.querySelectorAll('.wrap > *, #schedSection > *')]
        .filter(e => e.getBoundingClientRect().height > 0 &&
                     e.getBoundingClientRect().top + scrollY < gy)
        .map(e => (e.id || e.className || e.tagName) + "=" +
             Math.round(e.getBoundingClientRect().height)).join(","); }"""))
    print("ACIK_BOLUM:" + str(pg.evaluate("""() => [...document.querySelectorAll('section.card, #panels, #setupbar')]
        .filter(e => !e.hidden && e.offsetParent !== null).length""")))
    # Başka görünüme geç: sayfa KAYMAMALI, öbür bölüm KAPANMALI
    hedef = pg.evaluate("""() => { const a = [...document.querySelectorAll('#secnav a')]
        .find(x => x.dataset.gorunum !== GORUNUM); a.click(); return a.dataset.gorunum; }""")
    pg.wait_for_timeout(400)
    print("GECIS:" + str(pg.evaluate("() => GORUNUM") == hedef))
    print("TEK_ACIK:" + str(pg.evaluate("""() => [...document.querySelectorAll('section.card, #panels, #setupbar')]
        .filter(e => !e.hidden && e.offsetParent !== null).length""")))
    print("SAYFA:" + str(pg.evaluate("() => document.documentElement.scrollHeight")))
    # 24px altı hedef (satır içi bağlantı hariç)
    print("KUCUK:" + str(pg.evaluate("""() => {
      const sec = [...document.querySelectorAll(
        'button, a[href], input, select, summary, [role="button"], [tabindex="0"]')]
        .filter(e => { const b = e.getBoundingClientRect();
          return b.width > 0 && b.height > 0; });
      const b0 = (e) => e.getBoundingClientRect();
      /* WCAG 2.2 AA 2.5.8'in iki istisnası, ikisi de standardın kendi
         maddeleri:
         · "Inline" — cümle içindeki bağlantı, boyutu satır yüksekliğiyle
           sınırlı.
         · "Enclosed/Equivalent" — onay kutusunu saran <label> aynı işlevi
           yapıyor ve o tabanın üstünde. Kutuyu 24px yapmak, 12,5px yazının
           yanında görsel olarak yanlış olurdu. */
      const satirIci = (e) => e.tagName === "A" && e.parentElement &&
        (e.parentElement.textContent||"").trim().length >
        (e.textContent||"").trim().length + 8;
      const etiketli = (e) => {
        if (e.tagName !== "INPUT") return false;
        if (e.type !== "checkbox" && e.type !== "radio") return false;
        const l = e.closest("label");
        return !!l && b0(l).height >= 24 && b0(l).width >= 24;
      };
      return sec.filter(e => { const b = e.getBoundingClientRect();
        return !satirIci(e) && !etiketli(e) && (b.height < 24 || b.width < 24); })
        .map(e => (e.id || e.className || e.tagName) + " " +
             Math.round(b0(e).width) + "x" + Math.round(b0(e).height))
        .join(" | ") || "0"; }""")))
    pg.close()

    # ---------------- telefon: alt çubuk, program ilk ekranda
    pg = b.new_page(viewport={"width":390,"height":844}, is_mobile=True, has_touch=True)
    pg.goto(f"http://127.0.0.1:{P}/", wait_until="networkidle", timeout=30000)
    pg.wait_for_timeout(1500)
    print("TEL_CUBUK:" + pg.evaluate(
        "() => getComputedStyle(document.querySelector('#secnav')).position"))
    print("TEL_TASMA:" + str(pg.evaluate(
        "() => document.documentElement.scrollWidth - innerWidth")))
    pg.evaluate("() => { const h = document.querySelector('#hero'); if (h) h.hidden = true; }")
    pg.wait_for_timeout(200)
    print("TEL_GUNLISTE_Y:" + str(pg.evaluate(
        "() => Math.round(document.querySelector('#daylist').getBoundingClientRect().top + scrollY)")))
    b.close()
h.shutdown()
'''


def test_UCTAN_UCA_kabuk(tmp_path, monkeypatch):
    """★★ Tarayıcıda: tek görünüm açık, program ilk ekranda, geçiş
    kaydırmıyor, 24px altı hedef yok, telefonda alt çubuk."""
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
    assert c["ACILIS"] == "schedSection", f"açılış görünümü yanlış: {c}"
    tanim = c.get("USTTEKILER", "")
    assert int(c["IZGARA_Y"]) < 700, \
        f"ızgara ilk ekranda değil: {c['IZGARA_Y']}px · üstündekiler: {tanim}"
    # Kabuğun kendi payı: bölüm başlığı + kip/sekme satırı + kip notu.
    assert int(c["KABUK_PAYI"]) < 300, \
        f"kabuk ızgarayı {c['KABUK_PAYI']}px aşağı itiyor"
    assert c["ACIK_BOLUM"] == "1", f"aynı anda {c['ACIK_BOLUM']} bölüm açık"
    assert c["GECIS"] == "True"
    assert c["TEK_ACIK"] == "1", "geçişten sonra iki bölüm açık kaldı"
    assert c["KUCUK"] == "0", f"24px altında hedef: {c['KUCUK']}"
    assert c["TEL_CUBUK"] == "fixed", "telefonda alt çubuk yok"
    assert int(c["TEL_TASMA"]) <= 1, f"telefonda yatay taşma: {c['TEL_TASMA']}px"
    assert int(c["TEL_GUNLISTE_Y"]) < 1000, \
        f"telefonda program ilk ekranlarda değil: {c['TEL_GUNLISTE_Y']}px"
