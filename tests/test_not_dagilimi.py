"""Faz 38 — ders not dağılımı (OBS `/public/DersNotDagilimi`).

Kullanıcı hatırlattı: veri her dönem yayınlanıyor. `docs/fikirler.md` bu
fikri **"elimizde böyle bir veri yok"** diye reddetmişti; gerekçe düştü.

Fixture'lar GERÇEK cevaptan alındı (02.09.2026, tarayıcı üzerinden):
`tests/fixtures/not_dagilimi_MAT103E_2026.html` ve `…_bulunamadi.html`.

Testlerin tuttuğu üç şey:
  1. TR/EN kodu BİRLEŞİK — anahtar kaynağın başlığından geliyor, biz
     "sondaki E'yi at" diye tahmin etmiyoruz,
  2. "bulunamadı" HTTP 200 ile geliyor ve **boş dağılımdan ayrılıyor**
     (sessiz sıfır bu projenin tekrar eden hatası),
  3. VF (devamsızlık) FF'ten ayrı YÜZDE olarak yazılıyor ve kaynağın
     kendi toplamı ile harflerin toplamı arasındaki fark gizlenmiyor.
"""
import pytest

from itucap import config, db
from itucap.sources import obs_notdagilimi as ND

FIX = config.ROOT / "tests" / "fixtures"
MAT = (FIX / "not_dagilimi_MAT103E_2026.html").read_text(encoding="utf-8")
YOK = (FIX / "not_dagilimi_bulunamadi.html").read_text(encoding="utf-8")


# ------------------------------------------------------------------ kodlar
@pytest.mark.parametrize("kod,beklenen", [
    ("MAT 103E", ("MAT", "103E")),
    ("MAT103E", ("MAT", "103E")),
    ("blg 212", ("BLG", "212")),
    ("BLG 4901E", ("BLG", "4901E")),
    # ⚠️ ÖLÇÜM: numaranın sonunda BİRDEN FAZLA harf olabiliyor. Tek harfe
    # izin veren ilk kalıp bu kodlarda patlıyordu, yani hiç sorulamıyorlardı.
    ("ING 103CO", ("ING", "103CO")),
    ("ING103SC", ("ING", "103SC")),
    ("FIZ 101EL", ("FIZ", "101EL")),
])
def test_kod_ayirma(kod, beklenen):
    assert ND.split_code(kod) == beklenen


def test_kod_ayrilamazsa_HATA():
    """⚠️ Sessizce boş dönmek, uca anlamsız bir istek atmak demekti."""
    with pytest.raises(ValueError):
        ND.split_code("bu bir ders kodu değil")


def test_anahtar_KAYNAGIN_BASLIGINDAN(  ):
    """★ 'Sondaki E'yi at' bir SEZGİ; kaynak zaten iki kodu da yazıyor."""
    assert ND.codes_from_title(
        "MAT103 - MAT103E, Matematik I / Mathematics I Grade Distribution"
    ) == ("MAT 103", "MAT 103E")


def test_tek_dilli_baslikta_tek_kod():
    assert ND.codes_from_title("MUZ 487, Türk Müziği Grade Distribution") \
        == ("MUZ 487",)


# --------------------------------------------------------------- ayrıştır
def test_gercek_cevap_ayristiriliyor():
    d = ND.parse(MAT)
    assert d.key == "MAT 103"
    assert d.codes == ("MAT 103", "MAT 103E")
    assert [t.term for t in d.terms] == ["202630", "202620", "202610"]
    guz = [t for t in d.terms if t.term == "202610"][0]
    assert guz.year_name == "2025-2026" and guz.term_name == "Fall Semester"
    assert guz.counts["FF"] == 428 and guz.counts["VF"] == 388
    # ⚠️ ÖLÇÜM: kaynağın kendi toplamı harflerin toplamına EŞİT DEĞİL.
    # 2988 ilan edilmiş, harfler 2987 ediyor — 1 kişi listelenen 15 harfin
    # dışında. Düzeltmiyoruz, ikisini de taşıyoruz.
    assert guz.announced == 2988
    assert sum(guz.counts.values()) == 2987


def test_YAZ_donemi_de_geliyor():
    """Yaz okulu verisi ilk kez elimizde (`fikirler §2.3` için hammadde)."""
    yaz = [t for t in ND.parse(MAT).terms if t.term.endswith("30")]
    assert yaz and yaz[0].announced == 991


def test_BULUNAMADI_bos_dagilimdan_AYRI():
    """★★ Uç HTTP 200 dönüyor. Durum koduna bakan bir tarayıcı bunu
    "hepsi sıfır" diye kaydederdi — sessiz sıfır."""
    with pytest.raises(ND.NotFound):
        ND.parse(YOK)


def test_TANINMAYAN_sayfa_sessizce_gecilmiyor():
    """Ne veri ne 'bulunamadı' → sayfa yapısı değişmiş olabilir; bunu
    "veri yok" saymak, bozulmayı görünmez kılardı."""
    with pytest.raises(ValueError):
        ND.parse("<html><body>bambaşka bir sayfa</body></html>")


