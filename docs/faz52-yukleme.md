# Faz 52 — Yüklenme ekranı ve her sekmede aynı genişlik

*21.09.2026 · kullanıcı: **"açılış ekranını güncelleyip yazıları
büyütebilirsin"** → **"açılış ekranı dediğim yüklenme ekranı"** · ve
**"bir de bütün sekmelerde arayüzün genişliği aynı olsun"***

Testler **1155 → 1167**.

Yüklenme ekranı statik sitenin ilk ekranı: Python tarayıcıya iniyor (Pyodide,
17,3 MB), katalog açılıyor, program hesaplanıyor. İlk ziyarette bu yavaş bir
bağlantıda **~92 saniye** sürüyor ve kullanıcının o sürede gördüğü tek şey bu
ekran. Önce ölçüldü (~200 KB/s'lik bağlantı, CDP ile kısıtlanmış Chromium):

| | önce | sonra |
|---|---|---|
| yükleyici görünmeden önce inen | **571 KB** (486'sı gömülü yazı tipi) | **90 KB** |
| beyaz sayfa süresi (ilk boyama) | **2984 ms** | **632 ms** |
| çubuk, Python inerken | **68 sn boyunca %16,7'de donuk** | bayta bağlı, sürekli (32. sn %29, 72. sn %72) |
| çubuk %100 iken süren iş | **4,7 sn** | yok — %100 ancak arayüz beslenince |
| sayılan bayt | — (adım sayıyordu) | **17,3 / 17,3 MB** |
| durum satırı | 12px, **gri**, eş aralıklı | **19px, koyu** |
| ad · açılım · gizlilik notu | 30 · 11,5 · 13,5px | **56 · 14 · 16px** |
| çubuk kalınlığı | 3px | 8px |
| hata olunca | gri bir satır, **düğme yok** | hangi adımda durduğu + hata + "Yeniden dene" |
| ekran okuyucu | 90 sn boyunca **hiçbir şey** | `status` + `progressbar` |

Toplam süre **değişmedi** (~92 sn): o, ağın taşıyabildiği 17,3 MB. Değişen,
o sürenin **nasıl geçtiği** — beyaz sayfa, donuk çubuk ve yalan söyleyen
%100 yerine ne indiğini, ne kadar kaldığını ve ne yapıldığını söyleyen bir
ekran.

---

## A. Beyaz sayfa: yazı tipleri yükleyicinin önündeydi

Faz 43 yazı tiplerini CSS'e gömmüştü (dış istek 1 → 0, doğru karar). Ama
gömülü `@font-face`ler `<head>`deydi, yani tarayıcı yükleyiciyi çizmeden önce
**486 KB** yazı tipini indirmek zorundaydı. Yavaş bağlantıda 3 sn beyaz sayfa.

* Statik sitede yazı tipleri **sayfanın sonuna** taşındı (`fontlar_sonda`);
  yükleyiciden önce 90 KB kalıyor. `make app` ve `make ui` **değişmedi** —
  onlar yerelden açılıyor, orada sıra fark etmiyor.
* `app.js` sayfanın **en sonundaydı**: Pyodide indirmesi 835 KB'lık HTML
  bitmeden başlamıyordu. Artık yükleyicinin **hemen ardında** ve `async`;
  arayüzü beslemeden önce DOM'un bitmesini kendisi bekliyor (`domHazir`).

## B. ★★ Çubuk yalan söylüyordu

Eski çubuk beş adımı sayıyordu. Birinci adım (Python) indirmenin %80'i;
çubuk o sırada **68 saniye %16,7'de durdu**. Son adımın **başında** %100
oldu ve ekran 4,7 saniye daha "%100" gösterip çalıştı. İkisi de kullanıcıya
"dondu" dedirten şey.

Şimdi çubuk **bayt** sayıyor:

* **Payda** — her dosyanın boyu, site kurulurken ölçülüp `manifest.json`a
  yazılıyor (`yuk`). Pyodide CDN'den geliyorsa boyu bilinmiyor ve **uydurma
  sayı yazılmıyor**: çubuk bilinenlerle yetiniyor.
* **Pay** — gerçekten inen bayt. `fetch` sarmalanıyor, yanıt gövdesi sayan
  bir akıştan geçiyor; `<script>` ile gelenler (`pyodide.js`,
  `pyodide.asm.mjs`) `PerformanceObserver` ile, bitince sayılıyor.
* Çubuk %90 bayt + %10 adım; **%99'da tavan** — %100 ancak arayüz
  beslendiğinde.
* Altında `x / y MB · t sn`; indirme 12 sn hiç bayt almazsa "bağlantı yavaş,
  sayfayı açık bırak" diyor (yalnız indirme sürerken — hesaplama sırasında
  bayt gelmemesi takılma değil).
* Yükleme bitince sarmalayıcı **sökülüyor**: uygulamanın kendi istekleri
  sayılmasın.

> ⚠️⚠️ **İlk sürüm ölçümle çürüdü.** Pyodide `fetch`e dizge değil **`URL`
> nesnesi** veriyor; sayaç yalnız dizge ve `Request.url` okuyordu. Sonuç:
> 17,3 MB'ın **yalnız 5,2'si** sayıldı, `.wasm` (9,6 MB) hiç sayılmadı ve
> indirme akarken **yanlış "takıldı" uyarısı** çıktı. `String(girdi)` tam
> adresi veriyor. Testteki sahte Pyodide tam olarak bunu yapıyor.

> ⚠️ Yanıt başlıkları **aynen** korunuyor: `WebAssembly.instantiateStreaming`
> `application/wasm` türünü şart koşuyor; kaybolsaydı Pyodide `.wasm`ı ikinci
> kez indirirdi. Ölçüldü: bir kez iniyor.

## C. Yazılar büyüdü

| öğe | önce | sonra |
|---|---|---|
| İTÜ DEPAR | 30px | 40–56px (ekrana göre) |
| açılım | 11,5px | 14px |
| **durum satırı** (asıl okunan) | 12px, gri | **19px, koyu, 600** |
| adım listesi | — | 15px, durum işaretli (○ ● ✓ ✕) |
| MB · süre satırı | — | 14px |
| gizlilik notu | 13,5px | 16px |
| hata başlığı · metni · düğme | — | 21 · 15 · 16px (düğme 48px) |

> ⚠️ ✓ işareti IBM Plex Mono'da yok; tarayıcı yedek yazı tipinde **"√"**
> (karekök) çizdi. İşaretler artık sistem sembol yazı tipinden geliyor.

## D. Hata: donmuş ekran değil, çıkış yolu

Eskiden hata gri bir satırdı ve düğme yoktu — kullanıcı sayfanın donduğunu
sanıyordu. Şimdi: durum "Yüklenemedi", listede **hangi adımda** durduğu
✕ ile, hata metni (`textContent` ile — HTML olarak değil) ve **"Yeniden
dene"**. Odak düğmeye gidiyor.

> ⚠️ Hata kutusu önce gizlilik notunun **altındaydı**; telefonda ekranın
> dışında kalıyordu. Durum satırının hemen altına alındı.

## E. Erişilebilirlik

* Durum satırı `role="status"` + `aria-live="polite"`: adım değişince okunuyor.
* Çubuk `role="progressbar"`, `aria-valuenow` yüzde değişince güncelleniyor.
* MB satırı `aria-hidden`: her yarım saniye değişiyor, okunsa gürültü olur.
* Yükleyici `aria-busy`; hata olunca kalkıyor.
* Hareket azaltma tercihinde çubuğun parıltısı durdu; zorlanmış renk kipinde
  çubuk `Highlight` ile çiziliyor (Faz 51 dersi: yoksa görünmez).

---

## F. ★ Her sekmede aynı genişlik — Faz 47'nin bir kararı geri alındı

Faz 47 çerçeveyi yalnız **haftalık program** görünümünde genişletmişti
(1720px); metin bölümleri okuma ölçüsü için 1340px'te kalmıştı. Kullanıcı
aynı genişliği istedi ve ölçüm o kararın iki bedelini gösterdi:

* sekme değişince sol ray **zıplıyordu**: 1920px ekranda **196px**, 1440'ta
  56px,
* 1340px'lik çerçeve okuma ölçüsünü **zaten korumuyordu**: satırlar ~153
  karakterdi (1720'de 231).

Çerçeve artık **her sekmede aynı** (1720px; 1440 ekranda ekran kadar), zıplama
**0**. Okuma ölçüsü çerçeveden alınıp **metnin kendisine** verildi
(`max-width:80ch` — özet, açıklama, paragraf, ipucu). Izgaranın genişliği —
Faz 47'nin asıl konusu — korunuyor. Faz 47'nin iki testi gerekçesiyle
yeniden yazıldı.

## Ölçülüp değiştirilmeyenler

* **Toplam süre** — ağa bağlı. Kalıcı profilli bir tarayıcıda ölçüldü
  (~200 KB/s): ilk ziyaret **94,1 sn**, ikinci **3,0 sn**, üçüncü **2,5 sn**;
  ikinci ve üçüncüde ağdan **0 bayt** iniyor, her şey disk önbelleğinden.
  ⚠️ Playwright'ın gizli bağlamında (bellek içi önbellek) 9,6 MB'lık `.wasm`
  saklanmadı, ikinci açılış **51,6 sn** sürdü. Gerçek bir gizli pencerenin
  sınırı makinenin belleğine bağlı; o ölçülmedi.
* **Gece şeması** — yükleyici jetonlardan boyanıyor; ölçüldü, doğru.
* **İlk açılış kartı** (yeni kullanıcının gördüğü) — o da ölçüldü (aynı cümle
  ve düğme iki kez, geri dönen kullanıcıda yazıların yarısı 12px altı), ama
  kullanıcı "yüklenme ekranı"nı kastettiğini söyleyince dokunulmadı. Ayrı iş.

---

## ⚠️ Deney düzeneği üç kez yanıldı

Her düzeltme geri alınıp bekçinin **kırmızıya döndüğü** görüldü (28 durum).
Bu sırada düzeneğin kendisi üç yerde yanlış çıktı:

1. **Bayat `.pyc`.** Geri alma betiği dosyayı değiştirip aynı saniye içinde
   geri koyuyordu; değişiklik **aynı boydaydı** (19px→12px, 8px→3px). Python
   kaynağın saatini saniyeyle, boyunu baytla karşılaştırıyor — önceki
   durumun derlenmiş hâlini kullandı. "Çubuk eski kalınlıkta" durumu
   kırmızıydı, ama **bir öncekinin** değeriyle (durum satırı 12px). Betik
   artık her koşudan önce `__pycache__`i siliyor ve `-B` ile koşuyor; 28
   durumun hepsi yeniden koşuldu, hepsi **kendi sebebiyle** kırmızı.
2. **Uçtan uca genişlik bekçisi 1440px'te ölçüyordu.** Görünüme bağlı bir
   tavan (1440 ↔ 1720) o ekranda ekranın kendisine takılıp **aynı**
   çıkıyor — bekçi geri almada **yeşil kaldı**. Artık 1920px'te ölçüyor.
3. **"%100 ancak bitince" bekçisi hiçbir şey göremiyordu**: sahte
   Pyodide'da son adım anında bitiyordu. Gerçekte 4,7 sn; sahtesi artık
   1,5 sn bekliyor ve o sırada çubuk örnekleniyor. Geri almada 14 örneğin
   14'ü %100 → kırmızı.

## Testler

`tests/test_faz52_yukleme.py` (12 test): yükleyiciden önce <150 KB ve yazı
tipi yok · yazı tipleri kaybolmadı (sonda, hepsi) · yerel çıktılar değişmedi ·
`app.js` yükleyicinin ardında `async` + DOM bekleniyor · manifest'in beklenen
baytları (CDN'de uydurma yok) · sayaç `URL` nesnesini okuyor, başlıklar
korunuyor · %100 ancak bitince + sayaç sökülüyor · adım listesi iki tarafta
aynı · yazı boyları · ekran okuyucu rolleri · hareket ve zorlanmış renk ·
**tarayıcıda** (sahte Pyodide, 450 KB/s): çubuk Python inerken ilerliyor, geri
gitmiyor, bütün baytlar sayılıyor, son adımda %100 değil, yanlış uyarı yok,
yükleyici kalkıyor, `fetch` geri konuyor · **tarayıcıda hata**: adım ✕,
odak "Yeniden dene"de, `aria-busy` kalktı, düğme ≥44px.

`tests/test_faz47_kullanim.py`: iki test **yeniden yazıldı** (sebep
docstring'de): çerçeve her sekmede aynı ve geniş, okuma ölçüsü metinde;
uçtan uca ölçüm 1920px'te.
