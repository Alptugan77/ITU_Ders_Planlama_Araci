# Faz 28 — Sessiz kayıplar: bir yandal nasıl yok olur

*24.08.2026 · ilk kullanıcı incelemesinin kalan maddeleri (B3, B5, C3, D3, E)
ve yolda çıkan yedi hata*

---

## Başlangıç: iki bildirim ve bir inceleme

Kullanıcı iki şey bildirdi ve bir inceleme belgesi verdi:

1. *"yandal ve çap planını aynı anda yapmaya çalışınca program türü geçersiz
   diyor"*
2. *"çevrimiçi olan dersler programda daha açık renkle gösterilebilir"*

İkisi de bir önceki turda kapandı. Bu belge, incelemenin kalan maddelerini ve
**onları kapatırken bulunan yedi hatayı** anlatıyor. Yedisinin altısı aynı
sınıftan: *bir şey sessizce kayboluyor ve ekran bunu "yok" diye gösteriyor.*

---

## 1. ★★ Her yandal kodu bozuluyordu

Tarayıcıda ÇAP+yandal kaydını doğrularken kaydın **çalıştığını** gördüm —
`kaydedildi ✓`, 6,9 saniye. Ama `settings.toml`'a bakınca:

```toml
yandal_program = "ALGYD"      # kutudan seçilen: ALG_YD
```

Alt çizgi gitmişti. Kaynak:

```python
def _clean_code(value) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", str(value or "")).upper()[:8]
```

**Ölçüm — katalogdaki 205 program kodunun 78'i alt çizgi taşıyor ve
bunların hepsi yandal:** `ALG_YD`, `ARC_YD`, `MAT_YD_EC`… Yani *"yandal
seç"* düğmesi, seçilen her yandalı hiçbir şeyle eşleşmeyen bir koda
çeviriyordu. 8 karakterlik kesme de ayrı bir kayıp: `MAT_YD_EC` dokuz
karakter.

Sonuç zinciri: kod bozulur → plan aranır, bulunamaz → yandal listeden
düşer → ekranda **yandal hiç görünmez**. Kullanıcı seçiminin kaydolmadığını
sanır ve tekrar dener; aynı şey olur.

Düzeltme iki parçalı. Temizleyici alt çizgiyi koruyor — ama asıl mesele
şuydu: **temizleyip doğrulamamak.**

```python
def _dogrula_program(self, code, rol):
    if self._program_var(code) is not False:      # True veya "bakılamaz"
        return
    yakin = [...]                                  # ALGYD -> "ALG_YD mi?"
    raise ValueError(f"{rol} programı katalogda yok: {code}{ek}")
```

`_program_var` **üç değerli**: katalog boşsa `None` döner. Henüz veri
çekilmemişken "bu kod yanlış" demek, yanlış olurdu.

---

## 2. ★★ Planı olmayan ikinci program ekrandan siliniyordu

`plans.resolve_seconds` bunu bilerek yapıyor:

> *Planı bulunamayan tür listede KALIYOR (`plan_id=None`). Sessizce atmak,
> "yandalım var ama araç göstermiyor" ile "yandal planı çekilmemiş"i aynı
> şeye çevirirdi.*

`ui.collect` ise **bir satır sonra** o ayrımı çöpe atıyordu:

```python
seconds = [s for s in seconds if s.get("planId")]
```

Aynı soruya iki kaynağın farklı cevap vermesi — bu projenin ikinci klasik
hata sınıfı. Artık plansızlar `secondsMissing` olarak taşınıyor ve kurulum
çubuğunda duruyorlar:

```
BLGE anadal · MAT ÇAP · ALGYD Yandal [planı yok] · ?. dönem · 0 ders girilmiş
```

Seçim duruyor, hesap yapılmadığı **yazıyor**.

---

## 3. Sekme etiketi: hesaplanmış ama kullanılmamış fark

