"""Faz 92 — başvuru taraması, program seçilince kullanılacak planı gösteriyor.

Kullanıcı 25.09.2026: *"continue"*. Gerçek katalogda ÇAP öğrencisi olarak
yürürken bulundu:

1. BLGE öğrencisine "BLG" (kendi bölümü) ÇAP seçeneği olarak çıkıyordu.
2. Tarama "sana açık mı" sorusunu planın KODUNDAN tahmin ediyordu; program
   seçilince kullanılan plan (`plans.ikinci_plan`) OBS'nin "İlişkili
   Programlar" listesine bakıyordu. 1073 çiftte ayrışıyorlardı: BLG
   öğrencisine EHB için TUMMUH_EHB gösteriliyordu (OBS listesinde BLG yok),
   seçilince BLG_EHB kullanılıyordu. BLGE öğrencisi "BLG" ev sahipli 27
   planın hiçbirini görmüyordu.
3. Adı `program` tablosunda olmayan hedefler (ECN, SEC, VBA, YZV) hiç
   listelenmiyordu.
4. Aynı iterasyonlu iki plan arasındaki eşitliği sorgunun satır sırası
   bozuyordu (ISL → ELE: ISL_ELE mi TUMMUH_ELE mi, indekse bağlıydı).
"""
import pathlib
import sqlite3

import pytest

from itucap import basvuru as B
from itucap import db
from itucap import plans as PL
from itucap import ui as UI

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


SON = "2019-2020 / Güz Dönemi Sonrası"


def _katalog(yol: pathlib.Path, host_listesi: bool = True):
    """Gerçek katalogdan küçültülmüş hâl.

    EHB'nin iki ÇAP planı: TUMMUH_EHB (OBS: GEO'ya açık, BLG'ye DEĞİL) ve
    BLG_EHB (BLG + BLGE). BLG'nin ÇAP planı TUMMUH_BLG — OBS listesi BLGE'yi
    de yazıyor (gerçekte TUMMUH_MAT'ın MATE'yi yazdığı gibi). YZV'nin planı
    var ama `program` satırı yok. ELE: ISL_ELE ile TUMMUH_ELE, ikisi de
    iterasyonsuz ve ikisi de ISL'ye açık.
    """
    con = db.connect(yol, "schema.sql")
    con.executemany(
        "INSERT INTO program(code,name,level) VALUES (?,?,'LS')",
        [("BLG", "Bilgisayar Mühendisliği Lisans"),
         ("BLGE", "Bilgisayar Mühendisliği (İngilizce) Lisans"),
         ("EHB", "Elektronik ve Haberleşme Mühendisliği Lisans"),
         ("GEO", "Geomatik Mühendisliği Lisans"),
         ("ISL", "İşletme Mühendisliği Lisans"),
         ("ELE", "Elektronik Mühendisliği Lisans"),
         # Taban kodu aynı ama AYRI bölüm: dil eşi sayılmamalı.
         ("KMY", "Kimya Lisans"),
         ("KMYE", "Fizik (İngilizce) Lisans"),
         # Adında "Mühendisliği" var ama OBS hiçbir TUMMUH planında yazmıyor
         # (gerçek katalogda AIN, BES — uluslararası ortak programlar).
         ("AIN", "İnşaat Mühendisliği (İngilizce) UOLP (Azerbaycan-AZMIU)")])
    con.executemany(
        """INSERT INTO plan(id,program_code,plan_type,title,host_program_code,
                            iteration,source) VALUES (?,?,'cap',?,?,?,'obs')""",
        # TUMMUH_EHB daha YENİ: tarama OBS listesine bakmasaydı (koddan
        # tahmin), BLG öğrencisine bunu seçerdi.
        [(20, "EHB", "TUMMUH_EHB ÇAP Programı", "TUMMUH", "2021-2022 / Güz Dönemi Sonrası"),
         (21, "EHB", "BLG_EHB ÇAP Programı", "BLG", SON),
         (22, "BLG", "TUMMUH_BLG ÇAP Programı", "TUMMUH", SON),
         (23, "YZV", "BLG_YZV ÇAP Programı", "BLG", ""),
         (30, "ELE", "TUMMUH_ELE ÇAP Programı", "TUMMUH", ""),
         (31, "ELE", "ISL_ELE ÇAP Programı", "ISL", ""),
         (40, "KMY", "KMYE_KMY ÇAP Programı", "KMYE", SON)])
    slotlar = {20: ["EHB 201", "EHB 202", "EHB 203"], 21: ["EHB 301"],
               22: ["BLG 101", "BLG 102"], 23: ["YZV 101", "YZV 102"],
               30: ["ELE 101"], 31: ["ELE 201", "ELE 202"], 40: ["KMY 101"]}
    con.executemany(
        """INSERT INTO plan_slot(plan_id,slot_kind,course_code,credits,position)
           VALUES (?,'REQUIRED',?,3,?)""",
        [(p, c, i) for p, cs in slotlar.items() for i, c in enumerate(cs)])
    if host_listesi:
        con.executemany(
            "INSERT INTO plan_host_program(plan_id,program_code,obs_code) VALUES (?,?,?)",
            [(20, "GEO", "GEO_LS"), (20, "ISL", "ISL_LS"),
             (21, "BLG", "BLG_LS"), (21, "BLGE", "BLGE_LS"),
             (22, "GEO", "GEO_LS"), (22, "BLGE", "BLGE_LS"),
             (23, "BLG", "BLG_LS"), (23, "BLGE", "BLGE_LS"),
             (30, "ISL", "ISL_LS"), (30, "GEO", "GEO_LS"),
             (31, "ISL", "ISL_LS"),
             (40, "KMYE", "KMYE_LS")])
    con.commit()
    con.row_factory = sqlite3.Row
    ucon = db.connect(yol.with_name("user.sqlite3"), "schema_user.sql")
    ucon.execute("INSERT INTO student(id,label) VALUES (1,'ben')")
    ucon.commit()
    return con, ucon


