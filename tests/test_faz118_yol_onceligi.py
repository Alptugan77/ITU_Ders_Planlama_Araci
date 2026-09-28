"""Faz 118 — yol haritası önceliği: "anadala öncelik ver" / "ikisini en kısa
sürede bitir" (kullanıcı isteği 28.09.2026).

Harita her dönemi tek bir sırayla dolduruyordu (en uzun zinciri başlatan ders
önce). Artık iki programlı haritada üç yerleştirme sırası deneniyor ve ayarın
ölçütüne göre en iyisi seçiliyor:
* birlikte — en geç biten programın bitişi en erken;
* anadal   — anadalın bitişi en erken, eşitlikte ikinci programınki.

Gerçek katalogda 142 anadal+ÇAP çiftinde (3. yarıyıl, 21 kredi): "birlikte"
19 çiftte ortak bitişi 1–2 dönem öne çekiyor; "anadal" 27 çiftte anadalı
1–2 dönem erken bitiriyor. Sırayı "anadal önce" diye SABİTLEMEK 20 çiftte her
iki bitişi de kötüleştiriyordu — bu yüzden arama.

Aynı turda hız: denklik listesi her kurulumda kopyalanıyordu (3183 denkliğin
dizini baştan), dersin AKTS'si dizinsiz sorguyla her seferinde okunuyordu. Tek
kurulum 78 → 15 ms; üç sıralı arama 46 ms (eski tek kurulumdan hızlı).
"""
import pathlib
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from itucap import config
from itucap import istek as IST
from itucap import notlar as ND
from itucap import policy as POL
from itucap import server
from itucap import ui as UI
from itucap import yolharitasi as YH
from test_faz57_yol_haritasi import ANADAL, CAP, _katalog, _kur

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


# ------------------------------------------------------------------ düzenek
def _iki_program(tmp_path):
    """Bu dönem Bahar (202520). Anadalın dört dersi her dönem açılıyor (plan
    Güz, bu Bahar şubesi var); ÇAP'ın dört dersi YALNIZ Güz (plan 7. dönem).
    Dönem sınırı 12 kredi = iki ders.

    kritik / anadal önce: Güz'leri anadal dolduruyor → anadal 2., ÇAP 5. dönem.
    ÇAP önce: Güz'ler ÇAP'ın, Baharlar anadalın → ÇAP 3., anadal 4. dönem."""
    a = [f"AAA 10{i}" for i in range(1, 5)]
    c = [f"CCC 20{i}" for i in range(1, 5)]
    con = _katalog(tmp_path, [(k, 6, None) for k in a + c], [(k, 5) for k in a],
                   lesson=[(str(100 + i), k) for i, k in enumerate(a)], cap=c)
    con.execute("UPDATE plan_slot SET term_no=7 WHERE plan_id=2")
    con.commit()
    return con


def _bitis(h):
    return {p["role"]: (p["finish"] or {}).get("index") for p in h["programs"]}


def _harita(con, **kw):
    return _kur(con, planlar=ANADAL + CAP, term="202520", donem=5, max_load=12, **kw)


# ------------------------------------------------------------------ motor
def test_BIRLIKTE_en_gec_biteni_one_cekiyor(tmp_path):
    con = _iki_program(tmp_path)
    assert _bitis(_harita(con, oncelik="kritik")) == {"ANADAL": 2, "CAP": 5}
    h = _harita(con, oncelik="birlikte")
    assert _bitis(h) == {"ANADAL": 4, "CAP": 3}, "ortak bitiş 5 → 4 olmalıydı"
    assert h["priority"]["setting"] == "birlikte"
    assert h["priority"]["order"] == "ikinci_once"
    assert any(a.startswith("Öncelik: programların birlikte") for a in h["assumptions"])


def test_ANADAL_onceligi_anadali_en_erken_bitiriyor(tmp_path):
    con = _iki_program(tmp_path)
    h = _harita(con, oncelik="anadal")
    assert _bitis(h) == {"ANADAL": 2, "CAP": 5}
    # Anadal bitişi eşit (kritik ile anadal önce): tercih "anadal önce".
    assert h["priority"]["order"] == "anadal_once"
    assert any(a.startswith("Öncelik: anadal.") for a in h["assumptions"])


