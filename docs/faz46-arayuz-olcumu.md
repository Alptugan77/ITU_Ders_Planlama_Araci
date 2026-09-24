# Arayüz ve kullanılabilirlik — ölçülmüş iyileştirme listesi

*17.09.2026 · kullanıcı: "tasarım ve kullanılabilirlik açısından
iyileştirebilir şeyleri listele"*

Bu liste **fikir listesi değil**. Her madde tarayıcıda, gerçek veriyle
(78 aday, 16 derslik program, 3417 şube) ölçülmüş bir sayıya bağlı.
Ölçüm iki genişlikte yapıldı: **1440×900** (masaüstü) ve **390×844**
(telefon, dokunmatik).

Ölçüm betikleri tek seferlikti; sayılar aşağıda, üretme yöntemi her
maddenin altında yazıyor.

---

## Önce: ölçülüp **sağlam** çıkanlar

Bunlara dokunmaya gerek yok — "iyileştirme" diye bozmayalım:

| ne | ölçüm |
|---|---|
| Renk kontrastı | `tools/kontrast_olcumu.py`: **52 çift, iki tema, hepsi tabanın üstünde** |
| Odak halkası | `td.free` odakta `2px solid #3B4E9E` — görünür |
| Sayfa yatay taşması | `documentElement.scrollWidth == innerWidth` (390 == 390) — taşma yok |
| Gezinme çubuğu kaydırma ipucu | kenar solması var (`data-more`), Faz "UX 27.08" |
| Telefonda ızgara | gizleniyor, yerine gün listesi çıkıyor — doğru karar |

---

## 1. Ana iş ilk ekranda yok

| | masaüstü | telefon |
|---|---|---|
| haftalık programın tepesi | **y = 1825px** (1.5 ekran) | **y = 3354px** (4.0 ekran) |
| ilk ekranda ne var | başlık + gezinme + "Programın hazır" kutusu + kurulum çubuğu + kaydedilen program | aynısı, **hiç program içeriği yok** |
| ilk ekrandaki düğme | 13 | 13 |

Aracın adı "ders planlama" ve ürettiği şey **haftalık program**. O nesne
ilk ekranda yok; telefonda dört ekran aşağıda.

> *ölçüm: `section.card` kutularının `getBoundingClientRect().top + scrollY`*

## 2. Sayfa 7 (masaüstü) / 16 (telefon) ekran uzunluğunda

