"""Faz 57 — mezuniyet yol haritası (`yolharitasi.kur`).

Kullanıcı 23.09.2026: *"improve and add necessary features for a program like
this"*. Bu tür bir aracın en büyük eksiği ölçülerek bulundu: araç yalnız BU
dönemi planlıyordu. Vitrin öğrencisinde açılıştaki öneri 1, GEO 341E'yi (Güz
dersi, arkasında iki derslik zincir) çakışma yüzünden dışarıda bırakıyordu ve
bu anadalı BİR YIL geciktiriyordu — ekranın hiçbir yerinde yazmıyordu.

Testler üç katmanda:
* motor — küçük, elle kurulmuş katalogda her kural tek tek (mevsim, önşart
  zinciri, kredi sınırı, ÇAP tabanı, bilinmeyen mevsim, yerleşmeyen ders);
* veri — `collect()` haritayı ve "bu dönem şunu alırsan"ı üretiyor;
* ekran — vitrin öğrencisiyle uçtan uca: görünüm açılıyor, varsayımlar
  planın ÜSTÜNDE, "Programda dene" dersi programa ekleme penceresini açıyor.

Aynı turun küçük özellikleri de burada (hepsi aynı vitrin oturumunda
ölçülüyor): GNO hedefi ("eşikte kalmak için bu dönem kaç ortalama"), dolu
şubeden boş şubeye tek dokunuş, özette haftanın şekli, kampüs tercihinin
veri kapsamı.
"""
import pathlib
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import db
from itucap import policy as POL
from itucap import prereq as P
from itucap import ui as UI
from itucap import yolharitasi as YH

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