Faz 27'de sekmelere ayırt edici etiket eklenmişti. Tarayıcıda ölçünce üç
sekmeden ikisi **boş** etiket alıyordu — dört ölçütün hiçbiri onları
ayırmıyordu:

| | boş gün | başlangıç | kampüs | çevrimiçi | **bekleme** | **bitiş** |
|---|---|---|---|---|---|---|
| Öneri 1 | — | 08:30 | 0 | 3 | **218 dk** | 17:59 |
| Öneri 2 | — | 08:30 | 0 | 5 | 668 dk | 17:29 |
| Öneri 3 | — | 08:30 | 0 | 3 | 339 dk | 17:59 |

Fark **zaten hesaplanıyordu** (`shape.gaps`) ama hiçbir yerde ayırt edici
sayılmıyordu. Öğrenci için en somut fark buydu: 218 dakika bekleme ile 668
dakika arasında üç buçuk saat var.

İki ölçüt eklendi (bekleme, bitiş saati), **30 dakikalık eşikle**: birkaç
dakikalık farkı "en az bekleme" diye satmak olmayan bir üstünlük iddia
etmek olurdu.

```
Öneri 1 · 21.5 kredi · en az bekleme
Öneri 2 · 21.5 kredi · 5 çevrimiçi
Öneri 3 · 20.5 kredi
```

Üçüncüsü hâlâ etiketsiz — çünkü onu ötekilerden ayıran bir şey **yok**.
Uydurma etiket ("dengeli", "yoğun") kullanıcıya olmayan bir fark anlatırdı.

### Bu ölçütleri test ederken çıkan hata

`oneriFarki` kendi `shape`'ini kolluyordu ama **öbürlerininkini okurken
kollamıyordu**. `shape`siz tek bir öneri istisna atıyor ve **sekme çubuğu
komple çizilmiyordu**. Node'da gerçekten çalıştırılan testler yakaladı;
metin araması yakalayamazdı.

---

## 4. B3 — `202610` bir dönem adı değil

Başlıkta OBS'nin iç kodu yazıyordu. `config.donem_adi()` onu çeviriyor:

```
BLGE + MAT ÇAP · 2026-2027 Güz        (ipucu: "OBS dönem kodu: 202610")
```

⚠️ Tanımadığı kalıba **isim uydurmuyor**: boş dönüyor ve arayüz ham kodu
yazmaya devam ediyor. Yanlış bir dönem adı ham koddan çok daha kötü —
öğrenci "bahar" sanıp yanlış döneme bakar.

---

## 5. C3 — iki ham veri sızıntısı

### "belirsiz" bir bina adı sanılıyordu

```python
return "belirsiz" if (code or "").lower() == "undeclared" else (code or "")
```

**Ölçüm: 3630 buluşmanın 1542'si (%42) yerini ilan etmemiş.** Yani
ızgaradaki en sık görülen "bina adı" uydurma bir kelimeydi ve bina kodunun
durduğu yerde duruyordu.

`_hoca` ile aynı ilke uygulandı — bilinmeyen bilinmeyen kalıyor:
hücrede *yer yok*, ipucunda *"OBS'de yer bildirilmemiş"*. Bilinen kodlar da
artık ipucunda tam adıyla duruyor (`TMB — Temel Bilimler Binası`); kod tek
başına bir yer değil.

Terminal çıktısı da aynı sözü kullanıyor: aynı şeye iki ad vermek (arayüzde
"yer yok", terminalde "belirsiz") bu projenin klasik hatası.

### "ECN — ECN"

```sql
COALESCE(pr.name, p.program_code) AS name
```

Adı bilinmeyen programa **kodun kendisi ad diye veriliyordu**. Ölçüm: 4
program kodunun (`ECN`, `SEC`, `VBA`, `YZV`) `program` tablosunda satırı
yok — adları veride hiç yok, uydurulamaz. Artık `ECN — (adı katalogda yok)`.

---

## 6. D3 — ilk giren kişiye boş bölüm

