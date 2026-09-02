# Faz 37 — Katalogdaki kredi koşulu ve sessiz kalan eleme

*02.09.2026 · kullanıcı isteği: "ders seçim aracını dikkatlice inceleyip
eksikleri belirtir misin… kapatabileceğin eksiklikler varsa değiştir ve
geliştir"*

Araç olgun; bu fazın işi yeni özellik değil, **ölçüm**. Depoyu gerçek veriyle
çalıştırıp motorun ne gördüğünü ne görmediğini saydım. Üç eksik çıktı ve
üçünün de ortak yanı şu: veri elimizdeydi, motor bakmıyordu.

Testler **951 → 987** (985 geçti, 2 atlandı — o ikisi git deposu istiyor).

---

## A. ★★ Katalogdaki kredi koşulu motorda hiç kullanılmıyordu

### A1. Sütunun adı yanlış, içeriği doğru

`course.class_restriction`, itu-helper `courses.psv`'nin 7. alanından
geliyor ve kaynak ona **"Sınıf Kısıtı"** diyor. Taşıdığı değerler ise sınıf
değil **kredi**:

| Değer | Ders |
|---|---|
| `Yok` | 4335 |
| `95,00` | 437 |
| `60,00` | 45 |
| `30,00` | 15 |
| (boş) | 5953 |

İTÜ'de sınıf zaten kazanılmış krediyle belirlendiği için alan bir **kredi
tabanı**. Doğrulaması elimizdeydi ve fark etmemiştik: kullanıcının
21.08.2026'da beyan ettiği *"bitirme projesi 95 kredi altı alınamaz"* kuralı,
katalogda tam olarak `95,00` diye duruyor. Beyan ile kaynak birbirini
tutuyor — yani yorum tahmin değil, **doğrulanmış**.

### A2. Ölçülen boşluk

`kurallar.toml`'daki beyan (kod kalıbı `* 4901` … + ad kalıbı
`bitirme`/`graduation`) katalogda tabanı olan **498** dersin yalnız
**173**'ünü tanıyordu.

> **325 ders motorun kör noktasındaydı** — 268'i 95, 41'i 60, 15'i 30 kredilik.

Somut sonucu: 40 kredilik bir ÇEV öğrencisine `CEV 461E` (30 kredi koşulu),
bir END öğrencisine `END 441E` (95) önerilebiliyordu — kayıt gününde
reddedilecek bir ders. Kullanıcının kendi planlarında bir örnek çıktı:
**`ISL 478E — Entrepreneurship`, 95 kredi koşulu**, 85 kredide.

### A3. Ne yapıldı

`policy.parse_catalog_floor` + `[katalog_kredi_kosulu]` bloğu. Katalog
tabanı beyan edilmiş kurallarla **aynı yoldan** geçiyor (`POL.check`), yani
eleme de darboğaz raporu da tek yerden geliyor.

⚠️ **Sayıyı biz uydurmuyoruz**, katalogda yazıyor. Uydurma olabilecek tek şey
YORUM ("sınıf kısıtı" = kredi tabanı). O yüzden:

* `dogrulandi = false` — arayüz alanın kaynaktaki adını ve yorumun bize ait
  olduğunu **yazıyor**,
* `kullan = false` ile **kapatılabilir** ve nasıl kapatılacağı ekranda duruyor,
* eleme **sessiz değil**: kredi panelinde ders ders, kaç kredi eksik
  olduğuyla listeleniyor.

⚠️ Beyan ile katalog çelişirse **en katısı** uygulanır. Ölçüldü: `* 4902`
kalıbı 95 diyor, katalog o **61** derste `Yok` diyor. Birini "haklı" ilan
etmek elimizde olmayan bir bilgi gerektirirdi; katı taraf güvenli taraf.

### A4. Plan dışı ders ekleme — engel değil, uyarı

