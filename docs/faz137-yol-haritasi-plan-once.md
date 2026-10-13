# Faz 137 — Yol haritası: plan öne, varsayımların özü açık

**Tarih:** 13.10.2026
**İstek:** "continue" (arayüz ve kullanım iyileştirmesine devam)

Yol haritasına "hangi dönem hangi dersi alırım" sorusu için geliniyor.
Ölçüldüğünde (vitrin öğrencisi) dönem planı şuradaydı:

| | önce | sonra |
|---|---|---|
| masaüstü (1440px), planın üstü | 1555px | 1052px |
| telefon (390px), planın üstü | 3057px | 1765px |
| telefon, sayfa boyu | 5270px | 4686px |
| 6 dönem, masaüstü | 4 + 2 | 3 + 3 |

## Sıra

Önce: ayarlar → bitiş kartları → bu dönem alınması bitişi değiştirecek
ders → yaz okulu → kalma riski → 10 maddelik varsayım listesi → önşart
zinciri → "geçmişte" açıklaması → plan.

Sonra: ayarlar → bitiş kartları → bu dönem alınması bitişi değiştirecek
ders (kayıt kararı, düğmeli) → varsayım özeti → önşart zinciri →
**Dönem planı** → yerleşmeyen dersler → **Bitişi değiştirebilecek
durumlar** (yaz okulu, kalma riski).

## Varsayımlar hâlâ planın üstünde

Faz 57'nin kuralı (varsayımlar okunmadan geçilmesin) korunuyor; kutu
planın üstünde. Değişen, kutunun 10 madde dolu bir duvar olmaması:

* açık: "Bu plan bir tahmindir." ve üç temel varsayım: her ders ilk
  denemede geçiliyor, her dönem en çok N kredi, kontenjan ve yaz okulu yok.
  Üçü de motorun koşulsuz döndürdüğü maddeler (test tutuyor);
* açık: ⚠ ile başlayan maddeler (mevsimi bilinmeyen dersler, ortak
  program), çünkü bunlar bu öğrencinin verisindeki eksikler;
* katlı: "Hesaplama varsayımları (N)" altında maddelerin tamamı.

## Küçük düzeltmeler

* "geçmişte" açıklaması biçimsiz bir `.meta` olduğu için gövde boyundaydı,
  planın başlığından iri duruyordu. Artık küçük ve sönük, başlığın altında.
* Dönem sütunları dengeli: en çok dört sütun sığıyorsa satır sayısı
  hesaplanıp sütunlar ona göre dağıtılıyor (6 → 3 + 3, 5 → 3 + 2,
  7 → 4 + 3). Genişlik `#roadmapBody` kapsayıcı sorgusundan.

Görsel: `Claude outputs/f137-yol-haritasi-plan-once.png`.
