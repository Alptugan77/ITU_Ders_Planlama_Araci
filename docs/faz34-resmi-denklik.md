# Faz 34 — OBS resmî ders denklikleri

*28.08.2026 · kullanıcı isteği: "ders denkliklerini bu siteden çekmek lazım
https://obs.itu.edu.tr/public/GenelTanimlamalar/DersPlanDenklikleri" ve
"başka fakülteden ders denkliği olan bir dersi dilekçe ile alabileceğime dair
bir kısım (hangi dersin dengi, saat kaçta gibi bilgileri içersin)"*

## Ne değişti

Denkliği açık bölümü artık **beyanların yanında OBS'nin resmî ders
denkliklerini** de gösteriyor: almam gereken bir dersin resmî bir karşılığı bu
dönem açıksa, **başka bölümden** o dersi (dilekçeyle) alıp saydırabileceğimi
CRN/saat/hoca/kontenjan ile listeliyor.

Örnek (gerçek katalog): `BLG 317E Database Systems` gerekiyor → resmî denkliği
`BBF 302` bu dönem açık (Çar 08:30–11:29, Ali Çakmak, 160 boş). "OBS resmî
ders denkliği — **başka bölümden**; dilekçeyle saydırılır."

## Neden Ağustos'ta "0 denklik" görülmüştü — iki ayrı hata

Scraper vardı (`sources/obs_equivalence.py`) ama iki sebeple boş dönüyordu:

1. **Parser yapışık kodu okuyamıyordu.** Sayfa hücreleri `KOD Ad` biçiminde ve
   kod isme YAPIŞIK: `BLG 202Numerical Methods in CE`. Eski `\b([A-Z]{2,4})\s?
   (\d{3,4}...)\b` regex'i rakam ile ismin ilk harfi arasında **sınır bulamıyor**
   ve hiçbir şey döndürmüyordu → her satır sessizce düşüyordu. Yeni `_lead_code`
   kodu satır BAŞINDAN alıyor; ismin baş büyük harfini (`…202N`) dil eki (`…202E`)
   sanmamak için tek harfi ancak ardından küçük harf gelmiyorsa koda katıyor.

2. **Adım hiç çalışmıyordu.** `step_equivalence` yalnız elle `--equivalence-
   program-id` verilince koşuyordu; normal `make refresh`'e bağlı değildi. Artık
   ayardaki `eq_program_ids` ile **her tazelemede otomatik** çekiliyor.

Kullanıcı sayfayı kaydedip verince (GEO planı + BLG planı) gerçek biçim
görüldü ve iki hata da düzeldi. Ölçüldü: iki sayfadan **122 denklik**, sıfır
isim sızması.

## Denklik yönü ve OR anlamı

Sütunlar: **"Course At The Plan"** = HEDEF (plandaki ders), **"Equivalent
Course"** = `<br>` ile ayrılmış ALTERNATİFLER. Her alternatif **bağımsız**:
birini alınca hedef sağlanır (**OR**). Yani

```
BLG 202  ≡  BBF 202  /  CEN 202  /  MAT 202     (herhangi biri yeter)
```

Bu yüzden her alternatif **ayrı** bir denklik satırı olarak saklanıyor — hepsi
tek denkliğin AND kaynağı DEĞİL (öyle saklasak "hepsini al" derdi). Arayüz
resmi denkliği hedefe göre gruplayıp "yerine şu açık derslerden **birini** al"
diyor. (Kullanıcı beyanı ise çok kaynaklıysa AND kalır — "hepsi gerekli".)

## Taban kod ↔ dil eki (kritik eşleşme)

OBS denklik sayfası kodları **taban** (E'siz) yazıyor: `MAT 210`, `BLG 202`.
Plan ise **E'li**: `MAT 210E`, `BLG 202E`. Eşleştirmezsek denklik sessizce
görünmezdi ("iki kaynak aynı soruya farklı cevap"). `_dil_esi` her kodu iki
varyantıyla (`MAT 202` + `MAT 202E`) arıyor; türetilen kodu **asla olumlamıyor**,
yalnız gereken'de/şubede gerçekten varsa kullanıyor. İki varyant da açıksa
şubeler birleştiriliyor.

## Hangi denklik gösteriliyor

| Kaynak | Koşul |
|---|---|
| **Resmî** (OBS) | Yalnız hedef gerçekten **gereken** bir plan dersiyse (yoksa katalog çapında gürültü). Hedefe göre gruplanır, kaynaklar OR alternatifi. |
| **Beyan** (`denklikler.toml`) | Her zaman (niyet bildirir); çok kaynaklıysa AND. |
| Onay metni içeren (`dilekçe/onay/yönetim kurulu`) | `requires_approval` — arayüz "bölüm/yönetim kurulu onayı gerekebilir" der. |

Her satırda disclaimer: *saydırma için danışmanına ve fakülte yönetim kuruluna
danış.* Araç kaydı yapmıyor, karar vermiyor — bilgilendirme.

## Nasıl çalıştırılır

`config/settings.toml`:

```toml
[student]
eq_program_ids = [1247, 871]   # Geomatik (anadal) + Bilgisayar (ÇAP) ProgramId
```

> ProgramId, plan id'lerinden AYRI bir sayı uzayında. Denklik sayfasının
> Program açılır menüsünden bulunuyor (İngilizce program adı → id). Ölçülen:
> Geomatics Eng. UG = 1247, Computer Eng. UG = 871.

Sonra **kendi makinende** `make refresh` (bulut sandbox `obs.itu.edu.tr`'ye
erişemiyor; scraper öğrencinin ağından çalışır). Boş bırakılırsa denklik adımı
atlanır — sessizce değil, adım "0 program" der.

## Sayılar

| | |
|---|---|
| Test | **946** (+13) |
| Yeni test | `tests/test_obs_denklik.py` + gerçek fixture `tests/fixtures/ders_denklik_blg.html` |
| Gerçek veri | 2 sayfadan 122 denklik, 0 isim sızması; arayüzde 7 resmî + 2 beyan (HTAE+BLG, dönem 5) |
| Değişen | `sources/obs_equivalence.py` (parser), `ui.py` (`_acik_denklikler` + arayüz), `config.py` (`eq_program_ids`), `pipeline.py` (otomatik adım) |
