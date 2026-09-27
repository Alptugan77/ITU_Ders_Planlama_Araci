"""Faz 105 — kod göçü taraması ve grup olarak uygulama.

Faz 104 BBF göçünü tek bir gezide bulmuştu. Bu faz aynı hata sınıfını
BÜTÜN lisans planlarında arıyor (`tools/kod_gocu_taramasi.py`): plana sadık
öğrenci kendi planının dersinden önşart yüzünden engelleniyor mu. Gerçek
katalogda 126 engelli dersin 17'si, iki bağımsız kanıtı olan 17 yeni beyanla
açıldı (ad + kredi + AKTS aynı VE planın kendi dönem sırası).
"""
import sys
import tomllib
from pathlib import Path

import pytest

from itucap import declared as DEC, rules as R
from test_faz57_yol_haritasi import _katalog

KOK = Path(DEC.__file__).resolve().parents[2]
sys.path.insert(0, str(KOK / "tools"))
import kod_gocu_taramasi as KG  # noqa: E402


@pytest.fixture()
def beyan(tmp_path, monkeypatch):
    dosya = tmp_path / "katalog.toml"
    dosya.write_text("", encoding="utf-8")
    monkeypatch.setattr(DEC, "CATALOG_PATH", dosya)

    def yaz(metin):
        import os, time
        dosya.write_text(metin, encoding="utf-8")
        os.utime(dosya, ns=(time.time_ns(), time.time_ns() + 1_000_000))
    return yaz


@pytest.fixture()
def katalog(tmp_path):
    # Plan YENI 101'i 1., onu değil ESKI 101'i isteyen YAP 201'i 2. döneme koyuyor.
    con = _katalog(tmp_path / "k", [("ESKI 101", 3, None), ("YENI 101", 3, None),
                                    ("YAP 201", 3, "ESKI 101 MIN DD"), ("BAS 202", 3, None)],
                   plan=[("YENI 101", 1), ("YAP 201", 2), ("BAS 202", 2)])
    con.execute("UPDATE course SET name='Ortak Ad' WHERE code IN ('ESKI 101','YENI 101')")
    con.commit()
    return con


def test_TARAMA_goc_adayini_buluyor(katalog, beyan):
    s = KG.tara(katalog)
    assert [(e[3], e[4]) for e in s["engelli"]] == [("YAP 201", ["ESKI 101"])]
    assert s["adaylar"] == [("ESKI 101", "YENI 101", True, ["AAA"], ["YAP 201"])]


def test_TARAMA_beyandan_sonra_engel_yok(katalog, beyan):
    beyan('[[kod_gocu]]\neski = "ESKI 101"\nyeni = "YENI 101"\nnot_ = "t"\n')
    s = KG.tara(katalog)
    assert s["engelli"] == [] and s["adaylar"] == []


def test_TARAMA_farkli_adi_aday_saymiyor(katalog, beyan):
    katalog.execute("UPDATE course SET name='Başka' WHERE code='ESKI 101'")
    katalog.commit()
    assert KG.tara(katalog)["adaylar"] == []            # engel var, ama göç iddiası yok


def test_GRUP_zinciri_gecisli(beyan):
    beyan('[[kod_gocu]]\neski = "ELE 222"\nyeni = "EHB 222"\nnot_ = "t"\n'
          '[[kod_gocu]]\neski = "EHB 222"\nyeni = "EEE 225E"\nnot_ = "t"\n')
    g = DEC.code_migration_groups()
    assert g["ELE 222"] == g["EEE 225E"] == frozenset({"ELE 222", "EHB 222", "EEE 225E"})
    assert R.prereq_view({"ELE 222": "CC"})["EEE 225E"] == "CC"      # iki adım öte


def test_GERCEK_beyanlar_iki_kanitli():
    raw = tomllib.loads((KOK / "config" / "katalog-duzeltmeleri.toml").read_text(encoding="utf-8"))
    ciftler = {(g["eski"], g["yeni"]): g["not_"] for g in raw["kod_gocu"]}
    faz105 = {k: n for k, n in ciftler.items() if "27.09.2026" in n}
    assert len(faz105) == 17
    assert {("BLG 335E", "BBF 301E"), ("ELE 222", "EHB 222"), ("ECN 105E", "EFN 105E"),
            ("ISL 233E", "MMD 233E")} <= set(faz105)
    for n in faz105.values():                          # (1) aynılık + (2) plan zinciri
        assert " aynı" in n and "planı" in n and "ÖNCEKİ döneme" in n, n
    # AKTS'si farklı adaylar beyan EDİLMEDİ.
    assert not {("JEO 114", "JEO 117"), ("TEK 314", "TER 201E"), ("GEM 211E", "NAE 102E")} & set(ciftler)
