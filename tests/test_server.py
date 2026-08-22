"""Faz 8 — yerel uygulama: ayar yazma, uçlar ve güvenlik.

⚠️ Bu testler GERÇEK `config/settings.toml`'a yazmamalı. Her test kendi geçici
kökünde çalışıyor (`sandbox` fixture'ı); biri kaçarsa kullanıcının ayarları
bozulurdu.
"""
import json
import threading
import urllib.error
import urllib.request

import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import config, db, policy as POL, prereq as P, server, student as S


SETTINGS = """\
# baştaki yorum
[student]
anadal_program = "HTAE"      # satır sonu yorumu
second_kind = "cap"
cap_program = "BLG"
cap_plan_id = 20
program_codes = ["HTAE", "BLG"]
donem = 0

[scraper]
user_agent = "test#değil-yorum"
"""


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    """Geçici kök: settings.toml, kurallar.toml ve iki veritabanı."""
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "settings.toml").write_text(SETTINGS, encoding="utf-8")
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "REF_DB", tmp_path / "ref.sqlite3")
    monkeypatch.setattr(config, "USER_DB", tmp_path / "user.sqlite3")
    # ★ DATA_DIR modül yüklenirken hesaplanıyor; ROOT'u değiştirmek yetmiyor.
    # Yamalanmazsa yedekler GERÇEK data/ klasörüne düşer (test sızıntısı).
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(POL, "DEFAULT_PATH", tmp_path / "config" / "kurallar.toml")
    # denklik beyanları da sandbox içinde kalsın (autouse fixture'ı ezer)
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "config" / "denklikler.toml")
    return tmp_path


@pytest.fixture()
def seeded(sandbox):
    con = db.connect(config.REF_DB, "schema.sql")
    con.executemany(
        "INSERT INTO course(code,name,credits,ects,prereq_raw) VALUES (?,?,?,?,?)",
        [("MAT 103E", "Mathematics I", 4.0, 6.0, None),
         ("MAT 104E", "Mathematics II", 4.0, 6.0, None),
         ("BLG 212E", "Microprocessors", 3.0, 7.0, None),
         ("GEO 303E", "Kadastro", 3.0, 3.0, None)])
    con.execute("""INSERT INTO program(code,name) VALUES ('HTAE','Harita')""")
    con.execute("""INSERT INTO program(code,name) VALUES ('BLG','Bilgisayar')""")
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title,source)
                   VALUES (10,'HTAE','lisans','anadal','obs')""")
    con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,ects,position,term_no)
                   VALUES (10,'REQUIRED','GEO 303E',3.0,0,5)""")
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title,source,is_term_based)
                   VALUES (20,'BLG','cap','ÇAP planı','obs',0)""")
    con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,ects,position)
                   VALUES (20,'REQUIRED','BLG 212E',7.0,0)""")
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title,source,is_term_based)
                   VALUES (30,'BLG','yandal','Yandal planı','obs',0)""")
    con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,ects,position)
                   VALUES (30,'REQUIRED','BLG 212E',7.0,0)""")
    con.execute("""INSERT INTO lesson(crn,course_code,capacity,enrolled,building)
                   VALUES ('100','GEO 303E',50,0,'INB')""")
    con.execute("""INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min,building)
                   VALUES ('100',1,510,689,'INB')""")
    con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES ('100','HTAE')")
    con.commit()
    P.parse_all(con)
    con.close()
    ucon = db.connect(config.USER_DB, "schema_user.sql")
    sid = S.ensure_student(ucon)
    S.add_entries(ucon, sid, [S.make_entry("MAT 103E", "AA")])
    ucon.commit()
    ucon.close()
    return sandbox


# ============================================================ ayar yazıcısı
def test_update_preserves_comments_and_layout(sandbox):
    path = sandbox / "config" / "settings.toml"
    before = path.read_text(encoding="utf-8")
    config.update_settings({"donem": 6})
    after = path.read_text(encoding="utf-8")
    assert after.count("#") == before.count("#")
    assert "# baştaki yorum" in after
    assert "donem = 6" in after
    assert config.Settings.load(path).donem == 6


