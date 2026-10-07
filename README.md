# İTÜ DEPAR — Ders Planlama Aracı

İTÜ DEPAR (**DE**rs **P**lanlama **AR**acı), İstanbul Teknik Üniversitesi
lisans öğrencilerinin dönemlik ders programını ve mezuniyete kadarki
planını hazırlamalarına yardımcı olan bir araçtır. Anadal programıyla
birlikte **çift anadal (ÇAP)** ve **yandal** programlarını da destekler.

Araç web tarayıcısında ya da kullanıcının kendi bilgisayarında çalışır.
Kişisel veriler (transkript, notlar, tercihler) bu ortamların dışına
gönderilmez.

**Web sürümü:** <https://alptugan77.github.io/ITU_Ders_Planlama_Araci/>

> [!IMPORTANT]
> Bu araç yalnızca **bilgilendirme amaçlıdır** ve İTÜ'nün resmî bir aracı
> değildir. Ders kaydına ilişkin kararlar için akademik danışmanınıza ve
> OBS'ye başvurunuz. Araç, kullanıcı adına ders kaydı yapmaz ve OBS
> şifresi istemez.

---

## İçindekiler

1. [Genel bakış](#genel-bakış)
2. [Özellikler](#özellikler)
3. [Temel ilke: belirsizliğin açıkça gösterilmesi](#temel-ilke-belirsizliğin-açıkça-gösterilmesi)
4. [Kullanım seçenekleri](#kullanım-seçenekleri)
5. [Kurulum (yerel sürüm)](#kurulum-yerel-sürüm)
6. [Komutlar](#komutlar)
7. [Yapılandırma](#yapılandırma)
8. [Veri kaynakları ve güncelleme](#veri-kaynakları-ve-güncelleme)
9. [Gizlilik ve güvenlik](#gizlilik-ve-güvenlik)
10. [Mimari](#mimari)
11. [Test ve kalite güvencesi](#test-ve-kalite-güvencesi)
12. [Web sürümünün yayımlanması](#web-sürümünün-yayımlanması)
13. [Katkı](#katkı)
14. [Sorumluluk reddi ve lisans](#sorumluluk-reddi-ve-lisans)

---

## Genel bakış

Birden fazla programın öğretim planını aynı anda izlemek, elle yürütülmesi
güç bir iştir. Öğrencinin şu sorulara aynı anda cevap vermesi gerekir:
hangi dersin hangi programa sayıldığı, hangi önşartın sağlandığı, bu dönem
açılan şubelerle çakışmasız bir programın kurulup kurulamayacağı, dönem
kredi sınırının aşılıp aşılmadığı ve mezuniyetin hangi yarıyılda
gerçekleşeceği.

İTÜ DEPAR bu soruları OBS'de yayımlanan öğretim planları, ders kataloğu,
şube bilgileri ve ilgili mevzuat üzerinden hesaplar. Hesabın dayandığı her
varsayım, sonucun yanında açıkça belirtilir.

## Özellikler

### Dönemlik ders programı

* **Çakışmasız program önerisi.** Açık şubeler, önşartlar, kontenjan,
  dönem kredi sınırı ve kritik yol birlikte değerlendirilerek haftalık
  program önerileri oluşturulur.
* **Yumuşak tercihler.** En erken ders saati, boş gün, yerleşke değişimi,
  çevrimiçi şube ve öğretim üyesi tercihleri önerilerin sıralamasını
  etkiler; programları elemez. Tercihlerin etkisi kaydedilmeden önizlenebilir.
* **Saate kilitleme ve meşgul saatler.** Bir ders belirli bir şubeye ya da
  saat aralığına kilitlenebilir; iş, staj gibi nedenlerle kapalı tutulan
  saatlere ders yerleştirilmez.
* **Dilekçesiz denk dersler.** Plandaki bir dersin resmî denkliği olan ve
  şubesi öğrencinin kendi programına (anadal, ÇAP veya yandal kodu) açık
  olan dersler aday olarak sunulur ve plandaki dersin yerine sayılır.
* **Ek sınav şubeleri.** Öğretim yöntemi "Ek Sınav" olan şubeler, ilgili
  mevzuata uygun biçimde ders saati olmayan sınav hakları olarak ayrıca
  gösterilir.
* **Alternatif programlar ve karşılaştırma.** Birden fazla program (Plan A,
  B, C) kaydedilebilir ve yan yana karşılaştırılabilir.
* **Dışa aktarma.** Program takvim dosyası (`.ics`), paylaşılabilir
  bağlantı ya da görüntü (PNG) olarak dışa aktarılabilir. Derslik ve bina
  bilgisi programda yer alır.

### İlerleme ve mezuniyet planı

* **İlerleme paneli.** Anadal ve ikinci program ayrı ayrı izlenir; bu
  dönemin dersleri tamamlandığında ulaşılacak durum ayrıca gösterilir.
* **Mezuniyet yol haritası.** Kalan dersler; önşart sırası, dönem kredi
  sınırı, dersin açıldığı yarıyıl, haftalık saat uygunluğu ve ÇAP yarıyıl
  kredi tabanı dikkate alınarak dönemlere yerleştirilir. Her programın
  tahmini bitiş yarıyılı, plandaki bitişle ve azami öğrenim süresiyle
  karşılaştırılır.
* **Yol haritası önceliği.** İkinci program bulunan öğrenciler için iki
  ayar sunulur: *"Programları birlikte en kısa sürede bitir"* ve *"Anadala
  öncelik ver"*. Harita birkaç yerleştirme sırasıyla kurulur ve seçilen
  ölçüte göre en iyi yerleşim gösterilir; öbür ayarın sonucu da karşılaştırma
  için belirtilir.
* **Senaryolar.** Dönem başına en çok kredi (serbest değer), boş bırakılacak
  dönemler (Erasmus, staj) ve dönem başına zor ders sınırı değiştirilerek
  bitişin nasıl etkileneceği kaydedilmeden hesaplanabilir. Mevcut sınırın
  üzerindeki bir kredi değeri için yönetmeliğin aradığı GNO belirtilir.
* **Karar desteği.** "Bu dönem alınırsa bitişi öne çekecek dersler",
  "yaz okulunda alınırsa" hesabı ve "bu dersten kalınırsa mezuniyet ne kadar
  gecikir" (kalma riski) analizleri sunulur.
* **GNO hedefi ve not senaryosu.** Eşiklerin (ÇAP'a devam, mezuniyet, bir
  üst kredi basamağı) korunması için bu dönem gereken en düşük ortalama ve
  dönem sonu notlarına göre tahmini GNO hesaplanır.

### Mevzuat ve başvuru

* **Mevzuat denetimleri.** Dönem kredi yükü (Lisans Yönetmeliği MADDE 17),
  GNO eşikleri, bitirme çalışması kredi şartı ve ÇAP yarıyıl kredi tabanı
  denetlenir. Eşikler koda gömülü değildir; kaynaklarıyla birlikte
  `config/kurallar.toml` dosyasında tanımlıdır.
* **Başvuru uygunluğu.** Başvurulabilecek ÇAP ve yandal programları, her
  programda halihazırda sayılan dersler ve her ÇAP seçeneği için tahmini
  bitiş yarıyılı listelenir.
* **Darboğaz raporu.** Bir dersin neden alınamadığı (önşart, kontenjan,
  programa kapalı şube, kredi eşiği) açıkça gösterilir.
* **Danışman özeti.** Danışman görüşmesi için tek sayfalık, yazdırılabilir
  bir özet hazırlanır: bu dönemin programı ve CRN'leri, kredi ve GNO
  denetimleri, tahmini bitiş ve dilekçe gerektiren işlemler.

### Veri ve izleme

* **Geçmiş not dağılımları ve tahmini zorluk.** OBS'nin yayımladığı harf
  notu dağılımlarından dersin geçme oranı ve tahmini zorluğu hesaplanır.
  Bu bilgi yalnızca yol gösterici niteliktedir.
* **Kontenjan izleme.** Seçilen derslerde yer açıldığında bildirim
  gönderilir (`make watch`). macOS'ta izleme arka planda çalıştırılabilir.
* **Değişiklik raporu.** İki veri güncellemesi arasında eklenen dersler ve
  dolan kontenjanlar listelenir.

## Temel ilke: belirsizliğin açıkça gösterilmesi

Araç, öğrencinin mezuniyet planı hakkında bilgi vermektedir; hatalı bir
olumlu sonuç gerçek bir zarara yol açabilir. Bu nedenle tüm bileşenlerde
aşağıdaki kural uygulanır: **bilinmeyen bir bilgi, biliniyormuş gibi
gösterilmez.**

| Durum | Uygulama |
|---|---|
| Mevzuattan doğrulanmamış eşik | ⚠ işaretiyle gösterilir, kesin bilgi olarak sunulmaz |
| Hesaplanamayan şart (örneğin başarı sıralaması) | "Buradan denetlenemez" olarak belirtilir; sağlanmış sayılmaz |
| Notu girilmemiş ders | En elverişsiz durum (DD) varsayılır |
| Ad benzerliğinden çıkarılan denklik | Yalnızca önerilir; kullanıcı onaylamadan uygulanmaz |
| Bir dersi eleyen kural | Gerekçesiyle birlikte gösterilir |
| Katalogda bulunmayan bir dersi isteyen önşart | Ayrı bir kategori olarak raporlanır |
| Gelecek dönemlere ilişkin varsayımlar | Yol haritasının üstünde açıkça listelenir |

Hesaplanan GNO bir **tahmindir**; resmî ortalama OBS'de yer alan değerdir.

## Kullanım seçenekleri

| | Çalıştığı ortam | Verinin saklandığı yer | Gereksinim |
|---|---|---|---|
| **Web sürümü** | Tarayıcı (Pyodide) | Kullanıcının tarayıcısı (IndexedDB) | Yok |
| **Yerel sürüm** | Kullanıcının bilgisayarı | `data/user.sqlite3` | Python 3.11 veya üzeri |

Web sürümü, yerel sürümle **aynı Python motorunu** WebAssembly üzerinde
çalıştırır; iki sürümün hesapları bu nedenle birbirinden ayrışmaz. Aradaki
tek fark veri güncellemesidir: OBS'den veri çekme yalnızca yerel sürümde
yapılır, web sürümü siteyle birlikte yayımlanan kataloğu kullanır.

**Ana ekrana ekleme.** Web sürümü telefona uygulama gibi eklenebilir:

* iPhone'da Safari'de **Paylaş → Ana Ekrana Ekle**;
* Android'de Chrome'da **⋮ → Ana ekrana ekle** (veya **Uygulamayı yükle**).

Eklenen kısayol kendi simgesiyle ve adres çubuğu olmadan açılır. Bir kez
açıldıktan sonra bağlantı olmadan da çalışır.

## Kurulum (yerel sürüm)

Python 3.11 veya üzeri bir sürüm gereklidir.

```bash
git clone https://github.com/Alptugan77/ITU_Ders_Planlama_Araci.git
cd ITU_Ders_Planlama_Araci
make setup            # sanal ortam, bağımlılıklar ve örnek yapılandırma dosyaları
```

Ardından program bilgileri tanımlanır ve veriler çekilir:

```bash
make programs                  # ÇAP/yandal planlarını ve kimlik numaralarını listeler
$EDITOR config/settings.toml   # anadal ve ikinci program bilgileri
make refresh                   # katalog, öğretim planları ve şubeler (OBS)
make app                       # arayüzü tarayıcıda açar
```

Transkript, arayüzdeki **Plandan işaretle** penceresinden dönem dönem
girilebilir ya da OBS'den kopyalanan metin yapıştırılarak yüklenebilir.

## Komutlar

| Komut | Açıklama |
|---|---|
| `make app` | Düzenlenebilir arayüzü yerel sunucuyla açar |
| `make ui` | Sunucu gerektirmeyen tek dosyalık statik rapor üretir |
| `make refresh` | Katalog, planlar ve şubeleri OBS'den günceller |
| `make all-plans` | Bütün programların ÇAP/yandal planlarını ve resmî denklikleri çeker (uzun sürer; dönemde bir kez yeterlidir) |
| `make notdagilimi` | Geçmiş dönemlerin harf notu dağılımlarını çeker |
| `make basvuru` | Başvurulabilecek ÇAP/yandal programlarını listeler |
| `make recommend` | Komut satırında program önerisi üretir |
| `make progress` | İlerleme panelini komut satırında gösterir |
| `make changes` | Son iki güncelleme arasındaki değişiklikleri raporlar |
| `make watch` | Kontenjan izlemeyi başlatır |
| `make watch-kur` / `watch-durum` / `watch-kaldir` | İzlemeyi arka planda kurar, durumunu gösterir, kaldırır (macOS) |
| `make status` | Veritabanı özetini gösterir |
| `make site` | Statik web sürümünü üretir |
| `make vitrin` | Uydurma bir örnek öğrenciyle arayüzü açar |
| `make test` | Test takımını ve gizlilik denetimini çalıştırır |

Tüm komutların listesi için `make help` kullanılabilir.

## Yapılandırma

`config/` dizinindeki dosyalar elle düzenlenebilir; arayüzden yapılan
değişiklikler dosyadaki açıklama satırlarını korur.

| Dosya | İçerik | Depoda |
|---|---|---|
| `settings.toml` | Program seçimi, bulunulan yarıyıl, kredi sınırı, tercihler | Hayır (kişisel; `settings.example.toml` örnektir) |
| `denklikler.toml` | Kullanıcının denklik ve muafiyet beyanları | Hayır (kişisel; örnek dosyası vardır) |
| `kurallar.toml` | Mevzuat eşikleri (GNO, kredi yükü, bitirme çalışması, ÇAP tabanı) | Evet |
| `katalog-duzeltmeleri.toml` | OBS kataloğundaki bilinen hataların düzeltmeleri | Evet |

`settings.toml` dosyasındaki başlıca ayarlar:

| Ayar | Açıklama |
|---|---|
| `anadal_program` | Anadal program kodu (örneğin `BLGE`) |
| `second_kind` | İkinci program türü: `cap`, `yandal`, `ikisi` veya `yok` |
| `cap_program`, `yandal_program` | İkinci program kodları |
| `donem` | Bulunulan yarıyıl (0: otomatik) |
| `cap_baslangic_yariyili` | ÇAP'a başlanan yarıyıl; yarıyıl kredi tabanı buna göre belirlenir |
| `max_load` | Dönem kredi sınırı |
| `mesgul` | Ders konulmayacak saatler (örneğin `"PZT 12:30-14:30 iş"`) |
| `kilitli` | Belirli şubeye ya da saate kilitlenen dersler |
| `yol_onceligi` | Yol haritası önceliği: `birlikte` veya `anadal` |

Mevzuatta bir değişiklik olduğunda yalnızca `kurallar.toml` güncellenir;
kodun değiştirilmesi gerekmez. Her eşik, dayandığı madde ve doğrulanma
durumuyla birlikte tanımlanır.

## Veri kaynakları ve güncelleme

| Kaynak | Kullanım |
|---|---|
| [İTÜ Helper veri seti](https://github.com/itu-helper/data) | Ders kataloğu ve önşart metinleri; şubeler (saat, derslik, kontenjan); program ve bina kodları |
| OBS öğretim planları | Lisans, ÇAP ve yandal öğretim planları |
| OBS resmî ders denklikleri | Dersler arası resmî denklikler |
| OBS not dağılımları | Geçme oranı ve tahmini zorluk |

Veriler herkese açık kaynaklardan, istekler arasında bekleme süresi
bırakılarak çekilir. Kayıt döneminde `make refresh` komutunun gün içinde
birkaç kez çalıştırılması, değişiklik raporunu (`make changes`) anlamlı
kılar.

## Gizlilik ve güvenlik

* **Web sürümünde sunucu bulunmaz.** Tüm hesaplar tarayıcıda yapılır;
  veriler tarayıcıda saklanır ve hiçbir yere gönderilmez. Pyodide ve yazı
  tipleri de siteyle birlikte sunulur; açılışta üçüncü taraf bir hizmete
  istek yapılmaz. Bu durum otomatik testle denetlenir.
* **Verinin yedeklenmesi.** Web sürümünde veriler yalnızca kullanılan
  tarayıcıda bulunur. Tarayıcı verileri silindiğinde ya da cihaz
  değiştirildiğinde kaybolur. Ayar bölümündeki **Yedek indir** düğmesiyle
  alınan dosya, yeni cihazda **Yedekten yükle** ile geri yüklenebilir.
* **Çevrimdışı kullanım.** Web sürümü bir kez açıldıktan sonra bağlantı
  olmadan da açılabilir; bu durumda verinin tarihi ekranda belirtilir.
* **Yerel sürüm.** Kişisel veriler yalnızca `data/user.sqlite3` dosyasında
  tutulur; `data/` dizini sürüm denetimine dahil edilmez. Yerel sunucu
  yalnızca `127.0.0.1` adresinden erişilebilir.
* `make ui` ile üretilen `data/itucap.html` dosyası kişisel notları içerir;
  paylaşılmamalıdır.
* Araç OBS şifresi istemez, OBS'de oturum açmaz ve ders kaydı yapmaz.

## Mimari

```
src/itucap/
  sources/       OBS ve İTÜ Helper veri toplayıcıları
  pipeline.py    komut satırı ve veri güncelleme adımları
  normalize.py   ders kodu, havuz etiketi ve saat normalleştirme
  prereq.py      önşart ayrıştırıcı ve not ölçeği
  rules.py       plan yuvası doldurma, denklik kapanışı, plan ilerlemesi
  sequence.py    önşart kademeleri (kritik yol)
  recommend.py   aday puanlama ve çakışmasız program arama
  policy.py      mevzuat: kredi yükü, GNO eşikleri, kredi şartları
  yolharitasi.py çok dönemli mezuniyet planı
  notlar.py      not dağılımları ve tahmini zorluk
  progress.py    ilerleme paneli
  basvuru.py     başvuru uygunluğu taraması
  discover.py    aday denklik keşfi
  changes.py     anlık görüntü ve değişiklik raporu
  watch.py       kontenjan izleme
  plans.py       plan çözümleme (web sürümü için veri toplama bağımlılığı yoktur)
  istek.py       istek süresince önbellek
  server.py      uygulama durumu ve uç yönlendirmesi
  ui.py          tek dosyalık HTML arayüz üreticisi
  tasarim.py     tasarım sistemi (renk, yazı, aralık ölçekleri)
  simge/         uygulama simgesi (ana ekran, sekme; tools/simge_uret.py üretir)
tools/
  site_kur.py            statik site üreticisi
  gizlilik_denetimi.py   kişisel veri sızıntısı denetimi
  tasarim_envanteri.py   CSS envanteri ve ölçek denetimi
  kontrast_olcumu.py     renk kontrastı ölçümü
  vitrin.py              örnek öğrenciyle arayüz ve ekran görüntüsü
  simge_uret.py          uygulama simgesinin PNG/SVG dosyaları
web/
  app.js, sw.js          tarayıcı çalıştırıcısı (Pyodide, IndexedDB, çevrimdışı önbellek)
```

Uygulama durumu (`server.State`) iki taşıyıcı tarafından ortak
kullanılır: yerel HTTP sunucusu ve tarayıcıdaki Pyodide. Uç yönlendirmesi
tek bir yerde (`State.dispatch`) tanımlıdır; böylece iki sürüm aynı
davranışı gösterir.

Veriler iki ayrı veritabanında tutulur: herkese açık katalog
(`reference.sqlite3`) ve kişisel veriler (`user.sqlite3`). Kullanıcının
denklik beyanları da kişisel veri kabul edilir ve yalnızca
`user.sqlite3` dosyasında saklanır.

Ölçüme dayalı tasarım kararlarının gerekçeleri `docs/` dizinindeki faz
belgelerinde yer almaktadır.

## Test ve kalite güvencesi

```bash
make test
```

* Test takımı 1.750'yi aşkın test içerir: motor kuralları küçük, elle
  kurulmuş kataloglarla; uçtan uca davranış ise örnek öğrenciyle gerçek
  tarayıcıda (Playwright) sınanır. Playwright kurulu değilse tarayıcı
  testleri atlanır.
* Yeni kurallar, kod bilinçli olarak bozulduğunda testlerin başarısız
  olduğu doğrulanarak (mutasyon denetimi) eklenir.
* Gizlilik denetimi (`tools/gizlilik_denetimi.py`) üretilen sitenin
  içeriğini tarar; kişisel denklik beyanı, yerel dosya yolu ya da öğrenci
  verisi bulunursa yayımlama durdurulur.
* Tasarım denetimi, arayüzde tasarım ölçeği dışında bir değer
  kullanılmadığını doğrular.

## Web sürümünün yayımlanması

Web sürümü GitHub Pages üzerinden yayımlanır. GitHub Pages'in ücretsiz
planı yalnızca herkese açık depolarda çalışır.

```bash
make refresh
gh release create katalog-$(date +%Y%m%d) data/reference.sqlite3
```

Katalog (yaklaşık 15 MB) depoya eklenmez; yayımlama akışı
(`.github/workflows/pages.yml`) en son `katalog-*` sürümünden kataloğu
indirir, siteyi kurar ve yayımlamadan önce gizlilik denetimini çalıştırır.
Akış, `main` dalına kod gönderildiğinde, yeni bir sürüm yayımlandığında ya
da elle tetiklendiğinde çalışır. Yerel deneme için `make site` komutu
kullanılabilir.

## Katkı

Hata bildirimleri ve değişiklik önerileri memnuniyetle karşılanır. Bu
süreçte aşağıdaki hususlara dikkat edilmesi rica olunur:

1. **Kişisel veri paylaşılmamalıdır.** Hata bildirimlerinde transkript,
   not ya da `data/` dizinindeki dosyalar yerine hata mesajı ve hatayı
   yeniden oluşturma adımları yeterlidir.
2. **Mevzuat değişiklikleri kaynağıyla bildirilmelidir.** Hatalı bir eşik,
   ilgili madde numarasıyla birlikte bildirilmelidir; `kurallar.toml`
   dosyasında her eşik için `kaynak` ve `dogrulandi` alanları bulunur.
3. **Kural değişikliklerinden önce ilgili faz belgesi incelenmelidir.**
   Kuralların çoğu, gerçek veriyle yapılan ölçümler sonucunda
   düzeltilmiş varsayımlardır.

## Sorumluluk reddi ve lisans

Bu yazılım İstanbul Teknik Üniversitesi'nin resmî bir aracı değildir ve
üniversiteyle kurumsal bir bağı bulunmamaktadır. Veriler OBS ve İTÜ
Helper'dan alınmaktadır; hatalı ya da güncel olmayan bilgiler içerebilir.
Kayıt kararları danışman ve OBS ile doğrulanmalıdır.

Yazılım [MIT Lisansı](LICENSE) ile lisanslanmıştır.
