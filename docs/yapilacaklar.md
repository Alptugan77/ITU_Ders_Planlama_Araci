# Yapılacaklar

Faz 1–16 bitti (485 test). Depo GitHub'a hazır; statik site yayında. Bu liste **sonrası** için: ne kaldı, neden önemli,
ne kadar iş, neye bağlı.

> **Faz 10'da kapananlar:** CRN listesi ✅ · programı kaydet ✅ · denklik
> keşfi ✅ · tüm ÇAP/yandal planları ✅
> **Faz 11'de kapananlar:** kontenjan nöbeti ✅ · yedekten geri yükleme ✅ ·
> tek komutla başlatma ✅ · BL/BZ ✅ · plandan tikleme ✅ ·
> kredi yükü mevzuatı ✅ (MADDE 17 doğrulandı)
> **Faz 12'de kapananlar:** kalan GNO eşikleri ✅ (1.1) · "başvurabilir miyim"
> ekranı ✅ (1.3) · telefon düzeni ✅ (4.1) · nöbeti arayüzden yönetme ✅ (4.3) ·
> 2 çözülemeyen önşart ✅ (3.x) · "şartlı başarmış"ın şartı bulundu ✅ ·
> Gece Şeması tasarımı ✅

Sıralama tahmine değil, iki ölçüte dayanıyor: (a) kayıt gününde işe yarar mı,
(b) yanlış cevap verme riski taşıyor mu. İkisi de "hayır" olan iş listede
aşağıda.

Zorluk: **S** birkaç saat · **M** bir gün · **L** birkaç gün.

---

## 1. Şimdi sıradakiler

### 1.1 ~~Kalan iki GNO eşiğini doğrula~~ · ✅ **Faz 12'de kapandı**
22.08.2026'da ÇAP/Yandal Yönergesi ve Yönetmelik MADDE 20/31 okundu. İki
varsayım da **doğruymuş**, ayrıca beş eşik daha bulundu:

| Değer | Durum |
|---|---|
| Dönem kredi yükü (13–22 / 25 / 3.00) | ✅ MADDE 17 |
| Bitirme kredi eşiği (95) | ✅ |
| Not ölçeği (artılar dahil) | ✅ MADDE 20 |
| ÇAP başvuru GNO **3.00** | ✅ Madde 15 |
| ÇAP devam GNO **2.50** (*bir kez* düşülebilir) | ✅ Madde 19/k |
| ÇAP mezuniyeti: üniversite 2.50 + ikinci anadal 2.00 | ✅ Madde 18 |
| Yandal başvuru 2.50 · kayıt silme 2.00 | ✅ Madde 22/a, 27/c |
| Mezuniyet GNO **2.00** | ✅ MADDE 31/1 |
| "Şartlı başarmış" (DC+…DD) şartı | ✅ **bulundu**: mezuniyette GNO ≥ 2.00 |

Kalan tek belirsizlik mevzuatta değil, **veride**: ÇAP başvurusundaki
"anadal başarı sıralamasında üst %20" şartı sıralama verisi gerektiriyor;
ne bizde var ne OBS'den çekiliyor. Başvuru ekranı bunu `—` ile
"buradan bakılamaz" diye gösteriyor.

### 1.2 Denklik keşfini genişlet · M
**Neden:** Faz 10 ad+kredi eşleşmesiyle aday buluyor. İki kaynak daha var ve
ikisi de daha güvenilir:

* **OBS'nin resmi denklik tablosu** — bu çift için boştu (D3) ama başka
  çiftler için dolu olabilir; `--all-programs` taramasıyla birlikte
  denklikleri de süpürmek mantıklı.
* **Çoklu kaynak denklikleri** — `{KIM 211E, KIM 212} → KIM 206` gibi. Motor
  bunu destekliyor (Faz 2), keşif henüz tek-kaynak arıyor.

### 1.3 ~~"Yandal/ÇAP'a başvurabilir miyim" ekranı~~ · ✅ **Faz 12'de kapandı**
`make basvuru` ve arayüzdeki "Başvurabilir miyim" bölümü. Şartlar üç değerli
işaretle (✓ / ✗ / **—** buradan bakılamaz), programlar kalan işe göre sıralı.

**Kalan iş burada:** ÇAP planı yalnız BLG için çekilmiş; diğer 126 program
"planı yok" listesinde. `make all-plans` (senin makinende çalışıyor) bunu
doldurur ve ekran anlamlı hâle gelir. Lisans planından tahmin **bilerek
yapılmıyor** — ÇAP planı lisansın küçük bir alt kümesi.

### 1.4 Yarıyıl tabanını öneri motoruna sok · M
**Neden:** Faz 13'te ikinci anadal yarıyıl tabanı (3'te başlayan 6, 5'te
başlayan 9 kredi) eklendi ama motor bunu bir **uyarı** olarak gösteriyor,
puanlamaya katmıyor. Gerçek veride önerilen program ikinci anadaldan 4 kredi
içeriyordu — taban 9. Yani motor, kabul edilemez bir programı en iyi program
diye öneriyor.