| | masaüstü | telefon |
|---|---|---|
| sayfa yüksekliği | 6570px = **7.3 ekran** | 13834px = **16.4 ekran** |
| yığılmış bölüm | 11 | 11 |
| gezinme öğesi | 10 | 10 (**aynı anda 3'ü görünür**) |

Gezinme çubuğu **filtre değil çapa**: tıklayınca o bölüme kaydırıyor,
diğer 10 bölüm yerinde duruyor. Yani "Haftalık programım"a tıklamak
sayfayı kısaltmıyor.

> *ölçüm: `scrollHeight`; `#secnav a` sayısı ve görünür olanları*

## 3. Aynı anda 60 ikincil metin öğesi görünüyor

| sınıf | ne | adet |
|---|---|---|
| `.chip` | rozet | 22 |
| `.eyebrow` | bölüm üstü küçük başlık | 16 |
| `.why` | "neden" açıklaması | 13 |
| `.note` | uyarı/bilgi kutusu | 7 |
| `.hint` | ipucu satırı | 2 |
| **toplam** | | **60** |

Yalnız haftalık programın **üstünde** 8 blokta **313 kelime** var
(kip seçici + notu 48, arz uyarısı 47, araç çubuğu 59, ızgara üstü
ipuçları…). Sayfanın tamamı 1826 kelime.

Bu metinlerin her biri tek tek doğru ve ölçümle yazılmış (bu repo öyle
çalışıyor). Sorun tek tek doğru olmamaları değil, **hepsinin aynı anda
açık olması**: hiçbiri ikincilmiş gibi görünmüyor.

> *ölçüm: görünür (`offsetParent !== null`) ve metni boş olmayan öğeler*

## 4. 83 dokunma hedefi 24px'in altında

WCAG 2.2 AA (2.5.8 Target Size, Minimum) tabanı **24×24px**:

| hedef | adet | en küçük kenar | örnek |
|---|---|---|---|
| `td.free` — **boş saate tıkla** | 38 | **19px** | 235×19 |
| `.dispre` | 17 | 18px | 72×18 |
| `a` (metin içi bağlantı) | 11 | 15px | 151×15 |
| `.watchmini` | 11 | 21px | 38×21 |
| `.rm` (çıkar) | 4 | 22px | 46×22 |
| `input` (onay kutusu) | 2 | **13px** | 13×13 |

En can alıcısı birincisi: **Faz 44'te düzelttiğimiz "boş saate tıkla →
ders ekle" özelliğinin hedefi 19px yüksekliğinde.** Özellik çalışıyor
ama hedefi standart tabanın altında.

> *ölçüm: odaklanabilir/tıklanabilir seçicilerin `getBoundingClientRect()`*

## 5. Her ayar değişimi 5.6–5.7 saniye

| işlem | süre |
|---|---|
| ilk yükleme (yerel sunucu) | **7.5 sn** |
| `/api/mesgul` ekle | **5.7 sn** |
| `/api/mesgul` sil | **5.6 sn** |
| `/api/kilit` | **5.7 sn** |

Ağ değil, hesap: her yazma ucu `snapshot()` çağırıyor, o da **iki kip
için** aday havuzunu ve programları baştan kuruyor. Düğmeler "…"
gösterdiği için donmuş görünmüyor ama bir saat kilitlemek 6 saniye
sürüyor.

Ucuz iyileştirme: yazma cevabında **yalnız değişen parçayı** döndürmek,
ya da kip başına önbellek (ayar değişmeyen kipi yeniden kurmamak).

> *ölçüm: tarayıcıda `performance` yerine duvar saati; 2 tekrar*

## 6. Telefonda aday tablosu ekranı taşıyor (ama ulaşılabilir)

`#candSection table.list` **418px**, ekran 390px. Sarmalayıcı `div`in
`overflow-x: auto`su var, yani kaydırılabiliyor — sayfa taşmıyor. Yine de
dikey bir sayfanın içinde yatay kaydırma, telefonda en sık kaçırılan
etkileşim.

> *ölçüm: tablo genişliği + ata zincirinde `overflowX`*

## 7. "tazele" düğmesi cümlenin içinde

Başlıktaki veri tazeliği satırı şöyle: *"şube/kontenjan verisi 17 gün
önce tazelendi (31.08.2026 10:34) **[tazele]** · ⚠ 2025-2026 Güz bitmiş
görünüyor"*. 390px'te bu cümle üç satıra sarıyor ve düğme satırın
ortasında kalıyor — hem okuma hem tıklama bozuluyor.

> *ölçüm: telefon ekran görüntüsü, 390px*

---

## Sıralama

Etki × maliyet:

| # | madde | etki | maliyet |
|---|---|---|---|
| 1 | Ana iş ilk ekranda yok | **yüksek** | orta (düzen değişikliği) |
| 4 | 19px'lik boş-saat hedefi | yüksek | **düşük** (satır yüksekliği) |
| 5 | 5.7 sn yazma gecikmesi | yüksek | orta (uç/önbellek) |
| 3 | 60 ikincil metin | orta | orta (açılır hale getirmek) |
| 2 | 7/16 ekran uzunluk | orta | yüksek (1 ile aynı iş) |
| 7 | satır içi "tazele" | düşük | **düşük** |
| 6 | telefonda yatay tablo | düşük | düşük |

**1 ve 2 aynı işin iki yüzü** — ikisini birden çözen bir düzen önerisi
ayrı bir tuvalde, görsellerle: *"İTÜ DEPAR — yeni görünüş önerisi"*
(Claude artifact, 7 artboard). Önerinin özeti:

1. **Program ekranı terk etmez.** Üç sütunlu kabuk: solda 8 görünümlük
   dar ray, ortada haftalık program (sabit), sağda bağlam paneli.
   Haftalık programın tepesi 1825px → **54px**.
2. **Gezinme çapa değil, görünüm değiştirici.** 10 çapa → 8 görünüm;
   tıklayınca sayfa kaymıyor, sağ panel değişiyor. Sayfa **1 ekran**.
3. **Uyarı gizlenmiyor, katlanıyor.** 47 kelimelik arz kutusu, sayısını
   taşıyan bir düğmeye iniyor: *"⚠ 11 ders bu dönem yok"*. Gizlemek bu
   repoda yasak; katlamak değil.
4. **Izgara satırı 19px → 28px** (telefonda 44px), boş hücrede görünür
   bir `+`. 24px altı hedef 83 → 28 (hedef).
5. **Yazma ucu yalnız etkin kipi kuruyor** — öbür kip istenince.

⚠️ Önerinin sağ sütunu (**hedef**) ölçülmedi. Bu repoda kural önce ölç
sonra değiştir; düzen değişikliği de uygulandıktan sonra aynı betikle
yeniden ölçülmeli. Ölçülmemiş bir "iyileştirme" iyileştirme değildir.
