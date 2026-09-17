"""Faz 43 — tasarım sistemi uygulandı: üçüncü taraf yok, taklit kalın yok.

Kullanıcı 17.09.2026'da Faz 43 için bir **tasarım sistemi** (Design System
artifact) hazırlamıştı: jetonlar, tipografi, bileşen kartları ve `.woff2`
dosyalarıyla. Bu faz o sistemi uygulamaya geçirdi. Üç ölçülmüş bulgu:

  ★★ Sayfa her açılışta `fonts.googleapis.com`a **1 istek** atıyordu — oysa
     README *"açılışta üçüncü bir tarafa haber verilmiyor"* diyor.
  ★★ `--ink-3` iki temada da AA'nın ALTINDAYDI (gece 4.03, gündüz 4.22;
     taban 4.5) ve `--border-strong` gece temasında 2.13 (kenar tabanı 3.0).
  ★  Üç yazı ağırlığı isteniyordu ama hiçbiri yüklü değildi (Mono 700 → 36
     ders kodu, Sans 900 → 7 öğe, Chivo 500 → alt başlık): tarayıcı onları
     TAKLİT ediyordu.
"""
import pathlib
import re
import shutil
import subprocess
import sys

import pytest


@pytest.fixture(autouse=True)
def no_real_waivers(monkeypatch, tmp_path):
    from itucap import declared
    monkeypatch.setattr(declared, "DEFAULT_PATH", tmp_path / "yok.toml")


from itucap import ui as UI                                   # noqa: E402

KAYNAK = pathlib.Path(UI.__file__).read_text(encoding="utf-8")
TOOLS = pathlib.Path(UI.__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))


# ------------------------------------------------- 1. üçüncü taraf yok
def test_UCUNCU_TARAFA_hic_istek_YOK():
    """★★ Bu testin tuttuğu şey bir görünüm değil, bir SÖZ.

    README: *"Notların tarayıcından çıkmıyor… açılışta üçüncü bir tarafa
    haber verilmiyor."* Google Fonts isteği ziyaretçinin IP'sini ve tarayıcı
    imzasını üçüncü bir tarafa veriyordu — söz ile davranış çelişiyordu.

    Üretilen HTML'de hiçbir dış köken geçemez.
    """
    html = UI.render({})
    dis = re.findall(r'https?://(?!127\.0\.0\.1|localhost)[^"\'\s)]+', html)
    # Metin içindeki bilgi amaçlı adresler (OBS, GitHub) sayılmaz: yalnız
    # TARAYICININ İSTEK ATACAĞI yerler — link/script/@import/url().
    isteyen = re.findall(
        r'(?:<link[^>]+href=|<script[^>]+src=|@import\s+|url\()\s*["\']?'
        r'(https?://[^"\')\s]+)', html)
    assert not isteyen, f"dışarıya istek atan kaynak: {isteyen[:4]}"
    assert "fonts.googleapis.com" not in html
    assert "fonts.gstatic.com" not in html
    # Bilgi amaçlı bağlantı olabilir; onları yasaklamıyoruz.
    assert isinstance(dis, list)


def test_YAZI_TIPLERI_gomulu():
    """Yazı tipleri CSS'e base64 olarak gömülüyor — üç çıktıda da (sunucu,
    tek dosya, statik site) aynı mekanizma."""
    html = UI.render({})
    assert html.count("@font-face") == len(UI._FONT_YUZLERI)
    assert "data:font/woff2;base64," in html
    for _dosya, aile, agirlik in UI._FONT_YUZLERI:
        assert f'font-family:"{aile}";font-style:normal;font-weight:{agirlik}' \
            in html, f"{aile} {agirlik} gömülmemiş"


def test_font_dosyalari_PAKETTE_ve_lisansli():
    """⚠️ SIL OFL 1.1 dağıtımın yanında lisans metnini şart koşuyor."""
    kok = UI.font_dizini()
    assert kok.is_dir(), "fonts/ dizini yok"
    for dosya, _a, _w in UI._FONT_YUZLERI:
        assert (kok / dosya).is_file(), f"eksik yazı tipi: {dosya}"
    assert (kok / "OFL-Chivo.txt").is_file()
    assert (kok / "OFL-IBM-Plex.txt").is_file()


def test_font_okuma_IMPORT_ANINDA_degil():
    """★★ Faz 38'in dersi: `ui` modülü Pyodide paketine giriyor (`ENGINE`),
    `fonts/` girmiyor. Dosyalar import anında okunsaydı site açılmazdı.

    Okuma render içinde ve dosya yoksa SİSTEM yazı tipine düşüyor —
    Google'a değil."""
    govde = re.search(r"def _font_yuzleri\(\).*?(?=\ndef )", KAYNAK, re.S).group(0)
    assert "read_bytes()" in govde, "dosya okuma render dışında"
    assert "except OSError" in govde, "dosya yoksa çökmemeli"
    # Modül düzeyinde okuma yok:
    modul_duzeyi = re.sub(r"\ndef .*?(?=\ndef |\Z)", "\n", KAYNAK, flags=re.S)
    assert "read_bytes" not in modul_duzeyi, "import anında dosya okunuyor"


