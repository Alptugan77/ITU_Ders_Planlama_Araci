# Faz 90 — motor kontenjanı gerçek haliyle okuyor

Kullanıcı 25.09.2026: *"please continue your work and improve this"*.

Faz 89'un açık kalan kalemi gerçek katalogla bir yürüyüştü. Profil:
transkriptli 5. yarıyıl BLGE öğrencisi. Planın ilk dört yarıyılı girildi:
FIZ 102E FF, MAT 104E DC, TM seçmelisi henüz alınmamış.

"Zor dersleri dağıt" senaryosu doğru çalıştı. Bu dönemde iki zor ders vardı;
gelecek dönemlerde en çok bir tane olduğu için sınır bitişi değiştirmedi.
Kalma riski yerelde 0,36 sn sürdü. Asıl bulgu motorun **kontenjanı yanlış
okuması** oldu.

## Bulgular

1. **"Kontenjan kritik" bonusu dersin EN DOLU şubesine bakıyordu**
   (`max(fill_ratio)`, ilk sürümden beri).
   * 70 boş yeri olan BLG 351E "kritik" sayılıyordu, çünkü şubelerinden biri
     doluydu.
   * Yedi profilde adayların %70–100'ü bu bonusu alıyordu (BLGE: 16 adayın
     15'i). Bonus artık hiçbir şeyi ayırt etmiyordu.
2. **Bütün şubeleri dolu ders de bonus alıyordu.** "TM Elective I" havuzu:

   | Ders | Boş yer | Puan |
   |---|---|---|
   | BLG 337E | 6 | 22.5 |
   | BLG 345E | **0** | 22.5 |
   | BLG 368E | 4 | 22.5 |
   | BLG 448E | **0** | 22.5 |
   | BLG 348E | 11 | **7.5** |

   * Eşitliği **alfabe** bozuyordu, bu yüzden 1. öneri dolu BLG 345E'yi
     içeriyordu.
   * En çok yeri olan ders bonus almadığı için en düşük puanı alıyordu.
3. **Şube seçimi doluluğa ancak son sırada bakıyordu.** Sıralama önce
   ileriye bakış maliyetine göre yapılıyordu. EHB 311E'nin boş ve çakışmayan
   şubesi, zaten programa giremeyecek bir dersle çakıştığı için "pahalı"
   görünüyordu; öneri dolu şubeyi veriyordu.
4. **Danışman özeti:**
   * "Şubemin kontenjanı doludur" sorusu dört kez tekrarlanıyordu. Biri boş
     şubesi olan dersti; o soru değil, tek dokunuşla çözülüyor (Faz 57).
   * İkinci programı olmayan öğrenciye "ÇAP başvurusu ≥ 3.00 — bu eşiğe nasıl
     ulaşabilirim?" diye soruluyordu. Öğrencinin istemediği bir hedef
     dayatılıyordu.

## Düzeltmeler

**Motor** (`recommend.py`):
* `kontenjan_durumu(şubeler)` dört değer döndürüyor: `dolu` · `kritik` ·
  `acik` · `bilinmiyor`.
  * **kritik:** bütün şubelerin kontenjanı biliniyor ve açık şubelerin EN
    BOŞU bile %85'ten dolu. Anlamı "gerçekten yer kalmıyor".
  * **dolu:** bütün şubelerin kontenjanı biliniyor ve hiçbirinde yer yok.
  * **bilinmiyor:** kontenjanı ilan edilmemiş şube var. Ne bonus veriliyor ne
    ceza; bilinmeyen, bilinen gibi gösterilmiyor.
* "Kontenjan kritik" (+15) yalnız `kritik` durumda veriliyor.
* `dolu` durumda **−5** ceza var; gerekçe metni: *"bütün şubeler dolu —
  kontenjan izlenmeli"*. Aynı havuzdaki açık ders öne geçiyor. Havuzun
  tamamı doluysa ders yine öneriliyor ve arayüz "dolu" diyor.
* **Şube seçiminde dolu şubenin maliyeti 15** (`DOLU_SUBE_MALIYETI`).
  Birimi ileriye bakış maliyetiyle aynı, yani puan.
  * Boş şube, dolu şubeden en fazla 15 puan daha çok değer yakıyorsa boş
    şube seçiliyor.
  * Dolu şube değerli bir dersi kurtarıyorsa (örneğin o dersin tek şubesiyle
    çakışma) dolu şube seçilmeye devam ediyor.

