"""Faz 53 — SAAT ARALIĞINA KİLİT (yapılacaklar 2.4) + yol üstünde çıkanlar.

Kullanıcı 21.09.2026: *"onun dışında yapılacak güncellemeleri ve
geliştirmeleri uygulayabilirsin uygunca"* — listedeki 2.4: "bu ders SABAH
olsun, şubesi fark etmez". Faz 45'in kilidi ŞUBEYE bağlıydı; saat
önemliyse tek yol bir şube seçip ona kilitlemekti.

Gerçek veriyle ölçüldü (21.09.2026, 26 durum = ≥2 şubesi aralığa uyan
ders × aralık, motorun KENDİ sıralama ölçüsüyle):

| | aralık kilidi ≥ en iyi tek şube kilidi | süre medyanı |
|---|---|---|
| aralıktaki 3 şubeyi dene (Faz 45 dalı) | 16 / 26 | 0,36 sn |
| kilitli dersi öne al | 21 / 26 | 0,12 sn |
| **öne al + her şube dalına adil pay** | **26 / 26** | 0,18 sn |

⚠️⚠️ Yol üstünde Faz 45'in kendi hatası çıktı: 139 tek şube kilidinin
**22'si HİÇ PROGRAM ÜRETMİYORDU** (`ALM 102`nin iki şubesi de). Düşük puanlı
kilitli ders adayların sonunda kalıyor, motor bütçeyi ölü dallarda
bitiriyordu; arayüz de tek kilit ve hiç meşgul saat yokken "kilitler
birbiriyle ya da meşgul saatinle çakışıyor" diyordu. Kilitli ders artık önce
yerleşiyor: 22'nin 22'si program üretiyor.
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
from itucap import recommend as REC                           # noqa: E402
from itucap import ui as UI                                   # noqa: E402

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")
REC_KAYNAK = pathlib.Path(REC.__file__).read_text(encoding="utf-8")


def _kod(metin: str) -> str:
    """Yorumları söker — bekçi kendi yorumundaki dizgeyi kod sanmasın
    (Faz 48/51'in dersi)."""
    metin = re.sub(r"/\*.*?\*/", " ", metin, flags=re.S)
    return re.sub(r"(?m)^\s*#.*$", " ", metin)


def _fn(ad: str) -> str:
    m = re.search(r"(?:async )?function " + ad + r"\(.*?\)\{(.*?)\n\}", KAYNAK, re.S)
    assert m, f"{ad} yok"
    return _kod(m.group(1))


# --------------------------------------------------------------- yardımcı
def _sube(crn, kod, *saatler):
    return REC.Section(crn=crn, course=kod, instructor=None, capacity=40,
                       enrolled=0, meetings=tuple(
                           REC.Meeting(g, b, s, None, None, None) for g, b, s in saatler))


def _aday(kod, subeler, puan=50.0, **kw):
    ayar = dict(name=kod, role="ANADAL", ects=4.0, credits=3.0, unlocks=0,
                tier=0, critical=False, required=True, sections=subeler, score=puan)
    ayar.update(kw)
    return REC.Candidate(course=kod, **ayar)


SABAH, OGLEDEN = REC.KILIT_ONAYAR["sabah"], REC.KILIT_ONAYAR["ogleden_sonra"]


# ===================================================== 1. biçim
def test_ARALIK_okunuyor_ve_BOZUK_ayriliyor():
    assert REC.kilit_araligi("08:30-12:30") == (510, 750)
    assert REC.kilit_araligi(" 8:30 - 12:30 ") == (510, 750)
    assert REC.kilit_araligi("12:30-24:00") == (750, 1440)
    for bozuk in ("8.30-12.30", "12:30-08:30", "10:00-10:00", "12:61-13:00",
                  "23:00-25:00", "sabah", "", "13601"):
        assert REC.kilit_araligi(bozuk) is None, bozuk
    assert REC.kilit_bicimi("13601") == "sube"
    assert REC.kilit_bicimi("00:00-12:30") == "aralik"
    # ⚠️ Bozuk değer CRN SAYILMAZ — sayılsaydı hiçbir şubeyle eşleşmez, ders
    # zorunlu kalır ve BÜTÜN öneriler boşalırdı.
    for bozuk in ("8.30-12.30", "", "ABC", "12:30-08:30"):
        assert REC.kilit_bicimi(bozuk) == "bozuk", bozuk
    assert REC.aralik_yazi(510, 750) == "08:30-12:30"


def test_ONAYAR_VERIDEN_secildi():
    """12:30: hiçbir ders 12:00'de başlamıyor, sabah dersleri en geç 12:29'da
    bitiyor (763 buluşma), öğleden sonrakiler 12:30'da başlıyor (178)."""
    assert SABAH == (0, 750) and OGLEDEN == (750, 1440)
    js = re.search(r"const KILIT_ARALIKLARI = \[(.*?)\];", KAYNAK, re.S).group(1)
    assert '"00:00-12:30"' in js and '"12:30-24:00"' in js, \
        "arayüzün düğmeleri motorun ön ayarlarından ayrışmış"
    assert "const OGLE = 12 * 60 + 30;" in KAYNAK


def test_SAATSIZ_sube_ARALIGA_UYMAZ():
    """⚠️ "Sabah olsun" diyene saati bilinmeyen şubeyi vermek, bilinmeyeni
    biliniyor gibi göstermek olurdu (3417 şubenin 328'inin saati yok)."""
    assert REC.araliga_uyar(_sube("1", "A", (1, 510, 629)), *SABAH)
    assert not REC.araliga_uyar(_sube("2", "A", (1, 690, 809)), *SABAH), "12:30'u aşan"
    assert not REC.araliga_uyar(_sube("3", "A", (1, 510, 629), (3, 810, 929)), *SABAH), \
        "bir buluşması öğleden sonra olan şube sabah sayıldı"
    assert not REC.araliga_uyar(_sube("4", "A"), *SABAH), "saatsiz şube aralığa uydu"
    assert not REC.araliga_uyar(_sube("4", "A"), *OGLEDEN)


# ===================================================== 2. motor
def _havuz():
    """AAA: Pzt sabah (300) · Sal öğleden sonra (301) · Çar öğleden sonra (302)
    BBB: yalnız Sal öğleden sonra — AAA'nın 301'iyle ÇAKIŞIYOR."""
    return [
        _aday("AAA 101", [_sube("300", "AAA 101", (1, 540, 660)),
                          _sube("301", "AAA 101", (2, 810, 930)),
                          _sube("302", "AAA 101", (3, 870, 990))], puan=60),
        _aday("BBB 102", [_sube("400", "BBB 102", (2, 810, 930))], puan=50),
    ]


def test_ARALIK_kilidi_DERSI_tutuyor_ve_SAATE_uyuyor():
    """★★ İsteğin çekirdeği: ders HER öneride var ve şubesi aralıkta."""
    sonuc = REC.build_schedules(_havuz(), max_load=35, limit=3,
                                locked={"AAA 101": REC.aralik_yazi(*OGLEDEN)})
    assert sonuc
    for s in sonuc:
        p = {x.candidate.course: x.section for x in s.picks}
        assert "AAA 101" in p, "ders programdan düştü"
        assert REC.araliga_uyar(p["AAA 101"], *OGLEDEN), f"aralık dışı: {p['AAA 101'].crn}"


def test_SUBE_MOTORA_kaliyor():
    """★★ Aralık kilidinin CRN kilidinden farkı: motor aralıktaki ÖBÜR
    şubeyi de deniyor. 301'e kilitlemek BBB'yi düşürüyor; "öğleden sonra"
    kilidi 302'yi seçip ikisini birden tutuyor."""
    crn = REC.build_schedules(_havuz(), max_load=35, limit=1,
                              locked={"AAA 101": "301"})[0]
    aralik = REC.build_schedules(_havuz(), max_load=35, limit=1,
                                 locked={"AAA 101": REC.aralik_yazi(*OGLEDEN)})[0]
    assert set(crn.courses()) == {"AAA 101"}
    assert set(aralik.courses()) == {"AAA 101", "BBB 102"}
    assert {p.candidate.course: p.section.crn for p in aralik.picks}["AAA 101"] == "302"


def test_ARALIKTA_sube_YOKSA_sessizce_kaymiyor():
    """Faz 45'in kapanmış şube kuralıyla aynı: kilit sert, sonuç boş —
    arayüz bunu `neden: "aralik"` ile söylüyor."""
    tek = [_aday("AAA 101", [_sube("300", "AAA 101", (1, 540, 660))])]
    assert REC.build_schedules(tek, max_load=35, limit=3,
                               locked={"AAA 101": REC.aralik_yazi(*OGLEDEN)}) == []


def test_BOZUK_kilit_ONERILERI_BOSALTMIYOR():
    """⚠️ Elle yazılmış `"8.30-12.30"` Faz 45'te CRN sayılırdı: hiçbir şubeyle
    eşleşmez, ders zorunlu kalır, bütün öneriler boşalırdı."""
    kilitsiz = REC.build_schedules(_havuz(), max_load=35, limit=3)
    bozuk = REC.build_schedules(_havuz(), max_load=35, limit=3,
                                locked={"AAA 101": "8.30-12.30"})
    assert [s.courses() for s in bozuk] == [s.courses() for s in kilitsiz]


def test_KILITSIZ_sonuclar_BIREBIR_AYNI():
    """Öne alma ve adil pay YALNIZ kilit/zorunlu varken devrede."""
    assert "if pinned:\n        cands = sorted(cands, key=lambda c: c.course not in pinned)" \
        in REC_KAYNAK
    cs = _havuz()
    a = REC.build_schedules(cs, max_load=35, limit=3)
    assert [c.course for c in cs] == ["AAA 101", "BBB 102"], "çağıranın listesi değişti"
    b = REC.build_schedules(list(cs), max_load=35, limit=3, locked={})
    assert [s.courses() for s in a] == [s.courses() for s in b]


def _budama_havuzu():
    """Gerçek hatanın küçük modeli: yüksek puanlı 18 ders birbirine
    çakışmıyor (2^18 alt küme), EN YÜKSEK puanlısı kilitli dersin TEK
    şubesiyle çakışıyor. Kilitli ders en sonda → motor önce H01'i koyuyor,
    kalan 17'nin bütün alt kümelerini deneyip her birinde kilitli derse
    gelince ölüyor."""
    gunler = [(g, b) for g in (1, 2, 3, 4, 5) for b in (510, 630, 810, 930)]
    cs = [_aday(f"H{i:02d}", [_sube(f"9{i:02d}", f"H{i:02d}", (g, b, b + 100))],
                puan=100 - i, credits=1.0)
          for i, (g, b) in enumerate(gunler[:18])]
    g0, b0 = gunler[0]
    cs.append(_aday("KIL 101", [_sube("777", "KIL 101", (g0, b0, b0 + 100))], puan=1))
    return cs


def test_KILITLI_ders_ONCE_yerlesiyor(monkeypatch):
    """★★ FAZ 45'İN HATASI. Kilitli ders adayların sonundaydı; motor bütçeyi
    (`SEARCH_BUDGET`) ölü dallarda bitiriyordu ve GEÇERLİ program varken
    "öneri üretilemedi" çıkıyordu. Gerçek veride 139 tek şube kilidinin 22'si.
    Bütçe testte küçültüldü (hız için); mantık aynı."""
    monkeypatch.setattr(REC, "SEARCH_BUDGET", 20_000)
    sonuc = REC.build_schedules(_budama_havuzu(), max_load=35, limit=3,
                                locked={"KIL 101": "777"})
    assert sonuc, "geçerli program varken hiç öneri çıkmadı (kilitli ders sonda kaldı)"
    assert all("KIL 101" in s.courses() and "H00" not in s.courses() for s in sonuc)


def _pay_havuzu():
    """Havuz AÇLIĞI modeli. Kilitli L'nin iki sabah şubesi var: s1 (Pzt,
    daha BOŞ → önce deneniyor) ve s2 (Sal). Y ile Z'nin ikisi birden ancak
    s2 ile sığıyor: s1 seçilirse Y ve Z'nin kalan şubeleri birbiriyle
    çakışıyor. `blocking_cost` bunu göremiyor (ikisinin de başka şubesi
    var). Yedi küçük ders (2^7 = 128 alt küme) s1'in alt ağacında havuzu
    (limit=1 → 60) tek başına dolduruyor."""
    L = _aday("LLL 100", [
        REC.Section(crn="1", course="LLL 100", instructor=None, capacity=90, enrolled=0,
                    meetings=(REC.Meeting(1, 540, 660, None, None, None),)),
        REC.Section(crn="2", course="LLL 100", instructor=None, capacity=40, enrolled=0,
                    meetings=(REC.Meeting(2, 540, 660, None, None, None),))], puan=1)
    Y = _aday("YYY 200", [_sube("y1", "YYY 200", (1, 540, 660)),
                          _sube("y2", "YYY 200", (3, 540, 660))], puan=90)
    Z = _aday("ZZZ 300", [_sube("z1", "ZZZ 300", (1, 540, 660)),
                          _sube("z2", "ZZZ 300", (3, 540, 660))], puan=80)
    F = [_aday(f"F{i} 10", [_sube(f"f{i}", f"F{i} 10", (4 + i // 4, 480 + 120 * (i % 4),
                                                      580 + 120 * (i % 4)))],
               puan=10 - i, credits=1.0) for i in range(7)]
    return [L, Y, Z, *F]


def test_ADIL_PAY_havuzu_tek_subeye_BIRAKMIYOR():
    """★★ Ölçülen hatanın küçük modeli: pay olmadan ilk şubenin alt ağacı
    havuzu dolduruyor, ikinci şube hiç denenmiyor ve en iyi program
    (Y + Z birlikte) bulunamıyor."""
    en = REC.build_schedules(_pay_havuzu(), max_load=35, limit=1,
                             locked={"LLL 100": REC.aralik_yazi(*SABAH)})[0]
    p = {x.candidate.course: x.section.crn for x in en.picks}
    assert {"YYY 200", "ZZZ 300"} <= set(p), f"Y ve Z birlikte değil: {sorted(p)}"
    assert p["LLL 100"] == "2"


def test_ADIL_PAY_kodu_yerinde():
    """Havuz tek şubenin alt ağacıyla dolmasın: ölçüldü, 26 durumun 5'inde
    aralık kilidi aralıktaki TEK bir şube kilidinden kötü program veriyordu."""
    govde = re.search(r"def build_schedules\(.*?\n    return results\[:limit\]",
                      REC_KAYNAK, re.S).group(0)
    kod = _kod(govde)
    assert "paylas = index in _aralik_idx" in kod
    assert "list(uyanlar) if paylas" in kod, "aralık kilidinde bütün şubeler denenmiyor"
    assert re.search(r"ust\.append\(min\(ust\[-1\], len\(results\)\s*\+ max\(1, "
                     r"\(ust\[-1\] - len\(results\)\) // kalan\)\)\)", kod)
    assert "if len(results) >= ust[-1] or budget[0] <= taban[-1]:" in kod


# ===================================================== 3. ayar ↔ arayüz
def test_SATIRLAR_OLDUGU_GIBI_cozuluyor():
    s = UI._kilit_satirlari(["geo 315e@13601", "BLG 351E@8:30-12:30",
                             "BLG 351E@00:00-12:30", "ATA 121@8.30-12.30", "@123"])
    tur = [(x["course"], x["deger"], x["tur"]) for x in s]
    assert tur == [("GEO 315E", "13601", "sube"),
                   ("BLG 351E", "08:30-12:30", "golge"),     # sonraki geçerli
                   ("BLG 351E", "00:00-12:30", "aralik"),
                   ("ATA 121", "8.30-12.30", "bozuk"),
                   ("", "123", "bozuk")]
    # Motorun gördüğü: yalnız uygulananlar, aynı derste SONUNCUSU.
    assert UI._kilit_ayikla([x["satir"] for x in s]) == {
        "GEO 315E": "13601", "BLG 351E": "00:00-12:30"}


def test_BOZUK_ve_GOLGE_satir_GORUNUYOR():
    """⚠️⚠️ Faz 45'in docstring'i "bozuk satırı arayüz söylüyor" diyordu ama
    `_kilit_bilgisi` yalnız ayıklanmış sözlüğü okuyordu: bozuk satır HİÇBİR
    YERDE görünmüyordu."""
    havuz = {"AAA 101": {"300": [{"day": 1, "start": 540, "end": 660}],
                         "302": [{"day": 3, "start": 870, "end": 990}]}}
    b = UI._kilit_bilgisi(["AAA 101@300", "AAA 101@12:30-24:00", "ZZZ@8.30"], havuz)
    durum = {(x["course"], x["tur"]): (x["ok"], x["neden"]) for x in b}
    assert durum[("AAA 101", "golge")] == (False, "golge")
    assert durum[("AAA 101", "aralik")] == (True, "")
    assert durum[("ZZZ", "bozuk")] == (False, "bicim")
    ar = next(x for x in b if x["tur"] == "aralik")
    assert ar["uyan"] == ["302"] and (ar["lo"], ar["hi"]) == OGLEDEN
    # Aralığa uyan şube yok → ayrı cümle; ders yok → ayrı cümle.
    b2 = UI._kilit_bilgisi(["AAA 101@00:00-08:00", "YOK 100@00:00-12:30"], havuz)
    assert {x["course"]: x["neden"] for x in b2} == {"AAA 101": "aralik", "YOK 100": "ders"}


def test_serit_OKUNMAYANI_ve_ARALIGI_soyluyor():
    g = _fn("renderKilitNot")
    assert 'const okunmayan = list.filter(l => l.tur === "bozuk" || l.tur === "golge");' in g
    assert "<b>uygulanmamaktadır</b>" in g
    assert 'l.neden === "aralik"' in g, "aralığa uyan şube yoksa neden söylenmiyor"
    assert "kilitEtiketi(l)" in g, "rozet hâlâ yalnız CRN yazıyor"
    # "hepsini aç" her satırı KENDİSİYLE siliyor (ders kodu olmayan satır da).
    assert 'api("/api/kilit", {satir: l.satir})' in g


def test_bagli_sayilan_YALNIZ_uygulanan():
    assert "return Object.values(kilitler()).filter(l => havuz.has(l.course));" in \
        _fn("kilitliBuKipte")
    assert 'if(l.tur === "sube" || l.tur === "aralik") m[l.course] = l;' in _fn("kilitler")


def test_pencere_ARALIK_dugmeleri():
    g = _fn("kilitAralikSatiri")
    assert "if(!DATA.live) return \"\";" in g, "sunucusuz dosyada sahte düğme"
    assert 'aria-pressed="${on}"' in g
    assert "araligaUyar(s, k.lo, k.hi)" in g, "şube sayısı aralıktan hesaplanmıyor"
    # Şubesi yoksa düğme KAPALI ve nedeni yazılı — basınca boş sonuç değil.
    assert '${n || on ? "" : `disabled' in g
    assert "${kilitAralikSatiri(cand)}" in _fn("courseDialog")
    # Basılı olan RENK DEĞİL, kalın çerçeve (zorlanmış renk kipi, Faz 51).
    kural = re.search(r'\.kilitaralik\[aria-pressed="true"\]\{([^}]*)\}', KAYNAK).group(1)
    assert "border:2px solid" in kural


def test_sube_dugmesi_ARALIK_kilidini_ACMIYOR():
    """⚠️ Ders öğleden sonraya kilitliyken "Kilidi aç" yazan şube düğmesi,
    basan kişiye hangi kilidi açtığını söylemezdi."""
    g = _fn("kilitButonu")
    assert 'const on = !!l && l.tur !== "aralik" && l.crn === crn;' in g


# --------------------------------------------------------------- sunucu
def _durum(tmp_path, monkeypatch, ek=""):
    from itucap import db, server
    monkeypatch.setattr(C, "ROOT", tmp_path)
    (tmp_path / "config").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "config" / "settings.toml").write_text(
        '[student]\nanadal_program = "GEO"\n' + ek, encoding="utf-8")
    monkeypatch.setattr(C, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(C, "REF_DB", tmp_path / "data" / "reference.sqlite3")
    monkeypatch.setattr(C, "USER_DB", tmp_path / "data" / "user.sqlite3")
    db.connect(C.REF_DB, "schema.sql").close()
    db.connect(C.USER_DB, "schema_user.sql").close()
    return server.State.__new__(server.State)


def _ayar(tmp_path):
    return C.Settings.load(tmp_path / "config" / "settings.toml").kilitli


def test_uc_ARALIK_yaziyor_aciyor_DEGISTIRIYOR(tmp_path, monkeypatch):
    st = _durum(tmp_path, monkeypatch)
    r = st.toggle_lock("geo 315e", aralik="8:30-12:30")
    assert r["on"] and _ayar(tmp_path) == ["GEO 315E@08:30-12:30"], "biçim normalleşmedi"
    # Şube kilidi aralığın YERİNE geçiyor (bir derste tek kilit) ve söyleniyor.
    r = st.toggle_lock("GEO 315E", "13601")
    assert _ayar(tmp_path) == ["GEO 315E@13601"] and r["replaced"] == "08:30-12:30"
    r = st.toggle_lock("GEO 315E", aralik="12:30-24:00")
    assert _ayar(tmp_path) == ["GEO 315E@12:30-24:00"] and r["replaced"] == "13601"
    # Aynı aralık yeniden → AÇ.
    r = st.toggle_lock("GEO 315E", aralik="12:30-24:00")
    assert not r["on"] and _ayar(tmp_path) == []


def test_uc_OKUNAMAYAN_araligi_YAZMIYOR(tmp_path, monkeypatch):
    st = _durum(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="okunamadı"):
        st.toggle_lock("GEO 315E", aralik="8.30-12.30")
    assert _ayar(tmp_path) == []


def test_uc_SATIRI_kendisiyle_siliyor_ve_SIRAYI_koruyor(tmp_path, monkeypatch):
    st = _durum(tmp_path, monkeypatch,
                'kilitli = ["ZZZ 1@9", "@123", "AAA 1@2", "AAA 1@3"]\n')
    st.toggle_lock("", satir="@123")
    assert _ayar(tmp_path) == ["ZZZ 1@9", "AAA 1@2", "AAA 1@3"], "sıra bozuldu"
    st.toggle_lock("", satir="@123")                     # yok → hata değil
    # Dersin kilidini açmak GÖLGEDEKİ satırı da götürüyor — yoksa silinen
    # satırın yerine eskisi sessizce geçerli olurdu.
    r = st.toggle_lock("AAA 1")
    assert _ayar(tmp_path) == ["ZZZ 1@9"] and r["crn"] == "3"


# ===================================================== 4. yanlış tablodaki ayar
def test_YANLIS_TABLODAKI_ayar_SOYLENIYOR(tmp_path):
    """★★ Kullanıcının kendi dosyasında ölçüldü: `cap_baslangic_yariyili` ve
    `mesgul` `[regulation]` tablosunun altındaydı. Yorum "3 ya da 5 yaz"
    diyor; yazılsa yarıyıl tabanı UYGULANMIYOR ve araç söylemiyordu."""
    p = tmp_path / "settings.toml"
    p.write_text('[student]\nanadal_program = "GEO"\nmesgul = []\n'
                 '[regulation]\nmin_gno_apply = 3.0\ncap_baslangic_yariyili = 5\n'
                 'mesgul = ["PZT 12:30-14:30 iş"]\n', encoding="utf-8")
    s = C.Settings.load(p)
    assert s.cap_baslangic_yariyili == 0, "yanlış tablodan okundu (hangisi geçerli?)"
    assert {(u["anahtar"], u["tablo"], u["golge"]) for u in s.load_uyarilari} == {
        ("cap_baslangic_yariyili", "regulation", False),
        ("mesgul", "regulation", True)}
    # [regulation]'ın KENDİ anahtarları uyarı değil.
    assert all(u["anahtar"] != "min_gno_apply" for u in s.load_uyarilari)


def test_BASLIKTAN_ONCE_yazilan_ayar_da(tmp_path):
    p = tmp_path / "settings.toml"
    p.write_text('donem = 5\n[student]\nanadal_program = "GEO"\n', encoding="utf-8")
    s = C.Settings.load(p)
    assert s.donem == 0
    assert s.load_uyarilari == [{"anahtar": "donem", "tablo": "", "golge": False}]


def test_TEMIZ_dosyada_uyari_YOK():
    ornek = pathlib.Path(UI.__file__).resolve().parents[2] / "config" / "settings.example.toml"
    assert C.Settings.load(ornek).load_uyarilari == [], "örnek dosya kendi uyarısını veriyor"


def test_arayuz_UYARIYI_basiyor():
    g = _fn("renderAyarHatasi")
    assert "DATA.settingsWarnings" in g
    assert "okumamaktadır" in g and "etkisiz bir kopyadır" in g
    assert '"settingsWarnings": settings.load_uyarilari' in KAYNAK


# --------------------------------------------------------- uçtan uca
_CANLI = r'''
import sys, tempfile, threading, time, os
from pathlib import Path
sys.path.insert(0, os.environ["ITUCAP_SRC"])
_T = Path(tempfile.mkdtemp()); (_T/"config").mkdir(); (_T/"data").mkdir()
AYAR = _T/"config"/"settings.toml"
AYAR.write_text('[student]\nanadal_program="HTAE"\nsecond_kind="yok"\n'
                '[regulation]\ncap_baslangic_yariyili = 5\n', encoding="utf-8")
import itucap.config as config
config.ROOT = _T; config.DATA_DIR = _T/"data"
config.REF_DB = _T/"data"/"reference.sqlite3"; config.USER_DB = _T/"data"/"user.sqlite3"
from itucap import db
con = db.connect(config.REF_DB, "schema.sql")
con.execute("INSERT INTO program(code,name,level) VALUES ('HTAE','H','LS')")
con.execute("INSERT INTO plan(id,program_code,plan_type,title,source)"
            " VALUES (1,'HTAE','lisans','x','obs')")
# AAA: Pzt sabah (300) · Sal öğleden sonra (301) · Çar öğleden sonra (302)
# BBB: yalnız Sal öğleden sonra — AAA 301 ile ÇAKIŞIYOR.
plan = [("AAA 101E", [("300", 1, 540, 660), ("301", 2, 810, 930), ("302", 3, 870, 990)]),
        ("BBB 102E", [("400", 2, 810, 930)])]
for i, (kod, subeler) in enumerate(plan):
    con.execute("INSERT INTO course(code,name,credits,ects) VALUES (?,?,3,4)",
                (kod, "Ders " + kod))
    con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,position,term_no)"
                " VALUES (1,'REQUIRED',?,?,1)", (kod, i))
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
def aaa_crn(pg):
    return pg.evaluate("""() => (MODES[0].schedules||[]).map(s => {
        const x = s.picks.find(p => p.course === "AAA 101E");
        return x ? x.section.crn : "-"; }).join(",")""")
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width":1400,"height":1000})
    pg.goto(f"http://127.0.0.1:{P}/", wait_until="networkidle", timeout=30000)
    pg.wait_for_timeout(1500)
    print("AYARUYARI:" + pg.eval_on_selector("#ayarHatasi",
          "e => e.hidden ? 'gizli' : e.textContent.replace(/\\s+/g,' ')"))
    # Pencereyi aç, "Öğleden sonra olsun"a bas — ARAYÜZÜN KENDİ düğmesi.
    pg.evaluate("() => resetTo(0)"); pg.wait_for_timeout(400)
    pg.click('#grid .blk[data-course="AAA 101E"]'); pg.wait_for_timeout(500)
    print("DUGMELER:" + pg.evaluate("""() => [...document.querySelectorAll(
        '#detail .kilitaralik')].map(b => b.textContent.replace(/\\s+/g,' ').trim()
        + (b.disabled ? '[kapalı]' : '')).join('|')"""))
    pg.click('#detail .kilitaralik[data-aralik="12:30-24:00"]')
    pg.wait_for_function("() => (DATA.locked||[]).length === 1", timeout=60000)
    pg.wait_for_timeout(600)
    print("KILIT:" + pg.evaluate("() => JSON.stringify(DATA.locked.map(l => [l.tur, l.aralik, l.ok, l.uyan]))"))
    print("ONERI_CRN:" + aaa_crn(pg))
    print("ONERI1_DERS:" + pg.evaluate("() => MODES[0].schedules[0].picks.map(p => p.course).sort().join(',')"))
    print("SERIT:" + pg.eval_on_selector("#kilitNot", "e => e.hidden ? 'gizli' : e.textContent.replace(/\\s+/g,' ')"))
    pg.evaluate("() => resetTo(0)"); pg.wait_for_timeout(400)
    print("ROZET:" + str(pg.eval_on_selector_all("#grid .blk.kilit", "e => e.length")))
    print("BASLIK:" + pg.eval_on_selector('#grid .blk.kilit', "e => e.title"))
    pg.click('#grid .blk[data-course="AAA 101E"]'); pg.wait_for_timeout(500)
    print("BASILI:" + pg.evaluate("""() => [...document.querySelectorAll(
        '#detail .kilitaralik[aria-pressed="true"]')].map(b => b.textContent.replace(/\\s+/g,' ').trim()).join('|')"""))
    print("SUBEDUGME:" + pg.eval_on_selector("#kilitBtn", "e => e.textContent.trim()"))
    # Aynı düğme → kilit AÇILIYOR.
    pg.click('#detail .kilitaralik[aria-pressed="true"]')
    pg.wait_for_function("() => (DATA.locked||[]).length === 0", timeout=60000)
    pg.wait_for_timeout(400)
    print("ACILDI:" + pg.eval_on_selector("#kilitNot", "e => e.hidden ? 'gizli' : 'acik'"))
    # Elle yazılmış OKUNAMAYAN satır: öneriler boşalmıyor, şerit söylüyor, ✕ siliyor.
    once = aaa_crn(pg)
    import re as _re
    metin = AYAR.read_text(encoding="utf-8")
    # Kilit düğmeleri `kilitli = []` satırını zaten yazdı; ikinci bir satır
    # TOML'da çift anahtar olurdu. Var olanı değiştir.
    assert _re.search(r"(?m)^kilitli = ", metin), metin
    AYAR.write_text(_re.sub(r"(?m)^kilitli = .*$",
                            'kilitli = ["AAA 101E@8.30-12.30"]', metin), encoding="utf-8")
    pg.reload(wait_until="networkidle"); pg.wait_for_timeout(1500)
    print("BOZUK_ONERI:" + str(aaa_crn(pg) == once and aaa_crn(pg) != ""))
    print("BOZUK_SERIT:" + pg.eval_on_selector("#kilitNot", "e => e.hidden ? 'gizli' : e.textContent.replace(/\\s+/g,' ')"))
    pg.click('#kilitNot [data-satir]')
    pg.wait_for_function("() => (DATA.locked||[]).length === 0", timeout=60000)
    print("BOZUK_SILINDI:" + str('8.30' not in AYAR.read_text(encoding="utf-8")))
    # Telefon: pencere düğmeleri dokunulabilir mi
    pg.set_viewport_size({"width": 390, "height": 844}); pg.wait_for_timeout(400)
    pg.evaluate("() => resetTo(0)"); pg.wait_for_timeout(300)
    pg.evaluate("() => courseDialog('AAA 101E')"); pg.wait_for_timeout(400)
    print("TELEFON:" + str(pg.evaluate("""() => Math.min(...[...document.querySelectorAll(
        '#detail .kilitaralik')].map(b => Math.round(b.getBoundingClientRect().height)))""")))
    b.close()
h.shutdown()
'''


def test_UCTAN_UCA_aralik_kilidi(tmp_path, monkeypatch):
    """★★ Tarayıcıda: pencereden "Öğleden sonra olsun" → bütün öneriler
    aralıkta, motor çakışmayan ŞUBEYİ (302) seçip BBB'yi tutuyor, ızgarada
    işaret + adı, düğme basılı, aynı düğme açıyor; okunamayan satır
    önerileri boşaltmıyor, şeritte görünüyor, tek tıkla siliniyor; yanlış
    tablodaki ayar tepede söyleniyor; telefonda düğmeler ≥44px."""
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
                       text=True, timeout=300)
    if r.returncode != 0:
        pytest.fail(r.stderr[-2000:])
    c = dict(s.split(":", 1) for s in r.stdout.strip().splitlines()
             if ":" in s and s.split(":", 1)[0].isupper())
    assert "cap_baslangic_yariyili" in c["AYARUYARI"] and "okumamaktadır" in c["AYARUYARI"], c
    assert "Sabah olsun · 1 şube" in c["DUGMELER"], c["DUGMELER"]
    assert "Öğleden sonra olsun · 2 şube" in c["DUGMELER"], c["DUGMELER"]
    assert c["KILIT"] == '[["aralik","12:30-24:00",true,["301","302"]]]', c["KILIT"]
    assert set(c["ONERI_CRN"].split(",")) <= {"301", "302"}, \
        f"aralık dışı şube önerildi: {c['ONERI_CRN']}"
    assert c["ONERI1_DERS"] == "AAA 101E,BBB 102E", \
        f"motor çakışmayan şubeyi seçmedi, BBB düştü: {c['ONERI1_DERS']}"
    assert "AAA 101E · öğleden sonra" in c["SERIT"], c["SERIT"]
    assert int(c["ROZET"]) == 1, c
    assert "öğleden sonraya kilitli" in c["BASLIK"], c["BASLIK"]
    assert c["BASILI"].startswith("Öğleden sonra kilidini aç"), c["BASILI"]
    assert c["SUBEDUGME"] == "Bu saate kilitle", "şube düğmesi aralık kilidini açıyor gibi"
    assert c["ACILDI"] == "gizli", c
    assert c["BOZUK_ONERI"] == "True", "okunamayan kilit önerileri değiştirdi"
    assert "uygulanmamaktadır" in c["BOZUK_SERIT"] and "AAA 101E@8.30-12.30" in c["BOZUK_SERIT"], \
        c["BOZUK_SERIT"]
    assert c["BOZUK_SILINDI"] == "True"
    assert int(c["TELEFON"]) >= 44, f"telefonda kilit düğmesi küçük: {c['TELEFON']}px"


