# OBS uçları — WP1.1 çıktısı

> Keşif tarihi: **17 Ağustos 2026**. Tarayıcı DevTools Network kaydı + DOM incelemesi.
> Her dönem başında yeniden doğrula (sayfa yapısı değişebilir).

**Sonuç: OBS ÇAP planları tamamen public ve token gerektirmiyor.**
Anti-forgery token, cookie veya `Referer` başlığı gerekmedi. Kademeli menü
tamamen atlanabiliyor — plan listesi tek bir GET ile alınıyor.

---

## 1. Ders planları (`/public/DersPlan`)

### 1.1 Sabitler

Plan Tipi kodları (`PlanTipiKodu`), `#planTipiId` seçim kutusundan:

| Kod | Anlam |
|---|---|
| `on-lisans` | Ön Lisans |
| `lisans` | Lisans |
| **`cap`** | **ÇAP (Double Degree)** |
| `yandal` | Yandal (Minor) — ⚠️ **plan yayınlanmamış**, aşağıya bak |
| `muhendislik-tamamlama` | Mühendislik Tamamlama |
| `bilimsel-hazirlik` | Bilimsel Hazırlık |
| `yuksek-lisans` / `tezsiz-yuksek-lisans` / `yuksek-lisans-ikinci-ogretim` / `doktora` | Lisansüstü |
| `uolp` | UOLP (DDP) |

Fakülte id'leri (`FakulteId`), ilgili olanlar:

| Id | Fakülte |
|---|---|
| 4 | İnşaat Fakültesi (HTAE burada) |
| 28 | Bilgisayar ve Bilişim Fakültesi (BLG burada) |

### 1.2 Program listesi (kademeli menü) — *isteğe bağlı*

```
POST /public/DersPlan/GetAkademikProgramByBirimIdAndPlanTipi
Content-Type: application/x-www-form-urlencoded
birimId=28&planTipiKodu=cap
```

> ⚠️ **DÜZELTME (22.08.2026):** Parametre adı `birimId` — burada uzun süre
> `akademikBirimId` yazıyordu ve **yanlıştı**. Fark edilmemesinin sebebi bu
> adımın hiç çağrılmamış olması: ÇAP'ta program kodu tahmin edilebildiği için
> ("BLG" → "BLG_LS") kademeli menü atlanıyordu. Yandalda tahmin çalışmıyor ve
> uç ilk kez gerçekten çağrıldı; yanlış parametre **boş cevap** veriyordu —
> hata değil, sessiz sıfır.
>
> Cevap biçimi:
> ```json
> [{"programKodu": "ECN_YD", "programAdi": "Economics (Minor)"},
>  {"programKodu": "BHB_YD", "programAdi": "Informatics Applications … (Minor)"},
>  {"programKodu": "SUS_YD", "programAdi": "Sustainability (Minor)"}]
> ```

Fakülte 28 + `cap` → `YZVE_LS`, `BLG_LS`, `SECE_LS`
Fakülte 4 + `cap` → `INS_LS`, `CEV_LS`, `GEO_LS`, `HTA_LS`

> Bu adım **atlanabilir**: program kodunu (`BLG_LS`) zaten biliyorsan doğrudan 1.3'e geç.

### 1.3 Plan listesi ⭐ *(tek istekte iterasyonlar)*

```
GET /public/DersPlan/DersPlanlariList?PlanTipiKodu=cap&programKodu=BLG_LS
```

HTML tablo döner; her satırda `/public/DersPlan/DersPlanDetay/{id}` linki var.
`BLG_LS` + `cap` için **37 plan**.

### 1.4 Plan detayı — ⚠️ **iki farklı düzen**

```
GET /public/DersPlan/DersPlanDetay/{id}
```

Sütunlar her iki düzende de aynı:

```
Course Code | Course Title | Language | Compulsory/Elective | Credit | ECTS | Teo. | Tutorial | Lab. | Type
```

Son sütun (`Type`) ders kategorisini **doğrudan** verir (`MT`, `TB`, `TM`, `ITB`, `EC`) —
etiket metnini regex'le parse etmekten güvenilir. ÇAP planlarında `LA` / `-` gibi
farklı bir taksonomi görülüyor, o yüzden ham değer `plan_slot.type_raw`'a da yazılır.

**A) Anadal (`lisans`, `uolp`) — dönem başına AYRI tablo**

Örnek: HTAE → plan **2295**, 8 tablo. Her tablonun önünde `<h5>N. Semester</h5>`
başlığı var; tablonun ilk satırı boş, ikinci satırı sütun başlıkları.
`#dersPlanProgramList` tablosu **yok**.

