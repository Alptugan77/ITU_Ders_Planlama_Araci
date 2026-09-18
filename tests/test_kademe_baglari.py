"""Faz 16 — kademeler arası ÖNŞART BAĞLARI.

Kullanıcı isteği 22.08.2026: "çap kademelerini birbirine önşartla bağlı
olanları belli edecek şekilde olsun".

Kademe listesi zaten vardı ama hangi dersin hangisini açtığı GÖRÜNMÜYORDU:
'Kademe 1' yazıyordu, sebebi yazmıyordu. Burada iki katmanı da koruyoruz —
metin (kopyalanabilir, çizgi çizilmese de bilgi kaybolmaz) ve çizgiler.

★ Plan İÇİ ve plan DIŞI önşart ayrı gösterilir. Karıştırsaydık, anadalda çoktan
alınmış bir dersi 'ÇAP zincirinin parçası' sanardık.
"""
import json
import re

import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import config, db, prereq as P, student as S, ui as UI


@pytest.fixture()
def dbs(tmp_path, monkeypatch):
    """Üç kademeli küçük bir zincir: A → B → C, ayrıca plan DIŞI bir önşart."""
    monkeypatch.setattr(config, "REF_DB", tmp_path / "ref.sqlite3")
    monkeypatch.setattr(config, "USER_DB", tmp_path / "user.sqlite3")
    con = db.connect(tmp_path / "ref.sqlite3", "schema.sql")
    ucon = db.connect(tmp_path / "user.sqlite3", "schema_user.sql")
    con.executemany(
        "INSERT INTO course(code,name,ects,credits,prereq_raw) VALUES (?,?,?,?,?)",
        [("BLG 101E", "Giriş", 6.0, 3.0, None),
         ("BLG 201E", "Orta", 6.0, 3.0, "BLG 101E MIN DD"),
         ("BLG 301E", "İleri", 6.0, 3.0, "BLG 201E MIN DD"),
         # plan DIŞINDAN gelen önşart: MAT 103E ÇAP planında yok
         ("BLG 210E", "Yan dal", 5.0, 3.0, "MAT 103E MIN DD"),
         ("MAT 103E", "Matematik", 7.0, 4.0, None)],
    )
    con.execute("INSERT INTO plan(id,program_code,plan_type,title,source) "
                "VALUES (10,'HTAE','lisans','anadal','obs')")
    con.execute("INSERT INTO plan(id,program_code,plan_type,title,source,is_term_based) "
                "VALUES (20,'BLG','cap','ÇAP planı','obs',0)")
    for i, code in enumerate(["BLG 101E", "BLG 201E", "BLG 301E", "BLG 210E"]):
        con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,ects,credits,position)
                       VALUES (20,'REQUIRED',?,6.0,3.0,?)""", (code, i))
    con.commit()
    P.parse_all(con)
    sid = S.ensure_student(ucon)
    S.enroll(ucon, sid, 10, "ANADAL", "HTAE")
    S.enroll(ucon, sid, 20, "CAP", "BLG")
    return con, ucon, sid


def _collect(dbs):
    con, ucon, sid = dbs
    settings = config.Settings(anadal_program="HTAE", cap_program="BLG",
                               second_kind="cap",
                               program_codes=["HTAE", "BLG"])
    return UI.collect(con, ucon, sid, settings, 10, 20)


def _tiers(data, i=0):
    """★ 23.08.2026: kademeler artık PROGRAM BAŞINA gruplanıyor (ÇAP ve yandal
    aynı anda alınabildiği için). Bu testler tek ikinci programlı veriyle
    çalışıyor, ilk grubu alıyorlar."""
    return data["tierGroups"][i]["tiers"]


def _course(data, code):
    for t in _tiers(data):
        for c in t["courses"]:
            if c["course"] == code:
                return t["tier"], c
    raise AssertionError(f"{code} kademelerde yok")


# ------------------------------------------------------------------- veri
def test_kademeler_zinciri_yansitiyor(dbs):
    data = _collect(dbs)
    assert _course(data, "BLG 101E")[0] == 0
    assert _course(data, "BLG 201E")[0] == 1
    assert _course(data, "BLG 301E")[0] == 2


def test_her_ders_kendi_onsartini_tasiyor(dbs):
    """★ Asıl istek: bağ GÖRÜNÜR olsun."""
    data = _collect(dbs)
    assert _course(data, "BLG 201E")[1]["needs"] == ["BLG 101E"]
    assert _course(data, "BLG 301E")[1]["needs"] == ["BLG 201E"]
    assert _course(data, "BLG 101E")[1]["needs"] == []


def test_ters_yon_de_var(dbs):
    """'Bu dersi geçmezsem ne kilitli kalır' sorusu da cevaplanabilmeli."""
    data = _collect(dbs)
    assert _course(data, "BLG 101E")[1]["opens"] == ["BLG 201E"]
    assert _course(data, "BLG 301E")[1]["opens"] == []


def test_plan_disi_onsart_ayri_duruyor(dbs):
    """★ Plan dışı önşart, plan içi bağ gibi gösterilmemeli.

    Gösterseydik 'BLG 210E, MAT 103E'ye bağlı' diye bir ÇAP zinciri çizerdik;
    oysa MAT 103E anadal planının dersi ve çoktan alınmış olabilir."""
    _, c = _course(_collect(dbs), "BLG 210E")
    assert c["needs"] == []
    assert c["outside"] == ["MAT 103E"]


def test_kademe_0_gercekten_hemen_alinabilir(dbs):
    """Kademe 0 = plan içi önşartı olmayan. Testin anlamlı olduğunun kanıtı:
    zincirin ucundaki ders kademe 0 OLMAMALI."""
    data = _collect(dbs)
    kademe_sifir = {c["course"] for t in _tiers(data) if t["tier"] == 0
                    for c in t["courses"]}
    assert {"BLG 101E", "BLG 210E"} == kademe_sifir


# ----------------------------------------------------------------- arayüz
def test_sablon_bagi_ciziyor(dbs):
    html = UI.render(_collect(dbs))
    for parca in ("tierGroups", "tierStage", "tierLinks", "drawTierLinks", "tierChain",
                  "paintTierFocus", "<svg"):
        assert parca in html, parca


def test_veri_json_icinde(dbs):
    html = UI.render(_collect(dbs))
    payload = json.loads(re.search(r"const DATA = (\{.*?\});\n", html, re.S).group(1))
    assert any(c.get("needs")
               for g in payload["tierGroups"] for t in g["tiers"] for c in t["courses"])


# ------------------------------------------------- tarayıcıda gerçek çizim
@pytest.fixture()
def page(dbs, tmp_path):
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    dest = UI.write(_collect(dbs), tmp_path / "ui.html")
    try:
        pw = sync_playwright().start()
        browser = pw.chromium.launch()
        p = browser.new_page(viewport={"width": 1400, "height": 1200})
    except Exception as exc:                      # tarayıcı indirilmemiş
        pytest.skip(f"playwright başlatılamadı: {exc}")
    errors = []
    p.on("pageerror", lambda e: errors.append(str(e)))
    p.goto(dest.as_uri())
    # ⚠️ Faz 46: ray tek görünüm açıyor ve açılış görünümü haftalık program.
    # Kademeler bölümü DOM'da ama kapalı — testin ölçtüğü şey kademe
    # diyagramı, "hangi görünüm açık" değil.
    p.evaluate("() => gorunumAc('tierSection')")
    p.wait_for_timeout(120)
    yield p, errors
    browser.close()
    pw.stop()


def test_cizgiler_ciziliyor(page):
    """★ Çizgi SAYISI önşart sayısına eşit olmalı — 'svg var' yetmez.
    Her bağ İKİ yol: zemin kılıfı + çizgi (kesişimler okunsun diye)."""
    p, errors = page
    assert errors == []
    assert p.locator("#tierLinks0 path.line").count() == 2    # 101→201, 201→301
    assert p.locator("#tierLinks0 path.casing").count() == 2  # her çizginin kılıfı


def test_cizgi_dogru_dersleri_bagliyor(page):
    p, _ = page
    # data-a/data-b yalnız .line yollarında; kılıf salt görsel.
    baglar = {(el.get_attribute("data-a"), el.get_attribute("data-b"))
              for el in p.locator("#tierLinks0 path.line").all()}
    assert baglar == {("BLG 101E", "BLG 201E"), ("BLG 201E", "BLG 301E")}


def test_tiklayinca_yalniz_zincir_kaliyor(page):
    """Zincir = seçilenin ATALARI + TORUNLARI; ilgisiz ders sönümlenmeli."""
    p, errors = page
    p.locator('#tierStage0 li[data-c="BLG 201E"]').click()
    assert p.locator("#tierStage0.focus").count() == 1
    for kod in ("BLG 101E", "BLG 201E", "BLG 301E"):
        assert p.locator(f'#tierStage0 li[data-c="{kod}"].on').count() == 1
    assert p.locator('#tierStage0 li[data-c="BLG 210E"].on').count() == 0
    assert p.locator("#tierLinks0 path.on").count() == 2
    assert errors == []


def test_ikinci_tik_seçimi_kaldiriyor(page):
    p, _ = page
    hedef = p.locator('#tierStage0 li[data-c="BLG 201E"]')
    hedef.click()
    hedef.click()
    assert p.locator("#tierStage0.focus").count() == 0


def test_onsart_metni_kutuda_yaziyor(page):
    """Çizgi çizilemese bile bilgi kaybolmasın. Plan İÇİ önşart doğrudan
    ('önce …') yazılı; plan DIŞI önşart kompakt rozette ama kodları DOM'da
    ve rozete basınca AÇILIYOR — mobilde de erişilir (yalnız tooltip değil)."""
    p, _ = page
    # Plan içi önşart doğrudan görünür.
    assert "BLG 201E" in p.locator('#tierStage0 li[data-c="BLG 301E"]').inner_text()
    # Plan dışı önşart: rozet görünür, kod DOM'da (kaybolmadı), tık ile açılır.
    kutu = p.locator('#tierStage0 li[data-c="BLG 210E"]')
    rozet = kutu.locator(".dispre")
    assert "dış önşart" in kutu.inner_text()
    assert "MAT 103E" in kutu.inner_html()           # bilgi DOM'da, kaybolmadı
    assert rozet.get_attribute("aria-expanded") == "false"
    rozet.click()
    assert rozet.get_attribute("aria-expanded") == "true"
    assert "MAT 103E" in kutu.inner_text()           # dokununca görünür oluyor


def test_dis_onsart_rozeti_dersi_kilitlemiyor(page):
    """Rozete basmak zinciri KİLİTLEMEZ (stopPropagation); yalnız kodları
    açar. (Üstüne gelince önizleme çıkabilir ama fare çekilince kalmaz —
    kilit çıksaydı kalırdı.)"""
    p, _ = page
    p.locator('#tierStage0 li[data-c="BLG 210E"] .dispre').click()
    p.mouse.move(0, 0)                               # hover önizlemesini kaldır
    p.wait_for_timeout(150)
    assert p.locator("#tierStage0.focus").count() == 0


def test_cizgiler_kutularin_ustune_biniyor_mu(page):
    """Çizgi katmanı sahnenin TAMAMINI kaplamalı; yoksa uzun listede kesilir."""
    p, _ = page
    svg = p.locator("#tierLinks0").bounding_box()
    stage = p.locator("#tierStage0").bounding_box()
    assert svg["width"] >= stage["width"] - 1
    assert svg["height"] >= stage["height"] - 1
