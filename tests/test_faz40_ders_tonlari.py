"""Faz 40 — ders başına ton.

Kullanıcı isteği (16.09.2026): *"ders programındaki her ders için biraz daha
farklı bir ton kullanılsın, böylece ayırt etmek ve görselleştirmek
kolaylaşsın"*.

Buradaki testler üç şeyi tutuyor:
  1. merdiven ÖLÇÜLEN tabanların üstünde (kontrast + ayırt edilebilirlik),
  2. ton JS'te PİŞMİYOR — yoksa tema düğmesi sessizce bozulur,
  3. tonun ne anlattığı EKRANDA yazılı.
"""
import ast
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
CSS = re.sub(r"/\*.*?\*/", " ",
             re.search(r"<style>(.*?)</style>", KAYNAK, re.S).group(1), flags=re.S)

TOOLS = pathlib.Path(UI.__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))


def _merdiven_kaynaktan():
    """`const TON_BASAMAK = [...]` — JS dizisini Python listesine çevir."""
    ham = re.search(r"const TON_BASAMAK = (\[.*?\]);", KAYNAK, re.S).group(1)
    return [tuple(x) for x in ast.literal_eval(ham.replace('"', "'"))]


# ------------------------------------------------------- 1. ölçülen tabanlar
def test_MERDIVEN_olculen_tabanlarin_USTUNDE():
    """★★ Bu testin tuttuğu şey bir görünüm tercihi değil, bir TABAN.

    Ton merdivenini uzatmak ya da oranı büyütmek CAZİP: renkler daha çok
    ayrışır. Ama ölçüldü — `accent %36`'da yazı kontrastı 4.40'a düşüyor,
    yani WCAG AA tabanının (4.5) altına. Basamak eklemek de basamaklar arası
    farkı küçültüyor; bir yerden sonra "farklı ton" yalanı oluyor.

    Ölçüm `tools/ton_merdiveni.py`'de ve paleti `ui.py`'den OKUYOR: palet
    değişirse bu test de yeni palete göre ölçer.
    """
    import ton_merdiveni as T

    assert _merdiven_kaynaktan() == T.MERDIVEN, (
        "ui.py'deki TON_BASAMAK ile tools/ton_merdiveni.py ayrı düştü")

    yazi, zemin, adim = T.olc(T.MERDIVEN)
    assert yazi >= T.YAZI_TABANI, f"yazı kontrastı AA altına düştü: {yazi:.2f}"
    assert zemin >= T.ZEMIN_TABANI, (
        f"blok boş hücreden ayrılmıyor: zemin ΔE {zemin:.3f}")
    # Basamaklar birbirinden ayırt edilebilir kalmalı.
    assert adim >= 0.015, f"basamaklar birbirine girdi: ΔE {adim:.4f}"


def test_PLAN_DISI_dersin_tonu_YOK():
    """⚠️ Gri bir aileden ton merdiveni çıkmıyor — ölçüldü: yazı 4.39 (AA
    altı), zemin ΔE 0.021 (blok boş hücreden ayrılmıyor). Plan dışı dersin
    renksizliği zaten BİLGİ: hiçbir planın parçası değil."""
    assert 'const TONSUZ_ROL = new Set(["PLAN_DISI"]);' in KAYNAK
    assert "if(TONSUZ_ROL.has(rol)) return \"\";" in KAYNAK


# --------------------------------------------- 2. ton JS'te PİŞMİYOR (tema)
def test_TON_jetonla_veriliyor_RENK_PISIRILMIYOR():
    """★★ Tema düğmesi yeniden RENDER ETMİYOR — yalnız `data-theme`i
    değiştiriyor. Ton JS'te bir renge çevrilip satır içine yazılsaydı, tema
    değişince o renk ESKİ PALETTE KALIRDI ve kimse fark etmezdi.

    O yüzden satır içinde renk değil, YÖN + ORAN var: iki jeton da `var(...)`.
    Karışımı tarayıcı yapıyor, yani her zaman yürürlükteki paletle.
    """
    govde = re.search(r"function tonStil\(kod, rol\)\{(.*?)\n\}", KAYNAK, re.S)
    assert govde, "tonStil bulunamadı"
    m = re.search(r'`--tonhedef:([^`]*)`', govde.group(1))
    assert m, "tonStil satır içi jeton üretmiyor"
    sablon = m.group(1)
    # Şablonda hex/rgb/hsl geçemez — yalnız var() ve yüzde.
    assert not re.search(r"#[0-9A-Fa-f]{3,6}|rgb\(|hsl\(|oklab\(", sablon), (
        f"tonStil renk PİŞİRİYOR: {sablon!r}")
    assert "var(--" in sablon and "%" in sablon


