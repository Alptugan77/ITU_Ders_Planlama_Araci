# Faz 93 — programda derslik

Kullanıcı 25.09.2026: *"ders programında dersin fakültesi gözüküyor ama sınıfı
gözükmüyor sadece programa bakarak derslere gidilebilecek şekilde sınıfları
gösterir misin"*.

## Sorun

Derslik veride vardı (`lesson_meeting.room`) ama sunucu arayüze hiç
göndermiyordu. Izgarada yalnız bina kodu ("MED") duruyordu; öğrenci hangi
sınıfa gideceğini OBS'de ayrıca arıyordu.

Gerçek katalogda 3900 buluşmanın **1725'inde** derslik ilan edilmiş. 2175'inde
OBS "--" yazıyor (derslik ilan edilmemiş).

## Değişiklik

* Şube verisi dersliği taşıyor (`ui._derslik`). "--" gibi ilan edilmemiş
  değer BOŞ gidiyor: `_building` ve `_hoca` ile aynı ilke, "--" bir sınıf adı
  değil.
* Yerin göründüğü her yerde bina + derslik: **"INB D01"**.
  * haftalık ızgara, telefonun gün listesi, şube seçme penceresi;
  * PNG çıktısı, basılı kayıt listesi (sütun "Gün / saat · yer");
  * takvim dosyası: `LOCATION:INB D01 — İnşaat Fakültesi`;
  * terminal çıktısı.
* İpucu tam yeri söylüyor: "INB — İnşaat Fakültesi · derslik D01". Derslik
  ilan edilmemişse "derslik OBS'de bildirilmemiş" diyor; uydurulmuyor.
* "INB D01" hücrede ikiye bölünmüyor ve kalın yazılıyor: derse giderken
  bakılan şey bu.
* CRN yapıştırarak yüklenen şube de dersliği taşıyor. Aynı yol eskiden ham
  "undeclared" değerini bina adı diye gönderiyordu; artık aynı temizlikten
  geçiyor.

## Doğrulama

* `tests/test_faz93_derslik.py`: temizlik, şube verisi, CRN yükleme,
  terminal ve vitrinde uçtan uca (ızgara, ipucu, takvim, baskı, şube
  penceresi, telefon görünümü, CRN yükleme).
* 14 geri alma deneyinin 14'ü kırmızı. İlk turda ikisi yeşil kalmıştı (şube
  penceresi, CRN yükleme); testler güçlendirildi.
* Gerçek katalog, BLGE 5. yarıyıl önerisi: 11 buluşmanın 4'ünde derslik var
  (BBB Z-18, Z-20, Z-21); kalanında OBS derslik ilan etmemiş.
