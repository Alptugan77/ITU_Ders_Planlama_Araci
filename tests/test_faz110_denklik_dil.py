"""Faz 110 — resmî denklikler İngilizce kodlarda da; ayrıştırıcıda ek hatası.

`make all-plans` öncesi dikkatli denetim (kullanıcı 27.09.2026):

1. OBS DersPlanDenklikleri kodları DİLDEN BAĞIMSIZ, taban biçimde yazıyor
   ("BBF 203 ≡ BLG 252"). Motor birebir eşleştirdiği için İngilizce
   programdaki öğrencide (BBF 203E) hiçbir resmî denklik tetiklenmiyordu.
   Kural: dil korunur — İngilizce kaynak İngilizce hedefi kazandırır.
   Gerçek katalogda plana sadık öğrencide engelli ders 104 → 92.
2. İsim büyük harfli kısaltmayla başlayınca ilk harfi koda yapışıyordu
   ("EHB 101EHM Giriş" → EHB 101E, "SBP 126CBS" → SBP 126C). 3183
   satırda 11 hatalı; L laboratuvar eki korunuyor.
"""
import pytest

from itucap import db, rules as R
from itucap.sources import obs_equivalence as E


# ------------------------------------------------------------ ayrıştırıcı
@pytest.mark.parametrize("metin,katalog,beklenen", [
    ("EHB 101EHM Giriş ve Müh. Etiği", {"EHB 101", "EHB 101E"}, "EHB 101"),
    ("DFH 490E-Seyir Sistemleri", {"DFH 490"}, "DFH 490"),
    ("SBP 126CBS ve Planlama", {"SBP 126"}, "SBP 126"),
    ("PEM 251CBSe giriş", set(), "PEM 251"),
    ("MET 435PÇT ve Prje.", {"MET 435"}, "MET 435"),
    ("ING 112AAkademik Yazının Temelleri", {"ING 112A"}, "ING 112A"),   # gerçek ek
    ("FIZ 113LMekanik Laboratuvarı", set(), "FIZ 113L"),                  # lab eki korunur
    ("ING 101R English I (Remedial)", set(), "ING 101R"),                  # boşluklu ek
    ("BLG 202E Something", set(), "BLG 202E"),
    ("BLG 202Numerical Methods", set(), "BLG 202"),
])
def test_EK_AYRISTIRMA(metin, katalog, beklenen):
    assert E._lead_code(metin, katalog) == beklenen


# ------------------------------------------------------------ dil
@pytest.mark.parametrize("kod,en", [
    ("BLG 252", "BLG 252E"), ("BLG 252E", "BLG 252E"), ("FIZ 101L", "FIZ 101EL"),
    ("FIZ 101EL", "FIZ 101EL"), ("bozuk", "bozuk")])
def test_INGILIZCE_KOD(kod, en):
    assert R.ingilizce_kod(kod) == en


RESMI = [R.Equivalence(1, "BLG 252", (("BBF 203", "DD"),), "official", True)]


def test_DIL_KORUNUR():
    x, via = R.expand_with_equivalences({"BBF 203E": "BB"}, RESMI)
    assert x.get("BLG 252E") == "BB" and "BLG 252" not in x and via["BLG 252E"] == 1
    x, _ = R.expand_with_equivalences({"BBF 203": "CC"}, RESMI)
    assert x.get("BLG 252") == "CC" and "BLG 252E" not in x


def test_BEYAN_yazildigi_gibi():
    beyan = [R.Equivalence(9, "BLG 252", (("BBF 203", "DD"),), "user_declared", True)]
    x, _ = R.expand_with_equivalences({"BBF 203E": "BB"}, beyan)
    assert "BLG 252E" not in x and "BLG 252" not in x


def test_KARISIK_DILLI_cok_kaynak_tetiklenmez():
    eq = [R.Equivalence(2, "KIM 206", (("KIM 211", "DD"), ("KIM 212", "DD")), "official", True)]
    assert "KIM 206" not in R.expand_with_equivalences({"KIM 211E": "AA", "KIM 212": "AA"}, eq)[0]
    assert R.expand_with_equivalences({"KIM 211E": "AA", "KIM 212E": "BB"}, eq)[0]["KIM 206E"] == "BB"


def test_ANADAL_YUVASI_dil_kurali(tmp_path):
    """İngilizce anadal yuvası (BLG 252E): İngilizce BBF 203E denklikle doldurur,
    Türkçe BBF 203 doldurmaz (Faz 92 ilkesi)."""
    con = db.connect(tmp_path / "r.sqlite3", "schema.sql")
    con.execute("INSERT INTO plan(id,program_code,plan_type,title,source) VALUES (1,'BLGE','lisans','a','obs')")
    cur = con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,position) VALUES (1,'REQUIRED','BLG 252E',0)")
    con.commit()
    sid = cur.lastrowid
    assert R.slot_satisfied(con, sid, {"BBF 203E": "BB"}, RESMI).satisfied
    assert not R.slot_satisfied(con, sid, {"BBF 203": "BB"}, RESMI).satisfied
    assert not R.slot_satisfied(con, sid, {"BBF 203E": "BB"}, None).satisfied


# ------------------------------------------------------------ en iyi not
IKI_YOL = [R.Equivalence(3, "DFH 321", (("DFH 474", "DD"),), "official", True),
           R.Equivalence(4, "DFH 321", (("GUV 491", "DD"),), "official", True)]


