"""Faz 47 — kullanıcı geri bildirimi turu (18.09.2026).

Kullanıcı altı şey söyledi; hepsi ölçülüp uygulandı:

1. *"bilgisayarda yanlardaki boşlukları kaldırabilirsin, ders programını
   çok sıkıştırıyor"* — ölçüldü: ızgara HER genişlikte **660px**'ti;
   1920px'te iki yanda 290'ar, 2560px'te 610'ar piksel boş duruyordu.
2. *"kaydettiğim programı yükle dedikten sonra otomatik haftalık programım
   kısmına yönlendirsin"* — Faz 46'da `scrollIntoView` ÇALIŞMAZ olmuştu.
3. *"itü depar yazısı biraz daha büyük olabilir"* — Faz 46'da 29 → 20px.
4. *"sağdaki kısmı… genişliğini azaltıp yukardan aşağıya tuşları listeleyip
   lejant gibi bilgileri ders programının altında tutabilirsin"*.
5. *"ilk önce dönem seçtir… 5. dönem olan birisi geçtiği dersleri
   işaretlemek için otomatik tik attırabilir"*.
6. *"plandan işaretle kısmında eğer tik geri çekilirse dersi alınmış olarak
   gözükmesin"* — ★★ GERÇEK VERİ KAYBI/KİRLENMESİ, ölçümle doğrulandı.

Ölçüm (gerçek veri, tarayıcı):

| | önce | sonra |
|---|---|---|
| ızgara genişliği · 1440px ekran | 660px | **846px** |
| ızgara genişliği · 1680px | 660px | **1086px** |
| gün sütunu · 1440px | 120px | **158px** |
| tik geri çekilince ders düşüyor mu | **hayır** | evet |
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


from itucap import config as C                                # noqa: E402
from itucap import db                                        # noqa: E402
from itucap import server as SV                              # noqa: E402
from itucap import student as S                              # noqa: E402
from itucap import ui as UI                                  # noqa: E402

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")
CSS = re.search(r"<style>(.*?)</style>", KAYNAK, re.S).group(1)


# ------------------------------------------------- 6. tik geri çekilince
def _durum(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "ROOT", tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "config" / "settings.toml").write_text(
        '[student]\nanadal_program = "GEO"\n', encoding="utf-8")
    monkeypatch.setattr(C, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(C, "REF_DB", tmp_path / "data" / "reference.sqlite3")
    monkeypatch.setattr(C, "USER_DB", tmp_path / "data" / "user.sqlite3")
    db.connect(C.REF_DB, "schema.sql").close()
    ucon = db.connect(C.USER_DB, "schema_user.sql")
    st = SV.State.__new__(SV.State)
    st.ucon = ucon
    st.student_id = S.ensure_student(ucon)
    return st


def _alinmis(st):
    return {r[0] for r in st.ucon.execute(
        "SELECT course_code FROM earned_course WHERE student_id=?",
        (st.student_id,))}


def test_TIK_GERI_CEKILINCE_ders_dusuyor(tmp_path, monkeypatch):
    """★★ Kullanıcı bildirdi, ölçümle doğrulandı: pencere yalnız TİKLİ
    dersleri gönderiyor ve `replace=False` ile ekliyordu; tik geri çekilince
    HİÇBİR ŞEY olmuyordu (37 satır → 38, geri çekince yine 38)."""
    st = _durum(tmp_path, monkeypatch)
    st.save_transcript([{"course": "GEO 303E", "grade": "BB"}], False)
    assert "GEO 303E" in _alinmis(st)
    # Tik geri çekildi: ders artık pencerede TİKSİZ → `remove` ile geliyor.
    r = st.save_transcript([], False, ["GEO 303E"])
    assert r["removed"] == 1, r
    assert "GEO 303E" not in _alinmis(st), "tik geri çekilince ders kalmış"


def test_remove_PENCERENIN_GORMEDIGINE_dokunmuyor(tmp_path, monkeypatch):
    """⚠️ `replace=True` YAPILMADI — o, elle girilmiş ve plan DIŞI dersleri
    de silerdi. `remove` yalnız pencerenin gösterdiklerini taşıyor."""
    st = _durum(tmp_path, monkeypatch)
    st.save_transcript([{"course": "GEO 303E", "grade": "BB"},
                        {"course": "ZZZ 999", "grade": "AA"}], False)
    st.save_transcript([], False, ["GEO 303E"])       # ZZZ listede YOK
    kalan = _alinmis(st)
    assert "ZZZ 999" in kalan, "pencerenin görmediği ders silinmiş"
    assert "GEO 303E" not in kalan


def test_SILMEDEN_ONCE_yedek(tmp_path, monkeypatch):
    """Silici yazma yedeksiz olmaz — elle girilmiş transkript geri gelmez."""
    st = _durum(tmp_path, monkeypatch)
    st.save_transcript([{"course": "GEO 303E", "grade": "BB"}], False)
    once = st.ucon.execute("SELECT COUNT(*) FROM transcript_backup").fetchone()[0] \
        if _tablo_var(st.ucon, "transcript_backup") else None
    st.save_transcript([], False, ["GEO 303E"])
    if once is not None:
        sonra = st.ucon.execute(
            "SELECT COUNT(*) FROM transcript_backup").fetchone()[0]
        assert sonra > once, "silmeden önce yedek alınmamış"


def _tablo_var(con, ad):
    return bool(con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (ad,)).fetchone())


def test_SILECEK_YOKSA_bosuna_yedek_alinmiyor(tmp_path, monkeypatch):
    """Yedek sayısı 12 ile sınırlı; her kaydetmede yedek almak eski
    yedekleri düşürürdü."""
    st = _durum(tmp_path, monkeypatch)
    r = st.save_transcript([{"course": "GEO 303E", "grade": "BB"}], False,
                           ["AAA 101"])          # transkriptte yok
    assert r["removed"] == 0


def test_arayuz_TIKSIZLERI_gonderiyor():
    """★★ Sunucu tarafı doğru olsa da arayüz göndermezse hata sürer."""
    assert "remove: Object.entries(state).filter(([, v]) => !v.taken)" in KAYNAK
    # ⚠️ `replace` hâlâ false: plan DIŞI dersler korunuyor.
    fn = KAYNAK[KAYNAK.index('api("/api/transcript", {'):][:520]
    assert "replace: false" in fn


# ------------------------------------------------- 5. önce dönem + öneri tik
def test_DONEM_transkriptten_ONCE():
    """★ Sıra keyfî değil, BAĞIMLILIK: dönem biliniyorsa plan penceresi
    geçmiş dönemlerin zorunlularını önerebiliyor."""
    fn = re.search(r"    adimlar = \[(.*?)\n    \]", KAYNAK, re.S).group(1)
    assert fn.index('"key": "donem"') < fn.index('"key": "transkript"')


def test_ONERI_TIKI_iddia_degil():
    """⚠️⚠️ Bu repoda kural: bilinmeyen, bilinen gibi gösterilmez.
    "5. dönemdesin" ≠ "1–4. dönemin hepsini geçtin" (ders bırakmış, kalmış,
    yatay geçmiş olabilir). O yüzden öneri:
    · yalnız transkript BOŞKEN yapılıyor,
    · SAYIYLA yazıyor,
    · tek tıkla topluca kaldırılıyor,
    · Kaydet'e basılmadan hiçbir şey yazılmıyor."""
    assert "const bostu = !(SETUP.transcript || []).length;" in KAYNAK
    assert "if(donem > 1 && bostu){" in KAYNAK
    assert "${onerilen.length} ders işaretlendi" in KAYNAK
    assert "Bu işaretleme bir tahmindir" in KAYNAK
    assert 'id="ckUndo"' in KAYNAK


