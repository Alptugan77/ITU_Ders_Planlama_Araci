"""Tasarım sistemi v2 — jetonların TEK kaynağı (Faz 56).

Kullanıcı 23.09.2026: *"Extract the design system from this codebase and
make a new design system. improve every aspect of this site and make it
more usable and useful."*

★★ NEDEN AYRI BİR MODÜL. Faz 56'nın çıkarımı (`tools/tasarim_envanteri.py`)
v1 sisteminin söylediği ile kodun yaptığını karşılaştırdı:

| | v1 sistemi diyor | kodda ölçülen |
|---|---|---|
| yazı boyu | 9 basamak, taban 10.5px | **21** ayrı değer, 8.5px'e kadar |
| harf aralığı | 6 basamak | **14** |
| dolgu / boşluk | 2px ızgarası | **55** dolgu, **24** boşluk değeri |
| renk | jeton | **51** ayrı hex, **108** kullanım |
| yazı tipi yığını | 3 aile | **20** bildirim, mono'nun 3 ayrı yığını |

En pahalısı palet: **dört yerde elle kopyalanmıştı** (gece, medya-gündüz,
açık-gündüz, kâğıt) ve iki kez ayrıştı — Faz 38b'de `--yandal*` bir
blokta unutuldu, Faz 43'te iki yeni jeton üç bloğa tek tek eklendi. Bir
test "her blok her jetonu taşıyor" diye sayıyordu; yani hata sınıfı
yakalanıyordu ama kaynağı duruyordu. Artık palet BURADA bir kez yazılıyor,
dört blok da ondan ÜRETİLİYOR (`css_jetonlari`, `css_kagit`); ölçüm
araçları (`tools/kontrast_olcumu.py`, `tools/ton_merdiveni.py`) ve
tasarım sistemi dışa aktarımı (`jetonlar_json`) da aynı sözlüğü okuyor.

⚠️ Bu modül Pyodide paketine giriyor (`ui` onu içeri alıyor) — bu yüzden
standart kütüphane dışında hiçbir şeye dayanmıyor ve import anında dosya
okumuyor (Faz 38 ve 43'ün tuzağı).

★ RENK DEĞERLERİ v1'DEN DEVRALINDI, UYDURULMADI. Her biri ölçülerek
seçilmişti: kontrast tabanı (Faz 43, 52 çift), ders tonu merdiveni (Faz 40,
ΔE ve yazı kontrastı). Değiştirmek o iki ölçümü de geçersiz kılardı.
v2'nin renkte getirdiği şey değer değil ANLAM: rol (veri), yapı ve durum
jetonları artık ayrı adlar taşıyor — `ok` başarıyı, `anadal` programı
söylüyor, bugün aynı renkte olsalar bile. Tek yeni DEĞER `border-control`:
denetim kenarı artık cetvelden ayrı (aşağıda gerekçesi).
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# RENK — iki tema. Sıra, tasarım sistemi sayfasındaki sıradır.
#
# Her girdi: (jeton, gece, gündüz, ne için). "ne için" tasarım sistemi
# dışa aktarımına da giriyor; yazı jetonlarında HANGİ zeminde okunduğu
# yazılı ve o çiftler `tools/kontrast_olcumu.py`de ölçülüyor.
# ---------------------------------------------------------------------------
RENKLER: list[tuple[str, str, str, str]] = [
    # --- zemin ve yüzey
    ("ground", "#10141B", "#FFFFFF",
     "Sayfa zemini. Seçili sekmede ve birincil düğmede yazı rengi (on-seal)."),
    ("surface", "#161B24", "#FFFFFF", "Kart, pencere, form alanı zemini."),
    ("surface-2", "#1E242F", "#F0F2F6",
     "İkincil yüzey: not kutusu, satır üzerine gelme, kademe kutusu."),
    # --- çizgi
    ("border", "#262E3A", "#D4D9E2",
     "İnce hat: kart kenarı, tablo satır çizgisi, yarım saat çizgisi. "
     "Anlam TAŞIMAZ — yalnız ayırır."),
    ("border-strong", "#647085", "#141821",
     "Cetvel: tablo başlığı altı, ızgarada saat başı, bölüm cetveli. "
     "Gündüzde Şematik'in sert siyah cetveli."),
    ("border-control", "#647085", "#6B7384",
     "★ v2. Düğme ve alan kenarı. v1'de cetvelle aynıydı; gündüzde her "
     "düğme siyah çerçeveli çıkıyordu ve beş düğmelik sütunda birincil "
     "eylem kalabalıkta kayboluyordu. Denetim kenarı tabanı 3:1 (ölçülü)."),
    # --- mürekkep
    ("ink", "#E4E9F2", "#0D1017", "Gövde yazısı; ground, surface, surface-2 üstünde."),
    ("ink-2", "#9AA5B8", "#4B5462",
     "Açıklama ve uzun ikincil metin; ground, surface, surface-2 üstünde."),
    ("ink-3", "#848EA1", "#5F6878",
     "Meta, ipucu, CRN, saat sütunu — en fazla fs-md boyunda; ground, "
     "surface, surface-2 üstünde."),
    # --- yapı (tek aksan)
    ("seal", "#8FA3E8", "#3B4E9E",
     "YAPI: cetvel, eyebrow, bağlantı, seçili sekme zemini, odak halkası, "
     "önşart bağı. Veri taşımaz."),
    ("seal-soft", "#1A2036", "#E7EAF7",
     "Seçili kip/seçim zemini, üzerine gelme zemini; üstünde yazı seal."),
    ("seal-hover", "#9EB3F9", "#2F3F8E",
     "Birincil düğmenin üzerine gelme rengi (opaklık değil — zemini de soldururdu)."),
    # --- veri: program rolü
    ("anadal", "#5FC0A6", "#0A6B58", "VERİ: anadal dersi — şerit, panel üst çizgisi, ölçek."),
    ("anadal-soft", "#123029", "#D6EBE5", "Anadal blok/rozet zemini."),
    ("anadal-ink", "#8FD8C3", "#074A3D", "anadal-soft üstünde yazı."),
    ("cap", "#D9A05B", "#8A5210", "VERİ: ÇAP dersi."),
    ("cap-soft", "#2E2415", "#F6E7D2", "ÇAP blok/rozet zemini."),
    ("cap-ink", "#EFC48E", "#633B08", "cap-soft üstünde yazı."),
    ("yandal", "#7FB2C9", "#1F5C77",
     "VERİ: yandal dersi. ÇAP ile aynı anda olabildiği için ayrı renk."),
    ("yandal-soft", "#16252C", "#DCECF4", "Yandal blok/rozet zemini."),
    ("yandal-ink", "#A9D2E4", "#154457", "yandal-soft üstünde yazı."),
    # --- durum
    ("danger", "#E0836F", "#C02D18",
     "DURUM: kaybedilen/çelişen şey — dolu kontenjan, çakışma, kredi aşımı, "
     "kaldır. Her zaman bir sözcük ya da işaretle birlikte."),
    ("warn", "#D9B061", "#7A5709",
     "DURUM: eksik arz, belirsizlik, bayat veri, az yer kaldı."),
    ("warn-soft", "#2B2415", "#FCF1DB", "Uyarı kutusu zemini."),
    ("warn-ink", "#E8C88A", "#6B4A05", "warn-soft üstünde yazı."),
]

# Anlamsal takma adlar: DEĞER değil ANLAM. Tema bloklarına girmiyorlar —
# `:root`ta bir kez `var()` ile tanımlanıyorlar ve temayla kendiliğinden
# dönüyorlar. Tasarım sistemi dışa aktarımında `{hedef}` olarak çıkıyorlar.
TAKMA_ADLAR: list[tuple[str, str, str]] = [
    ("on-seal", "ground",
     "seal dolgulu zeminde yazı (seçili sekme, birincil düğme, bildirim). "
     "Sabit #fff YAZMA — gece temasında periwinkle üstünde beyaz kalır."),
    ("focus", "seal", "Klavye odak halkası (≥3:1 her yüzeyde)."),
    ("ok", "anadal",
     "DURUM: sağlanıyor (✓), kaydedildi, tamamlandı. ★ v2: v1'de doğrudan "
     "`anadal` yazılıyordu — rol rengi durum anlamına kayıyordu. Bugün "
     "aynı ton; ayrışırsa tek satır değişir."),
    ("ok-soft", "anadal-soft", "Başarı zemini (tamamlanmış adım numarası)."),
]

# Tema başına renk olmayan değerler (gölge, perde).
TEMA_DIGER: list[tuple[str, str, str, str]] = [
    ("scrim", "rgba(8,16,26,.5)", "rgba(8,16,26,.5)", "Pencere perdesi."),
    ("shadow", "0 18px 44px -20px rgba(0,0,0,.85)",
     "0 18px 44px -26px rgba(10,15,30,.5)",
     "Yüzen katman: pencere. Gölge YALNIZ içeriğin üstünde yüzende."),
    ("shadow-toast", "0 6px 24px rgba(0,0,0,.22)", "0 6px 24px rgba(10,15,30,.22)",
     "Kısa bildirim."),
    ("shadow-sticky", "0 -6px 14px -8px rgba(0,0,0,.55)",
     "0 -6px 14px -8px rgba(10,15,30,.28)", "Telefonda alt sekme çubuğu."),
    ("shadow-lift", "0 2px 10px -4px rgba(0,0,0,.5)",
     "0 2px 10px -4px rgba(10,15,30,.3)", "Kademe kutusunun üzerine gelme."),
]

# Kâğıt: her zaman gündüz paleti (Faz 48) + kâğıda özgü üç çizgi.
KAGIT_EK: list[tuple[str, str, str]] = [
    ("kagit-murekkep", "#000000", "Kâğıtta blok yazısı — renk yok, siyah."),
    ("kagit-cizgi", "#999999", "Kâğıtta ızgara ve CRN tablosu çizgisi."),
    ("kagit-blok", "#666666", "Kâğıtta ders bloğu kenarı."),
]


def palet(tema: str) -> dict[str, str]:
    """`{'ground': '#10141B', …}` — tema 'gece' ya da 'gunduz'."""
    i = {"gece": 1, "gunduz": 2}[tema]
    out = {ad: r[i] for r in RENKLER for ad in [r[0]]}
    out.update({r[0]: r[i] for r in TEMA_DIGER})
    return out


# ---------------------------------------------------------------------------
# ÖLÇEKLER — temadan bağımsız.
# ---------------------------------------------------------------------------

# Yazı boyu. v1'de 21 ayrı değer vardı; eşlemesi `tools/tasarim_envanteri.py`de.
# ★ Taban 11px (v1 "10.5 taban" diyordu ama kodda 8.5/9/9.5/10 vardı). Tek
# istisna `fs-2xs` (10px): YALNIZ grafik ekseni ve dar sayaç — akan metin değil.
YAZI_BOYU: list[tuple[str, str, str]] = [
    ("fs-2xs", "10px", "Yalnız grafik ekseni/sayacı (not dağılımı). Akan metin DEĞİL."),
    ("fs-xs", "11px", "Eyebrow, rozet, tablo başlığı, alan etiketi, blok içi ad."),
    ("fs-sm", "12px", "Meta, ipucu, çip, küçük düğme, ızgara bloğu."),
    ("fs-md", "13px", "İkincil arayüz metni, düğme, not kutusu, liste satırı."),
    ("fs-lg", "14px", "Arayüz metni: alan, bildirim, bölüm açıklaması, büyük düğme."),
    ("fs-base", "15px", "Gövde."),
    ("fs-xl", "18px", "Bölüm başlığı (h2). ★ v2: v1'de gövdeyle aynı 15px'ti."),
    ("fs-2xl", "22px", "Karşılama başlığı; telefonda aracın adı."),
    ("fs-3xl", "25px", "Üst çubukta aracın adı; panel yüzdesi."),
    ("fs-4xl", "29px", "Kurulumda aracın adı (masthead)."),
]

SATIR_ARALIGI: list[tuple[str, str, str]] = [
    ("lh-none", "1", "Tek satırlık sayı ve rozet."),
    ("lh-tight", "1.15", "Büyük başlık."),
    ("lh-snug", "1.3", "Blok içi, kademe kutusu, sıkı liste."),
    ("lh-normal", "1.5", "Not kutusu, açıklama."),
    ("lh-body", "1.6", "Gövde."),
    ("lh-loose", "1.7", "Dipnot ve uzun açıklama."),
]

HARF_ARALIGI: list[tuple[str, str, str]] = [
    ("ls-tight", "-.02em", "Büyük ad ve büyük rakam."),
    ("ls-0", "0", "Gövde."),
    ("ls-wide", ".02em", "Küçük kalın yazı, düğme."),
    ("ls-caps", ".06em", "Kısa BÜYÜK HARF: sekme, rozet, çip."),
    ("ls-label", ".11em", "Alan etiketi, tablo başlığı."),
    ("ls-eyebrow", ".16em", "Eyebrow, gün başlığı."),
]

AILELER: list[tuple[str, str, str]] = [
    ("font-display", '"Chivo",Helvetica,Arial,sans-serif',
     "Başlık, etiket, düğme, sekme — 600–900; Chivo'da 500 YOK. Uzun metinde kullanma."),
    ("font-sans", '"IBM Plex Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif',
     "Gövde — 400/600/700."),
    ("font-mono", '"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace',
     "Ders kodu, CRN, saat, kredi, yüzde — 400/600, tabular-nums."),
]

# Aralık — 2px ızgarası 16'ya kadar, sonra 4'ün katları. `tools/
# tasarim_envanteri.py --denetle` dolgu/boşluk/kenar boşluğunun bu kümede
# olduğunu denetliyor (1px optik ayar ve 0 hariç).
ARALIK: list[tuple[str, str, str]] = [
    ("sp-1", "2px", "Optik ayar, rozet içi."),
    ("sp-2", "4px", "Satır içi en küçük boşluk."),
    ("sp-3", "6px", "Çip/rozet arası."),
    ("sp-4", "8px", "Düğme grubu, sıkı liste."),
    ("sp-5", "10px", "Araç çubuğu."),
    ("sp-6", "12px", "Form alanı arası, not kutusu dolgusu."),
    ("sp-7", "14px", "Kart içi blok arası."),
    ("sp-8", "16px", "Alt blok arası."),
    ("sp-9", "20px", "Kart dolgusu (dikey)."),
    ("sp-10", "24px", "Kart dolgusu (yatay), sayfa kenarı."),
    ("sp-11", "32px", "Bölüm arası, sayfa üstü."),
    ("sp-12", "40px", "Kademe satırları arası."),
    ("sp-13", "56px", "Telefonda alt çubuk yüksekliği."),
    ("sp-14", "80px", "Sayfa sonu."),
]
ARALIK_KUMESI = {0, 1} | {int(v[:-2]) for _, v, _ in ARALIK}

CIZGI: list[tuple[str, str, str]] = [
    ("line-hair", "1px", "İnce hat, kenar."),
    ("line-rule", "2px", "Bölüm cetveli, gün başlığı altı."),
    ("line-accent", "3px", "Başlık altı cetvel, not kutusu sol çizgisi, seçili ray."),
    ("line-strip", "5px", "Izgara bloğunun rol şeridi."),
    ("line-head", "6px", "Panel ve pencere üst çizgisi."),
]

KOSE: list[tuple[str, str, str]] = [
    ("r", "0px", "Her yer — köşe YOK (Şematik)."),
    ("r-round", "50%", "Yalnız dönen halka."),
]

DENETIM: list[tuple[str, str, str]] = [
    ("hit-min", "24px", "WCAG 2.2 AA 2.5.8 tabanı — her hedef."),
    ("ctl-h", "34px", "Masaüstü düğme yüksekliği."),
    ("hit-touch", "44px", "Telefonda birincil denetim (Apple/Google kılavuzu)."),
    ("hit-touch-sm", "34px", "Telefonda satır içi küçük denetim (kaldır, izle)."),
]

KATMAN: list[tuple[str, str, str]] = [
    ("z-lift", "1", "Üzerine gelinen/vurgulanan blok."),
    ("z-links", "2", "Kademe bağ çizgileri (kutuların üstünde)."),
    ("z-nav", "40", "Telefonda alt sekme çubuğu."),
    ("z-toast", "60", "Kısa bildirim."),
    ("z-skip", "70", "İçeriğe atla bağlantısı (odakta)."),
]

HAREKET: list[tuple[str, str, str]] = [
    ("dur-fast", ".12s", "Renk/zemin geçişi."),
    ("dur-base", ".18s", "Bildirim girişi."),
    ("dur-spin", ".7s", "Dönen halka."),
    ("ease", "cubic-bezier(.2,.7,.3,1)", "Tek yumuşatma eğrisi."),
]

# Opaklık — bir DURUMU söyler, yazıyı taban altına indirmek için kullanılmaz
# (Faz 54: kapalı adımın açıklaması .5'te 2,0–3,5:1'e düşüyordu; Faz 56:
# blok adı .85'te 3.80:1). Değerler CSS'te yazılı; burada anlamları.
OPAKLIK: list[tuple[str, str, str]] = [
    ("op-disabled", ".45", "Devre dışı düğme (nedeni `title`'da)."),
    ("op-done", ".5", "Tamamlanmış kademe kutusu (üstü çizili + `ok` şerit)."),
    ("op-plan", ".72", "İlerleme ölçeğinde \"bu dönem\" taraması."),
    ("op-link", ".55", "Kademe bağ çizgisi, dinlenmede."),
    ("op-dim", ".22", "Kademe odağında zincir dışı kutular."),
    ("op-link-dim", ".08", "Kademe odağında zincir dışı bağlar."),
]

YERLESIM: list[tuple[str, str, str]] = [
    ("frame", "1720px", "Çerçeve genişliği — bütün görünümlerde aynı (Faz 52)."),
    ("measure", "80ch", "Okuma ölçüsü: düz yazı ~80 karakterde kırılır."),
    ("rail", "216px", "Sol ray genişliği."),
    ("aside", "240px", "Haftalık programın bağlam sütunu."),
]

OLCEKLER = {
    "type": YAZI_BOYU, "leading": SATIR_ARALIGI, "tracking": HARF_ARALIGI,
    "family": AILELER, "spacing": ARALIK, "line": CIZGI, "radius": KOSE,
    "control": DENETIM, "layer": KATMAN, "motion": HAREKET, "layout": YERLESIM,
    "opacity": OPAKLIK,
}


def deger(ad: str) -> str:
    """Temadan bağımsız bir ölçek jetonunun değeri: `deger("fs-xl") → "18px"`."""
    for grup in OLCEKLER.values():
        for a, d, _ in grup:
            if a == ad:
                return d
    raise KeyError(ad)


def coz(metin: str) -> str:
    """Metindeki `var(--ölçek)` başvurularını değerine çevirir.

    Testler için: bir kural `font-size:var(--fs-3xl)` diyorsa "en az 24px"
    iddiası hâlâ ölçülebilir olmalı. Renk jetonlarına DOKUNMUYOR (onlar
    temaya bağlı; tek bir değerleri yok).
    """
    import re

    def bir(m):
        try:
            return deger(m.group(1))
        except KeyError:
            return m.group(0)
    return re.sub(r"var\(--([a-z0-9-]+)\)", bir, metin)


# ---------------------------------------------------------------------------
# CSS üretimi
# ---------------------------------------------------------------------------
def _satirlar(ciftler, girinti="  ") -> str:
    """`--ad:değer;` satırları, satır başına en fazla ~4 bildirim."""
    parca, satir, uzun = [], [], 0
    for ad, deger in ciftler:
        b = f"--{ad}:{deger};"
        if satir and uzun + len(b) > 74:
            parca.append(girinti + " ".join(satir))
            satir, uzun = [], 0
        satir.append(b)
        uzun += len(b) + 1
    if satir:
        parca.append(girinti + " ".join(satir))
    return "\n".join(parca)


def _tema_ciftleri(tema: str) -> list[tuple[str, str]]:
    return list(palet(tema).items())


def css_jetonlari() -> str:
    """Şablondaki `__JETONLAR__` yerine giren dört blok.

    Yapı v1'le AYNI (gece doğar; sistem teması izlenir; `data-theme` iki
    yönde de ezer) — değişen tek şey blokların ELLE yazılmaması.

    ★ `color-scheme` v2'de eklendi. Ölçüldü: gece temasında onay kutusu,
    açılır liste ve kaydırma çubuğu tarayıcının AÇIK çiziminde kalıyordu
    ("yalnız yeri olanlar" kutusu koyu kartın ortasında bembeyaz bir kare).
    """
    olcek = [(ad, deger) for grup in OLCEKLER.values() for ad, deger, _ in grup]
    takma = [(ad, f"var(--{hedef})") for ad, hedef, _ in TAKMA_ADLAR]
    gece = _satirlar(_tema_ciftleri("gece"))
    gunduz4 = _satirlar(_tema_ciftleri("gunduz"), "    ")
    gunduz2 = _satirlar(_tema_ciftleri("gunduz"))
    return (
        "/* ⚙ ÜRETİLDİ — kaynak `src/itucap/tasarim.py`. Buraya elle yazma:\n"
        "   dört blok tek sözlükten geliyor (Faz 56). */\n"
        ":root{\n  color-scheme:dark;\n"
        + _satirlar(olcek) + "\n" + gece + "\n" + _satirlar(takma) + "\n}\n"
        ':root:not([data-theme="dark"]){\n'
        "  @media (prefers-color-scheme:light){\n    color-scheme:light;\n"
        + gunduz4 + "\n  }\n}\n"
        ':root[data-theme="light"]{\n  color-scheme:light;\n'
        + gunduz2 + "\n}"
    )


def css_kagit() -> str:
    """`@media print` içindeki `:root{…}` — kâğıt HER ZAMAN gündüz paleti."""
    ciftler = _tema_ciftleri("gunduz")
    ciftler = [(a, "none" if a.startswith("shadow") else d) for a, d in ciftler]
    ciftler += [(a, d) for a, d, _ in KAGIT_EK]
    return ":root{\n  color-scheme:light;\n" + _satirlar(ciftler) + "}"


# ---------------------------------------------------------------------------
# Tasarım sistemi dışa aktarımı (Design System artifact'ının tokens.json'u)
# ---------------------------------------------------------------------------
def jetonlar_json() -> dict:
    """Design System artifact biçiminde jetonlar — `tools/tasarim_sistemi.py`."""
    renk = [{"name": ad, "value": {"dark": g, "light": l}, "usage": not_}
            for ad, g, l, not_ in RENKLER]
    renk += [{"name": ad, "value": f"{{{hedef}}}", "usage": not_}
             for ad, hedef, not_ in TAKMA_ADLAR]
    renk.append({"name": "scrim", "value": {"dark": TEMA_DIGER[0][1],
                                            "light": TEMA_DIGER[0][2]},
                 "usage": TEMA_DIGER[0][3]})
    renk += [{"name": a, "value": d, "usage": n} for a, d, n in KAGIT_EK]

    def grup(liste):
        return {"tokens": [{"name": a, "value": d, "usage": n} for a, d, n in liste]}

    rol = {
        # (ad, aile, boy, satır, ağırlık, harf aralığı, büyük harf)
        "Başlık": [
            ("t-display", "display", "fs-4xl", "lh-tight", 900, "ls-tight", True),
            ("t-appname", "display", "fs-3xl", "lh-tight", 900, "ls-tight", True),
            ("t-title", "display", "fs-2xl", "lh-tight", 800, "ls-0", True),
            ("t-heading", "display", "fs-xl", "lh-tight", 800, "ls-wide", True),
            ("t-eyebrow", "display", "fs-xs", "lh-none", 700, "ls-eyebrow", True),
            ("t-tab", "display", "fs-xs", "lh-none", 600, "ls-caps", True),
            ("t-button", "display", "fs-md", "lh-none", 600, "ls-wide", False),
            ("t-tag", "display", "fs-xs", "lh-none", 700, "ls-caps", True),
        ],
        "Metin": [
            ("t-body", "sans", "fs-base", "lh-body", 400, "ls-0", False),
            ("t-ui", "sans", "fs-lg", "lh-normal", 400, "ls-0", False),
            ("t-small", "sans", "fs-md", "lh-normal", 400, "ls-0", False),
            ("t-caption", "sans", "fs-sm", "lh-normal", 400, "ls-0", False),
            ("t-label", "sans", "fs-xs", "lh-none", 600, "ls-label", True),
        ],
        "Sayı": [
            ("t-figure", "mono", "fs-3xl", "lh-none", 600, "ls-tight", False),
            ("t-code", "mono", "fs-md", "lh-snug", 600, "ls-0", False),
            ("t-meta", "mono", "fs-sm", "lh-snug", 400, "ls-0", False),
        ],
    }
    deger = {a: d for grp in OLCEKLER.values() for a, d, _ in grp}
    gruplar = []
    for ad, stiller in rol.items():
        gruplar.append({"name": ad, "family": stiller[0][1], "styles": [{
            "name": s[0], "family": s[1], "fontSize": deger[s[2]],
            "lineHeight": deger[s[3]], "fontWeight": s[4],
            "letterSpacing": deger[s[5]],
            "usage": (f"--{s[2]} · --{s[3]} · --{s[5]}"
                      + (" · BÜYÜK HARF CSS'te (text-transform), metin cümle "
                         "düzeninde yazılır" if s[6] else "")),
        } for s in stiller]})
    return {
        "name": "İTÜ DEPAR v2", "version": 2,
        "color": {"themes": [{"id": "dark", "name": "Gece"},
                             {"id": "light", "name": "Gündüz"}],
                  "tokens": renk},
        "type": {
            "fonts": [
                {"family": "Chivo", "file": f"fonts/Chivo-{w}.woff2", "weight": str(n)}
                for w, n in (("SemiBold", 600), ("Bold", 700), ("ExtraBold", 800),
                             ("Black", 900))
            ] + [
                {"family": "IBM Plex Sans", "file": f"fonts/IBMPlexSans-{w}.woff2",
                 "weight": str(n)}
                for w, n in (("Regular", 400), ("SemiBold", 600), ("Bold", 700))
            ] + [
                {"family": "IBM Plex Mono", "file": f"fonts/IBMPlexMono-{w}.woff2",
                 "weight": str(n)}
                for w, n in (("Regular", 400), ("SemiBold", 600))
            ],
            "families": {"display": AILELER[0][1], "sans": AILELER[1][1],
                         "mono": AILELER[2][1]},
            "groups": gruplar,
        },
        "spacing": grup(ARALIK),
        "radius": grup(KOSE),
        "shadow": {"tokens": [
            {"name": a, "value": {"dark": g, "light": l}, "usage": n}
            for a, g, l, n in TEMA_DIGER[1:]]},
        "fontSize": grup(YAZI_BOYU),
        "lineHeight": grup(SATIR_ARALIGI),
        "letterSpacing": grup(HARF_ARALIGI),
        "border": grup(CIZGI),
        "size": grup(DENETIM + YERLESIM),
        "zIndex": grup(KATMAN),
        "opacity": grup(OPAKLIK),
    }
