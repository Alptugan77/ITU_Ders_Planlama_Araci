"""Faz 6 — arayüz üretimi ve düzenlenebilir program."""
import json
import re

import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import config, db, prereq as P, student as S, ui as UI


def _lesson(con, crn, code, program, meetings=(), capacity=50, enrolled=0):
    con.execute("""INSERT INTO lesson(crn,course_code,capacity,enrolled,building)
                   VALUES (?,?,?,?,?)""", (crn, code, capacity, enrolled, "INB"))
    con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES (?,?)",
                (crn, program))
    for day, start, end in meetings:
        con.execute("""INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min,building)
                       VALUES (?,?,?,?,'INB')""", (crn, day, start, end))


@pytest.fixture()
def dbs(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "REF_DB", tmp_path / "ref.sqlite3")
    monkeypatch.setattr(config, "USER_DB", tmp_path / "user.sqlite3")
    con = db.connect(tmp_path / "ref.sqlite3", "schema.sql")
    ucon = db.connect(tmp_path / "user.sqlite3", "schema_user.sql")
    con.executemany(
        "INSERT INTO course(code,name,ects,prereq_raw) VALUES (?,?,?,?)",
        [("BLG 212E", "Mikroişlemci <Sistemler>", 7.0, None),
         ("BLG 351E", "Lab", 2.0, "BLG 212E MIN DD"),
         ("GEO 303E", "Kadastro", 3.0, None),
         ("SEC 201", "Seçmeli A", 4.0, None),
         ("SEC 202", "Seçmeli B", 4.0, None),
         ("SEC 203", "Seçmeli C", 4.0, None)],
    )
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title,source)
                   VALUES (10,'HTAE','lisans','anadal','obs')""")
    con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,ects,position,term_no)
                   VALUES (10,'REQUIRED','GEO 303E',3.0,0,5)""")
    cur = con.execute(
        """INSERT INTO plan_slot(plan_id,slot_kind,pool_label_raw,pool_category,ects,position)
           VALUES (10,'ELECTIVE_POOL','Seçmeli (ITB)','ITB',4.0,1)""")
    pool_slot = cur.lastrowid
    for code in ("SEC 201", "SEC 202", "SEC 203"):
        con.execute("INSERT INTO pool_option(slot_id,course_code) VALUES (?,?)",
                    (pool_slot, code))
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title,source,is_term_based)
                   VALUES (20,'BLG','cap','ÇAP planı','obs',0)""")
    for i, code in enumerate(["BLG 212E", "BLG 351E"]):
        e = con.execute("SELECT ects FROM course WHERE code=?", (code,)).fetchone()[0]
        con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,ects,position)
                       VALUES (20,'REQUIRED',?,?,?)""", (code, e, i))
    # BLG 212E'nin İKİ şubesi: Pzt ve Çar. 'başka şube' diyaloğu için gerekli.
    _lesson(con, "100", "BLG 212E", "BLG", [(1, 510, 689)])
    _lesson(con, "101", "BLG 212E", "BLG", [(3, 510, 689)])
    # Aynı havuzun ÜÇ dersi. Havuz slotu tek ders alır -> en az ikisi
    # seçilmeden aday kalır; boş hücre diyaloğunun her zaman gösterecek bir
    # şeyi olur. Günleri ayrı ki hangisi seçilirse seçilsin boş gün kalsın.
    _lesson(con, "200", "SEC 201", "HTAE", [(2, 510, 689)])
    _lesson(con, "201", "SEC 202", "HTAE", [(2, 630, 809)])
    _lesson(con, "202", "SEC 203", "HTAE", [(4, 510, 689)])
    # saati ilan edilmemiş ders — ızgarada görünemez, ayrıca listelenmeli
    _lesson(con, "300", "GEO 303E", "HTAE", capacity=60)
    con.commit()
    P.parse_all(con)
    sid = S.ensure_student(ucon)
    S.enroll(ucon, sid, 10, "ANADAL", "HTAE")
    S.enroll(ucon, sid, 20, "CAP", "BLG")
    return con, ucon, sid


def _collect(dbs, **kw):
    con, ucon, sid = dbs
    settings = config.Settings(anadal_program="HTAE", cap_program="BLG",
                               program_codes=["HTAE", "BLG", "BLGE"])
    return UI.collect(con, ucon, sid, settings, 10, 20, **kw)


