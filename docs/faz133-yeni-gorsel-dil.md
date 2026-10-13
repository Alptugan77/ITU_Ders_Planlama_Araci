# Faz 133 — Yeni görsel dil

**Tarih:** 13.10.2026
**İstek:** "redesign the ui and ux of the site". Karar kartında
"Görünüşü koru, düzeni düzelt" yerine **"New visual style"** seçildi.

Faz 132'nin düzeni (tek bantlı üst çubuk, ince "sonraki adımlar", iki gruplu
program sütunu, yol haritası ayar panosu) aynen duruyor. Bu faz **görünüşü**
değiştiriyor. Bilgi mimarisi, görünüm adları, düğme kimlikleri ve
metinler aynı kaldı.

## Fikir: renk veride

Eski dilde yapı rengi (periwinkle `--seal`) her yerdeydi: cetvel, eyebrow,
seçili sekme, birincil düğme, bağlantı. Program rolü renkleri de (anadal
yeşili, ÇAP kehribarı, yandal mavisi) aynı ekranda yarışıyordu.

Yeni dilde **yapı mürekkep rengi**, yani nötr. Seçili sekme, birincil
düğme ve bağlantı siyah (gece temasında kırık beyaz). Ekranda renk taşıyan
şey yalnız **veri**: dersin programı ve durum (dolu, uyarı, çakışma).
Renkli bir şey görmek "bu bir bilgi" demek.

| jeton | gece | gündüz | not |
|---|---|---|---|
| ground | `#1E1E22` | `#FAFAFB` | gece "loş" kaldı: OKLab L 0.237 (Faz 70: 0.22–0.30) |
| surface | `#29292F` | `#FFFFFF` | kart; zeminden ΔE 0.047 (gece) |
| surface-2 | `#33333A` | `#EFEFF1` | |
| ink / ink-2 / ink-3 | `#F2F2F4` / `#CFCFD6` / `#B5B5BF` | `#18181B` / `#46464E` / `#5E5E68` | ink-2 kartta 9.33:1, ink-3 7.11:1 (gece) |
| seal | `#F2F2F4` | `#26262B` | yapı = mürekkep |
| seal-soft | `#38383F` | `#E7E7EA` | seçili ray, seçili kip |

Veri ve durum renkleri (anadal, ÇAP, yandal, danger, warn) **değişmedi**.
Faz 40'ın ton merdiveni ve Faz 43'ün kontrast çiftleri onlara bağlı.

Ölçüm:

* `python tools/kontrast_olcumu.py`: 80 çiftin hepsi tabanın üstünde.
* `python tools/ton_merdiveni.py`: yazı ≥ 4.60, zemin ΔE ≥ 0.035. Gündüz
  zemini bu yüzden `#FAFAFB`. `#F5F5F6`'da yandal bloğu boş hücreden
  ayrılmıyordu (ΔE 0.026).

## Yazı: Geist + Geist Mono

Chivo (başlık), IBM Plex Sans (gövde) ve IBM Plex Mono (kod) yerine Geist
ve Geist Mono geldi (SIL OFL 1.1, lisans `fonts/OFL-Geist.txt`). İkisi de
**değişken yüz** (100–900):

* her ağırlık gerçek, taklit kalın (Faz 43'ün sorunu) olamaz;
* gömülü yazı tipi 9 dosya / ~400 KB yerine 2 dosya / ~140 KB;
* Türkçe karakterlerin hepsi var. "✓ ▸ ▾ ⚠" yok; eskisi gibi sistem yazı
  tipine düşüyor.

Başlıklar cümle düzeninde, 600 ağırlıkta. Zorla BÜYÜK HARF yalnız doluluk
rozetinde (DOLU / SON n, aciliyet) ve blok rol işaretinde kaldı. Raydaki
grup adları veride büyük harf ("PLANLA"). CSS onları `lang="tr"` ile
küçültüyor, ilk harfi büyütüyor.

## Biçim: tek köşe kuralı

| jeton | değer | nerede |
|---|---|---|
| `--r` | 8px | düğme, alan, sekme, ızgara bloğu, not kutusu |
| `--r-lg` | 12px | kart, pencere, panel |
| `--r-sm` | 6px | rozet, çip, ders kodu kutucuğu |

Kalın yapısal cetveller (3px üst çubuk, 6px panel başı, bölüm cetveli)
yerine ince hat ve kartın kendi gölgesi (`--shadow-card`) kullanılıyor.
Izgarada saat başı çizgisi cetvel rengi yerine belirgin bir ince hat.
`tools/tasarim_envanteri.py --denetle` üç köşe jetonunu tanıyor.

## Simge

`tools/simge_uret.py`: zemin artık mürekkep (`#26262B`), ders blokları
aynı veri renklerinde. PNG ve SVG yeniden üretildi.
