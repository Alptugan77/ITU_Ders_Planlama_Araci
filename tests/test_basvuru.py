"""Faz 12 — "başvurabilir miyim" (yapılacaklar 1.3).

Bu dosyanın çoğu testi tek bir şeyi kilitliyor: **bilinmeyen, bilinen gibi
gösterilmesin.** Modülün üç riski var ve üçü de sessizce yanlış cevap üretir:

* hesaplanamayan şartı "sağlandı" saymak,
* ÇAP planı yokken lisans planından ÇAP tahmini üretmek,
* yandal eşiğini ÇAP öğrencisine uygulamak.
"""
import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import basvuru as B
from itucap import db
from itucap import policy as POL

RULES = """
[[gno_esigi]]
anahtar = "basvuru"
ad = "ÇAP başvurusu"
program = "cap"
tur = "basvuru"
min_gno = 3.00
dogrulandi = true
kaynak = "Madde 15"

[[gno_esigi]]
anahtar = "yandal_basvuru"
ad = "Yandal başvurusu"
program = "yandal"
tur = "basvuru"
min_gno = 2.50
dogrulandi = true

[[gno_esigi]]
anahtar = "devam"
ad = "ÇAP'a devam"
program = "cap"
tur = "devam"
min_gno = 2.50
tolerans = 1
dogrulandi = true

[[gno_esigi]]
anahtar = "mezuniyet"
ad = "Mezuniyet"
program = "genel"
tur = "mezuniyet"
min_gno = 2.00
dogrulandi = true
"""


@pytest.fixture()
def rules(tmp_path):
    p = tmp_path / "kurallar.toml"
    p.write_text(RULES, encoding="utf-8")
    return p


@pytest.fixture()
def dbs(tmp_path):
    con = db.connect(tmp_path / "ref.sqlite3", "schema.sql")
    ucon = db.connect(tmp_path / "user.sqlite3", "schema_user.sql")
    con.executemany(
        "INSERT INTO course(code,name,credits,ects,prereq_raw) VALUES (?,?,?,?,?)",
        [("MAT 103E", "Mat I", 4.0, 6.0, None),
         ("FIZ 101E", "Fizik I", 3.0, 5.0, None),
         ("BLG 112E", "Prog", 3.0, 5.0, None),
         ("END 201E", "End", 3.0, 5.0, None)])
    con.executemany("INSERT INTO program(code,name,faculty,level) VALUES (?,?,?,?)",
                    [("BLG", "Bilgisayar Müh.", "BBF", "LS"),
                     ("END", "Endüstri Müh.", "ISL", "LS"),
                     ("GEO", "Geomatik Müh.", "INS", "LS")])
    # BLG'nin ÇAP planı VAR; END'in yok (lisans planı olsa bile).
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title,
                                    host_program_code,iteration)
                   VALUES (10,'BLG','cap','BLG ÇAP','GEO','2020-2021 / Güz Dönemi Sonrası')""")
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title)
                   VALUES (11,'END','lisans','END Lisans')""")
    con.executemany(
        """INSERT INTO plan_slot(plan_id,term_no,slot_kind,course_code,credits,position)
           VALUES (?,?,?,?,?,?)""",
        [(10, 1, "REQUIRED", "BLG 112E", 3.0, 1),
         (10, 1, "REQUIRED", "MAT 103E", 4.0, 2),
         (11, 1, "REQUIRED", "END 201E", 3.0, 1)])
    con.commit()
    con.row_factory = __import__('sqlite3').Row
    ucon.execute("INSERT INTO student(id,label) VALUES (1,'ben')")
    ucon.commit()
    return con, ucon


def _grade(ucon, code, grade):
    ucon.execute(
        """INSERT INTO earned_course(student_id,course_code,grade,status,source)
           VALUES (1,?,?,'PASSED','test')""", (code, grade))
    ucon.commit()