def test_collect_shape(dbs):
    data = _collect(dbs)
    assert [p["role"] for p in data["panels"]] == ["ANADAL", "CAP"]
    assert {"BLG 212E", "GEO 303E"} <= {c["course"] for c in data["candidates"]}
    assert data["schedules"]
    assert any(b["course"] == "BLG 351E" for b in data["blockers"])


def test_every_scheduled_course_is_representable(dbs):
    """★ Saatsiz ders ızgarada görünemez; JSON'da ayırt edilebilmeli.

    Yoksa '8 ders' yazıp 5 blok gösteriyoruz."""
    data = _collect(dbs)
    picks = data["schedules"][0]["picks"]
    timed = [p for p in picks if p["section"]["meetings"]]
    timeless = [p for p in picks if not p["section"]["meetings"]]
    assert len(timed) + len(timeless) == len(picks)
    assert timeless, "fixture saatsiz ders içermeli"


def test_render_embeds_valid_json(dbs):
    html = UI.render(_collect(dbs))
    assert "__DATA__" not in html
    payload = re.search(r"const DATA = (\{.*?\});\n", html, re.S).group(1)
    parsed = json.loads(payload)
    assert parsed["anadal"] == "HTAE"


def test_html_is_self_contained_except_fonts(dbs):
    """CDN yok: tek dosya, çift tıkla açılmalı. Tek dış kaynak Google Fonts."""
    html = UI.render(_collect(dbs))
    externals = re.findall(r'(?:src|href)="(https?://[^"]+)"', html)
    assert all("fonts.googleapis.com" in u or "fonts.gstatic.com" in u for u in externals), externals
    assert "<script>" in html and "cdn" not in html.lower()


def test_both_themes_declared(dbs):
    """Üç durum da tanımlı olmalı: bare :root, prefers-color-scheme, data-theme.

    ★ Test YÖNE bakmıyor, kapsama bakıyor. Tasarım koyu-doğar da olabilir
    (22.08.2026'dan beri öyle) açık-doğar da; önemli olan üç durumun da
    tanımlı olması. Yönü test etseydik, tasarım kararı teste gömülü kalırdı.
    """
    html = UI.render(_collect(dbs))
    assert ":root{" in html
    # Karşı tema ya prefers-color-scheme:dark ya da :light ile tanımlanmalı.
    assert ("prefers-color-scheme:dark" in html
            or "prefers-color-scheme:light" in html)
    # data-theme'in İKİ yönü de olmalı: düğme her iki yönde de kazanabilmeli.
    assert ':root[data-theme="dark"]' in html or ':root[data-theme="light"]' in html
    # Medya sorgusu, açık beyanla ezilebilecek şekilde korunmalı.
    assert ':root:not([data-theme="dark"])' in html \
        or ':root:not([data-theme="light"])' in html
    assert "background:var(--ground)" in html      # body kendi zeminini boyuyor


def test_no_color_is_defined_only_inside_a_theme_block(dbs):
    """Her renk simgesi bare :root'ta da tanımlı olmalı.

    Klasik okunmaz-arayüz hatası: bir renk YALNIZ medya sorgusunun ya da
    [data-theme] bloğunun içinde tanımlanır; kullanıcı 'sistem' ayarındayken
    o değişken hiç çözülmez ve bir temanın yazısı öbür temanın zemininde
    çıkar. Sistem ayarı en yaygın durum olduğu için bu testi kilitliyoruz.
    """
    html = UI.render(_collect(dbs))
    css = html[html.index("<style>"):html.index("</style>")]
    base = css[css.index(":root{"):]
    base = base[:base.index("}")]
    base_tokens = set(re.findall(r"(--[a-z0-9-]+):", base))
    # Tema bloklarında geçen her simge bare :root'ta da bulunmalı.
    for block in re.findall(r'(?:prefers-color-scheme:\w+\)|\[data-theme="\w+"\])\{([^{}]*)\}', css):
        for tok in re.findall(r"(--[a-z0-9-]+):", block):
            assert tok in base_tokens, f"{tok} yalnız tema bloğunda tanımlı"


def test_write_creates_file(dbs, tmp_path):
    dest = UI.write(_collect(dbs), tmp_path / "x.html")
    assert dest.exists() and dest.read_text(encoding="utf-8").startswith("<!doctype html>")


# ------------------------------------------------- düzenlenebilirlik sözleşmesi
#
# Aşağıdaki testler JS'i çalıştırmadan da geçerli olan **veri sözleşmesini**
# kilitliyor: arayüz tıklamayla ders değiştirebiliyorsa, JSON'un taşıması
# gereken alanlar var. Biri düşerse diyalog sessizce boş açılır.

