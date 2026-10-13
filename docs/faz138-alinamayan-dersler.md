# Faz 138 — Alınamayan dersler: kartta dersin adı

**Tarih:** 13.10.2026
**İstek:** "continue" (arayüz ve kullanım iyileştirmesine devam)

"Alınamayan dersler" görünümünde her kart yalnız ders kodunu ve bir
açıklamayı gösteriyordu:

* Dersin adı veride (`blockers[].name`) vardı ama yazılmıyordu. Öğrenci
  "BLG 336E"yi değil "Analysis of Algorithms II"yi tanır.
* "bu dönem açılmamış" grubundaki her kart "bu dönem şube açılmamıştır"
  diyordu, yani grubun etiketini kart sayısı kadar tekrar ediyordu.
* "izle" düğmesi metnin altına sarıyordu; kartların yüksekliği metnin
  uzunluğuna göre değişiyordu.

Kart artık: kod (ve iki ikinci program varsa program etiketi) ile "izle"
düğmesi aynı satırda, altında ders adı, altında açıklama. Açıklama yalnız
grubun etiketini tekrar ediyorsa yazılmıyor; "eksik: BLG 223E" gibi bilgi
taşıyan açıklamalar duruyor. Gizlenen metin motorun `ACILMAMIS` metniyle
birebir karşılaştırılıyor; motor metni değişirse açıklama yeniden görünür.

Görsel: `Claude outputs/f138-alinamayan-dersler-once-sonra.png`.
