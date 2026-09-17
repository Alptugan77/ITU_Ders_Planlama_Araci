# Kalan eksikler ve geliştirilmesi gerekenler

> **Faz 37'de kapananlar (02.09.2026):** §1.3 `class_restr` ölçümü ✅ ·
> §3.5 "tercih karşılanamıyorsa ne bırakmalı" ✅ · F.2 yeniden ölçüldü ✅
> — ve ölçüm sırasında **yeni bir kör nokta** çıktı: katalogdaki kredi
> koşulu (`course.class_restriction`) motorda hiç kullanılmıyordu, 498
> dersin 325'i görünmüyordu. Ayrıca `KREDI_ESIGI` engeli komut satırı
> raporunda **sessizce düşüyordu**. Ayrıntı:
> `docs/faz37-katalog-kredi-kosulu.md`.

> **Faz 38'de kapananlar (02.09.2026):** ★★ ders **not dağılımı** —
> "elimizde böyle bir veri yok" gerekçesi düştü, kaynak bulundu ve entegre
> edildi ✅ · ★★ `config.donem_adi` **bir yıl kaymıştı** (`202610` =
> 2025-2026 Güz, 2026-2027 değil) ✅ · planlanan dönem bitmişse uyarı ✅ ·
> yaz dönemi verisi (§2.3 için hammadde) ✅.
> Ayrıntı: `docs/faz38-not-dagilimi.md`.

24.08.2026, **Faz 28 sonrası**. A–D bölümleri bitti
(`docs/faz25-ders-secim-araci.md`), ilk 30 saniye elden geçti
(`docs/faz26-ilk-30-saniye.md`), **arayüz listesinin (§3) tamamı ve tercih
ağırlıkları (§2.2) bitti** (`docs/faz27-arayuz.md`), **ilk kullanıcı
incelemesinin tamamı (A1–A5, B1–B5, C1–C8, D1–D3, E) kapandı**
(`docs/faz28-sessiz-kayiplar.md`).

Faz 28'de incelemeyi kapatırken **yedi hata** çıktı; en ağırı şuydu: OBS'deki
205 program kodunun 78'i alt çizgi taşıyor ve hepsi yandal — kayıt kodu
temizleyicisi alt çizgiyi siliyordu, yani **kutudan seçilen her yandal
sessizce yok oluyordu**. Ayrıntısı faz belgesinde.

Bu liste **bundan sonrası**. Hepsi ölçülmüş: "şu veri var / şu kadar eksik"
dediğim yerde kataloğa bakıp saydım.

**S** birkaç saat · **M** bir gün · **L** birkaç gün.

---

## 0. Önce bunlar — kod değil, senin yapman gerekenler

Bunlar tek satır iş ama araç bunlar olmadan başkasına ulaşmıyor.

| Ne | Neden |
|---|---|
| ★★ `git remote add origin …` + `git push -u origin main` (**27 commit**) | **Depoda uzak sunucu TANIMLI DEĞİL.** Yayındaki site Faz 23'ten kalma; Faz 24–26'nın hiçbiri orada yok |
| Depoyu herkese açık yap · Pages kaynağını GitHub Actions'a al | Site yayına ancak böyle çıkıyor |
| `make all-plans` yeniden | `credits_min/max` ve `pool_status` alanları eski taramada boş |
| `katalog-YYYYMMDD` release yükle | Statik site veriyi buradan çekiyor |

---

## 1. Bulunan ama kapatılmayan eksikler

Faz 25 sırasında ölçtüm, kapsam dışında kaldı.

### 1.1 `BLG 4901` / `BLG 492` — aynı ders, iki kod · **M**
"Açtıkları" özelliğini ölçerken çıktı: önşart ağacı bitirme çalışmasını
`BLG 4901` diye anıyor, BLG planı `BLG 492` yazıyor. Dil eşi kuralı bunu
yakalamıyor (biri öbürünün İngilizcesi değil, **eski/yeni kod**).

Sonuç: FIZ 102E'nin "açtıkları" listesi BLG öğrencisinde boş çıkıyor, oysa
gerçekte bitirme çalışmasını açıyor.

