# İlk kez kullanan öğrenci gözüyle inceleme

> Kullanıcı, 24.08.2026: *"bu ders seçim aracına ilk kez kullanan bir öğrenci
> gözüyle bak ve eklenmesini veya değiştirilmesini istediğin şeyleri listele"*

**Nasıl baktım.** Depoyu sıfırdan kurdum: `make setup`'ın yaptığı gibi
`settings.example.toml` → `settings.toml`, `denklikler.example.toml` →
`denklikler.toml`, `user.sqlite3` **yok**. Katalog gerçek (`reference.sqlite3`,
3417 açık şube, 10792 ders). Sonra sayfayı bir tarayıcıda (Chromium) açıp
öğrencinin yapacağı sırayla ilerledim: bölümü seç → transkripti yapıştır →
dönemi seç → programa bak. Her adımda ekranın **ne dediğini** ve motorun **ne
yaptığını** ayrı ayrı kaydettim; ikisinin ayrıştığı yerler aşağıdaki listenin
omurgası.

Aşağıdakilerin hiçbiri `fikirler.md` ya da `yapilacaklar.md`'de yok. Oradaki
liste motorun **yapamadıklarını** sayıyor; bu liste motorun yapabildiği ama
ilk kullanıcıya **ulaşmayan** şeylerle ilgili.

---

## A — İlk beş dakikada araç kırılıyor

Bu beşi kapanmadan geri kalanın hiçbiri görünmüyor. Hepsi sessiz: hata
vermiyorlar, yanlış cevap veriyorlar.

### A1 ★★ Transkripti "olduğu gibi" yapıştırmak bütün notları çöpe atıyor

Karşılama kartının vaadi: *"En kolayı: transkriptini olduğu gibi yapıştır."*
Gerçek bir OBS not dökümü sütunlu:

```
MAT 103E    Mathematics I                   4.0    6.0   BB
FIZ 101E    Physics I                       3.0    4.5   CB
KIM 101E    General Chemistry I             3.0    4.5   DC
```

Ayrıştırıcı **notu koddan sonraki ilk sözcükten** okuyor. O sözcük not değil,
İngilizce ders adının ilk iki harfi:

```
Entry(MAT 103E, grade=None, IN_PROGRESS, note='bilinmeyen not: MA')
Entry(FIZ 101E, grade=None, IN_PROGRESS, note='bilinmeyen not: PH')
Entry(KIM 101E, grade=None, IN_PROGRESS, note='bilinmeyen not: GE')
```

Veritabanına yazılan: `manual-inprogress`, not `NULL`. Yani **BB, CB, DC
gitti**; dört ders de "devam ediyor" oldu.

Zinciri sonuna kadar takip ettim, öğrenciye maliyeti şu:

* GNO hesaplanamıyor → kredi tavanı en alt kademede kilitli kalıyor
  (transkript girmemiş gibi: 22 kredi),
* geçilen dersler "alınıyor" sayıldığı için **ilerleme %0'da kalıyor**,
  önşartlar açılmıyor, motor zaten geçilmiş dersleri yeniden öneriyor,
* ekranda iki cümle aynı anda duruyor ve birbirini yalanlıyor:
  üst çubukta **"4 ders girilmiş"**, hemen altındaki panelde
  **"İlerleme bilinmiyor — geçtiğin dersleri girmedin"**.

Hiçbir uyarı yok. Pencere kapanıyor, işlem başarılıymış gibi görünüyor.

**Ne yapmalı**

1. Notu satırın **sonundan** al: son geçerli not simgesini ara, ilk sözcüğü
   değil. Sütunlu satırda not her zaman sonda.
2. Uygulamadan **önce özet göster**: *"10 ders bulundu · 8 satır atlandı ·
   2 dersin notu okunamadı"* + atlanan satırların listesi. `parse_text`
   uyarıları zaten döndürüyor (`WARN` listesi dolu geliyor), arayüz onları
   hiç kullanmıyor.
3. Bir satırda **not vardı ama okunamadıysa** sessizce "devam ediyor"a
   düşme — projenin kendi kuralı bu: bilinmeyen, bilinen gibi gösterilmez.
   Burada tersi oluyor, bilinen (BB) bilinmeyene çevriliyor.

