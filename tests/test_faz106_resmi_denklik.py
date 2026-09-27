"""Faz 106 — resmî denklikler (OBS DersPlanDenklikleri).

Kullanıcı 27.09.2026: *"akts veya kredi farklıysa denklik olmuyor diye
biliyorum ama itü denklikleri yayınlıyor zaten
https://obs.itu.edu.tr/public/GenelTanimlamalar/DersPlanDenklikleri"*.

Kazıyıcı vardı (`sources/obs_equivalence.py`) ama adım isteğe bağlıydı ve
yayınlanan katalog onsuz kurulmuştu: `equivalence` tablosu BOŞ. Üç düzeltme:
`make all-plans` denklikleri de çekiyor; kalite raporu boş tabloyu söylüyor;
yol haritası önşartta denklikleri sayıyor (öneri motoru zaten sayıyordu).
"""
import sys
from pathlib import Path

import pytest

from itucap import declared as DEC, quality as Q, rules as R
from test_faz57_yol_haritasi import _katalog, _kur, _yer

KOK = Path(DEC.__file__).resolve().parents[2]
sys.path.insert(0, str(KOK / "tools"))
import kod_gocu_taramasi as KG  # noqa: E402


@pytest.fixture(autouse=True)
def beyansiz(tmp_path, monkeypatch):
    """Kod göçü beyanları bu testleri etkilemesin."""
    bos = tmp_path / "bos.toml"
    bos.write_text("", encoding="utf-8")
    monkeypatch.setattr(DEC, "CATALOG_PATH", bos)


def _denklik(con, kaynak, hedef):
    cur = con.execute("INSERT INTO equivalence(target_course, confidence) VALUES (?, 'official')", (hedef,))
    con.execute("INSERT INTO equivalence_source(equivalence_id, course_code) VALUES (?, ?)",
                (cur.lastrowid, kaynak))
    con.commit()


@pytest.fixture()
def katalog(tmp_path):
    # Plan YENI 101 (1.) → YAP 201 (2., önşartı ESKI 101). Resmî denklik: YENI 101 → ESKI 101.
    con = _katalog(tmp_path / "k", [("ESKI 101", 3, None), ("YENI 101", 3, None),
                                    ("YAP 201", 3, "ESKI 101 MIN DD")],
                   plan=[("YENI 101", 1), ("YAP 201", 2)])
    return con


def test_KALITE_bos_denklik_tablosunu_soyluyor(katalog):
    bul = lambda: [f for f in Q.run(katalog) if f.check_id == "official_equivalence_empty"]
    assert bul() and "DersPlanDenklikleri" in bul()[0].detail
    _denklik(katalog, "YENI 101", "ESKI 101")
    assert not bul()


def test_MAKE_all_plans_denklikleri_cekiyor():
    mk = (KOK / "Makefile").read_text(encoding="utf-8")
    assert "refresh --all-programs --all-equivalences" in mk


def test_TARAMA_resmi_denkligi_sayiyor(katalog):
    assert [e[3] for e in KG.tara(katalog)["engelli"]] == ["YAP 201"]
    _denklik(katalog, "YENI 101", "ESKI 101")
    assert KG.tara(katalog)["engelli"] == []


def test_YOL_HARITASI_onsartta_denklik(katalog):
    """Öğrenci YENI 101'i geçmiş; resmî denklik onu ESKI 101 sayıyor.
    YAP 201 (önşart ESKI 101) haritada yerleşmeli — eskiden önşart ham
    transkripte bakıyordu ve ESKI 101 hiçbir planda olmadığı için 'dış'
    sayılıyordu; burada ESKI 101'i plana koyarak dış kuralını devre dışı
    bırakıyoruz ki yalnız denklik açsın."""
    katalog.execute("INSERT INTO plan_slot(plan_id,slot_kind,course_code,credits,position,term_no)"
                    " VALUES (1,'REQUIRED','ESKI 101',3,9,1)")
    katalog.commit()
    _denklik(katalog, "YENI 101", "ESKI 101")
    esd = R.load_equivalences(katalog)
    h = _kur(katalog, {"YENI 101": "BB"}, donem=2, equivalences=esd)
    assert "YAP 201" in _yer(h), h["unplaced"]
    # Denklikle KARŞILANIYOR, varsayılmıyor: eskiden ESKI 101 "dış önşart"
    # sayılıp geçilmiş varsayılıyordu (kartta "dış önşart varsayıldı").
    dis = {i["course"]: i["externalPrereq"] for t in h["terms"] for i in t["items"]}
    assert dis["YAP 201"] == []
    assert "ESKI 101" not in _yer(h)                  # slot da denklikle dolu


def test_BEYAN_resmi_karsilastirma(katalog, tmp_path, monkeypatch):
    """Faz 107 — beyanlar resmî tabloyla karşılaştırılıyor (tek kaynaklı bağ,
    iki yönden biri); çok kaynaklı "A + B → C" kod göçü sayılmıyor."""
    dosya = tmp_path / "goc.toml"
    dosya.write_text('[[kod_gocu]]\neski = "ESKI 101"\nyeni = "YENI 101"\nnot_ = "t"\n'
                     '[[kod_gocu]]\neski = "YAP 201"\nyeni = "YENI 101"\nnot_ = "t"\n'
                     '[[kod_gocu]]\neski = "YAP 201"\nyeni = "ESKI 101"\nnot_ = "t"\n', encoding="utf-8")
    monkeypatch.setattr(DEC, "CATALOG_PATH", dosya)
    assert KG.beyan_karsilastir(katalog)["resmi_sayi"] == 0
    _denklik(katalog, "ESKI 101", "YENI 101")               # ters yön de sayılır
    cur = katalog.execute("INSERT INTO equivalence(target_course, confidence) VALUES ('YAP 201','official')")
    katalog.executemany("INSERT INTO equivalence_source(equivalence_id, course_code) VALUES (?,?)",
                        [(cur.lastrowid, "YENI 101"), (cur.lastrowid, "ESKI 101")])
    katalog.commit()
    k = KG.beyan_karsilastir(katalog)
    assert k["karsilanan"] == [("ESKI 101", "YENI 101")]
    # İki kaynaklı denklik (sıra ne olursa olsun) hiçbir kaynağı için göç değil.
    assert k["karsiliksiz"] == [("YAP 201", "YENI 101"), ("YAP 201", "ESKI 101")]
