# Faz 57 — Mezuniyet yol haritası, GNO hedefi, dış tıklama

*23.09.2026 · kullanıcı: "can you improve and add necessary features for a
program like this make it more usefull and usable and search for ways to
improve and new features that can be implemented. and also when a window
opens and to close mouse is clicked out of the window just close the window
do not interact with background"*

İki iş: (1) açık pencerenin dışına tıklamak **yalnız** kapatsın, (2) bu tür
bir araçta eksik olanı bul ve ekle. İkincisi tahminle değil, vitrin
öğrencisinin (Faz 56) ekranında **ölçülerek** seçildi; benzer araçların
(derece denetimi, ders programı kurucuları) sunduğu şeylerle karşılaştırma
§8'de.

Testler **1234 → 1255** (+21), 4 atlandı. Geri alma
deneyi: on iki düzeltmenin **on ikisi** geri konunca kendi sebebiyle
kırmızı (§9).

---

## 1. Dış tıklama yalnız kapatıyor

Faz 55'te dışarı tıklama pencereyi kapatıyor **ve** tıklamayı altındaki
öğeye iletiyordu (`elementFromPoint` + `dispatchEvent`): kapatmak için
tıklanan yer raydaki bir bağlantıysa görünüm değişiyor, ızgaradaki bir
dersse onun penceresi açılıyordu. Kullanıcı bunu istemedi: kapatmak için
tıklanan yer çoğu zaman rastgele.

Artık olay `preventDefault` + `stopPropagation` ile duruyor ve yalnız
`d.close()` çalışıyor. Faz 55'in üç güvencesi aynen duruyor: pencerede
başlayıp dışarıda biten sürükleme kapatmıyor, pencerenin kendi kenarı
kapatmıyor, kaydedilmemiş değişiklik varken ilk dış tıklama uyarıyor.

Uçtan uca test iki yönü birden tutuyor: pencere kapandı **ve** arkada
hiçbir şey olmadı (görünüm `schedSection`'da kaldı, ızgaradaki başka dersin
penceresi açılmadı).

## 2. ★★ Mezuniyet yol haritası (`src/itucap/yolharitasi.py`)

### Ölçülen eksik

Araç yalnız **bu dönemi** planlıyordu (`fikirler.md` §2.1, "L"). Kademeler
görünümü ÇAP'ın *en az* kaç dönem süreceğini söylüyordu ama bir plan
vermiyordu. Vitrin öğrencisinde bunun bedeli şuydu: açılıştaki öneri 1,
**GEO 341E**'yi (Güz dersi, arkasında GEO 401E → GEO 4902E zinciri) saat
çakışması yüzünden dışarıda bırakıyordu. Bu, anadalı **bir yıl**
geciktiriyordu (2026-2027 Bahar yerine 2027-2028 Bahar) ve ekranın hiçbir
yerinde yazmıyordu.

### Ne yapıyor

Kalan her plan slotunu (anadal + ÇAP/yandal, aynı ders iki planda tek
birim) dönem dönem yerleştiriyor:

| Kural | Neden |
|---|---|
| Bu dönem = kaydedilen program, yoksa açılıştaki öneri 1 | Hangisi kullanıldığı ekranda yazıyor |
| Mevsim = plandaki dönemin paritesi (tek → Güz, çift → Bahar); ÇAP/yandal dersinde ev sahibi programın lisans planı | Gelecek dönemlerin arzı bilinmiyor; bilinen en iyi kaynak plan |
| ★ Bu dönem şubesi olan ders **bu mevsimde de** açılır | Vitrinde MAT 210E: plan "Bahar" diyor, bu Güz iki şubesi var. Yalnız plana bakmak onu bir yıl ileri itiyordu |
| Anadal dersi plandaki döneminden önce konmuyor | Planın sırası; alttan kalan hemen gelecek döneme |
| Öncelik: en uzun zinciri başlatan önce, sonra plan sırası, zorunlu havuzdan önce | Kritik yol |
| ★ ÇAP yarıyıl tabanı **önce** doluyor, sonra herkes öncelik sırasıyla | Taban dolmazsa yönetmelik ihlali planın içinde kalırdı; hepsini ÇAP'a vermek de anadalın kritik yolunu geciktirirdi |
| Taban eksiği yalnız ÇAP **sürerken** yazıyor | Son ÇAP döneminde kalan kredi tabanın altındaysa fazlasını almak zaten imkânsız |
| Önşartı okunamayan ders engellenmiyor, **işaretleniyor** | Sonsuza kadar bekletmek de, sessizce yerleştirmek de yanlış olurdu |
| Önşartı hiçbir planda olmayan ders yerleşmiyor ve **sebebi** yazıyor | Bitiş o zaman "hesaplanamadı" |
| Boş dönem atılmıyor (yalnız sondakiler) | Bahar dersini bekleyen Güz dönemi takvimin parçası; atmak planı kısa gösterirdi |

