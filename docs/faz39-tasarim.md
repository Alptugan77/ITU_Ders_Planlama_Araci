# Faz 39 — Tasarım turu: bir sınıf adının kırdığı kart

*03.09.2026 · kullanıcı: "daha da geliştirir misin uygulamayı, lütfen
tasarımı konusunda da geliştir"*

Bu faz "renkleri tazeleyelim" turu değil. Site gerçek veriyle açıldı, ekran
ekran **ölçüldü** (Playwright + `getComputedStyle`), bulunan her şey sayıya
bağlandı. Çıkan dört şeyden **biri hataydı** — ve ekranda apaçık duruyordu.

Testler **1022 → 1030** (1028 geçti, 2 atlandı).

---

## A. ★★ Bulunan HATA: `.savedcard.cap`

Kaydedilen programdaki her ÇAP/yandal ders kartı **satır içine çöküp
kırpılıyordu**: kod, CRN, ders adı ve saat tek satıra diziliyor, kartın
dışına taşıyordu.

Sebep bir çakışma:

```css
.cap{display:inline-flex; white-space:nowrap; …}   /* ~1857: KONTENJAN ÇİPİ */
…
.savedcard.cap{border-left-color:var(--cap)}       /* ~2158: RENK vermek istemişti */
```

İkinci kural yalnız **kenar rengini** değiştirmek istiyordu. Ama tarayıcı
`class="savedcard cap"` gören her kartta **birinci** kuralı da uyguluyor:
kart bir blok olmaktan çıkıp `inline-flex` + `nowrap` oluyor.

Düzeltme tek kelime: değiştirici sınıfın adı `cap` → `ikinci`. Renk aynı
(`var(--cap)`), yalnız ad çakışmıyor.

**Asıl mesele bu değil.** Mesele şu: 1020 testin hiçbiri bunu görmüyordu ve
hata ekranın ortasındaydı. O yüzden test hatayı değil **hata sınıfını**
tutuyor (`tests/test_faz39_tasarim.py::test_DEGISTIRICI_SINIF_CAKISMASI_YOK`):

> Yerleşim tanımlayan bir sınıf (`display`, `white-space`, `flex-direction`,
> `position`, `grid-template-columns`), başka bir sınıfın **değiştiricisi**
> olarak kullanılamaz.

Test bütün CSS'i tarıyor, `.a.b` biçimindeki her kuralda `.b`'nin tek başına
ne tanımladığına bakıyor. Hata geri konulduğunda kırmızıya döndüğü
doğrulandı: `['.savedcard.cap']`.

⚠️ Bu, dosya içi tek stil sayfasında bilinen ve **tekrarlayan** bir tuzak.
Bugün `.cap` ile oldu; yarın `.mini`, `.tag`, `.row` ile olur. Kalıcı olan
düzeltme değil, testtir.

---

## B. Haftalık ızgaranın üçte biri boştu

| | önce | sonra |
|---|---|---|
| ızgara yüksekliği | 540px | **422px** |
| alttaki boş alan | 177px (**%33**) | 59px |

Dersler 16:29'da bitiyor, ızgara 21:00'a kadar sürüyordu. Boş satırlar
haftayı olduğundan **boş** gösteriyor, telefonda ekranı yiyordu.

⚠️ Boş hücre bu araçta bir **özellik**: tıklayınca "o saate uyan dersler"
açılıyor. O yüzden saatler **silinmedi, kırpıldı**:

* dolu aralığın bir saat öncesi ve sonrası duruyor (`PAY = 60/STEP`),
* en az 6 saatlik pencere korunuyor,
* gizlenen aralık düğmede **açıkça yazıyor**: `tüm günü göster (08:00–21:00)`,
* tek tıkla geri geliyor (`GRID_TUM`), geri dönüş düğmesi de var
  (`saatleri kısalt`).

Yani kırpma bir **görünüm** kararı; hiçbir saat yok sayılmıyor. Projenin
ilkesi burada da aynı: *gizlenen şey, gizlendiğini söylemeli.*

⚠️ **Kendi eklediğim hata:** düğme telefonda da görünüyordu — oysa mobilde
ızgara yok, gün gün liste var, düğme hiçbir şey yapmıyordu. Mobil turunda
görüldü, `@media (max-width:700px)` içine `.gridaralik{display:none}`
eklendi, teste bağlandı.

---

## C. 162 öğe zorla BÜYÜK HARF'ti

Ölçüm: sayfada `text-transform:uppercase` alan **162 öğe**. En uzunları
düğmeler ve bölüm çubuğuydu — "NASIL BİR PROGRAM İSTEDİĞİNİ SÖYLE".

Uzun büyük harf dizisi kelimenin siluetini yok eder; Türkçe'de İ/I ayrımı
yüzünden bir de tereddüt ekler. Kaldırıldığı yerler: `.ghost` (ikincil
düğmeler) ve `.secnav a` (bölüm çubuğu).

