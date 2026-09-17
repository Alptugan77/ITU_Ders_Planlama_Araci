"""Faz 43 — tasarım sistemi: tabanlar ve ölçekler.

Kullanıcı isteği (17.09.2026): *"can you update and improve the design
accordingly"* — kapsam soruldu; cevap **düzeltmeler + incelik**, uygulamaya
da işlensin, tasarım sistemi Türkçe olsun.

Faz 39'un dersi burada da geçerli: kalıcı olan düzeltme değil, TESTTİR. Bu
dosyadaki testlerin çoğu tek bir değeri değil bir TABANI ya da bir ÖLÇEĞİ
tutuyor; palet ya da kural değişince yeni değere göre ölçüyorlar:

  1. küçük yazı her temada, düştüğü her zeminde ≥ 4.5:1, denetim kenarı ≥ 3:1
  2. tonlu blokta yazının TEK rengi var — Faz 40'ın ölçtüğü renk
  3. bağlantının kuralı var
  4. yazı boyutu 9 basamak, harf aralığı 6 basamak, aralık 2px ızgarasında
  5. köşe yok, gölge yalnız yüzen katmanda, sabit renk paletin dışında yok
  6. açık palet iki blokta birebir aynı
  7. durumlar tek dilde (üzerine gelme, devre dışı, tamamlandı, kilitli)
  8. düz yazı esnek satırın içinde değil; telefonda sekmeler alt alta
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


from itucap import ui as UI                                   # noqa: E402

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")
HAM_CSS = re.search(r"<style>(.*?)</style>", KAYNAK, re.S).group(1)
CSS = re.sub(r"/\*.*?\*/", " ", HAM_CSS, flags=re.S)
SABLON = KAYNAK[KAYNAK.index("</style>"):]
KOK = pathlib.Path(UI.__file__).resolve().parents[2]
sys.path.insert(0, str(KOK / "tools"))

# --- ölçekler: tasarım sisteminin `tokens.json`'u ile AYNI basamaklar -------
YAZI_OLCEGI = {10.5, 11.5, 12.5, 13.5, 15, 22, 23, 27, 29}
HARF_ARALIGI = {"-.02em", "0", ".02em", ".06em", ".11em", ".16em"}
ARALIK_OLCEGI = {0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 22, 30}
# 1px: optik ayar (rozet içi) · 38: kademe satırları arası (bağ eğrisine yer)
# 60/80: sayfa sonu boşluğu (telefon/masaüstü)
ARALIK_ISTISNA = {1, 38, 60, 80}


def _kural(secici):
    for sel, govde in re.findall(r"([^{}]+)\{([^{}]*)\}", CSS):
        if sel.strip() == secici:
            return govde.replace(" ", "").replace("\n", "")
    raise AssertionError(f"kural yok: {secici}")


def _mobil_css():
    m = re.search(r"@media \(max-width:700px\)\{(.*?)\n\}", CSS, re.S)
    assert m, "mobil medya bloğu yok"
    return m.group(1)


def _baski_disi(css):
    """@media print bloğu ve yalnız kâğıtta görünen `#printCrn` kâğıt içindir:
    #fff/#000/#999 orada doğru."""
    css = re.sub(r"@media print\{.*?\n\}", " ", css, flags=re.S)
    return re.sub(r"#printCrn[^{]*\{[^}]*\}", " ", css)


def _satir_ici_stiller():
    return re.findall(r'style="([^"]*)"', SABLON)


def _yukleme_css():
    site = (KOK / "tools" / "site_kur.py").read_text(encoding="utf-8")
    return re.search(r'_LOADER_CSS = """(.*?)"""', site, re.S).group(1)


# ------------------------------------------------------------ 1. tabanlar
def test_KUCUK_YAZI_ve_DENETIM_KENARI_her_temada_TABANIN_USTUNDE():
    """★★ Ölçüm (Faz 43 öncesi): 90 çiftin 15'i taban altındaydı.

    `--ink-3` 88 yerde küçük yazı taşıyor (ipucu, sayaç, CRN, "tamamlandı",
    izle rozeti) ve düştüğü zeminlerde gece 3.32–4.03, gündüz 3.47–4.22:1'di.
    Gece şemasında düğme ve alan kenarı (`--border-strong`) 1.80–2.13:1'di:
    `.ghost` düğmesinin zemini şeffaf, kenarı onun TEK sınırı.

    Ölçüm `tools/kontrast_olcumu.py`'de ve paleti `ui.py`'den OKUYOR: palet
    değişirse bu test yeni palete göre ölçer.
    """
    import kontrast_olcumu as K

    satirlar = K.olc()
    assert len(satirlar) >= 90, "ölçülen çift sayısı düşmüş — liste budanmış olabilir"
    kotu = [f"{tema} {tur} {on} / {z}: {oran:.2f} < {taban}"
            for tema, tur, on, z, oran, taban in satirlar if oran < taban]
    assert not kotu, "taban altında:\n" + "\n".join(kotu)


