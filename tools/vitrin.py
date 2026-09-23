#!/usr/bin/env python3
"""Vitrin — gerçekçi ama UYDURMA bir öğrenciyle arayüzü açar (Faz 56).

Neden var: her tasarım turu (Faz 39, 46, 48, 50, 51) ekranı ölçerek
başladı ve her biri kendi küçük veri setini elle kurdu — üç dersli bir
anadal, tek şubeli bir ÇAP. O verilerle ızgara hiç dolmuyor, ton merdiveni
hiç tekrar etmiyor, not dağılımı hiç çizilmiyor, "ne değişti" hiç
görünmüyor. Yani tasarım, kullanıcının gördüğü ekranın küçük bir
kopyasında ölçülüyordu.

Bu araç tek bir kurgusal öğrenci kuruyor: HTAE anadalı 5. dönemde, BLG'de
ÇAP'a 5. yarıyılda başlamış, dört dönemlik transkripti var (biri FF),
cuma öğleden sonrası stajda. Katalog İTÜ'nün gerçek ders KODLARINI taşıyor
(ekran tanıdık görünsün diye) ama şubeler, hocalar, kontenjanlar ve
notlar UYDURMA — hiçbir kişiye ya da gerçek döneme ait değil.

⚠️ Veri geçici bir klasörde kuruluyor; depodaki `data/` ve `config/`e
DOKUNULMUYOR. Gizlilik denetimi transkript SATIRI arıyor (`KOD  NOT`);
burada notlar Python demetinde, o biçimde değil.

Kullanım:
    python tools/vitrin.py                 # kurar, sunucuyu açar, adresi yazar
    python tools/vitrin.py --ekran DIZIN   # her görünümün ekran görüntüsü
                                           # (Playwright gerekir)
"""
from __future__ import annotations

import argparse
import sys
import tempfile
import threading
import time
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK / "src"))

DONEM = "202610"          # 2026-2027 Güz

