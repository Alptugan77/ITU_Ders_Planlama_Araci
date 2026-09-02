# Faz 38 — Ders not dağılımı ve bir yıl kayan dönem kodu

*02.09.2026 · kullanıcı: "daha da geliştirebilir misin, bir de derslerin not
dağılımı verisine ulaşabiliyor olabilirsin, bu İTÜ tarafından her dönem
yayınlanıyor — https://obs.itu.edu.tr/public/DersNotDagilimi"*

`docs/fikirler.md`'nin **"Yapmamayı önerdiklerim"** tablosunda şu satır
vardı:

> | "Bu dersin ortalaması AA" / geçme oranı | **Elimizde böyle bir veri yok** |

Gerekçe bir ilke değil, bir **eksiklik** beyanıydı. Kaynak gösterilince
gerekçe düştü. Bu fazın işi o boşluğu doldurmak — ve doldururken aynı
ilkeyi korumak: veriyi **göster**, karar **verme**.

Testler **987 → 1013** (1011 geçti, 2 atlandı).

---

## A. Uç keşfi

Konteynerin ve yerel VM'in ağı `obs.itu.edu.tr`'ye kapalı olduğu için keşif
tarayıcı üzerinden yapıldı (aynı yöntem: `docs/obs-endpoints.md` §1).

```
GET /public/DersNotDagilimi/NotDagilimiSearch?bransKodu=MAT&dersNo=103E&yil=2026
```

Token yok, cookie yok, `Referer` gerekmiyor. Cevap bir HTML **parçası**;
veri satır içi betikte `const ALL_DATA = […]` olarak duruyor ve **tek istek
o yılın bütün yarıyıllarını** getiriyor — güz, bahar ve **yaz**.

Ayrıntı ve ham sayılar: `docs/obs-endpoints.md` §5.

---

## B. Üç tuzak — üçü de ölçüldü, üçü de koda geçti

### B1. ★★ TR ve EN kodu BİRLEŞİK

`dersNo=212` ile `dersNo=212E` **bayt bayt aynı** cevabı veriyor (6824 B) ve
başlık `BLG212 - BLG212E` yazıyor. Yani dağılım bir ders **çiftine** ait.

"BLG 212E'nin geçme oranı" demek veriyi olduğundan dar göstermek olurdu.
Kanonik anahtar **kaynağın kendi başlığından** alınıyor, iki kod da takma ad
olarak saklanıyor, arayüz `BLG 212 + BLG 212E birlikte` diye yazıyor.

⚠️ "Sondaki E'yi at" sezgisi bu depoda başka yerlerde kullanılıyor; burada
kullanılmadı çünkü **kaynak çiftin ikisini de yazıyor**. Sezgi yerine kaynağı
okumak `BLG 4901E` gibi kodlarda da doğru kalıyor.

### B2. ★ "Bulunamadı" da HTTP 200

Olmayan ders `<h4>… could not be found.</h4>` ile **200** dönüyor. Durum
koduna bakan bir tarayıcı bunu "boş dağılım" diye kaydederdi — bu depoda
tekrar tekrar canımızı yakan **sessiz sıfır** (bkz. `birimId` hatası,
Faz 28). `parse` üç durumu ayırıyor:

* veri var → `CourseDistribution`
* "bulunamadı" mesajı var → `NotFound` (ve `status='yayinlanmamis'` kaydı)
* ne veri ne mesaj → `ValueError` *"sayfa yapısı değişmiş olabilir"*

### B3. ★★ `yil` BİTİŞ yılı — ve `donem_adi` bir yıl kaymış

```
yil=2026 → 202630 | 2025-2026 | Summer Semester | n=991
           202620 | 2025-2026 | Spring Semester | n=1682
           202610 | 2025-2026 | Fall Semester   | n=2988
```

Üç ardışık yılda tutarlı. Mantık da doğruluyor: `202630` yazın notları Eylül
2026'da açıklanmış durumda; "2026-2027 yazı" olsaydı o yaz daha yaşanmamış
olurdu.

`config.donem_adi` ise `f"{yil}-{yil+1}"` üretiyordu: **`202610 → "2026-2027
Güz"`**. Kaynağa göre doğrusu **2025-2026 Güz**. Düzeltildi.

⚠️ Bunun bir sonucu var ve **sessizce düzeltmedik**: `settings.toml`'da
`term = "202610"` yazıyor, yani araç **geçmiş bir dönemi** planlıyor
görünüyor. Hangi dönemi planladığı kullanıcının beyanı; biz yalnız çelişkiyi
gösteriyoruz — başlıkta:

> ⚠ **2025-2026 Güz bitmiş görünüyor**

Bu uyarı **takvimden tahmin değil**: o dönem için OBS'nin dağılım yayınlamış
olduğu ders sayısına bakıyor (ölçüm: 140 ders). ⚠️ Sıfır dönmesi "dönem
gelecekte" demek değil — dağılım hiç çekilmemiş de olabilir; arayüz ikisini
`gradeCoverage` ile ayırıyor.

