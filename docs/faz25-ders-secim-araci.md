# Faz 25 — normal bir ders seçim aracı

> Kullanıcı isteği, 24.08.2026: *"D ve D'ye kadar olan kısmı entegre
> edebilirsin"* — `docs/fikirler.md` içindeki A, B, C ve D bölümleri.

Faz 24 aracı **kullanılabilir** hale getirdi (ilk giren kişi çıkmaza
düşmüyor). Faz 25 onu **işe yarar** hale getiriyor: kayıt haftasında
gerçekten yapılan işler.

Testler **724 → 782**.

---

## A. Veri elimizdeydi, arayüzde yoktu

Üç şey OBS'den çekiliyor, veritabanında duruyor, motorda taşınıyor ve
kullanıcı hiç göremiyordu.

### A1. Çevrimiçi ders
`lesson.teaching_method` 3417 şubenin **hepsinde** dolu; **139'u**
`Virtual (Online)`. Artık aday satırında ve şube seçme penceresinde rozet.

⚠️ Yan etki daha önemli: `Section.campuses()` çevrimiçi şubede artık **boş**
dönüyor. Kayıtlı bir dersliği olsa bile öğrenci oraya gitmiyor; kampüs
değişimi saymak **var olmayan bir yolculuk uydurmaktı** — ve araç bu sayıyı
program sıralamasında ölçüt olarak kullanıyor.

### A2. Doluluk çubuğu
`0/240` ile `18/18` arasındaki farkı görmek için hesap yapmak gerekiyordu.
Artık çubuk + "N boş" / "dolu", son üç kişide sarı, dolunca kırmızı.

⚠️ Kontenjanı **0 ilan edilmiş** şubede oran uydurulmuyor ("kontenjan yok").
Sayının yanında tazeleme tarihi duruyor.

### A3. "Açtıkları"
"119 dersin önşartı" bir sayı; ikna edici olan liste: *bunu almazsan şu 4
ders kapalı kalır.* Yalnız **senin planındaki**, **henüz geçmediğin** dersler.

★ İlk ölçümde kesişim **sıfır** çıktı: plan `BLG 355` yazıyor, önşart ağacı
`BLG 355E`. `plan_slot.alt_course_codes` bu eşi taşıyor ama 41480 slotun
yalnız **667**'sinde dolu. Katalogda **gerçekten var olan** dil eşi de
ekleniyor — ölçüm: 2809 E/TR çiftinin **2807**'sinde kredi ve AKTS birebir
aynı, aynı ders olduklarının kanıtı. Çıktıda dil çifti tekleştiriliyor
(`MAT 201` + `MAT 201E` = tek ders, iki değil).

---

## B. Normal ders seçim aracı eksikleri

### B1. ★ Plan dışı ders ekleme
Araç bugüne kadar **yalnız planındaki** dersleri ekletiyordu. Oysa normal bir
ders seçim aracının asıl sorularından biri: *"şu dersi programıma
sığdırabilir miyim?"* — başka bölümün dersi, serbest seçmeli, ya da sırf
merak edilen bir ders.

`/api/katalog` (kod/ad araması, iki dilde) + `/api/ders` (şubeler). Sonuç
CRN yoluyla **aynı biçimde** dönüyor: arayüzün tek bir ekleme yolu var
(`injectSections`), iki ayrı biçim zamanla ayrışan iki ayrı hata demekti.

⚠️ **Plan dışı ders hiçbir slotu doldurmuyor** (`slotId: 0`, `pool: ""`).
Kredisi dönem yüküne ve çakışma denetimine girer — kayıtta da öyle — ama
ilerleme yüzdesine girmez. Ve özet satırı bunu **açıkça yazıyor**:

> 4 ders · 12 kredi · 17 AKTS · **bunun 3 kredisi plan dışı — yüke sayılır,
> şart doldurmaz**

Sessiz kalmak, kullanıcının "%43 → %50 olmalıydı" diye düşünmesine yol
açıyordu.

★ Yan bulgu: `dispatch` her uçtan sonra `snapshot()` çağırıp **bütün raporu**
yeniden kuruyordu — ölçüldü, tek çağrı **~1.5 sn**. Harf başına arama yapan
bir uç için kullanılamaz. `READ_ONLY_PATHS` + 220 ms bekleme ile arama
0.9 sn'ye indi.

### B2. Yedek plan
Eskiden yalnız "öbür CRN'ler" listeleniyordu; hangisinin çakıştığı, nerede
yer kaldığı yazmıyordu. Artık her yedek şube için **çakışma** ve **boş yer**,
çakışmayanlar önde. Seçtiğin şubelerden biri doluysa bölüm açık geliyor.

### B3. Takvime aktar (.ics)
Tamamen tarayıcıda üretiliyor; hiçbir yere veri gitmiyor.

⚠️ Akademik takvim (dönem başı, tatiller, telafi) bu araçta **yok**.
Tarihler önümüzdeki pazartesiden başlatılıyor, tekrar **15 haftayla**
sınırlı ve bunun bir **tahmin** olduğu dosyanın içinde yazıyor. Saati ilan
edilmemiş ders sessizce düşmüyor — söyleniyor.

### B4. Paylaşılabilir bağlantı
`#crn=10493,10711,…` — açan kişi aynı ızgarayı görüyor.

✔ **Gizlilik**: bağlantıda yalnız CRN var. Not, transkript, bölüm —
hiçbiri girmiyor. Bu kullanıcıya da yazılıyor, çünkü *"programımı paylaşınca
notlarım da gider mi"* haklı bir soru. Bağlantıdaki bulunamayan CRN sessizce
atılmıyor.

### B5. Hocaya göre arama
Aday araması hoca adını da kapsıyor (2530 şubede gerçek ad var).

