"""Boş saate tıklayınca TAM havuzdan ders gösterme + "DEPAR" kip adı.

Kullanıcı isteği 27.08.2026: *"x.dönem + alttan da seçilse belli bir saate
tıklayınca o saatte seçilebilecek bütün dersleri göstersin ve tüm adaylar
seçeneğinin ismi Depar olsun"*.

★ Asıl davranış TARAYICIDA doğrulanıyor (aşağıda): "x.dönem + alttan"
kipindeyken boş saate tıklayınca, o kipte OLMAYAN bir üst-dönem dersi de
listede çıkmalı. Kaynak araması bunu kanıtlayamaz — bu yüzden gerçek
tıklama akışı koşuluyor.
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import ui as UI


# ============================================== 1. kip adı DEPAR
def test_tum_adaylar_kipi_DEPAR_adini_aliyor():
    """'Tüm adaylar' → aracın adı. `_modes`'un ürettiği ilk kipin etiketi."""
    hepsi = {"key": "all", "label": UI.AD_KISA, "note": "",
             "candidates": [1], "schedules": [{"picks": []}]}
    term = {"key": "term", "label": "5. dönem + alttan", "note": "",
            "candidates": [1], "schedules": [{"picks": []}]}
    modes = UI._modes(hepsi, term)
    tam = next(m for m in modes if m["key"] == "all")
    assert tam["label"] == "DEPAR"


def test_kip_etiketi_ad_degisince_degisiyor(monkeypatch):
    """★ Etiket `AD_KISA`'dan geliyor; ad değişirse kip adı da değişmeli —
    yoksa aracın adı DEPAR, kipin adı eski kalırdı (iki kaynak)."""
    # ⚠️ AD_ACILIM de tutarlı patchlenmeli: `render` açılımı kısaltmadan
    # türetiyor, uymayan çift `ValueError` veriyor (bkz. test_ad).
    monkeypatch.setattr(UI, "AD_KISA", "DESA")
    monkeypatch.setattr(UI, "AD_ACILIM", "Ders Seçim Aracı")
    html = UI.render({"schedules": [], "candidates": [], "donem": 0})
    assert 'label:"DESA"' in html
    assert 'label:"Tüm adaylar"' not in html


def test_client_fallback_placeholder_kullaniyor():
    """Şablonda elle 'Tüm adaylar' kalmamalı — tek kaynak `__AD_KISA__`."""
    t = UI._TEMPLATE
    assert "Tüm adaylar" not in t
    assert 'label:"__AD_KISA__"' in t


