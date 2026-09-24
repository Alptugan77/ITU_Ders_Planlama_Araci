# Faz 46 — Kabuk: program merkezde, gezinme görünüm değiştiriyor

*18.09.2026 · kullanıcı: "bütün düzeltmeleri ve yeni tasarımı uygular mısın"*

`docs/faz46-arayuz-olcumu.md`de ölçülen yedi maddenin hepsi uygulandı.
Testler **1085 → 1102** (1100 geçti, 2 atlandı).

---

## A. Önce ve sonra — aynı betik, aynı veri

1440×900 ve 390×844, gerçek veriyle (78 aday, 16 derslik program):

| ölçüt | önce | sonra |
|---|---|---|
| sayfa yüksekliği · masaüstü | 6570px (**7,3 ekran**) | **1253px (1,4)** |
| sayfa yüksekliği · telefon | 13834px (**16,4 ekran**) | **2624px (3,1)** |
| haftalık programın tepesi · masaüstü | 1825px | **444px** |
| gün listesinin tepesi · telefon | 3354px | **728px** |
| aynı anda açık bölüm | 11 | **1** |
| 24px altı dokunma hedefi | 72 | **0** |
| aynı anda görünen ikincil metin | 60 | **6** |
| sayfadaki toplam kelime | 1826 | **345** |
| bir ayar değişimi (yazma ucu) | 5,7 sn | **1,1 sn** |
| ilk yükleme (yerel sunucu) | 7,5 sn | **3,1 sn** |

Bozmadığımız şeyler ölçülerek doğrulandı: kontrast 52 çiftin 52'si iki
temada da tabanın üstünde · odak halkası duruyor · yatay taşma 0.

---

## B. Ne değişti

### B1. Üç sütunlu kabuk

```
┌──────────────────────────────────────────────────────────┐
│  İTÜ DEPAR · HTAE + BLG ÇAP · 5. dönem   ⚠ veri 18 gün  │  54px
├──────────┬───────────────────────────────┬───────────────┤
│  PLANLA  │  HAFTALIK PROGRAM             │  BU PROGRAM   │
│  ▸Program│  [5. dönem+alttan] [DEPAR]    │  23,5 kredi   │
│   Dersler│  [Öneri 1][2][3][Karşılaştır] │  ▸ 11 ders …  │
│   Neden  │  ┌───┬───┬───┬───┬───┐        │  [Kaydet]     │
│  DURUM   │  │PZT│SAL│ÇAR│PER│CUM│        │  [Kayıt günü] │
│   …      │  └───┴───┴───┴───┴───┘        │  ▸ Nasıl …    │
└──────────┴───────────────────────────────┴───────────────┘
```

Solda **ray** (eski bölüm çubuğu), ortada program, sağda bağlam. Sağ sütunda
duran şeyler yeni değil — özet, arz uyarısı, kilit şeridi, araç çubuğu ve
iki ipucu satırı ızgaranın ÜSTÜNDEYDİ: 8 blok, **313 kelime**.

### B2. Gezinme çapa değil, görünüm değiştirici

Eskiden 10 bağlantı vardı ve hepsi **aynı sayfada bir yere kaydırıyordu**.
"Haftalık programım"a tıklamak sayfayı kısaltmıyordu. Artık aynı anda tek
bölüm açık; sayfa 7,3 ekrandan 1,4'e indi.

⚠️ İki durum ayrı tutuluyor:

| bayrak | anlamı |
|---|---|
| `hidden` | **veri yok** — bölüm rayda hiç görünmüyor |
| `data-disgorunum` | **şu an bakmıyorsun** — rayda var, tek tıkla açılıyor |

İkisini tek bayrağa bindirmek, veri gelince açılmayan ya da boş açılan bir
sekme demekti.

Rayda **sayı** var: `Alabileceğim dersler 79`, `Neden alamıyorum 14`. Bölüme
girmeden büyüklüğü görünüyor; eskiden bunu öğrenmenin tek yolu oraya
kaydırmaktı. Sayamadığımız bölümde hiçbir şey yazmıyor.

### B3. Telefonda alt sekme çubuğu

