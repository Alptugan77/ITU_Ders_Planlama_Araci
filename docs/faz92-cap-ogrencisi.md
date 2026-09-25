# Faz 92 — ÇAP öğrencisi gözüyle: doğru plan, öbür dildeki ders

Kullanıcı 25.09.2026: *"continue"*.

Bu faz, gerçek katalogda transkriptli bir **ÇAP öğrencisi** olarak yürüyerek
yapıldı (BLGE, 5. yarıyıl; ÇAP seçenekleri, sonra ÇAP = EHB, MAT, END…).
Faz 79 (mezuniyete yakın) ve Faz 72 (yandal) yürüyüşleri ÇAP'a özgü yolları
denememişti. Bulunan sorunların hepsi **ekranda doğru görünen yanlış
cevaptı**.

## 1. Başvuru penceresi, seçilince kullanılacak planı göstermiyordu

"ÇAP planları" penceresi her program için bir plan seçip derslerini sayıyor.
Program seçilince kullanılan plan ise `plans.ikinci_plan` ile belirleniyor.
İkisi farklı kurallarla çalışıyordu:

| | Pencere (`basvuru.survey`) | Seçim (`plans.ikinci_plan`) |
|---|---|---|
| "Sana açık mı?" | planın koduna bakıyor (`host_program_code`): "TUMMUH" adında "Mühendislik" geçen herkese açık | OBS'nin "İlişkili Programlar" listesine bakıyor (`plan_host_program`) |
| İterasyon | kendi sıralaması (`best_plan`) | `_en_guncel` |

**Ölçüm (gerçek katalog, 127 anadal):** 1906 (anadal, hedef) çiftinin 1367'sinde
iki taraf aynı planı seçiyordu. 168 çiftte farklı plan seçiliyordu. 371 plan
pencerede hiç görünmüyordu. 534 plan ise o anadala açık olmadığı hâlde
gösteriliyordu.

Örnekler:

* **BLG öğrencisi, EHB.** Pencere "TUMMUH_EHB"yi gösteriyordu: 22 ders. OBS
  bu planın listesinde BLG'yi yazmıyor; BLG'nin planı "BLG_EHB", 16 ders.
  Pencere bir planın derslerini sayıyor, seçilince başka bir plan
  kullanılıyordu.
* **BLGE öğrencisi.** "BLG" ev sahipli 27 planın hiçbirini görmüyordu, çünkü
  kod BLGE ≠ BLG. Bu planlar arasında BLG_EHB, BLG_MAT ve BLG_ELK var.
  Öğrenci yalnız "Tüm Mühendislik" planlarını görüyordu.
* **AIN / BES (uluslararası ortak programlar).** Adında "Mühendisliği" geçtiği
  için 21 TUMMUH planı gösteriliyordu. OBS bu programları hiçbir planda
  yazmıyor.

**Düzeltme:**

* Pencere OBS listesine bakıyor (`plans.ev_sahibi_suzgeci`). Seçim de aynı
  işlevi kullanıyor.
* Listesi çekilmemiş planda (eski veri) koddan tahmin sürüyor. Bu tahmin artık
  dil eşinin taban kodunu da tanıyor: "BLG" ev sahipli plan BLGE'ye de açık.
* İterasyonu iki taraf da aynı işlevle seçiyor (`plans.en_guncel_satir`).
* Sonra, 1906 çiftin **1905'i** aynı. Kalan biri MATE → MAT: kendi bölümü,
  bilerek eleniyor (§2).
* Statik sitenin budanmış kataloğunda 254 (anadal × tür) taramanın 254'ü
  yerel araçla aynı.

## 2. Kendi bölümün "ÇAP seçeneği" olarak çıkıyordu

BLGE öğrencisine "BLG" (Bilgisayar Mühendisliği) ÇAP seçeneği olarak
çıkıyordu. OBS de bazen böyle yazıyor: eski bir TUMMUH_MAT planı listesinde
MATE'yi sayıyor.

**Düzeltme:** kendi bölümünün öbür dildeki programı elenir. Eş, son harften
**tahmin edilmez**:

* iki kod da katalogda lisans programı olmalı;
* adları "(İngilizce)" dışında aynı olmalı.