# ============================================== 2. slotDialog TAM havuzdan
def test_slotDialog_TAM_havuzu_geziyor():
    """★★ Kritik: aktif kipin `M().candidates`'ı değil, `DATA.candidates`
    (tam havuz) geziliyor. Aksi hâlde 'x.dönem+alttan' kipinde boş saate
    tıklayınca yalnız o dönemin dersleri çıkardı."""
    src = open(UI.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
    govde = re.search(r"function slotDialog\(day, min\)\{.*?\n\}", src, re.S)
    assert govde, "slotDialog bulunamadı"
    g = govde.group(0)
    assert "for(const cand of (DATA.candidates || []))" in g, \
        "tam havuz gezilmiyor"
    assert "üst dönem" in g, "kip dışı ders işaretlenmiyor"


def test_kip_disi_secim_SESSIZCE_dusmuyor():
    """★ `choose`/`picks`/`sectionOf` aktif kipte olmayan dersi de çözmeli;
    yoksa üst-dönem dersine tıklamak hiçbir şey yapmazdı (sessiz sıfır)."""
    src = open(UI.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
    assert "const candOf = (course) => CAND[course] || TUM_CAND()[course];" in src
    # Üç yol da tam havuza düşüyor.
    assert "const cand = candOf(course), sec = sectionOf(course, crn);" in src
    assert "candOf(x.course)" in src            # picks()
    assert "(candOf(course)?.sections" in src   # sectionOf


# ============================================== 3. TARAYICIDA uçtan uca
_CANLI = '''
import sys, tempfile, threading, time, os
from pathlib import Path
sys.path.insert(0, os.environ["ITUCAP_SRC"])
_T=Path(tempfile.mkdtemp()); (_T/"config").mkdir(); (_T/"data").mkdir()
(_T/"config"/"settings.toml").write_text(
    '[student]\\nanadal_program="HTAE"\\nsecond_kind="yok"\\ndonem=1\\n', encoding="utf-8")
import itucap.config as config
config.ROOT=_T; config.DATA_DIR=_T/"data"
config.REF_DB=_T/"data"/"reference.sqlite3"; config.USER_DB=_T/"data"/"user.sqlite3"
from itucap import db
con=db.connect(config.REF_DB,"schema.sql")
con.execute("INSERT INTO program(code,name,level) VALUES ('HTAE','H','LS')")
# 1. dönem dersi ve 6. dönem dersi — ikisi de AYNI saatte (Pzt 09:00) açık.
con.execute("INSERT INTO course(code,name,credits,ects) VALUES ('AAA 101E','Birinci',3,4)")
con.execute("INSERT INTO course(code,name,credits,ects) VALUES ('ZZZ 601E','Altinci',3,4)")
con.execute("INSERT INTO plan(id,program_code,plan_type,title,source) VALUES (1,'HTAE','lisans','x','obs')")
con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,position,term_no) VALUES (1,'REQUIRED','AAA 101E',0,1)")
con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,position,term_no) VALUES (1,'REQUIRED','ZZZ 601E',1,6)")
for crn,code in (("100","AAA 101E"),("600","ZZZ 601E")):
    con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled) VALUES (?,?,40,0)",(crn,code))
    con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES (?,'HTAE')",(crn,))
    con.execute("INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min) VALUES (?,1,540,630)",(crn,))
con.commit(); con.close(); db.connect(config.USER_DB,"schema_user.sql").close()
from itucap import server
st=server.State(label="ben")
h=server.build(st,host="127.0.0.1",port=0); P=h.server_address[1]
threading.Thread(target=h.serve_forever,daemon=True).start(); time.sleep(0.4)
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(viewport={"width":1400,"height":950})
    pg.goto(f"http://127.0.0.1:{P}/", wait_until="networkidle", timeout=30000)
    pg.wait_for_timeout(800)
    # "1. dönem + alttan" kipine geç (varsayılan zaten o olabilir; garantiye al)
    kipler = pg.eval_on_selector_all("#modes .modebtn", "es=>es.map(e=>e.textContent)")
    for i,ad in enumerate(kipler):
        if "dönem" in ad:
            pg.eval_on_selector_all("#modes .modebtn", f"es=>es[{i}].click()")
            break
    pg.wait_for_timeout(500)
    # Bu kipte ZZZ 601E aday DEĞİL (6. dönem, biz 1. dönemdeyiz).
    kip_adaylari = pg.evaluate("(M().candidates||[]).map(c=>c.course)")
    # Boş bir Pzt 09:00 hücresine tıkla.
    hucre = pg.query_selector('td.free[data-day="1"][data-min="540"]') or \
            pg.query_selector('td.free[data-day="1"]')
    hucre.click()
    pg.wait_for_timeout(500)
    metin = pg.inner_text("#detailBody")
    print("KIP_ADAYLARI:" + ",".join(kip_adaylari))
    print("ZZZ_KIPTE:" + ("E" if "ZZZ 601E" in kip_adaylari else "H"))
    print("ZZZ_LISTEDE:" + ("E" if "ZZZ 601E" in metin else "H"))
    print("UST_DONEM_NOTU:" + ("E" if "üst dönem" in metin else "H"))
    b.close()
h.shutdown()
'''


def test_UST_DONEM_dersi_bos_saatte_GORUNUYOR(tmp_path, monkeypatch):
    """★★ Uçtan uca: 1. dönem kipindeyken boş saate tıkla, 6. dönem dersi
    'üst dönem' notuyla listede çıksın."""
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
                       text=True, timeout=120)
    if r.returncode != 0:
        pytest.fail(r.stderr[-1000:])
    cikti = dict(s.split(":", 1) for s in r.stdout.strip().splitlines()
                 if ":" in s and s.split(":", 1)[0].isupper())
    assert cikti.get("ZZZ_KIPTE") == "H", "test kurulumu bozuk: ZZZ kipte olmamalı"
    assert cikti.get("ZZZ_LISTEDE") == "E", "üst dönem dersi boş saatte görünmüyor"
    assert cikti.get("UST_DONEM_NOTU") == "E", "üst dönem notu yok"