**Ne:** kod göçlerini (`X 4901` ↔ `X 492` gibi) ölç ve `config` içinde
beyan edilebilir bir eşleme tablosu yap.
⚠️ Otomatik tahmin **etme** — "aynı ders" iddiası yanlışsa ilerleme yüzdesi
bozulur. Beyan edilmiş eşleme + kaynak notu.

### 1.2 Anadal planı olmayan 81 bölüm · **L (tarama)**
`program` tablosunda 128 lisans programı var, **127**'sinin planı var —
yani anadal tarafı neredeyse tam. Ama `plan` tablosunda **208** farklı
program kodu geçiyor: ÇAP/yandal planları olan ama lisans planı çekilmemiş
bölümler var.

**Ne:** eksik lisans planlarını tara; olmuyorsa program seçme kutusunda
"planı yok" diye ayrı bir grupta göster (şu an hiç görünmüyorlar).

### 1.3 ~~`class_restr` sütunu tamamen boş~~ · ✅ **Faz 37'de kapandı**
Ölçüldü: itu-helper `lessons.psv` **11 alan** yayınlıyor
(`CRN|Kod|Yöntem|Hoca|Bina|Gün|Saat|Derslik|Kontenjan|Yazılan|Programlar`)
ve içinde ne sınıf kısıtı var ne önşart. Yani sütun boş değil, **kaynak
yayınlamıyor**. `lesson.class_restr` ve `lesson.prereq_raw` işaretlendi
(şema yorumu + `quality.kaynak_yayinlamiyor`), silinmedi.

★★ Aynı ölçüm çok daha büyük bir şey buldu: **`course.class_restriction`
sütunu boş değil ve adı yanıltıcı** — içindeki `95,00 / 60,00 / 30,00`
değerleri sınıf değil **kredi tabanı**, ve motor onları hiç okumuyordu.
498 dersin 325'i kör noktadaydı. `docs/faz37-katalog-kredi-kosulu.md`.

### 1.4 Kayıt günü nöbeti hâlâ elle başlatılıyor · **S**
`--kayit` kipi geldi ama nöbeti arka planda çalıştırma listede duruyor
(§4.2). Kayıt günü terminal açık tutmak gerekiyor.

---

## 2. Motorun sıçraması (eski liste, hâlâ geçerli)

### 2.1 Çok dönemli plan · **L**
Araç **bu dönemi** planlıyor. "ÇAP kaç dönemde biter" sorusuna kademe
sayısıyla bir *alt sınır* veriyor ama bir *plan* vermiyor.
⚠️ Arz belirsizliği belirleyici: 14 ÇAP dersinden 11'i arz sorunlu. Plan
veriden çok varsayıma dayanacak; bunu gizlememek gerek.

### 2.2 ~~Tercih ağırlıkları~~ · ✅ **Faz 27'de kapandı**
★★ İlk denemem çalışmadı ve bu öğreticiydi: tercihi ayrı bir sıralama
anahtarı yapınca HİÇBİR ŞEY değişmedi — `blocking_cost` float ve neredeyse
hiç eşitlenmiyor, ikinci anahtara sıra gelmiyordu. İkisi de "puan"
cinsinden olduğu için TOPLANINCA çalıştı.

### 2.3 Yaz okulu · **M**
Alttan ders taşıyan ÇAP öğrencisi için en önemli tıkanıklık çözücü. Dönem
kavramı şu an Güz/Bahar varsayıyor.

★ **Faz 38'de hammadde geldi:** not dağılımı ucu yaz dönemini de veriyor
(`202630 | Summer Semester`). Yani "bu ders yazın açılıyor mu, kaç kişi
aldı" sorusu artık VERİYLE cevaplanabilir — hangi dersin yaza bırakılabildiği
tahmin olmaktan çıkar. ⚠️ "Geçmiş yıl açıldı" ≠ "bu yaz açılacak".

---

## 3. ~~Arayüzde sırada ne var~~ · ✅ **Faz 27'de tamamı kapandı**

