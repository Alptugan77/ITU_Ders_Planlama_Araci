# Faz 121 — Kaydedilebilir planlama yükü ve "neyle çakışıyor"

Kullanıcının kendi verisiyle yapılan inceleme (28.09.2026; HTAE anadal,
BLG ÇAP, 5. yarıyıl).

## Planlama yükü

GNO ≥ 3,00 olan öğrencide yönetmelik sınırı 40 krediye çıkıyor (MADDE 17/2
yalnızca GNO şartı koyuyor; 40 `kurallar.toml`'daki tavan). Harita her
dönemi bu sınıra kadar dolduruyordu: 2026-2027 Bahar'a 14 ders
(39,5 kredi), 2027-2028 Güz'e 29,5 kredi yerleştiriliyordu. Buna göre
hesaplanan bitiş gerçekçi değildi.

* `settings.yol_yuk` (0 = yönetmelik sınırı). Harita
  `min(yol_yuk, sınır)` ile kuruluyor, yani sınır aşılamaz; sınırın üstünde
  kaydedilen değer sınıra indiriliyor ve arayüz bunu yazıyor.
* Senaryoda denenen değer "X krediyi planlama yükü olarak kaydet" düğmesiyle
  kaydediliyor; "Yönetmelik sınırına dön" ile sıfırlanıyor
  (`/api/yolyuk`, doğrulama sunucuda: 1–60, tam ya da buçuklu).
* Kayıt yokken sınır 25'in üstündeyse harita, en yüksek yükle kurulduğunu
  ve dönemlerin gerçekçi olmayabileceğini yazıyor.
* Sayfadaki harita, "bu dönem alırsanız", kalma riski ve ÇAP seçenekleri aynı
  yükü kullanıyor. "Bu dönem" yük aşımı ise yine yönetmelik sınırına göre
  hesaplanıyor.
* Kullanıcının verisinde 22 kredi kaydedildiğinde anadal bitişi 9. yarıyıldan
  10. yarıyıla kayıyor. Gerçekçi yükle hesaplanan bitiş budur.

## "Neyle çakışıyor"

Kullanıcı: *"GEO 307E, GEO 403E ile ne çakışıyor"*. Harita GEO 307E'yi
2027-2028 Güz'den "saat çakışması" gerekçesiyle erteliyordu, ama neyle
çakıştığını söylemiyordu. Sebep: GEO 227E (FF, tekrar alınacak). İki dersin
de tek şubesi Salı 08:30–10:29'da. GEO 307E ile GEO 403E ise çakışmıyor.

Artık dönem kartında "GEO 307E (GEO 227E ile aynı saatte)" yazıyor
(`timeDeferredWith`). Yalnızca bütün şubeleri çakışan, yani kesinlikle
birlikte alınamayan dersler yazılıyor. Üçlü kombinasyondan doğan çakışmada
yalnızca "saat çakışması" deniyor.

## Doğrulama

`tests/test_faz121_planlama_yuku.py`: çakışan ders adıyla (şubelerinden
yalnızca biri çakışan ders yazılmıyor), ayar dosyası, sunucu doğrulaması,
harita yükü ve sınır, arayüz. 5 mutasyonun 5'i kırmızı. Vitrinde kaydet ve
sıfırla düğmeleri tarayıcıda denendi, konsolda hata yok.
