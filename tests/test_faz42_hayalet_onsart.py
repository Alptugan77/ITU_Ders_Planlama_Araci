"""Faz 42 — hayalet önşart: katalogda olmayan dersi isteyen önşart.

Ölçüm (16.09.2026, gerçek katalog): 19365 önşart yaprağının **1509'u (%7.8)**
katalogda bulunmayan bir ders adını taşıyor — 275 farklı kod, 910 ders.
275'in 219'unun katalogda bir DİL EŞİ var (`BIL 100` yok, `BIL 100E` var) ve
kaynak metin ikisini zaten "veya" ile eşliyor; orada zarar yok.

İki zarar ölçüldü, ikisi de buradaki testlerle kilitli:
  ★★ eksik önşart listesi ALFABETİK sıralanıp 4'e kesiliyordu — FIZ 241E ve
     FIZ 272E'de gösterilen dördün dördü de katalogda yoktu, öğrencinin
     gerçekten alabileceği dersler kesilip gizleniyordu.
  ★  önşartı katalogdaki hiçbir dersle sağlanamayan 16 ders "eksik önşart:
     ELH 332" diyordu — olmayan bir dersi aramaya göndermek.
"""
import re
import sqlite3

import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import db, quality, recommend as REC, ui as UI   # noqa: E402

KATALOG = {"BIL 104E", "BIL 105E", "MAT 103E", "GEO 101E"}


# ------------------------------------------------------ sıralama ve işaret
def test_ALINABILIR_ders_ONCE_hayalet_SONRA():
    """★★ Faz 42'de bulunan HATA.

    Liste alfabetikti ve 4'e kesiliyordu. `BIL 102*` kodları alfabetik olarak
    `BIL 104E`den önce geldiği için ekranda YALNIZ katalogda olmayan dersler
    kalıyor, alınabilecekler kesiliyordu. Gerçek örnek: FIZ 241E.
    """
    eksik = {"BIL 102", "BIL 102CE", "BIL 102E", "BIL 102FE", "BIL 104E", "BIL 105E"}
    metin, hepsi_hayalet = REC._onsart_ayikla(eksik, KATALOG)
    assert not hepsi_hayalet
    # Önce: alınabilir ders EKRANA GİRİYOR mu (eski davranışta kesiliyordu).
    assert "BIL 104E" in metin, f"alınabilir ders kesilmiş: {metin}"
    assert "BIL 105E" in metin, f"alınabilir ders kesilmiş: {metin}"
    # Sonra: hayaletlerden ÖNCE geliyor mu.
    assert metin.index("BIL 104E") < metin.index("BIL 102"), \
        f"hayalet kod önce gösteriliyor: {metin}"


def test_kesilen_sayisi_YAZIYOR():
    """Kesme gizlenmiyor: kaç tane daha olduğu `+N` ile yazıyor."""
    eksik = {"BIL 104E", "BIL 105E", "MAT 103E", "GEO 101E", "ZZZ 999", "YYY 888"}
    metin, _ = REC._onsart_ayikla(eksik, KATALOG, goster=4)
    assert "+2" in metin


def test_HAYALET_kod_isaretleniyor():
    """⚠️ Hayalet kod ATILMIYOR — öğrencinin transkriptinde eski koduyla
    duruyor olabilir ve önşartı gerçekten sağlıyor olabilir. Yalnız
    işaretleniyor ki peşine düşülecek olan belli olsun."""
    metin, _ = REC._onsart_ayikla({"BIL 104E", "ESKI 101"}, KATALOG)
    assert "katalogda yok" in metin


def test_hepsi_hayaletse_AYRI_DURUM():
    """Hiçbir alternatifi katalogda yoksa bu ders buradan AÇILAMAZ."""
    metin, hepsi_hayalet = REC._onsart_ayikla({"ELH 332", "ELH 332E"}, KATALOG)
    assert hepsi_hayalet
    assert "hiçbiri katalogda yok" in metin


def test_hepsi_gercekse_UYARI_YOK():
    """Sessiz kalması gereken yerde susuyor — her listeye uyarı basmak
    uyarıyı okunmaz yapardı."""
    metin, hepsi_hayalet = REC._onsart_ayikla({"BIL 104E", "MAT 103E"}, KATALOG)
    assert not hepsi_hayalet
    assert "katalogda yok" not in metin


# ------------------------------------------- yeni kategori HER YERDE var mı
def test_yeni_kategori_KOMUT_SATIRINDA_dusmuyor():
    """★★ Faz 37'nin dersi: `KREDI_ESIGI` hesaplanıyor, arayüz gösteriyor ama
    `make recommend` çıktısı sessizce düşürüyordu. Yeni kategori eklerken
    aynı tuzağa düşmemek için etiket VE sıra listesi birlikte tutuluyor."""
    import inspect
    kaynak = inspect.getsource(REC.format_blockers)
    assert '"ONSART_KATALOGDA_YOK": "önşartı katalogda yok"' in kaynak, "etiket yok"
    sira = re.search(r"for reason in \((.*?)\):", kaynak, re.S).group(1)
    assert "ONSART_KATALOGDA_YOK" in sira, "sıralamada yok — rapordan düşer"


