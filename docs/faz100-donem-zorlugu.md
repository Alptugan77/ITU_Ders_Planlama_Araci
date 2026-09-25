# Faz 100 — Dönem zorluğu ders sayısı ve krediyle artıyor

Kullanıcı 25.09.2026: *"ders programında tahmini zorluk kısmında alınan ders
sayısı artıkça zorluk artmalı 1 ders alındığında o ders çok zor olsa bile
kolay geçer ama 15 tane orta ders alınırsa dönem zor geçer"*.

## Sorun

Programın "tahmini zorluğu" derslerin kredi ağırlıklı **ortalamasıydı**
(Faz 88). Ortalama yükü görmüyordu: tek bir çok zor ders 9.5/10, on beş orta
ders 5/10 çıkıyordu.

## Değişiklik (`programZorlugu`, arayüz)

Her dersin kredisi, zorluğuyla ağırlıklandırılıp **toplanıyor**:

    ağırlık = 0.5 + puan / 10      (çok kolay 0.5 … orta 1.0 … çok zor 1.5)
    dönem   = 10 × Σ(ağırlık × kredi) / 40, en çok 10

| Program | Eski (ortalama) | Yeni (dönem) |
|---|---|---|
| tek çok zor ders (3 kr) | 9.5 | 1.1 çok kolay |
| 7 orta ders (21 kr) | 5.0 | 5.3 orta |
| 15 orta ders (45 kr) | 5.0 | 10 çok zor |

* Kolay ders de emek istiyor: ağırlık 0'a inmiyor.
* Verisi olmayan ders **orta** sayılıyor (yükten düşürmek dönemi hafif
  gösterirdi) ve özet bunu yazıyor. Hiçbir dersin verisi yoksa dönem zorluğu
  verilmiyor: yalnız krediden zorluk iddia etmiyoruz.
* Gösterim:
  * **Özet:** "tahmini dönem zorluğu 5.7/10 (orta) · 8 ders, 24 kredi ·
    ders ortalaması 3.8/10: …". Dönem 8.5 ve üstündeyse "dönem yükü çok
    ağır" uyarısı çıkıyor.
  * **Karşılaştırma:** dönem zorluğu ana sayı, ortalama altta. "En hafif"
    eşiği 0.3: dönem ölçeğinde 3 kredilik bir dersin ortadan çok zora
    çıkması ≈0.4 fark ediyor, eski 0.5 eşiği bunu hiç göstermezdi.
  * **Danışman özeti:** aynı iki sayı.
* Ders penceresindeki ders zorluğu ve yol haritasındaki "zor ders" sayısı
  değişmedi. Öneri puanına hâlâ **dahil değil**.

## Doğrulama

* `tests/test_faz100_donem_zorlugu.py`: kullanıcının iki örneği, ölçek,
  monotonluk, verisiz ders, veri yokken sessizlik, ağır yük uyarısı. Beş
  mutasyonun beşi de kırmızı: tavan, 0.5 taban, verisiz ders, ortalamaya
  dönüş, uyarı eşiği.
* Faz 85/88/89 testlerinin sabitlenmiş metinleri yeni biçime güncellendi.
