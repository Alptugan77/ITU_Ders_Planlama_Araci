# Faz 99 — İlerleme kartında dönem şeridi ve kalan yuvalar

Kullanıcı 25.09.2026: *"bir de ilerleme durumu kısmı biraz boş kaldı gibi
ona eklenebilecek iyi bir şey varsa ekler misin"*.

## Sorun

Kart yüzde ve sayı veriyordu ("%64.9 · kalan zorunlu 12") ama **hangi**
derslerin kaldığını ve planın neresinde olunduğunu söylemiyordu. Bu bilgi
planda zaten vardı (`plan_slot.term_no`).

## Değişiklik

* **Sunucu:** `ui._panel_donemleri` her panele `terms` (dönem başına
  tamamlanan/toplam yuva) ve `open` (açık yuvalar: kod, ad, dönem, zorunlu
  mu; havuz yuvası için OBS etiketi, ör. "TM Elective I") ekliyor.
  ÇAP/yandal planlarında `term_no` NULL: `terms` boş, dönem uydurulmuyor.
* **Kart:**
  * **Dönem şeridi:** her dönem bir çubuk. Tamamlanan dönem yeşil,
    bulunulan dönem çerçeveli, önceki dönemde açık yuva kalmışsa uyarı
    renginde ("geride").
  * **Önceki dönemlerden kalan N yuva** ve **bulunulan dönemin yuvaları**;
    ikisi de boşsa sıradaki dönemin yuvaları. ÇAP/yandal kartında "Kalan
    zorunlu dersler (N) · ayrıca M seçmeli yuva".
  * Ders çipine tıklanınca ekleme/şube penceresi açılıyor (`addDialog`).
    Bu dönemki programda seçili ders "✓" ile işaretli; seçim değişince
    kart yeniden çiziliyor. Bu dönem açılmamış ders tıklanamaz, ipucu
    nedenini söylüyor.
* "Geride" yalnız ANADAL kartında: `DATA.donem` anadal dönemi, ÇAP
  planıyla karşılaştırılamaz.
* Transkript yokken (ilerleme bilinmiyor) şerit ve liste çizilmiyor.

## Doğrulama

`tests/test_faz99_ilerleme_donemleri.py` (3 birim + vitrin uçtan uca). Altı
mutasyonun altısı da kırmızı: geride koşulu, bulunulan dönem, ✓ işareti,
tıklama bağlantısı, ÇAP'ta şerit uydurma, havuz etiketi.
