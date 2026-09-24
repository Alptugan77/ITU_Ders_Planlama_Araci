"""Faz 64 — "bu dönem" bir yıl geride yazıyordu.

Kullanıcı 24.09.2026: *"we are currently in 2026-2027 fall semester not in
2025-2026"*.

itu-helper'ın `lessons.psv`'sinde dönem yok; yükleyici şubelere ayardaki
`term`i basıyordu, o da örnek ayardan kalma `202610`'du. OBS'nin kendi not
dağılımı ucuna göre (Faz 38) `202610` = **2025-2026** Güz. Yayındaki katalogun
şubeleri 20.09.2026'da çekildi — 2026-2027 Güz (`202710`). Yol haritası,
başlık ve danışman özeti bir yıl geriden başlıyordu.
"""
import pathlib
import tomllib

from itucap import config
from itucap import db
from itucap import ui as UI

KOK = pathlib.Path(UI.__file__).resolve().parents[2]
KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


def test_TARIHTEN_DONEM():
    t = config.donem_kodu_tarihten
    # Kullanıcının söylediği: 24.09.2026 → 2026-2027 Güz.
    assert t("2026-09-24") == "202710"
    assert config.donem_adi(t("2026-09-24")) == "2026-2027 Güz"
    assert t("2026-09-20T21:32:52+00:00") == "202710"      # yayındaki katalog
    assert t("2026-12-31") == "202710"
    assert t("2027-03-01") == "202720"
    assert config.donem_adi(t("2027-03-01")) == "2026-2027 Bahar"
    # Geçiş ayları: OBS hangi dönemi gösteriyor bilinmiyor → uydurma yok.
    for gecis in ("2027-01-10", "2026-06-15", "2026-07-01", "2026-08-10"):
        assert t(gecis) == "", gecis
    assert t("") == "" and t(None) == "" and t("bozuk") == ""


def _katalog(tmp_path, damga, cekim):
    con = db.connect(tmp_path / "ref.sqlite3", "schema.sql")
    con.execute("INSERT INTO lesson(crn,term,course_code,updated_at) VALUES ('1',?,'X 1',?)",
                (damga, cekim))
    con.commit()
    return con


def test_AKTIF_DONEM_cekim_gununden(tmp_path):
    s = config.Settings()
    s.term = ""
    # Yayındaki katalog: örnek ayardan kalma damga, Eylül'de çekim.
    assert UI._aktif_donem(_katalog(tmp_path / "a", "202610", "2026-09-20T21:32:52+00:00"),
                           s) == "202710"
    # Geçiş ayında çekildiyse damgaya düşülüyor.
    assert UI._aktif_donem(_katalog(tmp_path / "b", "202710", "2026-08-10T10:00:00+00:00"),
                           s) == "202710"
    # Kullanıcının beyanı her zaman önde.
    s.term = "202720"
    assert UI._aktif_donem(_katalog(tmp_path / "c", "202610", "2026-09-20"), s) == "202720"


def test_YUKLEYICI_ve_ARAYUZ_ayni_donemi_kullaniyor():
    boru = (KOK / "src" / "itucap" / "pipeline.py").read_text(encoding="utf-8")
    assert "config.donem_kodu_tarihten(db.now()) or settings.term" in boru
    i = KAYNAK.index("def collect(")
    k = KAYNAK[i:KAYNAK.index("\ndef ", i + 1)]
    assert "aktif_donem = _aktif_donem(con, settings)" in k
    for parca in ('"term": aktif_donem,', '"termLabel": config.donem_adi(aktif_donem),',
                  "ND.term_already_graded(con, aktif_donem)",
                  "ND.distribution(con, code, aktif_donem)"):
        assert parca in k, parca


def test_ORNEK_AYAR_yorumu_koduyla_ayni():
    """`term = "202610"  # 2026-2027 Güz` — kod ile yorum bir yıl ayrıydı."""
    metin = (KOK / "config" / "settings.example.toml").read_text(encoding="utf-8")
    satir = next(s for s in metin.splitlines() if s.startswith("term ="))
    kod = tomllib.loads(satir)["term"]
    assert config.donem_adi(kod) in satir.split("#", 1)[1], satir