# ----------------------------------------------------- hesaplanamayan şart
def test_ranking_condition_is_unknown_not_passed(dbs, rules):
    """★ Üst %20 sıralama şartı BU ARAÇTAN bakılamaz.

    Sessizce atlanırsa araç, karşılanmamış olabilecek bir şartı karşılanmış
    gösterir — bu projedeki en pahalı hata türü."""
    con, ucon = dbs
    _grade(ucon, "MAT 103E", "AA")
    s = B.survey(con, ucon, 1, "cap", rules_path=rules)
    rank = [c for c in s.checks if c.key == "siralama"]
    assert rank and rank[0].ok is None
    assert rank[0] in s.unknown
    assert not rank[0].blocking          # bilinmeyen, ENGEL değil


def test_eligible_does_not_mean_all_conditions_met(dbs, rules, monkeypatch):
    """`eligible` yalnız "bilinen şart düşmüyor" demek.

    Bakılamayan şart varsa arayüz bunu ayrıca söylemek zorunda; test bu iki
    kavramın ayrı kalmasını kilitliyor."""
    con, ucon = dbs
    _grade(ucon, "MAT 103E", "AA")       # GNO 4.00 → eşik geçilir
    monkeypatch.setattr(POL, "earned_credits", lambda *a, **k: 60.0)  # pencere içi
    s = B.survey(con, ucon, 1, "cap", rules_path=rules)
    assert s.eligible                    # bilinen şartların hepsi tamam
    assert s.unknown                     # ama hâlâ bakılamayan şart var


# ----------------------------------------------------------- eşik kapsamı
def test_yandal_threshold_is_not_applied_to_cap(dbs, rules):
    """Yandal eşiği (2.50) ÇAP taramasında görünmemeli — ayrı maddeler."""
    con, ucon = dbs
    _grade(ucon, "MAT 103E", "BB")
    cap = B.survey(con, ucon, 1, "cap", rules_path=rules)
    yan = B.survey(con, ucon, 1, "yandal", rules_path=rules)
    assert "yandal_basvuru" not in {c.key for c in cap.checks}
    assert "basvuru" not in {c.key for c in yan.checks}
    assert "yandal_basvuru" in {c.key for c in yan.checks}


def test_only_application_thresholds_are_checked(dbs, rules):
    """Devam ve mezuniyet eşikleri BAŞVURU ekranına girmez.

    Mezuniyet eşiğinde 'kaldın' demek bugünün sorusu değil; başvuru
    ekranında göstermek yanlış bir aciliyet üretirdi."""
    con, ucon = dbs
    _grade(ucon, "MAT 103E", "DD")
    s = B.survey(con, ucon, 1, "cap", rules_path=rules)
    keys = {c.key for c in s.checks}
    assert "devam" not in keys and "mezuniyet" not in keys


def test_failing_gpa_blocks(dbs, rules):
    con, ucon = dbs
    _grade(ucon, "MAT 103E", "DD")       # GNO 1.00
    s = B.survey(con, ucon, 1, "cap", rules_path=rules)
    assert not s.eligible
    assert any(c.key == "basvuru" and c.ok is False for c in s.checks)


# -------------------------------------------------------- kredi penceresi
@pytest.mark.parametrize("credits,ok", [
    (29.0, False),        # alt sınırın altında
    (30.0, True),         # tam alt sınır — dahil
    (94.0, True),
    (95.0, False),        # üst sınırın üstünde (94.99)
])
def test_cap_credit_window_is_a_window_not_a_floor(dbs, rules, credits, ok,
                                                   monkeypatch):
    """ÇAP'ta kredi bir PENCERE: çok az da olmaz, çok fazla da.

    Yalnız alt sınır kontrol edilseydi 8. dönemdeki bir öğrenciye
    'başvurabilirsin' denirdi — yönerge en geç 5. döneme izin veriyor."""
    con, ucon = dbs
    monkeypatch.setattr(POL, "earned_credits", lambda *a, **k: credits)
    s = B.survey(con, ucon, 1, "cap", rules_path=rules)
    win = [c for c in s.checks if c.key == "kredi_penceresi"][0]
    assert win.ok is ok


def test_yandal_credit_check_has_no_upper_bound(dbs, rules, monkeypatch):
    con, ucon = dbs
    monkeypatch.setattr(POL, "earned_credits", lambda *a, **k: 120.0)
    s = B.survey(con, ucon, 1, "yandal", rules_path=rules)
    assert [c for c in s.checks if c.key == "kredi_penceresi"][0].ok is True


