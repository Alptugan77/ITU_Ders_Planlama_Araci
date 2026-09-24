# Faz 7 — Mevzuat kısıtları, program seçimi, projeksiyon

> ⚠️ Bu belgedeki bütün sayılar **örnektir**. Repoda kimsenin gerçek notu
> ya da ortalaması yer almaz — kişisel veri `data/` altında kalır ve
> `.gitignore` ile dışarıda tutulur.


```bash
make ui                          # her şey içinde
make ui ARGS="--donem 7"         # bulunduğun dönemi elle ver
make programs T=yandal           # yandal planlarını listele
```

## ★ Önşart alanı her şeyi söylemiyor

Faz 2'den beri "alınabilir mi" sorusunu `course.prereq_raw`'dan cevaplıyorduk.
Kullanıcı 21.08.2026'da bir karşı örnek verdi: **bitirme projesi 95 kredi altı
alınamaz.** Bu kısıt hiçbir dersin önşart alanında yazmıyor — yönetmelikte
duruyor.

Motor `GEO 4901E`'yi öneriye koyuyordu. Kullanıcının 85 kredisi var; ders
OBS'de reddedilecekti.

Yeni modül `policy.py` bu tür kuralları taşıyor. Kural **koda gömülmedi**,
`config/kurallar.toml` içinde beyan ediliyor:

```toml
[[kredi_esigi]]
ad        = "Bitirme çalışması"
min_kredi = 95
kalip     = ["* 4901", "* 4901E", "* 4902", "* 4902E"]
aciklama  = "Bitirme çalışmasına başlamak için en az 95 kredi tamamlanmış olmalı."
```

Gerekçe: yönetmelik değişiyor, kod değişmemeli. Bir de kullanıcı kendisine
hangi kuralın uygulandığını dosyayı açıp görebilmeli.

### İki ölçüm kararı

**1. Muafiyet krediye sayılmaz.** Faz 2'de aynı ayrımı önşart/ilerleme için
yapmıştık; burada üçüncü kez çıktı. Muaf sayılan ders önşartı açar, kredi
kazandırmaz. Karışsaydı eşik erken dolar, öğrenci alamayacağı derse
yönlendirilirdi. Test bunu kilitliyor.

**2. Kredisi bilinmeyen ders 0 sayılır.** Transkriptte olup katalogda kredisi
bulunmayan ders (`DAN 102`) eşiği **olduğundan zor** gösteriyor. Ters yön
tehlikeli olurdu: eksik veriyi lehte yorumlayıp "alabilirsin" demek. Kaç
dersin bilinmediği arayüzde ayrıca yazıyor.

### Eleyen kural kendini gösterir

Sessiz eleme en kötü tasarım: `GEO 4901E` bir gün öneride varken ertesi gün
yok. Arayüzde ayrı bir bölüm var:

```
KREDİ EŞİĞİ
  ████████████████░░  85 / 95 kredi · 10 kredi eksik
  Bitirme çalışması — Bitirme çalışmasına başlamak için en az 95 kredi…
  Şu an tuttuğu dersler: BLG 4901E, BLG 4902E, GEO 4901E, GEO 4902E
```

Darboğaz raporuna da yeni bir engel türü eklendi: `KREDI_ESIGI`. Sıra önemli —
önce önşart, sonra kredi. Bir ders ikisinden de takılıyorsa önşart yazılıyor,
çünkü önce onu çözmek gerekiyor.

## ★ İkinci program: ÇAP ya da yandal

Motor "anadal + ÇAP" varsayıyordu. Yandal aynı yapı: ayrı plan, ayrı ilerleme,
ayrı renk. Fark yalnız **etikette** ve OBS'den hangi plan tipinin çekildiğinde.

```toml
second_kind = "cap"      # 'cap' | 'yandal' | 'yok'
```

`Settings` artık `second_role` / `second_label` / `second_program` /
`second_plan_id` türetiyor; motor `role != "ANADAL"` diye bakıyor, `== "CAP"`
diye değil. Arz bonusu (`cap_role = 50`) yandalda da geçerli — gerekçe aynı:
ikinci programın dersleri kısıtlı arzda.

`second_kind = "yandal"` yazınca `scrape_plan_types` kendiliğinden `yandal`
ekliyor; kullanıcının iki ayrı yeri güncellemesi gerekmiyor.

`second_kind = "yok"` tek programla çalıştırıyor — panel tek, darboğaz yok.

Plan id'sini bulmak için:

```bash
make programs T=yandal Q=BLG
```

## ★ İlerleme barında projeksiyon

Bar "geçtiğin"i gösteriyordu, "bu dönem ne olacağı"nı değil. Artık iki
katmanlı:

```
████████████████░░░░░░░░░░░░░░  ← dolu = geçilmiş, taralı = bu dönem seçili
bu dönem 13 slot dolarsa %52.5 → %73.8
slot 32/61 +13   kredi 73/117 +18   akts 122/212 +41   kalan zorunlu 23 → 12
```

