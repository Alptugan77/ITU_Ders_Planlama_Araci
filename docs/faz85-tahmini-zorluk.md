# Faz 85 — derslerin tahmini zorluğu

> ⚠️ **Faz 86'da değişti:** kademe artık ağırlıklı olarak **geçme oranından**
> (%70), ikincil olarak ortalamadan (%30) hesaplanıyor. Aşağıdaki "yalnız
> ortalama" ölçüsü tarihçedir; güncel ölçü `docs/faz86-gecme-orani-once.md`.

Kullanıcı 24.09.2026: *"derslerin önceki dönemlerdeki not ortalaması ve
dağılımına göre tahmini zorluk derecelendirilmesi yapabilir misin ve bunu
kullanıcıya uygun bir şekilde sunar mısın"*.

## Ölçü — tek ve açıklanabilir

`notlar.zorluk(con, kod)`:

1. **Olağan dönemler.** Harf notu sayısı en kalabalık dönemin %25'inden az
   olan dönem havuza girmez: bu dönemler tekrar/bütünleme sınıflarıdır
   (BLG 335 bahar: n=3, hepsi DD/FF).
2. **VF hariç harf ortalaması.** Devamsızlık dersin zorluğu hakkında bilgi
   vermez (Faz 38). GNO ölçeğindeki `meanPoints` VF'yi 0 sayar; bu ölçü
   saymaz. İkisi ayrı sorulara cevap verir.
3. **Beşte birlik dilim.** Ortalama, katalogda derecelenebilen bütün
   derslerin ortalamalarıyla karşılaştırılır. En düşük %20 **çok zor**,
   sonraki dilimler sırayla zor / orta / kolay / çok kolay.
   * Katalogda ≥ 300 derecelenebilen ders varsa **canlı yüzdelik**
     kullanılır. Gerçek katalogda 1187 ders var; pencere *"ortalaması bundan
     düşük olanların payı %37"* gibi bir cümle yazar.
   * Daha azsa (vitrin, kısmi çekim) yüzdelik anlamsızdır. Bu durumda gerçek
     katalogdan ölçülen **sabit sınırlar** kullanılır: 2.28 / 2.59 / 2.94 /
     3.42 (2025-2026).
4. **Derecelenmeyenler — kademe uydurulmaz:**
   * BL/BZ ile notlanan ders: *"harf notu ortalaması yoktur"*.
   * Olağan dönemlerde 20'den az harf notu olan ders. Nedeni yazılır.
   * 20–59 harf notu olan ders derecelenir ama **"az veri"** diye
     işaretlenir.

FF oranı ayrıca yazılır ama kademeye girmez. Tek ölçüt ortalamadır,
böylece kademenin nereden geldiği tek cümleyle açıklanabilir.

### Gerçek katalogdan örnekler (2025-2026)

| Ders | Ortalama (VF'siz) | Kademe |
|---|---|---|
| FIZ 102E | 1.84 | çok zor (%5) |
| MAT 103 | 1.97 | çok zor (%9) |
| KIM 101 | 2.35 | zor (%24) |
| MAT 271E | 2.55 | zor (%37) |
| RES 107 | 2.87 | orta (%56) |
| KMM 111 | 3.04 | kolay (%66) |
| ING 100 | 3.65 | çok kolay (%90) |
| ATA 121 | — | BL/BZ, derecelenmez |

## Sunum

* **Aday listesi:** her satırda beş yükselen çubuk ve etiket (*zor*,
  *orta · az veri*). Renk yalnız destek: kademe etikette ve ekran okuyucu
  metninde de yazar.
* **Sıralama:** *"tahmini zorluk (kolaydan zora)"* seçeneği eklendi.
  Verisi olmayan dersler sonda yer alır.
* **Ders penceresi:** "Programa ekle" penceresinde de görünür, çünkü bu
  bilgi en çok ders eklerken işe yarar. Pencerede kademe (n / 5), kullanılan
  dönemler, öğrenci sayısı, ortalama, katalogdaki yeri ve FF oranı yazar.
  Bir de not bulunur: ortalama, hocanın not verme eğilimini ve sınıfın
  yapısını da yansıtır; tahmindir; öneri puanına dahil edilmez.
* **Program özeti:** *"tahmini zorluk: 4 çok zor · 2 zor · 1 orta · …"*.
  Üç ya da daha fazla zor ders varsa yanına şu eklenir: *"zor ders sayısı
  yüksek; yükün dengelenmesi değerlendirilebilir"*.
* **Yol haritası:** her dersin yanında ölçek, dönem kartında *"tahmini
  zorluk: N zor ders"* satırı. Zorluk yerleşimi **etkilemez**; zor dersleri
  aynı döneme yığan bir planı öğrenci kendisi görebilir.

## Öneri puanına girmiyor

Faz 38 kuralı aynen geçerli: dağılımı puanlamaya sokmak aracı "kolay ders
bulucu"ya çevirirdi. Test bunu kilitliyor: `recommend.py`'de zorluk yok.

## Yan bulgu: BL/BZ dersleri

Gerçek katalogda ATA 121, TUR 121 gibi dersler BL/BZ ile notlanır
(ATA 121 güz: BL 1579, BZ 336, VF 374). `summarise` BL'yi
`GRADE_POINTS`teki 1.0 ile sayıyordu. Faz 76'nın liste satırı bu dersler için
*"ortalama 0.84"* yazıyordu ve BZ "geçti" sayılıyordu. Artık:

* ortalama yalnız harf notlarından hesaplanıyor; yalnız BL/BZ/VF olan derste ortalama yok;
* BZ başarısızlık sayılıyor;
* grafikte BL/BZ sütunları var (yalnız varsa).

## Hız

Katalog ölçeği bir kez okunuyor: 39 bin satır, yerelde 0,08 sn. Önbellek
anahtarı veritabanı dosyası ve `MAX(rowid)`; yeni çekim satır ekleyince
tazeleniyor. Ders başına sonuç da önbellekte; kalma riski haritayı ders
başına yeniden kuruyor. Gerçek sitede (Pyodide) program ve dönem değişikliği
≈0,2 sn (%4) uzadı.

## Testler

`tests/test_faz85_zorluk.py`: BL/BZ özeti ve kovası, VF'siz ve tekrar
sınıfsız ortalama, sabit ve canlı kademe, uç (derecelenmeyen, az veri,
önbelleğin tazelenmesi), öneri puanına girmediği, vitrinde uçtan uca (rozet,
sıralama, özet, pencere, yol haritası). Geri alma deneyi: 10 kuralın her biri
geri alınınca ilgili test kırmızıya dönüyor.