def test_update_keeps_trailing_comment_on_edited_line(sandbox):
    """★ Satır sonu yorumları projenin ölçüm notları — silinmemeli."""
    path = sandbox / "config" / "settings.toml"
    config.update_settings({"anadal_program": "GEOE"})
    line = [l for l in path.read_text(encoding="utf-8").splitlines()
            if l.startswith("anadal_program")][0]
    assert line == 'anadal_program = "GEOE"  # satır sonu yorumu'


def test_hash_inside_quotes_is_not_a_comment(sandbox):
    """`user_agent = "test#değil-yorum"` bozulmamalı."""
    path = sandbox / "config" / "settings.toml"
    config.update_settings({"donem": 1})
    assert 'user_agent = "test#değil-yorum"' in path.read_text(encoding="utf-8")


def test_missing_key_is_appended_to_student_section(sandbox):
    path = sandbox / "config" / "settings.toml"
    config.update_settings({"yandal_program": "BLG", "yandal_plan_id": 30})
    text = path.read_text(encoding="utf-8")
    assert text.index("yandal_program") < text.index("[scraper]")
    s = config.Settings.load(path)
    assert s.yandal_program == "BLG" and s.yandal_plan_id == 30


def test_unknown_key_is_refused(sandbox):
    """★ Arayüzden gelen rastgele alan yapılandırmaya sızmasın."""
    with pytest.raises(ValueError):
        config.update_settings({"user_agent": "kotu"})
    with pytest.raises(ValueError):
        config.update_settings({"__proto__": 1})


def test_list_and_number_round_trip(sandbox):
    path = sandbox / "config" / "settings.toml"
    config.update_settings({"program_codes": ["HTAE", "BLG", "BLGE"], "max_load": 30})
    s = config.Settings.load(path)
    assert s.allowed_programs == {"HTAE", "BLG", "BLGE"} and s.max_load == 30


# ====================================================== tek karar noktası
def test_form_and_text_entry_agree():
    """★ Aynı girdi, nereden girildiğine göre farklı sonuç vermemeli."""
    for code, grade in (("MAT 103E", "AA"), ("mat 103e", "cc"), ("MAT 103E", "FF")):
        form = S.make_entry(code, grade)
        text = S.parse_line(f"{code} {grade}")
        assert (form.course_code, form.grade, form.status) == \
               (text.course_code, text.grade, text.status)


def test_unknown_grade_defaults_to_worst_case():
    """Not verilmedi -> DD (geçti ama en kötü). 'MIN CC'de yanlış izin vermez."""
    entry = S.make_entry("MAT 103E", "")
    assert (entry.grade, entry.status, entry.grade_known) == ("DD", "PASSED", False)


def test_in_progress_is_not_passed():
    entry = S.make_entry("MAT 103E", None, "--")
    assert entry.status == "IN_PROGRESS" and entry.grade is None