# --------------------------------------------------------- plan eksikliği
def test_program_without_a_cap_plan_is_not_estimated(dbs, rules):
    """★ END'in ÇAP planı yok, lisans planı var.

    Lisans planından "ÇAP'ta şu kadar kalır" demek sayıyı iki katından fazla
    şişirirdi (BLG'de 59.5'e karşı ~140 kredi). O yüzden END seçeneklere
    değil, `missing` listesine girer."""
    con, ucon = dbs
    s = B.survey(con, ucon, 1, "cap", rules_path=rules)
    assert "BLG" in {o.program_code for o in s.options}
    assert "END" in {o.program_code for o in s.missing}
    assert "END" not in {o.program_code for o in s.options}
    assert all(o.missing_plan for o in s.missing)


def test_passed_courses_reduce_remaining_work(dbs, rules):
    con, ucon = dbs
    _grade(ucon, "BLG 112E", "AA")
    s = B.survey(con, ucon, 1, "cap", rules_path=rules)
    blg = [o for o in s.options if o.program_code == "BLG"][0]
    assert "BLG 112E" in blg.already
    assert blg.already_count == 1
    assert not hasattr(blg, "credits_left"), "kredi iddiası geri gelmiş"


def test_enrolled_programs_are_excluded(dbs, rules):
    con, ucon = dbs
    s = B.survey(con, ucon, 1, "cap", exclude={"BLG"}, rules_path=rules)
    assert "BLG" not in {o.program_code for o in s.options}


def test_options_are_sorted_by_courses_already_counting(dbs, rules):
    """Sağlam ölçüt tek: kaç dersin birebir tutuyor. Kredi değil."""
    con, ucon = dbs
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title,
                                    host_program_code)
                   VALUES (12,'END','cap','END ÇAP','GEO')""")
    con.execute("""INSERT INTO plan_slot(plan_id,term_no,slot_kind,course_code,
                   credits,position) VALUES (12,1,'REQUIRED','FIZ 101E',3.0,1)""")
    con.commit()
    _grade(ucon, "BLG 112E", "AA")
    s = B.survey(con, ucon, 1, "cap", rules_path=rules)
    counts = [o.already_count for o in s.options]
    assert counts == sorted(counts, reverse=True)


# ------------------------------------------------------------------ biçim
def test_json_keeps_the_three_valued_mark(dbs, rules):
    """JSON'da da ok=None korunmalı; True/False'a düşürülürse arayüz
    üç durumlu işareti çizemez."""
    con, ucon = dbs
    _grade(ucon, "MAT 103E", "AA")
    j = B.to_json(B.survey(con, ucon, 1, "cap", rules_path=rules))
    assert any(c["ok"] is None for c in j["checks"])
    assert j["unknownCount"] >= 1
    assert j["missingCount"] == len(j["missing"])
    # ⚠️ Kredi alanı geri gelmemeli — duramayacağımız sayı gösterilmiyor.
    for o in j["options"]:
        assert not any("redit" in k or "Left" in k for k in o), o


def test_describe_runs_without_options(dbs, rules):
    con, ucon = dbs
    text = B.describe(B.survey(con, ucon, 1, "cap", exclude={"BLG"},
                               rules_path=rules))
    assert "BAŞVURUSU" in text


# ================================================ anadal kapsamı (22.08.2026)
#
# Kullanıcı: "aşağıda sadece öğrencinin anadalı ile ilişkili programlar olsun".
# Haklıydı: ÇAP planları (anadal, hedef) ÇİFTİNE göre tanımlı — `INS_MAK`
# planı İnşaat öğrencisinin planı, Harita öğrencisi ona başvuramaz.

def test_plans_hosted_by_another_major_are_filtered_out(dbs, rules):
    con, ucon = dbs
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title,
                                    host_program_code)
                   VALUES (13,'END','cap','END ÇAP','MAK')""")
    con.commit()
    s = B.survey(con, ucon, 1, "cap", anadal="GEO", rules_path=rules)
    assert "BLG" in {o.program_code for o in s.options}     # host GEO
    assert "END" not in {o.program_code for o in s.options}  # host MAK
    assert s.other_host == 1