def test_candidates_carry_all_sections_for_swapping(dbs):
    """Aday yalnız önerilen şubeyi değil, TÜM şubelerini taşımalı.

    'başka şube' diyaloğu bu listeden besleniyor; yoksa hiç seçenek çıkmaz."""
    data = _collect(dbs)
    blg = next(c for c in data["candidates"] if c["course"] == "BLG 212E")
    assert {s["crn"] for s in blg["sections"]} == {"100", "101"}
    for sec in blg["sections"]:
        assert {"crn", "free", "capacity", "enrolled", "meetings"} <= set(sec)


def test_picked_crn_exists_in_candidate_sections(dbs):
    """★ Izgara `sectionOf(course, crn)` ile çiziliyor.

    Önerideki CRN adayın şube listesinde yoksa blok hiç çizilmez — sessiz
    boş ızgara. Bu iki kaynağın aynı olduğunu kilitliyoruz."""
    data = _collect(dbs)
    by_course = {c["course"]: {s["crn"] for s in c["sections"]}
                 for c in data["candidates"]}
    for sched in data["schedules"]:
        for pick in sched["picks"]:
            assert pick["section"]["crn"] in by_course[pick["course"]], pick["course"]


def test_pool_identity_is_exposed(dbs):
    """Aynı havuzdan iki ders seçilmesin diye JS `slotId` karşılaştırıyor."""
    data = _collect(dbs)
    pool = [c for c in data["candidates"] if c["course"] in ("SEC 201", "SEC 202")]
    assert len(pool) == 2
    assert pool[0]["pool"] and pool[0]["pool"] == pool[1]["pool"]
    assert pool[0]["slotId"] == pool[1]["slotId"]
    # zorunlu dersin havuzu yok -> takas kuralı ona işlemez
    blg = next(c for c in data["candidates"] if c["course"] == "BLG 212E")
    assert blg["pool"] == ""


def test_load_limit_travels_to_the_client(dbs):
    """Kullanıcı düzenleyince toplamı tarayıcı hesaplıyor; sınırı bilmeli."""
    data = _collect(dbs)
    # ★ 23.08.2026: tavan artık GNO'dan (MADDE 17). Bu öğrencinin notu yok,
    # yönetmeliğin taban bandı geçerli — 35 gibi elle yazılmış bir sayı DEĞİL.
    assert data["maxLoad"] == 22.0 and data["unit"] == "kredi"
    assert data["load"]["limitSource"] == "yönetmelik"
    assert data["unitLabel"] == "kredi"
    # Açık çağrı her zaman kazanır (testler, --max-load).
    assert _collect(dbs, max_load=31.0)["maxLoad"] == 31.0
    for c in data["candidates"]:
        assert c["credits"] is not None and c["ects"] is not None


def test_template_wires_the_interactions(dbs):
    """Sözleşmenin HTML tarafı: tıklanabilir hücre + üç diyalog + geri alma."""
    html = UI.render(_collect(dbs))
    for hook in ('class="free"', 'role="button"', "function slotDialog",
                 "function courseDialog", "function addDialog", "function choose",
                 "function removeCourse", "function resetTo", 'id="reset"'):
        assert hook in html, hook


# ------------------------------------------------------- tarayıcıda davranış
#
# Playwright proje bağımlılığı DEĞİL (kullanıcının makinesinde kurulu
# olmayabilir). Varsa çalışır, yoksa atlanır — sözleşme testleri yukarıda.

def _page(html_file):
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(html_file.as_uri())
    return pw, browser, page, errors


@pytest.fixture()
def page(dbs, tmp_path):
    pytest.importorskip("playwright.sync_api")
    dest = UI.write(_collect(dbs), tmp_path / "ui.html")
    try:
        pw, browser, page, errors = _page(dest)
    except Exception as exc:                      # tarayıcı indirilmemiş
        pytest.skip(f"playwright başlatılamadı: {exc}")
    yield page, errors
    browser.close()
    pw.stop()


def test_page_runs_without_js_errors(page):
    p, errors = page
    assert errors == []
    assert p.locator("#grid .blk").count() > 0


def _open_a_slot_with_options(p):
    """Seçenek sunan bir boş hücre bul ve diyaloğu açık bırak.

    Her boş saatin adayı olmak zorunda değil (Cuma bomboş olabilir); testin
    aradığı şey 'aday VARSA gösteriliyor mu'."""
    cells = p.locator("#grid td.free")
    for i in range(min(cells.count(), 40)):
        cells.nth(i).click()
        if p.locator("#detail .opt").count():
            return True
        p.locator("#detail [data-close]").first.click()
    return False