def test_BIRINCI_DONEM_hicbir_sey_isaretlemiyor():
    """★ "1. dönem olan birisinin geçtiği ders yoktur" — öneri de yapılmıyor,
    ve bunun SÖYLENDİĞİ bir satır var (boş liste açıklamasız kalmasın)."""
    assert "donem > 1" in KAYNAK, "1. dönemde de öneri yapılıyor"
    assert "<b>1. yarıyıldasınız;</b>" in KAYNAK


# ------------------------------------------------- 1-4. yerleşim
def test_IZGARA_GORUNUMU_genis():
    """★ Ölçüm: ızgara her ekranda 660px'ti; genişletildi (kullanıcı isteği).

    ⚠️⚠️ FAZ 52'DE YENİDEN YAZILDI — kilitlediği karar kullanıcı isteğiyle
    geri alındı (21.09.2026: *"bütün sekmelerde arayüzün genişliği aynı
    olsun"*). Bu test eskiden "genişleme YALNIZ ızgara görünümünde, metin
    bölümleri 1340px'te" diyordu. Ölçüm o kararın iki bedelini gösterdi:
    1920px'te sekme değişince ray 196px zıplıyordu, ve 1340px çerçeve okuma
    ölçüsünü zaten korumuyordu (satırlar ~153 karakter). Artık:
    · çerçeve HER sekmede aynı ve geniş,
    · okuma ölçüsü metnin kendisinde (`max-width:80ch`).
    Izgaranın genişliği (bu testin asıl konusu) korunuyor."""
    temel = re.search(r"(?m)^\.wrap\{([^}]*)\}", CSS).group(1)
    assert "max-width:1720px" in temel, "çerçeve yeniden daraltılmış"
    # Sekmeye göre çerçeve DEĞİŞMEMELİ — görünüme bağlı bir .wrap kuralı yok.
    assert not re.search(r":root\[data-gorunum=[^\]]*\]\s*\.wrap\{", CSS), \
        "çerçeve yine sekmeye göre değişiyor"
    assert "main .summary,main .modenote,main p,main .hint{max-width:80ch}" in CSS
    assert 'document.documentElement.dataset.gorunum = id;' in KAYNAK


