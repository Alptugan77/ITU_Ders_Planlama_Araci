"""Faz 68 — notu girilmemiş ders GNO'ya DD olarak girmiyor.

Gerçek sitede (gerçek katalog) BLG + EHB ÇAP, 5. yarıyıl öğrencisi dersleri
"Plandan işaretle" ile girdi — notlar "bilmiyorum". 26 notsuz ders DD sayıldı:
ekranda **GNO 1.00**, bütün eşikler ✗ ("ÇAP'a devam ✗", "Mezuniyet ✗"),
kredi sınırı 22'ye düştü, GNO hedefi "bu dönem yeterli değil" dedi. Hiçbiri
ölçülmüş değildi.

DD varsayımı ÖNŞART için doğru kalıyor (en kötü durum: "MIN CC" yanlışlıkla
sağlanmaz); GNO'ya ise yalnız notu BİLİNEN ders giriyor.
"""
import pathlib

from itucap import basvuru as B
from itucap import policy as POL
from itucap import rules as R
from itucap import student as S
from itucap import ui as UI
from test_ui import _collect, dbs  # noqa: F401

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


def _kredi(con):
    for kod in ("BLG 212E", "GEO 303E", "SEC 201"):
        con.execute("UPDATE course SET credits=3 WHERE code=?", (kod,))
    con.commit()


def test_NOTSUZ_ders_ORTALAMAYA_girmiyor(dbs):
    con, ucon, sid = dbs
    _kredi(con)
    S.add_entries(ucon, sid, [S.make_entry("GEO 303E", "AA"),
                              S.make_entry("BLG 212E", "")])          # not girilmedi
    g = POL.gpa(con, S.graded(ucon, sid), S.uncertain_grades(ucon, sid))
    assert g.value == 4.0 and g.counted == 1 and g.credits == 3
    assert g.uncertain == ["BLG 212E"] and g.partial
    # Önşartta hâlâ DD: "BLG 212E MIN DD" isteyen ders alınabilir.
    assert R.passed(S.graded(ucon, sid)["BLG 212E"])


def test_HIC_not_yoksa_GNO_BILINMIYOR(dbs):
    con, ucon, sid = dbs
    _kredi(con)
    S.add_entries(ucon, sid, [S.make_entry("GEO 303E", ""), S.make_entry("SEC 201", "")])
    d = _collect(dbs)
    assert d["gpa"]["counted"] == 0
    ths = d["gpa"]["thresholds"]
    assert ths and all(t["ok"] is None for t in ths), ths
    assert d["load"]["noGrades"] is True
    # İlerleme BİLİNİYOR (dersler girildi) — panel "bilinmiyor" demesin.
    assert d["load"]["noTranscript"] is False


def test_BASVURU_GNO_sarti_degerlendirilmiyor_kredi_penceresi_ediliyor():
    cs = B._checks("cap", 0.0, 60, has_data=True, gpa_known=False)
    gno = [c for c in cs if c.key != "kredi_penceresi" and "GNO" in (c.detail or "")
           or "Harf notu" in (c.detail or "")]
    assert gno and all(c.ok is None for c in gno), cs
    assert all("Harf notu girilmiş ders bulunmadığından" in c.detail for c in gno)
    pencere = next(c for c in cs if c.key == "kredi_penceresi")
    assert pencere.ok is True
    # Eski çağrı biçimi (gpa_known verilmezse) değişmedi.
    assert any(c.ok is False for c in B._checks("cap", 2.0, 60, has_data=True))


def test_ARAYUZ_iki_durumu_ayiriyor():
    assert '"noTranscript": not S.graded(ucon, student_id),' in KAYNAK
    assert '"noGrades": bool(S.graded(ucon, student_id)) and not gpa.counted,' in KAYNAK
    assert "harf notu girilmedi; <b>en düşük band varsayıldı</b>" in KAYNAK
    assert 'data-setup="dersler"' in KAYNAK
    assert "ortalamaya katılmadı; GNO yalnızca notu bilinen derslerden" in KAYNAK
    assert "harf notu girilmediğinden sınır bilinmemektedir" in KAYNAK


def test_BASVURU_taramasi_notsuz_transkriptte_GNO_iddia_etmiyor(dbs):
    """Gerçek sitede başvuru penceresi "GNO 1.00 / gereken 3.00 ✗" diyordu."""
    con, ucon, sid = dbs
    _kredi(con)
    S.add_entries(ucon, sid, [S.make_entry("GEO 303E", ""), S.make_entry("SEC 201", "")])
    s = B.survey(con, ucon, sid, kind="cap", anadal="HTAE")
    gno = [c for c in s.checks if "gereken" in (c.detail or "").lower()
           or "Gereken" in (c.detail or "")]
    assert gno and all(c.ok is None for c in gno), s.checks
    assert all("Harf notu girilmiş ders bulunmadığından" in c.detail for c in gno)