def _secenekler(con, ucon, anadal):
    s = B.survey(con, ucon, 1, "cap", exclude={anadal}, anadal=anadal)
    return {o.program_code: o for o in s.options}


# =============================================== 1. OBS listesi kesin söz
def test_BLG_ogrencisi_KENDI_planini_goruyor(tmp_path):
    """TUMMUH_EHB OBS'de BLG'ye açık değil; BLG'ninki BLG_EHB."""
    con, ucon = _katalog(tmp_path / "ref.sqlite3")
    for an in ("BLG", "BLGE"):
        s = _secenekler(con, ucon, an)
        assert s["EHB"].plan_id == 21, (an, s["EHB"].plan_title)
        assert s["EHB"].slots_total == 1


def test_OBS_listesinde_olmayana_semsiye_acilmiyor(tmp_path):
    """AIN'in adı "Mühendisliği" içeriyor; koddan tahmin TUMMUH planlarını
    ona açardı. OBS listesi yazmıyor → hiçbiri açık değil."""
    con, ucon = _katalog(tmp_path / "ref.sqlite3")
    s = B.survey(con, ucon, 1, "cap", exclude={"AIN"}, anadal="AIN")
    assert s.options == []
    assert s.other_host >= 3


def test_GEO_ogrencisi_semsiye_plani_goruyor(tmp_path):
    con, ucon = _katalog(tmp_path / "ref.sqlite3")
    s = _secenekler(con, ucon, "GEO")
    assert s["EHB"].plan_id == 20
    assert s["BLG"].plan_id == 22
    assert "YZV" not in s                    # BLG_YZV yalnız BLG/BLGE'ye açık


def test_TARAMA_ile_SECIM_ayni_plan(tmp_path):
    """★★ Pencerenin saydığı plan, program seçilince kullanılan plan."""
    con, ucon = _katalog(tmp_path / "ref.sqlite3")
    n = 0
    for an in ("BLG", "BLGE", "GEO", "ISL", "KMYE"):
        for kod, o in _secenekler(con, ucon, an).items():
            assert o.plan_id == PL.ikinci_plan(con, kod, "cap", an), (an, kod)
            n += 1
    assert n >= 8


# ============================================ 2. kendi bölümü seçenek değil
def test_DIL_ESI_kendi_bolumu_listelenmiyor(tmp_path):
    """OBS, TUMMUH_BLG'nin listesinde BLGE'yi yazıyor; yine de BLGE
    öğrencisi Bilgisayar Mühendisliği'nde ÇAP yapamaz."""
    con, ucon = _katalog(tmp_path / "ref.sqlite3")
    assert "BLG" not in _secenekler(con, ucon, "BLGE")
    assert "BLG" in _secenekler(con, ucon, "GEO")


def test_DIL_ESI_ad_ile_dogrulaniyor(tmp_path):
    """Taban kodu aynı ama adı farklı program ELENMİYOR: eş son harften
    tahmin edilmiyor."""
    con, ucon = _katalog(tmp_path / "ref.sqlite3")
    assert "KMY" in _secenekler(con, ucon, "KMYE")


def test_DIL_ESI_liste_yokken_de(tmp_path):
    """OBS listesi çekilmemiş eski katalog: şemsiye (TUMMUH) koddan tahmin
    ediliyor ve BLGE'yi de tutuyor — kendi bölümü yine elenmeli."""
    con, ucon = _katalog(tmp_path / "ref.sqlite3", host_listesi=False)
    s = _secenekler(con, ucon, "BLGE")
    assert "BLG" not in s
    # Yedek yol da taban kodu tanıyor: "BLG" ev sahipli plan BLGE'ye açık.
    assert "YZV" in s
    # Liste yokken ikisi de "açık" sayılıyor; yenisi seçiliyor — ve seçim
    # yine program seçildiğinde kullanılacak planla aynı.
    assert s["EHB"].plan_id == 20 == PL.ikinci_plan(con, "EHB", "cap", "BLGE")