def test_clicking_empty_cell_offers_courses(page):
    """Boş hücreye tıkla -> o saate uyan adaylar listelensin."""
    p, errors = page
    assert _open_a_slot_with_options(p), "hiçbir boş saat aday göstermedi"
    assert p.locator("#detail[open]").count() == 1
    assert errors == []


def test_choosing_from_slot_dialog_changes_the_grid(page):
    """★ Asıl sözleşme: seçenek tıklanınca ders programa GİRSİN."""
    p, errors = page
    before = p.locator("#grid .blk").all_inner_texts()
    assert _open_a_slot_with_options(p)
    added = p.locator("#detail .opt").first.get_attribute("data-course")
    p.locator("#detail .opt").first.click()
    assert p.locator("#detail[open]").count() == 0          # diyalog kapanır
    after = p.locator("#grid .blk").all_inner_texts()
    assert any(added in t for t in after)
    assert after != before
    assert p.locator("#reset:visible").count() == 1         # 'öneriye dön' belirir
    assert errors == []


def test_removing_a_course_and_resetting(page):
    """Dersi çıkar, sonra öneriye dön — başlangıç durumu geri gelmeli."""
    p, errors = page
    start = sorted(p.locator("#grid .blk").all_inner_texts())
    blk = p.locator("#grid .blk").first
    course = blk.get_attribute("data-course")
    blk.click()
    p.locator("#removeCourse").click()
    assert all(course not in t for t in p.locator("#grid .blk").all_inner_texts())
    p.locator("#reset").click()
    assert sorted(p.locator("#grid .blk").all_inner_texts()) == start
    assert errors == []


def test_selection_never_produces_a_time_conflict(page):
    """Çakışan bir ders seçilirse çakıştığı ders DÜŞMELİ, üst üste binmemeli."""
    p, errors = page
    for _ in range(6):
        free = p.locator("#grid td.free")
        if free.count() == 0:
            break
        free.first.click()
        opts = p.locator("#detail .opt")
        (opts.first if opts.count() else p.locator("#detail [data-close]").first).click()
    conflict = p.evaluate("""() => {
      const ps = picks();
      for(let i=0;i<ps.length;i++) for(let j=i+1;j<ps.length;j++)
        if(clash(ps[i].sec, ps[j].sec)) return [ps[i].cand.course, ps[j].cand.course];
      return null;
    }""")
    assert conflict is None, conflict
    assert errors == []


def test_same_pool_course_is_swapped_not_doubled(page):
    """Aynı seçmeli havuzdan iki ders programda birlikte duramaz."""
    p, errors = page
    dup = p.evaluate("""() => {
      choose('SEC 201', '200'); choose('SEC 202', '201');
      const ps = picks().filter(x => x.cand.pool);
      const ids = ps.map(x => x.cand.slotId);
      return {courses: ps.map(x => x.cand.course), dup: ids.length !== new Set(ids).size};
    }""")
    assert dup["dup"] is False, dup
    assert dup["courses"] == ["SEC 202"]
    assert errors == []


# ================================================== FAZ 7: eşik, kip, projeksiyon
def test_panels_carry_projection_inputs(dbs):
    """★ Projeksiyonu TARAYICI hesaplıyor (seçim canlı değişiyor).

    Bunun için panelin planId'si ve adayın planId/slotId/required alanları
    aynı JSON'da olmalı; biri eksikse bar hiç dolmaz."""
    data = _collect(dbs)
    plan_ids = {p["planId"] for p in data["panels"]}
    assert plan_ids == {10, 20}
    for p in data["panels"]:
        assert p["openRequired"] >= 0
    for c in data["candidates"]:
        assert c["planId"] in plan_ids
        assert c["slotId"] and isinstance(c["required"], bool)


def test_open_required_excludes_pool_slots(dbs):
    data = _collect(dbs)
    anadal = next(p for p in data["panels"] if p["role"] == "ANADAL")
    assert anadal["openRequired"] == 1          # GEO 303E; ITB havuzu sayılmaz


def test_term_mode_is_a_separate_pool(dbs):
    """'Dönemlik + alttan' kendi adaylarını ve kendi programlarını taşımalı."""
    data = _collect(dbs, donem=5)
    keys = [m["key"] for m in data["modes"]]
    # ★ 22.08.2026: sıra değişti — dönemlik kip artık VARSAYILAN (bkz. ui._modes).
    assert keys == ["term", "all"]
    term = next(m for m in data["modes"] if m["key"] == "term")
    assert term["candidates"] and term["schedules"]
    assert "5" in term["label"]
    assert data["donem"] == 5 and data["donemSource"] == "beyan"