**Danışman özeti** (`ui.py`):
* Dolu şubeler **tek soruda** toplanıyor. Programla çakışmayan boş şubesi
  olan ders soruya girmiyor.
* Program tablosunda CRN'nin yanında *"dolu"* işareti var; boş şube varsa
  *"boş şube: CRN"* yazıyor.
* Başvuru eşiği bir **seçenek** olarak soruluyor: *"ÇAP başvurusunu
  düşünürsem GNO ≥ 3.00 gerekmektedir; tahmini GNO'm 2.53. Bu hedef benim
  için gerçekçi midir?"* Devam ve mezuniyet eşikleri eski biçimde kaldı.

## Ölçüm (gerçek katalog, 7 profil × 2 kip = 14 öneri)

| | Önce | Sonra |
|---|---|---|
| 1. önerideki dolu şube sayısı | 49 | 34 (−%31) |
| … programla çakışmayan boş şubesi olan | 3 | **0** |
| "kontenjan kritik" alan aday (BLGE 5, dönem kipi) | 15/16 | 3/16 |
| Kredi / ders sayısı | — | 14 önerinin hepsinde aynı kredi |

Kalan dolu şubelerin boş ve çakışmayan alternatifi yok. Örnekler: TUR 122'nin
bütün şubeleri dolu; ITB havuzunun altı dersi de dolu. Bunlar "dolu" ve
"kontenjanın izlenmesi önerilir" diye işaretleniyor.

BLGE 5. yarıyılda 1. önerideki değişiklik:
* EHB 311E artık açık şubede.
* Dolu BLG 345E yerine 11 boş yerli BLG 348E geldi.
* Özetteki "DOLU" satırı 4'ten 2'ye indi.

## Hız

Arama bütçeli (`SEARCH_BUDGET`). Yeni puanlar adayların sırasını
değiştirdiği için arama ağacı da değişiyor. Dolu şube maliyetinin kendi
etkisi ±%2.

Yerel ölçüm (arama süresi, 3 koşunun ortancası):

| Profil | Eski | Yeni | Değişim |
|---|---|---|---|
| KMM 3 | 3,89 sn | 3,95 sn | +%1 |
| KMM 1 | 4,06 sn | 3,99 sn | −%2 |
| JEO 1 | 4,27 sn | 3,82 sn | −%10 |
| INSE 1 | 3,69 sn | 4,60 sn | +%25 |
| Toplam | 15,91 sn | 16,36 sn | **+%2,8** |

Gerçek katalogla kurulan statik sitede (Pyodide, KMM 3) aynı makinede
ölçüldü:
* program değişikliği: 7,27 → 7,70 sn;
* dönem değişikliği: 6,20 → 6,60 sn;
* yaklaşık **+%6**.

## Değişen eski testler (amaçları korunarak)

* **`test_faz59` (tercih önizlemesi):** eski durum ("10:30'dan önce yok +
  Pzt boş") BLG 223E'yi DOLU 22302 şubesine taşıyordu. Bu, düzeltilen
  davranışın ta kendisiydi. Yeni durum "Perşembe boş": GEO 321E açık
  13640'tan açık 13602'ye geçiyor.
* **`test_faz61` (danışman):** soru biçimi tek soruya döndü.
* **`test_faz88` (karşılaştırma):** öneriler değiştiği için "farklı zorluk"
  artık bir derse elle veriliyor. Kapsama koşulu yine sınanıyor.

## Testler

`tests/test_faz90_kontenjan.py`:
* durum sınıflaması;
* bonus ve ceza, kırılım toplamı;
* havuzda açık ders dolu dersin önünde (kritik ve bol yerli iki durum);
* havuz tamamen doluysa yine öneriliyor;
* şube seçimi (üç durum: eşit, ileriye bakış yanıltıcı, dolu şube değerli
  dersi kurtarıyor);
* vitrinde danışman özeti.

Önbelleksiz (`-B`) geri alma deneylerinde 9 kuralın hepsi kırmızı. İlk
koşuda iki deney yeşil kalmıştı ve ikisi de gerçek test boşluğuydu:
* −5 ceza, yalnız "kritik" açık alternatifle sınanıyordu;
* şube maliyeti, zaten "daha boş" eşitlik bozmasıyla çözülen bir durumla
  sınanıyordu.

İkisine de test eklendi.
