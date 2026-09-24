# Faz 43 — Tasarım sistemi uygulandı: Google'a giden son istek

*17.09.2026 · kullanıcı: "faz 43 için tasarım dosyası oluşturulmuş olması
lazım, hepsini publishlenebilecek şekilde hazırlayıp uygulamayı geliştirir
misin" · yayın önceliği: "githuba pushladığımda çalışsın"*

Kullanıcı Faz 43 için bir **tasarım sistemi** hazırlamıştı: jetonlar,
tipografi ölçeği, 30 bileşen kartı, ve `.woff2` yazı tipi dosyaları. Bu faz
o sistemi uygulamaya geçirdi. Sistem uygulamanın kendisini belgeliyordu, ama
üç yerde uygulamayla **ayrışıyordu** — ve üçü de ölçünce uygulamanın hatası
çıktı.

Testler **1055 → 1065** (1063 geçti, 2 atlandı).

---

## A. ★★ Her açılışta Google'a 1 istek

README şöyle diyor:

> Pyodide bile CDN'den değil siteden geliyor — açılışta **üçüncü bir tarafa
> haber verilmiyor**.

Ölçüm (tarayıcıda, ağ izlenerek): sayfa açılışında **1 dış istek** —
`fonts.googleapis.com`. İki cümle aynı anda doğru olamaz: o istek
ziyaretçinin IP'sini ve tarayıcı imzasını üçüncü bir tarafa veriyordu.
Pyodide için verilmiş karar neyse (pakete al), yazı tipi için de o olmalıydı.

Tasarım sistemi dosyaları zaten taşıyordu. Artık `src/itucap/fonts/` altında,
SIL OFL 1.1 lisans metinleriyle:

| aile | ağırlık | not |
|---|---|---|
| Chivo | 600, 700, 800, 900 | Latin + Latin Genişletilmiş-A (Türkçe) alt kümesi |
| IBM Plex Sans | 400, 600, 700 | IBM'in dağıttığı hâliyle, **değiştirilmedi** |
| IBM Plex Mono | 400, 600 | aynı |

⚠️ IBM Plex alt kümeye **indirilmedi**: "Plex" OFL'de ayrılmış bir yazı tipi
adı, alt küme onu "Modified Version" yapardı ve adın değişmesi gerekirdi.

**Ölçülen sonuç: dış istek 1 → 0.**

### Neden gömülü (base64), ayrı dosya değil

Aracın üç çıktısı var ve üçü de aynı şablondan geliyor: `make app` (sunucu),
`make ui` (çift tıklanan **tek dosya**), `make site` (statik site). Ayrı
dosya `make ui`'yi bozardı ve sunucuya statik dosya yolu eklemek gerekirdi —
üç yol, üçünde ayrı hata ihtimali. Tek mekanizma seçildi.

Bedeli ölçüldü: **355 KB woff2 → 473 KB base64**. Site kabuğu 281 → 756 KB
(gzip **450 KB**). Pyodide'ın ~10 MB'ının yanında ~%3.5.

⚠️ Dosyalar **import anında değil, render sırasında** okunuyor. `ui` modülü
Pyodide paketine giriyor (`site_kur.ENGINE`), `fonts/` girmiyor — import
anında okusaydık site açılmazdı. Faz 38'de `sources/` yüzünden tam olarak bu
olmuştu. Dosya yoksa sistem yazı tipine düşülüyor, **Google'a değil**; test
gerçekten gömüldüğünü ayrıca kontrol ediyor.

### ⚠️ Eski test açığı KURAL olarak yazmıştı

`tests/test_ui.py` şöyle diyordu:

```python
def test_html_is_self_contained_except_fonts(dbs):
    """CDN yok: tek dosya, çift tıkla açılmalı. Tek dış kaynak Google Fonts."""
```

Yani testin adı ve gövdesi istisnayı **onaylıyordu**. Bir test, kapatılması
gereken bir açığı meşrulaştırıyorsa, açık kadar o test de sorundur. İstisna
kaldırıldı: artık hiç dış kaynak geçemiyor.

---

## B. ★★ `--ink-3` iki temada da AA'nın altındaydı

Tasarım sisteminin paleti üç jetonda uygulamadan ayrılıyordu. Ölçünce
ayrışmanın sebebi belli oldu — uygulamadakiler **tabanın altındaydı**:

| jeton / zemin | uygulama | oran | sistem | oran |
|---|---|---|---|---|
| `ink-3` / `ground` (gece) | `#6C7688` | **4.03** ❌ | `#848EA1` | 5.59 ✅ |
| `ink-3` / `surface-2` (gece) | | **3.40** ❌ | | 4.72 ✅ |
| `ink-3` / `ground` (gündüz) | `#727C8C` | **4.22** ❌ | `#5F6878` | 5.62 ✅ |
| `ink-3` / `surface-2` (gündüz) | | **3.76** ❌ | | 5.01 ✅ |
| `border-strong` / `ground` (gece) | `#414C60` | **2.13** ❌ | `#647085` | 3.69 ✅ |

(Taban: yazı 4.5:1, denetim kenarı 3:1.)

`ink-3` az görünen bir renk değil — **meta, ipucu, CRN, kart açıklaması,
tablo başlığı** onunla yazılıyor. `border-strong` ise cetvelleri ve tablo
çizgilerini taşıyor.