# ===================================================== 5. durum değişince kip ve ızgara
def test_applyState_ILK_ACILIS_islerini_tekrarlamiyor():
    """★★ `boot()` ilk açılış için yazılmıştı ve her durum değişikliğinde
    baştan koşuyordu: kip 0'a dönüyor, kaydedilen program ve paylaşılan
    bağlantı YENİDEN uygulanıyordu. Kilit çalışıyordu ama ekran eski
    programı gösteriyordu."""
    g = _fn("boot")
    assert re.search(r"if\(!onceki\)\{\s*useMode\(0\);", g), "ilk açılış ayrılmamış"
    assert "useMode(i >= 0 ? i : 0, {kayitli: false});" in g
    assert "if(!onceki) baglantidanYukle();" in g, "bağlantı her değişiklikte yeniden yükleniyor"
    assert 'const onceki = {kip: (MODES[mode] || {}).key' in _fn("applyState")
    assert "if(i === 0 && !(secenek && secenek.kayitli === false)) startFromSaved();" in \
        _fn("useMode")
    # Öneriyi DEĞİŞTİRMEYEN işler ızgarayı koruyor.
    assert 'applyState(await api("/api/picks", {picks: sel}), {koru: true});' in KAYNAK
    # Her izleme çağrısından sonraki İLK applyState `koru` ile olmalı.
    konumlar = [m.end() for m in re.finditer(r'api\("/api/watch"', KAYNAK)]
    assert len(konumlar) >= 2
    for k in konumlar:
        sonraki = re.search(r"applyState\([^\n]*", KAYNAK[k - 60:k + 200]).group(0)
        assert "{koru: true}" in sonraki, f"izleme ızgarayı sıfırlıyor: {sonraki}"