def test_OBUR_AYARIN_SONUCU_da_donuyor(tmp_path):
    """Arayüz "öbür ayar seçilirse" satırını buradan yazıyor — ikinci kurulum yok."""
    con = _iki_program(tmp_path)
    s = _harita(con, oncelik="birlikte")["priority"]["options"]
    assert s["birlikte"]["order"] == "ikinci_once"
    assert s["anadal"]["order"] == "anadal_once"
    assert {r: f["index"] for r, f in s["anadal"]["finish"].items()} == {"ANADAL": 2, "CAP": 5}
    assert {r: f["index"] for r, f in s["birlikte"]["finish"].items()} == {"ANADAL": 4, "CAP": 3}
    # Seçenekler iki ayarda da AYNI (aynı üç kurulum, aynı ölçüt).
    assert _harita(con, oncelik="anadal")["priority"]["options"] == s


def test_TABAN_varsa_varsayimda_yaziyor(tmp_path):
    con = _iki_program(tmp_path)
    taban = POL.SecondFloor(minimum=6, start_term=3, verified=True, source="test")
    h = _harita(con, oncelik="birlikte", taban=taban)
    assert any("ÇAP yarıyıl kredi tabanı her sırada uygulanmıştır" in a
               for a in h["assumptions"])
    h = _harita(con, oncelik="birlikte")
    assert not any("tabanı her sırada" in a for a in h["assumptions"])


def _ozet(**roller):
    return {"programs": [{"role": r, "finish": None if i is None else {"index": i},
                          "unplaced": u} for r, (i, u) in roller.items()]}


def test_OLCUT_yerlesmeyen_once_sonra_bitis():
    iyi = _ozet(ANADAL=(6, 0), CAP=(6, 0))
    yerlesmeyen = _ozet(ANADAL=(3, 0), CAP=(None, 1))      # "daha erken" ama eksik
    assert YH._olcut(iyi, "birlikte", "ikinci_once") < YH._olcut(yerlesmeyen, "birlikte", "kritik")
    # İkisi de eksikse AZ eksik olan — öbürünün anadalı daha erken bitse bile.
    assert YH._olcut(_ozet(ANADAL=(6, 0), CAP=(None, 1)), "birlikte", "ikinci_once") < \
        YH._olcut(_ozet(ANADAL=(3, 0), CAP=(None, 2)), "birlikte", "kritik")
    # birlikte: en geç biten; eşitse toplam; o da eşitse sıra tercihi (kritik).
    assert YH._olcut(_ozet(ANADAL=(5, 0), CAP=(3, 0)), "birlikte", "anadal_once") < \
        YH._olcut(_ozet(ANADAL=(2, 0), CAP=(6, 0)), "birlikte", "kritik")
    assert YH._olcut(_ozet(ANADAL=(4, 0), CAP=(4, 0)), "birlikte", "ikinci_once") < \
        YH._olcut(_ozet(ANADAL=(4, 0), CAP=(5, 0)), "birlikte", "kritik")
    assert YH._olcut(_ozet(ANADAL=(4, 0), CAP=(4, 0)), "birlikte", "kritik") < \
        YH._olcut(_ozet(ANADAL=(4, 0), CAP=(4, 0)), "birlikte", "ikinci_once")
    # anadal: önce anadalın yerleşmeyeni ve bitişi; eşitse ÇAP'ı erken biten.
    assert YH._olcut(_ozet(ANADAL=(2, 0), CAP=(9, 0)), "anadal", "kritik") < \
        YH._olcut(_ozet(ANADAL=(3, 0), CAP=(3, 0)), "anadal", "ikinci_once")
    assert YH._olcut(_ozet(ANADAL=(3, 0), CAP=(4, 0)), "anadal", "ikinci_once") < \
        YH._olcut(_ozet(ANADAL=(3, 0), CAP=(6, 0)), "anadal", "anadal_once")
    assert YH._olcut(_ozet(ANADAL=(3, 0), CAP=(9, 1)), "anadal", "kritik") < \
        YH._olcut(_ozet(ANADAL=(4, 0), CAP=(4, 0)), "anadal", "anadal_once")
    assert YH._olcut(_ozet(ANADAL=(3, 0), CAP=(4, 0)), "anadal", "anadal_once") < \
        YH._olcut(_ozet(ANADAL=(3, 0), CAP=(4, 0)), "anadal", "kritik")


def test_TEK_PROGRAMDA_tek_kurulum(tmp_path, monkeypatch):
    con = _iki_program(tmp_path)
    say = []
    asil = YH._kur
    monkeypatch.setattr(YH, "_kur", lambda *a, **k: say.append(k["sira"]) or asil(*a, **k))
    h = _kur(con, planlar=ANADAL, term="202520", donem=5, max_load=12, oncelik="anadal")
    assert say == ["kritik"] and h["priority"]["options"] is None
    say.clear()
    _harita(con, oncelik="birlikte")
    assert sorted(say) == sorted(YH.SIRALAR)