### A2 ★★ ÇAP seçiliyor, kaydediliyor, sonra yok oluyor

Pencereden: anadal **HTAE**, ikinci program **ÇAP**, ÇAP bölümü **BLG**, plan
"otomatik" → Kaydet. `settings.toml` doğru yazılıyor:

```toml
second_kind = "cap"
cap_program = "BLG"
cap_plan_id = 0
```

Sayfa yenilendikten sonra üst çubuk: **"HTAE anadal · ikinci program yok"**.
ÇAP paneli yok, ÇAP dersi yok, kritik yol yok. Hata mesajı da yok.

Sebep `cap_plan_id = 0`. Kod "seçilmedi"yi `None` ile anlıyor; örnek ayar
dosyası `0` gönderiyor. `resolve_seconds` `planId: 0` döndürüyor — var olmayan
bir plan — ve program bütün ekrandan düşüyor. `plans.py`'deki yorum bu durumu
öngörmüş bile:

> *"Planı bulunamayan tür listede KALIYOR (`plan_id=None`). Sessizce atmak …
> arayüz farkı söyleyebilmeli."*

Ama `0 != None` olduğu için o yol hiç çalışmıyor.

**Ne yapmalı:** `plan_id_of` dönüşünde `0`'ı `None`'a çevir; plan
çözülemiyorsa programı gizleme, **"ÇAP planı bulunamadı — plandan birini
seç"** de. Aracın var oluş sebebi sessizce kaybolmamalı.

### A3 ★★ "Otomatik (en güncel) plan" en güncel değil

`plans.anadal_plan()` ve `resolve_seconds` şunu yapıyor:

```sql
ORDER BY (source='obs') DESC, id DESC LIMIT 1
```

`id` bir sıra numarası değil; plan kimliği. BLGE'nin beş müfredatı var,
`id DESC` şunu seçiyor:

| seçilen | doğrusu |
|---|---|
| **2010-2011 / Güz ile 2011-2012 arası** (59 slot) | 2024-2025 / Güz Dönemi Sonrası (51 slot) |

2026'da kayıt yaptıran öğrenci, **15 yıllık bir müfredata** göre planlanıyor.
Panel bunu yazıyor ("… 2010-2011 / Güz ile 2011-2012 …") ama öğrenci o satırın
seçilebilir bir şey olduğunu bilmiyor — zaten seçemiyor da (bkz. A4).

ÇAP tarafında aynı hata daha ağır: HTAE + BLG için kutuda **38 plan** var,
çoğu başka anadalın (`SEC_BLG`, `ROS_BLG`, `KOM_BLG`, `ELK_BLG`, `MAT_BLG`…).
Otomatik seçim `2723 · SEC_BLG` olurdu. Doğru plan `2229 · TUMMUH_BLG` ve bu
**veriden bulunabiliyor**:

```sql
select p.id from plan p join plan_host_program h on h.plan_id = p.id
 where p.plan_type='cap' and p.program_code='BLG' and h.program_code like 'HTA%'
-- → 1190, 2229
```

`plan_host_program` Faz 19'da doldurulmuş (10532 satır) ama plan seçiminde
kullanılmıyor.

**Ne yapmalı:** plan başlığındaki yıl aralığını ayrıştır, "…Dönemi Sonrası" /
en yeni aralığı seç. ÇAP/yandal kutusunu `plan_host_program` ile anadal
koduna göre **süz** — 38 seçenek 2'ye iner. İki aday kalırsa otomatik seçme,
sor.

### A4 ★ Anadal planı arayüzden seçilemiyor; ayar dosyasındaki değer hiç okunmuyor

`settings.example.toml` `anadal_plan_id`'yi belgeliyor, `server.py` API'den
`anadalPlanId` kabul ediyor — ama `plans.anadal_plan()` bu değere **hiç
bakmıyor**. Ayarı elle yazdım, ilerleme paneli yine 2010 planını gösterdi.

Yani A3'teki yanlış seçime karşı öğrencinin yapabileceği hiçbir şey yok.
Program penceresinde ÇAP planı ve yandal planı kutusu var; **anadal planı
kutusu yok**. Girişte sorulacak en doğal soru da bu: *"kaçıncı yılın
müfredatındasın?"*

