# Faz 96 — kullanım kılavuzu

Kullanıcı 25.09.2026: *"can you create a help or info section for people to
know the usecases and abilities of DEPAR and how to use it"*.

## Sorun

95 fazda eklenen özelliklerin çoğu bir düğmenin ya da bir görünümün içinde
duruyor. Yeni gelen öğrenci neyin var olduğunu bilmiyordu. Örnekler: kayıt
günü listesinin çevrimdışı açılması, CRN'den program yükleme, not senaryosu,
kalma riski, danışman özeti.

## Değişiklik

* **Yeni görünüm: "Kullanım kılavuzu".** Rayda YARDIM grubunda, telefonda
  "Daha" altında. Ayrıca başlıkta "Kılavuz" düğmesi var: ilk gelen öğrencinin
  ilk sorusu rayın en altında kaybolmasın.
* **İçerik:**
  * **DEPAR nedir:** ders programı ve mezuniyet planlama aracı; anadal, ÇAP
    ve yandal birlikte; kayıt yapmaz (ders kaydı Kepler'de).
  * **Başlarken:** bölüm ve yarıyıl → transkript yapıştırma → önerilen
    program; üç adım.
  * **Neler yapabilirsiniz:** altı kart — kayıt haftası, ders seçimi,
    ilerleme ve mezuniyet, not ortalaması ve eşikler, ÇAP ve yandal,
    danışman görüşmesi ve günlük kullanım.
  * **İşaretler:** dolu / son N, yerleşke geçişi, bina + derslik,
    çevrimiçi, zorluk.
  * **Bilmeniz gerekenler:** hesaplar tahmindir, esas olan OBS ve
    yönetmeliktir; kontenjan verisi tarihlidir; akademik takvim yoktur;
    bilinmeyen tahmin edilmez; veriler kendi bilgisayarınızda ya da
    tarayıcınızda kalır.
* **Yeri gösteren düğmeler.** Her kartta ilgili görünüme götüren düğmeler
  var. Görünüm o an kapalıysa (ör. henüz kaydedilmiş program yok)
  `gorunumAc` sessizce ilk görünüme düşerdi: "Kaydedilen program"a basan
  kişi haftalık programa gidiyordu. Artık kılavuzda kalınıyor ve nedeni
  yazılıyor.

## Kayma koruması

Kılavuzun andığı her düğme adı ("Kayıt günü listesi", "Takvime aktar",
"CRN'den program yükle"…) sayfanın geri kalanında gerçekten var olmalı.
Bir düğmenin adı değişirse test kırmızıya dönüyor; kılavuz sessizce
eskimiyor. İlk taslakta bu test iki yanlışı hemen yakaladı: "program
tercihleri" küçük harfle yazılmıştı ve "Alternatif olarak kaydet" hiç
anılmamıştı.

## Tam test takımının yakaladıkları

* İlk taslak "ders kaydı OBS'de" ve "OBS'ye girilecek CRN'ler" diyordu.
  Faz 67'nin kuralı: kayıt **Kepler'de** yapılır. Düzeltildi.
* Telefon kuralları ikinci bir `@media (max-width:560px)` bloğundaydı;
  sayfanın asıl telefon bloğuna taşındı.
* Kılavuz aracın adını elle yazıyordu ("DEPAR, İTÜ öğrencileri…"). Ad tek
  kaynaktan geliyor (`AD_KISA`, `AD_KURUM`); kılavuz da artık oradan alıyor.

## Doğrulama

* `tests/test_faz96_kilavuz.py`: görünüm listesi, "git" düğmelerinin var
  olan görünümlere gitmesi, düğme adlarının sayfada bulunması, sınır
  cümleleri ve vitrinde uçtan uca (başlık düğmesi, her "git" düğmesi,
  kapalı görünüm notu, telefon genişliğinde taşma yok).
* 8 geri alma deneyinin 8'i kırmızı.

## Güncelleme (25.09.2026): "Plandan işaretle" adımı

Kullanıcı: *"kılavuzda transkripten gir kısmı yerine dersleri plandan
işaretle kısmını ekler misin"*.

* Başlarken'in 2. adımı artık "Aldığınız dersleri plandan işaretleyiniz".
  Yarıyıl seçildiyse önceki yarıyılların zorunlu dersleri öneri olarak
  işaretli gelir (Faz 47); notu seçilmeyen ders DD sayılır. Notlar için
  "Transkript yapıştır" aynı pencerede seçenek olarak anılıyor.
* Adımdaki "Plandan işaretle" düğmesi kurulumdaki pencereyi aynı işlevle
  (`checklistDialog`) açıyor; ikinci bir yol yazılmadı.
* Test: adımın metni, düğme adının sayfada bulunması ve düğmenin gerçekten
  "Plandan işaretle" penceresini açması.
