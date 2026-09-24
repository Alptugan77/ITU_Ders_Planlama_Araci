"""Faz 82 — yol haritası derslerin SAATLERİNE bakıyor.

Kullanıcı 24.09.2026: *"yol haritasında derslerin saatlerinin toplamı
alabileceğim saatlere sığmıyor gibi geldi biraz imkansız bir tahmin ve
hesaplama bunu biraz geliştirir misin"*.

Harita her dönemi yalnız KREDİ sınırına kadar dolduruyordu: o derslerin aynı
hafta içinde çakışmadan alınıp alınamayacağına ve öğrencinin meşgul
saatlerine hiç bakmıyordu.
"""
import pathlib

import pytest

from itucap import db
from itucap import prereq as P
from itucap import recommend as REC
from itucap import ui as UI
from itucap import yolharitasi as YH

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


def _katalog(tmp_path, dersler):
    """dersler: [(kod, plan_dönemi, kredi, [(gün, başla, bitir), ...] ya da None)]"""
    con = db.connect(tmp_path / "ref.sqlite3", "schema.sql")
    con.execute("INSERT INTO program(code,name,level) VALUES ('AAA','A Müh.','LS')")
    con.execute("INSERT INTO plan(id,program_code,plan_type,title,source) "
                "VALUES (1,'AAA','lisans','x','obs')")
    for i, (kod, donem, kredi, saatler) in enumerate(dersler):
        con.execute("INSERT INTO course(code,name,credits,ects) VALUES (?,?,?,5)",
                    (kod, "Ders " + kod, kredi))
        con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,credits,position,"
                    "term_no) VALUES (1,'REQUIRED',?,?,?,?)", (kod, kredi, i, donem))
        if saatler:
            crn = str(100 + i)
            con.execute("INSERT INTO lesson(crn,term,course_code,capacity,enrolled) "
                        "VALUES (?,'202710',?,50,0)", (crn, kod))
            for g, a, b in saatler:
                con.execute("INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min) "
                            "VALUES (?,?,?,?)", (crn, g, a, b))
    P.parse_all(con)
    con.commit()
    return con


def _kur(con, mesgul=(), max_load=21):
    return YH.kur(con, {}, [{"planId": 1, "role": "ANADAL", "label": "anadal",
                             "program": "AAA"}],
                  term="202710", donem=5, max_load=max_load, bu_donem=[], mesgul=mesgul)


def _nerede(h):
    return {i["course"]: t["label"] for t in h["terms"] for i in t["items"] if i["course"]}


def test_AYNI_MEVSIMDE_CAKISAN_iki_ders_ayri_donemlere(tmp_path):
    # İkisi de 7. yarıyıl (Güz) dersi, TEK şubeleri Pzt 08:30–10:30 → çakışıyor.
    con = _katalog(tmp_path, [("AAA 401", 7, 3, [(1, 510, 630)]),
                              ("AAA 402", 7, 3, [(1, 510, 630)])])
    h = _kur(con)
    yer = _nerede(h)
    assert yer["AAA 401"] != yer["AAA 402"], yer
    guz = [t for t in h["terms"] if t["label"] == "2027-2028 Güz"][0]
    assert guz["timeCheck"] == "var" and guz["timeDeferred"], guz
    assert any("Saat çakışması" in a for a in h["assumptions"])


def test_CAKISMAYAN_iki_ders_ayni_donemde(tmp_path):
    con = _katalog(tmp_path, [("AAA 401", 7, 3, [(1, 510, 630)]),
                              ("AAA 402", 7, 3, [(2, 510, 630)])])
    yer = _nerede(_kur(con))
    assert yer["AAA 401"] == yer["AAA 402"] == "2027-2028 Güz", yer


def test_OBUR_MEVSIMDE_saat_bilinmiyor_kisitlama_yok(tmp_path):
    # 8. yarıyıl (Bahar) dersleri — bu Güz'ün verisi onların saatini söylemez.
    con = _katalog(tmp_path, [("AAA 403", 8, 3, None), ("AAA 404", 8, 3, None)])
    h = _kur(con)
    bahar = [t for t in h["terms"] if t["items"]][0]
    assert bahar["label"].endswith("Bahar") and bahar["timeCheck"] == "yok"
    assert {i["course"] for i in bahar["items"]} == {"AAA 403", "AAA 404"}


def test_MESGUL_SAAT_subeyi_eliyor_ve_gerekce(tmp_path):
    con = _katalog(tmp_path, [("AAA 401", 7, 3, [(1, 510, 630)]),
                              ("AAA 402", 7, 3, [(2, 510, 630)])])
    h = _kur(con, mesgul=REC.busy_sections(["Pzt 08:30-17:30 iş"]))
    yer = _nerede(h)
    assert "AAA 401" not in yer and yer["AAA 402"] == "2027-2028 Güz", yer
    neden = {u["course"]: u["reason"] for u in h["unplaced"]}
    assert "meşgul saatlerinizle çakışmaktadır" in neden["AAA 401"], neden
    assert any("Meşgul saatleriniz" in a for a in h["assumptions"])


def test_HAFTALIK_BUTCE(tmp_path):
    # Saati bilinmeyen (Bahar) 6'şar kredilik iki ders; meşgul saatler haftayı
    # 8 saate indiriyor → ikisi (≈12 sa) aynı döneme sığmıyor.
    con = _katalog(tmp_path, [("AAA 403", 8, 6, None), ("AAA 404", 8, 6, None)])
    mesgul = REC.busy_sections([f"{g} 08:30-17:30 iş" for g in ("Pzt", "Sal", "Çar", "Per")]
                               + ["Cum 08:30-09:30 iş"])
    h = _kur(con, mesgul=mesgul)
    dolu = [t for t in h["terms"] if t["items"]]
    assert all(len(t["items"]) == 1 for t in dolu), [(t["label"], t["items"]) for t in dolu]
    assert any(t["hourDeferred"] for t in dolu)
    assert dolu[0]["availableMinutes"] == 480


def test_ARAYUZ_ve_CAGIRANLAR():
    assert 'bu dönemin şube saatleriyle çakışmasız program kurulabiliyor' in KAYNAK
    assert "Saat çakışması nedeniyle bu döneme" in KAYNAK
    # Dört çağıran da meşgul saatleri geçiriyor (sayfa, senaryo, kalma riski, ÇAP).
    assert KAYNAK.count("mesgul=REC.busy_sections(settings.mesgul)") == 4
