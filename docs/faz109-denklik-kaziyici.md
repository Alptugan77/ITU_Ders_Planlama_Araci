# Faz 109 — Resmî denklik kazıyıcısı onarıldı; beyanlar resmî listeyle doğrulandı

OBS erişimi açılınca (27.09.2026) denklik adımı çalıştırıldı. 93 lisans
programının **hiçbirinden** denklik gelmedi. Faz 106'da bulunan "katalogda
denklik yok" sorununun asıl kök nedeni buydu: adım çalışsa bile boş dönüyordu.

## Üç sessiz kırılma (`sources/obs_equivalence.py`)

1. **Program menüsü artık Türkçe.** Seçenekler "Fizik Mühendisliği Lisans",
   "… Yüksek Lisans", "… Doktora" biçiminde. Süzgeç "Undergraduate" aradığı
   için 0 program buluyordu. Artık iki dil de tanınıyor ve "Yüksek Lisans"
   lisans sayılmıyor (93 program; kod yorumundaki ölçümle aynı).
2. **Sonuç tablosu ayrı uçta.** Sayfanın form GET'i tablo vermiyor; form
   sonucu `GET /public/GenelTanimlamalar/DersDenklikAra` ucundan AJAX ile
   alıyor (`config.EP["eq_search"]`).
3. **"Bulunamadı" metni her sayfada.** "Ders denklik bilgisi bulunamadı"
   artık her sayfanın JavaScript'inde (AJAX hata işleyicisi) duruyor. Eski
   denetim bu yüzden her sayfayı boş sayardı. Artık yalnız yanıtta tablo
   yoksa boş sayılıyor.

## Sonuç (bütün lisans programları, 26 dk)

* **3183 resmî denklik** geldi.
* Plana sadık öğrencide engelli ders sayısı 109'dan **104**'e indi.
* **Faz 104–105 beyanları resmî listeyle karşılaştırıldı**
  (`tools/kod_gocu_taramasi.py`, taban kodla): 21 beyanın **18'i resmî
  listede birebir var**. BBF göçünün tamamı, EEE, IND, IAD, MMD, NAE,
  ELE 222 ↔ EHB 222 bunların arasında. İki bağımsız kanıt ölçütü
  (Faz 105) resmî listeyle örtüştü.
* **Resmî karşılığı olmayan 3 beyan kaldırıldı:**
  * ECN 101E → EFN 105E: resmîde yalnız ECN 105 ↔ EFN 105 var.
  * ELH 222(E) → EHB 222(E): EHB 222'nin resmî eşleri EEE 225, EHB 231 ve
    ELE 222.
* **AKTS'si farklı 4 aday** resmî listede de yok. Kullanıcının kuralını
  ("AKTS ya da kredi farklıysa denklik olmuyor") doğruluyor.
* **Karşılaştırıcı taban kodla çalışıyor:** resmî sayfa kodları E'siz yazıyor
  ("BLG 252" ↔ "BBF 203"). İlk koşuda E'li beyanların hepsi "karşılıksız"
  çıkmıştı.
* **Motor 3183 denklikle sorunsuz:** gerçek BLGE profili 5.9 sn'de kuruldu,
  hata yok.

## Yayın

Katalog repoda tutulmuyor, yerelde kuruluyor. Yeni kataloğun kullanıcıya
ulaşması için `make all-plans` (Faz 106'dan beri `--all-equivalences` ile)
yeniden çalıştırılıp site kurulmalı.

## Doğrulama

`tests/test_faz109_denklik_kaziyici.py`: Türkçe program menüsü, sonucun ayrı
uçtan alınması, JavaScript'teki "bulunamadı" metninin sayfayı boş
saydırmaması, tablo yoksa boş sayılması ve taban kodlu beyan karşılaştırması.
Düzeltme geri alınınca 2 test kırmızı. Faz 105 testi 14 beyanı ve kaldırılan
3 beyanın yokluğunu sınıyor.
