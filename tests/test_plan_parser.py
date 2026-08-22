"""Ağ olmadan parser testleri — kaydedilmiş HTML fixture'ları üzerinden."""
from pathlib import Path

import pytest

from itucap import db
from itucap.sources import obs_plan

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def con(tmp_path, monkeypatch):
    from itucap import config
    monkeypatch.setattr(config, "REF_DB", tmp_path / "ref.sqlite3")
    return db.connect(tmp_path / "ref.sqlite3", "schema.sql")


class FakeClient:
    """ObsClient yerine geçen, diskteki fixture'ları döndüren sahte istemci."""

    def __init__(self, mapping):
        self.mapping = mapping
        self.calls = []

    def get(self, url, params=None):
        self.calls.append((url, params))
        for key, path in self.mapping.items():
            if key in url:
                return path.read_text(encoding="utf-8")
        raise KeyError(url)


def test_cap_plan_is_flat_and_has_host_programs(con):
    fx = FIXTURES / "cap_plan_2229.html"
    if not fx.exists():
        pytest.skip("fixture yok: make fixtures ile üret")
    client = FakeClient({"DersPlanDetay": fx})
    meta = {
        "plan_id": 2229, "title": "TUMMUH_BLG Double Major Program After 2018-2019 / Fall Semester",
        "pair_code": "TUMMUH_BLG", "host_program_code": "TUMMUH",
        "target_program_code": "BLG", "iteration": "After 2018-2019 / Fall Semester",
        "plan_type": "cap", "obs_program_code": "BLG_LS",
    }
    n = obs_plan.scrape_plan(client, con, meta, fetch_pools=False)

    plan = con.execute("SELECT * FROM plan WHERE id=2229").fetchone()
    assert plan["plan_type"] == "cap"
    assert plan["host_program_code"] == "TUMMUH"
    assert plan["is_term_based"] == 0          # ÇAP planı dönemsiz

    assert n >= 8
    kinds = dict(con.execute(
        "SELECT slot_kind, COUNT(*) FROM plan_slot WHERE plan_id=2229 GROUP BY 1").fetchall())
    assert kinds.get("REQUIRED", 0) >= 6
    assert kinds.get("ELECTIVE_POOL", 0) >= 2

    # seçmeli havuzlar grupId'yi yakalamış ve MT kategorisine düşmüş olmalı
    pools = con.execute(
        """SELECT pool_group_id, pool_category, ects_raw FROM plan_slot
           WHERE plan_id=2229 AND slot_kind='ELECTIVE_POOL' ORDER BY position"""
    ).fetchall()
    assert [p["pool_group_id"] for p in pools] == ["11386", "11387"]
    assert all(p["pool_category"] == "MT" for p in pools)
    assert pools[0]["ects_raw"] == "4 / 5 / 6"     # AKTS aralığı ham saklanıyor

    # ÇAP planında dönem yok
    assert con.execute(
        "SELECT COUNT(*) FROM plan_slot WHERE plan_id=2229 AND term_no IS NOT NULL"
    ).fetchone()[0] == 0

    # ★ Faz 1 doğrulaması: HTAE bu ÇAP planının geçerli olduğu anadallar arasında
    hosts = {r[0] for r in con.execute(
        "SELECT program_code FROM plan_host_program WHERE plan_id=2229")}
    assert "HTAE" in hosts


