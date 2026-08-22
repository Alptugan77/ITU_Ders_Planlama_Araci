"""Faz 10 — denklik keşfi, geri alma, kaydedilmiş program, tüm plan taraması."""
import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import config, db, declared, discover, prereq as P, student as S


@pytest.fixture()
def dbs(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "REF_DB", tmp_path / "ref.sqlite3")
    monkeypatch.setattr(config, "USER_DB", tmp_path / "user.sqlite3")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    con = db.connect(tmp_path / "ref.sqlite3", "schema.sql")
    con.executemany(
        "INSERT INTO course(code,name,credits,ects) VALUES (?,?,?,?)",
        [("BBF 103E", "Discrete Mathematics", 3.0, 5.0),
         ("BLG 112E", "Discrete Mathematics", 3.0, 5.0),
         ("MTH 112", "Discrete Mathematics", 4.0, 5.0),      # kredi FARKLI
         ("BLG 112", "Ayrık Matematik", 3.0, 5.0),
         ("AKM 204E", "Fluid Mechanics I", 3.0, 4.0),
         ("AKM 205E", "Fluid Mechanics II", 3.0, 4.0),
         ("GEO 303E", "Kadastro", 3.0, 3.0),
         ("STJ 100", "Staj", 0.0, 1.0),
         ("STJ 200", "Staj", 0.0, 1.0)],
    )
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title,source)
                   VALUES (10,'HTAE','lisans','anadal','obs')""")
    con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,ects,position,term_no)
                   VALUES (10,'REQUIRED','GEO 303E',3.0,0,5)""")
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title,source,is_term_based)
                   VALUES (20,'BLG','cap','ÇAP','obs',0)""")
    for i, code in enumerate(["BLG 112E", "AKM 205E", "STJ 200"]):
        con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,ects,position)
                       VALUES (20,'REQUIRED',?,5.0,?)""", (code, i))
    con.commit()
    P.parse_all(con)
    ucon = db.connect(tmp_path / "user.sqlite3", "schema_user.sql")
    sid = S.ensure_student(ucon)
    return con, ucon, sid


PLANS = [(10, "ANADAL"), (20, "CAP")]


def _suggest(dbs):
    con, ucon, sid = dbs
    return discover.suggest(con, ucon, sid, PLANS)


# ---------------------------------------------------------------- ad normali
def test_roman_numerals_are_kept():
    """★ 'Fluid Mechanics I' ile 'Fluid Mechanics II' AYNI DERS DEĞİL.

    Roma rakamı ekini temizleseydik yanlış denklik üretirdik."""
    assert discover.normalize_name("Fluid Mechanics I") != \
           discover.normalize_name("Fluid Mechanics II")
    assert discover.normalize_name("Discrete  Mathematics!") == \
           discover.normalize_name("Discrete Mathematics")
    assert discover.normalize_name("Data & Structures") == "data and structures"


# ------------------------------------------------------------------- öneri
def test_finds_the_bbf_case(dbs):
    """★ Kullanıcının örneği: BBF 103E aldım -> BLG 112E sayılmalı."""
    con, ucon, sid = dbs
    S.add_entries(ucon, sid, [S.make_entry("BBF 103E", "BB")])
    items = _suggest(dbs)
    assert [(i.source, i.target) for i in items] == [("BBF 103E", "BLG 112E")]
    hit = items[0]
    assert hit.confidence == discover.HIGH
    assert hit.plan_role == "CAP" and hit.source_grade == "BB"
    assert "aynı kredi (3)" in hit.reasons


def test_different_credits_lower_confidence(dbs):
    con, ucon, sid = dbs
    S.add_entries(ucon, sid, [S.make_entry("MTH 112", "AA")])
    hit = _suggest(dbs)[0]
    assert hit.confidence == discover.LOW
    assert any("kredi farklı" in r for r in hit.reasons)


def test_language_suffix_mismatch_lowers_confidence(dbs):
    """Türkçe ders İngilizce dersin yerine geçmeyebilir — HTA/HTAE ilkesi."""
    con, ucon, sid = dbs
    con.execute("UPDATE course SET name='Discrete Mathematics' WHERE code='BLG 112'")
    con.commit()
    S.add_entries(ucon, sid, [S.make_entry("BLG 112", "AA")])
    hit = _suggest(dbs)[0]
    assert hit.confidence == discover.LOW
    assert any("dil eki" in r for r in hit.reasons)


