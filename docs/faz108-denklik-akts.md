# Faz 108 — Denklik önerisinde AKTS

Kullanıcı 27.09.2026: *"akts veya kredi farklıysa denklik olmuyor diye
biliyorum ama itü denklikleri yayınlıyor zaten"*.

## Sorun

"Denklik önerileri" (`discover._build`), öğrencinin aldığı dersle plandaki
açık yuvayı ada göre eşleştirip güven veriyor. Güven yalnız **krediye**
bakıyordu:

* Adı ve kredisi aynı, AKTS'si farklı çift **yüksek güven** alıyordu.
* Bu çift arayüzdeki "yüksek güvenli N eşleşmenin tümünü uygula" düğmesiyle
  toplu uygulanabiliyordu.
* Kullanıcının kuralına göre böyle bir çift denk değil; uygulanınca ilerleme
  yüzdesi olduğundan iyi görünüyordu.

## Değişiklik

* **AKTS ölçüte eklendi.** Kredisi aynı ama AKTS'si farklı çift artık
  **düşük güven** alıyor ("AKTS farklı: 5 ≠ 7.5"); yüksek güvende gerekçelere
  "aynı AKTS" ekleniyor. AKTS bilinmiyorsa (katalogda ~%20) karar eskisi gibi
  krediyle veriliyor.
* **Düşük güven grubunda açıklama:** "Kredisi, AKTS'si ya da dili farklı
  dersler çoğunlukla denk sayılmaz. Uygulamadan önce İTÜ'nün resmî denklik
  listesine bakınız ya da danışmanınıza sorunuz." "Uygula" düğmesi kalıyor;
  karar öğrencinin.
* **Yeni dış bağlantı:** `obsDenklik` (OBS Ders Plan Denklikleri).

Resmî denklikler kataloğa girdiğinde (Faz 106, `make all-plans`) onlar zaten
kendiliğinden uygulanıyor. Bu öneriler, resmî listede olmayan eşleşmeler
içindir.

## Doğrulama

`tests/test_faz108_denklik_akts.py`: dört güven durumu (aynı AKTS, farklı
AKTS, AKTS bilinmiyor, farklı kredi) ve düşük güven açıklaması. Düzeltme geri
alınınca 2 test kırmızı.
