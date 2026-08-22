# Faz 5 — Öneri motoru ve çakışma çözücü

> ⚠️ Bu belgedeki bütün sayılar **örnektir**. Depoda kimsenin gerçek notu
> ya da ortalaması yer almaz — kişisel veri `data/` altında kalır ve
> `.gitignore` ile dışarıda tutulur.


```bash
make recommend
make recommend ARGS="--ects 24 --only cap --pin 'BLG 212E' --count 5"
```

## Puanlama — yol haritasından sapma

Yol haritası şunu öneriyordu:

```
score = 100 × dual_count + 40 × zorunlu + 30 × unlock + 25 × dönem_yakınlığı + …
```

İki terim bu proje için geçersiz:

* **`dual_count`** — D5'te ölçtük, bu çiftte çift sayım **sıfır**. Sabit sıfır
  bir terim sıralamayı hiç değiştirmez, sadece kodu kirletir.
* **`dönem_yakınlığı`** — D2'de ölçtük, ÇAP planı **dönemsiz**. Böyle bir sinyal
  yok.

Yerlerine ÇAP'ın gerçek darboğazını koyduk:

| Ağırlık | Kriter | Neden |
|---|---|---|
| 100 | **kritik yol** | ÇAP'ın süresini belirleyen önşart zinciri. Bu zincirdeki bir dersi kaçırmak mezuniyeti bir dönem öteler; zincir dışındaki ders ötelemez. |
| 40 | zorunlu | havuz dersinin alternatifi var, zorunlunun yok |
| 30 | unlock | kaç dersin önşartında geçiyor (normalize) |
| 25 | erken kademe | zincirin başındaki ders sonrakileri açar |
| 20 | ÇAP dersi | ÇAP anadaldan geride, öne çekilmeli |
| 15 | kontenjan/nadirlik | doluluk > %85 ya da tek şube |

Kritik yol, `sequence`'ın kademelerinden hesaplanıyor: en derin dersten geriye
doğru plan içi önşartlar boyunca yürünüyor.

## ★ Birim: İTÜ kredisi, AKTS değil

İlk sürüm dönem sınırını AKTS'den hesaplıyordu. Gerçek programla karşılaştırınca
tutmadı: kullanıcının 2026-2027 Güz programı **24 kredi ama 50 AKTS**. 30 AKTS'lik
varsayılan sınır programı yarıya kesiyordu.

`config/settings.toml`:

```toml
unit     = "kredi"       # 'kredi' | 'akts'
max_load = 24
```

AKTS her yerde ayrıca gösteriliyor; sadece **sınır** seçilen birimden hesaplanıyor.
Not: `ATA`/`TUR` dersleri 0 kredilidir — kredi sisteminde "bedava" görünürler,
AKTS'leri yine sayılır.

## Sert kısıtlar

Puanlanmaz, **eler**:

1. Geçilmiş (denklikler ve transitif kapanış dahil)
2. Önşart sağlanmıyor — `BİLİNMİYOR` ise **elenmez**, işaretlenir
3. Bu dönem hiç şube yok
4. ★ **Program kısıtı** — aşağıya bak
5. ★ **Kredi eşiği** — bitirme çalışması 95 kredi altında alınamaz
   (Faz 7, `config/kurallar.toml`; bkz. `docs/faz7-kurallar-ve-kipler.md`)
6. Saatler çakışıyor
7. ★ İsteğe bağlı: **dönem sınırı** — "dönemlik + alttan" kipinde anadal
   planından yalnız `term_no <= donem` olan slotlar (Faz 7)

### ★ Program kısıtı — ölçülmüş, varsayılmamış

Öğrencinin kayıt yapabildiği kodlar tek listede (`program_codes`); bir şubenin
"Dersi Alabilen Programlar" listesinde bunlardan **herhangi biri** varsa ders
alınabilir. Rol bazlı ayrım yok — HTAE öğrencisi BLG koduyla da kayıt yapıyor.

```toml
program_codes = ["HTAE", "BLG", "BLGE"]
```

`lesson_allowed_program` tam eşleşmeyle kontrol ediliyor:

| Ders | Alabilen programlar |
|---|---|
| `BLG 212E` | `BLG`, `BLGE` |
| `BLG 223E` | **yalnız `SECE`** |
| `GEO 303E` | `GEO`, `GEOE`, `HTA`, `HTAE` |