3.1 puan kırılımı ✅ · 3.2 yazdırma ✅ · 3.3 klavye ✅ · 3.4 karşılaştırma ✅

Bu bölümün yerine gelen yeni fikirler:

### 3.5 ~~Tercih karşılanamıyorsa NE BIRAKMALI~~ · ✅ **Faz 37'de kapandı**
`Schedule.pref_relief()` tek adımlık çare üretiyor: *"BHB 201E çıkarılırsa
istemediğin hoca kalmıyor (−3 kredi)"*. Kredi kaybı ve dersin zorunlu olup
olmadığı da yazıyor; zorunlu olmayan ve ucuz olan önde. "İstediğin hoca"
sayacını sıfıra indirmek çare sayılmıyor — o kazanç değil kayıp.

### 3.6 Tercihi kaydetmeden dene · **S**
Tercih değiştirmek için pencereyi açıp kaydetmek gerekiyor. Seçenek
değişirken sonucun canlı güncellenmesi, "hangi tercih neye mal oluyor"u
doğrudan gösterirdi.

---

## 4. Veri ve dayanıklılık

### 4.1 Tazeleme sırasında kısmi başarısızlık · **M**
`make refresh` bir adımda patlarsa ne kadarının güncellendiği belirsiz
kalıyor. Adım adım rapor + "şu kısım eski" işareti.

### 4.2 Nöbeti arka planda çalıştırma · **S**
(§1.4 ile aynı iş.) `launchd`/`systemd` birimi ya da `--daemon`.

### 4.3 Statik sitede veri tazeleme · **M**
Tarayıcıda OBS taraması yapılamıyor (CORS + `httpx`/`selectolax` yok).
Şu an site, yayına konan katalog dosyasıyla sınırlı. GitHub Actions ile
günlük otomatik release, siteyi kendiliğinden tazelerdi.

---

## Yapmamayı önerdiklerim (değişmedi)

Projenin ana kuralıyla çelişiyorlar: **bilinmeyeni bilinen gibi
göstermemek.**

| Fikir | Neden hayır |
|---|---|
| ~~"Bu dersin ortalaması AA" / geçme oranı~~ | ✅ **Faz 38'de yapıldı** — gerekçe ("veri yok") düştü: kullanıcı 02.09.2026'da `obs.itu.edu.tr/public/DersNotDagilimi`'yi hatırlattı. Veri herkese açık, tokensiz ve yaz dönemi dahil. **Ama puanlamaya girmiyor** (aşağıdaki satıra bak) |
| **Yeni:** not dağılımını öneri puanına katmak | Aracı "kolay ders bulucu"ya çevirirdi. Hangi dersin zorluğuna değdiği öğrencinin değer yargısı; motor onu yerine veremez. Gösteriyoruz, karar vermiyoruz |
| Hoca puanı / yorumu | Kaynak yok; olsa da kişiselleştirilmiş bir iddia olurdu. ⚠️ Faz 38'den sonra da geçerli: not dağılımı **ders** düzeyinde yayınlanıyor, hoca kırılımı YOK. Şubenin hocasıyla dersin dağılımını yan yana koymak, veride olmayan bir nedensellik iddia etmek olurdu |
| "GNO'n şu kadar olur" tahmini | Alacağı nottan bağımsız bir sayı üretmek olurdu |
| Otomatik OBS kaydı | Baştan beri sınır: araç senin yerine kayıt YAPMAZ |
| Kredi aralığını tek sayıya indirmek | Faz 23'te bilerek reddedildi |
| Yarıyıl tabanını "indirimli" varsaymak | Yönerge "düşürülebilir" diyor: talep + koordinatör + FYK |
| **Yeni:** nöbet aralığını 1 dk'nın altına indirmek | İTÜ sunucularını yormak; kayıt kipi zaten 1 dk ve 2 saatle sınırlı |
| **Yeni:** `.ics` dosyasına kesin tarih yazmak | Akademik takvim elimizde yok; tahmini tarihi kesinmiş gibi sunmak olurdu |
| **Yeni:** plan dışı dersi ilerleme yüzdesine katmak | Alınmamış bir şartı alınmış saymak — projenin en pahalı hatası |

