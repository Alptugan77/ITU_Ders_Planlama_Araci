"""Faz 104 — beyan edilmiş kod göçü (BLG 252E → BBF 203E).

Gerçek katalog gezisinde (BLGE 5. yarıyıl + EHB ÇAP, 26.09.2026) önerilen
program 22 kredilik sınırın yalnız 11'ini dolduruyordu. Sebep: BLGE
2024-25 planı BLG kodlarını BBF'ye taşımış (BBF 203E "Object Oriented
Programming" = BLG 252E: ad, kredi, AKTS ve önşart metni birebir aynı),
ama BBF 301E ve BBF 302E'nin önşartı hâlâ "BLG 252E" diyor. Yeni planla
okuyan öğrenci 5. dönemin iki ana dersinden engelleniyordu.

Otomatik eşleme YOK (aynı ad ≠ aynı ders: FIZ 101E / PHY 107). Beyan
`config/katalog-duzeltmeleri.toml` → `[[kod_gocu]]`, etkisi yalnız önşartta.
"""
import tomllib
from pathlib import Path

import pytest

from itucap import declared as DEC, recommend as REC, rules as R, student as S
from test_faz57_yol_haritasi import _katalog, _kur, _yer
from test_recommend import dbs  # noqa: F401  (fixture)

GOC = '[[kod_gocu]]\neski = "BLG 252E"\nyeni = "BBF 203E"\nnot_ = "t"\n'


@pytest.fixture()
def beyan(tmp_path, monkeypatch):
    """Beyan dosyası: yalnız BLG 252E → BBF 203E; `yaz("")` ile boşaltılır."""
    dosya = tmp_path / "katalog.toml"
    dosya.write_text(GOC, encoding="utf-8")
    monkeypatch.setattr(DEC, "CATALOG_PATH", dosya)

    def yaz(metin):
        dosya.write_text(metin, encoding="utf-8")
        import os, time
        os.utime(dosya, ns=(time.time_ns(), time.time_ns() + 1_000_000))
    return yaz


# ------------------------------------------------------------ beyan dosyası
def test_GERCEK_beyanlar_kanitli():
    raw = tomllib.loads((Path(DEC.__file__).resolve().parents[2] / "config"
                         / "katalog-duzeltmeleri.toml").read_text(encoding="utf-8"))
    ciftler = {(g["eski"], g["yeni"]): g["not_"] for g in raw["kod_gocu"]}
    assert set(ciftler) == {("BLG 252E", "BBF 203E"), ("BLG 336E", "BBF 303E"),
                            ("BLG 454E", "BBF 304E"), ("BLG 112E", "BBF 103E")}
    assert all("aynı" in n and "Ölçüldü" in n for n in ciftler.values())


# ------------------------------------------------------------ önşart görünümü
def test_ONSART_GORUNUMU(beyan):
    assert R.prereq_view({"BBF 203E": "BB"})["BLG 252E"] == "BB"        # yeni → eski
    assert R.prereq_view({"BLG 252E": "CC"})["BBF 203E"] == "CC"        # eski → yeni
    # İkisi de varsa iyisi: eski kodla kalmış, yeni kodla geçmiş.
    v = R.prereq_view({"BLG 252E": "FF", "BBF 203E": "CB"})
    assert v["BLG 252E"] == v["BBF 203E"] == "CB"
    beyan("")
    assert "BLG 252E" not in R.prereq_view({"BBF 203E": "BB"})          # beyan yoksa etki yok


# ---------------------------------------------------------------- engeller
def _kur_engel(dbs, gecti):  # noqa: F811
    con, ucon, sid = dbs
    con.executemany("INSERT INTO course(code,name,ects,prereq_raw) VALUES (?,?,5,?)",
                    [("BLG 252E", "OOP", None), ("BBF 203E", "OOP", None),
                     ("BBF 301E", "Algoritmalar", "(BLG 252 MIN DDveya BLG 252E MIN DD)")])
    con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,ects,position)"
                " VALUES (20,'REQUIRED','BBF 301E',5,9)")
    con.execute("INSERT INTO lesson(crn,course_code,capacity,enrolled) VALUES ('777','BBF 301E',40,0)")
    con.execute("INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min) VALUES ('777',4,510,689)")
    con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES ('777','BLG')")
    con.commit()
    from itucap import prereq as P
    P.parse_all(con)
    if gecti:
        S.add_entries(ucon, sid, S.parse_text("BBF 203E BB")[0])
    return {b.course: b for b in REC.cap_blockers(con, ucon, sid, 20, "BLG", {"HTAE", "BLG", "BLGE"})}


def test_YENI_KODU_gecen_engellenmiyor(dbs, beyan):  # noqa: F811
    assert "BBF 301E" not in _kur_engel(dbs, gecti=True)


def test_BEYANSIZ_hala_engelli(dbs, beyan):  # noqa: F811
    beyan("")
    assert _kur_engel(dbs, gecti=True)["BBF 301E"].reason == "ONSART"


def test_EKSIK_metni_yeni_kodu_soyluyor(dbs, beyan):  # noqa: F811
    e = _kur_engel(dbs, gecti=False)["BBF 301E"]
    assert e.reason == "ONSART" and "BLG 252E (yeni kodu BBF 203E)" in e.detail, e.detail


# -------------------------------------------------------------- yol haritası
@pytest.fixture()
def harita_katalog(tmp_path):
    # BLG 252E katalogda var ama HİÇBİR planda yok; plan yeni kodu koyuyor.
    return _katalog(tmp_path / "h", [("BLG 252E", 3, None), ("BBF 203E", 3, None),
                                     ("BBF 301E", 3, "BLG 252E MIN DD")],
                    plan=[("BBF 203E", 4), ("BBF 301E", 5)])


def test_YOL_HARITASI_sira(harita_katalog, beyan):
    h = _kur(harita_katalog, {}, donem=3)
    yer = _yer(h)
    assert yer["BBF 203E"] < yer["BBF 301E"], yer
    dis = {i["course"]: i["externalPrereq"] for t in h["terms"] for i in t["items"]}
    assert dis["BBF 301E"] == []                        # eski kod artık "dış" değil


def test_YOL_HARITASI_beyansiz_dis_sayiyordu(harita_katalog, beyan):
    beyan("")
    h = _kur(harita_katalog, {}, donem=3)
    dis = {i["course"]: i["externalPrereq"] for t in h["terms"] for i in t["items"]}
    assert dis["BBF 301E"] == ["BLG 252E"]              # eski davranış: varsayılıyordu


def test_YOL_HARITASI_ters_plan_sirasi(tmp_path, beyan):
    """Plan BBF 301E'yi BBF 203E'den ÖNCEKİ döneme koysa bile (dış sayılan eski
    kod varsayılsaydı BBF 301E önce yerleşirdi) önşart sırası korunuyor."""
    con = _katalog(tmp_path / "t", [("BLG 252E", 3, None), ("BBF 203E", 3, None),
                                    ("BBF 301E", 3, "BLG 252E MIN DD")],
                   plan=[("BBF 301E", 4), ("BBF 203E", 6)])
    yer = _yer(_kur(con, {}, donem=3))
    assert yer["BBF 203E"] < yer["BBF 301E"], yer
