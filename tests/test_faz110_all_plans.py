"""Faz 110 — `make all-plans` kum havuzunda uçtan uca denendi.

Kullanıcı 27.09.2026: *"dikkatli bir şekilde düzeltmeleri yapıp geliştirmeye
devam eder misin sonrasında ben make all-plans yapacağım"*. Deneme
(`ITUCAP_DATA` ile kopya katalogda `refresh --all-programs --all-equivalences`)
OBS plan adımında bir hata buldu:

* İkinci program seçilmemişken (`second_kind = "yok"`) boş kodla
  `programKodu=_LS` isteniyordu → OBS 500 → istisna; ardından gelen
  itu-helper kopyası temizliği (`step_dedupe_plans`) de atlanıyordu.
* Yalnız ilk ikinci program çekiliyordu (ÇAP + yandal birlikte olabilir).
* Yandal kodu zaten OBS biçiminde ("ECN_YD"); "_LS" eklenince OBS 500
  veriyor (canlı ölçüldü).
"""
import pytest

from itucap import config, db, pipeline as PL
from itucap.sources import obs_plan


@pytest.fixture()
def kayit(tmp_path, monkeypatch):
    istek = []

    class Sahte:
        def __init__(self, *_a, **_k): pass
        def close(self): pass

    monkeypatch.setattr(PL, "ObsClient", Sahte)
    monkeypatch.setattr(obs_plan, "list_plans", lambda c, tip, kod: istek.append((tip, kod)) or [])
    monkeypatch.setattr(obs_plan, "scrape_plan", lambda c, con, meta: 0)
    con = db.connect(tmp_path / "r.sqlite3", "schema.sql")
    return con, istek


@pytest.mark.parametrize("ayar,beklenen", [
    (dict(second_kind="yok", cap_program="EHB"), [("lisans", "BLGE_LS")]),
    (dict(second_kind="cap", cap_program="EHB"), [("lisans", "BLGE_LS"), ("cap", "EHB_LS")]),
    (dict(second_kind="ikisi", cap_program="EHB", yandal_program="ECN_YD"),
     [("lisans", "BLGE_LS"), ("cap", "EHB_LS"), ("yandal", "ECN_YD")]),
])
def test_IKINCI_PROGRAMLAR(kayit, ayar, beklenen):
    con, istek = kayit
    PL.step_obs_plans(con, config.Settings(anadal_program="BLGE", **ayar))
    assert istek == beklenen


def test_TUM_PROGRAM_ilerlemesi_toplamla(kayit, monkeypatch, capsys):
    """Tam tarama bir saati aşabiliyor: toplam baştan, ilerleme 'i/toplam'."""
    con, _istek = kayit
    monkeypatch.setattr(obs_plan, "list_faculties", lambda c: [(1, "F")])
    monkeypatch.setattr(obs_plan, "list_programs_named",
                        lambda c, fid, tip: [(f"P{i:02d}_LS", "p") for i in range(12)])
    monkeypatch.setattr(obs_plan, "save_programs", lambda *a, **k: None)
    PL.step_all_second_plans(con, config.Settings(), plan_types=("cap",))
    cikti = capsys.readouterr().out
    assert "cap: 12 program kodu taranacak (keşif)" in cikti
    assert "cap 10/12 kod" in cikti


class _Dur(Exception):
    pass


@pytest.mark.parametrize("skip_obs", [False, True])
def test_KOPYA_TEMIZLIGI_obs_dusse_de_calisir(tmp_path, monkeypatch, skip_obs):
    """Kum havuzundaki denemede OBS plan adımı düşünce kopya temizliği de
    atlanmıştı: BLGE'de 5 OBS + 5 itu-helper planı yan yana kaldı."""
    import argparse
    import sqlite3
    from itucap import declared
    con = db.connect(tmp_path / "r.sqlite3", "schema.sql")
    con.executemany("INSERT INTO plan(id,program_code,plan_type,title,source) VALUES (?,?,?,?,?)",
                    [(-1, "BLGE", "lisans", "itu-helper", "ituhelper"),
                     (7, "BLGE", "lisans", "OBS", "obs"),
                     (-2, "EHB", "lisans", "itu-helper", "ituhelper")])
    con.commit()
    monkeypatch.setattr(config.Settings, "load", staticmethod(lambda: config.Settings(anadal_program="BLGE")))
    monkeypatch.setattr(db, "reference_db", lambda: con)
    monkeypatch.setattr(db, "user_db", lambda: sqlite3.connect(":memory:"))
    monkeypatch.setattr(PL, "step_ituhelper", lambda *a, **k: None)

    def obs_500(*_a):
        raise RuntimeError("500 Internal Server Error")
    monkeypatch.setattr(PL, "step_obs_plans", obs_500)

    def dur(_con):
        raise _Dur
    monkeypatch.setattr(declared, "temizle_referans", dur)       # temizlikten sonrası gerekmiyor
    args = argparse.Namespace(offline=True, skip_obs=skip_obs, all_programs=False,
                              all_equivalences=False, equivalence_program_id=[])
    with pytest.raises(_Dur):
        PL.cmd_refresh(args)
    assert sorted(r[0] for r in con.execute("SELECT id FROM plan")) == [-2, 7]


def _obs_500(*_a):
    raise RuntimeError("500 Internal Server Error")


@pytest.fixture()
def temizlik(monkeypatch):
    cagri = []
    monkeypatch.setattr(PL, "step_ituhelper", lambda *a, **k: None)
    monkeypatch.setattr(PL, "step_obs_plans", _obs_500)
    monkeypatch.setattr(PL, "step_dedupe_plans", lambda con: cagri.append("temizlik") or 0)
    return cagri


@pytest.mark.parametrize("skip_obs", [False, True])
def test_ARAYUZ_TAZELE_obs_dusse_de_temizler(temizlik, monkeypatch, skip_obs):
    """Arayüzdeki "veriyi tazele" de temizliği OBS adımıyla aynı `try`
    içinde yapıyordu."""
    from itucap import changes as CH, server as SRV
    monkeypatch.setattr(SRV, "can_refresh", lambda: True)
    monkeypatch.setattr(SRV, "_apply_declared", lambda u: 0)
    monkeypatch.setattr(SRV, "_diff_json", lambda d: {})
    monkeypatch.setattr(PL, "step_prereq", lambda con: {})
    monkeypatch.setattr(CH, "take", lambda con: None)
    monkeypatch.setattr(CH, "compare", lambda con, watch=None: None)

    class Sahte:
        busy = False
        con = ucon = None
        refresh = SRV.State.refresh
        def settings(self): return config.Settings()
        def watch_codes(self): return set()

    out = Sahte().refresh(skip_obs)
    assert temizlik == ["temizlik"]
    assert ("500" in out["obsError"]) is not skip_obs


def test_NOBET_TURU_temizler(temizlik, monkeypatch):
    """Nöbet turunda (`make watch`) temizlik hiç yoktu."""
    from itucap import watch as W
    monkeypatch.setattr(db, "reference_db", lambda: None)
    monkeypatch.setattr(db, "user_db", lambda: None)
    monkeypatch.setattr(W.CH, "take", lambda con: None)
    monkeypatch.setattr(W.CH, "compare", lambda con, watch=None: "fark")
    monkeypatch.setattr(W, "watch_codes", lambda con, ucon, s: set())
    assert W.tick(config.Settings()) == "fark"
    assert temizlik == ["temizlik"]