"Ne değişti" bölümünün ölçütü `LIVE` idi. Hiç tazeleme yapmamış birine
başlık ve altında *"karşılaştırma için en az iki tazeleme gerekiyor"*
çıkıyordu: henüz kullanmadığı bir özelliğin boş kabuğu, üstelik bölüm
çubuğunda bir sıra kaplıyor.

Yeni ölçüt: **karşılaştırılacak bir şey olması.**

### Bunu düzeltirken çıkan hata

"Veriyi tazele" düğmesi **yalnızca o bölümün içindeydi**. Bölümü gizlemek
düğmeyi de yok ederdi. Düğme, verinin yaşını yazan satırın yanına taşındı —
soruyu soran cümlenin yanında cevabı veren düğme:

```
şube/kontenjan verisi dün tazelendi (23.08.2026 12:50)  [tazele]
```

İlerleme artık **tıklanan** düğmede gösteriliyor; eskiden metin hep gizli
bölümdeki düğmeye yazılıyordu ve oradan başlatılmayan tazeleme 1–2 dakika
boyunca hiçbir iz bırakmıyordu.

---

## 7. B5 — beyan edilen denklikler kişisel veriydi

İki kaynak aynı soruya farklı cevap veriyordu:

| Kaynak | Cevap |
|---|---|
| `declared.py` | *"Bunlar kişisel veri DEĞİL (müfredat bilgisi)"* → referans DB'ye yazar |
| `tools/gizlilik_denetimi.py` | katalogda `user_declared` görürse **HATA** |

Denetim haklıydı: *"şu dersim şunun yerine saysın"* beyanı hem hangi dersi
aldığını hem neye başvurduğunu ele verir. Beyanlar `user.sqlite3`'e taşındı.

Göç kayıpsız: beyanların asıl kaynağı `config/denklikler.toml` ve açılışta
kullanıcı veritabanına yeniden uygulanıyor. Katalogda kalmış eski satırlar
siliniyor — okumasak bile o dosya yayınlanan sitenin içine giriyor.

⚠️ Beyan id'leri `1_000_000_000` ötelenmiş: iki dosyada da id 1'den başlıyor
ve `via_equivalence` yanlış denkliği gösterirse *"bu ders şu denklikle
sayıldı"* derken **başka** bir denkliği göstermiş oluruz.

---

## 8. E — küçük ama yanlış olanlar

**Katalogda olmayan ders** `BLG 105E · (adsız) · –` diye görünüyordu: boş ad
ve sıfıra benzeyen bir tire. Ölçüm: plan slotlarının 67'si katalogda olmayan
bir derse bakıyor. Artık *"bu ders katalogda yok"* yazıyor ve tiredeki
belirsizlik ipucunda açıklanıyor.

**Tercihler keşfedilmiyordu.** Motor Faz 27'den beri yumuşak tercihleri
sıralamaya katıyor ama ilk giren kişi böyle bir kutu olduğunu bilmiyordu.

Dördüncü bir *kurulum adımı* denendi ve **geri alındı**: tercih çoğu
kullanıcıda hep boş kaldığı için karşılama kartı hiç kaybolmuyordu — Faz
26'nın tam da kaldırdığı "ekranın arkasında duvar var" hissi geri geliyordu.
Üç test bunu yakaladı. Tercihler kurulum değil **ince ayar**: kurulum bitince
çıkan şeritte duruyor, ve tercih girilmişse düğme hiç görünmüyor.

---

## 9. 7 saniyelik kayıt kendini söylüyor

ÇAP + yandal birlikte kaydedilince sunucu her şeyi baştan hesaplıyor:
**ölçüldü, 6,9 saniye.** Ekranda tek satır "kaydediliyor…" yazıp durunca
kullanıcı takıldı sanıp pencereyi kapatıyor ya da tekrar tıklıyordu. Üç
saniyeyi geçen bekleme artık geçen **gerçek** süreyi yazıyor:

> kaydediliyor… 5 sn — plan yeniden hesaplanıyor, pencereyi kapatma

