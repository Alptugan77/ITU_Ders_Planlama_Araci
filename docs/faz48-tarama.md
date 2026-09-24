# Faz 48 — Tarama: "başka ne kaldı?"

*18.09.2026 · kullanıcı: **"eklenebilecek başka düzeltmeler var mı diye
kontrol edip ekle"***

Testler **1116 → 1128**. Fikir üretilmedi: on bir görünüm ve dokuz pencere,
iki genişlikte (1512px / 390px), iki temada ve **yazdırma kipinde** tek tek
gezildi. Çıkan yedi kusurun hepsi aynı cümleyle özetleniyor:

> **Faz 46/47'nin kabuğu, kendisinden ÖNCE yazılmış bağlamlara sızdı.**

Görünüm kipi (aynı anda tek bölüm açık) sayfanın her köşesini değiştirdi;
yazdırma bloğu, dokunma hedefi tabanı ve "bir yere götüren" çağrılar o
kabuktan önce yazılmıştı.

---

## Bulunan ve düzeltilen yedi şey

| # | ne | ölçüm (önce) | sonra |
|---|---|---|---|
| 1 | öneri görünümünde "kaldır" | 46×**22**px | 46×**24**px |
| 2 | pencerelerde `<summary>` | 9 pencerenin **6'sında 19–21**px | **24**px |
| 3 | ölü `scrollIntoView` | **2** yer daha | `gorunumAc` |
| 4 | kâğıtta ızgara | **660**px | **1512**px |
| 5 | gece şemasında kâğıt | saat sütunu beyazda **~2,6:1** | gündüz paleti |
| 6 | program dışı görünümde Cmd+P | **166 karakter** (boş kâğıt) | 2172 |
| 7 | kâğıda ne çıktığı | **açık görünüme göre değişiyordu** | hep aynı |

### 1–2. Dokunma hedefi tabanı (WCAG 2.2 AA 2.5.8)

Faz 46 görünüm başına hedefleri ölçmüştü (72 → 0). O tarama **pencerelerin
içine bakmıyordu**; bu taramada dokuz pencere tek tek açıldı. "kaldır"
düğmesi 22px, katlanan başlıkların altısı 19–21px çıktı.

İkisi de **taban kuralla** çözüldü, tek tek sınıf yamayarak değil — yeni bir
`.rm` ya da yeni bir `<details>` eklendiğinde aynı hata tekrar etmesin diye.

> ⚠️⚠️ `summary` tabanı **esnek kutu yapılmadı** ve bu bilerek: (a) esnek
> kutu iki metin düğümü arasındaki boşluğu yutuyor — bu repoda ölçülmüş bir
> hata ("11 dersbu dönem"), ve pencere başlıkları `Puan <b>132.5</b> —
> neden?` gibi karışık içerikli; (b) `list-item` kutusu kalkınca **yerleşik
> açılma üçgeni siliniyor** ve o başlıkların tek açılma işareti o. Dikey
> dolgu ikisine de dokunmadan tabanı sağlıyor.

Yeniden ölçüm: iki genişlikte dokuz pencere, **1758 hedef, 24px altı: 0**.

### 3. Ölü `scrollIntoView` — sınıfın üçüncü görülüşü

Görünüm kipinde **kapalı bir bölüme kaydırmak hiçbir şey yapmaz**. Aynı hata
Faz 46'da (bölüm bağlantıları) ve Faz 47'de (kaydedilen programı yükle)
çıkmıştı; bu taramada iki tane daha bulundu:

* *"Programın hazır. Şimdi:"* panelindeki **"Haftalık programa bak"** ve
  **"Ders ekle / değiştir"** düğmeleri,
* kayıt günü penceresinden **CRN yapıştırıp yükleme**.

Kullanıcı tıklıyor, program yükleniyor, **ekranda hiçbir şey olmuyordu.**

Üçüncü görülüş olduğu için tek tek düğme değil **sınıf** tutuldu:
`test_SCROLLINTOVIEW_sinifi_KAPALI` kaynakta kalan tek `scrollIntoView`ın
açık görünümün İÇİNDEKİ bir satırı hizalayan `candOdakla` olduğunu
doğruluyor. Yeni bir "bir yere götür" çağrısı testi kırar.

### 4–7. Kâğıt

Yazdırma bloğu, hepsi aynı anda açık **eski** sayfaya göre yazılmıştı.
Dördü birden ölçüldü:

