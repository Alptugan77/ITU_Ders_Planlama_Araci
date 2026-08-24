"""Faz 20 — kullanıcı istekleri 23.08.2026.

  1. Başlıktan program adı çıksın: "Ders Planlama Aracı".
  2. Üst çubuğun arka planı ŞEFFAF OLMASIN.
  3. Kademeler aşağı doğru aksın, aralarında boşluk olsun.
  4. Kaydedilen program için ayrı bölüm, en üstte.
  5. Kredi tavanı GNO'ya göre otomatik.
  6. ÇAP/yandal listesinde planı olmayan bölüm görünmesin.
  7. BLG ile BLGE ayrı program gibi listelenmesin.
"""
import re

import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import ui as UI
from itucap.normalize import base_program_code, merge_language_variants

from test_ui import _collect, dbs  # noqa: E402,F401


# ------------------------------------------------- 7. dil varyantı tekleştirme
@pytest.mark.parametrize("kod,taban", [
    ("BLGE", "BLG"), ("BLG", "BLG"), ("HTAE", "HTA"), ("ECN_YD", "ECN_YD"),
])
def test_base_program_code(kod, taban):
    assert base_program_code(kod) == taban


def test_dil_varyanti_teklesiyor():
    assert merge_language_variants(["BLG", "BLGE", "MAT"]) == ["BLG", "MAT"]


def test_esi_olmayan_varyant_KORUNUYOR():
    """★ Körlemesine son harfi atmak, var olmayan bir programa yönlendirirdi.

    'HTAE'nin 'HTA' diye bir eşi yok; listede tek başınaysa kalmalı."""
    assert merge_language_variants(["HTAE", "MAT"]) == ["HTAE", "MAT"]


def test_bos_ve_tekrar_dayaniyor():
    assert merge_language_variants([]) == []
    assert merge_language_variants(["BLG", "blg", " BLG "]) == ["BLG"]


# ------------------------------------------- 6+7. başvuru listesi süzmesi
def _kur(tmp_path, monkeypatch, planli=("BLG", "BLGE", "MAT"), programlar=None):
    from itucap import config, db, student as S
    monkeypatch.setattr(config, "REF_DB", tmp_path / "r.sqlite3")
    monkeypatch.setattr(config, "USER_DB", tmp_path / "u.sqlite3")
    con = db.connect(tmp_path / "r.sqlite3", "schema.sql")
    ucon = db.connect(tmp_path / "u.sqlite3", "schema_user.sql")
    for code in (programlar if programlar is not None else ["BLG", "BLGE", "MAT", "JEO"]):
        con.execute("INSERT INTO program(code,name,level) VALUES (?,?,'LS')",
                    (code, code + " Mühendisliği"))
    for i, code in enumerate(planli, start=1):
        con.execute("""INSERT INTO plan(id,program_code,host_program_code,plan_type,
                                        title,iteration,source)
                       VALUES (?,?,'TUMMUH','cap',?,'2025-2026 / Güz Dönemi Sonrası','obs')""",
                    (100 + i, code, f"TUMMUH_{code} ÇAP"))
        con.execute("""INSERT INTO plan_slot(plan_id,slot_kind,course_code,credits,position)
                       VALUES (?,'REQUIRED','XXX 101',3.0,0)""", (100 + i,))
    con.commit()
    return con, ucon, S.ensure_student(ucon)


def test_plani_olmayan_bolum_listede_yok(tmp_path, monkeypatch):
    """★ Seçtirip sonra 'plan yok' demek, seçim sunmamaktan kötü."""
    from itucap import basvuru as B

    con, ucon, sid = _kur(tmp_path, monkeypatch)
    s = B.survey(con, ucon, sid, "cap", anadal="TUMMUH")
    assert "JEO" not in {o.program_code for o in s.options}


def test_listede_BLGE_yok_BLG_var(tmp_path, monkeypatch):
    from itucap import basvuru as B

    con, ucon, sid = _kur(tmp_path, monkeypatch)
    kodlar = {o.program_code for o in B.survey(con, ucon, sid, "cap", anadal="TUMMUH").options}
    assert "BLG" in kodlar and "BLGE" not in kodlar


def test_yalniz_ingilizce_program_varsa_KAYBOLMUYOR(tmp_path, monkeypatch):
    """★ Bölümün YALNIZ İngilizce planı varsa onu gizlemek, programı tamamen
    kaybetmek olurdu."""
    from itucap import basvuru as B

    con, ucon, sid = _kur(tmp_path, monkeypatch, planli=("BLGE", "MAT"))
    kodlar = {o.program_code for o in B.survey(con, ucon, sid, "cap", anadal="TUMMUH").options}
    assert "BLGE" in kodlar