---

## Bu fazın yöntemi

Değişikliklerin hepsi aynı iki adımdan geçti:

1. **Kodu değiştirmeden önce gerçek katalogda ölç.** "78/205 kod alt
   çizgili", "1542/3630 buluşmanın yeri yok", "67 plan slotu boşa bakıyor",
   "4 programın adı veride yok" — bu sayıların hiçbiri tahmin değil, ve
   birkaçı düzeltmenin şeklini değiştirdi.
2. **Düzeltmenin davranışı gerçekten değiştirdiğini doğrula.** Tarayıcıda
   koşan doğrulama, ilk turda değişikliklerin **hiçbirini** görmedi — çünkü
   eski sunucu süreci portu tutuyordu. Testler yeşildi ve yanıltıcıydı.

`oneriFarki` testleri metin araması değil: işlev node'da gerçekten
çalıştırılıyor. Sekme çubuğunu komple silen istisna ancak böyle çıktı.

---

## Sayılar

| | |
|---|---|
| Test | **875** (Faz 27 sonunda 843) |
| Bu fazda bulunan hata | 7 (biri de düzeltme sırasında çıktı) |
| Bozuk program kodu | 78 / 205 |
| Yeri ilan edilmemiş buluşma | 1542 / 3630 (%42) |
| Katalogda karşılığı olmayan plan slotu | 67 |
| Adı veride olmayan program | 4 |

---

## Kalanlar

- `make all-plans` yeniden koşturulmalı: `ECN`, `SEC`, `VBA`, `YZV` için
  `program` satırı gerçekten yok mu, yoksa tarama mı atlamış?
- 6,9 saniyelik kayıt **hâlâ 6,9 saniye**. Şu an dürüstçe söylüyor ama asıl
  çözüm kısmi hesaplama: program değişince yalnız etkilenen paneli kurmak.
- Yeri ilan edilmemiş %42'lik dilim OBS dönem başında dolduruyor olabilir;
  tazeleme sonrası tekrar ölçülmeli.

---

# Ek — 27.08.2026: yayındaki hata ve program kodlarının otomatikleşmesi

Kullanıcı **yayınlanan siteden** ekran görüntüsü gönderdi: `İkisi` seçili,
ÇAP `BLG`, yandal `BHB_YD`, ve altta kırmızı yazı: **"ikinci program türü
geçersiz"**. Bir de istek: *"alabileceğim ders kodlarını anadal çap ve
yandala göre otomatik ekler misin, orada sadece ekstra program türleri
girilebilsin"*.

## 1. Yayındaki hata: düzeltme var, sitede yok

`SECOND_KINDS` / `SECOND_CHOICES` uyuşmazlığı bu fazın başında kapandı.
Ekran görüntüsündeki site o düzeltmeyi **taşımıyor** — yayın hattı Faz 24'ten
beri çalıştırılmadı. Yerelde aynı seçim (`HTAE` + `BLG` ÇAP + `BHB_YD`
yandal) `kaydedildi ✓` veriyor.

## 2. ★★ Ama doğrulama sitede yeni bir hata çıkaracaktı

Faz 28'in başında eklediğim `_dogrula_program`, kodu **`program`
tablosunda** arıyordu. Açılır kutu ise **`plan` tablosundan** doluyor. Depoya
işlenmiş katalogda ölçtüm:

| | |
|---|---|
| `plan` tablosunda program kodu | 127 |
| `program` tablosunda satır | 129 |
| `program` tablosunda **yandal** | **0** (76 `_YD` kodu eksik) |

Yani kutu `BHB_YD — Bilişim Uygulamaları…` sunuyor, kullanıcı seçiyor,
doğrulama *"katalogda yok"* diye reddediyordu. Bir sessiz kaybı kapatırken
ekrana gelen bir kaybı açmak.