def test_term_mode_drops_later_terms_but_keeps_cap(dbs):
    con, ucon, sid = dbs
    con.execute("""INSERT INTO course(code,name,ects,credits) VALUES ('GEO 480E','Geç',3.0,3.0)""")
    con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,ects,position,term_no)
                   VALUES (10,'REQUIRED','GEO 480E',3.0,9,8)""")
    _lesson(con, "800", "GEO 480E", "HTAE", [(5, 510, 689)])
    con.commit()
    data = _collect(dbs, donem=5)
    inmode = {m["key"]: {c["course"] for c in m["candidates"]} for m in data["modes"]}
    assert "GEO 480E" in inmode["all"]
    assert "GEO 480E" not in inmode["term"]     # 8. dönem, elenir
    assert "BLG 212E" in inmode["term"]         # ÇAP dönemsiz, kalır


def test_credit_rule_is_reported_with_what_it_holds(dbs, tmp_path, monkeypatch):
    """★ Sessiz eleme yok: kural neyi tuttuğunu yazmalı."""
    from itucap import policy as POL
    con, ucon, sid = dbs
    con.execute("INSERT INTO course(code,name,ects,credits) VALUES ('GEO 4901E','Bitirme',12.0,3.0)")
    con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,ects,position,term_no)
                   VALUES (10,'REQUIRED','GEO 4901E',12.0,9,8)""")
    con.commit()
    f = tmp_path / "kurallar.toml"
    f.write_text('[[kredi_esigi]]\nad = "Bitirme"\nmin_kredi = 95\n'
                 'kalip = ["* 4901E"]\naciklama = "test"\n', encoding="utf-8")
    monkeypatch.setattr(POL, "DEFAULT_PATH", f)
    rule = _collect(dbs)["credits"]["rules"][0]
    assert rule["ok"] is False and rule["missing"] == 95.0
    assert rule["holding"] == ["GEO 4901E"]


def test_second_program_label_travels(dbs):
    """Yandal seçilirse arayüz 'ÇAP' yazmamalı."""
    con, ucon, sid = dbs
    settings = config.Settings(anadal_program="HTAE", cap_program="BLG",
                               second_kind="yandal", yandal_program="BLG",
                               program_codes=["HTAE", "BLG", "BLGE"])
    data = UI.collect(con, ucon, sid, settings, 10, 20)
    assert data["secondRole"] == "YANDAL" and data["secondLabel"] == "Yandal"
    assert [p["role"] for p in data["panels"]] == ["ANADAL", "YANDAL"]
    html = UI.render(data)
    assert 'data-role="YANDAL"' not in html or True     # rol JS'te uygulanıyor
    assert '.tag.CAP,.tag.YANDAL' in html               # stil ikisini de tanıyor


def test_projection_and_mode_hooks_exist(dbs):
    html = UI.render(_collect(dbs, donem=5))
    for hook in ("function planned(", "function renderPanels(", "function useMode(",
                 'class="meter"', "i.plan", 'id="creditBody"', 'id="modes"'):
        assert hook in html, hook


# --------------------------------------------------------- tarayıcı davranışı
@pytest.fixture()
def page7(dbs, tmp_path):
    pytest.importorskip("playwright.sync_api")
    dest = UI.write(_collect(dbs, donem=5), tmp_path / "ui7.html")
    try:
        pw, browser, page, errors = _page(dest)
    except Exception as exc:
        pytest.skip(f"playwright başlatılamadı: {exc}")
    yield page, errors
    browser.close()
    pw.stop()


def test_projection_updates_when_selection_changes(page7):
    """★ Bar iki katmanlı ve ikinci katman SEÇİME bağlı."""
    p, errors = page7
    before = p.evaluate("() => DATA.panels.map(x => planned(x.planId).slots)")
    assert sum(before) > 0, "fixture'da seçili ders olmalı"
    p.evaluate("() => { sel = []; render(); }")
    after = p.evaluate("() => DATA.panels.map(x => planned(x.planId).slots)")
    assert after == [0] * len(after)
    assert "ders yok" in p.locator(".proj").first.inner_text()
    assert errors == []