@pytest.mark.parametrize("liste", [IKI_YOL, IKI_YOL[::-1]])
def test_EN_IYI_NOT_sira_bagimsiz(liste):
    """Hedefe iki yoldan varılıyor: iyisi kalır, liste sırası fark etmez
    (gerçek listede 300 transkriptin 5'inde not sıraya göre değişiyordu)."""
    x, via = R.expand_with_equivalences({"DFH 474": "CC", "GUV 491": "CB"}, liste)
    assert x["DFH 321"] == "CB" and via["DFH 321"] == 4


def test_KENDISI_FF_denk_dersi_gecmis():
    """Hedefi kendisi FF, denğini BB ile geçmiş: önşart/yuva için BB. Ham not
    daha iyiyse ham not kalır ve 'denklikle' denmez."""
    x, via = R.expand_with_equivalences({"BLG 252": "FF", "BBF 203": "BB"}, RESMI)
    assert x["BLG 252"] == "BB" and via["BLG 252"] == 1
    x, via = R.expand_with_equivalences({"BLG 252": "BA", "BBF 203": "CC"}, RESMI)
    assert x["BLG 252"] == "BA" and "BLG 252" not in via
    x, via = R.expand_with_equivalences({"BLG 252": "CC", "BBF 203": "CC"}, RESMI)
    assert "BLG 252" not in via                              # eşitlikte ham not


def test_YUKSELME_zincirde_yayilir():
    zincir = [R.Equivalence(5, "B 102", (("A 101", "DD"),), "official", True),
              R.Equivalence(6, "C 103", (("B 102", "DD"),), "official", True)]
    x, _ = R.expand_with_equivalences({"A 101": "AA", "B 102": "DD"}, zincir[::-1])
    assert x["B 102"] == "AA" and x["C 103"] == "AA"


def test_ONBELLEK_sonucu_kirletilemez():
    x, via = R.expand_with_equivalences({"BBF 203": "BB"}, RESMI)
    x["BLG 252"] = "FF"; via.clear()
    y, via2 = R.expand_with_equivalences({"BBF 203": "BB"}, RESMI)
    assert y["BLG 252"] == "BB" and via2 == {"BLG 252": 1}


def test_ONBELLEK_liste_degisince_yenilenir():
    liste = list(RESMI)
    assert "KIM 206" not in R.expand_with_equivalences({"KIM 211": "AA"}, liste)[0]
    liste.append(R.Equivalence(7, "KIM 206", (("KIM 211", "DD"),), "official", True))
    assert R.expand_with_equivalences({"KIM 211": "AA"}, liste)[0]["KIM 206"] == "AA"


def test_YUKLEYICI_tek_sorgu(tmp_path):
    """Tek JOIN'li yükleyici: kaynaklar kod sırasıyla, kaynaksız denklik yok,
    ÇAP'a uygulanmayan ve beyan süzgeçleri eskisi gibi."""
    con = db.connect(tmp_path / "r.sqlite3", "schema.sql")
    con.executemany("INSERT INTO equivalence(id,target_course,applies_to_cap,confidence) VALUES (?,?,?,?)",
                    [(1, "KIM 206", 1, "official"), (2, "BOS 100", 1, "official"),
                     (3, "CAP 100", 0, "official"), (4, "BEY 100", 1, "user_declared")])
    con.executemany("INSERT INTO equivalence_source(equivalence_id,course_code,min_grade) VALUES (?,?,?)",
                    [(1, "KIM 212", "CC"), (1, "KIM 211", None), (3, "X 100", "DD"), (4, "Y 100", "DD")])
    con.commit()
    x = R.load_equivalences(con)
    assert [(e.id, e.target, e.sources) for e in x] == [
        (1, "KIM 206", (("KIM 211", "DD"), ("KIM 212", "CC")))]
    assert [e.id for e in R.load_equivalences(con, include_cap=False)] == [1, 3]
    assert [e.id for e in R.load_equivalences(con, ucon=con)] == [1, R.BEYAN_ID_OFSET + 4]


def test_KALITE_yetim_denklik_iki_yazimla(tmp_path):
    """Kum havuzunda "1146 denklikte hedef ders bulunamadı" uyarısının 1126'sı
    yalnız taban yazımdandı (katalogda BLG 252E var, sayfa BLG 252 diyor)."""
    from itucap import quality as Q
    con = db.connect(tmp_path / "r.sqlite3", "schema.sql")
    con.executemany("INSERT INTO course(code,name) VALUES (?,?)", [("BLG 252E", "OOP"), ("MAT 101", "M")])
    con.executemany("INSERT INTO equivalence(target_course,confidence) VALUES (?,?)",
                    [("BLG 252", "official"), ("MAT 101", "official"), ("ESK 100", "official"),
                     ("ESK 100", "official"), ("BLG 252", "user_declared")])
    con.commit()
    bulgu = {f.check_id: f for f in Q.run(con)}["orphan_equivalence"]
    # resmî BLG 252 → BLG 252E var; beyan yazıldığı gibi (Türkçe BLG 252 yok)
    assert "3 denklikte" in bulgu.detail and bulgu.detail.endswith("ESK 100, BLG 252")