def test_sunucu_ikinci_program_listesi_suzuyor(tmp_path, monkeypatch):
    from itucap import server as SRV

    con, ucon, sid = _kur(tmp_path, monkeypatch)
    state = SRV.State.__new__(SRV.State)
    state.con = con
    out = SRV.State.second_programs(state)
    assert {p["code"] for p in out["cap"]} == {"BLG", "MAT"}
    assert out["yandal"] == []                    # bu katalogda yandal planı yok


# ------------------------------------------------------------- 1. başlık
def test_baslikta_program_adi_yok(dbs):
    html = UI.render(_collect(dbs))
    assert "<title>Ders Planlama Aracı</title>" in html
    assert "ÇAP Panosu" not in html
    assert "ÇAP Ders Planlama Raporu" not in html


# ------------------------------------------- 2. tanımsız CSS jetonu kalmasın
def test_kullanilan_her_css_jetonu_TANIMLI(dbs):
    """★ Üst çubuğun şeffaf kalmasının sebebi buydu: `var(--bg)` diye bir
    jeton yok (doğrusu `--ground`), çözülmeyince arka plan hiç boyanmadı.

    Yazım hatası sessizce 'saydam' demek oluyor; bu test onu bir daha
    sessiz bırakmıyor."""
    html = UI.render(_collect(dbs))
    css = re.search(r"<style>(.*?)</style>", html, re.S).group(1)
    css = re.sub(r"/\*.*?\*/", " ", css, flags=re.S)      # yorumlar sayılmaz
    tanimli = set(re.findall(r"(--[a-z0-9-]+)\s*:", css))
    kullanilan = set(re.findall(r"var\((--[a-z0-9-]+)", css))
    assert kullanilan <= tanimli, f"tanımsız jeton: {sorted(kullanilan - tanimli)}"


def test_ust_cubuk_opak(dbs):
    html = UI.render(_collect(dbs))
    kural = re.search(r"\.secnav\{[^}]*\}", html, re.S).group(0)
    assert "background:var(--ground)" in kural
    assert "position:sticky" in kural


# --------------------------------------------------------- 3. kademe düzeni
def test_kademeler_asagi_doguru(dbs):
    html = UI.render(_collect(dbs))
    kural = re.search(r"\.tierstage\{[^}]*\}", html, re.S).group(0)
    assert "flex-direction:column" in kural
    assert re.search(r"gap:(\d+)px", kural) and int(
        re.search(r"gap:(\d+)px", kural).group(1)) >= 24


# ------------------------------------------------- 4. kaydedilen program
def test_kaydedilen_bolum_sablonda(dbs):
    html = UI.render(_collect(dbs))
    for parca in ("savedSection", "renderSaved", "findSection", "modeIndexFor",
                  "Kaydettiğin program"):
        assert parca in html, parca


def test_kaydedilen_bolum_bolum_cubugunda_ILK(dbs):
    html = UI.render(_collect(dbs))
    m = re.search(r"const SECTIONS = \[(.*?)\];", html, re.S).group(1)
    assert m.strip().startswith('["savedSection"')


# -------------------------------------------------------- 5. kredi tavanı
def test_tavan_gnodan_geliyor(dbs):
    data = _collect(dbs)
    assert data["load"]["limitSource"] == "yönetmelik"
    assert data["maxLoad"] == data["load"]["max"]


def test_acik_cagri_tavani_eziyor(dbs):
    """Testler ve `--max-load` için açık çağrı her zaman kazanmalı."""
    data = _collect(dbs, max_load=29.0)
    assert data["maxLoad"] == 29.0 and data["load"]["limitSource"] == "çağrı"


def test_auto_kapatilinca_ayar_gecerli(dbs):
    from itucap import config

    con, ucon, sid = dbs
    s = config.Settings(anadal_program="HTAE", cap_program="BLG",
                        second_kind="cap",
                        program_codes=["HTAE", "BLG"], max_load=17.0,
                        max_load_auto=False)
    data = UI.collect(con, ucon, sid, s, 10, 20)
    assert data["maxLoad"] == 17.0 and data["load"]["limitSource"] == "ayar"


def test_akts_biriminde_tavan_UYDURULMUYOR(dbs):
    """★ Yönetmelik KREDİDEN konuşuyor; AKTS tavanı diye bir madde yok.
    Çevirmek uydurma olurdu."""
    from itucap import config

    con, ucon, sid = dbs
    s = config.Settings(anadal_program="HTAE", cap_program="BLG",
                        second_kind="cap",
                        program_codes=["HTAE", "BLG"], unit="akts", max_load=45.0)
    data = UI.collect(con, ucon, sid, s, 10, 20)
    assert data["maxLoad"] == 45.0
