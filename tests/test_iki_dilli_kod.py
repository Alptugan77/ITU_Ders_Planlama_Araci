"""Faz 16 — OBS'nin yeni plan düzeni: tek hücrede İKİ ders kodu.

Kullanıcı raporu 22.08.2026: "elk çap planı 5 ders gözüküyor ama daha fazla
olması lazım böyle birkaç program var".

Teşhis: TUMMUH_ELK planının sayfasında 28 satır vardı, veritabanına 5 slot
yazılmıştı. Sebep, kod hücresinin artık iki kod taşıması:

    <td><a>EEF 110</a><br><a>EEF 110E</a><br></td>

`Node.text(strip=True)` bunu "EEF 110EEF 110E" diye BİTİŞİK veriyor; eski
parser tek kod bekliyordu, eşleşmeyince satırı `return 0` ile SESSİZCE
düşürüyordu. 23 satır böyle kayboldu ve plan "tamamlandı" görünüyordu.

★ Bu dosya iki şeyi birden koruyor:
  1. iki kodun da okunması ve ikisinin de slotu doldurabilmesi,
  2. ayrıştırılamayan satırın bir daha SESSİZCE düşmemesi.
"""
from pathlib import Path

import pytest

from itucap import db, quality, rules
from itucap.normalize import course_codes_in
from itucap.sources import obs_plan

