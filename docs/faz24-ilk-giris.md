# Faz 24 — siteye ilk giren kişi

> Kullanıcı isteği, 24.08.2026:
> *"ders seçim aracı ilk gelen kullanıcılar için biraz karmaşık kalıyor, ux
> konusunda eksikleri bulup kapatabilir misin. ilk kez siteye giren birisi
> gözüyle bak; normal bir ders seçim aracı olarak da kullanılabilir olması
> önemli."*

Yöntem: **boş bir kurulumu gerçekten çalıştırıp** (boş `user.sqlite3`,
`settings.toml` yok) sayfayı tarayıcıda açmak ve ilk giren kişinin
tıklayacağı sırayı adım adım takip etmek. Kod okuyarak bulunamayacak dört
hata bu şekilde çıktı.

---

## Bulunanlar

### ★★ 1. İlk giren herkes GELİŞTİRİCİNİN raporunu görüyordu

`config.Settings` varsayılanları `anadal_program="HTAE"`,
`cap_program="BLG"` idi — geliştiricinin kendi bölümleri. `tools/site_kur.py`
`settings.toml`'u siteye **koymuyor** (kişisel dosya), dolayısıyla yayınlanan
sitede varsayılanlar geçerliydi.

Sonuç: siteye ilk giren kişi eksiksiz bir rapor görüyordu — haftalık ızgara,
"%0 tamamlandı, 54 ders kaldı", ÇAP kademeleri. **Hiç seçmediği bir bölümün
raporu**, seçtiği sanılarak.

**Kapatma:** varsayılanlar boş. Boş varsayılanın yan etkisi de kapatıldı:
`cap_program` yazan ama `second_kind` yazmayan eski bir `settings.toml`'da
ÇAP sessizce kaybolurdu — tür artık ilan edilen program kodlarından
türetiliyor.

### ★★ 2. İlk kaydetme uygulamayı KİLİTLİYORDU

`config.update_settings` dosya yokken içeriği `["[student]"]` ile kuruyor,
sonra eklenecek anahtarlar için `[student]` bloğunun sonunu arıyordu. Ama
`student_end` yalnız **içerik** satırlarında güncelleniyordu; boş blokta
`-1` kalıyor ve ikinci bir başlık ekleniyordu:

```toml
[student]

[student]
anadal_program = "BLG"
```

`tomllib` bunu `Cannot declare ('student',) twice` diye reddediyor. Yani:
ilk kullanıcı bölümünü seçiyor, Kaydet'e basıyor, **uygulama bir daha
açılmıyor** — her istek ham bir JSON hatası döndürüyor.

**Kapatma:** başlığın kendisi de çapa sayılıyor. Üç test: dosya yokken,
elle yazılmış boş blokta, ve üç ardışık kaydetmede.

### ★ 3. Bölüm kutusu "AIN"de açılıyordu

Seçim kutusunda boş seçenek yoktu; liste alfabetik ilk bölümde (AIN)
duruyordu. Kutuya dokunmadan Kaydet'e basan herkes o bölüme yazılıyordu —
üstelik *seçtiğini sanarak*. Ayrıca seçenekler yalnız koddu; kimse kendi
OBS program kodunu ezbere bilmiyor.

**Kapatma:** `— bölümünü seç —` gerçek bir seçenek; etiketler `KOD — Ad`
(yerleşik yazarak-arama ikisine de çalışıyor); boş anadal hem arayüzde hem
sunucuda reddediliyor; liste **yalnız lisans planı olan 127 bölüm** —
seçtirip sonra "plan yok" demek, seçim sunmamaktan kötü.

### ★ 4. Bilinmeyen, bilinen gibi gösteriliyordu

Transkript girilmemiş kişide:

* üst çubuk **"dönem yükü sınırı 35 kredi"** diyordu — GNO yokken bu
  hesaplanmış bir sayı değil, varsayılan;
* "Başvurabilir miyim" **her eşiği ✗** işaretliyordu — hakkında hiçbir şey
  bilmediğimiz kişiye "başvuramazsın" demek;
* alt bilgi **"bu dosya notlarını içerir — paylaşma"** diyordu — girmediği
  bir veriyi sızdırdığını sandırıyor.

**Kapatma:** üçü de veri gelene kadar susuyor. `basvuru._checks` artık
`has_data=False` ile **her şartı `ok=None`** döndürüyor (üç durumlu işaret
zaten vardı, kullanılmıyordu).

---

## Kapatılan diğer eksikler

| Ne | Neden sorundu |
|---|---|
| Karşılama kartı (3 adım, "Aç" düğmeleri) | Ekran, ne yapılacağını söylemeden doluydu |
| Bölüm seçilmeden rapor gizli (`body.kurulum`) | Gösterilecek doğru bir şey yok |
| Kademeler bölümü boşken gizli | Araç "ÇAP aracı" gibi okunuyordu; ÇAP'sız kullanım asıl kullanım |
| "Ders ara" → "Geçtiğin dersler" | Düğme geçilen dersleri açıyordu; ilk giren "alacağım dersi arayacağım" diye tıklıyordu |
| Aday tablosunda arama + rol + kontenjan süzgeci | Liste 30'da kesiliyordu: 31. sıradaki ders arayana **yok** görünüyordu |
| "Plandan işaretle" çıkmazı | Program seçilmeden "Plan bulunamadı." diyordu; artık sebebi ve çıkış yolu var |
| "Kayıt yapabildiğin program kodları" → Gelişmiş | Nadir kullanılan bir metin kutusu, zorunlu alanların yanındaydı |
| `445 lisans programı` → `127 bölüm` | `plan` tablosunda her bölümün birden çok sürümü var; satır saymak yanlış sayı veriyordu |
| `[hidden]{display:none !important}` | `display` kuran her sınıf (`.ghost`, `.radios`) `hidden`'ı sessizce eziyordu |

---

## Yeni testler

`tests/test_ilk_giris.py` (25) · `tests/test_server.py` (+3, ayar yazıcısı) ·
`tests/test_basvuru.py` (+2, transkriptsiz sözleşme). Toplam **689**.

İki tanesi ayrıca bir **hata sınıfını** kapatıyor:

* `test_sayfanin_JS_i_AYRISIYOR` — şablon dizesinin içindeki bir yorumda ters
  tırnak kullanmak şablonu orada kapatıyor ve **tüm sayfa betiği** ayrışmaz
  hale geliyor. (Bu faz sırasında gerçekten oldu.) Eskiden bu yalnız
  `test_kademe_baglari` içinde, ilgisiz bir iddianın yan etkisi olarak
  yakalanıyordu ve hata mesajı "çizgiler çizilmedi" diyordu.
* `test_display_kuran_sinif_hidden_i_EZEMEZ` — kuralı yazmak yetmiyor,
  tarayıcıda `[hidden]` olup da görünen öğe kalmadığı ölçülüyor.

---

## Ölçüm

Boş kurulumda baştan sona yürüyüş (Playwright, `127.0.0.1:8791`):

```
A. adım2 program yokken: ÖNCE BÖLÜMÜNÜ SEÇ  (çıkmaz değil, yönlendiriyor)
C. kurulum modu:         ''                  (bölüm seçilince rapor açıldı)
D. üst çubuk:            3417 açık şube · dönem yükü sınırı: transkript girilince
E. kurulum çubuğu:       BLG anadal · ikinci program yok · 3. dönem (beyan)
G. karşılama kartı:      gizli                (üç adım bitti)
H. üst çubuk:            … · dönem yükü sınırı 22 kredi · 3. dönem (beyan)
I. aday sayacı:          25 aday
sayfa hatası:            []
```
