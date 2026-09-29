"""Faz 58 — yol haritası geçmişten öğreniyor; yaz okulu; ÇAP ortalaması; resim.

Kullanıcı 23.09.2026: *"continue your work to improve"*. Faz 57'nin
`fikirler.md` "Faz 57 araştırması" listesinden, ölçülerek seçilenler:

* Y.2 — dersin açıldığı yarıyıl GEÇMİŞ not dağılımından (plan susuyorsa).
  ⚠️ Bütünlemeci tuzağı: Güz dersinin Baharda 2–3 notu olabiliyor (Faz 38b,
  BLG 212). Eşik yıl içinde: ≥5 öğrenci ve o yılın en kalabalık yarıyılının ¼'ü.
* Y.3 — yaz okulu: geçen yaz gerçekten açılmış ders ilk yazda alınırsa
  bitiş değişiyor mu.
* Y.4 — "bu dönem şunu alırsan" yük sınırını aşıyorsa hangi ders çıksın;
  ÇAP yarıyıl tabanını bozan çıkarma önerilmiyor.
* Y.6 — GNO hedefi ÇAP'ın KENDİ ortalaması için de.
* Y.5 — haftalık programın resmi (PNG), tarayıcıda çiziliyor.
"""
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import db
from itucap import prereq as P
from itucap import ui as UI
from itucap import yolharitasi as YH

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


# ------------------------------------------------------------------ düzenek
def _katalog(tmp_path, dersler, plan, cap=(), dagilim=()):
    """dersler: [(kod, kredi, önşart)], plan: [(kod, dönem_no)],
    cap: [kod] (ev sahibi lisans planı YOK → mevsim planlardan okunamaz),
    dagilim: [(anahtar, dönem, öğrenci)] — anahtar 'XXX 101' (dil-bağımsız)."""
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
    for anahtar, donem, n in dagilim:
        con.execute("INSERT INTO grade_distribution(course_key,term,grade,students,announced)"
                    " VALUES (?,?,'CC',?,?)", (anahtar, donem, n, n))
        for kod in (anahtar, anahtar + "E"):
            con.execute("INSERT OR IGNORE INTO grade_distribution_alias(course_code,course_key)"
                        " VALUES (?,?)", (kod, anahtar))
    P.parse_all(con)
    con.commit()
    return con


ANADAL = [{"planId": 1, "role": "ANADAL", "label": "anadal", "program": "AAA"}]
CAP = [{"planId": 2, "role": "CAP", "label": "ÇAP", "program": "BBB"}]


def _kur(con, planlar=ANADAL, **kw):
    kw.setdefault("term", "202610")
    kw.setdefault("donem", 5)
    kw.setdefault("max_load", 21)
    kw.setdefault("bu_donem", [])
    return YH.kur(con, {}, planlar, **kw)


def _yer(h):
    return {i["course"]: t["index"] for t in h["terms"] if not t.get("summer")
            for i in t["items"]}


def _madde(h, kod):
    return next(i for t in h["terms"] for i in t["items"] if i["course"] == kod)


# ------------------------------------------------------------------ Y.2 — geçmiş
def test_BUTUNLEMECI_acilis_SAYILMIYOR(tmp_path):
    con = _katalog(tmp_path, [("BLG 335", 3, None)], [],
                   dagilim=[("BLG 335", "202510", 80), ("BLG 335", "202520", 3)])
    g = YH.gecmis_mevsimleri(con, ["BLG 335"])
    assert g["seasons"] == {"10"}, "3 bütünlemeci Bahar açılışı sayıldı"


def test_BUYUK_dersin_BUTUNLEMECISI_ORANLA_ayikliyor(tmp_path):
    # 200 kişilik Güz dersinin Baharda 12 notu: mutlak taban (5) geçiliyor,
    # o yüzden ayıran ORAN (%25). Oran olmasa bu ders "iki dönem açılır"
    # görünür ve yol haritası ona güvenip bitişi olduğundan erken gösterirdi.
    con = _katalog(tmp_path, [("MAT 103", 4, None)], [],
                   dagilim=[("MAT 103", "202510", 200), ("MAT 103", "202520", 12)])
    assert YH.gecmis_mevsimleri(con, ["MAT 103E"])["seasons"] == {"10"}


def test_IKI_YARIYIL_gercekse_ikisi_de(tmp_path):
    con = _katalog(tmp_path, [("MAT 210", 3, None)], [],
                   dagilim=[("MAT 210", "202510", 120), ("MAT 210", "202520", 45)])
    assert YH.gecmis_mevsimleri(con, ["MAT 210E"])["seasons"] == {"10", "20"}


