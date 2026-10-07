# Faz 130 — Uygulama simgesi, ana ekrana ekleme ve küçük düzeltmeler

**Tarih:** 07.10.2026
**İstek:** "can you add an app icon for when adding it to homescreen and also
fix and improve the app"

## 1. Simge ve Web App Manifest

Eskiden ne simge ne Web App Manifest vardı. Ana ekrana eklenince tarayıcı
sayfanın küçük bir görüntüsünü ya da baş harfi koyuyordu; uygulama adres
çubuğuyla açılıyordu.

**Simge.** Aracın kendi diliyle çizilmiş bir haftalık program:

- lacivert (`seal`) zemin;
- kalın beyaz bir cetvel (tasarım sisteminin bölüm cetveli);
- altında 3 × 3 ders bloğu: anadal ve ÇAP renginde dolu bloklar, soluk boş
  saatler.

Yazı yok: 48 px'te harf okunmuyor, blok okunuyor. Köşe, gölge ve degrade
yok; bu tasarım sisteminin kuralı.

**Tek kaynak.** `tools/simge_uret.py` geometriyi bir dikdörtgen listesi
olarak tutuyor. PNG'ler (Pillow, 4 kat çizilip küçültülerek) ve SVG aynı
listeden çıkıyor. Dosyalar `src/itucap/simge/` altında ve depoya işlenmiş
durumda; Pillow yalnız bu betik için gerekiyor.

| dosya | kullanım |
|---|---|
| `icon-192.png`, `icon-512.png` | manifest, `purpose: any` |
| `icon-maskable-512.png` | Android uyarlanabilir simge. İçerik %88 ölçekli; köşeler merkezden 0,38·boy uzakta, güvenli daire 0,40·boy. |
| `apple-touch-icon.png` (180) | iOS ana ekranı |
| `favicon.svg`, `favicon-32.png` | sekme simgesi |

**Manifest** (`ui.web_manifest()`):

- ad "İTÜ DEPAR — Ders Planlama Aracı", kısa ad "DEPAR";
- `display: standalone`;
- `start_url` ve `scope` göreli (`./`), çünkü site bir alt dizinde
  yayınlanıyor;
- renkler tasarım sisteminden (`ground`).

**Nereden sunuluyor:**

- Yerel sunucu `/app.webmanifest` ve simgeleri sabit bir ad listesinden
  (`UI.SIMGELER`) sunuyor. İstenen yol dosya adına dönüşmüyor; listede
  olmayan her şey 404.
- Site kurulumu (`tools/site_kur.py`) dosyaları sayfanın yanına kopyalıyor.
- Çevrimdışı katman dosya listesini sitede olandan çıkardığı için simgeler
  de önbelleğe giriyor.

**`<head>`:**

- `manifest`, `icon`, `apple-touch-icon`;
- `apple-mobile-web-app-title` = "DEPAR";
- sistem temasına göre iki `theme-color`.

**Seçili tema.** Kullanıcı Tema düğmesiyle sistemin tersini seçerse
tarayıcı çubuğu sayfadan ayrı renkte kalıyordu. `temaRenginiUygula()`
artık ikisini de seçili temaya çekiyor.

**Tam ekran (iPhone).** `viewport-fit=cover` ve alt çubukta
`env(safe-area-inset-bottom)` payı var; ev göstergesi alt sekmelerin
üstüne binmiyor. Tarayıcı içinde bu pay 0.

## 2. Kullanıcının verisiyle gezinti (telefon 390 px + masaüstü 1366 px)

12 görünümün hepsinde:

- sayfa/konsol hatası yok;
- yatay taşma yok;
- "undefined/NaN" gibi bozuk metin yok.

Bulunanlar:

- **"taban ✗" seçili sekmede okunmuyordu.** Kırmızı yazı lacivert zeminde
  1,31:1 (gündüz) ve 1,12:1 (gece) kontrasttaydı. Seçili sekmede artık
  sekme yazısının rengini alıyor ve altı çiziliyor: 7,58:1 / 8,22:1.
  Seçili olmayan sekmede kırmızı kalıyor.
- **"Kapat" telefonda tek başına bir satır kaplıyordu** ("Program hazırdır"
  paneli, +52 px). Başlığın sağ üst köşesine taşındı; dokunma hedefi 44 px.
- **Sayfa sonundaki "Yararlı bağlantılar" telefonda 27 px'ti.** Cümle içi
  bağlantılar için kural ≥24 px (Faz 48), fakat bu satır bir dokunma
  listesi; 44 px yapıldı. Veri kaynakları cümlesindeki bağlantı bilerek
  dışarıda bırakıldı: `inline-flex` denendi, satır akışını bozdu ve
  "↗"den önceki boşluğu yuttu. `inline-block` ile çözüldü.

## Testler

`tests/test_faz130_simge.py` (11 test):

- dosya boyları ve paket verisi;
- SVG ve PNG'lerin üreteç çıktısıyla aynı olması (piksel karşılaştırması);
- renklerin tasarım sisteminden gelmesi;
- maskable güvenli bölge;
- manifest alanları;
- `<head>` etiketleri;
- yerel sunucu: içerik türleri ve liste dışı yolların 404 dönmesi;
- site kurulumu;
- kontrast ölçümü;
- telefon kuralları.
