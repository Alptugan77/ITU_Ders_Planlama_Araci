# Yapılacaklar

Faz 1–27 bitti (834 test). Depo GitHub'a hazır; statik site yayında. Bu liste **sonrası** için: ne kaldı, neden önemli,
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
> **Faz 14'te kapananlar:** statik site (Pyodide) ✅ (4.4)
> **Faz 15'te kapananlar:** meşgul saatler ✅ · eksik ÇAP planları ✅ ·
> haftalık programın yeri ✅
> **Faz 16'da kapananlar:** yandal programları — fakülte düzeyinde ✅ (1.5)
> **Faz 17'de kapananlar:** 85 ÇAP planında kaybolan 435 ders satırı ✅ ·
> kademelerde önşart bağları ✅ · sessiz satır düşüşü için kalıcı kontrol ✅
> **Faz 18'de kapananlar:** varsayılan kip "N. dönem + alttan" ✅ ·
> başvuru bölümü pencereye indi ✅ · bölüm çubuğu ✅
> **Faz 19'da kapananlar:** yandal sayfa düzeni ✅ (yardımcı tablolar zorunlu
> ders sanılıyordu) · eski düzende TR/EN çift sayımı ✅ · kredi çapraz
> kontrolü ✅ · `plan_host_program` doldu ✅
> **Faz 20'de kapananlar:** başlıkta ÇAP yok ✅ · üst çubuk opak ✅ ·
> kademeler aşağı doğru ✅ · kaydedilen program en üstte ✅ · kredi tavanı
> GNO'dan otomatik ✅ · planı olmayan bölüm listede yok ✅ · BLG/BLGE tek ✅
> **Faz 21'de kapananlar:** ÇAP ve yandal AYNI ANDA ✅ (1.6) · eşikler kapsam
> taşıyor ✅ · yarıyıl tabanı yalnız ÇAP'ta ✅ · yandala ayrı renk ✅
> **Faz 22'de kapananlar:** ★ veri kaybı (WAL) ✅ · CRN'den program yükleme ✅ ·
> yarıyıl tabanı motorun puanlamasında ✅ (1.4)
> **Faz 23'te kapananlar:** kategori etiketleri 1236→26 ✅ · kredi ARALIK
> olarak saklanıyor ✅ · boş havuzun sebebi yazıyor ✅ (§3)
> **Faz 24'te kapananlar:** ★★ ilk giren herkes geliştiricinin raporunu
> görüyordu ✅ · ★★ ilk kaydetme `settings.toml`'u bozup uygulamayı
> kilitliyordu ✅ · bölüm kutusu "AIN"de açılıyordu ✅ · transkriptsizken
> tavan/eşik/gizlilik iddiaları ✅ · karşılama kartı ✅ · aday tablosunda
> arama ✅ · `hidden` gerçekten gizliyor ✅
> **Faz 25'te kapananlar:** çevrimiçi ders ✅ · doluluk çubuğu ✅ ·
> "açtıkları" listesi ✅ · ★ PLAN DIŞI ders ekleme ✅ · yedek plan ✅ ·
> takvime aktar (.ics) ✅ · paylaşılabilir bağlantı ✅ · hocaya göre arama ✅ ·
> kayıt öncesi kontrol ✅ · kayıt günü nöbet kipi ✅ · arz uyarısı üstte ✅ ·
> ★★ bozuk ayar dosyası + kapalı döngü ✅ · geri al ✅ · verinin yaşı ✅ ·
> kendi kendini denetleyen tur ✅
>
> **Faz 26'da kapananlar:** "tek adımda başla" ✅ · tek birincil eylem ✅ ·
> eylem adları ("Aç" değil) ✅ · sırası gelmemiş adım kapalı ✅ ·
> ★★ transkriptsizken "%0 tamamlandı" iddiası kalktı ✅ · başlık altı önce
> aracı tanıtıyor ✅ · "şimdilik böyle kalsın" ✅ · kurulum sonrası
> "şimdi ne yapabilirsin" ✅ · telefonda adım satırı ✅
>
> **Faz 27'de kapananlar:** ★★ tercih ağırlıkları ✅ (§2.2) · "neden bu
> puan" kırılımı ✅ (§3.1) · yazdırma düzeni ✅ (§3.2) · klavye ✅ (§3.3) ·
> önerileri yan yana karşılaştır ✅ (§3.4)
>
> ➜ Kalan eksikler: **`docs/fikirler.md`**
> ⚠️ **Depoda `git remote` YOK** — 27 commit yerelde, site Faz 23'ten kalma.

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

### 1.4 ~~Yarıyıl tabanını öneri motoruna sok~~ · ✅ **Faz 22'de kapandı**
`build_schedules(..., floors={"CAP": 9})`. Tabanı karşılayan program öne
geçiyor, karşılamayan **elenmiyor** (taban indirilebiliyor, ayrıca o dönem
açılan ders yetmiyor olabilir), her önerinin yanında `floorGaps` var ve hiçbiri
karşılamıyorsa arayüz bunu açıkça söylüyor.

Gerçek veride ölçüldü: taban 9 iken en iyi programda **4 ÇAP kredisi** vardı —
artık bu yazıyor.

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
| ~~**havuz etiketi `OTHER`**~~ · ✅ **Faz 23** — ölçüldü: 1236 slotun 1210'unda kaynakta kategori YOK, düzeltilebilir olan 26. Uyarı ikiye ayrıldı | kategori sayaçlarındaki boşluk artık açıklanıyor | — |
| **1396 havuz seçeneğinin ders karşılığı yok** | seçmeli havuzda görünmeyen alternatifler | M |
| ~~**85 ÇAP planında 435 satır kayıp**~~ · ✅ **Faz 17** — iki dilli kod hücresi; `dropped_plan_rows` kontrolü artık kalıcı bekçi | plan "5 ders" görünüyordu | — |
| **13 boş seçmeli havuz** — Faz 23'te sebep ayrıştırıldı (`pool_status`): OBS'nin tablosuz sayfa döndürdükleri bizim hatamız değil. Yeniden taramadan sonra gerçek parse hatası kalırsa o bakılır | başka bölümlerin havuzları | S |
| ~~**`plan_host_program` boş**~~ · ✅ **Faz 19** — yandal sayfalarında tablonun `id` niteliği yoktu, başlıktan tanınıyor | ÇAP planının doğru plan olduğu doğrulanabiliyor | — |
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
* `make test` 932 test + gizlilik denetimi (penetrasyon testi dahil). Playwright kuruluysa tarayıcı testleri de koşar,
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
