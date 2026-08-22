"""Faz 14 — statik site (GitHub Pages).

Motor tarayıcıda Pyodide ile çalışıyor; JS'e ÇEVRİLMİYOR. Bu dosya iki şeyi
kilitliyor:

1. **Motor tarayıcıya taşınabilir kalmalı.** Tek bir `import httpx` motorun
   web sürümünü kırar ve bunu ancak tarayıcıda fark ederiz.
2. **Yayınlanan katalog temiz olmalı.** Sızıntı dosya adında değil, dosyanın
   İÇİNDE olur — `.gitignore` böyle bir şeyi asla yakalayamaz.
"""
import gzip
import sqlite3
import sys

import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import config, db, ui as UI

sys.path.insert(0, str(config.ROOT / "tools"))


# --------------------------------------------- motor tarayıcıya taşınabilir mi
def test_engine_modules_have_no_scraping_dependencies():
    """★ Motorun web sürümünü kıran tek şey: tarama bağımlılığı.

    `httpx` ve `selectolax` Pyodide'de yok ve olmasına gerek de yok —
    tarama kullanıcının kendi makinesinde yapılıyor. Biri motora sızarsa
    site sessizce yüklenemez hâle gelir; burada erken yakalıyoruz.
    """
    import importlib

    import site_kur

    kirli = []
    for name in site_kur.ENGINE:
        if name == "__init__":
            continue
        before = set(sys.modules)
        importlib.import_module(f"itucap.{name}")
        yeni = {m.split(".")[0] for m in set(sys.modules) - before}
        kotu = yeni & {"httpx", "selectolax", "h11", "httpcore"}
        if kotu:
            kirli.append((name, sorted(kotu)))
    assert not kirli, f"motor modülleri tarama bağımlılığı çekiyor: {kirli}"


def test_engine_list_covers_what_server_needs():
    """`server.py` tarayıcıda kuruluyor; MODÜL SEVİYESİNDE içeri aldığı her
    şey site paketinde olmalı.

    Fonksiyon içindeki tembel importlar hariç: `refresh()` tarama yığınını
    öyle çağırıyor ve tarayıcıda hiç çalıştırılmıyor (bkz. `can_refresh`)."""
    import ast

    import site_kur

    src = (config.ROOT / "src" / "itucap" / "server.py").read_text(encoding="utf-8")
    agac = ast.parse(src)
    ic = set()
    for d in agac.body:                       # yalnız en üst seviye
        if isinstance(d, ast.ImportFrom) and d.level == 1:
            ic |= {a.name for a in d.names} if d.module is None else {d.module}
    eksik = {m for m in ic if m not in site_kur.ENGINE}
    assert not eksik, f"site paketinde eksik modül: {eksik}"


def test_refresh_fails_clearly_when_scraping_is_unavailable(monkeypatch):
    """★ Tarayıcıda "VERİYİ TAZELE" çalışamaz.

    Düzeltilmeden önce `ModuleNotFoundError: httpx` fırlıyordu — kullanıcının
    anlayamayacağı ve çözemeyeceği bir hata. Artık ne olduğunu söyleyen bir
    `ValueError` var ve arayüz düğmeyi hiç göstermiyor."""
    from itucap import server as SRV

    monkeypatch.setattr(SRV, "can_refresh", lambda: False)

    class Sahte:
        busy = False
        refresh = SRV.State.refresh

    with pytest.raises(ValueError) as hata:
        Sahte().refresh()
    assert "tazeleme" in str(hata.value).lower()
    assert "ModuleNotFound" not in str(hata.value)


def test_ui_hides_refresh_when_it_cannot_work():
    html = UI.render({}, deferred=True)
    assert "DATA.canRefresh === false" in html


# ----------------------------------------------------------- kabuk (deferred)
def test_deferred_shell_waits_for_data():
    """Kabuk kendi kendine `boot()` çağırmamalı — veri henüz yok.

    Çağırsaydı sayfa boş veriyle çizilir, sonra Pyodide gelince yeniden
    çizilirdi: kullanıcı bir anlığına 'hiç dersin yok' ekranı görürdü."""
    html = UI.render({}, deferred=True)
    assert "\nboot();\n" not in html
    assert "window.__ITUCAP_APPLY__" in html


def test_normal_render_still_boots():
    """`make ui` bozulmamalı: statik dosya kendi kendine açılmalı."""
    html = UI.render({"anadal": "X"})
    assert "\nboot();\n" in html
    assert "__ITUCAP_APPLY__" not in html


def test_api_can_be_routed_without_http():
    """★ Aynı şablon iki taşıyıcıda: HTTP ve tarayıcı içi Python.

    Kanca olmasaydı web sürümü şablonu kopyalamak zorunda kalırdı ve
    tasarım düzeltmeleri iki yerde ayrışırdı."""
    html = UI.render({}, deferred=True)
    assert "window.__ITUCAP_API__" in html