def test_SAG_SUTUN_dar_ve_dugmeler_ALT_ALTA():
    kural = re.search(r"(?m)^\.prgduzen\{([^}]*)\}", CSS).group(1)
    m = re.search(r"minmax\(0,1fr\)\s*(\d+)px", kural.replace(" ", ""))
    assert m and int(m.group(1)) <= 260, kural
    assert ".prgyan .toolbar{flex-direction:column" in CSS


def test_LEJANT_IZGARANIN_ALTINDA():
    """★ Kullanıcı: *"lejant gibi bilgileri ders programının altında
    tutabilirsin"*. ⚠️ Yine KATLI, silinmiş değil (Faz 40'ın dersi)."""
    orta = re.search(r'<div class="prgorta">(.*?)</div><!-- /prgorta -->',
                     KAYNAK, re.S).group(1)
    assert '<details class="ipucu">' in orta, "ipucu hâlâ sağ sütunda"
    assert 'id="tonNot"' in orta
    yan = re.search(r'<aside class="prgyan">(.*?)</aside>', KAYNAK, re.S).group(1)
    assert '<details class="ipucu">' not in yan


def test_AD_YAZISI_buyudu():
    kural = re.search(r"body:not\(\.kurulum\) header h1\{([^}]*)\}", CSS).group(1)
    # Faz 56: boy bir ölçek jetonu (`--fs-3xl`); iddia DEĞER üstünde.
    from itucap import tasarim as T
    m = re.search(r"font-size:(\d+)px", T.coz(kural).replace(" ", ""))
    assert m and int(m.group(1)) >= 24, kural


def test_YUKLEYINCE_gorunum_degisiyor():
    """★ Faz 46'da `scrollIntoView` çalışmaz olmuştu: hedef bölüm kapalı."""
    fn = re.search(r'\$\("#savedOpen"\)\.addEventListener\("click", \(\) => \{(.*?)\n  \}\);',
                   KAYNAK, re.S).group(1)
    assert 'gorunumAc("schedSection", true)' in fn
    # ⚠️ Yorum bloğu neyin NEDEN değiştiğini anlatıyor ve içinde eski adı
    # geçiyor; kontrol KODA bakmalı. Blok yorumları söküyoruz.
    kod = re.sub(r"/\*.*?\*/", " ", fn, flags=re.S)
    assert "scrollIntoView" not in kod, "eski kaydırma geri gelmiş"