def test_TONLU_BLOKTA_yazinin_TEK_rengi_var():
    """★★ Faz 40 merdiveni blok yazısını (`--accent-ink`) ölçmüştü: en kötü 4.67.

    Ama blokta üç satır var ve ikisi başka renkteydi — ölçülmüyordu:
      * ders adı (`.blkad`) accent-ink'in %85 opaklığı: 3.80–4.37:1
      * saat · yer · CRN (`small`) `--ink-2`: 3.09–3.91:1 — CRN kayıt günü
        elle yazılan sayı.
    Düzeltme renk seçmek değil, ölçülen rengi TEK renk yapmak: satırlar rengi
    bloktan miras alıyor, merdiven testi böylece bloktaki bütün yazıyı ölçüyor.
    """
    for secici in (".blk small", ".daylist .row small", ".blkad"):
        govde = _kural(secici)
        assert "color:" not in govde, f"{secici} kendi rengini veriyor"
        assert "opacity:" not in govde, f"{secici} yazıyı solduruyor"
    assert "color:var(--accent-ink)" in _kural(".blk")


def test_BAGLANTININ_kurali_var():
    """Sayfada `a` kuralı YOKTU: "Darboğaz bölümünde ayrıntı" tarayıcı
    mavisiyle (#0000EE) çiziliyordu — gece şemasında surface-2 üstünde 1.7:1.
    Renk tek işaret değil: alt çizgi de var."""
    govde = _kural("a")
    assert "color:var(--seal)" in govde
    assert "text-decoration:underline" in govde


def test_ETIKETIN_her_hali_BOYALI():
    """Denklik satırındaki "beyanın" etiketi `class="tag unknown"` taşıyordu
    ama `.tag.unknown` kuralı yoktu — zeminsiz, rengi mirastan gelen çıplak
    yazı. Şablonda sabit yazılı her `tag X` sınıfının kuralı olmalı."""
    sabit = set(re.findall(r'class="tag ([A-Za-z_]+)"', SABLON))
    # `tag ${kosul ? "CAP" : "unknown"}` — üçlü ifadenin iki kolu da sabit
    for ikili in re.findall(r'class="tag \$\{[^}]*?\? "([A-Za-z_]+)" : "([A-Za-z_]+)"', SABLON):
        sabit.update(ikili)
    for sinif in sabit:
        assert f".tag.{sinif}" in CSS, f".tag.{sinif} kuralı yok"
    assert "unknown" in sabit, "test kurulumu bozuk: `tag unknown` bulunamadı"


# ------------------------------------------------------------- 2. ölçekler
def test_YAZI_BOYUTU_dokuz_basamak_ve_ALT_SINIR_10_5():
    """★ 18 farklı boyut vardı (8.5px'ten 29px'e, yarım piksel adımlarla).
    Dokuz basamağa indi; en küçüğü 10.5 — `.panel .pctlbl` 9px'ti, "artıları
    ayır" grafiği 8.5px. Sayfa CSS'i, satır içi stiller ve sitenin yükleme
    ekranı birlikte taranıyor; baskı (pt) dışarıda."""
    kaynaklar = {"css": _baski_disi(CSS), "yükleme": _yukleme_css(),
                 "satır içi": ";".join(_satir_ici_stiller())}
    disarida = {}
    for ad, metin in kaynaklar.items():
        for v in re.findall(r"font-size:(\d+(?:\.\d+)?)px", metin):
            if float(v) not in YAZI_OLCEGI:
                disarida.setdefault(ad, set()).add(v)
    assert not disarida, f"ölçek dışı yazı boyutu: {disarida}"


def test_HARF_ARALIGI_alti_basamak():
    degerler = set(re.findall(r"letter-spacing:(-?\.?\d*\.?\d+em|0)", CSS))
    assert degerler <= HARF_ARALIGI, f"ölçek dışı: {degerler - HARF_ARALIGI}"