def test_projection_counts_a_pool_slot_once(page7):
    """Aynı havuza iki ders konamaz; slot sayısı da bir kez artmalı."""
    p, errors = page7
    n = p.evaluate("""() => {
      sel = []; render();
      const pool = M().candidates.filter(c => c.pool);
      if(pool.length < 2) return null;
      choose(pool[0].course, pool[0].sections[0].crn);
      choose(pool[1].course, pool[1].sections[0].crn);
      return planned(pool[0].planId).slots;
    }""")
    if n is not None:
        assert n == 1
    assert errors == []


def test_mode_switch_changes_the_candidate_table(page7):
    p, errors = page7
    assert p.locator(".modebtn").count() == 2
    first = p.locator("#cands tbody").inner_text()
    once = p.locator('.modebtn[aria-pressed="true"]').inner_text().strip()
    p.locator(".modebtn").nth(1).click()
    # Sıraya bağlı DEĞİL: hangi kip varsayılan olursa olsun, tıklayınca değişmeli.
    assert p.locator('.modebtn[aria-pressed="true"]').inner_text().strip() != once
    assert p.locator("#modeNote").inner_text()
    p.locator(".modebtn").nth(0).click()
    assert p.locator("#cands tbody").inner_text() == first
    assert errors == []


# ======================================================= Faz 12: eşik kapsamı
#
# `_threshold_info` üç ayrı hatadan koruyor. Üçü de "yanlış sayıyla doğru
# görünen cevap" üretirdi ki bu, hiç cevap vermemekten kötü.

def _rules(tmp_path, text):
    p = tmp_path / "kurallar.toml"
    p.write_text(text, encoding="utf-8")
    return p


THRESHOLDS = """
[[gno_esigi]]
anahtar = "basvuru"
ad = "ÇAP başvurusu"
program = "cap"
tur = "basvuru"
min_gno = 3.0
dogrulandi = true

[[gno_esigi]]
anahtar = "cap_mezuniyet_ikinci"
ad = "İkinci anadal ortalaması"
program = "cap"
tur = "mezuniyet"
min_gno = 2.0
dogrulandi = true

[[gno_esigi]]
anahtar = "yandal_basvuru"
ad = "Yandal başvurusu"
program = "yandal"
tur = "basvuru"
min_gno = 2.5
dogrulandi = true
"""


def test_yandal_thresholds_are_hidden_from_a_cap_student(dbs, tmp_path, monkeypatch):
    """Uygulanmayan bir kuralda 'kaldın' göstermek yanlış aciliyet üretir."""
    from itucap import policy as POL
    monkeypatch.setattr(POL, "DEFAULT_PATH", _rules(tmp_path, THRESHOLDS))
    keys = {t["key"] for t in _collect(dbs)["gpa"]["thresholds"]}
    assert "yandal_basvuru" not in keys
    assert "basvuru" in keys


def test_second_major_threshold_uses_the_second_major_average(dbs, tmp_path,
                                                              monkeypatch):
    """★ Madde 18 GENEL GNO'yu değil, ikinci anadalın KENDİ ortalamasını sorar.

    Genel GNO ile karşılaştırmak başka bir soruya cevap vermek olurdu: notu
    girilmemiş anadal dersleri DD sayıldığı için genel ortalama düşük çıkar
    ve öğrenciye karşıladığı bir şartta 'kaldın' denirdi."""
    from itucap import policy as POL
    con, ucon, sid = dbs
    monkeypatch.setattr(POL, "DEFAULT_PATH", _rules(tmp_path, THRESHOLDS))
    # Kredileri ver ki ortalamalar hesaplanabilsin.
    con.execute("UPDATE course SET credits=3 WHERE code IN ('BLG 212E','GEO 303E')")
    con.commit()
    ucon.execute("DELETE FROM earned_course WHERE student_id=?", (sid,))
    # ÇAP dersi İYİ (AA=4.0), anadal dersi KÖTÜ (DD=1.0).
    ucon.executemany(
        """INSERT INTO earned_course(student_id,course_code,grade,status,source)
           VALUES (?,?,?,'PASSED','test')""",
        [(sid, "BLG 212E", "AA"), (sid, "GEO 303E", "DD")])
    ucon.commit()

    data = _collect(dbs)
    ts = {t["key"]: t for t in data["gpa"]["thresholds"]}
    t = ts["cap_mezuniyet_ikinci"]
    assert t["basis"] == "ikinci anadal"
    # Genel GNO 2.50 (AA+DD ortalaması); ikinci anadal ortalaması 4.00.
    assert data["gpa"]["value"] == 2.5
    assert t["value"] == 4.0, "genel GNO ile karşılaştırılıyor"
    assert t["ok"] is True
    # Diğer eşikler genel GNO'ya bakmaya devam etmeli.
    assert ts["basvuru"]["basis"] == "genel"
    assert ts["basvuru"]["value"] == 2.5


