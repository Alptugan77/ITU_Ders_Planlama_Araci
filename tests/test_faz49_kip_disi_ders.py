"""Faz 49 — ızgaradaki derse TIKLANAMIYORDU (18.09.2026).

Kullanıcı: *"x.dönem + alttan kısmında kaydettiğim program yüklenince üstten
olan derslere tıklayamıyorum"*.

Ölçüldü (gerçek veri, "5. dönem + alttan" kipi, açılış ekranı):

| | |
|---|---|
| ızgaradaki ders | 14 |
| kipin aday havuzu | **11** |
| havuz DIŞI ve ekranda duran | **5** — GEO 401E · ATA 121 · TUR 121 · GEO 464E · SNT 103E |
| o beşine tıklayınca | **hiçbir şey** — pencere yok, hata yok, açıklama yok |
| havuzdaki bir derse tıklayınca | pencere açılıyor |

Sebep tek kelime: pencere dersi `CAND` (AKTİF KİPİN havuzu) üzerinden
çözüyordu; ızgara ise `candOf` ile çiziliyor — o, kipte yoksa tam havuza
düşüyor. Ekranda çizilen ama açılamayan ders çıkıyordu.

⚠️ Kip politikası bu repoda 27.08.2026'da zaten yazılmıştı (boş saat
penceresi): *"kip yalnız ÖNERİYİ daraltıyor, elle ekleme hakkını değil."*
Pencere o politikadan habersizdi.

⚠️⚠️ Açmak tek başına yetmez, çünkü iki şey GERÇEKTEN farklı ve söylenmezse
kullanıcı yanılır:
1. Bu kip o dersi kendiliğinden önermez — çıkarırsan geri getirmez.
2. Motor kilidi yalnız o kipin havuzundaki derse bağlıyor
   (`recommend.build_schedules`), yani kilit bu kipte **bağlamaz**.
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
JS = KAYNAK[KAYNAK.index("<script>"):]


def _fn(ad: str) -> str:
    """Bir JS işlevinin gövdesi, YORUMLARI SÖKÜLMÜŞ.

    ⚠️ Yorum bloğu neyin neden değiştiğini anlatırken eski kodu da yazıyor;
    yorumlu metinde arama yapan muhafız, koddan kalkmış bir şeyi kendi
    yorumunda bulup yeşil kalıyor (Faz 48'de iki muhafız böyleydi).
    """
    m = re.search(r"(?m)^function " + re.escape(ad) + r"\(.*?\n\}", JS, re.S)
    assert m, f"{ad} bulunamadı"
    return re.sub(r"/\*.*?\*/", " ", m.group(0), flags=re.S)


# =================================================== 1. hatanın kendisi
def test_PENCERE_tam_havuza_dusuyor():
    """★★ Bildirilen hata. Pencere `CAND` yerine `candOf` okumalı —
    `choose`, `sectionOf` ve ızgara zaten oradan okuyor."""
    govde = _fn("courseDialog")
    assert "candOf(course)" in govde, "pencere hâlâ kipin havuzuna kilitli"
    assert "CAND[course], cur" not in govde


def test_KIP_DISI_oldugu_SOYLENIYOR():
    """⚠️ Sessizce açmak da yanlış olurdu: bu kip dersi kendiliğinden
    önermiyor. Çıkarınca geri gelmemesi açıklanmamış bir davranış olurdu.

    ⚠️⚠️ Bu muhafız metnin VAR OLMASINA değil, KOŞULA bağlı olduğuna
    bakıyor. İlk hâli yalnız dizgeyi arıyordu ve `${disKip ? …}` →
    `${false ? …}` denemesinde YEŞİL kaldı: dizge duruyor, ekranda
    görünmüyordu. Asıl kanıt uçtan uca testte (tarayıcıda okunan metin)."""
    govde = _fn("courseDialog")
    assert "const disKip = !CAND[course]" in govde
    assert re.search(r"\$\{disKip \? `", govde), "not KOŞULA bağlı değil"
    assert "kendiliğinden önermez" in govde
    # Hangi kipin önerdiği de yazıyor — "peki nerede bulurum" sorusu açıkta
    # kalmasın.
    assert "onerenKip" in govde and "Öneren kip:" in govde


def test_KILIT_bu_kipte_BAGLAMAZ_diyor():
    """★★ Pencere açılınca kilit düğmesi de görünür oldu. Motor kilidi yalnız
    o kipin havuzundaki derse bağlıyor (`locked = {… if k in havuzda}`), yani
    burada basılan kilit bu kipte hiçbir şey yapmaz. Düğmeyi gizlemiyoruz
    (öbür kipte gerçekten çalışıyor), ne yapacağını yazıyoruz."""
    govde = _fn("kilitNotu")
    # KOŞUL + metin birlikte: `if(disKip)` → `if(false)` denemesinde yalnız
    # metne bakan hâli yeşil kalmıştı.
    assert re.search(r"if\(disKip\)\s*\n?\s*return", govde), \
        "kip dışı dalı koşula bağlı değil"
    assert "uygulanmaz" in govde
    # Motor tarafı gerçekten böyle mi — muhafız iddiayı KAYNAKTA doğruluyor.
    rec = pathlib.Path(UI.__file__).with_name("recommend.py").read_text(
        encoding="utf-8")
    assert "locked = {k: v for k, v in locked.items() if k in havuzda}" in rec


def test_SERIT_hepsi_kapsam_disiysa_yanlis_soylemiyor():
    """⚠️ Şerit "öneriler bu derslerin etrafında kuruluyor" diyordu; kilitli
    ders bu kipin havuzunda değilse bu düpedüz yanlış.

    ⚠️ FAZ 53'TE YENİDEN YAZILDI: şerit artık motorun UYGULADIĞI kilitleri
    (`uygulanan`) okunamayan/gölgede kalan satırlardan ayırıyor; kapsam dışı
    hesabı `list` değil `uygulanan` üzerinden, giriş cümlesi de "hiç
    uygulanan kilit yoksa" koşulunun arkasında. Kontrolün anlamı aynı."""
    govde = _fn("renderKilitNot")
    # ⚠️ `"kapsamDisi" in govde` YETMEZ: değişkeni `kapsamDisiYOK` diye
    # yeniden adlandıran deneme bu kontrolü geçti (alt dizge). Tanımın
    # kendisini arıyoruz.
    assert re.search(r"const kapsamDisi = uygulanan\.filter\(l => l\.ok && !bagli", govde), \
        "kapsam dışı kilitler hesaplanmıyor"
    assert "bu kipte uygulanmamaktadır" in govde
    assert "Bu kipte hiçbir kilit uygulanmamaktadır" in govde
    # Giriş cümlesi KOŞULLU: bağlayan kilit yoksa "etrafında kuruluyor"
    # denmiyor.
    assert re.search(r": bagli\.length \? `Öneriler", govde), "giriş cümlesi koşulsuz"


# =================================================== 2. aynı SINIF
def test_CAND_okumalari_SAYILI_yerde():
    """★★★ Sınıf muhafızı. `CAND` = aktif kipin havuzu; `candOf` = kipte
    yoksa tam havuz. Ekranda DURAN bir dersi `CAND` üzerinden çözen her yeni
    satır aynı hatayı geri getirir (tıklanamayan ders).

    O yüzden tek tek işlevleri değil, `CAND[...]` OKUMALARINI sayıyoruz.
    Listeye ekleme yapmak serbest — ama bilerek, sebebini yazarak."""
    # ⚠️ Yorumları söküp AYNI metinde arıyoruz: sökülmüş metinde bulup
    # özgün metinde konum aramak kaymaya yol açıyor (ilk denemede oldu —
    # muhafız bambaşka işlev adları saydı).
    kod = re.sub(r"/\*.*?\*/", " ", JS, flags=re.S)
    yerler = []
    for m in re.finditer(r"CAND\[", kod):
        once = kod[:m.start()]
        fn = re.findall(r"(?m)^(?:function (\w+)|const (\w+) = )", once)
        yerler.append((fn[-1][0] or fn[-1][1]) if fn else "?")
    sayim = {ad: yerler.count(ad) for ad in set(yerler)}
    beklenen = {
        "injectSections": 2,   # YAZMA: dersi havuza sokan yer (okuma değil)
        "candOf": 1,           # tanımın kendisi
        "courseDialog": 1,     # `disKip` — "bu kipte var mı" SORUSU
        "renderAcikDenklik": 1,  # tıklanamazlık SESSİZ değil; Faz 49'da ölçüldü
    }
    assert sayim == beklenen, (
        f"`CAND[` okumaları değişmiş: {sayim}\n"
        "Ekranda duran bir dersi çözüyorsan `candOf` kullan; gerçekten "
        "'bu kipte var mı' diye soruyorsan bu listeye sebebiyle ekle.")


def test_not_dagilimi_tazelemesi_de_TAM_HAVUZDAN():
    """Pencere kip dışı ders için açılıyor; dönem sekmesine basınca kutu
    `CAND` ile yeniden çizilseydi boşalırdı."""
    assert "notDagilimi(candOf(course))" in JS


def test_EKLEME_penceresi_de_TAM_HAVUZDAN():
    govde = _fn("addDialog")
    assert "candOf(course)" in govde


# =================================================== 3. uçtan uca
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
# 1. dönemde iki ders, 5. dönemde bir tane. Öğrenci 2. dönemde olacak:
# ÜSTTEN olan `ZZZ 501E` dönemlik havuzun DIŞINDA kalır.
PLAN = [("AAA 101E", 1, 1, 540), ("BBB 102E", 1, 2, 600), ("ZZZ 501E", 5, 3, 660)]
for kod, term, i, bas in PLAN:
    con.execute("INSERT INTO course(code,name,credits,ects) VALUES (?,?,3,4)",
                (kod, "Ders " + kod))
    con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,position,term_no)"
                " VALUES (1,'REQUIRED',?,?,?)", (kod, i, term))
    crn = str(700 + i)
    con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled)"
                " VALUES (?,?,40,0)", (crn, kod))
    con.execute("INSERT INTO lesson_allowed_program(crn,program_code)"
                " VALUES (?,'HTAE')", (crn,))
    con.execute("INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min)"
                " VALUES (?,?,?,?)", (crn, i, bas, bas + 110))
