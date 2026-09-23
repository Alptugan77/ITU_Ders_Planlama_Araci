"""Faz 28 — sekme etiketi gerçekten AYIRT EDİYOR mu + plansız ikinci program.

★ Bu dosyadaki `oneriFarki` testleri metin araması değil: işlev node'da
GERÇEKTEN çalıştırılıyor. Faz 27'de etiket eklenmişti ama tarayıcıda
ölçtüğümüzde üç sekmeden ikisi BOŞ etiket alıyordu — dört ölçütün hiçbiri
onları ayırmıyordu. Metin araması bunu yakalayamazdı.
"""
import json
import re
import shutil
import subprocess

import pytest

from itucap import ui as UI


# --------------------------------------------------------------------- yardım
def _oneriFarki_kaynagi() -> str:
    """`oneriFarki` + bağımlılıkları — node'da çalıştırılabilir hâlde."""
    src = (UI.__file__).replace(".pyc", ".py")
    metin = open(src, encoding="utf-8").read()
    govde = re.search(r"function oneriFarki\(s, i\)\{.*?\n\}", metin, re.S)
    assert govde, "oneriFarki bulunamadı"
    return (
        'const hhmm = (m) => String(Math.floor(m/60)).padStart(2,"0")+":"'
        '+String(m%60).padStart(2,"0");\n'
        'const GUNAD = ["Pzt","Sal","Çar","Per","Cum"];\n'
        "let ONERILER = [];\n"
        "const M = () => ({schedules: ONERILER});\n"
        + govde.group(0) + "\n"
    )


