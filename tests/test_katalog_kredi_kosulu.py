"""Faz 37 — katalogda ilan edilmiş kredi tabanı.

`course.class_restriction` sütunu itu-helper'ın "Sınıf Kısıtı" alanı ama
değerleri KREDİ ('Yok' / '95,00' / '60,00' / '30,00'). Faz 37'ye kadar hiç
okunmuyordu: beyan edilmiş kural katalogda tabanı olan 498 dersin yalnız
173'ünü tanıyordu, 325 ders motorun kör noktasındaydı.

Buradaki testler üç şeyi tutuyor:
  1. ayrıştırma UYDURMUYOR (bozuk değer eşiğe çevrilmez),
  2. beyan ile katalog çelişince EN KATI olan uygulanır,
  3. eleme SESSİZ DEĞİL — hem darboğaz raporunda hem komut satırı çıktısında.
"""
import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import db, policy as POL, recommend as REC        # noqa: E402
from itucap import student as S                               # noqa: E402

from test_ui import _collect, dbs                             # noqa: E402,F401


# ------------------------------------------------------------- ayrıştırma
@pytest.mark.parametrize("raw,beklenen", [
    ("95,00", 95.0),
    ("60,00", 60.0),
    ("30,00", 30.0),
    ("95.00", 95.0),
    ("95", 95.0),
    ("Yok", None),
    ("yok", None),
    ("", None),
    (None, None),
    ("   ", None),
])
def test_deger_ayristirma(raw, beklenen):
    assert POL.parse_catalog_floor(raw) == beklenen


def test_bozuk_deger_esige_CEVRILMEZ():
    """★ Kaynakta 7 derste sütun kaymış ve alanda ders adı duruyor.

    Bir ders adını krediye çevirmeye kalkmak uydurma bir kısıt üretirdi;
    `None` dönmek "bu ders için taban bilmiyoruz" demek — doğru cevap.
    """
    for bozuk in ("Mikroişlemci Sistemleri", "Complex Analysis", "Türkçe",
                  "Sosyal Robotlar"):
        assert POL.parse_catalog_floor(bozuk) is None


def test_sifir_taban_yok_sayilir():
    assert POL.parse_catalog_floor("0") is None
    assert POL.parse_catalog_floor("0,00") is None


# ------------------------------------------------------------------ kontrol
def test_katalog_tabani_dersi_ELER():
    v = POL.check("CEV 461E", credits_have=20.0, rules=[],
                  catalog_raw="30,00", catalog_rule=POL.DEFAULT_CATALOG_RULE)
    assert not v
    assert v.rule.name == POL.CATALOG_RULE_NAME
    assert v.missing == 10.0


def test_taban_dolduysa_gecer():
    assert POL.check("CEV 461E", 40.0, rules=[], catalog_raw="30,00",
                     catalog_rule=POL.DEFAULT_CATALOG_RULE)


def test_katalog_verilmezse_ESKI_DAVRANIS():
    """Değer geçmeyen çağıran eski davranışı görmeli — sessiz değişiklik yok."""
    assert POL.check("CEV 461E", 0.0, rules=[])


def test_kapatilabilir():
    kapali = POL.CatalogRule(enabled=False)
    assert POL.check("CEV 461E", 0.0, rules=[], catalog_raw="95,00",
                     catalog_rule=kapali)


def test_beyan_ile_katalog_celisince_EN_KATI():
    """`* 4902` beyanı 95 diyor, katalog o derslerde 'Yok' diyor (61 ders)."""
    beyan = [POL.CreditRule("Bitirme çalışması", 95.0, patterns=("* 4902E",))]
    v = POL.check("BLG 4902E", 10.0, rules=beyan, catalog_raw="Yok",
                  catalog_rule=POL.DEFAULT_CATALOG_RULE)
    assert not v and v.rule.min_credits == 95.0
    # Ters yön: katalog daha katıysa katalog kazanır.
    gevsek = [POL.CreditRule("Gevşek", 30.0, patterns=("* 4902E",))]
    v2 = POL.check("BLG 4902E", 40.0, rules=gevsek, catalog_raw="95,00",
                   catalog_rule=POL.DEFAULT_CATALOG_RULE)
    assert not v2 and v2.rule.min_credits == 95.0


def test_ayar_dosyasindan_okunuyor(tmp_path):
    p = tmp_path / "kurallar.toml"
    p.write_text("[katalog_kredi_kosulu]\nkullan = false\n", encoding="utf-8")
    assert POL.load_catalog_rule(p).enabled is False
    p.write_text("[katalog_kredi_kosulu]\nkullan = true\n"
                 'kaynak = "deneme"\n', encoding="utf-8")
    r = POL.load_catalog_rule(p)
    assert r.enabled and r.source == "deneme" and r.verified is False


def test_blok_yoksa_ACIK(tmp_path):
    p = tmp_path / "kurallar.toml"
    p.write_text("[[kredi_esigi]]\nad='x'\nmin_kredi=95\n", encoding="utf-8")
    assert POL.load_catalog_rule(p).enabled is True


def test_gercek_kurallar_dosyasi_okunuyor():
    """Repodaki `config/kurallar.toml` bu bloğu taşıyor ve açık."""
    r = POL.load_catalog_rule()
    assert r.enabled is True
    # ⚠️ Yorum bizim olduğu için doğrulanmamış işaretli kalmalı.
    assert r.verified is False
    assert "Sınıf Kısıtı" in r.source


