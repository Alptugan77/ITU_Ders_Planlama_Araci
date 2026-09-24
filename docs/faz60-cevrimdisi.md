# Faz 60 — Kayıt günü çevrimdışı; azami süre teyit edildi

*24.09.2026 · kullanıcı: "14 semester limit is correct for most cases. can you
continue improving and then create a PR".*

Testler **1278 → 1283** (+5), 4 atlandı. Geri alma deneyi:
on kuralın **onu** geri konunca kendi sebebiyle kırmızı (§3).

---

## 1. Azami süre teyit edildi

`[azami_sure]` artık `dogrulandi = true` — kaynak "2547 s. Kanun m. 44/c —
kullanıcı teyidi 24.09.2026". Kullanıcı "çoğu durumda doğru" dedi; bu yüzden
istisnalar `aciklama`da duruyor ve kartın ipucunda görünüyor (hazırlık ve
kayıt dondurma sayılmayabilir, süre dolunca ek sınav hakkı; kesin durum için
ÖİDB). Kartta ⚠ kalktı; sayı kesin bir son gün gibi sunulmuyor.

## 2. ★★ Kayıt günü çevrimdışı (`web/sw.js`, fikirler Y.8)

Statik site her açılışta motoru, kataloğu ve Pyodide'i ağdan indiriyordu;
bağlantı yoksa **hiçbir şey** açılmıyordu — planladığın program, CRN listesi,
yedek plan dahil. Kayıt günü bağlantı en kötü anında (OBS yavaş, yurt ağı
dolu, telefon çekmiyor).

Site artık bir service worker taşıyor (`site_kur` `site/sw.js`e yazıyor):

| Kural | Neden |
|---|---|
| Yalnız kendi kökenimiz, yalnız GET/HEAD | Gizlilik: CDN'e ve başka hiçbir yere dokunmuyor; hiçbir isteği değiştirmiyor, yalnız kendi dosyalarımızın kopyasını tutuyor |
| Kabuk (sayfa, motor, katalog) **ağ önce**; yoksa ya da 8 sn'de cevap yoksa kopya | Bağlantı varken her zaman taze veri |
| Pyodide (~10 MB) **önbellek önce**, önbellek adında sürüm | Sürüm değişmedikçe yeniden inmiyor |
| Kopyadan gelen cevap `X-Itucap-Onbellek: 1` taşıyor | Sayfa bunu görünce şerit çıkarıyor (aşağıda) |
| Sürüm = sitedeki dosyaların (Pyodide hariç) içerik özeti | Katalog ya da motor değişince eski kopya siliniyor; Pyodide değişmedikçe kabuk boşuna silinmiyor |
| Kayıt, site **tamamen açıldıktan sonra** | İlk ziyarette büyük indirmeyle yarışmasın |

### ★ Eski kontenjan canlıymış gibi gösterilmiyor

Katalog kopyadan geldiyse ya da bağlantı yoksa sayfanın üstünde:

> **Cihazdaki kopyadan açıldı** — planın, CRN'lerin ve yedeklerin burada; ama
> şube/kontenjan verisi 3 gün önce tazelendi (…). Kontenjan kayıt ekranında
> değişmiş olabilir: **CRN'leri OBS'de doğrula**.

Bağlantı gidip gelirse (`online`/`offline` olayları) şerit kendini
güncelliyor. Yalnız statik sitede; `make app` her zaman canlı veriyle.

### Test iki gerçek hata yakaladı

1. **HTTP önbelleği işaretsiz kopya veriyordu.** GitHub Pages `max-age=600`
   gönderiyor. Ağ-önce yolu düz `fetch` kullansaydı o 10 dakikada çevrimdışı
   istek HTTP önbelleğinden dönerdi — katalog işaretsiz, sayfa canlı sanırdı.
   Ağ denemesi artık `cache: "no-cache"` (çevrimiçiyken 304, ucuz).
2. **Yeni sürüm ESKİ kataloğu saklıyordu.** Kurulumdaki ön-önbellekleme de
   HTTP önbelleğinden okuyordu; site güncellenince yeni sürümün adıyla eski
   katalog saklanırdı. O da `no-cache`.

Test sunucusu GitHub Pages'in başlığını gönderiyor; iki düzeltmeden biri
geri konunca test kırmızı.

⚠️ Ölçüm düzeneği hakkında: Playwright'ın `set_offline`ı service worker'ın
isteklerini **kesmiyor** (ölçüldü: "çevrimdışı" yenilemede sunucu iki istek
aldı). Test gerçek kopukluğu sunucu tarafında kuruyor — bağlantıyı cevapsız
kapatarak. İlk taslakta bir yorumda HTTP önbelleği sorununu "ölçüldü" diye
yazmıştım; o belirti aslında bu düzenek hatasıydı. Sorun gerçek (max-age),
yorum düzeltildi ve test artık onu gerçekten ölçüyor.

Gerçek site bu ortamda kurulamıyor (katalog ve Pyodide yok). Katman, **aynı**
`site_kur.cevrimdisi_katman` ile yazılmış küçük bir sitede gerçek Chromium'da
ölçülüyor: çevrimiçi aç → kopukken yenile → sayfa açılıyor, katalog kopyadan
ve işaretli, Pyodide'in HEAD isteği CDN'e düşmüyor, başka kökene istek
karşılanmıyor → katalog değişince eski kopya siliniyor.

## 3. Testler ve geri alma deneyi

`tests/test_faz60_cevrimdisi.py` (5 test) + Faz 59 testinin azami süre
doğrulamaları (artık teyitli ve istisnaları yazılı).

| Geri konan | Kırmızı |
|---|---|
| Ağ denemesi HTTP önbelleğine düşüyor | uçtan uca |
| Ön-önbellekleme HTTP önbelleğinden | uçtan uca (eski katalog kaldı) |
| Kopya işaretsiz | uçtan uca |
| Pyodide HEAD'i ağa gidiyor | uçtan uca |
| Eski sürüm önbelleği silinmiyor | uçtan uca |
| Köken kontrolü yok | statik + uçtan uca |
| Sürüm özeti Pyodide'i de sayıyor | `test_SURUM_…` |
| Şerit açılışta çizilmiyor | `test_KOPYA_ISARETLI_…` |
| (Faz 59) azami süre doğrulanmamış / istisnasız | birim + uçtan uca |

⚠️ Tam paket bir adlandırma hatamı da yakaladı: sayfa bayrağına aracın adını
koymuştum (`__DEPAR_…`). `test_ad.py` ad değişince sayfada eski adın
kalmadığını ölçüyor; bayrak, başlık ve önbellek adları paket önekine
(`__ITUCAP_ONBELLEK__`, `X-Itucap-Onbellek`, `itucap-…`) çevrildi.

## 4. Ne yapılmadı

* Çevrimdışıyken **yazma** (transkript, program kaydı) zaten tarayıcıda
  (IndexedDB) — ağa ihtiyacı yok; ayrıca bir şey gerekmedi.
* "Uygulama olarak yükle" (PWA manifest) — ayrı bir iş; bu faz yalnız
  açılabilmeyi hedefledi.