**B) ÇAP (`cap`) — TEK düz tablo**

Örnek: plan **2229**, 22 satır, yarıyıl bilgisi yok, `Z`/`S` sütunu belirleyici.
Ayrıca **`#dersPlanProgramList`** tablosu var — "Associated Programs":
`Birincil Program Kodu | Birincil Program Adı | Güncelleme Tarihi`

> Parser bu ayrımı tablo öncesindeki `N. Semester` / `N. Yarıyıl` başlığına bakarak
> yapar (`obs_plan._term_numbers`). Başlık yoksa plan dönemsiz kabul edilir.

### 1.5 Seçmeli havuz içeriği

```
GET /public/DersPlan/_DersGrupSearch?grupId=11386
```

Partial view (modal). Seçmeli satırın 1. hücresindeki `Courses` linkinden gelir.

---

## 2. Ders denklikleri (`/public/GenelTanimlamalar/DersPlanDenklikleri`)

Form `GET` ile kendine submit eder. **Dört parametrenin hepsi zorunludur:**

```
GET /public/GenelTanimlamalar/DersPlanDenklikleri
    ?ProgramId=871&PlanTipiId=3&PlanId=2229&DersBransKoduId=3
```

Eksik parametre → sayfa `alert('Ders denklik bilgisi bulunamadı.');` döndürür.
**Ders kodunu boş bırakıp "hepsini al" mümkün değil** — döngü kurmak zorunlu.

Kademeli menü uçları (hepsi `POST`, JSON döner, anahtar alan **`objectId`**):

| Uç | Gövde | Örnek yanıt |
|---|---|---|
| `GetPlanTipleriByProgramId` | `programId` | `[{"objectId":2,"planTipiAdiLanguage":"Undergraduate"},{"objectId":3,"planTipiAdiLanguage":"Double Degree"}]` |
| `GetDersPlanlariByProgramIdAndPlanTipiId` | `programId`, `planTipiId` | plan listesi |
| `GetDersBransKodlariByPlanId` | `planId` | `[{"dersBransKodu":"KMM","objectId":6}, ...]` |

> `PlanId` değerleri `DersPlanDetay/{id}` ile **aynı** id uzayındadır (ör. 2229).
> Bu sayfadaki `ProgramId` ise **ayrı bir sayısal id**dir (BLG=871, HTAE=248, KMM=409).

### Ölçüm sonucu — denklik verisi seyrek

| Program | Denenen kombinasyon | Bulunan |
|---|---|---|
| HTAE (248) | 39 | **0** |
| BLG ÇAP planı 2229 | 1 | **0** |
| Kimya Müh. (409/415) | son 2 plan × tüm branşlar | **0** |

**Sonuç:** Bu proje için (HTAE + BLG) OBS'de yayınlanmış ders denkliği YOK.
Scraper "bulunamadı"yı normal karşılar, hata saymaz. Denklik ihtiyacı çıkarsa
`equivalence.confidence = 'user_declared'` ile elle girilecek.

---

## 3. Rate limiting ve nezaket

* İstekler arası **≥1 sn** (`config/settings.toml → request_delay_s`)
* 429/5xx'te exponential backoff (2s → 4s → 8s), 4 deneme
* `User-Agent` içinde araç adı ve amacı
* Her yanıt `data/raw_archive/YYYY-MM-DD/` altına arşivlenir

## 4. Bilinen kısıtlar

* **Bu proje kutusundan (bulut sandbox) `obs.itu.edu.tr` erişilemiyor** (proxy 403).
  Scraper'ı kendi makinenden çalıştır. `--skip-obs` ile itu-helper verisiyle
  çalışmaya devam edilebilir.
* Sayfa saf JS ile render edilmiyor — Playwright'a **gerek yok**, `httpx` yeterli.


---

## Yandal planları VAR — ama program kodu başka (22.08.2026)

> ⚠️ Bu bölüm önce "yandal planı yok" diyordu. **Yanlıştı.** Aşağıdaki
> gözlemler doğru ama sonuç yanlış çıkarılmıştı: yanlış program koduyla
> sorulduğu için boş dönüyordu.

Yandal programları **lisans bölümlerinden bağımsız**, fakülte düzeyinde
tanımlı ve kodları farklı: `ECN_YD`, `BHB_YD`, `SUS_YD`. `BLG_LS` diye
sormak yanlış soru — OBS de doğru cevap veriyor:

