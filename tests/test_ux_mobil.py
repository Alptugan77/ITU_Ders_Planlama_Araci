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


# ====================================== 6. kaydet/tazele MEŞGUL göstergesi
def test_kaydet_MESGUL_gostergesi():
    """★ "kaydete basılınca yükleniyor olduğu belli olsun" (28.08.2026).
    Dönen halka (.spin) + dugmeMesgul yardımcısı; save() ve tazele() kullanıyor;
    savePicks eski düz metin yerine yardımcıya geçti."""
    src = _src()
    assert ".spin{" in src and "@keyframes spin" in src
    assert "function dugmeMesgul(" in src
    # save() ve tazele() meşgul göstergesini kullanıyor
    assert src.count("dugmeMesgul(btn") >= 3          # save + savePicks + tazele
    # erişilebilirlik + hareket duyarlılığı
    assert 'class="spin" aria-hidden' in src
    assert "prefers-reduced-motion:reduce){.spin" in src


# ====================================== 7. meşgul göstergesi boyanma + sıfırlama
def test_mesgul_BOYANMA_ve_SIFIRLAMA():
    """★ (31.08.2026) İki hata: (a) statik sitede Pyodide ana iş parçacığını
    bloklayınca halka boyanmadan hesaba giriliyordu → bir kare bekle. (b) kalıcı
    #savePicks düğmesi kaydetmeden sonra "Kaydediliyor…" kilitli takılıp yeni
    programı kaydettirmiyordu → her çizimde temiz duruma dönüyor."""
    src = _src()
    # (a) boyanma: save/savePicks/tazele bloklayan işten ÖNCE bir kare bekliyor
    assert "const bekleBoyansin" in src
    assert src.count("await bekleBoyansin()") >= 3
    # (b) renderSaveState düğmeyi sıfırlıyor (kilit + metin)
    blok = src.split("function renderSaveState()")[1].split("function ")[0]
    assert 'btn.disabled = false' in blok
    assert 'btn.classList.remove("mesgul")' in blok
    assert 'btn.textContent = "Programı kaydet"' in blok