def test_pool_options_extracted_from_group_page(con):
    """★ Havuz hücresi kodu VE adı taşıyor; kod <a> içinde.

    Bu ayrıştırma bozulunca havuzlar sessizce boş kalıyor ve seçmeli dersler
    'sayılmamış' gibi görünüyor (18.08.2026'da yaşandı).
    """
    con.execute("""INSERT INTO plan(id,program_code,plan_type,title,source)
                   VALUES (2295,'HTAE','lisans','anadal','obs')""")
    con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,pool_label_raw,pool_category,
                                         pool_group_id,position)
                   VALUES (2295,'ELECTIVE_POOL','Elective Courses II(TB)','TB','11676',0)""")
    con.commit()
    client = FakeClient({"_DersGrupSearch": FIXTURES / "ders_grup_11676.html"})
    n = obs_plan.fetch_pool_options(client, con, 2295)

    codes = {r[0] for r in con.execute("SELECT course_code FROM pool_option")}
    assert codes == {"GEO 413E", "GEO 417E", "GEO 425E", "GEO 444E"}
    assert n == 4
    # başlık satırı ('Theoretical') ders sanılmamalı
    assert not any(c.startswith("THEOR") for c in codes)


def test_lisans_plan_is_term_based(con):
    """Anadal planı: her yarıyıl ayrı tablo, term_no doğru atanmalı."""
    fx = FIXTURES / "lisans_plan_2295.html"
    client = FakeClient({"DersPlanDetay": fx})
    meta = {
        "plan_id": 2295,
        "title": "Geomatics Engineering Undergraduate Program (100% English) After 2024-2025 / Fall Semester",
        "pair_code": None, "host_program_code": None, "target_program_code": None,
        "iteration": "After 2024-2025 / Fall Semester",
        "plan_type": "lisans", "obs_program_code": "HTAE_LS",
    }
    n = obs_plan.scrape_plan(client, con, meta, fetch_pools=False)
    assert n == 9

    plan = con.execute("SELECT * FROM plan WHERE id=2295").fetchone()
    assert plan["is_term_based"] == 1
    assert plan["program_code"] == "HTAE"
    assert plan["host_program_code"] is None
    assert plan["source"] == "obs"

    terms = dict(con.execute(
        "SELECT term_no, COUNT(*) FROM plan_slot WHERE plan_id=2295 GROUP BY 1").fetchall())
    assert terms == {1: 3, 2: 2, 7: 4}          # yarıyıl başlıklarından okundu

    # sütun başlığı satırı ders sanılmamalı
    assert con.execute(
        "SELECT COUNT(*) FROM plan_slot WHERE plan_id=2295 AND course_code LIKE 'COURSE%'"
    ).fetchone()[0] == 0

    # 'Type' sütunu kategoriyi doğrudan veriyor
    pools = con.execute(
        """SELECT pool_category, pool_group_id FROM plan_slot
           WHERE plan_id=2295 AND slot_kind='ELECTIVE_POOL' ORDER BY position"""
    ).fetchall()
    assert [p["pool_category"] for p in pools] == ["MT", "TM"]
    assert [p["pool_group_id"] for p in pools] == ["11677", "11675"]

    req = con.execute(
        "SELECT type_raw FROM plan_slot WHERE plan_id=2295 AND course_code='ATA 121'"
    ).fetchone()
    assert req["type_raw"] == "ITB"


def test_dedupe_prefers_obs(con):
    """Aynı program için OBS planı varsa itu-helper sentetik planı düşer."""
    from itucap.pipeline import step_dedupe_plans
    con.execute("""INSERT INTO plan(id,program_code,plan_type,source,title)
                   VALUES (-42,'HTAE','lisans','itu-helper','itu-helper kopyası')""")
    con.execute("""INSERT INTO plan(id,program_code,plan_type,source,title)
                   VALUES (2295,'HTAE','lisans','obs','OBS sürümü')""")
    con.execute("""INSERT INTO plan(id,program_code,plan_type,source,title)
                   VALUES (-43,'INSE','lisans','itu-helper','OBS karşılığı yok')""")
    con.commit()
    assert step_dedupe_plans(con) == 1
    remaining = {r[0] for r in con.execute("SELECT id FROM plan")}
    assert remaining == {2295, -43}


@pytest.mark.parametrize("title,expected", [
    # OBS'nin dili oturuma göre değişiyor; ikisi de doğru çıkmalı.
    ("TUMMUH_BLG Double Major Program After 2018-2019 / Fall Semester",
     "After 2018-2019 / Fall Semester"),
    ("TUMMUH_BLG ÇAP Programı 2018-2019 / Güz Dönemi Sonrası",
     "2018-2019 / Güz Dönemi Sonrası"),
    ("CEV_BLG Double Major Program Before 2013-2014 / Fall Semester",
     "Before 2013-2014 / Fall Semester"),
    ("EHB_BLG ÇAP Programı 2013-2014 / Güz ile 2018-2019 / Güz Dönemleri Arası",
     "2013-2014 / Güz ile 2018-2019 / Güz Dönemleri Arası"),
    ("Harita Mühendisliği Lisans Programı (%100 İngilizce) 2024-2025 / Güz Dönemi Sonrası",
     "2024-2025 / Güz Dönemi Sonrası"),
    ("ECN_BLG Double Major Program", ""),
])
def test_iteration_extraction(title, expected):
    assert obs_plan._iteration_of(title) == expected


def test_turkish_decimal_ects(con):
    """OBS Türkçe oturumda '4,5' döndürüyor; sayısal alan doğru dolmalı."""
    client = FakeClient({"DersPlanDetay": FIXTURES / "cap_plan_2229.html"})
    meta = {
        "plan_id": 2229, "title": "t", "pair_code": "TUMMUH_BLG",
        "host_program_code": "TUMMUH", "target_program_code": "BLG",
        "iteration": "", "plan_type": "cap", "obs_program_code": "BLG_LS",
    }
    obs_plan.scrape_plan(client, con, meta, fetch_pools=False)
    row = con.execute(
        "SELECT ects, ects_raw FROM plan_slot WHERE plan_id=2229 AND course_code='BLG 4902E'"
    ).fetchone()
    assert row["ects"] == 12.0
    # havuz satırında aralık var -> sayısal alan boş, ham hali korunuyor
    pool = con.execute(
        """SELECT ects, ects_raw FROM plan_slot
           WHERE plan_id=2229 AND slot_kind='ELECTIVE_POOL' ORDER BY position LIMIT 1"""
    ).fetchone()
    assert pool["ects"] is None
    assert pool["ects_raw"] == "4 / 5 / 6"