def test_SIRA_adlari_ayar_adlarindan_ayri_ve_gecersiz_reddediliyor(tmp_path):
    assert not set(YH.ONCELIKLER) & set(YH.SIRALAR), "ad çakışması: ayar tek sıra sanılır"
    assert config.YOL_ONCELIKLERI == YH.ONCELIKLER
    con = _iki_program(tmp_path)
    with pytest.raises(ValueError):
        _harita(con, oncelik="hizli")
    # Sabit sıra istenirse YALNIZ o sıra (türetilen haritalar).
    h = _harita(con, oncelik="ikinci_once")
    assert h["priority"] == {"setting": None, "order": "ikinci_once", "options": None}


def test_SIRA_anahtari():
    from types import SimpleNamespace as N
    a = N(roller={"ANADAL"}, yukseklik=1, donem_no=5, havuz="", anahtar="a")
    c = N(roller={"CAP"}, yukseklik=3, donem_no=7, havuz="", anahtar="c")
    ortak = N(roller={"ANADAL", "CAP"}, yukseklik=1, donem_no=6, havuz="", anahtar="o")
    sirala = lambda s: [x.anahtar for x in sorted([a, c, ortak], key=YH.sira_anahtari(s))]
    assert sirala("kritik") == ["c", "a", "o"]
    assert sirala("anadal_once") == ["a", "o", "c"]
    assert sirala("ikinci_once") == ["c", "o", "a"]


# ------------------------------------------------------------------ ayar ve uç
def test_AYAR_okunuyor_yaziliyor_gecersiz_varsayilana_dusuyor(tmp_path):
    yol = tmp_path / "settings.toml"
    yol.write_text('[student]\nanadal_program = "AAA"\n', encoding="utf-8")
    assert config.Settings.load(yol).yol_onceligi == "birlikte"
    config.update_settings({"yol_onceligi": "anadal"}, path=yol)
    assert 'yol_onceligi = "anadal"' in yol.read_text(encoding="utf-8")
    assert config.Settings.load(yol).yol_onceligi == "anadal"
    yol.write_text('[student]\nyol_onceligi = "hizli"\n', encoding="utf-8")
    assert config.Settings.load(yol).yol_onceligi == "birlikte"


def test_SUNUCU_ucu_dogruluyor_ve_yaziyor(monkeypatch):
    yazilan = []
    monkeypatch.setattr(config, "update_settings", lambda v, path=None: yazilan.append(v))
    with pytest.raises(ValueError):
        server.State.save_roadmap_priority(None, "hizli")
    assert yazilan == []
    assert server.State.save_roadmap_priority(None, "anadal") == "anadal"
    assert yazilan == [{"yol_onceligi": "anadal"}]
    assert "/api/yolonceligi" not in server.READ_ONLY_PATHS    # yazıyor → durum döner


def test_HER_HARITA_ayari_kullaniyor():
    """Sayfadaki harita, "bu dönem alırsan", kalma riski, senaryo ve ÇAP
    seçenekleri AYNI ayarla kurulmalı — biri unutulursa iki ekran farklı bitiş
    söyler."""
    cagrilar = re.findall(r"YH\.kur\((.*?)\)\n", KAYNAK, re.S)
    assert len(cagrilar) == 4
    for c in cagrilar:
        assert "oncelik=settings.yol_onceligi" in c, c[:120]


def test_AKTS_bellegi_ders_basina(tmp_path):
    con = _katalog(tmp_path, [("AAA 101", 3, None), ("BBB 102", 4, None)], [("AAA 101", 5)])
    with IST.istek():
        assert ND.ders_aktsi(con, "AAA 101") == 5.0
        assert ND.ders_aktsi(con, "BBB 102") == 6.0
        con.execute("UPDATE course SET ects=9 WHERE code='AAA 101'")
        assert ND.ders_aktsi(con, "AAA 101") == 5.0          # istek içinde bir kez
    assert ND.ders_aktsi(con, "AAA 101") == 9.0              # bağlam dışında taze


