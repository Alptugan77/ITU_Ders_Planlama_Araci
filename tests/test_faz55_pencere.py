"""Faz 55 — pencerenin DIŞINA tıklayınca kapansın (kullanıcı 23.09.2026:
*"sitenin üzerine açılan sekmelerde arka tarafa yani normal arayüze tıklayınca
oraya geçip açılan kısım kapansın"*).

Üç pencere de kipli `<dialog>`; arka plan tıklamayı yutuyordu, kapatmanın
tek yolu "Kapat" ya da Esc idi. Artık perdeye tıklamak pencereyi kapatıyor.

★★ Faz 57 (kullanıcı 23.09.2026: *"just close the window do not interact
with background"*): Faz 55'te tıklama kapattıktan sonra ALTINDAKİ yere de
geçiyordu (ray bağlantısı, ızgaradaki başka ders). Kapatmak için tıklanan
yer çoğu zaman rastgeleydi ve arkada bir şey açılıyordu. Artık dış tıklama
YALNIZ kapatıyor; testler iki yönü de tutuyor: kapandı VE arkada hiçbir şey
olmadı.

⚠️ Üç tuzak, üçü de uçtan uca test ediliyor:
* pencerede başlayıp dışarıda biten sürükleme (metin seçerken) kapatmamalı;
* pencerenin kendi kenarına tıklamak kapatmamalı;
* kaydedilmemiş değişiklik varken ilk dış tıklama işi SİLMEMELİ — uyarıyor.
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


def _blok():
    return KAYNAK[KAYNAK.index("(function pencereDisinaTiklama(){"):KAYNAK.index("\nboot();\n</script>")]


def test_UC_PENCERENIN_hepsine_bagli():
    b = _blok()
    assert 'document.querySelectorAll("dialog").forEach(d =>' in b
    # Sayfadaki kipli pencereler bu üçü; yenisi eklenirse de kapsanıyor.
    assert set(re.findall(r'<dialog id="(\w+)"', KAYNAK)) == {"detail", "setup", "basvuruDlg"}


def test_SURUKLEME_ve_KENAR_kapatmiyor():
    b = _blok()
    assert "basla = (e.target === d && disarida(d, e)) ? d : null;" in b
    assert "const gecerli = basla === d && e.target === d && disarida(d, e);" in b


def test_KAYDEDILMEMIS_is_SESSIZCE_silinmiyor():
    b = _blok()
    assert 'if(d.id === "setup" && SETUP_KIRLI && !uyarildi){' in b
    assert "SETUP_KIRLI = false;" in KAYNAK[KAYNAK.index("function openSetup("):][:200]


def test_DIS_TIKLAMA_yalniz_KAPATIYOR():
    """Faz 57 — tıklama altındaki öğeye İLETİLMİYOR ve belgeye yayılmıyor."""
    b = re.sub(r"/\*.*?\*/", " ", _blok(), flags=re.S)
    assert "elementFromPoint" not in b and "dispatchEvent" not in b, \
        "dış tıklama yine arkaya iletiliyor"
    assert b.index("e.stopPropagation();") < b.index("d.close();")


_CANLI = r'''
import sys, tempfile, threading, time, os
from pathlib import Path
sys.path.insert(0, os.environ["ITUCAP_SRC"])
_T = Path(tempfile.mkdtemp()); (_T/"config").mkdir(); (_T/"data").mkdir()
(_T/"config"/"settings.toml").write_text(
    '[student]\nanadal_program="HTAE"\nsecond_kind="yok"\ndonem = 1\n', encoding="utf-8")
import itucap.config as config
config.ROOT = _T; config.DATA_DIR = _T/"data"
config.REF_DB = _T/"data"/"reference.sqlite3"; config.USER_DB = _T/"data"/"user.sqlite3"
from itucap import db
con = db.connect(config.REF_DB, "schema.sql")
con.execute("INSERT INTO program(code,name,level) VALUES ('HTAE','H','LS')")
con.execute("INSERT INTO plan(id,program_code,plan_type,title,source)"
            " VALUES (1,'HTAE','lisans','x','obs')")
# 1. dönemde AAA + BBB; 3. dönemde CCC (yalnız DEPAR kipinde aday).
plan = [("AAA 101E", 1, [("300", 1, 540, 660), ("301", 2, 810, 930), ("302", 3, 870, 990)]),
        ("BBB 102E", 1, [("400", 2, 810, 930)]),
        ("CCC 301E", 3, [("500", 4, 540, 660), ("501", 5, 870, 990)])]
for i, (kod, donem, subeler) in enumerate(plan):
    con.execute("INSERT INTO course(code,name,credits,ects) VALUES (?,?,3,4)",
                (kod, "Ders " + kod))
    con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,position,term_no)"
                " VALUES (1,'REQUIRED',?,?,?)", (kod, i, donem))
    for crn, gun, bas, bit in subeler:
        con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled)"
                    " VALUES (?,?,40,0)", (crn, kod))
        con.execute("INSERT INTO lesson_allowed_program(crn,program_code)"
                    " VALUES (?,'HTAE')", (crn,))
        con.execute("INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min)"
                    " VALUES (?,?,?,?)", (crn, gun, bas, bit))
con.commit(); con.close(); db.connect(config.USER_DB, "schema_user.sql").close()

from itucap import server
st = server.State(label="ben")
h = server.build(st, host="127.0.0.1", port=0); P = h.server_address[1]
threading.Thread(target=h.serve_forever, daemon=True).start(); time.sleep(0.4)

from playwright.sync_api import sync_playwright
SEL = "() => sel.map(x => x.course + '@' + x.crn).sort().join(',')"
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width":1400,"height":1000})
    pg.goto(f"http://127.0.0.1:{P}/", wait_until="networkidle", timeout=30000)
    pg.wait_for_timeout(1500)
    pg.evaluate("() => { resetTo(0); gorunumAc('schedSection'); }"); pg.wait_for_timeout(300)
    acik = "() => document.querySelector('dialog[open]') ? document.querySelector('dialog[open]').id : '-'"
    ray = pg.eval_on_selector('a[data-gorunum="candSection"]',
        "e => { const r = e.getBoundingClientRect(); return [r.x + r.width/2, r.y + r.height/2]; }")
    # 1) Perdede raydaki bağlantının üstüne tıkla → kapanır VE oraya gider.
    pg.evaluate("() => courseDialog('AAA 101E')"); pg.wait_for_timeout(300)
    print("ACIK1:" + pg.evaluate(acik))
    pg.mouse.click(*ray); pg.wait_for_timeout(400)
    print("RAY:" + pg.evaluate(acik) + "|" + pg.evaluate("() => document.documentElement.dataset.gorunum"))
    # 2) Izgaradaki BAŞKA dersin üstüne tıkla → o dersin penceresi açılır.
    pg.evaluate("() => gorunumAc('schedSection')"); pg.wait_for_timeout(300)
    # ⚠️ Faz 56: hedef blok 1000px'lik pencerede y≈988'deydi — kenara 12px.
    # Tasarım sistemi v2 üst çubuğu ve karşılama kartını 13px uzatınca blok
    # ekranın DIŞINA düştü ve tıklama hiçbir şeye gitmedi. Test DAVRANIŞI
    # ölçüyor, yerleşimi değil: blok önce görünür yere getiriliyor.
    pg.eval_on_selector('#grid .blk[data-course="AAA 101E"]',
        "e => e.scrollIntoView({block: 'center'})"); pg.wait_for_timeout(200)
    aaa = pg.eval_on_selector('#grid .blk[data-course="AAA 101E"]',
        "e => { const r = e.getBoundingClientRect(); return [r.x + 8, r.y + 8]; }")
    pg.evaluate("() => courseDialog('BBB 102E')"); pg.wait_for_timeout(300)
    kutu = pg.eval_on_selector("#detail", "e => { const r = e.getBoundingClientRect(); return [r.left, r.right]; }")
    print("HEDEF_DISARIDA:" + str(not (kutu[0] <= aaa[0] <= kutu[1])))
    pg.mouse.click(*aaa); pg.wait_for_timeout(400)
    print("IZGARA:" + pg.evaluate(acik) + "|" + pg.evaluate("() => (document.querySelector('#detailBody h2')||{}).textContent || ''"))
    pg.evaluate("() => document.querySelector('#detail').close()")
    # 3) İçeride başlayıp dışarıda biten sürükleme → KAPANMAZ.
    pg.evaluate("() => courseDialog('AAA 101E')"); pg.wait_for_timeout(300)
    ic = pg.eval_on_selector("#detailBody h2", "e => { const r = e.getBoundingClientRect(); return [r.x + 5, r.y + 5]; }")
    pg.mouse.move(*ic); pg.mouse.down(); pg.mouse.move(8, 500, steps=5); pg.mouse.up(); pg.wait_for_timeout(300)
    print("SURUKLE:" + pg.evaluate(acik))
    # 4) Kenar (üst şerit) → KAPANMAZ.
    kenar = pg.eval_on_selector("#detail", "e => { const r = e.getBoundingClientRect(); return [r.x + r.width/2, r.y + 2]; }")
    pg.mouse.click(*kenar); pg.wait_for_timeout(300)
    print("KENAR:" + pg.evaluate(acik))
    pg.evaluate("() => document.querySelector('#detail').close()")
    # 5) Kaydedilmemiş değişiklik: ilk dış tıklama uyarır, ikincisi kapatır.
    pg.evaluate("() => tercihDialog()"); pg.wait_for_timeout(400)
    pg.click("#fKampus"); pg.wait_for_timeout(100)
    pg.mouse.click(8, 500); pg.wait_for_timeout(300)
    print("KIRLI1:" + pg.evaluate(acik) + "|" + pg.eval_on_selector("#setupMsg", "e => e.textContent"))
    pg.mouse.click(8, 500); pg.wait_for_timeout(300)
    print("KIRLI2:" + pg.evaluate(acik))
    # 6) Değişiklik yoksa tek tıklama yeter.
    pg.evaluate("() => termDialog()"); pg.wait_for_timeout(400)
    pg.mouse.click(8, 500); pg.wait_for_timeout(300)
    print("TEMIZ:" + pg.evaluate(acik))
    # 7) Telefon: kenardaki 16px'lik perde de çalışıyor.
    pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(300)
    pg.evaluate("() => courseDialog('AAA 101E')"); pg.wait_for_timeout(300)
    pg.mouse.click(5, 420); pg.wait_for_timeout(300)
    print("TELEFON:" + pg.evaluate(acik))
    b.close()
h.shutdown()
'''


def test_UCTAN_UCA_disari_tiklama(tmp_path, monkeypatch):
    if not shutil.which("node"):
        pytest.skip("node yok")
    try:
        import playwright  # noqa: F401
    except ImportError:
        pytest.skip("playwright yok")
    monkeypatch.setenv("ITUCAP_SRC", str(Path(UI.__file__).resolve().parents[1]))
    betik = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, dir=str(tmp_path))
    betik.write(_CANLI); betik.close()
    r = subprocess.run([sys.executable, betik.name], capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        pytest.fail(r.stderr[-2000:])
    c = dict(s.split(":", 1) for s in r.stdout.strip().splitlines()
             if ":" in s and s.split(":", 1)[0].isupper())
    assert c["ACIK1"] == "detail", c
    # Faz 57: kapanıyor ama raydaki bağlantı ÇALIŞMIYOR — görünüm aynı kalıyor.
    assert c["RAY"] == "-|schedSection", f"dışarı tıklama kapatmadı ya da arkaya geçti: {c['RAY']}"
    assert c["HEDEF_DISARIDA"] == "True", "deney düzeneği: hedef blok pencerenin altında kaldı"
    # Faz 57: ızgaradaki başka dersin penceresi AÇILMIYOR.
    assert c["IZGARA"].startswith("-|"), f"tıklama ızgaraya geçti: {c['IZGARA']}"
    assert c["SURUKLE"] == "detail", "içeriden başlayan sürükleme pencereyi kapattı"
    assert c["KENAR"] == "detail", "pencerenin kenarı kapattı"
    assert c["KIRLI1"].startswith("setup|Kaydedilmemiş"), f"kaydedilmemiş iş sessizce gitti: {c['KIRLI1']}"
    assert c["KIRLI2"] == "-", c
    assert c["TEMIZ"] == "-", c
    assert c["TELEFON"] == "-", c
