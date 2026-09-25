# Faz 101 — Sekme şeridi ızgaradaki programı söylüyor

Kullanıcı 25.09.2026: *"bir de kaydedilen program gözüktüğünde üstte
önerilen program seçilmiş gözüktüğü için karıştırılabilir programın kredisi
ve kaç çevrimiçi ders olduğu onu da düzelt lütfen"*.

## Sorun

Açılışta kaydedilen program ızgaraya yükleniyor. Sekme şeridinde ise
"Öneri 1 · 24 kredi" seçili duruyor, araç çubuğunda "değiştirildi"
yazıyordu. Izgaradaki 21 kredilik program, Öneri 1'in düzenlenmiş hâli gibi
okunuyordu. Sekmedeki kredi ve çevrimiçi sayısı öneriye aitti; özet de
çevrimiçi ders sayısını hiç yazmıyordu.

## Değişiklik

* **`izgaraKaynagi()`:** ızgaranın kaynağı içerikten çıkarılıyor, böylece
  kaydedilenden, alternatiften, CRN'den yüklemede ve geri almada doğru kalıyor:
  * bir öneriyle aynıysa o öneri;
  * kaydedilen programla aynıysa "Kaydedilen";
  * bir alternatifle aynıysa onun adı (ör. "Plan B");
  * hiçbiri değilse düzenlenmiş.
* **Şerit:**
  * ızgara öneri değilse başta **kendi sekmesi** seçili durur, ızgaranın
    kendi kredisi ve çevrimiçi ders sayısıyla ("Kaydedilen · 21 kredi · 1
    çevrimiçi"); öneri sekmeleri seçili görünmez;
  * kaydedilen program düzenlenince sekme "Kaydedilen" kalır, "değiştirildi"
    işareti çıkar, sayılar güncellenir;
  * kaydedilen program varsa sekmesi hep durur: "Öneriye dön"den sonra
    tıklayınca kaydedilen yeniden yüklenir (geri alınabilir);
  * kaydedilen program bir öneriyle aynıysa yalnız o öneri seçili görünür.
* **"değiştirildi"** yalnız ızgara tanınan hiçbir programa eşit değilse çıkar.
  **"Öneriye dön"** seçili öneriden farklıysa görünür; ipucu hangi önerinin
  yükleneceğini söyler.
* **Özet:** "7 ders · 35 AKTS · 1 çevrimiçi".

## Doğrulama

`tests/test_faz101_izgara_kaynagi.py` (vitrin uçtan uca) açılış, kaydedilen,
düzenleme, öneriye dönüş, sekmeden geri yükleme, öneriyle aynı kayıt ve
alternatif durumlarını sınıyor. Dokuz mutasyonun dokuzu da kırmızı.