def test_DENKLIK_listesi_kopyalanmiyor(tmp_path, monkeypatch):
    """`rules` denklik dizinini liste nesnesine göre önbelleğe alıyor; kopya her
    kurulumda dizini baştan kurduruyordu (gerçek katalogda ~25 ms)."""
    from itucap import rules as R
    con = _iki_program(tmp_path)
    esd = [R.Equivalence(1, "AAA 101", (("ZZZ 101", "DD"),), "official", True)]
    gorulen = []
    asil = R.expand_with_equivalences
    monkeypatch.setattr(R, "expand_with_equivalences",
                        lambda g, e, *a, **k: gorulen.append(e) or asil(g, e, *a, **k))
    _harita(con, oncelik="birlikte", equivalences=esd)
    assert gorulen and all(e is esd for e in gorulen)


# ------------------------------------------------------------------ arayüz
def test_ARAYUZ_panel_ve_uc():
    js = KAYNAK[KAYNAK.index("function yhOncelikPaneli("):]
    js = js[:js.index("\n}\n")]
    assert "if(!P || !P.options) return" in js, "tek programda panel çıkmamalı"
    assert 'aria-pressed="${k === secili}"' in js
    assert "İki ayar bu plan için aynı bitişi vermektedir." in js
    assert 'api("/api/yolonceligi", {oncelik: b.dataset.oncelik})' in KAYNAK
    assert "${yhOncelikPaneli(T, R)}${yhSenaryoPaneli(T)}" in KAYNAK


_CANLI = r'''
import sys, os
sys.path.insert(0, os.environ["ITUCAP_SRC"]); sys.path.insert(0, os.environ["ITUCAP_TOOLS"])
import vitrin
adres, h = vitrin.ac()
from itucap import config
ayar = config.ROOT / "config" / "settings.toml"
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    for ad, boyut in (("M", {"width": 1400, "height": 1000}), ("T", {"width": 390, "height": 844})):
        pg = b.new_page(viewport=boyut)
        hatalar = []
        pg.on("pageerror", lambda e: hatalar.append(str(e)))
        pg.goto(adres, wait_until="networkidle", timeout=30000); pg.wait_for_timeout(1200)
        pg.evaluate("() => gorunumAc('roadmapSection')"); pg.wait_for_timeout(300)
        panel = "() => (document.querySelector('.yhoncelik')||{innerText:''}).innerText.replace(/\\s+/g,' ')"
        basili = "() => [...document.querySelectorAll('.yhoncelik [data-oncelik]')].map(x => x.dataset.oncelik + '=' + x.getAttribute('aria-pressed')).join(',')"
        print(ad + "PANEL1:" + pg.evaluate(panel))
        print(ad + "BASILI1:" + pg.evaluate(basili))
        print(ad + "TASMA:" + str(pg.evaluate("() => document.documentElement.scrollWidth <= innerWidth")))
        if ad == "M":
            pg.click('.yhoncelik [data-oncelik="anadal"]'); pg.wait_for_timeout(2500)
            print("MBASILI2:" + pg.evaluate(basili))
            print("MPANEL2:" + pg.evaluate(panel))
            print("MVARSAYIM:" + str(pg.evaluate("() => DATA.roadmap.assumptions.some(a => a.startsWith('Öncelik: anadal.'))")))
            print("MAYAR:" + str('yol_onceligi = "anadal"' in ayar.read_text(encoding="utf-8")))
            pg.click('.yhoncelik [data-oncelik="birlikte"]'); pg.wait_for_timeout(2500)
            print("MBASILI3:" + pg.evaluate(basili))
        print(ad + "HATA:" + str(len(hatalar)) + " " + " | ".join(hatalar)[:300])
        pg.close()
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
    c = dict(s.split(":", 1) for s in r.stdout.strip().splitlines()
             if ":" in s and s.split(":", 1)[0].isupper())
    for ad in "MT":
        assert c[ad + "HATA"].startswith("0"), c[ad + "HATA"]
        assert c[ad + "BASILI1"] == "birlikte=true,anadal=false", c[ad + "BASILI1"]
        assert "ÖNCELİK" in c[ad + "PANEL1"] and "Anadala öncelik ver" in c[ad + "PANEL1"]
        assert c[ad + "TASMA"] == "True", "telefonda yatay taşma"
    assert ("seçilirse:" in c["MPANEL1"]
            or "aynı bitişi vermektedir" in c["MPANEL1"]), c["MPANEL1"]
    assert c["MBASILI2"] == "birlikte=false,anadal=true", c["MBASILI2"]
    assert c["MVARSAYIM"] == "True" and c["MAYAR"] == "True"
    assert c["MBASILI3"] == "birlikte=true,anadal=false"
