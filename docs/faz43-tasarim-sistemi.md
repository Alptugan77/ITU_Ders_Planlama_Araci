# Faz 43 — Tasarım sistemi: ölçülen tabanlar, dokuz basamak

*17.09.2026 · kullanıcı: "can you update and improve the design accordingly"*

Kapsam soruldu, cevap: **düzeltmeler + incelik** (kontrast, yazı ölçeği,
aralık ölçeği, durumlar), **uygulamaya da işlensin**, tasarım sistemi
**Türkçe** olsun. Tasarım sistemi bu fazın değerleriyle ayrı bir belge olarak
kuruldu; bu belge uygulamaya ne olduğunu anlatıyor.

Yöntem Faz 39 ile aynı: gerçek katalogla (10792 ders, 3793 şube) site açıldı,
ekran ekran bakıldı, her bulgu bir sayıya bağlandı. Kimliğe dokunulmadı:
sıfır köşe, cetvel, Chivo büyük harf başlık, mühür rengi, üç rol rengi ve
Faz 40'ın ton merdiveni **aynı**.

Testler **1055 → 1072**.

---

## A. ★★ Palet: 90 çiftin 15'i tabanın altındaydı

`tools/kontrast_olcumu.py` (yeni) paleti `ui.py`'den okuyup her yazı rengini
**düştüğü her zeminde**, iki temada ölçüyor. Önce:

| jeton | tema | düştüğü zeminlerde | taban |
|---|---|---|---|
| `--ink-3` #6C7688 | gece | 3.32 – 4.03 | 4.5 |
| `--ink-3` #727C8C | gündüz | 3.47 – 4.22 | 4.5 |
| `--border-strong` #414C60 | gece | 1.80 – 2.13 | 3.0 |

`--ink-3` sayfanın **en çok kullanılan** jetonu (88 yer): ipucu, sayaç, CRN,
"TAMAMLANDI", `izle` rozeti. `--border-strong` gece şemasında `.ghost`
düğmesinin, alanların, seçim gruplarının kenarı — `.ghost`'un zemini şeffaf,
yani kenar düğmenin **tek** sınırı (WCAG 1.4.11).

Düzeltme renk seçmek değil, **yalnız açıklık**: aynı hue, aynı kroma
(OKLCH), taban tutana kadar adım adım.

| jeton | tema | önce | sonra | en kötü zemin |
|---|---|---|---|---|
| `--ink-3` | gece | #6C7688 | **#848EA1** | 4.61 (cap-soft) |
| `--ink-3` | gündüz | #727C8C | **#5F6878** | 4.62 (cap-soft) |
| `--border-strong` | gece | #414C60 | **#647085** | 3.11 (surface-2) |

Sonuç: **92 çiftin 0'ı** taban altında.

