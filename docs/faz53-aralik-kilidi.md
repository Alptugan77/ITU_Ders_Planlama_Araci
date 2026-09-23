# Faz 53 — Saat aralığına kilit, arka plan nöbeti ve yol üstünde çıkan üç hata

*21.09.2026 · kullanıcı: **"onun dışında yapılacak güncellemeleri ve
geliştirmeleri uygulayabilirsin uygunca"*** — listeden 2.4 (saat aralığına
kilit) ve 4.2 (nöbeti arka planda çalıştırma).

Testler **1167 → 1201**.

İki iş listedendi. Ölçerken üç hata daha çıktı. Üçü de **var olan**
özelliklerdeydi ve ikisi kullanıcının kendi verisinde, kendi dosyasında
görüldü:

| | ne oluyordu | şimdi |
|---|---|---|
| tek şubeye kilit (Faz 45) | **139 denemenin 22'si hiç program üretmiyordu**, ekran da suçu "çakışan kilitlere" atıyordu | 22'nin 22'si program üretiyor |
| kilitten sonra ekran | başka kipe atılıyordun, ızgarada kilitli öneri değil **kaydettiğin eski program** duruyordu | kip ve ızgara yerinde |
| okunamayan kilit satırı | **hiçbir yerde görünmüyordu** (belge "görünüyor" diyordu) | "uygulanmıyor" diye görünüyor, tek tıkla siliniyor |
| yanlış tablodaki ayar | senin dosyanda `cap_baslangic_yariyili` `[regulation]` altında: **yazsan da okunmuyordu** | tepede söyleniyor |

---

## A. Saat aralığına kilit (2.4)

Faz 45 dersi **şubeye** kilitliyordu: "tam bu saatte". Asıl sık istek
daha gevşekti: *"bu ders sabah olsun, şubesi fark etmez"*. Tek yol bir şube
seçip ona kilitlemekti; bu da motorun o saatlerdeki **öbür şubeleri**
denemesini engelliyordu.

Ders penceresinde artık iki düğme var, yanında o saatlere uyan şube sayısı:

```
[Programdan çıkar] [Bu saate kilitle] [Kontenjanı izle]
Şube fark etmez, saat önemliyse:  [Sabah olsun · 16 şube]  [Öğleden sonra olsun · 10 şube]
```

* **Sınır veriden seçildi: 12:30.** 3630 ders saati tarandı: hiçbir ders
  12:00'de başlamıyor, sabah dersleri en geç 12:29'da bitiyor (763),
  öğleden sonrakiler 12:30'da başlıyor (178). Saatli 3089 şubenin 1283'ü
  tamamen sabah, 1412'si tamamen öğleden sonra; **394'ü iki yana taşıyor ve
  ikisine de uymuyor** — "sabah" demek bütün saatlerinin sabah olması.
