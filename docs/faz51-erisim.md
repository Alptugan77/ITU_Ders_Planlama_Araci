# Faz 51 — UX/UI incelemesi: okunmayan, görünmeyen, dokunulamayan

*19.09.2026 · kullanıcı: **"ux ve ui açısından uygulamayı inceleyip
eksiklerini giderir misin, eğer başka eksik fark edersen onları da gider"***

Testler **1145 → 1155**.

Faz 39–50 ölçülebilir olanı ölçtü: dokunma hedefi, kaydırma derinliği,
kontrast, yazdırma, telefon yerleşimi. Bu tur **hiç bakılmamış üç boyuta**
baktı — ve üçünde de aynı şey çıktı: **bilgi var ama bazı kullanıcılara hiç
ulaşmıyor.**

| ölçüm | önce | sonra |
|---|---|---|
| `main` yer işareti | **yok** | var |
| açılışta canlı bölge (`aria-live`) | **yok** — kısa bildirimler sessiz | var |
| arama kutusunun etiketi | **yok** (yalnız yer tutucu) | `aria-label` |
| adı olan pencere | **0 / 6** | **6 / 6** |
| zorlanmış renkte ızgara blokları | 11 tondan **tek renge** | rol YAZIYLA |
| zorlanmış renkte doluluk/ilerleme çubuğu | dolu ile kanal **aynı renk** | sistem renkleriyle |
| zorlanmış renkte seçili sekme/kip | "seçili" **görünmüyor** | kalın çerçeve |
| uç hatası ekran okuyucuya | **hiç** | canlı bölgeye düşüyor |
| dokunmatikte ulaşılmaz `title` | **82 öğe** (24'ü gerçek açıklama) | dokunulabilir |

---

## A. Ekran okuyucunun gördüğü sayfa

**`main` yoktu.** Sayfada `banner`, `navigation` ve `contentinfo` vardı ama
asıl içeriğin yer işareti yoktu — "içeriğe atla" yapılamıyordu. Etiket
`<div class="icerik">` → `<main class="icerik">`; bütün CSS sınıf üzerinden
olduğu için tek satırlık bir değişiklik.

**Canlı bölge açılışta yoktu.** `say2()` bildirim kutusunu *ilk bildirimde*,
içi dolu olarak DOM'a ekliyordu. Ekran okuyucular canlı bölgeyi önceden
tanıyıp sonraki **değişikliği** duyurur; hazır metinle sonradan eklenen bir
bölge çoğunlukla hiç okunmaz. Yani "kaydedildi", "tazeleme bu ortamda
yapılamıyor" gibi bütün kısa bildirimler görme engelli kullanıcıya **sessiz
geçiyordu**. Bölge artık `boot()`ta, boş olarak kuruluyor.

**Pencerelerin adı yoktu.** Altı pencerenin hiçbirinde `aria-label` ya da
`aria-labelledby` yoktu; açılışta yalnız "iletişim kutusu" deniyordu — hangi
ders, hangi saat, ne penceresi olduğu söylenmiyordu. Ad artık pencerenin
**kendi `<h2>` başlığından** türetiliyor.

> ⚠️ Elle ad yazılmadı: iki ayrı metin zamanla ayrışır, ekranda bir şey
> kulakta başka bir şey olurdu. Üç ayrı pencere açıcı (`openDialog`,
> `openSetup`, `openBasvuru`) var; üçü de tek yardımcıdan geçiyor ve test
> `showModal()` sayısını sayarak dördüncüsünün eklenmesini yakalıyor.

**Arama kutusunun etiketi yoktu** — yalnız yer tutucu. Yer tutucu etiket
değildir: yazmaya başlayınca kaybolur ve ekran okuyucu yalnız "arama" der.

---

## B. ★★ Zorlanmış renk kipi — bu araçta renk VERİDİR

Windows yüksek kontrast (`forced-colors: active`) tarayıcıya bütün renkleri
kullanıcının paletiyle değiştirtiyor. Ölçüm:

* ızgara blokları ve telefondaki gün listesi **11 ayrı tondan tek renge**
  düştü → rol (anadal / ÇAP / yandal) bilgisi **tamamen kayboldu**,
* doluluk ve ilerleme çubuklarının **dolu kısmı ile kanalı aynı renge**
  düştü → çubuk görünmez oldu (kayıt gününde bakılan tek sayı bu),
* seçili sekme, seçili kip ve açık bölüm **"seçili" görünmüyordu**.

Düzeltme, deponun kendi kuralıyla: *bilgi sessizce kaybolmaz.* Renk
gidiyorsa **yazı gelir** — blokların sonuna `· anadal` / `· ÇAP` /
`· yandal` / `· plan dışı` ekleniyor; çubuklar sistem renkleriyle
(`Highlight` dolu, `CanvasText` kenar) yeniden çiziliyor.

> ⚠️ `forced-color-adjust: none` **kullanılmadı**: kullanıcının paletini
> ezmek, yüksek kontrast isteyen kişinin isteğini geri çevirmek olurdu.

> ⚠️⚠️ Seçili durum için önce **`background:Highlight; color:HighlightText`**
> yazıldı — ve ölçüm çürüttü: Chromium bu kipte yazının arkasına `Canvas`
> renginde bir "arka levha" çiziyor; HighlightText de beyaz olunca sekme
> **beyaz üstüne beyaz**, yani bomboş bir şerit olarak çıktı (ekran
> görüntüsüyle görüldü). Seçili artık **kalın çerçeveyle** söyleniyor.
> Ders: bu kipte "doğru bilinen" kalıbı da ölçmek gerekiyor.

---

## C. Hata, görmeyen kullanıcıya da ulaşsın

Bir uç 500 dönünce hata **görünüyor** — ama yalnız düğmenin etiketi olarak
("hata: …"). Sekiz çağrı yerinin hepsi böyleydi. İki sorun:

1. hiçbiri canlı bölgeye düşmüyordu → ekran okuyucu hiçbir şey söylemiyordu;
2. düğmenin **erişilebilir adı** hatayla değişiyordu — geri dönen kullanıcı
   "hata: …" adlı bir düğme buluyor, ne yaptığını bilmiyordu.

Sekizi de tek yardımcıdan (`hataBildir`) geçiyor: görsel biçim aynı (hata
eylemin durduğu yerde görünmeli), ama metin canlı bölgeye de düşüyor ve
düğmenin asıl adı `aria-label`da korunuyor.

---

## D. ★★ `title` dokunmatikte görünmez

Ölçüm (390px, on bir görünüm): görünür **102 `title`ın 82'si** tıklanamayan
bir öğedeydi — yani telefonda o metne **ulaşılamıyordu**. 24'ü kısa bir
etiketi açıklayan gerçek cümleler ve üçü bu projenin temel dürüstlük
notları:

* "önşart bilgisi yok" → *"Katalogda önşart metni yok — 'önşartı yok' demek
  DEĞİL. OBS'den doğrula."*
* "⚠ dönem bitmiş görünüyor" → hangi kanıta dayandığı (kaç dersin dağılımı
  yayınlanmış),
* kategori/eşik rozetleri → yönergedeki şartın kendisi.

Fare kullanıcısı bunları üstüne gelerek okuyordu; **telefondaki kişi hiç
okuyamıyordu.** Artık noktalı altı çizili ve dokunulabilir: metin kısa
bildirim olarak çıkıyor (canlı bölgeye de düşüyor).

> ⚠️ İşleyici **yakalama evresinde** ve `stopPropagation` ile: bu rozetlerin
> çoğu tıklanabilir bir satırın içinde; yakalamasaydık dokunuş satırın
> penceresini açar, açıklama yine okunmazdı.
> ⚠️ `title` **kaldırılmadı** ve öğelere `tabindex`/`role` **eklenmedi**:
> ekran okuyucu `title`ı zaten açıklama olarak okuyor; 24 yeni klavye durağı
> onun için gürültü olurdu. Eklenen tek şey dokunmatikteki yol.

---

## Ölçülüp temiz çıkanlar

`lang="tr"` · sayfa başlığı · başlık düzeninde atlama yok (h1→h2→h3) ·
hareket duyarlılığında animasyon yok · odak halkası zorlanmış kipte de
duruyor · boş arama sonucu çıkış yolunu söylüyor ("süzgeci temizle") ·
pencere içi kaydetme hatası pencerede kalıyor · telefondaki kart düzeni
tablo anlamını **bozmuyor** (`table 1 / row 11 / cell 44`).

---

## ⚠️ Ölçüm aracının kendisi yanlıştı

Bu turda kendi sondam da çürüdü: **`getBoundingClientRect()` kapalı bir
`<details>` içindeki öğe için sıfırdan büyük kutu veriyor**, yani onu
"görünür" sayıyordum — `#arzDetay` "adsız düğme" diye raporlandı, oysa
görünmüyordu bile. Doğrusu `checkVisibility()`. Faz 48/50'nin sonuçları
bundan etkilenmedi (sonda **fazla** sayıyordu, eksik değil), ama bütün yeni
ölçümler `checkVisibility()` kullanıyor.

Bir de üçüncü kez aynı tuzak: muhafız, **kendi yorumundaki** yasak dizgeyi
kodda sanıp yeşil kaldı. Artık bu dosyada da `_kod()` yorumları söküyor.

---

## Testler

`tests/test_faz51_erisim.py` (10 test): `main` yer işareti · arama kutusu
etiketi · pencere adı tek yerden (+ dördüncü pencere açıcıyı yakalayan
`showModal` sayımı) · canlı bölge açılışta · hata canlı bölgeye düşüyor ve
düğmenin adı korunuyor · zorlanmış renkte rol yazıyla · zorlanmış renkte
çubuklar görünür · seçili durum çerçeveyle (HighlightText yasağı) ·
dokunmatikte açıklamaya ulaşılıyor · **uçtan uca** (tarayıcıda: yer işareti,
canlı bölge, üç pencerenin adı, 500 hatası, rozete dokunma, zorlanmış renk
kipinde rol yazısı + çubuk farkı + seçili çerçeve).

Dokuz düzeltmenin dokuzu da geri konup **kırmızıya döndüğü görüldü** — hem
kaynak muhafızı hem uçtan uca ölçüm.
