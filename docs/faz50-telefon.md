# Faz 50 — Not dağılımı çubukları ve telefon arayüzü

*18.09.2026 · kullanıcı: **"not dağılımında +lar yüzünden barların tabanları
aynı seviyede olmuyor düzeltir misin. bir de telefonun arayüz tasarımını
geliştirebilir misin şu anda telefonda kullanılması biraz zor"***

Testler **1136 → 1145**.

---

## A. ★★ Çubukların tabanı — kök sebep etiketten daha derindeydi

**Ölçüm** ("artıları ayır", 15 kova):

| | önce | sonra |
|---|---|---|
| çubuk tabanı | **3 ayrı seviye**, 7px fark | **tek seviye** |
| etiket kutusu | 10 / 12 / 17px (karakter sayısına göre) | tek boy |
| en büyük çubuk | 104px kaba **104px** isteniyordu (taşıyordu) | 76px, kabın içinde |

Görünen sebep etiketti: dikey yazılan "BA+" 17px, "AA" 12px; sütun alttan
hizalı olduğu için uzun etiket çubuğu yukarı itiyordu.

Gerçek sebep bir katman altındaydı: **`.ndsut` esnek kutuydu ve üç öğe
(sayı + `%100` çubuk + etiket) kabı taşırıyordu.** Tarayıcı taşmayı
öğeleri büzerek çözüyor, büzülme miktarı çubuğun boyuna göre değiştiği için
tabanlar kayıyordu. Aynı sebepten **yüzdeler de yanlıştı**: `%100` kabın
tamamı kadar isteniyordu, oysa sayı ve etiket de o kabın içinde.

**Düzeltme:** sütun üç satırlık ızgara — `auto / minmax(0,1fr) / auto`:
sayı, çubuk alanı, etiket. Birinci ve üçüncü satır bütün sütunlarda aynı
yükseklikte olduğu için taban ortak ve yüzdeler ortak bir alana göre.