# ------------------------------------------------------- yayınlanan veri temiz
def _sandbox_ref(tmp_path):
    """Kişisel denklik beyanı İÇEREN bir katalog — sızıntı senaryosu."""
    con = db.connect(tmp_path / "reference.sqlite3", "schema.sql")
    con.execute("INSERT INTO course(code,name,credits) VALUES ('MAT 103E','Mat',4)")
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title,iteration)
                   VALUES (1,'BLG','cap','yeni','2020-2021 / Güz Dönemi Sonrası')""")
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title,iteration)
                   VALUES (2,'BLG','cap','eski','2010-2011 / Güz Dönemi Öncesi')""")
    con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,position)
                   VALUES (2,'REQUIRED','MAT 103E',0)""")
    con.execute("""INSERT INTO equivalence(id,target_course,applies_to_cap,
                       confidence,note_raw,source_url)
                   VALUES (1,'MAT 210E',1,'user_declared','BEYAN: GEO 220E',
                           '/home/birisi/CAP/config/denklikler.toml')""")
    con.execute("""INSERT INTO equivalence_source(equivalence_id,course_code,min_grade)
                   VALUES (1,'GEO 220E','DD')""")
    con.execute("""INSERT INTO equivalence(id,target_course,applies_to_cap,
                       confidence,note_raw) VALUES (2,'FIZ 101E',1,'official','resmi')""")
    con.commit()
    con.close()
    return tmp_path / "reference.sqlite3"


def test_prune_removes_personal_equivalences(tmp_path):
    """★★ 22.08.2026'da gerçekten olan sızıntı.

    `reference.sqlite3` "herkese açık katalog" diye tasarlandı ama
    `declared.apply()` kullanıcının KENDİ beyanlarını oraya yazıyor.
    Yayınlanınca "bu kişi GEO 220E aldı ve MAT 210E yerine saydırıyor"
    demek olur — hangi dersi aldığını da ne talep ettiğini de açık eder.
    """
    import site_kur

    dst = tmp_path / "web.sqlite3"
    stats = site_kur.prune(_sandbox_ref(tmp_path), dst)
    con = sqlite3.connect(dst)
    assert con.execute(
        "SELECT COUNT(*) FROM equivalence WHERE confidence='user_declared'"
    ).fetchone()[0] == 0
    assert stats["kisisel_denklik_silindi"] == 1
    # Kaynak satırları da gitmeli — yoksa hangi dersi aldığı yine okunur.
    assert con.execute("SELECT COUNT(*) FROM equivalence_source").fetchone()[0] == 0
    # RESMİ denklik kalmalı: o herkese ait müfredat bilgisi.
    assert con.execute(
        "SELECT COUNT(*) FROM equivalence WHERE confidence='official'").fetchone()[0] == 1


def test_prune_strips_local_paths(tmp_path):
    """Yerel dosya yolu kullanıcı adını sızdırır (/home/birisi/…)."""
    import site_kur

    dst = tmp_path / "web.sqlite3"
    site_kur.prune(_sandbox_ref(tmp_path), dst)
    con = sqlite3.connect(dst)
    kalan = con.execute(
        "SELECT COUNT(*) FROM equivalence WHERE source_url LIKE '/home/%'"
    ).fetchone()[0]
    assert kalan == 0


def test_prune_keeps_only_the_current_plan_iteration(tmp_path):
    """Yürürlükte olmayan iterasyon ziyaretçiye indirtilmemeli."""
    import site_kur

    dst = tmp_path / "web.sqlite3"
    site_kur.prune(_sandbox_ref(tmp_path), dst)
    con = sqlite3.connect(dst)
    kalan = [r[0] for r in con.execute("SELECT id FROM plan")]
    assert kalan == [1], "yalnız 'Sonrası' iterasyonu kalmalı"
    # Düşen planın slotları da gitmeli, yoksa yetim satır kalır.
    assert con.execute("SELECT COUNT(*) FROM plan_slot").fetchone()[0] == 0


def test_privacy_audit_catches_a_leaky_site(tmp_path, monkeypatch):
    """★ Denetim dosya ADINA değil İÇERİĞİNE bakmalı.

    Sızıntı `katalog.sqlite3.gz` gibi masum bir adın içindeydi."""
    import gizlilik_denetimi as GD

    site = tmp_path / "site"
    site.mkdir()
    ref = _sandbox_ref(tmp_path)
    (site / "katalog.sqlite3.gz").write_bytes(gzip.compress(ref.read_bytes()))
    monkeypatch.setattr(GD, "ROOT", tmp_path)
    sorunlar = GD.site_denetle()
    assert any("KİŞİSEL denklik" in s for s in sorunlar), sorunlar


def test_privacy_audit_passes_a_clean_site(tmp_path, monkeypatch):
    import gizlilik_denetimi as GD
    import site_kur

    site = tmp_path / "site"
    site.mkdir()
    temiz = tmp_path / "temiz.sqlite3"
    site_kur.prune(_sandbox_ref(tmp_path), temiz)
    (site / "katalog.sqlite3.gz").write_bytes(gzip.compress(temiz.read_bytes()))
    monkeypatch.setattr(GD, "ROOT", tmp_path)
    assert GD.site_denetle() == []


def test_privacy_audit_rejects_personal_config_in_site(tmp_path, monkeypatch):
    """Ziyaretçinin değil, GELİŞTİRİCİNİN ayarları siteye girmemeli."""
    import gizlilik_denetimi as GD
    import site_kur

    site = tmp_path / "site"
    (site / "config").mkdir(parents=True)
    temiz = tmp_path / "temiz.sqlite3"
    site_kur.prune(_sandbox_ref(tmp_path), temiz)
    (site / "katalog.sqlite3.gz").write_bytes(gzip.compress(temiz.read_bytes()))
    (site / "config" / "settings.toml").write_text("x", encoding="utf-8")
    monkeypatch.setattr(GD, "ROOT", tmp_path)
    assert any("settings.toml" in s for s in GD.site_denetle())


def test_site_config_list_excludes_personal_files():
    """Site paketine giren yapılandırma listesi kişisel dosya içermemeli."""
    import site_kur

    assert "settings.toml" not in site_kur.CONFIG
    assert "denklikler.toml" not in site_kur.CONFIG
    # Herkese ait olanlar girmeli, yoksa mevzuat kuralları web'de çalışmaz.
    assert "kurallar.toml" in site_kur.CONFIG
    assert "katalog-duzeltmeleri.toml" in site_kur.CONFIG