Ölçüm: katalogdaki 37 X/XE çiftinin 37'si aynı bölüm.

## 3. Adı katalogda olmayan ÇAP programı hiç listelenmiyordu

ECN, SEC, VBA ve YZV'nin ÇAP planı var ama `program` tablosunda satırı yok.
Pencere listeyi o tablodan kurduğu için BLG öğrencisi **YZV'yi hiç
görmüyordu**. Ayarlardaki ÇAP listesi ise YZV'yi gösteriyordu.

**Düzeltme:**

* Planı olan program listede kalıyor.
* Ad uydurulmuyor: arayüz "(adı katalogda yok)" yazıyor.

## 4. Eşitlik ve "Öncesi" iterasyonu

* **Eşitlik.** Aynı iterasyonlu iki plan arasındaki eşitliği sorgunun satır
  sırası bozuyordu; o sıra da SQLite'ın seçtiği indekse bağlıydı. Örnek:
  ISL → ELE için ISL_ELE ile TUMMUH_ELE; ikisi de iterasyonsuz ve ikisi de
  ISL'ye açık. Artık eşitlikte anadalın **kendi** planı, sonra küçük id
  seçiliyor.
* **"Öncesi".** "2023-2024 / Güz Dönemi Öncesi" ile "2023-2024 … ile
  2026-2027 … Arası" aynı anahtarı alıyordu: (2023, 0). "Öncesi", o yıldan
  **önce** başlayanların planı; artık (Y-1) sayılıyor.
* **Yazım hatası.** OBS'de bir başlık "Sonraı" diye yazılmış; o da açık uçlu
  sayılıyor.

Program seçildiğinde kullanılan plan **20 gerçek çiftte** değişti (16 ÇAP,
4 yandal):

* 19'unda yürürlükten kalkmış "Öncesi" planı yerine aynı yıl başlayan "Arası"
  planı seçiliyor (ör. ELE → GEO: 2018 öncesi → 2018–2023).
* Biri eşitlik kuralı: UCK → ELE için TUMMUH_ELE yerine UCK_ELE.

Anadal lisans planlarının hiçbiri değişmedi.

## 5. Aynı dersin öbür dildeki kodu

İTÜ'de "EHB 222" ile "EHB 222E" aynı dersin Türkçe ve İngilizce şubesi. Ölçüm:
katalogdaki 2809 çiftin 2807'sinde kredi ve AKTS birebir aynı. Araç bu eşi
yalnız iki kod **aynı planda** yazılıysa tanıyordu (`alt_course_codes`).
OBS'nin ÇAP planları ise çoğunlukla Türkçe kod yazıyor.

**BLGE + ÇAP EHB ("BLG_EHB"), EHB 222E geçilmiş (CC):**

| | Önce | Sonra |
|---|---|---|
| ÇAP paneli | 0 / 16 | 1 / 16 |
| Engel listesi | "EHB 222 — bu dönem şube açılmamıştır" | yok (ders geçilmiş) |
| ÇAP'ın kendi ortalaması | bilinmiyor | 2.00 |
| Başvuru penceresi "sayılan ders" | 0 | 1 (EHB 222E) |

Karşılaştırma için: BLG öğrencisinin geçtiği EHB 222 iki planı da zaten
dolduruyordu. Aynı ders, dile göre farklı sonuç veriyordu.

**Bu dönem açık olan eş.** EEF 262'nin (ÇAP) o dönem yalnız İngilizce şubesi
açık: EEF 262E, EHB_LS'ye açık, yani EHB ÇAP öğrencisi alabilir. Araç "bu
dönem şube açılmamıştır" diyor ve dersi önermiyordu. BLGE öğrencisinin 13 ÇAP
seçeneğinden 7'sinde aynı durum vardı:

* MAT 175E, MAT 303E
* END 232E, END 312E, MEK 205E
* KON 303E, KON 325E, EEF 205E, EEF 281E
* FIZ 284E
* AKM 219E

Bu derslerin engelleri de artık gerçek sebebi söylüyor: önşart, programa
kapalı ya da kredi eşiği.

**Aynı ders iki kez.** Dersi henüz almamış öğrencinin yol haritası dersi iki
kez planlıyordu: anadalın EHB 222E'si 2026 Güz'e, ÇAP'ın EHB 222'si 2027
Güz'e.