def test_KARSILASTIRMA_YIL_ICINDE(tmp_path):
    # 2024 yılında yalnız Bahar (40) var: o yılın en kalabalığı o. Başka yılın
    # büyük Güz sınıfıyla (200) kıyaslanıp atılmamalı.
    con = _katalog(tmp_path, [("XXX 101", 3, None)], [],
                   dagilim=[("XXX 101", "202510", 200), ("XXX 101", "202420", 40)])
    assert YH.gecmis_mevsimleri(con, ["XXX 101"])["seasons"] == {"10", "20"}


def test_YAZ_yalniz_GERCEK_sinifsa(tmp_path):
    con = _katalog(tmp_path, [("XXX 101", 3, None), ("YYY 102", 3, None)], [],
                   dagilim=[("XXX 101", "202510", 60), ("XXX 101", "202530", 14),
                            ("YYY 102", "202510", 60), ("YYY 102", "202530", 2)])
    x = YH.gecmis_mevsimleri(con, ["XXX 101"])["summer"]
    assert [(s["term"], s["n"], s["label"]) for s in x] == [("202530", 14, "2024-2025 Yaz")]
    assert YH.gecmis_mevsimleri(con, ["YYY 102"])["summer"] == []


def test_DAGILIM_YOKSA_tahmin_YOK(tmp_path):
    con = _katalog(tmp_path, [("XXX 101", 3, None)], [])
    assert YH.gecmis_mevsimleri(con, ["XXX 101"]) is None


def test_PLAN_SUSUYORSA_mevsim_GECMISTEN(tmp_path):
    # İki ÇAP dersi, ev sahibi lisans planı yok. Geçmişte CCC 121 yalnız Güz'de,
    # CCC 122 yalnız Bahar'da verilmiş. Bu dönem Güz: ilk Bahar sıra 1, ilk
    # Güz sıra 2. Eskiden ikisi de "her dönem açılır" sayılıp sıra 1'e konuyordu.
    dersler = [("AAA 111", 3, None), ("CCC 121", 3, None), ("CCC 122", 3, None)]
    con = _katalog(tmp_path, dersler, [("AAA 111", 6)], cap=["CCC 121", "CCC 122"],
                   dagilim=[("CCC 121", "202510", 50), ("CCC 122", "202520", 50)])
    h = _kur(con, planlar=ANADAL + CAP)
    y = _yer(h)
    assert y["CCC 121"] == 2 and y["CCC 122"] == 1, y
    assert _madde(h, "CCC 121")["seasonSource"] == "gecmis"
    assert h["unknownSeason"] == 0
    assert any("geçmiş not dağılımından belirlenmiştir" in a and "düzenli bir sınıfın" in a
               for a in h["assumptions"])


def test_PLAN_ILE_GECMIS_celisirse_IKISI_DE_acik(tmp_path):
    # Plan 6. dönem (Bahar) diyor; geçmişte Güz'de de gerçek sınıf var.
    # Önşartı UUU bir sonraki Bahar'da → WWW sonraki Güz'de alınabilmeli.
    dersler = [("UUU 100", 3, None), ("WWW 104", 3, "UUU 100 MIN DD")]
    plan = [("UUU 100", 4), ("WWW 104", 6)]
    h = _kur(_katalog(tmp_path, dersler, plan,
                      dagilim=[("WWW 104", "202510", 60), ("WWW 104", "202520", 55)]))
    assert _yer(h) == {"UUU 100": 1, "WWW 104": 2}
    m = _madde(h, "WWW 104")
    assert (m["season"], m["alsoSeason"], m["alsoSeasonSource"]) == ("20", "10", "gecmis")


# ------------------------------------------------------------------ Y.3 — yaz
def _zincir(tmp_path, dagilim=()):
    # XXX (5., Güz) → YYY (7., Güz) → ZZZ (8., Bahar); bu dönem 2025-2026 Güz.
    return _katalog(tmp_path, [("XXX 101", 3, None), ("YYY 102", 3, "XXX 101 MIN DD"),
                               ("ZZZ 103", 3, "YYY 102 MIN DD")],
                    [("XXX 101", 5), ("YYY 102", 7), ("ZZZ 103", 8)], dagilim=dagilim)


def test_YAZ_ilk_BAHARDAN_sonra_ve_zinciri_one_cekiyor(tmp_path):
    con = _zincir(tmp_path)
    once = _kur(con)
    assert _yer(once) == {"XXX 101": 2, "YYY 102": 4, "ZZZ 103": 5}
    h = _kur(con, yaz="XXX 101")
    assert h["summer"]["placed"] and h["summer"]["label"] == "2025-2026 Yaz"
    yaz_karti = [t for t in h["terms"] if t.get("summer")]
    assert len(yaz_karti) == 1 and yaz_karti[0]["index"] == 1
    # Bahar kartının HEMEN ARKASINDA.
    sira = [(t["index"], bool(t.get("summer"))) for t in h["terms"]]
    assert sira.index((1, True)) == sira.index((1, False)) + 1
    assert _yer(h) == {"YYY 102": 2, "ZZZ 103": 3}
    assert h["programs"][0]["finish"]["index"] == 3


