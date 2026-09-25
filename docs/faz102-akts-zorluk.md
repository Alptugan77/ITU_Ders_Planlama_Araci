# Faz 102 — Ders ve dönem zorluğunda AKTS

Kullanıcı 25.09.2026: *"dönem ve ders zorluğunu hesaplarken aktsyi de hesaba
kat akts ne kadar emek gerektirdiğinin de bir göstergesi dersin"*.

AKTS tanımı gereği öğrencinin toplam emeği (1 AKTS ≈ 25–30 saat). Kredi ise
ders saatini ölçüyor.

## Ders zorluğu (`notlar._zorluk`)

Not tabanlı genel puana (Faz 87: %70 geçme + %30 yüksek not) bir iş yükü
düzeltmesi ekleniyor:

    düzeltme = 0.1 × (AKTS − 5), en çok ±1

* **5:** gerçek katalogda derecelenen 1274 dersin AKTS medyanı.
* **Örnekler:** 8 AKTS +0.3, 2 AKTS −0.3, 12 AKTS'lik bitirme +0.7.
* **Neden ağırlıklı ortalama değil:** %20 ağırlıkla karıştırmak uçtaki dersi
  ortaya çekiyordu. FIZ 102E (4.5 AKTS) 9.2'den 8.2'ye inip "çok zor"dan
  "zor"a düşüyordu; kullanıcının Faz 87 yargısı "FIZ 102 çok zor".
* **Neden 0.1:** MAT 103E'nin (6 AKTS) not puanı 8.3 ve kullanıcının yargısıyla
  "zor, çok zor değil". AKTS başına 0.17 ve üstü onu 8.5 eşiğine itiyor.
* **AKTS kaynağı:** önce katalog; yoksa planlardaki slot AKTS'si; o da yoksa
  düzeltme yapılmıyor ve pencere bunu yazıyor.
* **Sunucunun eklediği alanlar:** `ects`, `ectsEffect`, `gradeOverall` (not
  tabanlı puan).

**Gerçek katalogdaki etki:** 1274 dersin 74'ünün kademesi değişti, çoğu bant
sınırındaki derslerde bir kademe. Örnekler:

| Ders | AKTS | Not tabanlı | Yeni |
|---|---|---|---|
| MAT 103E | 6 | 8.3 zor | 8.4 zor |
| FIZ 102E | 4.5 | 9.2 çok zor | 9.1 çok zor |
| BLG 223E | 8 | 6.1 zor | 6.4 zor |
| BLG 4902E | 12 | 0.0 | 0.7 çok kolay |

Ders penceresinde yeni bir satır var: "İş yükü: 8 AKTS (tipik ders 5) → genel
puana +0.3 (not tabanlı puan 6.1)". Formül açıklaması ve ipucu da
güncellendi.

## Dönem zorluğu (`donemZorlugu`, arayüz)

Faz 100'de yük krediydi; artık AKTS:

    ağırlık = 0.5 + not tabanlı puan / 10     (çok kolay 0.5 … orta 1.0 … çok zor 1.5)
    dönem   = 10 × Σ(ağırlık × AKTS) / 60, en çok 10

* **Ölçek:** normal dönem 30 AKTS; orta zorlukta 5.0. Tek çok zor ders
  (5 AKTS) 1.2, on beş orta ders (75 AKTS) 10.
* **Ağırlık not tabanlı puandan.** Dersin AKTS düzeltmeli puanını kullanmak
  AKTS'yi iki kez saymak olurdu, çünkü AKTS zaten miktar olarak toplanıyor.
* **AKTS'si bilinmeyen ders:** kredisinin 1.75 katı (katalogdaki AKTS/kredi
  oranı). Özet bunu yazıyor: "(1 dersin AKTS'si kredisinden tahmin edildi)".
* **Ders ortalaması** da AKTS ağırlıklı.
* **Aynı hesap üç yerde:** haftalık program özeti, karşılaştırma ve danışman
  özeti ("8 ders, 40 AKTS").
* **Yol haritası kartları:** yeni olarak aynı dönem zorluğunu gösteriyor
  ("tahmini dönem zorluğu 6.4/10 (zor) · 1 zor ders"); sunucu kalemlere
  `ects` ekliyor, havuz yuvasında slotun AKTS'sini.
* **Karşılaştırmanın "en hafif" eşiği** onda birlik adımlarla karşılaştırılıyor:
  6.4 + 0.3 kayan noktada 6.7'den büyük çıkıyordu.

**Gerçek katalogdaki etki** (BLGE, 5. yarıyıl): Öneri 1 (11 ders, 23 kredi,
43.5 AKTS) kredi hesabıyla 6.2, AKTS ile 7.1 (zor). 30 AKTS'lik normal
dönemin çok üstünde olduğu için bu beklenen sonuç.

## Doğrulama

* **`tests/test_faz102_akts_zorluk.py` (14 test):**
  * düzeltme ve sınırı;
  * kullanıcı yargısı (MAT 103E zor, FIZ 102E çok zor);
  * sunucu alanları ve slot AKTS yedeği;
  * yol haritası kalemlerinin AKTS'si;
  * arayüzde AKTS'nin yük olması, not tabanlı ağırlık, krediden tahmin, AKTS
    ağırlıklı ortalama, pencere satırı, ipucu ve yol haritası kartı.
* **Mutasyonlar:** 15 mutasyonun 15'i kırmızı.
* **Güncellenen sabitlenmiş testler:** Faz 85/87/88/89/100. Vitrindeki
  program 8 × 5 AKTS = 40 AKTS olduğundan 5.7'den 6.4'e (zor) çıktı.
