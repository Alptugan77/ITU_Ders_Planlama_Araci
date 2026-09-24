# Faz 56 — Tasarım sistemi v2: çıkarım, tek kaynak, kullanılabilirlik

*23.09.2026 · kullanıcı: "Extract the design system from this codebase and
make a new design system. improve every aspect of this site and make it
more usable and useful."*

Üç iş, bu sırayla: (1) kodun **gerçekten** kullandığı tasarım sistemini
çıkar, (2) onu tek kaynaklı bir v2'ye çevir, (3) gerçekçi veriyle ekranı
gez ve bulduğunu düzelt. Hiçbiri tahminle yapılmadı; her karar aşağıda bir
sayıya bağlı.

Testler **1215 → 1234** (+19), 4 atlandı. Geri alma deneyi: on bir
düzeltmenin **on biri** geri konunca kendi sebebiyle kırmızı.

---

## 0. Önce ölçmek için bir öğrenci: `tools/vitrin.py`

Her tasarım turu (Faz 39, 46, 48, 50, 51) ekranı ölçerek başlamıştı, ama
her biri kendi üç dersli veri setini elle kurmuştu. O verilerle ızgara hiç
dolmuyor, not dağılımı hiç çizilmiyor, "Ne değişti" hiç görünmüyor, hiçbir
şube dolu değil. Yani tasarım, kullanıcının gördüğü ekranın küçük bir
kopyasında ölçülüyordu.

`tools/vitrin.py` tek bir **kurgusal** öğrenci kuruyor: HTAE anadalı 5.
dönemde, BLG'de ÇAP'a 5. yarıyılda başlamış, dört dönemlik transkripti var
(biri FF), cuma öğleden sonra stajda. 50 ders, 22 şube (biri dolu, biri
çevrimiçi, biri saatsiz), beş not dağılımı, iki anlık görüntü. Ders
**kodları** İTÜ'nün gerçek kodları (ekran tanıdık görünsün diye); şubeler,
hocalar, kontenjanlar ve notlar uydurma. Veri geçici klasörde kuruluyor,
repodaki `data/`ya dokunulmuyor.

```bash
python tools/vitrin.py                 # sunucuyu açar, adresi yazar
python tools/vitrin.py --ekran DIZIN   # 8 görünüm × 2 genişlik × 2 tema
```

Faz 56'nın uçtan uca testi de bu öğrenciyle koşuyor — araç kullanılmazsa
çürür, test onu diri tutuyor.

---

## 1. Çıkarım: v1 sistemi ne diyordu, kod ne yapıyordu

