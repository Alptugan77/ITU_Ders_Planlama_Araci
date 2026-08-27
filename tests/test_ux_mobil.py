"""UX/UI düzeltmeleri — mobil ve masaüstü (27.08.2026).

Gerçek ekranlar masaüstü + iPhone genişliğinde gezilerek bulundu; her test
o gezide görülen somut bir sorunu kolluyor.
"""
from itucap import recommend as REC
from itucap import ui as UI


def _src() -> str:
    return open(UI.__file__.replace(".pyc", ".py"), encoding="utf-8").read()


# ====================================== 1. önşart sinyali TEK yerde
def test_onsart_bilgisi_reasons_metnine_GIRMIYOR():
    """★★ Aynı bilgi hem rozet hem gerekçe metniydi; GEO derslerinin ~%85'i
    önşartsız olduğu için her satırda tekrar eden gürültüydü (ölçüldü: 18
    adayın 15'i). Rozet kalıyor, metin çıkıyor."""
    src = open(REC.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
    assert 'c.reasons.append("önşart bilgisi katalogda yok' not in src
    assert 'c.reasons.append("⚠ önşartı okunamadı' not in src


def test_onsart_rozeti_TAVSIYEYI_ipucunda_tasiyor():
    """Metin kalkınca 'OBS'den doğrula' tavsiyesi kaybolmamalı — rozet
    ipucuna taşındı."""
    src = _src()
    assert "OBS'den doğrula" in src        # rozet title'ında
    assert "danışmanına sor" in src


# ====================================== 2. rozet mobilde bölünmüyor
def test_rozet_TEK_PARCA():
    """★★ Dar ekranda rozet ortasından bölünüp kenarlığı kırık kutu
    çiziyordu ("ÖNŞART / BİLGİSİ YOK"). inline-block + nowrap tek parça
    tutuyor."""
    src = _src()
    chip = src.split(".chip{")[1].split("}")[0]
    assert "display:inline-block" in chip
    assert "white-space:nowrap" in chip


# ====================================== 3. şube kartı mobilde alt alta
def test_sube_KARTI_mobilde_STACK():
    """★★ Şube seçenek kartı iki kolonu yan yana sığdıramıyor, CRN ve hoca
    adı sağ kenardan KESİLİYORDU — CRN kayıt günü yazılan sayı."""
    src = _src()
    mobil = src.split("@media (max-width:560px)")[1].split("\n}")[0]
    assert ".opt{flex-direction:column" in mobil


# ====================================== 4. bölüm çubuğu kaydırma ipucu
def test_secnav_KENAR_SOLMASI():
    """★ Mobilde 9 bölüm çubuğa sığmıyor, sonuncusu kesiliyor ve
    kaydırılabildiğine dair ipucu yoktu."""
    src = _src()
    assert "const kenarSolmasi = " in src
    assert 'nav.dataset.more' in src
    assert '.secnav[data-more="right"]' in src
    assert '.secnav[data-more="both"]' in src


# ====================================== 5. kredi tavanı kaynağı başlıkta
def test_kredi_tavani_KAYNAGI_baslikta():
    """★ Kullanıcı 30 ayarlayıp başlıkta 40 görünce 'bozuk mu' diyordu.
    Yönetmelik GNO'ya göre tavanı yükseltiyor; başlık artık kaynağı yazıyor."""
    src = _src()
    assert "(yönetmelik)" in src
    assert "limitSource" in src