**Düzeltme:**

* **Kural** — `rules.dil_esi`. Eş, katalogda **gerçekten var olmalı**. İki
  kredi de biliniyorsa ve farklıysa eş sayılmaz; bu, `obs_plan` birleştirme
  kuralıyla aynı.
* **Yalnız bir yön** (`rules.ingilizce_esi`). İngilizce şubede alınan ders
  Türkçe kodlu slotu doldurur; araç bunu zaten kabul ediyordu (obs_plan'ın
  TR/E birleştirmesi, öneri motorunun "iki dilin şubesi" notu). Tersi
  otomatik değil: Faz 10'un HTA/HTAE ilkesine göre Türkçe ders İngilizce
  dersin yerine geçmeyebilir. Orada `discover` "dil eki farklı" diye düşük
  güvenli öneri yapıyor, karar kullanıcının. İlk sürüm iki yönlüydü ve
  `test_discover`deki bu ilkeyi bozdu; tam test takımı yakaladı. İngilizce
  kodlu ÇAP slotu için Türkçe şube de önerilmiyor.
* **Yalnız ÇAP/yandal planında** (`rules.dil_serbest`). ÇAP planı bölüme
  tanımlı, dile değil: OBS aynı "BLG_EHB" planını BLG'ye de BLGE'ye de
  veriyor. Anadal planına dokunulmadı. İngilizce programın zorunlu dersini
  Türkçe şubenin karşılayıp karşılamadığı programın kendi kuralı; araç
  bilemez. "Tamamlandı" demek, öğrenciye saymayan bir dersi atlatabilirdi.
  Anadalda yalnız planın kendi yazdığı eşler (`alt_course_codes`) sayılıyor.
* **Slotun dolması** (`slot_satisfied`, kademe, ÇAP ortalaması, başvuru
  penceresi): geçilen eş ÇAP slotunu doldurur.
* **Hangi şube önerilir** — ÇAP/yandal slotunda eşin şubesi de aday.
* **Engel** — ÇAP/yandal engeli eşin şubesine de bakıyor ve planın koduyla
  yazılıyor.
* **Aynı programda iki dil yok.** Arama, bir dersin iki dilini aynı programa
  koymuyor. Anadal X, ÇAP XE yazdığında bu eskiden de mümkündü.
* **Yol haritası** — iki plandaki eş tek birim sayılıyor: rolleri anadal +
  ÇAP, bir kez planlanıyor. Birleşme ÇAP tarafındaki eşle yapılıyor.

## Doğrulama

* **Geri alma deneyleri:** 27 kuralın her biri tek tek bozuldu ve her birinde
  en az bir test kırmızıya döndü.
  * `tests/test_faz92_cap_secenekleri.py` — 11 deney
  * `tests/test_faz92_dil_esi.py` — 16 deney (yön ve anadalın eşsiz kalması
    dahil)
  * İlk turda iki deney yeşil kalmıştı: "OBS listesini yok say" ve "eski
    seçiciye dön". Fikstür güçlendirildi.
* **Faz 91 eşdeğerlik ölçümü** (9 profil, bütün öneriler ve CRN'ler): main ile
  birebir aynı. Değişiklik yalnız dil eşi olan durumlara dokunuyor.
* **Hız:** 9 profilin toplamı main'in ölçüm aralığında (6,76–7,02 sn; main
  6,75–7,07).
  * Dil eşi istek önbelleğinde tutuluyor.
  * Başvuru taraması eşi planın ~1000 kodu için değil, geçilmiş ~25 ders
    için soruyor. İlk sürüm bunu yapmıyordu ve %11 yavaştı.
* **Statik site** (Pyodide, gerçek katalog, BLGE + ÇAP):
  * pencerede BLG_EHB 16 ders, "sayılan: EHB 222E";
  * YZV, SEC ve ECN "(adı katalogda yok)" etiketiyle ve tahmini bitişleriyle;
  * ÇAP paneli 1/16;
  * ÇAP = END'de öneri END 232E, END 312E ve MEK 205E'yi içeriyor;
  * sayfa hatası 0.
