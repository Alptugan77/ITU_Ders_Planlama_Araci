"""Faz 120 — "alınamayan dersler" paneli dilekçesiz denk dersi görüyor.

Kullanıcı (28.09.2026): *"BLG 317 bu dönem açılmamış gözüküyor ama yeni
adıyla BBF 302 açılmış"*. Faz 117'den beri denk ders öneride "BLG 317E
yerine" çıkabiliyordu, ama engel paneli aynı dersi hâlâ "bu dönem açılmamış"
diye sayıyordu. Kullanıcının kendi verisiyle ölçüldü: BBF 302E açık ve ÇAP
koduna (BLG) açık, ancak önşartı BLG 252E (yeni kodu BBF 203E) geçilmemiş;
asıl engel arz değil ÖNŞART. Artık:
* denk açık ve önşartı tutuyorsa `DENK_ACIK` — engel değil, durum (panelde
  "alınamayan" sayılmıyor, öneri "X yerine" diyor);
* denk açık ama önşartı eksikse `ONSART`, eksik dersiyle ve denk adıyla;
* denk yalnız başka programa açıksa (dilekçe gerekir) eskisi gibi `ACILMAMIS`.
"""
from itucap import prereq as P, recommend as REC
from test_faz117_denk_aday import _denk
from test_recommend import dbs  # noqa: F401  (fixture)


def _engel(dbs, kendi=("HTAE", "BLG")):  # noqa: F811
    con, ucon, sid = dbs
    con.execute("DELETE FROM lesson_meeting WHERE crn IN (SELECT crn FROM lesson WHERE course_code='BLG 212E')")
    con.execute("DELETE FROM lesson_allowed_program WHERE crn IN (SELECT crn FROM lesson WHERE course_code='BLG 212E')")
    con.execute("DELETE FROM lesson WHERE course_code='BLG 212E'")
    con.commit()
    P.parse_all(con)
    b = REC.cap_blockers(con, ucon, sid, 20, "BLG", {"HTAE", "BLG", "BLGE"}, dil_esi=True,
                         kendi_programlar=list(kendi) if kendi else None)
    return next(x for x in b if x.course == "BLG 212E")


def test_DENK_ACIK_ve_onsarti_tutuyor_engel_degil(dbs):  # noqa: F811
    _denk(dbs[0], "DNK 212E")
    b = _engel(dbs)
    assert b.reason == "DENK_ACIK", b
    assert "resmî denkliği DNK 212E açılmıştır ve dilekçesiz alınabilir" in b.detail
    assert "BLG 212E yerine" in b.detail


def test_DENK_ACIK_ama_ONSART_eksik(dbs):  # noqa: F811
    _denk(dbs[0], "DNK 212E")
    dbs[0].execute("INSERT INTO course(code,name) VALUES ('ONS 101','Önşart')")
    dbs[0].execute("UPDATE course SET prereq_raw='ONS 101 MIN DD' WHERE code='DNK 212E'")
    dbs[0].commit()
    b = _engel(dbs)
    assert b.reason == "ONSART", b
    assert b.detail.startswith("eksik: ONS 101") and "resmî denkliği DNK 212E açılmıştır" in b.detail
    # Faz 131 — önşart eksikken "alınabilir" denmiyor; sayılma ayrı yazılıyor.
    assert "alınabilir" not in b.detail
    assert "önşartı tamamlanmadan alınamaz" in b.detail
    assert "dilekçesiz BLG 212E yerine sayılır" in b.detail


def test_DENK_BASKA_PROGRAMA_acik_ACILMAMIS_kalir(dbs):  # noqa: F811
    _denk(dbs[0], "DNK 212E", progs=("MAK",))
    b = _engel(dbs)
    assert (b.reason, b.detail) == ("ACILMAMIS", "bu dönem şube açılmamıştır")


def test_KENDI_PROGRAM_verilmezse_eski_davranis(dbs):  # noqa: F811
    _denk(dbs[0], "DNK 212E")
    assert _engel(dbs, kendi=None).reason == "ACILMAMIS"


def test_ARAYUZ_kendi_programlari_geciyor_ve_panel_saymiyor():
    import pathlib
    from itucap import ui as UI
    k = pathlib.Path(UI.__file__).read_text(encoding="utf-8")
    assert k.count("kendi_programlar=kendi_programlar)]") == 2
    etiketler = k[k.index("const LABELS = {"):k.index("};", k.index("const LABELS = {"))]
    assert "DENK_ACIK" not in etiketler, "denk açık ders 'alınamayan' sayılmamalı"
