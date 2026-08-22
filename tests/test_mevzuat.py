"""Faz 12 — doğrulanan mevzuat: eşik kapsamı, şartlı başarı, önşart beyanı.

22.08.2026'da ÇAP/Yandal Yönergesi ve Lisans Yönetmeliği MADDE 20/31 okundu.
Faz 11'de ⚠ ile duran iki eşik doğrulandı, dört yeni eşik ve "şartlı
başarmış"ın şartı bulundu.

Buradaki testler sayıları değil **yapıyı** kilitliyor: kapsam alanı çalışıyor
mu, eski beyanlar bozuluyor mu, "şartlı geçer" iki ayrı soruyu ayrı tutuyor mu.
Sayının kendisi `config/kurallar.toml`'da ve mevzuat değişince orası değişir.
"""
import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import config, declared, policy as POL


# ------------------------------------------------------------ eşik kapsamı
SCOPED = """
[[gno_esigi]]
anahtar = "cap_b"
ad = "ÇAP başvuru"
program = "cap"
tur = "basvuru"
min_gno = 3.0
dogrulandi = true

[[gno_esigi]]
anahtar = "yan_b"
ad = "Yandal başvuru"
program = "yandal"
tur = "basvuru"
min_gno = 2.5
dogrulandi = true

[[gno_esigi]]
anahtar = "genel_m"
ad = "Mezuniyet"
program = "genel"
tur = "mezuniyet"
min_gno = 2.0
dogrulandi = true
"""

# Faz 11 ve öncesinden kalan biçim: program/tur alanı YOK.
LEGACY = """
[[gno_esigi]]
anahtar = "eski"
ad = "Eski eşik"
min_gno = 2.5
dogrulandi = false
"""


def _rules(tmp_path, text):
    p = tmp_path / "kurallar.toml"
    p.write_text(text, encoding="utf-8")
    return p


def test_program_scope_filters(tmp_path):
    p = _rules(tmp_path, SCOPED)
    cap = {t.key for t in POL.load_thresholds(p, program="cap")}
    yan = {t.key for t in POL.load_thresholds(p, program="yandal")}
    assert cap == {"cap_b", "genel_m"}          # 'genel' her ikisine de uyar
    assert yan == {"yan_b", "genel_m"}


def test_kind_filters(tmp_path):
    p = _rules(tmp_path, SCOPED)
    keys = {t.key for t in POL.load_thresholds(p, kind="basvuru")}
    assert keys == {"cap_b", "yan_b"}


def test_legacy_declaration_still_loads_everywhere(tmp_path):
    """★ `program` yazılmamış eski beyan 'genel' sayılır ve ELENMEZ.

    Aksi hâlde kapsam alanını eklemek, kullanıcının elle yazdığı eşikleri
    sessizce devre dışı bırakırdı — en kötü türden bir yükseltme hatası."""
    p = _rules(tmp_path, LEGACY)
    for scope in ("cap", "yandal", "genel"):
        assert {t.key for t in POL.load_thresholds(p, program=scope)} == {"eski"}


def test_tolerance_is_carried(tmp_path):
    """Madde 19/k: bir defaya mahsus altına düşülebilir.

    Toleransı düşürmek eşiği sert bir duvara çevirir; arayüz 'kaydın silinir'
    derken yönerge 'bir kez olabilir' diyor."""
    p = _rules(tmp_path, """
[[gno_esigi]]
anahtar = "devam"
ad = "devam"
program = "cap"
tur = "devam"
min_gno = 2.5
tolerans = 1
dogrulandi = true
""")
    assert POL.load_thresholds(p)[0].tolerance == 1


def test_source_is_carried(tmp_path):
    p = _rules(tmp_path, SCOPED.replace(
        'dogrulandi = true\n\n[[gno_esigi]]\nanahtar = "yan_b"',
        'dogrulandi = true\nkaynak = "Madde 15"\n\n[[gno_esigi]]\nanahtar = "yan_b"', 1))
    t = [x for x in POL.load_thresholds(p) if x.key == "cap_b"][0]
    assert t.source == "Madde 15"


def test_project_config_has_every_verified_threshold():
    """Projenin kendi kuralları: Faz 12'de doğrulanan altı eşik yerinde mi."""
    ts = {t.key: t for t in POL.load_thresholds(
        config.ROOT / "config" / "kurallar.toml")}
    for key in ("basvuru", "devam", "cap_mezuniyet_universite",
                "cap_mezuniyet_ikinci", "yandal_basvuru", "yandal_devam",
                "mezuniyet"):
        assert key in ts, key
        assert ts[key].verified, f"{key} hâlâ doğrulanmamış"
        assert ts[key].source, f"{key} kaynaksız"


