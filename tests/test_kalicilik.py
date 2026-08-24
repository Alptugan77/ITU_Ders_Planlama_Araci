"""Faz 22 — VERİ KAYBI: tarayıcıda transkript ve kaydedilen program uçuyordu.

Kullanıcı raporu 23.08.2026: *"planlar ve transkript kayıtlı kalmıyor
kaydedilen program da, sadece anadal ve çap bölümü kayıtlı kalıyor"*.

Teşhis — veri YAZILMIYOR değil, **taşınmıyordu**:

    37 derslik user.sqlite3 →  ana dosya 4096 bayt (yalnız başlık)
                               user.sqlite3-wal 78312 bayt (BÜTÜN VERİ)

SQLite WAL kipinde yazdığını yan dosyada tutuyor. Site kalıcılığı ana dosyayı
IndexedDB'ye kopyalayarak sağlıyor; yan dosya sayfa kapanınca yok oluyor.
`settings.toml` düz metin olduğu için etkilenmiyordu — "sadece bölüm ayarları
kalıyor" belirtisi tam olarak buydu.

★ Bu dosyadaki testler "yazıldı mı"yı değil **"dosyayı kopyalayınca duruyor
mu"yu** ölçüyor. Eski testler birincisini soruyordu ve hepsi geçiyordu.
"""
import shutil
import sqlite3

import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import config, db, student as S


def _kopyala_ve_ac(tmp_path, kaynak):
    """★ Tarayıcının yaptığı şeyin AYNISI: yalnız ANA dosyayı taşı."""
    hedef = tmp_path / "tasinan.sqlite3"
    shutil.copy(kaynak, hedef)
    con = sqlite3.connect(hedef)
    con.row_factory = sqlite3.Row
    return con


def test_yalniz_ana_dosya_tasininca_veri_DURUYOR(tmp_path, monkeypatch):
    """★ Asıl hata. Bu test WAL kipinde `no such table` ile düşerdi."""
    monkeypatch.setattr(config, "USER_DB", tmp_path / "u.sqlite3")
    monkeypatch.setattr(db, "journal_mode", lambda: "TRUNCATE")   # tarayıcı gibi
    ucon = db.user_db()
    sid = S.ensure_student(ucon)
    S.add_entries(ucon, sid, [S.make_entry("MAT 103E", "AA")])
    db.checkpoint(ucon)

    tasinan = _kopyala_ve_ac(tmp_path, config.USER_DB)
    assert tasinan.execute("SELECT COUNT(*) FROM earned_course").fetchone()[0] == 1


def test_WAL_kipinde_bile_checkpoint_kurtariyor(tmp_path, monkeypatch):
    """Eskiden WAL ile açılmış bir veritabanı da taşınabilmeli.

    Kip değişimi yeni dosyaları kurtarıyor; bu test ESKİLERİ kolluyor."""
    monkeypatch.setattr(config, "USER_DB", tmp_path / "w.sqlite3")
    monkeypatch.setattr(db, "journal_mode", lambda: "WAL")
    ucon = db.user_db()
    sid = S.ensure_student(ucon)
    S.add_entries(ucon, sid, [S.make_entry("MAT 103E", "AA")])

    # checkpoint ÖNCE: ana dosya boş olmalı (hatanın kanıtı)
    once = _kopyala_ve_ac(tmp_path, config.USER_DB)
    with pytest.raises(sqlite3.OperationalError):
        once.execute("SELECT COUNT(*) FROM earned_course").fetchone()

    db.checkpoint(ucon)
    sonra = _kopyala_ve_ac(tmp_path, config.USER_DB)
    assert sonra.execute("SELECT COUNT(*) FROM earned_course").fetchone()[0] == 1


def test_tarayicida_WAL_KULLANILMIYOR(monkeypatch):
    """★ Kararın kendisi: tarayıcıda yan dosya kalıcı olamıyor."""
    monkeypatch.setattr(db.sys, "platform", "emscripten")
    assert db.journal_mode() == "TRUNCATE"
    monkeypatch.setattr(db.sys, "platform", "darwin")
    assert db.journal_mode() == "WAL"


