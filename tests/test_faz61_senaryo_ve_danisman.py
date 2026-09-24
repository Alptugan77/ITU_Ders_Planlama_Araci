"""Faz 61 — yol haritası senaryoları ve danışman özeti.

Kullanıcı 24.09.2026: *"can you continue on your improvements and aditions"*.

* Senaryo: "dönemde en çok 18 kredi alabilirim", "3. dönem Erasmus'tayım" —
  ikisi de bitişi değiştiriyor ve ancak haritayı yeniden kurarak ölçülüyor
  (salt okunur `/api/yolharitasi`, kaydedilmiyor). Boş dönem takvimde KALIYOR
  ve yarıyıl sayısına dahil.
* Danışman özeti: tek sayfa — program CRN'leriyle, kontroller, tahmini bitiş
  ve yalnız ÖLÇÜLEN sorunlardan çıkan "danışmana sorulacaklar". Görünümlerle
  AYNI yardımcıları kullanıyor; yalnız özet basılıyor.
"""
import pathlib
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import db
from itucap import prereq as P
from itucap import server as SRV
from itucap import ui as UI
from itucap import yolharitasi as YH

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


def _js(ad):
    f = KAYNAK[KAYNAK.index(f"function {ad}("):]
    return f[:f.index("\n}\n")]


def _katalog(tmp_path):
    # XXX (5., Güz) → YYY (7., Güz) → ZZZ (8., Bahar); bu dönem 2025-2026 Güz.
    con = db.connect(tmp_path / "ref.sqlite3", "schema.sql")
    con.execute("INSERT INTO program(code,name,level) VALUES ('AAA','A','LS')")
    for kod, onsart in (("XXX 101", None), ("YYY 102", "XXX 101 MIN DD"),
                        ("ZZZ 103", "YYY 102 MIN DD")):
        con.execute("INSERT INTO course(code,name,credits,ects,prereq_raw) VALUES (?,?,3,5,?)",
                    (kod, "Ders " + kod, onsart))
    con.execute("INSERT INTO plan(id,program_code,plan_type,title,source)"
                " VALUES (1,'AAA','lisans','x','obs')")
    for i, (kod, d) in enumerate((("XXX 101", 5), ("YYY 102", 7), ("ZZZ 103", 8))):
        con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,credits,position,"
                    "term_no) VALUES (1,'REQUIRED',?,3,?,?)", (kod, i, d))
    P.parse_all(con)
    con.commit()
    return con


PLAN = [{"planId": 1, "role": "ANADAL", "label": "anadal", "program": "AAA"}]


def _kur(con, **kw):
    return YH.kur(con, {}, PLAN, term="202610", donem=5, max_load=21, bu_donem=[], **kw)


# ------------------------------------------------------------------ motor
def test_BOS_DONEM_takvimde_KALIYOR_ve_zinciri_kaydiriyor(tmp_path):
    con = _katalog(tmp_path)
    once = _kur(con)
    assert once["programs"][0]["finish"]["index"] == 5
    # XXX'in ilk Güz'ü (sıra 2) Erasmus → bir yıl kayıyor.
    h = _kur(con, bos=[2])
    kart = next(t for t in h["terms"] if t["index"] == 2)
    assert kart["skipped"] is True and kart["items"] == [] and kart["floorGap"] is None
    p = h["programs"][0]
    assert p["finish"]["index"] == 7 and p["finishSemester"] == 12
    assert any("boş bıraktın" in a and "yarıyıl sayısına DAHİL" in a for a in h["assumptions"])


def test_BOS_DONEM_zincire_DOKUNMUYORSA_bitis_ayni(tmp_path):
    # Sıra 1 (Bahar) boş: XXX zaten sıra 2'de, bitiş değişmemeli.
    con = _katalog(tmp_path)
    assert _kur(con, bos=[1])["programs"][0]["finish"]["index"] == 5


# ------------------------------------------------------------------ statik
def test_SENARYO_salt_okunur_ve_SINIRLI():
    assert "/api/yolharitasi" in SRV.READ_ONLY_PATHS
    k = KAYNAK[KAYNAK.index("def yol_senaryosu("):KAYNAK.index("def cap_bitisleri(")]
    assert "if any(not 1 <= x <= YH.UFUK for x in bos) or len(bos) > 6:" in k
    # Girdi ve doğrulama ÇAP seçenekleriyle ORTAK.
    assert "_harita_girdisi(" in k
    assert "_harita_girdisi(" in KAYNAK[KAYNAK.index("def cap_bitisleri("):]
    b = _js("boot")
    assert "YH_SENARYO = null; YH_AYAR = null;" in b