def _etiketler(oneriler: list[dict]) -> list[str]:
    node = shutil.which("node")
    if not node:
        pytest.skip("node yok")
    betik = (_oneriFarki_kaynagi()
             + f"ONERILER = {json.dumps(oneriler)};\n"
             + "console.log(JSON.stringify(ONERILER.map((s,i) => "
               "oneriFarki(s,i).replace(/<[^>]+>/g,'').replace(/^\\s*·\\s*/,'')"
               ".trim())));")
    r = subprocess.run([node, "-e", betik], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[:800]
    return json.loads(r.stdout)


def _oneri(**kw) -> dict:
    sekil = {"freeDays": [], "earliest": 510, "latest": 1000,
             "online": 0, "gaps": 100, "days": [1, 2, 3, 4, 5], "timeless": 0}
    sekil.update({k: v for k, v in kw.items() if k != "campusChanges"})
    return {"credits": 20, "campusChanges": kw.get("campusChanges", 0),
            "shape": sekil}


# ======================================== 1. etiket UYDURMUYOR
def test_tek_oneri_varsa_etiket_YOK():
    """Ayırt edecek bir şey yoksa etiket de yok."""
    assert _etiketler([_oneri()]) == [""]


def test_TAMAMEN_AYNI_uc_oneride_etiket_YOK():
    """★ Uydurma etiket ("dengeli", "yoğun") olmayan bir fark anlatırdı."""
    assert _etiketler([_oneri(), _oneri(), _oneri()]) == ["", "", ""]


# ======================================== 2. ölçütler sırayla
def test_yalniz_bu_onerinin_bos_biraktigi_gun():
    e = _etiketler([_oneri(freeDays=[3]), _oneri(), _oneri()])
    assert e[0] == "Çar boş" and e[1] == "" and e[2] == ""


def test_en_gec_baslayan():
    e = _etiketler([_oneri(earliest=510), _oneri(earliest=630)])
    assert e[1] == "10:30 başlıyor"


def test_tek_kampus():
    e = _etiketler([_oneri(campusChanges=2), _oneri(campusChanges=0)])
    assert e[1] == "tek kampüs"


def test_en_cok_cevrimici():
    e = _etiketler([_oneri(online=1), _oneri(online=4)])
    assert e[1] == "4 çevrimiçi"


# ======================================== 3. ★★ Faz 28'de eklenen iki ölçüt
def test_EN_AZ_BEKLEME_ayirt_edici(tmp_path):
    """★★ TARAYICIDA ÖLÇÜLDÜ: üç öneri 218 / 668 / 339 dakika boşlukla
    çıkıyordu ve etiketlerin ikisi BOŞTU. `gaps` zaten hesaplanıyordu;
    öğrenci için en somut fark buyken hiçbir yerde ayırt edici sayılmıyordu."""
    e = _etiketler([_oneri(gaps=218), _oneri(gaps=668), _oneri(gaps=339)])
    assert e[0] == "en az bekleme"
    assert e[1] == "" and e[2] == ""


def test_bekleme_farki_KUCUKSE_etiket_YOK():
    """⚠️ 10 dakikalık farkı "en az bekleme" diye satmak, olmayan bir
    üstünlük iddia etmek olurdu. Eşik 30 dakika."""
    assert _etiketler([_oneri(gaps=100), _oneri(gaps=110)]) == ["", ""]


def test_EN_ERKEN_BITEN():
    e = _etiketler([_oneri(latest=1080), _oneri(latest=960)])
    assert e[1] == "16:00'de bitiyor"


def test_bitis_farki_kucukse_etiket_yok():
    assert _etiketler([_oneri(latest=1000), _oneri(latest=1010)]) == ["", ""]


def test_shape_YOKSA_cokmuyor():
    """Eski bir durum nesnesi gelirse etiket boş kalmalı, sayfa kırılmamalı."""
    assert _etiketler([{"credits": 20, "campusChanges": 0}, _oneri()])[0] == ""


# ======================================== 4. plansız ikinci program arayüzde
def test_kurulum_cubugu_PLANSIZ_programi_da_yaziyor():
    """★ `secondsMissing` ekranda görünmezse kullanıcı seçimi kaydolmamış
    sanıyor — yandal kodu bozulunca tam olarak bu oldu."""
    src = open(UI.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
    assert "SECONDS_YOK" in src
    assert "secondsMissing" in src
    assert "planı yok" in src


def test_uzun_kayitta_gecen_sure_yaziyor():
    """★ ÇAP+yandal kaydı 7 saniye sürüyor (ölçüldü); tek satır
    "kaydediliyor…" kullanıcıya takıldı sandırıyordu."""
    src = open(UI.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
    assert "plan yeniden hesaplanıyor" in src
    assert "clearInterval(sayac)" in src


# ======================================== 5. B3 — dönem kodu okunur
def test_donem_kodu_okunur_ada_cevriliyor():
    """★★ Faz 38: BİR YIL KAYDIRILDI.

    Eskiden `202610 → "2026-2027 Güz"` bekleniyordu. OBS'nin kendi not
    dağılımı ucu `202610 | 2025-2026 | Fall Semester` diyor (üç ardışık
    yılda tutarlı), yani koddaki yıl akademik yılın BİTİŞ yılı.
    """
    from itucap import config
    assert config.donem_adi("202610") == "2025-2026 Güz"
    assert config.donem_adi("202520") == "2024-2025 Bahar"
    assert config.donem_adi("202430") == "2023-2024 Yaz"


def test_TANIMADIGI_kalibi_UYDURMUYOR():
    """⚠️ Yanlış bir dönem adı ham koddan çok daha kötü: öğrenci "bahar"
    sanıp yanlış döneme bakar. Çözemezse BOŞ dönüyor."""
    from itucap import config
    for kotu in ("", None, "2026", "20261", "abcdef", "202699", "2026101"):
        assert config.donem_adi(kotu) == "", kotu


def test_arayuz_cozulemeyen_kodda_HAM_KODU_yaziyor():
    src = open(UI.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
    assert "DATA.termLabel || DATA.term" in src
    assert "OBS dönem kodu: " in src, "ham kod ipucunda da yok"


# ======================================== 6. C3 — ham veri sızıntısı
def test_ilan_edilmemis_bina_BOS_donuyor():
    """★ "belirsiz" bir bina adı sanılıyordu. Ölçüldü: 3630 buluşmanın
    1542'si (%42) ilan edilmemiş — ızgaranın neredeyse yarısı."""
    assert UI._building("undeclared") == ""
    assert UI._building("-") == ""
    assert UI._building(None) == ""
    assert UI._building(" TMB ") == "TMB"


def test_bina_adi_sozlugu_kodu_ad_diye_vermiyor(tmp_path):
    import sqlite3
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE building(code TEXT, name TEXT, campus TEXT)")
    con.executemany("INSERT INTO building VALUES (?,?,?)",
                    [("TMB", "Temel Bilimler Binası", None),
                     ("XXX", "XXX", None),            # adı koduyla aynı
                     ("YYY", "", None)])              # adı yok
    assert UI._bina_adlari(con) == {"TMB": "Temel Bilimler Binası"}


def test_arayuz_yeri_olmayani_SOYLUYOR():
    src = open(UI.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
    assert "OBS'de yer bildirilmemiş" in src
    # Faz 56: "yer yok" kayıt gününde "kontenjan dolu" diye okunuyordu.
    # Yorumlar sökülüyor: değişikliği anlatan yorum eski sözü anıyor.
    import re
    kod = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    assert '"yer bildirilmedi"' in kod
    assert '"yer yok"' not in kod


def test_terminal_ve_arayuz_AYNI_sozu_kullaniyor():
    """★ Aynı şeye iki ad vermek (arayüzde "yer yok", terminalde "belirsiz")
    bu projenin klasik hatası. Tek söz.

    ⚠️ Faz 56: söz "yer yok"tan "yer bildirilmedi"ye döndü — iki tarafta
    BİRLİKTE. Kayıt aracında CRN'nin yanındaki "yer yok" KONTENJAN DOLU diye
    okunuyordu; kontenjanın kendi dili "dolu / N boş"."""
    from itucap import recommend as REC
    assert REC._building_label("undeclared") == "yer bildirilmedi"
    assert REC._building_label("-") == "yer bildirilmedi"
    assert REC._building_label(" TMB ") == "TMB"


# ======================================== 7. D3 + E — arayüz yerleşimi
def test_ne_degisti_bolumu_KARSILASTIRMA_yoksa_gizli():
    """★★ D3 — ölçüt `LIVE` idi: hiç tazeleme yapmamış kişiye "Ne değişti"
    başlığı ve altında "en az iki tazeleme gerekiyor" çıkıyordu."""
    src = open(UI.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
    assert "const karsilastirilabilir = " in src
    assert "$(\"#changeSection\").hidden = !(karsilastirilabilir" in src


def test_tazeleme_bolum_gizliyken_de_ERISILEBILIR():
    """⚠️ Tazeleme düğmesi YALNIZCA o bölümün içindeydi; bölümü gizlemek
    düğmeyi de yok ederdi. Veri yaşı satırına taşındı."""
    src = open(UI.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
    assert 'id="veriTazele"' in src
    assert "async function tazele(btn)" in src, "ilerleme tıklanan düğmede değil"


def test_tercih_kurulum_ADIMI_DEGIL_ince_ayar():
    """★★ Denendi ve geri alındı: dördüncü "kurulum adımı" yapılınca
    karşılama kartı hiç kaybolmuyordu (tercih çoğu kullanıcıda hep boş).
    Faz 26'nın kaldırdığı "duvar" hissi geri geliyordu."""
    src = open(UI.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
    assert '"key": "tercih"' not in src, "tercih yine kurulum adımı olmuş"
    assert "Nasıl bir program istediğini söyle" in src
    assert "const tercihGoster = !tercihSayisi();" in src


def test_katalogda_olmayan_ders_SEBEBI_yaziyor():
    """★ E — "BLG 105E · (adsız) · –": boş ad ve sıfıra benzeyen bir tire.
    Ölçüldü: plan slotlarının 67'si katalogda olmayan derse bakıyor."""
    src = open(UI.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
    assert "bu ders katalogda yok" in src
    assert "Kredisi katalogda yok" in src


# ======================================== 8. program kodları otomatik türetiliyor
# Kullanıcı isteği 27.08.2026: *"alabileceğim ders kodlarını anadal çap ve
# yandala göre otomatik ekler misin, orada sadece ekstra program türleri
# girilebilsin"*.
def test_kodlar_SECIMLERDEN_turetiliyor():
    from itucap import config
    s = config.Settings(anadal_program="HTAE", cap_program="BLG",
                        yandal_program="BHB_YD", second_kind="ikisi")
    assert s.derived_programs == ["HTAE", "BLG", "BHB_YD"]
    assert s.allowed_programs == {"HTAE", "BLG", "BHB_YD"}


def test_ekstra_kodlar_turetilenlere_EKLENIYOR():
    from itucap import config
    s = config.Settings(anadal_program="HTAE", cap_program="BLG",
                        second_kind="cap", program_codes=["blge"])
    assert s.allowed_programs == {"HTAE", "BLG", "BLGE"}


def test_bolum_DEGISINCE_eski_kod_KALMIYOR():
    """★★ Eski davranışta `program_codes` dosyaya yazılıyordu: anadalını
    değiştiren kişinin ders havuzu ESKİ koda göre süzülmeye devam ediyor ve
    bu ekranda hiçbir yerde yazmıyordu."""
    from itucap import config
    once = config.Settings(anadal_program="HTAE", second_kind="yok")
    sonra = config.Settings(anadal_program="MAK", second_kind="yok")
    assert once.allowed_programs == {"HTAE"}
    assert sonra.allowed_programs == {"MAK"}


def test_yinelenen_kod_bir_kez():
    from itucap import config
    s = config.Settings(anadal_program="BLG", cap_program="BLG",
                        second_kind="cap", program_codes=["BLG", "blg"])
    assert s.derived_programs == ["BLG"]
    assert s.allowed_programs == {"BLG"}


def test_kutuya_TURETILENLER_yazilmiyor(tmp_path, monkeypatch):
    """Kullanıcı türetilmiş kodu elle yazsa da dosyaya ekstra olarak
    kaydedilmiyor — yoksa bölüm değişince orada kalırdı."""
    import sqlite3

    from itucap import config, server as SRV
    monkeypatch.setattr(config, "ROOT", tmp_path)
    (tmp_path / "config").mkdir()
    st = SRV.State.__new__(SRV.State)
    st._reenroll = lambda: None
    st.con = sqlite3.connect(":memory:")
    st.con.execute("CREATE TABLE program(code TEXT PRIMARY KEY, name TEXT)")
    st.con.execute("CREATE TABLE plan(id INTEGER, program_code TEXT, plan_type TEXT)")
    st.con.executemany("INSERT INTO program VALUES (?,?)",
                       [("HTAE", "Hava"), ("BLG", "Bilgisayar"), ("BLGE", "Computer")])
    SRV.State.save_programs(st, {
        "anadalProgram": "HTAE", "secondKind": "cap", "secondProgram": "BLG",
        "programCodes": ["HTAE", "BLG", "BLGE"]})
    s = config.Settings.load(tmp_path / "config" / "settings.toml")
    assert s.program_codes == ["BLGE"], "türetilenler de yazılmış"
    assert s.allowed_programs == {"HTAE", "BLG", "BLGE"}


def test_son_ekstra_silinince_dosyadan_da_gidiyor(tmp_path, monkeypatch):
    """⚠️ Boş liste de yazılıyor: silineni dosyada bırakmak, kullanıcının
    sildiğini sanmasına yol açardı."""
    import sqlite3

    from itucap import config, server as SRV
    monkeypatch.setattr(config, "ROOT", tmp_path)
    (tmp_path / "config").mkdir()
    st = SRV.State.__new__(SRV.State)
    st._reenroll = lambda: None
    st.con = sqlite3.connect(":memory:")
    st.con.execute("CREATE TABLE program(code TEXT PRIMARY KEY, name TEXT)")
    st.con.execute("CREATE TABLE plan(id INTEGER, program_code TEXT, plan_type TEXT)")
    st.con.executemany("INSERT INTO program VALUES (?,?)",
                       [("HTAE", "Hava"), ("BLG", "Bilgisayar"), ("BLGE", "Computer")])
    gövde = {"anadalProgram": "HTAE", "secondKind": "cap", "secondProgram": "BLG"}
    SRV.State.save_programs(st, {**gövde, "programCodes": ["BLGE"]})
    assert config.Settings.load(
        tmp_path / "config" / "settings.toml").program_codes == ["BLGE"]
    SRV.State.save_programs(st, {**gövde, "programCodes": []})
    assert config.Settings.load(
        tmp_path / "config" / "settings.toml").program_codes == []


def _sahte_katalog(kodlar, subeler):
    import sqlite3
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE program(code TEXT PRIMARY KEY, name TEXT)")
    con.execute("CREATE TABLE plan(id INTEGER, program_code TEXT, plan_type TEXT)")
    con.execute("CREATE TABLE lesson_allowed_program(crn TEXT, program_code TEXT)")
    con.executemany("INSERT INTO program VALUES (?,?)", [(k, k) for k in kodlar])
    con.executemany("INSERT INTO lesson_allowed_program VALUES (?,?)", subeler)
    return con


def test_dil_esi_ONERILIYOR_dayatilmiyor():
    """⚠️ "Bu kodla da kayıt yapabilirsin" bir İDDİA; yanlışsa alamayacağın
    dersi alabilir gösterir. Öneri katalogda doğrulanıyor: eşin programı VE
    o koda açık en az bir şubesi olmalı."""
    from itucap import config, server as SRV
    st = SRV.State.__new__(SRV.State)
    st.con = _sahte_katalog(["HTAE", "BLG", "BLGE"], [("1", "BLGE"), ("2", "BLGE")])
    esler = SRV.State._dil_esleri(st)
    assert esler["BLG"] == {"code": "BLGE", "sections": 2}
    # ⚠️ Önerilen kod otomatik EKLENMİYOR.
    s = config.Settings(anadal_program="HTAE", cap_program="BLG", second_kind="cap")
    assert "BLGE" not in s.allowed_programs


def test_SUBESI_OLMAYAN_dil_esi_ONERILMIYOR():
    """İşe yaramayacak bir seçenek sunmak, sunmamaktan kötü."""
    from itucap import server as SRV
    st = SRV.State.__new__(SRV.State)
    st.con = _sahte_katalog(["HTAE", "BLG", "BLGE"], [])
    assert SRV.State._dil_esleri(st) == {}


def test_VAR_OLMAYAN_dil_esi_ONERILMIYOR():
    """★ Körlemesine son harfi atmak var olmayan bir programa yönlendirir:
    eş kodun katalogda GERÇEKTEN bulunması şart."""
    from itucap import server as SRV
    st = SRV.State.__new__(SRV.State)
    st.con = _sahte_katalog(["HTAE"], [("1", "HTA")])   # HTA programı YOK
    assert SRV.State._dil_esleri(st) == {}


def test_HTAE_HTA_GERCEK_bir_cift():
    """⚠️ `normalize.merge_language_variants` yorumu "HTAE'nin HTA diye bir
    eşi yok" diyordu. Katalogda ölçünce ikisinin de programı ve yüzlerce
    şubesi çıktı (HTA = Harita, HTAE = Harita İngilizce). Yorumdan değil
    VERİDEN karar veriyoruz."""
    from itucap import server as SRV
    st = SRV.State.__new__(SRV.State)
    st.con = _sahte_katalog(["HTA", "HTAE"], [("1", "HTA"), ("2", "HTAE")])
    esler = SRV.State._dil_esleri(st)
    assert esler["HTAE"]["code"] == "HTA"
    assert esler["HTA"]["code"] == "HTAE"


def test_oneri_KAYITLI_ayara_bagli_degil():
    """★ Kayıtlı ayara bağlasaydık öneri ancak KAYDETTİKTEN SONRA görünürdü
    — yani tam gerektiği anda değil. Tüm eşler gönderiliyor, arayüz o anki
    seçime göre süzüyor."""
    from itucap import server as SRV
    st = SRV.State.__new__(SRV.State)
    st.con = _sahte_katalog(["MAK", "MAKE", "BLG", "BLGE"],
                            [("1", "MAKE"), ("2", "BLGE")])
    esler = SRV.State._dil_esleri(st)
    assert set(esler) >= {"MAK", "BLG"}


def test_arayuz_turetilenleri_CANLI_ciziyor():
    src = open(UI.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
    assert "const turetilenKodlar = " in src
    assert 'id="fTuretilen"' in src
    # ⚠️ Faz 54: anadal değişince plan listeleri de yenileniyor (hangi plan
    # kimin için); dinleyici artık bir kapanış, `cizKodlar`ı yine çağırıyor.
    import re as _re
    m = _re.search(r'\$\("#fAnadal"\)\.addEventListener\("change", \(\) => \{(.*?)\}\);',
                   src, _re.S)
    assert m and "cizKodlar();" in m.group(1)
    assert "Ekstra program kodları" in src