def test_acilan_veritabani_beklenen_kipte(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "journal_mode", lambda: "TRUNCATE")
    con = db.connect(tmp_path / "x.sqlite3", "schema_user.sql")
    assert con.execute("PRAGMA journal_mode").fetchone()[0].lower() == "truncate"
    assert not (tmp_path / "x.sqlite3-wal").exists()


def test_WAL_veritabani_TRUNCATE_ile_acilinca_donusuyor(tmp_path, monkeypatch):
    """Var olan WAL veritabanı, yeni kiple açılınca kendini aktarır —
    yani kullanıcının eski dosyası kayıpsız geçiyor."""
    yol = tmp_path / "eski.sqlite3"
    monkeypatch.setattr(db, "journal_mode", lambda: "WAL")
    con = db.connect(yol, "schema_user.sql")
    S.ensure_student(con)
    con.close()

    monkeypatch.setattr(db, "journal_mode", lambda: "TRUNCATE")
    con2 = db.connect(yol, "schema_user.sql")
    assert con2.execute("PRAGMA journal_mode").fetchone()[0].lower() == "truncate"
    tasinan = _kopyala_ve_ac(tmp_path, yol)
    assert tasinan.execute("SELECT COUNT(*) FROM student").fetchone()[0] == 1


# ------------------------------------------------------ uçtan uca (sunucu)
@pytest.fixture()
def state(tmp_path, monkeypatch):
    from itucap import server as SRV

    monkeypatch.setattr(config, "REF_DB", tmp_path / "r.sqlite3")
    monkeypatch.setattr(config, "USER_DB", tmp_path / "u.sqlite3")
    monkeypatch.setattr(config.Settings, "load",
                        classmethod(lambda cls, path=None: config.Settings(
                            anadal_program="HTAE", second_kind="yok", term="202610")))
    db.connect(tmp_path / "r.sqlite3", "schema.sql").close()
    return SRV.State()


@pytest.mark.parametrize("yol,govde,tablo", [
    ("/api/transcript", {"items": [{"course": "MAT 103E", "grade": "AA"}],
                         "replace": True}, "earned_course"),
    ("/api/picks", {"picks": [{"course": "MAT 103E", "crn": "12345"}]}, "saved_pick"),
])
def test_her_yazma_ANA_DOSYAYA_isliyor(state, tmp_path, yol, govde, tablo):
    """★ Sözleşme: bir uç çağrıldıktan SONRA dosyayı kopyalamak yeterli olmalı.

    Bu, tarayıcı kalıcılığının tek varsayımı. Sağlanmazsa kullanıcı
    girdiğini kaybediyor ve bunu ancak sayfayı yenileyince fark ediyor."""
    state.dispatch(yol, govde)
    tasinan = _kopyala_ve_ac(tmp_path, config.USER_DB)
    assert tasinan.execute(f"SELECT COUNT(*) FROM {tablo}").fetchone()[0] >= 1


def test_kaydedilen_program_yenilemeden_sonra_geri_geliyor(state, tmp_path):
    """Uçtan uca: kaydet → dosyayı taşı → yeni State ile oku."""
    from itucap import server as SRV

    state.dispatch("/api/picks", {"picks": [{"course": "MAT 103E", "crn": "12345"}]})
    shutil.copy(config.USER_DB, tmp_path / "tasinan.sqlite3")
    for ek in ("-wal", "-shm"):                 # ★ yan dosyalar TAŞINMIYOR
        yan = tmp_path / f"u.sqlite3{ek}"
        if yan.exists():
            yan.unlink()
    shutil.copy(tmp_path / "tasinan.sqlite3", config.USER_DB)

    yeni = SRV.State()
    assert [p["course"] for p in yeni.saved()["picks"]] == ["MAT 103E"]