def test_ARALIK_2px_IZGARASINDA():
    """★ 50 farklı padding değeri vardı; 3, 5, 7, 9, 11, 13, 15px'lik tek
    piksellik sapmalar. Kural: tek sayı bir üst çift basamağa — ama `min-height`
    tanımlı denetimde yükseklik korunacak yöne (düğme 34px, alan 36px).

    Tarama `gap`/`margin`/`padding` değerlerine bakıyor; kenar kalınlığı ve
    konum (`top`, `right`) ayrı iş, sayılmıyor."""
    izin = ARALIK_OLCEGI | ARALIK_ISTISNA
    disarida = set()
    desen = r"(?:^|[{;\s])(?:gap|row-gap|column-gap|padding|margin)(?:-(?:top|right|bottom|left))?:([^;}]*)"
    metinler = [_baski_disi(CSS)] + _satir_ici_stiller()
    for metin in metinler:
        for m in re.finditer(desen, metin):
            for v in re.findall(r"(?<![\d.])(-?\d+(?:\.\d+)?)px", m.group(1)):
                if abs(float(v)) not in izin:
                    disarida.add(m.group(0).strip()[:60])
    assert not disarida, f"ölçek dışı aralık: {sorted(disarida)}"


# --------------------------------------------------------- 3. köşe, gölge, renk
def test_KOSE_YOK():
    """Şematik'in birinci kuralı: sıfır köşe. Tek istisna dönen halka (`.spin`)
    — bir daire. Not dağılımı sütunlarının 2px'lik üst köşesi bu kuralı
    delen tek yerdi."""
    assert "--r:0px" in CSS.replace(" ", "")
    for sel, govde in re.findall(r"([^{}]+)\{([^{}]*)\}", CSS):
        for v in re.findall(r"border-radius:([^;}]+)", govde):
            if sel.strip() == ".spin":
                assert v.strip() == "50%"
            else:
                assert v.strip() == "var(--r)", f"{sel.strip()}: border-radius:{v}"


def test_GOLGE_yalniz_YUZEN_katmanda():
    """★ "Gölge yok, degrade yok — tamamen düz." Kademe kutusunun üzerine
    gelince gölge veriyordu; yapışkan çubuk ve bildirimin gölgesi kuralın
    içinde sabit siyahtı ve AÇIK şemada da aynı siyahla basılıyordu.
    Artık: gölge jetonu (pencere, bildirim, yapışkan çubuk), iç çerçeve ya da hiç."""
    for v in re.findall(r"box-shadow:([^;}]+)", _baski_disi(CSS)):
        v = v.strip()
        assert (v.startswith("var(--shadow") or v.startswith("inset 0 0 0")
                or v == "none"), f"yüzen katman dışı gölge: {v}"
    for jeton in ("--shadow-sticky", "--shadow-toast"):
        assert CSS.count(jeton + ":") == 3, f"{jeton} üç paletin hepsinde tanımlı değil"


def test_SABIT_RENK_paletin_DISINDA_YOK():
    """Renk yalnız üç palet bloğunda yazılı. Sabit bir renk tema değişince
    yerinde kalır — Faz 38b'deki `var(--warn-bg,#fdf3e3)` gece şemasına açık
    zemin basıyordu. İstisnalar: baskı ve `mask-image` (renk değil, alfa)."""
    govde = _baski_disi(CSS)
    govde = re.sub(r":root\{.*?\n\}", " ", govde, count=1, flags=re.S)
    govde = re.sub(r':root:not\(\[data-theme="dark"\]\)\{.*?\n  \}\n\}', " ", govde, count=1, flags=re.S)
    govde = re.sub(r':root\[data-theme="light"\]\{.*?\n\}', " ", govde, count=1, flags=re.S)
    govde = re.sub(r"mask-image:[^;}]+", " ", govde)
    sabit = re.findall(r"#[0-9A-Fa-f]{3,8}\b|rgba?\([^)]*\)", govde)
    assert not sabit, f"paletin dışında sabit renk: {sabit}"


