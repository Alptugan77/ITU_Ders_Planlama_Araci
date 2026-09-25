"""Faz 98 — yol haritası BLG 4902E'yi BLG 4901E'den önce/aynı döneme koyuyordu.

Kullanıcı 25.09.2026: *"yol haritasında BLG4902E nin önşartı BLG4901E ama
sistem BLG4901'i aldım sayıyor ve ikisini aynı döneme öneriyor ki bu mümkün
değil"*.

Önşart metni (gerçek katalog): "(BLG 4901 MIN BB veya BLG 4901E MIN BB)".
İki hata vardı:
1. BLGE planında yalnız BLG 4901E var; Türkçe "BLG 4901" hiçbir planda yok
   → "dış önşart" sayılıp GEÇİLMİŞ varsayılıyordu, "veya" hep sağlanıyordu.
   7. yarıyılda BLG 4902E, BLG 4901E'den ÖNCEKİ döneme yerleşiyordu.
2. Geçilmiş her ders önşart için "AA" sayılıyordu; DD ile geçilen (ya da
   notsuz işaretlenip DD sayılan) BLG 4901E "MIN BB"yi karşılıyordu.
"""
import pytest

from test_faz57_yol_haritasi import ANADAL, _katalog, _kur, _yer

ONSART = "(BLG 4901 MIN BBveya BLG 4901E MIN BB)"
# Bitirme dersleri 95 kredi ister (yönetmelik, `kredi eşiği`): öğrenciye
# geçilmiş 100 kredilik bir dolgu dersi veriliyor ki test önşartı sınasın.
DOLGU = {"DLG 100": "AA"}



@pytest.fixture()
def con(tmp_path):
    return _katalog(tmp_path, [
        ("BLG 4901", 3, None), ("BLG 4901E", 3, None),
        ("BLG 4902E", 5, ONSART),
        ("ING 201", 3, None),                     # hiçbir planda yok: gerçekten dış
        ("DLG 100", 100, None),
        ("GEO 401E", 3, "ING 201 MIN DD"),
    ], plan=[("BLG 4901E", 7), ("BLG 4902E", 8), ("GEO 401E", 7)])


def test_ONCE_4901E_SONRA_4902E(con):
    yer = _yer(_kur(con, dict(DOLGU), donem=7))
    assert yer["BLG 4901E"] < yer["BLG 4902E"], yer


def test_DD_ile_gecilen_4901E_BB_isteyen_4902Eyi_ACMIYOR(con):
    h = _kur(con, {**DOLGU, "BLG 4901E": "DD"}, donem=8)
    assert "BLG 4902E" not in _yer(h)
    sebep = {u["course"]: u["reason"] for u in h["unplaced"]}["BLG 4902E"]
    assert "önşartın istediği not sağlanmamaktadır: BLG 4901E (en az BB, kayıtlı not DD)" in sebep
    assert "Notu girilmemiş ders DD sayılır" in sebep


def test_BB_ile_gecilen_4901E_aciyor(con):
    assert "BLG 4902E" in _yer(_kur(con, {**DOLGU, "BLG 4901E": "BB"}, donem=8))


def test_TURKCE_4901_gecilmisse_de_aciyor(con):
    """Öğrenci Türkçe şubeyi almışsa önşart (veya) gerçekten sağlanıyor."""
    assert "BLG 4902E" in _yer(_kur(con, {**DOLGU, "BLG 4901": "BA"}, donem=8))


def test_GERCEK_dis_onsart_hala_varsayiliyor(con):
    """ING 201 hiçbir planda yok, eşi de yok: eski kural sürüyor (yerleşir,
    varsayım olarak yazılır)."""
    assert "GEO 401E" in _yer(_kur(con, dict(DOLGU), donem=7))