@pytest.mark.parametrize("host,anadal,ok", [
    ("BLG", "BLGE", True), ("BLG", "BLG", True), ("BLGE", "BLGE", True),
    ("BLG", "GEO", False), ("GEO", "BLGE", False), ("", "BLGE", False)])
def test_HOST_taban_kod(host, anadal, ok):
    assert B.host_matches(host, anadal, "") is ok


# ====================================== 3. adı katalogda olmayan program
def test_ADSIZ_program_dusmuyor(tmp_path):
    con, ucon = _katalog(tmp_path / "ref.sqlite3")
    s = B.survey(con, ucon, 1, "cap", exclude={"BLG"}, anadal="BLG")
    j = B.to_json(s)
    yzv = [o for o in j["options"] if o["code"] == "YZV"]
    assert yzv and yzv[0]["name"] == "", "ad uydurulmamalı"
    assert yzv[0]["planId"] == 23


def test_ADSIZ_program_arayuzde_soyleniyor():
    assert "${o.name ? esc(o.name) : `<span style=\"color:var(--ink-3)\">(adı katalogda yok)</span>`}" in KAYNAK


# ============================================================ 4. eşitlik
def test_ESITLIKTE_anadalin_kendi_plani(tmp_path):
    """ISL_ELE ile TUMMUH_ELE: ikisi de ISL'ye açık, ikisinin de
    iterasyonu boş. ISL öğrencisi için kendi planı; GEO için şemsiye."""
    con, ucon = _katalog(tmp_path / "ref.sqlite3")
    assert PL.ikinci_plan(con, "ELE", "cap", "ISL") == 31
    assert _secenekler(con, ucon, "ISL")["ELE"].plan_id == 31
    assert PL.ikinci_plan(con, "ELE", "cap", "GEO") == 30


def test_ESITLIK_satir_sirasina_bagli_degil():
    """Aynı satırlar hangi sırayla gelirse gelsin aynı plan."""
    def satir(i, host):
        return {"id": i, "iteration": "", "source": "obs", "host_program_code": host}
    a = [satir(30, "TUMMUH"), satir(31, "ISL"), satir(12, "TUMMUH")]
    for sira in (a, a[::-1], [a[1], a[2], a[0]]):
        assert PL.en_guncel_satir(sira, "ISL")["id"] == 31
        assert PL.en_guncel_satir(sira, "GEO")["id"] == 12      # küçük id


# ============================================= 5. "Öncesi" iterasyonu eski
@pytest.mark.parametrize("eski,yeni", [
    # Aynı yılla başlıyorlar; "Öncesi" o yıldan ÖNCE başlayanların planı.
    ("2023-2024 / Güz Dönemi Öncesi",
     "2023-2024 / Güz ile 2026-2027 / Güz Dönemleri Arası"),
    ("2013-2014 / Güz Dönemi Öncesi", "2013-2014 / Güz Dönemi Sonrası"),
    ("2012-2013 / Güz Dönemi Öncesi", "2013-2014 / Güz Dönemi Öncesi"),
    # OBS'deki yazım hatası: "Sonraı" da açık uçlu.
    ("2021-2022 / Güz ile 2024-2025 / Güz Dönemleri Arası",
     "2021-2022 / Güz Dönemi Sonraı"),
])
def test_ITERASYON_sirasi(eski, yeni):
    assert PL.iteration_key(yeni) > PL.iteration_key(eski), (eski, yeni)


def test_ONCESI_secilmiyor_tarama_ve_secim_ayni(tmp_path):
    """Gerçek katalog: ELE öğrencisi GEO ÇAP'ı seçince 2018 "Öncesi" planı
    alıyordu. Tarama da seçim de 2018–2023 "Arası" planını vermeli."""
    con, ucon = _katalog(tmp_path / "ref.sqlite3")
    con.executemany(
        """INSERT INTO plan(id,program_code,plan_type,title,host_program_code,
                            iteration,source) VALUES (?,'GEO','cap',?,'ELE',?,'obs')""",
        # Eski planın id'si BÜYÜK: "en büyük id" gibi bir kestirme yanlışı seçer.
        [(61, "ELE_GEO eski", "2018-2019 / Güz Dönemi Öncesi"),
         (60, "ELE_GEO", "2018-2019 / Güz ile 2023-2024 / Güz Dönemleri Arası")])
    con.executemany(
        "INSERT INTO plan_host_program(plan_id,program_code,obs_code) VALUES (?,'ELE','ELE_LS')",
        [(60,), (61,)])
    con.commit()
    assert PL.ikinci_plan(con, "GEO", "cap", "ELE") == 60
    assert _secenekler(con, ucon, "ELE")["GEO"].plan_id == 60