def test_yeni_kategori_ARAYUZDE_de_var():
    kaynak = open(UI.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
    assert 'ONSART_KATALOGDA_YOK:["önşartı katalogda yok"' in kaynak
    grup = re.search(r'\["PROGRAMA_KAPALI","ACILMAMIS","ONSART".*?\]\.forEach',
                     kaynak, re.S).group(0)
    assert "ONSART_KATALOGDA_YOK" in grup, "arayüz gruplamasında yok"


# --------------------------------------------------------- uçtan uca motor
@pytest.fixture()
def hayalet_db(tmp_path, monkeypatch):
    from itucap import config
    monkeypatch.setattr(config, "REF_DB", tmp_path / "ref.sqlite3")
    monkeypatch.setattr(config, "USER_DB", tmp_path / "user.sqlite3")
    con = db.connect(tmp_path / "ref.sqlite3", "schema.sql")
    ucon = db.connect(tmp_path / "user.sqlite3", "schema_user.sql")
    con.execute("INSERT INTO program(code,name,level) VALUES ('AAA','A','LS')")
    con.execute("INSERT INTO plan(id,program_code,plan_type,title,source)"
                " VALUES (1,'AAA','cap','x','obs')")
    # KAP 101 katalogda YOK — bilerek eklenmiyor.
    dersler = [
        ("ACK 101E", "Var", None),
        ("OLU 301E", "Önşartı kapanmış", "KAP 101 MIN DD"),
        ("KARMA 301E", "Bir gerçek bir hayalet",
         "KAP 101 MIN DD veya ACK 101E MIN DD"),
    ]
    for kod, ad, ons in dersler:
        con.execute("INSERT INTO course(code,name,credits,ects,prereq_raw)"
                    " VALUES (?,?,3,4,?)", (kod, ad, ons))
        con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,position)"
                    " VALUES (1,'REQUIRED',?,0)", (kod,))
        crn = "9" + str(abs(hash(kod)) % 1000)
        con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled)"
                    " VALUES (?,?,30,0)", (crn, kod))
        con.execute("INSERT INTO lesson_allowed_program(crn,program_code)"
                    " VALUES (?,'AAA')", (crn,))
        con.execute("INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min)"
                    " VALUES (?,1,540,630)", (crn,))
    con.commit()
    from itucap import prereq as P, student as S
    P.parse_all(con)
    sid = S.ensure_student(ucon)
    S.enroll(ucon, sid, 1, "CAP", "AAA")
    return con, ucon, sid


def test_UCTAN_UCA_olu_ders_AYRI_kategoride(hayalet_db):
    """★★ Önşartı katalogda olmayan ders, 'önşart eksik' diye değil
    'önşartı katalogda yok' diye raporlanıyor."""
    con, ucon, sid = hayalet_db
    engeller = {b.course: b for b in
                REC.cap_blockers(con, ucon, sid, 1, "AAA", allowed_programs=["AAA"])}
    assert "OLU 301E" in engeller, "ders hiç raporlanmıyor"
    assert engeller["OLU 301E"].reason == "ONSART_KATALOGDA_YOK", \
        f"yanlış kategori: {engeller['OLU 301E'].reason}"
    assert "katalogda yok" in engeller["OLU 301E"].detail


def test_UCTAN_UCA_karma_derste_ALINABILIR_once(hayalet_db):
    """Bir dalı gerçekse ders normal 'önşart eksik'; ve listede alınabilir
    ders başta geliyor."""
    con, ucon, sid = hayalet_db
    engeller = {b.course: b for b in
                REC.cap_blockers(con, ucon, sid, 1, "AAA", allowed_programs=["AAA"])}
    b = engeller.get("KARMA 301E")
    assert b and b.reason == "ONSART", f"yanlış kategori: {b and b.reason}"
    assert b.detail.index("ACK 101E") < b.detail.index("KAP 101")


# ------------------------------------------------------------- kalite kaydı
def test_kalite_kaydi_SONUCU_olcuyor():
    """⚠️ `prereq_orphan_target` yalnız kaç hayalet KOD olduğunu sayıyor (275)
    ve bu sayı çoğunlukla zararsız — 219'unun dil eşi var. Yeni kontrol
    SONUCU ölçüyor: kaç ders gerçekten açılamıyor."""
    kimlikler = [cid for cid, _, _ in quality.CHECKS]
    assert "prereq_cozulemez" in kimlikler
    con = sqlite3.connect(":memory:")
    for ad in ("course", "prereq_node"):
        pass
    # Sentetik: KAP 101 katalogda yok → OLU 301E çözülemez.
    con.executescript("""
        CREATE TABLE course(code TEXT PRIMARY KEY);
        CREATE TABLE prereq_node(id INTEGER PRIMARY KEY, course_code TEXT,
            parent_id INTEGER, node_type TEXT, req_course TEXT);
        INSERT INTO course VALUES ('ACK 101E'), ('OLU 301E');
        INSERT INTO prereq_node VALUES (1,'OLU 301E',NULL,'LEAF','KAP 101');
        INSERT INTO prereq_node VALUES (2,'ACK 101E',NULL,'LEAF','ACK 101E');
    """)
    fn = next(f for cid, _, f in quality.CHECKS if cid == "prereq_cozulemez")
    sonuc = fn(con)
    assert sonuc and "OLU 301E" in sonuc
    assert "ACK 101E" not in sonuc, "çözülebilen ders de listelenmiş"
