"""Faz 41 — yeni kullanıcı gözüyle: bilmediğini bilen bir ekran.

Kullanıcı isteği (16.09.2026): *"başka eklenebilecek şeyleri düşün ve ekle,
bunu yeni bir kullanıcı açısından da düşünerek yap"*.

Yöntem: ayar dosyası olmayan, transkripti olmayan, gerçek kataloğu olan bir
kurulum açıldı ve tarayıcıda adım adım yürünüldü. Çıkan üç şeyin ortak yanı
var — üçü de aracın **bilmediği bir şeyi biliyormuş gibi** göstermesiydi.
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
CSS = re.sub(r"/\*.*?\*/", " ",
             re.search(r"<style>(.*?)</style>", KAYNAK, re.S).group(1), flags=re.S)


def _kural(secici):
    for sel, govde in re.findall(r"([^{}]+)\{([^{}]*)\}", CSS):
        if sel.strip() == secici:
            return govde
    raise AssertionError(f"kural yok: {secici}")


# ------------------------------------------------- 1. dönem bilinmiyorsa
def test_DONEM_bilinmiyorsa_program_bunu_SOYLUYOR():
    """★★ Ölçüm (yeni kullanıcı yürüyüşü): yalnız bölümünü seçen öğrenciye
    kurulan 14 derslik programda plan dönemleri 1, 2, 3, 4, 5, 7, 8 idi —
    birinci sınıf dersi FIZ 101E ile 7. dönem dersi GEO 401E yan yana.
    Ekranda bunu açıklayan tek satır yoktu.

    ⚠️ Motor yanlış değil: dönem bilinmeyince plandaki her açık ders aday.
    Yanlış olan SUNUM — "senin haftalık programın" diye gösteriliyordu.
    """
    assert "function renderDonemUyarisi()" in KAYNAK
    assert "renderDonemUyarisi();" in KAYNAK, "render() içinde çağrılmıyor"
    govde = re.search(r"function renderDonemUyarisi\(\)\{(.*?)\n\}",
                      KAYNAK, re.S).group(1)
    # Dönem BİLİNİYORSA susuyor.
    assert "if(DATA.donem || !ps.length)" in govde, "dönem biliniyorken de çıkıyor"


def test_donem_uyarisi_OLCULEN_dagilimi_yaziyor():
    """Uyarı "bazı dersler farklı dönemden" demiyor — SAYIYI döküyor.

    Bu repoda tekrarlayan ders: sayı dökülmezse kullanıcı uyarıyı genel bir
    uyarı sanıp geçiyor (bkz. `_term_note`, Faz 18)."""
    govde = re.search(r"function renderDonemUyarisi\(\)\{(.*?)\n\}",
                      KAYNAK, re.S).group(1)
    assert "p.cand.termNo" in govde, "dağılım gerçek seçimden hesaplanmıyor"
    assert "dönemden ${say[t]}" in govde, "dönem başına SAYI yazılmıyor"
    # Ve ne OLMADIĞINI söylüyor. (Kaynakta satır sarması var, boşluk normalize.)
    assert "bu dönem için önerilen ders listesi değildir" in re.sub(r"\s+", " ", govde)


def test_donem_uyarisinda_TEK_TIKLIK_cikis_var():
    """Dürüstlük yetmiyor: düzeltmesi bir tık uzakta olmalı, yoksa kullanıcı
    uyarıyı okuyup ne yapacağını bilemiyor."""
    govde = re.search(r"function renderDonemUyarisi\(\)\{(.*?)\n\}",
                      KAYNAK, re.S).group(1)
    assert 'id="donemUyariAc"' in govde
    assert "termDialog()" in govde


def test_donem_bilinmiyorken_TAHMIN_iddia_EDILMIYOR():
    """⚠️ Dönem diyaloğu, dönem bilinmezken bile
    "Şu an kullanılan: 0. dönem (tahmin)" yazıyordu.

    İki ayrı yanlış: "0. dönem" diye bir şey yok, ve transkript yokken
    ÇIKARILACAK bir şey olmadığı için ortada bir "tahmin" de yok."""
    assert re.search(r"\$\{DATA\.donem\s*\?\s*`Şu an kullanılan:", KAYNAK, re.S), \
        "dönem durumu koşulsuz yazılıyor"
    assert "Yarıyıl bilgisi bulunmamaktadır" in KAYNAK
    # "0. dönem" hiçbir dalda üretilemiyor: sayı yalnız DATA.donem doluyken.
    assert "${DATA.donem}. dönem</b>\n           (" in KAYNAK.replace("\r", "") or \
        "dönem</b>" in KAYNAK


# ------------------------------------------------------ 2. boş kip kutusu
def test_BOS_kip_kutusu_cizilmiyoR():
    """★ `.modes` çerçeveli bir kutu; kip düğmeleri yalnız dönem BİLİNİYORSA
    iki tane oluyor (`MODES.length < 2` → innerHTML ""). Boşalınca geriye
    2×2px çerçeve kalıyordu ve açık şemada `--border-strong` neredeyse
    siyah: başlığın altında sebepsiz bir NOKTA.

    Yalnız yeni kullanıcı görüyordu — dönemi olan hiç kimse göremezdi."""
    assert "display:none" in _kural(".modes:empty").replace(" ", "")


def test_iki_uyari_YAN_YANA_okunabiliyor():
    """Arz uyarısı ile dönem uyarısı aynı anda çıkabiliyor; dipdibe gelince
    tek blok gibi okunuyorlardı. Ayrı renk + ayrı boşluk."""
    k = _kural(".note.donemsiz").replace(" ", "")
    assert "border-left-color:var(--seal)" in k, "arz uyarısından ayrışmıyor"
    assert "margin-top:10px" in k


# ------------------------------------------------------- uçtan uca akış
_CANLI = r'''
import sys, tempfile, threading, time, os
from pathlib import Path
sys.path.insert(0, os.environ["ITUCAP_SRC"])
_T = Path(tempfile.mkdtemp()); (_T/"config").mkdir(); (_T/"data").mkdir()
# ⚠️ `donem` BİLEREK YOK — yeni kullanıcı bölümünü seçmiş, dönemini söylememiş.
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
# 1. dönem dersi ve 6. dönem dersi — ikisi de açık, çakışmıyor.
for kod, term, gun in (("AAA 101E", 1, 1), ("ZZZ 601E", 6, 2)):
    con.execute("INSERT INTO course(code,name,credits,ects) VALUES (?,?,3,4)",
                (kod, "Ders " + kod))
    con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,position,term_no)"
                " VALUES (1,'REQUIRED',?,?,?)", (kod, term, term))
    crn = str(100 + term)
    con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled) VALUES (?,?,40,0)",
                (crn, kod))
    con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES (?,'HTAE')",
                (crn,))
    con.execute("INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min)"
                " VALUES (?,?,540,630)", (crn, gun))
con.commit(); con.close(); db.connect(config.USER_DB, "schema_user.sql").close()

from itucap import server
st = server.State(label="ben")
h = server.build(st, host="127.0.0.1", port=0); P = h.server_address[1]
threading.Thread(target=h.serve_forever, daemon=True).start(); time.sleep(0.4)

from playwright.sync_api import sync_playwright
DURUM = """() => ({
  uyari: !document.querySelector('#donemUyari').hidden,
  metin: (document.querySelector('#donemUyari').innerText||'').replace(/\s+/g,' '),
  modH: Math.round(document.querySelector('#modes').getBoundingClientRect().height),
  modSayisi: MODES.length, donem: DATA.donem,
  donemSayisi: new Set(picks().map(p => p.cand.termNo)).size,
})"""
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width":1400,"height":1000})
    pg.goto(f"http://127.0.0.1:{P}/", wait_until="networkidle", timeout=30000)
    pg.wait_for_timeout(1200)
    o = pg.evaluate(DURUM)
    print("ONCE_UYARI:" + ("E" if o["uyari"] else "H"))
    print("ONCE_DONEM_SAYISI:" + str(o["donemSayisi"]))
    print("ONCE_MOD_YUKSEKLIK:" + str(o["modH"]))
    print("SAYI_YAZIYOR:" + ("E" if "1. dönemden" in o["metin"] else "H"))
    print("NE_DEGIL_YAZIYOR:" + ("E" if "bu dönem için önerilen ders listesi değildir" in o["metin"] else "H"))
    # Uyarıdaki düğme dönem diyaloğunu açıyor mu?
    pg.click("#donemUyariAc"); pg.wait_for_timeout(700)
    print("DIYALOG_ACILDI:" + ("E" if pg.query_selector("dialog[open]") else "H"))
    pg.evaluate("""() => { const d = document.querySelector('dialog[open]');
      const b = [...d.querySelectorAll('button')].find(x => x.textContent.trim()==='1');
      if (b) b.click(); }""")
    pg.wait_for_timeout(600)
    pg.evaluate("""() => { const d = document.querySelector('dialog[open]');
      if (!d) return; const b = [...d.querySelectorAll('button')].find(
        x => /kaydet/i.test(x.textContent)); if (b) b.click(); }""")
    pg.wait_for_timeout(5000)
    s = pg.evaluate(DURUM)
    print("SONRA_UYARI:" + ("E" if s["uyari"] else "H"))
    print("SONRA_DONEM:" + str(s["donem"]))
    print("SONRA_MOD_SAYISI:" + str(s["modSayisi"]))
    b.close()
h.shutdown()
'''


def test_UCTAN_UCA_donem_bilinmiyor_uyarisi_ve_cikisi(tmp_path, monkeypatch):
    """★★ Tarayıcıda: dönem yokken uyarı çıkıyor, ölçülen dağılımı yazıyor,
    boş kip kutusu çizilmiyor; uyarıdaki düğme dönem diyaloğunu açıyor ve
    dönem seçilince uyarı kayboluyor, kip açılıyor."""
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
                       text=True, timeout=180)
    if r.returncode != 0:
        pytest.fail(r.stderr[-1500:])
    c = dict(s.split(":", 1) for s in r.stdout.strip().splitlines()
             if ":" in s and s.split(":", 1)[0].isupper())
    assert c.get("ONCE_DONEM_SAYISI") == "2", "test kurulumu bozuk: iki dönem olmalı"
    assert c["ONCE_UYARI"] == "E", "dönem yokken uyarı çıkmıyor"
    assert c["SAYI_YAZIYOR"] == "E", "dönem başına sayı yazmıyor"
    assert c["NE_DEGIL_YAZIYOR"] == "E", "'öneri değil' uyarısı yok"
    assert c["ONCE_MOD_YUKSEKLIK"] == "0", "boş kip kutusu hâlâ çiziliyor"
    assert c["DIYALOG_ACILDI"] == "E", "uyarıdaki düğme diyaloğu açmıyor"
    assert c["SONRA_DONEM"] == "1", "dönem kaydedilmedi"
    assert c["SONRA_UYARI"] == "H", "dönem seçildi ama uyarı duruyor"
    assert int(c["SONRA_MOD_SAYISI"]) == 2, "kip açılmadı"