def test_ton_karisimi_CSS_TARAFINDA():
    """Karışım `color-mix(in oklab, …)` ile CSS'te; varsayılan = ton yok."""
    for sec in (".blk", ".daylist .row"):
        kural = _kural(sec)
        assert "color-mix(in oklab" in kural, f"{sec}: karışım yok"
        assert "--tonhedef:var(--soft)" in kural.replace(" ", ""), (
            f"{sec}: varsayılan hedef tanımlı değil")
        assert "--tonoran:0%" in kural.replace(" ", ""), (
            f"{sec}: varsayılan oran tanımlı değil")


def _kural(secici):
    for sel, govde in re.findall(r"([^{}]+)\{([^{}]*)\}", CSS):
        if sel.strip() == secici:
            return govde
    raise AssertionError(f"kural yok: {secici}")


# ------------------------------------------------ 3. ekranda ne yazdığı
def test_TONUN_NE_DEDIGI_ekranda_YAZILI():
    """⚠️ Proje ilkesi: bir görsel kodlama anlam taşıyorsa ne taşıdığını
    SÖYLEMEK zorunda. Yoksa koyu yeşil "daha dolu" ya da "daha zor" diye
    okunabilir. Basamak sayısı da gizlenmiyor — 9 tondan sonrası tekrar."""
    assert 'id="tonNot"' in KAYNAK
    not_metni = re.search(r'id="tonNot">(.*?)</span>', KAYNAK, re.S).group(1)
    assert "ton" in not_metni.lower()
    assert "9" in not_metni, "kaç ton olduğu yazmıyor"
    assert "üzerine gelindiğinde" in not_metni, "emin olma yolu yazmıyor"


def test_AYNI_DERSIN_butun_saatleri_isaretlenebiliyor():
    """Ton bir ipucu; bu onu kesinliğe çeviriyor. İşaret RENK DEĞİL (çerçeve),
    çünkü renk körlüğünde ton farkı okunmayabilir.

    Ölçüm: açık şubelerin **%15.5'i** (3089'un 479'u) birden fazla güne
    yayılıyor — yani her programda ateşlenmiyor. Yine de ızgara ile telefon
    listesini birbirine bağlıyor ve "hangi bloğa bakıyorum" sorusunu kapatıyor.
    """
    assert "function esDersBagla()" in KAYNAK
    assert "esder" in CSS and "outline:2px solid" in _kural(
        ".blk.esder,.daylist .row.esder").replace(" ", "").replace(
            "outline:2pxsolid", "outline:2px solid")
    for olay in ("mouseenter", "mouseleave", "focus", "blur"):
        assert f'addEventListener("{olay}"' in KAYNAK, f"{olay} bağlı değil"


def test_ton_haritasi_AYNI_DERSE_AYNI_TON():
    """Haftalık program ve kaydedilen program AYNI haritayı kullanıyor —
    yoksa aynı ders iki yerde iki tonda görünürdü."""
    assert "tonHaritaKur([" in KAYNAK
    kur = re.search(r"tonHaritaKur\(\[(.*?)\]\);", KAYNAK, re.S).group(1)
    assert "picks()" in kur and "savedPicks" in kur


