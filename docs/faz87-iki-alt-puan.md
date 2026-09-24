# Faz 87 — zorluk iki alt puanda, 10 üzerinden

Kullanıcı 24.09.2026: *"zorluğu iki kısıma ayır yüksek not alma zorluğu ve
geçme zorluğu bunları 10 üzerinden puanlandır sonra geçme zorluğunun %70i ile
yüksek not alma zorluğunun %30unu toplayıp genel bir zorluk üret örnek olarak
2.5 ortalama 10 üzerinden 5 ediyor vfleri de geçme oranına say çünkü vizeden
kalan kişiler finale giremediği için vf gözüküyor %85 geçme oranı da 10
üzerinden 5 gibi düşün mat 103 çok zor değil belki zor sayılabilir"*.

Faz 85–86'nın katalog yüzdeliği ve sabit tabloları (`tools/zorluk_olcegi.py`)
kaldırıldı. Ölçek artık **mutlak**: "10 üzerinden 5" doğrudan okunabiliyor,
katalogdaki öbür derslere bağlı değil, vitrinde de gerçek katalogda da aynı
sayıyı veriyor.

## Ölçü (`notlar.zorluk`)

| Alt puan | Dayanak | 0 | 5 | 10 |
|---|---|---|---|---|
| **Geçme zorluğu** | geçme oranı, **VF başarısız sayılır** | %100 | %85 | %70 ve altı |
| **Yüksek not alma zorluğu** | harf notu alanların ortalaması | 4.00 | 2.50 | 1.00 ve altı |

Her iki alt puan doğrusal, 0–10 arasına kırpılıyor.

**Genel = 0.7 × geçme zorluğu + 0.3 × yüksek not alma zorluğu.**

**VF neden geçme oranına giriyor:** vizeden kalan öğrenci finale giremediği
için notu VF görünür. Yani VF çoğunlukla dersten kalmaktır; Faz 85–86 bunu
devamsızlık diye dışarıda bırakıyordu. Ortalamaya ise girmiyor, çünkü VF'li
öğrencinin harf notu yok.

**Kademeler** (genel puan):

| Genel puan | Kademe |
|---|---|
| 0–2 | çok kolay |
| 2–4 | kolay |
| 4–6 | orta |
| 6–8.5 | zor |
| 8.5–10 | çok zor |

"Çok zor" dilimi bilerek dar tutuldu. Kullanıcının yargısı: MAT 103 zor,
çok zor değil.

Tekrar/bütünleme sınıfları havuz dışı kalıyor. Kural değişmedi; öğrenci
sayısına artık VF de dahil. BL/BZ dersleri ve 20'den az öğrencili dersler
derecelenmiyor; 20–59 öğrencide "az veri" işareti var.

## Gerçek katalog (2025-2026, olağan dönemler)

| Ders | Geçme (VF dahil) | Ortalama | Geçme z. | Yüksek not z. | Genel | Kademe |
|---|---|---|---|---|---|---|
| FIZ 102E | %64.9 | 1.84 | 10.0 | 7.2 | 9.2 | çok zor |
| BLG 335E | %72.8 | 1.88 | 9.1 | 7.1 | 8.5 | çok zor |
| **MAT 103** | %73.1 | 1.97 | 9.0 | 6.8 | **8.3** | **zor** |
| FIZ 101 | %74.1 | 2.12 | 8.6 | 6.3 | 7.9 | zor |
| KIM 101 | %81.0 | 2.35 | 6.3 | 5.5 | 6.1 | zor |
| MAT 271E | %83.1 | 2.55 | 5.6 | 4.8 | 5.4 | orta |
| KMM 211 | %93.8 | 2.51 | 2.1 | 5.0 | 3.0 | kolay |
| GMI 214 | %97.9 | 2.18 | 0.7 | 6.1 | 2.3 | kolay |
| ING 100 | %93.5 | 3.65 | 2.2 | 1.2 | 1.9 | çok kolay |

GMI 214 gibi çan eğrisiyle not verilen ve herkesin geçtiği dersler kolay
kalıyor; Faz 86'nın çözdüğü sorun geri gelmedi.

## Sunum

* **Rozet** (aday listesi, yol haritası): beş çubuk, kademe ve genel puan
  (*"zor 8.3"*). İpucu metninde iki alt puan ve dayanakları yazıyor.
* **Ders penceresi**:
  * genel puan *"8.3 / 10"*;
  * iki alt puan satırı, her biri kendi 0–10 çubuğu, ağırlığı ve dayanağıyla:
    *"geçme oranı %73.1 (VF dahil)"*, *"harf notu ortalaması 1.97"*;
  * ölçeğin çapaları, formül, VF'nin neden geçemeyenlere sayıldığı ve
    kademe sınırları yazıyor.
* **"Kolaydan zora" sıralaması** genel puana göre yapılıyor.
* **Program özeti ve yol haritası** değişmedi (kademe sayıları).
* Öneri puanına **girmiyor** (Faz 38 kuralı).

## Testler

`tests/test_faz87_iki_alt_puan.py`:
* kullanıcının iki çapası (2.5 → 5, %85 → 5) ve uçlar, kırpma;
* %70 / %30;
* kademe sınırları;
* VF'nin geçmeye başarısız olarak girip ortalamaya girmemesi;
* MAT 103 → zor, FIZ 102E → çok zor, GMI 214 → kolay;
* uçtan alt puanlar ve arayüz metinleri.

`tests/test_faz85_zorluk.py` yeni alanlara uyarlandı. Faz 86'nın
yüzdelik testleri silindi, çünkü o düzenek kalktı.

Geri alma deneyi: 9 kuralın her biri geri alınınca test kırmızıya dönüyor.
NOT_CAPA deneyi otomatik koşuda bayt kodu önbelleği yüzünden yeşil göründü;
elle koşunca kırmızı.
