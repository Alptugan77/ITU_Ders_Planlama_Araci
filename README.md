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
  ve kritik yolu birlikte değerlendirip haftalık program kuruyor.
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
  bildirim.
* **Geçmiş dönem not dağılımı** — İTÜ'nün her dönem yayınladığı harf notu
  dağılımı (`make notdagilimi`). ⚠️ Dağılım TÜRKÇE VE İNGİLİZCE kodu
  birlikte kapsıyor (kaynak öyle yayınlıyor), geçmiş bir döneme ait ve
  **öneri puanına girmiyor** — hangi dersin değdiği senin kararın.
* **Darboğaz raporu** — bir ders neden alınamıyor: önşart mı, kontenjan mı,
  programa kapalı mı, kredi eşiği mi.
* **Okunur haftalık program** — renk hangi programdan olduğunu (anadal /
  ÇAP / yandal), ton hangi ders olduğunu söylüyor. ⚠️ Ton merdiveni ölçüyle
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

## Gizlilik

* **Web sürümünde sunucu yok.** Notların tarayıcında hesaplanıyor,
  tarayıcında saklanıyor, hiçbir yere gönderilmiyor: uç yok, istek yok,
  telemetri yok. Pyodide **ve yazı tipleri** CDN'den değil siteden
  geliyor — açılışta üçüncü bir tarafa haber verilmiyor. Ölçülüyor:
  üretilen HTML'de tek bir dış kaynak bile geçemiyor (test).
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
  server.py     State + yönlendirme; iki taşıyıcı da bunu kullanır
tools/
  site_kur.py            statik site üretici (katalogu budar + temizler)
  gizlilik_denetimi.py   kişisel veri sızıntısı denetimi
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
make test        # 1102 test + gizlilik denetimi
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