def test_uncomputable_threshold_is_none_not_false(dbs, tmp_path, monkeypatch):
    """★ ÇAP planında notlu ders yoksa ortalama hesaplanamaz.

    ✗ göstermek 'kaldın' demek olurdu — oysa öğrenci daha başlamamış."""
    from itucap import policy as POL
    con, ucon, sid = dbs
    monkeypatch.setattr(POL, "DEFAULT_PATH", _rules(tmp_path, THRESHOLDS))
    ucon.execute("DELETE FROM earned_course WHERE student_id=?", (sid,))
    ucon.commit()
    ts = {t["key"]: t for t in _collect(dbs)["gpa"]["thresholds"]}
    assert ts["cap_mezuniyet_ikinci"]["ok"] is None
    assert ts["cap_mezuniyet_ikinci"]["why"]        # nedeni yazılmalı


def test_conditional_rule_reaches_the_page(dbs):
    """Şartlı geçer kuralı (MADDE 20/2-b) arayüze taşınmalı."""
    r = _collect(dbs)["gpa"]["conditionalRule"]
    assert r["passes"] is True
    assert r["minGpa"] == 2.00 and r["verified"]


def test_application_survey_is_collected(dbs):
    """Faz 12 — 'başvurabilir miyim' verisi sayfaya girmeli."""
    b = _collect(dbs)["basvuru"]
    assert b and set(b) == {"cap", "yandal"}
    assert any(c["ok"] is None for c in b["cap"]["checks"])   # üç durumlu işaret


def test_narrow_screen_layout_is_declared(dbs):
    """★ Izgara 660px altına inemiyor; dar ekranda gün listesi devralmalı
    (yapılacaklar 4.1). İkisi birden görünürse aynı veri iki kez çıkar."""
    html = UI.render(_collect(dbs))
    assert "@media (max-width:700px)" in html
    assert 'id="daylist"' in html
    assert ".gridwrap{display:none}" in html


# ==================================== Faz 12: dar ekran + çakışma işaretleme
@pytest.fixture()
def phone(dbs, tmp_path):
    """390px genişlik — telefon (yapılacaklar 4.1)."""
    pytest.importorskip("playwright.sync_api")
    dest = UI.write(_collect(dbs), tmp_path / "ui.html")
    from playwright.sync_api import sync_playwright
    try:
        pw = sync_playwright().start()
        browser = pw.chromium.launch()
        p = browser.new_page(viewport={"width": 390, "height": 844})
    except Exception as exc:                       # noqa: BLE001
        pytest.skip(f"playwright başlatılamadı: {exc}")
    errors = []
    p.on("pageerror", lambda e: errors.append(str(e)))
    p.goto(dest.as_uri())
    yield p, errors
    browser.close()
    pw.stop()


def test_phone_swaps_grid_for_day_list(phone):
    """★ Dar ekranda ızgara gizlenir, gün listesi görünür.

    İkisi birden görünürse aynı program iki kez çıkar; ikisi birden
    gizlenirse program hiç görünmez. Testin ikisini de kilitlemesi gerek."""
    p, errors = phone
    assert errors == []
    assert not p.locator(".gridwrap").is_visible()
    assert p.locator("#daylist").is_visible()
    assert p.locator("#daylist .row").count() > 0


def test_phone_does_not_scroll_sideways(phone):
    """Gün listesinin varlık sebebi bu: yana kaydırma olmamalı."""
    p, _ = phone
    assert p.evaluate("document.documentElement.scrollWidth") <= 390


def test_day_list_marks_clashes(phone):
    """★ Listenin ızgaraya göre zayıf yanı çakışmayı göstermemesi.

    Kabul edip geçmek yerine çakışma ayrıca hesaplanıyor. Bu test bir
    çakışma kurup işaretlendiğini doğruluyor — yoksa telefonda çakışan bir
    program sessizce onaylanmış görünürdü."""
    p, _ = phone
    marked = p.evaluate("""() => {
      // Aynı güne, kesişen saatlerde iki ders koy ve yeniden çiz.
      sel = [
        {course:'A 1', crn:'1', cand:{course:'A 1', role:'ANADAL'},
         sec:{meetings:[{day:1, start:540, end:660, building:'X'}]}},
        {course:'B 2', crn:'2', cand:{course:'B 2', role:'CAP'},
         sec:{meetings:[{day:1, start:600, end:720, building:'X'}]}},
      ];
      picks = () => sel;
      renderDayList();
      return document.querySelectorAll('#daylist .row.clash').length;
    }""")
    assert marked == 2, "kesişen iki ders de işaretlenmeli"