def test_ACIK_PALET_iki_blokta_BIREBIR():
    """★ Açık palet iki kez yazılı: sistem teması (`prefers-color-scheme`) ve
    düğmeyle seçilen (`[data-theme="light"]`). Faz 38b'de ikincisinde
    `--yandal*` YOKTU; birincisinde de aynı satır iki kez yazılıydı. İkisinin
    birebir aynı olduğunu tutan bir test yoktu — şimdi var."""
    medya = re.search(r':root:not\(\[data-theme="dark"\]\)\{\s*@media \(prefers-color-scheme:light\)\{(.*?)\n  \}\n\}',
                      CSS, re.S)
    acik = re.search(r':root\[data-theme="light"\]\{(.*?)\n\}', CSS, re.S)
    assert medya and acik, "açık palet blokları bulunamadı"

    def jetonlar(blok):
        ciftler = re.findall(r"(--[a-z0-9-]+)\s*:\s*([^;]+);", blok)
        adlar = [a for a, _ in ciftler]
        assert len(adlar) == len(set(adlar)), f"aynı jeton iki kez: {sorted({a for a in adlar if adlar.count(a) > 1})}"
        return {a: " ".join(v.split()) for a, v in ciftler}

    assert jetonlar(medya.group(1)) == jetonlar(acik.group(1))


# ------------------------------------------------------------- 4. durumlar
def test_DURUMLAR_tek_dilde():
    """★ Aynı iş, dört davranış: sekmenin üzerine gelince zemini değişiyordu;
    kip düğmesinin, seçim grubunun, dönem düğmesinin ve not dağılımı
    sekmesinin HİÇ değişmiyordu. Birincil düğme opaklıkla soluyordu. Devre
    dışı üç ayrı opaklıktaydı (.35 / .45 / .5)."""
    duz = CSS.replace(" ", "").replace("\n", "")
    for secici in ('.modebtn:not([aria-pressed="true"]):hover',
                   '.radios button:not([aria-pressed="true"]):hover',
                   '.terms button:not([aria-pressed="true"]):hover',
                   '.ndtab:not(.sec):hover',
                   '.tab:not([aria-selected="true"]):hover'):
        assert secici.replace(" ", "") in duz, f"üzerine gelme yok: {secici}"
    birincil = _kural(".ghost.primary:hover")
    assert "opacity" not in birincil and "var(--seal-hover)" in birincil

    devre_disi = set()
    for sel, govde in re.findall(r"([^{}]+)\{([^{}]*)\}", CSS):
        if "disabled" in sel:
            devre_disi |= set(re.findall(r"opacity:([.\d]+)", govde))
    assert devre_disi == {".45"}, f"devre dışı opaklığı tek değil: {devre_disi}"


def test_TAMAMLANDI_efsaneyle_AYNI_ve_OKUNUR():
    """Kademe kutusu `DONE` .5 opaklıktaydı — gündüz şemasında kod 3.38:1.
    Efsanedeki örnek (`.tierlegend i.done`) ise .6'ydı: efsane, gösterdiği
    şeye benzemiyordu. Üçü de .6 (gündüz 4.66, gece 5.51)."""
    op = lambda s: re.search(r"opacity:([.\d]+)", _kural(s)).group(1)  # noqa: E731
    assert op('.tier li[data-s="DONE"]') == op(".tierlegend i.done") == op(".step.done") == ".6"


def test_KILITLI_adimin_METNI_okunur():
    """Kilitli adımın TAMAMI .5 opaklıktaydı: "bölümü seçtikten sonra ne
    açılacak" sorusunun cevabı gündüz şemasında başlıkta 3.38:1, açıklamada
    1.77:1. Artık yalnız numara ve düğme sönük (düğme `[disabled]` kuralından)."""
    for sel, govde in re.findall(r"([^{}]+)\{([^{}]*)\}", CSS):
        if sel.strip() == ".step.kilit":
            assert "opacity" not in govde, "kilitli adımın tamamı soluyor"
    assert "color:var(--ink-3)" in _kural(".step.kilit .no")


# ------------------------------------------------------------ 5. yerleşim
def test_BOLUM_ACIKLAMASI_esnek_satirda_DEGIL():
    """★★ Faz 39'daki `.cap` hatasının kardeşi. `.summary` bir SAYI SATIRI
    (`display:flex; gap:14px`); beş bölümün açıklama paragrafı da onu
    kullanıyordu. Esnek kutuda her metin parçası ve her `<b>` ayrı öğe olur:
    "planlarının **dolmamış** slotları" kelimeler arası 14px'le çiziliyor,
    telefonda "dolmamış" kendi satırına düşüyordu.

    Kural: `.summary` yalnız JS'in doldurduğu sayı satırı (kimliği var);
    düz yazı `.aciklama`."""
    for m in re.finditer(r'<div class="summary"([^>]*)>', SABLON):
        assert "id=" in m.group(1), f"kimliksiz .summary (düz yazı mı?): {m.group(0)}"
    assert SABLON.count('<div class="aciklama">') >= 5
    assert "display:" not in _kural(".aciklama")
    # Aynı sınıfın ikinci örneği: `.proj` sayı satırının içine konan iki cümle.
    assert "display:block" in _kural(".proj.bilinmiyor"), (
        "`.proj.bilinmiyor` düz yazı taşıyor ama `.proj`'un esnek düzenini miras alıyor")