* **Saati ilan edilmemiş şube uymuyor** (3417 şubenin 328'i). "Sabah olsun"
  diyene saati bilinmeyen şubeyi vermek, bilinmeyeni biliniyor gibi
  göstermek olurdu.
* **Uyan şube yoksa düğme kapalı** ve "şubesi yok" yazıyor — basıp boş
  sonuç almak yerine.
* Kilit yine **sert**: ders her öneride var, şubesi aralıkta. Dönem
  değişip aralıkta şube kalmazsa kilit düşmüyor; şerit "bu dersin sabah
  saatlerine uyan şubesi yok" diyor.
* Bir derste yine **tek kilit**: şube kilidi ile aralık kilidi birbirinin
  yerine geçiyor, düşen söyleniyor.
* Ayar biçimi: `"ATA 121@12:30-24:00"`. Elle istediğin aralığı da
  yazabilirsin (`"BLG 351E@10:30-15:30"`); arayüz onu "10:30–15:30 arası"
  diye gösteriyor.

### Ölçüm: aralık kilidi gerçekten "en iyi şubeyi" buluyor mu?

Ölçüt şu: aralıktaki şubeleri **tek tek** kilitleyerek bulunabilecek en iyi
program (bugünkü yolun en iyisi, ama kullanıcının hepsini denemesi
gerekirdi). Aralık kilidi **en az onun kadar** iyi olmalı. Gerçek veride 26
durum (≥2 şubesi aralığa uyan her ders × her aralık), **motorun kendi
sıralama ölçüsüyle** (taban → puan → yük):

| arama | aralık kilidi ≥ en iyi tek şube | süre (medyan / en çok) |
|---|---|---|
| aralıktaki ilk 3 şube (Faz 45'in dal sınırı) | 16 / 26 | 0,36 / 1,62 sn |
| + kilitli ders aramada öne | 21 / 26 | 0,12 / 0,37 sn |
| **+ her şube dalına adil pay** | **26 / 26** | 0,18 / 0,51 sn |

> ⚠️ İlk karşılaştırmayı **kredi** ile yaptım ve yanıltıcı çıktı: 26,5
> kredilik program, motorun sıraladığı 25,5 kredilikten **daha düşük
> puanlıydı**. Motor puana göre sıralıyor; ölçüt de o olmalıydı. Yeniden
> ölçüldü; tablo onun sonucu.

**Adil pay neden gerekti.** Motor bir "havuz" dolduruyor (öneri başına 60
aday program) ve derinlik öncelikli arıyor. Aralıktaki ilk şubenin alt
ağacı havuzu tek başına dolduruyordu; ötekilere sıra gelmiyordu — şube
sayısını 3'ten "hepsi"ne çıkarmak **hiçbir şeyi değiştirmedi** (ölçüldü).
Artık her şube dalı, kalan havuzun ve kalan arama bütçesinin kalan dal
sayısına bölünmüş payını alıyor; kullanmadığı pay sonrakine geçiyor.

---

## B. ★★ Faz 45'in hatası: tek şube kilidi bazen HİÇ program üretmiyordu

A'daki ölçüm için aralıktaki şubelere tek tek kilit koyunca şu çıktı:
**139 kilidin 22'si "öneri üretilemedi"** verdi. `ALM 102`nin iki şubesi
de, `TUR 122`nin altı sabah şubesinin üçü, `ITA 101`in dördünün üçü.
Ekrandaki açıklama da yanlıştı: *"bu kipte bağlayan 1 kilit birbiriyle ya
da meşgul saatinle çakışıyor"* — tek kilit varken, hiç meşgul saat yokken.

Sebep: adaylar puana göre sıralı ve kilitli ders düşük puanlıysa **sonlarda**
kalıyordu. Motor önce yüksek puanlı dersleri yerleştiriyor, kilitli derse
gelince onun saati dolu çıkıyor ve dal ölüyordu; arama bütçesi bu ölü
dallarda bitiyordu. Kilitli (ve `--pin` ile zorunlu tutulan) ders artık
**önce** yerleşiyor: **22'nin 22'si program üretiyor**, o kilitlerde arama
~1,5 sn → ~0,15 sn. Kilit yokken sıra **değişmiyor** — kilitsiz bütün
sonuçlar birebir aynı (testte tutuluyor).

---

## C. ★★ Kilitten sonra ekran yanlış şeyi gösteriyordu

Gerçek verinin bir kopyasıyla denendi: tam kipte (DEPAR) `ATA 121`
öğleden sonraya kilitlendi. Sonuç:

* dönemlik kipe ("5. dönem + alttan") **atıldım**,
* ızgarada kilitli öneri değil, **kaydettiğim eski program** duruyordu,
* şerit *"bu kipte bağlamıyor · ekranda CRN 10123, kilit öğleden sonra"*
  diyordu.

Kilit çalışıyordu; ekran onu bozuk gösteriyordu. Sebep: sunucudan gelen
her yeni durumda **ilk açılış kodu** baştan koşuyordu — kip 0'a dönüyor,
kaydedilen program ve paylaşılan bağlantı (`#crn=…`) yeniden
uygulanıyordu. Kilit, meşgul saat, tavan, izleme, kaydetme: hepsi.
Üstüne, dönemlik kip boşalınca kiplerin **sırası** değişiyor, "kip 0"
başka bir kipi gösteriyordu.

Artık:

* kip **adıyla** korunuyor;
* öneriyi değiştiren işlerden sonra (kilit, meşgul saat, tavan, ayarlar) o
  kipin 1. önerisi gösteriliyor;
* öneriyi değiştirmeyen işlerde (kontenjan izleme, programı kaydetme)
  ızgara ve sekme **olduğu gibi** kalıyor — elle yaptığın düzenleme gitmiyor;
* kaydedilen programı yüklemek ve bağlantıyı uygulamak yalnız **ilk
  açılışın** işi.

---

## D. Okunamayan kilit satırı sessizce düşüyordu

Faz 45'in kodunda bir cümle vardı: *"biçimi bozuk satır atlanıyor ama
sessizce değil: arayüz 'bu satır okunamadı' diyor"*. Diyen bir yer yoktu —
arayüze giden liste zaten ayıklanmış sözlükten yapılıyordu. Şimdi ayarlara
elle yazılan bir aralık (`"BLG 351E@8.30-12.30"`) yazım hatası yapmayı
kolaylaştırdığı için bu açık önemliydi. Ayrıca bozuk değer **CRN
sayılıyordu**: hiçbir şubeyle eşleşmeyip dersi zorunlu bırakacak, **bütün
önerileri boşaltacaktı**.

* Bozuk satır motora girmiyor, şeritte **"uygulanmıyor — okunamadı"** diye,
  doğru biçimle birlikte görünüyor; ✕ satırın **kendisini** siliyor (ders
  kodu bile olmayabilir: `"@123"`).
* Aynı derse iki satır yazılmışsa motor sonuncusunu uyguluyor; öncekisi
  "uygulanmıyor — sonra yazılan geçerli" diye görünüyor.
* Sunucu satırları artık **sıralamıyor**: sıralamak, dokunulmayan bir
  dersin hangi satırının geçerli olduğunu sessizce değiştirebiliyordu.

---

## E. ★ Yanlış tablodaki ayar — senin dosyanda

Ayar dosyası yalnız `[student]` ve `[scraper]` tablolarından okunuyor.
Mac'teki `config/settings.toml`'da iki satır dosyanın **sonuna**, yani
`[regulation]` tablosunun altına düşmüş:

```toml
[regulation]
…
cap_baslangic_yariyili = 0     ← okunmuyor
mesgul = []                    ← okunmuyor ([student]'taki kullanılıyor)
```

Yorum *"3 ya da 5 yaz"* diyor; oraya yazsaydın **yarıyıl kredi tabanı
uygulanmayacaktı** ve araç bunu söylemeyecekti. Şu an ikisi de varsayılan
değerde, yani bugün bir şey bozuk değil. Ama tuzak duruyordu.

Artık tepede sarı bir not çıkıyor: hangi satır, hangi tabloda, araç onu
okumuyor mu yoksa yanıltıcı bir kopya mı, nasıl düzeltilir. Satırı yanlış
tablodan **okumuyoruz**, çünkü iki yerde farklı değer olunca hangisinin
geçerli olduğunu tahmin etmek gerekirdi. Örnek ayar dosyası temiz (testte
tutuluyor).

> **Senin yapman gereken:** bu iki satırı `[student]` başlığının altına
> taşı ya da sil. Not o zaman kaybolur.

---

## F. Nöbeti arka planda çalıştırma (4.2)

```bash
make watch-kur                      # 10 dakikada bir; oturum açılınca kendiliğinden
make watch-kur ARGS="--only-good"   # yalnız fırsatları bildir
make watch-durum                    # çalışıyor mu + günlüğün son satırları
make watch-kaldir                   # durdur ve kaldır
```

`make watch` bir terminal penceresini işgal ediyordu; pencere kapanınca ya
da bilgisayar yeniden başlayınca nöbet de bitiyordu. macOS'un servis
yöneticisi (`launchd`) onu bir **Kullanıcı Aracısı** olarak çalıştırıyor.

* **Kullanıcı aracısı**, sistem servisi değil: yönetici parolası istemiyor,
  yalnız senin oturumunda çalışıyor, bildirimi masaüstüne gösterebiliyor.
* **Çökünce yeniden başla, bitince başlatma**, ve bunu **en fazla 5
  dakikada bir** yap — çöküp kalkan bir döngü OBS'yi dakikada onlarca kez
  yormasın.
* **Kayıt günü kipi (`--kayit`) arka planda yok**: o kip dakikada bir tarayıp
  2 saat sonra kendiliğinden duruyor; arka planda unutulup günlerce dönmesi
  kaçınılması gereken şeyin ta kendisi.
* Günlük `data/nobet.log` (`data/` zaten `.gitignore`da).
* **Durum üç ayrı cümle**: kurulu değil · kurulu ama yüklü değil · yüklü ama
  çalışmıyor (hatayla düştü, launchd yeniden deneyecek) — sebep günlükte.
* macOS değilse **hiçbir dosya yazılmıyor** ve `make watch` öneriliyor.

> ✅ **Gerçek Mac'te denendi (kullanıcı, 23.09.2026).** `nobet kur` →
> "Nöbet arka planda — 10 dakikada bir"; `make watch-durum` → "Nöbet
> çalışıyor (pid 18882) — her 10 dk" ve günlüğün ilk satırları ("229 ders
> izleniyor"); `make watch-kaldir` → tanım dosyası silindi. Çalışma alanı
> Linux olduğu için testler tanımı `plistlib` ile, komutları sahte bir
> çalıştırıcıyla doğruluyor; üç komutun gerçek davranışı bu denemeyle
> görüldü.
> Not: `watch_courses` boşken 229 ders izleniyor — Faz 11'in uyarısı
> geçerli: her turda bir şey değişir. Ders penceresindeki "Kontenjanı izle"
> listeyi birkaç derse daraltıyor.

---

## G. Küçük: telefonda kilit ekran okuyucuya söylenmiyordu

Telefonun gün listesinde kilit simgesi `aria-hidden` idi; görmeyen kullanıcı
dersin kilitli olduğunu hiç duymuyordu. Simge artık "sabaha kilitli" /
"CRN … şubesine kilitli" adını taşıyor; ızgaradaki başlık da aynı sözü
kullanıyor.

---

## Geri alma deneyi

26 düzeltmenin her biri geri alındı ve bekçinin **kendi sebebiyle** kırmızıya
döndüğü görüldü (Faz 52'nin bayat `.pyc` dersiyle: her koşudan önce
`__pycache__` siliniyor). Bu sırada iki bekçi eksik çıktı ve yazıldı:

* **adil pay** için yalnız kaynak bekçisi vardı; davranışı tutan küçük bir
  model eklendi (7 küçük ders ilk şubenin alt ağacında havuzu dolduruyor,
  en iyi program ancak ikinci şubeyle kuruluyor);
* **kip korunması** için uçtan uca test yazıldı — geri alınınca tam olarak
  gerçek veride görülen şey çıkıyor: dönemlik kipe atılma ve ızgarada
  kaydedilen `AAA 101E@300`.

## Testler

`tests/test_faz53_aralik_kilidi.py` (27 test): biçim ve bozuk değer ·
ön ayarlar veriden ve iki tarafta aynı · saatsiz şube uymuyor · kilit dersi
tutuyor ve aralıkta · şube motora kalıyor (CRN kilidi BBB'yi düşürüyor,
aralık kilidi tutuyor) · aralıkta şube yoksa kaymıyor · bozuk kilit
önerileri boşaltmıyor · kilitsiz sonuçlar birebir aynı · **kilitli ders
önce** (bütçe tükenmesi modeli) · **adil pay** (davranış + kaynak) · satır
çözümü, gölge ve bozuk satırlar · şerit, pencere düğmeleri, şube düğmesi ·
sunucu (yaz/aç/değiştir, okunamayanı yazmama, satırı kendisiyle silme, sıra)
· yanlış tablodaki ayar (üç durum + örnek dosya temiz) · ilk açılış işleri
tekrarlanmıyor · **uçtan uca** iki senaryo (aralık kilidi + bozuk satır +
ayar uyarısı + telefon; kip ve ızgaranın korunması).

`tests/test_faz53_nobet_servisi.py` (7 test): tanım · kur (eskisini indir,
5 dk taban) · yüklenemezse başarı demiyor · kaldır · durumun üç cümlesi ·
macOS değilse hiçbir şey yazılmıyor · komut satırı ve `make` hedefleri.

Gerekçesiyle yeniden yazılanlar: `test_faz49` (şerit artık uygulanan
kilitlerle okunmayan satırları ayırıyor), `test_faz25_d` (`useMode`'un
ikinci parametresi), `test_faz51` (`boot`'un parametresi).