Katalog araması sonucunda tabanı tutmayan derse rozet çıkıyor
(**"95 kredi ister"**). Plan dışı ekleme kullanıcının açık kararı, o yüzden
engellemiyoruz; ama hiç uyarmadan programa koymak kayıt gününde öğrenilecek
bir sürpriz olurdu.

### A5. Bozuk değerler uydurulmuyor

**6 derste** alan kaymış ve içinde ders adı duruyor
(`BLG 210` → 'Mikroişlemci Sistemleri', `MAT 339` → 'Complex Analysis'…),
**1 derste** beklenmedik bir sayı var (`ROS 201` = `'1'`, kredisi de NULL).
`parse_catalog_floor` bunları **taban saymıyor** (None döner) ve
`quality.katalog_kredi_kosulu_bozuk` ikisini de sayıyor — bir ders adını
krediye çevirmeye kalkmak uydurma bir kısıt üretirdi.

---

## B. ★ Eleme komut satırında SESSİZ kalıyordu

`recommend.format_blockers` çıktı döngüsü şuydu:

```python
for reason in ("PROGRAMA_KAPALI", "ACILMAMIS", "ONSART", "BILINMIYOR"):
```

`KREDI_ESIGI` **yok**. Engel hesaplanıyor, sözlükte etiketi duruyor, web
arayüzü gösteriyor — `make recommend` çıktısı sessizce düşürüyordu. Bu, bu
projenin ana ilkesinin ("eleyen kural kendini göstermek zorunda") komut
satırındaki ihlaliydi ve A'daki değişiklik onu daha da önemli hale getirdi:
artık 325 ders daha bu yoldan elenebiliyor.

★ Yan bulgu: başlıklar `labels[reason].upper()` ile yazılıyordu ve Python'un
`upper()`'ı Türkçe bilmiyor — çıktıda **"ÖNŞART EKSIK"**, **"ŞUBELERI"**
yazıyordu (noktasız I). `_tr_upper` ile düzeltildi.

---

## C. `fikirler §1.3` cevaplandı: sütun boş değil, kaynak yayınlamıyor

Soru şuydu: *"`class_restr` 3417 şubenin hiçbirinde dolu değil; OBS artık
yayınlamıyor mu, tarayıcı mı okumuyor?"*

Ölçüldü: itu-helper `lessons.psv` **11 alan** yayınlıyor —
`CRN|Kod|Yöntem|Hoca|Bina|Gün|Saat|Derslik|Kontenjan|Yazılan|Programlar`.
İçinde ne sınıf kısıtı var ne önşart. `lesson.class_restr` ve
`lesson.prereq_raw` **kaynakta yok**.

Sütunlar silinmedi, **işaretlendi**: şema yorumu + her taramada rapor eden
`quality.kaynak_yayinlamiyor` kontrolü. "Veri yok" ile "kaynak vermiyor"
farklı şeyler ve kaynak yarın yayınlamaya başlarsa sayı kendiliğinden
değişir. ⚠️ Bu sütunların boşluğundan **"sınıf kısıtı yok" sonucu
çıkarılamaz.**

---

## D. Tercih karşılanamıyorsa NE BIRAKMALI (`fikirler §3.5`)

Faz 27 ölçümü: "Pzt + Cuma boş" istendiğinde motor ikisini birden
sağlayamıyor ve −10 farkla en yakınını sunuyor. Doğru davranış ama kullanıcı
çıkışın nerede olduğunu göremiyordu.

`Schedule.pref_relief()` artık **tek adımlık** çare üretiyor:

> ↳ **BHB 201E** çıkarılırsa istemediğin hoca kalmıyor *(−3 kredi)*

⚠️ Üç sınır bilerek kondu:

* **Tek ders.** "Şu ikisini de çıkar" demek programı baştan kurmak olurdu ve
  o işi zaten motor yapıyor (öbür öneriler). Tek ders geri alınabilir hamle.