def test_TELEFONDA_oneri_sekmeleri_ALT_ALTA():
    """Uzun sekme etiketleri ("ÖNERİ 1 · 21 KREDİ · EN AZ BEKLEME") telefonda
    farklı genişlikte satırlara sarılıyor, sol çizgiler yarım kalıyordu."""
    mobil = _mobil_css().replace(" ", "").replace("\n", "")
    assert ".tabs{flex-direction:column;width:100%}" in mobil
    assert ".tab:first-child{border-top:0}" in mobil


# ------------------------------------------------------- uçtan uca (tarayıcı)
_CANLI = r'''
import sys, tempfile, threading, time, os
from pathlib import Path
sys.path.insert(0, os.environ["ITUCAP_SRC"])
_T = Path(tempfile.mkdtemp()); (_T/"config").mkdir(); (_T/"data").mkdir()
(_T/"config"/"settings.toml").write_text(
    '[student]\nanadal_program="HTAE"\nsecond_kind="yok"\ndonem=1\n', encoding="utf-8")
# Mevzuat kuralları deponun kendisinden: kredi yükü kuralı varken transkript
# yoksa panel "İlerleme bilinmiyor" notunu gösteriyor — esnek kutu denetimi onu da görsün.
import shutil
shutil.copy(Path(os.environ["ITUCAP_SRC"]).parent / "config" / "kurallar.toml", _T/"config"/"kurallar.toml")
import itucap.config as config
config.ROOT = _T; config.DATA_DIR = _T/"data"
config.REF_DB = _T/"data"/"reference.sqlite3"; config.USER_DB = _T/"data"/"user.sqlite3"
from itucap import db
con = db.connect(config.REF_DB, "schema.sql")
con.execute("INSERT INTO program(code,name,level) VALUES ('HTAE','H','LS')")
con.execute("INSERT INTO plan(id,program_code,plan_type,title,source) VALUES (1,'HTAE','lisans','x','obs')")
for i, kod in enumerate(("AAA 101E", "BBB 102E", "CCC 103E", "DDD 104E", "EEE 105E")):
    con.execute("INSERT INTO course(code,name,credits,ects) VALUES (?,?,3,4)", (kod, "Ders " + kod))
    con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,position,term_no) VALUES (1,'REQUIRED',?,?,1)", (kod, i))
    crn = str(100 + i)
    con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled,building) VALUES (?,?,40,0,'INB')", (crn, kod))
    con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES (?,'HTAE')", (crn,))
    con.execute("INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min,building) VALUES (?,?,540,630,'INB')", (crn, i + 1))
con.commit(); con.close(); db.connect(config.USER_DB, "schema_user.sql").close()

from itucap import server
st = server.State(label="ben")
h = server.build(st, host="127.0.0.1", port=0); P = h.server_address[1]
threading.Thread(target=h.serve_forever, daemon=True).start(); time.sleep(0.4)

from playwright.sync_api import sync_playwright
OKU = """() => {
  /* Hesaplanan renk `color-mix` sonucu olarak `oklab(…)`/`color(srgb …)`
     dönebiliyor; sayıları elle ayıklamak yanlış ölçer. Tuval her CSS rengini
     sRGB piksele çeviriyor. */
  const tuval = document.createElement('canvas'); tuval.width = tuval.height = 1;
  const cx = tuval.getContext('2d', {willReadFrequently: true});
  const rgb = s => { cx.clearRect(0, 0, 1, 1); cx.fillStyle = '#000'; cx.fillStyle = s;
                     cx.fillRect(0, 0, 1, 1); return Array.from(cx.getImageData(0, 0, 1, 1).data).slice(0, 3); };
  const lum = c => { const l = c.map(v => { v /= 255; return v <= .04045 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); });
                     return .2126 * l[0] + .7152 * l[1] + .0722 * l[2]; };
  const oran = (a, b) => { const x = lum(rgb(a)), y = lum(rgb(b)); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };
  let enKotu = 99;
  document.querySelectorAll('#grid .blk[data-course]').forEach(b => {
    const zemin = getComputedStyle(b).backgroundColor;
    b.querySelectorAll('b, .blkad, small').forEach(e => {
      const cs = getComputedStyle(e);
      if (cs.opacity !== "1") enKotu = 0;
      enKotu = Math.min(enKotu, oran(cs.color, zemin));
    });
  });
  const a = document.createElement('a'); a.href = '#'; a.textContent = 'x';
  document.querySelector('.card').appendChild(a);
  const kart = getComputedStyle(document.querySelector('.card')).backgroundColor;
  const bag = oran(getComputedStyle(a).color, kart);
  a.remove();
  /* Esnek/ızgara kutuda DÜZ YAZI: doğrudan metin + satır içi vurgu. Her parça ayrı
     öğe olur ve kelimeler koparılır. `.proj` bilerek böyle (sayı satırı, boşluk = gap). */
  const duzyazi = [];
  document.querySelectorAll('body *').forEach(el => {
    const d = getComputedStyle(el).display;
    if (!/flex|grid/.test(d) || el.offsetParent === null) return;
    const cocuk = [...el.childNodes];
    const metin = cocuk.some(n => n.nodeType === 3 && n.textContent.trim().length > 1);
    const vurgu = cocuk.some(n => n.nodeType === 1 && /^(B|STRONG|EM|A|CODE)$/.test(n.tagName));
    if (metin && vurgu && el.className !== 'proj') duzyazi.push(String(el.className || el.tagName));
  });
  return {blok: enKotu, bag: bag, n: document.querySelectorAll('#grid .blk[data-course]').length,
          duzyazi: [...new Set(duzyazi)].join('|') || '-'};
}"""
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1400, "height": 950})
    pg.goto(f"http://127.0.0.1:{P}/", wait_until="networkidle", timeout=30000)
    pg.wait_for_timeout(900)
    for tema in ("dark", "light"):
        pg.eval_on_selector("html", f"e => e.setAttribute('data-theme','{tema}')")
        pg.wait_for_timeout(250)
        o = pg.evaluate(OKU)
        print(f"BLOK_{tema.upper()}:{o['blok']:.2f}")
        print(f"BAG_{tema.upper()}:{o['bag']:.2f}")
        print(f"SAYI_{tema.upper()}:{o['n']}")
        print(f"DUZYAZI_{tema.upper()}:{o['duzyazi']}")
    b.close()
h.shutdown()
'''


