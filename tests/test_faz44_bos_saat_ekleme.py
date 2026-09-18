"""Faz 44 — boş saatte "eklenebilir" ile "takas" ayrıldı.

Kullanıcı 17.09.2026: *"x.dönem + alttan kısmında takvime tıklayıp ekstra
ders eklenemiyor"*. Ölçüldü, haklıydı — ama sebep sandığım yerde değildi.

Ölçüm (gerçek veri, tarayıcıda):

| | "N. dönem + alttan" | DEPAR |
|---|---|---|
| boş hücre | 38 | 56 |
| **yalnız TAKAS sunan hücre** | **27 (%71)** | 24 |
| diyalog tamamen boş | 1 | 32 |
| çakışmadan eklenebilen | 10 | **0** |

Motor yanlış değil: hafta 14 dersle dolu, boş hücreler derslerin ARASINDAKİ
boşluklar, aday şubelerin çoğu 2–3 saatlik ve komşu derse taşıyor. Yanlış
olan SUNUM — "çıkarılır: GEO 321E" notu her satırın içine gömülüydü ve liste
"ekleyebileceğin dersler" gibi duruyordu.

⚠️ İlk teşhisim YANLIŞTI: Faz 39'un ızgara kırpmasının eklenebilir saatleri
gizlediğini sandım, ona göre kod yazdım. Ölçünce o dersin (BHB 201E) 17:30'da
olduğu, yani görünür aralıkta kaldığı çıktı; yazdığım kodu geri aldım. Teşhis
ölçümden önce gelirse, düzeltme hatanın yanından geçiyor.
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
SLOT = re.search(r"function slotDialog\(day, min\)\{(.*?)\n\}\n", KAYNAK, re.S).group(1)


def test_secenek_KAC_DERS_DUSURDUGUNU_tasiyor():
    """Gruplama için satır, düşen ders sayısını da taşımalı — yoksa ayrım
    metin içindeki nota bakmakla yapılırdı."""
    assert "cand.course, drop.length]);" in SLOT, "satır drop sayısını taşımıyor"
    assert "const temiz = (r) => r[3] === 0;" in SLOT


def test_SIGANLAR_ile_TAKASLAR_ayri_gruplarda():
    """★★ Asıl düzeltme: tek karışık liste yerine iki ayrı başlık."""
    assert "buraya sığıyor" in SLOT
    assert SLOT.count("yer açman gerekiyor") >= 2, "takas grubu ayrılmamış"
    # Sığanlar ÖNCE yazılıyor.
    assert SLOT.index("buraya sığıyor") < SLOT.index("yer açman gerekiyor")


def test_HIC_SIGMIYORSA_bu_soyleniyor():
    """⚠️ Proje ilkesi: yapılamayan şey söylenmeli. Kullanıcı 27 hücrede
    tek tek 18 satır okuyup "demek ki ekleyemiyorum" sonucuna varıyordu."""
    assert "Bu saate çakışmadan sığan ders yok" in SLOT
    assert "hicTemiz" in SLOT and "varTakas" in SLOT
    # Sayı dökülüyor (genel uyarı değil).
    assert "${varTakas}" in SLOT


def test_takas_secenekleri_GIZLENMIYOR():
    """⚠️ Takas bazen istenen şeydir ("şunun yerine bunu koy"). Ayrı başlığa
    alınıyor, gizlenmiyor — gizleseydik "bu saatte hiçbir şey yok" sanılırdı."""
    assert "nearX" in SLOT and "restX" in SLOT
    assert "grup(" in SLOT


def test_ILK_TESHIS_geri_alindi():
    """⚠️ Ölçmeden yazdığım `eklenebilirGizli` kodu depoda kalmamalı."""
    assert "eklenebilirGizli" not in KAYNAK
    assert "kacik" not in KAYNAK


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
# AAA: Pzt 09:00-11:00 (öneriye girer)   BBB: Pzt 10:00-12:00 (AAA ile ÇAKIŞIR)
# CCC: Sal 09:00-11:00 (hiçbir şeyle çakışmaz → TEMİZ eklenebilir)
dersler = [("AAA 101E", 1, 540, 660), ("BBB 102E", 1, 600, 720),
           ("CCC 103E", 2, 540, 660)]
for i, (kod, gun, bas, bit) in enumerate(dersler):
    con.execute("INSERT INTO course(code,name,credits,ects) VALUES (?,?,3,4)",
                (kod, "Ders " + kod))
    con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,position,term_no)"
                " VALUES (1,'REQUIRED',?,?,1)", (kod, i))
    crn = str(200 + i)
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
OKU = """() => { const d = document.querySelector('dialog[open]');
  if (!d) return {yok: true};
  return {uyari: (d.querySelector('.note')||{}).innerText || '',
          gruplar: [...d.querySelectorAll('.chipline')].map(c =>
             c.innerText.replace(/\s+/g,' ').trim())}; }"""
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width":1400,"height":1000})
    pg.goto(f"http://127.0.0.1:{P}/", wait_until="networkidle", timeout=30000)
    pg.wait_for_timeout(1500)
    # Yalnız AAA seçili olsun ki BBB takas, CCC temiz olsun.
    pg.evaluate("""() => { sel = [{course:'AAA 101E', crn:'200'}]; render(); }""")
    pg.wait_for_timeout(1200)
    n = pg.evaluate("() => picks().length")
    print("SECILI:" + str(n))
    # Pzt 10:00 → BBB çakışır (takas), CCC başka gün → 'başka saatte sığıyor' olmaz
    hucre = pg.query_selector('#grid td.free[data-day="1"][data-min="600"]') \
         or pg.query_selector('#grid td.free[data-day="1"]')
    hucre.click(); pg.wait_for_timeout(800)
    r = pg.evaluate(OKU)
    print("PZT_UYARI:" + ("E" if "çakışmadan sığan ders yok" in r.get("uyari","") else "H"))
    print("PZT_TAKAS:" + ("E" if any("YER AÇMAN" in g.upper() for g in r.get("gruplar",[])) else "H"))
    pg.evaluate("() => document.querySelector('dialog[open]').close()")
    pg.wait_for_timeout(300)
    # Sal 09:00 → CCC temiz sığar
    h2 = pg.query_selector('#grid td.free[data-day="2"][data-min="540"]') \
      or pg.query_selector('#grid td.free[data-day="2"]')
    h2.click(); pg.wait_for_timeout(800)
    r2 = pg.evaluate(OKU)
    print("SAL_SIGAN:" + ("E" if any("SIĞIYOR" in g.upper() for g in r2.get("gruplar",[])) else "H"))
    print("SAL_UYARI:" + ("E" if "çakışmadan sığan ders yok" in r2.get("uyari","") else "H"))
    # temiz seçeneği ekle
    pg.evaluate("""() => { const d=document.querySelector('dialog[open]');
      d.querySelector('.optlist .opt').click(); }""")
    pg.wait_for_timeout(2500)
    print("SONRA:" + str(pg.evaluate("() => picks().length")))
    b.close()
h.shutdown()
'''


def test_UCTAN_UCA_sigan_ve_takas_ayriliyor(tmp_path, monkeypatch):
    """★★ Tarayıcıda: hiçbir şeyin sığmadığı hücrede uyarı çıkıyor, sığanı
    olan hücrede "sığıyor" grubu var ve o seçenek NET ekleniyor."""
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
    assert c.get("SECILI") == "1", f"test kurulumu bozuk: {c}"
    assert c["PZT_TAKAS"] == "E", "takas grubu yok"
    assert c["PZT_UYARI"] == "E", "hiçbir şey sığmıyorken uyarı çıkmıyor"
    assert c["SAL_SIGAN"] == "E", "sığan ders grubu yok"
    assert c["SAL_UYARI"] == "H", "sığan varken yanlışlıkla 'sığan yok' deniyor"
    assert int(c["SONRA"]) == 2, f"temiz seçenek NET eklenmedi: {c['SONRA']}"