* **Kayıp saklanmıyor.** Kaç kredi gittiği ve dersin zorunlu olup olmadığı
  yazıyor; boş gün uğruna sessizce bir zorunlu ders düşmesin. Sıralama da
  buna göre: zorunlu olmayan ve ucuz olan önde.
* **"İstediğin hoca" çare sayılmıyor.** O sayacı sıfıra indirmek kazanç
  değil kayıp; yalnız İHLAL sayan tercihler (erken saat, boş gün, istenmeyen
  hoca) çare üretiyor.

★ Puan ile çare **aynı sayacı** kullanıyor (`_tercih_sayaclari`). İki yerde
ayrı sayılsaydı arayüz "Cuma boşalıyor" derken puan değişmezdi ve kullanıcı
hangisine inanacağını bilemezdi. `test_puan_ile_care_AYNI_sayimi_kullaniyor`
bunu kilitliyor.

---

## E. Küçük düzeltmeler

| Ne | Neden |
|---|---|
| Yandal kartındaki **`OTHER 0/6`** → **`KATEGORİSİZ 0/6`** (+ açıklama balonu) | `OTHER` motorun iç etiketi; yandal kartında görünen **tek** chip oydu ve kullanıcıya hiçbir şey anlatmıyordu |
| `max_ects_per_term` | Ayarı okuyan **tek satır kod yok**: MADDE 17 yükü KREDİ üzerinden sınırlıyor. Silmedik, "uygulanmıyor" diye işaretledik — doğrulanmamış bir tavanla ders elemek olurdu |

---

## Doğrulama

```
pytest                    985 geçti · 2 atlandı (git deposu isteyen ikisi)
make site                 katalog 10.9 MB → gzip 2.9 MB · kurulum sorunsuz
  ↳ yayınlanan katalogda class_restriction KORUNUYOR ve site config/kurallar.toml'u
    taşıyor → web ve yerel sürüm AYNI kuralı uyguluyor (ayrışmıyorlar)
tarayıcı                  sayfa hatası yok
  ↳ kredi paneli: "Katalog bu 1 ders için ayrıca kredi koşulu ilan etmiş …
                   ISL 478E Entrepreneurship — en az 95 kredi, 10 kredi eksik"
                   + kaynak + "kapatmak için kurallar.toml"
  ↳ katalog araması: ISL 443E · [PLAN DIŞI] [95 KREDİ İSTER]
  ↳ ilerleme kartı: KATEGORİSİZ 0/6
  ↳ tercih notu: "↳ BHB 201E çıkarılırsa istemediğin hoca kalmıyor (−3 kredi)"
make recommend            ŞUBELERİ / ÖNŞART EKSİK (noktalı İ) + KREDİ EŞİĞİ bölümü
kalite raporu
  [warn] katalog_kredi_kosulu_bozuk : 6 derste sayı yok · 1 derste beklenmedik değer
  [info] katalog_kredi_kosulu_kapsam: 325 ders YALNIZ katalogda, 61 derste beyan
                                      var ama katalog 'Yok' diyor
  [info] kaynak_yayinlamiyor        : lesson.class_restr/prereq_raw — kaynak yayınlamıyor
```

---

## Kapanmayanlar (bilerek)

* **`fikirler §1.1 / F.4` kod göçü tablosu** — 72 plan slotu katalogda
  karşılığı olmayan bir derse bakıyor, 275 önşart hedefi katalogda yok.
  Eşleme **beyan** ister; tahmin etmek ilerleme yüzdesini bozar.
* **`§2.1` çok dönemli plan** ve **`§2.3` yaz okulu** — büyük işler.
* **`F.5` yayın hattı** — depoda `origin` artık tanımlı ama site hâlâ
  yayınlanmayı bekliyor; düzeltmelerin kullanıcıya ulaşması buna bağlı.
* **`F.2` yerin ilan edilmediği %42** — yeniden ölçüldü, **1542/3630 =
  %42.5**, değişmemiş. Kalıcı görünüyor: "kampüs değişimi" tercihi bu kadar
  veriyle çalışıyor demektir.