# (kod, ad, kredi, AKTS, önşart metni) — önşart metni OBS'nin biçiminde.
DERSLER = [
    # --- HTAE 1. dönem
    ("MAT 103E", "Mathematics I", 4, 6, None),
    ("FIZ 101E", "Physics I", 3, 5, None),
    ("FIZ 101EL", "Physics I Laboratory", 1, 1.5, None),
    ("KIM 101E", "General Chemistry I", 3, 5, None),
    ("GEO 101E", "Introduction to Geomatics", 3, 5, None),
    ("ING 101", "English I", 3, 4, None),
    ("TUR 121", "Türk Dili I", 2, 2, None),
    ("ATA 121", "Atatürk İlkeleri ve İnkılap Tarihi I", 2, 2, None),
    # --- 2. dönem
    ("MAT 104E", "Mathematics II", 4, 6, "MAT 103E MIN DD veya MAT 103 MIN DD"),
    ("FIZ 102E", "Physics II", 3, 5, "FIZ 101E MIN DD"),
    ("GEO 102E", "Basic Surveying", 3, 5, "GEO 101E MIN DD"),
    ("BLG 101E", "Introduction to Programming", 3, 5, None),
    ("ING 102", "English II", 3, 4, "ING 101 MIN DD"),
    ("TUR 122", "Türk Dili II", 2, 2, None),
    ("ATA 122", "Atatürk İlkeleri ve İnkılap Tarihi II", 2, 2, None),
    # --- 3. dönem
    ("MAT 201E", "Linear Algebra", 3, 5, "MAT 104E MIN DD"),
    ("GEO 211E", "Map Projections", 3, 5, "GEO 102E MIN DD"),
    ("GEO 221E", "Adjustment Computation I", 3, 5, "MAT 104E MIN DD"),
    ("GEO 231E", "Photogrammetry I", 3, 5, None),
    ("EKO 201E", "Economics", 3, 4, None),
    # --- 4. dönem
    ("MAT 210E", "Numerical Methods", 3, 5, "MAT 201E MIN DD"),
    ("GEO 222E", "Adjustment Computation II", 3, 5, "GEO 221E MIN DD"),
    ("GEO 242E", "Remote Sensing", 3, 5, None),
    ("GEO 252E", "Geodesy", 3, 5, "GEO 211E MIN DD"),
    ("ING 201", "English III", 3, 4, "ING 102 MIN DD"),
    # --- 5. dönem (bu dönem)
    ("GEO 315E", "Cadastre", 3, 5, None),
    ("GEO 321E", "Satellite Geodesy", 3, 5, "GEO 252E MIN DD"),
    ("GEO 331E", "Geographic Information Systems", 3, 5, "BLG 101E MIN DD"),
    ("GEO 341E", "Engineering Surveying", 3, 5, "GEO 222E MIN DD"),
    ("GEO 351E", "Photogrammetry II", 3, 5, "GEO 231E MIN DD"),
    # --- 6. dönem
    ("GEO 302E", "Land Management", 3, 5, "GEO 315E MIN DD"),
    ("GEO 364E", "Hydrography", 3, 5, None),
    ("GEO 372E", "Laser Scanning", 3, 5, "GEO 351E MIN DD"),
    # --- 7–8. dönem
    ("GEO 401E", "Graduation Project I", 3, 8, "GEO 341E MIN DD"),
    ("GEO 464E", "Spatial Data Infrastructure", 3, 5, "GEO 331E MIN DD"),
    ("GEO 4902E", "Graduation Project II", 3, 10, "GEO 401E MIN DD"),
    # --- seçmeli havuz (MT)
    ("GEO 381E", "Urban Mapping", 3, 5, None),
    ("GEO 383E", "Deformation Monitoring", 3, 5, None),
    ("GEO 385E", "Navigation Systems", 3, 5, None),
    # --- BLG ÇAP
    ("BLG 102E", "Introduction to Scientific and Engineering Computing", 3, 5, None),
    ("BLG 223E", "Data Structures", 3, 5, "BLG 102E MIN DD veya BLG 101E MIN DD"),
    ("BLG 231E", "Digital Circuits", 3, 5, None),
    ("BLG 222E", "Computer Organization", 3, 5, "BLG 231E MIN DD"),
    ("BLG 252E", "Object Oriented Programming", 3, 5, "BLG 102E MIN DD"),
    ("BLG 311E", "Formal Languages and Automata", 3, 5, "BLG 223E MIN DD"),
    ("BLG 335E", "Analysis of Algorithms I", 3, 5, "BLG 223E MIN DD"),
    ("BLG 336E", "Analysis of Algorithms II", 3, 5, "BLG 335E MIN DD"),
    ("BLG 317E", "Database Systems", 3, 5, "BLG 223E MIN DD"),
    ("BLG 312E", "Computer Operating Systems", 3, 5, "BLG 222E MIN DD"),
    ("BLG 361E", "Software Engineering", 3, 5, "BLG 252E MIN DD"),
]

HTAE_PLAN = {
    1: ["MAT 103E", "FIZ 101E", "FIZ 101EL", "KIM 101E", "GEO 101E", "ING 101",
        "TUR 121", "ATA 121"],
    2: ["MAT 104E", "FIZ 102E", "GEO 102E", "BLG 101E", "ING 102", "TUR 122",
        "ATA 122"],
    3: ["MAT 201E", "GEO 211E", "GEO 221E", "GEO 231E", "EKO 201E"],
    4: ["MAT 210E", "GEO 222E", "GEO 242E", "GEO 252E", "ING 201"],
    5: ["GEO 315E", "GEO 321E", "GEO 331E", "GEO 341E", "GEO 351E"],
    6: ["GEO 302E", "GEO 364E", "GEO 372E"],
    7: ["GEO 401E", "GEO 464E"],
    8: ["GEO 4902E"],
}
MT_HAVUZU = ["GEO 381E", "GEO 383E", "GEO 385E"]
BLG_CAP = ["BLG 102E", "BLG 223E", "BLG 231E", "BLG 222E", "BLG 252E",
           "BLG 311E", "BLG 335E", "BLG 336E", "BLG 317E", "BLG 312E",
           "BLG 361E"]