Her program için tahmini bitiş, plandaki bitişle (anadal: planın son
dönemi − bulunduğun dönem) karşılaştırılıyor: "planındaki bitişten 2 dönem
geç" ya da "planındaki bitişle aynı ✓".

### ★ "Bu dönem şunu alırsan"

Haritanın asıl işe yarayan cevabı. Bu dönem aday havuzunda olup programda
**olmayan**, arkasından en az iki halkalık zincir gelen dersler (en çok 5)
için harita yeniden kuruluyor ve bitiş karşılaştırılıyor. Yalnız ölçülen
kazanç yazılıyor. Vitrinde: *"GEO 341E — bu dönem alırsan anadal 2 dönem
erken biter (2026-2027 Bahar) · yük sınırını aşıyor, bir dersi çıkarman
gerekir"* ve **Programda dene** düğmesi ders programına geçip dersin şube
penceresini açıyor.

⚠️ Saat çakışması burada çözülmüyor, söyleniyor: şube seçimi ve hangi
dersin çıkacağı ders programının işi.

### Varsayımlar planın ÜSTÜNDE

"Bu bir plan, kehanet değil." kutusu dönem kartlarından **önce** geliyor
(test sırayı tutuyor): her ders ilk denemede geçiliyor; her dönem bugünkü
kredi sınırı; mevsim kuralı; kontenjan/şube/çakışma yok; yaz okulu yok;
havuzun önşartı yok sayıldı; mevsimi hiçbir planda bulunamayan ders sayısı.
Bilinmeyeni bilinen gibi göstermemenin tek yolu onu söylemek.

(Faz 137: kutu hâlâ planın üstünde; özü ve ⚠ uyarılar açık, maddelerin
tamamı "Hesaplama varsayımları (N)" altında katlı.)

### Bedeli

Vitrinde bir sayfa kurulumu haritayı 2 kez kuruyor (asıl + bir aday):
**7 ms**. Statik sitede Pyodide'da da koşuyor; `tools/site_kur.py`'nin
motor listesine `yolharitasi` eklendi (test tutuyor).

## 3. ★ GNO hedefi — "eşikte kalmak için bu dönem kaç ortalama?"

