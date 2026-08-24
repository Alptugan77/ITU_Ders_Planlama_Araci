"""Faz 21 — ÇAP ve yandal AYNI ANDA (yapılacaklar 1.6).

Kullanıcı 23.08.2026: *"yandal ve çap aynı anda alınabiliyor"*. Araç bugüne
kadar **tek** ikinci program varsayıyordu.

★ Bu fazın asıl riski ders sayısı değil, **KURAL KARIŞMASI**. ÇAP'ın kendi
mezuniyet ortalaması (Yönerge Madde 18) ile yandalın şartları (Madde 22) ayrı
maddelerden geliyor. Tek "ikinci program" kutusuna sıkıştırılsaydı biri
öbürünün kuralıyla değerlendirilirdi — ve bu ekranda **doğru görünürdü**.
Bu dosyadaki testlerin çoğu tam olarak o karışmayı kolluyor.
"""
import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import config, db, plans as PL, prereq as P, student as S, ui as UI


@pytest.fixture()
def dbs(tmp_path, monkeypatch):
    """Anadal (HTAE) + ÇAP planı (BLG) + yandal planı (ECN_YD)."""
    monkeypatch.setattr(config, "REF_DB", tmp_path / "ref.sqlite3")
    monkeypatch.setattr(config, "USER_DB", tmp_path / "user.sqlite3")
    con = db.connect(tmp_path / "ref.sqlite3", "schema.sql")
    ucon = db.connect(tmp_path / "user.sqlite3", "schema_user.sql")
    con.executemany(
        "INSERT INTO course(code,name,ects,credits,prereq_raw) VALUES (?,?,?,?,?)",
        [("GEO 303E", "Kadastro", 3.0, 3.0, None),
         ("BLG 212E", "Mikroişlemci", 7.0, 3.0, None),
         ("BLG 351E", "Lab", 2.0, 2.0, "BLG 212E MIN DD"),
         ("ECN 201", "İktisada Giriş", 4.0, 3.0, None),
         ("ECN 301", "Mikroiktisat", 4.0, 3.0, "ECN 201 MIN DD")])
    con.execute("INSERT INTO program(code,name,level) VALUES ('BLG','Bilgisayar','LS')")
    con.execute("INSERT INTO program(code,name,level) VALUES ('ECN_YD','Economics','YD')")
    con.execute("INSERT INTO plan(id,program_code,plan_type,title,source) "
                "VALUES (10,'HTAE','lisans','anadal','obs')")
    con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,credits,ects,
                                         position,term_no)
                   VALUES (10,'REQUIRED','GEO 303E',3.0,3.0,0,5)""")
    con.execute("INSERT INTO plan(id,program_code,plan_type,title,source,is_term_based) "
                "VALUES (20,'BLG','cap','ÇAP planı','obs',0)")
    for i, c in enumerate(["BLG 212E", "BLG 351E"]):
        con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,credits,ects,
                                             position) VALUES (20,'REQUIRED',?,3.0,5.0,?)""",
                    (c, i))
    con.execute("INSERT INTO plan(id,program_code,plan_type,title,source,is_term_based) "
                "VALUES (30,'ECN_YD','yandal','Yandal planı','obs',0)")
    for i, c in enumerate(["ECN 201", "ECN 301"]):
        con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,credits,ects,
                                             position) VALUES (30,'REQUIRED',?,3.0,4.0,?)""",
                    (c, i))
    for crn, code, prog in [("100", "BLG 212E", "BLG"), ("101", "BLG 351E", "BLG"),
                            ("200", "ECN 201", "HTAE"), ("201", "ECN 301", "HTAE"),
                            ("300", "GEO 303E", "HTAE")]:
        con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled,building) "
                    "VALUES (?,?,50,0,'INB')", (crn, code))
        con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES (?,?)",
                    (crn, prog))
        con.execute("""INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min,building)
                       VALUES (?,?,?,?,'INB')""", (crn, int(crn[0]), 510, 630))
    con.commit()
    P.parse_all(con)
    sid = S.ensure_student(ucon)
    return con, ucon, sid


IKISI = dict(anadal_program="HTAE", cap_program="BLG", yandal_program="ECN_YD",
             second_kind="ikisi", program_codes=["HTAE", "BLG"])


def _collect(dbs, **kw):
    con, ucon, sid = dbs
    s = config.Settings(**{**IKISI, **kw})
    return UI.collect(con, ucon, sid, s, 10, None,
                      seconds=PL.resolve_seconds(con, s))


# --------------------------------------------------------------- ayarlar
def test_ikisi_secimi_iki_tur_veriyor():
    s = config.Settings(**IKISI)
    assert s.second_kinds == ("cap", "yandal")
    assert [x[0] for x in s.seconds] == ["cap", "yandal"]


def test_tekil_secimler_bozulmadi():
    for kind, beklenen in (("cap", ("cap",)), ("yandal", ("yandal",)), ("yok", ())):
        assert config.Settings(second_kind=kind).second_kinds == beklenen


def test_kodu_olmayan_tur_atlaniyor():
    """★ 'ikisi' seçilip yandal kodu girilmemişse ortada yandal YOK.

    Boş kodla devam etmek, olmayan bir programın planını arayıp
    'plan bulunamadı' demek olurdu."""
    s = config.Settings(**{**IKISI, "yandal_program": ""})
    assert [x[0] for x in s.seconds] == ["cap"]


def test_tekil_ozellikler_ILKINI_veriyor():
    """Eski çağrı yerleri kırılmamalı; tekil alanlar birinciyi gösteriyor."""
    s = config.Settings(**IKISI)
    assert (s.second_role, s.second_label, s.second_program) == ("CAP", "ÇAP", "BLG")


def test_iki_plan_tipi_de_taranacak_listede():
    s = config.Settings.load.__func__(config.Settings)  # varsayılan
    s = config.Settings(**IKISI)
    # `load` çağrılmadığı için burada elle bakıyoruz: iki tür de bilinmeli.
    assert set(s.second_kinds) == {"cap", "yandal"}


def test_program_kodlari_iki_programi_da_kapsiyor(tmp_path):
    yol = tmp_path / "s.toml"
    yol.write_text('[student]\nanadal_program="HTAE"\ncap_program="BLG"\n'
                   'yandal_program="ECN_YD"\nsecond_kind="ikisi"\n', encoding="utf-8")
    s = config.Settings.load(yol)
    assert set(s.program_codes) == {"HTAE", "BLG", "ECN_YD"}
    assert {"cap", "yandal"} <= set(s.scrape_plan_types)


# ------------------------------------------------------------ plan çözümü
def test_resolve_seconds_iki_plan_buluyor(dbs):
    con, _ucon, _sid = dbs
    out = PL.resolve_seconds(con, config.Settings(**IKISI))
    assert [(s["kind"], s["planId"], s["role"]) for s in out] == \
        [("cap", 20, "CAP"), ("yandal", 30, "YANDAL")]


def test_plani_bulunamayan_tur_LISTEDE_KALIYOR(dbs):
    """★ 'Yandalım var ama araç göstermiyor' ile 'yandal planı çekilmemiş'
    aynı şey değil — arayüz farkı söyleyebilmeli."""
    con, _ucon, _sid = dbs
    out = PL.resolve_seconds(con, config.Settings(**{**IKISI, "yandal_program": "YOK_YD"}))
    assert out[1]["kind"] == "yandal" and out[1]["planId"] is None


def test_eski_imza_hala_ilk_plani_veriyor(dbs):
    con, _ucon, _sid = dbs
    assert PL.resolve_plans(con, config.Settings(**IKISI)) == (10, 20)


def test_watch_codes_iki_programi_da_kapsiyor(dbs):
    con, ucon, _sid = dbs
    kodlar = PL.watch_codes(con, ucon, config.Settings(**IKISI))
    assert {"BLG 212E", "ECN 201", "GEO 303E"} <= kodlar


# ------------------------------------------------------------- paneller
def test_uc_panel(dbs):
    assert [p["role"] for p in _collect(dbs)["panels"]] == ["ANADAL", "CAP", "YANDAL"]


def test_seconds_alani_iki_programi_tasiyor(dbs):
    data = _collect(dbs)
    assert [(s["kind"], s["program"]) for s in data["seconds"]] == \
        [("cap", "BLG"), ("yandal", "ECN_YD")]


# --------------------------------------------------------------- adaylar
def test_iki_programin_dersleri_de_aday(dbs):
    kodlar = {c["course"] for c in _collect(dbs)["candidates"]}
    assert {"BLG 212E", "ECN 201", "GEO 303E"} <= kodlar


def test_aday_rolleri_dogru(dbs):
    rol = {c["course"]: c["role"] for c in _collect(dbs)["candidates"]}
    assert rol["BLG 212E"] == "CAP" and rol["ECN 201"] == "YANDAL"
    assert rol["GEO 303E"] == "ANADAL"


def test_iki_zincirin_kritik_yolu_da_hesaplaniyor(dbs):
    """★ Yalnız birine baksaydık öbür programın zincir başı dersi
    'kritik değil' görünür, öneri sıralaması onu geri atardı."""
    kritik = {c["course"] for c in _collect(dbs)["candidates"] if c["critical"]}
    assert "BLG 212E" in kritik and "ECN 201" in kritik


# ------------------------------------------------------------- kademeler
def test_her_program_kendi_kademelerinde(dbs):
    gruplar = _collect(dbs)["tierGroups"]
    assert [g["role"] for g in gruplar] == ["CAP", "YANDAL"]
    dersler = [{c["course"] for t in g["tiers"] for c in t["courses"]} for g in gruplar]
    assert dersler == [{"BLG 212E", "BLG 351E"}, {"ECN 201", "ECN 301"}]


def test_kademeler_BIRLESTIRILMIYOR(dbs):
    """★ Tek listede birleştirseydik iki ayrı programın zincirleri
    birbirine bağlıymış gibi görünürdü — aralarında önşart ilişkisi yok."""
    for g in _collect(dbs)["tierGroups"]:
        icerdekiler = {c["course"] for t in g["tiers"] for c in t["courses"]}
        for t in g["tiers"]:
            for c in t["courses"]:
                assert set(c["needs"]) <= icerdekiler


# -------------------------------------------------------------- darboğaz
def test_darbogaz_hangi_programa_ait_yaziyor(dbs):
    """İki programın engellerini ayrımsız göstermek 'hangi program yüzünden
    takıldım' sorusunu cevapsız bırakırdı."""
    roller = {b["role"] for b in _collect(dbs)["blockers"]}
    assert roller <= {"CAP", "YANDAL"}
    for b in _collect(dbs)["blockers"]:
        assert b["program"] in {"BLG", "ECN_YD"}