```
GET /public/DersPlan/DersPlanlariList?PlanTipiKodu=yandal&programKodu=BLG_LS
→ "Akademik programa bağlı ders planı bulunmamaktadır."   (0 satır)

GET /public/DersPlan/DersPlanlariList?PlanTipiKodu=cap&programKodu=BLG_LS
→ 38 satır  ("CEV_BLG ÇAP Programı 2013-2014 / Güz Dönemi Öncesi" …)
```

Aynı sonuç `END_LS` için de alındı ve `--all-programs` taraması **128
programın hiçbirinde** yandal planı bulamadı.

Doğru kodlar **1.2'deki kademeli menüden** geliyor (fakülte + plan tipi).
`make kesif T=yandal` bunu yapıyor; `make all-plans` artık kodları tahmin
etmek yerine bu keşfi kullanıyor.

### Alınan iki ders

**1. Sessiz sıfır iki kez yanılttı.** Önce `list_programs` cevabı
ayrıştıramadığında boş liste döndü ve "23 fakültede de yandal yok" sanıldı.
Sonra yanlış parametre adı yine boş liste verdi. İkisinde de sıfır, "veri
yok" gibi okundu. Artık: ayrıştırılamayan cevap **ham metniyle** taşınıyor
(`{"_ham": …}`) ve keşif komutu bilinen-dolu bir çiftle **kontrol isteği**
atıyor — kontrol de boşsa sorun bizdedir.

**2. "Atlanabilir" adım, hiç çalıştırılmadığı için bozuk kalabilir.**
Kademeli menü ÇAP'ta gerçekten gereksizdi; o yüzden yıllarca çağrılmadı ve
içindeki yanlış parametre adı hiç ortaya çıkmadı. Kullanılmayan yol, test
edilmemiş yoldur.

---

## 5. Ders not dağılımı (`/public/DersNotDagilimi`)

> Keşif: **2 Eylül 2026**. Kullanıcı hatırlattı; `docs/fikirler.md` bu veriyi
> "elimizde yok" diye reddetmişti. Token, cookie, `Referer` gerekmiyor.

### 5.1 Uç

```
GET /public/DersNotDagilimi/NotDagilimiSearch?bransKodu=MAT&dersNo=103E&yil=2026
```

Sayfanın kendisi de aynı parametreleri kabul ediyor (`?bransKodu=…`) ve
açılışta bu ucu AJAX ile çağırıyor. Cevap bir **HTML parçası**; veri satır içi
betikte:

```js
const ALL_DATA = [{"DonemKodu":"202630","YilAdi":"2025-2026",
                   "DonemTipAdi":"Summer Semester",
                   "ToplamAciklananOgrenci":991,
                   "Dagilim":[{"HarfNotu":"AA","Sayi":54,"Yuzde":5.45}, …]}, …];
```

★ **Tek istek o yılın bütün yarıyıllarını getiriyor** — güz (`…10`), bahar
(`…20`) ve **yaz** (`…30`).

### 5.2 Üç tuzak (üçü de ölçüldü)

| Tuzak | Ölçüm |
|---|---|
| **TR/EN kodu BİRLEŞİK** | `dersNo=212` ile `dersNo=212E` **bayt bayt aynı** cevabı veriyor (6824 B); başlık `BLG212 - BLG212E` yazıyor. Dağılım ders ÇİFTİNE ait |
| **"Bulunamadı" da HTTP 200** | Olmayan ders `<h4>… could not be found.</h4>` + 200. Durum koduna bakan tarayıcı bunu "hepsi sıfır" kaydederdi |
| **`yil` BİTİŞ yılı** | `yil=2026` → `202610 \| 2025-2026 \| Fall`. Yani `202610` = 2025-2026 Güz. `config.donem_adi` bunu bir yıl ileri yazıyordu |

### 5.3 Ölçülen sayılar (02.09.2026)

* `yil=2027` **boş** — 2026-2027 notları henüz açıklanmamış (beklenen).
* `yil=2019`'a kadar geriye veri var.
* Kaynağın kendi toplamı (`ToplamAciklananOgrenci`) harflerin toplamına
  **her zaman eşit değil**: MAT 103 güz 2988/2987, bahar 1682/1678.
  Aradaki kişiler listelenen 15 harfin dışında (BL/BZ/muafiyet olabilir).
* Kullanıcının planındaki 251 dersten **176**'sında dağılım var, **75**'inde
  yok (dil dersleri, bazı seçmeliler).
* Ders numarası sonunda **birden fazla harf** olabiliyor: `ING 103CO`,
  `ING 103SC`, `FIZ 101EL`.

### 5.4 Yok

Hoca kırılımı **yok** — dağılım ders düzeyinde. Şubenin hocasıyla dersin
dağılımını yan yana koymak, veride olmayan bir nedensellik iddia etmek olurdu.