def test_satisfied_slot_produces_no_suggestion(dbs):
    """Dersi zaten geçmişsen öneriye gerek yok."""
    con, ucon, sid = dbs
    S.add_entries(ucon, sid, [S.make_entry("BBF 103E", "BB"),
                              S.make_entry("BLG 112E", "CC")])
    assert not any(i.target == "BLG 112E" for i in _suggest(dbs))


def test_short_names_are_ignored(dbs):
    """'Staj' gibi kısa adlar ayırt etmiyor — yanlış denklik üretirdi."""
    con, ucon, sid = dbs
    S.add_entries(ucon, sid, [S.make_entry("STJ 100", "BL")])
    assert not any(i.target == "STJ 200" for i in _suggest(dbs))


def test_series_courses_do_not_match_each_other(dbs):
    """★ 'Fluid Mechanics I' aldıysan 'II' sayılmaz."""
    con, ucon, sid = dbs
    S.add_entries(ucon, sid, [S.make_entry("AKM 204E", "AA")])
    assert not any(i.target == "AKM 205E" for i in _suggest(dbs))


def test_already_declared_is_not_suggested_again(dbs, tmp_path, monkeypatch):
    con, ucon, sid = dbs
    S.add_entries(ucon, sid, [S.make_entry("BBF 103E", "BB")])
    path = tmp_path / "denklikler.toml"
    monkeypatch.setattr(declared, "DEFAULT_PATH", path)
    declared.append("BLG 112E", ["BBF 103E"], path=path)
    declared.apply(con, path)
    assert _suggest(dbs) == []


def test_empty_transcript_suggests_nothing(dbs):
    assert _suggest(dbs) == []


def test_format_runs(dbs):
    con, ucon, sid = dbs
    S.add_entries(ucon, sid, [S.make_entry("BBF 103E", "BB")])
    text = discover.format_suggestions(_suggest(dbs))
    assert "BBF 103E" in text and "YÜKSEK GÜVEN" in text
    assert "bulunamadı" in discover.format_suggestions([])


# ------------------------------------------------------------- geri alma
def test_remove_deletes_only_the_matching_block(tmp_path):
    """★ Tek tıkla uygulanan tek tıkla kaldırılabilmeli.

    Kaldırma yorumları ve öbür blokları BOZMAMALI."""
    path = tmp_path / "denklikler.toml"
    path.write_text(
        '# baştaki yorum\n\n'
        '[[denklik]]\nhedef   = "BLG 112E"\nkaynak  = ["BBF 103E"]\n\n'
        '[[denklik]]\nhedef   = "MAT 210E"\nkaynak  = ["GEO 220E"]\n\n'
        '[[muafiyet]]\ndersler = ["ING 101"]\n', encoding="utf-8")
    assert declared.remove("BLG 112E", path) is True
    text = path.read_text(encoding="utf-8")
    assert "BLG 112E" not in text
    assert "# baştaki yorum" in text and "MAT 210E" in text and "[[muafiyet]]" in text
    assert [d["target"] for d in declared.load_file(path)] == ["MAT 210E"]