# ------------------------------------------------- ★ KURAL KARIŞMASI YOK
def test_esikler_KAPSAMLA_isaretli(dbs):
    esikler = _collect(dbs)["gpa"]["thresholds"]
    assert esikler, "eşik yok"
    for e in esikler:
        assert e["scope"] in {"cap", "yandal", "genel"}


def test_capa_ozel_esik_yandal_kapsaminda_DEGIL(dbs):
    esik = {e["key"]: e for e in _collect(dbs)["gpa"]["thresholds"]}
    if "cap_mezuniyet_ikinci" in esik:
        assert esik["cap_mezuniyet_ikinci"]["scope"] == "cap"


def test_ayni_esik_iki_kez_gosterilmiyor(dbs):
    """İki kapsamda da çıkan eşik GENEL bir kuraldır; iki kez göstermek
    iki ayrı şart varmış izlenimi verirdi."""
    anahtarlar = [e["key"] for e in _collect(dbs)["gpa"]["thresholds"]]
    assert len(anahtarlar) == len(set(anahtarlar))


def test_yarıyil_tabani_YALNIZ_CAPTA(dbs):
    """★ Yönerge 'İkinci anadala N. yarıyılda başlayan öğrenci…' diyor;
    'ikinci anadal' = ÇAP. Yandala uygulamak, var olmayan bir kuralla
    'az aldın' demek olurdu."""
    yalniz_yandal = _collect(dbs, second_kind="yandal", cap_baslangic_yariyili=5)
    assert yalniz_yandal["secondFloor"] is None
    ikisi = _collect(dbs, cap_baslangic_yariyili=5)
    assert ikisi["secondFloor"] and ikisi["secondFloor"]["min"] == 9