def test_project_config_scopes_yandal_away_from_cap():
    """★ Yandal eşiği ÇAP öğrencisine uygulanmamalı — ayrı maddeler,
    farklı sayılar (2.50/2.00 karşı 3.00/2.50)."""
    p = config.ROOT / "config" / "kurallar.toml"
    cap = {t.key for t in POL.load_thresholds(p, program="cap")}
    assert "yandal_basvuru" not in cap and "yandal_devam" not in cap
    assert "mezuniyet" in cap                     # 'genel' herkese uyar


# ---------------------------------------------------------- şartlı başarı
def test_conditional_rule_separates_passing_from_graduating(tmp_path):
    """★ MADDE 20/2-b + MADDE 31/1 iki AYRI soru.

    `passes` dersin tamamlandığını söyler; `graduation_min_gpa` mezuniyet
    şartını. Tek soruya indirmek ya dersi haksız yere kapatır ya mezuniyeti
    haksız yere açardı."""
    p = _rules(tmp_path, """
[sartli_basari]
notlar = ["DC+", "DC", "DD+", "DD"]
gecer = true
mezuniyet_min_gno = 2.00
dogrulandi = true
kaynak = "MADDE 20/2-b + MADDE 31/1"
""")
    r = POL.load_conditional(p)
    assert r.passes is True
    assert r.graduation_min_gpa == 2.00
    assert r.verified and r.source
    assert set(r.grades) == {"DC+", "DC", "DD+", "DD"}


def test_conditional_rule_defaults_when_undeclared(tmp_path):
    """Beyan yoksa eşik None döner — motor hiçbir şey iddia etmez."""
    r = POL.load_conditional(tmp_path / "yok.toml")
    assert r.graduation_min_gpa is None
    assert r.grades == POL.CONDITIONAL_PASS


def test_project_config_declares_the_conditional_rule():
    r = POL.load_conditional(config.ROOT / "config" / "kurallar.toml")
    assert r.verified and r.graduation_min_gpa == 2.00 and r.passes


# ------------------------------------------------------- önşart beyanı
def test_prereq_override_declares_no_prerequisite(tmp_path):
    """★ `onsart = ""` "önşart YOK" demek — "bilinmiyor" değil.

    Katalogda önşart alanına ders adı ya da dil yazılmış dersler var
    (MST 471, ROS 201). Ayrıştırıcı haklı olarak çözemiyor; doğrusu
    'önşart yok'."""
    p = tmp_path / "denklikler.toml"
    p.write_text("""
[[onsart_beyani]]
ders = "mst 471"
onsart = ""
not_ = "katalogda ders adı yazılmış"
""", encoding="utf-8")
    ov = declared.load_prereq_overrides(p)
    assert ov["MST 471"]["text"] == ""
    assert ov["MST 471"]["note"]           # gerekçe zorunlu değil ama taşınıyor


def test_prereq_override_can_also_declare_a_real_prerequisite(tmp_path):
    p = tmp_path / "denklikler.toml"
    p.write_text("""
[[onsart_beyani]]
ders = "ROS 201"
onsart = "MAT 103 MIN DD"
""", encoding="utf-8")
    assert declared.load_prereq_overrides(p)["ROS 201"]["text"] == "MAT 103 MIN DD"


def test_override_is_applied_during_parsing(tmp_path, monkeypatch):
    """Beyan ayrıştırıcıdan ÖNCE devreye girmeli; sonra girseydi ders
    yine `prereq_unparsed` listesinde kalırdı."""
    from itucap import db, prereq

    p = tmp_path / "katalog.toml"
    p.write_text("""
[[onsart_beyani]]
ders = "MST 471"
onsart = ""
not_ = "katalog hatası"
""", encoding="utf-8")
    # ⚠️ CATALOG_PATH yamalanmalı, DEFAULT_PATH değil: katalog düzeltmeleri
    # kişisel beyanlardan AYRI dosyada. Yanlışını yamalarsak test gerçek
    # proje dosyasını okur ve kendi kurgusunu doğrulamamış olur.
    monkeypatch.setattr(declared, "CATALOG_PATH", p)

    con = db.connect(tmp_path / "ref.sqlite3", "schema.sql")
    con.execute("INSERT INTO course(code,name,prereq_raw) VALUES (?,?,?)",
                ("MST 471", "Deniz", "Deniz Kazalarıve Emniyet Kültürü"))
    con.commit()
    stats = prereq.parse_all(con)
    assert stats["failed"] == 0
    assert stats["overridden"] == 1
    assert con.execute("SELECT COUNT(*) FROM prereq_unparsed").fetchone()[0] == 0
    # Beyan iz bırakmalı: sessizce uygulanan bir kural denetlenemez.
    repairs = con.execute(
        "SELECT repair FROM prereq_repair WHERE course_code='MST 471'").fetchall()
    assert repairs and "beyan" in repairs[0][0]


