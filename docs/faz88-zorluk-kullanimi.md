# Faz 88 — tahmini zorluk, kararın verildiği yerlerde

Kullanıcı 24.09.2026: *"geliştirmelere devam et ve sonrasında pr oluştur"*.

Faz 85–87'de tahmini zorluk yalnız dersin satırında ve penceresinde
görünüyordu. Öğrencinin asıl karar verdiği iki yerde yoktu:
* programlar **arasında** seçim yaparken;
* "bu dersten kalırsam" diye bakarken.

Not dağılımı kutusundaki bir cümle de Faz 87'nin hesabıyla çelişiyordu.

## 1. Karşılaştırma ve özet: programın zorluğu

`programZorlugu(adaylar)`: derslerin genel puanlarının (10 üzerinden, Faz 87)
**kredi ağırlıklı** ortalaması. 4 kredilik çok zor ders, 1 kredilik
laboratuvardan fazla yük getirir.

* Verisi olmayan ders ortalamaya **girmiyor**; sayısı ayrıca yazılıyor.
* **Karşılaştırma** (Faz 78): "Tahmini zorluk" satırı eklendi: *"5.4 / 10 · 2
  zor ders"*. En düşük sütuna **en hafif** etiketi konuyor, ama üç koşul var:
  * fark ≥ 0.5 olmalı;
  * **her sütunda derslerin en az yarısının verisi olmalı**. Vitrinde 8 dersin
    5'inin verisi yok; 3 dersten çıkan ortalamayla "en hafif" demek,
    bilinmeyeni bilinen gibi göstermek olurdu.
* **Program özeti** aynı sayıyı yazıyor: *"tahmini zorluk 5.4/10: 2 zor · 4
  orta · 2 çok kolay"*.

Gerçek katalogdaki sonuç (JEO, 1. dönem):

| Öneri | Tahmini zorluk | Zor ders | Etiket |
|---|---|---|---|
| Öneri 1 | 5.4 | 2 | en hafif |
| Öneri 2 | 6.0 | 2 | — |
| Öneri 3 | 5.4 | 2 | en hafif |

## 2. Kalma riski: kalma ihtimali

Faz 75 "kalırsam mezuniyet ne kadar gecikir" sorusunu cevaplıyordu. Şimdi
her satırın yanında **geçmişte kalma oranı** da var: FF + VF, olağan
dönemler, Faz 87'deki geçme oranının tümleyeni.

* Aynı gecikmede kalma oranı yüksek ders önde.
* Oranı bilinmeyen ders için *"geçmiş kalma oranı bilinmemektedir"*
  yazılıyor; oran uydurulmuyor.
* **Öncelik satırı** yalnız iki koşul birlikte tutarsa çıkıyor: ders bitişi
  geciktiriyor **ve** geçmişte en az %20'si geçememiş.
* Oranın OBS dağılımından geldiği ve kişisel bir tahmin olmadığı yazıyor.

## 3. Not senaryosu: geçmişteki ortanca notla doldur

"Tümüne uygula" listesine **geçmişteki ortanca not** seçeneği eklendi.

* Derecelenebilen her derse, olağan dönemlerdeki **ortanca harf notu**
  yazılıyor (VF hariç). Çift sayıda notta ortadaki iki nottan düşüğü
  seçiliyor (temkinli).
* Verisi olmayan dersin mevcut seçimine **dokunulmuyor** ve sayısı
  söyleniyor: *"3 derse … yazılmıştır; 5 ders için … notu elle seçiniz"*.
* Her satırda küçük bir ipucu var: *"ortanca CB"*.
* Tek bir not elle değiştirilince toplu uygulamanın bildirimi kalkıyor.

Öğrencinin "tipik bir sonuçla GNO'm ne olur" sorusuna başlangıç noktası.
Kişisel tahmin olmadığı yazıyor.

## 4. VF metni

Not dağılımı kutusu şöyle diyordu: *"VF devamsızlığı gösterir, dersin
zorluğunu göstermez"*. Faz 87'de kullanıcı VF'nin vize barajı nedeniyle final
hakkını kaybedenleri de gösterdiğini söyledi ve VF geçemeyenlere sayılmaya
başladı. Kutu, ipucu ve `notlar.py` yorumları artık şunu söylüyor: *"VF,
final sınavına girme koşulunu sağlayamayan öğrencileri gösterir (devamsızlık
ya da vize/ödev barajı); tahmini zorlukta geçemeyenlere sayılır."*

## Testler

`tests/test_faz88_zorluk_kullanimi.py`:
* ortanca: tek/çift sayı, VF hariç, artılı notlar;
* VF metni;
* vitrinde uçtan uca:
  * kredi ağırlığı, verisiz dersin dışarıda kalması;
  * özet;
  * karşılaştırma, "en hafif" etiketinin veri yeterliliği koşulu;
  * kalma riski sıralaması, öncelik eşiği, bilinmeyen oran;
  * ortancayla doldurmanın verisiz derse dokunmaması;
  * tek seçimin bildirimi kaldırması.

Geri alma deneyleri bayt kodu önbelleği olmadan (`-B`, `__pycache__`
silinerek) koşuldu; 11 kuralın her biri geri alınınca test kırmızıya
dönüyor. Bir mutasyon (ortanca döngüsünü `GRADES` üzerinden yapmak) anlamca
eşdeğer çıktı; yerine VF'yi paydaya katan mutasyon denendi ve kırmızı.