İki sonuç: (a) BLG derslerini **ÇAP program kodun** açıyor, anadal kodun değil —
yol haritası §1.6 doğruymuş; (b) `HTAE` GEO derslerinde ayrıca listelendiği için
"HTA ile HTAE'yi aynı say" gibi bir gevşetme yapmıyoruz — İngilizce programdaki
öğrenciye Türkçe şube açmak olurdu.

### Puanlamada iki ölçüme dayalı ağırlık

`cap_role = 50` — ikinci programın (ÇAP **ya da yandal**) derslerinin
**arzı kısıtlı**: 14 kalan dersten yalnız 2–3'ü
bir dönemde alınabiliyor. Kaçırılan fırsat ÇAP'ı bir dönem uzatıyor. Önceki 20'lik
ağırlıkta 2 kredilik `BLG 351E`, 0 kredilik `ATA 122` tarafından dışlanıyordu.

`deferrable = -20` — 10'dan fazla şubesi olan ders (`ATA 121`: 28, `TUR 121`: 37)
fiilen her dönem açılıyor; bu dönem alınmazsa kayıp yok. "Tek şube / kontenjan
kritik" bonusunun aynadaki karşılığı.

## Çakışmasız kombinasyon

Adaylar puana göre sıralı; arama derinlemesine ilerleyip bir **havuz** program
toplar, sonra toplam puana göre sıralar. Farklı **ders kümeleri** üretilir —
aynı kümenin farklı CRN varyantları tekrar edilmez, onlar "alternatif CRN"
olarak ayrıca listelenir (kontenjan dolarsa yedek).

### Üç kural, üçü de gerçek programla karşılaştırmadan çıktı (20.08.2026)

**1. Bir seçmeli havuz slotu TEK ders ile dolar.** Motor aynı ITB havuzu için
`HUK 217` ve `HUK 218`'i birlikte öneriyordu. Aday artık doldurduğu `slot_id`'yi
taşıyor; arama aynı havuzu iki kez doldurmuyor.

**2. Şube seçiminde ileriye bakış.** "En boş şubeyi al" yetmiyor:
`BLG 351E`'nin Pazartesi şubesi zorunlu `GEO 401E` ile (72,5 puan) çakışıyor,
Çarşamba şubesi ise yalnızca bir havuz dersiyle (32,5). Motor artık her şube için
*"bu seçilirse geriye kalan adaylardan kaçının puanı yanar"* maliyetini hesaplayıp
en az yakanı seçiyor. Bir aday ancak **tüm** şubeleri çakışıyorsa yanmış sayılır.
Bu tek değişiklik program puanını 1043 → 1083'e, gerçek programla örtüşmeyi
11/14'ten 12/14'e çıkardı.

**3. Saatsiz şube son çare.** Saati ilan edilmemiş bir şube hiçbir şeyle
çakışmadığı için ileriye bakış maliyeti 0 çıkıyor ve metriği kandırıyordu —
motor `BLG 212E`'yi saatsiz şubeye kaydırmıştı. Belirsizlik avantaj değil:
saatli şubeler önce denenir.

`--pin` ile bir dersi zorunlu tutabilirsin; motor programı onun etrafına kurar.

Kampüs değişimi, aynı gün ardışık iki dersin kampüsü farklıysa sayılıyor
(`building_codes.psv` → `building.campus`). Eşit puanlı programlar arasında
kampüs değişimi az olan öne geçiyor.

## ★ "ÇAP'ta neden alamıyorsun" raporu

Faz 5'in en çok işe yarayan çıktısı bu oldu. Kalan her ÇAP dersi için engelin
**türü** raporlanıyor:

```
ŞUBELERI PROGRAMINA KAPALI (1 ders)
  BLG 223E    2 şube var ama yalnız SECE alabiliyor

BU DÖNEM AÇILMAMIŞ (10 ders)
  BLG 102E, BLG 252E, BLG 202E, BLG 335E, BLG 336E, …

ÖNŞART EKSIK (3 ders)
  BLG 411E    eksik: BLG 252, BLG 252E
  BLG 4901E   eksik: BLG 312, BLG 312E, BLG 322, BLG 322E
  BLG 4902E   eksik: BLG 4901, BLG 4901E
```