Ölçüm tekrar edilebilir: **`tools/kontrast_olcumu.py`** — tasarım sisteminin
README'sinin adıyla andığı ama repoda olmayan araç. Paleti `ui.py`'den okuyor
(elle kopya değil), 26 çifti iki temada ölçüyor: **52 ölçüm, hepsi tabanın
üstünde**. Jetonu eski değerine döndürünce üç satır kırmızıya dönüyor —
denendi.

---

## C. ★ Taklit kalın: yüklenmeyen üç ağırlık

Ölçüm (tarayıcıda, gerçekten çizilen `font-family` + `font-weight`):

| istenen | kaç öğe | yüklü mü |
|---|---|---|
| `IBM Plex Mono 700` | **36** (ders kodları) | ❌ Google 400/500/600 yüklüyordu |
| `IBM Plex Sans 900` | 7 | ❌ 400/500/600/700 yükleniyordu |
| `Chivo 500` | 1 (aracın alt başlığı) | ❌ Chivo'da 500 yüzü **yok** |

Yüklü olmayan ağırlığı tarayıcı **ince yüzü şişirerek taklit ediyor**
(synthetic bold): gerçek yüzden daha bulanık, daha geniş. En görünür yeri 36
ders kodu — 12.5px mono'da fark gözle seçiliyor.

⚠️ Çare ağırlık **eklemek** değildi (her biri ~60 KB): istenen ağırlığı
gömülü olana indirmek. `<b>` varsayılanı `bolder`, kalın bir bağlamda 900'e
tırmanıyordu; 700'e sabitlendi.

```css
b,strong{font-weight:700}
b.mono,.mono b,.mono strong{font-weight:600}
```

Ölçülen sonuç: istenen her (aile, ağırlık) çifti artık gömülü olanlardan
biri, ve dokuz yüzün dokuzu da `loaded`.

---

## D. Sistemden gelen yeni jetonlar

* `--seal-hover` — birincil düğmenin üzerine gelme rengi. Opaklık değil ayrı
  renk: opaklık zemini de soldurup kontrastı düşürüyordu.
* `--scrim` — pencere perdesi. `dialog::backdrop` elle yazılmış
  `rgba(8,16,26,.5)` taşıyordu; jetona bağlandı.

⚠️ İkisi de **üç palet bloğuna** birden eklendi (gece, medya sorgulu gündüz,
açık gündüz) ve test sayıyor — Faz 38b'de `--yandal*` gündüz bloğunda
unutulmuştu.

---

## E. Push'ta çalışması için

Kullanıcının önceliği buydu. Denetlendi:

| | durum |
|---|---|
| `.github/workflows/pages.yml` tetikleyici | `src/**` → yazı tipleri `src/itucap/fonts/` altında, **push yayını tetikler** ✅ |
| `.gitignore` | `*.woff2` ve yeni araç dışlanmıyor, repoya girerler ✅ |
| `pyproject.toml` `package-data` | `fonts/*.woff2` ve `fonts/*.txt` eklendi ✅ |
| `test.yml` | her push'ta `pytest -q` — Faz 43 testleri orada koşar ✅ |
| gizlilik denetimi (yayının zorunlu adımı) | kurulmuş site **temiz** ✅ |
| Pyodide paketleme | CI `npm install pyodide@<sürüm>` ile indirip `site_kur.py`'ye veriyor ✅ |

⚠️ **Eskimiş uyarı düzeltildi.** `docs/fikirler.md` F.5 şöyle diyordu:
*"Yayından önce `make all-plans` gerekiyor — repodaki katalogda hiçbir yandal
programı yok (76 `_YD` kodunun `program` satırı eksik)."* Ölçüldü: **71 `_YD`
kodunun 71'inin de `program` satırı var, eksik 0**. Uyarı yapılmış bir işi
yapılmamış gösteriyordu ve yayını geciktiren sebeplerden biriydi.

⚠️ Konteynerde doğrulanamayan tek şey: Pyodide'ın CDN'den indirilmesi (ağ
kapalı), o yüzden kurulmuş site burada motoru açamıyor. CI'da o adım kendi
akışında çalışıyor; şablon ve gizlilik tarafı burada doğrulandı.

---

## F. Testler

`tests/test_faz43_tasarim_sistemi.py` (10 test):

| test | neyi tutuyor |
|---|---|
| `test_UCUNCU_TARAFA_hic_istek_YOK` | ★★ README'deki SÖZ |
| `test_KURULAN_SITE_de_ucuncu_tarafa_gitmiyor` | ★★ yayınlanan dosya |
| `test_YAZI_TIPLERI_gomulu` | dokuz yüz de CSS'te |
| `test_font_dosyalari_PAKETTE_ve_lisansli` | OFL metinleri yanında |
| `test_font_okuma_IMPORT_ANINDA_degil` | ★★ Faz 38 tuzağı (Pyodide) |
| `test_PALET_kontrast_tabanini_tutuyor` | ★★ 52 ölçüm, iki tema |
| `test_olculen_jetonlar_YERINDE` | düzeltme geri alınırsa görünür |
| `test_TAKLIT_KALIN_yok` | yalnız gömülü ağırlıklar isteniyor |
| `test_yeni_jetonlar_UC_PALETTE_de_var` | Faz 38b tuzağı |
| `test_kontrast_araci_CALISIYOR` | sistemin andığı araç gerçekten var |

İki düzeltme geri konulup **kırmızıya döndükleri görüldü**: Google Fonts
bağlantısı geri gelince iki test, `b,strong` kuralı silinince bir test.

`python tools/kontrast_olcumu.py --hepsi` bütün çiftleri döküyor.