def test_filtered_count_is_reported(dbs, rules):
    """★ Eleyen kural kendini göstermek zorunda.

    Sessizce süzülen bir liste 'İTÜ'de bu kadar ÇAP varmış' diye yanlış bir
    izlenim bırakırdı."""
    con, ucon = dbs
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title,
                                    host_program_code)
                   VALUES (13,'END','cap','END ÇAP','MAK')""")
    con.commit()
    j = B.to_json(B.survey(con, ucon, 1, "cap", anadal="GEO", rules_path=rules))
    assert j["otherHost"] == 1
    assert j["anadal"] == "GEO"


def test_no_anadal_means_no_filtering(dbs, rules):
    """Anadal verilmezse süzme yapılmaz — kütüphane olarak da kullanılabilsin."""
    con, ucon = dbs
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title,
                                    host_program_code)
                   VALUES (13,'END','cap','END ÇAP','MAK')""")
    con.commit()
    s = B.survey(con, ucon, 1, "cap", rules_path=rules)
    assert {"BLG", "END"} <= {o.program_code for o in s.options}
    assert s.other_host == 0


@pytest.mark.parametrize("host,anadal,name,ok", [
    ("GEO", "GEO", "Geomatik Mühendisliği", True),         # birebir
    ("INS", "GEO", "Geomatik Mühendisliği", False),        # başka bölüm
    ("TUMMUH", "HTAE", "Harita Mühendisliği (İngilizce)", True),
    ("TUMMUH", "MIM", "Mimarlık Lisans", False),           # mühendislik değil
    ("MIM_FK", "MIM", "Mimarlık Lisans", True),
    ("", "GEO", "Geomatik Mühendisliği", False),           # host bilinmiyor
])
def test_host_matching(host, anadal, name, ok):
    """★ 'TUMMUH' = tüm mühendislik; kimin girdiği program ADINDAN çıkıyor.

    ⚠️ Türkçe büyük harf tuzağı: `"Mühendisliği".upper()` Python'da
    **"MÜHENDISLIĞI"** verir (noktalı i → noktasız I). İlk yazımda
    "MÜHENDİSL" arayan kontrol hiçbir programı tutmadı. `strip_accents` +
    `lower()` iki yönde de güvenli."""
    assert B.host_matches(host, anadal, name) is ok


def test_umbrella_matching_survives_turkish_casing():
    """Aynı tuzağın regresyon kilidi — büyük/küçük harf yazımı ne olursa olsun."""
    for name in ("Harita Mühendisliği", "HARİTA MÜHENDİSLİĞİ",
                 "harita mühendisliği", "Harita MÜHENDISLIĞI"):
        assert B.host_matches("TUMMUH", "HTAE", name), name


