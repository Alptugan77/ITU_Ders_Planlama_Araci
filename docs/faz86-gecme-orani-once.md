# Faz 86 — tahmini zorlukta geçme oranı ortalamanın önünde

> ⚠️ **Faz 87'de değişti:** katalog yüzdeliği ve sabit tablolar kalktı; zorluk
> artık iki alt puanda, 10 üzerinden ve VF geçme oranına başarısız olarak
> giriyor. Güncel ölçü: `docs/faz87-iki-alt-puan.md`.

Kullanıcı 24.09.2026: *"zorluk düzeyi hesaplamasında geçilme yüzdesini
geçilme notunun üstüne koyar mısın bazen çan dağılımı yüzünden kolay dersler
orta zorlukta veya zor diye anlaşılabilir"*.

## Sorun — ölçüldü

Faz 85 kademeyi yalnız not ortalamasından çıkarıyordu. Bağıl (çan eğrisi)
değerlendirmede ortalamayı hocanın dağıtımı belirler: sınıfın neredeyse hepsi
geçse de ortalama düşük kalabilir. Gerçek katalogda (2025-2026) ortalaması
2.40'ın altında, FF oranı %4'ün altında **21 ders** vardı ve hepsi "zor" ya
da "çok zor" çıkıyordu:

| Ders | Geçme | Ortalama | Faz 85 | Faz 86 |
|---|---|---|---|---|
| GMI 214 | %98.9 | 2.18 | çok zor | orta |
| CEV 401 | %98.3 | 2.30 | zor | orta |
| MAK 307 | %97.7 | 2.31 | zor | orta |
| CEV 211 | %99.2 | 2.35 | zor | kolay |
| EFN 301E | %100 | 1.36 | çok zor | kolay |

Gerçekten zor dersler yerinde kaldı:

| Ders | Geçme | Ortalama | Kademe |
|---|---|---|---|
| FIZ 102E | %75.4 | 1.84 | çok zor |
| MAT 103 | %83.6 | 1.97 | çok zor |
| BLG 223E | %82.5 | 2.36 | çok zor |
| ING 100 | %98.8 | 3.65 | çok kolay |

## Yeni ölçü

1. **Geçme oranı**: olağan dönemlerde VF hariç harf notu alanlar arasında
   FF almayanların payı.
2. İki yüzdelik hesaplanıyor. Her ikisinde eşitler orta sırada; derslerin
   %20'sinde FF = 0 ve orta sıra olmasa hepsi en kolay uca yığılırdı.
   * FF oranının katalogdaki yüzdeliği: yüksek FF → zor.
   * Ortalamanın katalogdaki yüzdeliği: düşük ortalama → zor.
3. **Birleşik puan** = 0.7 × FF yüzdeliği + 0.3 × (1 − ortalama yüzdeliği).
4. Kademe = birleşik puanın katalogdaki beşte birlik dilimi.

Böylece geçme oranı belirleyici oluyor. Ortalama ise aynı geçme oranındaki
dersleri ayırıyor: FF'si 0 olan 239 ders kendi aralarında ortalamayla
sıralanıyor.

**Sabit tablolar:** katalogda 300'den az derecelenebilir ders varsa kullanılıyor.
* Üç sayının (FF, ortalama, birleşik) 21 noktalık yüzdelik tablosu.
* Gerçek katalogdan `tools/zorluk_olcegi.py` ile üretildi; elle yazılmadı.
* Canlı hesapla uyumu gerçek katalogda **%99,1** (1187 dersin 1176'sında aynı kademe).

## Sunum

* **Ders penceresi:** önce sayı satırı: *geçme oranı %83.6 · ortalama 1.97 ·
  n=4948*. Ardından katalogdaki yer (*geçme oranı bundan düşük olanların payı
  %12, ortalaması bundan düşük olanların payı %9*) ve şu not: *"Kademe
  ağırlıklı olarak geçme oranından (%70), ikincil olarak not ortalamasından
  (%30) belirlenir: bağıl (çan eğrisi) değerlendirmede ortalama düşük olsa da
  öğrencilerin çoğu dersi geçebilir."*
* **Rozetin ipucu metni** aynı sırayla: geçme oranı, sonra ortalama.
* **"Kolaydan zora" sıralaması:** aynı kademede önce geçme oranı, sonra
  ortalama.

## Testler

`tests/test_faz86_gecme_orani.py`. Kapsam:
* çan eğrili ders zor görünmüyor, aynı ortalamayla FF'si yüksek ders çok zor;
* ağırlıklar;
* eşitlerin orta sırası;
* katalogdan canlı ölçek;
* sabit tabloların biçimi ve üreticisi;
* metin ve sıralama.

`test_faz85` yeni alanlara uyarlandı. Vitrindeki GEO 315E'nin FF oranı ≈%8
olduğu için orta'dan zor'a geçti; aynı kademede geçme oranı eşitlik bozmasını
doğrudan sınayan kontrol eklendi.

Geri alma deneyleri kırmızıya dönüyor:
* ağırlıkları yalnız ortalamaya çevirmek;
* iki eşitlik kuralından birini kaldırmak;
* sıralamadaki geçme oranı kuralını kaldırmak.