_KIP = r'''
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
    print("KIPLER:" + pg.evaluate("() => MODES.map(m => m.key).join(',')"))
    # 1. kipte (dönemlik) AAA'yı elle SABAH şubesine al ve programı KAYDET.
    pg.evaluate("() => { resetTo(0); choose('AAA 101E', '300'); }"); pg.wait_for_timeout(300)
    once = pg.evaluate(SEL)
    pg.click("#savePicks")
    pg.wait_for_function("() => (DATA.savedPicks && DATA.savedPicks.picks || []).length > 0",
                         timeout=60000)
    pg.wait_for_timeout(500)
    print("KAYIT_SONRA_AYNI:" + str(pg.evaluate(SEL) == once))
    # DEPAR kipine geç, AAA'yı öğleden sonraya kilitle.
    pg.evaluate("() => useMode(MODES.findIndex(m => m.key === 'all'))"); pg.wait_for_timeout(300)
    pg.evaluate("() => courseDialog('AAA 101E')"); pg.wait_for_timeout(400)
    pg.click('#detail .kilitaralik[data-aralik="12:30-24:00"]')
    pg.wait_for_function("() => (DATA.locked||[]).length === 1", timeout=60000)
    pg.wait_for_timeout(500)
    print("KILIT_SONRA_KIP:" + pg.evaluate("() => M().key"))
    print("KILIT_SONRA_SEL:" + pg.evaluate(SEL))
    print("SERIT:" + pg.eval_on_selector("#kilitNot", "e => e.textContent.replace(/\\s+/g,' ')"))
    # İzleme (öneriyi değiştirmiyor): elle yapılan seçim KALMALI.
    pg.evaluate("() => choose('CCC 301E', '501')"); pg.wait_for_timeout(300)
    elle = pg.evaluate(SEL)
    pg.evaluate("() => courseDialog('BBB 102E')"); pg.wait_for_timeout(400)
    pg.click("#watchBtn")
    pg.wait_for_function("() => ((SETUP && SETUP.watchCourses) || []).length === 1", timeout=60000)
    pg.wait_for_timeout(500)
    print("IZLEME_SONRA_KIP:" + pg.evaluate("() => M().key"))
    print("IZLEME_SONRA_AYNI:" + str(pg.evaluate(SEL) == elle))
    b.close()
h.shutdown()
'''