con.commit(); con.close(); db.connect(config.USER_DB, "schema_user.sql").close()

from itucap import server
st = server.State(label="ben")
h = server.build(st, host="127.0.0.1", port=0); P = h.server_address[1]
threading.Thread(target=h.serve_forever, daemon=True).start(); time.sleep(0.4)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width":1440,"height":1000})
    hata = []
    pg.on("pageerror", lambda e: hata.append(str(e)[:200]))
    pg.goto(f"http://127.0.0.1:{P}/", wait_until="networkidle", timeout=30000)
    pg.wait_for_timeout(1500)
    # 2. dönem: "2. dönem + alttan" kipi doğuyor
    pg.evaluate("""async () => { applyState(await api("/api/donem", {donem: 2})); }""")
    pg.wait_for_timeout(1500)
    # Üç dersi de içeren programı KAYDET (kullanıcının yaptığı gibi)
    pg.evaluate("""async () => {
      const tam = MODES.findIndex(m => (m.candidates||[]).some(c => c.course === "ZZZ 501E"));
      if(tam >= 0 && tam !== mode) useMode(tam);
      sel = ["AAA 101E","BBB 102E","ZZZ 501E"].map(k =>
        ({course: k, crn: (candOf(k).sections[0]||{}).crn}));
      await api("/api/picks", {picks: sel});
    }""")
    pg.wait_for_timeout(2000)
    # Sayfayı YENİDEN aç: açılış kipi "2. dönem + alttan" ve kaydedilen yükleniyor
    pg.goto(f"http://127.0.0.1:{P}/", wait_until="networkidle", timeout=30000)
    pg.wait_for_timeout(2000)
    pg.evaluate("() => gorunumAc('schedSection')"); pg.wait_for_timeout(400)
    d = pg.evaluate("""() => ({
      kip: MODES[mode].label,
      secili: sel.map(x => x.course),
      disHavuz: sel.filter(x => !CAND[x.course]).map(x => x.course),
      blok: [...document.querySelectorAll('#grid .blk[data-course]')].map(e => e.dataset.course),
    })""")
    print("KIP:" + d["kip"])
    print("DIS:" + ",".join(d["disHavuz"]))
    print("BLOK:" + ",".join(sorted(d["blok"])))
    # ★ Asıl ölçüm: ızgaradaki bloğa TIKLA
    pg.evaluate("""() => { const e = document.querySelector(
      '#grid .blk[data-course="ZZZ 501E"]'); if(e) e.click(); }""")
    pg.wait_for_timeout(700)
    r = pg.evaluate("""() => { const dl = document.querySelector("dialog[open]");
      if(!dl) return {acik:false};
      const t = (dl.innerText||"").replace(/\s+/g," ");
      return {acik:true,
              /* ⚠️ AYIRT EDİCİ cümle: "aday havuzunda değil" KİLİT notunda da
                 geçiyor, ona bakan bir ölçüm kip notu hiç çizilmese bile
                 yeşil kalırdı (muhafız denemesinde oldu). */
              kipNotu: t.includes("kendiliğinden önermez"),
              kilitNotu: t.replace(/\\s+/g, " ").includes("bu kipte uygulanmaz"),
              cikar: !!dl.querySelector("#removeCourse")}; }""")
    print("PENCERE:" + str(r["acik"]))
    print("KIPNOTU:" + str(r.get("kipNotu")))
    print("KILITNOTU:" + str(r.get("kilitNotu")))
    print("CIKAR:" + str(r.get("cikar")))
    # ★ Kip DIŞI dersi kilitle: şerit ne diyor? (Motor bu kipte yok sayıyor.)
    pg.evaluate("() => { const k = document.querySelector('#kilitBtn'); if(k) k.click(); }")
    pg.wait_for_timeout(3000)
    s = pg.evaluate("""() => { const el = document.querySelector("#kilitNot");
      if(!el || el.hidden) return {yok:true};
      const t = (el.innerText||"").replace(/\s+/g," ");
      return {yok:false, kapsam: t.includes("bu kipte uygulanmamaktadır"),
              yanlisIddia: t.includes("etrafında kuruluyor")}; }""")
    print("SERIT:" + str(s.get("kapsam")))
    print("SERIT_YANLIS:" + str(s.get("yanlisIddia")))
    print("HATA:" + ("|".join(hata[:3]) if hata else "-"))
    b.close()
