# Faz 9 — GNO, değişim takibi ve bulunan hatalar

> ⚠️ Bu belgedeki bütün sayılar **örnektir**. Repoda kimsenin gerçek notu
> ya da ortalaması yer almaz — kişisel veri `data/` altında kalır ve
> `.gitignore` ile dışarıda tutulur.


```bash
make changes                 # son iki tazeleme arasında ne değişti
make changes ARGS="--all"    # yalnız kendi derslerin değil, hepsi
make app                     # sayfadan "Veriyi tazele" düğmesi
```

## ★ Bulunan hata: aldığın ders yeniden öneriliyordu

Faz 8'de transkripte "devam ediyor" işareti girilebiliyor. Motoru kontrol
ettim: `S.grades()` devam eden dersleri döndürmüyor, `R.passed()` de onları
geçilmiş saymıyor — **dolayısıyla motor onları hâlâ aday sayıyordu**.

```
GEO 401E devam ediyor ama aday mı?  True
```

Yani programında zaten olan bir dersi "bunu al" diye öneriyordu. Düzeltme iki
parçalı, çünkü iki ayrı şey:

* **Adaylardan çıkar** — `S.in_progress()` ile eleniyor
* **Kaybetme** — darboğaz raporunda yeni bir tür: `ALIYORSUN`, "bu dönem
  programında". Sessizce yok saymak, "bu ders neden önerilmedi" sorusuna
  yanlış cevap vermek olurdu.

## ★ GNO — hesaplanabiliyordu, hesaplanmıyordu

`settings.toml`'da Faz 1'den beri duran üç satır vardı:

```toml
min_gno_apply = 3.00
min_gno_continue = 2.50      # ⚠️ DOĞRULA
```

Kod bunlara bağlı değildi — çünkü GNO'yu bilmiyorduk. Ama transkript zaten
elimizde: notlar + krediler = ağırlıklı ortalama.

```
GNO 2.45  (31 ders, 74 kredi)   ← örnek
  ÇAP başvurusu ≥ 3.00  ✗ ⚠
  ÇAP'a devam    ≥ 2.50  ✓ ⚠
```

### Üç ölçüm kararı

**1. BL ve MU ortalamaya girmez.** `GRADE_POINTS` içinde BL=1.0, MU=4.0 —
ama bunlar *önşart* değerleri. Kredisiz/muaf dersleri 4.00 sayan bir hesap
GNO'yu şişirir ve "eşiği geçiyorsun" der. Test bunu kilitliyor.

**2. Kalınan ders sıfır olarak sayılır.** Yalnız geçilenlere bakmak GNO'yu
sistematik olarak yüksek gösterirdi. `S.graded()` FF'leri de döndürüyor.

**3. Tekrar edilen derste en yüksek not.** İTÜ'de son alınan not geçerli;
transkriptte dönem bilgisi her zaman olmadığı için en yüksek notu almak
pratikte aynı sonucu veriyor ve dönemsiz girişte de çalışıyor.

### Eşikler doğrulanmadıysa öyle görünür

`config/kurallar.toml`:

```toml
[[gno_esigi]]
anahtar    = "devam"
ad         = "ÇAP'a devam"
min_gno    = 2.50
dogrulandi = false          # ← arayüzde ⚠ ile işaretlenir
```

Bu projede tekrar tekrar karşımıza çıkan ilke: **doğrulanmamış sayıyı kesin
gibi gösterme.** Arayüz hem `⚠` koyuyor hem de "teyit edip `dogrulandi = true`
yap" diyor. Aynı şekilde GNO'nun kendisi de "tahmini" diye etiketli ve
kredisi/notu bilinmeyen dersler sayıyla birlikte raporlanıyor.

## ★ Değişim takibi — eksik olan hafızaydı

Faz 5'in bulgusu şuydu: 14 kalan ÇAP dersinden 10'u "bu dönem açılmamış".
Ama ders programı dönem başında **kademeli** yayınlanıyor; bunların bir kısmı
sonradan açılıyor. Kontenjanlar da kayıt haftasında saatler içinde doluyor.

