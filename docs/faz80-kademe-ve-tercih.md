# Faz 80 — Kademelerin tasarımı · tercihlerde üst üste binen öğeler

*24.09.2026 · kullanıcı: "kademeler kısmının tasarımını iyileştirir misin bir de
tercihler kısmında üst üste gelen öğeler var onlara bakar mısın".*

Testler +2 (`tests/test_faz80_kademe_ve_tercih.py`). Geri alma deneyi: altı
kuralın altısı kırmızı.

## Tercihler penceresi

* **Çakışma:** "Aynı gün kampüs değiştirmek istemiyorum" ile "Çevrimiçi şubeyi
  yeğlerim" 190px'lik ızgara sütunlarındaydı; `.tickbox` satır kaydırmadığı
  (`white-space:nowrap`) için uzun etiket yandaki kutunun üstüne taşıyordu
  (1400px'te ölçüldü). Artık alt alta bir liste (`.tickliste`); etiket
  gerekirse kayıyor, açıklama (kampüs verisi kapsamı) kutunun altında.
* Başlık "Tercihlerin" → **"Tercihler"** (resmî dil, Faz 66).
* "Kaydetmeden dene" sonucu "1. öneri bu tercihlerle / — / değişmiyor" diye
  üç satıra bölünüyordu (sütun düzeninde üç ayrı düğüm) — tek satır.
* Bütün görünümler ve on pencere 1400 / 390 px'te çakışma için tarandı;
  başka gerçek çakışma bulunmadı (kalan bulgular kaydırma kutusunun
  yapışkan alt çubuğun altında kalan satırları).

## Kademeler

* Kutuda ders **adı** (tek satır, taşarsa üç nokta).
* Kademe başlığında **dönem:** tamamlanmamış ilk kademe "bu dönem", her
  sonraki "en erken 2026-2027 Bahar" … — "Her kademe en az bir dönem
  sürer" kuralı; ipucunda dersin açıldığı yarıyılın geciktirebileceği yazıyor.
* **Tamamlanmış kademe** tek satıra katlanıyor ("Kademe 0 · tamamlandı
  BLG 102E · BLG 231E"); üstü çizili kutular ekranın yarısını kaplıyordu.
* **Telefonda** (≤700px, tek sütun) çizgiler dinlenmede gizli; bir derse
  dokununca yalnız o zincirin çizgileri çıkıyor. Önceden bütün bağlar sağdaki
  oluğa üst üste biniyordu. Bağ bilgisi her kutuda "önce …" diye yazılı.