**Ne:** `recommend.py` puanlamasına "ikinci anadal kredisi tabanın altındaysa
ağır ceza" ekle; tabanı karşılayan program bulunamıyorsa bunu açıkça söyle
(*"bu dönem açık ÇAP derslerinden tabanı karşılayan çakışmasız program yok —
indirim talebi gerekebilir"*). Sert kısıt YAPMA: taban indirilebiliyor,
imkânsız görünen durum aslında çözülebilir olabilir.

### 1.5 ~~Yandal planlarını çek~~ · ✅ **Faz 16'da çözüldü**
Sorun OBS'de değil bizdeydi. Yandal programları lisans bölümlerinden bağımsız,
fakülte düzeyinde tanımlı ve kodları farklı: `ECN_YD`, `BHB_YD`, `SUS_YD`.
Tarayıcı `f"{program}_LS"` tahmin ediyordu — yanlış soru.

Kademeli menü (fakülte + plan tipi) doğru kodları veriyor. O adım "atlanabilir"
diye işaretliydi ve hiç çağrılmamıştı; içindeki parametre adı da yanlıştı
(`akademikBirimId`, doğrusu **`birimId`**). Kullanılmayan yol, test edilmemiş
yoldur.

```bash
make kesif T=yandal ARGS=--planlar   # tanı
make all-plans                       # artık yandalı da çekiyor
```

**Kalan:** `make all-plans` bir kez çalıştırılıp katalog yeniden yayınlanmalı.

## 2. Motorun bir sonraki sıçraması

### 2.1 Çok dönemli plan · L
**Neden:** Araç şu an **bu dönemi** planlıyor. "ÇAP kaç dönemde biter"
sorusuna kademe sayısıyla bir *alt sınır* veriyor ama bir *plan* vermiyor.
Kritik yol zaten hesaplanmış; eksik olan ileriye doğru yerleştirme.

**Ne:** N dönem ileri planla: her dönem kredi tavanına uy, önşartları sırala,
kredi eşiklerini (bitirme 95) doğru döneme koy, arzı bilinmeyen dersler için
"açılırsa" senaryosu üret. Çıktı: dönem dönem tablo + "şu ders kayarsa
mezuniyet bir dönem öteleniyor" duyarlılık analizi.

**Uyarı:** Arz belirsizliği burada belirleyici — 14 ÇAP dersinden 11'i arz
sorunlu (Faz 5). Plan, veriden çok varsayıma dayanacak; bunu gizlememek gerek.

### 2.2 Tercih ağırlıkları · M
**Neden:** Motor "en yüksek puanlı çakışmasız program"ı buluyor ama senin
tercihlerini bilmiyor: sabah dersi istemiyorum, Cuma boş olsun, şu hoca,
kampüs değişimi olmasın.

**Ne:** `config/tercihler.toml` ile beyan edilen yumuşak ağırlıklar; puanlamaya
eklenir, sert kısıt olmaz. Arayüzde kaydırıcı olabilir.

### 2.3 Yaz okulu · M
**Neden:** Alttan ders taşıyan ÇAP öğrencisi için yaz okulu en önemli
tıkanıklık çözücü. Şu an dönem kavramı Güz/Bahar varsayıyor.

**Ne:** `term` kodunda yaz dönemini tanı, kredi tavanını ayrı al, "bunu yazda
alırsan şu zincir bir dönem kısalır" analizi.

---

## 3. Veri kalitesi

Her biri `make refresh` kalite raporunda görünüyor; hiçbiri hata değil ama
her biri motorun bir köşesini kör bırakıyor.

| İş | Etki | Zorluk |
|---|---|---|
| ~~**2 çözülemeyen önşart**~~ · ✅ **Faz 12** — ikisi de önşart değilmiş (katalogda ders adı / dil yazılmış); `[[onsart_beyani]]` ile kapandı | 0 çözülemeyen önşart kaldı | — |
| **275 önşart hedefi katalogda yok** — kapatılmış dersler; "sağlanamaz" mı "yok say" mı karar ver | yanlış tarafa kararsa ders elenir ya da yanlışlıkla açılır | M |
| **254 havuz etiketi `OTHER`** — kategori eşlemesi | ilerleme panelindeki kategori sayaçları eksik | M |
| **1396 havuz seçeneğinin ders karşılığı yok** | seçmeli havuzda görünmeyen alternatifler | M |
| **43 boş seçmeli havuz** (11'i grupId'li = parse hatası) — `--all-programs` sonrası ortaya çıktı | başka bölümlerin havuzları; seni etkiliyorsa `make plan-info` ile bak | M |
| **`plan_host_program` boş** — OBS'den çekilmeli; `make verify` bu yüzden kırmızı | ÇAP planının doğru plan olduğu doğrulanamıyor | S · **OBS gerekir** |
| **Resmi denklik yok** (D3) — bu çiftte OBS'de yayınlanmamış | Faz 10 keşfi ad+krediden aday üretiyor; resmi kaynak hâlâ boş | — · **OBS'ye bağlı** |

---

## 4. Kullanım kolaylığı

### 4.1 ~~Telefonda okunabilirlik~~ · ✅ **Faz 12'de kapandı**
700px altında ızgara yerini gün gün dikey listeye bırakıyor; aday tablosu
iki sütun düşürüyor. ★ Listenin çakışmayı göstermeme zayıflığı çözüldü:
kesişen dersler ayrıca hesaplanıp kırmızıyla işaretleniyor.

### 4.2 Nöbeti arka planda çalıştırma · S
`make watch` bir terminal penceresi işgal ediyor. macOS `launchd` ile arka
planda çalışan bir servis, bilgisayar açıldığında kendiliğinden başlar.

### 4.3 ~~Nöbeti arayüzden yönetme~~ · ✅ **Faz 12'de kapandı**
Ders diyaloğunda "Kontenjanı izle", darboğaz raporunda kısa "izle". Düğme
yalnız **arz sorunlu** derste var — önşarta takılan ders nöbetle çözülmez.

---

## 4.4 ~~Yayın~~ · ✅ **Faz 14'te kapandı** — statik site

Motor **JS'e çevrilmedi**, Python tarayıcıya taşındı (Pyodide). Tek kod
tabanı, 433 test web sürümünü de kapsıyor, iki sürüm ayrışamaz.

```bash
make site                              # yerelde kur ve dene
make refresh && gh release create katalog-$(date +%Y%m%d) data/reference.sqlite3
# GitHub -> Actions -> "pages" -> Run workflow
```

Ziyaretçinin notları tarayıcısında (IndexedDB) kalıyor; sunucu, uç, telemetri
yok. Yayınlanan tek veri herkese açık katalog — **tutulacak kişisel veri
üretilmiyor**, KVKK'da veri sorumlusu olunmuyor.

**Kalan:** çok kullanıcılı sunucu (C yolu) hâlâ bilerek yapılmıyor —
başkalarının notlarını tutmak, karşılığında bir şey kazandırmadan sorumluluk
yükler. Statik site aynı işi sıfır riskle görüyor.

## 5. Bilerek yapılmayanlar

Bunlar "unutuldu" değil, **karar**:

* **OBS'ye otomatik kayıt.** Araç asla senin adına ders kaydı yapmayacak.
  Şifre istemiyor, oturum açmıyor. Kayıt kararı ve tuşa basma sende.
* **Notları buluta koymak.** `data/` altındaki her şey kişisel veri; klasörün
  tamamı `.gitignore`da. Yerel sunucu yalnız `127.0.0.1`'e bağlanıyor ve öyle
  kalacak. Araç herkese açılabilir (bkz. 4.4) ama **notlar hep kullanıcının
  kendi makinesinde/tarayıcısında** kalmalı.
* **Başka öğrencilerin verisi.** Tek kullanıcılık bir araç; çok kullanıcılı
  yapmak gizlilik yüzeyini büyütür, karşılığında bir şey kazandırmaz.
* **Tahmini GNO'yu resmi gibi göstermek.** Hesap transkriptinden çıkıyor ve
  "tahmini" etiketiyle duruyor; OBS'nin sayısı esas.
* **Denkliği otomatik uygulamak.** Ad eşleşmesi zayıf bir sinyal ("Fluid
  Mechanics" adını 17 ders taşıyor). Yanlış denklik, tamamlamadığın şartı
  tamamlanmış gösterir. Öneri otomatik, **uygulama senin tıkın**.

---

## 6. Bakım notları

* `make refresh` her çalıştığında bir **anlık görüntü** bırakıyor (son 12).
  Kayıt haftasında günde birkaç kez çalıştırmak `make changes`'i anlamlı kılar.
* `make test` 400 test + gizlilik denetimi. Playwright kuruluysa tarayıcı testleri de koşar,
  değilse atlanır — proje bağımlılığı değil.
* `make all-plans` dönemde bir kez yeter — 128 program, ~1081 plan, dakikalar
  sürüyor. Program değiştirmeyi düşünmüyorsan gerekmez.
* `make watch` kayıt haftasında açık bırakılacak şey; `watch_courses` ile
  birkaç derse daraltmadan kullanma, bildirim gürültüye döner.
* `config/` altındaki üç dosya elle düzenlenebilir ve **yorumları korunur**:
  `settings.toml` (kim/hangi program/hangi dönem), `kurallar.toml` (mevzuat
  eşikleri), `denklikler.toml` (elle denklik ve muafiyet beyanı).
* Ölçüme dayalı kararların gerekçesi `docs/` altındaki faz belgelerinde.
  Bir kuralı değiştirmeden önce oraya bak — çoğu, gerçek veriyle
  karşılaştırma sonucu düzeltilmiş bir varsayım.