# Transkript: (ders, not, dönem). MAT 210E FF — alttan alınacak.
TRANSKRIPT = [
    *[(k, n, "202410") for k, n in zip(HTAE_PLAN[1],
      ["BB", "CB", "AA", "CC", "BA", "BB", "AA", "BA"])],
    *[(k, n, "202420") for k, n in zip(HTAE_PLAN[2],
      ["CB", "CC", "BB", "BA", "BB", "AA", "BB"])],
    *[(k, n, "202510") for k, n in zip(HTAE_PLAN[3],
      ["CC", "BB", "CB", "BA", "BB"])],
    *[(k, n, "202520") for k, n in zip(HTAE_PLAN[4],
      ["FF", "CB", "BB", "CC", "BA"])],
    ("BLG 102E", "BB", "202520"), ("BLG 231E", "CB", "202520"),
]

BINALAR = [("INB", "İnşaat Fakültesi"), ("EEB", "Elektrik-Elektronik Fakültesi"),
           ("FEB", "Fen-Edebiyat Fakültesi"), ("MED", "Maden Fakültesi"),
           ("KMB", "Kimya-Metalurji Fakültesi")]

# Şubeler: (crn, ders, kontenjan, kayıtlı, hoca, bina, yöntem,
#           [(gün, başlangıç, bitiş)], açık olduğu programlar)
S = 60


def _t(h: str) -> int:
    s, d = h.split(":")
    return int(s) * S + int(d)


SUBELER = [
    # --- 5. dönem anadal
    ("13601", "GEO 315E", 60, 41, "Prof. Dr. N. Aksoy", "INB", "Face to Face",
     [(1, _t("08:30"), _t("11:29"))], ["HTAE"]),
    ("13602", "GEO 321E", 55, 52, "Doç. Dr. E. Tunç", "INB", "Face to Face",
     [(2, _t("09:30"), _t("12:29"))], ["HTAE"]),
    ("13640", "GEO 321E", 40, 12, "Doç. Dr. E. Tunç", "INB", "Face to Face",
     [(4, _t("13:30"), _t("16:29"))], ["HTAE"]),
    ("13603", "GEO 331E", 70, 70, "Dr. Öğr. Üyesi S. Kara", "INB", "Face to Face",
     [(3, _t("08:30"), _t("11:29"))], ["HTAE"]),
    ("13641", "GEO 331E", 45, 30, "Dr. Öğr. Üyesi S. Kara", "", "Virtual (Online)",
     [(3, _t("13:30"), _t("16:29"))], ["HTAE"]),
    ("13604", "GEO 341E", 60, 35, "Prof. Dr. M. Özer", "INB", "Face to Face",
     [(1, _t("13:30"), _t("15:29")), (4, _t("08:30"), _t("09:29"))], ["HTAE"]),
    ("13605", "GEO 351E", 50, 18, "Doç. Dr. A. Şahin", "INB", "Face to Face",
     [(2, _t("13:30"), _t("16:29"))], ["HTAE"]),
    # --- alttan / havuz
    ("21150", "MAT 210E", 120, 97, "Dr. Öğr. Üyesi B. Yıldız", "FEB", "Face to Face",
     [(4, _t("10:30"), _t("12:29")), (5, _t("08:30"), _t("09:29"))],
     ["HTAE", "BLG", "INS"]),
    ("21151", "MAT 210E", 90, 90, "Dr. Öğr. Üyesi B. Yıldız", "FEB", "Face to Face",
     [(2, _t("14:30"), _t("17:29"))], ["HTAE", "BLG"]),
    ("13660", "GEO 381E", 35, 20, "", "INB", "Face to Face",
     [(5, _t("09:30"), _t("12:29"))], ["HTAE"]),
    ("13661", "GEO 385E", 30, 29, "Prof. Dr. N. Aksoy", "INB", "Face to Face",
     [(3, _t("12:30"), _t("14:29"))], ["HTAE"]),
    ("13662", "GEO 383E", 30, 8, "Doç. Dr. A. Şahin", "", "", [], ["HTAE"]),
    # --- üst dönem (kipte önerilmez ama elle eklenebilir)
    ("13670", "GEO 364E", 40, 22, "Dr. Öğr. Üyesi C. Er", "INB", "Face to Face",
     [(5, _t("13:30"), _t("16:29"))], ["HTAE"]),
    ("13671", "GEO 401E", 60, 10, "", "INB", "Face to Face",
     [(4, _t("14:30"), _t("17:29"))], ["HTAE"]),
    # --- BLG ÇAP
    ("22301", "BLG 223E", 80, 64, "Doç. Dr. H. Çelik", "EEB", "Face to Face",
     [(1, _t("11:30"), _t("13:29")), (3, _t("11:30"), _t("12:29"))], ["BLG", "HTAE"]),
    ("22302", "BLG 223E", 80, 80, "Prof. Dr. T. Güneş", "EEB", "Face to Face",
     [(2, _t("08:30"), _t("11:29"))], ["BLG", "HTAE"]),
    ("22303", "BLG 252E", 70, 48, "Dr. Öğr. Üyesi K. Arslan", "EEB", "Face to Face",
     [(4, _t("08:30"), _t("11:29"))], ["BLG", "HTAE"]),
    ("22304", "BLG 222E", 90, 71, "Prof. Dr. O. Demirci", "EEB", "Face to Face",
     [(5, _t("12:30"), _t("15:29"))], ["BLG", "HTAE"]),
    ("22305", "BLG 222E", 60, 58, "Prof. Dr. O. Demirci", "", "Virtual (Online)",
     [(1, _t("15:30"), _t("18:29"))], ["BLG", "HTAE"]),
    ("22306", "BLG 311E", 70, 70, "Doç. Dr. R. Koç", "EEB", "Face to Face",
     [(3, _t("14:30"), _t("17:29"))], ["BLG"]),
    ("22307", "BLG 317E", 60, 20, "Dr. Öğr. Üyesi P. Uslu", "EEB", "Face to Face",
     [(2, _t("15:30"), _t("17:29"))], ["BLG", "HTAE"]),
]