### A5 ★★ `program_codes` yer tutucuda kalınca araç sessizce boş dönüyor

`settings.example.toml`:

```toml
program_codes = ["XXX", "YYY"]
```

Pencereden bölümü seçtim (BLGE). Pencere `program_codes`'a **dokunmuyor** —
o alan "Gelişmiş" katlanır bölümünün altında. Sonuç: hiçbir şubenin
"Dersi Alabilen Programlar" listesinde XXX ya da YYY olmadığı için **her şey
eleniyor**:

```
öneri üretilemedi
aday ders yok — bölümünü ve geçtiğin dersleri girdiğinden emin ol
```

…boş bir haftalık ızgaranın üstünde, **"ARAÇ ÇALIŞIYOR"** başlığıyla. Komut
satırındaki karşılığı öğrenciyi büsbütün yanlış yere gönderiyor:

```
· ders programı henüz yayınlanmamış olabilir (make refresh)
· ya da tüm slotların dolu
```

Aynı ayarı `program_codes = []` yapınca her şey anında çalışıyor.

**Ne yapmalı:** örnek dosyada `[]` gönder; pencere kaydederken yer tutucu
kodları temizlesin; "0 aday" mesajı gerçek sebebi yazsın —
*"3417 şubenin hiçbiri şu program kodlarına açık değil: XXX, YYY"*.

---

## B — Ekran, doğru olmayan şeyler söylüyor

Faz 24 ve 26 bu sınıftan hataları tek tek temizlemiş; kalanlar aynı ailenin
üyeleri.

**B1 · Karşılama kartı boş programın üstünde "çalışıyor" diyor.**
*"Aşağıdaki haftalık program **şu an çalışıyor**"* cümlesi, ızgara boş ve
"öneri üretilemedi" yazarken de duruyor. Başlık, motorun **çıktısına**
bakmalı: öneri yoksa *"Bir şey ters gitti — sebebi şu"*.

**B2 · "Bölümünü seç ✓ TAMAM" — bölüm `XXX` iken.** Yer tutucu değer
"yapıldı" sayılıyor. `XXX`/`YYY`/`0` kurulumu tamamlamış saymamalı.

**B3 · Başlıkta ham kodlar.** `XXX · 202610`. `202610` öğrenci için bir şey
ifade etmiyor; **2026-2027 Güz** yazmalı. Kodun yanında bölüm adı da olmalı.

**B4 · Transkript yokken "GNO 0.00" iddiası — ve motor buna göre kısıtlıyor.**
Mevzuat paneli:

```
13–22 kredi · motor bunu kullanıyor — GNO'ndan hesaplandı: 22
· GNO 0.00 → en çok 22 kredi (genel sınır)
```

Hakkında hiçbir şey bilinmeyen öğrencinin GNO'su 0.00 değil, **yok**. Üstelik
bu sayı süs değil: öneri gerçekten 22 krediyle sınırlanıyor. İşin ilginci
**doğrusu aynı sayfada zaten var** — "Kayıt günü" penceresindeki kontrol
listesi:

```
—  Kredi tavanı   transkript girilmedi — tavan bilinmiyor
```

İki panel aynı soruya iki farklı cevap veriyor. Faz 26'da "%0 tamamlandı" için
verilen karar burada uygulanmamış.

**B5 · Hiç beyan etmediğim 4 denklik "uygulanmış" görünüyor.**
Bomboş bir kurulumda, BLGE öğrencisinin ekranında:

```
UYGULANMIŞ BEYAN 4
GEO 220E → MAT 210   ·   GEO 109E → MAT 281   …
```

Kaynağı buldum: `equivalence` tablosu **`reference.sqlite3`** içinde — yani
"herkese açık katalog" dosyasında. README'nin iddiası şu:

> *"Ders kataloğu (`data/reference.sqlite3`) herkese açık veri, ayrı dosyada."*
> *"kişisel veri tek bir dosyada toplanıyor"*

Doğru değil; kişisel denklik beyanları katalog dosyasında duruyor. Yayın
akışı bunu siliyor (`kisisel_denklik_silindi: 4`) — ama bu, temizliğin
yayın hattına bağımlı olduğu anlamına geliyor, mimariye değil. Beyanlar
`user.sqlite3`'e taşınmalı.