> ⚠️ Yer varsa dikey yazı da kalktı: ölçüldü, 560px'ten sonra sütun ≥26px
> ve yatay "BA+" 17px — sığıyor. Döndürülmüş 8.5px yazı okunmuyordu. Dar
> ekranda (390px'te sütun 17.7px) sığmadığı için orada dikey kalıyor, ama
> kutusu **sabit**.

Dört genişlik × iki kip tarayıcıda ölçülüyor (`test_CUBUK_TABANLARI_ayni_seviyede`).

---

## B. Telefon turu — ölçülen beş sorun

390×844'te on bir görünüm ve beş pencere tek tek gezildi.

| ölçüm | önce | sonra |
|---|---|---|
| aday listesinde **bir ders satırı** | **330px**, kontenjan sütunu kutunun dışına taşıp rakamı kesiyor ("180"→"18") | **118–165px**, kesik yok |
| içeriğin başladığı yer (10 görünümde) | **475px** (ekranın %56'sı kabuk) | **255px** |
| öneri sekmeleri | **3 satır**, "ÖNERİ 1 · 20**KREDİ**" | 1–2 satır, "20 kredi" |
| 44px altı denetim | görünüm başına **7–8** | 0 |
| `.watchmini` / `.dispre` telefon kuralı | **ölü** (24px) | 34 / 32px |
| ekran sayısı (aday · engel · kademe · ilerleme) | 3.0 · 2.1 · 3.5 · 1.9 | 2.8 · 1.9 · 3.4 · 1.6 |

### B1. ★★ Aday listesi telefonda kart oldu

Asıl iş burada yapılıyor ve telefonda **hem çok uzundu hem eksik
okunuyordu**: dört sütun kalsa bile ders sütununa ~160px düşüyor, açıklama
25 karakterde sarıyor, sağdaki kontenjan sütunu kutunun dışına taşıp
rakamı kesiyordu.

Artık aynı `<tr>` telefonda kart olarak diziliyor:

```
BLG 212E  [programda]                    132.5 puan
Microprocessor Systems — 13 dersin önşartı; ÇAP…
3 kredi                        ▓▓▓░ 180 boş 2 şube
```

> ⚠️ **Tek DOM.** İkinci bir çizim yazsaydık ikisi ayrışırdı — bu depoda
> ölçülmüş bir hata sınıfı. Masaüstünde hâlâ tablo (satır 69–70px,
> değişmedi), telefonda kart.
> ⚠️ Kartta sütun başlığı olmuyor; `kredi` etiketi `data-e` ile hücrenin
> yanına yazılıyor — başlıksız çıplak sayı bırakmıyoruz.

### B2. Sekmelerdeki yutulan boşluk — sınıfın üçüncü görülüşü

"ÖNERİ 1 · 20**KREDİ**": `.tab` esnek kutu, esnek kutu da **öğe
sınırındaki boşluğu yutuyor**. Aynı sınıf arz başlığında (Faz 46) ve
`summary` tabanında (Faz 48) çıkmıştı. Etiketin tamamı tek `<span>` içine
alındı.

Kredi sayısı da `.tabfark` içine girdi: telefonda seçili olmayan sekme
yalnız "Öneri 2" yazıyor (Faz 46'nın kararı — ayırt edici metin yalnız
seçili sekmede, tamamı `title`da).

### B3. Kabuk bedeli

"Programın hazır. Şimdi:" panelinin dört düğmesinin **ikisi alt çubuğun
kopyasıydı** ("Haftalık programa bak" = Program sekmesi, "Ders ekle" =
Dersler sekmesi) ve panel **her görünümün** üstünde 232px yer kaplıyordu.
Telefonda: iki kopya düğme çıktı, panel yalnız **program görünümünde**
duruyor.

> ⚠️ Bilgi gizlenmiyor: hedefin kendisi ekranın altında, her zaman, bir
> dokunuş uzakta.

### B4. ★★ Üç telefon kuralı ÖLÜYDÜ

`.watchmini` (34px), `.tier li .dispre` (32px) ve `summary` (32px) telefon
kuralları yazılıydı ama **çalışmıyordu**: temel kuralları kaynakta medya
bloğundan **sonra** geliyor ve aynı özgüllükte oldukları için eziyordu.

> **Medya sorgusu özgüllük kazandırmaz.** Sık yapılan varsayım; burada iki
> fazdır sessizce yanlış çalışıyordu. Ölçüldü: hesaplanan `min-height` =
> 24px. Seçiciler öğe adıyla nitelendi (`button.watchmini`, `span.dispre`,
> `.ipucu>summary` …).

Ayrıca onay kutusu 18px'ti → 22px, satırı 44px.

---

## Ölçülüp DEĞİŞTİRİLMEYENLER

| ne | ölçüm | neden dokunulmadı |
|---|---|---|
| başlık bloğu | 213px | İçindekilerin hepsi taşıyıcı: hangi programlar, hangi dönem, **verinin yaşı**, tazele. Piksel için bilgi katlamak bu deponun kuralına aykırı. |
| `.rm` / `.watchmini` 34px | 44'ün altında | Faz 39'un ölçülmüş kararı: yoğun liste satırlarını şişirmemek. WCAG 2.2 AA tabanı (24) fazlasıyla sağlanıyor. |
| satır içi bağlantı (34px) | 44'ün altında | WCAG'ın "Inline" muafiyeti. |
| gün listesi satırı | 76px | Okunuyor, kesilmiyor, çakışma işaretli. |
| komşu hedefler arası 0px | 13 çift | Hepsi **bitişik tasarlanmış** segment denetimleri (sekme çubuğu, kip anahtarı) — yanlış dokunma değil, tek parça kontrol. |

---

## Testler

`tests/test_faz50_telefon.py` (9 test): sütun ızgara (esnek kutu değil) ·
etiket kutusu sabit · yer varsa yatay etiket · **çubuk tabanları tek
seviyede** (tarayıcıda, 4 genişlik × 2 kip) · sekme etiketi tek parça ·
aday tablosu telefonda kart · "Şimdi" paneli program görünümünde · telefon
hedef kuralı ölü değil · **uçtan uca** (390px: kart düzeni, kart yüksekliği,
kesik hücre yok, sekmedeki boşluk piksel olarak ölçülüyor, 32px altı hedef
yok, içeriğin başladığı yer).

⚠️ `test_faz39_tasarim` yeniden yazıldı (silinmedi, sebebi başında): hem
`_mobil_css()` yalnız İLK medya bloğunu okuyordu, hem de aradığı iki kural
**ölüydü** — test "kural yazılı mı" diye soruyordu, "çalışıyor mu" diye
değil. Asıl güvence artık hesaplanan değeri ölçen uçtan uca test.