def test_project_config_closes_both_unparsable_prereqs():
    """★ Katalog düzeltmeleri KİŞİSEL DEĞİL, o yüzden ayrı dosyada.

    `denklikler.toml` senin beyanların — `.gitignore`da, depoya girmiyor.
    OBS kataloğundaki hatalar herkesi ilgilendiriyor; onlar
    `katalog-duzeltmeleri.toml`'da ve depoyla birlikte geliyor."""
    ov = declared.load_prereq_overrides(
        config.ROOT / "config" / "katalog-duzeltmeleri.toml")
    assert {"MST 471", "ROS 201"} <= set(ov)
    for code in ("MST 471", "ROS 201"):
        assert ov[code]["text"] == ""
        assert ov[code]["note"], f"{code} gerekçesiz beyan edilmiş"


# ------------------------------------------------- depo hijyeni (Faz 12/GitHub)
def test_personal_config_is_not_required_to_run():
    """★ Kişisel yapılandırma dosyaları depoda YOK; araç yine de kurulmalı.

    `config/settings.toml` ve `denklikler.toml` `.gitignore`da. Yeni klonlayan
    biri `make setup` çalıştırınca örnekten kopyalanıyor. Bu test örneklerin
    gerçekten var olduğunu ve okunabildiğini kilitliyor — yoksa depo
    klonlanabilir ama çalıştırılamaz olurdu."""
    for name in ("settings.example.toml", "denklikler.example.toml"):
        p = config.ROOT / "config" / name
        assert p.exists(), f"{name} yok — yeni klonlayan kurulum yapamaz"
        assert p.read_text(encoding="utf-8").strip()


def test_example_settings_carry_no_real_program():
    """Örnek yapılandırma kimsenin bölümünü içermemeli."""
    text = (config.ROOT / "config" / "settings.example.toml").read_text(encoding="utf-8")
    import re as _re
    for line in text.splitlines():
        if _re.match(r"\s*(anadal_program|cap_program|yandal_program)\s*=", line):
            value = line.split("=", 1)[1].split("#")[0].strip().strip('"')
            assert value in ("", "XXX", "YYY"), f"gerçek program kodu sızmış: {line}"


def test_catalog_fixes_ship_with_the_repo():
    """Katalog düzeltmeleri herkese ait — depoda olmalı ve `.gitignore`da olmamalı."""
    p = config.ROOT / "config" / "katalog-duzeltmeleri.toml"
    assert p.exists()
    ignored = (config.ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "katalog-duzeltmeleri" not in ignored


def test_gitignore_actually_ignores_every_personal_path():
    """★ Kişisel veri yollarının gerçekten yok sayıldığını GIT'e sorar.

    Önce `.gitignore` metninde satır arıyordu; o test yazıma bağlıydı ve
    kuralları sadeleştirince (yedi satır yerine tek `data/`) kırıldı — oysa
    davranış aynıydı, hatta daha güçlüydü. Metin yerine SONUCU ölçmek doğru:
    kural nasıl yazılırsa yazılsın, bu yolların hiçbiri depoya giremez.
    """
    import shutil
    import subprocess

    if not shutil.which("git") or not (config.ROOT / ".git").exists():
        pytest.skip("git deposu değil")
    yollar = [
        "data/user.sqlite3", "data/reference.sqlite3",
        "data/itucap.html", "data/yedek/transkript-20260101-000000.txt",
        "data/ituhelper/courses.psv",
        "transkript.txt", "transkript-yeni.txt",
        "config/settings.toml", "config/denklikler.toml",
    ]
    r = subprocess.run(["git", "check-ignore", "--no-index", *yollar],
                       cwd=config.ROOT, capture_output=True, text=True)
    yoksayilan = set(r.stdout.split())
    eksik = [y for y in yollar if y not in yoksayilan]
    assert not eksik, f"depoya sızabilir: {eksik}"


def test_shared_config_is_not_ignored():
    """Ters yön: herkese ait dosyalar YOK SAYILMAMALI.

    `data/` gibi geniş bir kural yazarken paylaşılan bir dosyayı da
    kapatmak kolay; o zaman depo klonlanır ama çalışmaz."""
    import shutil
    import subprocess

    if not shutil.which("git") or not (config.ROOT / ".git").exists():
        pytest.skip("git deposu değil")
    paylasilan = ["config/kurallar.toml", "config/katalog-duzeltmeleri.toml",
                  "config/settings.example.toml", "config/denklikler.example.toml",
                  "src/itucap/basvuru.py", "README.md", "LICENSE"]
    r = subprocess.run(["git", "check-ignore", "--no-index", *paylasilan],
                       cwd=config.ROOT, capture_output=True, text=True)
    assert not r.stdout.split(), f"yanlışlıkla yok sayılıyor: {r.stdout.split()}"
