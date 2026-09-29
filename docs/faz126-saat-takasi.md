# Faz 126 — "Bu dönem alınırsa" satırı saat takasını hesaplıyor

Kullanıcı (28.09.2026): *"anadala öncelik verince BLG 223E yerine GEO 307E'yi
neden almıyor"*.

## Sorun

Yol haritasındaki "bu dönem alınırsa" satırı, kazancı dersin programa
**eklendiği** varsayımıyla ölçüyordu. Kullanıcının verisinde bu satır
"GEO 307E bu dönem alınırsa anadal 1 dönem erken biter" diyordu. Oysa
GEO 307E'nin tek şubesi programdaki BLG 223E ile aynı saatte (Salı
08:30); ikisi birlikte alınamaz. Satırın altındaki not da "Saat çakışması
bu bölümde hesaplanmamıştır" diyordu.

## Değişiklik

Adayın bütün şubeleri programdaki bir dersin bütün şubeleriyle çakışıyorsa
(kesin çakışma) harita, takas yapılmış programla yeniden kuruluyor. Satır,
eklemeye dayalı kazanç yerine **her programın net etkisini** yazıyor; bu
etki kazanç da olabilir, kayıp da. Ayrıca "X yerine dene" düğmesi
ekleniyor. Başlık da "bitişi değiştirecek ders" olarak değişti, çünkü bir
takas programlardan birini geciktirebiliyor.

## Kullanıcının verisinde

| Ayar | Satır |
|---|---|
| Birlikte en kısa | GEO 307E — programdaki BLG 223E ile aynı saattedir; onun yerine alınırsa anadal aynı, ÇAP 2 dönem geç biter |
| Anadala öncelik | BLG 223E — programdaki GEO 307E ile aynı saattedir; onun yerine alınırsa anadal 1 dönem geç, ÇAP 4 dönem erken biter |

Böylece kullanıcının sorusunun cevabı ekranda yazıyor: "birlikte" ayarında
takas anadalı öne çekmiyor, yalnızca ÇAP'ı geciktiriyor.

## Vitrinde bulunan uygulanamaz öneri

Vitrin öğrencisinde (HTAE + BLG ÇAP) satır şöyleydi: "GEO 341E alınırsa
anadal 2 dönem erken; yük aşılıyor — GEO 315E çıkarılırsa kazanç korunur".
Bu öneri uygulanamazdı: GEO 341E, programdaki BLG 252E ile kesin çakışıyor
ve GEO 315E çıkarılsa da ikisi birlikte alınamıyor. Artık takas
öneriliyor: BLG 252E yerine alınırsa anadal 2 dönem erken biter, ÇAP
değişmez. Ancak BLG 252E bir ÇAP dersi olduğundan takas, ÇAP yarıyıl kredi
tabanının altına düşürüyor ve bu açıkça yazılıyor.

Takas iki denetimden geçiyor; ikisi de "çıkarma" önerisindekiyle aynı:

* takas sonrası yükün sınırı aşıp aşmadığı;
* ÇAP tabanının bozulup bozulmadığı.

Takas varken uygulanamaz olan "çıkarma" düğmesi gösterilmiyor.

## Doğrulama

`tests/test_faz126_saat_takasi.py` 4 test içeriyor:

* kesin çakışmada takas ve etkisi;
* çakışma yokken takas yapılmaması;
* şubelerden biri çakışmıyorsa takas yapılmaması;
* arayüz metinleri.

3 mutasyonun 3'ü kırmızı. Satır kullanıcının verisiyle, yerel ve geçici bir
sunucuda tarayıcıda çizildi; konsolda hata yok.
