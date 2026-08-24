# Kalan eksikler ve geliştirilmesi gerekenler

24.08.2026, **Faz 27 sonrası**. A–D bölümleri bitti
(`docs/faz25-ders-secim-araci.md`), ilk 30 saniye elden geçti
(`docs/faz26-ilk-30-saniye.md`), **arayüz listesinin (§3) tamamı ve tercih
ağırlıkları (§2.2) bitti** (`docs/faz27-arayuz.md`).

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

### 1.3 `class_restr` sütunu tamamen boş · **S (ölçüm)**
3417 şubenin **hiçbirinde** dolu değil. Ya OBS artık yayınlamıyor ya da
tarayıcı okumuyor. Bilmeden bırakmak, ileride "sınıf kısıtı yok" diye
yanlış bir sonuca götürebilir.

**Ne:** bir OBS sayfasında elle bak; kaynakta yoksa sütunu kaldır ya da
"kaynak yayınlamıyor" diye işaretle.

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

---

## 3. ~~Arayüzde sırada ne var~~ · ✅ **Faz 27'de tamamı kapandı**

3.1 puan kırılımı ✅ · 3.2 yazdırma ✅ · 3.3 klavye ✅ · 3.4 karşılaştırma ✅

Bu bölümün yerine gelen yeni fikirler:

### 3.5 Tercih karşılanamıyorsa NE BIRAKMALI · **M**
Faz 27'de ölçüldü: "Pzt + Cuma boş" istendiğinde motor ikisini birden
sağlayamıyor ve −10 farkla en yakınını sunuyor. Doğru davranış ama
kullanıcıya *"neyi bırakırsan olur"* denmiyor.
**Ne:** "ITB 037E'yi çıkarırsan Cuma boşalıyor" gibi tek adımlık öneri.

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
| "Bu dersin ortalaması AA" / geçme oranı | Elimizde böyle bir veri yok |
| Hoca puanı / yorumu | Kaynak yok; olsa da kişiselleştirilmiş bir iddia olurdu |
| "GNO'n şu kadar olur" tahmini | Alacağı nottan bağımsız bir sayı üretmek olurdu |
| Otomatik OBS kaydı | Baştan beri sınır: araç senin yerine kayıt YAPMAZ |
| Kredi aralığını tek sayıya indirmek | Faz 23'te bilerek reddedildi |
| Yarıyıl tabanını "indirimli" varsaymak | Yönerge "düşürülebilir" diyor: talep + koordinatör + FYK |
| **Yeni:** nöbet aralığını 1 dk'nın altına indirmek | İTÜ sunucularını yormak; kayıt kipi zaten 1 dk ve 2 saatle sınırlı |
| **Yeni:** `.ics` dosyasına kesin tarih yazmak | Akademik takvim elimizde yok; tahmini tarihi kesinmiş gibi sunmak olurdu |
| **Yeni:** plan dışı dersi ilerleme yüzdesine katmak | Alınmamış bir şartı alınmış saymak — projenin en pahalı hatası |