# ================================================================ sunucu
@pytest.fixture()
def live(seeded):
    state = server.State()
    httpd = server.build(state, "127.0.0.1", 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"

    def get(path):
        try:
            with urllib.request.urlopen(base + path) as res:
                return res.status, json.loads(res.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def post(path, payload, token="__ok__", origin=None):
        req = urllib.request.Request(
            base + path, data=json.dumps(payload).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json"})
        if token is not None:
            req.add_header("X-Itucap-Token", state.token if token == "__ok__" else token)
        if origin:
            req.add_header("Origin", origin)
        try:
            with urllib.request.urlopen(req) as res:
                return res.status, json.loads(res.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    yield state, base, get, post
    httpd.shutdown()
    httpd.server_close()


def test_state_endpoint_carries_live_flag_and_setup(live):
    _state, _base, get, _post = live
    code, data = get("/api/state")
    assert code == 200 and data["live"] is True and data["token"]
    setup = data["setup"]
    assert setup["anadalProgram"] == "HTAE" and setup["secondKind"] == "cap"
    assert any(t["course"] == "MAT 103E" for t in setup["transcript"])
    assert {p["code"] for p in setup["programs"]} >= {"HTAE", "BLG"}
    assert setup["grades"][0] == "AA"


def test_index_serves_html_with_token(live):
    _state, base, _get, _post = live
    with urllib.request.urlopen(base + "/") as res:
        html = res.read().decode("utf-8")
    assert html.startswith("<!doctype html>") and '"live": true' in html
    assert res.headers["Cache-Control"] == "no-store"       # kişisel veri
    assert res.headers["X-Frame-Options"] == "DENY"


def test_course_search(live):
    _state, _base, get, _post = live
    _code, data = get("/api/courses?q=MAT")
    assert {c["code"] for c in data["results"]} == {"MAT 103E", "MAT 104E"}
    assert get("/api/courses?q=M")[1]["results"] == []       # tek harf aranmaz


# ------------------------------------------------------------- güvenlik
def test_write_requires_token(live):
    _state, _base, _get, post = live
    assert post("/api/donem", {"donem": 3}, token=None)[0] == 403
    assert post("/api/donem", {"donem": 3}, token="a" * 32)[0] == 403


def test_foreign_origin_is_refused(live):
    """★ Başka bir sitenin sekmesi 127.0.0.1'e istek atsa bile yazamamalı."""
    _state, _base, _get, post = live
    assert post("/api/donem", {"donem": 3}, origin="https://kotu.example")[0] == 403


def test_own_origin_is_accepted(live):
    _state, base, _get, post = live
    assert post("/api/donem", {"donem": 3}, origin=base)[0] == 200


def test_unknown_path_is_404(live):
    _state, _base, get, post = live
    assert get("/api/yok")[0] == 404
    assert post("/api/yok", {})[0] == 404


def test_oversized_body_is_refused(live):
    _state, _base, _get, post = live
    code, _ = post("/api/transcript", {"items": [], "pad": "x" * (server.MAX_BODY + 10)})
    assert code == 400


# ----------------------------------------------------------------- yazma
def test_term_is_saved_and_validated(live, sandbox):
    _state, _base, _get, post = live
    code, data = post("/api/donem", {"donem": 4})
    assert code == 200 and data["donem"] == 4 and data["donemSource"] == "beyan"
    assert config.Settings.load().donem == 4
    assert any("4" in m["label"] for m in data["modes"])
    assert post("/api/donem", {"donem": 99})[0] == 400
    assert post("/api/donem", {"donem": -1})[0] == 400


def test_transcript_add_changes_credits(live):
    _state, _base, _get, post = live
    _c, before = post("/api/donem", {"donem": 0})
    assert before["credits"]["earned"] == 4.0                # MAT 103E
    code, data = post("/api/transcript", {
        "items": [{"course": "MAT 103E", "grade": "AA"},
                  {"course": "MAT 104E", "grade": "BB"}], "replace": True})
    assert code == 200 and data["saved"] == 2
    assert data["credits"]["earned"] == 8.0


def test_transcript_replace_removes_dropped_rows(live):
    """★ 'çıkar' düğmesi replace:true ile çalışıyor; ders gerçekten gitmeli."""
    _state, _base, _get, post = live
    post("/api/transcript", {"items": [{"course": "MAT 103E", "grade": "AA"},
                                       {"course": "MAT 104E", "grade": "AA"}],
                             "replace": True})
    _c, data = post("/api/transcript", {"items": [{"course": "MAT 103E", "grade": "AA"}],
                                        "replace": True})
    codes = {t["course"] for t in data["setup"]["transcript"]}
    assert codes == {"MAT 103E"}


def test_transcript_paste_reports_bad_lines(live):
    _state, _base, _get, post = live
    code, data = post("/api/transcript/paste",
                      {"text": "MAT 104E AA\nbu satır ders değil\n", "replace": False})
    assert code == 200 and data["saved"] == 1
    assert data["bad"] == ["bu satır ders değil"]


def test_remove_endpoint(live):
    _state, _base, _get, post = live
    _c, data = post("/api/transcript/remove", {"course": "MAT 103E"})
    assert not data["setup"]["transcript"]


# ------------------------------------------------------- program seçimi
def test_switch_to_yandal(live, sandbox):
    _state, _base, _get, post = live
    code, data = post("/api/programs", {"anadalProgram": "HTAE", "secondKind": "yandal",
                                        "secondProgram": "BLG", "secondPlanId": 30})
    assert code == 200
    assert data["secondRole"] == "YANDAL" and data["secondLabel"] == "Yandal"
    assert [p["role"] for p in data["panels"]] == ["ANADAL", "YANDAL"]
    s = config.Settings.load()
    assert (s.second_kind, s.yandal_program, s.yandal_plan_id) == ("yandal", "BLG", 30)


def test_switch_to_single_program(live):
    _state, _base, _get, post = live
    _c, data = post("/api/programs", {"anadalProgram": "HTAE", "secondKind": "yok"})
    assert [p["role"] for p in data["panels"]] == ["ANADAL"]
    assert data["blockers"] == [] and data["cap"] == ""


def test_program_change_reenrolls_student(live):
    """★ Eski kayıt silinmezse ilerleme paneli kapatılmış programı gösterirdi."""
    state, _base, _get, post = live
    post("/api/programs", {"anadalProgram": "HTAE", "secondKind": "yandal",
                           "secondProgram": "BLG", "secondPlanId": 30})
    roles = {r["role"]: r["plan_id"] for r in S.enrollments(state.ucon, state.student_id)}
    assert roles == {"ANADAL": 10, "YANDAL": 30}


def test_invalid_program_payloads(live):
    _state, _base, _get, post = live
    assert post("/api/programs", {"anadalProgram": "HTAE", "secondKind": "sacma"})[0] == 400
    assert post("/api/programs", {"anadalProgram": "", "secondKind": "yok"})[0] == 400
    assert post("/api/programs", {"anadalProgram": "HTAE", "secondKind": "cap",
                                  "secondProgram": ""})[0] == 400


def test_program_codes_are_sanitised(live):
    """★ Kod alanı doğrudan yapılandırmaya yazılıyor — temizlenmeli."""
    _state, _base, _get, post = live
    post("/api/programs", {"anadalProgram": "htae", "secondKind": "cap",
                           "secondProgram": "blg",
                           "programCodes": ["htae", "b l g", "x\"; drop", ""]})
    assert config.Settings.load().allowed_programs == {"HTAE", "BLG", "XDROP"}


# ================================================== Faz 9: tazeleme ve GNO
def test_state_carries_gpa_and_changes(live):
    _state, _base, get, _post = live
    _code, data = get("/api/state")
    assert "gpa" in data and data["gpa"]["counted"] == 1        # MAT 103E
    assert data["gpa"]["value"] == 4.0
    assert [t["key"] for t in data["gpa"]["thresholds"]] == []  # sandbox'ta eşik yok
    assert "changes" in data and data["changes"]["since"] == ""  # henüz görüntü yok


def test_gpa_updates_after_transcript_edit(live):
    _state, _base, _get, post = live
    _c, data = post("/api/transcript", {
        "items": [{"course": "MAT 103E", "grade": "AA"},
                  {"course": "MAT 104E", "grade": "CC"}], "replace": True})
    assert data["gpa"]["value"] == 3.0 and data["gpa"]["counted"] == 2


def test_in_progress_course_is_reported_not_recommended(live):
    """★ Bu dönem aldığın ders öneriye girmez ama KAYBOLMAZ da."""
    _state, _base, _get, post = live
    _c, data = post("/api/transcript", {
        "items": [{"course": "BLG 212E", "inProgress": True}], "replace": False})
    assert data["taking"] == ["BLG 212E"]
    assert "BLG 212E" not in {c["course"] for c in data["candidates"]}
    assert any(b["reason"] == "ALIYORSUN" and b["course"] == "BLG 212E"
               for b in data["blockers"])


def test_destructive_write_leaves_a_backup(live, sandbox):
    """★ Elle girilmiş transkript geri gelmez — silici yazma yedek bırakmalı."""
    _state, _base, _get, post = live
    post("/api/transcript", {"items": [{"course": "MAT 104E", "grade": "BB"}],
                             "replace": True})
    backups = list((sandbox / "yedek").glob("transkript-*.txt"))
    assert backups, "replace öncesi yedek yazılmalıydı"
    assert "MAT 103E" in backups[0].read_text(encoding="utf-8")   # ESKİ hâli


def test_refresh_endpoint_requires_token(live):
    _state, _base, _get, post = live
    assert post("/api/refresh", {}, token=None)[0] == 403


def test_concurrent_refresh_is_refused(live, monkeypatch):
    """İki kez tıklayınca aynı iş iki kez yapılmasın."""
    state, _base, _get, post = live
    state.busy = True
    try:
        code, body = post("/api/refresh", {})
        assert code == 400 and "sürüyor" in body["error"]
    finally:
        state.busy = False


# ================================================ Faz 10: denklik ve kayıt
def test_equivalence_apply_and_undo(live, sandbox):
    """★ Tek tıkla uygulanan tek tıkla kaldırılabilmeli."""
    _state, _base, _get, post = live
    # MAT 104E'yi "aldım" say, MAT 103E planında olsun diye takas et
    code, data = post("/api/equivalence",
                      {"target": "GEO 303E", "sources": ["MAT 103E"]})
    assert code == 200
    assert [e["target"] for e in data["equivalences"]] == ["GEO 303E"]
    toml = (sandbox / "config" / "denklikler.toml").read_text(encoding="utf-8")
    assert "GEO 303E" in toml and "MAT 103E" in toml

    _c, back = post("/api/equivalence/remove", {"target": "GEO 303E"})
    assert back["equivalences"] == []
    assert "GEO 303E" not in (sandbox / "config" / "denklikler.toml").read_text(
        encoding="utf-8")


def test_equivalence_fills_the_plan_slot(live):
    """Denklik uygulanınca slot dolmalı — ilerleme yüzdesi artmalı."""
    _state, _base, get, post = live
    _c, before = get("/api/state")
    anadal_before = next(p for p in before["panels"] if p["role"] == "ANADAL")
    _c, after = post("/api/equivalence",
                     {"target": "GEO 303E", "sources": ["MAT 103E"]})
    anadal_after = next(p for p in after["panels"] if p["role"] == "ANADAL")
    assert anadal_after["percent"] > anadal_before["percent"]
    assert "GEO 303E" not in {c["course"] for c in after["candidates"]}


def test_equivalence_rejects_empty_payload(live):
    _state, _base, _get, post = live
    assert post("/api/equivalence", {"target": "", "sources": ["X 101"]})[0] == 400
    assert post("/api/equivalence", {"target": "X 101", "sources": []})[0] == 400


def test_suggestions_appear_in_state(live):
    _state, _base, get, post = live
    post("/api/transcript", {"items": [{"course": "MAT 103E", "grade": "AA"},
                                       {"course": "MAT 104E", "grade": "BB"}],
                             "replace": True})
    _c, data = get("/api/state")
    assert isinstance(data["suggestions"], list)


def test_saved_picks_round_trip_over_http(live):
    """★ Izgaradaki düzenleme sayfa kapanınca kaybolmamalı."""
    _state, _base, get, post = live
    _c, data = get("/api/state")
    assert data["savedPicks"]["picks"] == []
    _c, saved = post("/api/picks", {"picks": [{"course": "GEO 303E", "crn": "100"}]})
    assert saved["savedPicks"]["picks"] == [{"course": "GEO 303E", "crn": "100"}]
    assert saved["savedPicks"]["savedAt"]
    _c, cleared = post("/api/picks/clear", {})
    assert cleared["savedPicks"]["picks"] == []


def test_saved_picks_survive_a_new_state_read(live):
    _state, _base, get, post = live
    post("/api/picks", {"picks": [{"course": "GEO 303E", "crn": "100"}]})
    _c, fresh = get("/api/state")
    assert len(fresh["savedPicks"]["picks"]) == 1


# ============================================ Faz 11: kredi yükü, tikleme, yedek
def test_max_load_endpoint_writes_settings(live, sandbox):
    """★ Yönetmelik tavanına çekme düğmesi settings.toml'a yazmalı."""
    _state, _base, _get, post = live
    code, data = post("/api/maxload", {"maxLoad": 25})
    assert code == 200 and data["maxLoad"] == 25
    assert config.Settings.load().max_load == 25
    assert post("/api/maxload", {"maxLoad": 0})[0] == 400
    assert post("/api/maxload", {"maxLoad": 999})[0] == 400


def test_checklist_lists_plan_courses_with_taken_flag(live):
    """★ Tek tek aramak yerine plandan tikleme — veri sözleşmesi."""
    _state, _base, get, _post = live
    _c, data = get("/api/state")
    checklist = data["setup"]["checklist"]
    assert [p["role"] for p in checklist] == ["ANADAL", "CAP"]
    flat = [o for p in checklist for t in p["terms"] for s in t["slots"]
            for o in s["options"]]
    by_code = {o["course"]: o for o in flat}
    assert by_code["GEO 303E"]["taken"] is False
    assert by_code["GEO 303E"]["credits"] == 3.0
    assert data["setup"]["passFail"] == ["BL", "BZ"]


def test_checklist_marks_courses_already_taken(live):
    _state, _base, get, post = live
    post("/api/transcript", {"items": [{"course": "GEO 303E", "grade": "BB"}],
                             "replace": False})
    _c, data = get("/api/state")
    flat = {o["course"]: o for p in data["setup"]["checklist"]
            for t in p["terms"] for s in t["slots"] for o in s["options"]}
    assert flat["GEO 303E"]["taken"] is True and flat["GEO 303E"]["grade"] == "BB"


def test_bz_is_an_offered_grade(live):
    _state, _base, get, _post = live
    _c, data = get("/api/state")
    assert "BZ" in data["setup"]["grades"] and "BL" in data["setup"]["grades"]


def test_restore_endpoint_round_trip(live, sandbox):
    _state, _base, get, post = live
    post("/api/transcript", {"items": [{"course": "MAT 103E", "grade": "AA"},
                                       {"course": "MAT 104E", "grade": "BB"}],
                             "replace": True})
    _c, state = get("/api/state")
    backups = state["setup"]["backups"]
    assert backups, "silici yazma yedek bırakmalıydı"
    post("/api/transcript", {"items": [{"course": "MAT 103E", "grade": "FF"}],
                             "replace": True})
    _c, back = post("/api/transcript/restore", {"file": backups[0]["file"]})
    codes = {t["course"] for t in back["setup"]["transcript"]}
    assert codes == {"MAT 103E"}          # yedek ilk (tek derslik) hâliydi


def test_restore_rejects_traversal(live):
    _state, _base, _get, post = live
    assert post("/api/transcript/restore", {"file": "../../etc/passwd"})[0] == 400


def test_load_rule_reaches_the_client(live, sandbox):
    """Yönetmelik kuralı beyan edilmişse arayüze ulaşmalı."""
    (sandbox / "config" / "kurallar.toml").write_text(
        '[kredi_yuku_bant]\nmin_kredi=13\nmax_kredi=22\nmuaf=["cap"]\n'
        'dogrulandi=true\nkaynak="MADDE 17"\n'
        '[[kredi_yuku]]\nad="genel"\nmax_kredi=22\nmin_gno=0.0\n'
        '[[kredi_yuku]]\nad="25"\nmax_kredi=25\nmin_gno=2.25\n', encoding="utf-8")
    _state, _base, get, post = live
    post("/api/transcript", {"items": [{"course": "MAT 103E", "grade": "BB"}],
                             "replace": True})          # GNO 3.00
    _c, data = get("/api/state")
    assert data["load"]["max"] == 25 and data["load"]["exempt"] is True
    assert data["load"]["verified"] is True


# ------------------------------------------------- Faz 12: kontenjan nöbeti
def test_watch_endpoint_toggles_the_list(live, sandbox):
    """★ "Bu dersi izle" (yapılacaklar 4.3) settings.toml'a yazmalı.

    Nöbet listesi şimdiye kadar yalnız elle düzenlenebiliyordu; kayıt
    haftasında bir dersi izlemeye almak için dosya açmak gerekiyordu."""
    _state, _base, _get, post = live
    code, data = post("/api/watch", {"course": "blg 351e"})
    assert code == 200
    assert data["on"] is True
    assert data["watching"] == ["BLG 351E"]        # normalize edilmiş
    assert config.Settings.load().watch_courses == ["BLG 351E"]

    code, data = post("/api/watch", {"course": "BLG 351E"})
    assert code == 200 and data["on"] is False
    assert config.Settings.load().watch_courses == []


def test_watch_endpoint_rejects_empty_course(live):
    _state, _base, _get, post = live
    assert post("/api/watch", {"course": "  "})[0] == 400


def test_watch_list_is_exposed_to_the_page(live):
    """Arayüz düğmenin durumunu bilmeli; yoksa 'izle' hep kapalı görünür."""
    _state, _base, get, post = live
    post("/api/watch", {"course": "BLG 335E"})
    code, data = get("/api/state")
    assert code == 200
    assert data["setup"]["watchCourses"] == ["BLG 335E"]
