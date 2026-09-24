# İTÜ DEPAR

**DE**rs **P**lanlama **AR**acı — kısaltma uydurma değil, açılımın kendisi.

İTÜ'de **çift anadal (ÇAP)** veya **yandal** yapan öğrenciler için ders
planlama aracı. Kendi bilgisayarında çalışır, verin senin makinenden çıkmaz.

> Python paketi ve import yolu `itucap` olarak kalıyor — `pip install -e .`,
> `python -m itucap.pipeline` gibi her şey aynı. Değişen aracın **görünen
> adı**; depo adı ve site adresi de aynı.

> ⚠️ Bu araç **bilgilendirme amaçlıdır**. Ders kayıt kararların için
> danışmanına ve OBS'ye danış. Araç senin adına **kayıt yapmaz**, OBS
> şifreni **istemez**.

---

## Ne yapar

İki programın planını aynı anda tutmak, elle takip edilmesi zor bir iş: hangi
ders hangisine sayılıyor, hangi önşart açık, bu dönem hangi kombinasyon
çakışmıyor, kredi tavanını aşıyor muyum. Araç bunları hesaplıyor:

* **Çakışmasız program önerisi** — açık şubeleri, önşartları, kredi tavanını
  ve kritik yolu birlikte değerlendirip haftalık program kuruyor. Tercihlerin
  (erken saat, boş gün, kampüs, hoca) sıralamayı etkiliyor ve **kaydetmeden
  denenebiliyor**: 1. önerinin nasıl değişeceği yan yana gösteriliyor.
* **İlerleme paneli** — anadal ve ikinci program ayrı ayrı; "bu dönemi
  bitirirsen nerede olursun" taramalı katmanla gösteriliyor.
* **Önşart motoru** — katalog metnini ayrıştırıp (`MAT 103 MIN DD veya ...`)
  ağaç kuruyor; denklik ve muafiyet beyanlarını hesaba katıyor.
* **Mevzuat kontrolü** — dönem kredi yükü (MADDE 17), GNO eşikleri, bitirme
  çalışması kredi şartı. Hepsi `config/kurallar.toml`'da **beyan edilmiş**,
  koda gömülmemiş.
* **"Başvurabilir miyim"** — hangi ÇAP/yandal programlarına başvurabilirsin,
  hangisinde kaç dersin zaten sayılıyor.
* **Kontenjan nöbeti** — `make watch` ile izlediğin derste yer açılınca
  bildirim. macOS'ta `make watch-kur` onu **arka planda** çalıştırıyor:
  terminal gerekmiyor, oturum açılınca kendiliğinden başlıyor
  (`make watch-durum`, `make watch-kaldir`).
* **Geçmiş dönem not dağılımı** — İTÜ'nün her dönem yayınladığı harf notu
  dağılımı (`make notdagilimi`). ⚠️ Dağılım TÜRKÇE VE İNGİLİZCE kodu
  birlikte kapsıyor (kaynak öyle yayınlıyor), geçmiş bir döneme ait ve
  **öneri puanına girmiyor** — hangi dersin değdiği senin kararın.
* **Darboğaz raporu** — bir ders neden alınamıyor: önşart mı, kontenjan mı,
  programa kapalı mı, kredi eşiği mi.
* **Mezuniyet yol haritası** — kalan dersler dönem dönem: önşart sırası,
  dönem kredi sınırın, dersin açıldığı mevsim ve ÇAP yarıyıl tabanı hesaba
  katılıyor; her programın tahmini bitişi planındaki bitişle
  karşılaştırılıyor ve **"bu dönem şunu alırsan N dönem erken bitersin"**
  yazıyor — yük sınırını aşıyorsa hangi dersin çıkabileceğiyle. Planda
  mevsimi olmayan dersin mevsimi geçmiş not dağılımından okunuyor
  (bütünleme için açılan birkaç kişilik not listesi sayılmadan); geçen yaz
  açılmış ders için **"yazın alırsan"** hesabı da var. Bitişin kaçıncı
  yarıyıl olduğu ve azami öğrenim süresi (14 yarıyıl) kartta yazıyor;
  ÇAP başvuru penceresi her program için **"bu ÇAP'la ne zaman bitirirsin"**
  sorusunu da cevaplıyor. **Senaryo**: "dönemde en çok 18 kredi", "şu dönem
  Erasmus'tayım" — harita kaydetmeden yeniden kuruluyor ve bugünkü plana göre
  farkı yazıyor.
* **Danışman özeti** — görüşmeye götürülecek tek sayfa: bu dönemin programı
  CRN'leriyle, kredi/taban/GNO kontrolleri, tahmini bitiş ve yalnız ölçülen
  sorunlardan çıkan **"danışmana sorulacaklar"**. Yalnız o sayfa basılıyor. ⚠️ Bir plan, kehanet
  değil: varsayımları (her ders ilk denemede geçilir, gelecek dönemlerin
  şubesi bilinmiyor, geçen yıl açılması bu yıl açılacağı demek değil)
  haritanın üstünde yazıyor.
