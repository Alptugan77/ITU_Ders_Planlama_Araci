# itucap

İTÜ'de **çift anadal (ÇAP)** veya **yandal** yapan öğrenciler için ders
planlama aracı. Kendi bilgisayarında çalışır, verin senin makinenden çıkmaz.

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
* **Darboğaz raporu** — bir ders neden alınamıyor: önşart mı, kontenjan mı,
  programa kapalı mı, kredi eşiği mi.

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
| Duramayacağımız sayı | Hiç gösterilmez (bkz. başvuru ekranında kalan kredi) |

Hesaplanan GNO bir **tahmindir**, OBS'nin resmi ortalaması değildir; arayüz
bunu her yerde yazar.

## Gizlilik

* Notların yalnız `data/user.sqlite3` dosyasında; o dosya **`.gitignore`da**.
* Ders kataloğu (`data/reference.sqlite3`) herkese açık veri, ayrı dosyada.
* Yerel sunucu **yalnız `127.0.0.1`**'e bağlanır. Dışarı açmak için
  tasarlanmadı; portu tünelleme.
* Üretilen `data/itucap.html` **notlarını içerir** — paylaşma.
* Araç OBS şifresi istemez, oturum açmaz, senin adına kayıt yapmaz.

## Kurulum

Python 3.11+ gerekiyor (`tomllib` için).

```bash
git clone https://github.com/<kullanıcı>/itucap.git
cd itucap
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
  ui.py         tek dosyalık HTML arayüz üretici
  server.py     yerel sunucu (127.0.0.1, jeton + Origin denetimi)
```

İki veritabanı ayrı tutuluyor: `reference.sqlite3` (herkese açık katalog) ve
`user.sqlite3` (senin notların). Ayrım kasıtlı — kişisel veri tek bir dosyada
toplanıyor, yedeklemesi ve silmesi kolay.

## Test

```bash
make test        # 395 test
```

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
