# Faz 135 — Yeni simge; program resminde önizleme, tema ve telefon biçimi

**Tarih:** 13.10.2026
**İstek:** "also can you improve the icon and save as png part"

## Simge

Eski simge mürekkep zeminde bir cetvel ve 3×3 eşit kareydi. 48 px'te bir
tablo ya da takvim gibi okunuyordu, ders programı gibi değil. Yeni simge
programın kendi görüntüsü: üç gün sütunu, sütunlarda farklı boyda dersler.
Anadal ve ÇAP renginde bloklar, bir beyaz blok, iki boş saat. Köşeler
Faz 133'ün kuralına uyuyor (512'de 22px, yani blok köşesinin oranı).

Geometri tek yerde: `tools/simge_uret.py` `BLOKLAR`. PNG ve SVG ondan
üretiliyor. Program resminin köşesindeki küçük simge `ui.SIMGE_BLOKLAR`'dan
çiziliyor; `test_faz135` ikisinin ayrışmadığını denetliyor. Maskable
simge Android'in güvenli dairesinde kalıyor (Faz 130 testi).

## Program resmi (PNG)

| | önce | sonra |
|---|---|---|
| düğme | doğrudan indiriyordu, ne çıkacağı görülmüyordu | pencere: önizleme, sonra indir |
| tema | hep ekrandaki tema | Açık / Koyu seçilir |
| biçim | hep geniş (1100×~900) | Geniş veya Telefon (540 genişlik, dikey) |
| telefonda | yalnız indirme | destekleyen tarayıcıda "Paylaş" (WhatsApp, galeri) |
| bloklar | köşesiz, arka arkaya iki ders birleşik | 6px köşe, aralarında boşluk |
| çevrimiçi ders | zemini saydam, ızgara çizgileri içinden geçiyordu | kart zemini ve kesikli çerçeve |
| ızgara | her gün arasında dikey çizgi ve dış çerçeve | yalnız sönük saat çizgileri |
| renk açıklaması | yok, yeşilin ne olduğu bilinmiyordu | anadal / ÇAP / meşgul saat |
| ad | başlığın altında, uyarıyla aynı satırda | sağ üstte simgeyle |

Pencere telefonda "Telefon" biçimiyle, masaüstünde "Geniş" biçimiyle açılıyor.
Tema ilk açılışta ekrandaki tema. Seçim sayfa açık kaldıkça hatırlanıyor.

### Koyu resim neden açık çıkıyordu

Resim renkleri sayfanın jetonlarından ve ızgaradaki bloğun hesaplanmış
renginden alınıyor (ton merdiveni dahil). Başka temanın renklerini okumak
için `data-theme` bir anlığına değiştirilip renkler okunuyor. Faz 133'ün
blok renk geçişi açıkken `getComputedStyle` geçişin başındaki rengi
döndürüyordu, yani koyu resimde bloklar açık temanın rengindeydi. Ölçüm
boyunca kökte `gecissiz` sınıfı geçişi kapatıyor. Geri dönüş de geçişsiz
hesaplatılıyor, böylece ekrandaki bloklar bir kez renk değiştirmiyor.

### Gizlilik

Değişmedi: resimde yalnız ders, şube, saat ve derslik var. Not, transkript
ve GNO yok (Faz 58 testi). Pencere bunu yazıyor. "Paylaş" yalnız kullanıcı
bastığında çalışıyor; dosya tarayıcının paylaşım sayfasına gidiyor, bu
araç hiçbir yere göndermiyor.

Görseller: `Claude outputs/f135-*.png`.
