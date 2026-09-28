# Faz 122 — Öncelik ayarı bu dönemin önerisinde; ÇAP tabanı saate bakıyor

Kullanıcı (28.09.2026): *"anadala öncelik verince BLG 223E yerine GEO 307E'yi
neden almıyor"*.

## Ölçüm (kullanıcının kendi verisi)

Salı 08:30–10:29 saatinde üç dersin tek şubesi var: GEO 227E (FF, tekrar),
GEO 307E ve BLG 223E (ÇAP, zincir başı). Üçü de yalnızca Güz'de açılıyor;
aynı saati paylaştıkları için üç ayrı Güz dönemi gerekiyor.

1. Öncelik ayarı (Faz 118) yalnızca gelecek dönemleri yerleştiriyordu. Bu
   dönemin önerisi ÇAP'a sabit +150 veriyordu (kritik yol +100, rol +50):
   BLG 223E 212 puan, GEO 307E 72 puan.
2. Puanı değiştirmek tek başına yetmedi: GEO 307E alındığında anadal yine
   9. yarıyılda bitiyor, ÇAP ise 8. yarıyıldan 10.'ya kayıyordu. Sebep
   haritanın **ÇAP tabanı** adımıydı: taban saate bakmadan BLG 223E ile
   dolduruluyordu. Oysa 2027-2028 Güz'de GEO 227E ve GEO 403E'nin tek
   saatleri BLG 223E ile çakışıyor, ve aynı dönemin öbür ÇAP dersleri
   (BLG 335E, 4901E, 317E) tabanı zaten dolduruyordu.

## Değişiklik

* `recommend.score_all(…, oncelik)`: "anadal" ayarında rol artısı (+50)
  anadal derslerine geçiyor ve ÇAP kritik yol artısı uygulanmıyor
  (bilgi olarak gerekçede kalıyor). ÇAP yarıyıl tabanı program aramasında
  yine zorunlu (yönerge).
* Harita, ÇAP tabanını iki kuralla deniyor:
  * eski kural: sıradaki ilk ÇAP dersleri;
  * saatli kural: sırada daha öndeki bir dersle kesin çakışmayan ÇAP
    dersleri önce; taban yine dolmuyorsa eski kural.

  Her iki kural da Faz 118 aramasına aday olarak giriyor
  (`priority.floorByTime`). Saatli kural tek başına kullanıldığında 383
  gerçek çiftin yaklaşık %3'ünde sonuç kötüleşiyordu; aday olarak eklenince
  hiçbir çiftte kötüleşmedi.
* "Bu dönem alınırsa": haritada saat çakışmasıyla ertelenen ders de aday
  oluyor. Örneğin GEO 307E'nin zinciri yok, ama bitişi o belirliyor.

## Sonuç

Kullanıcının verisi:

| Ayar | Bu dönemin önerisi | Anadal | ÇAP |
|---|---|---|---|
| Birlikte en kısa | BLG 223E | 9. yarıyıl | 8. yarıyıl |
| Anadala öncelik | GEO 307E | **8. yarıyıl** (planındaki) | 12. yarıyıl |

Takas iki yönde de ölçülü olarak görünüyor. "Birlikte" ayarında araç
"GEO 307E bu dönem alınırsa anadal 1 dönem erken biter", "anadal" ayarında
"BLG 223E alınırsa ÇAP 4 dönem erken biter" diyor.

Gerçek katalogda 383 anadal+ÇAP çiftinde, eskiye göre kötüleşme yok;
iyileşen çiftler:

| Ayar | 3. yarıyıl | 5. yarıyıl |
|---|---|---|
| "birlikte" | 13 | 10 |
| "anadal" | 34 | 19 |

## Doğrulama

`tests/test_faz122_oncelik_bu_donem.py`: puan kırılımı, saatli taban,
tabansız durumda ek kurulum olmaması, arayüz geçişi. 4 mutasyonun 4'ü
kırmızı.
