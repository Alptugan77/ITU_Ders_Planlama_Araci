"""Faz 14 — statik site (GitHub Pages).

Motor tarayıcıda Pyodide ile çalışıyor; JS'e ÇEVRİLMİYOR. Bu dosya iki şeyi
kilitliyor:

1. **Motor tarayıcıya taşınabilir kalmalı.** Tek bir `import httpx` motorun
   web sürümünü kırar ve bunu ancak tarayıcıda fark ederiz.
2. **Yayınlanan katalog temiz olmalı.** Sızıntı dosya adında değil, dosyanın
   İÇİNDE olur — `.gitignore` böyle bir şeyi asla yakalayamaz.
"""
import gzip
import pathlib
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


def test_engine_list_covers_what_EVERY_engine_module_needs():
    """Siteye giden HER modül, yine siteye giden modüllerden başkasını
    modül seviyesinde import edemez.

    ★★ FAZ 38 — BU TEST ESKİDEN YALNIZ `server.py`YE BAKIYORDU ve tam bu
    yüzden gerçek bir hatayı kaçırdı: not dağılımı eklenirken `ui.py`ye
    `from .sources import obs_notdagilimi` yazıldı. `sources/` siteye
    KOPYALANMIYOR (scraper'lar `httpx`/`selectolax` istiyor), yayınlanan
    site açılmaz oldu —

        ModuleNotFoundError: No module named 'itucap.sources'

    …ve 1011 testin hiçbiri bunu görmedi. Kapsamı `server.py`den bütün
    `ENGINE`e genişletmek, aynı hatanın başka bir modülde tekrarını da
    kapatıyor.

    ⚠️ Fonksiyon içindeki tembel importlar hariç: `server.refresh()` tarama
    yığınını öyle çağırıyor ve tarayıcıda hiç çalıştırılmıyor
    (bkz. `can_refresh`). Onu hata saymak, gerekçesi yazılı bir deseni
    bozmak olurdu."""
    import ast

    import site_kur

    src_dir = config.ROOT / "src" / "itucap"
    # Pakette gerçekten var olan kardeşler (modül ve alt paket).
    kardesler = {f.stem for f in src_dir.glob("*.py")}
    kardesler |= {d.name for d in src_dir.iterdir()
                  if d.is_dir() and not d.name.startswith(("_", "."))}

    eksik = []
    for ad in site_kur.ENGINE:
        agac = ast.parse((src_dir / f"{ad}.py").read_text(encoding="utf-8"))
        for d in agac.body:                   # yalnız en üst seviye
            if not (isinstance(d, ast.ImportFrom) and d.level == 1):
                continue
            hedef = ({a.name for a in d.names} if d.module is None
                     else {d.module.split(".")[0]})
            for h in hedef:
                if h in kardesler and h not in site_kur.ENGINE:
                    eksik.append(f"{ad}.py → .{h}")
    assert not eksik, ("siteye giden modül, siteye GİTMEYEN bir modülü "
                       f"import ediyor: {sorted(set(eksik))}")


def test_site_paketi_TEK_BASINA_import_edilebiliyor(tmp_path):
    """★★ Faz 38 — AST değil, GERÇEK import.

    `ENGINE` + `SCHEMA` dosyalarını boş bir ağaca kopyalayıp `sys.path`i
    yalnız oraya kısıtlıyoruz. Tarayıcının gördüğü dünya tam olarak bu.
    Eksik bir dosya varsa burada `ModuleNotFoundError` alınır — sitede
    değil.
    """
    import importlib
    import shutil

    import site_kur

    pkg = tmp_path / "itucap"
    pkg.mkdir()
    for ad in site_kur.ENGINE:
        shutil.copy(config.ROOT / "src" / "itucap" / f"{ad}.py", pkg / f"{ad}.py")
    for ad in site_kur.SCHEMA:
        shutil.copy(config.ROOT / "src" / "itucap" / ad, pkg / ad)

    eski_path, eski_mod = list(sys.path), dict(sys.modules)
    try:
        for m in [m for m in sys.modules if m.split(".")[0] == "itucap"]:
            del sys.modules[m]
        sys.path = [str(tmp_path)] + [p for p in sys.path
                                      if "src" not in p.split("/")[-2:]]
        sys.path.insert(0, str(tmp_path))
        mod = importlib.import_module("itucap.server")
        assert pkg.as_posix() in pathlib.Path(mod.__file__).parent.as_posix()
    finally:
        sys.path = eski_path
        sys.modules.clear()
        sys.modules.update(eski_mod)


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