def test_BU_DONEM_BAHARSA_yaz_HEMEN_arkasinda(tmp_path):
    con = _zincir(tmp_path)
    h = _kur(con, term="202620", donem=4, yaz="XXX 101")
    assert h["summer"]["placed"] and h["summer"]["index"] == 0
    assert h["summer"]["label"] == "2025-2026 Yaz"


def test_YAZ_onsarti_TUTMUYORSA_yerlesmiyor(tmp_path):
    con = _zincir(tmp_path)
    h = _kur(con, yaz="YYY 102")          # XXX yazdan önce geçilmiyor
    assert h["summer"]["placed"] is False
    assert "önşartı" in h["summer"]["reason"]
    assert _yer(h) == _yer(_kur(con))


def test_YAZ_ADAYLARI_yalniz_GECMISTE_YAZI_olanlar(tmp_path):
    con = _zincir(tmp_path, dagilim=[("XXX 101", "202510", 60), ("XXX 101", "202530", 12),
                                     ("YYY 102", "202510", 60), ("YYY 102", "202530", 2)])
    adaylar = [a["course"] for a in _kur(con)["summerCandidates"]]
    assert adaylar == ["XXX 101"]


# ------------------------------------------------------------------ arayüz (statik)
def test_RESIM_yalniz_DERS_PROGRAMI_ve_TARAYICIDA():
    f = KAYNAK[KAYNAK.index("async function resimIndir(){"):]
    f = f[:f.index("\n}\n")]
    kod = re.sub(r"/\*.*?\*/", " ", f, flags=re.S)
    # Dış kaynak, ağ isteği yok; not/transkript/GNO RESME GİRMİYOR.
    for yasak in ("fetch(", "XMLHttpRequest", "http://", "https://", "DATA.gpa",
                  "transcript", "grades"):
        assert yasak not in kod, yasak
    assert 'tuval.toBlob(r, "image/png")' in kod
    assert 'id="pngBtn"' in KAYNAK


def test_CIKARMA_onerisi_CAP_TABANINI_bozmuyor():
    f = KAYNAK[KAYNAK.index("def _yol_haritasi("):KAYNAK.index("def _plan_uyarisi(")]
    assert "if taban and cap_kredi(sonra) + 1e-9 < taban.minimum <= cap_kredi(bu) + 1e-9:" in f