Aynı hata sınıfı, üçüncü kez: **aynı soruya iki kaynak farklı cevap
veriyor.** Kural artık tek cümle: *kullanıcıya sunduğumuz her seçenek
geçerli sayılır.* Doğrulama iki kaynağın birleşimine bakıyor; sunmadığımız
bir kod (elle yazılan `BHBYD`) hâlâ reddediliyor ve `BHB_YD` öneriliyor.

## 3. Program kodları artık seçimlerden türetiliyor

Eskiden `KAYIT YAPABİLDİĞİN PROGRAM KODLARI` serbest metin kutusuydu ve
`Settings.load` boşsa onu seçimlerden **doldurup dosyaya yazıyordu**. İki
sonucu vardı:

* türetilmiş kod ile elle yazılmış kod **ayırt edilemiyordu**;
* **bölüm değişince eski kod kutuda kalıyordu** — anadalını değiştiren
  kişinin ders havuzu eski koda göre süzülmeye devam ediyor ve bu ekranda
  hiçbir yerde yazmıyordu. Sessiz, ve sonucu "bu ders neden listede yok".

Artık:

```
KAYIT YAPABİLDİĞİN PROGRAM KODLARI
[HTAE] [BLG] [BHB_YD]          ← okunur, seçimlerden CANLI türüyor
```

`allowed_programs` = türetilenler ∪ ekstralar, her okumada yeniden. Kutu
yalnız ekstraları tutuyor ve genelde boş kalıyor. Eski dosyalar ilk kayıtta
kendiliğinden temizleniyor; birleşim aynı kümeyi verdiği için davranış
değişmiyor.

## 4. Dil eşi: öneriliyor, dayatılmıyor

`BLG` seçen öğrenci çoğu zaman `BLGE` şubelerine de kayıt yapabiliyor
(kullanıcının kendi ayarı: HTAE, BLG, BLGE). Ama bu bir **iddia**: yanlışsa
alamayacağı bir dersi alabilir gösterir. O yüzden otomatik eklenmiyor:

```
BUNLAR DA EKLENEBİLİR
[+ HTA] [+ BLGE]     ← tıklayınca ekstra kutusuna girer
```

Öneri de uydurulmuyor. Eşin katalogda **gerçekten** bir programı ya da planı
olmalı **ve** o koda açık en az bir şube bulunmalı. Ölçüldü: 205 koddan
**78'inin** doğrulanmış bir eşi var.

⚠️ Ve bir yorum yanlış çıktı. `normalize.merge_language_variants` şöyle
diyordu: *"'HTAE'nin 'HTA' diye bir eşi yok"*. Katalogda ölçtüm:

| kod | ad | şube |
|---|---|---|
| `HTA` | Harita Mühendisliği Lisans | 774 |
| `HTAE` | Harita Mühendisliği (İngilizce) Lisans | 655 |

Gerçek bir çift. Kuralın kendisi doğruydu, **gerekçesi yanlıştı** — ve o
gerekçe iki yıl boyunca örnek olarak alıntılanabilirdi. Yorum düzeltildi;
eş kararı artık her yerde katalogdan doğrulanıyor.

⚠️ Öneri **kayıtlı ayara değil**, o anki seçime bakıyor. Kayıtlıya
bağlasaydık öneri ancak kaydettikten sonra görünürdü — yani tam gerektiği
anda değil. Sunucu doğrulanmış eş haritasının tamamını gönderiyor (ölçüldü
~50 ms, önbelleğe alındı ve `refresh` düşürüyor), arayüz o anki seçime göre
süzüyor.

## Sayılar

| | |
|---|---|
| Test | **889** |
| Yayınlanan katalogda `program` satırı olmayan yandal | 76 / 76 |
| Doğrulanmış dil eşi çifti | 78 / 205 |

## Kalan

**Yayın hattı çalıştırılmalı.** Sitedeki hatanın düzeltmesi depoda duruyor;
`gh release create katalog-YYYYMMDD` + Actions → `pages` çalışmadan
kullanıcıya ulaşmıyor.