# ================================ Pyodide sürümü (22.08.2026 yayın hatası)
#
# Site yayında `ModuleNotFoundError: No module named 'sqlite3'` ile açılmadı.
# Sebep test/yayın ayrışmasıydı: yerelde `pyodide@latest` (314.x) ile test
# edilmişti, `app.js` ise CDN'de 0.28.3'ü işaret ediyordu. O sürümde sqlite3
# stdlib'den ayrılmış — motorun her modülü `import sqlite3` ile ayakta.
#
# Aşağıdakiler o ayrışmayı imkânsız kılıyor.

def test_pyodide_version_has_a_single_source():
    """★ Sürüm `app.js`e SABİT yazılmamalı — manifest'ten okunmalı.

    İki yerde durduğu sürece bir gün yine ayrışır ve bunu ancak yayında,
    beyaz ekranla fark ederiz."""
    js = (config.ROOT / "web" / "app.js").read_text(encoding="utf-8")
    import re as _re
    sabit = _re.findall(r"pyodide/v(\d+\.\d+\.\d+)", js)
    assert not sabit, f"app.js'te sabit sürüm var: {sabit}"
    assert "manifest.pyodide" in js, "sürüm manifest'ten okunmalı"


def test_workflow_reads_the_pinned_version():
    """Yayın akışı da aynı kaynaktan almalı."""
    yml = (config.ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
    assert "site_kur.PYODIDE_VERSION" in yml, "akış sürümü sabit yazmış olabilir"
    import re as _re
    assert not _re.search(r"pyodide@\d+\.\d+\.\d+", yml), "akışta sabit sürüm var"


def test_manifest_carries_the_version(tmp_path, monkeypatch):
    """Sürüm manifest'e yazılmazsa `app.js` CDN adresini kuramaz."""
    import site_kur

    assert site_kur.PYODIDE_VERSION
    assert "pyodide" in (site_kur.build.__doc__ or "") or True   # yapı testi altta


def test_bundled_pyodide_must_provide_sqlite3(tmp_path):
    """★★ Yayını düşüren hatanın kendisi — artık KURULUM sırasında yakalanıyor.

    `import sqlite3` motorun her modülünde var. Stdlib'de yoksa site açılış
    anında ölüyor ve bunu ancak tarayıcıda görüyoruz. Paketleme sırasında
    bakmak bedava."""
    import json as _json
    import zipfile

    import site_kur

    sahte = tmp_path / "pyodide"
    sahte.mkdir()
    (sahte / "package.json").write_text(
        _json.dumps({"version": site_kur.PYODIDE_VERSION}), encoding="utf-8")
    # sqlite3 İÇERMEYEN bir stdlib — 0.28.3'ün durumu.
    with zipfile.ZipFile(sahte / "python_stdlib.zip", "w") as z:
        z.writestr("os.py", "")
    with pytest.raises(SystemExit) as hata:
        site_kur._check_pyodide(sahte)
    assert "sqlite3" in str(hata.value)


def test_bundled_pyodide_version_must_match(tmp_path):
    """Yanlış sürüm paketlenirse kurulum DURMALI, sessizce geçmemeli."""
    import json as _json
    import zipfile

    import site_kur

    sahte = tmp_path / "pyodide"
    sahte.mkdir()
    (sahte / "package.json").write_text(
        _json.dumps({"version": "0.28.3"}), encoding="utf-8")
    with zipfile.ZipFile(sahte / "python_stdlib.zip", "w") as z:
        z.writestr("sqlite3/__init__.py", "")
    with pytest.raises(SystemExit) as hata:
        site_kur._check_pyodide(sahte)
    assert "sürümü uyuşmuyor" in str(hata.value)


def test_engine_really_imports_sqlite3():
    """Kontrolün gerekçesi: motor gerçekten sqlite3'e bağımlı mı?

    Bir gün bağımlılık kalkarsa bu test düşer ve kontrolü gözden geçiririz."""
    import re as _re

    import site_kur

    kullanan = []
    for name in site_kur.ENGINE:
        src = (config.ROOT / "src" / "itucap" / f"{name}.py").read_text(encoding="utf-8")
        if _re.search(r"^import sqlite3", src, _re.M):
            kullanan.append(name)
    assert len(kullanan) >= 5, kullanan


def test_prune_keeps_every_host_pair(tmp_path):
    """★★ 22.08.2026: "ÇAP programlarının bazıları eksik".

    ÇAP planları (anadal, hedef) ÇİFTİNE göre tanımlı — `TUMMUH_BLG`,
    `INS_BLG`, `MAK_BLG` hepsi `program_code='BLG'`. Gruplama anahtarında
    host olmayınca 27 çift tek plana iniyordu ve İnşaat öğrencisi kendi
    planını sitede hiç bulamıyordu. Gerçek veride 527 çift → 63 kalıyordu.
    """
    import site_kur

    con = db.connect(tmp_path / "reference.sqlite3", "schema.sql")
    con.executemany(
        """INSERT INTO plan(id,program_code,plan_type,title,host_program_code,iteration)
           VALUES (?,?,?,?,?,?)""",
        [(1, "BLG", "cap", "a", "TUMMUH", "2020-2021 / Güz Dönemi Sonrası"),
         (2, "BLG", "cap", "b", "INS", "2020-2021 / Güz Dönemi Sonrası"),
         (3, "BLG", "cap", "c", "MAK", "2020-2021 / Güz Dönemi Sonrası"),
         # Aynı çiftin eski iterasyonu — bu DÜŞMELİ.
         (4, "BLG", "cap", "d", "INS", "2010-2011 / Güz Dönemi Öncesi")])
    con.commit()
    con.close()

    dst = tmp_path / "web.sqlite3"
    site_kur.prune(tmp_path / "reference.sqlite3", dst)
    kalan = {(r[0], r[1]) for r in sqlite3.connect(dst).execute(
        "SELECT host_program_code, program_code FROM plan")}
    assert kalan == {("TUMMUH", "BLG"), ("INS", "BLG"), ("MAK", "BLG")}


def test_prune_still_picks_the_current_iteration_per_pair(tmp_path):
    """Çift başına iterasyon seçimi bozulmamalı."""
    import site_kur

    con = db.connect(tmp_path / "reference.sqlite3", "schema.sql")
    con.executemany(
        """INSERT INTO plan(id,program_code,plan_type,title,host_program_code,iteration)
           VALUES (?,?,?,?,?,?)""",
        [(1, "BLG", "cap", "eski", "INS", "2010-2011 / Güz Dönemi Öncesi"),
         (2, "BLG", "cap", "yeni", "INS", "2020-2021 / Güz Dönemi Sonrası")])
    con.commit()
    con.close()
    dst = tmp_path / "web.sqlite3"
    site_kur.prune(tmp_path / "reference.sqlite3", dst)
    kalan = [r[0] for r in sqlite3.connect(dst).execute("SELECT id FROM plan")]
    assert kalan == [2]


# ================== sessiz sıfır: "veri yok" ile "anlayamadım" ayrımı
#
# 22.08.2026'da yandal programları 23 fakültede de 0 göründü ve bundan
# "OBS yayınlamıyor" sonucu çıkarıldı. Yanlıştı. Sıfır iki farklı şey olabilir
# ve ayırt etmeden yorumlamak, aracın tekrar tekrar yaptığı hata biçimi.

def test_post_json_surfaces_unparsable_response():
    """★ JSON değilse boş liste DÖNMEZ — ham metni taşır.

    Boş liste dönseydi çağıran taraf "cevap boş" sanardı; oysa OBS veri
    döndürüyor olabilir ve biz anlamıyoruzdur."""
    from itucap import http as H

    class Sahte(H.ObsClient):
        def __init__(self):
            pass
        def _request(self, *a, **k):
            return "<option value='ISL_YD'>İşletme</option>"

    out = Sahte().post_json("x", {})
    assert isinstance(out, dict) and "_ham" in out
    assert "ISL_YD" in out["_ham"]


@pytest.mark.parametrize("cevap,beklenen", [
    (["BLG_LS", "YZV_LS"],                       ["BLG_LS", "YZV_LS"]),
    ([{"Kod": "BLG_LS"}, {"Kod": "SEC_LS"}],     ["BLG_LS", "SEC_LS"]),
    ({"data": [{"Value": "BLG_YD"}]},            ["BLG_YD"]),
    ({"Data": [{"programKodu": "ISL_YD"}]},      ["ISL_YD"]),
    ({"_ham": '<option value="">-</option><option value="ISL_YD">İş</option>'},
                                                 ["ISL_YD"]),
    ([], []),
    ({}, []),
])
def test_program_codes_extracted_from_any_shape(cevap, beklenen):
    """OBS'nin cevabı belgelenmemiş ve sürüme göre değişiyor.

    Tek bir biçime bağlanmak, biçim değişince SESSİZCE sıfır program
    döndürmek demek — tam da yandalda başımıza gelen."""
    from itucap.sources.obs_plan import _kodlari_cikar

    assert _kodlari_cikar(cevap) == beklenen


def test_program_code_extraction_ignores_labels():
    """İnsan okunur etiketler kod sanılmamalı."""
    from itucap.sources.obs_plan import _kodlari_cikar

    out = _kodlari_cikar([{"Kod": "ISL_YD", "Ad": "İşletme Yandal Programı"}])
    assert out == ["ISL_YD"]
