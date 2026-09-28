"""Faz 121 — yol haritasında kaydedilebilir planlama yükü ve "neyle çakışıyor".

Kullanıcının kendi verisiyle (HTAE + BLG ÇAP, 28.09.2026) ölçüldü:
* GNO ≥ 3.00 → yönetmelik sınırı 40 (MADDE 17/2); harita 2026-2027 Bahar'a
  14 ders / 39,5 kredi koyuyordu. Senaryoda denenen değer artık "planlama
  yükü" olarak kaydedilebiliyor; harita min(yük, sınır) ile kuruluyor. 22
  kredi: anadal 9. → 10. yarıyıl (dürüst olan bu).
* "GEO 307E, GEO 403E ile ne çakışıyor": harita GEO 307E'yi 2027-2028 Güz'den
  "saat çakışması" diye erteliyordu ama NEYLE olduğunu söylemiyordu. Sebep
  GEO 227E (FF, tekrar): ikisinin de tek şubesi Salı 08:30. Kart artık
  "GEO 307E (GEO 227E ile aynı saatte)" diyor.
"""
import pathlib

import pytest

from itucap import config, server
from itucap import ui as UI
from test_faz82_yol_haritasi_saat import _katalog, _kur

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


def test_CAKISAN_DERS_adiyla(tmp_path):
    con = _katalog(tmp_path, [("AAA 400", 7, 3, [(2, 510, 630)]),
                              ("AAA 401", 7, 3, [(1, 510, 630)]),
                              ("AAA 402", 7, 3, [(1, 510, 630)])])
    # AAA 400'ün İKİNCİ şubesi Pzt 08:30'da: AAA 402 ile o şubesi çakışıyor
    # ama Salı şubesiyle birlikte alınabiliyor — "aynı saatte" YAZILMAMALI.
    con.execute("INSERT INTO lesson(crn,term,course_code,capacity,enrolled) "
                "VALUES ('999','202710','AAA 400',50,0)")
    con.execute("INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min) "
                "VALUES ('999',1,510,630)")
    con.commit()
    h = _kur(con)
    t = next(t for t in h["terms"] if t.get("timeDeferred"))
    assert t["timeDeferred"] == ["AAA 402"], t
    assert t["timeDeferredWith"] == {"AAA 402": ["AAA 401"]}, t


def test_AYAR_okunuyor_ve_gecersiz_sifir(tmp_path):
    yol = tmp_path / "s.toml"
    yol.write_text("[student]\nyol_yuk = 22\n", encoding="utf-8")
    assert config.Settings.load(yol).yol_yuk == 22.0
    for kotu in ('"abc"', "-3", "99"):
        yol.write_text(f"[student]\nyol_yuk = {kotu}\n", encoding="utf-8")
        assert config.Settings.load(yol).yol_yuk == 0.0
    config.update_settings({"yol_yuk": 18.5}, path=yol)
    assert config.Settings.load(yol).yol_yuk == 18.5


def test_SUNUCU_dogruluyor(monkeypatch):
    yazilan = []
    monkeypatch.setattr(config, "update_settings", lambda v, path=None: yazilan.append(v))
    for kotu in (0.5, 61, 22.3, "abc"):
        with pytest.raises(ValueError):
            server.State.save_roadmap_load(None, kotu)
    assert yazilan == []
    assert server.State.save_roadmap_load(None, 22) == 22.0
    assert server.State.save_roadmap_load(None, 0) == 0.0          # sıfırla
    assert yazilan == [{"yol_yuk": 22.0}, {"yol_yuk": 0.0}]


def _harita(tmp_path, yol_yuk, sinir=40):
    con = _katalog(tmp_path, [(f"AAA 4{i:02d}", 7, 6, None) for i in range(8)])
    ayar = config.Settings(anadal_program="AAA", term="202710", yol_yuk=yol_yuk)
    return UI._yol_haritasi(con, _Bos(), 1, ayar, 1, [], {"XXX 100": "BB"}, [], 5, sinir,
                           None, None, [], [])


class _Bos:
    """Kayıtlı program yok (`load_picks` boş döner)."""
    def execute(self, *a, **k):
        class C:
            def fetchall(self): return []
            def fetchone(self): return None
            def __iter__(self): return iter(())
        return C()


def test_HARITA_planlama_yukuyle_kuruluyor(tmp_path, monkeypatch):
    monkeypatch.setattr(UI, "_aktif_donem", lambda con, s: "202710")
    monkeypatch.setattr(UI.S, "load_picks", lambda *a, **k: {})
    h = _harita(tmp_path / "a", 0)
    assert h["maxLoad"] == 40 and h["loadLimit"] == 40
    assert h["planLoad"] == {"saved": 0.0, "applied": 40.0, "clamped": False}
    assert any("(mevcut sınır)" in a for a in h["assumptions"])
    h = _harita(tmp_path / "b", 12)
    assert h["maxLoad"] == 12 and max(t["credits"] for t in h["terms"]) <= 12
    assert any("12 kredi (kaydedilen planlama yükü)" in a for a in h["assumptions"])
    h = _harita(tmp_path / "c", 45)                            # sınırı aşamaz
    assert h["maxLoad"] == 40 and h["planLoad"]["clamped"] is True


def test_ARAYUZ():
    k = KAYNAK[KAYNAK.index("function yhYukKaydi("):]
    k = k[:k.index("\n}\n")]
    assert "A.maxLoad !== T.maxLoad && A.maxLoad <= sinir" in k, "sınır üstü kaydedilmemeli"
    assert "Yönetmelik sınırına dön" in k and "sinir > 25" in k
    assert 'api("/api/yolyuk", {kredi: deger()})' in KAYNAK
    assert "ile aynı saatte" in KAYNAK
    assert "/api/yolyuk" not in server.READ_ONLY_PATHS