def test_OZET_gorunumlerle_AYNI_hesap():
    assert "tabanDurumu(F)" in _js("renderFloor")
    assert "tabanDurumu(F)" in _js("danismanSorulari")
    assert "tabanDurumu(F)" in _js("danismanOzeti")
    f = _js("danismanOzeti")
    assert "__AD_TAM__" in f and "Bu sayfa GNO'nu içerir" in f


def test_BASKI_yalniz_OZET_ve_BODYde():
    assert "body.ozetbaski>*:not(#ozetBaski){display:none !important}" in KAYNAK
    d = _js("danismanDialog")
    assert "if(kab.parentElement !== document.body) document.body.appendChild(kab);" in d
    assert 'addEventListener("afterprint", bitti);' in d


# ------------------------------------------------------------------ uçtan uca (vitrin)
_CANLI = r'''
import sys, os, json
sys.path.insert(0, os.environ["ITUCAP_SRC"]); sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import vitrin
adres, h = vitrin.ac()
from itucap import server
st = server.State(label="ben")
R = st.snapshot()["roadmap"]
bu = [{"course": i["course"], "credits": i["credits"], "role": (i["roles"] or [""])[0]}
      for i in R["terms"][0]["items"]]
for govde in ({"bu": bu, "maxLoad": 25, "bos": [99]}, {"bu": bu, "maxLoad": 0, "bos": []},
              {"bu": bu, "maxLoad": 25, "bos": ["x"]}):
    try:
        st.dispatch("/api/yolharitasi", govde); print("RED:yok")
    except ValueError as e:
        print("RED:" + str(e))
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 1000})
    hatalar = []
    pg.on("pageerror", lambda e: hatalar.append(str(e)))
    pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(1200)
    # --- senaryo
    pg.evaluate("() => gorunumAc('roadmapSection')"); pg.wait_for_timeout(300)
    kart = "() => document.querySelector('.yhprogram[data-role=ANADAL]').innerText.replace(/\\s+/g,' ')"
    serit = "() => (document.querySelector('.yhseritsenaryo')||{innerText:''}).innerText.replace(/\\s+/g,' ')"
    pg.click('[data-bos="2"]'); pg.wait_for_timeout(600)
    print("S1:" + pg.evaluate(kart) + "|" + pg.evaluate(serit))
    print("ATLANDI:" + pg.evaluate("() => [...document.querySelectorAll('.yhdonem.atlandi h3 span')].map(e => e.textContent.trim()).join(',')"))
    pg.select_option("#yhYuk", "15"); pg.wait_for_timeout(600)
    print("S2:" + pg.evaluate(serit))
    pg.click("#yhSenaryoKapat"); pg.wait_for_timeout(300)
    print("S3:" + pg.evaluate(serit) + "|" + pg.evaluate(kart))
    # --- danışman özeti: yük aşılınca soru çıkıyor
    pg.evaluate("() => gorunumAc('schedSection')")
    soru = "() => [...document.querySelectorAll('#detail .dsoru li')].map(e => e.innerText.replace(/\\s+/g,' '))"
    # (1) Olağan yol: çakışan ÇAP dersi düşüyor → taban eksiği sorusu.
    pg.evaluate("() => choose('GEO 341E', candOf('GEO 341E').sections[0].crn)"); pg.wait_for_timeout(300)
    pg.click("#danismanBtn"); pg.wait_for_timeout(400)
    print("SORU1:" + json.dumps(pg.evaluate(soru), ensure_ascii=False))
    pg.evaluate("() => { document.querySelector('#detail').close(); geriAl(); }")
    # (2) Yük sınırını aşan program (çakışma kontrolünü atlayarak) → yük sorusu.
    pg.evaluate("() => { sel.push({course: 'GEO 341E', crn: candOf('GEO 341E').sections[0].crn}); render(); }")
    pg.wait_for_timeout(200)
    pg.click("#danismanBtn"); pg.wait_for_timeout(400)
    print("SORU:" + json.dumps(pg.evaluate("() => [...document.querySelectorAll('#detail .dsoru li')].map(e => e.innerText.replace(/\\s+/g,' '))"), ensure_ascii=False))
    print("TABLO:" + str(pg.evaluate("() => document.querySelectorAll('#detail .dozet tbody tr').length"))
          + "|" + str(pg.evaluate("() => picks().length")))
    pg.evaluate("() => { window.print = () => { window.__basildi = true; }; }")
    pg.click("#ozetYazdir"); pg.wait_for_timeout(200)
    pg.emulate_media(media="print")
    print("BASKI:" + json.dumps(pg.evaluate("""() => [!!window.__basildi,
        document.body.classList.contains('ozetbaski'),
        getComputedStyle(document.querySelector('#ozetBaski')).display,
        getComputedStyle(document.querySelector('header')).display,
        document.querySelector('#ozetBaski').parentElement === document.body,
        (document.querySelector('#ozetBaski h2')||{}).textContent]""")))
    pg.evaluate("() => dispatchEvent(new Event('afterprint'))"); pg.wait_for_timeout(100)
    print("SONRA:" + json.dumps(pg.evaluate("() => [document.body.classList.contains('ozetbaski'), document.querySelector('#ozetBaski').innerHTML.length]")))
    print("HATA:" + str(len(hatalar)) + " " + " | ".join(hatalar)[:300])
    b.close()
h.shutdown()
'''