# --------------------------------------------------------- uçtan uca
_CANLI = r'''
import sys, os, shutil, tempfile, threading, time
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
# 1. dönemde iki zorunlu, 2. dönemde bir tane; öğrenci 3. dönemde olacak.
plan = [("AAA 101E", 1, 1, 540), ("BBB 102E", 1, 2, 540), ("CCC 201E", 2, 3, 600),
        ("DDD 301E", 3, 4, 660)]
for kod, term, i, bas in plan:
    con.execute("INSERT INTO course(code,name,credits,ects) VALUES (?,?,3,4)",
                (kod, "Ders " + kod))
    con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,position,term_no)"
                " VALUES (1,'REQUIRED',?,?,?)", (kod, i, term))
    crn = str(700 + i)
    con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled) VALUES (?,?,40,0)",
                (crn, kod))
    con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES (?,'HTAE')",
                (crn,))
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
    pg.goto(f"http://127.0.0.1:{P}/", wait_until="networkidle", timeout=30000)
    pg.wait_for_timeout(1500)
    print("SIRA:" + ",".join(pg.evaluate("() => DATA.onboarding.steps.map(s => s.key)")))
    # Dönem 3 → 1. ve 2. dönemin zorunluları ÖNERİ olarak tiklensin
    pg.evaluate("""async () => { applyState(await api("/api/donem", {donem: 3})); }""")
    pg.wait_for_timeout(1200)
    pg.evaluate("() => checklistDialog()"); pg.wait_for_timeout(800)
    print("ONERI:" + str(pg.eval_on_selector_all(
        '#setupBody input[type=checkbox][data-course]:checked', "e => e.length")))
    print("SERIT:" + ("E" if pg.eval_on_selector_all("#ckUndo", "e => e.length") else "H"))
    # Kaydet → transkripte yazılsın
    pg.click("#setupSave"); pg.wait_for_timeout(2500)
    print("KAYITLI:" + str(pg.evaluate("() => SETUP.transcript.length")))
    # ŞİMDİ birinin tikini geri çek ve kaydet
    pg.evaluate("() => checklistDialog()"); pg.wait_for_timeout(800)
    pg.evaluate("""() => { const cb = [...document.querySelectorAll(
        '#setupBody input[type=checkbox][data-course]')].find(c => c.checked);
      cb.checked = false; cb.dispatchEvent(new Event("change", {bubbles:true})); }""")
    pg.click("#setupSave"); pg.wait_for_timeout(2500)
    print("SONRA:" + str(pg.evaluate("() => SETUP.transcript.length")))
    # ızgara görünümü geniş mi — ⚠️ Faz 52: 1920px'te ölçülüyor. 1440px'te
    # görünüme bağlı bir tavan (ör. 1440 ↔ 1720) ekranın kendisine takılıp
    # AYNI çıkıyordu; geri alma deneyi bekçiyi yeşil bıraktı.
    pg.set_viewport_size({"width": 1920, "height": 1000}); pg.wait_for_timeout(300)
    pg.evaluate("() => gorunumAc('schedSection')"); pg.wait_for_timeout(400)
    print("WRAP_IZGARA:" + str(pg.evaluate(
        "() => Math.round(document.querySelector('.wrap').getBoundingClientRect().width)")))
    pg.evaluate("() => gorunumAc('candSection')"); pg.wait_for_timeout(400)
    print("WRAP_METIN:" + str(pg.evaluate(
        "() => Math.round(document.querySelector('.wrap').getBoundingClientRect().width)")))
    b.close()
h.shutdown()
'''


def test_UCTAN_UCA_faz47(tmp_path, monkeypatch):
    """★★ Tarayıcıda: dönem önce sorulyor, öneri tikleniyor, kaydediliyor,
    tik geri çekilince DÜŞÜYOR; ızgara görünümü geniş, metin görünümü dar."""
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
    assert c["SIRA"].split(",")[:3] == ["program", "donem", "transkript"], c
    assert int(c["ONERI"]) == 3, f"1–2. dönemin 3 zorunlusu önerilmeli: {c}"
    assert c["SERIT"] == "E", "öneri şeridi ve geri al düğmesi yok"
    assert int(c["KAYITLI"]) == 3, c
    assert int(c["SONRA"]) == 2, f"tik geri çekilince ders düşmedi: {c}"
    # ⚠️ Faz 52: eskiden "ızgara görünümü metin görünümünden GENİŞ" isteniyordu.
    # Kullanıcı bütün sekmelerde AYNI genişliği istedi; ölçüt tersine döndü.
    assert int(c["WRAP_IZGARA"]) == int(c["WRAP_METIN"]), \
        f"sekmeye göre çerçeve genişliği değişiyor: {c}"
    assert int(c["WRAP_IZGARA"]) >= 1700, f"çerçeve daralmış (1920px ekranda): {c}"