---

## C. Kayıt gününe hazırlık

### C1. Kayıt öncesi kontrol
Araç bu bilgilerin **hepsini** zaten biliyordu ama beş ayrı bölüme
dağılmıştı. Artık "Kayıt günü" penceresinin başında tek liste:

| | |
|---|---|
| ✓ | Kredi tavanı · 9 / 22 kredi |
| ✓ | Çakışma yok · temiz |
| ✓ | Kontenjan · 3 şubede yer var (24.08.2026 02:52) |
| — | İkinci anadal tabanı · başlangıç yarıyılı beyan edilmedi |
| ✓ | Her dersin CRN'i var · 3 CRN |

⚠️ Üç durumlu. **"—" = buradan bakılamaz, "sağlandı" DEĞİL.**

### C2. Kayıt günü nöbeti
`make watch ARGS="--kayit"` → 1 dk aralık, **2 saat sonra kendiliğinden
durur**.

⚠️ Sınırı topluca düşürmek İTÜ sunucularını gereksiz yormak olurdu. Kip
**açıkça** isteniyor, uyarı basıyor ve süresi bitince **neden** durduğunu
yazıyor — sessizce durmak "nöbet çöktü" dedirtir.

### C3. "Bu dönem açılmamış" uyarısı
Darboğaz bölümü sayfanın aşağısındaydı. Planındaki bir ders bu dönem
açılmadıysa bu, kayıt gününden **önce** bilinmesi gereken bir şey: mezuniyet
planını değiştirir. Uyarı haftalık programın üstüne çıktı.

⚠️ "Açılmayacak" demiyor — dönem başında ilanlar kademeli yayınlanıyor.
"Şu ana kadar ilan edilmemiş" + tazeleme tarihi.

---

## D. Güven ve doğruluk

### D1. ★★ Bozuk ayar dosyası ve kapalı döngü
Faz 24'te *yazıcı* hatası düzeldi ama **elle** bozulmuş bir dosya hâlâ her
isteği ham bir `tomllib` hatasına çeviriyordu — uygulama hiç açılmıyordu.

Şimdi sayfa **açılıyor**, hatayı ve satırını tepede yazıyor, varsayılana
düşüyor. ⚠️ Sessizce yok saymak değil: yanlış ayarla çalışmak,
çalışmamaktan kötü.

Ama asıl bulgu ikincisiydi: yazıcı satır bazlı çalıştığı için **bozukluğu
olduğu gibi koruyordu**. Kullanıcı hatayı görüyor, "Program"dan yeniden
seçiyor, **aynı hatayı yine görüyordu** — kapalı bir döngü. Yazıcı artık
ürettiği metni doğruluyor:

* girdi zaten bozuksa → `.bozuk` uzantısıyla **yedekle**, temiz dosya yaz
  (silmiyoruz: içinde kullanıcının notları olabilir),
* girdi sağlamken çıktı bozuksa → hata **bizde**, dosyaya **dokunma**.

### D2. Geri al
"Öneriye dön" tüm programı siliyordu: bir hatayı düzeltmek için bütün emeği
silmek gerekiyordu. Artık düğme + `Ctrl/Cmd+Z`.

⚠️ Yığın seçimin **tamamını** saklıyor, "şu dersi geri koy" değil: bir ders
eklemek çakışan başkalarını da çıkarabiliyor (havuz kuralı, saat çakışması);
tek dersi geri koymak onları geride bırakırdı. Kip değişince yığın
temizleniyor — her kipin kendi aday havuzu var.

### D3. Verinin yaşı
`generatedAt` sayfanın üretildiği an; kontenjan **son tazelemeye** ait. İkisi
günlerce ayrışabiliyor. Artık başlıkta ayrı satır, 2 günden eskiyse sarı.

⚠️ Damga yoksa "bugün" varsaymıyor. "bugün/dün" **takvim günü** demek:
dün 12:50'de tazelenen veri 13 saat sonra hâlâ "bugün" görünüyordu.

### D4. Kendi kendini denetleyen tur
Faz 24'teki iki kilitleyici hata kod okuyarak değil, **boş bir kurulumu
gerçekten çalıştırınca** çıktı. O yürüyüş artık test:

* boş kurulumun sayfası **ayrı bir süreçte** üretiliyor — bu depoda
  `config/settings.toml` **var** ve testin içindeki modüller onu görüyor;
  Faz 24'teki hata tam da *"geliştiricinin dosyası varken sorun görünmüyor"*
  hatasıydı;
* tarayıcıda açılıyor: sayfa hatası **yok**, karşılama kartı görünür, rapor
  gizli, `[hidden]` olup da görünen öğe **yok**.

---

## Doğrulama

Boş kurulumdan başlayıp hepsine dokunan tur (`/tmp/fresh/dogrula.py`):

```
KURULUM  hero gizli: True
A  doluluk çubuğu: 26
A  veri yaşı     : şube/kontenjan verisi dün tazelendi (23.08.2026 12:50)
B1 katalog      : ['ITB 205E', 'MUZ 487', 'MUZ 497', 'SNT 226E']
B1 özet         : 4 ders · 12 kredi · bunun 3 kredisi plan dışı — yüke
                  sayılır, şart doldurmaz
D2 geri al      : Geri al: MUZ 487 eklendi
C1 kontroller   : ✓ Kredi tavanı · ✓ Çakışma yok · ✓ Kontenjan · ✓ CRN
B4 bağlantı     : …/#crn=12554,10660,10689
B3 ics          : indi
SAYFA HATASI    : []
```

Bozuk `settings.toml` ile: sayfa açılıyor, hata yazıyor, **Program**'dan
yeniden seçince düzeliyor ve `settings.toml.bozuk` yedeği kalıyor.
