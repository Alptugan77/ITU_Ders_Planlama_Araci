"""Faz 90 — motor kontenjanı gerçek haliyle okuyor.

Kullanıcı 25.09.2026: *"please continue your work and improve this"*.
Gerçek katalogda 5. yarıyıl BLGE öğrencisiyle (transkriptli) bulundu:

* "Kontenjan kritik" bonusu dersin EN DOLU şubesine bakıyordu: 70 boş yerli
  BLG 351E "kritik"ti; yedi profilde adayların %70–100'ü bonusu alıyordu.
* Bütün şubeleri dolu ders de bonus alıyordu. "TM Elective I" havuzunda dolu
  BLG 345E ile 4 boş yerli BLG 368E eşit puan alıyor, eşitliği alfabe
  bozuyordu → öneri 1 dolu seçmeli içeriyordu.
* Şube seçimi dolu şubeyle boş şube arasında ayrım yapmıyordu: EHB 311E'nin
  boş ve çakışmayan şubesi varken öneri dolu şubeyi veriyordu.
"""
from itucap import recommend as REC


def _m(day, start=480, end=600):
    return REC.Meeting(day, start, end, None, None, None)


def _s(crn, course, day, capacity=50, enrolled=0, start=480, end=600):
    return REC.Section(crn, course, None, capacity, enrolled, (_m(day, start, end),))


def _c(course, sections, role="ANADAL", required=False, slot=0):
    return REC.Candidate(course, "", role, 5, 3, 0, 0, False, required, sections,
                         slot_id=slot, slot_ids=(slot,) if slot else ())


def test_KONTENJAN_DURUMU():
    D = REC.kontenjan_durumu
    assert D([_s("1", "A", 1, 50, 50), _s("2", "A", 2, 50, 50)]) == "dolu"
    assert D([_s("1", "A", 1, 50, 49)]) == "kritik"                  # 1 yer kaldı
    # ★ Eskiden "kritik": şubelerden biri dolu, öbüründe 45 yer var.
    assert D([_s("1", "A", 1, 50, 50), _s("2", "A", 2, 50, 5)]) == "acik"
    # Kontenjanı ilan edilmemiş şube varsa iddia yok.
    assert D([_s("1", "A", 1, 0, 0), _s("2", "A", 2, 50, 50)]) == "bilinmiyor"
    assert D([]) == "bilinmiyor"


def test_PUAN_bonus_ve_ceza():
    bos_yeri_var = _c("BLG 351E", [_s("1", "BLG 351E", 1, 50, 50),
                                   _s("2", "BLG 351E", 2, 80, 10)])
    kapali = _c("BLG 345E", [_s("3", "BLG 345E", 3, 40, 40)])
    kritik = _c("BLG 337E", [_s("4", "BLG 337E", 4, 40, 36)])
    bilinmiyor = _c("SNT 105E", [_s("5", "SNT 105E", 5, 0, 0)])
    REC.score_all([bos_yeri_var, kapali, kritik, bilinmiyor])
    anahtar = lambda c: {p["key"] for p in c.parts}                  # noqa: E731
    assert "scarcity" not in anahtar(bos_yeri_var)
    assert "scarcity" in anahtar(kritik) and "kontenjan kritik" in kritik.reasons
    assert "full" in anahtar(kapali) and "scarcity" not in anahtar(kapali)
    assert "bütün şubeler dolu — kontenjan izlenmeli" in kapali.reasons
    assert not {"full", "scarcity"} & anahtar(bilinmiyor)
    # Kırılım toplamı puanla tutuyor (Faz 27 kuralı).
    for c in (bos_yeri_var, kapali, kritik, bilinmiyor):
        assert round(sum(p["points"] for p in c.parts), 1) == c.score


def test_AYNI_HAVUZDA_acik_ders_dolu_dersin_onunde():
    """BLG 345E (dolu) alfabede önde; eskiden eşit puanla o seçiliyordu."""
    dolu = _c("BLG 345E", [_s("1", "BLG 345E", 1, 40, 40)], slot=7)
    acik = _c("BLG 368E", [_s("2", "BLG 368E", 2, 40, 36)], slot=7)
    en_iyi = REC.build_schedules(REC.score_all([dolu, acik]), max_load=99, limit=3)[0]
    assert [p.candidate.course for p in en_iyi.picks] == ["BLG 368E"]


def test_HAVUZ_bol_yerli_ders_de_dolu_dersin_onunde():
    """Açık ders 'kritik' değilse (bol yer) bonus almıyor; iki ders yalnız
    'tek şube'yle eşit kalırdı ve alfabe dolu dersi seçerdi. Eşitliği -5'lik
    'dolu' cezası bozuyor (BLG 348E: 11 boş yer)."""
    dolu = _c("BLG 345E", [_s("1", "BLG 345E", 1, 40, 40)], slot=7)
    bol = _c("BLG 348E", [_s("2", "BLG 348E", 2, 40, 5)], slot=7)
    REC.score_all([dolu, bol])
    assert not {"scarcity"} & {p["key"] for p in bol.parts}
    en_iyi = REC.build_schedules([dolu, bol], max_load=99, limit=3)[0]
    assert [p.candidate.course for p in en_iyi.picks] == ["BLG 348E"]


def test_HAVUZDA_hepsi_doluysa_yine_oneriliyor():
    """Alternatif yoksa dolu ders öneriden düşmüyor (arayüz 'dolu' der)."""
    a = _c("SNT 105E", [_s("1", "SNT 105E", 1, 40, 40)], slot=9)
    b = _c("SNT 114E", [_s("2", "SNT 114E", 2, 40, 40)], slot=9)
    en_iyi = REC.build_schedules(REC.score_all([a, b]), max_load=99, limit=3)[0]
    assert len(en_iyi.picks) == 1