def test_kredi_tavani_CAP_muafiyetini_koruyor(dbs):
    """MADDE 17/1 muafiyeti ÇAP öğrencisine ait; iki program birdeyken de
    geçerli — belirleyici olan ÇAP'ın varlığı."""
    assert _collect(dbs)["load"]["exempt"] is True
    assert _collect(dbs, second_kind="yandal")["load"]["exempt"] is False


def test_basvuruda_iki_program_da_haric(dbs):
    b = _collect(dbs)["basvuru"]
    kodlar = {o["code"] for k in ("cap", "yandal") for o in b[k]["options"]}
    assert "BLG" not in kodlar and "ECN_YD" not in kodlar


# ----------------------------------------------------------- geri uyumluluk
def test_tek_program_davranisi_DEGISMEDI(dbs):
    con, ucon, sid = dbs
    s = config.Settings(anadal_program="HTAE", cap_program="BLG",
                        second_kind="cap",
                        program_codes=["HTAE", "BLG"])
    data = UI.collect(con, ucon, sid, s, 10, 20)          # eski konumsal çağrı
    assert [p["role"] for p in data["panels"]] == ["ANADAL", "CAP"]
    assert len(data["tierGroups"]) == 1


def test_tek_yandal_eski_cagriyla_da_dogru(dbs):
    """★ `cap_id` konumsalı tarihsel bir isim; içinde yandal planı olabiliyor.
    Rolün CAP'a düşmediğini kolluyoruz (sunucuda tam bu hata çıktı)."""
    con, ucon, sid = dbs
    s = config.Settings(anadal_program="HTAE", yandal_program="ECN_YD",
                        second_kind="yandal", program_codes=["HTAE"])
    data = UI.collect(con, ucon, sid, s, 10, 30)
    assert [p["role"] for p in data["panels"]] == ["ANADAL", "YANDAL"]