# ------------------------------------------------ motor: eleme GÖRÜNÜR olmalı
@pytest.fixture()
def kurulum(tmp_path):
    con = db.connect(tmp_path / "ref.sqlite3", "schema.sql")
    ucon = db.connect(tmp_path / "user.sqlite3", "schema_user.sql")
    con.executemany(
        "INSERT INTO course(code,name,credits,ects,prereq_raw,class_restriction)"
        " VALUES (?,?,?,?,?,?)",
        [("CEV 461E", "Environmental Chemistry I", 3.0, 5.0, None, "30,00"),
         ("CEV 100E", "Serbest ders", 3.0, 5.0, None, "Yok")],
    )
    con.execute("INSERT INTO plan(id,program_code,plan_type) VALUES (9,'CEV','cap')")
    con.executemany(
        "INSERT INTO plan_slot(plan_id,slot_kind,course_code,credits,position)"
        " VALUES (9,'REQUIRED',?,3.0,?)",
        [("CEV 461E", 0), ("CEV 100E", 1)])
    con.executemany(
        "INSERT INTO lesson(crn,term,course_code,capacity,enrolled)"
        " VALUES (?,'202610',?,30,0)",
        [("11111", "CEV 461E"), ("11112", "CEV 100E")])
    con.executemany(
        "INSERT INTO lesson_allowed_program(crn,program_code) VALUES (?,?)",
        [("11111", "CEV"), ("11112", "CEV")])
    con.executemany(
        "INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min)"
        " VALUES (?,1,540,660)", [("11111",), ("11112",)])
    con.commit()
    ucon.execute("INSERT INTO student(id,label) VALUES (1,'ben')")
    ucon.commit()
    return con, ucon


def test_darbogazda_KREDI_ESIGI_cikiyor(kurulum):
    con, ucon = kurulum
    engeller = REC.cap_blockers(con, ucon, 1, 9, "CEV", ["CEV"])
    by = {b.course: b for b in engeller}
    assert by["CEV 461E"].reason == "KREDI_ESIGI"
    assert "30" in by["CEV 461E"].detail
    assert "CEV 100E" not in by          # tabanı yok — engel de yok


def test_KREDI_ESIGI_komut_satiri_ciktisinda_YAZIYOR(kurulum):
    """★★ Faz 37 hatası: engel hesaplanıyordu, `format_blockers` basmıyordu.

    Arayüz gösteriyor, `make recommend` sessizce düşürüyordu — eleyen kural
    kendini göstermek zorunda.
    """
    con, ucon = kurulum
    metin = REC.format_blockers(REC.cap_blockers(con, ucon, 1, 9, "CEV", ["CEV"]))
    assert "KREDİ EŞİĞİ DOLMAMIŞ" in metin
    assert "CEV 461E" in metin
    assert "30 kredi eksik" in metin


def test_baslik_TURKCE_buyuk_harf(kurulum):
    """`'önşart eksik'.upper()` noktasız I verir — başlıkta yazım hatası."""
    con, ucon = kurulum
    metin = REC.format_blockers(REC.cap_blockers(con, ucon, 1, 9, "CEV", ["CEV"]))
    assert "EŞIĞI" not in metin        # noktasız I ile yazılmamalı


def test_aday_listesinden_ELENIYOR(kurulum):
    con, ucon = kurulum
    adaylar = REC.candidates(con, ucon, 1, None, 9, "CEV", "CEV",
                             allowed_programs=["CEV"])
    kodlar = {c.course for c in adaylar}
    assert "CEV 461E" not in kodlar
    assert "CEV 100E" in kodlar


# ------------------------------------------------- arayüz: eleme GÖRÜNÜYOR mu
def test_arayuz_TRANSKRIPT_YOKKEN_iddia_etmiyor(dbs):
    """★★ Faz 24/26'nın dersi: 0 kredi bir ÖLÇÜM değil, veri yokluğu.

    Girilmemiş bir transkript üzerinden "bu 12 dersi tutmuyorsun" demek,
    aracın en pahalı hata sınıfı. Kuralın varlığı yine söyleniyor.
    """
    con, ucon, sid = dbs
    con.execute("UPDATE course SET class_restriction='95,00' WHERE code='SEC 201'")
    con.commit()
    k = _collect(dbs)["credits"]["catalog"]
    assert k["noTranscript"] is True
    assert k["blocked"] == []


def test_arayuz_HAVUZDAKI_dersi_de_listeliyor(dbs):
    """⚠️ Katalog tabanı taşıyan derslerin çoğu seçmeli havuzda.

    Havuzları dışarıda bırakmak, elenen dersin sebebini tam da en çok
    elendiği yerde gizlerdi.
    """
    con, ucon, sid = dbs
    con.execute("UPDATE course SET credits=3.0 WHERE code IN ('GEO 303E','SEC 201')")
    con.execute("UPDATE course SET class_restriction='95,00' WHERE code='SEC 201'")
    con.commit()
    S.add_entries(ucon, sid, [S.make_entry("GEO 303E", "AA")])
    k = _collect(dbs)["credits"]["catalog"]
    assert k["noTranscript"] is False
    assert [b["course"] for b in k["blocked"]] == ["SEC 201"]
    assert k["blocked"][0]["min"] == 95.0 and k["blocked"][0]["missing"] == 92.0
    # Kaynak ve doğrulanma durumu taşınıyor: yorum bizim, gizlenmiyor.
    assert "Sınıf Kısıtı" in k["source"] and k["verified"] is False


def test_arayuz_taban_DOLUYSA_yazmiyor(dbs):
    """Tabanı zaten dolduran dersi listelemek gürültü olurdu."""
    con, ucon, sid = dbs
    con.execute("UPDATE course SET credits=3.0 WHERE code IN ('GEO 303E','SEC 201')")
    con.execute("UPDATE course SET class_restriction='1,00' WHERE code='SEC 201'")
    con.commit()
    S.add_entries(ucon, sid, [S.make_entry("GEO 303E", "AA")])
    assert _collect(dbs)["credits"]["catalog"]["blocked"] == []
