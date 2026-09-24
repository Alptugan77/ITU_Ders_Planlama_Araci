# Faz 89 — "zor dersleri dağıt" senaryosu ve danışman özetinde zorluk

Kullanıcı 24.09.2026: *"geliştirmelere devam et ve sonrasında pr oluştur"*.

## 1. Yol haritası senaryosu: dönem başına en çok N zor ders

Faz 85'ten beri dönem kartı *"tahmini zorluk: 3 zor ders — yük yoğun olabilir"*
diyordu. Ama öğrenci şu soruyu soramıyordu: *"zor dersleri dağıtırsam ne
zaman biterim?"*

**Motor** (`yolharitasi.kur(..., zor_siniri=N)`):
* Bir döneme en çok N zor ders konuyor. Zor ders, tahmini zorluk kademesi
  ≥ 4 olan ders (genel puan ≥ 6, Faz 87).
* Fazlası o dönem **ertelenip** sonraki uygun döneme kalıyor. Erteleme, saat
  bütçesi (Faz 82) gibi ayrı bir kontrol olarak yapılıyor.
* Sınır ÇAP yarıyıl tabanının ayrı geçişinde de uygulanıyor.
* Seçmeli havuz ve zorluğu **bilinmeyen** ders sınıra sayılmıyor. Verisi
  olmayan dersi "zor" diye ertelemek, bilinmeyeni bilinen gibi göstermek olurdu.
* Dönem kartında *"Dönem başına zor ders sınırı nedeniyle sonraki döneme
  bırakıldı: …"* yazıyor.
* Varsayımlara bir satır ekleniyor.
* Ufuk içinde yerleşemeyen ders için somut bir gerekçe yazılıyor.

**Uç ve arayüz:**
* `/api/yolharitasi` yeni bir `zor` alanı alıyor: 1–5 geçerli; 0 ya da boş
  sınır yok demek; başka değerler reddediliyor.
* Senaryo panelinde *"Dönem başına en çok [sınırsız / 1 / 2 / 3] zor ders"*
  seçimi var. Bu seçim yalnız haritada zor ders **varsa** gösteriliyor.
* Senaryo şeridi seçimi yazıyor. Program kartları bitişin mevcut plana göre
  farkını gösteriyor.

Yapay katalog örneği: aynı Güz yarıyılında üç çok zor ders var.

| Sınır | Yerleşim | Bitiş |
|---|---|---|
| sınırsız | üçü aynı Güz | 2027-2028 Güz |
| 1 | her Güz'e bir ders | 2029-2030 Güz |

Vitrinde gelecek dönemlerde tek zor ders var (MAT 210E); sınır 1 bitişi
değiştirmiyor ve ekran *"mevcut planla aynı"* diyor.

## 2. Danışman özeti

* Program tablosuna **Tahmini zorluk** sütunu eklendi: *"orta 5.5"*,
  verisizse *"—"*.
* Kontrollere programın zorluğu eklendi: *"Tahmini zorluk 3.8 / 10 (kredi
  ağırlıklı; geçmiş not dağılımından) · zor ders yok"*. Sayı karşılaştırma ve
  özetteki `programZorlugu` ile aynı.
* Otomatik sorular:
  * Programda **≥ 3 zor ders** varsa: *"… 3 zor ders bulunmaktadır (…). Yük
    dengesi açısından birini sonraki döneme bırakmalı mıyım?"*
  * Kalma riski **zaten hesaplanmışsa**, hem mezuniyeti geciktiren hem de
    geçmişte kalma oranı ≥ %20 olan her ders için: *"… dersinden kalmam
    mezuniyetimi geciktirebilir; geçmişte bu dersi geçemeyen öğrenci oranı
    %30. Bu derse nasıl hazırlanmam önerilir?"*
  * Özet kendi başına hesap tetiklemiyor.

## Türkçe ek düzeltmesi

İlk sürüm *"öğrencilerin %30'i"* yazıyordu; doğrusu *"%30'u"*. Ek sayıya göre
değiştiği için hem bu soru hem Faz 88'deki öncelik satırı ek gerektirmeyen
bir kalıba geçti: *"geçemeyen öğrenci oranı %30"*, *"%20 veya üzerindedir"*.

## Testler

`tests/test_faz89_zor_dagit_ve_danisman.py` şunları kapsıyor:
* sınırsızda hepsi aynı dönemde;
* sınır 1 ve 2;
* kolay ve verisiz ders sayılmıyor;
* "zor" (4) ile "çok zor" (5) aynı sayılıyor;
* ÇAP tabanı geçişi;
* ufuk gerekçesi;
* uç doğrulaması (9, "x", −1 reddediliyor; 0 sınır yok);
* vitrinde seçim, şerit ve danışman özetinin iki hâli (zor ders yok / üç zor
  ders + kalma riski).

Geri alma deneyleri önbelleksiz (`-B`) koşuldu; sonunda 11 kuralın hepsi
kırmızı. İlk koşuda üç deney yeşil kalmıştı ve üçü de gerçek test boşluğuydu:

| Mutasyon | Neden yakalanmadı | Eklenen test |
|---|---|---|
| Sınırın bütün dersleri sayması | Kolay ders zor derslerden sonra geliyordu | Öncelikte önde olan kolay ders |
| Kademe ≥ 5 | Testte "zor" (4) kademesinde ders yoktu | "Zor" kademesinde ders |
| ÇAP geçişinde sınırın atlanması | Testte ÇAP tabanı yoktu | ÇAP tabanlı durum |