Araç zaten her `refresh`'te 3400 şubeyi çekiyordu. Eksik olan tek şey
**geçen seferkini hatırlamaktı**.

Her tazeleme bir anlık görüntü bırakıyor; iki görüntünün farkı beş soruyu
cevaplıyor:

```
DEĞİŞİM RAPORU   2026-08-21T13:25  →  2026-08-21T14:00
  (yalnız seni ilgilendiren 191 ders)

★ AÇILDI (1)
  BLG 102E     1 şube — Intr to Sci&Eng Comp (C)

KONTENJAN DOLDU (1)
  GEO 401E     CRN 13607  60/60

ŞUBE KAPANDI (1)
  GEO 313E     CRN 13598
```

**Süzgeç şart.** 3400 şubelik ham dökümde kendi dersini bulmak imkânsız;
rapor varsayılan olarak iki planının açık slotlarındaki derslere daralıyor
(`--all` ile hepsi).

### Testin yakaladığı ikinci hata

İlk sürümde görüntüler yalnız `lesson_snapshot` tablosundan okunuyordu.
Şubesiz bir görüntü — dönem başı, OBS henüz yayınlamadı — o tabloya **hiç
satır yazmıyor**, dolayısıyla görünmez oluyordu. Sonuç: "boş görüntü" ile
"görüntü yok" ayırt edilemiyordu ve *hepsi kapandı* gibi önemli bir değişim
raporlanamıyordu.

Düzeltme: görüntünün kendisi ayrı bir tabloda (`snapshot_run`). İki test bunu
kilitliyor.

## Sayfadan tazeleme

`make app` içinde **Veriyi tazele** düğmesi. OBS'ye ulaşılamazsa **eski veri
korunuyor** ve bu açıkça yazılıyor — sessizce başarılı görünmek, kullanıcıyı
eski veriyle karar verirken bilgisiz bırakmak olurdu. İki kez tıklamaya karşı
`busy` bayrağı var.

## Yedekleme — tek geri döndürülemez veri

Transkript OBS'den yeniden çekilemiyor; kullanıcı tek tek yazdı. Arayüzdeki
"Kaydet" tam listeyi yazıyor (`replace=True`), yani bir yanlış tıklama her
şeyi silebilirdi.

Artık her silici yazmadan önce `data/yedek/transkript-<zaman>.txt` yazılıyor.
Yedek **aynı ayrıştırıcıdan** geçen bir metin dosyası, yani geri yüklenebilir:

```bash
make transcript FILE=data/yedek/transkript-20260821-120000.txt
```

Son 20 yedek tutuluyor. Klasör `.gitignore` kapsamında — kişisel veri.

## Dayanıklılık

* **Port dolu** — `make app` sıradaki portu deniyor ve söylüyor; traceback
  basıp çıkmak kullanıcıya çözemeyeceği bir hata göstermekti.
* **Sunucu kapalı** — sayfa "Failed to fetch" yerine
  "sunucuya ulaşılamadı — `make app` hâlâ çalışıyor mu?" diyor.
* **Çok büyük gövde** — okumadan reddetmek istemciye kırık bağlantı
  gösteriyordu; sert bir tavana kadar boşaltılıp sonra 400 dönülüyor.

## Test kapsamı

250 test (Faz 9'dan 28 yeni).

**Değişim** — ilk görüntüyle karşılaştırma yapılamaz · yeni açılan ders ·
var olan derse eklenen şube (ayrı olay) · dolan/açılan kontenjan · kapanan
şube · süzgeç · budama · biçimlendirme

**GNO** — krediyle ağırlıklı · kalınan ders sıfır sayılır · BL/MU dışarıda ·
0 kredili ders dışarıda ve raporlanıyor · tekrar edilen derste en yüksek not ·
devam eden dersin notu yok · boş transkriptte sıfıra bölme yok · eşikler
doğrulanma bayrağını taşıyor

**Devam eden ders** — önerilmiyor ama darboğazda `ALIYORSUN` diye görünüyor

**Yedek** — silici yazmadan önce yazılıyor · geri yüklenebilir · boş
transkriptte yedek yok · budanıyor