Dört birincil sekme (**Program · Dersler · Neden · İlerlemem**) yazılı,
kalan yedisi **Daha** altında. Faz 39'un "kenar solmasıyla kaydır" çözümü
ölçümde çürüdü: 390px'te 10 çapanın **3'ü** görünüyordu ve solma kaydırmayı
ancak ima ediyordu.

⚠️ İki CSS ayrıntısı ölçümle bulundu:
* `raykesme` — sıfır yükseklikli satır kırıcı. Birincil sekmelerin
  `flex-basis`i 0 olduğu için esnek satır "dolmuş" sayılmıyordu ve "Daha"
  açılınca ilk iki alt sekme birincil satıra sızıp dördünü 26px'e eziyordu.
* `flex-wrap: wrap-reverse` — açılan ızgara **yukarı** büyüsün; birincil
  satır başparmak menzilinde, en altta kalsın.

### B4. Dokunma hedefleri

| hedef | önce | sonra |
|---|---|---|
| ızgara boş hücresi (38 adet) | 19px | **28px** + görünür `+` işareti |
| `.tier li .dispre` (17) | 18px | 24px |
| `.watchmini` (11) | 21px | 24px |
| `.trtable .rm` (4) | 22px | 24px |
| onay kutusu (2) | 13px | 18px + saran etiket ≥24px |

⚠️⚠️ **Faz 39'un bir kararı geri alındı.** O turda "masaüstünde sıkışık
durması doğru, fare pikseli tutturur" demiştim ve tabanı yalnız telefona
koymuştum. WCAG 2.2 AA 2.5.8 işaretleyici girdiler için de geçerli ve
masaüstünde 24px altında **72 hedef** vardı. Taban artık her yerde 24,
telefonda 32/34. Testi (`test_TELEFONDA_kucuk_denetim_KALMADI`) sildim değil,
**yeniden yazdım**: telefon kuralı duruyor, masaüstü muafiyeti kalktı.

İki istisna WCAG'in kendi maddeleri, ölçümde de öyle uygulanıyor:
*Inline* (cümle içi bağlantı, boyutu satır yüksekliğiyle sınırlı) ve
*Enclosed/Equivalent* (onay kutusunu saran `<label>` aynı işi yapıyor ve
tabanın üstünde).

### B5. Metin katlandı — gizlenmedi

Arz uyarısı 115px ve 47 kelimeydi. Artık tek satır: **"▸ 11 ders bu dönem
alınamıyor"**. ⚠️ Bu repoda "genel uyarı" yasak — katlanmış hâlde bile
**sayı** yazıyor, ayrıntı tek tıkla aynı yerde. Kullanım ipuçları (59
kelime) da katlandı; Faz 40'ın dersi gereği silinmedi.

Sayfa içi bölüm bağlantıları (`Darboğaz bölümünde ayrıntı`) artık görünüm
açıyor. Görünüm kipinde kaydırmak hiçbir şey yapmazdı ve çalışmaz bir
bağlantı bırakmak Faz 25/44'te ölçtüğümüz hatanın aynısı olurdu.

### B6. 5,7 saniye → 1,1 saniye

`snapshot()` profillendi (cProfile, gerçek veri):

| | kümülatif | ne |
|---|---|---|
| `prereq.parsed_trees` | **14,8 sn** | tek durum çıkarımında **12 kez** çağrılıyor, her seferinde aynı ~4.630 önşart metnini baştan ayrıştırıyor (**55.560 ayrıştırma**) |
| `build_schedules` → `_sube_maliyeti` | **3,4 sn** | `blocking_cost(s, index)` `chosen`a bakmıyor ama arama ağacının **her düğümünde** yeniden hesaplanıyor (46.549 çağrı) |

İki önbellek:
* `prereq.parse` → `lru_cache`. Ağaç üretildikten sonra değiştirilmiyor
  (mutasyon yalnız ayrıştırma sırasında ve `load_tree`de).
* `build_schedules` içinde `_sira[index]` — indeks başına bir kez sıralama.

Duvar saati: **7,9 sn → 0,95 sn.** Bu yalnız yazma uçlarını değil ilk
yüklemeyi ve test süresini de kısalttı (tam takım 359 → 128 sn).

