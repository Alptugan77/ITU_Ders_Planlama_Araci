# Faz 54 — Siteyi ziyaretçi gibi gezmek

*23.09.2026 · kullanıcı: **"siteyi gözden geçirip ux ve ui konusunda geliştirip
eklenicek şeyleri ekler misin onlar dışında da yapılacak geliştirmeler varsa
yap"***

Testler **1201 → 1214**.

Yayınlanan statik site (tarayıcıda Python) baştan sona **yeni bir ziyaretçi
olarak** gezildi. Adımlar: bölüm seçimi, dönem, "Plandan işaretle", sekiz
görünümün hepsi. Masaüstünde, telefonda ve gece şemasında, her adımda ölçüm
alındı. Bulunanlar ağırlık sırasıyla:

| | ne oluyordu | şimdi |
|---|---|---|
| ★★★ ÇAP/yandal planı | **5437 çiftin 1802'sinde (%33)** site başka bölümün planını seçiyordu | **17 653 çiftin 0'ında** yerelden farklı |
| ★★ sitenin ilk açılışı (Faz 53 hatası) | kaydedilen program yüklenmiyor, paylaşılan bağlantı uygulanmıyor, açılış DEPAR'da | düzeldi |
| ★★ kontenjan tarihi | 23 gün önceki kontenjan **"bugün itibarıyla"** yazıyordu (4 yer) | son tazeleme tarihi |
| ★★ verinin yedeği | yoktu: tarayıcı temizlenince transkript **geri gelmez** biçimde gidiyordu | indir / yükle / kalıcı depolama |
| ★ dönem seçimi | "N. dönem + alttan" kipi açılmıyordu (ilk kart bunu vaat ediyor) | açılıyor |
| sitede "tazele" | hiç çalışmayacak bir düğme | yerine neden eski olduğu yazıyor |
| alt bilgi | sitede "bu dosya notlarını içerir" (dosya yok) | "notların yalnız bu tarayıcıda" |
| ilk kart, kapalı adımlar | açıklamalar **2,0–3,5:1** (taban 4,5) | okunur, kesik kenarla |
| telefonda arama kutusu | 38px | 44px |

---

## A. ★★★ Site ÇAP/yandal planını başka bölümden seçiyordu

Sitede HTAE (Harita) seçip ikinci program olarak BLG ÇAP deyince İlerlemem
görünümü **`ROS_BLG ÇAP Programı 2025-2026`** gösterdi. O plan Robotik
öğrencileri için. Harita öğrencisinin planı `TUMMUH_BLG`.

Motor bunu biliyordu. İlk kullanıcı incelemesinin A3 düzeltmesi "otomatik"
planı öğrencinin **anadalına uygun** planlar arasından seçiyor ve bunu
`plan_host_program` tablosundan okuyor. Site kurulumu ise o tabloyu "tarayıcıda
kullanılmıyor" diye **siliyordu**. Tablo boş olunca süzgeç hiçbir plan
bulamıyor, kural gereği süzmeden devam ediyor ve en yeni planı alıyordu. Kimin
için olduğuna bakmıyordu.

Ölçüm, gerçek katalog: anadalına uygun planı olan **5437** (anadal × ikinci
program) çifti vardı. Sitede bunların **1802'si (%33)** başka bölümün planına
düşüyordu. A3 düzeltmesi yerelde çalışıyordu, yayınlanan sitede hiç
çalışmamıştı.

* Tablo tutuldu, yalnız kalan planların satırlarıyla. Fark 272'ye indi.
* Kalan 272'nin sebebi başkaydı. Aynı çiftin **yeni** iterasyonu bazen bir
  anadalı listeden düşürüyor. Örnek: `TUMMUH_MAD` 2023'te ELE yok, 2018'de
  var. Budama yalnız en yeni iterasyonu tuttuğu için ELE öğrencisi sitede
  başka bölümün planına düşüyordu. Kurulum artık yerel aracın seçeceği her
  planı da tutuyor. Bunu `plans.ikinci_plan`ın kendisiyle hesaplıyor: 17 bin
  çağrı, ~1 sn.
* Sonuç: **17 653 çiftin 0'ında** site ile yerel araç ayrışıyor. Katalog
  3,0 → 3,1 MB (sıkıştırılmış), plan 731 → 761.

