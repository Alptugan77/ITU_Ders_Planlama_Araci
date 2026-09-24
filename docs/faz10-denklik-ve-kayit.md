# Faz 10 — Denklik keşfi, tüm programlar, CRN listesi

> ⚠️ Bu belgedeki bütün sayılar **örnektir**. Repoda kimsenin gerçek notu
> ya da ortalaması yer almaz — kişisel veri `data/` altında kalır ve
> `.gitignore` ile dışarıda tutulur.


```bash
make suggest                 # aday denklikler
make all-plans               # HER programın ÇAP/yandal planı (yavaş, OBS gerekir)
make app                     # Denklikler paneli · CRN listesi · programı kaydet
```

## ★ "Eşliği olanlar otomatik geçildi sayılsın"

Kullanıcı 21.08.2026: *"eşliği olanlar otomatik geçildi sayılsın, mesela ben
BBF 103 aldım."*

Motor bunu **Faz 2'den beri yapabiliyordu**: `rules.expand_with_equivalences()`
denklikleri transitif olarak uyguluyor, denklikle kazanılan ders slotu
dolduruyor. Eksik olan mekanizma değil, **veriydi** — D3'te ölçtük, OBS bu
çift için hiç denklik yayınlamamış. Kullanıcının her denkliği elle
`config/denklikler.toml`'a yazması gerekiyordu.

Yeni `discover.py` eksik parçayı dolduruyor: **aday denklikleri buluyor.**

```
BBF 103E  "Discrete Mathematics"  3 kredi   (aldın)
BLG 112E  "Discrete Mathematics"  3 kredi   (ÇAP planında)
→ aynı ders adı, aynı kredi                 [YÜKSEK GÜVEN]
```

Uygulayınca ÇAP ilerlemesi **%15 → %20** oldu ve `BLG 112E` adaylardan çıktı.

### Neden otomatik UYGULAMIYORUZ

Ad eşleşmesini ölçtüm: katalogda 1987 aynı-adlı grup var, 827'si farklı bölüm
öneki taşıyor. "Fluid Mechanics" adını taşıyan **17 ayrı ders** var.

Yanlış bir denkliği sessizce uygulamak bu projedeki en kötü hata olurdu:
öğrenci tamamlamadığı bir şartı tamamlanmış sanar, dersi almaz, mezun olamaz.
O yüzden buradaki iş **öneri** — aday bulunur, güven hesaplanır, gerekçesi
yazılır; uygulamak tek tık ama **kullanıcının tıkı**.

Aramanın kendisi de dar tutuluyor: yalnız (a) transkriptindeki geçilmiş
dersler ile (b) planlarının **dolmamış** slotları. 4600 derslik katalogda kör
arama yapılmıyor.

### Güven nasıl hesaplanıyor

| Sinyal | Etki |
|---|---|
| aynı ders adı | giriş şartı |
| aynı kredi | **yüksek** |
| kredi farklı | düşük |
| aynı ders numarası | gerekçeye eklenir |
| dil eki farklı (`BLG 112` ↔ `BLG 112E`) | yükseği düşüğe indirir |

İki koruma daha:

* **Roma rakamı korunuyor.** `Fluid Mechanics I` ile `II` aynı ders değil;
  eki temizleseydik yanlış denklik üretirdik.
* **Kısa adlar elenmiyor.** "Staj" gibi 6 harften kısa adlar ayırt etmiyor.

### ★ Geri alınabilir olmalı

Tek tıkla uygulanan şey tek tıkla kaldırılabilmeli. `declared.remove()`
`denklikler.toml`'daki bloğu satır bazlı siliyor — yorumlar ve
`[[muafiyet]]` blokları olduğu gibi kalıyor — sonra `apply()` yeniden
senkronluyor. Arayüzde "uygulanmış beyan" listesi ve yanında **kaldır**.

`apply()` zaten *authoritative*: dosyada olmayan bir beyan veritabanında
kalmıyor. Test bunu kilitliyor.

## ★ Tüm ÇAP ve yandal programları

Faz 7'de ikinci programın türü seçilebilir olmuştu ama `refresh` yalnız
**seçili** programın planını çekiyordu. Sonuç: arayüzdeki seçici tek seçenek
gösteriyordu — seçilebilir ama seçilecek bir şey yok.

```bash
make all-plans        # = refresh --all-programs
```

~129 lisans programı × 2 plan tipi taranıyor. **Varsayılan değil**, çünkü
yavaş: her istek arasında `request_delay_s` bekleniyor. OBS'yi yormamak bu
projenin baştan beri kuralı; bu yüzden ayrı bir komut.

