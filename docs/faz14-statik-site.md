# Faz 14 — GitHub Pages: motor tarayıcıda

> ⚠️ Bu belgedeki bütün sayılar **örnektir**. Depoda kimsenin gerçek notu
> ya da ortalaması yer almaz.

```bash
make site                            # site/ klasörünü kur
python3 -m http.server -d site 8000  # yerelde dene
```

439 test (Faz 14'ten 20 yeni).

## ★ Karar: çevirmek değil, taşımak

Aracı herkese açmanın iki yolu vardı ve ikisi arasındaki fark, bu fazın
tamamını belirledi.

**Yol 1 — motoru JavaScript'e çevir.** Önşart ayrıştırıcısı, puanlama,
çakışma araması, mevzuat kuralları… ~2600 satır. Sonuç: **iki motor**. Bir
kural birinde düzelir öbüründe düzelmez ve hangisinin doğru olduğunu kimse
bilmez. Bir öğrencinin mezuniyet planı hakkında konuşan bir araçta bu,
kabul edilebilir bir risk değil.

**Yol 2 — Python'u tarayıcıya taşı.** Ölçtüm: motorun tamamı **standart
kütüphane** kullanıyor.

```
rules        dataclasses enum sqlite3 typing
recommend    dataclasses sqlite3 typing
policy       dataclasses fnmatch pathlib sqlite3 tomllib typing
prereq       dataclasses re sqlite3 typing
…
stdlib dışı: YOK
```

Tarama bağımlılıkları (`httpx`, `selectolax`) motorda değil, `sources/`
altında. Yani motor zaten taşınabilirdi; kimse denememişti.

[Pyodide](https://pyodide.org) (CPython'un WebAssembly derlemesi) ile motor
**satırı değişmeden** tarayıcıda çalışıyor. Kazanç:

* tek kod tabanı — mevzuat `config/kurallar.toml`'da bir kez değişiyor,
* **439 test web sürümünü de kapsıyor**, çünkü aynı kod,
* yerel sürümle web sürümü ayrışamaz.

Bedeli ~2.5 saniyelik ilk yükleme. Dönemde birkaç kez açılan bir araç için
ucuz.

## Ölçüm

| | |
|---|---|
| Pyodide yüklenmesi | 2.4 s |
| Katalog indirme + açma (2.4 MB gzip) | 0.2 s |
| Motor kurulumu + ilk hesap | 2.6 s |
| **Toplam (soğuk açılış)** | **~5 s** |

Katalog budanıyor: 15 MB → 8.7 MB → **2.4 MB gzip**. En büyük kazanç eski
plan iterasyonları — OBS aynı program için yıl aralığı başına ayrı plan
tutuyor, yürürlükte olan yalnız biri (446 plan → 128).

## ★ Üç refactor, üçü de kod kalitesi için de doğruydu

Web sürümü çalışsın diye yapılan değişikliklerin hiçbiri "web için hack"
değil; üçü de zaten olması gereken ayrımlardı.

**1. `plans.py` ayrıldı.** `resolve_plans` ve `watch_codes` `pipeline.py`
içindeydi ama oraya ait değillerdi: `pipeline` tarama modüllerini içeri
alıyor, plan çözümlemek içinse ağ gerekmiyor. `server.py` bu yüzden bütün
tarama yığınını sürüklüyordu.

**2. `State.dispatch()` çıktı.** Yazma uçlarının yönlendirmesi `do_POST`
içindeydi. Aynı `State` iki taşıyıcıyla kullanılıyor artık — yerel HTTP ve
tarayıcı içi Python. Yönlendirme HTTP katmanında kalsaydı web sürümü onu
**kopyalamak** zorunda kalırdı ve iki kopya zamanla ayrışırdı.

**3. `api()` kancası.** Arayüz artık taşıyıcıyı bilmiyor:

```js
if(window.__ITUCAP_API__) return window.__ITUCAP_API__(path, payload);
// yoksa HTTP ile 127.0.0.1'e
```

Şablon kopyalanmadı — aynı CSS, aynı JS, aynı `ui.py`. İki sürüm çıksaydı
bir tasarım düzeltmesi birinde yapılır, öbüründe unutulurdu.

## ★★ Yayına dakikalar kala yakalanan sızıntı

Site ilk kurulduğunda ekranda **kullanıcının kendi denklik beyanları**
göründü:

```
UYGULANMIŞ BEYAN  4
GEO 220E → MAT 210      GEO 109E → MAT 281  …
```

Sebep: `reference.sqlite3` "herkese açık katalog" diye tasarlanmıştı ama
`declared.apply()` kullanıcının beyanlarını oraya yazıyor
(`confidence='user_declared'`). Yerelde sorun değil. Yayınlanınca *"bu kişi
GEO 220E aldı ve MAT 210E yerine saydırıyor"* demek olur — hem hangi dersi
aldığını hem ne talep ettiğini açık eder.

★ **`.gitignore` bunu asla yakalayamazdı.** Dosya adı masumdu
(`katalog.sqlite3.gz`); sızıntı dosyanın **içindeydi**.

İki katman eklendi:

* `site_kur.py` yayınlanacak katalogdan `user_declared` denklikleri ve
  kaynak satırlarını siliyor; `source_url`'deki yerel dosya yollarını
  (`/home/kullanici/…` — kullanıcı adını sızdırır) temizliyor.
* `gizlilik_denetimi.py` artık **kurulan sitenin içini** açıp tarıyor:
  kişisel denklik, yerel yol, öğrenci tablosu. GitHub Actions bunu
  yayından **önce** çalıştırıyor; kirliyse yayın durur.

> Bir kez sızan veri geri alınamaz. Bu yüzden denetim yayın hattının
> zorunlu adımı, isteğe bağlı bir kontrol değil.

## ★ Gizlilik mimarisi

Sitenin **sunucusu yok**. Ziyaretçinin notları:

* tarayıcısında hesaplanıyor (Pyodide sanal diskinde bir SQLite),
* tarayıcısında saklanıyor (IndexedDB — `localStorage` ikili veri tutamaz),
* **hiçbir yere gönderilmiyor**: uç yok, istek yok, telemetri yok.

Yayınlanan tek veri herkese açık ders kataloğu. Yani site **tutulacak
kişisel veri üretmiyor** — sızdıracak veritabanı yok, KVKK'da veri
sorumlusu olunmuyor.

★ Pyodide **CDN'den değil, paketten** geliyor. CDN kullansaydık her
ziyaretçinin tarayıcısı üçüncü bir tarafa istek atardı; "hiçbir şey
tarayıcından çıkmıyor" diyen bir aracın açılışta başkasına haber vermesi
tutarsız olurdu. Yan fayda: CDN engellense de site çalışır.

## ★★ Yayındaki ilk hata: test edilen sürüm ≠ yayınlanan sürüm

Site ilk açılışta beyaz ekran ve şu hatayla geldi:

```
ModuleNotFoundError: No module named 'sqlite3'
The module 'sqlite3' is unvendored from the Python standard library
in the Pyodide distribution.
```

Sebep bir kod hatası değil, **iki farklı çalışma ortamı**:

| | sqlite3 |
|---|---|
| `pyodide@314.x` — yerelde test ettiğim | stdlib'e **vendor edilmiş** |
| `pyodide@0.28.3` — `app.js`teki CDN sabiti | stdlib'den **ayrılmış** |

Motorun her modülü `import sqlite3` ile ayakta. Yerelde çalıştı çünkü
paketlenmiş kopyayı kullandım; yayında CDN'e düştü ve orada sqlite3 yoktu.
Yani testim doğru şeyi ölçtü, **yanlış ortamda**.

★ Asıl hata sürüm seçimi değil, sürümün **iki yerde** durmasıydı. Düzeltme
buna göre:

* `PYODIDE_VERSION` yalnız `tools/site_kur.py`'de. `app.js` onu
  `manifest.json`dan okuyor, GitHub Actions da oradan alıyor — sabit hiçbir
  yerde tekrar edilmiyor.
* Kurulum sırasında **paketlenen Pyodide denetleniyor**: sürüm beklenen mi,
  `python_stdlib.zip` sqlite3 içeriyor mu. İçermiyorsa kurulum durur.
  Tarayıcıda fark etmek yerine paketlerken bakmak bedava.
* `app.js` yine de sqlite3'ü içeri almayı deniyor; yoksa `loadPackage` ile
  yüklüyor, o da olmazsa **ne olduğunu söyleyen** bir hata veriyor.
* Üç test ayrışmayı imkânsız kılıyor: `app.js`te sabit sürüm olmamalı,
  akış sabit sürüm yazmamalı, sqlite3'süz paket kurulumu durdurmalı.

Pyodide paketlenmeden kurulum yapılırsa artık uyarı basılıyor — o hâlde her
ziyaretçi CDN'e istek atar ve gizlilik sözü delinir.

## ★ Çalışmayacak düğme gösterme

Tarayıcıda "Veriyi tazele" çalışamaz — tarama yığını yok, üstelik OBS'ye
tarayıcıdan istek atmak CORS'a takılır. Düzeltilmeden önce
`ModuleNotFoundError: httpx` fırlıyordu: kullanıcının ne anlayabileceği ne
çözebileceği bir hata.

Artık `can_refresh()` bayrağı var; arayüz düğmeyi **hiç göstermiyor** ve
yerine katalogun nasıl güncellendiğini yazıyor.

Aynı ilke bir yerde daha uygulandı: yarıyıl tabanı paneli *"settings.toml'a
yaz"* diyordu — web ziyaretçisinin düzenleyebileceği bir dosya yok. ÇAP'a
başlanan yarıyıl artık **Dönem** düğmesinden giriliyor; mesaj taşıyıcıya
göre değişiyor.

## Katalog nasıl güncellenir

Katalog depoda **yok** (15 MB türetilmiş veri, `.gitignore`da). Yayın akışı
onu bir sürüm varlığından indiriyor:

```bash
make refresh                                            # OBS'den taze veri
gh release create katalog-$(date +%Y%m%d) data/reference.sqlite3
# → Actions → "pages" → Run workflow
```

Böylece kişisel veri barındıran hiçbir dosya depoya girmiyor ama site
güncel katalogla kurulabiliyor. Dönem başında bir kez yeterli.

## Test kapsamı

**Taşınabilirlik** — motor modülleri tarama bağımlılığı çekmiyor (biri
sızarsa web sürümü sessizce kırılırdı) · `server.py`'nin modül seviyesindeki
importları site paketinde · tembel importlar hariç tutuluyor

**Kabuk** — ertelenmiş kabuk kendi kendine `boot()` çağırmıyor (boş veriyle
çizip sonra yeniden çizmek "hiç dersin yok" ekranı gösterirdi) · `make ui`
bozulmadı, hâlâ kendi kendine açılıyor · `api()` kancası yerinde

**Yayınlanan veri** — kişisel denklik siliniyor, **resmî olan kalıyor** ·
kaynak satırları da siliniyor · yerel dosya yolları temizleniyor · yalnız
yürürlükteki iterasyon kalıyor, düşen planın slotları yetim kalmıyor ·
denetim kirli siteyi **yakalıyor**, temiz siteyi geçiriyor · geliştiricinin
`settings.toml`'u siteye girerse yakalanıyor

**Çalışmayan düğme** — tazeleme anlaşılır bir `ValueError` veriyor,
`ModuleNotFoundError` değil · arayüz düğmeyi gizliyor
