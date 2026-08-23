"""Faz 19 — yandal plan sayfasının kendi düzeni.

Faz 17'de eklenen `dropped_plan_rows` kontrolü ilk gerçek taramada işini
yaptı ve YENİ bir hata gösterdi: 13 yandal planında 34 satır düşüyordu.
Kazıya gidince asıl sorun düşen satırlar değil, **fazladan yazılan satırlar**
çıktı.

Yandal sayfasının düzeni ÇAP'tan farklı:

    TABLO 0   Ders Kodu | Ders Adı | Ders Dili | Z/S | Kredi | AKTS | …   ← PLAN
    TABLO 1+  Ders Kodu | Ders Adı | Kredi                          ← YARDIMCI
              ("tamamlama dersleri", seçmeli havuzların içerikleri)
    SON       Birincil Program Kodu | …                             ← anadallar

Yardımcı tablolar plan gereksinimi DEĞİL — "anadalında benzer ders varsa
bunlardan alabilirsin" listesi. Konuma güvenen eski kod hepsini zorunlu ders
sanıyordu: **UCK yandalı 8 ders / 22,5 kredi iken 43 zorunlu ders
görünüyordu.** Üstelik "İlişkili Programlar" tablosunun yandal sayfalarında
`id="dersPlanProgramList"` niteliği yok, o da ders tablosu sanılıyordu.

★ Bu, düşen satırdan daha sinsi bir hata: eksik veri "eksik" diye görünür,
uydurulmuş veri **doğru görünür**.
"""
from pathlib import Path

import pytest

from itucap import db, quality, sequence
from itucap.sources import obs_plan

FIXTURES = Path(__file__).parent / "fixtures"
META = {
    "plan_id": 1876, "title": "Uçak Mühendisliği Lisans Programı (Yandal)",
    "pair_code": "UCK_YD", "host_program_code": None,
    "target_program_code": "UCK_YD", "iteration": "",
    "plan_type": "yandal", "obs_program_code": "UCK_YD",
}


@pytest.fixture()
def con(tmp_path, monkeypatch):
    from itucap import config
    monkeypatch.setattr(config, "REF_DB", tmp_path / "ref.sqlite3")
    return db.connect(tmp_path / "ref.sqlite3", "schema.sql")


class FakeClient:
    def __init__(self, path):
        self.path = path

    def get(self, url, params=None):
        return self.path.read_text(encoding="utf-8")


@pytest.fixture()
def plan(con):
    obs_plan.dropped_rows.clear()
    obs_plan.scrape_plan(FakeClient(FIXTURES / "yandal_plan_1876.html"), con, META,
                         fetch_pools=False)
    return con


# ------------------------------------------------------ tablo sınıflandırma
def test_yalniz_ders_tablosu_slot_uretiyor(plan):
    """★ Asıl hata: 3 ders varken 8 slot yazılıyordu (yardımcı tablolar dahil)."""
    assert plan.execute(
        "SELECT COUNT(*) FROM plan_slot WHERE plan_id=1876").fetchone()[0] == 3


def test_yardimci_tablodaki_ders_zorunlu_sayilmiyor(plan):
    """★ 'Tamamlama dersi' bir gereksinim DEĞİL — anadalın örtüşmesine bağlı."""
    kodlar = {r[0] for r in plan.execute(
        "SELECT course_code FROM plan_slot WHERE plan_id=1876")}
    assert kodlar == {"UCK 351", "UZB 331", "UCK 322E"}
    for yardimci in ("UCK 421", "UCK 363E", "FIZ 201", "MAT 205"):
        assert yardimci not in kodlar


def test_yardimci_tablo_atilmiyor_notlara_giriyor(plan):
    """Gereksinim saymıyoruz ama İÇERİĞİ de kaybetmiyoruz —
    danışmanla konuşurken gereken tam şey bu liste."""
    notlar = plan.execute("SELECT notes_raw FROM plan WHERE id=1876").fetchone()[0] or ""
    assert "UCK 421" in notlar and "FIZ 201" in notlar
    assert "plan gereksinimi DEĞİL" in notlar


