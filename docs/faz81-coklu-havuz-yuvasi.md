# Faz 81 — Seçmeli, uyduğu her havuz yuvasına yerleşebiliyor

*24.09.2026 · kullanıcı: "bunlardan sonra eklenebilecek şeyleri eklemeye ve
geliştirmeye devam et lütfen".*

Testler +4 (`tests/test_faz81_coklu_havuz_yuvasi.py`). Geri alma deneyi: dört
kuralın dördü kırmızı.

## Sorun (ölçüldü)

Aday üretimi her dersi yalnız ilk göründüğü plan yuvasıyla tutuyordu; motorun
"havuz tek dersle dolar" kontrolü de o tek yuvaya bakıyordu. Gerçek katalogda
havuzdaki (plan, ders) çiftlerinin **%38'i** (87.094'ten 33.149) birden çok
yuvaya uyuyor. ENDE'de "Functional-MT" dersleri 5., 6., 7. ve 8. yarıyılın
dört yuvasına uyuyor; hepsi 5. yarıyıl yuvasına bağlandığından motor bir
dönemde bu gruptan **en çok bir** ders önerebiliyordu — son sınıf öğrencisinin
dört yuvası boşken. Aynı sınır istemcide "programa sığanlar" süzgecini
(Faz 74) ve "yerine geçer" uyarısını da etkiliyordu.

## Çözüm

* `Candidate.slot_ids`: dersin uyduğu **bütün** yuvalar (birincisi eski
  `slot_id`).
* `yuva_ata`: iki taraflı eşleştirme (Kuhn) — seçilen derslerin her biri AYRI
  bir yuvaya yerleşebiliyorsa aday programa girebilir. Aynı dersin iki dili
  (EEF 110 / EEF 110E) tek yuvaya bağlı olduğundan eski kural korunuyor.
* İstemcide aynı eşleştirme (`yuvaAta`): `poolBlocker` (hangi dersin yerine
  geçer), panellerdeki "bu dönem N slot dolarsa" sayısı, kalma riski girdisi.
* Yol haritasının "bu dönem" girdisi de eşleştirmeden gelen yuvayı taşıyor —
  iki seçmeli iki ayrı yuvayı dolduruyor.

## Gerçek sitede (ENDE, 7. yarıyıl)

Önerilen program 9 dersten **10 derse**, 20.5 krediden **23.5 krediye** çıktı:
iki ayrı "5th Semester Elective" dersi (ECN 201E, BHB 201E) aynı programda —
önceden olanaksızdı. Durumun yeniden hesaplanması Pyodide'de 1,09 sn;
bitiş tahmini değişmedi.