---

## C — Öğrencinin ekranda göremediği şeyler

**C1 · Izgarada ders adı yok.** Hücrelerde yalnız kod: `EHB 222E`,
`ING 103N`, `BLG 231E`. Birinci sınıf öğrencisi bu kodların hangi ders
olduğunu bilmiyor. Kod + kısa ad (dar hücrede en azından `title`) gerekiyor.

**C2 · Izgarada CRN yok.** Kayıt gününün asıl sayısı "Kayıt günü"
penceresinin arkasında. Hücrede küçük punto bir CRN, o pencereye gitmeden
işi bitirir.

**C3 · Ham veri sızıyor:** bina alanında `belirsiz`, ÇAP bölüm listesinde
`ECN — ECN`, `SEC — SEC`, `VBA — VBA`, `YZV — YZV` (adı çekilememiş kayıtlar).

**C4 · Üç öneri sekmesi de aynı görünüyor:** `ÖNERİ 1 · 20 KREDİ`,
`ÖNERİ 2 · 20 KREDİ`, `ÖNERİ 3 · 20 KREDİ`. Farkı görmek için "Karşılaştır"a
girmek gerekiyor — oysa fark zaten hesaplanmış. Sekme etiketi ayırt edici
olanı taşısın: *"Cuma boş"*, *"en erken 10:30"*, *"tek kampüs"*.

**C5 · Sekme adları jargon.** `EŞİKLER · DENKLİK · DEĞİŞİM · ADAYLAR`
öğrencinin sözlüğünde yok. Karşılıkları: *Kredi sınırım · Sayılan derslerim ·
Son değişiklikler · Alabileceğim dersler*.

**C6 · "Bu dersi neden alamıyorum" sorusunun cevabı yok.** Darboğaz bölümü
`blockers.length` boşsa gizleniyor **ve** yalnız ikinci program için
hesaplanıyor (`"İkinci programda neden alamıyorsun"`). Tek programlı öğrenci
bu cevabı hiç görmüyor. Aday listesinde olmayan bir dersi arayıp *"neden
burada yok"* diyebilmeli — motor sebebi zaten biliyor (önşart / kontenjan /
programa kapalı / kredi eşiği).

**C7 · Bölüm kutusu 127 satır, arama yok, koda göre sıralı.** Öğrenci
"Bilgisayar" diye arar; liste `AIN, ARC, BES, BIO…` diye gidiyor ve
Bilgisayar Mühendisliği dört ayrı yerde (`BLG`, `BLGE`, `CEN`, `CES`).
Yazarak süzülen bir kutu + fakülteye göre gruplama gerekiyor.

**C8 · Varsayılanlar tehlikeli.** Pencere şu değerlerle açılıyor:

| alan | varsayılan |
|---|---|
| Anadal | `AIN — İnşaat Mühendisliği (İngilizce) UOLP (Azerbaycan-AZMIU)` |
| İkinci program | **ÇAP** |
| ÇAP bölümü | `ARC — Mimarlık (İngilizce) (KKTC)` |

Hiçbir şeye dokunmadan "Kaydet" demek, tamamen yanlış ama **geçerli
görünen** bir kurulum üretiyor. İlk seçenek `— seç —` olmalı ve ikinci
program varsayılanı `Yok`.

---

## D — Güven kırıcılar

**D1 ★ Katalogda önşart yoksa "önşartı yok" sayılıyor.**
Ölçtüm: 10792 dersin **4630'unda** (%42.9) önşart metni var; açık şubesi olan
2021 dersin 858'inde (%42.5). Kalan %57 için motor "önşartı yok, alabilirsin"
diyor.

Somut sonucu, **3. dönem, hiç ders geçmemiş** bir BLGE öğrencisinin
ÖNERİ 1'inde:

* `BLG 492E — Graduation Project` (puan 47.5),
* `FIZ 102E — Physics II`, **`FIZ 101E` ile aynı dönemde**.

Aynı sayfadaki mevzuat paneli bitirme çalışması için *"en az 95 kredi
tamamlanmış olmalı · 0 / 95 kredi · 95 kredi eksik"* diyor. `policy` bunu
hesaplıyor, `recommend` kullanmıyor.