---

## C. Ne YAPMADIK — ve neden

| Yapılmadı | Gerekçe |
|---|---|
| **Dağılımı öneri puanına katmak** | Aracı "kolay ders bulucu"ya çevirirdi. Hangi dersin zorluğuna değdiği öğrencinin **değer yargısı**; motor onu yerine veremez. Ekranda bunu da yazıyoruz |
| **Hocaya bağlamak** | Kaynak dağılımı **ders** düzeyinde yayınlıyor; hoca kırılımı YOK. Şubenin hocasıyla dersin dağılımını yan yana koymak, veride olmayan bir nedensellik iddia etmek olurdu |
| **Aday satırına "%geçme" rozeti** | Karar anı ders penceresidir. Her satıra kolaylık rozeti basmak, listeyi sessizce "kolaydan zora" okutur |
| **Ortalamayı kendi kuralımızla hesaplamak** | `prereq.GRADE_POINTS` kullanılıyor: `FF` de `VF` de sıfır puan (İTÜ ortalamada ikisini de sayıyor). Başka bir kural, aynı sayfada iki farklı "ortalama" tanımı bırakırdı |

★ Ama `VF` **devamsızlıktır**: yüzdesi `FF`'ten **ayrı** yazılıyor, çünkü
düşük bir ortalamanın devam politikasından mı zorluktan mı geldiği
okunabilmeli.

---

## D. Kaynağın kendi toplamı tutmuyor

Ölçüm: `ToplamAciklananOgrenci` harflerin toplamına **her zaman eşit değil**.

| Ders / dönem | OBS toplamı | Harflerin toplamı | Fark |
|---|---|---|---|
| MAT 103 · 202610 | 2988 | 2987 | 1 |
| MAT 103 · 202620 | 1682 | 1678 | 4 |
| BLG 212 · 202610 | 243 | 235 | 8 |

Aradaki kişiler listelenen 15 harfin dışında (BL/BZ/muafiyet olabilir).
Birini öbürünün yerine yazmak veriyi **düzeltmek** olurdu; ikisi de taşınıyor
ve fark arayüzde tek cümleyle söyleniyor.

---

## E. Kapsam ve maliyet

`make notdagilimi` varsayılan olarak **planındaki** dersleri tarıyor
(kullanıcıda 251 ders → 176'sında veri, 75'inde yok; ~4-5 dakika).
`ARGS="--hepsi"` bütün katalogu tarar: ~5400 istek, ~1,5 saat — dönemde bir
kez yeter.

⚠️ Veri yayınlanan katalogu **büyütüyor**: 176 ders 10,9 MB → 11,4 MB yaptı
(gzip 2,9 → 3,0 MB). `make site` çıktısı artık kaç dersin dağılımını
taşıdığını yazıyor — sessiz büyüme bir gün "site neden 30 MB" sorusunu
cevapsız bırakırdı.

★ Yan kazanç: uç **yaz dönemini** de veriyor (`202630`). `fikirler §2.3`
(yaz okulu) için ilk kez hammadde var — "bu ders yazın açıldı mı, kaç kişi
aldı" artık veriyle cevaplanabilir. ⚠️ "Geçmiş yıl açıldı" ≠ "bu yaz açılacak".

---

## F. Ölçerken çıkan hata

Ders numarasının sonunda **birden fazla harf** olabiliyor: `ING 103CO`,
`ING 103SC`, `ING 103AC`, `ING 103DD`, `FIZ 101EL`. İlk kalıp tek harfe izin
veriyordu ve bu kodlarda `ValueError` fırlatıyordu — yani planın bir kısmı
**hiç sorulamıyordu**. Gerçek listeyle çalışırken çıktı; teste bağlandı.

---

## Doğrulama

```
pytest                    1011 geçti · 2 atlandı
make site                 katalog 11,4 MB → gzip 3,0 MB · not dağılımı 176 ders
gizlilik denetimi         kurulmuş site taranıyor — dağılım toplu veri,
                          kişisel veri taşımıyor
tarayıcıda (gerçek veri, 176 ders yüklü):
  başlık        "… · ⚠ 2025-2026 Güz bitmiş görünüyor"
  BLG 212E      "Not dağılımı — 235 kişi, geçen %83.8"
                ortalama 2.26 · FF %8.5 · VF %7.7 · 2025-2026 Fall Semester
                "BLG 212 + BLG 212E birlikte (OBS Türkçe ve İngilizce kodu
                 ayırmıyor) · elimizde 2 dönem var"
                "OBS toplamı 243; harflerin toplamı 235 — 8 kişi listelenen
                 15 harfin dışında"
  sayfa hatası  yok
```

Fixture'lar gerçek cevaptan alındı:
`tests/fixtures/not_dagilimi_MAT103E_2026.html` (3 yarıyıl) ve
`…_bulunamadi.html` (150 baytlık "bulunamadı" cevabı).