* **Kabuk sızması.** `.govde` iki sütunlu bir ızgara: ray `display:none`
  olsa bile **216px'lik sütun** duruyordu; `.prgduzen` de 240px'lik bağlam
  sütununu ayırıyordu. A4'te ızgara 660px, sayfanın yarısı boş.
* **Gece şeması kâğıda geçiyordu.** Saat sütunu (08:00, 09:00…)
  `rgb(132,142,161)`, özet satırı `rgb(154,165,184)` — beyaz kâğıtta ~2,6:1,
  okunmuyor. Kâğıt artık **her zaman gündüz paleti**; ⚠️ palet uydurulmadı,
  açık şemanın jetonlarının birebir aynısı ve test ikisini
  **karşılaştırıyor** (sabit değer yazmıyor).
* **Program görünümü dışında kâğıt boştu.** İki kural çarpışıyordu: görünüm
  kipi açık olmayan bölüme `[data-disgorunum]{display:none !important}`
  koyuyor, yazdırma bloğu da öbür bölümleri gizliyor — geriye **166
  karakter** kalıyordu. Artık hangi görünümdeysen ol, kâğıda **haftalık
  program + CRN listesi** basılıyor.
* **Kâğıt artık belirli.** Ölçüm, beş görünümden yazdırıldığında: ızgara
  1512px, metin 2172 karakter, yükseklik 1381px — **beşi de birebir aynı.**
  (Önce: 1280–1464px arası genişlik, 2172–2931 arası metin.)

> Kural, yazdırma bloğunun kendi yorumunda zaten yazıyordu: *"basılan sayfa
> ekranın fotoğrafı değil."* Uygulanmamıştı.

---

## Ölçülüp TEMİZ çıkanlar (değişiklik yok)

Bunlar da tarandı; kayıt için:

| ne | ölçüm |
|---|---|
| odak halkası | ilk **24 durakta** eksiksiz |
| kapalı görünümde klavye tuzağı | **119 Tab durağının 0'ı** kapalı bölümde |
| pencereler | hepsi `:modal`; Esc'te odak **çağırana dönüyor** |
| 320px yeniden akış (1.4.10) | on bir görünümde yatay taşma **0** |
| %200 yazı (1.4.4) | taşma **0** |
| kaydırma işareti | kayan tek kutu `data-more` taşıyor |
| kesilen ders adı | **yok** |

---

## Muhafız denemesi iki zayıf muhafız buldu

Bu repoda kural: **düzeltmeyi geri koy, testin kırmızıya döndüğünü gör.**
Yedi düzeltme geri konuldu; ilk turda ikisi **yeşil kaldı**:

1. İki muhafız `@media print` bloğunda **yorumlarıyla birlikte** arama
   yapıyordu. Yorum, neyin neden değiştiğini anlatırken seçici adlarını da
   yazıyor — koddan silinen `#panels`ı muhafız kendi yorumunda buluyor ve
   yeşil kalıyordu. Artık `_kod()` yorumları söküyor.
2. Palet denemesi **yanlış bloğu** bozdu (dört blokta aynı girintili satır
   var). Doğru bloğa nişan alınınca kırmızıya döndü — ama bu arada
   `prefers-color-scheme` bloğunda **aynı `--yandal` satırının iki kez**
   durduğu görüldü (Faz 38b'nin düzeltmesi bir kez fazla uygulanmış).
   Zararsız ama elle tutulan dört palet kopyasının kaydığının kanıtı.

Onun için iki eski test **yeniden yazıldı** (silinmedi, sebebi başlarında):
`test_faz43_tasarim_sistemi` jetonları **dosyada saymayı** bıraktı
(*"`--scrim:` tam 3 yerde geçmeli"* — kâğıt paleti dördüncü blok olunca
kırıldı) ve artık **blokların jeton kümesini karşılaştırıyor**. Yeni bir
jeton yalnız bir palete eklenirse test, adını hiçbir yere yazmaya gerek
kalmadan kırılır.

---

## Testler

`tests/test_faz48_tarama.py` (12 test): katlanan başlık 24px · taban
`summary` esnek kutu **değil** · "kaldır" 24px · `scrollIntoView` sınıfı
kapalı · "Şimdi:" düğmeleri görünüm açıyor · CRN yüklemesi görünüm açıyor ·
kâğıt hep gündüz paleti · üç açık palet aynı · kabuk kâğıda sızmıyor · hangi
görünümde olursa olsun program basılıyor · kâğıt hep aynı kâğıt · uçtan uca
(tarayıcıda: kâğıt beş görünümden aynı, gece şemasında da gündüz renkleri,
pencerelerde 24px altı hedef yok).