def test_UCTAN_UCA_kip_ve_izgara_KORUNUYOR(tmp_path, monkeypatch):
    """★★ Gerçek veride görüldü: DEPAR kipinde kilitleyen kullanıcı
    dönemlik kipe atılıyor ve ızgarada KAYDETTİĞİ eski program duruyordu.
    Artık kilitten sonra kip aynı, ızgarada kilitli öneri var; izleme gibi
    öneriyi değiştirmeyen bir iş elle yapılan seçimi silmiyor."""
    if not shutil.which("node"):
        pytest.skip("node yok")
    try:
        import playwright  # noqa: F401
    except ImportError:
        pytest.skip("playwright yok")
    monkeypatch.setenv("ITUCAP_SRC", str(Path(UI.__file__).resolve().parents[1]))
    betik = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                        dir=str(tmp_path))
    betik.write(_KIP); betik.close()
    r = subprocess.run([sys.executable, betik.name], capture_output=True,
                       text=True, timeout=300)
    if r.returncode != 0:
        pytest.fail(r.stderr[-2000:])
    c = dict(s.split(":", 1) for s in r.stdout.strip().splitlines()
             if ":" in s and s.split(":", 1)[0].isupper())
    assert c["KIPLER"] == "term,all", c
    assert c["KAYIT_SONRA_AYNI"] == "True", "kaydetmek ızgarayı değiştirdi"
    assert c["KILIT_SONRA_KIP"] == "all", f"kilitten sonra kip değişti: {c}"
    sec = dict(x.split("@") for x in c["KILIT_SONRA_SEL"].split(","))
    assert sec.get("AAA 101E") in {"301", "302"}, \
        f"ızgarada kilitli öneri değil kaydedilen program var: {c['KILIT_SONRA_SEL']}"
    assert "bu kipte bağlamıyor" not in c["SERIT"], c["SERIT"]
    assert c["IZLEME_SONRA_KIP"] == "all", c
    assert c["IZLEME_SONRA_AYNI"] == "True", "izleme düğmesi elle yapılan seçimi sildi"