# Not dağılımı — (anahtar, dönem, {not: öğrenci}) — UYDURMA sayılar.
DAGILIMLAR = [
    ("GEO 315", "202510", {"AA": 9, "BA+": 3, "BA": 11, "BB+": 4, "BB": 14,
                           "CB+": 2, "CB": 10, "CC+": 1, "CC": 8, "DC": 5,
                           "DD": 3, "FF": 4, "VF": 1}),
    ("GEO 315", "202410", {"AA": 7, "BA": 12, "BB": 15, "CB": 11, "CC": 9,
                           "DC": 4, "DD": 3, "FF": 6, "VF": 2}),
    ("MAT 210", "202510", {"AA": 6, "BA": 8, "BB": 12, "CB": 15, "CC": 18,
                           "DC": 14, "DD": 11, "FF": 22, "VF": 9}),
    ("BLG 223", "202510", {"AA": 14, "BA+": 2, "BA": 10, "BB": 12, "CB": 11,
                           "CC": 9, "DC": 7, "DD": 5, "FF": 10, "VF": 4}),
    ("GEO 321", "202420", {"AA": 3, "BA": 4, "BB": 6, "CB": 5, "CC": 3,
                           "DD": 2, "FF": 1}),
]


def kur(kok: Path) -> Path:
    """`kok` altında config/ ve data/ kurar; `config` modülünü oraya çevirir."""
    from itucap import config, db
    from itucap import prereq as P
    from itucap import student as ST

    (kok / "config").mkdir(parents=True, exist_ok=True)
    (kok / "data").mkdir(parents=True, exist_ok=True)
    # ★ Mevzuat dosyaları da (Faz 57'de fark edildi): `policy` onları
    # `config.ROOT` altından okuyor ve kök buraya çevrildiği için vitrin
    # öğrencisinin HİÇ mevzuatı yoktu — GNO eşiği, kredi basamakları, ÇAP
    # yarıyıl tabanı. Yayınlanan site bu iki dosyayı taşıyor; vitrin de.
    import shutil
    for ad in ("kurallar.toml", "katalog-duzeltmeleri.toml"):
        shutil.copy(KOK / "config" / ad, kok / "config" / ad)
    (kok / "config" / "settings.toml").write_text(
        "[student]\n"
        'anadal_program = "HTAE"\n'
        'second_kind = "cap"\n'
        'cap_program = "BLG"\n'
        "cap_plan_id = 2229\n"
        "anadal_plan_id = 2295\n"
        f'term = "{DONEM}"\n'
        "donem = 5\n"
        "cap_baslangic_yariyili = 5\n"
        "max_load = 22\n"
        'mesgul = ["CUM 13:30-17:30 staj"]\n',
        encoding="utf-8")
    config.ROOT = kok
    config.DATA_DIR = kok / "data"
    config.REF_DB = kok / "data" / "reference.sqlite3"
    config.USER_DB = kok / "data" / "user.sqlite3"

    con = db.connect(config.REF_DB, "schema.sql")
    con.executemany("INSERT INTO program(code,name,faculty,level) VALUES (?,?,?,'LS')",
                    [("HTAE", "Geomatik Mühendisliği", "İnşaat"),
                     ("BLG", "Bilgisayar Mühendisliği", "Bilgisayar ve Bilişim"),
                     ("INS", "İnşaat Mühendisliği", "İnşaat")])
    con.executemany("INSERT INTO building(code,name,campus) VALUES (?,?,'Ayazağa')",
                    BINALAR)
    for kod, ad, kredi, akts, onsart in DERSLER:
        con.execute("INSERT INTO course(code,name,credits,ects,prereq_raw,language)"
                    " VALUES (?,?,?,?,?,?)",
                    (kod, ad, kredi, akts, onsart,
                     "tr" if not kod.split()[1][-1:].isalpha() else "en"))
    kredi = {k: (c, e) for k, _, c, e, _ in DERSLER}

    con.execute("INSERT INTO plan(id,program_code,plan_type,obs_program_code,title,"
                "source,is_term_based) VALUES (2295,'HTAE','lisans','HTAE_LS',"
                "'HTAE Undergraduate Program','obs',1)")
    poz = 0
    for donem, kodlar in HTAE_PLAN.items():
        for kod in kodlar:
            c, e = kredi[kod]
            con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,credits,"
                        "ects,position,term_no) VALUES (2295,'REQUIRED',?,?,?,?,?)",
                        (kod, c, e, poz, donem))
            poz += 1
        if donem == 5:
            cur = con.execute(
                "INSERT INTO plan_slot(plan_id,slot_kind,pool_label_raw,pool_category,"
                "credits,ects,position,term_no) VALUES (2295,'ELECTIVE_POOL',"
                "'Meslek Seçmeli (MT)','MT',3,5,?,5)", (poz,))
            poz += 1
            for kod in MT_HAVUZU:
                con.execute("INSERT INTO pool_option(slot_id,course_code) VALUES (?,?)",
                            (cur.lastrowid, kod))

    con.execute("INSERT INTO plan(id,program_code,host_program_code,plan_type,"
                "obs_program_code,title,source,is_term_based) VALUES (2229,'BLG',"
                "'HTAE','cap','TUMMUH_BLG','BLG Double Major Program','obs',0)")
    con.execute("INSERT INTO plan_host_program(plan_id,program_code,obs_code,"
                "program_name) VALUES (2229,'HTAE','HTAE_LS','Geomatik Mühendisliği')")
    for i, kod in enumerate(BLG_CAP):
        c, e = kredi[kod]
        con.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,credits,ects,"
                    "position) VALUES (2229,'REQUIRED',?,?,?,?)", (kod, c, e, i))

    import datetime as dt
    simdi = dt.datetime.now().replace(microsecond=0)
    for crn, kod, kon, kay, hoca, bina, yontem, bul, prog in SUBELER:
        con.execute("INSERT INTO lesson(crn,term,course_code,course_title,instructor,"
                    "building,teaching_method,capacity,enrolled,updated_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (crn, DONEM, kod, "", hoca, bina, yontem, kon, kay,
                     (simdi - dt.timedelta(hours=5)).isoformat()))
        for p in prog:
            con.execute("INSERT INTO lesson_allowed_program(crn,program_code)"
                        " VALUES (?,?)", (crn, p))
        for gun, bas, bit in bul:
            con.execute("INSERT INTO lesson_meeting(crn,day_of_week,start_min,end_min,"
                        "building,room) VALUES (?,?,?,?,?,?)",
                        (crn, gun, bas, bit, bina, "D" + crn[-2:] if bina else ""))

    # İki anlık görüntü — "Ne değişti" boş kalmasın. Eski görüntüde iki
    # şube daha boştu, BLG 317E hiç yoktu.
    for i, taken in enumerate([simdi - dt.timedelta(days=1, hours=5),
                               simdi - dt.timedelta(hours=5)]):
        stamp = taken.isoformat()
        con.execute("INSERT INTO snapshot_run(taken_at,lessons) VALUES (?,?)",
                    (stamp, len(SUBELER)))
        for crn, kod, kon, kay, *_ in SUBELER:
            if i == 0 and kod == "BLG 317E":
                continue
            eski = kay - 6 if (i == 0 and crn in {"13603", "22302", "22306"}) else kay
            con.execute("INSERT INTO lesson_snapshot(taken_at,crn,course_code,capacity,"
                        "enrolled) VALUES (?,?,?,?,?)", (stamp, crn, kod, kon, eski))

    yil = {"202510": "2025-2026", "202410": "2024-2025", "202420": "2024-2025"}
    ad = {"10": "Fall Semester", "20": "Spring Semester"}
    for anahtar, donem, sayilar in DAGILIMLAR:
        top = sum(sayilar.values())
        for harf, n in sayilar.items():
            con.execute("INSERT INTO grade_distribution(course_key,term,grade,students,"
                        "announced,term_name,year_name) VALUES (?,?,?,?,?,?,?)",
                        (anahtar, donem, harf, n, top, ad[donem[-2:]], yil[donem]))
        for kod in (anahtar + "E", anahtar):
            con.execute("INSERT OR IGNORE INTO grade_distribution_alias(course_code,"
                        "course_key) VALUES (?,?)", (kod, anahtar))
    con.commit()
    P.parse_all(con)
    con.close()

    ucon = db.connect(config.USER_DB, "schema_user.sql")
    sid = ST.ensure_student(ucon)
    ST.enroll(ucon, sid, 2295, "ANADAL", "HTAE")
    ST.enroll(ucon, sid, 2229, "CAP", "BLG")
    for kod, harf, donem in TRANSKRIPT:
        girdi = ST.make_entry(kod, harf)
        ST.add_entries(ucon, sid, [girdi], term=donem)
    ucon.close()
    return kok