Hesap **tarayıcıda**, çünkü program düzenlenebilir (Faz 6) — bir dersi
çıkarınca projeksiyon anında düşüyor. Bunun için JSON'un panelde `planId`,
adayda `planId`/`slotId`/`required` taşıması gerekiyor; test bu sözleşmeyi
kilitliyor.

Sayım **slot bazlı**, ders bazlı değil: aynı seçmeli havuza iki ders
konulamadığı için bir havuz en fazla bir slot ilerletir.

## ★ "Dönemlik + alttan" kipi

İkinci bir aday havuzu: anadal planından yalnız `term_no <= donem` olan
slotlar. Dönemsiz planlar (ÇAP/yandal) her kipte kalıyor — eleyecek dönem
bilgisi yok, uydurmuyoruz.

```
[ Tüm adaylar ] [ 7. dönem + alttan ]
10 dönemlik (7. dönem) · 64 alttan (1–6. dönem) · 2 ÇAP — planı dönemsiz, hepsi kalır
```

Her kipin **kendi programları** var, sadece filtrelenmiş bir liste değil —
yoksa ızgarada olmayan bir dersi tabloda görürdün.

### Dönem tahmini dürüst olmalı

`donem` sırasıyla: `--donem` > `settings.toml` > **tahmin**. Tahmin ölçütü,
geçilmiş slotların en derin `term_no`'su.

Bu bir tahmin, kayıt kaydı değil: kayıt donduran, yaz okulu okuyan ya da
alttan çok ders taşıyan öğrencide şaşar. O yüzden başlıkta hangisinin
kullanıldığı **yazıyor** — `7. dönem (tahmin)`. Sessizce tahmin edip yanlış
liste göstermek en kötüsü olurdu.

## ★ Tasarım: kurum belgesi kaydı

Kullanıcı "daha resmi ve akademik" istedi. Değişen şey renk paleti değil,
**kayıt**:

| | önce | sonra |
|---|---|---|
| Başlık yüzü | Archivo (grotesk) | **Source Serif 4** |
| Gövde | Archivo | **Source Sans 3** (aynı üst aile) |
| Yüzey | gölgeli kart, 10px köşe | gölgesiz, 4px köşe, ince çerçeve |
| Yapı rengi | yok (aksan = veri rengi) | **lacivert** cetvel/başlık/sekme |
| Bölüm başlığı | eyebrow + h2 | eyebrow + sona uzanan **cetvel** + serif h2 |
| Belge başı | tek çizgi | kalın + ince **çift cetvel** |

Kritik ayrım: **lacivert YAPI, yeşil/kehribar VERİ.** Lacivert bir öğe hiçbir
zaman "anadal" anlamına gelmiyor. Bu ayrım olmasaydı üçüncü bir renk eklemek
ızgarayı okunmaz yapardı.

Source Serif 4 ile Source Sans 3 aynı üst aileden — birlikte çizilmişler,
yan yana yamalı durmuyorlar. Rakamlar her yerde IBM Plex Mono ve
`tabular-nums`: kredi, CRN, saat ve yüzde sütun hâlinde hizalanıyor.

Seçili sekmede bir hata düzeltildi: zemin `--seal`, yazı **`--ground`**. Sabit
`#fff` yazsaydık koyu temada açık mavi üstünde beyaz kalırdı — üç durumun
(açık / koyu / sistem) hepsinde kontrast korunuyor.

## Test kapsamı

195 test (Faz 7'den 37 yeni).

**Kredi eşiği** — kalıp ve açık liste eşleşmesi · yalnız geçilen dersler sayılır
· **muafiyet kredi kazandırmaz** · bilinmeyen kredi 0 sayılır ve raporlanır ·
eşik altında eler, üstünde açar · en katı kural kazanır · kural TOML'dan gelir,
dosya yoksa varsayılana düşer · projenin kendi config'i 95'i beyan ediyor ·
darboğaz raporunda `KREDI_ESIGI` çıkıyor

**Program seçimi** — `second_kind` → rol/etiket/plan eşlemesi · yandal seçilince
plan tipi otomatik ekleniyor · `yok` tek programa düşürüyor · geçersiz değer
`cap`'e düşüyor · yandal adayları arz bonusunu alıyor

**Dönem** — tahmin en derin geçilmiş dönemi veriyor · `max_term` ileriki dönemi
eliyor, dönemsiz planı elemiyor · `open_required` havuz slotlarını saymıyor

**Projeksiyon (tarayıcıda)** — seçim boşalınca projeksiyon sıfırlanıyor · aynı
havuzun iki dersi slotu bir kez ilerletiyor · kip anahtarı aday tablosunu
değiştiriyor ve geri dönüyor