---

## Faz 28'de eklenen kalemler

Bunlar incelemeyi kapatırken **ölçerken** çıktı; kapsam dışında bırakıldı.

### F.1 `ECN`, `SEC`, `VBA`, `YZV` — ÇAP planı var, program satırı yok · **S**
`plan` tablosunda bu dört kodun ÇAP planı var ama `program` tablosunda satırı
yok, `obs_program_ref` ve `plan_host_program` da tanımıyor. Arayüz şimdilik
dürüst davranıyor (`ECN — (adı katalogda yok)`), ama **doğru cevap muhtemelen
veride olmalı**.

**Ne:** `make all-plans` yeniden koşturulup bu dört kodun gerçekten mi yok
yoksa taramanın mı atladığı ölçülmeli.
⚠️ Adı **tahmin etme** — plan başlıkları (`TUMMUH_ECN ÇAP Programı`) ana
programı söylüyor, ikinci programın adını değil.

### F.2 Yerin ilan edilmediği %42 · **S (ölçüm)** — *02.09.2026'da yeniden ölçüldü*
3630 buluşmanın 1542'sinde bina `undeclared`. Arayüz artık "yer yok" diyor
ama bu oranın **dönem başında** mı böyle olduğu, yoksa kalıcı mı olduğu
bilinmiyor. Kayıt haftasına yakın tekrar ölçülmeli — kalıcıysa ızgaranın
yarısı yersiz kalacak ve "kampüs değişimi" tercihi de o kadar veriyle
çalışıyor demektir.

★ **Faz 37 ölçümü: 1542/3630 = %42.5 — bir hafta sonra DEĞİŞMEMİŞ.** Kalıcı
görünüyor. "Kampüs değişimi" tercihinin verisinin yarısı yok demektir; bunu
tercih ekranında yazmak gerekebilir.

### F.3 Kayıt 6,9 saniye sürüyor · **M**
ÇAP + yandal birlikte kaydedilince sunucu **her şeyi** baştan hesaplıyor.
Faz 28 bunu dürüstçe söylüyor (geçen süreyi yazıyor) ama süre değişmedi.

**Ne:** kısmi hesaplama — program değişince yalnız etkilenen paneli kur.
`READ_ONLY_PATHS` ile aynı fikir, bir adım ötesi.

### F.4 Kod göçü tablosu hâlâ yok · **M**
§1.1'in kardeşi. Faz 28'de plan slotlarını sayarken çıktı: **67 plan slotu**
katalogda karşılığı olmayan bir derse bakıyor (`ELH 212`, `BLG 211`, `ELE
321`…). Bunların bir kısmı kapanmış ders, bir kısmı kod göçü. Arayüz artık
"katalogda yok" diyor; hangisinin hangisi olduğunu söyleyemiyor.

### F.5 ★★ Yayın hattı çalıştırılmalı — düzeltmeler kullanıcıya ulaşmıyor · **S**
27.08.2026'da kullanıcı yayınlanan siteden *"ikinci program türü geçersiz"*
ekran görüntüsü gönderdi. O hatanın düzeltmesi **depoda duruyor**; site Faz
24'ten beri yayınlanmadı. Bu, listedeki en pahalı kalem: yapılan işin hiçbiri
kullanıcıya ulaşmıyor.

~~⚠️ Yayından önce `make all-plans` gerekiyor — depodaki katalogda hiçbir
yandal programı yok (76 `_YD` kodunun `program` satırı eksik).~~
✅ **Geçersiz (17.09.2026'da ölçüldü).** Katalogdaki 71 `_YD` kodunun
**71'inin de** `program` satırı var — eksik **0**. Bu uyarı yapılmış bir
işi yapılmamış gösteriyor ve yayını geciktiriyordu. Kalan tek eksik F.1'in
dört kodu (`ECN`, `SEC`, `VBA`, `YZV`).
