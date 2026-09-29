# Faz 129 — Kullanılabilirlik: kısa üst çubuk, taban mesajının sebebi

**Tarih:** 29.09.2026
**İstek:** "geliştirmeye devam et lütfen ekleyebileceğin işe yarar şeyler
varsa ekler misin lütfen kullanılabilirliğini de arttır"

Uygulama kullanıcının kendi verisiyle (HTAE anadal + BLG ÇAP, 5. dönem)
telefon (390 px) ve masaüstü (1366 px) boyutlarında gezildi. İki sorun
ölçüldü.

## 1. Telefonda üst çubuk ekranın üçte birini kaplıyordu

Ad, Kılavuz/Tema düğmeleri, dönem satırı, durum satırı ("3871 açık şube ·
dönem yükü sınırı …") ve veri yaşı + "tazele" ayrı satırlardaydı. Uzun dönem
satırı ("HTAE + BLG ÇAP · 2026-2027 GÜZ") ad sütununu genişletip düğmeleri
alt satıra itiyordu. İçerik her görünümde 240 px'ten sonra başlıyordu.

Değişiklik (`@media (max-width:700px)`, yalnız kurulum bitmişse):

- Ad sütunu esnek (`flex:1 1 0`); Kılavuz/Tema aynı satırda, sağda.
- Durum satırı yalnız **Program** görünümünde; diğer görünümlerde o bilgi
  kendi bölümünde zaten var.
- Veri yaşı cümlesi ve "tazele" düğmesi aynı satırda.
- Dokunma hedefleri 44 px olarak kaldı.

| görünüm | önce | sonra |
|---|---|---|
| Dersler (telefon) | ~240 px | 125 px |
| Program (telefon) | ~240 px | 167 px |
| Masaüstü | 94 px | 94 px (değişmedi) |

Yatay taşma yok, sayfa hatası yok.

## 2. "Taban karşılanamıyor" mesajı yanlış sebebi sayıyordu

Kullanıcının verisinde üç önerinin üçü de "TABAN ✗" idi. Mesaj "ders arzı,
saat çakışması veya önşart nedeniyle" diyordu. Oysa bu dönem alınabilecek
BÜTÜN ÇAP dersleri (BLG 223E 3,5 + BLG 212E 3 + BLG 351E 1) 7,5 kredidir;
taban 9 krediyken hiçbir program tabanı karşılayamaz. Saat çakışmasının
bir etkisi yoktur.

- `tabanArzi()`: aday havuzundaki ikinci anadal derslerinin toplam kredisi.
  Aynı yuvanın denk dersi ayrıca sayılmaz. Aday havuzu önşartı, kredi
  eşiğini ve açık şubeyi zaten süzmüş durumdadır.
- Arz tabanın altındaysa mesaj bunu söyler, dersleri kredileriyle sayar
  ve açılmayan veya önşartı eksik dersler için "Alınamayan dersler"
  bölümünü gösterir.
- Arz yetiyorsa mesaj sebebi saat çakışması veya yük sınırı olarak
  daraltır (önşart zaten süzülmüştür).
- Danışman özetindeki taban dilekçesi arzı da yazar: "Bu dönem ikinci
  anadaldan alınabilecek derslerin tamamı 7.5 krediden ibarettir (BLG 223E,
  BLG 212E, BLG 351E)." Bu, taban indirimi başvurusunun en güçlü
  gerekçesidir.

## Testler

`tests/test_faz129_kullanilabilirlik.py` (5 test):

- CSS kuralları ve medya sorgusu;
- `tabanArzi` node ile çalıştırılarak: rol süzgeci, yuva tekilliği, boş
  ve kredisiz aday;
- mesajın iki dalı; eski üç ihtimalli cümlenin geri gelmemesi;
- dilekçe metni.

Mutasyon denetimi: 5 mutantın 5'i de kırmızı (rol süzgeci, yuva
tekilliği, arz karşılaştırması, esnek ad sütunu, kredisiz aday).