def test_remove_unknown_target_is_noop(tmp_path):
    path = tmp_path / "denklikler.toml"
    path.write_text('[[denklik]]\nhedef = "A 101"\nkaynak = ["B 101"]\n', encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    assert declared.remove("YOK 999", path) is False
    assert path.read_text(encoding="utf-8") == before


def test_apply_is_authoritative(dbs, tmp_path):
    """Dosyadan silinen beyan veritabanından da gitmeli."""
    con, _ucon, _sid = dbs
    path = tmp_path / "denklikler.toml"
    declared.append("BLG 112E", ["BBF 103E"], path=path)
    declared.apply(con, path)
    assert con.execute("SELECT COUNT(*) FROM equivalence").fetchone()[0] == 1
    declared.remove("BLG 112E", path)
    declared.apply(con, path)
    assert con.execute("SELECT COUNT(*) FROM equivalence").fetchone()[0] == 0


def test_equivalence_makes_the_course_count_as_passed(dbs, tmp_path):
    """★ Kullanıcının asıl isteği: denklik varsa GEÇİLMİŞ sayılsın."""
    from itucap import rules as R
    con, ucon, sid = dbs
    S.add_entries(ucon, sid, [S.make_entry("BBF 103E", "BB")])
    path = tmp_path / "denklikler.toml"
    declared.append("BLG 112E", ["BBF 103E"], path=path)
    declared.apply(con, path)
    expanded, via = R.expand_with_equivalences(S.grades(ucon, sid),
                                               R.load_equivalences(con))
    assert expanded.get("BLG 112E") == "BB" and "BLG 112E" in via
    slot = con.execute(
        "SELECT id FROM plan_slot WHERE course_code='BLG 112E'").fetchone()[0]
    assert R.slot_satisfied(con, slot, S.grades(ucon, sid),
                            R.load_equivalences(con)).satisfied is True


# --------------------------------------------------- kaydedilmiş program
def test_saved_picks_round_trip(dbs):
    _con, ucon, sid = dbs
    assert S.load_picks(ucon, sid, "202610")["picks"] == []
    S.save_picks(ucon, sid, "202610", [("BLG 112E", "100"), ("GEO 303E", "200")])
    got = S.load_picks(ucon, sid, "202610")
    assert [p["course"] for p in got["picks"]] == ["BLG 112E", "GEO 303E"]
    assert got["savedAt"]


def test_saving_replaces_the_previous_selection(dbs):
    """Kaydet TAM listeyi yazar — çıkardığın ders kayıtta kalmamalı."""
    _con, ucon, sid = dbs
    S.save_picks(ucon, sid, "202610", [("BLG 112E", "100"), ("GEO 303E", "200")])
    S.save_picks(ucon, sid, "202610", [("BLG 112E", "101")])
    got = S.load_picks(ucon, sid, "202610")["picks"]
    assert got == [{"course": "BLG 112E", "crn": "101"}]


def test_saved_picks_are_per_term(dbs):
    _con, ucon, sid = dbs
    S.save_picks(ucon, sid, "202610", [("BLG 112E", "100")])
    S.save_picks(ucon, sid, "202620", [("GEO 303E", "200")])
    assert len(S.load_picks(ucon, sid, "202610")["picks"]) == 1
    assert S.load_picks(ucon, sid, "202620")["picks"][0]["course"] == "GEO 303E"
    S.clear_picks(ucon, sid, "202610")
    assert S.load_picks(ucon, sid, "202610")["picks"] == []
    assert S.load_picks(ucon, sid, "202620")["picks"]        # öteki dönem duruyor


# --------------------------------------------- tüm ÇAP/yandal taraması
def test_all_second_plans_sweeps_every_program(dbs, monkeypatch):
    """★ Faz 7'de ikinci program seçilebilir oldu ama seçilecek plan yoktu."""
    from itucap import pipeline
    from itucap.sources import obs_plan

    con, _ucon, _sid = dbs
    con.execute("INSERT INTO program(code,name,level) VALUES ('HTAE','Harita','LS')")
    con.execute("INSERT INTO program(code,name,level) VALUES ('BLG','Bilgisayar','LS')")
    con.execute("INSERT INTO program(code,name,level) VALUES ('SAO','Ön lisans','OL')")
    con.commit()

    asked, scraped = [], []
    monkeypatch.setattr(pipeline, "ObsClient", lambda *a, **k: type(
        "C", (), {"close": lambda self: None})())

    def fake_list(client, plan_type, program):
        asked.append((plan_type, program))
        if plan_type == "cap" and program == "BLG_LS":
            return [{"plan_id": 1, "title": "t"}]
        return []

    monkeypatch.setattr(obs_plan, "list_plans", fake_list)
    monkeypatch.setattr(obs_plan, "scrape_plan",
                        lambda c, con_, meta: scraped.append(meta) or 7)

    stats = pipeline.step_all_second_plans(con, config.Settings())
    assert stats["programs"] == 2              # yalnız LS programları
    assert ("cap", "HTAE_LS") in asked and ("yandal", "BLG_LS") in asked
    assert ("cap", "SAO_LS") not in asked      # ön lisans taranmıyor
    assert stats["plans"] == 1 and stats["slots"] == 7


def test_all_second_plans_survives_a_failing_program(dbs, monkeypatch):
    """Bir program patlarsa tarama durmamalı — 129 programın biri yüzünden."""
    from itucap import pipeline
    from itucap.sources import obs_plan

    con, _ucon, _sid = dbs
    con.execute("INSERT INTO program(code,name,level) VALUES ('A','A','LS')")
    con.execute("INSERT INTO program(code,name,level) VALUES ('B','B','LS')")
    con.commit()
    monkeypatch.setattr(pipeline, "ObsClient", lambda *a, **k: type(
        "C", (), {"close": lambda self: None})())

    def boom(client, plan_type, program):
        if program == "A_LS":
            raise RuntimeError("OBS 500")
        return [{"plan_id": 2, "title": "t"}]

    monkeypatch.setattr(obs_plan, "list_plans", boom)
    monkeypatch.setattr(obs_plan, "scrape_plan", lambda c, con_, meta: 3)
    stats = pipeline.step_all_second_plans(con, config.Settings())
    assert stats["errors"] == 2 and stats["plans"] == 2      # B iki tipte de geçti


# ================================ kalite kontrolü kapsamı (21.08.2026 hatası)
def _cap_plan(con, plan_id, program, slots, has_table=1, plan_type="cap"):
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title,source,
                                    has_course_table)
                   VALUES (?,?,?,'t','obs',?)""",
                (plan_id, program, plan_type, has_table))
    for i in range(slots):
        con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,position)
                       VALUES (?, 'REQUIRED', ?, ?)""", (plan_id, f"X {100+i}", i))
    con.commit()