Tarama **kırılgan değil**: bir program hata verirse sayaç artıyor ve tarama
devam ediyor. 129 programın biri yüzünden hepsini kaybetmek olmazdı.

## ★ CRN listesi — zincirin son halkası

Araç haftalık programı kuruyordu ama kayıt günü OBS'ye yazacağın numaraları
ekrandan tek tek okumak gerekiyordu.

**CRN listesi** düğmesi: tek satırda kopyalanabilir CRN dizisi, altında
ders/gün/saat/boş kontenjan tablosu, açılır bölümde **yedek CRN'ler**
(kontenjan dolarsa). Araç senin yerine kayıt yapmıyor — bu liste elle girmen
için.

## ★ Programı kaydet

Izgaradaki düzenleme sayfa kapanınca kayboluyordu. Motorun **önerisi** ile
**senin seçimin** ayrı şeyler: öneri her tazelemede yeniden hesaplanıyor,
seçim ise senin kararın.

`saved_pick` tablosu (dönem bazlı, `user.sqlite3` içinde). Sayfa açılışında
kaydedilmiş program varsa **o** yükleniyor; "Öneriye dön" ikisi arasında
geçiş sağlıyor. Kaydet tam listeyi yazıyor, yani çıkardığın ders kayıtta
kalmıyor.

## ★ Kalite kontrolünün kapsamı büyüdü

İlk `make all-plans` çalıştırmasında tarama sorunsuzdu — **1081 plan, 23246
slot, 0 hata** — ama `make` şununla düştü:

```
❌ [cap_plan_size] ÇAP planı ders sayısı şüpheli (PARSE HATASI): [(1815, 0)]
make: *** [all-plans] Error 1
```

Kontrol yanlış değildi, **kapsamı** eskiydi. Tek bir ÇAP planı varken
yazılmıştı: o plan bozuksa araç güvenilmezdi, `error` doğruydu. Artık
veritabanında tüm üniversitenin planları var ve plan 1815 başka bir bölümün —
kullanıcının sonuçlarını etkilemiyor, kullanıcının yapabileceği bir şey de yok.

Yeni kural: anomali **senin kullandığın** planlardaysa `error`, değilse `warn`.

```
⚠️  [cap_plan_size] başka programların planlarında anomali — seni etkilemiyor:
    1 plan boş çıktı (1815(MAK: 0 slot))
```

İki ek: mesaj artık **boş plan** ile **60'tan fazla slotlu plan**'ı ayırıyor
(farklı arızalar), ve tazeleme kapanışta ne olduğunu açıkça söylüyor —
`✅ Tazeleme başarılı. (Uyarılar bilgi amaçlı, veri kullanılabilir.)`

Şüpheli bir planı incelemek için:

```bash
make plan-info ID=1815      # ham satır, slot dökümü, OBS bağlantısı
```

## Bir hata: anahtar çakışması

`/api/transcript` cevabı `{"saved": n}` döndürüyordu; snapshot'a eklediğim
`data["saved"]` bunu eziyordu ve kayıt sayacı sessizce kayboluyordu. Test
yakaladı. Snapshot anahtarı `savedPicks` oldu.

## Test kapsamı

279 test (Faz 10'dan 29 yeni).

**Keşif** — BBF 103E → BLG 112E bulunuyor ve yüksek güven alıyor · farklı
kredi güveni düşürüyor · dil eki farkı düşürüyor · geçilmiş slot önerilmiyor ·
kısa adlar elenmiyor · `Fluid Mechanics I` ile `II` eşleşmiyor · zaten beyan
edilmiş tekrar önerilmiyor

**Geri alma** — kaldırma yalnız eşleşen bloğu siliyor, yorumları ve
`[[muafiyet]]`'i bozmuyor · bilinmeyen hedef no-op · `apply()` dosyayı
otorite kabul ediyor · denklik uygulanınca ders **geçilmiş** sayılıyor ve
slot doluyor

**Kayıt** — kaydet/yükle/temizle · kaydet tam listeyi yazıyor · dönem bazlı ·
HTTP üzerinden gidip geliyor

**Tarama** — yalnız lisans programları · her iki plan tipi · bir program
patlarsa tarama devam ediyor

**Kalite kapsamı** — başka bölümün bozuk planı `warn` · kendi planın `error` ·
boş plan ile şişmiş plan ayrı raporlanıyor · kaynakta boş yayınlanan plan
parse hatası sayılmıyor