# ------------------------------------------------------------------ uçtan uca (vitrin)
_CANLI = r'''
import sys, os, json
sys.path.insert(0, os.environ["ITUCAP_SRC"]); sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import vitrin
adres, h = vitrin.ac()
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1400, "height": 1000}, accept_downloads=True)
    pg = ctx.new_page()
    hatalar = []
    pg.on("pageerror", lambda e: hatalar.append(str(e)))
    pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(1200)
    R = pg.evaluate("() => DATA.roadmap")
    print("TAKENOW:" + json.dumps(R["takeNow"], ensure_ascii=False))
    print("YAZ:" + json.dumps(R["summerGains"], ensure_ascii=False))
    print("ROLLER:" + json.dumps({x["course"]: x["role"] for x in
          pg.evaluate("() => picks().map(p => ({course: p.cand.course, role: p.cand.role}))")}))
    print("KAYNAKLAR:" + json.dumps({i["course"]: i.get("seasonSource") for t in R["terms"]
                                     for i in t["items"]}, ensure_ascii=False))
    pg.evaluate("() => gorunumAc('roadmapSection')"); pg.wait_for_timeout(300)
    print("YAZKUTU:" + pg.evaluate("() => (document.querySelector('.yhyaz')||{innerText:''}).innerText.replace(/\\s+/g,' ')"))
    print("SIMDI:" + pg.evaluate("() => (document.querySelector('.yhsimdi')||{innerText:''}).innerText.replace(/\\s+/g,' ')"))
    # ★ Faz 126 — GEO 341E, programdaki BLG 252E ile KESİN çakışıyor: eski
    # "GEO 315E çıkar" önerisi uygulanamazdı. Düğme artık takas: BLG 252E
    # çıkıyor, GEO 341E'nin şube penceresi açılıyor.
    pg.click("[data-cikar]"); pg.wait_for_timeout(400)
    print("CIKAR:" + str(pg.evaluate("() => sel.some(x => x.course === 'BLG 252E')"))
          + "|" + pg.evaluate("() => (document.querySelector('dialog[open]')||{}).id || '-'")
          + "|" + pg.evaluate("() => document.documentElement.dataset.gorunum")
          + "|" + pg.evaluate("() => $('#undo').textContent"))
    pg.evaluate("() => { document.querySelector('dialog[open]').close(); geriAl(); }")
    pg.wait_for_timeout(200)
    # ÇAP ortalaması hedefi — ekrandaki sayı ve hesabın girdileri.
    print("CAPGNO:" + json.dumps(pg.evaluate("""() => ({
        ik: DATA.gpa.secondGpa[0], picks: picks().map(p => [p.cand.course, p.cand.credits]),
        retake: DATA.gpa.retake,
        satir: [...document.querySelectorAll('#gnoHedefBody .gnosatir[data-taban=ikinci]')]
          .map(e => e.querySelector('.gereken').textContent.trim())})"""), ensure_ascii=False))
    # Resim.
    pg.evaluate("() => gorunumAc('schedSection')")
    with pg.expect_download() as d:
        pg.click("#pngBtn")
    yol = os.path.join(os.environ["CIKTI"], "p.png"); d.value.save_as(yol)
    print("PNG:" + d.value.suggested_filename + "|" + open(yol, "rb").read(8).hex())
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
    monkeypatch.setenv("CIKTI", str(tmp_path))
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
    import json
    assert c["HATA"].startswith("0"), c["HATA"]

    # Y.4 — GEO 341E yükü aşıyor; öneri GEO 315E ve kazanç korunuyor.
    # ÇAP dersleri (tam 9 kredi = taban) önerilmiyor.
    t = json.loads(c["TAKENOW"])[0]
    roller = json.loads(c["ROLLER"])
    assert t["course"] == "GEO 341E" and t["overLoad"], t
    assert t["drop"]["course"] == "GEO 315E" and t["drop"]["lossTerms"] == 0, t
    assert roller[t["drop"]["course"]] != "CAP"
    # Faz 126 — takas: BLG 252E yerine; anadal 2 dönem erken, ÇAP aynı, ama
    # ÇAP yarıyıl tabanının altına düşürüyor ve bu YAZIYOR.
    assert t["swap"]["replaces"] == ["BLG 252E"] and t["swap"]["floorBreak"] is True, t
    assert {e["role"]: e["terms"] for e in t["swap"]["effects"]} == {"ANADAL": 2, "CAP": 0}
    assert "BLG 252E ile aynı saattedir" in c["SIMDI"] and "tabanının altına" in c["SIMDI"]
    assert "GEO 315E çıkarılarak dene" not in c["SIMDI"], "uygulanamaz öneri kalmış"

    # Y.3 — GEO 341E geçen yaz 14 öğrenciyle açıldı; ilk yazda alınırsa 2 dönem.
    y = json.loads(c["YAZ"])
    assert [(x["course"], x["term"], x["gains"][0]["terms"]) for x in y] == \
        [("GEO 341E", "2026-2027 Yaz", 2)], y
    assert "14 öğrenci" in c["YAZKUTU"] and "bu yaz da açılacağı anlamına gelmez" in c["YAZKUTU"]

    # Y.2 — iki ÇAP dersinin mevsimi planda yoktu; geçmişten okundu.
    k = json.loads(c["KAYNAKLAR"])
    assert k["BLG 335E"] == "gecmis" and k["BLG 336E"] == "gecmis", k

    ciktimi, pencere, gorunum, geri = c["CIKAR"].split("|")
    assert ciktimi == "False" and pencere == "detail" and gorunum == "schedSection", c["CIKAR"]
    assert geri == "Geri al: BLG 252E çıkarıldı", geri

    # Y.6 — ÇAP ortalaması: yalnız ÇAP planındaki dersler; Python'da aynı hesap.
    import math
    o = json.loads(c["CAPGNO"])
    kod = set(o["ik"]["codes"])
    secili = [(k, kr) for k, kr in o["picks"] if k in kod and kr > 0]
    T = sum(kr for _, kr in secili)
    tekrar = [k for k, _ in secili if k in o["retake"]]
    C = o["ik"]["credits"] - sum(o["retake"][k]["credits"] for k in tekrar)
    P_ = o["ik"]["points"] - sum(o["retake"][k]["points"] for k in tekrar)
    x = math.ceil(((2.0 * (C + T) - P_) / T) * 100 - 1e-6) / 100
    assert T == 9 and o["satir"] == [f"≥ {x:.2f}"], (o, x)

    # Y.5 — resim iniyor ve gerçekten PNG.
    ad, imza = c["PNG"].split("|")
    assert ad == "ders-programi.png" and imza == "89504e470d0a1a0a", c["PNG"]