⚠️ `--ink-2` ile `--ink-3` arası daraldı (gece surface'te 6.95 / 5.23) — ama
hiyerarşi yalnız renkten gelmiyor: `--ink-3` hep daha küçük boyutta.
Aradaki farkı korumak için `--ink-2`'yi açmak ölçülebilir bir şey vermezdi.

⚠️ **Gündüz `--border-strong` (#141821) değişmedi.** 17.8:1 — Şematik'in
sert siyah cetveli, tasarımın kimliği.

---

## B. ★★ Tonlu blokta ölçülmeyen iki satır

Faz 40 merdiveni bloğun yazısını (`--accent-ink`) ölçmüştü: en kötü 4.67.
Ama blokta **üç** satır var ve ikisi başka renkteydi:

| satır | renk | tonlu zeminde (en kötü basamaklar) |
|---|---|---|
| ders kodu | accent-ink | 4.67 – 5.37 ✓ |
| ders adı (`.blkad`) | accent-ink **%85 opaklık** | **3.80 – 4.37** |
| saat · yer · CRN (`small`) | `--ink-2` | **3.09 – 3.91** |

Üçüncü satırda **CRN** var — kayıt günü elle yazılan sayı (Faz 25).

Düzeltme yeni bir renk değil: iki satır rengi **bloktan miras** alıyor,
opaklık kalktı. Böylece merdiven testi bloktaki bütün yazıyı ölçüyor.
Hiyerarşi ağırlık/boyut/aileyle duruyor (kod kalın mono, ad küçük sans,
saat mono).

Tarayıcıda ölçüldü (uçtan uca test, hesaplanan renk, iki tema): blok yazısı
en kötü **5.09** (gece) / **5.44** (gündüz) — test kurulumunun beş dersi için.

⚠️ Test kuralı değil **tarayıcıyı** okuyor: hesaplanan `color-mix` rengi
`oklab(…)` biçiminde dönüyor, sayıyı elle ayıklamak yanlış ölçüyordu
(ilk sürümde gündüz "2.05" çıktı). Renk tuvalde piksele çevrilip ölçülüyor.

---

## C. ★ Bağlantının kuralı yoktu

Sayfada `a{…}` kuralı **hiç yoktu**. "Darboğaz bölümünde ayrıntı" tarayıcı
mavisiyle (#0000EE) çiziliyordu: gündüz 8.4:1 (okunur ama markasız), gece
şemasında surface-2 üstünde **1.66:1** — görünmüyordu.

Artık `--seal` + alt çizgi (gece 7.05, gündüz 7.58 — tarayıcıda). Renk tek
işaret değil: çizgi de var.

---

## D. Durumlar tek dilde

| | önce | sonra |
|---|---|---|
| üzerine gelme | sekmede var; kip, seçim grubu, dönem düğmesi, not dağılımı sekmesinde **yok** | beşinde de `--seal-soft` |
| birincil düğme hover | `opacity:.9` — yazıyı soldurur | `--seal-hover` (yeni jeton): yazı 9.0 / 9.5 |
| devre dışı | .35 / .45 / .5 | **.45** |
| tamamlandı (kademe) | .5 — gündüz **3.38:1** | **.6** — 4.66 |
| efsanedeki "almışsın" örneği | .6 (gösterdiği şeye benzemiyordu) | .6 — aynı |
| kilitli adım | adımın **tamamı** .5: başlık 3.38, açıklama **1.77** | yalnız numara + düğme sönük |
| bağ çizgisi (dinlenmede) | .55 — gündüz **2.64:1** | .7 — 3.66 (efsane zaten .7'ydi) |
| kademe kutusu hover | dış gölge | iç çerçeve (boş hücrenin hover'ı gibi) |

Ayrıca `.trtable .rm` ve `izle` rozetinin hover'ı yoktu; arama sonucundaki
"listede" satırı `disabled` geliyordu ama kuralı yoktu — `button{color:inherit}`
tarayıcının soluk rengini ezdiği için seçilebilir satırdan farkı görünmüyordu.

---

## E. Ölçekler

### E1. Yazı boyutu: 18 → 9

Yarım piksel adımlarla 18 farklı boyut vardı (8.5 – 29px). Kural: en yakın
basamak, eşitlikte büyüğe.

| basamak | nerede | eski değerler |
|---|---|---|
| 29 | başlık (h1) | 29 |
| 27 | panel yüzdesi (mono) | 27 |
| 23 | başlık, telefonda | 23 |
| 22 | karşılama başlığı | 22 |
| 15 | gövde, bölüm başlığı | 16, 15, 14 |
| 13.5 | alan, tablo, liste satırı | 13.5, 13 |
| 12.5 | düğme, not, meta | 12.5, 12 |
| 11.5 | sekme, ikincil meta | 11.5, 11 |
| 10.5 | eyebrow, etiket, rozet — **alt sınır** | 10.5, 10, **9**, **8.5** |

⚠️ 8.5px'ler "artıları ayır" grafiğiydi (15 sütun). 10.5'e çıkınca dar
ekranda sığmıyordu: sütun 22px'in altına inmiyor, grafik **yana kayıyor**.
Küçültmek yerine kaydırmak — okunmayan etiket, olmayan etiketten iyi değil.

Satır içi stiller (225) ve sitenin yükleme ekranı da aynı ölçeğe çekildi.
`.acilim` Chivo **500** istiyordu — o ağırlık hiç yüklenmiyor (600–900);
tarayıcı zaten 600 çiziyordu, artık CSS de öyle diyor.

### E2. Harf aralığı: 13 → 6

`-.02em · 0 · .02em · .06em · .11em · .16em`.

### E3. Aralık: 2px ızgarası

50 farklı `padding`, 17 farklı `gap` vardı — çoğu tek piksellik sapma (3, 5,
7, 9, 11, 13, 15px). Kural: tek sayı bir üst çift basamağa; **ama**
`min-height` tanımlı denetimde yükseklik korunacak yöne (düğme 34px, alan 36px).

Ölçek: `2 · 4 · 6 · 8 · 10 · 12 · 14 · 16 · 18 · 22 · 30` — istisnalar:
1px (rozet içi optik ayar), 38px (kademe satırları arası, bağ eğrisine yer),
60/80px (sayfa sonu). Sonra: 40 `padding`, 13 `gap` — hepsi ölçekte.

⚠️ Sayfa uzadı (masaüstü 7810 → 8140px): kart dolgusu 20 → 22, küçük yazılar
yarım piksel büyüdü. Bilerek.

---

## F. Köşe, gölge, sabit renk

* **Köşe:** tek istisna not dağılımı sütunlarının 2px'lik üst köşesiydi —
  kalktı. 18 yerde `border-radius:0` sabit yazılıydı, `var(--r)` oldu.
  Dönen halka (`.spin`) daire kalıyor.
* **Gölge:** yalnız **yüzen katmanda** (pencere, bildirim, yapışkan çubuk),
  hepsi jeton: `--shadow`, `--shadow-toast`, `--shadow-sticky`. Yapışkan
  çubuk ve bildirimin gölgesi kuralın içinde **sabit siyahtı** — gündüz
  şemasında da gece şemasının `rgba(0,0,0,.55)`'iyle basılıyordu.
* **Sabit renk:** paletin dışında 4 sabit renk vardı (iki gölge, kademe
  hover gölgesi, pencere perdesi) → 0. Perde `--scrim` oldu. Baskı ve
  `mask-image` (renk değil, alfa) istisna.
* **Etiket:** denklik satırındaki "beyanın" etiketi `class="tag unknown"`
  taşıyordu ama `.tag.unknown` kuralı yoktu — zeminsiz, rengi mirastan gelen
  çıplak bir büyük harf yazı. Nötr etiketle (`PLAN_DISI`) aynı oldu; test
  şablonda sabit yazılı her `tag X` sınıfının kuralını arıyor.
* **Açık palet** iki kez yazılı (sistem teması + düğmeyle seçilen) ve
  medya sorgulu blokta `--yandal*` satırı **iki kez** duruyordu — zararsız,
  ama Faz 38b'deki eksik jetonu gizleyen sürüklenmenin ta kendisi. İkisinin
  birebir aynı olduğunu tutan test yoktu; şimdi var.

---

## G. ★★ Yerleşim: düz yazı esnek satırın içindeydi

`.summary` bir **sayı satırı**: `display:flex; gap:14px`. Beş bölümün
açıklama paragrafı da onu kullanıyordu ("Bunu zaten almış olabilirsin",
"Denkliği bu dönem açık", "Aday dersler", başvuru penceresi, "Kademeler").
Esnek kutuda her metin parçası ve her `<b>` **ayrı öğe** olur:

> Transkriptindeki dersler ile planlarının ␣␣␣**dolmamış**␣␣␣ slotları…

Telefonda "dolmamış" kendi satırına düşüyordu. Faz 39'daki `.savedcard.cap`
ile **aynı hata sınıfı**: bir yerleşim sınıfı başka bir iş için kullanılmış.
Düz yazı artık `.aciklama`; `.summary` yalnız JS'in doldurduğu, kimliği olan
sayı satırı. Test bunu kural olarak tutuyor.

**İkinci örnek, aynı sınıf:** transkript girilmemiş paneldeki *"İlerleme
bilinmiyor — geçtiğin dersleri girmedin. Aşağıdaki sayılar **planın tamamı**,
senin kalanın değil."* notu `.proj.bilinmiyor` idi — `.proj` da bir esnek sayı
satırı. Not "İlerleme bilinmiyor" tek başına bir satır, geri kalanı kopuk
parçalar olarak çiziliyordu; yalnız transkripti olmayan (yani **yeni**)
kullanıcı görüyordu. `display:block`.

Hata sınıfı artık tarayıcıda da aranıyor: uçtan uca test görünen her
esnek/ızgara kutuya bakıyor, doğrudan metinle `<b>`/`<a>` karışık tutan varsa
düşüyor (tek istisna `.proj` sayı satırının kendisi).

### G1. Telefonda öneri sekmeleri

Uzun etiketler ("ÖNERİ 1 · 21 KREDİ · EN AZ BEKLEME") farklı genişlikte
satırlara sarılıyor, sol çizgiler yarım kalıyordu. Telefonda alt alta, tam
genişlik, aralarında cetvel.

---

## H. Ne yapılmadı

* **Rol renkleri, mühür, ton merdiveni değişmedi.** Ölçüm geçiyordu.
* **Satır içi 225 stil sınıfa taşınmadı.** Değerleri ölçeğe çekildi ve test
  tutuyor; taşımak bu fazın işi değil, riski büyük, ekranda karşılığı yok.
* **⚠️ Yazı tipleri hâlâ Google Fonts'tan geliyor.** README'nin gizlilik
  bölümü "açılışta üçüncü bir tarafa haber verilmiyor" diyor (Pyodide bile
  siteden geliyor) — ama sayfa açılırken `fonts.googleapis.com`'a istek
  gidiyor. Tasarım değil gizlilik işi: fontları siteyle birlikte yayınlamak
  `site_kur.py`'ye ve `test_html_is_self_contained_except_fonts`'a dokunuyor.
  Açık kalem olarak `yapilacaklar.md`'ye yazıldı.
* **Baskı stili** değişmedi (pt, #000/#999 — kâğıt).

---

## I. Testler

`tests/test_faz43_tasarim_sistemi.py` (17 test):

| test | neyi tutuyor |
|---|---|
| `test_KUCUK_YAZI_ve_DENETIM_KENARI_her_temada_TABANIN_USTUNDE` | ★★ 92 çift, paletten ölçerek |
| `test_TONLU_BLOKTA_yazinin_TEK_rengi_var` | ★★ merdivenin ölçtüğü renk bloktaki tek renk |
| `test_BAGLANTININ_kurali_var` | `a` = mühür + alt çizgi |
| `test_ETIKETIN_her_hali_BOYALI` | şablondaki her `tag X` sınıfının kuralı var |
| `test_YAZI_BOYUTU_dokuz_basamak_ve_ALT_SINIR_10_5` | CSS + satır içi + yükleme ekranı |
| `test_HARF_ARALIGI_alti_basamak` | |
| `test_ARALIK_2px_IZGARASINDA` | CSS + satır içi |
| `test_KOSE_YOK` | tek istisna `.spin` |
| `test_GOLGE_yalniz_YUZEN_katmanda` | jeton, iç çerçeve ya da hiç |
| `test_SABIT_RENK_paletin_DISINDA_YOK` | baskı ve maske hariç |
| `test_ACIK_PALET_iki_blokta_BIREBIR` | ★ Faz 38b'nin hata sınıfı |
| `test_DURUMLAR_tek_dilde` | hover beş grupta, devre dışı tek değer |
| `test_TAMAMLANDI_efsaneyle_AYNI_ve_OKUNUR` | kademe = efsane = adım |
| `test_KILITLI_adimin_METNI_okunur` | |
| `test_BOLUM_ACIKLAMASI_esnek_satirda_DEGIL` | ★★ `.summary` ve `.proj.bilinmiyor` — hata sınıfı |
| `test_TELEFONDA_oneri_sekmeleri_ALT_ALTA` | |
| `test_UCTAN_UCA_blok_yazisi_ve_baglanti_TARAYICIDA` | ★★ hesaplanan renk, iki tema; esnek kutuda düz yazı yok |

**On yedi düzeltmenin on yedisi geri konulup kırmızıya döndükleri görüldü**
(opaklık, `small` rengi, iki palet değeri, bağlantı kuralı, `.summary`,
telefon sekmeleri, 2px köşe, çift yandal satırı, 8.5px, 7px dolgu, hover
gölgesi, birincil düğme opaklığı, DONE .5, kilitli adım .5, `.tag.unknown`,
`.proj.bilinmiyor`). Dördünde uçtan uca test de düştü.

`python tools/kontrast_olcumu.py` ölçümü tekrar üretiyor.
