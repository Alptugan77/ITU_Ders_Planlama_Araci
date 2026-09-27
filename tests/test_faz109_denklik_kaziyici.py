"""Faz 109 — resmî denklik kazıyıcısının iki (üç) sessiz kırılması.

OBS erişimi açılınca ölçüldü (27.09.2026): denklik adımı 93 lisans
programının HİÇBİRİNDEN denklik getirmiyordu. Sebepler:
1. Program menüsü artık TÜRKÇE ("… Lisans", "… Yüksek Lisans"); süzgeç
   "Undergraduate" arıyordu → 0 program.
2. Sonuç tablosu sayfanın GET'inde değil, ayrı `DersDenklikAra` ucunda.
3. "Ders denklik bilgisi bulunamadı" metni artık HER sayfanın JavaScript'inde;
   eski "bulunamadı" denetimi tablolu sayfayı da boş sayardı.
"""
import pytest

from itucap import config, db
from itucap.sources import obs_equivalence as E

MENU = ('<select id="programId" name="ProgramId"><option value="">Seçiniz</option>'
        '<option value="17">Fizik Mühendisliği Lisans</option>'
        '<option value="31">Fizik Mühendisliği (İngilizce) Lisans</option>'
        '<option value="44">Fizik Mühendisliği Yüksek Lisans</option>'
        '<option value="45">Fizik Mühendisliği Doktora</option>'
        '<option value="871">Computer Engineering Undergraduate</option></select>')

JS = ("<script>$.ajax({url: '/public/GenelTanimlamalar/DersDenklikAra', "
      "error: function () { alert('Ders denklik bilgisi bulunamadı.'); }});</script>")
TABLO = ('<table><thead><tr><th>Plandaki Ders</th><th>Denk Dersler</th></tr></thead><tbody>'
         '<tr><td>BLG 102Programlamaya Giriş (C)</td><td> BIL 105 Bilim ve Müh <br /> CEN 102 Prog <br /></td></tr>'
         '</tbody></table>')


def test_TURKCE_program_menusu():
    ids = [i for i, _ in E.program_options(MENU)]
    assert ids == [17, 31, 871]                  # Yüksek Lisans ve Doktora dışarıda


class _Istemci:
    def __init__(self, yanit):
        self.yanit, self.istekler = yanit, []

    def get(self, url, params):
        self.istekler.append(url)
        return self.yanit


@pytest.fixture()
def con(tmp_path):
    return db.connect(tmp_path / "r.sqlite3", "schema.sql")


def test_SONUC_ayri_uctan_ve_JS_metni_bos_saydirmiyor(con):
    ist = _Istemci(JS + TABLO)                    # bulunamadı metni + tablo birlikte
    assert E._fetch_one(ist, con, 907, 2, 2340, 3) == 2
    assert ist.istekler == [config.EP["eq_search"]]
    assert config.EP["eq_search"].endswith("/public/GenelTanimlamalar/DersDenklikAra")


def test_TABLO_yoksa_bos(con):
    assert E._fetch_one(_Istemci(JS), con, 907, 2, 2340, 3) == 0


def test_BEYAN_karsilastirma_taban_kodla(con, tmp_path, monkeypatch):
    """Resmî sayfa kodları E'siz yazıyor ("BBF 203" ↔ "BLG 252"); E'li beyan
    ("BLG 252E" → "BBF 203E") yine karşılanmış sayılmalı."""
    import sys
    from pathlib import Path
    from itucap import declared as DEC
    sys.path.insert(0, str(Path(DEC.__file__).resolve().parents[2] / "tools"))
    import kod_gocu_taramasi as KG
    dosya = tmp_path / "g.toml"
    dosya.write_text('[[kod_gocu]]\neski = "BLG 252E"\nyeni = "BBF 203E"\nnot_ = "t"\n', encoding="utf-8")
    monkeypatch.setattr(DEC, "CATALOG_PATH", dosya)
    cur = con.execute("INSERT INTO equivalence(target_course, confidence) VALUES ('BBF 203','official')")
    con.execute("INSERT INTO equivalence_source(equivalence_id, course_code) VALUES (?, 'BLG 252')", (cur.lastrowid,))
    con.commit()
    assert KG.beyan_karsilastir(con)["karsilanan"] == [("BLG 252E", "BBF 203E")]