def test_UCTAN_UCA_vitrin(tmp_path, monkeypatch):
    try:
        import playwright  # noqa: F401
    except ImportError:
        pytest.skip("playwright yok")
    kok = Path(UI.__file__).resolve().parents[2]
    monkeypatch.setenv("ITUCAP_SRC", str(kok / "src"))
    monkeypatch.setenv("ITUCAP_TOOLS", str(kok / "tools"))
    betik = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, dir=str(tmp_path))
    betik.write(_CANLI); betik.close()
    r = subprocess.run([sys.executable, betik.name], capture_output=True, text=True,
                       timeout=300, cwd=str(tmp_path))
    if r.returncode != 0:
        if "Executable doesn't exist" in r.stderr or "BrowserType.launch" in r.stderr:
            pytest.skip("tarayıcı başlatılamadı")
        pytest.fail(r.stderr[-2000:])
    satirlar = [s for s in r.stdout.strip().splitlines() if ":" in s]
    red = [s.split(":", 1)[1] for s in satirlar if s.startswith("RED:")]
    c = dict(s.split(":", 1) for s in satirlar if s.split(":", 1)[0].isupper())
    import json
    assert c["HATA"].startswith("0"), c["HATA"]
    assert red == ["boş dönem geçersiz", "kredi sınırı geçersiz", "boş dönem geçersiz"], red

    # Senaryo: vitrinde 2026-2027 Güz Erasmus → GEO 341E zinciri bir yıl kayıyor.
    kart, serit = c["S1"].split("|")
    assert "2028-2029 Bahar" in kart and "12. yarıyılında" in kart, kart
    assert "bugünkü plana göre 2 dönem geç" in kart
    assert "Senaryo gösteriliyor — kaydedilmedi." in serit and "boş: 2026-2027 Güz" in serit
    assert c["ATLANDI"] == "2026-2027 Güz"
    assert "dönem başına en çok 15 kredi" in c["S2"], c["S2"]
    serit3, kart3 = c["S3"].split("|")
    assert serit3 == "" and "2027-2028 Bahar" in kart3 and "bugünkü plana" not in kart3

    # Danışman özeti (1): GEO 341E şubesi bir ÇAP dersiyle çakışıyor, o düşünce
    # ÇAP tabanı 6/9 — özet bunu soruyor (renderFloor ile aynı hesap).
    soru1 = json.loads(c["SORU1"])
    assert any(s.startswith("İkinci anadaldan bu dönem 6 kredi alıyorum; yarıyıl tabanı 9 (3 eksik)")
               for s in soru1), soru1
    # (2) GEO 341E çakışmasız eklenince 27/25 — yük sorusu.
    soru = json.loads(c["SORU"])
    assert any(s.startswith("Programım 27 kredi, sınırım 25") for s in soru), soru
    assert any("GEO 331E şubem (CRN 13603) dolu" in s for s in soru), soru
    assert any(s.startswith("Anadal tahmini bitişim") for s in soru), soru
    satir, secim = c["TABLO"].split("|")
    assert satir == secim, "özetteki tablo programdaki derslerle aynı değil"
    b = json.loads(c["BASKI"])
    assert b == [True, True, "block", "none", True, "Danışman özeti"], b
    assert json.loads(c["SONRA"]) == [False, 0], "baskıdan sonra sayfa eski hâline dönmedi"
