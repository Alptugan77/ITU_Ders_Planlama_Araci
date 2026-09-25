"""Faz 87 — zorluk iki alt puanda, 10 üzerinden.

Kullanıcı 24.09.2026: *"zorluğu iki kısıma ayır yüksek not alma zorluğu ve
geçme zorluğu bunları 10 üzerinden puanlandır sonra geçme zorluğunun %70i ile
yüksek not alma zorluğunun %30unu toplayıp genel bir zorluk üret örnek olarak
2.5 ortalama 10 üzerinden 5 ediyor vfleri de geçme oranına say çünkü vizeden
kalan kişiler finale giremediği için vf gözüküyor %85 geçme oranı da 10
üzerinden 5 gibi düşün mat 103 çok zor değil belki zor sayılabilir"*.
"""
import pathlib

import pytest

from itucap import notlar as ND
from itucap import ui as UI

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")


@pytest.mark.parametrize("ortalama,puan", [
    (2.5, 5.0),          # kullanıcının örneği
    (4.0, 0.0), (1.0, 10.0), (0.5, 10.0),   # uçlar ve kırpma
    (3.0, 3.3), (2.0, 6.7),
])
def test_YUKSEK_NOT_ALMA_zorlugu(ortalama, puan):
    assert ND.not_zorlugu(ortalama) == puan


@pytest.mark.parametrize("gecme,puan", [
    (85.0, 5.0),         # kullanıcının örneği
    (100.0, 0.0), (70.0, 10.0), (50.0, 10.0),
    (94.0, 2.0), (73.1, 9.0),
])
def test_GECME_zorlugu(gecme, puan):
    assert ND.gecme_zorlugu(gecme) == puan


def test_GENEL_yuzde70_gecme_yuzde30_not():
    assert (ND.ZORLUK_AGIRLIK_GECME, ND.ZORLUK_AGIRLIK_NOT) == (0.7, 0.3)
    assert ND.genel_zorluk(10.0, 0.0) == 7.0
    assert ND.genel_zorluk(0.0, 10.0) == 3.0
    assert ND.genel_zorluk(5.0, 5.0) == 5.0


@pytest.mark.parametrize("genel,kademe", [
    (0.0, 1), (1.9, 1), (2.0, 2), (3.9, 2), (4.0, 3), (5.9, 3),
    (6.0, 4), (8.4, 4), (8.5, 5), (10.0, 5)])
def test_KADEMELER(genel, kademe):
    assert ND.zorluk_kademesi(genel) == kademe


def test_VF_GECME_ORANINA_basarisiz_sayilir():
    """Vizeden kalan öğrenci finale giremiyor ve VF görünüyor."""
    z = ND.zorluk_ortalamasi({"202610": {"AA": 40, "CC": 40, "FF": 10, "VF": 10}})
    assert z["passRate"] == 80.0 and z["n"] == 100       # VF'siz sayılsaydı %88.9
    assert z["mean"] == 2.67                              # ortalamaya girmiyor (VF'li harf notu yok)


def test_MAT103_zor_cok_zor_degil():
    """Gerçek katalog (2025-2026, olağan dönemler, VF dahil): geçme %73.1,
    ortalama 1.97 → 9.0 / 6.8 → 8.3 = zor."""
    gecme, notz = ND.gecme_zorlugu(73.1), ND.not_zorlugu(1.97)
    assert (gecme, notz) == (9.0, 6.8)
    genel = ND.genel_zorluk(gecme, notz)
    assert genel == 8.3 and ND.ZORLUK_ETIKET[ND.zorluk_kademesi(genel)] == "zor"
    # FIZ 102E (geçme %64.9, ortalama 1.84) çok zor kalıyor.
    assert ND.zorluk_kademesi(ND.genel_zorluk(ND.gecme_zorlugu(64.9),
                                              ND.not_zorlugu(1.84))) == 5


def test_CAN_EGRISI_dersi_kolay():
    """Faz 86'nın sorunu da çözülü kalıyor: GMI 214 geçme %97.9, ortalama 2.18."""
    genel = ND.genel_zorluk(ND.gecme_zorlugu(97.9), ND.not_zorlugu(2.18))
    assert genel == 2.3 and ND.zorluk_kademesi(genel) == 2


def test_UC_iki_alt_puani_tasiyor(tmp_path):
    from itucap import db
    con = db.connect(tmp_path / "ref.sqlite3", "schema.sql")
    for g, n in {"AA": 20, "BB": 20, "CC": 20, "DD": 15, "FF": 15, "VF": 10}.items():
        con.execute("INSERT INTO grade_distribution(course_key,term,grade,students,announced)"
                    " VALUES ('KMM 211','202610',?,?,0)", (g, n))
    con.execute("INSERT INTO grade_distribution_alias VALUES ('KMM 211','KMM 211')")
    con.commit()
    z = ND.zorluk(con, "KMM 211")
    assert (z["passRate"], z["mean"], z["n"]) == (75.0, 2.17, 100)      # 195 / 90
    assert (z["passScore"], z["gradeScore"], z["score"], z["label"]) == (8.3, 6.1, 7.6, "zor")


def test_ARAYUZ():
    assert "Geçme zorluğu" in KAYNAK and "Yüksek not alma zorluğu" in KAYNAK
    assert "<b>VF geçemeyenlere sayılır</b>" in KAYNAK
    assert "Genel puan = geçme zorluğu × 0.7 + yüksek not alma zorluğu × 0.3," in KAYNAK
    assert "artı iş yükü düzeltmesi 0.1 × (AKTS − 5), en çok ±1" in KAYNAK      # Faz 102
    assert "(x ? x.score : 99) - (y ? y.score : 99)" in KAYNAK
    # Katalog yüzdeliği (Faz 86) kalktı.
    assert "passLowerShare" not in KAYNAK and not hasattr(ND, "zorluk_olcegi")