def test_other_programs_broken_plan_is_only_a_warning(dbs):
    """★ 1081 planın birindeki anomali `make`'i düşürmemeli.

    Kontrol tek ÇAP planı varken yazılmıştı. `--all-programs` sonrası
    veritabanında tüm üniversitenin planları var; başka bölümün planı
    senin sonuçlarını etkilemiyor ve senin yapabileceğin bir şey yok.
    """
    from itucap import quality
    con, _ucon, _sid = dbs
    _cap_plan(con, 1815, "MAK", slots=0)              # bozuk, ama SENİN DEĞİL
    findings = {f.check_id: f for f in quality.run(con, mine=(10, 20))}
    hit = findings["cap_plan_size"]
    assert hit.severity == "warn"
    assert "seni etkilemiyor" in hit.detail and "1815" in hit.detail


def test_my_own_broken_plan_is_an_error(dbs):
    """Kendi planın bozuksa sonuçlar güvenilmez — bu gerçekten hata."""
    from itucap import quality
    con, _ucon, _sid = dbs
    _cap_plan(con, 77, "BLG", slots=0)
    findings = {f.check_id: f for f in quality.run(con, mine=(10, 77))}
    hit = findings["cap_plan_size"]
    assert hit.severity == "error"
    assert "SENİN" in hit.detail and "plan-info ID=77" in hit.detail


def test_empty_and_oversized_plans_are_reported_separately(dbs):
    """Boş plan ile şişmiş plan farklı arızalar — mesaj ikisini ayırmalı."""
    from itucap import quality
    con, _ucon, _sid = dbs
    _cap_plan(con, 101, "MAK", slots=0)
    _cap_plan(con, 102, "GEM", slots=61, plan_type="yandal")
    detail = {f.check_id: f.detail for f in quality.run(con, mine=())}["cap_plan_size"]
    assert "1 plan boş çıktı" in detail and "60'tan fazla" in detail


def test_plans_without_a_course_table_are_not_parse_errors(dbs):
    """Kaynakta boş yayınlanan plan bizim hatamız değil — ayrı bulgu."""
    from itucap import quality
    con, _ucon, _sid = dbs
    _cap_plan(con, 103, "MAK", slots=0, has_table=0)
    ids = {f.check_id for f in quality.run(con, mine=())}
    assert "cap_plan_size" not in ids
    assert "upstream_empty_plans" in ids