`tools/tasarim_envanteri.py` şablonun elle yazılan CSS'ini ve HTML/JS
içindeki satır içi stilleri tarıyor. v1 tasarım sistemi (Faz 43'te
kullanıcının hazırladığı "İTÜ DEPAR" Design System artifact'ı) ile
karşılaştırma:

| | v1 sistemi diyor | kodda ölçülen |
|---|---|---|
| yazı boyu | 9 basamak, **taban 10.5px** | **21** ayrı değer; 8.5 · 9 · 9.5 · 10px var |
| harf aralığı | 6 basamak | **14** ayrı değer |
| satır aralığı | — | **12** ayrı değer |
| yazı ailesi | 3 aile | **20** bildirim, mono'nun **3 ayrı** yedek yığını |
| aralık | 2px ızgarası, tek piksellik sapma yok | **55** dolgu, **24** boşluk, **16** üst boşluk değeri; 3 · 5 · 7 · 9 · 11 · 13 · 15px |
| renk | her renk jeton | **51** ayrı hex, **108** kullanım |
| palet | tek | **dört elle kopya** (gece, medya-gündüz, açık-gündüz, kâğıt) |
| katman | — | adsız `z-index` 1 · 2 · 40 · 60 |

En pahalısı palet. Dört kopya **iki kez ayrıştı**: Faz 38b'de `--yandal*`
açık blokta unutuldu (açık şema seçilince yandal gece renginde çıktı), Faz
43'te iki yeni jeton üç bloğa tek tek eklendi. Faz 43 ve 48 bunu bir testle
yakalıyordu ("her blok her jetonu taşıyor") — hata sınıfı yakalanıyordu ama
**kaynağı** duruyordu.

---

## 2. v2: tek kaynak

### A. ★★ `src/itucap/tasarim.py`

Palet ve ölçekler artık bir Python modülünde, **bir kez**. Şablonda
`__JETONLAR__` ve `__JETONLAR_KAGIT__` yer tutucuları var; `ui.render()`
dört bloğu buradan üretiyor. Üç okuyucu, tek kaynak:

| okuyucu | eskiden | şimdi |
|---|---|---|
| sayfa (`ui.render`) | şablondaki dört elle kopya | `tasarim.css_jetonlari()`, `css_kagit()` |
| `tools/kontrast_olcumu.py` | `ui.py`'nin `<style>`ı düzenli ifadeyle | `tasarim.palet()` |
| `tools/ton_merdiveni.py` | aynı | aynı |
| Design System artifact | elle | `tasarim.jetonlar_json()` (`tasarim_envanteri.py --jetonlar`) |

⚠️ Modül Pyodide paketine giriyor (`ui` onu içeri alıyor), o yüzden
`site_kur.ENGINE`de ve yalnız standart kütüphaneye dayanıyor; import
anında dosya okumuyor (Faz 38 ve 43'ün tuzağı). Test ikisini de tutuyor.

### B. Renk değerleri DEĞİŞMEDİ — anlamları ayrıldı

Her renk v1'den devralındı. Değer değiştirmek Faz 43'ün kontrast
ölçümünü (52 çift) ve Faz 40'ın ton merdivenini (ΔE + yazı kontrastı)
geçersiz kılardı. v2'nin renkte getirdiği şey **anlam**:

| jeton | ne | neden |
|---|---|---|
| `border-control` ★ yeni değer | düğme ve alan kenarı | v1'de cetvelle (`border-strong`) aynıydı: gündüzde **her düğme siyah çerçeveli** çıkıyordu ve beş düğmelik sütunda birincil eylem kalabalıkta kayboluyordu. Gündüz `#6B7384`, gece aynı. Düştüğü dört yüzeyde ölçüldü: en kötü **3.11** (taban 3.0) |
| `on-seal` | `seal` dolgusunda yazı | sabit `#fff` yazılmasın (gece periwinkle üstünde beyaz kalır) |
| `focus` | odak halkası | |
| `ok`, `ok-soft` | başarı (✓, kaydedildi) | v1'de doğrudan `anadal` yazılıyordu — rol rengi durum anlamına kayıyordu. Bugün aynı ton; ayrışırsa tek satır |
| `shadow-toast/-sticky/-lift` | yüzen katman gölgeleri | üç `rgba()` satır içindeydi |
| `kagit-*` | kâğıt çizgisi/mürekkebi | yazdırma bloğunda `#999`, `#666`, `#000` satır içindeydi |

Kontrast aracı artık **70 çifti** iki temada ölçüyor (52'den; yeni
`border-control` ×4, şube rozeti ×2, çevrimiçi blok ×3). Hepsi tabanın üstünde. Ton
merdiveni değişmedi: en kötü yazı 4.67, zemin ΔE 0.039.

### C. ★ `color-scheme` — gece temasında beyaz onay kutusu

Ölçüldü (ekran görüntüsü): gece temasında "yalnız yeri olanlar" onay
kutusu koyu kartın ortasında **bembeyaz** bir kareydi; açılır listeler ve
kaydırma çubuğu da tarayıcının açık çiziminde kalıyordu. Palet renkleri
değiştiriyordu ama tarayıcıya "bu sayfa koyu" demiyordu. Artık gece
bloğu `color-scheme:dark`, gündüz blokları ve kâğıt `light`.

### D. Ölçekler

| aile | jetonlar | eşleme (v1 → v2) |
|---|---|---|
| yazı boyu | `fs-2xs` 10 · `xs` 11 · `sm` 12 · `md` 13 · `lg` 14 · `base` 15 · `xl` 18 · `2xl` 22 · `3xl` 25 · `4xl` 29 | 8.5/9/9.5/10/10.5 → 11 (grafik ekseni 10) · 11.5 → 12 · 12.5 → 13 · 13.5 → 14 · 23 → 22 · 27 → 25 |
| harf aralığı | `ls-tight` · `0` · `wide` · `caps` · `label` · `eyebrow` | 14 → 6 |
| satır aralığı | `lh-none` · `tight` · `snug` · `normal` · `body` · `loose` | 12 → 6 |
| aile | `font-display` · `font-sans` · `font-mono` | 20 bildirim → 3 jeton |
| aralık | `sp-1`…`sp-14`: 2px ızgarası 16'ya kadar, sonra 20 · 24 · 32 · 40 · 56 · 80 | tek sayılar yukarı yuvarlandı (3→4 … 15→16); 18→20, 22/26→24, 30→32, 38→40, 60→56, 78→80 |
| katman | `z-lift` · `links` · `nav` · `toast` · `skip` | |
| hareket | `dur-fast` .12s · `dur-base` .18s · `dur-spin` .7s | |

**Taban 11px.** v1 "10.5 taban" diyordu ama kodda 9px'lik bir "TAMAMLANDI"
etiketi ve 10px'lik rozetler vardı. Tek istisna `fs-2xs` (10px): yalnız not
dağılımı grafiğinin ekseni ve çevrimiçi simgesi — akan metin değil; test
bunu seçici seçici tutuyor.

**Bölüm başlığı 15 → 18px.** h2 gövdeyle aynı boydaydı; tek ayrım ağırlık
ve büyük harfti.

### E. `--denetle`: bir kerelik temizlik yetmez

Her faz yeni bir `font-size:12.5px` ekleyebilir. `tasarim_envanteri.py
--denetle` elle yazılan CSS'te ve satır içi stillerde ölçek dışı her değeri
satır numarasıyla yazıyor ve çıkış 1 veriyor; test onu çalıştırıyor.
Muhafızın muhafızı da var: test bir kopyaya `12.5px`, `7px` ve `#ff0000`
ekleyip denetimin üçünü de yakaladığını doğruluyor.

⚠️ **Göç betiğinin kendi hatası denetimle çıktı.** Betik satır içi
stillerin SON bildirimini atlıyordu (bakış ileriye `;` bekliyordu, satır
içinde son bildirimden sonra `;` yok). Denetim dokuz tanesini yakaladı:
`padding:7px 12px` ×4, `margin-top:7px` ×2, `18px` ×2, `5px`. Elle düzeltildi.

---

## 3. Ekranda bulunanlar (vitrin öğrencisiyle)

### F. ★★ Telefonda meşgul saatler YOKTU

Masaüstü ızgarası cuma 13:30–17:30'u taralı bir "staj" bloğu olarak
çiziyordu; telefondaki gün listesi aynı gün için **"boş"** yazıyordu.
`renderDayList()` hiç `DATA.busy` okumuyordu. Aynı veri iki biçimde iki
farklı şey söylüyordu — bu repoda Faz 49'dan beri ölçülen hata sınıfı.

Artık liste meşgul saati ızgaradakiyle aynı taramayla, "ders konmaz"
notuyla ve dokununca kaldırma penceresiyle gösteriyor. Meşgul saatle
kesişen ders **çakışma** sayılıyor (elle eklenen ders oraya düşebilir;
ızgarada o hücreyi ders örtüyor, listede ikisi de görünüyor). İki meşgul
saatin kesişmesi çakışma değil.

### G. ★★ Önerilen programın bir şubesi DOLUYDU, ızgara söylemiyordu

Vitrin verisinde öneri 1'in `GEO 331E` şubesi 70/70. Doluluk yalnız aday
listesinde görünüyordu (`doluluk()`); kayıt gününe götürülen ızgarada hiçbir
işaret yoktu. Artık:

* blokta `DOLU` ya da `SON N` rozeti — eşik `doluluk()` ile **aynı** (0 →
  dolu, ≤3 → son N), aynı şube iki yerde iki durumda görünmesin;
* boş şubede işaret yok — ızgara ancak dikkat gerektiren şeyi söylemeli;
* rozet **kendi zemininde** (`surface`): blok rolün tonlu zemininde duruyor
  ve ton merdiveni yalnız `-ink` yazısını ölçüyor; danger/warn o zeminlerde
  ölçülmemişti. Zemin verince ölçülen bir çift oldu: danger 5.79–6.29,
  warn 6.57–8.50;
* işaret yalnız renk değil: sözcük + çerçeve (zorlanmış renk kipinde de).

### H. ★ Özet bir satır yığını değildi

Bağlam sütununun tepesi 240px'e sığdırılmış yedi parçalı bir esnek satırdı;
sarınca "sınır 22 kredi puan 792.5" diye yapışık okunuyordu ve asıl soru
("sınıra ne kadar yakınım") bir çıkarma istiyordu. Artık:

* **21 / 22 kredi** büyük rakamla ve ölçekle; aşınca kırmızı **ve**
  "aşıldı" yazıyor (ölçek zorlanmış renk kipinde de çiziliyor);
* dolu şube varsa adıyla ve ne yapılacağıyla;
* lejant **her ikinci programın kendi renginde** — ⚠️ nokta `var(--cap)`e
  sabitti, yandal öğrencisi amber bir "yandal" noktası görüyordu, blokları
  ise mavi;
* "puan" artık "öneri puanı" ve dokununca ne olduğunu söylüyor (Faz 51'in
  dokunulabilir açıklaması).

### I. ★ "yer yok" kayıt gününde "kontenjan dolu" okunuyordu

Izgarada `15:30–18:29 yer yok · 22305`. Anlamı "derslik ilan edilmemiş"ti;
kayıt aracında CRN'nin yanındaki "yer yok" ise en doğal hâliyle "kontenjan
dolu" demek. Kontenjanın kendi dili "dolu / N boş". Söz **"yer
bildirilmedi"** oldu — Faz 28'in kuralı gereği terminalde
(`recommend._building_label`) ve arayüzde **birlikte**; test ikisini tutuyor.

### J. "Ne değişti" ISO damgası basıyordu

`2026-09-22T17:00:45 → 2026-09-23T17:00:45`. Aracın her yerde kullandığı
biçim `22.09.2026 17:00`. Çözülemeyen damga olduğu gibi kalıyor — uydurma
bir tarih ham damgadan kötü.

### K. İçeriğe atla

Faz 51 `<main>` yer işaretini ekledi ama klavye kullanıcısı her görünüm
değişiminde üst çubuktaki ve raydaki ~13 durağı geçiyordu. İlk Tab'da
görünen bir bağlantı odağı `<main>`e taşıyor; adres çubuğuna `#icerik`
yazmıyor (paylaşılan bağlantı `#crn=` taşıyor, onu kirletmesin).

### L. ★★ v1 sisteminin YAZDIĞI dört kural kodda YOKTU

v2 artifact'ını kurmak için v1'in bileşen kartları tek tek okundu. Dördü,
kodun hiç almadığı bir kuralı anlatıyordu — sistem doğru, uygulama eksikti:

| v1 kuralı | kodda | ölçüm |
|---|---|---|
| *"Bloktaki bütün yazı `-ink`: ad için opaklık, saat için `ink-2` verme"* | `.blkad{opacity:.85}`, `.blk small{color:var(--ink-2)}` | ton merdiveninin en kötü basamağında ad **3.80:1**, saat · yer · **CRN** satırı **3.09:1** (taban 4.5). CRN kayıt günü elle yazılan sayı. Düzeldi: tam `-ink`, **4.67:1** |
| *"Birincil düğme: `seal-hover` (opaklık değil)"* | `.ghost.primary:hover{opacity:.9}` — jeton Faz 43'ten beri **tanımlı ve hiç kullanılmıyor** | düzeldi; artık "tanımlı renk jetonu ölü kalamaz" testi var |
| *"Açıklama paragrafı `.aciklama`; `.summary` yalnız sayı satırı"* | beş bölüm açıklaması esnek `.summary` içinde | Kademeler'de **"Çizgiler önşart bağıdır"** cümlenin ortasında kendi satırına kırılıyordu (her `<b>` ayrı esnek öğe). Esnek kutu sınıfının dördüncü görülüşü |
| rol ≠ durum | ✓, "tamam", "programda", tamamlanmış adım `--anadal` | 20 satır `--ok`/`--ok-soft`e; odak halkası `--focus`a |

Kontrast aracı artık **70 çifti** ölçüyor (çevrimiçi bloğun dolgusuz
hâli için rolün mürekkebi zeminde: ≥9.72:1).

---

## 4. Bedeli ve kendi hatalarım

| | ölçüm |
|---|---|
| başlık/kip/sekme satırı (1400px) | h2 büyüyünce **iki satıra sardı** (36 → 82px) ve ızgarayı 46px itti. Sekme yazısı `fs-xs`e, dolgusu 12px'e indi, h2'nin fazladan harf aralığı kalktı → yine **36px**, 27px pay. Test tutuyor |
| ızgaranın tepesi (yeni kullanıcı, karşılama kartı açık) | 896 → **909px** (+13): üst çubuk +3, karşılama kartı +5, gerisi aralık yuvarlaması |
| Faz 55 testi | tıklama hedefi 1000px'lik pencerede y≈**988**'deydi, kenara 12px. +13px onu ekranın dışına itti ve "dışarı tıklama ızgaraya geçmedi" dedi. Test DAVRANIŞI ölçüyor, yerleşimi değil: hedef önce görünür yere getiriliyor (gerekçesi testte) |
| yeni testin kendisi | bir düzenli ifade gömülü yazı tiplerinin base64'ü üstünde geri izleyip **245 saniye** sürdü; şablonun elle yazılan CSS'ine çevrildi → 0,05 sn |

Değiştirilen eski testler (her birinde gerekçe yazılı): Faz 43 ve 48
paleti kaynaktan değil **üretilen** sayfadan okuyor; Faz 47'nin "ad ≥24px"
iddiası jetonu çözerek (`tasarim.coz`) ölçüyor; Faz 48'in kâğıt testi dört
gölge jetonunu ve `--kagit-*`yi tanıyor; Faz 51'in zorlanmış renk listesine
`.yuk` girdi; Faz 28'in tek söz testi "yer bildirilmedi".

---

## 5. Testler

`tests/test_faz56_tasarim_v2.py` (19 test):

| test | neyi tutuyor |
|---|---|
| `test_PALET_SABLONDA_ELLE_YAZILMIYOR` | ★★ şablonda tek bir renk tanımı yok |
| `test_URETILEN_bloklar_dort_ve_her_biri_TAM` | dört blok, her biri paletin tamamı |
| `test_COLOR_SCHEME_iki_temada_da` | beyaz onay kutusu |
| `test_TAKMA_ADLAR_var_olan_jetona_bakiyor` | `on-seal`, `ok`… |
| `test_MODUL_saf_ve_import_aninda_dosya_okumuyor` | Pyodide sınırı |
| `test_OLCUM_ARACLARI_ayni_kaynagi_okuyor` | üç okuyucu, tek kaynak |
| `test_OLCEK_DENETIMI_temiz` | ★★ ölçek dışı değer yok |
| `test_DENETIM_gercekten_yakaliyor` | muhafızın muhafızı |
| `test_yazi_TABANI_11px` | 10px yalnız grafikte |
| `test_h2_govdeden_BUYUK` | hiyerarşi |
| `test_JETONLAR_JSON_tasarim_sistemi_bicimine_uyuyor` | artifact dışa aktarımı |
| `test_YER_YOK_kalkti_TEK_soz` | terminal + arayüz |
| `test_YER_DURUMU_esigi_doluluk_ile_AYNI` | iki yerde aynı eşik |
| `test_ICERIGE_ATLA_var` | |
| `test_ACIKLAMA_esnek_satirda_DEGIL` | düz yazı esnek satırda değil |
| `test_TANIMLI_renk_jetonu_KULLANILIYOR` | ★ ölü jeton yok (`seal-hover`) |
| `test_BLOK_ICI_yazi_yalniz_INK` | ★★ 3.09 / 3.80:1 geri gelmesin |
| `test_DURUM_rengi_ROL_rengi_degil` | `--ok` ≠ `--anadal` |
| `test_UCTAN_UCA_vitrin` | ★★ vitrin öğrencisiyle: `color-scheme` iki temada, başlık tek satır, `DOLU`/`SON 2` rozetleri, özetteki dolu şube, yandal lejantı, okunur tarih, Tab → atla → `<main>`, telefonda cuma "staj", yatay taşma yok |

**Geri alma deneyi** (her biri geri konup test koşuldu):

| geri alınan | sonuç |
|---|---|
| gün listesinde meşgul saat | 🔴 `telefonda cuma: Cumboş` |
| ızgara rozeti | 🔴 `dolu şube ızgarada işaretlenmedi` |
| `color-scheme` | 🔴 `SEMA: normal` |
| okunur tarih | 🔴 `2026-09-22T17:34:26 → …` |
| lejant rengi | 🔴 `yandal lejantı:` |
| atla odağı | 🔴 `odak <main>e geçmedi` |
| Kademeler açıklaması `.summary` | 🔴 `düz yazı esnek satırda` + `Kademeler açıklaması: -` |
| blok saat `ink-2` | 🔴 statik + tarayıcıda |
| blok adı `opacity:.85` | 🔴 statik + tarayıcıda |
| birincil üzerine gelme opaklık | 🔴 `tanımlı ama kullanılmayan` |
| ✓ işareti `--anadal` | 🔴 `rol rengi` |

---

## 6. Ne yapılmadı

* **Palet yeniden boyanmadı.** Şematik + Gece kimliği kullanıcının
  seçimiydi (22.08.2026) ve renkleri iki ayrı ölçümle (kontrast, ton
  merdiveni) bağlı. v2 kimliği korudu, kodunu düzeltti.
* **Kenar kalınlığı ve `min-height` jetona çevrilmedi.** Ölçekleri var
  (`line-*`, `hit-*`) ama değerler az (5 ve 4) ve her biri bir testte tek
  tek tutuluyor; `var()`e çevirmek o testleri dolaylı yapardı. Denetim
  onları sayıyor.
* **Yeni yazı tipi yok.** Her ağırlık ~60 KB ve site tek dosya; Chivo +
  IBM Plex yerinde.

➜ Tasarım sisteminin kendisi (jetonlar, tipografi, bileşenler) Design
System artifact'ı olarak yayında: "İTÜ DEPAR v2" — `tasarim_envanteri.py
--jetonlar` onun `tokens.json`unu üretiyor.
