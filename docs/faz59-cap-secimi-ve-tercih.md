# Faz 59 — "Ya ÇAP'ı şurada yapsaydım", azami süre, tercihi kaydetmeden dene

*24.09.2026 · kullanıcı: "continue on your improvements and changes".*

`fikirler.md`'nin açık kalemlerinden üçü:

| | Ne | Neden |
|---|---|---|
| Y.1 | Başvuru penceresinde her ÇAP programı için **tahmini bitiş** | Derece planlayıcılarının en çok kullanılan özelliği; pencere "sende sayılan ders" sayısını veriyor, asıl soruyu — ne zaman biterim — cevaplamıyordu |
| Y.7 | **Azami öğrenim süresi** ve bitişin kaçıncı yarıyıl olduğu | Yol haritası bitişi dönem adıyla yazıyordu; öğrenci yarıyılla düşünüyor ve süre sınırı kimse söylemeden aşılabiliyordu |
| §3.6 | Tercihi **kaydetmeden dene** | Tercihin bedelini görmek için kaydetmek, beğenmezsen geri almak gerekiyordu |

Testler **1270 → 1278** (+8), 4 atlandı. Geri alma deneyi:
yedi kuralın **yedisi** geri konunca kendi sebebiyle kırmızı (§5).

---

## 1. ★★ "Ya ÇAP'ı şurada yapsaydım" (`ui.cap_bitisleri`, `/api/capbitis`)

Yol haritası motoru (Faz 57) herhangi bir plan listesiyle çalışıyor. Başvuru
penceresi açılınca, öğrencinin anadalına açık her ÇAP planı için **anadal +
o ÇAP** birlikte kuruluyor ve "Tahmini ÇAP bitişi" sütununa yazılıyor:

> **2027-2028 Bahar** (10. yarıyıl) — 5 ders kaldı · 4 dönemde yarıyıl
> tabanı tutmuyor · 1 dersin mevsimi bilinmiyor

Ayrıca: ÇAP anadalı geciktiriyorsa (yalnız anadalla kurulan haritaya göre)
"anadalı N dönem geciktiriyor"; birden çok seçenek varsa **Bitişe göre
sırala**.

**Varsayımlar pencerede yazıyor:** ÇAP'a bir sonraki yarıyıl başlanıyor
(yarıyıl tabanı ona göre: vitrinde 6. yarıyıl → 9 kredi); bu dönem yol
haritasındaki dersler alınıyor; yol haritasının bütün varsayımları geçerli;
**başvurunun kabulü, kontenjan ve sıralama şartı hesapta yok**; şu anki
ÇAP/yandal plana girmiyor — soru "onun yerine bu olsaydı".

### ⚠️ Kalan kredi YOK

İlk sürüm "5 ders, 15 kredi kaldı" yazıyordu. Bu pencerenin 22.08.2026
kararıyla çelişiyordu: kullanıcı kalan kredinin yanlış çıktığını bildirmişti
ve sebebi havuz slotlarının kredisinin programdan programa farklı
sayılmasıydı. Kredi hem uçtan hem hücreden çıkarıldı; ders sayısı sağlam.
Test hücrenin gövdesinde "kredi" kelimesini arıyor.

### Neden istek üzerine

60 programı sayfa açılırken kurmak statik sitede (Pyodide) saniyeler
sürerdi. Uç salt okunur (`READ_ONLY_PATHS` — durum yeniden kurulmuyor),
girdisi sınırlı (≤60 plan, ≤20 ders, kredi sınırı 1–60) ve sonuç bu dönemin
dersleri değişmedikçe önbellekte. Vitrinde tek programla 9 ms.