FIXTURES = Path(__file__).parent / "fixtures"
META = {
    "plan_id": 2533, "title": "TUMMUH_ELK ÇAP Programı 2025-2026 / Güz Dönemi Sonrası",
    "pair_code": "TUMMUH_ELK", "host_program_code": "TUMMUH",
    "target_program_code": "ELK", "iteration": "2025-2026 / Güz Dönemi Sonrası",
    "plan_type": "cap", "obs_program_code": "ELK_LS",
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
    obs_plan.scrape_plan(FakeClient(FIXTURES / "cap_plan_2533.html"), con, META,
                         fetch_pools=False)
    return con


# --------------------------------------------------------------- ayrıştırma
@pytest.mark.parametrize("metin,bekleneni", [
    ("EEF 110\nEEF 110E",        ["EEF 110", "EEF 110E"]),
    ("EEF 110 / EEF 110E",       ["EEF 110", "EEF 110E"]),
    ("MAT 103E",                 ["MAT 103E"]),
    ("EEF 110\nEEF 110\n",       ["EEF 110"]),        # tekrar atılır
    ("Dersler",                  []),
    ("",                         []),
])
def test_course_codes_in(metin, bekleneni):
    assert course_codes_in(metin) == bekleneni


def test_bitisik_metinden_kod_uydurulmaz():
    """★ Ayırıcısız metin, YANLIŞ kod üretmemeli.

    'EEF 110EEF 110E' üzerinde kod ararsak regex 'EEF 110EE' gibi var olmayan
    bir ders üretir. Var olmayan bir kod, boş sonuçtan daha tehlikelidir:
    öğrenci bunu OBS'de arar ve bulamaz."""
    assert course_codes_in("EEF 110EEF 110E") == []


# ------------------------------------------------------------------ tarama
def test_butun_satirlar_yaziliyor(plan):
    """★ Asıl hata: 4 satırlık tablodan 4 slot çıkmalı, 1 değil."""
    n = plan.execute("SELECT COUNT(*) FROM plan_slot WHERE plan_id=2533").fetchone()[0]
    assert n == 4


def test_satir_sayisi_ile_slot_sayisi_ayni(plan):
    """Sessiz düşmenin veritabanından görülebilir kanıtı."""
    satir, slot = plan.execute(
        "SELECT MAX(position)+1, COUNT(*) FROM plan_slot WHERE plan_id=2533").fetchone()
    assert satir == slot


def test_ikinci_dil_kodu_saklaniyor(plan):
    row = plan.execute(
        "SELECT course_code, alt_course_codes FROM plan_slot "
        "WHERE plan_id=2533 AND position=0").fetchone()
    assert row["course_code"] == "EEF 110"
    assert row["alt_course_codes"] == "EEF 110E"


def test_zs_sutunu_atilmiyor(plan):
    """Ham Z/S bilgisi saklanmalı — 'zorunlu muydu' sorusu sonradan sorulacak."""
    assert plan.execute(
        "SELECT zs_raw FROM plan_slot WHERE plan_id=2533 AND position=0").fetchone()[0] == "Z"


def test_adi_belli_secmeli_bos_havuz_olmuyor(plan):
    """★ Z/S='S' ama grup bağlantısı yok: ders ADI belli.

    Eskiden seçeneksiz bir havuz yazılıyordu — hiçbir zaman dolamayan, yani
    ilerlemeyi sonsuza kadar eksik gösteren bir slot. Doğrusu, seçenekleri
    dersin iki dili olan bir havuz."""
    slot = plan.execute(
        "SELECT id, slot_kind FROM plan_slot WHERE plan_id=2533 AND position=2").fetchone()
    assert slot["slot_kind"] == "ELECTIVE_POOL"
    secenek = {r[0] for r in plan.execute(
        "SELECT course_code FROM pool_option WHERE slot_id=?", (slot["id"],))}
    assert secenek == {"EEF 206", "EEF 206E"}


def test_gercek_havuz_hala_havuz(plan):
    """grupId'li satır eskisi gibi havuz kalmalı — düzeltme onu bozmamalı."""
    row = plan.execute(
        "SELECT slot_kind, pool_group_id, pool_category FROM plan_slot "
        "WHERE plan_id=2533 AND position=3").fetchone()
    assert row["slot_kind"] == "ELECTIVE_POOL"
    assert row["pool_group_id"] == "12559"
    assert row["pool_category"] == "MT"


def test_eski_duzen_hala_calisiyor(con):
    """Tek kodlu ESKİ sayfa düzeni bozulmadı (regresyon)."""
    fx = FIXTURES / "cap_plan_2229.html"
    if not fx.exists():
        pytest.skip("fixture yok")
    n = obs_plan.scrape_plan(FakeClient(fx), con, {**META, "plan_id": 2229}, fetch_pools=False)
    assert n >= 8
    kinds = dict(con.execute(
        "SELECT slot_kind, COUNT(*) FROM plan_slot WHERE plan_id=2229 GROUP BY 1"))
    assert kinds.get("REQUIRED", 0) >= 6


# ------------------------------------------------------- slot karşılanması
def test_iki_dilden_biri_slotu_doldurur(plan):
    """★ İngilizce şubeyi almış öğrenci 'dersi almamış' sayılmamalı."""
    slot_id = plan.execute(
        "SELECT id FROM plan_slot WHERE plan_id=2533 AND position=0").fetchone()[0]
    assert rules.slot_satisfied(plan, slot_id, {"EEF 110E": "BB"}).satisfied
    assert rules.slot_satisfied(plan, slot_id, {"EEF 110": "CC"}).satisfied
    assert not rules.slot_satisfied(plan, slot_id, {"EEF 210": "AA"}).satisfied


def test_plan_codes_iki_dili_de_veriyor(plan):
    """★ ÇAP ORTALAMASI bunun üzerinden hesaplanıyor.

    Yalnız ana koda baksaydı, İngilizce şubede alınan ders ÇAP ortalamasına
    hiç girmezdi — ve bu, ekranda 'hesaplanamadı' değil, YANLIŞ BİR SAYI olarak
    görünürdü."""
    assert {"EEF 110", "EEF 110E", "EEF 211", "EEF 211E"} <= rules.plan_codes(plan, 2533)


def test_plan_codes_havuzu_istenince_ekliyor(plan):
    assert "EEF 206E" not in rules.plan_codes(plan, 2533)
    assert "EEF 206E" in rules.plan_codes(plan, 2533, pools=True)


def test_plan_codes_bos_plan_listesinde_patlamaz(plan):
    assert rules.plan_codes(plan) == set()
    assert rules.plan_codes(plan, None, None) == set()


def test_slot_codes_eski_satirda_patlamaz():
    """`alt_course_codes` NULL olan eski kayıtlarda davranış değişmemeli."""
    assert rules.slot_codes({"course_code": "MAT 103E", "alt_course_codes": None}) \
        == ["MAT 103E"]


# ---------------------------------------------------------- kalite kontrolü
def test_dusen_satir_kontrolu_sifir_dondurur(plan):
    assert quality._dropped_plan_rows(plan) is None


def test_dusen_satir_kontrolu_bosluk_yakalar(plan):
    """Kontrolün gerçekten çalıştığının kanıtı: bir slotu silince yakalamalı."""
    plan.execute("DELETE FROM plan_slot WHERE plan_id=2533 AND position=1")
    detay = quality._dropped_plan_rows(plan)
    assert detay and "1 satır" in detay


def test_kendi_planindaki_bosluk_one_cikar(plan):
    plan.execute("DELETE FROM plan_slot WHERE plan_id=2533 AND position=1")
    assert "SENİN" in quality._dropped_plan_rows(plan, mine=(2533,))


class _Sabit:
    def __init__(self, html):
        self.html = html

    def get(self, url, params=None):
        return self.html


_BASLIK = ("<tr><th>Ders Kodu</th><th>Ders Adı</th><th>Ders Dili</th><th>Z/S</th>"
           "<th>Kredi</th><th>AKTS</th><th>Teo.</th><th>Uyg.</th><th>Lab.</th>"
           "<th>Türü</th></tr>")


def test_ayristirilamayan_satir_raporlanir(con):
    """★ Ders tablosunun İÇİNDEKİ anlaşılmayan satır sessizce düşmüyor."""
    html = ("<table>" + _BASLIK +
            "<tr><td>EEF 110</td><td>Ders</td><td>Türkçe</td><td>Z</td><td>2</td>"
            "<td>4</td><td>1</td><td>2</td><td>0</td><td>LA</td></tr>"
            "<tr><td>çöp</td><td>satır</td><td>-</td><td>-</td><td>3</td>"
            "<td>6</td><td></td><td></td><td></td><td></td></tr></table>")
    obs_plan.dropped_rows.clear()
    n = obs_plan.scrape_plan(_Sabit(html), con, {**META, "plan_id": 9001},
                             fetch_pools=False)
    assert n == 1
    assert obs_plan.dropped_rows and obs_plan.dropped_rows[0][0] == 9001


def test_siniflandirilamayan_tablo_raporlanir(con):
    """★ Yeni bir hata kapısı: satır değil, TABLO kaybolabilir.

    Başlık satırı tanınmazsa tablo hiç gezilmez. Sessiz kalsaydık plan
    "OBS'de boş yayınlanmış" görünürdü — kendi hatamızı kaynağın eksiği gibi
    göstermek, düzeltilmesi en zor yalan türü."""
    html = ("<table><tr><th>Kod</th><th>Ad</th><th>Bir şey</th><th>Başka</th>"
            "<th>Daha</th><th>Fazla</th></tr>"
            + "".join(f"<tr><td>EEF 21{i}</td><td>Ders {i}</td><td>x</td>"
                      f"<td>y</td><td>3</td><td>6</td></tr>" for i in range(4))
            + "</table>")
    obs_plan.dropped_rows.clear()
    obs_plan.scrape_plan(_Sabit(html), con, {**META, "plan_id": 9002}, fetch_pools=False)
    assert any(p == 9002 and "sınıflandırılamayan" in r[0]
               for p, r in obs_plan.dropped_rows)
    # ★ "kaynakta boş" DEMİYORUZ — tablo vardı, biz anlayamadık.
    assert con.execute("SELECT has_course_table FROM plan WHERE id=9002").fetchone()[0] == 1


# ------------------------------------- eski düzen: TR ve EN AYRI SATIRDA
def _iki_satir(kod_tr, kod_en, kredi_tr="3", kredi_en="3"):
    return ("<table>" + _BASLIK
            + f"<tr><td>{kod_en}</td><td>Circuits</td><td>English</td><td>Z</td>"
              f"<td>{kredi_en}</td><td>5</td><td>3</td><td>0</td><td>0</td><td>LA</td></tr>"
            + f"<tr><td>{kod_tr}</td><td>Devreler</td><td>Türkçe</td><td>Z</td>"
              f"<td>{kredi_tr}</td><td>5</td><td>3</td><td>0</td><td>0</td><td>LA</td></tr>"
            + "<tr><td>MAT 103</td><td>Matematik</td><td>Türkçe</td><td>Z</td>"
              "<td>4</td><td>6</td><td>4</td><td>0</td><td>0</td><td>TB</td></tr></table>")


def test_ayri_satirdaki_dil_cifti_birlesiyor(con):
    """★ Eski sayfa düzeninde TR ve EN AYRI SATIR — her ikisini ayrı zorunlu
    ders saymak planı iki katına çıkarıyordu (INS_ELK: sayfa 70 kredi diyor,
    biz 121,5 topluyorduk)."""
    obs_plan.scrape_plan(_Sabit(_iki_satir("EHB 211", "EHB 211E")), con,
                         {**META, "plan_id": 9100}, fetch_pools=False)
    rows = {r["course_code"]: r["alt_course_codes"] for r in con.execute(
        "SELECT course_code, alt_course_codes FROM plan_slot WHERE plan_id=9100")}
    assert rows == {"EHB 211": "EHB 211E", "MAT 103": None}


def test_birlesince_kredi_iki_kez_sayilmiyor(con):
    obs_plan.scrape_plan(_Sabit(_iki_satir("EHB 211", "EHB 211E")), con,
                         {**META, "plan_id": 9101}, fetch_pools=False)
    assert con.execute(
        "SELECT SUM(credits) FROM plan_slot WHERE plan_id=9101").fetchone()[0] == 7.0


def test_birlesince_pozisyon_bosluk_birakmiyor(con):
    """★ Kendi düzeltmemizi 'satır kayboldu' diye raporlamamalıyız —
    raporlasaydık kontrol güvenilmez olur ve okunmaz hâle gelirdi."""
    obs_plan.scrape_plan(_Sabit(_iki_satir("EHB 211", "EHB 211E")), con,
                         {**META, "plan_id": 9102}, fetch_pools=False)
    satir, slot = con.execute(
        "SELECT MAX(position)+1, COUNT(*) FROM plan_slot WHERE plan_id=9102").fetchone()
    assert satir == slot == 2
    assert quality._dropped_plan_rows(con) is None


def test_kredisi_farkli_olan_birlestirilmiyor(con):
    """★ 'X' ile 'XE' kredileri farklıysa aynı ders olduğundan EMİN DEĞİLİZ.

    Birleştirmek, gerçekten iki ayrı dersi olan bir plandan ders silmek
    olurdu — sessizce eksik plan, en pahalı hata."""
    obs_plan.scrape_plan(_Sabit(_iki_satir("EHB 211", "EHB 211E", "3", "4")), con,
                         {**META, "plan_id": 9103}, fetch_pools=False)
    assert con.execute(
        "SELECT COUNT(*) FROM plan_slot WHERE plan_id=9103").fetchone()[0] == 3


def test_yeni_duzen_birlestirmeden_etkilenmiyor(plan):
    """Regresyon: tek hücrede iki kod gelen plan zaten birleşikti — birleştirme
    ondan slot SİLMEMELİ (fixture 4 satırlık kısaltılmış sürüm)."""
    assert plan.execute(
        "SELECT COUNT(*) FROM plan_slot WHERE plan_id=2533").fetchone()[0] == 4
    assert plan.execute(
        "SELECT COUNT(*) FROM plan_slot WHERE plan_id=2533 "
        "AND alt_course_codes IS NOT NULL").fetchone()[0] == 2