# ----------------------------------------------------------------- özet
def test_ozet_VF_ile_FF_yi_AYIRIYOR():
    guz = [t for t in ND.parse(MAT).terms if t.term == "202610"][0]
    o = ND.summarise(guz.counts, guz.announced)
    assert o["n"] == 2987
    assert o["failed"] == 428 and o["absent"] == 388
    assert o["passed"] == 2987 - 428 - 388
    assert o["failRate"] == 14.3 and o["absentRate"] == 13.0


def test_kaynagin_TOPLAMI_ile_fark_SOYLENIYOR():
    """★ Kaynak 2988 diyor, harfler 2987 ediyor. Sessizce birini seçmek
    veriyi düzeltmek olurdu; farkı taşıyoruz."""
    guz = [t for t in ND.parse(MAT).terms if t.term == "202610"][0]
    o = ND.summarise(guz.counts, guz.announced)
    assert o["announced"] == 2988 and o["gap"] == 1
    bahar = [t for t in ND.parse(MAT).terms if t.term == "202620"][0]
    assert ND.summarise(bahar.counts, bahar.announced)["gap"] == 4


def test_ortalama_ARACIN_KENDI_olcegiyle():
    """★ Ortalama `prereq.GRADE_POINTS` ile hesaplanıyor: `VF` de `FF` de
    sıfır puan (İTÜ ortalamada ikisini de sayıyor). Burada başka bir kural
    kullanmak, aynı sayfada iki farklı "ortalama" tanımı bırakırdı.
    ⚠️ Ama VF ayrıca yüzde olarak da yazılıyor: düşük ortalamanın
    devamsızlıktan mı zorluktan mı geldiği okunabilmeli."""
    o = ND.summarise({"AA": 1, "VF": 99})
    assert o["meanPoints"] == 0.04
    assert o["absent"] == 99 and o["n"] == 100
    assert o["absentRate"] == 99.0


def test_bos_dagilim_ORTALAMA_UYDURMUYOR():
    o = ND.summarise({})
    assert o["n"] == 0 and o["meanPoints"] is None and o["passRate"] is None


# ------------------------------------------------------------------ sakla
@pytest.fixture()
def con(tmp_path):
    return db.connect(tmp_path / "ref.sqlite3", "schema.sql")


def test_saklama_ve_okuma(con):
    d = ND.parse(MAT)
    assert ND.store(con, d, 2026) == 3
    # İKİ kodla da bulunabiliyor: kullanıcı hangisini yazarsa yazsın.
    for kod in ("MAT 103", "MAT 103E"):
        r = ND.distribution(con, kod)
        assert r and r["key"] == "MAT 103"
        assert r["summary"]["n"] == 991          # en yeni dönem (yaz)


def test_AYNI_YARIYIL_tercih_ediliyor(con):
    """⚠️ 'En yeni' ile 'aynı yarıyıl' farklı: güz dersinin bahar dağılımı
    çoğunlukla birkaç bütünlemeci demek (ölçüm: BLG 212E baharda n=2,
    ikisi de FF)."""
    ND.store(con, ND.parse(MAT), 2026)
    r = ND.distribution(con, "MAT 103E", term="202710")   # güz istiyoruz
    assert r["selected"]["term"] == "202610"
    assert r["summary"]["n"] == 2987


def test_bilinmeyen_ders_TAHMIN_ETMIYOR(con):
    assert ND.lookup(con, "XYZ 999") is None
    assert ND.distribution(con, "XYZ 999") is None


def test_YAYINLANMAMIS_kaydediliyor(con):
    """'Veri yok' da bilgi: kaydedilmezse her tazelemede yeniden sorulur."""
    ND.store_missing(con, "MUZ 487", 2026)
    row = con.execute("SELECT status, terms FROM grade_distribution_run "
                      "WHERE course_key='MUZ 487'").fetchone()
    assert row["status"] == "yayinlanmamis" and row["terms"] == 0
    assert ND.coverage(con)["unpublished"] == 1


def test_yeniden_yazmak_BIRIKTIRMIYOR(con):
    d = ND.parse(MAT)
    ND.store(con, d, 2026)
    ND.store(con, d, 2026)
    n = con.execute("SELECT COUNT(*) FROM grade_distribution "
                    "WHERE course_key='MAT 103' AND term='202610'").fetchone()[0]
    assert n == 15                                # 15 harf, iki kez değil


def test_donem_bitmis_mi(con):
    ND.store(con, ND.parse(MAT), 2026)
    assert ND.term_already_graded(con, "202610") == 1
    # ⚠️ 0 "gelecekte" demek değil; yalnız "bu dönem için notumuz yok".
    assert ND.term_already_graded(con, "202710") == 0
    assert ND.term_already_graded(con, "") == 0


# ------------------------------------------------- dönem kodu bir yıl kaydı
def test_donem_kodu_BITIS_yili():
    """★★ OBS'nin kendi ucu: `yil=2026` → `202610 | 2025-2026 | Fall`."""
    assert config.donem_adi("202610") == "2025-2026 Güz"
    assert config.term_year("202610") == 2026
    assert config.term_year("saçma") is None


def test_fixture_YilAdi_ile_donem_adi_UYUSUYOR():
    """Fixture kaynaktan geldiği için bu test iki tarafı bağlıyor: kod
    değişirse kaynağın kendi etiketiyle çelişir."""
    for t in ND.parse(MAT).terms:
        assert config.donem_adi(t.term).startswith(t.year_name)