⚠️ Bir önbellek davranış değiştirmemeli. Doğrulandı: aynı havuzla kurulan
program önbellekten önce ve sonra **birebir aynı** (16 ders, 22,5 kredi,
aynı CRN'ler), ve `test_ONBELLEK_SONUCU_DEGISTIRMIYOR` bunu tutuyor.
Sıralama anahtarına `chosen` girerse memo kaldırılmalı — testte yazılı.

### B7. Küçükler

* "tazele" düğmesi cümlenin ortasındaydı; satır artık esnek, düğme ayrı parça.
* Aday tablosu 390px'te 418px — kaydırılabiliyordu ama işareti yoktu. Kenar
  solması eklendi (eski bölüm çubuğundan gelen desen, gereken yere taşındı).

---

## C. Geri alınan kararlar — ikisi de sebebiyle

Bu turda iki eski karar **değişti**. İkisi de teste yazılı, sebebiyle:

1. **Faz 20: "kaydedilen program en üstte."** Doğruydu — kayıt haftasında
   araca dönmenin sebebi "ben ne kaydetmiştim". Ama o zaman sayfa tek
   yığındı ve "en üstte" = "ilk görülen". Görünüm kipinde açılışa koymak,
   kullanıcıyı **düzenlenemeyen** bir kaydın karşısına çıkarırdı. Oysa
   `startFromSaved()` kaydedileni zaten ÇALIŞMA ızgarasına yüklüyor: haftalık
   program görünümü kaydın kendisi artı düzenlenebilirlik. Kayıt rayda,
   sayısıyla duruyor. (`test_ILK_GORUNUM_haftalik_program`)
2. **Faz 39: "masaüstünde küçük hedef doğru."** Ölçümle çürüdü — B4.

---

## D. Testler

`tests/test_faz46_kabuk.py` (17 test): kabuk iskeleti · program ortada /
bağlam sağda · gezinme çapa değil · `hidden` ile görünüm ayrı · sayfa içi
bağlantılar · gizli bölümün ölçüsü yeniden alınıyor · ızgara satırı 28px ·
onay kutusu · uyarı katlandı ama sayısı görünüyor · yatay kaydırma ipucu ·
tazele düğmesi · telefon alt çubuğu · önşart önbelleği · şube sırası memosu ·
önbellek sonucu değiştirmiyor · **üretilen JS ayrıştırılabiliyor** · uçtan
uca kabuk.

⚠️ Sonuncusu bu turda **gerçekten olan** bir hatadan doğdu: arayüzün tamamı
Python'da bir JS şablon dizgesi içinde duruyor ve içine ters tırnaklı bir
HTML yorumu yazınca JS dizgeyi orada kapattı — sayfanın tamamı öldü
(`GORUNUM is not defined`). Tarayıcı testleri yakaladı ama 7 saniye sürdüler;
`node --check` ile yapılan yeni kontrol 0,2 saniye sürüyor ve hata
**sınıfını** tutuyor, tek örneğini değil.

Yeniden yazılan dört test (silinmedi, sebebi başlarında yazılı):
`test_ILK_GORUNUM_haftalik_program`,
`test_ray_GORUNUM_degistiriyor_KAYDIRMIYOR`,
`test_TELEFONDA_hicbir_gorunum_ULASILAMAZ_DEGIL`,
`test_TELEFONDA_kucuk_denetim_KALMADI`.

Beş düzeltme geri konulup kırmızıya döndükleri görüldü: ızgara satırı,
önşart önbelleği, şube sırası memosu, görünüm değiştirici, sağ sütun.

## E. Bu turda ölçüm bir hatayı yakaladı

Kademe diyagramının bağ çizgileri `getBoundingClientRect` ile kuruluyor.
Bölüm kapalıyken bütün ölçüler 0 çıkıyor ve görünüm açılınca **çizgisiz**
bir diyagram kalıyordu. Testte yakalandı, `gorunumAc` artık görünüm açılınca
yeniden çizdiriyor. Gizli bir bölümün ölçüsü yoktur — görünür olunca bir kez
daha ölçmek zorunludur.
