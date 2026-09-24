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

# ⚠️ Faz 56: palet artık şablonda ELLE yazılı değil — `tasarim.py`den
# ÜRETİLİYOR (`__JETONLAR__`). Bloklar o yüzden KAYNAKTAN değil, ÜRETİLEN
# sayfadan okunuyor: test kullanıcının aldığı CSS'e bakıyor.
_CSS = re.search(r"<style>(.*?)</style>", UI.render({}), re.S).group(1)


def _palet(desen: str) -> dict:
    """Bir palet bloğunun jetonları.

    ⚠️ Bu yardımcı Faz 48'de eklendi: iki test jetonları TÜM DOSYADA
    sayıyordu ("`--scrim:` tam 3 yerde geçmeli"). Kâğıt paleti dördüncü blok
    olarak eklenince ikisi de kırıldı — oysa anlatmak istedikleri şey
    "sayı 3'tür" değil, *"her palet bloğu her jetonu doldurur"*. Sayım artık
    blok blok.
    """
    govde = re.search(desen, _CSS, re.S)
    assert govde, f"palet bloğu bulunamadı: {desen}"
    return {k: v.strip() for k, v in
            re.findall(r"(--[a-z0-9-]+):\s*([^;}]+)", govde.group(1))}


PALETLER = {
    "gece": _palet(r"(?m)^:root\{(.*?)\n\}"),
    "medya-gündüz": _palet(r"@media \(prefers-color-scheme:light\)\{(.*?)\n  \}"),
    "açık-gündüz": _palet(r':root\[data-theme="light"\]\{(.*?)\n\}'),
    "kâğıt": _palet(r"@media print\{.*?\n  :root\{(.*?)\}"),
}


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
    """Düzeltmenin gerçekten uygulandığı — ve geri alınırsa fark edileceği.

    ⚠️ Faz 48: "gündüz `ink-3` DOSYADA iki kez geçer" sayımı, kâğıt paleti
    eklenince yanlış oldu. Sayım yerine bloklara bakıyoruz — asıl mesele
    hangi bloğun hangi değeri taşıdığı."""
    # Faz 70: gece paleti okunurluk için yeniden (kullanıcı: "dark theme is
    # less readable"); değerler tasarim.py'de ve ölçümü kontrast aracında.
    assert PALETLER["gece"]["--ink-3"] == "#A9B2C2", "gece ink-3 eski değerde"
    assert PALETLER["gece"]["--border-strong"] == "#7D899E"
    for ad in ("medya-gündüz", "açık-gündüz", "kâğıt"):
        assert PALETLER[ad]["--ink-3"] == "#5F6878", f"{ad} ink-3 sapmış"


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


def test_yeni_jetonlar_HER_PALETTE_var():
    """⚠️ Faz 38b'de `--yandal*` gündüz bloğunda UNUTULMUŞTU; Faz 48
    taramasında `prefers-color-scheme` bloğunda aynı satır İKİ KEZ duruyordu.
    Elle tutulan palet kopyaları kayıyor.

    Artık tek tek jeton adı saymak yerine BÜTÜN blokların jeton KÜMESİ
    karşılaştırılıyor: yeni bir jeton yalnız bir bloğa eklenirse test
    kırılır, adını bu dosyaya yazmak gerekmeden.

    Tek beklenen fark `--r` (köşe yarıçapı): temaya göre değişmiyor, gece
    bloğunda bir kez tanımlanıp her yerde geçerli.

    ⚠️ Faz 56: gece bloğu artık temadan bağımsız ÖLÇEKLERİ (`--fs-*`,
    `--sp-*` …) ve anlamsal takma adları da taşıyor; onlar bir kez
    tanımlanıyor, tema bloklarına girmiyor. Karşılaştırılan küme o yüzden
    PALET jetonları: `tasarim.palet()`in anahtarları. Kâğıdın fazlası yalnız
    `--kagit-*` olabilir."""
    from itucap import tasarim as T

    palet = {"--" + k for k in T.palet("gece")}
    assert palet == {"--" + k for k in T.palet("gunduz")}, "iki tema ayrı jeton taşıyor"
    assert palet <= set(PALETLER["gece"]), f"gece eksik: {sorted(palet - set(PALETLER['gece']))}"
    for ad in ("medya-gündüz", "açık-gündüz", "kâğıt"):
        d = set(PALETLER[ad])
        fazla = {j for j in d - palet if not j.startswith("--kagit-")}
        assert palet <= d and not fazla, (
            f"{ad} paleti sapmış — eksik: {sorted(palet - d)} fazla: {sorted(fazla)}")
    assert len(palet) >= 25, f"palet küçülmüş: {len(palet)}"
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