# ------------------------------------------------------ 2. kontrast tabanı
def test_PALET_kontrast_tabanini_tutuyor():
    """★★ Ölçülen hata: `--ink-3` gece 4.03 / gündüz 4.22 (taban 4.5) ve
    `--border-strong` gece 2.13 (kenar tabanı 3.0).

    `ink-3` az görünen bir renk değil — meta, ipucu, CRN, kart açıklaması
    onunla yazılıyor. Ölçüm paleti `ui.py`'den OKUYOR: jeton değişirse test
    de yeni değerle ölçer."""
    import kontrast_olcumu as K

    kotu = K.olc()
    assert not kotu, "taban altında çift var: " + " · ".join(
        f"{t} {fg}/{bg} {o:.2f}<{tb}" for t, fg, bg, o, tb, _ in kotu)


def test_olculen_jetonlar_YERINDE():
    """Düzeltmenin gerçekten uygulandığı — ve geri alınırsa fark edileceği."""
    assert "--ink-3:#848EA1" in KAYNAK, "gece ink-3 eski değerde"
    assert KAYNAK.count("--ink-3:#5F6878") == 2, "gündüz ink-3 iki blokta olmalı"
    assert "--border-strong:#647085" in KAYNAK


# --------------------------------------------------------- 3. taklit kalın
def test_TAKLIT_KALIN_yok():
    """★ Ölçüm: 36 ders kodu `IBM Plex Mono 700`, 7 öğe `IBM Plex Sans 900`,
    alt başlık `Chivo 500` istiyordu — üçü de YÜKLENMEYEN ağırlık; tarayıcı
    ince yüzü şişirip taklit ediyordu.

    ⚠️ Çare ağırlık eklemek değil (her biri ~60 KB), istenen ağırlığı
    gömülü olana indirmek."""
    gomulu = {(a, w) for _d, a, w in UI._FONT_YUZLERI}
    assert ("Chivo", 500) not in gomulu and ("IBM Plex Mono", 700) not in gomulu
    assert "b,strong{font-weight:700}" in KAYNAK, "`<b>` 900'e tırmanabilir"
    assert "b.mono,.mono b,.mono strong{font-weight:600}" in KAYNAK
    # Alt başlık artık Chivo'nun en ince GERÇEK yüzünü istiyor.
    acilim = re.search(r"\.acilim\{(.*?)\}", KAYNAK, re.S).group(1)
    assert "font-weight:600" in acilim, "Chivo 500 geri gelmiş (o yüz yok)"


def test_yeni_jetonlar_UC_PALETTE_de_var():
    """⚠️ Faz 38b'de `--yandal*` gündüz bloğunda UNUTULMUŞTU. Yeni jeton
    eklerken üç blok da (gece, medya sorgulu gündüz, açık gündüz) dolmalı."""
    for jeton, sayi in (("--seal-hover:", 3), ("--scrim:", 3)):
        assert KAYNAK.count(jeton) == sayi, f"{jeton} {KAYNAK.count(jeton)} yerde"
    assert "dialog::backdrop{background:var(--scrim)}" in KAYNAK


# ------------------------------------------------- 4. kurulmuş site temiz
def test_KURULAN_SITE_de_ucuncu_tarafa_gitmiyor(tmp_path):
    """★★ Asıl teslim burası: yayınlanan `index.html`.

    Şablon doğru olsa bile site kurucusu ayrı bir yol; ziyaretçinin indirdiği
    dosyada dış köken kalmamalı."""
    html = UI.render({}, deferred=True)
    isteyen = re.findall(
        r'(?:<link[^>]+href=|<script[^>]+src=|@import\s+|url\()\s*["\']?'
        r'(https?://[^"\')\s]+)', html)
    assert not isteyen, f"kurulan sitede dış kaynak: {isteyen[:4]}"
    assert "@font-face" in html, "site kabuğunda yazı tipi yok"


def test_kontrast_araci_CALISIYOR():
    """Tasarım sisteminin README'si bu aracı adıyla anıyor; var olmalı ve
    sıfırla dönmeli."""
    arac = TOOLS / "kontrast_olcumu.py"
    assert arac.is_file()
    r = subprocess.run([sys.executable, str(arac)], capture_output=True,
                       text=True, timeout=120)
    assert r.returncode == 0, r.stdout[-600:]
    assert "tabanın üstünde" in r.stdout
