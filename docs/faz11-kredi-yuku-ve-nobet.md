# Faz 11 — MADDE 17, BL/BZ, plandan tikleme, kontenjan nöbeti

> ⚠️ Bu belgedeki bütün sayılar **örnektir**. Repoda kimsenin gerçek notu
> ya da ortalaması yer almaz — kişisel veri `data/` altında kalır ve
> `.gitignore` ile dışarıda tutulur.


```bash
make watch                   # kontenjan nöbeti
make app                     # "Plandan işaretle" · kredi yükü paneli · yedekten dön
./itucap.command             # macOS: çift tıkla
```

## ★ Yönetmelik MADDE 17 — tavan 35 değil, 25

Kullanıcı yönetmelik metnini verdi. Sonuç, aracın o güne kadar yaptığı en
somut düzeltme:

> (2) a) Daha fazla kredi almak isteyen öğrencilerden; **25 kredi de dahil**
> olmak üzere en az **2.25** ağırlıklı genel not ortalaması, **25 kredinin
> üzerinde** kredi almak isteyen öğrencilerden en az **3.00** aranır.

Örnek bir öğrencinin GNO'su **2.70** olsun. Yani:

| | |
|---|---|
| Ayarlı tavan (öğrenci beyanı) | **35 kredi** |
| Yönetmeliğin izin verdiği | **25 kredi** |
| 35'e çıkmak için gereken | GNO ≥ 3.00 |

Motor 35 krediye kadar program kuruyordu; o programlar **kayıtta
reddedilebilirdi**. Arayüz artık çelişkiyi kırmızı bir kutuda gösteriyor ve
tek tıkla düzeltiyor ("Tavanı 25'e çek"). Düzeltince motor anında yeniden
hesapladı: 16 ders, 22.5 kredi.

### İki fıkra AYRI şeyler söylüyor

Bu ayrımı kaçırmak kolay ve sonucu ağır:

* **(1)** bir **bant**: 13–22 kredi. Birinci yarıyıl, **ÇAP öğrencisi** ve son
  sınıf bu banttan **muaf**.
* **(2)** bandın üstüne çıkmanın **GNO şartı** — ve "her öğrenci" diyor.

Yani ÇAP öğrencisinin **alt sınırı yok** ama **üst sınırı GNO'suna bağlı**.
Muafiyeti tavana da uygulamak, öğrenciyi kayıtta reddedilecek bir programa
yönlendirirdi. Bir test tam olarak bunu kilitliyor
(`test_exemption_does_not_lift_the_ceiling`).

Kural yine `config/kurallar.toml`'da, `dogrulandi = true` — kaynak metin
kullanıcıdan geldi, bu sefer ⚠ yok.

## ★ MADDE 20 — tam not ölçeği (artı notlar)

