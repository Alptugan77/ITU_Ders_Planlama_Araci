"""Faz 39 — tasarım turu.

Kullanıcı isteği (03.09.2026): *"daha da geliştirir misin uygulamayı, lütfen
tasarımı konusunda da geliştir"*. Gerçek veriyle ekran ekran bakıldı; buradaki
testler bulunan iki HATAYI ve iki ölçülebilir kararı kilitliyor.
"""
import re

import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import ui as UI                                   # noqa: E402

from test_ui import _collect, dbs                             # noqa: E402,F401

KAYNAK = open(UI.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
CSS = re.sub(r"/\*.*?\*/", " ",
             re.search(r"<style>(.*?)</style>", KAYNAK, re.S).group(1), flags=re.S)

# Bir öğenin YERLEŞİMİNİ belirleyen özellikler. Bir değiştirici sınıf bunlardan
# birini tanımlayan başka bir sınıfla aynı adı taşıyorsa, kartın düzeni sessizce
# o sınıfın düzenine döner.
YERLESIM = {"display", "white-space", "flex-direction", "position",
            "grid-template-columns"}


def _kurallar():
    return [(s.strip(), gövde)
            for sel, gövde in re.findall(r"([^{}]+)\{([^{}]*)\}", CSS)
            for s in sel.split(",")]


def test_DEGISTIRICI_SINIF_CAKISMASI_YOK():
    """★★ Faz 39'da bulunan HATA: `.savedcard.cap`.

    `.cap` bu sayfada **kontenjan çipinin** sınıfı
    (`display:inline-flex; white-space:nowrap`). Kaydedilen programda ÇAP/
    yandal dersini işaretlemek için aynı ad değiştirici olarak kullanılınca,
    o kartların HEPSİ satır içine çöküp kırpıldı: kod, CRN, ders adı ve saat
    tek satırda, kartın dışına taşarak. Ekranda apaçık duruyordu ve
    1020 testin hiçbiri görmüyordu.

    Bu test hatayı değil, **hata sınıfını** tutuyor: yerleşim tanımlayan bir
    sınıf, başka bir sınıfın değiştiricisi olarak kullanılamaz.
    """
    yerlesim_tanimlayan = {}
    for sel, gövde in _kurallar():
        m = re.fullmatch(r"\.([A-Za-z0-9_-]+)", sel)
        if m:
            özellik = {p.split(":")[0].strip() for p in gövde.split(";") if ":" in p}
            yerlesim_tanimlayan.setdefault(m.group(1), set()).update(özellik)
    riskli = {k for k, v in yerlesim_tanimlayan.items() if v & YERLESIM}

    çakışma = []
    for sel, _ in _kurallar():
        m = re.fullmatch(r"\.([A-Za-z0-9_-]+)\.([A-Za-z0-9_-]+)", sel)
        if m and m.group(2) in riskli:
            çakışma.append(
                f"{sel} — .{m.group(2)} tek başına "
                f"{sorted(yerlesim_tanimlayan[m.group(2)] & YERLESIM)} tanımlıyor")
    assert not çakışma, ("değiştirici sınıf, yerleşim tanımlayan bir sınıfla "
                         "aynı adı taşıyor: " + " · ".join(sorted(çakışma)))


def test_kaydedilen_kart_IKINCI_diye_isaretleniyor():
    """Renk aynı kaldı, yalnız ad değişti — düzelmenin gerçekten uygulandığı."""
    assert ".savedcard.ikinci{" in CSS
    assert '"ikinci"' in KAYNAK and 'savedcard ${hit.cand.role' in KAYNAK


# ----------------------------------------------------- ızgara boş saatleri
def test_IZGARA_kullanilan_araliga_kirpiliyor():
    """★ Ölçüm: 540px'lik ızgaranın 177px'i (%33) alttaki BOŞ saatlerdi —
    dersler 16:29'da bitiyor, ızgara 21:00'a kadar sürüyordu.

    ⚠️ Saatler silinmiyor, kırpılıyor: boş hücre bir ÖZELLİK ("tıkla → o
    saate uyan dersler"). Gizlenen aralık düğmede yazıyor ve tek tıkla
    geri geliyor."""
    assert "GRID_TUM" in KAYNAK
    assert "tüm günü göster" in KAYNAK and "saatleri kısalt" in KAYNAK
    # Kırpma yalnız GRID_TUM kapalıyken.
    assert "if(son >= 0 && !GRID_TUM)" in KAYNAK


def test_izgara_kirpma_dugmesi_MOBILDE_GIZLI():
    """⚠️ Telefonda ızgara yok, gün gün liste var — düğme hiçbir şey yapmaz.
    (Faz 39'da eklerken atlandı, mobil turunda görüldü.)"""
    mobil = re.search(r"@media \(max-width:700px\)\{(.*?)\n\}", CSS, re.S)
    assert mobil and ".gridaralik{display:none}" in mobil.group(1).replace(" ", "")


# ------------------------------------------------------------- tipografi
def test_UZUN_etiketlerde_BUYUK_HARF_YOK():
    """★ Ölçüm: sayfada 162 öğe zorla BÜYÜK HARF'e çevriliyordu; en uzunları
    düğmeler ve bölüm çubuğuydu ("NASIL BİR PROGRAM İSTEDİĞİNİ SÖYLE").
    Uzun büyük harf dizisi kelime siluetini yok eder, Türkçe'de İ/I yüzünden
    daha da yavaş okunur.

    ⚠️ BAŞLIKLAR ve eyebrow'lar BÜYÜK HARF KALIYOR — tasarımın kimliği o.
    """
    def kural(seçici):
        for sel, gövde in _kurallar():
            if sel == seçici:
                return gövde
        raise AssertionError(f"kural yok: {seçici}")

    assert "text-transform:uppercase" not in kural(".ghost")
    assert "text-transform:uppercase" not in kural(".ray a")
    # Kimlik duruyor:
    assert "text-transform:uppercase" in kural(".eyebrow")
    assert "text-transform:uppercase" in kural("h3")   # h1,h2,h3 grubu


def test_bolum_cubugu_DOKUNMA_HEDEFI_yeterli():
    """Ölçüm: 32px'ti — parmakla ıskalanacak kadar kısa.

    ⚠️ Faz 46'da çubuk RAY oldu (dikey) ve hedef 40 → 44px çıktı: dikey
    rayda yükseklik bedava, dokunmatik kılavuzunun tabanı 44."""
    for sel, gövde in _kurallar():
        if sel == ".ray a":
            assert "min-height:44px" in gövde.replace(" ", "")
            return
    raise AssertionError(".ray a kuralı yok")


def _mobil_css():
    """Bütün `max-width:700px` bloklarını süslü parantez sayarak toplar.

    ⚠️ Eskiden `(.*?)\\n\\}` ile İLK bloğun bir kısmını alıyordu: repoda üç
    ayrı 700px bloğu var ve aranan kural hangisine yazıldıysa test onu
    göremiyordu (Faz 50'de oldu).
    """
    out = []
    for m in re.finditer(r"@media \(max-width:700px\)\{", CSS):
        i, derinlik = m.end(), 1
        while i < len(CSS) and derinlik:
            if CSS[i] == "{":
                derinlik += 1
            elif CSS[i] == "}":
                derinlik -= 1
            i += 1
        out.append(CSS[m.end():i - 1])
    assert out, "mobil medya bloğu yok"
    return "\n".join(out)


def test_TELEFONDA_kucuk_denetim_KALMADI():
    """★ Ölçüm (390px): 32 denetim 32px'in ALTINDAYDI — `kaldır` ×4 (22px),
    `izle` ×11 (21px), `+N dış önşart` ×17 (19px). Değişiklikten sonra: 0.

    ⚠️⚠️ FAZ 46'DA BU KURALIN İKİNCİ YARISI GERİ ALINDI. Faz 39'da
    "masaüstünde sıkışık durması doğru, fare pikseli tutturur" demiştim.
    Ölçüm (18.09.2026, 1440px) bunu çürüttü: WCAG 2.2 AA 2.5.8 hedef
    tabanı (24×24) İŞARETLEYİCİ girdiler için de geçerli, yalnız dokunma
    için değil — ve masaüstünde 24px altında **72 hedef** vardı. Artık
    taban her yerde 24, telefonda 32/34. Yani telefon kuralı duruyor,
    masaüstü muafiyeti kalktı.

    ⚠️⚠️ FAZ 50: bu iki kuralın İKİSİ DE ÖLÜYDÜ ve bu test onu göremiyordu.
    `.watchmini` ve `.tier li .dispre` TEMEL kuralları kaynakta medya
    bloğundan SONRA geliyor; medya sorgusu özgüllük kazandırmadığı için
    24px'i eziyordu. Tarayıcıda ölçüldü: hesaplanan `min-height` = 24px.
    Seçiciler öğe adıyla nitelendi (`button.watchmini`, `span.dispre`) ve
    asıl güvence artık HESAPLANAN değeri ölçen `test_faz50_telefon`
    (`KUCUK34`). Burada yalnız kuralın niteli hâli aranıyor —
    çünkü niteliksiz hâli sessizce ölüyor."""
    mobil = _mobil_css().replace(" ", "").replace("\n", "")
    assert "button.rm,button.watchmini{min-height:34px" in mobil
    assert ".tierlispan.dispre{min-height:32px" in mobil
    # Masaüstünde de taban var — ama TELEFONUNKİNDEN KÜÇÜK (24 < 32/34).
    # ⚠️ `_mobil_css()` iç içe blokları yutabiliyor; bu yüzden kuralları
    # doğrudan kendi seçicileriyle arıyoruz, "mobil bloğu çıkar" diye değil.
    for seçici in (r"\.trtable \.rm", r"\.watchmini", r"\.tier li \.dispre"):
        # `(?m)^` şart: mobil karşılıkları girintili ve `.rm,.watchmini{`
        # gibi birleşik — girintisiz satır başı yalnız masaüstü kuralı.
        m = re.search(r"(?m)^" + seçici + r"\{([^{}]*)\}", CSS)
        assert m, f"{seçici} kuralı yok"
        h = re.search(r"min-height:\s*(\d+)px", m.group(1))
        assert h, f"{seçici} masaüstünde tabansız"
        assert 24 <= int(h.group(1)) < 32, f"{seçici}: {h.group(1)}px"


def test_izleme_rozeti_SATIR_ICI_STILDEN_kurtuldu():
    """Rozet 6 bildirimlik satır içi stille üretiliyordu — engelli her dersin
    yanında, 11 kez. Sınıfa taşındı.

    ⚠️ Asıl kazanç görünüm değil: durumu artık `aria-pressed` söylüyor.
    Ekran okuyucu "izleniyor"u yalnız metinden çıkarabiliyordu."""
    assert ".watchmini{" in CSS
    assert '.watchmini[aria-pressed="true"]{' in CSS
    rozet = re.search(r'<button class="watchmini"(.*?)</button>', KAYNAK, re.S)
    assert rozet, "watchmini düğmesi bulunamadı"
    assert "style=" not in rozet.group(1), "satır içi stil geri gelmiş"
    assert 'aria-pressed="${on' in rozet.group(1)