# ---------------------------------------------------------- iterasyon seçimi
def test_open_ended_iteration_wins(dbs, rules):
    """★ Aynı ÇAP çiftinin birden çok yıl aralığı var; yürürlükte olan
    'Sonrası' ile bitendir. `id` sırası OBS'nin iç sayacı — kronolojik değil,
    ona güvenmek eski müfredatı gösterirdi."""
    con, ucon = dbs
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title,
                                    host_program_code,iteration)
                   VALUES (99,'BLG','cap','eski','GEO',
                           '2013-2014 / Güz Dönemi Öncesi')""")
    con.commit()
    s = B.survey(con, ucon, 1, "cap", anadal="GEO", rules_path=rules)
    blg = [o for o in s.options if o.program_code == "BLG"][0]
    assert blg.plan_id == 10                      # 'Sonrası' olan, id 99 değil
    assert "Sonras" in blg.plan_iteration


def test_latest_year_wins_when_no_open_ended_iteration(dbs, rules):
    con, ucon = dbs
    con.execute("DELETE FROM plan WHERE id=10")
    con.executemany("""INSERT INTO plan(id,program_code,plan_type,title,
                                        host_program_code,iteration)
                       VALUES (?,?,?,?,?,?)""",
                    [(98, "BLG", "cap", "a", "GEO", "2013-2014 / Güz Arası"),
                     (97, "BLG", "cap", "b", "GEO", "2019-2020 / Güz Arası")])
    con.commit()
    s = B.survey(con, ucon, 1, "cap", anadal="GEO", rules_path=rules)
    blg = [o for o in s.options if o.program_code == "BLG"][0]
    assert blg.plan_id == 97                      # 2019 > 2013


def test_declared_equivalences_do_not_inflate_other_programs(dbs, rules):
    """★ 22.08.2026 hata raporunun kökü.

    Kullanıcının `denklikler.toml`'da beyan ettiği denklik KENDİ ÇAP'ı için
    geçerli (FYK kararı o çifte özel). Her programın planına uygulanınca
    'tamamlandı' şişiyor ve başvurmadığı bir programda saydırılmamış bir ders
    saydırılmış görünüyordu. Burada yalnız birebir kod eşleşmesi sayılır."""
    con, ucon = dbs
    con.execute("""INSERT INTO equivalence(id,target_course,applies_to_cap,
                                           confidence,note_raw)
                   VALUES (1,'BLG 112E',1,'user_declared','beyan')""")
    con.execute("""INSERT INTO equivalence_source(equivalence_id,course_code,
                                                  min_grade)
                   VALUES (1,'MAT 103E','DD')""")
    con.commit()
    _grade(ucon, "MAT 103E", "AA")               # BLG 112E'yi KARŞILADIĞI beyan
    s = B.survey(con, ucon, 1, "cap", anadal="GEO", rules_path=rules)
    blg = [o for o in s.options if o.program_code == "BLG"][0]
    # MAT 103E planda BİREBİR var ve geçilmiş → sayılır, doğru.
    # BLG 112E yalnız BEYAN edilen denklikle "tamamlanmış" olurdu → sayılmaz.
    assert blg.already == ["MAT 103E"]
    assert "BLG 112E" not in blg.already, "beyan edilen denklik sayılmamalı"


# ============================ yandal planı yok (OBS gerçeği, 22.08.2026)
#
# OBS `PlanTipiKodu=yandal` isteğini KABUL ediyor ve "Akademik programa bağlı
# ders planı bulunmamaktadır" diyor. 128 programın hiçbirinde yandal planı yok.
# Uç çalışıyor, veri yok. Bu bir hata değil, veri gerçeği.

def test_missing_plan_type_is_reported_separately(dbs, rules):
    """★ "henüz çekilmedi" ile "yayınlanmamış" AYRI şeyler.

    Birincisinde kullanıcıya `make all-plans` demek doğru; ikincisinde
    YANLIŞ — çalıştırsa da bir şey gelmez, boşuna uğraşır. Yanlış yönlendirme
    "bilinmeyeni bilinen gibi göstermek" kadar zararlı."""
    con, ucon = dbs
    cap = B.survey(con, ucon, 1, "cap", rules_path=rules)
    yan = B.survey(con, ucon, 1, "yandal", rules_path=rules)
    assert cap.plan_type_available is True      # fixture'da cap planı var
    assert yan.plan_type_available is False     # yandal planı hiç yok


def test_json_carries_plan_type_availability(dbs, rules):
    con, ucon = dbs
    j = B.to_json(B.survey(con, ucon, 1, "yandal", rules_path=rules))
    assert j["planTypeAvailable"] is False


def test_describe_does_not_promise_a_useless_command(dbs, rules):
    """`make all-plans` önerisi, çekilecek veri varken anlamlı."""
    con, ucon = dbs
    yan = B.describe(B.survey(con, ucon, 1, "yandal", rules_path=rules))
    assert "all-plans" in yan and "DEĞİŞTİRMEZ" in yan
    cap = B.describe(B.survey(con, ucon, 1, "cap", exclude={"BLG"},
                              rules_path=rules))
    assert "DEĞİŞTİRMEZ" not in cap


def test_thresholds_still_apply_without_plans(dbs, rules):
    """★ Plan yokluğu ŞARTLARI geçersiz kılmaz.

    Yandal başvuru eşiği yönergede duruyor; planı yayınlanmamış olması
    "bu şart yok" demek değil. Şartları da gizleseydik, öğrenci
    başvurabileceğini sanıp GNO şartını hiç görmezdi."""
    con, ucon = dbs
    _grade(ucon, "MAT 103E", "DD")
    yan = B.survey(con, ucon, 1, "yandal", rules_path=rules)
    assert not yan.plan_type_available
    assert any(c.key == "yandal_basvuru" for c in yan.checks)
