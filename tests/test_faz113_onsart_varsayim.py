"""Faz 113 — yol haritasının önşart varsayımları.

Kullanıcı (28.09.2026): *"önşart varsayımları da yanlış çalışıyor bakar
mısın onlara"*. Gerçek katalogda (BLGE, 5. yarıyıl, transkriptli):

* BLG 4901E kartı "önşart varsayıldı: FIZ 101L, FIZ 102L" diyordu. Öğrenci
  FIZ 101EL/102EL'i geçmişti; o dallar zaten sağlanıyordu. Asıl varsayılan
  MAT 210 (2024 planında Mühendislik Matematiği yok) görünmüyordu, çünkü
  kart ilk ikisini gösteriyor ve liste ağaçtaki BÜTÜN dış dersleri yazıyordu.
* "Veya" dalları ayrı ayrı yazılıyordu: BBF 304E için MAT 271, MAT 271E,
  ECN 301E, YZV 231, YZV 231E — beşi birden varsayılmış gibi.
* Laboratuvar kodunun dil eşi bulunmuyordu ('FIZ 101L' için 'FIZ 101LE'
  aranıyordu). Faz 98 kuralı ("plandaki dersin dil eşi dış değil") lab
  derslerinde işlemiyordu: FIZ 101EL henüz alınmamışken "FIZ 101L veya
  FIZ 101EL" isteyen ders, lab dersinden ÖNCE yerleşebiliyordu.
"""
from itucap import rules as R, yolharitasi as YH
from test_faz57_yol_haritasi import _katalog, _kur, _yer

LAB = "FIZ 101L MIN DDveya FIZ 101EL MIN DD"                # OBS biçimi


def test_LAB_DIL_ESI(tmp_path):
    con = _katalog(tmp_path / "a", [("FIZ 101L", 1, None), ("FIZ 101EL", 1, None),
                                    ("KIM 101L", 1, None), ("KIM 101EL", 2, None),
                                    ("MAT 210", 4, None), ("MAT 210E", 4, None)], plan=[])
    assert R.dil_esi(con, "FIZ 101L") == "FIZ 101EL" and R.dil_esi(con, "FIZ 101EL") == "FIZ 101L"
    assert R.dil_esi(con, "KIM 101L") is None                   # kredi farklı: eş değil
    assert R.dil_esi(con, "MAT 210") == "MAT 210E"              # eski davranış aynen


def test_LAB_ONSARTI_dis_sayilmiyor_sira_korunuyor(tmp_path):
    """(Bitirme dersinin kredi eşiği karışmasın diye BLG 333E.) Plan dersi lab
    dersinden ÖNCEKİ döneme koysa bile (Türkçe
    FIZ 101L dış sayılıp geçilmiş varsayılsaydı önce yerleşirdi)."""
    con = _katalog(tmp_path / "b", [("FIZ 101L", 1, None), ("FIZ 101EL", 1, None),
                                    ("BLG 333E", 3, LAB)],
                   plan=[("BLG 333E", 5), ("FIZ 101EL", 6)])
    h = _kur(con)
    yer = _yer(h)
    assert yer["FIZ 101EL"] < yer["BLG 333E"], yer
    dis = {i["course"]: i["externalPrereq"] for t in h["terms"] for i in t["items"]}
    assert dis["BLG 333E"] == []


def test_VARSAYIM_yalniz_eksik_dal(tmp_path):
    """Lab dalı geçilmiş İngilizce kodla sağlanıyor; varsayılan yalnız MAT 210."""
    con = _katalog(tmp_path / "c", [("FIZ 101L", 1, None), ("FIZ 101EL", 1, None),
                                    ("MAT 210", 4, None), ("MAT 210E", 4, None),
                                    ("BLG 333E", 3, f"({LAB})ve (MAT 210 MIN DDveya MAT 210E MIN DD)")],
                   plan=[("BLG 333E", 7)])
    h = _kur(con, {"FIZ 101EL": "BB"})
    dis = {i["course"]: i["externalPrereq"] for t in h["terms"] for i in t["items"]}
    assert dis["BLG 333E"] == ["MAT 210(E)"], dis
    assert any("(MAT 210(E))" in a for a in h["assumptions"]), h["assumptions"]


def test_VEYA_dallari_tek_grup(tmp_path):
    con = _katalog(tmp_path / "d", [("MAT 271", 3, None), ("MAT 271E", 3, None),
                                    ("ECN 301E", 3, None), ("YZV 231", 3, None), ("YZV 231E", 3, None),
                                    ("BBF 304E", 3, "(MAT 271 MIN DDveya MAT 271E MIN DD)veya "
                                                    "ECN 301E MIN DDveya (YZV 231 MIN DDveya YZV 231E MIN DD)")],
                   plan=[("BBF 304E", 6)])
    dis = {i["course"]: i["externalPrereq"] for t in _kur(con)["terms"] for i in t["items"]}
    assert dis["BBF 304E"] == ["ECN 301E veya MAT 271(E) veya YZV 231(E)"], dis


def test_DIS_GRUPLARI_birim():
    from itucap import prereq as P
    agac = P.parse("(AAA 101 MIN DDveya BBB 102 MIN DD)ve CCC 103 MIN DDve (DDD 104 MIN DDveya EEE 105 MIN DD)").tree
    # C sağlanmış; A/B dış, D dış ama E plan dersi (dış değil) → D tek başına grup
    g = YH.dis_gruplari(None, agac, {"CCC 103": "AA"}, {"AAA 101", "BBB 102", "DDD 104"})
    assert g == ["AAA 101 veya BBB 102", "DDD 104"], g