# ------------------------------------------------------------------ düzenek
def _katalog(tmp_path, dersler, plan, lesson=(), cap=()):
    """dersler: [(kod, kredi, önşart)], plan: [(kod, dönem_no)], cap: [kod]."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    con = db.connect(tmp_path / "ref.sqlite3", "schema.sql")
    con.execute("INSERT INTO program(code,name,level) VALUES ('AAA','A','LS')")
    con.execute("INSERT INTO program(code,name,level) VALUES ('BBB','B','LS')")
    for kod, kredi, onsart in dersler:
        con.execute("INSERT INTO course(code,name,credits,ects,prereq_raw)"
                    " VALUES (?,?,?,?,?)", (kod, "Ders " + kod, kredi, kredi + 2, onsart))
    con.execute("INSERT INTO plan(id,program_code,plan_type,title,source)"
                " VALUES (1,'AAA','lisans','x','obs')")
    for i, (kod, donem) in enumerate(plan):
        kredi = next(k for c, k, _ in dersler if c == kod)
        con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,credits,position,"
                    "term_no) VALUES (1,'REQUIRED',?,?,?,?)", (kod, kredi, i, donem))
    if cap:
        con.execute("INSERT INTO plan(id,program_code,host_program_code,plan_type,title,"
                    "source) VALUES (2,'BBB','AAA','cap','y','obs')")
        for i, kod in enumerate(cap):
            kredi = next(k for c, k, _ in dersler if c == kod)
            con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,credits,"
                        "position) VALUES (2,'REQUIRED',?,?,?)", (kod, kredi, i))
    for crn, kod in lesson:
        con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled) VALUES (?,?,9,0)",
                    (crn, kod))
    P.parse_all(con)
    con.commit()
    return con


ANADAL = [{"planId": 1, "role": "ANADAL", "label": "anadal", "program": "AAA"}]
CAP = [{"planId": 2, "role": "CAP", "label": "ÇAP", "program": "BBB"}]


def _kur(con, grades=None, planlar=ANADAL, **kw):
    kw.setdefault("term", "202510")
    kw.setdefault("donem", 5)
    kw.setdefault("max_load", 21)
    kw.setdefault("bu_donem", [])
    return YH.kur(con, grades or {}, planlar, **kw)


def _yer(harita):
    """ders → dönem sırası (0 = bu dönem)."""
    return {i["course"] or i["pool"]: t["index"] for t in harita["terms"] for i in t["items"]}


# ------------------------------------------------------------------ motor
def test_DONEM_KODU_ilerliyor():
    assert YH.sonraki_donem("202510") == "202520"
    assert YH.sonraki_donem("202520") == "202610"


def test_ONSART_ZINCIRI_dönem_dönem_ve_MEVSIMINDE(tmp_path):
    # XXX (5. dönem, Güz) → YYY (7., Güz) → ZZZ (8., Bahar). Bu dönem 2025 Güz.
    con = _katalog(tmp_path, [("XXX 101", 3, None), ("YYY 102", 3, "XXX 101 MIN DD"),
                              ("ZZZ 103", 3, "YYY 102 MIN DD")],
                   [("XXX 101", 5), ("YYY 102", 7), ("ZZZ 103", 8)])
    h = _kur(con)
    y = _yer(h)
    # XXX Güz dersi: bu dönem alınmıyorsa ilk Güz 2026 Güz (sıra 2).
    assert y == {"XXX 101": 2, "YYY 102": 4, "ZZZ 103": 5}, y
    ana = h["programs"][0]
    # Plandaki bitiş: 8. dönem − 5 = 3 dönem sonra (2026-2027 Bahar).
    assert ana["nominal"]["index"] == 3
    assert ana["finish"]["index"] == 5
    assert h["longest"] == ["XXX 101", "YYY 102", "ZZZ 103"]
    # Boş Bahar dönemi ATILMIYOR — Güz dersini bekleyen dönem takvimin parçası.
    assert [t["index"] for t in h["terms"]] == [0, 1, 2, 3, 4, 5]


def test_BU_DONEM_alinan_zinciri_ONE_cekiyor(tmp_path):
    con = _katalog(tmp_path, [("XXX 101", 3, None), ("YYY 102", 3, "XXX 101 MIN DD"),
                              ("ZZZ 103", 3, "YYY 102 MIN DD")],
                   [("XXX 101", 5), ("YYY 102", 7), ("ZZZ 103", 8)])
    h = _kur(con, bu_donem=[{"course": "XXX 101", "credits": 3, "slotId": 0, "role": "ANADAL"}])
    assert _yer(h) == {"XXX 101": 0, "YYY 102": 2, "ZZZ 103": 3}
    assert h["programs"][0]["finish"]["index"] == h["programs"][0]["nominal"]["index"] == 3


def test_BU_DONEM_SUBESI_olan_ders_o_mevsimde_de_aciliyor(tmp_path):
    # WWW planda 6. dönem (Bahar) ama BU GÜZ şubesi var → Güz'de de açılır.
    # Önşartı UUU (alttan kalan Bahar dersi) önce gelecek Bahar'da alınıyor;
    # WWW'yi bir sonraki Bahar'a itmek bir yıl uydurma gecikme olurdu
    # (vitrinde MAT 210E'nin başına gelen buydu).
    dersler = [("UUU 100", 3, None), ("WWW 104", 3, "UUU 100 MIN DD")]
    plan = [("UUU 100", 4), ("WWW 104", 6)]
    h = _kur(_katalog(tmp_path / "a", dersler, plan, lesson=[("100", "WWW 104")]))
    assert _yer(h) == {"UUU 100": 1, "WWW 104": 2}, "bu dönem şubesi yok sayıldı"
    madde = next(i for t in h["terms"] for i in t["items"] if i["course"] == "WWW 104")
    assert (madde["season"], madde["alsoSeason"]) == ("20", "10")
    # Şubesi yoksa planın mevsimi: bir sonraki Bahar.
    h = _kur(_katalog(tmp_path / "b", dersler, plan))
    assert _yer(h) == {"UUU 100": 1, "WWW 104": 3}


def test_KREDI_SINIRI_donemi_bolüyor(tmp_path):
    dersler = [(f"KKK 10{i}", 4, None) for i in range(6)]
    con = _katalog(tmp_path, dersler, [(k, 6) for k, _, _ in dersler])
    h = _kur(con, max_load=12, donem=5)
    for t in h["terms"]:
        assert t["credits"] <= 12
    assert sum(len(t["items"]) for t in h["terms"]) == 6
    assert "en çok 12 kredi" in " ".join(h["assumptions"])


def test_ANADAL_plandaki_donemden_ONCE_konmuyor(tmp_path):
    con = _katalog(tmp_path, [("EEE 106", 3, None)], [("EEE 106", 8)])
    assert _yer(_kur(con, donem=5)) == {"EEE 106": 3}


def test_GECILEN_ders_haritada_YOK(tmp_path):
    con = _katalog(tmp_path, [("XXX 101", 3, None), ("YYY 102", 3, "XXX 101 MIN DD")],
                   [("XXX 101", 5), ("YYY 102", 6)])
    h = _kur(con, grades={"XXX 101": "BB"})
    assert "XXX 101" not in _yer(h)
    assert _yer(h)["YYY 102"] == 1


def test_BILINMEYEN_MEVSIM_soyleniyor(tmp_path):
    # ÇAP dersi: ev sahibi lisans planı katalogda yok → mevsim bilinmiyor.
    con = _katalog(tmp_path, [("AAA 111", 3, None), ("CCC 121", 3, None)], [("AAA 111", 6)],
                   cap=["CCC 121"])
    h = _kur(con, planlar=ANADAL + CAP)
    assert h["unknownSeason"] == 1
    assert any("mevsimi hiçbir planda bulunamadı" in a for a in h["assumptions"])
    madde = next(i for t in h["terms"] for i in t["items"] if i["course"] == "CCC 121")
    assert madde["season"] is None


def test_CAP_TABANI_once_doluyor_ve_EKSIGI_yaziliyor(tmp_path):
    # Taban 9 kredi; bu dönemden sonra tek ÇAP dersi (3 kr) alınabiliyor,
    # arkası zincir. Eksik yazılmalı — ama ÇAP'ın SON döneminde değil.
    con = _katalog(tmp_path, [("AAA 111", 3, None), ("AAA 112", 3, None), ("AAA 113", 3, None),
                              ("CCC 121", 3, None), ("CCC 122", 3, "CCC 121 MIN DD")],
                   [("AAA 111", 6), ("AAA 112", 6), ("AAA 113", 6)], cap=["CCC 121", "CCC 122"])
    taban = POL.SecondFloor(minimum=9, start_term=5, verified=True, source="test")
    h = _kur(con, planlar=ANADAL + CAP, max_load=9, taban=taban)
    y = _yer(h)
    assert y["CCC 121"] == 1, "ÇAP tabanı önce doldurulmadı"
    birinci = next(t for t in h["terms"] if t["index"] == 1)
    assert birinci["floorGap"] == 6
    son_cap = next(t for t in h["terms"] if t["index"] == y["CCC 122"])
    assert son_cap["floorGap"] is None, "son ÇAP döneminde imkânsız taban istendi"


def test_CAP_TABANI_anadalin_kritik_yoluna_RAGMEN_doluyor(tmp_path):
    # Anadalın iki zinciri önceliği alıyor (yükseklik 2); ÇAP dersleri tek
    # halka. Taban (6 kr) ÖNCE doldurulmazsa 9 kredilik dönemin ikisi anadala
    # gider ve ÇAP tabanı tutmaz — yönetmelik ihlali planın içinde kalırdı.
    con = _katalog(tmp_path, [("AAA 111", 3, None), ("AAA 112", 3, "AAA 111 MIN DD"),
                              ("AAA 113", 3, None), ("AAA 114", 3, "AAA 113 MIN DD"),
                              ("CCC 121", 3, None), ("CCC 122", 3, None),
                              ("CCC 123", 3, None)],
                   [("AAA 111", 6), ("AAA 112", 7), ("AAA 113", 6), ("AAA 114", 7)],
                   cap=["CCC 121", "CCC 122", "CCC 123"])
    taban = POL.SecondFloor(minimum=6, start_term=5, verified=True, source="test")
    h = _kur(con, planlar=ANADAL + CAP, max_load=9, taban=taban)
    birinci = next(t for t in h["terms"] if t["index"] == 1)
    cap = sum(i["credits"] for i in birinci["items"] if "CAP" in i["roles"])
    assert cap >= 6 and birinci["floorGap"] is None, birinci


def test_DIS_ONSART_varsayiliyor_ve_YAZIYOR(tmp_path):
    # ★ 24.09.2026 (gerçek katalog): önşartı hiçbir planda olmayan ders eskiden
    # hiç yerleşmiyordu ve tek bir tanesi programın bitişini "hesaplanamadı"
    # yapıyordu (BLG+EHB'de iki programın ikisi de). Artık yerleşiyor ve
    # hangi dış dersin varsayıldığı derste, kartta ve varsayımda yazıyor.
    con = _katalog(tmp_path, [("QQQ 131", 3, "DIS 100 MIN DD"), ("DIS 100", 3, None)],
                   [("QQQ 131", 6)])
    h = _kur(con)
    p = h["programs"][0]
    assert p["finish"] is not None and p["unplaced"] == 0 and p["externalAssumed"] == 1
    madde = next(i for t in h["terms"] for i in t["items"] if i["course"] == "QQQ 131")
    assert madde["externalPrereq"] == ["DIS 100"]
    assert any("DIS 100" in a and "varsayıldı" in a for a in h["assumptions"])


def test_PLANLI_onsart_eksikse_BEKLIYOR_ve_ufukta_YERLESMEYEN(tmp_path):
    # Dış ders varsayılması PLANLI önşartı atlatmıyor: YYY, XXX'i bekler.
    # Ufuk bir dönemse XXX (Güz) hiç yerleşmez, YYY de — sebebiyle.
    con = _katalog(tmp_path, [("XXX 101", 3, None), ("YYY 102", 3, "XXX 101 MIN DD")],
                   [("XXX 101", 5), ("YYY 102", 6)])
    h = _kur(con, ufuk=1)
    assert h["programs"][0]["finish"] is None and h["programs"][0]["unplaced"] == 2
    assert all("yerleşmedi" in u["reason"] or "önşart" in u["reason"] for u in h["unplaced"])


def test_OKUNAMAYAN_ONSART_engellemiyor_ama_ISARETLENIYOR(tmp_path):
    # Önşart metni ayrıştırılamadı: dersi sonsuza kadar bekletmek de, önşartı
    # yokmuş gibi sessizce yerleştirmek de yanlış olurdu — yerleşiyor, notla.
    con = _katalog(tmp_path, [("XXX 101", 3, "X 1 MIN DD")], [("XXX 101", 6)])
    madde = next(i for t in _kur(con)["terms"] for i in t["items"])
    assert madde["course"] == "XXX 101" and madde["unparsed"] is True
    assert "önşartı okunamadı" in KAYNAK


def test_BAGLANTININ_row_factory_si_KORUNUYOR(tmp_path):
    con = _katalog(tmp_path, [("XXX 101", 3, None)], [("XXX 101", 5)])
    con.row_factory = None
    _kur(con)
    assert con.row_factory is None
    con.row_factory = sqlite3.Row
    _kur(con)
    assert con.row_factory is sqlite3.Row


# ------------------------------------------------------------------ GNO hedefi (veri)
def test_GNO_puani_YUVARLANMADAN_geliyor(tmp_path):
    con = _katalog(tmp_path, [("XXX 101", 3, None), ("YYY 102", 4, None)], [])
    g = POL.gpa(con, {"XXX 101": "BA", "YYY 102": "CB"})
    assert g.points == pytest.approx(3.5 * 3 + 2.5 * 4)
    assert g.value == round(g.points / g.credits, 2)


def test_TEKRAR_notu_yalniz_HAVUZDAKI_ve_GNOya_GIREN(tmp_path):
    con = _katalog(tmp_path, [("XXX 101", 3, None), ("YYY 102", 4, None),
                              ("ZZZ 103", 0, None), ("WWW 104", 2, None)], [])
    notlar = {"XXX 101": "FF", "YYY 102": "DD", "ZZZ 103": "BZ", "WWW 104": "BL"}
    t = UI._tekrar_notlari(con, notlar, {"XXX 101", "ZZZ 103", "WWW 104", "QQQ 999"})
    # YYY havuzda değil; ZZZ 0 kredi; WWW'nin BL'si ortalamaya girmiyor.
    assert t == {"XXX 101": {"grade": "FF", "credits": 3.0, "points": 0.0}}


def test_GNO_HEDEFI_canli_ve_tahmin_DEGIL():
    f = KAYNAK[KAYNAK.index("function renderGnoHedef(){"):]
    f = f[:f.index("\n}\n")]
    t = KAYNAK[KAYNAK.index("function gnoTabani("):]
    t = t[:t.index("\n}\n")]
    # Seçim değişince yeniden hesaplanıyor.
    r = KAYNAK[KAYNAK.index("function render(){"):]
    assert "renderGnoHedef();" in r[:r.index("\n}\n")]
    # Formül: tekrar alınan dersin eski puanı ve kredisi çıkıyor (Faz 58'de
    # `gnoTabani`na taşındı — genel ve ÇAP ortalaması aynı hesabı kullanıyor).
    assert "const C = C0 - tekrar.reduce" in t
    assert "const P = P0 - tekrar.reduce" in t
    assert "const x = (h.min * (C + T) - P) / T;" in f
    assert "Tahmin değil, gereken notun hesabı" in f
    # Zaten girilmiş programın başvuru eşiği hedef sayılmıyor.
    assert '!(t.kind === "basvuru" && icinde.has(t.scope))' in KAYNAK


# ------------------------------------------------------------------ arayüz (statik)
def test_GORUNUM_kayitli_ve_varsayimlar_PLANIN_USTUNDE():
    assert '["roadmapSection", "Yol haritası", "DURUM", "Harita", true]' in KAYNAK
    assert 'id="roadmapSection"' in KAYNAK and "renderRoadmap();" in KAYNAK
    f = KAYNAK[KAYNAK.index("function renderRoadmap(){"):]
    f = f[:f.index("\n}\n")]
    son = f.rindex("body.innerHTML = `")
    sira = f[son:f.index("`;", son)]      # Faz 61: ifade artık iki satır
    assert sira.index("${varsayim}") < sira.index("${donemler}"), \
        "varsayımlar planın altına kaydı — okunmadan geçiliyor"
    assert "Bu bir plan, kehanet değil." in f


def test_MOTOR_statik_sitede_de_var():
    site = (pathlib.Path(UI.__file__).resolve().parents[2] / "tools" / "site_kur.py").read_text(
        encoding="utf-8")
    assert '"yolharitasi"' in site


def test_BASKIDA_ve_KURULUMDA_gizli():
    assert "body.kurulum #roadmapSection" in KAYNAK
    assert re.search(r"@media print\{[^}]*#roadmapSection", KAYNAK, re.S) \
        or "#tierSection,#roadmapSection" in KAYNAK


# ------------------------------------------------------------------ uçtan uca (vitrin)
_CANLI = r'''
import sys, os
sys.path.insert(0, os.environ["ITUCAP_SRC"]); sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import vitrin
adres, h = vitrin.ac()
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 1000})
    hatalar = []
    pg.on("pageerror", lambda e: hatalar.append(str(e)))
    pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(1200)
    R = pg.evaluate("() => DATA.roadmap")
    print("KAYNAK:" + R["source"])
    print("PROGRAMLAR:" + ",".join(f"{x['role']}={(x['finish'] or {}).get('label')}"
                                   for x in R["programs"]))
    print("SIMDI:" + ",".join(x["course"] + "/" + str(x["gains"][0]["terms"])
                              for x in R["takeNow"]))
    pg.evaluate("() => gorunumAc('roadmapSection')"); pg.wait_for_timeout(300)
    print("GORUNUR:" + str(pg.is_visible("#roadmapSection")))
    print("KART:" + str(pg.locator("#roadmapBody .yhdonem").count()))
    print("GEC:" + (pg.text_content("#roadmapBody .yhprogram[data-role=ANADAL] .yhgec") or "").strip())
    pg.click("#roadmapBody [data-dene]"); pg.wait_for_timeout(500)
    print("DENE:" + pg.evaluate("() => (document.querySelector('dialog[open]')||{}).id || '-'")
          + "|" + pg.evaluate("() => document.documentElement.dataset.gorunum"))
    print("DENEDERS:" + pg.evaluate(
        "() => (document.querySelector('dialog[open] h2')||{}).textContent || ''"))
    pg.evaluate("() => document.querySelector('dialog[open]').close()")
    # --- GNO hedefi: programdaki kredilerle, sonra MAT 210E (FF) tekrarıyla.
    def gno():
        return pg.evaluate("""() => ({g: {p: DATA.gpa.points, c: DATA.gpa.credits,
            r: DATA.gpa.retake}, T: picks().map(p => [p.cand.course, p.cand.credits]),
            satir: [...document.querySelectorAll('#gnoHedefBody .gnosatir[data-taban=genel]')].map(e =>
              e.querySelector('b').textContent + '=' + e.querySelector('.gereken').textContent.trim()),
            etiket: [...document.querySelectorAll('#gnoHedefBody .gnosatir[data-taban=genel] > span:first-child')]
              .map(e => e.textContent.replace(/\\s+/g, ' ')).join(' | '),
            tekrar: ((document.querySelector('#gnoHedefBody .gnobaslik')||{}).textContent || '')
              .replace(/\\s+/g, ' ')})""")
    import json
    print("GNO1:" + json.dumps(gno(), ensure_ascii=False))
    pg.evaluate("() => choose('MAT 210E', candOf('MAT 210E').sections[0].crn)")
    pg.wait_for_timeout(200)
    print("GNO2:" + json.dumps(gno(), ensure_ascii=False))
    pg.evaluate("() => geriAl()"); pg.wait_for_timeout(200)
    # --- Dolu şube: açılışta GEO 331E dolu şubede, öbürü GEO 385E ile çakışıyor.
    ozet = "() => (document.querySelector('.ozetdolu')||{innerText:''}).innerText.replace(/\\s+/g,' ')"
    print("DOLU1:" + pg.evaluate(ozet))
    pg.evaluate("() => removeCourse('GEO 385E')"); pg.wait_for_timeout(200)
    print("DOLU2:" + pg.evaluate(ozet))
    pg.click("[data-bosa]"); pg.wait_for_timeout(200)
    print("DOLU3:" + pg.evaluate("() => sel.find(x => x.course === 'GEO 331E').crn")
          + "|" + pg.evaluate(ozet) + "|" + pg.evaluate("() => $('#undo').textContent"))
    pg.evaluate("() => geriAl()"); pg.wait_for_timeout(200)
    print("DOLU4:" + pg.evaluate("() => sel.find(x => x.course === 'GEO 331E').crn"))
    # --- Haftanın şekli.
    print("SEKIL:" + pg.evaluate("() => document.querySelector('.ozetsekil').innerText.replace(/\\s+/g,' ')"))
    # --- Kampüs tercihi: vitrinde her binanın kampüsü belli → not yok;
    # bir buluşmanın kampüsü silinince not çıkıyor.
    pg.evaluate("() => tercihDialog()"); pg.wait_for_timeout(300)
    print("KAMPUS1:" + str(pg.locator("#fKampus + .hint, label:has(#fKampus) .hint").count()))
    pg.evaluate("() => document.querySelector('#setup').close()")
    pg.evaluate("() => { M().candidates.find(c => c.sections.some(s => !s.online && s.meetings.length))"
                ".sections.find(s => !s.online && s.meetings.length).meetings[0].campus = null; }")
    pg.evaluate("() => tercihDialog()"); pg.wait_for_timeout(300)
    print("KAMPUS2:" + pg.evaluate("() => document.querySelector('#fKampus').closest('label').innerText.replace(/\\s+/g,' ')"))
    print("HATA:" + str(len(hatalar)))
    b.close()
h.shutdown()
'''


def test_UCTAN_UCA_vitrin_yol_haritasi(tmp_path, monkeypatch):
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
    c = dict(s.split(":", 1) for s in r.stdout.strip().splitlines()
             if ":" in s and s.split(":", 1)[0].isupper())
    assert c["HATA"] == "0"
    assert c["KAYNAK"].startswith("açılıştaki öneri 1"), c["KAYNAK"]
    # Vitrin öğrencisi: GEO 341E alınmazsa anadal 2027-2028 Bahar'a kayıyor.
    assert "ANADAL=2027-2028 Bahar" in c["PROGRAMLAR"], c["PROGRAMLAR"]
    assert "GEO 341E/2" in c["SIMDI"], c["SIMDI"]
    assert c["GORUNUR"] == "True"
    assert int(c["KART"]) >= 4
    assert c["GEC"].startswith("planındaki bitişten 2 dönem geç"), c["GEC"]
    # "Programda dene" → ders programına geçip dersi ekleme penceresi.
    assert c["DENE"] == "detail|schedSection", c["DENE"]
    assert "GEO 341E" in c["DENEDERS"], c["DENEDERS"]

    # GNO hedefi — Python'da AYNI aritmetik, ekrandaki sayıyla karşılaştırılıyor.
    import json
    import math

    def gereken(o, hedef):
        tekrar = [k for k, _ in o["T"] if k in o["g"]["r"]]
        T = sum(k for _, k in o["T"])
        C = o["g"]["c"] - sum(o["g"]["r"][k]["credits"] for k in tekrar)
        P = o["g"]["p"] - sum(o["g"]["r"][k]["points"] for k in tekrar)
        return math.ceil(((hedef * (C + T) - P) / T) * 100 - 1e-6) / 100

    for anahtar in ("GNO1", "GNO2"):
        o = json.loads(c[anahtar])
        satir = dict(x.split("=", 1) for x in o["satir"])
        assert satir["2.00"] == "her durumda ✓", satir
        assert satir["2.50"] == f"≥ {gereken(o, 2.5):.2f}", (anahtar, satir, o)
        # ÇAP öğrencisine "ÇAP başvurusu" hedefi gösterilmiyor; 3.00 yalnız
        # kredi bandı yüzünden var.
        assert "3.00" in satir and "başvuru" not in o["etiket"], o["etiket"]
    o1, o2 = json.loads(c["GNO1"]), json.loads(c["GNO2"])
    assert "MAT 210E (FF)" not in o1["tekrar"] and "MAT 210E (FF)" in o2["tekrar"]
    # FF tekrarı: eski notun sıfırı gidiyor → aynı kredide gereken ortalama DÜŞER.
    assert gereken(o2, 2.5) < gereken({**o2, "g": {**o2["g"], "r": {}}}, 2.5)

    assert "uyan boş şube yok" in c["DOLU1"], c["DOLU1"]
    assert "boş şubeye geç" in c["DOLU2"] and "13641" in c["DOLU2"], c["DOLU2"]
    crn, ozet, geri = c["DOLU3"].split("|")
    assert crn == "13641" and "GEO 331E" not in ozet, c["DOLU3"]
    assert geri == "Geri al: GEO 331E şube değişikliği", geri
    assert c["DOLU4"] == "13603", "boş şubeye geçiş geri alınamadı"

    assert re.fullmatch(r"\d gün kampüste · (?:(?:Pzt|Sal|Çar|Per|Cum) ?)+· \d\d:\d\d–\d\d:\d\d"
                        r"( · en uzun ara .+ \((?:Pzt|Sal|Çar|Per|Cum)\))?", c["SEKIL"].strip()), c["SEKIL"]
    assert "1 dk" not in c["SEKIL"], "İTÜ'nün :29 bitişi ham farkla yazıldı"

    assert c["KAMPUS1"] == "0"
    assert "bina/kampüs ilan edilmemiş" in c["KAMPUS2"], c["KAMPUS2"]