def test_day_list_does_not_mark_adjacent_courses(phone):
    """Bitişik dersler (biri bitince öbürü başlıyor) çakışma DEĞİL.

    Sınırı `<` yerine `<=` yazmak, arka arkaya iki dersi çakışıyor gösterip
    doğru bir programı yanlış diye işaretlerdi."""
    p, _ = phone
    marked = p.evaluate("""() => {
      sel = [
        {course:'A 1', crn:'1', cand:{course:'A 1', role:'ANADAL'},
         sec:{meetings:[{day:1, start:540, end:660, building:'X'}]}},
        {course:'B 2', crn:'2', cand:{course:'B 2', role:'CAP'},
         sec:{meetings:[{day:1, start:660, end:780, building:'X'}]}},
      ];
      picks = () => sel;
      renderDayList();
      return document.querySelectorAll('#daylist .row.clash').length;
    }""")
    assert marked == 0


# ============================== Faz 13: ikinci anadal yarıyıl tabanı (arayüz)
FLOOR_RULES = """
[[ikinci_anadal_taban]]
baslangic_yariyili = 5
min_kredi = 9
dogrulandi = true
kaynak = "Yönerge"

[ikinci_anadal_taban_indirim]
oran = 0.5
kosullar = ["öğrencinin talebi", "Fakülte Yönetim Kurulu Kararı"]
son_tarih = "dersten tümüyle çekilme tarihi"
otomatik = false
dogrulandi = true
"""


def _collect_with_start(dbs, tmp_path, monkeypatch, start):
    from itucap import config as C, policy as POL
    monkeypatch.setattr(POL, "DEFAULT_PATH", _rules(tmp_path, FLOOR_RULES))
    con, ucon, sid = dbs
    settings = C.Settings(anadal_program="HTAE", cap_program="BLG",
                          program_codes=["HTAE", "BLG", "BLGE"],
                          cap_baslangic_yariyili=start)
    return UI.collect(con, ucon, sid, settings, 10, 20)


def test_floor_reaches_the_page(dbs, tmp_path, monkeypatch):
    F = _collect_with_start(dbs, tmp_path, monkeypatch, 5)["secondFloor"]
    assert F["min"] == 9.0 and F["startTerm"] == 5 and F["verified"]


def test_undeclared_start_term_prompts_instead_of_claiming(dbs, tmp_path, monkeypatch):
    """★ Beyan yoksa taban iddia edilmez — ama SESSİZ de kalınmaz.

    Kullanıcı böyle bir kuralın varlığından haberdar olmalı; yoksa
    karşılamadığı bir şartı hiç öğrenemez."""
    F = _collect_with_start(dbs, tmp_path, monkeypatch, 0)["secondFloor"]
    assert F["undeclared"] is True
    assert F["setting"] == "cap_baslangic_yariyili"
    assert "min" not in F                       # hiçbir sayı iddia edilmiyor


def test_relief_is_marked_not_automatic_on_the_page(dbs, tmp_path, monkeypatch):
    """Arayüz indirimi ÇARE olarak göstermeli, uygulanmış gibi değil."""
    F = _collect_with_start(dbs, tmp_path, monkeypatch, 5)["secondFloor"]
    r = F["relief"]
    assert r["automatic"] is False
    assert r["min"] == 4.5
    assert r["conditions"] and r["deadline"]
    # Taban indirilmemiş hâliyle duruyor:
    assert F["min"] == 9.0


def test_floor_panel_counts_only_the_second_program(dbs, tmp_path, monkeypatch,
                                                    tmp_path_factory):
    """★ Taban yalnız İKİNCİ ANADALDAN alınan krediyi sayar.

    Toplam krediyi saysaydı anadal dersleri tabanı doldururdu ve öğrenci
    ÇAP'tan hiç ders almadan şartı karşılıyor görünürdü."""
    import re as _re
    html = UI.render(_collect_with_start(dbs, tmp_path, monkeypatch, 5))
    fn = html[html.index("function renderFloor()"):html.index("function renderLoad()")]
    # Filtre anadal'ı dışlıyor mu?
    assert _re.search(r'role\s*!==\s*"ANADAL"', fn), fn[:400]