⚠️ **Kaldırılmadığı yerler:** `h1,h2,h3`, `.eyebrow`, tablo başlıkları ve
çipler. Büyük harf bu tasarımın kimliği; mesele kimlik değil, **uzunluktu**.
Test ikisini birden tutuyor: kaldırılanlar kalkmış, kalanlar duruyor.

---

## D. Telefonda 32 denetim parmakla ıskalanıyordu

`.secnav a` yüksekliği **32px**'ti — Apple'ın da Google'ın da önerdiği
44/48px'in çok altında, ve bu çubuk telefonda sayfanın **ana gezinme aracı**.
`min-height:40px` verildi, rengi `--ink-3` → `--ink-2`'ye çıkarıldı.

Aynı betik 390px'te 32px'in altındaki **bütün** denetimleri saydı — çubuk
düzelince liste boşalmadı, tersine asıl liste ortaya çıktı:

| denetim | adet | yükseklik | sonra |
|---|---|---|---|
| `kaldır` / `çıkar` (`.rm`) | 4 | 22px | **34px** |
| `izle` (`.watchmini`) | 11 | 21px | **34px** |
| `+N dış önşart` (`.dispre`) | 17 | 19–20px | **32px** |
| **toplam** | **32** | | **0 kaldı** |

⚠️ Büyütme **yalnız telefonda**. Masaüstünde bu rozetlerin sıkışık durması
doğru — fare pikseli tutturur, ve `.dispre` zaten kutuyu şişirmesin diye
küçültülmüştü (Faz 27). İki bağlam iki ölçü; test ikisini de tutuyor.

### D1. İzleme rozeti satır içi stilden kurtuldu

`.watchmini` altı bildirimlik bir `style="…"` ile üretiliyordu — engelli
**her** dersin yanında, aynı altı bildirim, 11 kez. Sınıfa taşındı.

Asıl kazanç görünüm değil: rozet bir **açık/kapalı düğmesi** ve durumunu
yalnız metniyle ("izle" / "izleniyor") söylüyordu. Artık
`aria-pressed="true|false"` taşıyor; renk de o özniteliğe bağlı
(`.watchmini[aria-pressed="true"]{color:var(--cap)}`). Ekran okuyucu
düğmenin basılı olduğunu duyuyor.

---

## E. Ne yapılmadı

* **Renk paleti değişmedi.** Ölçtüğüm kontrast oranları zaten geçiyordu;
  beğeni için palet değiştirmek, gece/gündüz/`[data-theme]` üç bloğunu da
  yeniden doğrulamayı gerektirir ve karşılığında ölçülebilir bir şey vermez.
* **Yazı tipi değişmedi.** Chivo + sistem yığını yerinde; site tek dosya ve
  yeni bir font indirmesi açılış süresine yazılır.
* Faz 38b'de eksik bulunan `--warn-soft`/`--warn-ink` jetonları ve açık
  şemada eksik `--yandal*` bu turda üç paletin **hepsine** eklendi —
  deponun kendi `test_kullanilan_her_css_jetonu_TANIMLI` testi yakaladı.

---

## F. Testler

`tests/test_faz39_tasarim.py` (8 test):

| test | neyi tutuyor |
|---|---|
| `test_DEGISTIRICI_SINIF_CAKISMASI_YOK` | ★★ hata **sınıfı** — yerleşim tanımlayan sınıf değiştirici olamaz |
| `test_kaydedilen_kart_IKINCI_diye_isaretleniyor` | düzeltmenin gerçekten uygulandığı |
| `test_IZGARA_kullanilan_araliga_kirpiliyor` | kırpma + geri alma düğmesi |
| `test_izgara_kirpma_dugmesi_MOBILDE_GIZLI` | kendi eklediğim mobil hatası |
| `test_UZUN_etiketlerde_BUYUK_HARF_YOK` | kaldırılanlar kalktı, **kimlik durdu** |
| `test_bolum_cubugu_DOKUNMA_HEDEFI_yeterli` | 40px |
| `test_TELEFONDA_kucuk_denetim_KALMADI` | 32 → 0, **ve masaüstü büyümedi** |
| `test_izleme_rozeti_SATIR_ICI_STILDEN_kurtuldu` | sınıf + `aria-pressed` |

Dördü (`.savedcard.cap`, mobil düğme, 32 küçük hedef, satır içi stil) geri
konulup **kırmızıya döndükleri görüldü**; test yazıp geçtiğini görmek yetmez,
düşürdüğünü de görmek gerekir.

Ölçüm betiği tek seferlik değil: `getComputedStyle` ile yatay taşma, ızgara
boş alanı, 32px altı dokunma hedefi ve büyük harf sayısı okunuyor. Bir
sonraki tasarım turu aynı sayılarla başlayabilir.