Kredi sınırım görünümündeki eşik çipleri **bugünü** söylüyordu (✓/✗).
Asıl soru yarındı: ÇAP'a devam 2.50 isteyen öğrenci 2.78'deyken bu dönem 24
kredi alırsa ortalaması kaça kadar düşebilir?

    gereken = (hedef × (C' + T) − P') / T

C', P': ortalamaya giren kredi ve puan; **tekrar alınan dersin eski notu
çıkarılmış** (İTÜ'de son alınan not geçerli, Faz 9). T: programdaki kredi.
Seçim değişince canlı yeniden hesaplanıyor.

* **Puan yuvarlanmadan geliyor** (`Gpa.points`, yeni alan). `value ×
  credits`tan hesaplasaydık 2 haneli yuvarlama 100+ kredide gereken
  ortalamayı 0.05'e kadar kaydırırdı.
* Tekrar alınan dersler `_tekrar_notlari()`: yalnız bu dönem aday
  havuzunda olan ve GNO'ya giren notlar (`POL.gpa` ile aynı süzgeç — BL/BZ,
  muaf ve 0 kredili ders dışarıda). Vitrinde MAT 210E (FF) programa
  eklenince FF'nin sıfırı gidiyor ve gereken ortalama **düşüyor**.
* Zaten girilmiş programın **başvuru** eşiği hedef değil: ÇAP öğrencisine
  "ÇAP başvurusu için 3.71 gerekir" demek yanlış bir kaygı üretirdi.
* Kredi bandı da bir hedef: "3.00 — dönem sınırı 40 kredi olsun".
* Üç durum ayrı yazıyor: *her durumda ✓* (hepsi FF olsa bile üstünde),
  *≥ 1.61 — her dersten en az DC+ alırsan yeter*, *bu dönem yetmez — hepsi
  AA olsa bile GNO en çok X*.
* ÇAP'ın kendi ortalamasına bağlı eşikler burada yok ve bu yazıyor.

`fikirler.md` "GNO'n şu kadar olur" tahminini reddediyor — alacağın nottan
bağımsız bir sayı. Bu onun **tersi**: alacağın notun eşiği. Ekranda da
öyle yazıyor: *"Tahmin değil, gereken notun hesabı."*

## 4. Dolu şubeden boş şubeye tek dokunuş

Özet "dolu: GEO 331E" diyordu; sonra dersin penceresini açıp şubeleri tek
tek okumak gerekiyordu. Artık her dolu dersin yanında ya **boş şubeye geç
(CRN, boş yer)** düğmesi ya da *"uyan boş şube yok; kontenjanı izle"*.

Seçilen şube: başka şube, kontenjanı **ilan edilmiş** ve boş yeri olan
(bilinmeyen kontenjan "boş" sayılmıyor), programdaki derslerle ve meşgul
saatlerle çakışmayan; birden çoksa en çok boş yeri olan. Geçiş `choose()`
ile — "Geri al: GEO 331E şube değişikliği" ile geri alınıyor.

Vitrinde ölçülen: öneri 1 GEO 331E'yi dolu şubesine (70/70) koyuyor; öbür
şubesinde 15 yer var ama GEO 385E ile çakışıyor → "uyan boş şube yok".
GEO 385E çıkınca aynı satır tek dokunuşla geçiriyor.

## 5. Haftanın şekli özette

Karşılaştırma ekranı (Faz 27) önerilerin şeklini yan yana koyuyordu ama
**elle düzenlenen** programın şekli hiçbir yerde yazmıyordu. Özette artık:
*"4 gün kampüste · Pzt Sal Çar Per · 08:30–16:29 · en uzun ara 2 sa
(Per)"*. Kampüs günü yalnız yüz yüze buluşması olan gün; çevrimiçi şube
gün eklemiyor. ⚠️ İTÜ saatleri :29'da bitip :30'da başlıyor; ham fark "2 sa
1 dk" yazıyordu — 5 dakikaya yuvarlanıyor (test tutuyor).

## 6. Kampüs tercihi ne kadar veriyle çalışıyor (fikirler F.2)

F.2 iki kez ölçmüştü: buluşmaların **%42,5**'inde bina ilan edilmemiş, ve
"bunu tercih ekranında yazmak gerekebilir" diye bitiyordu. Kampüsü
bilinmeyen buluşma kampüs değişimi sayılmıyor — tercih o derslerde hiç
uygulanmıyor. Tercih penceresinde kutunun altına, öğrencinin **kendi**
adaylarında sayılarak yazılıyor: *"Adaylarının N yüz yüze ders saatinin K
tanesinde bina/kampüs ilan edilmemiş — bu tercih onlarda uygulanamıyor."*
Hepsi biliniyorsa hiçbir şey yazmıyor.

★ Yolda bir motor hatası: `Section.campuses()` çevrimiçi şubeyi zaten
dışlıyordu (24.08.2026), ama `Schedule.campus_changes()` buluşmaları
doğrudan sayıyordu — kayıtlı dersliği Maçka'da olan çevrimiçi ders,
Ayazağa'daki öğrenciye var olmayan bir yolculuk ekliyordu. Düzeltildi,
`test_recommend.py` tutuyor.

## 7. Vitrinin mevzuatı yoktu

Yol haritasını vitrinde denerken çıktı: `policy` mevzuat dosyalarını
`config.ROOT` altından okuyor ve vitrin kökü geçici klasöre çevirdiği için
vitrin öğrencisinin **hiç** mevzuatı yoktu — GNO eşiği, kredi basamakları,
ÇAP yarıyıl tabanı. Yayınlanan site bu iki dosyayı taşıyor; vitrin artık
da taşıyor (`kurallar.toml`, `katalog-duzeltmeleri.toml`).

Yan etkisi ölçüldü: GNO'dan gelen 25 kredilik sınır açılış önerisine bir
ders daha ekledi ve Faz 56'nın uçtan uca testi "tam bir 'son N' rozeti"
bekliyordu. Test artık rozetin **çizildiğini** ölçüyor (BLG 222E "son 2"
ve hepsi `son [123]`), sayısını değil.

## 8. Araştırma: benzer araçlarda olup bizde olmayanlar

Derece denetimi / planlama yazılımları (Degree Works, Stellic) ve ders
programı kurucuları (Coursicle, Schedule Builder) karşılaştırıldı.

**Bizde zaten olanlar:** kontenjan nöbeti (Coursicle'ın yer bildirimi),
meşgul saat bloklama, program karşılaştırma (Faz 27), yedek plan, paylaşım
bağlantısı (`#crn=`), `.ics` dışa aktarma, önşart ve kademe analizi.

**Bu fazda kapanan:** çok dönemli plan ve "bu dönem şunu alırsan" (derece
planlayıcılarının "what-if" + "graduation timeline" özelliği), GNO hedefi.

**Kalanlar** — `fikirler.md` "Faz 57 araştırması" bölümüne yazıldı, her
biri boyut ve ön koşuluyla.

## 9. Testler ve geri alma deneyi

`tests/test_faz57_yol_haritasi.py` (20 test) + `test_recommend.py` (+1) +
Faz 55/56 testlerinin güncellenen doğrulamaları.

Her düzeltme tek tek geri kondu; hepsi kendi sebebiyle kırmızı:

| Geri konan | Kırmızı |
|---|---|
| Bu dönem şubesi mevsimi genişletmiyor | `test_BU_DONEM_SUBESI_…` |
| ÇAP tabanı önce doldurulmuyor | `test_CAP_TABANI_anadalin_kritik_yoluna_RAGMEN_…` |
| Taban eksiği son ÇAP döneminde de | `test_CAP_TABANI_once_doluyor_…` |
| `row_factory` geri konmuyor | `test_BAGLANTININ_row_factory_si_KORUNUYOR` |
| Anadal dersi plandaki dönemden önce | `test_ANADAL_plandaki_donemden_ONCE_…` |
| Boş dönemler atılıyor | `test_ONSART_ZINCIRI_…` |
| Tekrar alınan dersin eski notu düşülmüyor | statik + uçtan uca (GNO2) |
| Başvuru eşiği hedef sayılıyor | statik + uçtan uca |
| Boş şube çakışmaya bakmıyor | uçtan uca (DOLU1) |
| Ara süresi yuvarlanmıyor | uçtan uca (SEKIL) |
| Kampüs notu yazılmıyor | uçtan uca (KAMPUS2) |
| Çevrimiçi şube kampüs değişimi sayılıyor | `test_CEVRIMICI_sube_…` |

⚠️ Kendi hatam, not düşülsün: ilk geri alma turunda `if taban:` yerine
`if False:` yazıp geri koydum — **aynı bayt boyu**, aynı saniye. Python'un
`.pyc` önbelleği kaynağın mtime'ı + boyuyla doğruluyor ve bozuk sürümü
çalıştırmaya devam etti; bir sonraki test turu sebepsiz kırmızıydı.
Deneyler artık `PYTHONDONTWRITEBYTECODE=1` ile ve önbellek silinerek
koşuyor.

Kontrast: yol haritasının dört yeni çifti (`warn`/`surface-2`,
`warn`/`seal-soft`, `ink-3`/`seal-soft`, `ok`=`anadal`/`surface`) ölçüm
listesine girdi — **78 çift**, hepsi tabanın üstünde. Tasarım denetimi
(`tasarim_envanteri.py --denetle`) temiz.

## 10. Ne yapılmadı

* Yol haritası **yaz okulunu** hesaba katmıyor (fikirler §2.3 hâlâ açık);
  not dağılımı verisi yaz dönemlerini taşıyor, hammadde var.
* Mevsimi hiçbir planda bulunamayan ders (vitrinde 6 ÇAP dersi) her dönem
  açılır sayılıyor. Not dağılımının geçmiş dönemleri bunu veriyle
  cevaplayabilir — fikirler'e yazıldı.
* "Programda dene" çıkarılacak dersi **önermiyor**; ders programı çakışanı
  düşürüyor, yük aşımını kullanıcı çözüyor.