def ac(kok: Path | None = None) -> tuple[str, object]:
    """Kurar ve yerel sunucuyu açar. (adres, sunucu) döner."""
    kok = kur(kok or Path(tempfile.mkdtemp(prefix="vitrin-")))
    from itucap import declared, server
    declared.DEFAULT_PATH = kok / "config" / "denklikler.toml"
    st = server.State(label="ben")
    h = server.build(st, host="127.0.0.1", port=0)
    threading.Thread(target=h.serve_forever, daemon=True).start()
    time.sleep(0.3)
    return f"http://127.0.0.1:{h.server_address[1]}/", h


GORUNUMLER = ["schedSection", "panels", "roadmapSection", "candSection", "tierSection",
              "blockSection", "creditSection", "changeSection", "basvuruSection"]


def ekran(adres: str, dizin: Path) -> list[Path]:
    """Her görünüm × (masaüstü, telefon) × (gece, gündüz)."""
    from playwright.sync_api import sync_playwright
    dizin.mkdir(parents=True, exist_ok=True)
    cikti = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        for ad, boyut, mobil in (("masaustu", {"width": 1440, "height": 900}, False),
                                 ("telefon", {"width": 390, "height": 844}, True)):
            for tema in ("dark", "light"):
                ctx = b.new_context(viewport=boyut, is_mobile=mobil, has_touch=mobil,
                                    color_scheme=tema)
                pg = ctx.new_page()
                pg.goto(adres, wait_until="networkidle")
                pg.wait_for_timeout(900)
                for g in GORUNUMLER:
                    var = pg.evaluate(
                        f"() => !!document.querySelector('#secnav a[data-gorunum=\"{g}\"]')")
                    if not var:
                        continue
                    pg.evaluate(f"() => gorunumAc && gorunumAc('{g}')")
                    pg.wait_for_timeout(250)
                    yol = dizin / f"{ad}-{tema}-{g}.png"
                    pg.screenshot(path=str(yol), full_page=True)
                    cikti.append(yol)
                ctx.close()
        b.close()
    return cikti


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ekran", type=Path, help="ekran görüntülerinin dizini")
    ap.add_argument("--kok", type=Path, help="verinin kurulacağı dizin (geçici)")
    a = ap.parse_args()
    adres, _ = ac(a.kok)
    if a.ekran:
        for yol in ekran(adres, a.ekran):
            print(yol)
        return 0
    print(f"vitrin açık: {adres}  (Ctrl+C ile kapat)")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