def test_ilisikili_programlar_tablosu_ders_sanilmiyor(plan):
    """★ Yandal sayfasında bu tablonun id NİTELİĞİ YOK; başlıktan tanınmalı."""
    hosts = {r[0] for r in plan.execute(
        "SELECT obs_code FROM plan_host_program WHERE plan_id=1876")}
    assert hosts == {"BIO_LS", "MET_LS"}
    assert "BIO" not in {r[0] for r in plan.execute(
        "SELECT course_code FROM plan_slot WHERE plan_id=1876")}


def test_program_kodu_normalize_ediliyor(plan):
    assert {r[0] for r in plan.execute(
        "SELECT program_code FROM plan_host_program WHERE plan_id=1876")} == {"BIO", "MET"}


# ---------------------------------------------------------- uydurma dönem
def test_donem_numarasi_UYDURULMUYOR(plan):
    """★ En sinsi kısım. `_term_numbers` başlık bulamazsa tabloları 1..N diye
    numaralandırıyordu. Yardımcı tablolar da ders tablosu sayılınca yandal
    planı 6 'dönem'e bölünmüş gibi görünüyordu — ve arayüzün "N. dönem +
    alttan" kipi bu uydurma numaralara göre ders eliyordu."""
    donemler = {r[0] for r in plan.execute(
        "SELECT term_no FROM plan_slot WHERE plan_id=1876")}
    assert donemler == {None}
    assert plan.execute("SELECT is_term_based FROM plan WHERE id=1876").fetchone()[0] == 0


def test_lisans_planinda_donem_hala_var(con):
    """Regresyon: gerçek yarıyıl tabloları olan planda dönem KAYBOLMAMALI."""
    fx = FIXTURES / "lisans_plan_2295.html"
    if not fx.exists():
        pytest.skip("fixture yok")
    obs_plan.scrape_plan(FakeClient(fx), con,
                         {**META, "plan_id": 2295, "plan_type": "lisans"},
                         fetch_pools=False)
    donemler = {r[0] for r in con.execute(
        "SELECT term_no FROM plan_slot WHERE plan_id=2295")}
    assert donemler - {None}, "dönem bilgisi kayboldu"
    assert con.execute("SELECT is_term_based FROM plan WHERE id=2295").fetchone()[0] == 1


# ------------------------------------------------------- kredi çapraz kontrol
def test_sayfanin_yazdigi_kredi_saklaniyor(plan):
    assert plan.execute(
        "SELECT declared_credits FROM plan WHERE id=1876").fetchone()[0] == 9.5


def test_kredi_tutuyor(plan):
    """★ Bağımsız çıpa: kaynağın yazdığı toplam ile bizim topladığımız kredi.

    Yandal hatası bu kontrol olsaydı ilk taramada yakalanırdı — 22,5 kredilik
    plan için 43 ders topladığımızda sayı tutmuyordu."""
    assert quality._plan_credit_mismatch(plan) is None


def test_kredi_tutmayinca_yakalaniyor(plan):
    """Kontrolün gerçekten çalıştığının kanıtı."""
    plan.execute("UPDATE plan SET declared_credits=99 WHERE id=1876")
    detay = quality._plan_credit_mismatch(plan)
    assert detay and "1876" in detay


def test_kredisiz_planda_iddia_yok(plan):
    """★ Sayfa toplam yazmamışsa KARŞILAŞTIRMA YAPMIYORUZ.

    Bilinmeyeni 0 sayıp "tutmuyor" demek, olmayan bir hata uydurmak olurdu."""
    plan.execute("UPDATE plan SET declared_credits=NULL WHERE id=1876")
    assert quality._plan_credit_mismatch(plan) is None


# ------------------------------------------------------------- uçtan uca
def test_kademeler_yandal_planinda_anlamli(plan):
    """Yandal planı artık 3 dersten oluşuyor; kademelendirme de öyle görmeli."""
    adimlar = sequence.plan_sequence(plan, 1876)
    assert {s.course for s in adimlar} == {"UCK 351", "UZB 331", "UCK 322E"}


def test_dusen_satir_yok(plan):
    satir, slot = plan.execute(
        "SELECT MAX(position)+1, COUNT(*) FROM plan_slot WHERE plan_id=1876").fetchone()
    assert satir == slot
    assert quality._dropped_plan_rows(plan) is None
    assert obs_plan.dropped_rows == []
