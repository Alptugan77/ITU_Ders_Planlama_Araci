# Faz 94 — arka arkaya iki ders farklı yerleşkede

Kullanıcı 25.09.2026: *"continue"*. Faz 93'ün ("programa bakarak derse
gidilebilsin") devamı.

## Sorun

İTÜ'de ders :29'da bitiyor, sonraki :30'da başlıyor. Arka arkaya iki ders
farklı yerleşkedeyse (Ayazağa ↔ Maçka) araya bir dakika kalıyor.

**Ölçüm (gerçek katalog, 11 profil × iki kip):** önerilerdeki 17 yerleşke
değişiminin **10'unda arada 1 dakika** vardı. Örnekler:

* ISL 224E Maçka 11:29'da biter → BLG 351E Ayazağa 11:30'da başlar;
* ATA 122 Maçka → DAN 102 Gümüşsuyu.

Motorun `campus_changes` sayısı üç saatlik arayı da bir dakikalık arayı da
aynı sayıyordu ve yalnız "kampüs değiştirmek istemiyorum" tercihi açıksa
sıralamaya giriyordu. Arayüz bunu hiçbir yerde söylemiyordu.

Ayrıca katalogdaki 67 binanın **32'sinin yerleşkesi boş**. MEDC, BBB ve MSB
bu dönemin 457 ders saatini taşıyor; bunların yerleşkesi bilinmediği için
hiçbir kontrol onları göremiyordu.

## Değişiklik

* **Sayım** (`Schedule.sikisik_gecisler`): aynı gün arka arkaya, iki
  yerleşke de biliniyor, farklı ve arada 60 dakikadan az.
  * Katalogda yol süresi yok; 60 dakika bir kabul, bir ölçüm değil.
  * Yerleşkesi bilinmeyen ya da çevrimiçi ders sayılmıyor.
* **Motor.** Her sıkışık geçiş programdan 30 puan düşürüyor; bu, ders
  puanlarıyla (40–100) aynı ölçek. Aynı dersleri geçişsiz veren program öne
  geçiyor, ama değerli bir ders bunun için programdan düşmüyor.
  * Sert kısıt değil: başka yol yoksa program yine önerilir ve uyarılır.
  * Arama aynı ders kümesinin ilk bulduğu şube varyantını tutuyordu. Artık
    sıkışık geçişi daha az olan varyant onun yerine geçiyor. Geçiş yoksa
    hiçbir şey değişmiyor.
* **Arayüz.** Izgarada ve gün listesinde ikinci derste "⚠ Maçka → Ayazağa ·
  1 dk" işareti var. İpucu önceki dersi ve arayı söylüyor; söz
  "yetişemezsiniz" değil, "bu sürede yetişmeyebilir". Karşılaştırma
  tablosunda kampüs değişimi satırı sıkışık olanları ayrıca sayıyor.
* **Yerleşke beyanı** (`config/katalog-duzeltmeleri.toml`,
  `[[kampus_beyani]]`):
  * MEDC ve BBB Ayazağa, MSB Maçka — her biri katalogdaki bina adıyla
    gerekçeli;
  * yalnız katalog boşken kullanılıyor, katalogdaki değeri ezmiyor;
  * emin olunmayan bina (YDY) beyan edilmedi.

## Doğrulama

* Gerçek katalog, aynı 11 profil: sıkışık geçiş **10 → 0**.
* İlk öneriler 22 kipin 3'ünde değişti: aynı kredi (biri −0,5), bir ders ya
  da şube değişimi.
* 9 profillik eşdeğerlik ölçümünde yalnız geçişi olan iki profil değişti.
* Süre main ile aynı: arka arkaya ölçümde 9,08 / 8,87 sn (main) ve 9,09 sn.
* `tests/test_faz94_yerleske_gecisi.py`: 9 geri alma deneyinin 9'u kırmızı.
  İlk turda iki deney yeşil kalmıştı (ceza sıfırlanınca, CRN yükleme
  beyanı); testler güçlendirildi.
