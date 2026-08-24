import pytest

from itucap import normalize as N


@pytest.mark.parametrize("raw,cat,term", [
    ("8.yy Seçime Bağlı Ders (MT)", "MT", 8),
    ("8.yy Elective Course (MT)", "MT", 8),
    ("7.yy Seçime Bağlı Ders(MT)", "MT", 7),          # boşluk yok
    ("5.yy Seçime Bağlı Ders(ITB)", "ITB", 5),
    ("3.yySınırlı Seçim Dersi(TB)", "TB", 3),
    ("4.yySınırlı Seçim Dersi(TM)", "TM", 4),
    ("5th Semester Elective Course (TM)", "TM", 5),
    ("English Course 1", "ENG", None),
    ("Selective", "OTHER", None),
])
def test_pool_label(raw, cat, term):
    assert N.normalize_pool_label(raw) == (cat, term)


def test_cozulemeyen_etiket_kaydediliyor():
    """★ 23.08.2026 — İKİ AYRI LİSTE, çünkü iki ayrı şey.

    'Selective' kaynakta kategori TAŞIMIYOR: düzeltilecek bir şey yok,
    kategori uydurmak veri uydurmak olurdu.
    'Seçmeli MT Ders' ise kategori taşıyor ama yerleştiremedik — BİZİM
    eksiğimiz. İkisini tek listede toplamak, düzeltilebilir olanı
    düzeltilemezlerin içinde görünmez kılıyordu."""
    N.unmatched_labels.clear()
    N.uncategorised_labels.clear()
    N.normalize_pool_label("Selective")
    assert N.uncategorised_labels == ["Selective"]
    assert N.unmatched_labels == []

    N.normalize_pool_label("Seçmeli MT Ders")           # kategori var, çözülemedi
    assert N.unmatched_labels == ["Seçmeli MT Ders"]


@pytest.mark.parametrize("raw,cat", [
    # ★ 23.08.2026'da 1400 gerçek etikette ölçülen biçimler (45 kazanç, 0 kayıp)
    ("MT Seçim Dersi", "MT"),                       # başta
    ("MT Seçim Dersi 2 (E)", "MT"),                 # başta + arap sıra + parantez
    ("Seçime Bağlı Ders MT VI", "MT"),              # roma V'in ötesi
    ("Seçime Bağlı Ders MT 1", "MT"),               # arap sıra
    ("8th Semester Elective CrseI-MT", "MT"),       # tireyle sonda
    ("6.yy Zorunlu Seçmeli Ders III (MT-Tasarım)", "MT"),   # parantezde son ek
    ("3rd Semester Elect. Course-ITB", "ITB"),
])
def test_kategori_bicimleri(raw, cat):
    assert N.normalize_pool_label(raw)[0] == cat


@pytest.mark.parametrize("raw", [
    "Intr. to Sci & Eng Comp.",          # ★ 'Eng' bir DERS ADI parçası
    "Intro. to Scientific&Eng.Comp.",
    "Selective", "Temel Meslek VI", "Stüdyo IV",
])
def test_ders_adindaki_kelime_kategori_SANILMIYOR(raw):
    """★ Harf duyarsız arasaydık 48 slotu yanlışlıkla ENG diye etiketlerdik.
    Kategori kodları kaynakta her zaman BÜYÜK HARF."""
    assert N.normalize_pool_label(raw)[0] == "OTHER"


@pytest.mark.parametrize("raw,alt,ust", [
    ("2 / 2,5 / 3", 2.0, 3.0),
    ("3", 3.0, 3.0),
    ("4,5", 4.5, 4.5),
    ("", None, None),
    ("—", None, None),
])
def test_kredi_araligi(raw, alt, ust):
    """★ Aralıktan TEK SAYI seçmiyoruz — ortalama ya da en küçüğü almak,
    kaynakta olmayan bir sayı uydurmak olurdu ve o sayı kredi tavanına,
    yarıyıl tabanına, ilerleme yüzdesine akardı."""
    assert N.parse_credit_range(raw) == (alt, ust)


@pytest.mark.parametrize("raw,out", [
    ("MAT103E", "MAT 103E"),
    ("MAT  103E", "MAT 103E"),
    ("blg 4901e", "BLG 4901E"),
    ("KIM 101EL", "KIM 101EL"),
])
def test_course_code(raw, out):
    assert N.normalize_course_code(raw) == out


def test_time_range():
    assert N.parse_time_range("11:30/13:29") == (690, 809)
    assert N.parse_time_range("--") is None
    assert N.parse_time_range("") is None


@pytest.mark.parametrize("day,idx", [
    ("Monday", 1), ("Tuesday", 2), ("Cuma", 5), ("Perşembe", 4), ("Sunday", 7),
])
def test_days(day, idx):
    assert N.day_to_index(day) == idx


def test_obs_code():
    assert N.obs_code_to_program("HTAE_LS") == "HTAE"
    assert N.obs_code_to_program("EHB_MTM_LS") == "EHB_MTM"


def test_split_cap_plan_code():
    # ★ ÇAP planları (anadal, çap) çiftine göre tanımlı
    assert N.split_cap_plan_code("TUMMUH_BLG") == ("TUMMUH", "BLG")
    assert N.split_cap_plan_code("GEO_BLG") == ("GEO", "BLG")
    assert N.split_cap_plan_code("BLG") == (None, "BLG")