def test_UCTAN_UCA_blok_yazisi_ve_baglanti_TARAYICIDA(tmp_path, monkeypatch):
    """★★ Tarayıcıda, iki temada: tonlu bloktaki HER yazı satırının hesaplanan
    rengi, bloğun hesaplanan zemininde ≥ 4.5; bağlantı kart zemininde ≥ 4.5;
    görünen hiçbir esnek/ızgara kutu düz yazı taşımıyor (transkriptsiz kurulum:
    panelin "İlerleme bilinmiyor" notu tam da bu hataydı).

    Statik testler kuralı okuyor; bu test tarayıcının gerçekten ne çizdiğini
    ölçüyor — satır içi bir stil ya da sonradan gelen bir kural bunu bozarsa
    yalnız burası görür."""
    if not shutil.which("node"):
        pytest.skip("node yok")
    try:
        import playwright  # noqa: F401
    except ImportError:
        pytest.skip("playwright yok")
    monkeypatch.setenv("ITUCAP_SRC", str(Path(UI.__file__).resolve().parents[1]))
    betik = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, dir=str(tmp_path))
    betik.write(_CANLI); betik.close()
    r = subprocess.run([sys.executable, betik.name], capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        pytest.fail(r.stderr[-1500:])
    cikti = dict(s.split(":", 1) for s in r.stdout.strip().splitlines()
                 if ":" in s and s.split(":", 1)[0].replace("_", "").isupper())
    for tema in ("DARK", "LIGHT"):
        assert int(cikti.get(f"SAYI_{tema}", 0)) >= 3, "test kurulumu bozuk: blok yok"
        assert float(cikti[f"BLOK_{tema}"]) >= 4.5, (
            f"{tema}: tonlu blokta yazı {cikti[f'BLOK_{tema}']}:1 — taban 4.5")
        assert float(cikti[f"BAG_{tema}"]) >= 4.5, (
            f"{tema}: bağlantı {cikti[f'BAG_{tema}']}:1 — taban 4.5")
        assert cikti[f"DUZYAZI_{tema}"] == "-", (
            f"esnek kutuda düz yazı (kelimeler kopar): {cikti[f'DUZYAZI_{tema}']}")
