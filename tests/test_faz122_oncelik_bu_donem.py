"""Faz 122 — öncelik ayarı bu dönemin önerisine de; ÇAP tabanı saate bakıyor.

Kullanıcı (28.09.2026): *"anadala öncelik verince BLG 223E yerine GEO 307E'yi
neden almıyor"*. Kullanıcının kendi verisiyle ölçüldü (HTAE + BLG ÇAP):
* Ayar yalnız gelecek dönemleri yerleştiriyordu; bu dönemin önerisi ÇAP'a
  sabit +150 (kritik yol + rol) veriyordu → BLG 223E hep Salı 08:30'u alıyor.
* Salt puan değiştirmek yetmedi: anadal yine 9. yarıyıl, ÇAP 8 → 10. Sebep
  haritanın ÇAP TABANI geçişi: tabanı saate bakmadan BLG 223E ile
  dolduruyor, GEO 227E (FF) ve GEO 403E bir yıl kayıyordu — oysa aynı
  dönemin öbür ÇAP dersleri tabanı dolduruyordu.
Şimdi "anadal" ayarında: anadal 8. yarıyıl (planındaki), ÇAP 12; "birlikte":
anadal 9, ÇAP 8 — takas iki yönde de ölçülü görünüyor. Saatli taban kuralı
aramaya EK aday: 383 gerçek çiftte hiçbir sonuç kötüleşmedi, 13–34 çift
iyileşti.
"""
import pathlib

from itucap import db, policy as POL, prereq as P
from itucap import recommend as REC
from itucap import ui as UI
from itucap import yolharitasi as YH

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


def _aday(kod, rol, kritik=False):
    return REC.Candidate(course=kod, name=kod, role=rol, ects=5, credits=3, unlocks=0,
                         tier=0, critical=kritik, required=True, sections=[])


def test_PUAN_anadal_onceliginde_rol_artisi_anadala():
    ana, cap = _aday("GEO 307E", "ANADAL"), _aday("BLG 223E", "CAP", kritik=True)
    REC.score_all([ana, cap])
    assert cap.score > ana.score
    assert {p["key"] for p in cap.parts} >= {"critical", "cap_role"}
    ana, cap = _aday("GEO 307E", "ANADAL"), _aday("BLG 223E", "CAP", kritik=True)
    REC.score_all([ana, cap], "anadal")
    assert ana.score > cap.score
    assert "anadal_oncelik" in {p["key"] for p in ana.parts}
    assert not {"critical", "cap_role"} & {p["key"] for p in cap.parts}
    assert "ÇAP kritik yolunda (anadal önceliği seçili)" in cap.reasons   # bilgi kalıyor
    assert sum(p["points"] for p in ana.parts) == ana.score               # kırılım tutuyor


def _katalog(tmp_path):
    """Bu dönem Güz (202610) ve planlar Güz: anadal AAA 301 (Pzt 08:30),
    ÇAP CCC 301 (Pzt 08:30 — çakışıyor, zinciri uzun) ve CCC 302 (Sal)."""
    con = db.connect(tmp_path / "ref.sqlite3", "schema.sql")
    con.execute("INSERT INTO program(code,name,level) VALUES ('AAA','A','LS'),('CCC','C','LS')")
    con.execute("INSERT INTO plan(id,program_code,plan_type,title,source) VALUES (1,'AAA','lisans','a','obs')")
    con.execute("INSERT INTO plan(id,program_code,host_program_code,plan_type,title,source) "
                "VALUES (2,'CCC','AAA','cap','c','obs')")
    dersler = [("AAA 301", 1, 5, 1), ("CCC 301", 2, 5, 1), ("CCC 302", 2, 5, 2), ("CCC 401", 2, 7, None)]
    for i, (kod, plan, donem, gun) in enumerate(dersler):
        con.execute("INSERT INTO course(code,name,credits,ects,prereq_raw) VALUES (?,?,3,5,?)",
                    (kod, kod, "CCC 301 MIN DD" if kod == "CCC 401" else None))
        con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,credits,position,term_no) "
                    "VALUES (?,'REQUIRED',?,3,?,?)", (plan, kod, i, donem))
        if gun:
            crn = str(100 + i)
            con.execute("INSERT INTO lesson(crn,term,course_code,capacity,enrolled) VALUES (?,'202610',?,50,0)",
                        (crn, kod))
            con.execute("INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min) VALUES (?,?,510,630)",
                        (crn, gun))
            for p in ("AAA", "CCC"):
                con.execute("INSERT INTO lesson_allowed_program(crn,program_code) VALUES (?,?)", (crn, p))
    P.parse_all(con)
    con.commit()
    return con


PLANLAR = [{"planId": 1, "role": "ANADAL", "label": "anadal", "program": "AAA"},
           {"planId": 2, "role": "CAP", "label": "ÇAP", "program": "CCC"}]
TABAN = POL.SecondFloor(minimum=3, start_term=3, verified=True, source="test")


def _yer(h):
    return {i["course"]: t["index"] for t in h["terms"] for i in t["items"] if i["course"]}


def test_TABAN_saatli_one_yer_birakiyor(tmp_path):
    """Bu dönem Güz: saat denetimi sonraki Güz'lerde (2 ve 4) çalışıyor."""
    con = _katalog(tmp_path)
    kw = dict(term="202510", donem=5, max_load=6, bu_donem=[], taban=TABAN)
    # Eski taban: CCC 301 (zinciri uzun, sırada önde) tabanı dolduruyor → AAA 301 kayıyor.
    eski = YH.kur(con, {}, PLANLAR, oncelik="anadal_once", **kw)
    assert _yer(eski)["CCC 301"] == 2 and _yer(eski)["AAA 301"] == 4, _yer(eski)
    # Aramada saatli taban: taban CCC 302 ile doluyor, AAA 301 ilk Güz'de.
    h = YH.kur(con, {}, PLANLAR, oncelik="anadal", **kw)
    assert _yer(h)["AAA 301"] == 2 and _yer(h)["CCC 302"] == 2, _yer(h)
    assert h["priority"]["floorByTime"] is True
    assert h["priority"]["options"]["anadal"]["floorByTime"] is True


def test_TABAN_yoksa_ek_kurulum_yok(tmp_path, monkeypatch):
    con = _katalog(tmp_path)
    say = []
    asil = YH._kur
    monkeypatch.setattr(YH, "_kur", lambda *a, **k: say.append(k["taban_saatli"]) or asil(*a, **k))
    YH.kur(con, {}, PLANLAR, term="202510", donem=5, max_load=6, bu_donem=[], oncelik="anadal")
    assert say == [False, False, False]
    say.clear()
    YH.kur(con, {}, PLANLAR, term="202510", donem=5, max_load=6, bu_donem=[], taban=TABAN,
           oncelik="anadal")
    assert sorted(say) == [False] * 3 + [True] * 3


def test_ARAYUZ_oneri_ve_bu_donem_adaylari():
    assert "oncelik=settings.yol_onceligi)                # Faz 122" in KAYNAK
    assert 'and (h["chain"] >= 2 or h["course"] in saatle)][:5]' in KAYNAK
