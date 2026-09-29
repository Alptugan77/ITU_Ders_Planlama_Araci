"""Faz 126 — "bu dönem alınırsa" satırı saat takasını hesaplıyor.

Kullanıcı (28.09.2026): *"anadala öncelik verince BLG 223E yerine GEO 307E'yi
neden almıyor"*. Satır GEO 307E için "anadal 1 dönem erken" diyordu — dersin
programa EKLENDİĞİ varsayımıyla. Oysa tek şubesi programdaki BLG 223E ile
aynı saatte; ikisi birlikte alınamaz. Artık takas kuruluyor ve her programın
net etkisi yazılıyor. Kullanıcının verisinde: "birlikte" ayarında GEO 307E,
BLG 223E yerine → anadal aynı, ÇAP 2 dönem geç; "anadal" ayarında BLG 223E,
GEO 307E yerine → anadal 1 dönem geç, ÇAP 4 dönem erken.
"""
import pathlib
from types import SimpleNamespace as N

from itucap import config
from itucap import recommend as REC
from itucap import ui as UI
from test_faz57_yol_haritasi import _katalog
from test_faz121_planlama_yuku import _Bos


def _cat(tmp_path, cakisan=True):
    con = _katalog(tmp_path, [("XXX 301", 3, None), ("YYY 401", 3, "XXX 301 MIN DD"),
                              ("ZZZ 302", 3, None)],
                   [("XXX 301", 5), ("YYY 401", 7), ("ZZZ 302", 5)],
                   lesson=[("100", "XXX 301"), ("101", "ZZZ 302")])
    con.execute("INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min) VALUES ('100',1,510,630)")
    con.execute("INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min) VALUES ('101',?,510,630)",
                (1 if cakisan else 2,))
    for crn in ("100", "101"):
        con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES (?,'AAA')", (crn,))
    con.commit()
    return con


def _aday(con, kod):
    return REC.Candidate(course=kod, name=kod, role="ANADAL", ects=5, credits=3, unlocks=0,
                         tier=0, critical=False, required=True,
                         sections=REC.load_sections(con, kod, {"AAA"}))


def _harita(con, monkeypatch):
    monkeypatch.setattr(UI, "_aktif_donem", lambda c, s: "202510")
    monkeypatch.setattr(UI.S, "load_picks", lambda *a, **k: {})
    x, z = _aday(con, "XXX 301"), _aday(con, "ZZZ 302")
    acilis = [N(picks=[N(candidate=z)])]
    ayar = config.Settings(anadal_program="AAA", term="202510")
    return UI._yol_haritasi(con, _Bos(), 1, ayar, 1, [], {"ABC 100": "BB"}, [], 5, 21,
                            None, None, [x, z], acilis)


def test_KESIN_CAKISMADA_takas_etkisi(tmp_path, monkeypatch):
    h = _harita(_cat(tmp_path), monkeypatch)
    x = next(t for t in h["takeNow"] if t["course"] == "XXX 301")
    assert x["swap"]["replaces"] == ["ZZZ 302"]
    etki = {e["role"]: e["terms"] for e in x["swap"]["effects"]}
    assert set(etki) == {"ANADAL"} and isinstance(etki["ANADAL"], int)


def test_CAKISMA_YOKSA_takas_yok(tmp_path, monkeypatch):
    h = _harita(_cat(tmp_path, cakisan=False), monkeypatch)
    x = next(t for t in h["takeNow"] if t["course"] == "XXX 301")
    assert "swap" not in x and x["gains"]


def test_ARAYUZ():
    k = pathlib.Path(UI.__file__).read_text(encoding="utf-8")
    assert "function yhTakas(x){" in k and "ile aynı saattedir" in k
    assert '${x.swap ? "" : ` — bu dönem alınırsa' in k           # takasta yarım kazanç yok
    assert "yerine dene</button>" in k


def test_BIR_SUBESI_CAKISMIYORSA_takas_yok(tmp_path, monkeypatch):
    """XXX 301'in ikinci şubesi Çarşamba: ZZZ 302 ile birlikte alınabilir."""
    con = _cat(tmp_path)
    con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled) VALUES ('102','XXX 301',9,0)")
    con.execute("INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min) VALUES ('102',3,510,630)")
    con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES ('102','AAA')")
    con.commit()
    x = next(t for t in _harita(con, monkeypatch)["takeNow"] if t["course"] == "XXX 301")
    assert "swap" not in x