* **GNO hedefi** — eşikte kalmak (ÇAP'a devam, mezuniyet, bir üst kredi
  bandı, ÇAP'ın kendi ortalaması) için bu dönem **en az** hangi ortalama
  gerekiyor; tekrar aldığın dersin eski notu düşülerek. Tahmin değil,
  gereken notun hesabı.
* **Okunur haftalık program** — renk hangi programdan olduğunu (anadal /
  ÇAP / yandal), ton hangi ders olduğunu söylüyor; seçtiğin şube doluysa
  ya da son birkaç yeri kaldıysa blokta **DOLU / SON N** yazıyor; dolu
  şubenin yerine boş ve çakışmayan bir şube varsa özetten **tek dokunuşla**
  geçiliyor. Özet haftanın şeklini de yazıyor (kaç gün kampüstesin, en uzun
  ara); program `.ics`, bağlantı ya da **resim (PNG)** olarak dışarı
  alınabiliyor. ⚠️ Ton merdiveni ölçüyle
  seçildi: yazı kontrastı iki temada da WCAG AA'nın (4.5) üstünde, 9 tondan
  sonrası tekrar ediyor ve bunu ekranda **yazıyor**.

## Tasarım ilkesi: bilinmeyen, bilinen gibi gösterilmez

Bu araç bir öğrencinin mezuniyet planı hakkında konuşuyor; yanlış bir "evet"
gerçek bir zarar. O yüzden baştan beri tek bir kural işliyor:

| Durum | Ne yapılıyor |
|---|---|
| Mevzuattan doğrulanmamış eşik | ⚠ ile işaretlenir, kesinmiş gibi gösterilmez |
| Hesaplanamayan şart (ör. başarı sıralaması) | `—` "buradan bakılamaz" — atlanmaz, "sağlandı" sayılmaz |
| Notu girilmemiş ders | En kötü durum (DD) varsayılır — eşik yanlışlıkla açılmasın |
| Ad benzerliğinden çıkan denklik | **Önerilir**, otomatik uygulanmaz (17 dersin adı "Fluid Mechanics") |
| Bir dersi eleyen kural | Kendini gösterir — "GEO 4901E neden kayboldu" sorusu sorulmasın |
| Önşart, katalogda olmayan bir dersi istiyor | Ayrı kategori: *"önşartı katalogda yok"* — olmayan bir dersi aramaya gönderilmiyorsun (16 ders) |
| Kaçıncı dönemde olduğun bilinmiyor | Program **her dönemden** ders karıştırır ve bunu ölçüp yazar ("7 ayrı dönemden: 1.'den 4, 7.'den 3") — dönem **tahmin edilmez** |
| Duramayacağımız sayı | Hiç gösterilmez (bkz. başvuru ekranında kalan kredi) |

Hesaplanan GNO bir **tahmindir**, OBS'nin resmi ortalaması değildir; arayüz
bunu her yerde yazar.

## Tasarım sistemi

Arayüzün jetonları (renk, yazı, aralık, katman, hareket) tek bir yerde:
`src/itucap/tasarim.py`. Sayfanın gece/gündüz/kâğıt paletleri oradan
**üretiliyor**; kontrast ve ton ölçüm araçları da aynı kaynağı okuyor.
`python tools/tasarim_envanteri.py --denetle` elle yazılan CSS'te ölçek dışı
bir değer (ör. `font-size:12.5px`, `#ff0000`) kalmadığını denetliyor — test
paketinin parçası. Gerekçe ve ölçümler: `docs/faz56-tasarim-sistemi-v2.md`.

## Gizlilik

* **Web sürümünde sunucu yok.** Notların tarayıcında hesaplanıyor,
  tarayıcında saklanıyor, hiçbir yere gönderilmiyor: uç yok, istek yok,
  telemetri yok. Pyodide **ve yazı tipleri** CDN'den değil siteden
  geliyor — açılışta üçüncü bir tarafa haber verilmiyor. Ölçülüyor:
  üretilen HTML'de tek bir dış kaynak bile geçemiyor (test).
  ⚠️ Bunun bedeli: veri **yalnız o tarayıcıda**. Tarayıcı verisini silersen
  ya da cihaz değiştirirsen gider — Ayar görünümündeki **Yedeğini indir**
  bir JSON dosyası veriyor, yeni cihazda ilk karttan "yedeğinden devam et"
  ile geri yükleniyor (ikisi de tamamen tarayıcıda).
* **Kayıt günü bağlantı yoksa da açılıyor.** Web sürümü bir kez açıldıktan
  sonra kendi dosyalarının (sayfa, motor, katalog, Pyodide) kopyasını
  tarayıcıda tutuyor; başka hiçbir yere dokunmuyor. Kopyadan açılınca sayfa
  bunu **verinin tarihiyle** söylüyor — eski kontenjan canlıymış gibi
  gösterilmiyor.
* Yerel sürümde notların yalnız `data/user.sqlite3` dosyasında; `data/`
  klasörünün tamamı **`.gitignore`da**.
* Ders kataloğu (`data/reference.sqlite3`) herkese açık veri, ayrı dosyada.
* Yerel sunucu **yalnız `127.0.0.1`**'e bağlanır. Dışarı açmak için
  tasarlanmadı; portu tünelleme.
* Üretilen `data/itucap.html` **notlarını içerir** — paylaşma.
* Araç OBS şifresi istemez, oturum açmaz, senin adına kayıt yapmaz.

## İki kullanım yolu

| | Nerede çalışır | Veri nerede | Ne gerekir |
|---|---|---|---|
| **Web** | tarayıcıda (Pyodide) | senin tarayıcında (IndexedDB) | yok — siteyi aç |
| **Yerel** | kendi bilgisayarında | `data/user.sqlite3` | Python 3.11+ |

Web sürümü aynı motoru çalıştırıyor — JavaScript'e çevrilmiş bir kopya değil,
Python'un WebAssembly derlemesi. Yani iki sürüm ayrışamaz. Farkı yalnız
**veri tazeleme**: OBS'den tarama kendi makinende yapılıyor, web sürümü
siteyle birlikte yayınlanan katalogu kullanıyor.

### Siteyi kendin yayınla

Site: <https://alptugan77.github.io/ITU_Ders_Secim_Araci/>

⚠️ **Depo herkese açık olmalı.** GitHub Pages ücretsiz planda yalnız public
depolarda çalışıyor (private için GitHub Pro / Team gerekiyor).

```bash
make refresh                     # OBS'den taze katalog
# Katalogu bir sürüm varlığı olarak yükle:
#   gh release create katalog-$(date +%Y%m%d) data/reference.sqlite3
#   (gh yoksa: GitHub -> Releases -> Draft a new release -> etiket
#    "katalog-YYYYAAGG" -> data/reference.sqlite3 dosyasını sürükle)
# Sonra: GitHub -> Actions -> "pages" -> Run workflow
```

Katalog depoya girmiyor (türetilmiş veri, 15 MB); yayın akışı onu sürüm
varlığından indirip siteyi kuruyor ve **yayından önce gizlilik denetimi
çalıştırıyor** — kirliyse yayın durur. Yerelde denemek için: `make site`.

## Kurulum

Python 3.11+ gerekiyor (`tomllib` için).

```bash
git clone https://github.com/Alptugan77/ITU_Ders_Secim_Araci.git
cd ITU_Ders_Secim_Araci
make setup                    # sanal ortam + bağımlılıklar + örnek config
```

Sonra kendi bölümünü tanıt:

```bash
make programs                 # ÇAP/yandal planlarını listeler, id'leri gösterir
$EDITOR config/settings.toml  # anadal_program, cap_program, cap_plan_id
make refresh                  # katalog + planlar + şubeler (OBS'den)
make student                  # transkript şablonu üretir
make app                      # tarayıcıda açılır
```

`make app` yerine `make ui` tek dosyalık statik rapor üretir — sunucusuz,
çift tıkla açılır, ama düzenleme yapamazsın.

## Günlük kullanım

```bash
make app                      # ana arayüz (düzenlenebilir)
make basvuru                  # hangi programlara başvurabilirim
make recommend                # komut satırında program önerisi
make progress                 # ilerleme paneli
make changes                  # son iki tazeleme arasında ne değişti
make notdagilimi              # geçmiş dönemlerin harf notu dağılımı
make watch                    # kontenjan nöbeti (kayıt haftası)
make watch-kur                # aynı nöbet ARKA PLANDA (macOS; watch-durum / watch-kaldir)
make status                   # veritabanı özeti
make test                     # test paketi
```

Transkriptini arayüzden girmek en kolayı: **Plandan işaretle** düğmesi planın
derslerini dönem dönem listeliyor, tik atıp not seçiyorsun.

## Yapılandırma

`config/` altındaki dosyalar elle düzenlenebilir ve **yorumları korunur**:

| Dosya | Ne | Depoda mı |
|---|---|---|
| `settings.toml` | hangi program, hangi dönem, kredi tavanı | ❌ kişisel (`.example` var) |
| `denklikler.toml` | senin denklik ve muafiyet beyanların | ❌ kişisel (`.example` var) |
| `kurallar.toml` | mevzuat eşikleri (GNO, kredi yükü, bitirme) | ✅ herkese ait |
| `katalog-duzeltmeleri.toml` | OBS kataloğundaki hataların düzeltmesi | ✅ herkese ait |

Mevzuat değişirse `kurallar.toml` düzenlenir — **kod değişmez**. Her eşik
kaynağını (madde numarası) ve doğrulanma durumunu taşır.

## Mimari

```
src/itucap/
  sources/      OBS ve itu-helper scraper'ları
  normalize.py  ders kodu / havuz etiketi / saat normalleştirme
  prereq.py     önşart ayrıştırıcı (özyinelemeli iniş) + not ölçeği
  rules.py      slot doldurma, denklik kapalılığı, plan ilerlemesi
  sequence.py   önşart kademelendirme (kritik yol)
  recommend.py  aday puanlama + çakışmasız program arama
  policy.py     mevzuat: kredi eşiği, GNO eşikleri, kredi yükü
  basvuru.py    "başvurabilir miyim" taraması
  discover.py   aday denklik keşfi (ad + kredi eşleşmesi)
  changes.py    anlık görüntü ve fark
  watch.py      kontenjan nöbeti
  plans.py      plan çözümleme (tarama bağımlılığı YOK — web için şart)
  ui.py         tek dosyalık HTML arayüz üretici
  tasarim.py    tasarım sistemi v2: palet ve ölçeklerin TEK kaynağı
  server.py     State + yönlendirme; iki taşıyıcı da bunu kullanır
tools/
  site_kur.py            statik site üretici (katalogu budar + temizler)
  gizlilik_denetimi.py   kişisel veri sızıntısı denetimi
  tasarim_envanteri.py   CSS envanteri + ölçek denetimi (--denetle, --jetonlar)
  kontrast_olcumu.py     palet kontrastı (70 çift, iki tema)
  vitrin.py              gerçekçi UYDURMA öğrenciyle arayüzü aç / ekran görüntüsü
web/app.js               tarayıcı çalıştırıcısı (Pyodide + IndexedDB)
```

`State` iki taşıyıcıyla kullanılıyor: yerel HTTP sunucusu ve tarayıcıdaki
Pyodide. Yönlendirme `State.dispatch()`'te tek yerde — kopyalansaydı iki
sürüm zamanla ayrışırdı.

İki veritabanı ayrı tutuluyor: `reference.sqlite3` (herkese açık katalog) ve
`user.sqlite3` (senin notların). Ayrım kasıtlı — kişisel veri tek bir dosyada
toplanıyor, yedeklemesi ve silmesi kolay.

**Denklik beyanların da `user.sqlite3`'te** (Faz 28). Daha önce referans
veritabanına yazılıyorlardı; `declared.py` "bunlar müfredat bilgisi, kişisel
değil" diyordu ama `tools/gizlilik_denetimi.py` yayınlanan katalogda beyan
görünce hata veriyordu — aynı soruya iki farklı cevap. Denetim haklıydı:
*"şu dersim şunun yerine saysın"* beyanı hem hangi dersi aldığını hem neye
başvurduğunu ele verir. Eski veritabanlarında kalmış beyanlar açılışta
siliniyor ve `config/denklikler.toml`'dan kullanıcı veritabanına yeniden
uygulanıyor; kaynak dosya değişmediği için hiçbir beyan kaybolmuyor.

## Test

```bash
make test        # 1238 test + gizlilik denetimi
```

Gizlilik denetimi (`tools/gizlilik_denetimi.py`) dosya adına **değil
içeriğine** bakıyor: kurulmuş siteyi açıp katalogda kişisel denklik beyanı,
yerel dosya yolu ya da öğrenci tablosu arıyor. Bir kez sızan veri geri
alınamaz, o yüzden yayın hattının zorunlu adımı.

Playwright kuruluysa tarayıcı testleri de koşar; kurulu değilse atlanır —
proje bağımlılığı değil.

## Katkı

Sorun bildirimi ve PR açık. İki şey rica:

1. **Kişisel veri gönderme.** Hata bildirirken transkript, not ya da
   `data/` altındaki dosyaları paylaşma; hata mesajı ve adımlar yeterli.
2. **Mevzuat değişikliğini kaynağıyla bildir.** Bir eşik yanlışsa madde
   numarasıyla söyle; `kurallar.toml`'da `dogrulandi` ve `kaynak` alanları var.

Ölçüme dayalı kararların gerekçesi `docs/` altındaki faz belgelerinde. Bir
kuralı değiştirmeden önce oraya bak — çoğu, gerçek veriyle karşılaştırma
sonucu düzeltilmiş bir varsayım.

## Sorumluluk reddi

Bu resmî bir İTÜ aracı **değildir** ve İTÜ ile bir ilişkisi yoktur. Veriler
OBS ve itu-helper'dan alınır, hatalı ya da güncel olmayabilir. Kayıt
kararlarını danışmanına ve OBS'ye doğrulat.

## Lisans

[MIT](LICENSE)