Vitrine ikinci bir ÇAP seçeneği eklendi (INS, HTAE'ye açık, uydurma): dört
halkalık zincir, öğrencinin zaten geçtiği MAT 201E ve geçmiş dağılımı olan
dersler — hesap her parçasıyla görünsün diye.

## 2. Azami öğrenim süresi ve bitiş yarıyılı

Yol haritası kartları artık bitişin **kaçıncı yarıyıl** olduğunu yazıyor
(`finishSemester` = bulunduğun dönem + bitişin sırası; yaz sayılmıyor;
dönem bilinmiyorsa yazılmıyor). Anadal kartında: *"10. yarıyılında · azami
14 ⚠"*; bitiş azami süreyi aşarsa *"azami öğrenim süresini N yarıyıl aşıyor —
danışmanınla konuş"*.

### ⚠️ Sayı doğrulanmadı ve bu görünüyor

`config/kurallar.toml` → `[azami_sure] yariyil = 14, dogrulandi = false`.
Kaynak: **2547 sayılı Kanun Madde 44/c** (lisans: 7 yıl; arama sonuçlarında
İTÜ'nün kendi "azami süre" yönergesi de bu maddeye dayanıyor). İTÜ Lisans
Yönetmeliği'ndeki madde numarasına ve hazırlığın sayılıp sayılmadığına bu
ortamdan ulaşılamadı (`sis.itu.edu.tr` ve `mkn.itu.edu.tr` ağ politikasıyla
kapalı). Bu yüzden:

* sayı ⚠ ile gösteriliyor, üzerine gelince/dokununca kaynak ve
  "doğrulanmadı" yazıyor (eşiklerle aynı kural);
* yalnız **anadala** uygulanıyor — ÇAP'ın kendi süre kuralını bulamadık,
  uydurmuyoruz; ÇAP kartında yalnız yarıyıl yazıyor.

Teyit edildiğinde `kaynak`ı İTÜ maddesiyle değiştirip `dogrulandi = true`
yapmak yeter; test o gün bilerek kırmızı olacak (doğrulanmamış işaretini
tutuyor) ve güncellenmeli.

## 3. Tercihi kaydetmeden dene (`/api/tercih/onizle`)

Tercih penceresinde **Kaydetmeden dene**: sunucu ayarların **bellekteki**
kopyasını (`dataclasses.replace`) tercihlerle değiştirip raporu aynı yoldan
(`UI.collect`) kuruyor ve açık kipin 1. önerisini döndürüyor. Dosyaya
hiçbir şey yazılmıyor — uçtan uca test ayar dosyasını önce ve sonra
karşılaştırıyor.

Pencerede bugünkü 1. öneriyle yan yana: giren/çıkan ders, değişen şube,
haftanın şekli (gün, saat aralığı, boş gün), tercih puanı ve karşılanamayan
kısım; karşılanamıyorsa Faz 37'nin "ne bırakılmalı" önerisi. Vitrinde
"10:30'dan önce yok, pazartesi boş": *"BLG 223E şubesi 22301 → 22302 ·
Tercih puanı −44: 4 ders istediğinden erken başlıyor · 2 ders boş istediğin
güne düşüyor"* — yani bu tercihler bu dönemin şubeleriyle büyük ölçüde
karşılanamıyor ve bunu kaydetmeden öğreniyorsun.

⚠️ Doğrulama kaydetmeyle ORTAK (`_tercih_degerleri`): önizlemenin kabul edip
kaydetmenin reddettiği bir tercih olmasın. Arayüzde de iki düğme aynı
`govde()`yu gönderiyor.

## 4. Bedel

`/api/capbitis`: plan başına bir harita kurulumu (vitrinde 9 ms / 1 plan).
`/api/tercih/onizle`: bir tam rapor (gerçek veride ~1,5 s — düğme "hesaplanıyor…"
diyor ve kilitleniyor). İkisi de salt okunur; sayfa açılışını
yavaşlatmıyor.

## 5. Testler ve geri alma deneyi

`tests/test_faz59_capbitis_ve_tercih.py` (8 test). Faz 54'ün bir testi
"tercih kaydı kipi korur" kuralını `}), {});` kalıbını SAYARAK ölçüyordu;
tercih gövdesi `govde()`ye taşınınca kalıp değişti, kural değişmedi. Test
artık iki çağrının kendisini arıyor.

| Geri konan | Kırmızı |
|---|---|
| Önizleme ayar dosyasına yazıyor | statik + uçtan uca (dosya karşılaştırması) |
| Hücre kalan kredi yazıyor | statik + uçtan uca |
| Azami süre ÇAP'a da uygulanıyor | `test_AZAMI_SURE_yalniz_ANADALA_ve_isaretli` |
| Azami süre "doğrulandı" işaretleniyor | birim + uçtan uca (⚠ yok) |
| Dönem bilinmiyorken yarıyıl tahmin ediliyor | `test_BITIS_YARIYILI_donemden_sayiliyor` |
| İki uç salt okunur değil | iki statik test |
| Kaydet ve dene ayrı gövde gönderiyor | `test_ONIZLEME_salt_okunur_ve_DOGRULAMA_ORTAK` |

## 6. Ne yapılmadı

* Azami sürenin İTÜ maddesi ve ÇAP'ın kendi süre kuralı — ağ politikası
  yüzünden bu ortamdan doğrulanamadı; `fikirler.md` Y.7'ye not düşüldü.
* Yandal için "ya şurada yapsaydım" — İTÜ yandal planlarını OBS'de
  yayınlamıyor (Faz 12, 22.08.2026 doğrulaması); plan yoksa hesap yok.
* Y.8 (kayıt günü çevrimdışı) açık.