h.shutdown()
'''


def test_UCTAN_UCA_faz49(tmp_path, monkeypatch):
    """★★ Kullanıcının yolu, baştan sona: programı kaydet → sayfayı aç →
    açılış kipi "2. dönem + alttan" → kaydedilen program yükleniyor →
    üst dönem dersinin ızgaradaki bloğuna TIKLA."""
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
    assert "dönem + alttan" in c["KIP"], f"açılış kipi beklenen değil: {c}"
    assert c["DIS"] == "ZZZ 501E", f"üst dönem dersi havuz dışı değil: {c}"
    assert "ZZZ 501E" in c["BLOK"], f"ders ızgarada çizilmiyor: {c}"
    assert c["PENCERE"] == "True", f"★ tıklayınca pencere AÇILMIYOR: {c}"
    assert c["KIPNOTU"] == "True", f"kip dışı olduğu söylenmiyor: {c}"
    assert c["KILITNOTU"] == "True", f"kilidin bağlamayacağı yazmıyor: {c}"
    assert c["CIKAR"] == "True", f"programdan çıkarma düğmesi yok: {c}"
    assert c["SERIT"] == "True", f"şerit kapsam dışı kilidi söylemiyor: {c}"
    assert c["SERIT_YANLIS"] == "False", \
        f"şerit bağlamayan kilit için 'etrafında kuruluyor' diyor: {c}"
    assert c["HATA"] == "-", f"JS hatası: {c['HATA']}"