**Bulgu: engelin çoğu önşart değil, ARZ.** 14 kalan ÇAP dersinden 11'i ya hiç
açılmıyor ya da şubeleri başka programlara ayrılmış. Bu, "hangi dersi önce
alayım" sorusunun cevabını değiştiriyor: sıralama optimizasyonu değil, **bölümle
konuşmak** gerekiyor.

Dönem başlarında ders programı kademeli yayınlandığı için, `lesson` tablosu
5.000'in altındaysa rapor bunu uyarı olarak ekliyor — "açılmamış" dersler
sonradan çıkabilir.

## Elle denklik beyanı

`config/denklikler.toml` — versiyonlanabilir, `make clean` sonrası kaybolmaz,
her `make refresh` sırasında yeniden uygulanır.

```bash
make recommend            # denklikler otomatik uygulanır
python -m itucap.pipeline equivalence list
python -m itucap.pipeline equivalence add --target "MAT 210E" --sources "GEO 220E"
```

`confidence='user_declared'` ile işaretlenir; arayüz resmi denkliklerden ayırır.
Ders saydırma için Fakülte Yönetim Kurulu kararı gerekebilir.

## Gerçek programla doğrulama (20.08.2026)

Motorun ürettiği program, kullanıcının OBS'de kendi kurduğu programla
karşılaştırıldı:

| | |
|---|---|
| Kullanıcının programı | 14 ders · 24 kredi · 50 AKTS |
| Motorun önerisi | 16 ders · 26 kredi · 55,5 AKTS |
| **Ortak ders** | **12/14** |

Gün ve saatler **14/14** tuttu — gün eşlemesinde hata yok. Motor `BLG 351E`'yi
kullanıcıyla aynı güne (Çar 12:30) ve `BLG 212E`'yi aynı güne (Pzt 08:30)
yerleştirdi.

Kalan farklar:

* Motor `GEO 4901E`, `ATA 122`, `TUR 122`, `HUK 217` ekliyor — kredi tavanında
  (35) yer kaldığı için
* `BLG 351E` ilk karşılaştırmada motorun önerisinde yoktu ve bunu yanlışlıkla
  "önşartı eksik" diye açıkladım. **Yanlıştı.** Önşart bir VEYA:
  `(BLG 212 veya BLG 212E) veya (BLG 222 veya BLG 222E)` — kullanıcı `BLG 222E`'yi
  vermiş, motor da dersi `OK` sayıyor. Ders sadece **kredi tavanı 24'e ayarlıyken
  sığmıyordu**; tavan gerçek değeri olan 35'e çıkınca öneriye giriyor.
  Ders: motorun bir dersi *atlaması* ile *engellemesi* ayrı şeyler; çıktı bunları
  ayırt edebilmeli.
* `GEO 464E` ve `SNT 103E` yerine motor aynı havuzlardan `GEO 458E` ve
  `HUK 217`'yi seçiyor. Havuz içi tercih zevk meselesi — motor puanı eşit
  olanlardan kontenjanı bol olanı alıyor. `--pin` ile kendi seçimini
  sabitleyebilirsin.

## Test kapsamı

147 test (Faz 5'ten 23 yeni):

* Çakışma: aynı gün/bitişik saat/farklı gün
* Program kısıtı: `BLG 212E` HTAE'ye kapalı, `BLG 223E` yalnız SECE'ye açık
* Geçilen ders önerilmiyor; denklik önşartı açıyor
* Kontenjan kritik / tek şube bonusu
* Kritik yol en derin dersten geriye doğru
* Üretilen her programda **çakışma yok**, AKTS sınırı aşılmıyor
* `--pin` edilen ders her programda var
* Alternatif CRN'ler çakışanları dışlıyor
* Darboğaz sınıflandırması: arz mı, önşart mı
* Yük birimi: `kredi` seçiliyken sınır krediden, `akts` seçiliyken AKTS'den
* Tek program listesi iki planı da kapsıyor; kod çıkarılınca ders elenir
* Aynı seçmeli havuzdan iki ders seçilmiyor
* Şube seçimi ileriye bakıyor: daha dolu ama az bloke eden şube tercih ediliyor
* Saatli şube varken saatsiz şube seçilmiyor