**Pencere de artık söylüyor.** Program seçim penceresinde BLG'nin 27 ÇAP
planı tek bir yığındı ve hangisinin senin olduğu yazmıyordu. Şimdi iki grup
var: "HTAE öğrencileri için (1)" ve "başka bölümlerin planları (26)".
"Otomatik" seçeneği de ne seçeceğini söylüyor ("HTAE için en güncel").
Bölümün planlarından hiçbiri anadalın için ilan edilmemişse bu açıkça
yazıyor. Anadalı değiştirince liste de değişiyor.

## B. ★★ Faz 53'ün sitede kırdığı şey

Sitede sayfa önce boş bir kabuk olarak çiziliyor. Python hazır olunca ilk
durum `applyState` ile veriliyor, yani `boot()` o ana kadar hiç koşmamış
oluyor. Faz 53 `applyState`e "kipi koru, kaydedileni yeniden yükleme,
bağlantıyı yeniden uygulama" dedi. Böylece sitenin **ilk açılışı** da bir
"durum değişikliği" sayıldı:

* boş kabuğun tek kipi ("all") korundu, açılış **DEPAR**'da oldu;
* **kaydedilen program yüklenmedi;**
* **paylaşılan bağlantı (#crn=…) uygulanmadı.**

Yerel uygulamada `boot()` sayfa yüklenirken koştuğu için hata orada
görünmüyordu. Faz 53'ün testleri de yerel sunucuyla yazılmıştı. Artık ilk
kez koşan `boot`, ilk açılış sayılıyor. Hata Faz 53 teslimiyle Mac'e gitmişti
ama henüz yayınlanmamıştı.

## C. ★★ Kontenjan tarihi yanlış damgaydı

Sayfanın başı *"şube/kontenjan verisi 23 gün önce tazelendi (31.08.2026)"*
diyordu. Alt bilgisi ise *"Veriler 23.09.2026 20:56 itibarıyladır"* diyordu.
İki cümle aynı sayfadaydı.

Faz 25/D3 tepeyi düzeltmişti ama dört yer (alt bilgi, doluluk çubuğu, kayıt
kontrolü, arz notu) hâlâ `generatedAt`ı yazıyordu. O damga sayfanın
**üretildiği** anı gösterir ve sitede her açılışta "şimdi"dir. Kayıt
kontrolü böylece 23 gün önceki "yer var"ı bugünün tarihiyle yazıyordu. Doluluk
çubuğunun yorumu bile *"sayı yaşsız bir gerçek gibi durmasın"* diyordu. İki
test de **yanlış damgayı kilitlemişti** ve gerekçesiyle yeniden yazıldı.

## D. ★★ Sitede verinin yedeği

Sitede bölüm, transkript, kilitler ve kaydedilen program **yalnız tarayıcının
deposunda** duruyor. Tarayıcı verisini silmek, başka cihaza geçmek ya da
Safari'nin 7 gün girilmeyen sitenin deposunu temizlemesi hepsini götürüyor.
Geri almanın yolu yoktu. Şimdi:

* **Ayar görünümü → "Verin yalnız bu tarayıcıda"**: *Yedeğini indir* (JSON
  dosyası) ve *Yedekten yükle…*.
* **Yeni cihazda ilk kart**: "Başka bir tarayıcıda çalıştıysan: yedeğinden
  devam et…". Kurulum bitmeden Ayar görünümü gizli olduğu için bu yol şart.
* **Yüklemeden önce ne olacağı söyleniyor**: "Bu yedek şimdiki verinin
  yerine geçecek. Yedek: 2026-09-23 · HTAE · 31 ders. Şimdi: … ders." Önce
  şimdikini indirmek tek tık.
* **Kalıcı depolama**: tarayıcının veriyi yer açmak için silip silemeyeceği
  yazıyor. Silebilecekse "Kalıcı saklamasını iste" düğmesi var. Tarayıcıya
  soru yalnız bu düğmeyle gidiyor, çünkü Firefox izin penceresi açıyor ve
  habersiz açılması şaşırtırdı.
* **Güvenlik**: yüklemede yalnız bilinen üç dosya yazılıyor (yol listeden).
  Veritabanının başlığı ve ayar dosyası Python'da doğrulanıyor. Yedekte
  olmayan dosya depodan **siliniyor**, yoksa iki verinin karışımı kalırdı.
  Hiçbir şey sunucuya gitmiyor.

Yerel uygulamada (`make app`) veri zaten `data/` altında ve yedekleniyor.
Kutu orada yok.

## E. Küçükler

* **Dönem seçilince dönemlik kip açılıyor.** Faz 53 kipi her durumda
  koruyordu. Kurulum işleri (bölüm, dönem, transkript) artık varsayılan kipe
  dönüyor. Tercih ve meşgul saat ise yalnız öneriyi değiştiriyor, orada kip
  korunuyor.
* **Sitede "tazele" düğmesi yok.** Basınca "bu ortamda yapılamıyor" diyen bir
  düğmeydi. Yerine "Site dönem başında güncelleniyor — güncel kontenjan
  OBS'de" yazıyor.
* **Alt bilgi ve ilk kart ortamı doğru söylüyor.** Sitede "notların yalnız bu
  tarayıcıda — yedeğini al", yerelde "bu bilgisayarda (`data/`)".
* **İlk kartta kapalı adımlar okunuyor.** `opacity:.5` açıklamaları 2,0–3,5:1'e
  düşürüyordu. Oysa yeni gelen kişi sırada ne olduğunu oradan okuyor. Durum
  artık kesik kenar, soluk başlık ve kilit simgesiyle veriliyor.
* **Telefonda arama kutusu 38 → 44px.**

## Ölçülüp değiştirilmeyenler

* **Izgaradaki yazı boyu.** Haftalık programda görünen karakterlerin %69'u
  12px altında (ders adı 10,5px, saat 11px). Ama 154px'lik blokta saat/yer
  satırı 11px'te ancak sığıyor, büyütünce ikinci satıra düşüyor. Faz 39/46/50
  bunu ölçüp ayarlamıştı, o yüzden dokunulmadı.
* **İşlem süreleri (tarayıcıda Python).** Bölüm kaydı 1,8 sn, dönem 1,9 sn,
  transkript 1,5 sn. Hepsinde "kaydediliyor…" göstergesi var.
* **Konsol:** bütün gezintide 0 hata, 0 uyarı.

## Geri alma deneyi

15 düzeltmenin her biri geri alındı ve bekçisinin **kendi sebebiyle** kırmızıya
döndüğü görüldü. Sekizi **gerçek sitede** görüldü: sentetik bir katalogla,
gerçek Pyodide kurulup açıldı. Faz 53'ün sitede kırdığı şeyi yakalayacak test
yoktu, çünkü o fazın testleri yerel sunucuyla yazılmıştı. Bu fazdan itibaren
site uçtan uca deneniyor.

## Testler

`tests/test_faz54_site.py` (13 test):

* **Kurulum:** host tablosu tutuluyor, seçim yerelle aynı (gereken eski
  iterasyon dahil); kaynak bekçisi var.
* **Pencere:** planlar kimin için olduğuna göre gruplanıyor. JS'teki taban
  kod kuralı Python'la aynı (node ile karşılaştırılıyor).
* **Açılış ve kip:** sitenin ilk durumu ilk açılış sayılıyor; kurulum işleri
  varsayılan kipe dönüyor.
* **Görünüm:** kontenjan tarihi son tazelemeden geliyor; sitede ölü düğme ve
  yanlış cümle yok; adımlar opaklıkla soldurulmuyor; telefonda arama kutusu
  44px.
* **Yedek:** yalnız bilinen dosyalar yazılıyor; önce ne olacağı söyleniyor,
  sonra yazılıyor.
* **Gerçek site, baştan sona** (Pyodide):
  1. tarih doğru, tazele düğmesi yok;
  2. plan grupları doğru, HTAE + BLG → TUMMUH_BLG;
  3. dönem seçilince dönemlik kip açılıyor;
  4. kaydedilen program yeniden açılışta geliyor;
  5. paylaşılan bağlantı uygulanıyor;
  6. yedek iniyor, yeni cihazda ilk karttan yükleniyor;
  7. bozuk yedek reddediliyor.

`node_modules/pyodide` yoksa (CI) gerçek site testi atlanıyor.

Gerekçesiyle yeniden yazılanlar:

* `test_faz25_a` / `test_faz25_bc`: yanlış damgayı (`generatedAt`) kilitliyorlardı.
* `test_faz28`: anadal dinleyicisi artık plan listesini de yeniliyor.
* `test_ilk_giris`: gizlilik cümlesi artık ortama göre değişiyor.