# --------------------------------------------------------- uçtan uca (tarayıcı)
_CANLI = r'''
import sys, tempfile, threading, time, os, pathlib
from pathlib import Path
sys.path.insert(0, os.environ["ITUCAP_SRC"])
_T = Path(tempfile.mkdtemp()); (_T/"config").mkdir(); (_T/"data").mkdir()
(_T/"config"/"settings.toml").write_text(
    '[student]\nanadal_program="HTAE"\nsecond_kind="yok"\ndonem=1\n',
    encoding="utf-8")
import itucap.config as config
config.ROOT = _T; config.DATA_DIR = _T/"data"
config.REF_DB = _T/"data"/"reference.sqlite3"; config.USER_DB = _T/"data"/"user.sqlite3"
from itucap import db
con = db.connect(config.REF_DB, "schema.sql")
con.execute("INSERT INTO program(code,name,level) VALUES ('HTAE','H','LS')")
con.execute("INSERT INTO plan(id,program_code,plan_type,title,source)"
            " VALUES (1,'HTAE','lisans','x','obs')")
for i, kod in enumerate(("AAA 101E", "BBB 102E", "CCC 103E")):
    con.execute("INSERT INTO course(code,name,credits,ects) VALUES (?,?,3,4)",
                (kod, "Ders " + kod))
    con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,position,term_no)"
                " VALUES (1,'REQUIRED',?,?,1)", (kod, i))
    crn = str(100 + i)
    con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled) VALUES (?,?,40,0)",
                (crn, kod))
    con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES (?,'HTAE')",
                (crn,))
    con.execute("INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min)"
                " VALUES (?,?,540,630)", (crn, i + 1))
con.commit(); con.close(); db.connect(config.USER_DB, "schema_user.sql").close()

from itucap import server
st = server.State(label="ben")
h = server.build(st, host="127.0.0.1", port=0); P = h.server_address[1]
threading.Thread(target=h.serve_forever, daemon=True).start(); time.sleep(0.4)

from playwright.sync_api import sync_playwright
OKU = """() => {
  const o = {};
  document.querySelectorAll('#grid .blk[data-course]').forEach(e => {
    o[e.dataset.course] = getComputedStyle(e).backgroundColor;
  });
  return o;
}"""
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width":1400,"height":950})
    pg.goto(f"http://127.0.0.1:{P}/", wait_until="networkidle", timeout=30000)
    pg.wait_for_timeout(900)
    pg.eval_on_selector("html", "e => e.setAttribute('data-theme','dark')")
    pg.wait_for_timeout(250)
    gece = pg.evaluate(OKU)
    pg.eval_on_selector("html", "e => e.setAttribute('data-theme','light')")
    pg.wait_for_timeout(250)
    gunduz = pg.evaluate(OKU)
    print("BLOK_SAYISI:" + str(len(gece)))
    print("FARKLI_TON:" + str(len(set(gece.values()))))
    # Tema değişince ton YENİDEN hesaplanmalı (renk pişirilmiş olsaydı aynı kalırdı)
    ayni = [k for k in gece if gece[k] == gunduz.get(k)]
    print("TEMAYLA_DEGISMEYEN:" + str(len(ayni)))
    b.close()
h.shutdown()
'''


def test_UCTAN_UCA_tonlar_FARKLI_ve_TEMAYLA_degisiyor(tmp_path, monkeypatch):
    """★★ Tarayıcıda: aynı roldeki üç ders üç FARKLI zemin alıyor ve tema
    değişince üçü de yeniden hesaplanıyor.

    İkincisi asıl sigorta: tema düğmesi yeniden render etmiyor, o yüzden
    JS'te pişirilmiş bir renk sessizce eski temada kalırdı."""
    if not shutil.which("node"):
        pytest.skip("node yok")
    try:
        import playwright  # noqa: F401
    except ImportError:
        pytest.skip("playwright yok")
    monkeypatch.setenv("ITUCAP_SRC", str(Path(UI.__file__).resolve().parents[1]))
    monkeypatch.setenv("TON_HOME", str(tmp_path))
    betik = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                        dir=str(tmp_path))
    betik.write(_CANLI); betik.close()
    r = subprocess.run([sys.executable, betik.name], capture_output=True,
                       text=True, timeout=180)
    if r.returncode != 0:
        pytest.fail(r.stderr[-1500:])
    cikti = dict(s.split(":", 1) for s in r.stdout.strip().splitlines()
                 if ":" in s and s.split(":", 1)[0].isupper())
    assert int(cikti.get("BLOK_SAYISI", 0)) == 3, "test kurulumu bozuk"
    assert int(cikti["FARKLI_TON"]) == 3, (
        f"üç ders {cikti['FARKLI_TON']} farklı ton aldı — çakışma çözülmüyor")
    assert int(cikti["TEMAYLA_DEGISMEYEN"]) == 0, (
        "tema değişti ama ton aynı kaldı — renk pişirilmiş olabilir")
