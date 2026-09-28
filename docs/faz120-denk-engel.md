# Faz 120 — Engel paneli dilekçesiz denk dersi görüyor

Kullanıcı (28.09.2026): *"denk derslerde hâlâ gözükmüyor önerilerde; BLG 317
bu dönem açılmamış gözüküyor ama yeni adıyla BBF 302 açılmış"*.

## Ölçüm (kullanıcının kendi verisiyle, gerçek katalog)

HTAE anadal ve BLG ÇAP, 5. yarıyıl, 37 geçilmiş ders.

* Resmî liste: BLG 317 ≡ BBF 302. ÇAP planında BLG 317E var; bu dönem
  BLG 317E'nin şubesi yok. BBF 302E'nin üç şubesi var, üçü de BLG'ye açık,
  yani dilekçe gerekmiyor.
* Faz 117'nin kuralı doğru çalışıyor, ama BBF 302E aday olmuyor. Sebebi:
  önşartı (BLG 252E, yeni kodu BBF 203E; ya da MUH 212 / YZV 201) geçilmemiş.
  BLG 317E'nin önşartı da aynı. BLG 252E için bu dönem yalnızca ek sınav
  şubesi açılmış.
* Engel paneli ise dersi "bu dönem açılmamış" (arz) diye gösteriyordu.
  Asıl engel önşart; denk dersin açık olduğu da hiçbir yerde yazmıyordu.

## Kural (`recommend.cap_blockers`, `kendi_programlar`)

Plandaki ders açılmamışsa ya da şubeleri programa kapalıysa, `candidates`
ile aynı kuralla dilekçesiz denk ders aranıyor: resmî, tek kaynaklı
denklik ve şubesi öğrencinin kendi programına (anadal, ÇAP ya da yandal)
açık.

* Denk açık ve önşartı tutuyorsa → `DENK_ACIK`. Bu bir engel değil, durum:
  "Alınamayan dersler" paneli bu satırı saymıyor. Öneri "X yerine" diyor.
* Denk açık ama önşartı eksikse → `ONSART` ("önşart eksik" grubu).
  Satır eksik dersi ve denk dersi yazıyor: "eksik: BLG 252E (yeni kodu
  BBF 203E) … — BLG 317E bu dönem açılmamıştır; resmî denkliği BBF 302E
  açık ve dilekçesiz alınabilir".
* Denk ders yalnızca başka bir programa açıksa (dilekçe gerekir) satır eskisi
  gibi kalıyor.

## Doğrulama

`tests/test_faz120_denk_engel.py` 5 test içeriyor: dört durum ve arayüz
geçişi. Kullanıcının verisiyle yeniden üretildi. 3 mutasyonun 2'si
kırmızı; kalan biri gereksiz bir şube süzgecini gösterdi ve süzgeç
kaldırıldı (`load_sections` aynı süzmeyi zaten yapıyor).