Kullanıcı "BA+, BB+, CB+, CC+ gibi notlar da var" dedi. Yönetmeliği okudum
([MADDE 20](https://www.sis.itu.edu.tr/TR/mevzuat/lisans-yonetmelik.php)) ve
metin dörtten fazlasını söylüyordu — ölçek **0.25 adımlı** ve **altı** artı
not var:

| | | | | | | |
|---|---|---|---|---|---|---|
| AA | 4.00 | BB+ | 3.25 | CC+ | 2.25 | DD+ 1.25 |
| BA+ | 3.75 | BB | 3.00 | CC | 2.00 | DD 1.00 |
| BA | 3.50 | CB+ | 2.75 | DC+ | 1.75 | FF/VF 0.00 |
| | | CB | 2.50 | DC | 1.50 | |

Üç şey daha çıktı:

* **FD güncel ölçekte YOK.** Kodda vardı; eski transkriptlerde geçebildiği
  için tanınmaya devam ediyor ama yeni giriş listesinde önerilmiyor.
* **Muafiyet işareti `M`**, bizim kullandığımız `MU` değil. İkisi de kabul
  ediliyor — transkript hangisini yazarsa.
* **`T`** (dersten çekilme) ve **`E`** (tasarım projesi tamamlanmadı) hiç
  tanınmıyordu. İkisi de geçmez, ikisi de ortalamaya girmez.

### İki yerde desen kırıktı

Artı notu eklemek tek satırlık bir iş değildi:

1. **Transkript satırı** `[A-Za-z]{2}` arıyordu — `MAT 103E BA+` yazınca artı
   düşüyordu, sessizce `BA` kaydediliyordu.
2. **Önşart ayrıştırıcısı** not adlarını regex'e doğrudan gömüyordu. `+` bir
   regex metakarakteri: kaçırılmadan `BA+` deseni **"BAAA"** ile eşleşirdi.
   `re.escape` ve uzun-önce sıralaması şart.

### "Şartlı başarmış"

MADDE 20 iki başarı düzeyi tanımlıyor: **AA…CC "başarmış"**, **DC+…DD
"şartlı başarmış"**. Mezuniyette şartlı notların sayılması bir GNO şartına
bağlı — **bu şartı doğrulamadım**, o yüzden motor bir kural uygulamıyor;
yalnız hangi derslerin bu aralıkta olduğunu söylüyor.

★ Bir incelik: notu **girilmemiş** ders DD varsayılıyor (en kötü durum). Onu
"şartlı geçer" diye raporlamak, var olmayan bir sorun göstermek olurdu —
gerçek not girilince çoğu yukarı çıkacak. Rapor yalnız **gerçek** DD/DC
notlarını sayıyor.

## ★ BL / BZ — 0 kredili derslerin başarı sistemi

0 kredili dersler (staj, danışmanlık, seminer) harf notu almıyor:
**BL** = başarılı, **BZ** = başarısız.

İki eksik vardı:

* `BZ` arayüzün not listesinde **yoktu** — girilemiyordu.
* `BZ` GNO'dan **dışlanmıyordu**; 0.00 olarak ortalamaya giriyor ve GNO'yu
  haksız yere düşürüyordu.

Üçü de (BL, BZ, MU) artık GNO dışında. Kritik ayrım: `GRADE_POINTS` içindeki
`BL = 1.0` **önşart** karşılaştırması için — staj önşartı açılabilmeli. GNO
başka bir bağlam; ikisi karışırsa ya ortalama şişer ya önşart kapanır.

## ★ Plandan tikleme

60+ dersi tek tek aramak işkenceydi. Plan zaten elimizde: dönem dönem
listeleniyor, tik atılıyor, not seçiliyor.

```
1. DÖNEM
  ☑ GEO 101E  Intro. to Info. Technologies   1.5  [AA ▾]
  ☑ GEO 103E  Fundamentals of Surveying        3  [BB ▾]
```

Üç ayrıntı:

* **0 kredili derste not listesi BL/BZ ile başlıyor** — `DAN 102` açılınca
  ilk seçenekler `BL`, `BZ`. Harf notları arkada duruyor ama kayboluyor değil.
* **Havuz slotları seçenekleriyle geliyor** — "ITB havuzundan HUK 217 aldım"
  diyebilmek gerekiyor.
* **Kaydet EKLER, silmez** (`replace: false`). Plan dışı dersler (BBF 103E
  gibi) korunuyor — plandan tikleme onları silseydi denklik keşfi çökerdi.

"Bu döneme kadarki zorunluları işaretle" düğmesi çoğu öğrenci için doğru
başlangıcı tek tıkla kuruyor; yanlışları tek tek düzeltmek kolay.

## ★ Kontenjan nöbeti

Faz 9 "ne değişti" diyebiliyordu — **sen sorunca**. Kayıt haftasında istenen
bu değil: *"BLG 351E'de yer açılınca haber ver."*

```bash
make watch                              # 10 dk'da bir
make watch ARGS="--only-good"           # yalnız FIRSAT bildir
```

macOS bildirimi `osascript` ile — **bağımlılık yok**. Gönderilemezse bir kez
söylüyor, sonra terminale yazmaya devam ediyor.

İki tasarım kararı:

* **Aralığın tabanı 5 dakika.** Kayıt haftasında bile daha sık taramanın
  kazancı yok, OBS'yi yormanın anlamı da. Kod bunu zorluyor, ayarla
  aşılamıyor.
* **`--only-good`** — dolan kontenjan da bilgi ama gece 3'te uyandırmaya
  değmez. Fırsat (yer açıldı / ders açıldı / yeni şube) ile kötü haber ayrı.

İzleme listesi `settings.toml`'dan daraltılabiliyor:

```toml
watch_courses = ["BLG 351E", "BLG 335E"]
```

Boş bırakılırsa planlarının açık slotlarındaki **191 ders** izleniyor — her
turda bir şey değişir ve bildirim gürültüye döner. Kayıt haftasında birkaç
derse daraltmak doğru kullanım.

## ★ Yedekten geri yükleme

Yedekler Faz 9'dan beri alınıyordu ama geri yükleme terminaldeydi. Artık
"Ders ara" diyaloğunda **"Yedekten geri yükle (N)"** var.

Geri yükleme de silici bir yazma, o yüzden **önce mevcut hâl yedekleniyor** —
yanlış yedeği seçen kullanıcı iki kez kaybetmesin. Dosya adı arayüzden
geldiği için dizin çıkışı engelli (`../../etc/passwd` reddediliyor).

### Komut satırında yedek yoktu

Yedek almayı Faz 9'da **yalnız sunucu tarafına** koymuşum. `make transcript
FILE=... --replace` aynı silici işlemi yapıyordu ama yedeksiz. 22.08.2026'da
yanlış dosya (doldurulmamış şablon) verildi ve transkript boşaldı — kurtarma
kullanıcının makinesindeki kopyadan yapıldı.

Aynı tehlikeli işlem, nereden çağrıldığına göre farklı davranıyordu. Artık
komut da yedekliyor ve dosya boşsa açıkça uyarıyor:

```
💾 Yedek: data/yedek/transkript-20260822-021500.txt
⚠️  Dosyada hiç ders yoktu — transkript BOŞALDI. Geri almak için: …
```

### Testin yakaladığı hata: aynı saniyede iki yedek

Damga saniye çözünürlüklü (`transkript-20260822-014333.txt`). Aynı saniyede
iki silici yazma olursa ikinci yedek birinciyi **sessizce eziyordu** — yani
kurtarma özelliği tam da önlemesi gereken kaybı yaratıyordu. Artık çakışan ad
`-2`, `-3` ile ayrılıyor.

## macOS başlatıcı

`itucap.command` — Finder'da çift tıkla. Sanal ortam yoksa kuruyor, veri
yoksa bir kez tazeliyor, sonra `make app`. Terminal bilmeyi gerektirmiyor.

## Test kapsamı

338 test (Faz 11'den 59 yeni).

**MADDE 17** — tavan GNO'yu izliyor (7 eşik değeri) · "25 dahil" gerçekten
dahil · ÇAP öğrencisinin alt sınırı yok · tek programlının var · birinci
yarıyıl ve son sınıf muaf · **muafiyet tavanı yükseltmiyor** · bir üst
basamağın şartı yazılıyor · beyan yoksa hiçbir şey iddia edilmiyor · projenin
kendi config'i 25'i veriyor

**MADDE 20 ölçeği** — 15 not değeri tek tek · artı notlar transkript
satırında ayrıştırılıyor · artı notlar ÖNŞART metninde ayrıştırılıyor
(`+` kaçışı) · `CC+` bir `MIN CC` eşiğini geçiyor, `DC+` geçmiyor ·
`T`/`E` geçmiyor, `M`/`MU` önşart açıyor · altı işaret GNO dışında ·
şartlı geçer listesi notu girilmemiş dersleri saymıyor

**BL/BZ** — BL geçiyor, BZ kalıyor · ikisi de GNO'ya girmiyor · BL kredi
kazandırmıyor · arayüz not listesinde ikisi de var

**Tikleme** — plan dersleri rol/dönem/havuz yapısıyla geliyor · alınmış
dersler işaretli geliyor · kredi bilgisi taşınıyor

**Yedek** — geri yükleme eski transkripti getiriyor · önce yedekliyor ·
dizin çıkışı reddediliyor · **aynı saniyedeki iki yedek çakışmıyor** ·
komut satırındaki `--replace` de yedek bırakıyor

**Nöbet** — aralık tabanı 5 dk · özet fırsatı öne alıyor · `--only-good` kötü
haberi susturuyor · beyan edilen izleme listesi kullanılıyor · AppleScript
tırnak kaçışı
