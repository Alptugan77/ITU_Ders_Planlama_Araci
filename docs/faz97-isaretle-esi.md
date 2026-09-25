# Faz 97 — "Plandan işaretle" İngilizce eşiyle karşılanmış ÇAP dersini söylüyor

Kullanıcı 25.09.2026: *"kılavuzda transkripten gir kısmı yerine dersleri
plandan işaretle kısmını ekler misin bir de geliştirmeye devam et"*.

Kılavuzun ikinci adımı "Plandan işaretle" oldu (bkz. `faz96-kilavuz.md`).
O pencereyi ÇAP öğrencisi olarak açınca bir tutarsızlık bulundu.

## Sorun

Faz 92'den beri İngilizce şubede geçilen ders, Türkçe kodlu ÇAP slotunu
dolduruyor. Örnek: BLGE öğrencisinin anadalda geçtiği EHB 222E, ÇAP'ın
("BLG_EHB") EHB 222 slotunu dolduruyor ve ilerleme paneli 1/16 diyor.

"Plandan işaretle" penceresi ise ÇAP bölümünde EHB 222'yi **boş**
gösteriyordu (gerçek katalogda doğrulandı). Öğrenci bunu "düzeltmek" için
tiklerse transkripte notu bilinmeyen, DD sayılan ikinci bir ders ekleniyordu.
Bu da GNO'yu bozuyordu.

## Değişiklik

* **Sunucu** (`plan_checklist`): ÇAP/yandal zorunlu slotunda ders alınmamış
  ama İngilizce eşi geçilmişse öğe `via: "EHB 222E"` ve `viaGrade` taşıyor.
  Kural Faz 92'ninkiyle aynı: yalnız ÇAP/yandal, yalnız İngilizce → Türkçe
  yön; anadal planı değişmiyor.
* **Pencere:**
  * satır işaretli ve kilitli; not seçimi yok; "✓ EHB 222E ile karşılandı";
  * ipucu nedenini söylüyor;
  * Kaydet bu dersi ne ekliyor ne siliyor;
  * dönemden önerilen tikler ve "önceki yarıyılları işaretle" onu atlıyor.

## Doğrulama

* `tests/test_faz97_isaretle_esi.py`:
  * sunucu verisi (ÇAP işaretleniyor; ters yön ve anadal işaretlenmiyor);
  * tarayıcıda kilitli satır;
  * Kaydet'in gönderdiği listede ders yok.
* 5 geri alma deneyinin 5'i kırmızı. İlk turda "anadal da" deneyi yeşil
  kalmıştı; fikstüre anadal tarafında eşi geçilmiş bir ders eklendi.