**Ne yapmalı:** (a) önşart metni olmayan derse *"önşart bilgisi yok"* rozeti —
bu, projenin kendi ilkesinin gereği; (b) kredi eşiği olan dersleri (bitirme
çalışması) eşik sağlanmadan önerme; (c) aynı dersin I/II ardışıklığı için
kodtan (`101 → 102`) **öneri** üret, iddia değil.

**D2 · Kolay yol saklı, zor yol önde.** Kart *"transkriptini olduğu gibi
yapıştır"* diyor; pencerede öne çıkan şey **tek tek ders yazmak**, toplu
yapıştırma katlanmış bir `<details>` içinde. İkisini yer değiştir.

**D3 · İlk kullanıcıya "Ne değişti" paneli gösterilmemeli.** İçeriği
`2026-08-24T07:06:16 → 2026-08-24T07:08:50` — iki dakika arayla iki damga; ve
web sürümünde "Veriyi tazele" zaten çalışamıyor. Transkript girilene ve en az
bir tazeleme geçene kadar gizle.

---

## E — Küçükler

* Başlık altındaki ilk cümle hâlâ sayıyla başlıyor:
  *"3417 açık şube · dönem yükü sınırı: transkript girilince"*. İlk giren
  için bağlamsız.
* Kurulumda 2–3 varsayılan tercih sorulabilir (*akşam dersi istemiyorum,
  bir gün boş olsun*). Şu an ilk öneri Cuma **18:00**'e ders koyabiliyor ve
  öğrenci tercih diye bir şey olduğunu bilmiyor. Motor bunu Faz 27'de
  destekliyor, girişte hiç sorulmuyor.
* `BLG 105E` girildiğinde kredi sütunu `–` ve ders adı boş kalıyor (2010
  planı + katalog eşleşmemesi). Ders bulunamadıysa bunu söylemek gerekiyor.

---

## Doğru çalışan, dokunulmaması gereken yerler

Dürüst olmak gerekirse ilk kullanıcı için çok iyi olan üç şey de var:

* **"Kayıt günü" CRN listesi.** Kopyalanabilir, kayıt öncesi kontrol
  listesi ve `—` = *"buradan bakılamaz"* işareti tam olarak doğru dil.
* **Telefon düzeni.** 390 px'te yatay taşma yok, ızgara gün gün listeye
  dönüşüyor, konsolda hata yok.
* **"Başvurabilir miyim"** ekranı, sağlanamayan üç şartı gizlemek yerine
  madde numarasıyla *"buradan değerlendirilemiyor"* diyor.

---

## Önerdiğim sıra

| # | İş | Neden önce | Zorluk |
|---|---|---|---|
| 1 | A5 `program_codes` yer tutucusu | Tek satır; araç bunsuz **boş** açılıyor | S |
| 2 | A1 transkript ayrıştırıcı + özet | Vaat edilen ana yol; notları kaybediyor | M |
| 3 | A2 `cap_plan_id = 0` | ÇAP sessizce yok oluyor | S |
| 4 | A3 + A4 plan seçimi (en güncel + `plan_host_program` süzgeci + anadal planı kutusu) | Yanlış müfredat, sessiz ve düzeltilemez | M |
| 5 | B4 + B2 transkriptsiz iddialar | Faz 26 kararının uygulanmamış kalan yarısı | S |
| 6 | D1 önşart bilinmiyorsa söyle | En görünür güven kırıcı (bitirme çalışması önerisi) | M |
| 7 | C7 + C8 bölüm kutusu (arama + boş varsayılan) | Kurulumun ilk on saniyesi | S |
| 8 | C1 + C2 ızgarada ad ve CRN | Her gün bakılan ekran | S |
| 9 | B5 denklik beyanlarını `user.sqlite3`'e taşı | README'nin iddiasıyla veri yerini uyumlu kıl | M |
| 10 | C5 sekme adları · C4 öneri etiketleri · D2/D3 | Cila | S |

⚠️ Bunların hiçbiri yayındaki siteye ulaşmıyor: `fikirler.md` §0'a göre depoda
`git remote` hâlâ tanımlı değil ve site Faz 23'ten kalma. Yani A1–A5
kapansa bile öğrenci hâlâ eski sürümü görecek.