def test_SUBE_bos_olan_secilir():
    ehb = _c("EHB 311E", [_s("10", "EHB 311E", 1, 30, 30), _s("11", "EHB 311E", 2, 30, 28)],
             required=True)
    en_iyi = REC.build_schedules(REC.score_all([ehb]), max_load=99, limit=3)[0]
    assert en_iyi.picks[0].section.crn == "11"


def test_SUBE_ileriye_bakis_yaniltsa_da_bos_sube():
    """EHB 311E durumu: açık şube, programa ZATEN giremeyecek bir dersle
    (burada kredi sınırı) çakıştığı için ileriye bakışta 'pahalı' görünüyordu;
    aynı ders kümesi dolu şubeyle kuruluyordu. Dolu şubenin maliyeti bu küçük
    farkı bozuyor."""
    x = _c("EHB 311E", [_s("10", "EHB 311E", 1, 30, 30), _s("11", "EHB 311E", 2, 30, 28)],
           required=True)
    z = _c("SNT 105E", [_s("12", "SNT 105E", 2, 40, 10)], slot=3)      # yalnız Salı
    cands = REC.score_all([x, z])
    en_iyi = REC.build_schedules(cands, max_load=3, limit=3)[0]      # ikisi birden sığmıyor
    assert {p.candidate.course: p.section.crn for p in en_iyi.picks} == {"EHB 311E": "11"}


def test_SUBE_dolu_olan_baska_dersi_kurtariyorsa_secilir():
    """Dolu şubenin maliyeti sınırlı: boş şube değerli bir dersin TEK şubesiyle
    çakışıyorsa dolu şube seçilir ve iki ders birlikte kalır."""
    x = _c("X 101", [_s("1", "X 101", 1, 30, 30), _s("2", "X 101", 2, 30, 0)], role="CAP")
    y = _c("Y 101", [_s("3", "Y 101", 2, 30, 0)], required=True)
    en_iyi = REC.build_schedules(REC.score_all([x, y]), max_load=99, limit=3)[0]
    secim = {p.candidate.course: p.section.crn for p in en_iyi.picks}
    assert secim == {"X 101": "1", "Y 101": "3"}, secim
    assert REC.DOLU_SUBE_MALIYETI < REC.WEIGHTS["required"]


# ------------------------------------------------------------ danışman özeti
import json  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

from itucap import ui as UI  # noqa: E402

_CANLI = r'''
import sys, os, json
sys.path.insert(0, os.environ["ITUCAP_SRC"]); sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import vitrin
adres, h = vitrin.ac()
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 1000})
    hatalar = []
    pg.on("pageerror", lambda e: hatalar.append(str(e)))
    pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(800)
    # BLG 223E'yi DOLU 22302'ye al (açık 22301 programla çakışmıyor).
    pg.evaluate("() => { sel.find(x => x.course === 'BLG 223E').crn = '22302'; render(); }")
    pg.wait_for_timeout(200)
    print("BOS:" + json.dumps(pg.evaluate("() => (bosSube('BLG 223E') || {}).crn || null")))
    # Başvuru eşiği tutmuyor (yandal; vitrin öğrencisi ÇAP'lı, listede yandal
    # başvurusu yok — kurallar.toml'daki biçimde ekleniyor) + ÇAP'a devam tutmuyor.
    pg.evaluate("""() => { DATA.gpa.thresholds.push({key: 'yandal_basvuru', kind: 'basvuru',
        scope: 'yandal', label: 'Yandal başvurusu', min: 2.5, ok: false, basis: 'genel'});
      DATA.gpa.thresholds.find(t => t.key === 'devam').ok = false; }""")
    html = pg.evaluate("() => danismanOzeti()")
    print("SORU:" + json.dumps(pg.evaluate("""(h) => { const x = document.createElement('div'); x.innerHTML = h;
        return [...x.querySelectorAll('.dsoru li')].map(e => e.textContent.replace(/\\s+/g,' ').trim()); }""", html), ensure_ascii=False))
    print("SATIR:" + json.dumps(pg.evaluate("""(h) => { const x = document.createElement('div'); x.innerHTML = h;
        return [...x.querySelectorAll('tbody tr')].filter(r => /BLG 223E|GEO 331E/.test(r.textContent))
          .map(r => r.textContent.replace(/\\s+/g,' ').trim()); }""", html), ensure_ascii=False))
    print("HATA:" + str(len(hatalar)) + " " + " | ".join(hatalar)[:300])
    b.close()
h.shutdown()
'''


def test_DANISMAN_vitrin(tmp_path, monkeypatch):
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
    assert c["HATA"].startswith("0"), c["HATA"]
    assert json.loads(c["BOS"]) == "22301"
    soru = json.loads(c["SORU"])
    dolu = [s for s in soru if "kontenjanı doludur" in s]
    # Tek soru; boş şubesi olan BLG 223E soru DEĞİL, GEO 331E soru.
    assert len(dolu) == 1 and "GEO 331E (CRN 13603)" in dolu[0] and "BLG 223E" not in dolu[0], soru
    assert ("Yandal başvurusunu düşünürsem GNO ≥ 2.50 gerekmektedir; tahmini GNO'm 2.78. "
            "Bu hedef benim için gerçekçi midir?") in soru, soru
    assert any(s.startswith("ÇAP'a devam") and s.endswith("Bu eşiğe nasıl ulaşabilirim?")
               for s in soru), soru
    satir = json.loads(c["SATIR"])
    blg = [x for x in satir if x.startswith("BLG 223E")][0]
    geo = [x for x in satir if x.startswith("GEO 331E")][0]
    assert "22302 dolu" in blg and "boş şube: 22301" in blg, blg
    assert "13603 dolu" in geo and "boş şube" not in geo, geo
